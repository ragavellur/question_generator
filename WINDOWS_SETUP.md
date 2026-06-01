# Question Generator — Windows Setup Guide

This guide explains how to set up the Question Generator on a Windows computer. You can use the **automated scripts** (recommended) or follow the **manual steps** below.

---

## Prerequisites

| Requirement | Details |
|------------|---------|
| **Windows** | Windows 10 or Windows 11 (64-bit) |
| **Python** | Python 3.12 — download from [python.org](https://www.python.org/downloads/) |
| **RAM** | 8 GB minimum, 16 GB recommended |
| **Disk** | 15 GB free space |

### Installing Python

1. Go to https://www.python.org/downloads/
2. Download **Python 3.12.x** for Windows (64-bit)
3. Run the installer
4. **IMPORTANT**: Check the box that says **"Add Python to PATH"** at the bottom of the installer
5. Click **Install Now**
6. After installation, open a **Command Prompt** and verify:
   ```
   python --version
   ```
   You should see `Python 3.12.x`

---

## Method 1: Automated Installation (Recommended)

### Step 1: Extract the project files

1. Locate the ZIP file you received (e.g., `question_generator.zip` or `offline-installation.zip`)

2. Right-click the zip file and select **Extract All...**

3. Choose a destination folder (e.g., `C:\question_generator`)

4. Click **Extract**

### Step 2: Choose your installation flow

| You have internet on this machine | This machine has NO internet |
|---|---|
| Run the **Online** installer directly | First run the **download script** on an internet machine, then transfer |

---

### Online Installation (This Machine Has Internet)

1. **Open PowerShell as Administrator:**
   - Press `Windows Key`, type `PowerShell`
   - Right-click **Windows PowerShell** and select **Run as Administrator**

2. **Navigate to the project folder:**
   ```powershell
   cd C:\question_generator
   ```

3. **Run the installer:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File server\install_windows.ps1
   ```

4. **Select "Online"** when prompted (type `1` and press Enter)

5. Wait for installation to complete (may take 30–60 minutes depending on your internet speed).

### Offline Installation (Prepare on Another Machine)

**On the internet-connected machine:**

1. Open **PowerShell** (no need for Administrator)

2. Navigate to the project folder:
   ```powershell
   cd C:\path\to\question_generator
   ```

3. Run the download script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File download_dependencies_windows.ps1
   ```

4. This will download everything (~12–14 GB). Wait for it to complete.

5. Copy the entire `question_generator` folder to the offline machine using:
   - USB drive (large enough — 14 GB+)
   - Network share
   - External hard drive

**On the target Windows machine (no internet):**

1. **Open PowerShell as Administrator**

2. Navigate to the project folder:
   ```powershell
   cd C:\question_generator
   ```

3. Run the installer:
   ```powershell
   powershell -ExecutionPolicy Bypass -File server\install_windows.ps1
   ```

4. **Select "Offline"** when prompted (type `2` and press Enter)

5. Wait for installation to complete.

### Step 3: Start the Server

After installation, start the server:

```powershell
powershell -ExecutionPolicy Bypass -File server\run_windows.ps1
```

Open **http://localhost:8000** in your web browser.

---

## Method 2: Manual Installation (Step by Step)

Follow these steps if you prefer to do everything manually or if the automated scripts don't work.

### 1. Install Python 3.12

1. Download from https://www.python.org/downloads/
2. Run the installer
3. Check **"Add Python to PATH"**
4. Click **Install Now**
5. Verify: Open Command Prompt and run `python --version`

### 2. Create a Virtual Environment

Open **PowerShell** or **Command Prompt** in the project folder:

```cmd
cd C:\question_generator\server
python -m venv .venv
```

### 3. Activate the Virtual Environment

**PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

**Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

You should see `(.venv)` at the beginning of the command line.

### 4. Install Python Packages

```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

This will install all Python dependencies (FastAPI, ChromaDB, PyMuPDF, sentence-transformers, etc.).

If you get errors about `python-multipart` or similar, run the command again.

### 5. Install Ollama

1. Go to https://ollama.com/download/windows
2. Download **OllamaSetup.exe**
3. Run the installer (follow the on-screen instructions)
4. After installation, verify:
   ```cmd
   ollama --version
   ```

### 6. Download Ollama Models

Ollama needs three models. Open a new **Command Prompt** or **PowerShell** (after Ollama is installed) and run:

```cmd
ollama pull qwen2.5:7b-instruct
```

Wait for this to complete (it's about 4.7 GB — takes 15–30 minutes).

```cmd
ollama pull nomic-embed-text
```

This is smaller (about 274 MB — takes 2–5 minutes).

```cmd
ollama pull llama3.2:3b
```

This is about 2 GB (takes 5–15 minutes).

### 7. Cache the Cross-Encoder Model

Make sure your virtual environment is activated, then run:

```cmd
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
```

This downloads about 423 MB. Wait for it to complete.

### 8. Install Tailwind CSS

Download the Tailwind CSS file for the web UI:

```cmd
curl -sL https://cdn.tailwindcss.com -o app\static\js\tailwind.min.js
```

### 9. Create Data Directories

```cmd
mkdir ..\data\chroma_db
mkdir ..\data\uploaded_docs
```

### 10. Start the Server

Make sure Ollama is running (check the system tray — the Ollama llama icon should be there).

Then, from the `server` folder with the virtual environment activated:

```cmd
set DATA_DIR=..\data
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Starting the Server (After Installation)

### Quick Start

Just double-click or run:

```powershell
powershell -ExecutionPolicy Bypass -File server\run_windows.ps1
```

This will:
1. Check if Ollama is running (start it if needed)
2. Start the web server
3. Open http://localhost:8000

### With Custom Data Directory

```powershell
$env:DATA_DIR = "D:\my_project_data"
powershell -ExecutionPolicy Bypass -File server\run_windows.ps1
```

### Manual Start

```cmd
cd C:\question_generator\server
.venv\Scripts\activate
set DATA_DIR=..\data
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### "Python is not recognized"
- You skipped the "Add Python to PATH" step during installation
- Reinstall Python and make sure to check that box
- Or manually add Python to your PATH environment variable

### "ExecutionPolicy" error when running scripts
Run PowerShell with this command:
```powershell
powershell -ExecutionPolicy Bypass -File script_name.ps1
```

### "pip is not recognized"
Ensure Python is in your PATH. Or use:
```cmd
python -m pip install ...
```

### "Ollama not found" after installation
- Restart your computer (Ollama adds itself to PATH but needs a restart)
- Or manually add `C:\Program Files\Ollama` to your PATH

### "Ollama server is not running"
- Check your system tray (bottom-right of screen) for the Ollama llama icon
- If not there, start Ollama from the Start Menu
- Or run `ollama serve` in a terminal

### "Port 8000 already in use"
Another program is using port 8000. Either close that program or change the port:
```cmd
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### "Module not found" errors
Your virtual environment may not be activated. Make sure you see `(.venv)` in your command prompt.

### "sentence-transformers" or "torch" errors
These are large packages. If installation failed, try:
```cmd
pip install --no-cache-dir sentence-transformers
```

### Web UI has no styling (plain text)
Tailwind CSS is missing. Download it:
```cmd
curl -sL https://cdn.tailwindcss.com -o server\app\static\js\tailwind.min.js
```
Or copy the file from the project dependencies if you did an offline setup.

---

## Files Reference

| File | Purpose |
|------|---------|
| `WINDOWS_SETUP.md` | This guide |
| `download_dependencies_windows.ps1` | Download all dependencies for offline Windows install |
| `server/install_windows.ps1` | Install everything on Windows (online or offline) |
| `server/run_windows.ps1` | Start the server |
| `dependencies/python/` | Python wheel files (.whl) |
| `dependencies/ollama/binary/OllamaSetup.exe` | Ollama Windows installer |
| `dependencies/ollama/models/` | Ollama model files (blobs + manifests) |
| `dependencies/models/` | HuggingFace model cache (cross-encoder) |
| `dependencies/tailwind/` | Tailwind CSS |
