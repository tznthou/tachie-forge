#!/usr/bin/env python3
"""Local web UI for the remove-tachie-bg de-background system.

Wraps the already-validated scripts/remove_bg.py (called as a subprocess, so
the verified de-background core is never touched) behind a simple drag-drop
browser interface with the dual-background (dark + white) eye-check preview.

Run:  python3 app.py    (or double-click start.command)
Then: http://localhost:8765
"""
import base64
import os
import subprocess
import sys
import tempfile

from flask import Flask, jsonify, request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "remove_bg.py"))

# shell 繼承的 PYTHONPATH 會插在 sys.path 最前面蓋過 venv 套件; 清掉讓 subprocess
# (remove_bg.py)確實用 venv 依賴(start.command 已清, 這裡保手動啟動的場景)
os.environ.pop("PYTHONPATH", None)

app = Flask(__name__, static_folder="static")


def _b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/remove", methods=["POST"])
def remove():
    if "image" not in request.files or request.files["image"].filename == "":
        return jsonify({"error": "沒有收到圖片"}), 400
    bg_type = request.form.get("bg_type", "other")
    if bg_type not in ("green", "solid", "transparent", "other"):
        bg_type = "other"

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "cut.png")
        request.files["image"].save(inp)
        try:
            r = subprocess.run(
                [sys.executable, SCRIPT, inp, "-o", out, "--bg-type", bg_type],
                capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            return jsonify({"error": "去背逾時(圖太大?)"}), 500
        if r.returncode != 0 or not os.path.exists(out):
            return jsonify({"error": (r.stderr or "去背失敗").strip()}), 500

        dark = os.path.join(td, "cut_darkcheck.png")
        white = os.path.join(td, "cut_whitecheck.png")
        return jsonify({
            "cutout": _b64(out),
            "dark": _b64(dark) if os.path.exists(dark) else None,
            "white": _b64(white) if os.path.exists(white) else None,
            "log": r.stdout.strip(),
        })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"\n  立繪去背系統已啟動 →  http://localhost:{port}\n  (Ctrl+C 結束)\n")
    app.run(host="127.0.0.1", port=port, debug=False)
