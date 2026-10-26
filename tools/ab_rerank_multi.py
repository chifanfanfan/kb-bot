"""在 256 条 / 107 块的大基准上复评重排与多查询。

    python tools/ab_rerank_multi.py

这两项之前在小语料上被判"不划算"，语料变大后值得重测。
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import eval_retrieval, load_cases  # noqa: E402

CONFIGS = [
    ("基线（分数融合）", dict(use_rerank=False, use_multi_query=False)),
    ("+ 重排", dict(use_rerank=True, use_multi_query=False)),
    ("+ 多查询", dict(use_rerank=False, use_multi_query=True)),
    ("+ 两者", dict(use_rerank=True, use_multi_query=True)),
]


def main() -> None:
    cases = load_cases()
    kb = KnowledgeBase()
    base = replace(kb.retriever.cfg, use_mmr=False, fusion="score")
    print(f"评测集 {len(cases)} 条 | 库 {kb.store.count()} 块\n")
    print(f"{'配置':<18}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}{'单条耗时':>10}")
    print("-" * 61)
    for label, flags in CONFIGS:
        kb.retriever.cfg = replace(base, **flags)
        t = time.perf_counter()
        m = eval_retrieval(kb.retriever, cases, llm=kb.llm if flags.get("use_multi_query") else None)
        dt = (time.perf_counter() - t) / max(m["n"], 1) * 1000
        print(f"{label:<18}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['hit@5']:>8.2f}"
              f"{m['mrr']:>8.3f}{dt:>8.0f} ms")
    kb.retriever.cfg = base


if __name__ == "__main__":
    main()
