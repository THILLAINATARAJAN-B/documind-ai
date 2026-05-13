import os
import mimetypes
import uuid
import struct
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File as FastAPIFile,
    Query,
)
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import decode_token

from app.models.models import (
    User,
    File,
    FileType,
    TranscriptSegment,
)

from app.schemas.file import (
    FileResponse,
    TranscriptSegmentResponse,
    SummaryResponse,
)

from app.services.audio_processor import process_audio_video
from app.services.chat_engine import summarize_file
from app.services.embeddings import (
    upsert_chunks,
    delete_user_file_index,
)
from app.services.pdf_processor import process_pdf

from .deps import get_current_user_dep

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])
settings = get_settings()

ALLOWED_PDF = {"application/pdf"}

ALLOWED_AV = {
    "audio/mpeg",
    "audio/wav",
    "video/mp4",
    "audio/mp4",
    "video/quicktime",
    "audio/x-wav",
    "audio/x-m4a",
}

# Magic bytes: (offset, bytes_to_match, description)
MAGIC_PDF = [(0, b"%PDF", "PDF")]

MAGIC_AV = [
    (0,  b"ID3",               "MP3 ID3"),
    (0,  b"\xff\xfb",          "MP3"),
    (0,  b"\xff\xf3",          "MP3"),
    (0,  b"\xff\xf2",          "MP3"),
    (0,  b"RIFF",              "WAV/RIFF"),      # WAV — also check offset 8
    (4,  b"ftyp",              "MP4/M4A"),       # MP4 — bytes 4-7
    (0,  b"\x1aE\xdf\xa3",    "WebM/MKV"),
    (0,  b"OggS",              "OGG"),
]


def _validate_magic_bytes(contents: bytes, allowed_magic: list) -> bool:
    """Return True if file contents match at least one magic signature."""
    for offset, signature, _ in allowed_magic:
        end = offset + len(signature)
        if len(contents) >= end and contents[offset:end] == signature:
            return True

    # Special case: WAV needs "RIFF" at 0 AND "WAVE" at offset 8
    if len(contents) >= 12:
        if contents[0:4] == b"RIFF" and contents[8:12] == b"WAVE":
            return True

    return False


def _sanitize_filename(filename: str) -> str:
    """Strip path traversal characters from filename."""
    return os.path.basename(filename).strip()


@router.post("/pdf", response_model=FileResponse)
async def upload_pdf(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    # 1. Content-type header check
    if file.content_type not in ALLOWED_PDF:
        raise HTTPException(400, "Only PDF files are allowed")

    contents = await file.read()

    # 2. Size check
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_file_size_mb}MB limit")

    # 3. Magic-byte check — prevent renamed executables
    if not _validate_magic_bytes(contents, MAGIC_PDF):
        raise HTTPException(400, "File content does not match PDF format")

    return await _save_and_process(
        file=file,
        contents=contents,
        file_type=FileType.pdf,
        user=current_user,
        db=db,
    )


@router.post("/audio", response_model=FileResponse)
async def upload_audio_video(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    # 1. Content-type header check
    if file.content_type not in ALLOWED_AV:
        raise HTTPException(
            400,
            "Only audio/video files are allowed (MP3, WAV, MP4, M4A)",
        )

    contents = await file.read()

    # 2. Size check
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_file_size_mb}MB limit")

    # 3. Magic-byte check
    if not _validate_magic_bytes(contents, MAGIC_AV):
        raise HTTPException(400, "File content does not match audio/video format")

    return await _save_and_process(
        file=file,
        contents=contents,
        file_type=FileType.audio,
        user=current_user,
        db=db,
    )


async def _save_and_process(
    file: UploadFile,
    contents: bytes,
    file_type: FileType,
    user: User,
    db: Session,
) -> FileResponse:

    os.makedirs(settings.upload_dir, exist_ok=True)

    safe_name = _sanitize_filename(file.filename or "upload")
    ext = os.path.splitext(safe_name)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    file_size_mb = len(contents) / (1024 * 1024)
    logger.info(
        "Upload started | user=%s | file=%s | size=%.2fMB | type=%s",
        user.id, safe_name, file_size_mb, file_type.value,
    )

    # ── Write file to disk ────────────────────────────────────────────────────
    with open(file_path, "wb") as f:
        f.write(contents)

    # ── DB + FAISS inside try/except — rollback everything on failure ─────────
    db_file = None
    try:
        db_file = File(
            user_id=user.id,
            filename=unique_name,
            original_filename=safe_name,
            file_type=file_type,
            file_path=file_path,
        )
        db.add(db_file)
        db.flush()  # gets db_file.id without committing

        logger.info("Processing file_id=%s for user=%s", db_file.id, user.id)

        # ── PDF ───────────────────────────────────────────────────────────────
        if file_type == FileType.pdf:
            chunks = process_pdf(file_path)
            logger.info("PDF chunked into %d chunks", len(chunks))
            upsert_chunks(chunks, user_id=user.id, file_id=db_file.id)

        # ── AUDIO / VIDEO ─────────────────────────────────────────────────────
        else:
            logger.info("Starting Whisper transcription for file_id=%s", db_file.id)
            segments, chunks_with_ts = await process_audio_video(file_path)
            logger.info(
                "Transcription done: %d segments, %d chunks",
                len(segments), len(chunks_with_ts),
            )

            for i, seg in enumerate(segments):
                ts = TranscriptSegment(
                    file_id=db_file.id,
                    text=seg["text"],
                    start_seconds=seg["start"],
                    end_seconds=seg["end"],
                    segment_index=i,
                )
                db.add(ts)

            chunk_texts = [c["text"] for c in chunks_with_ts]
            start_seconds_list = [c["start_seconds"] for c in chunks_with_ts]

            upsert_chunks(
                chunk_texts,
                user_id=user.id,
                file_id=db_file.id,
                start_seconds_list=start_seconds_list,
            )

        # ── Commit ONLY after both DB rows and FAISS are written ──────────────
        db.commit()
        db.refresh(db_file)
        logger.info("Upload complete: file_id=%s", db_file.id)

    except Exception as exc:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        if db_file and db_file.id:
            try:
                delete_user_file_index(user_id=user.id, file_id=db_file.id)
            except Exception:
                pass
        logger.error("Upload failed for user=%s: %s", user.id, str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(exc)}")

    return db_file


@router.get("/files", response_model=List[FileResponse])
def list_files(
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return (
        db.query(File)
        .filter(File.user_id == current_user.id)
        .order_by(File.uploaded_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/files/{file_id}/stream", response_model=None)
def stream_media(
    file_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    payload = decode_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    db_file = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == user.id)
        .first()
    )

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    mime_type, _ = mimetypes.guess_type(db_file.file_path)

    return FastAPIFileResponse(
        path=db_file.file_path,
        media_type=mime_type or "application/octet-stream",
        filename=db_file.original_filename,
    )


@router.get(
    "/files/{file_id}/segments",
    response_model=List[TranscriptSegmentResponse],
)
def get_segments(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    db_file = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )

    if not db_file:
        raise HTTPException(404, "File not found")

    return (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.file_id == file_id)
        .order_by(TranscriptSegment.segment_index)
        .all()
    )


@router.get("/files/{file_id}/summary", response_model=SummaryResponse)
async def get_summary(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    db_file = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )

    if not db_file:
        raise HTTPException(404, "File not found")

    cache_key = f"summary:{file_id}"
    cached = redis.get(cache_key) if redis else None

    if cached:
        return SummaryResponse(file_id=file_id, summary=cached, cached=True)

    summary = await summarize_file(
        file_id=file_id,
        user_id=current_user.id,
        db=db,
    )

    if redis:
        redis.setex(cache_key, 3600, summary)

    return SummaryResponse(file_id=file_id, summary=summary, cached=False)


@router.delete("/files/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    db_file = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )

    if not db_file:
        raise HTTPException(404, "File not found")

    # 1. Remove FAISS embeddings (no OpenAI calls)
    delete_user_file_index(user_id=current_user.id, file_id=file_id)

    # 2. Invalidate summary cache
    if redis:
        redis.delete(f"summary:{file_id}")

    # 3. Remove physical file
    if os.path.exists(db_file.file_path):
        os.remove(db_file.file_path)

    # 4. DB delete (cascades TranscriptSegments via FK)
    db.delete(db_file)
    db.commit()
    logger.info("Deleted file_id=%s for user=%s", file_id, current_user.id)