"""长对话测试：滚动摘要（memory.summary）在 >6 轮时才触发，此前从未被覆盖。

    python tools/eval_long_conversation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import ConversationMemory, KnowledgeBase  # noqa: E402
from kb.eval import _contains, is_refusal  # noqa: E402

TURNS = [
    ("北极星 Pro 年付多少钱？", ["1990"]),
    ("那月付呢？", ["199"]),
    ("退款窗口是多久？", ["7 天"]),
    ("P1 级故障多久响应？", ["30 分钟"]),
    ("那 P2 呢？", ["2 小时"]),
    ("数据在传输和存储时怎么加密？", ["TLS 1.3", "AES-256"]),
    ("备份保留多久？", ["30 天"]),
    ("注销账号之后数据多久清除？", ["7 天"]),
    ("开放 API 的限流是多少？", ["1000"]),
    ("超了返回什么状态码？", ["429"]),
]


def main() -> None:
    kb = KnowledgeBase()
    memory = ConversationMemory(kb.llm, max_turns=6)
    ok = 0

    for i, (q, keywords) in enumerate(TURNS, 1):
        ans = kb.answer(q, memory=memory)
        refused = is_refusal(ans.text)
        missing = [k for k in keywords if not _contains(ans.text, k)]
        good = not refused and not missing
        ok += good
        compacted = "已压缩" if memory.summary else "未压缩"
        print(f"{i:2d}. [{'PASS' if good else 'FAIL'}] {q}")
        if not good:
            print(f"      → {'拒答' if refused else '缺 ' + str(missing)}: {ans.text.strip()[:80]}")
        print(f"      轮次缓存={len(memory.turns)} 摘要={compacted}")
        memory.add(q, ans.text)

    print(f"\n正确率 {ok}/{len(TURNS)}")
    print(f"滚动摘要({len(memory.summary)} 字): {memory.summary[:200] if memory.summary else '（空）'}")
    print(f"最近保留轮次: {len(memory.turns)}")


if __name__ == "__main__":
    main()
