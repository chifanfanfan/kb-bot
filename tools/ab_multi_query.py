"""A/B：多查询改写能不能提升召回。

    python tools/ab_multi_query.py

只跑检索指标（不调生成模型），每条问题会额外调用一次改写。
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
    ("单查询（当前）", False, False),
    ("+ 多查询改写", True, False),
    ("多查询 + 重排", True, True),
]


def main() -> None:
    cases = load_cases()
    kb = KnowledgeBase()
    base = kb.retriever.cfg
    print(f"评测集 {len(cases)} 条\n")
    print(f"{'配置':<18}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}{'耗时':>10}")
    print("-" * 60)
    for name, multi, rerank in CONFIGS:
        kb.retriever.cfg = replace(base, use_multi_query=multi, use_rerank=rerank, use_mmr=False)
        t0 = time.perf_counter()
        m = eval_retrieval(kb.retriever, cases, llm=kb.llm if multi else None)
        dt = (time.perf_counter() - t0) / max(m["n"], 1) * 1000
        print(f"{name:<18}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['hit@5']:>8.2f}"
              f"{m['mrr']:>8.3f}{dt:>8.0f} ms")
    kb.retriever.cfg = base


if __name__ == "__main__":
    main()
