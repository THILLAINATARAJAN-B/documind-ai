from typing import AsyncGenerator, Dict, List
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embeddings import search_chunks
from app.models.models import TranscriptSegment
import logging
import re

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level client so it can be patched in tests
client = AsyncOpenAI(api_key=settings.openai_api_key)

_TIMESTAMP_RE = re.compile(r"TIMESTAMP:\s*([\d.]+)")


def _build_context(chunks: List[Dict]) -> str:
    parts = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            text = chunk.get("text", "")
            start = chunk.get("start_seconds")
            if start is not None:
                minutes = int(start) // 60
                seconds = int(start) % 60
                parts.append(f"[{minutes}:{seconds:02d}] {text}")
            else:
                parts.append(text)
        else:
            # Plain string chunk (fallback)
            parts.append(str(chunk))
    return "\n\n".join(parts)


async def stream_answer(
    question: str,
    file_id: int,
    user_id: int,
    file_type,
    db: Session,
) -> AsyncGenerator[Dict, None]:
    """
    Perform RAG search and stream GPT-4 answer tokens.
    Yields dicts: {type: 'token'|'timestamp'|'error', content|value: ...}

    Timestamp detection:
    - Primary: if first chunk has start_seconds, emit before streaming.
    - Secondary: inline TIMESTAMP: <float> markers in GPT output (e.g. audio).
    """
    try:
        chunks = search_chunks(
            query=question,
            user_id=user_id,
            file_id=file_id,
            top_k=5,
        )
    except Exception as e:
        logger.error("FAISS search failed: %s", e, exc_info=True)
        yield {"type": "error", "content": "Failed to search document. Please try again."}
        return

    if not chunks:
        yield {"type": "token", "content": "I couldn't find relevant content in the uploaded file to answer your question."}
        return

    context = _build_context(chunks)

    file_type_str = file_type.value if hasattr(file_type, "value") else str(file_type)
    is_av = file_type_str in ("audio", "video")

    system_prompt = (
        "You are a helpful assistant. Answer questions based ONLY on the provided context. "
        "If the answer is not in the context, say so clearly. "
        + ("Context includes timestamps in [MM:SS] format. When referencing a moment, output TIMESTAMP: <seconds> on its own line." if is_av else "")
    )

    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    # Primary timestamp from chunk metadata
    if is_av and chunks:
        first_chunk = chunks[0]
        first_ts = first_chunk.get("start_seconds") if isinstance(first_chunk, dict) else None
        if first_ts is not None:
            yield {"type": "timestamp", "value": first_ts}

    try:
        stream = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            temperature=0.2,
        )

        async for event in stream:
            delta = event.choices[0].delta
            if delta.content:
                content = delta.content
                # Secondary: parse inline TIMESTAMP markers from GPT output
                if is_av:
                    lines = content.split("\n")
                    for line in lines:
                        m = _TIMESTAMP_RE.search(line)
                        if m:
                            try:
                                ts_val = float(m.group(1))
                                yield {"type": "timestamp", "value": ts_val}
                            except ValueError:
                                pass
                        else:
                            if line:
                                yield {"type": "token", "content": line}
                else:
                    yield {"type": "token", "content": content}

    except RateLimitError:
        logger.warning("OpenAI rate limit hit for user=%s", user_id)
        yield {"type": "error", "content": "OpenAI rate limit reached. Please wait a moment and try again."}

    except APIConnectionError as e:
        logger.error("OpenAI connection error: %s", e)
        yield {"type": "error", "content": "Could not connect to OpenAI. Check your internet connection."}

    except APIError as e:
        logger.error("OpenAI API error: %s", e, exc_info=True)
        yield {"type": "error", "content": f"OpenAI API error: {e.message}"}

    except Exception as e:
        logger.error("Unexpected error in stream_answer: %s", e, exc_info=True)
        yield {"type": "error", "content": "An unexpected error occurred. Please try again."}


# Batch size for multi-batch summarisation
_SUMMARISE_BATCH = 10


async def summarize_file(
    file_id: int,
    user_id: int,
    db: Session,
) -> str:
    """
    Summarize file content.
    - For audio/video: use DB transcript segments.
    - For PDF: use FAISS-indexed chunks.
    Supports multi-batch map-reduce for large files.
    Cached by the caller.
    """
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.file_id == file_id)
        .order_by(TranscriptSegment.segment_index)
        .all()
    )

    if segments:
        all_chunks = [s.text for s in segments]
    else:
        raw = search_chunks(
            query="summarize the main content",
            user_id=user_id,
            file_id=file_id,
            top_k=50,
        )
        all_chunks = [c["text"] if isinstance(c, dict) else c for c in raw]

    if not all_chunks or not " ".join(all_chunks).strip():
        return "No content available to summarize."

    # ── Map phase: summarise each batch ────────────────────────────────────────
    batch_summaries: List[str] = []
    for i in range(0, len(all_chunks), _SUMMARISE_BATCH):
        batch = all_chunks[i : i + _SUMMARISE_BATCH]
        context = " ".join(batch)[:8000]
        resp = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Summarize the following content concisely in 2-3 sentences.",
                },
                {"role": "user", "content": f"Content:\n{context}"},
            ],
            temperature=0.3,
        )
        batch_summaries.append(resp.choices[0].message.content or "")

    # ── Reduce phase: if only one batch, return directly ───────────────────────
    if len(batch_summaries) == 1:
        return batch_summaries[0] or "Summary not available."

    # Multiple batches → reduce to final summary
    combined = "\n\n".join(batch_summaries)[:8000]
    final_resp = await client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Given several partial summaries, write one final concise summary in 3-5 sentences.",
            },
            {"role": "user", "content": f"Partial summaries:\n{combined}"},
        ],
        temperature=0.3,
    )
    return final_resp.choices[0].message.content or "Summary not available."
