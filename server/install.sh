#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"
PROJECT_DIR="$(dirname "$APP_DIR")"
DEPS_DIR="$PROJECT_DIR/dependencies"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"

echo "======================================"
echo "  Question Generator Installer"
echo "======================================"
echo ""

# ---- Python check ----
command -v python3 >/dev/null 2>&1 || {
    echo "Error: Python3 is required but not found."
    exit 1
}
echo "✓ Python3 $(python3 --version 2>&1 | awk '{print $2}')"
PY3=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1-2)

# ---- Mode selection ----
echo ""
echo "Choose installation mode:"
echo "  1) Online  — Download everything from the internet"
echo "  2) Offline — Install from local dependencies/ folder"
echo ""
read -r -p "Enter 1 or 2: " INSTALL_MODE < /dev/tty

case "$INSTALL_MODE" in
    1|online|Online|ONLINE)
        INSTALL_MODE="online"
        echo "→ Online installation selected"
        ;;
    2|offline|Offline|OFFLINE)
        INSTALL_MODE="offline"
        echo "→ Offline installation selected"
        ;;
    *)
        echo "Error: Invalid selection. Enter 1 (online) or 2 (offline)."
        exit 1
        ;;
esac

# =====================================================================
#  OFFLINE MODE — Validate dependencies
# =====================================================================
if [ "$INSTALL_MODE" = "offline" ]; then
    echo ""
    echo "--- Validating offline dependencies ---"
    MISSING=0

    if [ ! -d "$DEPS_DIR" ]; then
        echo "✗ dependencies/ folder not found at: $DEPS_DIR"
        echo "  Run download_dependencies.sh on an internet-connected Linux machine,"
        echo "  then transfer the entire project folder to this machine."
        exit 1
    fi

    # 1. Python wheels
    PY_WHEELS=$(ls "$DEPS_DIR/python/"*.whb 2>/dev/null | wc -l) || true
    PY_WHEELS2=$(ls "$DEPS_DIR/python/"*.whl 2>/dev/null | wc -l) || true
    echo "  Python wheels: $((PY_WHEELS + PY_WHEELS2)) found"
    if [ "$((PY_WHEELS + PY_WHEELS2))" -lt 10 ]; then
        echo "  ✗ Too few Python wheels (expected 20+). Re-run download_dependencies.sh."
        MISSING=1
    fi

    # 2. pip bootstrapper
    PIP_BOOT=$(ls "$DEPS_DIR/python/get-pip.py" "$DEPS_DIR/python/pip"*.whl 2>/dev/null | wc -l) || true
    if [ "$PIP_BOOT" -eq 0 ]; then
        echo "  ⚠ pip bootstrapper not found (get-pip.py or pip wheel). Will use system pip if available."
    fi

    # 3. Ollama binary
    if [ -f "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tgz" ]; then
        echo "  Ollama binary: found ($(du -h "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tgz" | cut -f1))"
    else
        echo "  ✗ Ollama binary not found at dependencies/ollama/binary/"
        MISSING=1
    fi

    # 4. Ollama models
    if [ -d "$DEPS_DIR/ollama/models/blobs" ] && [ -d "$DEPS_DIR/ollama/models/manifests" ]; then
        MODEL_COUNT=$(find "$DEPS_DIR/ollama/models/manifests/registry.ollama.ai/library" -maxdepth 1 -type d 2>/dev/null | wc -l)
        echo "  Ollama models: $MODEL_COUNT found ($(du -sh "$DEPS_DIR/ollama/models" | cut -f1))"
    else
        echo "  ✗ Ollama models not found (missing blobs/ or manifests/ in dependencies/ollama/models/)"
        MISSING=1
    fi

    # 5. Cross-encoder model
    CE_COUNT=$(find "$DEPS_DIR/models" -name "*.json" -o -name "*.safetensors" -o -name "*.bin" 2>/dev/null | wc -l) || true
    if [ "$CE_COUNT" -gt 0 ]; then
        echo "  Cross-encoder model: $CE_COUNT files found ($(du -sh "$DEPS_DIR/models" | cut -f1))"
    else
        echo "  ⚠ Cross-encoder model not found in dependencies/models/"
        echo "    It will be downloaded on first use (requires internet at runtime)."
    fi

    # 6. Tailwind
    if [ -f "$DEPS_DIR/tailwind/tailwind.min.js" ]; then
        echo "  Tailwind CSS: found ($(du -h "$DEPS_DIR/tailwind/tailwind.min.js" | cut -f1))"
    else
        echo "  ⚠ Tailwind CSS not found in dependencies/tailwind/"
        echo "    Web UI may not render correctly without it."
    fi

    # 7. System .deb packages
    SYS_DEBS=$(ls "$DEPS_DIR/system/"*.deb 2>/dev/null | wc -l) || true
    echo "  System packages (.deb): $SYS_DEBS found"

    if [ "$MISSING" -eq 1 ]; then
        echo ""
        echo "Critical dependencies missing. Aborting."
        echo "Re-run download_dependencies.sh on a machine WITH internet."
        exit 1
    fi
    echo "✓ All critical dependencies present"
fi

# =====================================================================
#  SYSTEM DEPENDENCIES (apt packages)
# =====================================================================
echo ""
echo "--- System dependencies ---"

if [ "$INSTALL_MODE" = "online" ]; then
    echo "Installing system packages via apt..."
    apt-get update -qq
    apt-get install -y -qq "python${PY3}-venv" wget fonts-dejavu-core
    echo "✓ System dependencies installed"
elif [ "$INSTALL_MODE" = "offline" ] && [ "$SYS_DEBS" -gt 0 ]; then
    echo "Installing system packages from local .deb files..."
    cd "$DEPS_DIR/system"
    dpkg -i *.deb || true
    cd "$APP_DIR"
    echo "✓ System packages installed (warnings above may be ignored if packages already present)"
else
    echo "  Skipping system package installation."
    echo "  Ensure python3-venv, wget, and fonts-dejavu-core are installed manually."
fi

# =====================================================================
#  PIP BOOTSTRAP
# =====================================================================
echo ""
echo "--- Pip ---"
if python3 -m pip --version >/dev/null 2>&1; then
    echo "  ✓ pip already available"
else
    echo "  Installing pip..."
    if [ "$INSTALL_MODE" = "online" ]; then
        wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
        python3 /tmp/get-pip.py --user --break-system-packages
    elif [ -f "$DEPS_DIR/python/get-pip.py" ]; then
        python3 "$DEPS_DIR/python/get-pip.py" --user --break-system-packages
    elif [ -f "$DEPS_DIR/python/pip"*.whl ]; then
        python3 -m pip install --user "$DEPS_DIR/python/pip"*.whl
    else
        echo "  ⚠ No pip bootstrapper found. Python packages may fail."
    fi
    export PATH="$HOME/.local/bin:$PATH"
fi

# =====================================================================
#  VIRTUAL ENVIRONMENT
# =====================================================================
echo ""
echo "--- Virtual environment ---"
INSTALL_DIRECT=false
if [ -d ".venv" ] && [ ! -f ".venv/bin/pip" ]; then
    echo "  Removing broken virtual environment..."
    rm -rf ".venv"
fi
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    if python3 -m venv .venv && [ -f ".venv/bin/pip" ]; then
        echo "  ✓ Virtual environment created"
    else
        echo "  ⚠ System lacks python3-venv. Installing directly..."
        INSTALL_DIRECT=true
    fi
fi

PIP="python3 -m pip"
if [ "$INSTALL_DIRECT" = false ]; then
    source .venv/bin/activate
    PIP="pip"
    echo "  ✓ Virtual environment activated"
    $PIP install --upgrade pip
fi

# =====================================================================
#  PYTHON DEPENDENCIES
# =====================================================================
echo ""
echo "--- Python dependencies ---"

if [ "$INSTALL_MODE" = "online" ]; then
    echo "Installing from PyPI..."
    $PIP install --no-cache-dir -r requirements.txt \
        ${INSTALL_DIRECT:+--break-system-packages}
    echo "✓ Python dependencies installed"
elif [ "$INSTALL_MODE" = "offline" ]; then
    echo "Installing from local wheels..."
    $PIP install --no-index --find-links="$DEPS_DIR/python/" -r requirements.txt \
        ${INSTALL_DIRECT:+--break-system-packages}
    echo "✓ Python dependencies installed from local cache"
fi

# =====================================================================
#  DEJAVU FONTS
# =====================================================================
echo ""
echo "--- DejaVu fonts ---"
FONTS_DIR="$APP_DIR/app/static/fonts"
FONT_PATH="$FONTS_DIR/DejaVuSans.ttf"
if [ -f "$FONT_PATH" ]; then
    echo "✓ Bundled font found at $FONT_PATH"
else
    mkdir -p "$FONTS_DIR"
    if [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
        cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf "$FONTS_DIR/"
        cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf "$FONTS_DIR/" || true
        echo "✓ DejaVu Sans font installed"
    else
        echo "  ⚠ DejaVu Sans font not found. PDF will fall back to basic font."
    fi
fi

# =====================================================================
#  TAILWIND CSS
# =====================================================================
echo ""
echo "--- Tailwind CSS ---"
TAILWIND_DEST="$APP_DIR/app/static/js/tailwind.min.js"
if [ -f "$TAILWIND_DEST" ]; then
    echo "✓ Tailwind CSS already present"
elif [ "$INSTALL_MODE" = "online" ]; then
    echo "Downloading Tailwind CSS..."
    curl -sL https://cdn.tailwindcss.com -o "$TAILWIND_DEST" && \
        echo "✓ Tailwind CSS downloaded ($(du -h "$TAILWIND_DEST" | cut -f1))" || \
        echo "  ⚠ Tailwind download failed. Web UI may not render correctly."
elif [ -f "$DEPS_DIR/tailwind/tailwind.min.js" ]; then
    echo "Copying Tailwind CSS from dependencies..."
    cp "$DEPS_DIR/tailwind/tailwind.min.js" "$TAILWIND_DEST"
    echo "✓ Tailwind CSS installed from local cache"
else
    echo "  ⚠ Tailwind CSS not available. Web UI may not render correctly."
    echo "    Download manually: curl -sL https://cdn.tailwindcss.com -o $TAILWIND_DEST"
fi

# =====================================================================
#  OLLAMA
# =====================================================================
echo ""
echo "--- Ollama ---"

if command -v ollama &>/dev/null; then
    echo "  ✓ Ollama already installed at $(which ollama)"
elif [ "$INSTALL_MODE" = "online" ]; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "  ✓ Ollama installed"
elif [ -f "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tar.zst" ]; then
    echo "  Installing Ollama from local binary..."
    if command -v zstd; then
        zstd -dc "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tar.zst" | tar xf - -C /usr/local/
    elif tar --help 2>&1 | grep -q zstd; then
        tar -I zstd -xf "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tar.zst" -C /usr/local/
    else
        echo "  Installing zstd..."
        apt-get install -y zstd
        zstd -dc "$DEPS_DIR/ollama/binary/ollama-linux-amd64.tar.zst" | tar xf - -C /usr/local/
    fi
    echo "  ✓ Ollama installed from local binary"
else
    echo "  ⚠ Ollama binary not found. Skipping."
fi

# ---- Ollama models ----
OLLAMA_MODELS_DIR="${OLLAMA_MODELS:-$HOME/.ollama/models}"
if command -v ollama &>/dev/null; then
    if [ "$INSTALL_MODE" = "online" ]; then
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
    elif [ -d "$DEPS_DIR/ollama/models/blobs" ]; then
        echo ""
        echo "Importing Ollama models from local cache..."
        mkdir -p "$OLLAMA_MODELS_DIR"
        cp -r "$DEPS_DIR/ollama/models/"* "$OLLAMA_MODELS_DIR/"
        echo "✓ Ollama models imported ($(du -sh "$DEPS_DIR/ollama/models" | cut -f1))"
    fi
fi

# ---- Start Ollama server ----
if command -v ollama &>/dev/null && ! pgrep -x ollama >/dev/null 2>&1; then
    echo "  Starting Ollama server..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    echo "  ✓ Ollama server started"
elif pgrep -x ollama >/dev/null 2>&1; then
    echo "  ✓ Ollama server already running"
fi

# =====================================================================
#  CROSS-ENCODER RERANKER MODEL
# =====================================================================
echo ""
echo "--- Cross-encoder reranker model ---"
if [ "$INSTALL_MODE" = "online" ]; then
    echo "Caching cross-encoder reranker model..."
    python3 -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
    echo "✓ Reranker model cached"
elif [ -d "$DEPS_DIR/models" ]; then
    CE_FILES=$(find "$DEPS_DIR/models" -type f 2>/dev/null | wc -l)
    if [ "$CE_FILES" -gt 0 ]; then
        echo "Copying cross-encoder model from local cache..."
        mkdir -p "$HOME/.cache/huggingface"
        cp -r "$DEPS_DIR/models/"* "$HOME/.cache/huggingface/"
        echo "✓ Reranker model installed from local cache"
    fi
fi

# =====================================================================
#  GROQ
# =====================================================================
echo ""
echo "Optional: For Groq cloud LLM support, set your API key:"
echo "  echo \"export GROQ_API_KEY='gsk_your_key_here'\" >> $APP_DIR/.env"
echo ""

# =====================================================================
#  DATA DIRECTORIES
# =====================================================================
echo ""
echo "--- Data directories ---"
mkdir -p "$DATA_DIR/chroma_db" "$DATA_DIR/uploaded_docs"
echo "✓ Data directories created at: $DATA_DIR"

# =====================================================================
#  SUMMARY
# =====================================================================
echo ""
echo "======================================"
echo "  Installation complete!"
echo "======================================"
echo ""
echo "  Start the server:"
echo "    DATA_DIR=\"$DATA_DIR\" bash run.sh"
echo ""
echo "  Or with defaults:"
echo "    bash run.sh"
echo ""
echo "  Then open: http://localhost:8000"
echo ""
