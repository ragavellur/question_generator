# run_windows.ps1
# Start the Question Generator server on Windows
# Usage: powershell -ExecutionPolicy Bypass -File server\run_windows.ps1

$ErrorActionPreference = "Stop"

$APP_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_DIR = (Get-Item "$APP_DIR\..").FullName
$DATA_DIR = if ($env:DATA_DIR) { $env:DATA_DIR } else { "$PROJECT_DIR\data" }

Write-Host "======================================"
Write-Host "  Starting Question Generator"
Write-Host "======================================"
Write-Host ""

# Check if Ollama is running
Write-Host "Checking Ollama..."
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✓ Ollama server is running"
} catch {
    Write-Host "Starting Ollama server..."
    $process = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
    Start-Sleep -Seconds 5
    Write-Host "✓ Ollama server started"
}

# Verify virtual environment exists
$uvicorn = "$APP_DIR\.venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) {
    Write-Host "✗ Virtual environment not found at $APP_DIR\.venv"
    Write-Host "  Run the installer first:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File server\install_windows.ps1"
    exit 1
}

# Start the application
Write-Host ""
Write-Host "Starting Question Generator server..."
Write-Host "Data directory: $DATA_DIR"
Write-Host ""
Write-Host "Open http://localhost:8000 in your browser"
Write-Host "Press Ctrl+C to stop the server"
Write-Host ""

$env:DATA_DIR = $DATA_DIR
& $uvicorn app.main:app --host 0.0.0.0 --port 8000
