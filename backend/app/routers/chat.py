from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, File, ChatSession, ChatMessage, MessageRole
from app.schemas.chat import AskRequest, ChatMessageResponse
from app.services.chat_engine import stream_answer
from app.core.redis_client import get_redis
from app.core.config import get_settings
from .deps import get_current_user_dep
from typing import List
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])
settings = get_settings()


@router.post("/ask")
async def ask_question(
    payload: AskRequest,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    db_file = db.query(File).filter(
        File.id == payload.file_id, File.user_id == current_user.id
    ).first()
    if not db_file:
        raise HTTPException(404, "File not found")

    # Configurable rate limiting via settings
    redis = get_redis()
    if redis is not None:
        rate_key = f"rate:{current_user.id}"
        count = redis.incr(rate_key)
        if count == 1:
            redis.expire(rate_key, 60)
        if count > settings.rate_limit_per_minute:
            raise HTTPException(
                429,
                f"Rate limit exceeded ({settings.rate_limit_per_minute} req/min). Try again in a minute.",
            )

    # Get or create chat session
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == current_user.id,
        ).first()
        if not session:
            raise HTTPException(404, "Session not found")
    else:
        session = ChatSession(user_id=current_user.id)
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        file_id=payload.file_id,
        role=MessageRole.user,
        content=payload.question,
    )
    db.add(user_msg)
    db.commit()

    async def event_generator():
        full_response = ""
        timestamp_ref = None

        try:
            yield f"data: {json.dumps({'session_id': session.id, 'type': 'session'})}\n\n"

            async for chunk in stream_answer(
                question=payload.question,
                file_id=payload.file_id,
                user_id=current_user.id,
                file_type=db_file.file_type,
                db=db,
            ):
                if chunk.get("type") == "token":
                    full_response += chunk["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
                elif chunk.get("type") == "timestamp":
                    timestamp_ref = chunk["value"]
                    yield f"data: {json.dumps({'type': 'timestamp', 'value': timestamp_ref})}\n\n"

            # Save assistant message only on success
            assistant_msg = ChatMessage(
                session_id=session.id,
                file_id=payload.file_id,
                role=MessageRole.assistant,
                content=full_response,
                timestamp_ref=timestamp_ref,
            )
            db.add(assistant_msg)
            db.commit()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"stream_answer error for user={current_user.id} file={payload.file_id}: {e}")
            error_payload = {
                "type": "error",
                "message": "An error occurred while generating the response. Please try again.",
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: Session = Depends(get_db),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    return session.messages
