"""把 PDF 里的姓名/学号等替换成占位符，便于把真实文档用作评测语料。

做法是真正的"涂改"：不只画个方块盖住，而是把文字从内容流里删掉再写入占位符，
所以文本层里也不会残留——否则检索/日志里还会看到原值。

    python tools/redact_pdf.py 输入.pdf 输出.pdf 梁永翔 202235010321 欧子玉
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


def redact(src: Path, dst: Path, terms: list[str], placeholder: str = "***") -> int:
    doc = pymupdf.open(str(src))
    hits = 0
    for page in doc:
        for term in terms:
            for rect in page.search_for(term):
                page.add_redact_annot(rect, text=placeholder, fill=(1, 1, 1), text_color=(0, 0, 0))
                hits += 1
    if hits:
        for page in doc:
            page.apply_redactions()
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst), garbage=4, deflate=True)
    doc.close()
    return hits


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        raise SystemExit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    terms = sys.argv[3:]
    hits = redact(src, dst, terms)
    print(f"替换 {hits} 处 → {dst}")

    # 自检：确认文本层里已经没有原值
    doc = pymupdf.open(str(dst))
    text = "".join(page.get_text() for page in doc)
    leaked = [t for t in terms if t in text]
    print("残留检查:", "干净" if not leaked else f"仍有 {leaked}")
    doc.close()


if __name__ == "__main__":
    main()
