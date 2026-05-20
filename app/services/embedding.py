import os
import time

import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from app.models.schemas import Chunk
from app.models.state import set_processing_status

EMBED_TIMEOUT = 300.0
BATCH_SIZE = 30


async def embed_chunks(chunks: list[Chunk], doc_id: str) -> list[Chunk]:
    texts = [_prepare_text_for_embedding(c) for c in chunks]
    url = f"{OLLAMA_BASE_URL}/api/embed"

    all_embeddings = []
    total = len(texts)
    start_time = time.time()

    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as client:
        for i in range(0, total, BATCH_SIZE):
            batch_start = time.time()
            batch = texts[i:i + BATCH_SIZE]
            body = {
                "model": OLLAMA_EMBED_MODEL,
                "input": batch,
            }
            try:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
                all_embeddings.extend(data.get("embeddings", []))
            except Exception:
                all_embeddings.extend([None] * len(batch))

            done = min(i + BATCH_SIZE, total)
            batch_elapsed = time.time() - batch_start
            total_elapsed = time.time() - start_time
            batches_total = (total + BATCH_SIZE - 1) // BATCH_SIZE
            batches_done = (done + BATCH_SIZE - 1) // BATCH_SIZE
            avg_per_batch = total_elapsed / batches_done if batches_done else 0
            remaining_batches = batches_total - batches_done
            est_remaining = avg_per_batch * remaining_batches
            pct = int(done / total * 100)

            msg = f"Embedded {done} of {total} chunks ({pct}%)"
            if est_remaining > 60:
                msg += f", ~{int(est_remaining // 60)}m {int(est_remaining % 60)}s remaining"
            else:
                msg += f", ~{int(est_remaining)}s remaining"

            set_processing_status(doc_id, "embedding", 85 + pct // 10, msg)

    for i, chunk in enumerate(chunks):
        if i < len(all_embeddings) and all_embeddings[i] is not None:
            chunk.embedding = all_embeddings[i]
        else:
            chunk.embedding = None

    return chunks


def _prepare_text_for_embedding(chunk: Chunk) -> str:
    text = chunk.content.strip()
    if len(text) > 4096:
        text = text[:4096]
    return f"passage: {text}"


def prepare_query(query: str) -> str:
    return f"query: {query}"
