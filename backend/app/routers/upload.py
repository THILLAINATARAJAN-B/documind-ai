import os
import mimetypes
import uuid
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
}


@router.post("/pdf", response_model=FileResponse)
async def upload_pdf(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_PDF:
        raise HTTPException(400, "Only PDF files are allowed")

    return await _save_and_process(
        file=file,
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
    if file.content_type not in ALLOWED_AV:
        raise HTTPException(
            400,
            "Only audio/video files are allowed (MP3, WAV, MP4)",
        )

    return await _save_and_process(
        file=file,
        file_type=FileType.audio,
        user=current_user,
        db=db,
    )


async def _save_and_process(
    file: UploadFile,
    file_type: FileType,
    user: User,
    db: Session,
) -> FileResponse:

    os.makedirs(settings.upload_dir, exist_ok=True)

    # ── 1. Read & validate file size BEFORE touching disk or DB ──────────────
    contents = await file.read()

    if len(contents) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            400,
            f"File exceeds {settings.max_file_size_mb}MB limit",
        )

    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    # ── 2. Write file to disk ─────────────────────────────────────────────────
    with open(file_path, "wb") as f:
        f.write(contents)

    # ── 3. DB + FAISS inside a try/except — rollback everything on failure ────
    db_file = None
    try:
        db_file = File(
            user_id=user.id,
            filename=unique_name,
            original_filename=file.filename,
            file_type=file_type,
            file_path=file_path,
        )
        db.add(db_file)
        db.flush()  # gets db_file.id without committing yet

        # ── PDF PROCESSING ────────────────────────────────────────────────────
        if file_type == FileType.pdf:
            chunks = process_pdf(file_path)
            upsert_chunks(
                chunks,
                user_id=user.id,
                file_id=db_file.id,
            )

        # ── AUDIO / VIDEO PROCESSING ──────────────────────────────────────────
        else:
            segments, chunks_with_ts = await process_audio_video(file_path)

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

    except Exception as exc:
        # Roll back DB — no orphaned file row
        db.rollback()
        # Remove the file from disk — no orphaned file on disk
        if os.path.exists(file_path):
            os.remove(file_path)
        # Clean up any partial FAISS write for this file_id
        if db_file and db_file.id:
            try:
                delete_user_file_index(user_id=user.id, file_id=db_file.id)
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(exc)}",
        )

    return db_file


@router.get("/files", response_model=List[FileResponse])
def list_files(
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    return (
        db.query(File)
        .filter(File.user_id == current_user.id)
        .order_by(File.uploaded_at.desc())
        .all()
    )


@router.get("/files/{file_id}/stream", response_model=None)
def stream_media(
    file_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Serve audio/video file for playback.
    JWT passed via ?token= because <audio>/<video> tags
    cannot attach Authorization headers.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    payload = decode_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = (
        db.query(User)
        .filter(User.id == int(user_id))
        .first()
    )

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    db_file = (
        db.query(File)
        .filter(
            File.id == file_id,
            File.user_id == user.id,
        )
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
        .filter(
            File.id == file_id,
            File.user_id == current_user.id,
        )
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


@router.get(
    "/files/{file_id}/summary",
    response_model=SummaryResponse,
)
async def get_summary(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    db_file = (
        db.query(File)
        .filter(
            File.id == file_id,
            File.user_id == current_user.id,
        )
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
        .filter(
            File.id == file_id,
            File.user_id == current_user.id,
        )
        .first()
    )

    if not db_file:
        raise HTTPException(404, "File not found")

    # 1. Remove FAISS embeddings first (no API calls — uses reconstruct)
    delete_user_file_index(
        user_id=current_user.id,
        file_id=file_id,
    )

    # 2. Invalidate summary cache
    if redis:
        redis.delete(f"summary:{file_id}")

    # 3. Remove physical file from disk
    if os.path.exists(db_file.file_path):
        os.remove(db_file.file_path)

    # 4. DB delete cascades TranscriptSegments and ChatMessages via FK
    db.delete(db_file)
    db.commit()