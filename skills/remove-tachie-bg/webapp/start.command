#!/bin/bash
# 立繪去背系統 — macOS 雙擊啟動器
# 優先用專案根目錄的 .venv (uv 建立, 含 flask/rembg 全套), 沒有才退回系統 python3
cd "$(dirname "$0")"
VENV="$(cd ../../.. && pwd)/.venv"
if [ -x "$VENV/bin/python3" ]; then
  export PATH="$VENV/bin:$PATH"
  exec "$VENV/bin/python3" app.py
fi
exec python3 app.py
