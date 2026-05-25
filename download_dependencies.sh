#!/usr/bin/env bash
# shellcheck disable=SC2086
# download_dependencies.sh — Downloads ALL dependencies for offline installation.
# Run this on a Linux x86_64 machine WITH internet, then transfer the project folder
# to the offline target machine and run server/install.sh (offline mode).

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
    echo "⚠  This script should be run on Linux x86_64 to download"
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

# Ensure pip is available
if ! python3 -m pip --version; then
    echo "  Installing pip..."
    if ! python3 -m ensurepip --upgrade; then
        wget https://bootstrap.pypa.io/get-pip.py -O /tmp/get-pip.py && \
        python3 /tmp/get-pip.py --user && \
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi

echo "  Downloading wheels (this may take a while)..."
if python3 -m pip download -r server/requirements.txt -d dependencies/python/; then
    PY_WHEELS=$(ls dependencies/python/*.whl | wc -l)
    echo "  → $PY_WHEELS wheel files downloaded"
    echo "  Size: $(du -sh dependencies/python/ | cut -f1)"

    # Download pip bootstrapper
    python3 -m pip download pip -d dependencies/python/ || true
    wget https://bootstrap.pypa.io/get-pip.py -O dependencies/python/get-pip.py || true
    echo "  → $(ls dependencies/python/*.whl | wc -l) wheels + get-pip.py"
else
    echo "  ✗ pip download failed. Trying with source builds allowed..."
    python3 -m pip download --no-binary :all: -r server/requirements.txt -d dependencies/python/ || \
        echo "  ✗ Failed to download Python packages. Check network and run again."
fi

echo ""

# =====================================================================
#  2. SYSTEM PACKAGES (.deb)
# =====================================================================
echo "[2/6] Downloading system packages (.deb)..."

DEBS="python3.12-venv fonts-dejavu-core wget build-essential git curl libssl-dev zlib1g-dev"

if ! command -v apt-get; then
    echo "  ⚠ apt-get not available. Skipping system packages."
    echo "    Install manually on target: $DEBS"
else
    echo "  Updating package lists..."
    apt-get update -qq || echo "  ⚠ apt-get update failed (may be OK if repos are stale)"

    cd dependencies/system

    echo "  Downloading .deb packages..."
    apt-get download $DEBS || echo "  ⚠ Some packages not downloaded"

    # Download transitive dependencies
    ALL_DEPS=$(apt-cache depends --recurse --no-recommends --no-suggests \
        --no-conflicts --no-breaks --no-replaces --no-enhances $DEBS \
        | grep "^\w" | sort -u || true)
    if [ -n "$ALL_DEPS" ]; then
        echo "  Downloading transitive dependencies..."
        apt-get download $ALL_DEPS || true
    fi

    cd "$ROOT_DIR"
    SYS_DEBS=$(ls dependencies/system/*.deb | wc -l)
    echo "  → $SYS_DEBS .deb files"
    du -sh dependencies/system/ | sed 's/^/  Size: /'
fi

echo ""

# =====================================================================
#  3. OLLAMA BINARY
# =====================================================================
echo "[3/6] Downloading Ollama binary..."

OLLAMA_ASSET="ollama-linux-amd64.tar.zst"
OLLAMA_URL="https://github.com/ollama/ollama/releases/latest/download/$OLLAMA_ASSET"
OLLAMA_BINARY="dependencies/ollama/binary/$OLLAMA_ASSET"
if wget --timeout=120 "$OLLAMA_URL" -O "$OLLAMA_BINARY"; then
    echo "  → $OLLAMA_ASSET ($(du -h "$OLLAMA_BINARY" | cut -f1))"
else
    echo "  ✗ Failed to download Ollama binary."
    echo "    Download manually from: $OLLAMA_URL"
    echo "    Save to: $OLLAMA_BINARY"
fi

echo ""

# =====================================================================
#  4. OLLAMA MODELS
# =====================================================================
echo "[4/6] Downloading Ollama models..."

# If ollama not in PATH, extract downloaded binary temporarily
OLLAMA_TEMP=""
if ! command -v ollama; then
    OLLAMA_ARCHIVE=""
    if [ -f "dependencies/ollama/binary/ollama-linux-amd64.tar.zst" ]; then
        OLLAMA_ARCHIVE="dependencies/ollama/binary/ollama-linux-amd64.tar.zst"
    elif [ -f "dependencies/ollama/binary/ollama-linux-amd64.tgz" ]; then
        OLLAMA_ARCHIVE="dependencies/ollama/binary/ollama-linux-amd64.tgz"
    fi
    if [ -n "$OLLAMA_ARCHIVE" ]; then
        echo "  Extracting Ollama binary temporarily from $(basename "$OLLAMA_ARCHIVE")..."
        OLLAMA_TEMP="$(mktemp -d)"
        case "$OLLAMA_ARCHIVE" in
            *.tar.zst)
                if command -v zstd; then
                    zstd -dc "$OLLAMA_ARCHIVE" | tar xf - -C "$OLLAMA_TEMP"
                else
                    echo "  zstd not found. Install: sudo apt install zstd"
                fi
                ;;
            *.tgz)
                tar -xzf "$OLLAMA_ARCHIVE" -C "$OLLAMA_TEMP"
                ;;
        esac
        export PATH="$OLLAMA_TEMP/bin:$PATH"
        if command -v ollama; then
            echo "  ✓ Ollama ready at $(which ollama)"
        else
            echo "  ✗ Failed to extract Ollama binary."
        fi
    else
        echo "  ✗ Ollama binary not found. Run [3/6] first or install ollama."
        echo "    Then manually: ollama pull qwen2.5:7b-instruct nomic-embed-text llama3.2:3b"
    fi
fi

if command -v ollama; then
    # Start Ollama server if not running
    OLLAMA_PID=""
    if ! curl -s http://127.0.0.1:11434/api/tags; then
        echo "  Starting Ollama server..."
        ollama serve > /tmp/ollama-download.log 2>&1 &
        OLLAMA_PID=$!
        sleep 5
        if ! curl -s http://127.0.0.1:11434/api/tags; then
            echo "  ✗ Ollama server failed to start. Check /tmp/ollama-download.log"
        fi
    fi

    for model in qwen2.5:7b-instruct nomic-embed-text llama3.2:3b; do
        echo "  Pulling $model..."
        if ollama pull "$model"; then
            echo "  ✓ $model pulled"
        else
            echo "  ✗ Failed to pull $model"
        fi
    done

    # Export models
    OLLAMA_MODELS_DIR="${OLLAMA_MODELS:-$HOME/.ollama/models}"
    if [ -d "$OLLAMA_MODELS_DIR" ]; then
        mkdir -p dependencies/ollama/models
        cp -r "$OLLAMA_MODELS_DIR/"* dependencies/ollama/models/
        echo "  Models exported to dependencies/ollama/models/"
        echo "  Size: $(du -sh dependencies/ollama/models/ | cut -f1)"
    fi

    # Stop temp server
    if [ -n "$OLLAMA_PID" ]; then
        kill "$OLLAMA_PID" || true
        sleep 2
    fi
fi

# Clean up temp binary
if [ -n "$OLLAMA_TEMP" ]; then
    rm -rf "$OLLAMA_TEMP"
    echo "  Temporary Ollama cleaned up"
fi

echo ""

# =====================================================================
#  5. CROSS-ENCODER MODEL
# =====================================================================
echo "[5/6] Downloading cross-encoder reranker model..."

export TRANSFORMERS_CACHE="$ROOT_DIR/dependencies/models"
export HF_HOME="$ROOT_DIR/dependencies/models"

# Install sentence-transformers from local wheels temporarily to trigger model download
CE_DEPS_DIR="$(mktemp -d)"
echo "  Installing sentence-transformers from local wheels..."
if python3 -m pip install --target="$CE_DEPS_DIR" --no-index \
    --find-links="$ROOT_DIR/dependencies/python/" sentence-transformers; then
    echo "  Running cross-encoder download..."
    if PYTHONPATH="$CE_DEPS_DIR:$PYTHONPATH" python3 -c "
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('  ✓ Cross-encoder model downloaded')
"; then
        CE_SIZE=$(du -sh "$ROOT_DIR/dependencies/models" | cut -f1 || echo "0")
        echo "  Size: $CE_SIZE"
    else
        echo "  ✗ Failed to download cross-encoder model."
        echo "    It will be downloaded on first use (requires internet at runtime)."
    fi
else
    echo "  ⚠ Could not install sentence-transformers from local wheels."
    echo "  Retrying with online pip..."
    if python3 -c "
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
"; then
        CE_SIZE=$(du -sh "$ROOT_DIR/dependencies/models" | cut -f1 || echo "0")
        echo "  Size: $CE_SIZE"
    else
        echo "  ✗ Failed to download cross-encoder model."
        echo "    It will be downloaded on first use (requires internet at runtime)."
    fi
fi
rm -rf "$CE_DEPS_DIR"

echo ""

# =====================================================================
#  6. TAILWIND CSS
# =====================================================================
echo "[6/6] Downloading Tailwind CSS..."

if curl -sL --max-time 60 "https://cdn.tailwindcss.com" -o dependencies/tailwind/tailwind.min.js; then
    echo "  → tailwind.min.js ($(du -h dependencies/tailwind/tailwind.min.js | cut -f1))"
else
    echo "  ✗ Failed to download Tailwind CSS."
    echo "    Download manually: curl -sL https://cdn.tailwindcss.com"
    echo "    Save to: dependencies/tailwind/tailwind.min.js"
fi

echo ""

# =====================================================================
#  SUMMARY
# =====================================================================
echo "============================================"
echo "  Download Complete!"
echo "============================================"
echo ""
echo "  Total size: $(du -sh dependencies/ | cut -f1)"
echo ""
echo "  Contents:"
du -sh dependencies/*/ | sed 's/^/    /'
echo ""
echo "  Next steps:"
echo "    1. Transfer the entire 'question_generator' folder to the target machine"
echo "       (USB drive, SCP, rsync, etc.)"
echo "    2. On the target machine, run:"
echo "         cd question_generator/server"
echo "         bash install.sh"
echo "       and select 'Offline' when prompted"
echo "    3. Start the server:"
echo "         DATA_DIR=../data bash run.sh"
echo ""
