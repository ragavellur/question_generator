import json
import hashlib
import os

from app.config import PROFILE_CACHE_DIR
from app.services.llm_client import chat_json


PROFILE_PROMPT_SYSTEM = """You are a document structure analyzer. Given sample pages from a PDF document, analyze the document's structure and return a JSON profile that describes how to clean and parse it.

Focus on identifying:
1. Where the actual content begins (after front matter like cover, copyright, TOC, preface)
2. Where the back matter begins (index, bibliography, appendices)
3. Running header and footer patterns on odd vs even pages
4. Figure/table caption patterns
5. Noise elements to remove (page numbers, decorative headers, etc.)
6. How chapters, sections, and subsections are marked
7. Content types present (definitions, examples, problems, equations, summaries)

Return ONLY valid JSON, no commentary."""


PROFILE_PROMPT_TEMPLATE = """I am providing sample pages from a PDF document. Each sample has a page number, position label, and text content.

SAMPLE PAGES:
{pages_json}

Analyze the structure and return a JSON object with these fields:
- "front_matter_end_page": int or null - the last page number of front matter (cover, copyright, TOC, preface, etc.)
- "back_matter_start_page": int or null - the first page number of back matter (index, bibliography, appendices, etc.)
- "first_content_page": int - the page where actual content starts
- "header": object describing running header pattern: {{"odd_page_pattern": regex or null, "even_page_pattern": regex or null, "lines_to_remove": int}}
- "footer": object describing footer pattern: {{"pattern": regex or null, "lines_to_remove": int}}
- "chapter_pattern": regex to detect chapter headings (e.g., "Chapter \\\\d+", "CHAPTER \\\\d+", "\\\\d+\\\\.")
- "section_pattern": regex to detect section headings (e.g., "\\\\d+\\\\.\\\\d+")
- "subsection_pattern": regex or null for subsection headings
- "noise_patterns": list of {{"pattern": regex, "description": string}} for patterns that should be removed
- "figure_caption_pattern": regex or null to detect figure captions
- "table_caption_pattern": regex or null to detect table captions
- "page_number_pattern": regex to detect standalone page numbers
- "has_outline": bool - does the document have a table of contents outline?
- "structure_type": "chapters" | "sections" | "none"
- "notes": string - any observations

Be thorough. Look at every sample page carefully."""


def _cache_key(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        content = f.read(65536)
    return hashlib.md5(content).hexdigest()


def _cache_path(cache_key: str) -> str:
    os.makedirs(PROFILE_CACHE_DIR, exist_ok=True)
    return os.path.join(PROFILE_CACHE_DIR, f"{cache_key}.json")


def get_cached_profile(pdf_path: str) -> dict | None:
    key = _cache_key(pdf_path)
    path = _cache_path(key)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def cache_profile(pdf_path: str, profile: dict):
    key = _cache_key(pdf_path)
    path = _cache_path(key)
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)


async def generate_profile(pdf_path: str, pages: list[dict], outline: list[dict], total_pages: int) -> dict:
    cached = get_cached_profile(pdf_path)
    if cached:
        return cached

    from app.services.pdf_processor.extractor import get_strategic_sample
    sample = get_strategic_sample(pages, outline, total_pages)

    pages_json = json.dumps(sample, indent=2)

    profile = await chat_json(
        prompt=PROFILE_PROMPT_TEMPLATE.format(pages_json=pages_json),
        system=PROFILE_PROMPT_SYSTEM,
        temperature=0.05,
    )

    profile["has_outline"] = len(outline) > 0
    profile.setdefault("noise_patterns", [])
    profile.setdefault("keep_sections", ["summary", "problems", "examples", "definitions"])

    cache_profile(pdf_path, profile)
    return profile
