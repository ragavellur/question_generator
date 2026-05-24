import asyncio
from app.services.pdf_processor.extractor import extract
from app.services.pdf_processor.llm_profiler import generate_profile
from app.services.pdf_processor.cleaner import clean_pages
from app.services.pdf_processor.structure import detect_structure
from app.services.pdf_processor.chunker import chunk_document
from app.services.pdf_processor.llm_verifier import verify_sample
from app.services.embedding import embed_chunks
from app.services.vector_store import store_chunks
from app.services.bm25_store import index_document

from app.models.schemas import DocumentProfile
from app.models.state import set_processing_status
from app.config import FRONT_MATTER_KEYWORDS, BACK_MATTER_KEYWORDS


def _merge_outline_boundaries(profile: dict, outline: list[dict]):
    if not outline:
        return

    last_front_page = 0
    back_matter_start = None
    first_content_page = None

    for entry in outline:
        level = entry.get("level", 1)
        if level != 1:
            continue
        title = entry.get("title", "").lower().strip()
        page = entry.get("page")
        if not page or page < 1:
            continue

        is_front = any(kw in title for kw in FRONT_MATTER_KEYWORDS)
        is_back = any(kw in title for kw in BACK_MATTER_KEYWORDS)

        if is_front:
            last_front_page = max(last_front_page, page)
        elif is_back and back_matter_start is None:
            back_matter_start = page
        elif not is_front and not is_back and first_content_page is None:
            first_content_page = page

    if last_front_page > 0:
        profile["front_matter_end_page"] = last_front_page
    if back_matter_start is not None:
        profile["back_matter_start_page"] = back_matter_start
    if first_content_page is not None:
        profile["first_content_page"] = first_content_page


async def process_pdf(pdf_path: str, doc_id: str, doc_name: str):
    try:
        set_processing_status(doc_id, "extracting", 5, "Extracting text from PDF...")
        await asyncio.sleep(0)

        extracted = extract(pdf_path)
        pages = extracted["pages"]
        outline = extracted["outline"]
        total_pages = extracted["total_pages"]
        print(f"[PIPELINE] {doc_name}: {total_pages} pages, {len(outline)} outline entries, {len(pages)} page texts")

        set_processing_status(doc_id, "profiling", 15, "LLM is analyzing document structure...")
        await asyncio.sleep(0)

        profile = await generate_profile(pdf_path, pages, outline, total_pages)
        print(f"[PIPELINE] Profile: front_matter_end={profile.get('front_matter_end_page')}, back_matter_start={profile.get('back_matter_start_page')}, first_content={profile.get('first_content_page')}, has_outline={profile.get('has_outline')}")

        _merge_outline_boundaries(profile, outline)
        print(f"[PIPELINE] After merge: front_matter_end={profile.get('front_matter_end_page')}, back_matter_start={profile.get('back_matter_start_page')}, first_content={profile.get('first_content_page')}")

        set_processing_status(doc_id, "cleaning", 30, "Cleaning noise from extracted text...")
        await asyncio.sleep(0)

        cleaned_pages = clean_pages(pages, profile)
        print(f"[PIPELINE] Cleaned pages: {len(cleaned_pages)}")

        set_processing_status(doc_id, "detecting_structure", 45, "Detecting chapters and sections...")
        await asyncio.sleep(0)

        chapters = detect_structure(outline, total_pages, profile)
        print(f"[PIPELINE] Chapters detected: {len(chapters)}")

        set_processing_status(doc_id, "chunking", 60, "Creating semantic chunks...")
        await asyncio.sleep(0)

        chunks = chunk_document(doc_id, doc_name, cleaned_pages, chapters)
        print(f"[PIPELINE] Chunks created: {len(chunks)}")

        if len(chunks) == 0:
            set_processing_status(doc_id, "done", 100, "Processing complete! (no chunks)")
            return

        set_processing_status(doc_id, "verifying", 75, "Verifying chunk quality with LLM...")
        await asyncio.sleep(0)

        verification_results = await verify_sample(
            [c.model_dump() for c in chunks],
            sample_size=min(3, len(chunks)),
        )
        issues_found = any(
            v["result"].get("quality_score", 5) < 3
            for v in verification_results
        )
        print(f"[PIPELINE] Verification issues: {issues_found}")

        if issues_found:
            set_processing_status(doc_id, "re_cleaning", 80, "Re-cleaning based on LLM feedback...")
            await asyncio.sleep(0)

            profile["noise_patterns"].append({
                "pattern": "",
                "description": "Additional noise patterns from LLM verification",
            })

            cleaned_pages = clean_pages(pages, profile)
            chunks = chunk_document(doc_id, doc_name, cleaned_pages, chapters)
            verification_results = await verify_sample(
                [c.model_dump() for c in chunks],
                sample_size=min(2, len(chunks)),
            )
            print(f"[PIPELINE] After re-clean: {len(chunks)} chunks")

        set_processing_status(doc_id, "embedding", 85, "Generating embeddings...")
        await asyncio.sleep(0)

        print(f"[PIPELINE] Starting embed_chunks for {len(chunks)} chunks...")
        try:
            await embed_chunks(chunks, doc_id)
            embedded = sum(1 for c in chunks if c.embedding is not None)
            print(f"[PIPELINE] Embedded {embedded}/{len(chunks)} chunks")
        except Exception as e:
            print(f"[PIPELINE] Embedding failed: {e}")

        set_processing_status(doc_id, "storing", 95, "Storing in vector database...")
        await asyncio.sleep(0)

        chapter_data = [c.model_dump() for c in chapters]
        store_chunks(chunks, doc_id, doc_name, chapter_data)
        index_document(doc_id, chunks)

        set_processing_status(doc_id, "done", 100, "Processing complete!")

    except Exception as e:
        set_processing_status(doc_id, "error", 0, f"Processing failed: {str(e)}")
