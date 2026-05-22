# Installation Guide

## Prerequisites

- **Python 3.12+** (`python3 --version`)
- **Ollama** — Local LLM runner. Install from [ollama.com](https://ollama.com) or:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```
- **Git** (`git --version`)
- **System packages** (Ubuntu/Debian):
  ```bash
  sudo apt install python3.12 python3.12-venv build-essential libssl-dev zlib1g-dev
  ```
  On macOS these come with Xcode Command Line Tools (`xcode-select --install`).

## Quick Install (Automated)

```bash
git clone <repo-url> question_generator
cd question_generator
./install.sh
```

`install.sh` does everything:

1. Creates Python 3.12 virtual environment (`.venv/`)
2. Installs packages from `requirements.txt`
3. Pulls Ollama models:
   - `qwen2.5:7b-instruct` — Question generation (≈4.7 GB)
   - `nomic-embed-text` — Embeddings (≈274 MB)
   - `llama3.2:3b` — RAG chat (≈2.0 GB)
4. Pre-downloads cross-encoder reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` (≈423 MB)
5. Prompts for Groq API key (optional — press Enter to skip)
6. Creates data directories (`$DATA_DIR/chroma_db/`, `$DATA_DIR/uploaded_docs/`)
7. Writes `.env` file with all settings

Estimated time: 10–30 minutes (depends on download speeds and CPU).

## Manual Installation

### 1. Clone and prepare environment

```bash
git clone <repo-url> question_generator
cd question_generator
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Pull Ollama models

```bash
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### 3. Pre-download cross-encoder (optional, for hybrid search)

```python
# python -c "
from sentence_transformers import CrossEncoder;
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
# "
```

First run loads and caches it automatically (~30s on first call).

### 4. Configure environment

Create `.env` in the project root:

```bash
# Required
DATA_DIR=./data
CHROMA_DB_PATH=$DATA_DIR/chroma_db
UPLOAD_DIR=$DATA_DIR/uploaded_docs

# LLM models
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_RAG_MODEL=llama3.2:3b

# Groq (optional — for cloud RAG)
# GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx

# Performance
N_CTX=8192
N_THREADS=8
LLM_TIMEOUT=3600

# Generation settings
CHUNKS_PER_TYPE_CALL=8
CHUNK_CONTENT_MAX_CHARS=1200
```

Or just use defaults: `install.sh` writes this automatically.

### 5. Start Ollama

```bash
# In a terminal or screen/tmux session:
ollama serve
```

Or run it as a service:
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

### 6. Start the server

```bash
DATA_DIR=./data bash run.sh
```

This starts uvicorn on `0.0.0.0:8000` (no `--reload`). Server logs go to `/tmp/uvicorn.log`.

## Running as a Service

### Using screen (recommended for simplicity)

```bash
# Start Ollama
screen -S ollama
ollama serve
# Ctrl+A, D to detach

# Start server
screen -S uvicorn
cd /path/to/question_generator
DATA_DIR=/path/to/data bash run.sh
# Ctrl+A, D to detach

# Reattach
screen -r uvicorn
```

### Using systemd (Linux)

```ini
# /etc/systemd/system/question-generator.service
[Unit]
Description=Question Generator
After=network.target ollama.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/question_generator
Environment=DATA_DIR=/path/to/data
ExecStart=/path/to/question_generator/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Production Deployment

### Cloudflare Tunnel (recommended for remote access)

If your server is behind NAT, use `cloudflared` to expose the web UI:

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Create tunnel (one-time setup)
cloudflared tunnel create question-generator

# Configure
# ~/.cloudflared/config.yml:
# url: http://localhost:8000
# tunnel: <tunnel-id>
# credentials-file: /root/.cloudflared/<tunnel-id>.json
```

### Performance Tuning

On CPU-only servers (Intel i7-6700, 8 threads):

| Setting | Value | Effect |
|---------|-------|--------|
| `N_THREADS` | 8 | Match physical threads |
| `N_CTX` | 8192 | Reduces prompt size, faster generation |
| `CHUNKS_PER_TYPE_CALL` | 8 | Fewer tokens per LLM call |
| `CHUNK_CONTENT_MAX_CHARS` | 1200 | Shorter context chunks |
| `LLM_TIMEOUT` | 3600 | Prevents premature timeout on slow hardware |

Expected generation speed: ≈8 minutes per question type (6 types × 5 questions = ~40 min total).

### Using Groq for Fast RAG

Set `GROQ_API_KEY` in `.env` or environment. Groq uses `llama-3.1-8b-instant` (free tier, 6k TPM, 30 requests/min). RAG answers arrive in 2–5 seconds vs 30–60 seconds with local Ollama (`llama3.2:3b`).

## Troubleshooting

### "No module named 'app'"
Run from project root (where `app/` directory lives). Activate the venv first.

### Ollama connection refused
Ensure `ollama serve` is running. Default port: `http://localhost:11434`. Check with `curl http://localhost:11434`.

### "An error occurred during generation"
Check `/tmp/uvicorn.log` for traceback. Common causes:
- LLM timeout (increase `LLM_TIMEOUT`)
- OOM killer (reduce `N_CTX`)
- Ollama not running

### ChromaDB "dimension mismatch"
Data directory was moved or model changed. Re-process the PDF.

### Cross-encoder downloads on first call
The reranker downloads automatically on first use (~423 MB). Pre-download during install to avoid delay.

### WAL checkpoint lost data on restart
If SQLite WAL uncheckpointed data is lost after a restart, the DB file may be stale. Always use Direct File Copy for backups (not `INSERT INTO` from WAL content), and set `journal_mode=DELETE` before copying.
