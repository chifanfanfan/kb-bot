"""5 分钟演示：一次跑完"生僻数值 / 表格字段 / 该拒答"三类问题。

    python tools/demo.py

不需要预先建库——没有索引时会自动用 data/synthetic 里的语料建一个。
"""

from __future__ import annotations

import time
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import is_refusal  # noqa: E402

DEMO = [
    ("数值型", "北极星 Pro 年付多少钱？退款窗口几天？"),
    ("表格型", "users 表的主键是什么类型？posts 表里哪个字段存审核状态？"),
    ("该拒答", "支持私有化部署吗？"),
]

THESIS = ROOT / "data" / "毕业论文_脱敏.pdf"
SYNTHETIC = ROOT / "data" / "synthetic"


def _corpus() -> list[Path]:
    """优先用真实论文；没有的话退回仓库自带的 5 份合成文档。"""
    if THESIS.exists():
        return [THESIS]
    return sorted(SYNTHETIC.glob("*.pdf"))


def ensure_index(kb: KnowledgeBase) -> None:
    if kb.store.count() > 0:
        return
    files = _corpus()
    if not files:
        raise SystemExit("没有语料：把 PDF 放进 data/，或运行 tools/make_sample_pdf.py")
    print(f"索引为空，正在用 {len(files)} 份文档建库（首次约 30 秒）...\n")
    kb.build(files)


def main() -> None:
    kb = KnowledgeBase()
    ensure_index(kb)

    for kind, q in DEMO:
        t0 = time.perf_counter()
        ans = kb.answer(q)
        dt = time.perf_counter() - t0
        print(f"【{kind}】{q}   ({dt:.1f}s)")
        print(f"  → {ans.text.strip().splitlines()[0][:110]}")
        if ans.citations:
            c = ans.citations[0]
            print(f"  ← 《{c['doc']}》p{c['page']}·{c['section']}")
        if is_refusal(ans.text):
            print("  ← 正确拒答（资料中没有）")
        print()

    print(f"库内 {kb.store.count()} 块")


if __name__ == "__main__":
    main()
