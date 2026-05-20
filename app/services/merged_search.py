from app.config import RERANKER_RETRIEVE_COUNT, RERANKER_TOP_K
from app.services.bm25_store import search as bm25_search
from app.services.reranker import rerank as cross_rerank


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def hybrid_search(
    vector_chunks: list[dict],
    doc_id: str,
    query: str,
    reranker_enabled: bool = True,
) -> list[dict]:
    if not vector_chunks:
        return []

    chunk_map = {}
    for i, c in enumerate(vector_chunks):
        cid = c.get("chunk_id", "")
        chunk_map[cid] = c

    bm25_results = bm25_search(doc_id, query, top_k=RERANKER_RETRIEVE_COUNT)

    bm25_ids = {cid for cid, _ in bm25_results}

    vector_ranked = list(chunk_map.values())

    fused_scores: dict[str, float] = {}
    for i, c in enumerate(vector_ranked):
        cid = c.get("chunk_id", "")
        fused_scores[cid] = fused_scores.get(cid, 0.0) + _rrf_score(i)

    bm25_rank = 0
    for cid, score in bm25_results:
        if cid in chunk_map:
            fused_scores[cid] = fused_scores.get(cid, 0.0) + _rrf_score(bm25_rank)
            bm25_rank += 1

    scored = [(cid, score) for cid, score in fused_scores.items() if cid in chunk_map]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_n = RERANKER_RETRIEVE_COUNT
    fused_chunks = [chunk_map[cid] for cid, _ in scored[:top_n]]

    if reranker_enabled and len(fused_chunks) > RERANKER_TOP_K:
        return cross_rerank(query, fused_chunks, top_k=RERANKER_TOP_K)

    return fused_chunks[:RERANKER_TOP_K]
