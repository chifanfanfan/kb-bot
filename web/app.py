"""一个最小可用的 Web 界面：上传 PDF、提问、看来源。

    python web/app.py            # 默认 http://127.0.0.1:8000
    python web/app.py --port 9000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

from kb import KnowledgeBase  # noqa: E402
from kb.config import DATA_DIR  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 单文件 64 MB

KB: KnowledgeBase | None = None


def kb() -> KnowledgeBase:
    global KB
    if KB is None:
        KB = KnowledgeBase()
    return KB




@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/stats")
def api_stats():
    store = kb().store
    docs = {r.doc for r in store.all_records()}
    return jsonify({"chunks": store.count(), "docs": len(docs)})


@app.post("/api/ask")
def api_ask():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "问题不能为空"}), 400
    try:
        ans = kb().answer(question)
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
    return jsonify({
        "answer": ans.text,
        "note": ans.note,
        "grounded": ans.grounded,
        "citations": ans.citations,
    })


@app.post("/api/upload")
def api_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "没有文件"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "只支持 PDF"}), 400
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / secure_filename(file.filename)
    file.save(path)
    try:
        stats = kb().build([path])
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
    return jsonify({
        "pages": stats["pages"],
        "sections": stats["sections"],
        "chunks": stats["chunks"],
        "ocr_pages": stats["ocr_pages"],
    })


@app.post("/api/reset")
def api_reset():
    kb().store.reset()
    kb().retriever.refresh()
    return jsonify({"ok": True})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"打开 http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
