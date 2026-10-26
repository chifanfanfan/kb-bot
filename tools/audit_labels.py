"""标注审计：把每条题的答案和判定结果落盘，便于人工核对标签是否写错。

    python tools/audit_labels.py            # 全量
    python tools/audit_labels.py --only-fail

输出 eval/audit.json，每条包含 问题/关键词/答案/判定/是否拒答。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import _contains, is_refusal, load_cases  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "eval" / "audit.json"


def main() -> None:
    only_fail = "--only-fail" in sys.argv
    kb = KnowledgeBase()
    cases = load_cases()
    rows = []
    for i, case in enumerate(cases, 1):
        ans = kb.answer(case.q)
        refused = is_refusal(ans.text)
        missing = [] if case.refusal else [k for k in case.keywords if not _contains(ans.text, k)]
        ok = (refused if case.refusal else (not refused and not missing))
        rows.append({
            "q": case.q, "gold": case.gold, "keywords": case.keywords,
            "refusal": case.refusal, "tag": case.tag,
            "ok": ok, "refused": refused, "missing": missing,
            "answer": ans.text.strip(),
        })
        if i % 20 == 0:
            print(f"  {i}/{len(cases)}")

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
    fails = [r for r in rows if not r["ok"]]
    print(f"\n总 {len(rows)} 条，失败 {len(fails)} 条 → {OUT}\n")
    for r in fails:
        if only_fail:
            print(f"[{r['tag']}] {r['q']}")
            print(f"   kw={r['keywords']} missing={r['missing']} refused={r['refused']}")
            print(f"   ans={r['answer'][:120].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
