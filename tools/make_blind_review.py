"""生成盲评包：抽 30 条，把"问题 + 期望要点 + 系统答案"给人独立判对错。

    python tools/make_blind_review.py --n 30

产出两个文件：
- eval/blind_review.md      给评审人：只有问题和答案，没有系统判定，也没有标准答案原文
- eval/blind_review_key.md  给你自己：编号 → 用例，用于事后对答案

为什么要这么做：关键词判定只能证明"包含某些字"，证明不了"答得对"。
让不知道系统判定的人独立打分，才能算出判定规则的可靠度。
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import is_refusal, load_cases  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval"
SEED = 20261103


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    args = ap.parse_args()

    cases = load_cases()
    random.seed(SEED)
    sample = random.sample(cases, min(args.n, len(cases)))
    print(f"抽取 {len(sample)} 条（seed={SEED}）")

    kb = KnowledgeBase()
    if getattr(kb, "_cache", None) is not None:
        kb._cache = None

    lines = [
        "# 盲评问卷（30 条）",
        "",
        "请对每条回答判断：**答对了 / 答错了 / 该拒答但没拒答**。",
        "判断标准：回答是否包含问题所问的关键事实（数字、条款、字段、结论）。",
        "不要参考任何系统评分，按你自己的判断填。",
        "",
        "| # | 问题 | 系统回答 | 你的判定 |",
        "|---|---|---|---|",
    ]
    key = ["# 评分对照表（内部）", "", "| # | 问题 | 期望关键词 | 类型 |", "|---|---|---|---|"]

    for i, case in enumerate(sample, 1):
        ans = kb.answer(case.q)
        text = ans.text.replace("\n", " ").replace("|", "\\|")[:220]
        lines.append(f"| {i} | {case.q} | {text} |  |")
        kind = "该拒答" if case.refusal else "可答"
        kws = "、".join(case.keywords) if case.keywords else "-"
        key.append(f"| {i} | {case.q} | {kws} | {kind} |")
        if is_refusal(ans.text):
            print(f"  {i:2d}. [拒答] {case.q[:26]}")
        if i % 10 == 0:
            print(f"  进度 {i}/{len(sample)}", flush=True)

    OUT.mkdir(exist_ok=True)
    (OUT / "blind_review.md").write_text("\n".join(lines) + "\n", "utf-8")
    (OUT / "blind_review_key.md").write_text("\n".join(key) + "\n", "utf-8")
    print(f"\n已生成：{OUT / 'blind_review.md'}")
    print(f"已生成：{OUT / 'blind_review_key.md'}")


if __name__ == "__main__":
    main()
