import json

from app.models.schemas import Chunk, Chapter
from app.models.state import get_chunks_collection, get_docs_collection


STORE_BATCH_SIZE = 200


def store_chunks(chunks: list[Chunk], doc_id: str, doc_name: str, chapters: list[dict]):
    collection = get_chunks_collection()

    batch_ids = []
    batch_embeddings = []
    batch_metadatas = []
    batch_documents = []

    def _flush():
        if batch_ids:
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                documents=batch_documents,
            )
            batch_ids.clear()
            batch_embeddings.clear()
            batch_metadatas.clear()
            batch_documents.clear()

    for chunk in chunks:
        if not chunk.embedding:
            continue

        batch_ids.append(chunk.chunk_id)
        batch_embeddings.append(chunk.embedding)
        batch_metadatas.append({
            "doc_id": doc_id,
            "doc_name": doc_name,
            "chapter": chunk.chapter,
            "chapter_title": chunk.chapter_title,
            "section": chunk.section,
            "section_title": chunk.section_title,
            "subsection": chunk.subsection,
            "content_type": chunk.content_type.value,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "token_count": chunk.token_count,
        })
        batch_documents.append(chunk.content)

        if len(batch_ids) >= STORE_BATCH_SIZE:
            _flush()

    _flush()

    docs_col = get_docs_collection()
    docs_col.upsert(
        ids=[doc_id],
        metadatas=[{
            "name": doc_name,
            "path": "",
            "total_pages": max(c.page_end for c in chunks) if chunks else 0,
            "chunk_count": len(chunks),
            "chapters": json.dumps(chapters),
            "processed": "true",
        }],
        documents=[doc_name],
    )


def _build_where(filters: dict | None) -> dict | None:
    if not filters:
        return None
    cleaned = {k: v for k, v in filters.items() if v is not None and v != [] and v != ""}
    if not cleaned:
        return None
    clauses = []
    for k, v in cleaned.items():
        if isinstance(v, list):
            if len(v) == 1:
                clauses.append({k: v[0]})
            else:
                clauses.append({"$or": [{k: item} for item in v]})
        else:
            clauses.append({k: v})
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def query_chunks(
    query_text: str,
    n_results: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    collection = get_chunks_collection()

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=_build_where(filters),
    )

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "chunk_id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })
    return output


def get_hierarchy(doc_id: str) -> list[dict]:
    collection = get_chunks_collection()
    results = collection.get(
        where={"doc_id": doc_id},
        include=["metadatas"],
    )

    seen_chapters = {}
    for meta in results["metadatas"]:
        ch = meta["chapter"]
        if ch not in seen_chapters:
            seen_chapters[ch] = {
                "number": ch,
                "title": meta.get("chapter_title", ""),
                "sections": set(),
            }
        sec = meta.get("section", "")
        if sec:
            seen_chapters[ch]["sections"].add(sec)

    hierarchy = []
    for ch_num in sorted(seen_chapters.keys(), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else x):
        ch_data = seen_chapters[ch_num]
        ch_data["sections"] = sorted(
            ch_data["sections"],
            key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else x,
        )
        hierarchy.append(ch_data)

    return hierarchy


def list_documents() -> list[dict]:
    docs_col = get_docs_collection()
    results = docs_col.get(include=["metadatas"])

    docs = []
    for i, doc_id in enumerate(results["ids"]):
        meta = results["metadatas"][i]
        docs.append({
            "id": doc_id,
            "name": meta.get("name", "Unknown"),
            "total_pages": meta.get("total_pages", 0),
            "chunk_count": meta.get("chunk_count", 0),
            "processed": meta.get("processed") == "true",
        })
    return docs


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    collection = get_chunks_collection()
    results = collection.get(ids=chunk_ids, include=["documents", "metadatas"])

    chunks = []
    for i in range(len(results["ids"])):
        chunks.append({
            "chunk_id": results["ids"][i],
            "content": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    return chunks


def get_chunks_by_filter(filters: dict, limit: int = 50) -> list[dict]:
    collection = get_chunks_collection()
    results = collection.get(
        where=_build_where(filters),
        limit=limit,
        include=["documents", "metadatas"],
    )

    chunks = []
    for i in range(len(results["ids"])):
        chunks.append({
            "chunk_id": results["ids"][i],
            "content": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    return chunks


def delete_document(doc_id: str):
    chunks_col = get_chunks_collection()
    chunks_col.delete(where={"doc_id": doc_id})

    docs_col = get_docs_collection()
    docs_col.delete(ids=[doc_id])
