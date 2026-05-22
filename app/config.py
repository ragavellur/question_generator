import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

N_CTX = int(os.getenv("N_CTX", "8192"))
N_THREADS = int(os.getenv("N_THREADS", "8"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_RAG_MODEL = os.getenv("OLLAMA_RAG_MODEL", "llama3.2:3b")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(BASE_DIR, "chroma_db"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploaded_docs"))

CHUNK_MIN_TOKENS = 400
CHUNK_MAX_TOKENS = 1200

PROFILE_CACHE_DIR = os.path.join(CHROMA_DB_PATH, "profiles")

RAG_CHUNK_COUNT = int(os.getenv("RAG_CHUNK_COUNT", "5"))
CHUNKS_PER_TYPE_CALL = int(os.getenv("CHUNKS_PER_TYPE_CALL", "8"))
CHUNK_CONTENT_MAX_CHARS = int(os.getenv("CHUNK_CONTENT_MAX_CHARS", "1200"))

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "3600"))
GROQ_RAG_CHUNK_COUNT = int(os.getenv("GROQ_RAG_CHUNK_COUNT", "5"))

BM25_ENABLED = True
BM25_INDEX_DIR = os.path.join(CHROMA_DB_PATH, "bm25")

RERANKER_ENABLED = True
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_RETRIEVE_COUNT = 30
RERANKER_TOP_K = 5

FRONT_MATTER_KEYWORDS = [
    "cover", "half title", "title page", "copyright", "dedication",
    "about the author", "contents", "table of contents", "preface",
    "foreword", "acknowledgment", "list of figures",
    "list of tables", "list of symbols", "nomenclature",
    "series", "edition", "published by", "all rights reserved",
]
BACK_MATTER_KEYWORDS = [
    "appendix", "bibliography", "index", "references",
    "glossary", "answers", "solutions", "credits",
]

QUESTION_TYPES = ["mcq", "truefalse", "fib", "very_short", "short", "long"]
DOMAINS = ["factual", "comprehension", "application"]
DIFFICULTIES = ["easy", "medium", "hard"]

DOMAIN_DEFINITIONS = {
    "factual": (
        "This question should test direct recall of facts, terms, and basic concepts "
        "from the text (e.g., 'What is...', 'Who is...', 'List the...'). Must include "
        "one of the following keywords: state, define, list, identify, name, mention, "
        "outline, recall, label, recognize, specify, classify, enumerate, highlight, indicate."
    ),
    "comprehension": (
        "This question should test understanding by asking the user to explain ideas or "
        "concepts (e.g., 'Explain why...', 'Compare...', 'Summarize...'). Must include "
        "one of the following keywords: compare, explain, discuss, describe, differentiate, "
        "analyze, evaluate, justify, interpret, elaborate, define, critique, summarize, "
        "illustrate, assess, translate, contrast, classify, discriminate, detect error, "
        "rectify error, identify relationship, extrapolate, interpolate, arrange in order."
    ),
    "application": (
        "This question should test the ability to apply knowledge in a new, hypothetical "
        "situation or real life situation (e.g., 'What would happen if...', 'How would you "
        "use this to solve...'). Must include one of the following keywords: calculate, "
        "predict, analyze, design, solve, construct, formulate, develop, apply, examine, "
        "demonstrate, compute, modify, synthesize, implement, discover, devise a plan, "
        "set of operations, select facts, select principle."
    ),
}

SUBTYPE_INSTRUCTIONS = {
    "mcq": "Each question must have 4 unique options (A-D). The marks value should be 1.",
    "truefalse": (
        "The question must be a statement. The answer must be only 'True' or 'False'. "
        "The marks value should be 1."
    ),
    "fib": (
        "CRITICAL: The question statement MUST contain a blank space represented by "
        "underscores (______). The blank should be an important concept/word the statement "
        "explains. Statement should be only 10-15 words. The marks value should be 1."
    ),
    "very_short": "The answer should be 2-3 full lines long. Do not use blanks. The marks value should be 2.",
    "short": "The answer should be a small paragraph (7-9 full lines). Do not use blanks. The marks value should be 3.",
    "long": (
        "The answer should be a large paragraph (12-15 full lines), more than 40 words. "
        "Do not add commentary like 'Please note'. The marks value should be 5."
    ),
}
