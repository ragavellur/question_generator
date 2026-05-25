# Question Generator — Installation Guide

## Project Structure

```
question_generator/
├── server/                        # All application code
│   ├── app/                       # FastAPI application
│   │   ├── main.py               # Server entry point
│   │   ├── config.py             # Configuration (env vars)
│   │   ├── routers/              # API endpoints
│   │   │   ├── frontend.py       # HTML page routes
│   │   │   ├── upload.py         # PDF upload
│   │   │   ├── documents.py      # Document management
│   │   │   ├── questions.py      # Question generation
│   │   │   └── chat.py           # RAG chat
│   │   ├── services/             # Business logic
│   │   │   ├── pdf_processor/    # PDF extraction pipeline
│   │   │   ├── question_generator.py
│   │   │   ├── rag.py, llm_client.py, vector_store.py
│   │   │   ├── bm25_store.py, reranker.py, merged_search.py
│   │   │   ├── task_manager.py, worker.py, db.py
│   │   │   └── embedding.py, document_manager.py
│   │   ├── templates/            # Jinja2 HTML templates
│   │   ├── static/               # JS, CSS, images, fonts
│   │   └── models/               # Pydantic schemas
│   ├── .venv/                    # Python virtual environment (created by install.sh)
│   ├── install.sh                # Installation script
│   ├── run.sh                    # Server startup script
│   ├── requirements.txt          # Python package list
│   ├── .gitignore
│   ├── AGENTS.md                 # Assistant rules
│   ├── README.md                 # Project overview (root symlink)
│   ├── ARCHITECTURE.md           # System design (root symlink)
│   └── INSTALL.md                # Install guide (root symlink)
├── data/                         # Runtime data (created by install/run)
│   ├── chroma_db/                # Vector database (ChromaDB) + SQLite tasks
│   └── uploaded_docs/            # Uploaded PDF files
├── dependencies/                 # Offline installation bundle (prepared separately)
│   ├── python/                   # pip wheel files (.whl)
│   ├── system/                   # .deb system packages
│   ├── ollama/
│   │   ├── binary/               # Ollama Linux binary (.tar.zst, ~1.1 GB)
│   │   └── models/               # Ollama model files (blobs + manifests)
│   ├── models/                   # HuggingFace model cache (cross-encoder)
│   └── tailwind/                 # Tailwind CSS Play CDN script (~400 KB)
├── download_dependencies.sh      # Prepares the dependencies/ folder
├── README.md                     # Project overview
├── ARCHITECTURE.md               # System architecture doc
├── INSTALL.md                    # This file (also symlinked as server/INSTALL.md)
└── .gitignore
```

**Key principle**: `server/` contains code only. `data/` contains runtime data (not tracked by git). `dependencies/` contains the offline bundle (not tracked by git).

---

## Prerequisites

| Requirement | Details |
|------------|---------|
| **OS** | Ubuntu 22.04 or 24.04 LTS (x86_64) |
| **Python** | 3.12 (comes with Ubuntu 24.04; for 22.04 use `deadsnakes` PPA) |
| **RAM** | 8 GB minimum, 16 GB recommended |
| **Disk** | 15 GB free (for models + data) |
| **Git** | `apt-get install git` |

---

## Quick Start (Online — Machine with Internet)

```bash
# 1. Clone the repository
git clone <repo-url> question_generator
cd question_generator

# 2. Run the installer — choose "Online" when prompted
bash server/install.sh

# 3. Start the server
DATA_DIR=../data bash server/run.sh

# 4. Open in browser
# http://localhost:8000
```

The installer will:
- Install system packages (`python3-venv`, `wget`, `fonts-dejavu-core`)
- Create a Python virtual environment (`.venv/`)
- Install all Python packages from PyPI
- Install Ollama and pull 3 LLM models (~7 GB total)
- Cache the cross-encoder reranker model (~423 MB)
- Download Tailwind CSS for the web UI
- Create the `data/` directories

---

## Offline Installation (Machine WITHOUT Internet)

The offline installation is a **two-stage process**:

### Stage 1: Prepare the Offline Bundle

Run this on **any Linux x86_64 machine with internet** (can be a different machine, a VM, or Docker container).

```bash
# Clone the repo on the internet-connected machine
git clone <repo-url> question_generator
cd question_generator

# Download everything into dependencies/
bash download_dependencies.sh
```

**What gets downloaded (~12–14 GB total):**

| Component | What's inside | Size | Estimated time |
|-----------|--------------|------|----------------|
| `dependencies/python/` | All pip wheel files (torch, chromadb, sentence-transformers, etc.) | ~2.8 GB | 10–30 min |
| `dependencies/system/` | .deb packages (python3.12-venv, fonts, build tools) | ~120 MB | 2–5 min |
| `dependencies/ollama/binary/` | Ollama Linux x86_64 binary (`ollama-linux-amd64.tar.zst`) | ~1.1 GB | 2–5 min |
| `dependencies/ollama/models/` | 3 Ollama models (qwen2.5:7b, nomic-embed-text, llama3.2:3b) | ~7 GB | 20–60 min |
| `dependencies/models/` | Cross-encoder reranker (HuggingFace cache) | ~423 MB | 5–10 min |
| `dependencies/tailwind/` | Tailwind CSS Play CDN script | ~400 KB | <1 min |

**Total: ~12–14 GB**

Once complete, the `dependencies/` folder contains everything needed for offline installation.

#### Important Notes

- **Platform**: You MUST run `download_dependencies.sh` on Linux x86_64 (same architecture as the target machine). macOS downloads ARM64 wheels which won't work on Linux.
- **zstd required**: The Ollama binary uses `.tar.zst` format. `download_dependencies.sh` auto-detects `zstd`; if missing, install it: `sudo apt-get install zstd`
- **No internet machine available?** Use Docker:
  ```bash
  docker run --platform linux/amd64 -it -v $(pwd):/workspace ubuntu:24.04
  cd /workspace && bash download_dependencies.sh
  ```
- **Intermittent connection?** The script can be re-run — it will re-download missing files.
- **Download failed for some components?** See [Troubleshooting](#troubleshooting) below.

### Stage 2: Transfer to Target Machine

Copy the entire `question_generator/` folder to the offline target machine.

| Method | Command |
|--------|---------|
| **USB drive** | `cp -r question_generator /path/to/usb/` |
| **SCP over LAN** | `scp -r question_generator user@target:/home/user/` |
| **Network share** | Mount share, then copy |

**For large transfers (~14 GB), use `rsync` with compression (over LAN):**
```bash
rsync -avzP --progress question_generator/ user@target:/home/user/question_generator/
```

### Stage 3: Install on Target Machine

```bash
# On the target machine (no internet)
cd question_generator

# Run the installer — choose "Offline" when prompted
bash server/install.sh
```

The installer will:
1. **Validate** that all required files exist in `dependencies/`
2. Install system packages from local `.deb` files (`dpkg` warning messages about already-installed packages can be ignored)
3. Create a Python virtual environment
4. Install Python packages from local wheels (no internet needed)
5. Copy DejaVu fonts for PDF generation
6. Install Tailwind CSS for the web UI
7. Install Ollama from the local binary
8. Import Ollama models from local cache (copy to `~/.ollama/models/`)
9. Import the cross-encoder model to HuggingFace cache
10. Create the `data/` directories

If any **critical** dependency is missing, the installer will abort with a clear error message telling you which component is missing.

### Stage 4: Start the Server

```bash
cd question_generator

# Start with data directory pointing to sibling data/ folder
DATA_DIR=../data bash server/run.sh

# Or, without setting DATA_DIR (defaults to ../data/ automatically):
bash server/run.sh
```

Then open **http://localhost:8000** in a browser on the target machine.

---

## Configuration

All settings can be configured via environment variables. Set them before running `run.sh`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `../data` (relative to `server/`) | Root directory for chroma_db and uploaded_docs |
| `CHROMA_DB_PATH` | `$DATA_DIR/chroma_db` | ChromaDB vector database location |
| `UPLOAD_DIR` | `$DATA_DIR/uploaded_docs` | PDF upload directory |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Model for question generation |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Model for text embeddings |
| `OLLAMA_RAG_MODEL` | `llama3.2:3b` | Model for RAG chat |
| `GROQ_API_KEY` | *(empty)* | API key for Groq cloud LLM (optional) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model |
| `N_CTX` | `8192` | LLM context window in tokens |
| `N_THREADS` | `8` | LLM CPU threads |
| `LLM_TIMEOUT` | `3600` | LLM request timeout in seconds |
| `CHUNKS_PER_TYPE_CALL` | `8` | Context chunks per generation call |
| `CHUNK_CONTENT_MAX_CHARS` | `1200` | Max chars per chunk in prompts |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model for reranking |

**Example with custom data path:**
```bash
DATA_DIR=/mnt/large_disk/question_generator_data bash server/run.sh
```

---

## Running as a Service

### Using screen (simple)

```bash
# Start Ollama in a screen session
screen -S ollama
ollama serve
# Ctrl+A, D to detach

# Start server in another screen
screen -S uvicorn
cd /home/user/question_generator
DATA_DIR=/home/user/question_generator_data bash server/run.sh
# Ctrl+A, D to detach

# Reattach to check logs
screen -r uvicorn
```

### Using systemd (for automatic restart on boot)

```ini
# /etc/systemd/system/question-generator.service
[Unit]
Description=Question Generator
After=network.target ollama.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/question_generator/server
Environment=DATA_DIR=/home/youruser/question_generator_data
ExecStart=/home/youruser/question_generator/server/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Troubleshooting

### "python3 not found"
Install Python 3.12:
```bash
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv
```

### "pip install fails" (online mode)
- Check internet connection
- Try increasing `LLM_TIMEOUT` if it's a timeout issue
- Run `pip install --no-cache-dir -r server/requirements.txt` manually

### "pip install fails" (offline mode)
- Ensure `dependencies/python/` has wheel files — re-run `download_dependencies.sh`
- Check that wheels are for Linux x86_64 and Python 3.12
- Run: `ls dependencies/python/*.whl | head -20` to verify

### "dpkg: dependency problems" (offline system packages)
This means some .deb packages require other packages not in the `dependencies/system/` folder. The target machine likely has these already installed (especially on Ubuntu 24.04). Check which packages failed and install them manually:
```bash
sudo apt-get install <package-name>
```
If the target truly has no internet, use `apt-get download <package-name>` on the internet machine and add the .deb to `dependencies/system/`.

### "Ollama not found" or "ollama: command not found"
- Online: The install script failed. Run `curl -fsSL https://ollama.com/install.sh | sh` manually.
- Offline: The binary wasn't downloaded. Check `dependencies/ollama/binary/ollama-linux-amd64.tar.zst` exists. Install manually:
  ```bash
  zstd -dc dependencies/ollama/binary/ollama-linux-amd64.tar.zst | sudo tar xf - -C /usr/local/
  ```

### "Ollama models not found"
- Online: The `ollama pull` command failed. Run `ollama pull qwen2.5:7b-instruct` manually.
- Offline: The model files weren't copied. Check `dependencies/ollama/models/blobs/` exists. Copy manually:
  ```bash
  cp -r dependencies/ollama/models/* ~/.ollama/models/
  ```

### "Cross-encoder model not found"
The model will be auto-downloaded on first use if internet is available. For offline, ensure `dependencies/models/` has files and was copied to `~/.cache/huggingface/`.

### "Web UI has no styling (plain HTML)"
Tailwind CSS is missing. Download it manually from an internet machine:
```bash
curl -sL https://cdn.tailwindcss.com -o server/app/static/js/tailwind.min.js
```

### "Internal server error" or "500" in the web UI
Check the server log:
```bash
tail -100 /tmp/uvicorn.log
```

### "ChromaDB dimension mismatch"
The embedding model was changed after documents were already processed. Re-process the PDF.

### "Server won't start - address in use"
Another process is already using port 8000. Kill it or change the port:
```bash
kill $(lsof -ti:8000)
# Or use a different port:
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### "Ollama connection refused" when server starts
Ensure Ollama is running:
```bash
pgrep -x ollama || ollama serve
```
Check the Ollama log:
```bash
tail -50 /tmp/ollama.log
```

### Need help?
Check the full documentation in `server/ARCHITECTURE.md` for system details, or refer to `server/AGENTS.md` for assistant behavior rules when using AI-assisted management.
