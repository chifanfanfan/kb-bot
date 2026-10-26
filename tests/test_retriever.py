"""快检：融合排序与评测工具函数。用假 embedder，不加载模型。"""

from __future__ import annotations

import numpy as np
import pytest

from kb.chunker import Chunk
from kb.config import RetrieveConfig
from kb.eval import Case, _contains, _rank_of_gold, is_refusal
from kb.retriever import HybridRetriever
from kb.store import VectorStore


class FakeEmbedder:
    """把文本映射成固定向量：含"退款"的偏第一维，含"加密"的偏第二维。"""

    dim = 2

    def encode(self, texts):
        out = []
        for t in texts:
            vec = np.array([1.0 if "退款" in t else 0.0, 1.0 if "加密" in t else 0.0])
            norm = np.linalg.norm(vec) or 1.0
            out.append(vec / norm)
        return np.vstack(out)

    def encode_one(self, text):
        return self.encode([text])[0].tolist()


def _chunk(cid: str, text: str, section: str) -> Chunk:
    return Chunk(cid, text, "d.pdf", section, 1, 1, 0, f"d:{section}", text)


@pytest.fixture()
def retriever(tmp_path):
    store = VectorStore(tmp_path / "chroma")
    chunks = [
        _chunk("a", "北极星 Pro 退款政策：14 天内无理由退款", "1.3 退款"),
        _chunk("b", "数据加密采用 AES-256", "1.6 安全"),
        _chunk("c", "年付价格为 1990 元", "1.2 定价"),
    ]
    emb = FakeEmbedder()
    store.add(chunks, emb.encode([c.text for c in chunks]).tolist())
    r = HybridRetriever(store, emb, RetrieveConfig(use_mmr=False, use_rerank=False, use_multi_query=False))
    r.refresh()
    return r


def test_hybrid_finds_keyword_hit(retriever):
    hits = retriever.search("退款多久？", k=2)
    assert hits and hits[0].section == "1.3 退款"


def test_score_fusion_prefers_strong_bm25(retriever):
    """向量判无关、BM25 极高分时，分数融合应把它排上来。"""
    hits = retriever.search("AES-256", k=3)
    assert hits[0].section == "1.6 安全"


def test_rank_of_gold():
    class H:
        def __init__(self, section):
            self.section = section

    hits = [H("1.1"), H("1.3 退款"), H("1.2")]
    assert _rank_of_gold(hits, ["1.3 退款"]) == 2
    assert _rank_of_gold(hits, ["9.9"]) is None


def test_contains_ignores_whitespace():
    assert _contains("年付价格为 1990 元/席位/年", "1990")
    assert _contains("十天之内", "十天")
    assert not _contains("资料中没有提到", "退款")


def test_is_refusal():
    assert is_refusal("资料中没有找到相关内容，无法回答。")
    assert is_refusal("资料中没有提到 CEO 相关信息。")
    assert not is_refusal("年付价格为 1990 元。")


def test_case_dataclass_defaults():
    c = Case(q="问题", gold=[], keywords=[], refusal=True, tag="absent")
    assert c.refusal and c.gold == []
