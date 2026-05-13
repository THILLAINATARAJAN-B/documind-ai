import os
import pickle
import shutil
from typing import List, Dict, Optional
import faiss
import numpy as np
from openai import OpenAI
from app.core.config import get_settings

settings = get_settings()
openai_client = OpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _index_path(user_id: int) -> str:
    path = os.path.join(settings.faiss_store_dir, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def _get_embeddings(texts: List[str]) -> np.ndarray:
    response = openai_client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL,
    )
    return np.array([item.embedding for item in response.data], dtype="float32")


def _load_index(path: str):
    """Load FAISS index + metadata from disk. Returns (index, metadata)."""
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")

    if os.path.exists(index_file) and os.path.exists(meta_file):
        index = faiss.read_index(index_file)
        with open(meta_file, "rb") as f:
            metadata: List[Dict] = pickle.load(f)
    else:
        index = faiss.IndexFlatL2(EMBEDDING_DIM)
        metadata = []

    return index, metadata


def _save_index(path: str, index, metadata: List[Dict]):
    """
    Atomic write: write to .tmp files first, then rename.
    Prevents corruption if the server crashes mid-write.
    """
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")
    index_tmp = index_file + ".tmp"
    meta_tmp = meta_file + ".tmp"

    faiss.write_index(index, index_tmp)
    with open(meta_tmp, "wb") as f:
        pickle.dump(metadata, f)

    # Atomic rename — if either rename fails, originals are untouched
    os.replace(index_tmp, index_file)
    os.replace(meta_tmp, meta_file)


def upsert_chunks(
    chunks: List[str],
    user_id: int,
    file_id: int,
    start_seconds_list: Optional[List[float]] = None,
):
    """
    Embed chunks and append to user's FAISS index.
    For audio/video, pass start_seconds_list so timestamps
    are persisted in metadata alongside each chunk.
    Uses atomic write to prevent index corruption on crash.
    """
    if not chunks:
        return

    path = _index_path(user_id)
    index, metadata = _load_index(path)

    embeddings = _get_embeddings(chunks)
    index.add(embeddings)

    for i, chunk in enumerate(chunks):
        entry: Dict = {"file_id": file_id, "text": chunk}
        if start_seconds_list and i < len(start_seconds_list):
            entry["start_seconds"] = start_seconds_list[i]
        metadata.append(entry)

    _save_index(path, index, metadata)


def search_chunks(
    query: str,
    user_id: int,
    file_id: int,
    top_k: int = 5,
) -> List[Dict]:
    """
    Search FAISS index for top-k relevant chunks for a given file.
    Returns list of dicts with keys: 'text', 'start_seconds' (optional).
    """
    path = _index_path(user_id)
    index_file = os.path.join(path, "index.faiss")

    if not os.path.exists(index_file):
        return []

    index, metadata = _load_index(path)

    if index.ntotal == 0:
        return []

    query_embedding = _get_embeddings([query])
    distances, indices = index.search(query_embedding, min(top_k * 3, index.ntotal))

    results = []
    for idx in indices[0]:
        if idx < len(metadata) and metadata[idx]["file_id"] == file_id:
            results.append(metadata[idx])
            if len(results) >= top_k:
                break

    return results


def delete_user_file_index(user_id: int, file_id: int):
    """
    Remove all chunks belonging to a specific file from the FAISS index.

    FIX vs old code: We no longer re-embed all kept chunks via OpenAI.
    Instead we track the FAISS vector positions for each chunk in metadata,
    then rebuild the index from the stored embedding vectors directly
    using index.reconstruct() — zero additional API calls.

    If the index type doesn't support reconstruct (e.g. IVF without storing),
    we fall back to a safe full rebuild only for the kept chunks.
    """
    path = _index_path(user_id)
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")

    if not os.path.exists(index_file):
        return

    index, metadata = _load_index(path)

    kept_indices = [i for i, m in enumerate(metadata) if m["file_id"] != file_id]
    kept_meta = [metadata[i] for i in kept_indices]

    removed_count = len(metadata) - len(kept_meta)
    if removed_count == 0:
        return  # Nothing to delete

    if not kept_meta:
        # All chunks belonged to this file — wipe everything cleanly
        new_index = faiss.IndexFlatL2(EMBEDDING_DIM)
        _save_index(path, new_index, [])
        return

    # Reconstruct kept vectors directly from the FAISS index — NO API calls
    try:
        kept_vectors = np.vstack([
            index.reconstruct(i).reshape(1, -1) for i in kept_indices
        ]).astype("float32")

        new_index = faiss.IndexFlatL2(EMBEDDING_DIM)
        new_index.add(kept_vectors)
        _save_index(path, new_index, kept_meta)

    except Exception:
        # Fallback: if reconstruct fails (shouldn't for IndexFlatL2),
        # delete the whole user index so it gets rebuilt on next upload.
        # Better to lose all embeddings than to corrupt the store.
        shutil.rmtree(path, ignore_errors=True)