# install_windows.ps1
# Installs Question Generator on Windows.
# Run this from the project root directory.
# Requires: Python 3.12 (from python.org, with "Add to PATH" checked)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File server/install_windows.ps1
#
# Or for offline installation (after running download_dependencies_windows.ps1):
#   powershell -ExecutionPolicy Bypass -File server/install_windows.ps1

$ErrorActionPreference = "Stop"

$APP_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$APP_DIR = (Get-Item $APP_DIR).FullName
$PROJECT_DIR = (Get-Item "$APP_DIR\..").FullName
$DEPS_DIR = "$PROJECT_DIR\dependencies"
$DATA_DIR = if ($env:DATA_DIR) { $env:DATA_DIR } else { "$PROJECT_DIR\data" }

Write-Host "======================================"
Write-Host "  Question Generator Installer"
Write-Host "  for Windows"
Write-Host "======================================"
Write-Host ""

# ---- Python check ----
try {
    $pyVersion = & python --version 2>&1
    Write-Host "✓ $pyVersion"
} catch {
    Write-Host "Error: Python is required but not found."
    Write-Host "Download and install Python 3.12 from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

# ---- Mode selection ----
Write-Host ""
Write-Host "Choose installation mode:"
Write-Host "  1) Online  — Download everything from the internet"
Write-Host "  2) Offline — Install from local dependencies/ folder"
Write-Host ""
$choice = Read-Host "Enter 1 or 2"

if ($choice -eq "1" -or $choice -match "^(online|Online|ONLINE)$") {
    $INSTALL_MODE = "online"
    Write-Host "→ Online installation selected"
} elseif ($choice -eq "2" -or $choice -match "^(offline|Offline|OFFLINE)$") {
    $INSTALL_MODE = "offline"
    Write-Host "→ Offline installation selected"
} else {
    Write-Host "Error: Invalid selection. Enter 1 (online) or 2 (offline)."
    exit 1
}

# =====================================================================
#  OFFLINE MODE — Validate dependencies
# =====================================================================
if ($INSTALL_MODE -eq "offline") {
    Write-Host ""
    Write-Host "--- Validating offline dependencies ---"
    $MISSING = $false

    if (-not (Test-Path $DEPS_DIR)) {
        Write-Host "✗ dependencies/ folder not found at: $DEPS_DIR"
        Write-Host "  Run download_dependencies_windows.ps1 on an internet-connected Windows machine,"
        Write-Host "  then transfer the entire project folder to this machine."
        exit 1
    }

    # 1. Python wheels
    $pyWheels = (Get-ChildItem "$DEPS_DIR/python/*.whl" -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "  Python wheels: $pyWheels found"
    if ($pyWheels -lt 10) {
        Write-Host "  ✗ Too few Python wheels (expected 20+). Re-run download_dependencies_windows.ps1."
        $MISSING = $true
    }

    # 2. pip bootstrapper
    $pipBoot = (Get-ChildItem "$DEPS_DIR/python/get-pip.py" -ErrorAction SilentlyContinue).Count
    if ($pipBoot -eq 0) {
        Write-Host "  ⚠ pip bootstrapper not found (get-pip.py). Will use system pip if available."
    }

    # 3. Ollama installer
    if (Test-Path "$DEPS_DIR/ollama/binary/OllamaSetup.exe") {
        $instSize = (Get-Item "$DEPS_DIR/ollama/binary/OllamaSetup.exe").Length / 1MB
        Write-Host "  Ollama installer: found ($([math]::Round($instSize, 1)) MB)"
    } else {
        Write-Host "  ✗ Ollama installer not found at dependencies/ollama/binary/"
        $MISSING = $true
    }

    # 4. Ollama models
    if ((Test-Path "$DEPS_DIR/ollama/models/blobs") -and (Test-Path "$DEPS_DIR/ollama/models/manifests")) {
        $modelSize = (Get-ChildItem "$DEPS_DIR/ollama/models/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB
        Write-Host "  Ollama models: found ($([math]::Round($modelSize, 1)) GB)"
    } else {
        Write-Host "  ✗ Ollama models not found (missing blobs/ or manifests/ in dependencies/ollama/models/)"
        $MISSING = $true
    }

    # 5. Cross-encoder model
    $ceCount = (Get-ChildItem "$DEPS_DIR/models" -Recurse -Include "*.json","*.safetensors","*.bin" -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($ceCount -gt 0) {
        $ceSize = (Get-ChildItem "$DEPS_DIR/models/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  Cross-encoder model: $ceCount files found ($([math]::Round($ceSize, 1)) MB)"
    } else {
        Write-Host "  ⚠ Cross-encoder model not found in dependencies/models/"
        Write-Host "    It will be downloaded on first use (requires internet at runtime)."
    }

    # 6. Tailwind
    if (Test-Path "$DEPS_DIR/tailwind/tailwind.min.js") {
        $twSize = (Get-Item "$DEPS_DIR/tailwind/tailwind.min.js").Length / 1KB
        Write-Host "  Tailwind CSS: found ($([math]::Round($twSize, 1)) KB)"
    } else {
        Write-Host "  ⚠ Tailwind CSS not found in dependencies/tailwind/"
        Write-Host "    Web UI may not render correctly without it."
    }

    if ($MISSING) {
        Write-Host ""
        Write-Host "Critical dependencies missing. Aborting."
        Write-Host "Re-run download_dependencies_windows.ps1 on a machine WITH internet."
        exit 1
    }
    Write-Host "✓ All critical dependencies present"
}

# =====================================================================
#  PYTHON VIRTUAL ENVIRONMENT
# =====================================================================
Write-Host ""
Write-Host "--- Virtual environment ---"

if (Test-Path "$APP_DIR\.venv") {
    Write-Host "  Virtual environment already exists."
} else {
    Write-Host "  Creating virtual environment..."
    $venvResult = & python -m venv "$APP_DIR\.venv" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Virtual environment created"
    } else {
        Write-Host "  ✗ Failed to create virtual environment:"
        Write-Host "    $venvResult"
        Write-Host "    Ensure Python 3.12 is installed with the full installation (check 'Python venv' in installer)."
        exit 1
    }
}

# Activate virtual environment
$pip = "$APP_DIR\.venv\Scripts\pip.exe"
$python = "$APP_DIR\.venv\Scripts\python.exe"

if (-not (Test-Path $pip)) {
    # Maybe pip was not installed in the venv
    & python -m ensurepip --upgrade
    # Create pip.exe reference
    $pip = "$APP_DIR\.venv\Scripts\pip.exe"
}

Write-Host "  ✓ Virtual environment ready at $APP_DIR\.venv"

# =====================================================================
#  PYTHON DEPENDENCIES
# =====================================================================
Write-Host ""
Write-Host "--- Python dependencies ---"

Set-Location $APP_DIR

if ($INSTALL_MODE -eq "online") {
    Write-Host "Installing from PyPI..."
    & $pip install --no-cache-dir -r requirements.txt 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Python dependencies installed"
    } else {
        Write-Host "✗ Failed to install Python dependencies."
        exit 1
    }
} else {
    Write-Host "Installing from local wheels..."
    & $pip install --no-index --find-links="$DEPS_DIR/python/" -r requirements.txt 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Python dependencies installed from local cache"
    } else {
        Write-Host "✗ Failed to install Python dependencies from local cache."
        Write-Host "  The wheels may be for a different Python version. Check that you downloaded"
        Write-Host "  for Windows amd64 and Python 3.12."
        exit 1
    }
}

# =====================================================================
#  TAILWIND CSS
# =====================================================================
Write-Host ""
Write-Host "--- Tailwind CSS ---"

$tailwindDest = "$APP_DIR\app\static\js\tailwind.min.js"

if (Test-Path $tailwindDest) {
    Write-Host "✓ Tailwind CSS already present"
} elseif ($INSTALL_MODE -eq "online") {
    Write-Host "Downloading Tailwind CSS..."
    try {
        Invoke-WebRequest -Uri "https://cdn.tailwindcss.com" -OutFile $tailwindDest -TimeoutSec 60 -ErrorAction Stop
        $twSize = (Get-Item $tailwindDest).Length / 1KB
        Write-Host "✓ Tailwind CSS downloaded ($([math]::Round($twSize, 1)) KB)"
    } catch {
        Write-Host "  ⚠ Tailwind download failed. Web UI may not render correctly."
    }
} elseif (Test-Path "$DEPS_DIR/tailwind/tailwind.min.js") {
    Write-Host "Copying Tailwind CSS from dependencies..."
    Copy-Item "$DEPS_DIR/tailwind/tailwind.min.js" $tailwindDest -Force
    Write-Host "✓ Tailwind CSS installed from local cache"
} else {
    Write-Host "  ⚠ Tailwind CSS not available. Web UI may not render correctly."
}

# =====================================================================
#  OLLAMA
# =====================================================================
Write-Host ""
Write-Host "--- Ollama ---"

$ollamaInstalled = $false
try {
    $null = Get-Command ollama -ErrorAction Stop
    $ollamaInstalled = $true
    Write-Host "  ✓ Ollama already installed at $(Get-Command ollama)."
} catch {
    Write-Host "  Ollama is not installed."
}

if (-not $ollamaInstalled) {
    if ($INSTALL_MODE -eq "online") {
        Write-Host "  Downloading Ollama installer..."
        try {
            Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile "$env:TEMP\OllamaSetup.exe" -TimeoutSec 120 -ErrorAction Stop
            Write-Host "  Installing Ollama..."
            Start-Process -FilePath "$env:TEMP\OllamaSetup.exe" -ArgumentList "/S" -Wait -NoNewWindow
            Start-Sleep -Seconds 10
            try {
                $null = Get-Command ollama -ErrorAction Stop
                $ollamaInstalled = $true
                Write-Host "  ✓ Ollama installed"
            } catch {
                Write-Host "  ✗ Failed to install Ollama. Install manually from: https://ollama.com/download/windows"
            }
        } catch {
            Write-Host "  ✗ Failed to download Ollama installer. Install manually from: https://ollama.com/download/windows"
        }
    } elseif (Test-Path "$DEPS_DIR/ollama/binary/OllamaSetup.exe") {
        Write-Host "  Installing Ollama from local installer..."
        Start-Process -FilePath "$DEPS_DIR/ollama/binary/OllamaSetup.exe" -ArgumentList "/S" -Wait -NoNewWindow
        Start-Sleep -Seconds 10
        try {
            $null = Get-Command ollama -ErrorAction Stop
            $ollamaInstalled = $true
            Write-Host "  ✓ Ollama installed from local installer"
        } catch {
            Write-Host "  ✗ Failed to install Ollama. Run OllamaSetup.exe manually."
        }
    } else {
        Write-Host "  ⚠ Ollama installer not found. Skipping."
    }
}

# ---- Ollama models ----
$ollamaModelsDir = "$env:USERPROFILE\.ollama\models"
if ($ollamaInstalled) {
    if ($INSTALL_MODE -eq "online") {
        Write-Host ""
        Write-Host "Pulling LLM model (qwen2.5:7b-instruct)..."
        & ollama pull qwen2.5:7b-instruct
        Write-Host "✓ LLM model pulled"

        Write-Host ""
        Write-Host "Pulling embedding model (nomic-embed-text)..."
        & ollama pull nomic-embed-text
        Write-Host "✓ Embedding model pulled"

        Write-Host ""
        Write-Host "Pulling RAG chat model (llama3.2:3b)..."
        & ollama pull llama3.2:3b
        Write-Host "✓ RAG chat model pulled"
    } elseif (Test-Path "$DEPS_DIR/ollama/models/blobs") {
        Write-Host ""
        Write-Host "Importing Ollama models from local cache..."
        $null = New-Item -ItemType Directory -Force -Path $ollamaModelsDir
        Copy-Item -Path "$DEPS_DIR/ollama/models/*" -Destination "$ollamaModelsDir\" -Recurse -Force
        Write-Host "✓ Ollama models imported"
    }
}

# ---- Start Ollama server ----
if ($ollamaInstalled) {
    $ollamaRunning = $false
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $ollamaRunning = $true
        Write-Host "  ✓ Ollama server already running"
    } catch {
        Write-Host "  Starting Ollama server..."
        $ollamaProcess = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
        Start-Sleep -Seconds 5
        Write-Host "  ✓ Ollama server started"
    }
}

# =====================================================================
#  CROSS-ENCODER RERANKER MODEL
# =====================================================================
Write-Host ""
Write-Host "--- Cross-encoder reranker model ---"

if ($INSTALL_MODE -eq "online") {
    Write-Host "Caching cross-encoder reranker model..."
    & $python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
    Write-Host "✓ Reranker model cached"
} elseif (Test-Path "$DEPS_DIR/models") {
    $ceFiles = (Get-ChildItem "$DEPS_DIR/models" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($ceFiles -gt 0) {
        Write-Host "Copying cross-encoder model from local cache..."
        $hfCache = "$env:USERPROFILE\.cache\huggingface"
        $null = New-Item -ItemType Directory -Force -Path $hfCache
        Copy-Item -Path "$DEPS_DIR/models/*" -Destination "$hfCache\" -Recurse -Force
        Write-Host "✓ Reranker model installed from local cache"
    }
}

# =====================================================================
#  DATA DIRECTORIES
# =====================================================================
Write-Host ""
Write-Host "--- Data directories ---"
$null = New-Item -ItemType Directory -Force -Path "$DATA_DIR/chroma_db"
$null = New-Item -ItemType Directory -Force -Path "$DATA_DIR/uploaded_docs"
Write-Host "✓ Data directories created at: $DATA_DIR"

# =====================================================================
#  RUN SCRIPT
# =====================================================================
Write-Host ""
Write-Host "--- Creating run_windows.ps1 ---"
$runScript = @"
# run_windows.ps1
# Start the Question Generator server on Windows
`$ErrorActionPreference = "Stop"
`$APP_DIR = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$DATA_DIR = if (`$env:DATA_DIR) { `$env:DATA_DIR } else { Join-Path (Split-Path `$APP_DIR -Parent) "data" }

# Check if Ollama is running
try {
    `$null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ Ollama server is running"
} catch {
    Write-Host "Starting Ollama server..."
    `$process = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
    Start-Sleep -Seconds 5
}

# Start the application
Write-Host "Starting Question Generator server..."
Write-Host "Open http://localhost:8000 in your browser"
Write-Host ""

`$env:DATA_DIR = `$DATA_DIR
& "`$APP_DIR\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8000
"@
Set-Content -Path "$APP_DIR\run_windows.ps1" -Value $runScript
Write-Host "✓ Created run_windows.ps1"

# =====================================================================
#  SUMMARY
# =====================================================================
Write-Host ""
Write-Host "======================================"
Write-Host "  Installation complete!"
Write-Host "======================================"
Write-Host ""
Write-Host "  Start the server:"
Write-Host "    powershell -ExecutionPolicy Bypass -File server\run_windows.ps1"
Write-Host ""
Write-Host "  Or with custom data path:"
Write-Host "    `$env:DATA_DIR = 'D:\my_data'"
Write-Host "    powershell -ExecutionPolicy Bypass -File server\run_windows.ps1"
Write-Host ""
Write-Host "  Then open: http://localhost:8000"
Write-Host ""
