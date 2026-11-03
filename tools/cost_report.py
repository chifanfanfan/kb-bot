"""成本报表：从 cache/usage.jsonl 统计 token 消耗与费用。

    python tools/cost_report.py

注意：单价写死在下面，可能随官方调价变化，用之前去官网核对一眼。
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "cache" / "usage.jsonl"
ANSWERS = ROOT / "cache" / "answers.jsonl"

# DeepSeek 官方价（元 / 百万 token），2026-11 抓的价格，调价请自行更新
PRICE_IN_MISS = 2.0     # 输入，未命中缓存
PRICE_IN_HIT = 0.5      # 输入，命中上下文缓存（这里按 miss 保守估）
PRICE_OUT = 8.0         # 输出


def main() -> None:
    if not USAGE.exists():
        print(f"没有记录：{USAGE}")
        print("先跑几次问答（web / cli / 评测），再来生成报表。")
        return

    rows = []
    for line in USAGE.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not rows:
        print("usage.jsonl 是空的")
        return

    calls = len(rows)
    pt = sum(r.get("prompt", 0) for r in rows)
    ct = sum(r.get("completion", 0) for r in rows)

    cost = pt / 1e6 * PRICE_IN_MISS + ct / 1e6 * PRICE_OUT
    per_call = cost / calls
    per_q_pt = pt / calls
    per_q_ct = ct / calls

    p50 = statistics.median(r.get("prompt", 0) for r in rows)
    p95 = sorted(r.get("prompt", 0) for r in rows)[max(0, int(calls * 0.95) - 1)]

    print("=" * 46)
    print(" token 成本报表")
    print("=" * 46)
    print(f" 调用次数        {calls}")
    print(f" 输入 token      {pt:,}   （均值 {per_q_pt:,.0f} / p50 {p50:,.0f} / p95 {p95:,.0f}）")
    print(f" 输出 token      {ct:,}   （均值 {per_q_ct:,.0f}）")
    print(f" 总费用          ¥{cost:.4f}")
    print(f" 单次调用        ¥{per_call:.4f}")
    print(f" 折算单次问答    ¥{per_call * 2.2:.4f}  （按平均 2.2 次 LLM 调用算）")

    # 缓存
    hits = 0
    entries = 0
    if ANSWERS.exists():
        try:
            data = json.loads(ANSWERS.read_text("utf-8"))
            entries = len(data)
            hits = sum(v.get("hits", 0) for v in data.values())
        except json.JSONDecodeError:
            pass
    total_req = calls + hits
    rate = hits / total_req if total_req else 0
    saved = hits * per_call * 2.2
    print("-" * 46)
    print(f" 缓存条目        {entries}")
    print(f" 缓存命中        {hits} 次  （命中率 {rate:.0%}）")
    print(f" 缓存省下        ¥{saved:.4f}")
    print("=" * 46)


if __name__ == "__main__":
    main()
