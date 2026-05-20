import asyncio
import uuid
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag import rag_query

router = APIRouter(prefix="/api")

_tasks: dict[str, dict] = {}


class ChatRequest(BaseModel):
    doc_id: str
    message: str
    history: list[dict] = []


@router.post("/chat")
async def chat_start(req: ChatRequest):
    if not req.doc_id:
        raise HTTPException(status_code=400, detail="Document ID is required")
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "searching",
        "message": "Starting...",
        "progress": 0,
        "answer": None,
        "sources": [],
        "error": None,
        "created_at": time.time(),
    }

    async def _run():
        try:
            async def on_progress(stage: str, msg: str, pct: int):
                _tasks[task_id].update({"status": stage, "message": msg, "progress": pct})

            result = await rag_query(
                doc_id=req.doc_id,
                question=req.message.strip(),
                history=req.history,
                on_progress=on_progress,
            )
            _tasks[task_id].update({
                "status": "done",
                "message": "Complete",
                "progress": 100,
                "answer": result["answer"],
                "sources": result["sources"],
            })
        except Exception as e:
            _tasks[task_id].update({
                "status": "error",
                "message": str(e),
                "error": str(e),
            })

    asyncio.create_task(_run())

    return {"task_id": task_id, "status": "searching"}


@router.get("/chat/{task_id}")
async def chat_status(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task["status"],
        "message": task.get("message"),
        "progress": task.get("progress", 0),
        "answer": task.get("answer"),
        "sources": task.get("sources", []),
        "error": task.get("error"),
    }
