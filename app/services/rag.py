import httpx
from typing import Callable, Coroutine

from app.config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, OLLAMA_RAG_MODEL, GROQ_API_KEY, GROQ_MODEL, RAG_CHUNK_COUNT, GROQ_RAG_CHUNK_COUNT
from app.models.state import get_chunks_collection
from app.services.llm_client import chat_with_messages

EMBED_TIMEOUT = 30.0


async def _embed_query(text: str) -> list[float]:
    url = f"{OLLAMA_BASE_URL}/api/embed"
    body = {
        "model": OLLAMA_EMBED_MODEL,
        "input": [f"query: {text}"],
    }
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]


async def rag_query(
    doc_id: str,
    question: str,
    history: list[dict] | None = None,
    max_chunks: int | None = None,
    on_progress: Callable[[str, str, int], Coroutine] | None = None,
    provider: str = "ollama",
) -> dict:
    if max_chunks is None:
        max_chunks = GROQ_RAG_CHUNK_COUNT if provider == "groq" else RAG_CHUNK_COUNT

    async def _progress(stage: str, message: str, pct: int):
        if on_progress:
            await on_progress(stage, message, pct)

    await _progress("searching", "Searching document for relevant content...", 10)

    query_emb = await _embed_query(question)

    collection = get_chunks_collection()
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=max_chunks,
        where={"doc_id": doc_id},
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"] or not results["ids"][0]:
        return {
            "answer": "I can only answer questions related to this document.",
            "sources": [],
        }

    await _progress("generating", "Generating answer...", 30)

    context_parts = []
    sources = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        content = results["documents"][0][i]
        ch_title = meta.get("chapter_title", "") or f"Chapter {meta.get('chapter', '?')}"
        sec_title = meta.get("section_title", "") or (f"Section {meta.get('section', '?')}" if meta.get("section") else "")
        label = f"{ch_title}{' / ' + sec_title if sec_title else ''}"
        # Truncate content to keep prompt manageable
        truncated = content[:2000] if len(content) > 2000 else content
        context_parts.append(f"--- Chunk {i + 1} ({label}) ---\n{truncated}")
        sources.append({
            "chunk_id": results["ids"][0][i],
            "chapter": meta.get("chapter", ""),
            "section": meta.get("section", ""),
            "title": label,
            "content_preview": truncated[:400],
            "page_start": meta.get("page_start", 0),
            "page_end": meta.get("page_end", 0),
        })

    context = "\n\n".join(context_parts)

    system_prompt = (
        "You are a document Q&A assistant. Answer ONLY based on the provided context below. "
        "If the context does not contain the answer, say exactly: "
        "'I can only answer questions related to this document.' "
        "Do not use any prior knowledge. Do not make up information. Be concise and accurate."
    )

    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for h in history[-4:]:
            messages.append({"role": h["role"], "content": h["content"]})

    user_prompt = f"Context from the document:\n{context}\n\nQuestion: {question}"
    messages.append({"role": "user", "content": user_prompt})

    if provider == "groq":
        if not GROQ_API_KEY:
            return {"answer": "Groq API key not configured. Set GROQ_API_KEY env var.", "sources": []}
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY)
        groq_messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-4:]:
                groq_messages.append({"role": h["role"], "content": h["content"]})
        groq_messages.append({"role": "user", "content": user_prompt})
        completion = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            temperature=0.0,
        )
        answer = completion.choices[0].message.content
    else:
        answer = await chat_with_messages(messages, model=OLLAMA_RAG_MODEL, temperature=0.0)

    return {"answer": answer, "sources": sources}
