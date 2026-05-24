#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

VENV=".venv"
if [ -d "$VENV" ] && [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
elif ! command -v uvicorn &>/dev/null; then
    export PATH="$HOME/.local/bin:$PATH"
fi

DATA_DIR="${DATA_DIR:-$(dirname "$APP_DIR")/data}"
export CHROMA_DB_PATH="${CHROMA_DB_PATH:-$DATA_DIR/chroma_db}"
export UPLOAD_DIR="${UPLOAD_DIR:-$DATA_DIR/uploaded_docs}"

mkdir -p "$CHROMA_DB_PATH" "$UPLOAD_DIR"

if ! pgrep -x ollama >/dev/null 2>&1; then
    echo "⚠  Ollama is not running. LLM features will fail."
    echo "   Start it with: ollama serve"
    echo ""
fi

echo "=== Question Generator ==="
echo "Data:   $DATA_DIR"
echo "Starting on http://0.0.0.0:8000"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a /tmp/uvicorn.log
