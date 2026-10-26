"""冻结多轮对话里的改写结果，让评测可复现。

    python tools/freeze_rewrites.py          # 生成 eval/rewrites_frozen.json
    set KB_REWRITES=eval/rewrites_frozen.json
    python tools/eval_multi_turn.py          # 之后再跑就不调改写 LLM 了
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kb import KnowledgeBase  # noqa: E402
from kb import rewrite as rw  # noqa: E402

OUT = ROOT / "eval" / "rewrites_frozen.json"
CONV = ROOT / "eval" / "conversations.json"


def main() -> None:
    convs = json.loads(CONV.read_text("utf-8"))["conversations"]
    kb = KnowledgeBase()
    rw.load_frozen(str(OUT))
    rw._frozen_path = str(OUT)  # 让新产生的改写也写回文件

    n = 0
    for conv in convs:
        history = ""
        for turn in conv["turns"]:
            rw.rewrite(kb.llm, turn["q"], history)
            n += 1
            # 用真实答案推进历史，保证与评测时的历史一致
            ans = kb.answer(turn["q"])
            history += f"用户：{turn['q']}\n助手：{ans.text[:150]}\n"
            history = "\n".join(history.strip().splitlines()[-6:])

    count = rw.dump_frozen(str(OUT))
    print(f"处理 {n} 轮，冻结 {count} 条改写 → {OUT}")
    print(f"文件大小 {OUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
