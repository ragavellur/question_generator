import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.services.document_manager import save_uploaded_file
from app.models.state import get_processing_status, set_processing_status
from app.services.db import enqueue, get_queue_position, get_active, queue_length, is_processing

router = APIRouter(prefix="/api")


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    doc_id, filepath = save_uploaded_file(file.filename, content)
    enqueue(doc_id, file.filename, filepath)
    set_processing_status(doc_id, "queued", 0, "File uploaded, waiting in queue...")
    pos = get_queue_position(doc_id)

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "queued",
        "queue_position": pos,
    }


@router.get("/upload/{doc_id}/status")
async def get_upload_status(doc_id: str):
    status = get_processing_status(doc_id)
    if status is None:
        return {"document_id": doc_id, "status": "unknown", "progress": 0, "message": ""}
    return status


@router.get("/processing/status")
async def get_processing_status_global():
    from app.services.task_manager import task_manager as _tm
    active = get_active()
    qlen = queue_length()
    return {
        "processing": is_processing(),
        "active_doc_id": active["doc_id"] if active else None,
        "active_filename": active["filename"] if active else None,
        "active_status": active["status"] if active else None,
        "active_message": active["message"] if active else None,
        "queue_length": qlen,
        "generation_active": _tm.has_active_task(),
    }
