"""多轮对话演示：看"追问改写"如何把省略的问题变成可检索的问句。

    python tools/memory_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import ConversationMemory, KnowledgeBase  # noqa: E402

QUESTIONS = [
    "北极星 Pro 默认支持多少并发会话？",
    "那 API 调用限制呢？",
    "年付的退款窗口是几天？",
    "如果我第 10 天申请退年付，能退吗？",
]


def main() -> None:
    kb = KnowledgeBase()
    memory = ConversationMemory(kb.llm, max_turns=2)  # 故意压小，触发滚动摘要

    for q in QUESTIONS:
        condensed = memory.condense(q)
        ans = kb.answer(q, memory=memory)
        print(f"\n用户：{q}")
        if condensed != q:
            print(f"改写：{condensed}")
        print(f"回答：{ans.text.strip()}")
        memory.add(q, ans.text)

    print("\n" + "=" * 50)
    print("滚动摘要：", memory.summary or "（尚未触发）")
    print("保留的最近轮次：", len(memory.turns))


if __name__ == "__main__":
    main()
