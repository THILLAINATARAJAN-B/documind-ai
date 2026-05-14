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

    # Real MP3 magic bytes (ID3 header) so _validate_magic_bytes passes
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
    """list route returns non-empty results."""
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
    """segments endpoint returns real data."""
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
    """os.path.exists=True branch triggers os.remove."""
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
    """GET /upload/files/{id}/summary route."""
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
    """summary 404 branch."""
    response = client.get("/upload/files/99999/summary", headers=auth_headers)
    assert response.status_code == 404


def test_health_check(client):
    """main.py /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_redis_client_none_fallback():
    """get_redis returns None on failed connection."""
    import app.core.redis_client as rm
    original = rm.redis_client
    rm.redis_client = None
    from app.core.redis_client import get_redis
    assert get_redis() is None
    rm.redis_client = original


def test_get_db_finally_block():
    """database.py get_db finally block."""
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
    """File exceeding max_file_size_mb returns 400."""
    from unittest.mock import patch as mp
    # Temporarily lower the limit to 0 MB so any file is "too large"
    with mp("app.routers.upload.settings") as mock_settings:
        mock_settings.max_file_size_mb = 0
        mock_settings.upload_dir = "./uploads"
        response = client.post(
            "/upload/pdf",
            files={"file": ("big.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"]
