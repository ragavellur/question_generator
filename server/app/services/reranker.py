from app.config import RERANKER_ENABLED, RERANKER_MODEL

_model = None


def _load_model():
    global _model
    if _model is None and RERANKER_ENABLED:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(RERANKER_MODEL)


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    if not RERANKER_ENABLED:
        return chunks[:top_k]
    _load_model()
    if _model is None:
        return chunks[:top_k]
    pairs = [(query, c.get("content", "")) for c in chunks]
    scores = _model.predict(pairs)
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    result = []
    for i, score in indexed[:top_k]:
        chunk = dict(chunks[i])
        chunk["rerank_score"] = float(score)
        result.append(chunk)
    return result
