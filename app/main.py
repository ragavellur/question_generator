import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.routers import frontend, upload, documents, questions, chat
from app.services.llm_client import check_health
from app.services.task_manager import task_manager
from app.services.db import init_db
from app.services.worker import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)
        task_manager.cleanup_old()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("chroma_db", exist_ok=True)
    os.makedirs("uploaded_docs", exist_ok=True)

    print("Checking Ollama connection...")
    try:
        ok = await check_health()
        if ok:
            print("✓ Ollama is running")
        else:
            print("⚠ Ollama not reachable")
    except Exception as e:
        print(f"⚠ Ollama check failed: {e}")

    init_db()
    cleanup_task = asyncio.create_task(_cleanup_loop())
    worker_task = asyncio.create_task(worker_loop())
    yield
    worker_task.cancel()
    cleanup_task.cancel()


app = FastAPI(
    title="Question Generator",
    description="Upload PDF documents, extract structured content, and generate educational questions using LLM.",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(frontend.router)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(chat.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
