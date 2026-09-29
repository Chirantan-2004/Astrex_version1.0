#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

PORT=8000
if python3 - <<'PY'
import socket
s = socket.socket()
s.bind(('127.0.0.1', 8000))
s.close()
PY
then
  PORT=8000
else
  PORT=8001
fi

echo "Starting ASTRAX on http://127.0.0.1:$PORT"
python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
