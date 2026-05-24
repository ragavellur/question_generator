#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo "  Download All Dependencies for"
echo "  Offline Installation"
echo "============================================"
echo ""

# ---- Platform check ----
ARCH=$(uname -m)
OS=$(uname -s)
if [ "$OS" != "Linux" ] || [ "$ARCH" != "x86_64" ]; then
    echo "⚠  This script must be run on Linux x86_64 to download"
    echo "   the correct binary wheels and packages for the target machine."
    echo "   Current: $OS $ARCH"
    echo ""
    echo "   If you are on macOS/Windows, use a Linux VM or Docker:"
    echo "     docker run --platform linux/amd64 -it ubuntu:24.04"
    echo ""
    read -r -p "Continue anyway? (y/N) " ans < /dev/tty
    if [ "${ans:-n}" != "y" ] && [ "${ans:-n}" != "Y" ]; then
        exit 1
    fi
fi

mkdir -p dependencies/{python,system,ollama/{binary,models},models,tailwind}

# =====================================================================
#  1. PYTHON PACKAGES (pip wheels)
# =====================================================================
echo ""
echo "[1/6] Downloading Python packages..."
echo "      Platform: linux x86_64, Python 3.12"

if [ ! -f "server/requirements.txt" ]; then
    echo "  ✗ server/requirements.txt not found. Run from project root."
    exit 1
fi

# Check if pip is available
if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "  Installing pip first..."
    python3 -m ensurepip --upgrade 2>/dev/null || {
        echo "  Downloading get-pip.py..."
        wget -q https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py
        python3 /tmp/get-pip.py --user
        export PATH="$HOME/.local/bin:$PATH"
    }
fi

# Download all wheels + dependencies (native platform — checked above)
python3 -m pip download \
    -r server/requirements.txt \
    -d dependencies/python/ \
    2>&1 | tail -5

# Fall back to allowing source builds if some packages have no binary wheel
PY_WHEELS=$(ls dependencies/python/*.whl 2>/dev/null | wc -l)
if [ "$PY_WHEELS" -lt 5 ]; then
    echo "  Too few binary wheels, retrying with source builds allowed..."
    python3 -m pip download \
        --no-binary :all: \
        -r server/requirements.txt \
        -d dependencies/python/ \
        2>&1 | tail -5
    PY_WHEELS=$(ls dependencies/python/*.whl 2>/dev/null | wc -l)
fi
echo "  → $PY_WHEELS wheel/source files downloaded"

# Download pip itself and get-pip.py for offline bootstrapping
python3 -m pip download pip -d dependencies/python/ 2>/dev/null || true
wget -q https://bootstrap.pypa.io/get-pip.py -O dependencies/python/get-pip.py 2>/dev/null || true

echo "  → $(ls dependencies/python/*.whl 2>/dev/null | wc -l) wheels + get-pip.py"
echo "  Size: $(du -sh dependencies/python/ | cut -f1)"

# =====================================================================
#  2. SYSTEM PACKAGES (.deb)
# =====================================================================
echo ""
echo "[2/6] Downloading system packages (.deb)..."

DEBS="python3.12-venv fonts-dejavu-core wget build-essential git curl libssl-dev zlib1g-dev"
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq 2>/dev/null
    cd dependencies/system
    apt-get download $DEBS 2>/dev/null || true
    # Also download transitive dependencies
    ALL_DEPS=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances $DEBS 2>/dev/null | grep "^\w" | sort -u) || true
    if [ -n "$ALL_DEPS" ]; then
        apt-get download $ALL_DEPS 2>/dev/null || true
    fi
    cd "$ROOT_DIR"
    SYS_DEBS=$(ls dependencies/system/*.deb 2>/dev/null | wc -l)
    echo "  → $SYS_DEBS .deb files"
    echo "  Size: $(du -sh dependencies/system/ | cut -f1)"
else
    echo "  ⚠ apt-get not available. Skipping system package download."
    echo "    Install these manually on the target machine:"
    echo "      $DEBS"
fi

# =====================================================================
#  3. OLLAMA BINARY
# =====================================================================
echo ""
echo "[3/6] Downloading Ollama binary..."

OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tgz"
if wget -q --timeout=30 "$OLLAMA_URL" -O dependencies/ollama/binary/ollama-linux-amd64.tgz 2>/dev/null; then
    echo "  → ollama-linux-amd64.tgz ($(du -h dependencies/ollama/binary/ollama-linux-amd64.tgz | cut -f1))"
else
    echo "  ⚠ Failed to download Ollama binary from GitHub."
    echo "    Download manually from: $OLLAMA_URL"
    echo "    Save to: dependencies/ollama/binary/ollama-linux-amd64.tgz"
fi

# =====================================================================
#  4. OLLAMA MODELS
# =====================================================================
echo ""
echo "[4/6] Exporting Ollama models..."

# If ollama not in PATH but we have the downloaded binary, extract it temporarily
OLLAMA_TEMP=""
if ! command -v ollama >/dev/null 2>&1; then
    if [ -f "dependencies/ollama/binary/ollama-linux-amd64.tgz" ]; then
        echo "  Extracting Ollama binary temporarily for model download..."
        OLLAMA_TEMP="$(mktemp -d)"
        tar -xzf dependencies/ollama/binary/ollama-linux-amd64.tgz -C "$OLLAMA_TEMP"
        export PATH="$OLLAMA_TEMP:$PATH"
        echo "  ✓ Ollama binary ready at $OLLAMA_TEMP/ollama"
    else
        echo "  ✗ Ollama binary not found in dependencies/ollama/binary/"
        echo "    Cannot download models without Ollama. Re-run [3/6] first."
    fi
fi

# If we have ollama available (system or temp), pull models
if command -v ollama >/dev/null 2>&1; then
    # Check if ollama server is running; start if needed
    OLLAMA_PID=""
    if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "  Starting Ollama server for model export..."
        ollama serve > /tmp/ollama-download.log 2>&1 &
        OLLAMA_PID=$!
        sleep 5
        # Verify it started
        if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            echo "  ✗ Failed to start Ollama server. Check /tmp/ollama-download.log"
        fi
    fi

    for model in qwen2.5:7b-instruct nomic-embed-text llama3.2:3b; do
        echo "  Pulling $model (this may take a while)..."
        ollama pull "$model"
        echo "  ✓ $model pulled"
    done

    # Copy model files to dependencies
    OLLAMA_MODELS_DIR="${OLLAMA_MODELS:-$HOME/.ollama/models}"
    if [ -d "$OLLAMA_MODELS_DIR" ]; then
        mkdir -p dependencies/ollama/models
        cp -r "$OLLAMA_MODELS_DIR/"* dependencies/ollama/models/
        echo "  Models exported to dependencies/ollama/models/"
        echo "  Size: $(du -sh dependencies/ollama/models/ | cut -f1)"
    fi

    # Stop temp server if we started it
    if [ -n "$OLLAMA_PID" ]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        # Wait for shutdown
        sleep 2
    fi
fi

# Clean up temporary Ollama binary
if [ -n "$OLLAMA_TEMP" ]; then
    rm -rf "$OLLAMA_TEMP"
    echo "  Temporary Ollama binary cleaned up"
fi

# =====================================================================
#  5. CROSS-ENCODER MODEL
# =====================================================================
echo ""
echo "[5/6] Downloading cross-encoder reranker model..."

export TRANSFORMERS_CACHE="$ROOT_DIR/dependencies/models"
export HF_HOME="$ROOT_DIR/dependencies/models"

python3 -c "
from sentence_transformers import CrossEncoder
print('Downloading cross-encoder/ms-marco-MiniLM-L-6-v2...')
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('✓ Cross-encoder model downloaded successfully')
" 2>&1

CE_SIZE=$(du -sh "$ROOT_DIR/dependencies/models" 2>/dev/null | cut -f1 || echo "0")
echo "  Size: $CE_SIZE"

# =====================================================================
#  6. TAILWIND CSS
# =====================================================================
echo ""
echo "[6/6] Downloading Tailwind CSS..."

if curl -sL --max-time 30 "https://cdn.tailwindcss.com" -o dependencies/tailwind/tailwind.min.js 2>/dev/null; then
    echo "  → tailwind.min.js ($(du -h dependencies/tailwind/tailwind.min.js | cut -f1))"
else
    echo "  ⚠ Failed to download Tailwind CSS."
    echo "    Download manually: curl -sL https://cdn.tailwindcss.com"
    echo "    Save to: dependencies/tailwind/tailwind.min.js"
fi

# =====================================================================
#  SUMMARY
# =====================================================================
echo ""
echo "============================================"
echo "  Download Complete!"
echo "============================================"
echo ""
echo "  Total size: $(du -sh dependencies/ | cut -f1)"
echo ""
echo "  Contents:"
du -sh dependencies/*/ 2>/dev/null | sed 's/^/    /'
echo ""
echo "  Next steps:"
echo "    1. Copy the entire 'question_generator' folder to the target machine"
echo "       (e.g., USB drive, SCP, or network share)"
echo "    2. On the target machine, run:"
echo "         cd question_generator/server"
echo "         bash install.sh"
echo "       and select 'Offline' when prompted"
echo "    3. Start the server:"
echo "         DATA_DIR=../data bash run.sh"
echo ""
