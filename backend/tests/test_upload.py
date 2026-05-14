import io
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@patch("app.routers.upload.process_pdf", return_value=["chunk1", "chunk2"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_upload_pdf(mock_upsert, mock_process, client, auth_headers):
    pdf_bytes = b"%PDF-1.4 mock pdf content"
    response = client.post(
        "/upload/pdf",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_type"] == "pdf"
    assert data["original_filename"] == "test.pdf"


def test_upload_pdf_wrong_type(client, auth_headers):
    response = client.post(
        "/upload/pdf",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_list_files_empty(client, auth_headers):
    response = client.get("/upload/files", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_delete_file(mock_upsert, mock_process, client, auth_headers):
    pdf_bytes = b"%PDF-1.4 mock"
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("del.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    with patch("app.routers.upload.delete_user_file_index"):
        with patch("os.path.exists", return_value=False):
            del_resp = client.delete(f"/upload/files/{file_id}", headers=auth_headers)
    assert del_resp.status_code == 204


def test_get_segments_not_found(client, auth_headers):
    response = client.get("/upload/files/9999/segments", headers=auth_headers)
    assert response.status_code == 404


@patch("app.routers.upload.process_audio_video")
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_upload_audio_video(mock_upsert, mock_process_av, client, auth_headers):
    """POST /upload/audio — valid MP3 magic bytes pass validation."""
    async def fake_av(path):
        return [{"text": "Hello", "start": 0.0, "end": 5.0}], [{"text": "Hello world transcript", "start_seconds": 0.0}]

    mock_process_av.side_effect = fake_av

    fake_audio = io.BytesIO(b"ID3" + b"\x00" * 100)
    response = client.post(
        "/upload/audio",
        files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
        headers=auth_headers,
    )
    assert response.status_code in [200, 201]
    assert response.json()["file_type"] in ["audio", "video"]


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_list_files_with_content(mock_upsert, mock_process, client, auth_headers):
    client.post(
        "/upload/pdf",
        files={"file": ("listed.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    response = client.get("/upload/files", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_get_segments_for_audio_file(mock_upsert, mock_process, client, auth_headers, db):
    from app.models.models import File, FileType, TranscriptSegment

    f = File(
        user_id=1,
        filename="audio.mp3",
        original_filename="audio.mp3",
        file_path="/tmp/audio.mp3",
        file_type=FileType.audio,
    )
    db.add(f)
    db.commit()
    db.refresh(f)

    seg = TranscriptSegment(
        file_id=f.id,
        segment_index=0,
        text="Hello world",
        start_seconds=0.0,
        end_seconds=5.0,
    )
    db.add(seg)
    db.commit()

    response = client.get(f"/upload/files/{f.id}/segments", headers=auth_headers)
    assert response.status_code == 200
    segs = response.json()
    assert len(segs) == 1
    assert segs[0]["text"] == "Hello world"


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_delete_file_removes_from_disk(mock_upsert, mock_process, client, auth_headers):
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("todelete.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    with patch("app.routers.upload.delete_user_file_index"):
        with patch("os.path.exists", return_value=True):
            with patch("os.remove"):
                del_resp = client.delete(f"/upload/files/{file_id}", headers=auth_headers)
    assert del_resp.status_code == 204


@patch("app.routers.upload.process_pdf", return_value=["chunk1", "chunk2"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_get_summary_via_upload_route(mock_upsert, mock_process, client, auth_headers):
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("sum.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    with patch("app.routers.upload.summarize_file", new=AsyncMock(return_value="Great summary.")):
        response = client.get(f"/upload/files/{file_id}/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Great summary."
    assert data["file_id"] == file_id


def test_get_summary_file_not_found(client, auth_headers):
    response = client.get("/upload/files/99999/summary", headers=auth_headers)
    assert response.status_code == 404


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_redis_client_none_fallback():
    import app.core.redis_client as rm
    original = rm.redis_client
    rm.redis_client = None
    from app.core.redis_client import get_redis
    assert get_redis() is None
    rm.redis_client = original


def test_get_db_finally_block():
    from app.core.database import get_db
    gen = get_db()
    db = next(gen)
    assert db is not None
    try:
        gen.throw(RuntimeError("forced close"))
    except (RuntimeError, StopIteration):
        pass


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_upload_pdf_too_large(mock_upsert, mock_process, client, auth_headers):
    with patch("app.routers.upload.settings") as mock_settings:
        mock_settings.max_file_size_mb = 0
        mock_settings.upload_dir = "./uploads"
        response = client.post(
            "/upload/pdf",
            files={"file": ("big.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"]


# ── NEW: magic-byte validation failures ──────────────────────────────────────

def test_upload_pdf_invalid_magic_bytes(client, auth_headers):
    """PDF with wrong magic bytes → 400 (line 88)."""
    response = client.post(
        "/upload/pdf",
        files={"file": ("fake.pdf", io.BytesIO(b"NOTAPDF content here"), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "PDF format" in response.json()["detail"]


def test_upload_audio_wrong_content_type(client, auth_headers):
    """audio upload with disallowed content-type → 400 (line 112)."""
    response = client.post(
        "/upload/audio",
        files={"file": ("test.txt", io.BytesIO(b"notaudio"), "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_upload_audio_invalid_magic_bytes(client, auth_headers):
    """audio with correct content-type but wrong magic bytes → 400 (line 112 magic check)."""
    response = client.post(
        "/upload/audio",
        files={"file": ("bad.mp3", io.BytesIO(b"NOTAUDIO" * 20), "audio/mpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "audio/video format" in response.json()["detail"]


@patch("app.routers.upload.process_pdf", side_effect=RuntimeError("pdf parse boom"))
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_upload_pdf_process_failure_rolls_back(mock_upsert, mock_process, client, auth_headers):
    """Exception inside _save_and_process triggers rollback + 500 (lines 227-237)."""
    response = client.post(
        "/upload/pdf",
        files={"file": ("fail.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 500
    assert "Upload failed" in response.json()["detail"]


# ── NEW: /files/{id}/stream endpoint (lines 265-297) ─────────────────────────

def test_stream_media_no_token(client):
    """Missing token → 401 (line 268)."""
    response = client.get("/upload/files/1/stream")
    assert response.status_code == 401


def test_stream_media_invalid_token(client):
    """Bad token → 401 (line 272)."""
    response = client.get("/upload/files/1/stream?token=invalidtoken")
    assert response.status_code == 401


def test_stream_media_file_not_found(client, auth_headers):
    """Valid token but file_id doesn't exist → 404 (line 290)."""
    # Get a valid token from auth_headers
    token = auth_headers["Authorization"].split(" ")[1]
    response = client.get(f"/upload/files/99999/stream?token={token}")
    assert response.status_code == 404


@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_stream_media_file_missing_on_disk(mock_upsert, mock_process, client, auth_headers):
    """File in DB but not on disk → 404 (line 294)."""
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("stream.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]
    token = auth_headers["Authorization"].split(" ")[1]

    with patch("os.path.exists", return_value=False):
        response = client.get(f"/upload/files/{file_id}/stream?token={token}")
    assert response.status_code == 404
    assert "disk" in response.json()["detail"]


# ── NEW: summary cache hit (line 350) ────────────────────────────────────────

@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_get_summary_cache_hit(mock_upsert, mock_process, client, auth_headers):
    """Redis cache hit returns cached=True and skips summarize_file (line 350)."""
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("cached.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    # Pre-populate the fake_redis cache
    from tests.conftest import fake_redis
    fake_redis.setex(f"summary:{file_id}", 3600, "Cached summary value.")

    with patch("app.routers.upload.summarize_file", new=AsyncMock(return_value="Should not be called")) as mock_sum:
        response = client.get(f"/upload/files/{file_id}/summary", headers=auth_headers)
        mock_sum.assert_not_called()

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["summary"] == "Cached summary value."


# ── NEW: delete clears redis summary cache (line 378) ────────────────────────

@patch("app.routers.upload.process_pdf", return_value=["chunk1"])
@patch("app.routers.upload.upsert_chunks", return_value=None)
def test_delete_file_clears_summary_cache(mock_upsert, mock_process, client, auth_headers):
    """Delete endpoint calls redis.delete for summary cache key (line 378)."""
    upload_resp = client.post(
        "/upload/pdf",
        files={"file": ("toclear.pdf", io.BytesIO(b"%PDF-1.4 mock"), "application/pdf")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["id"]

    from tests.conftest import fake_redis
    fake_redis.setex(f"summary:{file_id}", 3600, "old summary")

    with patch("app.routers.upload.delete_user_file_index"):
        with patch("os.path.exists", return_value=False):
            del_resp = client.delete(f"/upload/files/{file_id}", headers=auth_headers)
    assert del_resp.status_code == 204
    # cache should be gone
    assert fake_redis.get(f"summary:{file_id}") is None
