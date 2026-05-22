import json
import random
from collections import defaultdict

from app.config import DOMAIN_DEFINITIONS, SUBTYPE_INSTRUCTIONS
from app.services.llm_client import chat_json
from app.services.vector_store import query_chunks, get_chunks_by_ids, get_chunks_by_filter
from app.services.embedding import prepare_query
from app.models.schemas import QuestionConfig, Question


SYSTEM_PROMPT = """You are a question generator for educational content. Given context from textbooks or documents, generate questions that test different cognitive levels.

Always follow the exact JSON output schema specified. Generate questions that are accurate based SOLELY on the provided context. Do not make up information."""


def _build_prompt(config: QuestionConfig, context_chunks: list[dict]) -> str:
    context_text = ""
    for i, chunk in enumerate(context_chunks, 1):
        meta = chunk.get("metadata", {})
        header = f"[Chunk {i}]"
        if meta.get("chapter_title"):
            header += f" Chapter {meta.get('chapter', '?')}: {meta['chapter_title']}"
        if meta.get("section_title"):
            header += f" | Section {meta.get('section', '?')}: {meta['section_title']}"
        context_text += f"\n\n{header}\n{chunk['content']}"

    types_section = ""
    for qt in config.question_types:
        types_section += f"\n\n### {qt.upper()}\nGenerate exactly {config.count_per_type} question(s).{SUBTYPE_INSTRUCTIONS.get(qt, '')}"

    domain_defs = "\n\n".join(
        f"### {d.capitalize()}\n{DOMAIN_DEFINITIONS.get(d, '')}"
        for d in config.domains
    )

    total_needed = len(config.question_types) * config.count_per_type

    difficulty_instruction = ""
    if config.difficulty:
        difficulty_map = {
            "easy": "Questions should be straightforward and test basic recall.",
            "medium": "Questions should require moderate thinking, combining concepts.",
            "hard": "Questions should be challenging, requiring deep analysis.",
        }
        difficulty_instruction = f"\n\nDIFFICULTY: {config.difficulty.upper()}\n{difficulty_map.get(config.difficulty, '')}"

    return f"""CONTEXT (textbook/document excerpts):
{context_text}

TASK: Generate exactly {total_needed} questions total, with exactly {config.count_per_type} questions for EACH type listed below. Spread questions across ALL chapters/sections shown in the context — do not focus on only one chapter.

DOMAIN DEFINITIONS FOR EACH QUESTION:
{domain_defs}
{difficulty_instruction}

QUESTION TYPES (generate exactly {config.count_per_type} per type):{types_section}

OUTPUT SCHEMA (strict JSON):
{{
  "questions": [
    {{
      "question_type": "MCQ|True/False|FIB|Very Short|Short Answer|Long Answer",
      "domain": "Factual|Comprehension|Application",
      "difficulty": "easy|medium|hard",
      "marks": <integer>,
      "question_text": "The full question text. For FIB, include ______ for the blank.",
      "options": ["a.) ...", "b.) ...", "c.) ...", "d.) ..."],
      "answer": "The correct answer. For FIB, just the word for the blank.",
      "source": "The source chapter/section. If the chunk header includes a section, use format 'Ch X, Sec Y.Y' (e.g. 'Ch 3, Sec 3.2'). If only a chapter, use format 'Ch X' (e.g. 'Ch 3'). ALWAYS use exactly one of these two formats — never just 'Sec Y.Y' alone. Must match numbers exactly from the [Chunk N] headers in CONTEXT above."
    }}
  ]
}}

IMPORTANT RULES:
- The output MUST contain EXACTLY {total_needed} questions: {config.count_per_type} MCQ, {config.count_per_type} True/False, {config.count_per_type} FIB, {config.count_per_type} Very Short, {config.count_per_type} Short Answer, {config.count_per_type} Long Answer.
- Every question MUST be answerable from the provided context alone.
- Questions must be self-contained. NEVER use vague references like "the text", "the passage", "the document", "the chapter", "above", "mentioned", "discussed", "this topic". Explicitly name the concept.
- Do NOT reference equation numbers (e.g. "Equation 2.51"), chapter numbers (e.g. "Chapter 14"), section numbers, figure/table numbers, or any document-structure elements in the question text. Name the concept directly — the question must be fully understandable without seeing the source document.
- For FIB: blank is ______ (6 underscores), sentence 10-15 words.
- For MCQ: exactly 4 options (a-d), all plausible, one correct.
- For True/False: answer must be exactly "True" or "False".
- Spread questions across ALL chapters/sections in the context. Do NOT focus on only one or two chapters.
- Vary domains and difficulty levels across questions within each type.
- Return ONLY valid JSON, no explanation."""


async def generate_questions(config: QuestionConfig) -> list[dict]:
    context_chunks = await _retrieve_context(config)

    if not context_chunks:
        return []

    prompt = _build_prompt(config, context_chunks)
    total_needed = len(config.question_types) * config.count_per_type
    num_predict = total_needed * 250 + 800

    try:
        result = await chat_json(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            temperature=0.3,
            num_predict=num_predict,
        )

        if isinstance(result, list):
            questions = result
        elif isinstance(result, dict):
            questions = result.get("questions", [])
        else:
            questions = []

        if not questions:
            raise RuntimeError("LLM returned empty response")

        validated = _validate_questions(questions)
        return validated

    except Exception as e:
        raise RuntimeError(f"Question generation failed: {e}")


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

    total_needed = len(config.question_types) * config.count_per_type

    if config.chapter_numbers and len(config.chapter_numbers) > 1:
        all_chunks = get_chunks_by_filter(filters, limit=10000)
        if not all_chunks:
            return []

        by_chapter = defaultdict(list)
        for c in all_chunks:
            ch = c.get("metadata", {}).get("chapter", "?")
            by_chapter[ch].append(c)

        per_chapter = max(3, total_needed * 5 // len(config.chapter_numbers))

        sampled = []
        for ch in config.chapter_numbers:
            chunks = by_chapter.get(ch, [])
            if len(chunks) > per_chapter:
                random.shuffle(chunks)
                sampled.extend(chunks[:per_chapter])
            else:
                sampled.extend(chunks)

        max_chunks = min(len(sampled), total_needed * 5)
        if len(sampled) > max_chunks:
            random.shuffle(sampled)
            sampled = sampled[:max_chunks]

        return sampled

    if config.section_numbers and len(config.section_numbers) > 1:
        return get_chunks_by_filter(filters, limit=10000)

    query = prepare_query(
        f"Generate educational questions about {' '.join(config.chapter_numbers or [])} "
        f"for {', '.join(config.question_types)} questions"
    )

    return query_chunks(
        query_text=query,
        n_results=min(20, total_needed * 5),
        filters=filters,
    )


def _validate_questions(questions: list[dict]) -> list[dict]:
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue

        qtype = q.get("question_type", "").lower().replace(" ", "_")
        if qtype in ["mcq", "mcqs"]:
            q["question_type"] = "MCQ"
        elif qtype in ["true/false", "truefalse", "tf"]:
            q["question_type"] = "True/False"
        elif qtype in ["fib", "fill_in_the_blank", "fill in the blank"]:
            q["question_type"] = "FIB"
        elif qtype in ["short_answer", "short"]:
            q["question_type"] = "Short Answer"
        elif qtype in ["long_answer", "long"]:
            q["question_type"] = "Long Answer"
        elif qtype in ["very_short", "very short"]:
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
