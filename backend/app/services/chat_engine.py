from typing import AsyncGenerator, Dict, List
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embeddings import search_chunks
from app.models.models import TranscriptSegment
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_context(chunks: List[Dict]) -> str:
    parts = []
    for chunk in chunks:
        text = chunk.get("text", "")
        start = chunk.get("start_seconds")
        if start is not None:
            minutes = int(start) // 60
            seconds = int(start) % 60
            parts.append(f"[{minutes}:{seconds:02d}] {text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


async def stream_answer(
    question: str,
    file_id: int,
    user_id: int,
    file_type: str,
    db: Session,
) -> AsyncGenerator[Dict, None]:
    """
    Perform RAG search and stream GPT-4 answer tokens.
    Yields dicts: {type: 'token'|'timestamp'|'error', content|value: ...}
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

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

    is_av = file_type in ("audio", "video")
    system_prompt = (
        "You are a helpful assistant. Answer questions based ONLY on the provided context. "
        "If the answer is not in the context, say so clearly. "
        + ("Context includes timestamps in [MM:SS] format." if is_av else "")
    )

    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    timestamp_ref = None
    if is_av and chunks:
        first_ts = chunks[0].get("start_seconds")
        if first_ts is not None:
            timestamp_ref = first_ts

    if timestamp_ref is not None:
        yield {"type": "timestamp", "value": timestamp_ref}

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
                yield {"type": "token", "content": delta.content}

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


async def summarize_file(
    file_id: int,
    user_id: int,
    db: Session,
) -> str:
    """
    Summarize the content of a file using its transcript segments (audio/video)
    or FAISS-indexed chunks (PDF). Cached by the caller.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.file_id == file_id)
        .order_by(TranscriptSegment.segment_index)
        .all()
    )

    if segments:
        context = " ".join(s.text for s in segments)
    else:
        chunks = search_chunks(
            query="summarize the main content",
            user_id=user_id,
            file_id=file_id,
            top_k=10,
        )
        context = " ".join(c["text"] for c in chunks)

    if not context.strip():
        return "No content available to summarize."

    context = context[:8000]

    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Summarize the following content concisely in 3-5 sentences.",
            },
            {"role": "user", "content": f"Content:\n{context}"},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or "Summary not available."
