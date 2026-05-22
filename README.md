# Question Generator

Upload PDF documents, extract structured content, and generate educational questions using LLMs. Supports 6 question types with domain-based categorization (Factual, Comprehension, Application), difficulty levels, and RAG-based chat over your documents.

## Features

- **PDF Processing Pipeline** — Upload PDFs, auto-extract text, detect structure (chapters/sections), clean and chunk with LLM-verified quality
- **6 Question Types** — MCQ, True/False, Fill-in-the-Blank, Very Short Answer, Short Answer, Long Answer
- **3 Cognitive Domains** — Factual, Comprehension, Application
- **3 Difficulty Levels** — Easy, Medium, Hard
- **Group-Shuffle Generation** — Questions scatter across all selected chapters randomly
- **Progress Tracking** — Real-time status per type, elapsed time, expandable results
- **PDF/JSON Export** — Download question papers with answer key
- **RAG Chat** — Ask questions about document content with source citations (chapter/section/page)
- **Hybrid Search** — Vector similarity (ChromaDB) + BM25 keyword + cross-encoder reranking
- **Cloud LLM Support** — Optional Groq provider for faster RAG responses
- **Task History** — Persistent task management with view/download/cleanup

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.12) |
| Database | SQLite (tasks, queue, logs) |
| Vector Store | ChromaDB (cosine similarity) |
| PDF Extraction | PyMuPDF |
| LLM (Local) | Ollama (qwen2.5:7b-instruct) |
| Embeddings | Ollama (nomic-embed-text, 768d) |
| RAG Chat | Ollama (llama3.2:3b) or Groq (llama-3.1-8b-instant) |
| Keyword Search | rank-bm25 |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| PDF Export | fpdf2 |
| Frontend | Jinja2 templates + vanilla JS + Tailwind CSS (CDN) |
| PDF Processor | Custom pipeline (extract → profile → clean → structure → chunk → verify → embed → index) |

## Quick Start

```bash
# Install everything (system deps, Python venv, Ollama, models)
./install.sh

# Start the server
DATA_DIR=/path/to/data ./run.sh

# Open http://localhost:8000
```

See [INSTALL.md](INSTALL.md) for detailed instructions.

## Project Structure

```
├── app/
│   ├── main.py              FastAPI app, lifespan, background workers
│   ├── config.py            Environment variables and constants
│   ├── models/              Pydantic schemas, ChromaDB state
│   ├── routers/             API endpoints (upload, documents, questions, chat, frontend)
│   ├── services/            Business logic (PDF pipeline, vector store, LLM, RAG, tasks)
│   ├── templates/           Jinja2 HTML templates
│   └── static/              JS, CSS, fonts, images
├── install.sh               Automated installation
├── run.sh                   Server startup
└── requirements.txt         Python dependencies
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system architecture.
