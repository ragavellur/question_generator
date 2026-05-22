import json
import re
import random
import asyncio
import time
import logging
from collections import defaultdict

from app.config import DOMAIN_DEFINITIONS, SUBTYPE_INSTRUCTIONS, CHUNKS_PER_TYPE_CALL, CHUNK_CONTENT_MAX_CHARS
from app.services.llm_client import chat, _extract_json, _sanitize_json_text
from app.services.vector_store import query_chunks, get_chunks_by_ids, get_chunks_by_filter
from app.services.embedding import prepare_query
from app.models.schemas import QuestionConfig

TOKEN_BUDGETS = {
    "mcq": 250,
    "truefalse": 80,
    "fib": 100,
    "very_short": 150,
    "short": 180,
    "long": 260,
}

RULES_BY_TYPE = {
    "mcq": "Each question must have exactly 4 unique options (a-d). Never include an options field for any other question type.",
    "truefalse": "The question must be a statement. The answer must be only 'True' or 'False'. Do NOT include an options field.",
    "fib": "The question statement MUST contain a blank space represented by ______ (6 underscores). Sentence should be 10-15 words. Do NOT include an options field.",
    "very_short": "The answer should be 2-3 full lines long. Do NOT include an options field. Do NOT include any options list.",
    "short": "The answer should be a small paragraph (7-9 full lines). Do NOT include an options field.",
    "long": "The answer should be a large paragraph (12-15 full lines, more than 40 words). Do NOT include an options field or any choices.",
}

SYSTEM_PROMPT = """You are a question generator for educational content. Given context from textbooks or documents, generate questions that test different cognitive levels.

Always follow the exact JSON output schema specified. Generate questions that are accurate based SOLELY on the provided context. Do not make up information.

CRITICAL: Your entire response must be a single valid JSON object. No markdown, no explanation, no extra text. All string values must be properly escaped — no raw control characters, no unescaped quotes, no invalid escape sequences."""


def _type_label(qt: str) -> str:
    return {
        "mcq": "MCQ",
        "truefalse": "True/False",
        "fib": "FIB",
        "very_short": "Very Short",
        "short": "Short Answer",
        "long": "Long Answer",
    }.get(qt, qt)


def _sanitize_content(text: str) -> str:
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', text)


def _build_prompt_for_type(
    qt: str,
    count: int,
    context_chunks: list[dict],
    domains: list[str],
    difficulty: str | None,
) -> str:
    context_text = ""
    for i, chunk in enumerate(context_chunks, 1):
        meta = chunk.get("metadata", {})
        header = f"[Chunk {i}]"
        if meta.get("chapter_title"):
            header += f" Chapter {meta.get('chapter', '?')}: {meta['chapter_title']}"
        if meta.get("section_title"):
            header += f" | Section {meta.get('section', '?')}: {meta['section_title']}"
        content = chunk['content']
        if CHUNK_CONTENT_MAX_CHARS > 0 and len(content) > CHUNK_CONTENT_MAX_CHARS:
            content = content[:CHUNK_CONTENT_MAX_CHARS]
        context_text += f"\n\n{header}\n{content}"

    domain_defs = "\n\n".join(
        f"### {d.capitalize()}\n{DOMAIN_DEFINITIONS.get(d, '')}"
        for d in domains
    )

    difficulty_instruction = ""
    if difficulty:
        dm = {
            "easy": "Questions should be straightforward and test basic recall.",
            "medium": "Questions should require moderate thinking, combining concepts.",
            "hard": "Questions should be challenging, requiring deep analysis.",
        }
        difficulty_instruction = f"\n\nDIFFICULTY: {difficulty.upper()}\n{dm.get(difficulty, '')}"

    label = _type_label(qt)
    type_rules = RULES_BY_TYPE.get(qt, "")
    options_line = '      "options": ["a.) ...", "b.) ...", "c.) ...", "d.) ..."],\n' if qt == "mcq" else ""
    marks_val = 1 if qt == "mcq" else "<integer>"
    answer_text = "The correct answer letter and text" if qt == "mcq" else "The correct answer"

    return f"""CONTEXT (textbook/document excerpts):
{context_text}

TASK: Generate exactly {count} {label} question(s) based on the context above. Spread questions across different chapters/sections shown in the context.

DOMAIN DEFINITIONS:
{domain_defs}
{difficulty_instruction}

QUESTION TYPE: {label}
{type_rules}

OUTPUT SCHEMA (strict JSON):
{{
  "questions": [
    {{
      "question_type": "{label}",
      "domain": "Factual|Comprehension|Application",
      "difficulty": "easy|medium|hard",
      "marks": {marks_val},
      "question_text": "The full question text",
{options_line}      "answer": "{answer_text}",
      "source": "Ch X, Sec Y.Y or Ch X"
    }}
  ]
}}

RULES:
- Output MUST contain EXACTLY {count} question objects.
- Every question answerable from the context alone.
- Self-contained questions — never use "the text", "the passage", "the chapter", "above", "mentioned".
- Do NOT reference equation numbers (e.g. "Equation 2.51"), chapter numbers (e.g. "Chapter 14"), section numbers, figure/table numbers, or any document-structure elements in the question text. Name the concept directly — the question must be fully understandable without seeing the source document.
- Do NOT include an "options" field for True/False, FIB, Very Short, Short Answer, or Long Answer. Only MCQ questions have options.
- Spread questions across different chapters/sections in the context.
- Vary domains and difficulty.
- Return ONLY valid JSON, no explanation, no markdown, no extra text.
- All string values must be properly escaped — no raw control characters."""


def _sample_chunks(chunks: list[dict], n: int = CHUNKS_PER_TYPE_CALL) -> list[dict]:
    if len(chunks) <= n:
        return chunks
    return random.sample(chunks, n)


_call_logger = logging.getLogger(f"{__name__}.call_type")


def _log_raw_on_fail(raw: str, label: str, prefix: str = "JSON parse failed"):
    preview = raw[:600] if raw else "(empty response)"
    _call_logger.error("%s [%s]: raw response (first 600 chars):\n%s", prefix, label, preview)


async def _call_type(qt: str, count: int, context_chunks: list[dict], domains: list[str], difficulty: str | None, label: str = "") -> list[dict]:
    for chunk in context_chunks:
        if "content" in chunk:
            chunk["content"] = _sanitize_content(chunk["content"])

    prompt = _build_prompt_for_type(qt, count, context_chunks, domains, difficulty)
    per_q = TOKEN_BUDGETS.get(qt, 250)
    num_predict = count * per_q + 300

    raw = ""
    try:
        raw = await chat(prompt=prompt, system=SYSTEM_PROMPT, temperature=0.3, num_predict=num_predict, label=label)
        raw = _sanitize_json_text(raw)
        result = json.loads(raw)
    except json.JSONDecodeError:
        try:
            result = _extract_json(raw)
        except Exception as extract_err:
            _log_raw_on_fail(raw, label, f"JSON decode + _extract_json failed: {extract_err}")
            raise RuntimeError(f"Non-JSON response: {raw[:400]}")
    except Exception as e:
        _log_raw_on_fail(raw, label, f"HTTP/connection error: {e}")
        raise RuntimeError(f"Connection error: {e}")

    if isinstance(result, list):
        questions = result
    elif isinstance(result, dict):
        questions = result.get("questions", [])
    else:
        questions = []

    validated = _validate_questions(questions)
    _call_logger.info("CALL_TYPE [%s]: LLM returned %d raw, %d validated", label, len(questions), len(validated))
    return validated


async def generate_questions_stream(config: QuestionConfig):
    context_chunks = await _retrieve_context(config)
    if not context_chunks:
        yield {"event": "error", "message": "No content chunks found for the selected chapters/sections."}
        return

    yield {"event": "status", "message": f"Loaded {len(context_chunks)} content chunks. Generating questions..."}

    queue: asyncio.Queue = asyncio.Queue()
    retry_round = 0

    async def _run_generation():
        nonlocal retry_round
        try:
            all_questions = []
            seen = set()

            for qt in config.question_types:
                label = _type_label(qt)
                await queue.put({"event": "status", "message": f"Generating {config.count_per_type} {label} question(s)...", "current_type": label})
                try:
                    batch = _sample_chunks(context_chunks)
                    questions = await _call_type(qt, config.count_per_type, batch, config.domains, config.difficulty, label=f"{config.count_per_type}x{label}")
                    new_qs = []
                    expected_label = _type_label(qt)
                    for q in questions:
                        if q.get("question_type", "") != expected_label:
                            continue
                        key = (q.get("question_text", ""), expected_label)
                        if key not in seen:
                            seen.add(key)
                            new_qs.append(q)
                            all_questions.append(q)

                    await queue.put({
                        "event": "progress",
                        "type": label,
                        "questions": new_qs,
                        "count": len(new_qs),
                        "total_so_far": len(all_questions),
                    })
                except Exception as e:
                    logging.getLogger(__name__).warning("First-pass %s failed: %s", label, e)
                    await queue.put({"event": "warning", "message": f"{label}: {e}"})

            _label_to_key = {_type_label(k): k for k in config.question_types}
            final = []
            type_final = defaultdict(int)
            for q in all_questions:
                raw_qt = _label_to_key.get(q["question_type"], "")
                if raw_qt in config.question_types and type_final[raw_qt] < config.count_per_type:
                    type_final[raw_qt] += 1
                    final.append(q)

            type_summary = ", ".join(f"{_type_label(qt)}={type_final.get(qt,0)}" for qt in config.question_types)
            logging.getLogger(__name__).info("First pass complete: all_questions=%d, per_type=[%s]", len(all_questions), type_summary)

            for qt in config.question_types:
                need = config.count_per_type - type_final.get(qt, 0)
                if need > 0:
                    retry_round += 1
                    if retry_round > 2:
                        logging.getLogger(__name__).warning("Max retries reached for %s, giving up", _type_label(qt))
                        break
                    logging.getLogger(__name__).info("Retry %d for %s: have %d, need %d more", retry_round, _type_label(qt), type_final.get(qt, 0), need)
                    label = _type_label(qt)
                    await queue.put({"event": "status", "message": f"Generating {need} more {label} question(s)...", "current_type": label})
                    try:
                        batch = _sample_chunks(context_chunks)
                        questions = await _call_type(qt, need + 1, batch, config.domains, config.difficulty, label=f"{need+1}x{label}")
                        expected_label = _type_label(qt)
                        for q in questions:
                            if q.get("question_type", "") != expected_label:
                                continue
                            key = (q.get("question_text", ""), q.get("question_type", ""))
                            if key not in seen:
                                seen.add(key)
                                final.append(q)
                                type_final[qt] += 1
                                if type_final[qt] >= config.count_per_type:
                                    break
                    except Exception as e:
                        logging.getLogger(__name__).warning("Retry %s failed: %s", label, e)
                        await queue.put({"event": "warning", "message": f"Retry {label}: {e}"})

            final_summary = ", ".join(f"{_type_label(qt)}={type_final.get(qt,0)}" for qt in config.question_types)
            logging.getLogger(__name__).info("Generation complete: final=%d, per_type=[%s]", len(final), final_summary)
            await queue.put({"event": "done", "questions": final, "total": len(final)})
        except Exception as e:
            logging.getLogger(__name__).exception("Unexpected error in _run_generation: %s", e)
            await queue.put({"event": "error", "message": str(e)})

    gen_task = asyncio.create_task(_run_generation())
    had_progress = False
    had_warning = False
    last_status = ""
    last_current_type = None
    last_status_time = 0.0

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=8.0)
                if event.get("event") == "progress":
                    had_progress = True
                    had_warning = False
                if event.get("event") == "status":
                    last_status = event.get("message", "")
                    last_current_type = event.get("current_type")
                    last_status_time = time.time()
                if event.get("event") == "warning":
                    had_warning = True
                yield event
                if event.get("event") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                if had_warning:
                    continue
                if not last_status:
                    continue
                elapsed = int(time.time() - last_status_time)
                yield {"event": "status", "message": f"{last_status} (waiting {elapsed}s, LLM working)", "current_type": last_current_type, "timeout": True}
    finally:
        if not gen_task.done():
            gen_task.cancel()
            try:
                await gen_task
            except asyncio.CancelledError:
                pass


async def _retrieve_context(config: QuestionConfig) -> list[dict]:
    if config.chunk_ids:
        return get_chunks_by_ids(config.chunk_ids)

    filters = {"doc_id": config.doc_ids[0]} if len(config.doc_ids) == 1 else None

    if config.chapter_numbers:
        filters = filters or {}
        filters["chapter"] = config.chapter_numbers
    if config.section_numbers:
        filters = filters or {}
        filters["section"] = config.section_numbers

    if config.chapter_numbers and len(config.chapter_numbers) > 1:
        all_chunks = get_chunks_by_filter(filters, limit=10000)
        if not all_chunks:
            return []
        random.shuffle(all_chunks)
        return all_chunks

    if config.section_numbers and len(config.section_numbers) > 1:
        return get_chunks_by_filter(filters, limit=10000)

    query = prepare_query(
        f"Generate educational questions about {' '.join(config.chapter_numbers or [])} "
        f"for {', '.join(config.question_types)} questions"
    )

    return query_chunks(
        query_text=query,
        n_results=500,
        filters=filters,
    )


def _validate_questions(questions: list[dict]) -> list[dict]:
    vlog = logging.getLogger(f"{__name__}.validate")
    valid = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            vlog.warning("Q%d: skipped — not a dict", i)

        qtype = q.get("question_type", "").lower().replace(" ", "_")
        if qtype in ("mcq", "mcqs"):
            q["question_type"] = "MCQ"
        elif qtype in ("true/false", "truefalse", "tf"):
            q["question_type"] = "True/False"
        elif qtype in ("fib", "fill_in_the_blank", "fill in the blank"):
            q["question_type"] = "FIB"
        elif qtype in ("short_answer", "short"):
            q["question_type"] = "Short Answer"
        elif qtype in ("long_answer", "long"):
            q["question_type"] = "Long Answer"
        elif qtype in ("very_short", "very short"):
            q["question_type"] = "Very Short"
        else:
            vlog.warning("Q%d: skipped — unknown question_type '%s'", i, q.get("question_type", ""))
            continue

        q["domain"] = q.get("domain", "Factual").capitalize()
        if q["domain"] not in ("Factual", "Comprehension", "Application"):
            vlog.warning("Q%d: invalid domain '%s', defaulting to Factual", i, q.get("domain", ""))
            q["domain"] = "Factual"

        q["difficulty"] = q.get("difficulty", "medium").lower()
        if q["difficulty"] not in ("easy", "medium", "hard"):
            vlog.warning("Q%d: invalid difficulty '%s', defaulting to medium", i, q.get("difficulty", ""))
            q["difficulty"] = "medium"

        q["marks"] = q.get("marks", 1)
        if not isinstance(q["marks"], int) or q["marks"] < 1:
            vlog.warning("Q%d: invalid marks '%s', defaulting to 1", i, q.get("marks", ""))
            q["marks"] = 1

        q["question_text"] = (q.get("question_text") or "").strip()
        if not q["question_text"]:
            vlog.warning("Q%d: skipped — empty question_text", i)
            continue

        q["answer"] = (q.get("answer") or "").strip()
        if not q["answer"]:
            vlog.warning("Q%d: skipped — empty answer", i)
            continue

        q["source"] = q.get("source", "")

        if q["question_type"] == "MCQ":
            opts = q.get("options", [])
            if not isinstance(opts, list) or len(opts) != 4:
                vlog.warning("Q%d: skipped — MCQ with %d options (need 4)", i, len(opts) if isinstance(opts, list) else 0)
                continue
            q["options"] = opts
        else:
            q["options"] = None

        valid.append(q)

    return valid
