"""多轮评测：追问改写到底值不值。

    python tools/eval_multi_turn.py

对同一组对话跑两遍：
  A. 带记忆（condense 追问改写）
  B. 不带记忆（把原始问句直接丢给检索）
差异就是"指代消解"这部分的真实价值。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import ConversationMemory, KnowledgeBase  # noqa: E402
from kb.eval import _contains, is_refusal  # noqa: E402

CONV = Path(__file__).resolve().parent.parent / "eval" / "conversations.json"


def run(kb: KnowledgeBase, convs: list[dict], use_memory: bool) -> tuple[int, int, list[str]]:
    ok = total = 0
    fails: list[str] = []
    for conv in convs:
        memory = ConversationMemory(kb.llm, max_turns=6) if use_memory else None
        for turn in conv["turns"]:
            ans = kb.answer(turn["q"], memory=memory)
            refused = is_refusal(ans.text)
            missing = [k for k in turn["keywords"] if not _contains(ans.text, k)]
            good = not refused and not missing
            ok += good
            total += 1
            if not good:
                fails.append(f"[{conv['topic']}] {turn['q']} → {'拒答' if refused else '缺 ' + str(missing)}")
            if memory is not None:
                memory.add(turn["q"], ans.text)
    return ok, total, fails


def main() -> None:
    import os

    from kb import rewrite as rw

    frozen = os.environ.get("KB_REWRITES")
    if frozen:
        n = rw.load_frozen(frozen)
        print(f"已载入冻结改写 {n} 条（不调 LLM 改写，结果可复现）\n")

    convs = json.loads(CONV.read_text("utf-8"))["conversations"]
    kb = KnowledgeBase()
    print(f"{len(convs)} 组对话 / {sum(len(c['turns']) for c in convs)} 轮\n")

    for label, use_memory in (("A. 带记忆（改写）", True), ("B. 无记忆（原句）", False)):
        ok, total, fails = run(kb, convs, use_memory)
        print(f"{label}: {ok}/{total} = {ok / total:.0%}")
        for f in fails:
            print(f"   ✗ {f}")
        print()


if __name__ == "__main__":
    main()
