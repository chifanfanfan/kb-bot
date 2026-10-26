"""PDF 解析：抽文本 → 去页眉页脚 → 按标题切"章节"。

pypdf 只负责把每页文字拿出来；真正的结构判断在这里做，因为后面分块要
按章节走，而不是把整本书当成一坨纯文本。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# 常见标题形态：第3章、1.2 小节、一、二、三、附录/前言/总结
HEADING_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百零\d]+[章节篇条]\s*[、.：:]?\s*\S.*$"),
    re.compile(r"^\d+(\.\d+){0,3}[\s、.．]\s*\S.{0,60}$"),
    re.compile(r"^[一二三四五六七八九十]+[、.．]\s*\S.{0,60}$"),
    re.compile(r"^(附录|前言|序言|摘要|目录|总结|结语|参考)(\s|[:：]|$).{0,60}$"),
    re.compile(r"^(参考文献|致谢|Abstract|ABSTRACT)\s*$"),
]
MAX_HEADING_LEN = 40
# 目录里的点线引导符，如 "6.2 展望...........7"
DOT_LEADER = re.compile(r"[.．·]{4,}|…{2,}")
# 参考文献条目：形如 "47 (05): 1023-1042" 或带 [J]/doi，别当成标题
REF_LIKE = re.compile(r"\(\d{2,4}\)\s*[:：]|\[[JCMPR]\]|doi\.org|DOI|pp\.\s*\d")


@dataclass
class Section:
    doc: str
    section: str
    page: int
    page_end: int
    text: str


@dataclass
class ParsedDoc:
    name: str
    path: Path
    pages: int
    sections: list[Section]
    ocr_pages: int = 0


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > MAX_HEADING_LEN:
        return False
    # 句子不是标题：以句末标点结尾的多半是正文被折断的那一行
    if s.endswith(("。", "；", "，", "、", "：", ":")):
        return False
    # 目录行：带点线引导
    if DOT_LEADER.search(s):
        return False
    # 参考文献条目
    if REF_LIKE.search(s):
        return False
    return any(p.match(s) for p in HEADING_PATTERNS)


def _strip_running_heads(pages: list[str]) -> list[str]:
    """去掉在多数页面重复出现的行（页眉、页脚、页码）。"""
    if len(pages) < 4:
        return pages
    counter: Counter[str] = Counter()
    for text in pages:
        seen = {ln.strip() for ln in text.splitlines() if 0 < len(ln.strip()) <= 80}
        counter.update(seen)
    threshold = max(3, int(len(pages) * 0.6))
    boilerplate = {ln for ln, n in counter.items() if n >= threshold}
    if not boilerplate:
        return pages
    cleaned = []
    for text in pages:
        kept = [ln for ln in text.splitlines() if ln.strip() not in boilerplate]
        cleaned.append("\n".join(kept))
    return cleaned


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 中文正文里被硬换行切断的句子，补回连续。
    # 表格行必须豁免：markdown 行以 "|" 结尾，不能被合并成一行。
    text = re.sub(r"(?<=[^\n。！？；：|])\n(?![|\n])", "", text)
    return text.strip()


def _cell(value) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip().replace("|", "\\|")
    # pymupdf 有时把 "password_hash" 拆成 "password hash _"；把两部分拼回一个标识符
    text = re.sub(r"\s+_$", "_", text)
    m = re.fullmatch(r"(\w+) (\w+)_", text)
    if m:
        text = f"{m.group(1)}_{m.group(2)}"
    return text


def _table_to_markdown(table) -> str:
    """把检测到的表格还原成 markdown 行，保留列语义。"""
    try:
        rows = [[_cell(c) for c in row] for row in table.extract()]
    except Exception:
        return ""
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * width) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _page_text_with_tables(page) -> str:
    """有表格的页：表格换成 markdown，其余文字按阅读顺序保留。

    pypdf 抽出来的表格是 "id BIGINT 20 NO 用户主键 username VARCHAR..." 这种
    连读文本，模型读不懂列之间的关系，经常直接拒答。pymupdf 能识别表格结构，
    这里就借它把表格重新排版。
    """
    try:
        found = page.find_tables()
    except Exception:
        return page.get_text()
    tables = list(getattr(found, "tables", []) or [])
    if not tables:
        return page.get_text()

    boxes = [t.bbox for t in tables]
    items: list[tuple[float, float, str]] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        if any(not (x1 <= bx0 or x0 >= bx1 or y1 <= by0 or y0 >= by1)
               for bx0, by0, bx1, by1 in boxes):
            continue  # 落在表格区域内的文字，用 markdown 代替
        if text.strip():
            items.append((y0, x0, text))

    for table in tables:
        md = _table_to_markdown(table)
        if md:
            items.append((table.bbox[1], table.bbox[0], md))

    items.sort(key=lambda it: (it[0], it[1]))
    return "\n".join(it[2].strip() for it in items if it[2].strip())


def _extract_pages_text(path: Path) -> tuple[list[str], int]:
    """返回 (每页文本, 页数)。有表格的页用 pymupdf 重排，其余用 pypdf。"""
    try:
        import pymupdf

        doc = pymupdf.open(str(path))
        texts = [_page_text_with_tables(page) for page in doc]
        pages = doc.page_count
        doc.close()
        return texts, pages
    except Exception as exc:
        print(f"  [warn] pymupdf 解析失败，退回 pypdf：{type(exc).__name__}: {exc}")
        reader = PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages], len(reader.pages)


def parse_pdf(path: Path, *, ocr: bool = False, llm=None) -> ParsedDoc:
    raw_pages, page_count = _extract_pages_text(path)

    ocr_used = 0
    if ocr:
        from .ocr import ocr_pages, page_is_sparse

        sparse = [i for i, t in enumerate(raw_pages) if page_is_sparse(t)]
        if sparse:
            if llm is None:
                print(f"  [warn] {len(sparse)} 页几乎抽不到文字，但未提供模型，跳过 OCR")
            else:
                print(f"  {path.name}: {len(sparse)} 页无文本，调用视觉模型 OCR ...")
                try:
                    got = ocr_pages(path, sparse, llm)
                except Exception as exc:
                    print(f"  [warn] OCR 失败，保留原文本：{type(exc).__name__}: {exc}")
                    got = {}
                for idx, text in got.items():
                    if text:
                        raw_pages[idx] = text
                        ocr_used += 1

    pages = _strip_running_heads(raw_pages)

    sections: list[Section] = []
    doc_name = path.name
    current_title = "正文"
    current_page = 1
    buffer: list[str] = []

    def flush(page_end: int) -> None:
        text = _normalize("\n".join(buffer))
        if len(text) >= 20:
            sections.append(
                Section(doc=doc_name, section=current_title, page=current_page,
                        page_end=page_end, text=text)
            )

    for page_no, text in enumerate(pages, start=1):
        for line in text.splitlines():
            if _is_heading(line):
                flush(page_no)
                buffer = []
                current_title = line.strip()
                current_page = page_no
            else:
                buffer.append(line)
    flush(page_count)

    if not sections:
        whole = _normalize("\n".join(pages))
        if whole:
            sections = [Section(doc_name, "正文", 1, page_count, whole)]

    # 过小的节（常见于测试表格、占位标题）并进上一节，避免产生大量碎块
    merged: list[Section] = []
    for sec in sections:
        if len(sec.text) < 60 and merged:
            prev = merged[-1]
            prev.text = f"{prev.text}\n{sec.text}"
            prev.page_end = sec.page_end
        else:
            merged.append(sec)

    return ParsedDoc(name=doc_name, path=path, pages=page_count, sections=merged,
                     ocr_pages=ocr_used)
