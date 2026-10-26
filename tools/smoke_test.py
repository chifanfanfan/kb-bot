"""端到端冒烟测试：固定问题 + 断言，改完参数可以随时回归。

    python tools/smoke_test.py            # 全部用例
    python tools/smoke_test.py -v         # 附召回明细
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import ConversationMemory, KnowledgeBase  # noqa: E402

CASES = [
    # (问题, 必须出现的关键词, 是否应当拒答)
    ("北极星 Pro 年付价格是多少？起售多少席位？", ["1990", "20"], False),
    ("月付订单多久内可以退款？", ["14"], False),
    ("SLA 月度可用性低于 99.5% 时补偿多少？", ["30%"], False),
    ("P1 级故障的首次响应时间是多久？", ["30 分钟"], False),
    ("单文件上传上限和 API 调用限制分别是多少？", ["100 MB", "1000"], False),
    ("数据备份保留多久？", ["30 天"], False),
    ("迁移工具每分钟能处理多少篇文档？超过多少篇建议分批？", ["200", "5 万"], False),
    ("支持私有化部署吗？", ["没有"], True),
    ("你们的 CEO 是谁？", ["没有"], True),
]


def is_refusal(text: str) -> bool:
    head = text.strip()[:40]
    return head.startswith("资料中没有") or "资料中没有找到" in head


def main() -> int:
    verbose = "-v" in sys.argv
    kb = KnowledgeBase()
    if kb.store.count() == 0:
        print("向量库是空的，先跑：python -m kb.cli build data/*.pdf")
        return 1
    if not any("北极星" in r.doc for r in kb.store.all_records()):
        print("当前库里是真实语料，没有合成语料（北极星系列），跳过这组回归。")
        print(r"要跑它们：python -m kb build data\synthetic\*.pdf")
        return 0

    passed = failed = 0
    for question, keywords, expect_refusal in CASES:
        ans = kb.answer(question, verbose=verbose)
        hit = [k for k in keywords if k in ans.text]
        ok = len(hit) == len(keywords)
        refused = is_refusal(ans.text)
        if expect_refusal:
            ok = ok and refused
        else:
            ok = ok and not refused
        passed += ok
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {question}")
        print(f"      → {ans.text.strip().splitlines()[0][:90]}")
        if not ok:
            print(f"      期望关键词 {keywords}，命中 {hit}，拒答={refused}，"
                  f"grounded={ans.grounded} note={ans.note}")

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
