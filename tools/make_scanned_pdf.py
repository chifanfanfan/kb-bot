"""把一份文字版 PDF 渲染成"扫描版"（只有图片、没有文字层），用来测 OCR。

    python tools/make_scanned_pdf.py data/北极星Pro产品手册.pdf data/扫描版示例.pdf [页数]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf as fitz


def make_scanned(src: Path, dst: Path, dpi: int = 200, pages: int | None = None) -> None:
    src_doc = fitz.open(str(src))
    out = fitz.open()
    limit = min(pages or len(src_doc), len(src_doc))
    for i in range(limit):
        pix = src_doc[i].get_pixmap(dpi=dpi)
        page = out.new_page(width=pix.width * 72 / dpi, height=pix.height * 72 / dpi)
        page.insert_image(page.rect, pixmap=pix)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dst))
    out.close()
    src_doc.close()
    print(f"saved: {dst} ({limit} 页, {dst.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/北极星Pro产品手册.pdf")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "data/扫描版示例.pdf")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else None
    make_scanned(src, dst, pages=n)
