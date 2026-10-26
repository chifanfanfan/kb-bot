"""RAG 主流程：召回 → 拼上下文 → 生成 → 引用校验 → 幻觉兜底。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .chunker import build_chunks
from .config import STORE_DIR, Config
from .embedding import BGEEmbedding
from .llm import LLM
from .memory import ConversationMemory
from .pdf_loader import parse_pdf
from .retriever import Hit, HybridRetriever
from .store import VectorStore

SYSTEM_PROMPT = """你是文档问答助手。只能依据【资料】回答，遵守：
1. 每个结论后面必须标注来源编号，如 [1]、[2]；一句话有多个来源就都标上。
2. 资料里没有的信息，直接说"资料中没有提到"，禁止用常识或推测补全。
3. 数字、日期、专有名词必须与资料完全一致，不做换算或近似。
4. 资料之间有冲突时，分别列出并指出冲突，不要擅自取舍。
5. 回答用中文，先给结论，再给依据，不超过 400 字。
6. 表结构里的字段类型、长度、是否可空等属性就是该字段的定义，直接按字面回答；
   不要因为资料没写"这是上限/下限"而拒答。
7. 同一主题存在多条不同层级的条款时，优先采用最具体的那条
   （例如服务可用性补偿优先于通用违约赔偿），并说明适用条件。
"""

STRICT_PROMPT = """你是文档问答助手，处于严格模式。上一次回答包含资料无法支持的内容。
请重写：只保留资料里能逐字找到依据的句子，其余全部删除；若资料不足以回答，只输出"资料中没有提到"。
每个保留的句子后面必须标注来源编号。"""

VERIFY_PROMPT = """判断【回答】中的每个事实性论断能否在【资料】中找到依据。
输出 JSON：{"grounded": true/false, "unsupported": ["无法支持的论断", ...]}
只判定事实性内容；修辞、过渡句、"资料中没有提到"这类表述不算论断。"""

REFUSAL = "资料中没有找到与「{q}」相关的内容，无法回答。可以换个说法，或补充相关文档后再问。"


@dataclass
class Answer:
    text: str
    citations: list[dict] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    grounded: bool = True
    note: str = ""


def _dedupe_by_parent(hits: list[Hit]) -> list[Hit]:
    seen: dict[str, Hit] = {}
    for h in hits:
        cur = seen.get(h.id.split(":c")[0])
        if cur is None or h.score > cur.score:
            seen[h.id.split(":c")[0]] = h
    return list(seen.values())


def _window(parent: str, child: str, limit: int) -> str:
    """父块太长时，取以命中块为中心的一段，而不是从头截断。

    真实文档里一个大节动辄两三千字，表格常常在中后段；直接截前 1200 字
    会让模型"看不到表格"，然后误判成"资料里没有"。
    """
    if len(parent) <= limit:
        return parent
    pos = parent.find(child[:80]) if child else -1
    if pos < 0:
        return parent[:limit]
    start = max(0, min(pos - limit // 3, len(parent) - limit))
    return parent[start : start + limit]


class KnowledgeBase:
    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or Config()
        self.embedder = BGEEmbedding()
        self.store = VectorStore(STORE_DIR)
        self.llm = LLM(self.cfg.llm)
        self.retriever = HybridRetriever(self.store, self.embedder, self.cfg.retrieve)
        self.retriever.refresh()

    # ---------------- 建库 ----------------
    def _embed_text(self, chunk) -> str:
        """编码用的文本：小节标题 + 正文。

        小块常常是"……因此需要快速返回审核结果……"，脱离标题后语义指向不明；
        把标题拼进去等于给每个块补了上下文（contextual retrieval 的轻量版）。
        """
        if getattr(self.cfg.chunk, "embed_with_title", True):
            return f"{chunk.section}\n{chunk.text}"
        return chunk.text

    def build(self, pdf_paths: list[Path], verbose: bool = True, ocr: bool = True) -> dict:
        stats = {"docs": 0, "sections": 0, "chunks": 0, "skipped_dupes": 0,
                 "ocr_pages": 0, "pages": 0}
        for path in pdf_paths:
            doc = parse_pdf(path, ocr=ocr, llm=self.llm if ocr else None)
            stats["ocr_pages"] += doc.ocr_pages
            stats["pages"] += doc.pages
            doc_id = re.sub(r"[^\w\u4e00-\u9fff]+", "_", doc.name)[:40]
            chunks = build_chunks(doc.sections, self.cfg.chunk, doc_id)
            if not chunks:
                if verbose:
                    print(f"  {doc.name}: 没抽到可用的文本，跳过")
                continue
            vectors = self.embedder.encode([self._embed_text(c) for c in chunks])
            keep, kept_vecs = [], []
            for chunk, vec in zip(chunks, vectors):
                if kept_vecs and float((np.asarray(kept_vecs) @ vec).max()) > 0.97:
                    stats["skipped_dupes"] += 1
                    continue
                keep.append(chunk)
                kept_vecs.append(vec)
            self.store.add(keep, [v.tolist() for v in kept_vecs])
            stats["docs"] += 1
            stats["sections"] += len(doc.sections)
            stats["chunks"] += len(keep)
            if verbose:
                print(f"  {doc.name}: {doc.pages} 页 → {len(doc.sections)} 节 → {len(keep)} 块")
        self.retriever.refresh()
        return stats

    # ---------------- 上下文 ----------------
    def _context(self, hits: list[Hit], max_chars: int = 12000) -> tuple[str, list[dict]]:
        block, cites, used = [], [], 0
        for i, h in enumerate(hits, start=1):
            body = _window(h.parent_text, h.text, 3000)
            entry = (
                f"[{i}] 《{h.doc}》第 {h.page}-{h.page_end} 页 · {h.section}\n{body}"
            )
            if used + len(entry) > max_chars:
                break
            block.append(entry)
            used += len(entry)
            cites.append(
                {"n": i, "doc": h.doc, "section": h.section, "page": h.page,
                 "page_end": h.page_end, "snippet": h.text[:120], "score": round(h.score, 4)}
            )
        return "\n\n---\n\n".join(block), cites

    @staticmethod
    def _parse_citations(text: str) -> list[int]:
        return sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})

    # ---------------- 问答 ----------------
    def answer(self, question: str, memory: ConversationMemory | None = None,
               verbose: bool = False) -> Answer:
        # 把「追问改写」和「多查询扩写」合并成一次调用：
        # 两件事都是"把用户的话翻译成检索用语"，分开做要多一次网络往返。
        from .memory import needs_condense
        from .rewrite import rewrite

        # 有历史就把历史给模型，由它判断要不要补全。
        # 之前用 needs_condense() 做硬门控，漏掉了"达不到怎么赔？"这类省略主语的追问，
        # 结果检索丢了"99.9%"这个关键限定。
        history = ""
        if memory is not None and memory.turns:
            history = "\n".join(
                f"用户：{t.question}\n助手：{t.answer[:150]}" for t in memory.turns[-3:]
            )
        needs_rewrite = bool(history) or self.cfg.retrieve.use_multi_query
        if needs_rewrite:
            query, extra_queries = rewrite(self.llm, question, history)
        else:
            query, extra_queries = question, []
        hits = self.retriever.search(query, extra_queries=extra_queries)
        best_vec = max((h.vector_score for h in hits), default=0.0)

        if not hits or best_vec < self.cfg.retrieve.min_score:
            return Answer(
                text=REFUSAL.format(q=query),
                grounded=False,
                note=f"最高向量相似度 {best_vec:.3f} < 阈值 {self.cfg.retrieve.min_score}",
            )

        hits = _dedupe_by_parent(hits)
        context, cites = self._context(hits)
        user = f"【资料】\n{context}\n\n【问题】{question}\n\n请依据资料回答，并标注 [编号]。"
        text = self.llm.chat(SYSTEM_PROMPT, user)

        # 引用编号必须真实存在，防止模型编造 [9]
        valid = {c["n"] for c in cites}
        cited = [n for n in self._parse_citations(text) if n in valid]
        # 短答案（通常就是一句结论）跳过二次校验，省一次 LLM 调用
        skip_verify = 0 < len(text) < self.cfg.verify_min_chars and bool(cited)
        grounded, issues = (True, []) if skip_verify else self._verify(text, context)

        if not grounded:
            text = self.llm.chat(STRICT_PROMPT, user)
            cited = [n for n in self._parse_citations(text) if n in valid]
            grounded, issues = self._verify(text, context)
            if not grounded and verbose:
                print(f"  [warn] 严格模式后仍有无法支持的论断：{issues[:3]}")

        if "资料中没有提到" in text and not cited:
            return Answer(text=text, citations=[], hits=hits, grounded=grounded,
                          note="检索有结果但资料不足以支撑回答")

        return Answer(
            text=text,
            citations=[c for c in cites if c["n"] in cited] or cites[:3],
            hits=hits,
            grounded=grounded,
            note="" if grounded else f"含 {len(issues)} 处未验证论断",
        )

    def _verify(self, answer: str, context: str) -> tuple[bool, list[str]]:
        if "资料中没有提到" in answer:
            return True, []
        result = self.llm.json_chat(
            VERIFY_PROMPT,
            f"【资料】\n{context[:4000]}\n\n【回答】\n{answer}",
            fallback={"grounded": True, "unsupported": []},
        )
        unsupported = result.get("unsupported") or []
        grounded = bool(result.get("grounded", True)) and not unsupported
        return grounded, unsupported
