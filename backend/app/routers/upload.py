import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import User, File, FileType, TranscriptSegment
from app.schemas.file import FileResponse, TranscriptSegmentResponse, SummaryResponse
from app.services.pdf_processor import process_pdf
from app.services.audio_processor import process_audio_video
from app.services.embeddings import upsert_chunks, delete_user_file_index
from app.services.chat_engine import summarize_file
from app.core.redis_client import get_redis
from typing import List
from .deps import get_current_user_dep

router = APIRouter(prefix="/upload", tags=["Upload"])
settings = get_settings()

ALLOWED_PDF = {"application/pdf"}
ALLOWED_AV = {"audio/mpeg", "audio/wav", "video/mp4", "audio/mp4", "video/quicktime", "audio/x-wav"}


@router.post("/pdf", response_model=FileResponse)
async def upload_pdf(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_PDF:
        raise HTTPException(400, "Only PDF files are allowed")
    return await _save_and_process(file, FileType.pdf, current_user, db)


@router.post("/audio", response_model=FileResponse)
async def upload_audio_video(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_AV:
        raise HTTPException(400, "Only audio/video files are allowed (MP3, WAV, MP4)")
    return await _save_and_process(file, FileType.audio, current_user, db)


async def _save_and_process(
    file: UploadFile, file_type: FileType, user: User, db: Session
) -> FileResponse:
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    contents = await file.read()
    if len(contents) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.max_file_size_mb}MB limit")

    with open(file_path, "wb") as f:
        f.write(contents)

    db_file = File(
        user_id=user.id,
        filename=unique_name,
        original_filename=file.filename,
        file_type=file_type,
        file_path=file_path,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    if file_type == FileType.pdf:
        chunks = process_pdf(file_path)
        upsert_chunks(chunks, user_id=user.id, file_id=db_file.id)
    else:
        segments, chunks = await process_audio_video(file_path)
        for i, seg in enumerate(segments):
            ts = TranscriptSegment(
                file_id=db_file.id,
                text=seg["text"],
                start_seconds=seg["start"],
                end_seconds=seg["end"],
                segment_index=i,
            )
            db.add(ts)
        db.commit()
        upsert_chunks(chunks, user_id=user.id, file_id=db_file.id)

    return db_file


@router.get("/files", response_model=List[FileResponse])
def list_files(
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    return db.query(File).filter(File.user_id == current_user.id).all()


@router.get("/files/{file_id}/segments", response_model=List[TranscriptSegmentResponse])
def get_segments(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    db_file = db.query(File).filter(File.id == file_id, File.user_id == current_user.id).first()
    if not db_file:
        raise HTTPException(404, "File not found")
    return db.query(TranscriptSegment).filter(TranscriptSegment.file_id == file_id).order_by(TranscriptSegment.segment_index).all()


@router.get("/files/{file_id}/summary", response_model=SummaryResponse)
async def get_summary(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    db_file = db.query(File).filter(File.id == file_id, File.user_id == current_user.id).first()
    if not db_file:
        raise HTTPException(404, "File not found")

    cache_key = f"summary:{file_id}"
    cached = redis.get(cache_key)
    if cached:
        return SummaryResponse(file_id=file_id, summary=cached, cached=True)

    summary = await summarize_file(file_id=file_id, user_id=current_user.id, db=db)
    redis.setex(cache_key, 3600, summary)
    return SummaryResponse(file_id=file_id, summary=summary, cached=False)


@router.delete("/files/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    db_file = db.query(File).filter(File.id == file_id, File.user_id == current_user.id).first()
    if not db_file:
        raise HTTPException(404, "File not found")
    if os.path.exists(db_file.file_path):
        os.remove(db_file.file_path)
    delete_user_file_index(user_id=current_user.id, file_id=file_id)
    db.delete(db_file)
    db.commit()