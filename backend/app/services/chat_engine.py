from typing import AsyncGenerator, Dict, List, Optional
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embeddings import search_chunks
from app.models.models import FileType, TranscriptSegment
import logging

logger = logging.getLogger(__name__)
settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

RAG_SYSTEM_PROMPT = """You are DocuMind AI, an assistant that answers questions based on provided document context.
Use the context below to answer. If the context contains relevant information, use it.
For follow-up questions like examples, elaborations, or clarifications — use the context to derive your answer.
Only say "I could not find that information in the uploaded file" if the topic is completely absent from the context.
Be helpful, concise, and accurate."""

AUDIO_SYSTEM_PROMPT = """You are DocuMind AI. You answer questions based on a transcript of an audio/video file.
Use the transcript context to answer fully. For follow-up questions or requests for examples, elaborate using what's in the transcript.
Only say "I could not find that information" if the topic is completely absent from the transcript.
Be helpful and concise. Do NOT include any TIMESTAMP text in your response."""


def _find_best_timestamp(
    answer_text: str,
    segments: List[TranscriptSegment],
    fallback_ts: float,
    question: str = "",
) -> float:
    if not segments or not answer_text:
        return fallback_ts

    answer_lower = answer_text.lower()
    question_lower = question.lower()

    STOPWORDS = {
        "the", "what", "is", "are", "about", "there", "any", "thing",
        "that", "this", "with", "from", "have", "been", "will", "was",
        "for", "can", "how", "does", "did", "its", "and", "not"
    }

    answer_words = [
        w.strip(".,;:!?()\"'")
        for w in answer_lower.split()
        if len(w.strip(".,;:!?()\"'")) > 4
    ]

    question_words = [
        w.strip(".,;:!?()\"'")
        for w in question_lower.split()
        if len(w.strip(".,;:!?()\"'")) > 2
        and w.strip(".,;:!?()\"'") not in STOPWORDS
    ]

    if not answer_words and not question_words:
        return fallback_ts

    scored: List[tuple] = []  # (score, start_seconds)

    for seg in segments:
        seg_lower = seg.text.lower()
        score = sum(1 for w in answer_words if w in seg_lower)
        score += sum(2 for w in question_words if w in seg_lower)
        if score > 0:
            scored.append((score, seg.start_seconds))

    if not scored:
        return fallback_ts

    max_score = max(s for s, _ in scored)

    # Among all segments within 80% of the top score, pick the earliest
    # This prefers where the topic is INTRODUCED over where it's elaborated
    threshold = max_score * 0.8
    candidates = [ts for score, ts in scored if score >= threshold]

    return min(candidates)  # earliest timestamp among top scorers


async def stream_answer(
    question: str,
    file_id: int,
    user_id: int,
    file_type: FileType,
    db: Session,
) -> AsyncGenerator[Dict, None]:
    """Stream GPT-4o answer using RAG. Yields dicts with type=token|timestamp|error."""

    try:
        chunk_results: List[Dict] = search_chunks(
            query=question, user_id=user_id, file_id=file_id, top_k=5
        )

        context_texts = [c["text"] for c in chunk_results] if chunk_results else []
        context = "\n\n".join(context_texts) if context_texts else "No relevant context found."

        # Fallback: start_seconds of the top FAISS chunk
        faiss_fallback_ts: float = 0.0
        if file_type in [FileType.audio, FileType.video] and chunk_results:
            for chunk in chunk_results:
                if "start_seconds" in chunk:
                    faiss_fallback_ts = chunk["start_seconds"]
                    break

        system_prompt = (
            AUDIO_SYSTEM_PROMPT
            if file_type in [FileType.audio, FileType.video]
            else RAG_SYSTEM_PROMPT
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ]

        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            stream=True,
            temperature=0.3,
            max_tokens=800,
        )

        # Stream tokens to frontend while collecting full answer
        full_answer = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_answer += delta.content
                yield {"type": "token", "content": delta.content}

        # After streaming completes, find the best timestamp
        # Pass question= so question keywords get 2x weight in scoring
        if file_type in [FileType.audio, FileType.video]:
            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.file_id == file_id)
                .order_by(TranscriptSegment.segment_index)
                .all()
            )
            best_ts = _find_best_timestamp(
                answer_text=full_answer,
                segments=segments,
                fallback_ts=faiss_fallback_ts,
                question=question,          # ← THIS WAS MISSING IN YOUR CODE
            )
            yield {"type": "timestamp", "value": best_ts}

    except RateLimitError:
        logger.error("OpenAI rate limit hit")
        yield {"type": "error", "content": "OpenAI rate limit reached. Please wait a moment and try again."}
    except APIConnectionError:
        logger.error("OpenAI connection error")
        yield {"type": "error", "content": "Could not connect to AI service. Please check your connection."}
    except APIError as e:
        logger.error(f"OpenAI API error: {e}")
        yield {"type": "error", "content": "AI service returned an error. Please try again."}
    except Exception as e:
        logger.error(f"Unexpected error in stream_answer: {e}")
        yield {"type": "error", "content": "An unexpected error occurred. Please try again."}


async def summarize_file(file_id: int, user_id: int, db: Session) -> str:
    """Map-reduce summarization over all chunks of a file."""
    from app.services.embeddings import _index_path
    import os
    import pickle

    path = _index_path(user_id)
    meta_file = os.path.join(path, "metadata.pkl")
    if not os.path.exists(meta_file):
        return "No content found for this file."

    with open(meta_file, "rb") as f:
        metadata = pickle.load(f)

    file_chunks = [m["text"] for m in metadata if m["file_id"] == file_id]
    if not file_chunks:
        return "No content found for this file."

    batch_size = 10
    partial_summaries = []
    for i in range(0, len(file_chunks), batch_size):
        batch = file_chunks[i : i + batch_size]
        batch_text = "\n\n".join(batch)
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following content concisely in 3-5 sentences.",
                    },
                    {"role": "user", "content": batch_text},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            partial_summaries.append(resp.choices[0].message.content)
        except Exception as e:
            logger.error(f"Summarize batch error: {e}")
            partial_summaries.append("[Summary unavailable for this section]")

    if len(partial_summaries) == 1:
        return partial_summaries[0]

    combined = "\n\n".join(partial_summaries)
    try:
        final_resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Combine these partial summaries into one cohesive summary.",
                },
                {"role": "user", "content": combined},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        return final_resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Summarize reduce error: {e}")
        return "\n\n".join(partial_summaries)