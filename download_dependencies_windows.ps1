# download_dependencies_windows.ps1
# Downloads ALL dependencies for offline Windows installation.
# Run this on a Windows machine WITH internet.
# Then transfer the project folder to the offline Windows machine
# and run install_windows.ps1 (offline mode).

$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT_DIR

Write-Host "============================================"
Write-Host "  Download All Dependencies for"
Write-Host "  Windows Offline Installation"
Write-Host "============================================"
Write-Host ""

# ---- Create directories ----
$null = New-Item -ItemType Directory -Force -Path "dependencies/python"
$null = New-Item -ItemType Directory -Force -Path "dependencies/ollama/binary"
$null = New-Item -ItemType Directory -Force -Path "dependencies/ollama/models"
$null = New-Item -ItemType Directory -Force -Path "dependencies/models"
$null = New-Item -ItemType Directory -Force -Path "dependencies/tailwind"

# =====================================================================
#  1. PYTHON PACKAGES (pip wheels)
# =====================================================================
Write-Host ""
Write-Host "[1/5] Downloading Python packages..."
Write-Host "      Platform: Windows amd64, Python 3.12"

if (-not (Test-Path "server/requirements.txt")) {
    Write-Host "  ✗ server/requirements.txt not found. Run from project root."
    exit 1
}

# Check Python is available
try {
    python --version
} catch {
    Write-Host "  ✗ Python is not installed or not in PATH."
    Write-Host "    Download and install Python 3.12 from: https://www.python.org/downloads/"
    Write-Host "    Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

Write-Host "  Downloading wheels (this may take a while)..."
$pipResult = & python -m pip download -r server/requirements.txt -d dependencies/python/ 2>&1
if ($LASTEXITCODE -eq 0) {
    $pyWheels = (Get-ChildItem "dependencies/python/*.whl" | Measure-Object).Count
    $pySize = (Get-ChildItem "dependencies/python/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "  → $pyWheels wheel files downloaded"
    Write-Host "  Size: $([math]::Round($pySize, 1)) MB"

    # Download pip bootstrapper
    & python -m pip download pip -d dependencies/python/ 2>$null
    try {
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "dependencies/python/get-pip.py" -ErrorAction Stop
    } catch {
        Write-Host "  ⚠ Could not download get-pip.py"
    }
    $finalCount = (Get-ChildItem "dependencies/python/*.whl" | Measure-Object).Count
    Write-Host "  → $finalCount wheels + get-pip.py"
} else {
    Write-Host "  ✗ pip download failed:"
    Write-Host "    $pipResult"
    Write-Host "    Check your internet connection and try again."
}

Write-Host ""

# =====================================================================
#  2. OLLAMA INSTALLER (Windows)
# =====================================================================
Write-Host "[2/5] Downloading Ollama for Windows..."

$ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
$ollamaInstaller = "dependencies/ollama/binary/OllamaSetup.exe"

try {
    Write-Host "  Downloading OllamaSetup.exe..."
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaInstaller -TimeoutSec 120 -ErrorAction Stop
    $installerSize = (Get-Item $ollamaInstaller).Length / 1MB
    Write-Host "  → OllamaSetup.exe ($([math]::Round($installerSize, 1)) MB)"
} catch {
    Write-Host "  ✗ Failed to download Ollama installer."
    Write-Host "    Download manually from: https://ollama.com/download/windows"
    Write-Host "    Save to: dependencies/ollama/binary/OllamaSetup.exe"
}

Write-Host ""

# =====================================================================
#  3. OLLAMA MODELS
# =====================================================================
Write-Host "[3/5] Downloading Ollama models..."

$ollamaAvailable = $false
try {
    $null = Get-Command ollama -ErrorAction Stop
    $ollamaAvailable = $true
    Write-Host "  ✓ Ollama found at $(Get-Command ollama)."
} catch {
    Write-Host "  Ollama is not installed. Attempting temporary install..."
    if (Test-Path "dependencies/ollama/binary/OllamaSetup.exe") {
        Write-Host "  Installing Ollama silently..."
        $installLog = "$env:TEMP\ollama_install.log"
        Start-Process -FilePath "dependencies/ollama/binary/OllamaSetup.exe" -ArgumentList "/S" -Wait -NoNewWindow
        Start-Sleep -Seconds 10
        try {
            $null = Get-Command ollama -ErrorAction Stop
            $ollamaAvailable = $true
            Write-Host "  ✓ Ollama installed successfully."
        } catch {
            Write-Host "  ✗ Failed to install Ollama automatically."
        }
    } else {
        Write-Host "  ✗ Ollama installer not found. Run [2/5] first."
    }
}

if ($ollamaAvailable) {
    # Start Ollama server if not running
    $ollamaRunning = $false
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $ollamaRunning = $true
    } catch {
        Write-Host "  Starting Ollama server..."
        $ollamaProcess = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
        Start-Sleep -Seconds 10
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
            $ollamaRunning = $true
        } catch {
            Write-Host "  ✗ Ollama server failed to start. Check if Ollama is installed correctly."
        }
    }

    if ($ollamaRunning) {
        $models = @("qwen2.5:7b-instruct", "nomic-embed-text", "llama3.2:3b")
        foreach ($model in $models) {
            Write-Host "  Pulling $model..."
            $pullResult = & ollama pull $model 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ $model pulled"
            } else {
                Write-Host "  ✗ Failed to pull $model"
                Write-Host "    $pullResult"
            }
        }

        # Export models
        $ollamaModelsDir = "$env:USERPROFILE\.ollama\models"
        if (Test-Path $ollamaModelsDir) {
            $null = New-Item -ItemType Directory -Force -Path "dependencies/ollama/models"
            Copy-Item -Path "$ollamaModelsDir\*" -Destination "dependencies/ollama/models\" -Recurse -Force
            $modelSize = (Get-ChildItem "dependencies/ollama/models/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB
            Write-Host "  Models exported to dependencies/ollama/models/"
            Write-Host "  Size: $([math]::Round($modelSize, 1)) GB"
        }
    }
}

Write-Host ""

# =====================================================================
#  4. CROSS-ENCODER MODEL
# =====================================================================
Write-Host "[4/5] Downloading cross-encoder reranker model..."

$env:TRANSFORMERS_CACHE = "$ROOT_DIR\dependencies\models"
$env:HF_HOME = "$ROOT_DIR\dependencies\models"

# Install sentence-transformers from local wheels temporarily
$ceDepsDir = "$env:TEMP\ce_deps_" + (Get-Random)
$null = New-Item -ItemType Directory -Force -Path $ceDepsDir

Write-Host "  Installing sentence-transformers from local wheels..."
$pipInstall = & python -m pip install --target="$ceDepsDir" --no-index --find-links="$ROOT_DIR/dependencies/python/" sentence-transformers 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Running cross-encoder download..."
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = "$ceDepsDir;$env:PYTHONPATH"
    $ceResult = python -c @"
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('  ✓ Cross-encoder model downloaded')
"@ 2>&1
    if ($LASTEXITCODE -eq 0) {
        if (Test-Path "$ROOT_DIR/dependencies/models") {
            $ceSize = (Get-ChildItem "$ROOT_DIR/dependencies/models/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Host "  Size: $([math]::Round($ceSize, 1)) MB"
        }
    } else {
        Write-Host "  ✗ Failed to download cross-encoder model."
        Write-Host "    It will be downloaded on first use (requires internet at runtime)."
    }
    $env:PYTHONPATH = $oldPythonPath
} else {
    Write-Host "  ⚠ Could not install sentence-transformers from local wheels."
    Write-Host "  Retrying with online pip..."
    $ceResult = python -c @"
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('  ✓ Cross-encoder model downloaded')
"@ 2>&1
    if ($LASTEXITCODE -eq 0) {
        if (Test-Path "$ROOT_DIR/dependencies/models") {
            $ceSize = (Get-ChildItem "$ROOT_DIR/dependencies/models/" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Host "  Size: $([math]::Round($ceSize, 1)) MB"
        }
    } else {
        Write-Host "  ✗ Failed to download cross-encoder model."
        Write-Host "    It will be downloaded on first use (requires internet at runtime)."
    }
}

# Clean up temp deps
Remove-Item -Path $ceDepsDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""

# =====================================================================
#  5. TAILWIND CSS
# =====================================================================
Write-Host "[5/5] Downloading Tailwind CSS..."

try {
    Invoke-WebRequest -Uri "https://cdn.tailwindcss.com" -OutFile "dependencies/tailwind/tailwind.min.js" -TimeoutSec 60 -ErrorAction Stop
    $twSize = (Get-Item "dependencies/tailwind/tailwind.min.js").Length / 1KB
    Write-Host "  → tailwind.min.js ($([math]::Round($twSize, 1)) KB)"
} catch {
    Write-Host "  ✗ Failed to download Tailwind CSS."
    Write-Host "    Download manually: curl -sL https://cdn.tailwindcss.com"
    Write-Host "    Save to: dependencies/tailwind/tailwind.min.js"
}

Write-Host ""

# =====================================================================
#  SUMMARY
# =====================================================================
$totalSize = (Get-ChildItem "dependencies/" -Recurse | Measure-Object -Property Length -Sum).Sum
$totalSizeGB = $totalSize / 1GB

Write-Host "============================================"
Write-Host "  Download Complete!"
Write-Host "============================================"
Write-Host ""
Write-Host "  Total size: $([math]::Round($totalSizeGB, 1)) GB"
Write-Host ""
Write-Host "  Contents:"
foreach ($dir in Get-ChildItem "dependencies/" -Directory) {
    $dirSize = (Get-ChildItem $dir.FullName -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "    $([math]::Round($dirSize, 1)) MB  $($dir.Name)/"
}
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Transfer the entire 'question_generator' folder to the target Windows machine"
Write-Host "       (USB drive, network share, etc.)"
Write-Host "    2. On the target machine, run (as Administrator):"
Write-Host "         powershell -ExecutionPolicy Bypass -File install_windows.ps1"
Write-Host "       and select 'Offline' when prompted"
Write-Host "    3. Start the server:"
Write-Host "         DATA_DIR=../data powershell -ExecutionPolicy Bypass -File server/run_windows.ps1"
Write-Host ""
