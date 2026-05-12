from typing import AsyncGenerator, Dict
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embeddings import search_chunks
from app.models.models import FileType, TranscriptSegment

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

RAG_SYSTEM_PROMPT = """You are DocuMind AI, an expert assistant that answers questions strictly based on the provided context.
If the answer is not found in the context, say "I could not find that information in the uploaded file."
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
    """Stream GPT-4o answer using RAG. Yields dicts with type=token or type=timestamp."""

    context_chunks = search_chunks(query=question, user_id=user_id, file_id=file_id, top_k=5)
    context = "\n\n".join(context_chunks) if context_chunks else "No relevant context found."

    # For audio/video, also send raw segments for timestamp matching
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
                ts_line = [l for l in full_content.split("\n") if "TIMESTAMP:" in l][0]
                ts_value = float(ts_line.split("TIMESTAMP:")[1].strip())
                yield {"type": "timestamp", "value": ts_value}
            except (ValueError, IndexError):
                pass


async def summarize_file(file_id: int, user_id: int, db: Session) -> str:
    """Map-reduce summarization over all chunks of a file."""
    from app.services.embeddings import _index_path
    import os, pickle

    path = _index_path(user_id)
    meta_file = os.path.join(path, "metadata.pkl")
    if not os.path.exists(meta_file):
        return "No content found for this file."

    with open(meta_file, "rb") as f:
        metadata = pickle.load(f)

    file_chunks = [m["text"] for m in metadata if m["file_id"] == file_id]
    if not file_chunks:
        return "No content found for this file."

    # Summarize in batches of 10 chunks
    batch_size = 10
    partial_summaries = []
    for i in range(0, len(file_chunks), batch_size):
        batch = file_chunks[i:i + batch_size]
        batch_text = "\n\n".join(batch)
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

    if len(partial_summaries) == 1:
        return partial_summaries[0]

    # Final reduce step
    combined = "\n\n".join(partial_summaries)
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