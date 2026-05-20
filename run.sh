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

mkdir -p chroma_db uploaded_docs

echo "=== Question Generator ==="
echo "Starting on http://0.0.0.0:8000"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
