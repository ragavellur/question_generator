import json
import random
import asyncio
from collections import defaultdict

from app.config import DOMAIN_DEFINITIONS, SUBTYPE_INSTRUCTIONS
from app.services.llm_client import chat, _extract_json
from app.services.vector_store import query_chunks, get_chunks_by_ids, get_chunks_by_filter
from app.services.embedding import prepare_query
from app.models.schemas import QuestionConfig


from app.config import CHUNKS_PER_TYPE_CALL

TOKEN_BUDGETS = {
    "mcq": 500,
    "truefalse": 150,
    "fib": 200,
    "very_short": 250,
    "short": 300,
    "long": 450,
}

SYSTEM_PROMPT = """You are a question generator for educational content. Given context from textbooks or documents, generate questions that test different cognitive levels.

Always follow the exact JSON output schema specified. Generate questions that are accurate based SOLELY on the provided context. Do not make up information."""


def _type_label(qt: str) -> str:
    return {
        "mcq": "MCQ",
        "truefalse": "True/False",
        "fib": "FIB",
        "very_short": "Very Short",
        "short": "Short Answer",
        "long": "Long Answer",
    }.get(qt, qt)


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
        content = chunk['content'][:1200] if len(chunk['content']) > 1200 else chunk['content']
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
    instr = SUBTYPE_INSTRUCTIONS.get(qt, "")

    return f"""CONTEXT (textbook/document excerpts):
{context_text}

TASK: Generate exactly {count} {label} question(s) based on the context above. Spread questions across different chapters/sections shown in the context.

DOMAIN DEFINITIONS:
{domain_defs}
{difficulty_instruction}

QUESTION TYPE: {label}
{instr}

OUTPUT SCHEMA (strict JSON):
{{
  "questions": [
    {{
      "question_type": "{label}",
      "domain": "Factual|Comprehension|Application",
      "difficulty": "easy|medium|hard",
      "marks": <integer>,
      "question_text": "The full question text. For FIB, include ______ for the blank.",
      "options": ["a.) ...", "b.) ...", "c.) ...", "d.) ..."],
      "answer": "The correct answer. For FIB, just the word for the blank.",
      "source": "Ch X, Sec Y.Y or Ch X — match the numbers from the [Chunk N] headers above."
    }}
  ]
}}

RULES:
- Output MUST contain EXACTLY {count} question objects.
- Every question answerable from the context alone.
- Self-contained questions — never use "the text", "the passage", "the chapter", "above", "mentioned".
- FIB: blank is ______ (6 underscores), sentence 10-15 words.
- MCQ: exactly 4 options (a-d), all plausible, one correct.
- True/False: answer exactly "True" or "False".
- Spread questions across different chapters/sections in the context.
- Vary domains and difficulty.
- Return ONLY valid JSON, no explanation."""


def _sample_chunks(chunks: list[dict], n: int = CHUNKS_PER_TYPE_CALL) -> list[dict]:
    if len(chunks) <= n:
        return chunks
    return random.sample(chunks, n)


async def _call_type(qt: str, count: int, context_chunks: list[dict], domains: list[str], difficulty: str | None) -> list[dict]:
    prompt = _build_prompt_for_type(qt, count, context_chunks, domains, difficulty)
    per_q = TOKEN_BUDGETS.get(qt, 250)
    num_predict = count * per_q + 500

    raw = ""
    try:
        raw = await chat(prompt=prompt, system=SYSTEM_PROMPT, temperature=0.3, num_predict=num_predict)
        raw = raw.strip()
        result = json.loads(raw)
    except json.JSONDecodeError:
        try:
            result = _extract_json(raw)
        except Exception:
            raise RuntimeError(f"Non-JSON response: {raw[:400]}")
    except Exception as e:
        raise RuntimeError(f"Connection error: {e}")

    if isinstance(result, list):
        questions = result
    elif isinstance(result, dict):
        questions = result.get("questions", [])
    else:
        questions = []

    return _validate_questions(questions)


async def generate_questions_stream(config: QuestionConfig):
    context_chunks = await _retrieve_context(config)
    if not context_chunks:
        yield {"event": "error", "message": "No content chunks found for the selected chapters/sections."}
        return

    yield {"event": "status", "message": f"Loaded {len(context_chunks)} content chunks. Generating questions..."}

    queue: asyncio.Queue = asyncio.Queue()

    async def _run_generation():
        try:
            all_questions = []
            seen = set()
            type_counts = defaultdict(int)

            for qt in config.question_types:
                label = _type_label(qt)
                await queue.put({"event": "status", "message": f"Generating {config.count_per_type} {label} question(s)..."})

                try:
                    batch = _sample_chunks(context_chunks)
                    questions = await _call_type(qt, config.count_per_type + 1, batch, config.domains, config.difficulty)

                    new_qs = []
                    for q in questions:
                        qtype = q.get("question_type", "")
                        if qtype.lower().replace(" ", "_") != qt and qtype.lower().replace("/", "_") != qt:
                            continue
                        key = (q.get("question_text", ""), qtype)
                        if key not in seen:
                            seen.add(key)
                            new_qs.append(q)
                            all_questions.append(q)
                            type_counts[qt] += 1

                    await queue.put({
                        "event": "progress",
                        "type": label,
                        "questions": new_qs,
                        "count": len(new_qs),
                        "total_so_far": len(all_questions),
                    })
                except Exception as e:
                    await queue.put({"event": "warning", "message": f"{label}: {e}"})

            final = []
            type_final = defaultdict(int)
            for q in all_questions:
                raw_qt = q["question_type"].lower().replace(" ", "_").replace("/", "_")
                if raw_qt in config.question_types and type_final[raw_qt] < config.count_per_type:
                    type_final[raw_qt] += 1
                    final.append(q)

            for qt in config.question_types:
                need = config.count_per_type - type_final.get(qt, 0)
                if need > 0:
                    label = _type_label(qt)
                    await queue.put({"event": "status", "message": f"Generating {need} more {label} question(s)..."})
                    try:
                        batch = _sample_chunks(context_chunks)
                        questions = await _call_type(qt, need + 2, batch, config.domains, config.difficulty)
                        for q in questions:
                            qtype = q.get("question_type", "").lower().replace(" ", "_").replace("/", "_")
                            if qtype != qt:
                                continue
                            key = (q.get("question_text", ""), q.get("question_type", ""))
                            if key not in seen:
                                seen.add(key)
                                final.append(q)
                                type_final[qt] += 1
                                if type_final[qt] >= config.count_per_type:
                                    break
                    except Exception as e:
                        await queue.put({"event": "warning", "message": f"Retry {label}: {e}"})

            await queue.put({"event": "done", "questions": final, "total": len(final)})
        except Exception as e:
            await queue.put({"event": "error", "message": str(e)})

    gen_task = asyncio.create_task(_run_generation())

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=8.0)
                yield event
                if event.get("event") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "status", "message": "Working on it... (LLM is generating, this may take time)"}
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
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue

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
            continue

        q["domain"] = q.get("domain", "Factual").capitalize()
        if q["domain"] not in ("Factual", "Comprehension", "Application"):
            q["domain"] = "Factual"

        q["difficulty"] = q.get("difficulty", "medium").lower()
        if q["difficulty"] not in ("easy", "medium", "hard"):
            q["difficulty"] = "medium"

        q["marks"] = q.get("marks", 1)
        if not isinstance(q["marks"], int) or q["marks"] < 1:
            q["marks"] = 1

        q["question_text"] = (q.get("question_text") or "").strip()
        if not q["question_text"]:
            continue

        q["answer"] = (q.get("answer") or "").strip()
        if not q["answer"]:
            continue

        q["source"] = q.get("source", "")

        if q["question_type"] == "MCQ":
            opts = q.get("options", [])
            if not isinstance(opts, list) or len(opts) != 4:
                continue
            q["options"] = opts
        else:
            q["options"] = None

        valid.append(q)

    return valid
