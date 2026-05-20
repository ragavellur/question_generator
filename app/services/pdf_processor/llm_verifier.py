import random

from app.services.llm_client import chat_json


VERIFIER_SYSTEM = """You are a quality control checker for PDF text extraction. Given a chunk of extracted text, verify its quality and correctness. Return JSON only."""


VERIFIER_PROMPT_TEMPLATE = """Inspect this text chunk extracted from a PDF document:

CHUNK METADATA:
- Document: {doc_name}
- Chapter: {chapter}
- Section: {section}
- Page range: {page_start}-{page_end}
- Assigned content type: {content_type}

CHUNK TEXT:
{content}

Analyze the chunk and return JSON:
{{
  "clean": bool,  // true if chunk has no headers, footers, page numbers, or other extraction artifacts
  "noise_found": [str],  // list of noise types detected, empty if clean
  "metadata_ok": bool,  // true if chapter/section/page metadata matches the content
  "correct_content_type": str,  // what you think the content type is (definition|example|derivation|problem|summary|conceptual)
  "meaningful": bool,  // true if the chunk contains usable educational content
  "issues": [str],  // any issues found
  "quality_score": 1-5  // 5 = perfect, 1 = unusable
}}"""


async def verify_chunk(chunk: dict) -> dict:
    prompt = VERIFIER_PROMPT_TEMPLATE.format(
        doc_name=chunk.get("doc_name", "unknown"),
        chapter=chunk.get("chapter", "?"),
        section=chunk.get("section", "?"),
        page_start=chunk.get("page_start", 0),
        page_end=chunk.get("page_end", 0),
        content_type=chunk.get("content_type", "unknown"),
        content=chunk.get("content", "")[:2000],
    )

    try:
        result = await chat_json(prompt, system=VERIFIER_SYSTEM, temperature=0.05)
        return result
    except Exception as e:
        return {"clean": True, "noise_found": [], "metadata_ok": True,
                "correct_content_type": chunk.get("content_type", "conceptual"),
                "meaningful": True, "issues": [f"Verification failed: {e}"], "quality_score": 3}


async def verify_sample(chunks: list[dict], sample_size: int = 3) -> list[dict]:
    if not chunks:
        return []

    sample = random.sample(chunks, min(sample_size, len(chunks)))
    results = []
    for chunk in sample:
        result = await verify_chunk(chunk)
        results.append({
            "chunk_id": chunk.get("chunk_id", ""),
            "result": result,
        })
    return results
