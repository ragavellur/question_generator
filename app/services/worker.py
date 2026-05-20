import asyncio
import logging

from app.services.db import dequeue_next, get_active
from app.services.pdf_processor.pipeline import process_pdf

logger = logging.getLogger(__name__)


async def worker_loop():
    while True:
        try:
            if get_active() is None:
                job = dequeue_next()
                if job is not None:
                    logger.info(f"[WORKER] Starting job for {job['filename']} ({job['doc_id']})")
                    try:
                        await process_pdf(job["filepath"], job["doc_id"], job["filename"])
                    except Exception as e:
                        logger.error(f"[WORKER] Unhandled error for {job['filename']}: {e}")
        except Exception as e:
            logger.error(f"[WORKER] Loop error: {e}")

        await asyncio.sleep(2)
