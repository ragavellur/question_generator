import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.models.schemas import QuestionConfig
from app.services.question_generator import generate_questions_stream, _type_label
from app.services.task_manager import task_manager
from app.services.vector_store import list_documents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/generate")
async def generate(config: QuestionConfig):
    if not config.doc_ids:
        raise HTTPException(status_code=400, detail="At least one document must be selected")
    if not config.question_types:
        raise HTTPException(status_code=400, detail="At least one question type must be selected")

    task_id = task_manager.create_task()
    type_labels = [_type_label(qt) for qt in config.question_types]
    total_target = len(config.question_types) * config.count_per_type

    all_docs = list_documents()
    doc_names = {}
    for d in all_docs:
        doc_names[d["id"]] = d["name"]

    task_config = {
        "doc_ids": config.doc_ids,
        "doc_names": [doc_names.get(did, did[:12] + "...") for did in config.doc_ids],
        "chapter_numbers": config.chapter_numbers,
        "section_numbers": config.section_numbers,
        "all_chapters": getattr(config, "all_chapters", False),
        "question_types": config.question_types,
        "type_labels": type_labels,
        "domains": config.domains,
        "difficulty": config.difficulty,
        "count_per_type": config.count_per_type,
    }

    task_manager.update_task(task_id, selected_types=type_labels, completed_types=[], current_type=None, total_target=total_target, config=task_config)

    async def _run():
        task_manager.update_task(task_id, status="running", message="Starting generation...")
        try:
            async for event in generate_questions_stream(config):
                if task_manager.get_task(task_id) is None:
                    logger.warning("Aborting _run() for task_id=%s — task deleted from DB", task_id)
                    break
                if event["event"] == "progress":
                    qs = event.get("questions", [])
                    logger.info(f"PROGRESS event: type={event.get('type')}, count={len(qs)}, total_so_far={event.get('total_so_far')}, task_id={task_id}")
                    task = task_manager.get_task(task_id)
                    existing = task["questions"] if task else []
                    existing.extend(qs)
                    comp = task.get("completed_types", []) if task else []
                    comp = list(dict.fromkeys(comp + [event.get("type")]))
                    task_manager.update_task(
                        task_id,
                        questions=existing,
                        completed_types=comp,
                        total_so_far=event.get("total_so_far", 0),
                        message=f"Generated {event.get('total_so_far', 0)} questions so far",
                    )
                elif event["event"] == "status":
                    update = {}
                    if not event.get("timeout"):
                        update["message"] = event.get("message", "")
                    if "current_type" in event:
                        update["current_type"] = event["current_type"]
                    if update:
                        task_manager.update_task(task_id, **update)
                elif event["event"] == "warning":
                    msg = event.get("message", "")
                    logger.warning("WARNING event: task_id=%s message=%s", task_id, msg)
                    ts = task_manager.get_task(task_id)
                    prev = ts.get("message", "") if ts else ""
                    task_manager.update_task(task_id, message=f"{prev} | {msg}")
                elif event["event"] == "done":
                    logger.info("DONE event: task_id=%s total=%d questions=%d", task_id, event.get("total", 0), len(event.get("questions", [])))
                    task_manager.update_task(
                        task_id,
                        status="done",
                        questions=event.get("questions", []),
                        completed_types=list(type_labels),
                        total_so_far=event.get("total", 0),
                        message=f"Completed — {event.get('total', 0)} questions generated",
                    )
                elif event["event"] == "error":
                    logger.error("ERROR event: task_id=%s message=%s", task_id, event.get("message", ""))
                    task_manager.update_task(
                        task_id,
                        status="error",
                        error=event.get("message", "Unknown error"),
                    )
        except Exception as e:
            logger.exception("UNHANDLED EXCEPTION in _run() for task_id=%s: %s", task_id, e)
            task_manager.update_task(task_id, status="error", error=str(e))

    asyncio.create_task(_run())

    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks")
async def list_tasks(status: str | None = None):
    all_tasks = task_manager.list_tasks()
    if status == "active":
        return [t for t in all_tasks if t.get("status") in ("queued", "running")]
    elif status:
        return [t for t in all_tasks if t.get("status") == status]
    return all_tasks


@router.get("/generate/{task_id}")
async def get_generation_status(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


class CleanupRequest(BaseModel):
    max_age: int = 3600


@router.post("/tasks/cleanup")
async def cleanup_tasks(req: CleanupRequest):
    min_age = 300  # don't delete tasks younger than 5 minutes
    age = max(req.max_age, min_age)
    count = task_manager.cleanup_old(max_age=age)
    return {"deleted": count}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    ok = task_manager.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


class PDFRequest(BaseModel):
    questions: list[dict]


@router.post("/generate-pdf")
async def generate_pdf(req: PDFRequest):
    import os
    import re
    from io import BytesIO
    from fpdf import FPDF

    import app as _app_mod
    _APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(_app_mod.__file__)))

    FONT_NAME = "Helvetica"
    FONT_DIRS = [
        os.path.join(_APP_DIR, "app", "static", "fonts"),
        "/usr/share/fonts/truetype/dejavu/",
        "/usr/share/fonts/dejavu/",
        "/System/Library/Fonts/",
        "/Library/Fonts/",
        "/System/Library/Fonts/Supplemental/",
    ]
    FONT_DIR = None
    for d in FONT_DIRS:
        if os.path.isdir(d):
            FONT_DIR = d
            break

    def safe(t: str) -> str:
        if FONT_NAME == "Helvetica":
            return t.encode("latin-1", errors="replace").decode("latin-1")
        return t

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    if FONT_DIR:
        regular = os.path.join(FONT_DIR, "DejaVuSans.ttf")
        bold = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
        if os.path.exists(regular):
            FONT_NAME = "DejaVu"
            pdf.add_font(FONT_NAME, "", regular)
            if os.path.exists(bold):
                pdf.add_font(FONT_NAME, "B", bold)

    l_margin = 15
    r_margin = 15
    pdf.set_left_margin(l_margin)
    page_w = 210 - l_margin - r_margin

    pdf.add_page()
    pdf.set_font(FONT_NAME, "B", 18)
    pdf.cell(0, 15, safe("Question Paper"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(FONT_NAME, "", 9)
    pdf.cell(0, 7, safe("Generated by Question Generator"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    type_order = {"MCQ": 1, "True/False": 2, "FIB": 3, "Very Short": 4, "Short Answer": 5, "Long Answer": 6}
    domain_order = {"Factual": 1, "Comprehension": 2, "Application": 3}

    sorted_qs = sorted(req.questions, key=lambda q: (
        type_order.get(q.get("question_type", ""), 99),
        domain_order.get(q.get("domain", ""), 99)
    ))

    diff_labels = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}

    for i, q in enumerate(sorted_qs, 1):
        qtype = q.get("question_type", "")
        domain = q.get("domain", "Factual")
        difficulty = q.get("difficulty", "medium")
        marks = q.get("marks", 1)
        source = q.get("source", "")
        qtext = q.get("question_text", "")
        opts = q.get("options", []) if q.get("options") else []

        meta_parts = [f"Q{i}", qtype, domain, diff_labels.get(difficulty, "Medium"), f"{marks} mks"]
        if source:
            meta_parts.append(source)

        pdf.set_font(FONT_NAME, "B", 8)
        meta_text = " | ".join(meta_parts)
        pdf.set_fill_color(245, 247, 250)
        pdf.cell(0, 6, safe(" " + meta_text), fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font(FONT_NAME, "", 11)
        qtext = q.get("question_text", "")
        pdf.multi_cell(0, 6, safe(qtext))
        pdf.ln(1)

        if opts and len(opts) == 4:
            pdf.set_font(FONT_NAME, "", 10)
            for label, opt_text in enumerate(opts):
                pdf.cell(0, 6, safe(f"     {opt_text}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

        pdf.set_draw_color(210, 215, 222)
        pdf.line(l_margin, pdf.get_y(), 210 - r_margin, pdf.get_y())
        pdf.ln(4)

    pdf.add_page()
    pdf.set_font(FONT_NAME, "B", 16)
    pdf.cell(0, 15, safe("Answer Key"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_draw_color(30, 77, 140)
    pdf.set_line_width(0.4)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(6)

    for i, q in enumerate(sorted_qs, 1):
        answer = q.get("answer", "")
        pdf.set_font(FONT_NAME, "B", 10)
        pdf.cell(12, 7, safe(f"Q{i}:"), new_x="RIGHT", new_y="TOP")
        pdf.set_font(FONT_NAME, "", 10)
        pdf.multi_cell(0, 7, safe(f"{answer}"))
        pdf.ln(1)

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="questions.pdf"'},
    )
