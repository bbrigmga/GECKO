@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
echo Starting Grok Portfolio Replicator at http://localhost:8765
uvicorn app.main:app --reload --port 8765
