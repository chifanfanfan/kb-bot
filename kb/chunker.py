"""分块：结构感知 + 句子边界 + 重叠窗口，并生成父子两块。

为什么要这么切（详见 README）：

1. 先按章节切，保证一个块不跨主题；
2. 章内按句子打包到 target size，不硬切，避免把一句结论劈成两半；
3. 相邻块保留 overlap 个字符的尾巴，防止答案正好落在切口；
4. 每个小块都挂一个"父块"（整个小节，≤1500 字），召回时用小而准的块，
   喂给模型时换成大而全的父块——兼顾召回精度和上下文完整性。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import ChunkConfig
from .pdf_loader import Section

SENT_SPLIT = re.compile(r"(?<=[。！？；!?;])|(?<=\.)\s+|\n+")


@dataclass
class Chunk:
    id: str
    text: str
    doc: str
    section: str
    page: int
    page_end: int
    index: int
    parent_id: str
    parent_text: str
    extra: dict = field(default_factory=dict)


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_SPLIT.split(text) if p and p.strip()]
    merged: list[str] = []
    for p in parts:
        # 过短的片段（如单独的"。"）并回上一句
        if merged and len(p) < 4:
            merged[-1] += p
        else:
            merged.append(p)
    return merged


def _tail(text: str, n: int) -> str:
    """取结尾 n 个字符，尽量从句子开头起。"""
    if len(text) <= n:
        return text
    tail = text[-n:]
    m = re.search(r"[。！？；!?;]", tail)
    return tail[m.end():] if m else tail


def pack_sentences(sentences: list[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        if len(sent) > size:  # 超长句（表格行、无标点段落）硬切
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(sent), size - overlap):
                chunks.append(sent[i : i + size])
            continue
        if len(buf) + len(sent) <= size:
            buf += sent
        else:
            chunks.append(buf)
            buf = _tail(buf, overlap) + sent
    if buf:
        chunks.append(buf)
    return chunks


def build_chunks(sections: list[Section], cfg: ChunkConfig, doc_id: str,
                 paragraph_first: bool = True) -> list[Chunk]:
    chunks: list[Chunk] = []
    for s_idx, section in enumerate(sections):
        parent_id = f"{doc_id}:s{s_idx}"
        parent_text = section.text[: cfg.parent_size]

        # 小节里如果有多段、且每段都够长，就先按段落切开再打包。
        # 否则一个 377 字的小节会把"发帖流程 / 评论流程 / 浏览流程"混成一个块，
        # 向量被平均掉，问其中一条流程时反而召回不到（实测 rank 9、向量分 0）。
        paragraphs = [p.strip() for p in section.text.split("\n\n") if p.strip()]
        if paragraph_first and len(paragraphs) >= 2 and all(len(p) >= 60 for p in paragraphs):
            units = paragraphs
        else:
            units = [section.text]

        # 记录每个块是不是"一个完整单元"（整节或整段），用于决定长度下限
        piece_items: list[tuple[str, bool]] = []
        for unit in units:
            ps = pack_sentences(split_sentences(unit), cfg.size, cfg.overlap)
            whole = len(ps) == 1
            piece_items.extend((p, whole) for p in ps)

        for c_idx, (piece, whole_unit) in enumerate(piece_items):
            piece = piece.strip()
            # 整节/整段只有一个块时，min_chunk 不该把它丢掉——
            # 那会让这段内容在库里彻底不可检索（评测里真的踩到了）。
            floor = 30 if whole_unit else cfg.min_chunk
            if len(piece) < floor:
                continue
            chunks.append(
                Chunk(
                    id=f"{parent_id}:c{c_idx}",
                    text=piece,
                    doc=section.doc,
                    section=section.section,
                    page=section.page,
                    page_end=section.page_end,
                    index=c_idx,
                    parent_id=parent_id,
                    parent_text=parent_text,
                )
            )
    return chunks
