import random

import fitz


def extract(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)

    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append({
            "page_num": i + 1,
            "text": text,
            "char_count": len(text),
        })

    outline = []
    toc = doc.get_toc()
    for level, title, page in toc:
        outline.append({
            "level": level,
            "title": title,
            "page": page,
        })

    metadata = dict(doc.metadata) if doc.metadata else {}

    doc.close()

    return {
        "total_pages": len(pages),
        "metadata": metadata,
        "pages": pages,
        "outline": outline,
        "has_outline": len(outline) > 0,
    }


def get_strategic_sample(pages: list[dict], outline: list[dict], total_pages: int) -> list[dict]:
    if total_pages <= 20:
        return [{"page": p["page_num"], "position": "full", "text": p["text"][:600].strip()}
                for p in pages if p["text"].strip()][:15]

    candidates = set()

    front_matter_candidates = [p for p in outline if p["level"] == 1]
    if front_matter_candidates:
        first = front_matter_candidates[0]["page"]
        candidates.add(first)
        for entry in front_matter_candidates[:5]:
            candidates.add(entry["page"])

    candidates.add(1)
    mid = total_pages // 2
    candidates.add(mid)
    candidates.add(total_pages)

    non_content = {c for c in candidates if 1 <= c <= total_pages}
    remaining = [i for i in range(1, total_pages + 1) if i not in non_content]
    random.shuffle(remaining)

    need = 15 - len(non_content)
    chosen = list(non_content) + remaining[:need]

    sample = []
    for pn in chosen:
        page = pages[pn - 1]
        text = page["text"][:600].strip()
        if text:
            sample.append({"page": pn, "position": "sample", "text": text})

    return sample[:15]
