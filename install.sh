#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "=== Question Generator Installer ==="

command -v python3 >/dev/null 2>&1 || {
    echo "Error: Python3 is required but not found."
    exit 1
}
echo "✓ Python3 $(python3 --version 2>&1 | awk '{print $2}')"

PY3=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)

# ---- System deps ----
echo ""
echo "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq "python${PY3}-venv" wget fonts-dejavu-core
echo "✓ System dependencies installed"

# ---- Pip ----
python3 -m pip --version >/dev/null 2>&1 || {
    echo "Installing pip..."
    wget -q https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
    python3 /tmp/get-pip.py --user --break-system-packages
    export PATH="$HOME/.local/bin:$PATH"
}

# ---- Virtual environment ----
INSTALL_DIRECT=false
if [ -d ".venv" ] && [ ! -f ".venv/bin/pip" ]; then
    echo "  Removing broken virtual environment..."
    rm -rf ".venv"
fi
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    if python3 -m venv .venv 2>/dev/null && [ -f ".venv/bin/pip" ]; then
        echo "✓ Virtual environment created"
    else
        echo "  warning: system lacks python3-venv. Installing directly..."
        INSTALL_DIRECT=true
    fi
fi

PIP="python3 -m pip"
if [ "$INSTALL_DIRECT" = false ]; then
    source .venv/bin/activate
    PIP="pip"
    echo "✓ Virtual environment activated"
    $PIP install --upgrade pip -q
fi

# ---- Python deps ----
$PIP install --no-cache-dir -r requirements.txt \
    ${INSTALL_DIRECT:+--break-system-packages}
echo "✓ Python dependencies installed"

# ---- DejaVu fonts ----
echo ""
echo "Checking fonts for PDF generation..."
FONTS_DIR="$APP_DIR/app/static/fonts"
FONT_PATH="$FONTS_DIR/DejaVuSans.ttf"
if [ -f "$FONT_PATH" ]; then
    echo "✓ Bundled font found at $FONT_PATH"
else
    mkdir -p "$FONTS_DIR"
    if [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
        cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf "$FONTS_DIR/"
        cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf "$FONTS_DIR/" 2>/dev/null || true
        echo "✓ DejaVu Sans font installed"
    else
        echo "  ⚠ DejaVu Sans font not found. PDF will fall back to basic font."
    fi
fi

# ---- Ollama ----
echo ""
echo "Setting up Ollama..."
if command -v ollama &>/dev/null; then
    echo "  ✓ Ollama already installed at $(which ollama)"
else
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "  ✓ Ollama installed"
fi

# Start Ollama if not already running
if ! pgrep -x ollama >/dev/null 2>&1; then
    echo "  Starting Ollama server..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    echo "  ✓ Ollama server started"
else
    echo "  ✓ Ollama server already running"
fi

echo ""
echo "Pulling LLM model (qwen2.5:7b-instruct)..."
ollama pull qwen2.5:7b-instruct
echo "✓ LLM model pulled"

echo ""
echo "Pulling embedding model (nomic-embed-text)..."
ollama pull nomic-embed-text
echo "✓ Embedding model pulled"

echo ""
echo "Pulling RAG chat model (llama3.2:3b)..."
ollama pull llama3.2:3b
echo "✓ RAG chat model pulled"

echo ""
echo "Caching cross-encoder reranker model..."
python3 -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')" 2>/dev/null
echo "✓ Reranker model cached"

# ---- Groq ----
echo ""
echo "Optional: For Groq cloud LLM support, set your API key:"
echo "  export GROQ_API_KEY=\"gsk_your_key_here\""
echo ""

# ---- Directories ----
DATA_DIR="${DATA_DIR:-$APP_DIR/data}"
mkdir -p "$DATA_DIR/chroma_db" "$DATA_DIR/uploaded_docs"

echo ""
echo "=== Installation complete ==="
echo "Run: DATA_DIR=\"$DATA_DIR\" ./run.sh"
