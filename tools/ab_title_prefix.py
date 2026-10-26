"""A/B：编码时是否把小节标题拼进正文。

    python tools/ab_title_prefix.py

两套索引各建一次（同一 embedding 模型，只差标题前缀），只跑检索指标。
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.chunker import build_chunks  # noqa: E402
from kb.config import ChunkConfig, ROOT, RetrieveConfig  # noqa: E402
from kb.embedding import BGEEmbedding  # noqa: E402
from kb.eval import eval_retrieval, load_cases  # noqa: E402
from kb.pdf_loader import parse_pdf  # noqa: E402
from kb.retriever import HybridRetriever  # noqa: E402
from kb.store import VectorStore  # noqa: E402

PDF = ROOT / "data" / "毕业论文_脱敏.pdf"


def main() -> None:
    cases = load_cases()
    cfg = ChunkConfig()
    docs = parse_pdf(PDF)
    chunks = build_chunks(docs.sections, cfg, "thesis")
    emb = BGEEmbedding()
    print(f"语料 {len(chunks)} 块｜评测集 {len(cases)} 条｜模型 bge-small-zh\n")
    print(f"{'配置':<22}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}")
    print("-" * 54)

    for label, with_title in (("仅正文", False), ("标题 + 正文", True)):
        store = VectorStore(ROOT / f"chroma_title_{int(with_title)}")
        store.reset()
        texts = [f"{c.section}\n{c.text}" if with_title else c.text for c in chunks]
        store.add(chunks, [v.tolist() for v in emb.encode(texts)])
        retriever = HybridRetriever(
            store, emb, replace(RetrieveConfig(), use_mmr=False, use_rerank=False, use_multi_query=False)
        )
        retriever.refresh()
        m = eval_retrieval(retriever, cases)
        print(f"{label:<22}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['hit@5']:>8.2f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
