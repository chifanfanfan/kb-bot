"""A/B：换更大的中文 embedding 模型，召回能提升多少。

    python tools/ab_embedding.py

每个模型单独建一份索引（向量维度不同，不能混用集合），只跑检索指标，不调生成模型。
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
MODELS = ["bge-small-zh-v1.5", "bge-base-zh-v1.5"]


def main() -> None:
    cases = load_cases()
    cfg = ChunkConfig()
    docs = parse_pdf(PDF)
    chunks = build_chunks(docs.sections, cfg, "thesis")
    print(f"语料 {len(docs.sections)} 节 / {len(chunks)} 块｜评测集 {len(cases)} 条\n")
    print(f"{'模型':<22}{'维度':>6}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}{'编码':>10}")
    print("-" * 70)

    for name in MODELS:
        t0 = time.perf_counter()
        emb = BGEEmbedding(model_dir=ROOT / "models" / name)
        store = VectorStore(ROOT / f"chroma_{name}")
        store.reset()
        vectors = emb.encode([c.text for c in chunks])
        store.add(chunks, [v.tolist() for v in vectors])
        enc = time.perf_counter() - t0

        retriever = HybridRetriever(
            store, emb, replace(RetrieveConfig(), use_mmr=False, use_rerank=False, use_multi_query=False)
        )
        retriever.refresh()
        m = eval_retrieval(retriever, cases)
        print(f"{name:<22}{emb.dim:>6}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}"
              f"{m['hit@5']:>8.2f}{m['mrr']:>8.3f}{enc:>8.1f}s")


if __name__ == "__main__":
    main()
