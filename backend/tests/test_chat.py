import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.models.models import File, FileType
import io


@patch("app.routers.upload.process_pdf", return_value=["chunk1", "chunk2"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_ask_creates_session(mock_upsert, mock_process, client, auth_headers):
    pdf_bytes = b"%PDF-1.4 mock"
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    # Use `new=` not `side_effect=` so async-for works correctly
    async def mock_stream_answer(*args, **kwargs):
        yield {"type": "token", "content": "Test answer"}

    with patch("app.routers.chat.stream_answer", new=mock_stream_answer):
        with patch("app.routers.chat.get_redis") as mock_redis:
            mock_r = MagicMock()
            mock_r.incr.return_value = 1
            mock_redis.return_value = mock_r
            response = client.post(
                "/chat/ask",
                json={"file_id": file_id, "question": "What is this about?"},
                headers=auth_headers,
            )
    assert response.status_code == 200


def test_ask_file_not_found(client, auth_headers):
    with patch("app.routers.chat.get_redis") as mock_redis:
        mock_r = MagicMock()
        mock_r.incr.return_value = 1
        mock_redis.return_value = mock_r
        response = client.post(
            "/chat/ask",
            json={"file_id": 9999, "question": "test"},
            headers=auth_headers,
        )
    assert response.status_code == 404


def test_get_summary_file_not_found(client, auth_headers):
    """summary route 404 — file doesn't exist."""
    response = client.get("/upload/files/99999/summary", headers=auth_headers)
    assert response.status_code == 404


@patch("app.routers.upload.process_pdf", return_value=["chunk1", "chunk2"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_get_summary_completed(mock_upsert, mock_process, client, auth_headers):
    """GET /upload/files/{id}/summary returns summary for uploaded file."""
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("complete.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    with patch("app.routers.upload.summarize_file", new=AsyncMock(return_value="Nice summary.")):
        response = client.get(f"/upload/files/{file_id}/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Nice summary."
    assert data["file_id"] == file_id


def test_get_messages_session_not_found(client, auth_headers):
    """GET /sessions/{id}/messages — 404 for missing session."""
    response = client.get("/chat/sessions/99999/messages", headers=auth_headers)
    assert response.status_code == 404


@patch("app.routers.upload.process_pdf", return_value=["chunk1", "chunk2"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_get_messages_for_session(mock_upsert, mock_process, client, auth_headers, db):
    """GET /sessions/{id}/messages — returns messages list."""
    from app.models.models import ChatSession, ChatMessage, MessageRole

    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("msg.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    session = ChatSession(user_id=1)
    db.add(session)
    db.commit()
    db.refresh(session)

    msg = ChatMessage(
        session_id=session.id,
        file_id=file_id,
        role=MessageRole.user,
        content="What is this about?",
    )
    db.add(msg)
    db.commit()

    response = client.get(f"/chat/sessions/{session.id}/messages", headers=auth_headers)
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) >= 1
    assert messages[0]["content"] == "What is this about?"


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_ask_rate_limit_exceeded(mock_upsert, mock_process, client, auth_headers):
    """Rate limit raises 429 before StreamingResponse."""
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("rate.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    mock_r = MagicMock()
    mock_r.incr.return_value = 21
    mock_r.expire = MagicMock()

    with patch("app.routers.chat.get_redis", return_value=mock_r):
        response = client.post(
            "/chat/ask",
            json={"file_id": file_id, "question": "test"},
            headers=auth_headers,
        )

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


def test_ask_question_too_long(client, auth_headers):
    """Question > 2000 chars returns 422 validation error."""
    with patch("app.routers.chat.get_redis") as mock_redis:
        mock_r = MagicMock()
        mock_r.incr.return_value = 1
        mock_redis.return_value = mock_r
        response = client.post(
            "/chat/ask",
            json={"file_id": 1, "question": "x" * 2001},
            headers=auth_headers,
        )
    assert response.status_code == 422


def test_ask_question_empty(client, auth_headers):
    """Empty question returns 422 validation error."""
    with patch("app.routers.chat.get_redis") as mock_redis:
        mock_r = MagicMock()
        mock_r.incr.return_value = 1
        mock_redis.return_value = mock_r
        response = client.post(
            "/chat/ask",
            json={"file_id": 1, "question": "   "},
            headers=auth_headers,
        )
    assert response.status_code == 422
