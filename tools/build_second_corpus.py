"""建"第二语料"：三份政府公开文件（政策法规类，和产品手册完全不同领域）。

    python tools/build_second_corpus.py

产物：
- data/general/*.pdf         三份 PDF（用 PyMuPDF 的 china-s 字体，中文不乱码）
- eval/general/chroma/       独立向量库
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf  # noqa: E402

from kb import KnowledgeBase  # noqa: E402
from kb.config import Config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "general"
STORE = ROOT / "eval" / "general" / "chroma"

SOURCES = [
    ("个人信息保护法", "http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html"),
    ("十四五数字经济发展规划", "https://www.gov.cn/zhengce/content/2022-01/12/content_5667817.htm"),
    ("数字中国建设整体布局规划", "https://www.gov.cn/zhengce/2023-02/27/content_5743484.htm"),
]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", html)
    lines = [ln.strip() for ln in text.splitlines()]
    # 去掉导航/版权这类短行和重复的站名
    keep = [ln for ln in lines if len(ln) >= 12]
    return "\n".join(keep)


def make_pdf(title: str, body: str, path: Path) -> int:
    """把长文本写成 PDF（每页约 1800 字），返回页数。"""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), title, fontname="china-s", fontsize=16)
    y = 90
    for para in body.splitlines():
        # 手工折行（PyMuPDF 不自动换行）
        line = ""
        for ch in para:
            line += ch
            if len(line) >= 42:
                if y > 780:
                    page = doc.new_page()
                    y = 60
                page.insert_text((50, y), line, fontname="china-s", fontsize=9)
                y += 14
                line = ""
        if line:
            if y > 780:
                page = doc.new_page()
                y = 60
            page.insert_text((50, y), line, fontname="china-s", fontsize=9)
            y += 14
        y += 4
    doc.save(str(path))
    pages = doc.page_count
    doc.close()
    return pages


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    paths = []
    for title, url in SOURCES:
        try:
            body = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {title}: {type(exc).__name__} {exc}")
            continue
        path = DATA / f"{title}.pdf"
        pages = make_pdf(title, body, path)
        print(f"[ok] {title}: {len(body)} 字 → {pages} 页 → {path.name}")
        paths.append(path)

    if not paths:
        raise SystemExit("没有抓到任何文档，检查网络")

    cfg = Config()
    cfg.store_dir = STORE
    cfg.collection = "kb_general"
    cfg.use_cache = False
    if STORE.exists():
        import shutil
        shutil.rmtree(STORE)
    kb = KnowledgeBase(cfg)
    stats = kb.build(paths)
    print(f"\n建库完成：{stats}")
    print(f"库位置：{STORE}")


if __name__ == "__main__":
    main()
