"""两个降延迟实验。

A. 重排候选数：rerank_pool 8 → 4，质量掉多少、快多少
B. 条件式多查询：只在首轮置信度低时才扩写，省掉简单题的 LLM 调用

    python tools/ab_cost.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import _rank_of_gold, eval_retrieval, load_cases  # noqa: E402
from kb.expand import expand_queries  # noqa: E402

THRESHOLDS = (0.45, 0.50, 0.55, 0.60)


def experiment_a(kb, cases) -> None:
    print("A. 重排候选数（多查询保持开启）")
    print(f"{'pool':>6}{'hit@1':>8}{'hit@3':>8}{'MRR':>8}{'单条耗时':>10}")
    print("-" * 40)
    base = replace(kb.cfg.retrieve, use_mmr=False, use_rerank=True, use_multi_query=True)
    for pool in (4, 8):
        cfg = replace(base, rerank_pool=pool)
        kb.cfg.retrieve = cfg
        kb.retriever.cfg = cfg
        t = time.perf_counter()
        m = eval_retrieval(kb.retriever, cases, llm=kb.llm)
        dt = (time.perf_counter() - t) / max(m["n"], 1) * 1000
        print(f"{pool:>6}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['mrr']:>8.3f}{dt:>7.0f} ms")
    print()


def experiment_b(kb, cases) -> None:
    """先跑一遍不扩写，拿到每题首轮置信度；再只对低置信题扩写。"""
    plain = replace(kb.cfg.retrieve, use_mmr=False, use_rerank=True, use_multi_query=False)
    kb.cfg.retrieve = plain
    kb.retriever.cfg = plain

    conf: list[float] = []
    base_rank: list[int | None] = []
    for case in cases:
        if case.refusal or not case.gold:
            conf.append(0.0)
            base_rank.append(None)
            continue
        hits = kb.retriever.search(case.q, k=5)
        conf.append(max((h.vector_score for h in hits), default=0.0))
        base_rank.append(_rank_of_gold(hits, case.gold))

    n_answerable = sum(1 for c in cases if not c.refusal and c.gold)
    print("B. 条件式多查询（只在首轮置信度低于阈值时扩写）")
    print(f"{'阈值':>6}{'扩写题数':>10}{'hit@1':>8}{'hit@3':>8}{'MRR':>8}")
    print("-" * 42)

    # 预先把低置信题的扩写结果算好（expand_queries 内部有缓存）
    for th in THRESHOLDS:
        expanded_rank: dict[int, int | None] = {}
        calls = 0
        for i, case in enumerate(cases):
            if case.refusal or not case.gold or conf[i] >= th:
                continue
            calls += 1
            extra = expand_queries(kb.llm, case.q)
            hits = kb.retriever.search(case.q, k=5, extra_queries=extra)
            expanded_rank[i] = _rank_of_gold(hits, case.gold)

        hit1 = hit3 = 0
        mrr = 0.0
        for i, case in enumerate(cases):
            if case.refusal or not case.gold:
                continue
            rank = expanded_rank.get(i, base_rank[i])
            if rank:
                mrr += 1.0 / rank
                hit1 += rank <= 1
                hit3 += rank <= 3
        print(f"{th:>6.2f}{calls:>10}{hit1 / n_answerable:>8.2f}"
              f"{hit3 / n_answerable:>8.2f}{mrr / n_answerable:>8.3f}")
    print()


def main() -> None:
    cases = load_cases()
    kb = KnowledgeBase()
    print(f"评测集 {len(cases)} 条 | 库 {kb.store.count()} 块\n")
    experiment_a(kb, cases)
    experiment_b(kb, cases)


if __name__ == "__main__":
    main()
