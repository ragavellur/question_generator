import uuid
import re

from app.config import CHUNK_MIN_TOKENS, CHUNK_MAX_TOKENS
from app.models.schemas import Chunk, ContentType, Chapter


_CONTENT_TYPE_KEYWORDS: dict[ContentType, list[str]] = {
    ContentType.definition: [
        "is defined as", "is called", "refers to", "denotes", "is known as",
        "is the", "are the", "means that", "represents the",
    ],
    ContentType.example: [
        "example", "for instance", "consider", "illustrate", "sample",
        "such as", "e.g.",
    ],
    ContentType.derivation: [
        "equation", "substituting", "hence", "therefore", "we have",
        "from equation", "gives", "yields", "solving for",
    ],
    ContentType.problem: [
        "problem", "calculate", "find the", "determine", "compute",
        "consider a", "assume", "given that", "show that",
    ],
    ContentType.summary: [
        "summary", "in this chapter", "we have discussed", "review",
        "recap", "overview", "key points", "important concepts",
    ],
}


def _detect_content_type(text: str) -> ContentType:
    text_lower = text.lower()
    for ctype, keywords in _CONTENT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return ctype
    return ContentType.conceptual


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _split_into_chunks(text: str, min_tokens: int, max_tokens: int) -> list[str]:
    if _count_tokens(text) <= max_tokens:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if _count_tokens(current + "\n\n" + para) <= max_tokens:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    merged = []
    buffer = ""
    for chunk in chunks:
        if not buffer:
            buffer = chunk
        elif _count_tokens(buffer + "\n\n" + chunk) <= max_tokens:
            buffer += "\n\n" + chunk
        else:
            if _count_tokens(buffer) >= min_tokens or not merged:
                merged.append(buffer)
            else:
                if merged:
                    merged[-1] += "\n\n" + buffer
                else:
                    merged.append(buffer)
            buffer = chunk
    if buffer:
        if _count_tokens(buffer) >= min_tokens or not merged:
            merged.append(buffer)
        else:
            merged[-1] += "\n\n" + buffer

    return merged if merged else [text]


def chunk_document(
    doc_id: str,
    doc_name: str,
    cleaned_pages: list[dict],
    chapters: list[Chapter],
) -> list[Chunk]:
    page_map = {p["page_num"]: p["text"] for p in cleaned_pages}

    chunks: list[Chunk] = []

    for chapter in chapters:
        for section in chapter.sections:
            page_start = section.page_start
            page_end = section.page_end

            section_text = ""
            for pn in range(page_start, page_end + 1):
                if pn in page_map:
                    section_text += page_map.get(pn, "") + "\n\n"

            section_text = section_text.strip()
            if not section_text:
                continue

            token_count = _count_tokens(section_text)
            content_type = _detect_content_type(section_text)

            if token_count <= CHUNK_MAX_TOKENS:
                chunk = Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    doc_name=doc_name,
                    chapter=chapter.number,
                    chapter_title=chapter.title,
                    section=section.number,
                    section_title=section.title,
                    subsection="",
                    content=section_text,
                    page_start=page_start,
                    page_end=page_end,
                    token_count=token_count,
                    content_type=content_type,
                    content_preview=section_text[:200].strip(),
                )
                chunks.append(chunk)
            else:
                sub_chunks = _split_into_chunks(section_text, CHUNK_MIN_TOKENS, CHUNK_MAX_TOKENS)
                for sub_text in sub_chunks:
                    sub_tokens = _count_tokens(sub_text)
                    sub_type = _detect_content_type(sub_text)
                    chunk = Chunk(
                        chunk_id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        doc_name=doc_name,
                        chapter=chapter.number,
                        chapter_title=chapter.title,
                        section=section.number,
                        section_title=section.title,
                        subsection="",
                        content=sub_text,
                        page_start=page_start,
                        page_end=page_end,
                        token_count=sub_tokens,
                        content_type=sub_type,
                        content_preview=sub_text[:200].strip(),
                    )
                    chunks.append(chunk)

    return chunks
