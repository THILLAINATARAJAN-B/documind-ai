from typing import AsyncGenerator, Dict
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embeddings import search_chunks
from app.models.models import FileType, TranscriptSegment
import logging

logger = logging.getLogger(__name__)
settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

RAG_SYSTEM_PROMPT = """You are DocuMind AI, an expert assistant that answers questions strictly based on the provided context.
If the answer is not found in the context, say \"I could not find that information in the uploaded file.\"
Be concise and accurate. Do not hallucinate."""

AUDIO_SYSTEM_PROMPT = """You are DocuMind AI. You answer questions based on a transcript of an audio/video file.
When your answer references a specific moment in the transcript, always end your response with:
TIMESTAMP: <seconds>
where <seconds> is the start time (in seconds) of the most relevant segment. If no specific moment applies, omit this line.
Be concise and accurate."""


async def stream_answer(
    question: str,
    file_id: int,
    user_id: int,
    file_type: FileType,
    db: Session,
) -> AsyncGenerator[Dict, None]:
    """Stream GPT-4o answer using RAG. Yields dicts with type=token|timestamp|error."""

    try:
        context_chunks = search_chunks(query=question, user_id=user_id, file_id=file_id, top_k=5)
        context = "\n\n".join(context_chunks) if context_chunks else "No relevant context found."

        timestamp_map = {}
        if file_type in [FileType.audio, FileType.video]:
            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.file_id == file_id)
                .order_by(TranscriptSegment.segment_index)
                .all()
            )
            for seg in segments:
                timestamp_map[seg.text[:60]] = seg.start_seconds
            system_prompt = AUDIO_SYSTEM_PROMPT
        else:
            system_prompt = RAG_SYSTEM_PROMPT

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

        full_content = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
                yield {"type": "token", "content": delta.content}

        # Extract timestamp from response if audio/video
        if file_type in [FileType.audio, FileType.video]:
            if "TIMESTAMP:" in full_content:
                try:
                    ts_line = [line for line in full_content.split("\n") if "TIMESTAMP:" in line][0]
                    ts_value = float(ts_line.split("TIMESTAMP:")[1].strip())
                    yield {"type": "timestamp", "value": ts_value}
                except (ValueError, IndexError):
                    pass

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
        batch = file_chunks[i:i + batch_size]
        batch_text = "\n\n".join(batch)
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Summarize the following content concisely in 3-5 sentences."},
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
                {"role": "system", "content": "Combine these partial summaries into one cohesive summary."},
                {"role": "user", "content": combined},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        return final_resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Summarize reduce error: {e}")
        return "\n\n".join(partial_summaries)
