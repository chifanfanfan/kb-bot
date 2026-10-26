"""一个最小可用的 Web 界面：上传 PDF、提问、看来源。

    python web/app.py            # 默认 http://127.0.0.1:8000
    python web/app.py --port 9000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template_string, request  # noqa: E402
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


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PDF 知识库问答</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --line:#262b36; --fg:#e6e8ee; --dim:#8b93a7; --accent:#4f8cff; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.65 system-ui,"Segoe UI","Microsoft YaHei",sans-serif;
         background:var(--bg); color:var(--fg); height:100vh; display:flex; flex-direction:column; }
  header { padding:14px 20px; border-bottom:1px solid var(--line); display:flex; gap:16px;
           align-items:center; background:var(--panel); }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  .stats { color:var(--dim); font-size:13px; }
  main { flex:1; overflow-y:auto; padding:24px 20px; }
  .wrap { max-width:820px; margin:0 auto; }
  .msg { margin-bottom:22px; }
  .q { color:var(--dim); margin-bottom:6px; }
  .q b { color:var(--fg); font-weight:600; }
  .a { white-space:pre-wrap; }
  .warn { color:#f0b429; font-size:13px; margin-top:6px; }
  .src { margin-top:10px; border-left:2px solid var(--line); padding-left:12px; font-size:13px; color:var(--dim); }
  .src div { margin:4px 0; }
  .src b { color:var(--accent); font-weight:600; }
  footer { border-top:1px solid var(--line); background:var(--panel); padding:14px 20px; }
  form { max-width:820px; margin:0 auto; display:flex; gap:10px; }
  input[type=text] { flex:1; padding:11px 14px; border-radius:8px; border:1px solid var(--line);
                     background:var(--bg); color:var(--fg); font-size:15px; outline:none; }
  input[type=text]:focus { border-color:var(--accent); }
  button { padding:11px 18px; border-radius:8px; border:0; background:var(--accent); color:#fff;
           font-size:15px; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  button.ghost { background:transparent; border:1px solid var(--line); color:var(--dim); font-size:13px;
                 padding:7px 12px; }
  .drop { color:var(--dim); font-size:13px; }
  .spinner { display:inline-block; width:14px; height:14px; border:2px solid var(--line);
             border-top-color:var(--accent); border-radius:50%; animation:s .8s linear infinite; vertical-align:-2px; }
  @keyframes s { to { transform:rotate(360deg); } }
</style>
</head>
<body>
<header>
  <h1>PDF 知识库问答</h1>
  <span class="stats" id="stats">加载中…</span>
  <span style="flex:1"></span>
  <input type="file" id="file" accept=".pdf" style="display:none">
  <button class="ghost" onclick="document.getElementById('file').click()">上传 PDF</button>
  <button class="ghost" onclick="reset()">清空库</button>
</header>
<main><div class="wrap" id="log"></div></main>
<footer>
  <form onsubmit="ask(event)">
    <input type="text" id="q" placeholder="问点什么，比如：年付多少钱？" autocomplete="off">
    <button id="send" type="submit">提问</button>
  </form>
</footer>
<script>
const log = document.getElementById('log');

async function refreshStats() {
  const r = await fetch('/api/stats'); const d = await r.json();
  document.getElementById('stats').textContent =
    d.chunks ? `${d.chunks} 个文本块 · ${d.docs} 个文档` : '库是空的，先上传 PDF';
}

function addQuestion(q) {
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `<div class="q"><b>你</b>：${escapeHtml(q)}</div><div class="a"><span class="spinner"></span></div>`;
  log.appendChild(div); log.scrollTop = log.scrollHeight;
  return div.querySelector('.a');
}

async function ask(ev) {
  ev.preventDefault();
  const input = document.getElementById('q');
  const q = input.value.trim();
  if (!q) return;
  input.value = ''; document.getElementById('send').disabled = true;
  const slot = addQuestion(q);
  try {
    const r = await fetch('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'},
                                       body: JSON.stringify({question: q})});
    const d = await r.json();
    if (d.error) { slot.textContent = '出错了：' + d.error; return; }
    let html = escapeHtml(d.answer);
    if (d.note) html += `<div class="warn">⚠ ${escapeHtml(d.note)}</div>`;
    if (d.citations && d.citations.length) {
      html += '<div class="src">' + d.citations.map(c =>
        `<div><b>[${c.n}]</b> 《${escapeHtml(c.doc)}》第 ${c.page}-${c.page_end} 页 · ${escapeHtml(c.section)}<br>　　${escapeHtml(c.snippet)}…</div>`
      ).join('') + '</div>';
    }
    slot.innerHTML = html;
  } catch (e) { slot.textContent = '网络错误：' + e.message; }
  finally { document.getElementById('send').disabled = false; log.scrollTop = log.scrollHeight; }
}

document.getElementById('file').addEventListener('change', async (e) => {
  const f = e.target.files[0]; if (!f) return;
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `<div class="q"><b>上传</b>：${escapeHtml(f.name)}</div><div class="a"><span class="spinner"></span> 解析并建索引…</div>`;
  log.appendChild(div); log.scrollTop = log.scrollHeight;
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/upload', {method:'POST', body: fd});
  const d = await r.json();
  div.querySelector('.a').textContent = d.error ? ('失败：' + d.error)
    : `完成：${d.pages} 页 → ${d.sections} 节 → ${d.chunks} 块${d.ocr_pages ? `（OCR ${d.ocr_pages} 页）` : ''}`;
  refreshStats();
});

async function reset() {
  if (!confirm('确定清空向量库？')) return;
  await fetch('/api/reset', {method:'POST'});
  log.innerHTML = ''; refreshStats();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

refreshStats();
</script>
</body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


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
