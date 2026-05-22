import os
import pickle
import re
import threading

from rank_bm25 import BM25Okapi

from app.config import BM25_ENABLED, BM25_INDEX_DIR
from app.models.schemas import Chunk

_lock = threading.Lock()
_cache: dict[str, BM25Okapi] = {}


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return text.split()


def index_document(doc_id: str, chunks: list[Chunk]):
    if not BM25_ENABLED:
        return
    os.makedirs(BM25_INDEX_DIR, exist_ok=True)
    tokenized_corpus = [_tokenize(c.content) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    path = os.path.join(BM25_INDEX_DIR, f"{doc_id}.pkl")
    with open(path, "wb") as f:
        pickle.dump({
            "chunk_ids": [c.chunk_id for c in chunks],
            "tokenized_corpus": tokenized_corpus,
            "bm25_params": {"k1": 1.5, "b": 0.75},
        }, f)
    with _lock:
        _cache[doc_id] = bm25


def search(doc_id: str, query: str, top_k: int = 30) -> list[tuple[str, float]]:
    if not BM25_ENABLED:
        return []
    bm25 = _load_index(doc_id)
    if bm25 is None:
        return []
    tokenized_query = _tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    path = os.path.join(BM25_INDEX_DIR, f"{doc_id}.pkl")
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        data = pickle.load(f)
    chunk_ids = data["chunk_ids"]
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top = [(chunk_ids[i], float(score)) for i, score in indexed[:top_k] if score > 0]
    return top


def _load_index(doc_id: str) -> BM25Okapi | None:
    with _lock:
        if doc_id in _cache:
            return _cache[doc_id]
    path = os.path.join(BM25_INDEX_DIR, f"{doc_id}.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = pickle.load(f)
    bm25 = BM25Okapi(data["tokenized_corpus"], k1=1.5, b=0.75)
    with _lock:
        _cache[doc_id] = bm25
    return bm25
