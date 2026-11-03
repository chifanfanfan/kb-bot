"""对比新旧判定规则：同一批答案，两种判法，看哪些题判定翻转。

    python tools/audit_judge.py            # 默认跑 1/4 子集（64 条）
    python tools/audit_judge.py --all      # 全量 255 条（约 15 分钟）

输出：
- 旧判法（只去空格）判对/判错
- 新判法（归一化 + 否定词）判对/判错
- 翻转的题：旧对新的、旧错新的
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import _contains, _norm, is_refusal, load_cases  # noqa: E402


def old_contains(text: str, keyword: str) -> bool:
    """旧实现：只去空白。"""
    return "".join(keyword.split()) in "".join(text.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    cases = load_cases()
    if not args.all:
        cases = cases[::4]
    print(f"用例 {len(cases)} 条")

    kb = KnowledgeBase()
    if getattr(kb, "_cache", None) is not None:
        kb._cache = None  # 关缓存，保证测的是新答案
    print("缓存已关闭\n")

    flips: list[tuple[str, bool, bool, list[str], str]] = []
    old_ok = new_ok = 0
    for i, case in enumerate(cases, 1):
        ans = kb.answer(case.q)
        if case.refusal:
            ok = is_refusal(ans.text)
            old_ok += ok
            new_ok += ok
            continue
        miss_old = [k for k in case.keywords if not old_contains(ans.text, k)]
        miss_new = [k for k in case.keywords if not _contains(ans.text, k)]
        ok_old = not is_refusal(ans.text) and not miss_old
        ok_new = not is_refusal(ans.text) and not miss_new
        old_ok += ok_old
        new_ok += ok_new
        if ok_old != ok_new:
            flips.append((case.q, ok_old, ok_new, case.keywords, ans.text[:110]))
        if i % 10 == 0:
            print(f"  进度 {i}/{len(cases)}", flush=True)

    total = len(cases)
    print("\n" + "=" * 52)
    print(f"旧判法：{old_ok}/{total} = {old_ok/total:.1%}")
    print(f"新判法：{new_ok}/{total} = {new_ok/total:.1%}")
    print(f"翻转：{len(flips)} 条")
    print("=" * 52)

    for q, o, n, kws, text in flips:
        arrow = "旧对→新错" if o else "旧错→新对"
        print(f"\n[{arrow}] {q}")
        print(f"  关键词：{kws}")
        print(f"  答案：{text}")


if __name__ == "__main__":
    main()
