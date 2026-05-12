import os
import pickle
from typing import List, Dict
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


def upsert_chunks(chunks: List[str], user_id: int, file_id: int):
    """Embed chunks and store in user's FAISS index."""
    if not chunks:
        return

    path = _index_path(user_id)
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")

    # Load or create index
    if os.path.exists(index_file):
        index = faiss.read_index(index_file)
        with open(meta_file, "rb") as f:
            metadata: List[Dict] = pickle.load(f)
    else:
        index = faiss.IndexFlatL2(EMBEDDING_DIM)
        metadata = []

    embeddings = _get_embeddings(chunks)
    index.add(embeddings)

    for chunk in chunks:
        metadata.append({"file_id": file_id, "text": chunk})

    faiss.write_index(index, index_file)
    with open(meta_file, "wb") as f:
        pickle.dump(metadata, f)


def search_chunks(query: str, user_id: int, file_id: int, top_k: int = 5) -> List[str]:
    """Search FAISS index for top-k relevant chunks for a given file."""
    path = _index_path(user_id)
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")

    if not os.path.exists(index_file):
        return []

    index = faiss.read_index(index_file)
    with open(meta_file, "rb") as f:
        metadata: List[Dict] = pickle.load(f)

    query_embedding = _get_embeddings([query])
    distances, indices = index.search(query_embedding, min(top_k * 3, index.ntotal))

    results = []
    for idx in indices[0]:
        if idx < len(metadata) and metadata[idx]["file_id"] == file_id:
            results.append(metadata[idx]["text"])
            if len(results) >= top_k:
                break

    return results


def delete_user_file_index(user_id: int, file_id: int):
    """Remove all chunks belonging to a specific file from the FAISS index."""
    path = _index_path(user_id)
    index_file = os.path.join(path, "index.faiss")
    meta_file = os.path.join(path, "metadata.pkl")

    if not os.path.exists(index_file):
        return

    with open(meta_file, "rb") as f:
        metadata: List[Dict] = pickle.load(f)

    # Filter out chunks for the deleted file and rebuild index
    kept_meta = [m for m in metadata if m["file_id"] != file_id]
    removed_meta = [m for m in metadata if m["file_id"] == file_id]

    if not removed_meta:
        return

    new_index = faiss.IndexFlatL2(EMBEDDING_DIM)
    if kept_meta:
        texts = [m["text"] for m in kept_meta]
        embeddings = _get_embeddings(texts)
        new_index.add(embeddings)

    faiss.write_index(new_index, index_file)
    with open(meta_file, "wb") as f:
        pickle.dump(kept_meta, f)