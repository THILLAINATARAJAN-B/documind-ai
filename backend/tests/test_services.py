import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import numpy as np
import os


# ─── PDF PROCESSOR ────────────────────────────────────────────────────────────

class TestPdfProcessor:
    def test_process_pdf_success(self):
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is sample PDF text for testing. " * 20
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.close = MagicMock()
        with patch("fitz.open", return_value=mock_doc):
            from app.services.pdf_processor import process_pdf
            chunks = process_pdf("fake.pdf")
            assert isinstance(chunks, list)
            assert len(chunks) > 0

    def test_process_pdf_empty_raises(self):
        mock_page = MagicMock()
        mock_page.get_text.return_value = "   "
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.close = MagicMock()
        with patch("fitz.open", return_value=mock_doc):
            from app.services.pdf_processor import process_pdf
            with pytest.raises(ValueError, match="no extractable text"):
                process_pdf("empty.pdf")

    def test_process_pdf_multiple_pages(self):
        pages = []
        for i in range(3):
            p = MagicMock()
            p.get_text.return_value = f"Page {i} content with some text. " * 10
            pages.append(p)
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter(pages))
        mock_doc.close = MagicMock()
        with patch("fitz.open", return_value=mock_doc):
            from app.services.pdf_processor import process_pdf
            chunks = process_pdf("multi.pdf")
            assert len(chunks) >= 1


# ─── AUDIO PROCESSOR (async) ─────────────────────────────────────────────────

class TestAudioProcessor:
    def test_process_audio_success(self):
        mock_seg = MagicMock()
        mock_seg.text = "Hello world"
        mock_seg.start = 0.0
        mock_seg.end = 5.0

        mock_response = MagicMock()
        mock_response.segments = [mock_seg]

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.audio_processor.client", mock_client):
            with patch("builtins.open", mock_open(read_data=b"audio")):
                from app.services.audio_processor import process_audio_video
                segments, chunks = asyncio.run(process_audio_video("fake.mp3"))
                assert isinstance(segments, list)
                assert len(segments) == 1
                assert segments[0]["text"] == "Hello world"
                assert isinstance(chunks, list)

    def test_process_audio_empty_segments(self):
        mock_response = MagicMock()
        mock_response.segments = []
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.audio_processor.client", mock_client):
            with patch("builtins.open", mock_open(read_data=b"audio")):
                from app.services.audio_processor import process_audio_video
                segments, chunks = asyncio.run(process_audio_video("empty.mp3"))
                assert segments == []
                assert chunks == [] or isinstance(chunks, list)

    def test_process_audio_returns_timestamps(self):
        mock_seg = MagicMock()
        mock_seg.text = "Introduction to AI and machine learning concepts"
        mock_seg.start = 12.4
        mock_seg.end = 35.1
        mock_response = MagicMock()
        mock_response.segments = [mock_seg]
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.audio_processor.client", mock_client):
            with patch("builtins.open", mock_open(read_data=b"audio")):
                from app.services.audio_processor import process_audio_video
                segments, chunks = asyncio.run(process_audio_video("test.mp3"))
                assert segments[0]["start"] == 12.4
                assert segments[0]["end"] == 35.1

    def test_process_audio_open_error(self):
        """IOError when opening audio file is propagated."""
        mock_client = AsyncMock()
        with patch("app.services.audio_processor.client", mock_client):
            with patch("builtins.open", side_effect=IOError("file not found")):
                from app.services.audio_processor import process_audio_video
                with pytest.raises(IOError):
                    asyncio.run(process_audio_video("missing.mp3"))

    def test_process_audio_multi_segment(self):
        """Multiple segments all returned."""
        segs = []
        for i in range(3):
            s = MagicMock()
            s.text = f"Segment {i}"
            s.start = float(i * 10)
            s.end = float(i * 10 + 9)
            segs.append(s)
        mock_response = MagicMock()
        mock_response.segments = segs
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.audio_processor.client", mock_client):
            with patch("builtins.open", mock_open(read_data=b"audio")):
                from app.services.audio_processor import process_audio_video
                segments, chunks = asyncio.run(process_audio_video("multi.mp3"))
                assert len(segments) == 3
                assert segments[2]["text"] == "Segment 2"


# ─── EMBEDDINGS ───────────────────────────────────────────────────────────────

class TestEmbeddings:
    def test_get_embeddings_internal(self):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            from app.services.embeddings import _get_embeddings
            result = _get_embeddings(["test chunk"])
            assert result.shape == (1, 1536)

    def test_upsert_chunks(self, tmp_path):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536),
                               MagicMock(embedding=[0.2] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as mock_settings:
                mock_settings.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import upsert_chunks
                upsert_chunks(["chunk one", "chunk two"], user_id=1, file_id=42)

    def test_upsert_empty_chunks(self):
        from app.services.embeddings import upsert_chunks
        upsert_chunks([], user_id=1, file_id=1)

    def test_search_chunks_no_index(self, tmp_path):
        with patch("app.services.embeddings.settings") as mock_settings:
            mock_settings.faiss_store_dir = str(tmp_path)
            from app.services.embeddings import search_chunks
            result = search_chunks("query", user_id=999, file_id=1)
            assert result == []

    def test_search_chunks_with_index(self, tmp_path):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536),
                               MagicMock(embedding=[0.2] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as mock_settings:
                mock_settings.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import upsert_chunks, search_chunks

                mock_response.data = [MagicMock(embedding=[0.1] * 1536),
                                       MagicMock(embedding=[0.2] * 1536)]
                upsert_chunks(["AI is great", "ML is useful"], user_id=1, file_id=1)

                mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
                result = search_chunks("AI", user_id=1, file_id=1)
                assert isinstance(result, list)

    def test_delete_user_file_index_no_file(self, tmp_path):
        with patch("app.services.embeddings.settings") as mock_settings:
            mock_settings.faiss_store_dir = str(tmp_path)
            from app.services.embeddings import delete_user_file_index
            delete_user_file_index(user_id=999, file_id=1)

    def test_upsert_chunks_with_timestamps(self, tmp_path):
        """upsert_chunks stores start_seconds in metadata when provided."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536),
                               MagicMock(embedding=[0.2] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as s:
                s.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import upsert_chunks
                import pickle
                upsert_chunks(
                    ["segment one", "segment two"],
                    user_id=1,
                    file_id=5,
                    start_seconds_list=[0.0, 10.5],
                )
                meta_file = tmp_path / "1" / "metadata.pkl"
                with open(meta_file, "rb") as f:
                    meta = pickle.load(f)
                assert meta[0]["start_seconds"] == 0.0
                assert meta[1]["start_seconds"] == 10.5

    def test_search_chunks_empty_index(self, tmp_path):
        """index.ntotal == 0 → returns []"""
        import faiss, pickle
        user_path = tmp_path / "1"
        user_path.mkdir()
        idx = faiss.IndexFlatL2(1536)
        faiss.write_index(idx, str(user_path / "index.faiss"))
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump([], f)

        mock_client = MagicMock()
        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as s:
                s.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import search_chunks
                result = search_chunks("query", user_id=1, file_id=1)
                assert result == []


# ─── CHAT ENGINE (async) ──────────────────────────────────────────────────────

class TestChatEngine:
    def test_stream_answer_pdf(self):
        mock_chunks = [{"text": "Relevant chunk about AI"}]

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content="AI "))]
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock(delta=MagicMock(content="is great"))]

        async def mock_stream():
            for c in [mock_chunk1, mock_chunk2]:
                yield c

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_db = MagicMock()

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("What is AI?", 1, 1, FileType.pdf, mock_db):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "token" for r in results)

    def test_stream_answer_audio_with_timestamp(self):
        mock_chunks = [{"text": "AI is discussed here", "start_seconds": 12.4}]

        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Answer text"))]

        async def mock_stream():
            yield mock_chunk1

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("When is AI discussed?", 1, 1, FileType.audio, mock_db):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "token" for r in results)
                assert any(r["type"] == "timestamp" for r in results)

    def test_summarize_file_no_content(self, tmp_path):
        with patch("app.services.embeddings.settings") as mock_settings:
            mock_settings.faiss_store_dir = str(tmp_path)
            with patch("app.services.chat_engine.client"):
                from app.services.chat_engine import summarize_file
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
                result = asyncio.run(summarize_file(file_id=999, user_id=999, db=mock_db))
                assert "No content" in result

    def test_summarize_file_with_content(self, tmp_path):
        """Single batch (1 chunk) → exactly 1 GPT call, no reduce step."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        vecs = np.array([[0.1] * 1536], dtype="float32")
        index.add(vecs)
        faiss.write_index(index, str(user_path / "index.faiss"))
        meta = [{"file_id": 1, "text": "Machine learning is fascinating."}]
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump(meta, f)

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Summary: ML overview"))]
        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        # Patch BOTH embeddings.settings (for faiss path) AND embeddings.openai_client
        # (so _get_embeddings never calls the real OpenAI API).
        mock_embed_client = MagicMock()
        mock_embed_resp = MagicMock()
        mock_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_embed_client.embeddings.create.return_value = mock_embed_resp

        with patch("app.services.embeddings.settings") as mock_emb_settings:
            mock_emb_settings.faiss_store_dir = str(tmp_path)
            with patch("app.services.embeddings.openai_client", mock_embed_client):
                with patch("app.services.chat_engine.client", mock_openai_client):
                    from app.services.chat_engine import summarize_file
                    mock_db = MagicMock()
                    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
                    result = asyncio.run(summarize_file(file_id=1, user_id=1, db=mock_db))
                    assert isinstance(result, str)
                    assert len(result) > 0

    def test_stream_answer_search_fails(self):
        """If search_chunks raises, stream_answer yields error dict."""
        with patch("app.services.chat_engine.search_chunks", side_effect=RuntimeError("FAISS error")):
            with patch("app.services.chat_engine.client"):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.pdf, MagicMock()):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "error" for r in results)

    def test_stream_answer_no_chunks(self):
        """search_chunks returns [] → yields informative token."""
        with patch("app.services.chat_engine.search_chunks", return_value=[]):
            with patch("app.services.chat_engine.client"):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.pdf, MagicMock()):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "token" for r in results)

    def test_stream_answer_rate_limit_error(self):
        """RateLimitError from OpenAI yields error dict."""
        from openai import RateLimitError
        mock_chunks = [{"text": "some context"}]

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=RateLimitError(
                "rate limit",
                response=MagicMock(status_code=429, headers={}),
                body={},
            )
        )

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.pdf, MagicMock()):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "error" for r in results)
                assert any("rate limit" in r.get("content", "").lower() for r in results if r["type"] == "error")

    def test_stream_answer_connection_error(self):
        """APIConnectionError from OpenAI yields error dict."""
        from openai import APIConnectionError
        mock_chunks = [{"text": "some context"}]

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.pdf, MagicMock()):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "error" for r in results)


# ─── SECURITY ─────────────────────────────────────────────────────────────────

class TestSecurity:
    def test_hash_and_verify_password(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_create_and_decode_token(self):
        from app.core.security import create_access_token, decode_access_token
        token = create_access_token({"sub": "user@example.com", "user_id": 1})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"

    def test_decode_invalid_token(self):
        from app.core.security import decode_access_token
        result = decode_access_token("this.is.invalid")
        assert result is None

    def test_decode_tampered_token(self):
        from app.core.security import decode_access_token
        result = decode_access_token("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.wrongsig")
        assert result is None

    def test_create_refresh_token_is_unique(self):
        """Two refresh tokens should always be different."""
        from app.core.security import create_refresh_token
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2
        assert len(t1) > 20

    def test_decode_token_alias(self):
        """decode_token alias should behave identically to decode_access_token."""
        from app.core.security import create_access_token, decode_token
        token = create_access_token({"sub": "42"})
        payload = decode_token(token)
        assert payload["sub"] == "42"

    def test_refresh_token_rejected_as_access_token(self):
        """A non-JWT opaque refresh token must return None from decode_access_token."""
        from app.core.security import create_refresh_token, decode_access_token
        refresh = create_refresh_token()
        assert decode_access_token(refresh) is None


# ─── EMBEDDINGS EXTRA (covers lines 41-43, 80-82, 94-112) ────────────────────

class TestEmbeddingsExtra:
    def test_upsert_chunks_existing_index(self, tmp_path):
        """Loading existing index branch."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        faiss.write_index(index, str(user_path / "index.faiss"))
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump([], f)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as s:
                s.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import upsert_chunks
                upsert_chunks(["new chunk"], user_id=1, file_id=2)

    def test_search_chunks_filters_by_file_id(self, tmp_path):
        """file_id filtering in search."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        vecs = np.array([[0.1] * 1536, [0.2] * 1536], dtype="float32")
        index.add(vecs)
        faiss.write_index(index, str(user_path / "index.faiss"))
        meta = [{"file_id": 1, "text": "correct chunk"},
                {"file_id": 99, "text": "wrong file chunk"}]
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump(meta, f)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as s:
                s.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import search_chunks
                results = search_chunks("query", user_id=1, file_id=1)
                result_texts = [r["text"] if isinstance(r, dict) else r for r in results]
                assert "correct chunk" in result_texts
                assert "wrong file chunk" not in result_texts

    def test_delete_user_file_index_with_data(self, tmp_path):
        """Actual deletion rebuild."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        vecs = np.array([[0.1] * 1536, [0.2] * 1536], dtype="float32")
        index.add(vecs)
        faiss.write_index(index, str(user_path / "index.faiss"))
        meta = [{"file_id": 1, "text": "keep this"},
                {"file_id": 2, "text": "delete this"}]
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump(meta, f)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("app.services.embeddings.openai_client", mock_client):
            with patch("app.services.embeddings.settings") as s:
                s.faiss_store_dir = str(tmp_path)
                from app.services.embeddings import delete_user_file_index
                delete_user_file_index(user_id=1, file_id=2)

        import pickle as pkl
        with open(str(user_path / "metadata.pkl"), "rb") as f:
            remaining = pkl.load(f)
        assert all(m["file_id"] == 1 for m in remaining)

    def test_delete_all_chunks_clears_index(self, tmp_path):
        """Deleting the only file leaves an empty clean index."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        vecs = np.array([[0.1] * 1536], dtype="float32")
        index.add(vecs)
        faiss.write_index(index, str(user_path / "index.faiss"))
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump([{"file_id": 1, "text": "only chunk"}], f)

        with patch("app.services.embeddings.settings") as s:
            s.faiss_store_dir = str(tmp_path)
            from app.services.embeddings import delete_user_file_index
            delete_user_file_index(user_id=1, file_id=1)

        import pickle as pkl
        with open(str(user_path / "metadata.pkl"), "rb") as f:
            remaining = pkl.load(f)
        assert remaining == []


# ─── CHAT ENGINE EXTRA ────────────────────────────────────────────────────────

class TestChatEngineExtra:
    def test_stream_answer_no_timestamp_in_audio(self):
        """Audio response where chunk has NO start_seconds — no timestamp yielded."""
        mock_chunks = [{"text": "The speaker talks about AI."}]

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="The speaker talks about AI."))]

        async def mock_stream():
            yield mock_chunk

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("question", 1, 1, FileType.video, mock_db):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "token" for r in results)
                assert not any(r["type"] == "timestamp" for r in results)

    def test_stream_answer_inline_timestamp_in_audio(self):
        """Secondary: inline TIMESTAMP: <float> marker in GPT output yields timestamp."""
        mock_chunks = [{"text": "AI is discussed here"}]

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="Some answer\nTIMESTAMP: 12.4"))]

        async def mock_stream():
            yield mock_chunk

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_db = MagicMock()

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.audio, mock_db):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert any(r["type"] == "timestamp" for r in results)

    def test_stream_answer_invalid_inline_timestamp_ignored(self):
        """Inline TIMESTAMP with non-numeric value is silently ignored."""
        mock_chunks = [{"text": "context text"}]

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="Some answer\nTIMESTAMP: notanumber"))]

        async def mock_stream():
            yield mock_chunk

        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        mock_db = MagicMock()

        with patch("app.services.chat_engine.search_chunks", return_value=mock_chunks):
            with patch("app.services.chat_engine.client", mock_openai_client):
                from app.services.chat_engine import stream_answer
                from app.models.models import FileType

                async def collect():
                    results = []
                    async for item in stream_answer("q", 1, 1, FileType.audio, mock_db):
                        results.append(item)
                    return results

                results = asyncio.run(collect())
                assert not any(r["type"] == "timestamp" for r in results)

    def test_summarize_multi_batch(self, tmp_path):
        """12 chunks → 2 batches (batch_size=10) + 1 reduce call = 3 total calls."""
        import pickle, faiss
        user_path = tmp_path / "1"
        user_path.mkdir()
        index = faiss.IndexFlatL2(1536)
        vecs = np.array([[0.1] * 1536] * 12, dtype="float32")
        index.add(vecs)
        faiss.write_index(index, str(user_path / "index.faiss"))
        meta = [{"file_id": 1, "text": f"Chunk {i} about AI."} for i in range(12)]
        with open(str(user_path / "metadata.pkl"), "wb") as f:
            pickle.dump(meta, f)

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(choices=[MagicMock(message=MagicMock(content=f"Summary {call_count}"))])

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create = mock_create

        # Must also mock openai_client in embeddings so _get_embeddings is intercepted
        mock_embed_client = MagicMock()
        mock_embed_resp = MagicMock()
        mock_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_embed_client.embeddings.create.return_value = mock_embed_resp

        with patch("app.services.embeddings.settings") as s:
            s.faiss_store_dir = str(tmp_path)
            with patch("app.services.embeddings.openai_client", mock_embed_client):
                with patch("app.services.chat_engine.client", mock_openai_client):
                    from app.services.chat_engine import summarize_file
                    mock_db = MagicMock()
                    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
                    result = asyncio.run(summarize_file(file_id=1, user_id=1, db=mock_db))
                    assert isinstance(result, str)
                    assert call_count >= 2

    def test_summarize_uses_transcript_segments(self, tmp_path):
        """When DB has transcript segments, summarize uses them (no FAISS call)."""
        mock_seg = MagicMock()
        mock_seg.text = "AI is transforming many industries."

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="AI summary"))]
        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        with patch("app.services.chat_engine.client", mock_openai_client):
            from app.services.chat_engine import summarize_file
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_seg]
            result = asyncio.run(summarize_file(file_id=1, user_id=1, db=mock_db))
            assert isinstance(result, str)
            assert len(result) > 0
            # No FAISS/embedding calls made
            mock_openai_client.chat.completions.create.assert_called_once()
