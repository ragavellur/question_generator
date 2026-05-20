from fastapi import APIRouter, HTTPException
from app.services.document_manager import get_all_documents, get_document_hierarchy, remove_document
from app.services.vector_store import get_chunks_by_filter

router = APIRouter(prefix="/api/documents")


@router.get("")
async def list_documents():
    return get_all_documents()


@router.get("/{doc_id}/hierarchy")
async def document_hierarchy(doc_id: str):
    hierarchy = get_document_hierarchy(doc_id)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Document not found")
    return hierarchy


@router.get("/{doc_id}/chunks")
async def document_chunks(
    doc_id: str,
    chapter: str | None = None,
    section: str | None = None,
):
    filters = {"doc_id": doc_id}
    if chapter:
        filters["chapter"] = chapter
    if section:
        filters["section"] = section

    chunks = get_chunks_by_filter(filters, limit=100)
    return chunks


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    remove_document(doc_id)
    return {"status": "deleted", "document_id": doc_id}
