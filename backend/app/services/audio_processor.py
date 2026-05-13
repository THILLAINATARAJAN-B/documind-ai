import os
from typing import List, Dict, Tuple
from openai import AsyncOpenAI
from app.core.config import get_settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)


async def process_audio_video(file_path: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Transcribe audio/video using Whisper with segment-level timestamps.

    Returns:
        segments       – [{text, start, end}, ...]    stored in DB as TranscriptSegment rows
        chunks_with_ts – [{text, start_seconds}, ...] stored in FAISS with accurate timestamps

    Timestamp mapping strategy (position-based):
        1. Build full_transcript by joining segment texts with spaces.
        2. Record the character-offset range [char_start, char_end) for each segment.
        3. Split full_transcript with LangChain → raw_chunks.
        4. For each chunk, find its start position in full_transcript via str.find().
        5. Walk segment offsets to find which segment owns that position → correct timestamp.
    """
    audio_path = file_path

    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".mp4", ".mov", ".avi", ".mkv"]:
        audio_path = file_path.replace(ext, "_audio.mp3")
        os.system(
            f'ffmpeg -i "{file_path}" -q:a 0 -map a "{audio_path}" -y -loglevel quiet'
        )

    with open(audio_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    if audio_path != file_path and os.path.exists(audio_path):
        os.remove(audio_path)

    segments = []
    for seg in response.segments:
        segments.append(
            {
                "text": seg.text.strip(),
                "start": seg.start,
                "end": seg.end,
            }
        )

    # ── Build full transcript + segment character-offset map ──────────────────
    # We join with a single space so positions are deterministic.
    parts = []
    seg_char_ranges = []   # [(char_start, char_end, start_seconds), ...]
    cursor = 0

    for seg in segments:
        text = seg["text"]
        seg_char_ranges.append((cursor, cursor + len(text), seg["start"]))
        parts.append(text)
        cursor += len(text) + 1  # +1 for the space separator

    full_transcript = " ".join(parts)

    # ── Split into overlapping chunks ─────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    raw_chunks = splitter.split_text(full_transcript)

    # ── Map each chunk → timestamp via character position ────────────────────
    chunks_with_ts: List[Dict] = []
    search_start = 0  # optimise: each chunk starts at or after the previous one

    for chunk_text in raw_chunks:
        # Find where this chunk sits in full_transcript
        pos = full_transcript.find(chunk_text, search_start)
        if pos == -1:
            # Fallback: search from beginning (handles overlap edge cases)
            pos = full_transcript.find(chunk_text)
        if pos == -1:
            # Last resort: use previous chunk's timestamp
            prev_ts = chunks_with_ts[-1]["start_seconds"] if chunks_with_ts else 0.0
            chunks_with_ts.append({"text": chunk_text, "start_seconds": prev_ts})
            continue

        # Find which segment owns character position `pos`
        matched_ts = 0.0
        for (cs, ce, ts) in seg_char_ranges:
            if cs <= pos < ce:
                matched_ts = ts
                break
            if cs > pos:
                # pos falls in the space between two segments → use next segment
                matched_ts = ts
                break

        chunks_with_ts.append({"text": chunk_text, "start_seconds": matched_ts})
        search_start = max(0, pos - 50)  # allow slight overlap backtrack

    return segments, chunks_with_ts