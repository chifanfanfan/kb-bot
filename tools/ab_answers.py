"""端到端 A/B：检索优化到底有没有转化成答案质量。

    python tools/ab_answers.py [--stride 2]

默认在评测集上取一半样本跑，控制耗时。
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace

sys.path.insert(0, __file__.rsplit("tools", 1)[0])

from kb import KnowledgeBase  # noqa: E402
from kb.eval import eval_answers, load_cases  # noqa: E402

CONFIGS = [
    ("仅重排", dict(use_rerank=True, use_multi_query=False)),
    ("重排 + 多查询", dict(use_rerank=True, use_multi_query=True)),
]


def main() -> None:
    stride = 2
    for i, arg in enumerate(sys.argv):
        if arg == "--stride" and i + 1 < len(sys.argv):
            stride = int(sys.argv[i + 1])

    cases = load_cases()[::stride]
    kb = KnowledgeBase()
    print(f"子集 {len(cases)} 条（stride={stride}）| 库 {kb.store.count()} 块\n")
    print(f"{'配置':<18}{'正确率':>8}{'拒答':>8}{'引用率':>8}{'延迟':>8}")
    print("-" * 50)
    for label, flags in CONFIGS:
        cfg = replace(kb.cfg.retrieve, fusion="score", use_mmr=False, **flags)
        kb.cfg.retrieve = cfg
        kb.retriever.cfg = cfg
        t = time.perf_counter()
        r = eval_answers(kb, cases)
        dt = (time.perf_counter() - t) / len(cases)
        print(f"{label:<18}{r['accuracy']:>8.1%}{r['refusal_ok']:>4}/{r['refusal_total']:<3}"
              f"{r['cited_rate']:>8.0%}{dt:>7.1f}s")


if __name__ == "__main__":
    main()
