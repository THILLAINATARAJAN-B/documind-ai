import os
import tempfile
from typing import List, Dict, Tuple
from openai import AsyncOpenAI
from app.core.config import get_settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)


async def process_audio_video(file_path: str) -> Tuple[List[Dict], List[str]]:
    """
    Transcribe audio/video using Whisper with word-level timestamps.
    Returns (segments, text_chunks).
    segments = [{"text": str, "start": float, "end": float}, ...]
    text_chunks = list of text chunks for FAISS embedding
    """
    audio_path = file_path

    # If video file, extract audio track using ffmpeg
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".mp4", ".mov", ".avi", ".mkv"]:
        audio_path = file_path.replace(ext, "_audio.mp3")
        os.system(f'ffmpeg -i "{file_path}" -q:a 0 -map a "{audio_path}" -y -loglevel quiet')

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

    segments = []
    for seg in response.segments:
        segments.append({
            "text": seg.text.strip(),
            "start": seg.start,
            "end": seg.end,
        })

    # Build full transcript and chunk it for embeddings
    full_transcript = " ".join(s["text"] for s in segments)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(full_transcript)

    return segments, chunks