"""快检：分块的边界行为。不依赖模型和网络。"""

from __future__ import annotations

from kb.chunker import build_chunks, pack_sentences, split_sentences
from kb.config import ChunkConfig
from kb.pdf_loader import Section


def test_split_sentences_keeps_short_fragments():
    parts = split_sentences("第一句话。第二句！第三句？")
    assert parts == ["第一句话。", "第二句！", "第三句？"]


def test_pack_respects_size_and_never_cuts_mid_sentence():
    text = "。".join(["这是一个测试句子" * 3]) + "。"
    pieces = pack_sentences(split_sentences(text), size=50, overlap=10)
    assert pieces
    for p in pieces:
        # 允许多一点点（句子边界会对齐），但不能近乎翻倍
        assert len(p) <= 70


def test_pack_overlap_starts_at_sentence_boundary():
    sentences = [f"第{i}句话内容比较长一些用于测试。" for i in range(1, 12)]
    pieces = pack_sentences(sentences, size=60, overlap=20)
    assert len(pieces) > 1
    # 第二块开头应该是完整句子，而不是半个字
    assert pieces[1].startswith("第")


def test_build_chunks_drops_fragments_but_keeps_small_sections():
    cfg = ChunkConfig(size=200, overlap=30, min_chunk=80)
    small = Section("d.pdf", "1.1 小节", 1, 1, "这一节虽然很短，但内容完整，仍然应该被保留下来，而不是像碎片一样被丢弃掉。")
    big = Section("d.pdf", "1.2 小节", 2, 2, "。".join(["完整句子内容" * 4] * 6) + "。")
    chunks = build_chunks([small, big], cfg, "doc")
    assert any(c.section == "1.1 小节" for c in chunks), "整节不该因为短而被丢掉"
    assert len(chunks) >= 2
    assert all(c.parent_text for c in chunks)


def test_paragraph_first_splits_on_blank_line():
    cfg = ChunkConfig(size=400, overlap=40)
    text = "第一段讲发帖流程。" * 8 + "\n\n" + "第二段讲评论流程。" * 8
    section = Section("d.pdf", "3.3 流程", 1, 1, text)
    chunks = build_chunks([section], cfg, "doc", paragraph_first=True)
    assert len(chunks) == 2, "两段应当各自成块"
    assert chunks[0].parent_id == chunks[1].parent_id  # 同节，父块一致
