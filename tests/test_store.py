"""快检：向量库的写入、查询与失效重连。用临时目录，不碰真实库。"""

from __future__ import annotations

import pytest

from kb.chunker import Chunk
from kb.store import VectorStore


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        id=cid, text=text, doc="d.pdf", section="1.1 测试", page=1, page_end=1,
        index=0, parent_id="d:s0", parent_text=text,
    )


@pytest.fixture()
def store(tmp_path):
    return VectorStore(tmp_path / "chroma")


def test_add_and_count(store):
    store.add([_chunk("a", "退款政策"), _chunk("b", "加密方式")], [[1.0, 0.0], [0.0, 1.0]])
    assert store.count() == 2
    recs = store.all_records()
    assert {r.id for r in recs} == {"a", "b"}
    assert all(r.parent_text for r in recs)


def test_query_returns_nearest(store):
    store.add([_chunk("a", "退款政策"), _chunk("b", "加密方式")], [[1.0, 0.0], [0.0, 1.0]])
    res = store.query([1.0, 0.0], k=1)
    assert res["ids"][0][0] == "a"


def test_reset_clears(store):
    store.add([_chunk("a", "x")], [[1.0, 0.0]])
    store.reset()
    assert store.count() == 0


def test_reconnect_after_external_reset(store, tmp_path):
    """模拟另一个进程把集合删掉：句柄失效后应自动重连，而不是抛错。"""
    store.add([_chunk("a", "x")], [[1.0, 0.0]])
    store.client.delete_collection("kb_chunks")
    assert store.count() == 0  # 不抛异常，且看到的是新集合
