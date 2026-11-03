"""快检：答案缓存的命中、失效与归一化。"""

from __future__ import annotations

from kb.cache import AnswerCache, normalize


def test_normalize_ignores_space_and_punct():
    assert normalize("Users 表的主键是什么？") == normalize("users表的主键是什么")
    assert normalize("退款！多久？") == normalize("退款 多久")


def test_miss_then_hit(tmp_path):
    c = AnswerCache(tmp_path / "a.jsonl")
    assert c.get("退款多久", "v1") is None
    assert c.misses == 1

    c.put("退款多久", "v1", {"text": "7 天", "citations": [], "grounded": True, "note": ""})
    got = c.get("退款多久", "v1")
    assert got and got["text"] == "7 天"
    assert c.hits == 1


def test_doc_version_invalidates(tmp_path):
    c = AnswerCache(tmp_path / "a.jsonl")
    c.put("退款多久", "v1", {"text": "7 天"})
    assert c.get("退款多久", "v1") is not None
    assert c.get("退款多久", "v2") is None, "文档版本变了必须失效"


def test_persisted_across_instances(tmp_path):
    path = tmp_path / "a.jsonl"
    c1 = AnswerCache(path)
    c1.put("q", "v", {"text": "A"})
    c2 = AnswerCache(path)
    assert c2.get("q", "v")["text"] == "A"


def test_hit_rate(tmp_path):
    c = AnswerCache(tmp_path / "a.jsonl")
    c.put("q", "v", {"text": "A"})
    c.get("q", "v")
    c.get("other", "v")
    assert c.hit_rate == 0.5
