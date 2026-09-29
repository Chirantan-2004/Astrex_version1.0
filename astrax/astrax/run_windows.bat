@echo off
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

set "PORT=8000"
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 8000)); s.close()" >nul 2>&1
if errorlevel 1 set "PORT=8001"

echo Starting ASTRAX on http://127.0.0.1:%PORT%
python -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
