# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (Vanilla JS)                         │
│  main.js · chat.js · tasks.js · Tailwind CSS CDN · Jinja2 templates │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP (REST + polling)
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI Server (uvicorn)                        │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Frontend │ │  Upload  │ │Documents │ │Questions │ │   Chat   │  │
│  │  Router  │ │  Router  │ │  Router  │ │  Router  │ │  Router   │  │
│  │  (pages) │ │ /api/up  │ │/api/docs │ │/api/gen  │ │ /api/chat │  │
│  └──────────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│                     │            │            │              │        │
│                     ▼            ▼            ▼              ▼        │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                       Service Layer                            │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │  Vector   │  │   BM25   │  │   RAG    │  │    LLM       │  │   │
│  │  │  Store    │  │  Store   │  │  Query   │  │   Client     │  │   │
│  │  │(ChromaDB) │  │(pickle)  │  │(Ollama/  │  │  (Ollama)    │  │   │
│  │  │           │  │          │  │  Groq)   │  │              │  │   │
│  │  └──────────┘  └──────────┘  └────┬─────┘  └──────┬───────┘  │   │
│  │  ┌──────────┐  ┌──────────┐      │                │           │   │
│  │  │  Task     │  │  Reranker│      └────────────────┘           │   │
│  │  │  Manager  │  │(sentence │                                    │   │
│  │  │ (SQLite)  │  │transf.) │                                    │   │
│  │  └──────────┘  └──────────┘                                    │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │              PDF Processor Pipeline                       │   │   │
│  │  │  Extract → Profile → Clean → Structure → Chunk →         │   │   │
│  │  │  Verify → Embed → Store → BM25 Index                     │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│  Ollama  │ │  Groq    │ │ ChromaDB │ │   SQLite     │
│ (local)  │ │(cloud)   │ │(vec db)  │ │ processing.db│
│  LLM +   │ │  LLM     │ │ chunks + │ │ tasks, queue  │
│  embed   │ │          │ │ docs     │ │ logs         │
└──────────┘ └──────────┘ └──────────┘ └──────────────┘
```

## Startup & Lifespan

Defined in `app/main.py`. On server start:

1. Create data directories (`chroma_db/`, `uploaded_docs/`)
2. Check Ollama connectivity (logs warning if unreachable)
3. Initialize SQLite tables (`init_db()` — processing_queue, tasks, generation_log)
4. `TaskManager.__init__()` marks any queued/running tasks as "error" (stale from previous run)
5. Launch background workers:
   - **`worker_loop()`** (every 2s) — dequeues PDF processing jobs
   - **`_cleanup_loop()`** (every 5min) — deletes old finished tasks via `cleanup_old()`

## Routers

### Frontend Router (`app/routers/frontend.py`)
Serves 6 Jinja2 HTML pages: `/`, `/upload`, `/documents`, `/generate`, `/chat`, `/tasks`. Static files mounted at `/static`.

### Upload Router (`app/routers/upload.py`)
- **`POST /api/upload`** — Accepts PDF file, saves to `UPLOAD_DIR`, enqueues in SQLite, returns `document_id`
- **`GET /api/upload/{doc_id}/status`** — Returns processing progress
- **`GET /api/processing/status`** — Global processing state (active job, queue length, generation status)

### Documents Router (`app/routers/documents.py`)
- **`GET /api/documents`** — Lists all processed documents
- **`GET /api/documents/{doc_id}/hierarchy`** — Chapter/section tree
- **`GET /api/documents/{doc_id}/chunks`** — Content chunks with optional chapter/section filter
- **`DELETE /api/documents/{doc_id}`** — Deletes document (ChromaDB + filesystem)

### Questions Router (`app/routers/questions.py`)
- **`POST /api/generate`** — Starts async generation, returns `task_id`
- **`GET /api/generate/{task_id}`** — Poll task status/questions/progress
- **`GET /api/tasks`** — List all tasks
- **`POST /api/tasks/cleanup`** — Delete old finished tasks (min 300s age)
- **`DELETE /api/tasks/{task_id}`** — Delete specific task
- **`POST /api/generate-pdf`** — Render questions as PDF (fpdf2)

### Chat Router (`app/routers/chat.py`)
- **`POST /api/chat`** — Start RAG query, returns `task_id`
- **`GET /api/chat/{task_id}`** — Poll answer, sources, progress

## Service Layer

### PDF Processor Pipeline (`app/services/pdf_processor/`)
Orchestrated by `pipeline.py:process_pdf()`:

| Step | % | Component | Description |
|------|---|-----------|-------------|
| Extract | 5% | `extractor.py` | PyMuPDF text + outline extraction per page |
| Profile | 15% | `llm_profiler.py` | LLM analyzes sample pages → header/footer patterns, noise patterns, chapter detection, front/back matter boundaries |
| Merge | — | `pipeline.py` | `_merge_outline_boundaries()` refines front/back matter from outline data |
| Clean | 30% | `cleaner.py` | Removes headers, footers, page numbers, figure captions, noise patterns per page |
| Structure | 45% | `structure.py` | Builds chapter/section tree from outline or LLM-detected patterns |
| Chunk | 60% | `chunker.py` | Splits each chapter section into semantic chunks (min 400t, max 1200t) |
| Verify | 75% | `llm_verifier.py` | LLM checks 3 random chunks for quality; if score < 3, re-cleans |
| Re-clean | 80% | `cleaner.py` | Only if verify found issues: stricter cleaning + re-chunking |
| Embed | 85% | `embedding.py` | Batch embedding via Ollama (30 at a time) with progress+ETA |
| Store | 95% | `vector_store.py` | Upserts to ChromaDB + `bm25_store.py` pickles BM25 index |
| Done | 100% | — | Marks SQLite queue as done |

### Question Generator (`app/services/question_generator.py`)

Async generator yielding events (`status`, `progress`, `warning`, `done`, `error`).

**Flow:**
1. `_retrieve_context(config)` — Get chunks by chunk_ids, by doc+chapter+section filters, or embedding query
2. For each requested question type:
   a. `_sample_chunks(context, 8)` — Randomly sample 8 context chunks
   b. `_build_prompt_for_type(qt, count, chunks, domains, difficulty)` — Build prompt with context, domain definitions, JSON schema
   c. Call LLM via `_call_type()` → sanitize → `_validate_questions()` → deduplicate
   d. Yield `progress` event
3. If any type is short of target after first pass, retry up to 2 rounds
4. Yield `done` with final sorted question list

**Prompt construction:**
- System prompt with JSON-only output instruction
- Context chunks (sanitized, each ≤1200 chars)
- Per-type generation rules (token budgets, option requirements)
- Domain definitions with examples
- Difficulty guidelines
- JSON array schema with field descriptions

**Validation (`_validate_questions()`):**
- Normalizes question_type (mcq→MCQ, truefalse→True/False, etc.)
- Validates domain ∈ {Factual, Comprehension, Application}
- Validates difficulty ∈ {easy, medium, hard}
- Validates marks ≥ 1
- Rejects empty question_text or answer
- MCQ must have exactly 4 options

### Vector Store (`app/services/vector_store.py`)
Wraps ChromaDB with two collections:
- **`document_chunks`** — Cosine similarity space, metadata: doc_id, chapter, section, content_type, page_range, token_count
- **`documents`** — Document-level metadata

Key design: `query_chunks()` generates embedding via Ollama first, then calls `query_embeddings=` (not `query_texts=`) to avoid ChromaDB default embedding dimension mismatch (384d vs 768d).

### Task Manager (`app/services/task_manager.py`)
SQLite-backed task persistence with in-memory cache. Fields: `id`, `status`, `message`, `questions` (JSON), `selected_types` (JSON), `completed_types` (JSON), `config` (JSON), `total_so_far`, `total_target`, `error`, `created_at`, `updated_at`.

Supports `create_task()`, `update_task()`, `get_task()`, `list_tasks()`, `delete_task()`, `cleanup_old()`.

### RAG Query (`app/services/rag.py`)
1. Embed query via Ollama with "query:" prefix
2. Vector search ChromaDB for 30 candidates
3. If hybrid enabled: BM25 search + RRF fusion + cross-encoder rerank → top 5
4. If not hybrid: take top 5 from vector search
5. Build context string from chunk content
6. Call LLM (Ollama or Groq) with context + question + history
7. Return `{answer, sources}` with chapter/section/page citations

### Hybrid Search (`app/services/merged_search.py`)
- **RRF (Reciprocal Rank Fusion):** `score = 1 / (k + rank)` with k=60
- Fuses vector similarity rank + BM25 keyword rank
- Optionally passes top 30 through cross-encoder reranker

### BM25 Store (`app/services/bm25_store.py`)
Per-document BM25 indexes stored as pickle files in `CHROMA_DB_PATH/bm25/`. Built during PDF processing. Thread-safe index loading with per-doc lock.

### Reranker (`app/services/reranker.py`)
Lazy-loads `cross-encoder/ms-marco-MiniLM-L-6-v2` from HuggingFace/sentence-transformers on first use. Singleton model instance.

## Database Schema

All in `CHROMA_DB_PATH/processing.db` (SQLite, WAL mode).

### `processing_queue`
```sql
CREATE TABLE processing_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id       TEXT NOT NULL UNIQUE,
    filename     TEXT NOT NULL,
    filepath     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    progress     INTEGER DEFAULT 0,
    message      TEXT DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    completed_at TEXT
);
```

### `tasks`
```sql
CREATE TABLE tasks (
    id               TEXT PRIMARY KEY,
    status           TEXT NOT NULL DEFAULT 'queued',
    message          TEXT DEFAULT '',
    questions        TEXT DEFAULT '[]',      -- JSON array
    total_so_far     INTEGER DEFAULT 0,
    error            TEXT,
    selected_types   TEXT DEFAULT '[]',      -- JSON array
    completed_types  TEXT DEFAULT '[]',      -- JSON array
    current_type     TEXT,
    total_target     INTEGER DEFAULT 0,
    config           TEXT DEFAULT '{}',      -- JSON object
    created_at       REAL NOT NULL,
    updated_at       TEXT DEFAULT (datetime('now'))
);
```

### `generation_log`
```sql
CREATE TABLE generation_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details    TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
```

## Frontend

### JS Architecture
Three independent modules, each loaded on its respective page:
- **`main.js`** (910 lines) — Upload drag-drop + polling, global processing poller, generate page (doc select, hierarchy tree, chapter/section checkboxes, chunk loading, generate/resume polling, question card rendering, progress tracker with dots, JSON/PDF download), documents page (list + hierarchy modal)
- **`chat.js`** (512 lines) — Chat sessions stored in localStorage, message rendering, source preview modal, document/provider/hybrid selectors, polling for answers
- **`tasks.js`** (388 lines) — Task table with status badges, cleanup/delete actions, questions modal with collapsible answers, config summary badges, PDF/JSON download

### Polling Pattern
All async operations (generation, chat, upload processing) use client-side polling (setInterval) because SSE caused HTTP/2 protocol errors through Cloudflare Tunnel. The frontend hits the status endpoint every 1.5–2s.

### Templates
7 Jinja2 templates extending `base.html` using Tailwind CSS via CDN. `base.html` provides nav bar with IAF-themed gradient, global processing banner, and auto-refresh for active generation.

## Data Flows

### PDF Upload
```
Browser upload → POST /api/upload → save file → enqueue SQLite →
worker_loop picks up → process_pdf() →
  extract pages (PyMuPDF)
  → LLM profile (front/back matter, patterns)
  → merge outline boundaries
  → clean text (headers, footers, noise)
  → detect chapter structure
  → chunk into semantic units
  → verify quality (LLM) → re-clean if needed
  → embed via Ollama (batches of 30)
  → store in ChromaDB (document_chunks + documents)
  → build BM25 index → pickle to disk
→ mark done
```

### Question Generation
```
User configures types/count/domains/difficulty →
POST /api/generate → create task (queued) →
_run() in background:
  retrieve context chunks (by filter or vector query)
  for each type:
    sample 8 chunks → build prompt → LLM call (~8 min on CPU)
    validate JSON → deduplicate → yield progress event
  if short of target → retry up to 2 rounds
  yield done event with final questions
→ Frontend polls GET /api/generate/{task_id} every 1.5s →
  renders progress dots, completed type summaries, elapsed time →
  on done: display question cards, enable PDF/JSON download
```

### RAG Chat
```
User types question →
POST /api/chat with doc_id, provider, hybrid flag →
background _run():
  embed query (Ollama, "query:" prefix)
  vector search ChromaDB (top 30)
  if hybrid: BM25 search + RRF fusion + cross-encoder rerank (top 5)
  if not hybrid: take top 5 vector results
  build context string with chapter/section citations
  call LLM (Ollama or Groq) with context + history
  return {answer, sources}
→ Frontend polls GET /api/chat/{task_id} every 1.5s →
  renders streaming dots → display answer with source links
```

## Configuration

All configurable via environment variables. See `app/config.py` for defaults.

Key variables:

| Env Var | Default | Purpose |
|---------|---------|---------|
| `DATA_DIR` | `./data` | Root for chroma_db, uploaded_docs (in run.sh) |
| `CHROMA_DB_PATH` | `$DATA_DIR/chroma_db` | ChromaDB + SQLite storage |
| `UPLOAD_DIR` | `$DATA_DIR/uploaded_docs` | Uploaded PDFs |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Question generation LLM |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_RAG_MODEL` | `llama3.2:3b` | RAG chat LLM |
| `GROQ_API_KEY` | — | Groq cloud API key |
| `N_CTX` | 8192 | LLM context window |
| `N_THREADS` | 8 | LLM thread count |
| `LLM_TIMEOUT` | 3600 | LLM request timeout (s) |
| `CHUNKS_PER_TYPE_CALL` | 8 | Context chunks per generation call |
| `CHUNK_CONTENT_MAX_CHARS` | 1200 | Max chars per chunk in prompts |

## Key Design Decisions

1. **Polling over SSE** — Cloudflare Tunnel drops SSE connections with `ERR_HTTP2_PROTOCOL_ERROR`. Client-side polling (1.5s interval) works reliably.

2. **Data directories outside project** — ChromaDB writes trigger uvicorn `--reload`. Data lives at `$DATA_DIR/` (default `./data/`) to avoid project directory modification during `--reload`.

3. **`query_embeddings=` over `query_texts=`** — ChromaDB's `query_texts=` uses its default embedding function (384d all-MiniLM-L6-v2). Our stored vectors are 768d (nomic-embed-text). We generate the query embedding via Ollama first, then pass it with `query_embeddings=`.

4. **Progressive question yield** — Each question type is generated independently, and results are yielded incrementally. This lets the frontend show progress per type without waiting for all types to complete.

5. **5-minute cleanup floor** — The cleanup endpoint enforces a minimum 300s age to prevent accidental deletion of recently completed tasks.

6. **Self-contained questions** — Generated questions include full text (no figure/equation/chapter references from source) so they work standalone in a question paper.

7. **Thread-local SQLite connections** — `db.py` uses `threading.local()` to give each thread its own WAL-mode connection, avoiding SQLite thread-safety issues while maintaining WAL read concurrency.

8. **BM25 + Reranker as optional enhancements** — BM25 keyword search and cross-encoder reranking are enabled by default but can be disabled via config. They're loaded lazily (BM25 index per doc, reranker singleton on first call) to avoid unnecessary memory usage.

## Security Notes

- Single-user system: no authentication layer
- No API keys stored in code; `GROQ_API_KEY` must be set as environment variable
- No remote access to ChromaDB (local file-based persistence only)
- Uploaded PDFs are validated for `.pdf` extension only
