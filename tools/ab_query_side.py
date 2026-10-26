"""A/B：查询侧的两个小改动。

1. BGE 官方查询指令：检索时把查询编码成 "为这个句子生成表示以用于检索相关文章：<query>"
   （文档侧不加），bge-zh 系列论文里推荐的用法；
2. jieba 分词：BM25 现在是"单字 + 二元组"，换成词级分词有时更贴中文习惯。

    python tools/ab_query_side.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.config import ROOT, RetrieveConfig  # noqa: E402
from kb.embedding import BGEEmbedding  # noqa: E402
from kb.eval import eval_retrieval, load_cases  # noqa: E402
from kb.retriever import HybridRetriever  # noqa: E402
from kb.store import VectorStore  # noqa: E402

INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
MODEL = "bge-small-zh-v1.5"


def main() -> None:
    cases = load_cases()
    emb = BGEEmbedding()
    store = VectorStore(ROOT / f"chroma_{MODEL}")
    base = replace(RetrieveConfig(), use_mmr=False, use_rerank=False, use_multi_query=False)

    variants = [
        ("基线（单字+二元组）", base),
        ("+ 查询指令", replace(base, query_instruction=INSTRUCTION)),
    ]
    print(f"评测集 {len(cases)} 条｜模型 {MODEL}\n")
    print(f"{'配置':<22}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}")
    print("-" * 54)
    for label, cfg in variants:
        r = HybridRetriever(store, emb, cfg)
        r.refresh()
        m = eval_retrieval(r, cases)
        print(f"{label:<22}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['hit@5']:>8.2f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
