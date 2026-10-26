"""检索：向量召回 + BM25 召回 → RRF 融合 → MMR 去重 → 重排。

单独任何一路都不够：
- 纯向量对"专有名词/编号/型号"不敏感，问"XY-2000 的保修期"经常召回无关段落；
- 纯 BM25 对同义改写无能为力（"退货" vs "退款"）。
两路都召 20 条，再用 RRF 融合，是很稳的默认组合。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

from .config import RetrieveConfig
from .embedding import BGEEmbedding
from .store import Record, VectorStore

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[a-zA-Z0-9_\-]+")


def tokenize(text: str) -> list[str]:
    """中文字符 + 汉字二元组 + 英文数字词。不用 jieba，省一个依赖且够用。"""
    chars = CJK.findall(text)
    bigrams = [a + b for a, b in zip(chars, chars[1:])]
    words = [w.lower() for w in WORD.findall(text)]
    return chars + bigrams + words


@dataclass
class Hit:
    id: str
    text: str
    parent_text: str
    doc: str
    section: str
    page: int
    page_end: int
    score: float = 0.0
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf: float = 0.0
    rerank: float = 0.0
    extra: dict = field(default_factory=dict)

    def brief(self) -> str:
        return f"[{self.doc} p{self.page}·{self.section}] {self.text[:60]}..."


class HybridRetriever:
    def __init__(self, store: VectorStore, embedder: BGEEmbedding, cfg: RetrieveConfig) -> None:
        self.store = store
        self.embedder = embedder
        self.cfg = cfg
        self._records: list[Record] = []
        self._bm25: BM25Okapi | None = None
        self._vec_cache: dict[str, np.ndarray] = {}
        self._reranker = None
        self._rerank_failed = False

    def _get_reranker(self):
        """懒加载：没开重排、或模型没下载时，不拖慢启动也不报错。"""
        if self._reranker is not None or self._rerank_failed:
            return self._reranker
        try:
            from .reranker import CrossEncoderReranker

            self._reranker = CrossEncoderReranker()
        except Exception as exc:  # 模型缺失/网络问题 → 退回纯 RRF 排序
            print(f"[warn] 重排模型不可用，退回 RRF 排序：{type(exc).__name__}: {exc}")
            self._rerank_failed = True
        return self._reranker

    # ---------- 索引 ----------
    def refresh(self) -> None:
        self._records = self.store.all_records()
        corpus = [tokenize(r.text) for r in self._records]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        self._vec_cache.clear()

    # ---------- 两路召回 ----------
    def _vector_hits(self, query: str, k: int) -> list[Hit]:
        emb = self.embedder.encode_one(self.cfg.query_instruction + query)
        res = self.store.query(emb, k)
        hits: list[Hit] = []
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        for cid, text, meta, dist in zip(ids, docs, metas, dists):
            meta = meta or {}
            hits.append(
                Hit(
                    id=cid,
                    text=text or "",
                    parent_text=meta.get("parent_text", text or ""),
                    doc=meta.get("doc", ""),
                    section=meta.get("section", ""),
                    page=int(meta.get("page", 0)),
                    page_end=int(meta.get("page_end", 0)),
                    vector_score=float(1.0 - dist),  # cosine distance → 相似度
                )
            )
        return hits

    def _bm25_hits(self, query: str, k: int) -> list[Hit]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        top = np.argsort(scores)[::-1][:k]
        hits: list[Hit] = []
        for idx in top:
            if scores[idx] <= 0:
                continue
            r = self._records[int(idx)]
            hits.append(
                Hit(
                    id=r.id,
                    text=r.text,
                    parent_text=r.parent_text,
                    doc=r.doc,
                    section=r.section,
                    page=r.page,
                    page_end=r.page_end,
                    bm25_score=float(scores[idx]),
                )
            )
        return hits

    # ---------- 融合 ----------
    @staticmethod
    def _rrf(vector_hits: list[Hit], bm25_hits: list[Hit], rrf_k: int) -> dict[str, float]:
        fused: dict[str, float] = {}
        for rank, hit in enumerate(vector_hits, start=1):
            fused[hit.id] = fused.get(hit.id, 0.0) + 1.0 / (rrf_k + rank)
        for rank, hit in enumerate(bm25_hits, start=1):
            fused[hit.id] = fused.get(hit.id, 0.0) + 1.0 / (rrf_k + rank)
        return fused

    def _mmr(self, query_vec: np.ndarray, hits: list[Hit], k: int, lam: float) -> list[Hit]:
        if not hits:
            return []
        missing = [h for h in hits if h.id not in self._vec_cache]
        if missing:
            fresh = self.embedder.encode([h.text for h in missing])
            for h, v in zip(missing, fresh):
                self._vec_cache[h.id] = v
        vecs = np.vstack([self._vec_cache[h.id] for h in hits])
        selected: list[int] = []
        remaining = list(range(len(hits)))
        sim_to_query = vecs @ query_vec
        while remaining and len(selected) < k:
            best_idx, best_val = None, -1e9
            for i in remaining:
                div = max((float(vecs[i] @ vecs[j]) for j in selected), default=0.0)
                val = lam * float(sim_to_query[i]) - (1 - lam) * div
                if val > best_val:
                    best_idx, best_val = i, val
            selected.append(best_idx)
            remaining.remove(best_idx)
        return [hits[i] for i in selected]

    # ---------- 对外 ----------
    def search(self, query: str, k: int | None = None, extra_queries: list[str] | None = None) -> list[Hit]:
        cfg = self.cfg
        k_final = k or cfg.top_k_final
        queries = [query] + [q for q in (extra_queries or []) if q and q != query]

        fused: dict[str, float] = {}
        pool: dict[str, Hit] = {}
        score_sum: dict[str, float] = {}
        # 原问题权重 1.0，变体权重可调：变体容易引入新词，把检索带偏
        weights = [1.0] + [getattr(cfg, "variant_weight", 1.0)] * (len(queries) - 1)
        for q, w in zip(queries, weights):
            vec_hits = self._vector_hits(q, cfg.top_k_vector)
            bm25_hits = self._bm25_hits(q, cfg.top_k_bm25) if cfg.use_bm25 else []
            max_bm25 = max((h.bm25_score for h in bm25_hits), default=0.0) or 1.0
            for hits in (vec_hits, bm25_hits):
                for rank, hit in enumerate(hits, start=1):
                    fused[hit.id] = fused.get(hit.id, 0.0) + w / (cfg.rrf_k + rank)
                    # 分数融合：两路各自归一化后加权。
                    # RRF 只看名次，会压掉"向量判无关但 BM25 极高分"的段落；
                    # 分数融合保留强度信息，对这种分歧更稳。
                    alpha = getattr(cfg, "fusion_alpha", 0.5)
                    norm = alpha * max(0.0, hit.vector_score) + (1 - alpha) * (hit.bm25_score / max_bm25)
                    score_sum[hit.id] = score_sum.get(hit.id, 0.0) + w * norm
                    kept = pool.get(hit.id)
                    if kept is None:
                        pool[hit.id] = hit
                    else:
                        kept.vector_score = max(kept.vector_score, hit.vector_score)
                        kept.bm25_score = max(kept.bm25_score, hit.bm25_score)

        use_score_fusion = getattr(cfg, "fusion", "rrf") == "score"
        for cid, hit in pool.items():
            hit.rrf = fused.get(cid, 0.0)
            hit.score = score_sum.get(cid, 0.0) if use_score_fusion else hit.rrf

        ranked = sorted(pool.values(), key=lambda h: (h.score, h.rrf), reverse=True)
        candidates = ranked[: max(k_final * 3, 12)]

        if cfg.use_mmr:
            qv = self.embedder.encode_one(query)
            candidates = self._mmr(np.array(qv), candidates, len(candidates), cfg.mmr_lambda)

        if cfg.use_rerank:
            pool = candidates[: cfg.rerank_pool]
            reranker = self._get_reranker()
            if reranker is not None and len(pool) > 1:
                scores = reranker.score(query, [h.text for h in pool])
                for hit, score in zip(pool, scores):
                    hit.rerank = float(score)
                    hit.score = hit.rerank
                pool.sort(key=lambda h: h.rerank, reverse=True)
                return pool[:k_final]

        return candidates[:k_final]
