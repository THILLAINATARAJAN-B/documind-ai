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
        segments       – [{text, start, end}, ...]   → stored in DB (TranscriptSegment rows)
        chunks_with_ts – [{text, start_seconds}, ...]→ stored in FAISS with correct timestamps

    Each FAISS chunk carries the start_seconds of the FIRST Whisper segment
    whose text prefix appears inside that chunk, so timestamp lookup is accurate.
    """
    audio_path = file_path

    # If video file, extract audio track using ffmpeg
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

    # Clean up extracted audio if we created it
    if audio_path != file_path and os.path.exists(audio_path):
        os.remove(audio_path)

    # Build segments list for DB storage
    segments = []
    for seg in response.segments:
        segments.append(
            {
                "text": seg.text.strip(),
                "start": seg.start,
                "end": seg.end,
            }
        )

    # Build full transcript and split into overlapping chunks for FAISS
    full_transcript = " ".join(s["text"] for s in segments)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    raw_chunks = splitter.split_text(full_transcript)

    # For each LangChain chunk, find the timestamp of the FIRST Whisper segment
    # whose text appears inside the chunk. This is the correct audio seek point.
    #
    # WHY THIS FIX IS NEEDED:
    #   segments = 31 items (one per Whisper timestamp)
    #   raw_chunks = ~6 items (LangChain merges many segments into each chunk)
    #   Old code: start_seconds_list[i] = segments[i]["start"]
    #             → chunk[0] got 0:00, chunk[1] got 0:06 (WRONG — segment index != chunk index)
    #   New code: match chunk text back to segment text → correct timestamp every time
    chunks_with_ts: List[Dict] = []
    for chunk_text in raw_chunks:
        matched_start = 0.0  # fallback: start of file if no match found
        for seg in segments:
            # Use first 30 chars of segment as a fingerprint
            # (handles minor whitespace differences from the text splitter)
            seg_prefix = seg["text"][:30].strip()
            if seg_prefix and seg_prefix in chunk_text:
                matched_start = seg["start"]
                break
        chunks_with_ts.append({"text": chunk_text, "start_seconds": matched_start})

    return segments, chunks_with_ts