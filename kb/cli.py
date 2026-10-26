"""命令行入口。

    python -m kb build data/*.pdf     # 建库
    python -m kb ask "问题"            # 单轮提问
    python -m kb chat                 # 多轮对话（带记忆）
    python -m kb stats                # 看库里有多少块
    python -m kb reset                # 清空向量库
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config
from .memory import ConversationMemory
from .rag import KnowledgeBase


def _print_answer(ans, verbose: bool) -> None:
    print("\n" + ans.text.strip())
    if ans.note:
        print(f"\n  ⚠ {ans.note}")
    if ans.citations:
        print("\n  来源：")
        for c in ans.citations:
            print(f"   [{c['n']}] 《{c['doc']}》第 {c['page']}-{c['page_end']} 页 · {c['section']}")
            print(f"       {c['snippet'].replace(chr(10), ' ')}...")
    if verbose:
        print("\n  召回明细：")
        for h in ans.hits[:8]:
            print(f"   - {h.score:.4f} (vec {h.vector_score:.3f}, bm25 {h.bm25_score:.2f}) "
                  f"{h.doc} p{h.page} {h.section} | {h.text[:40]}...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb", description="PDF 知识库问答机器人")
    parser.add_argument("--verbose", action="store_true", help="打印召回明细")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="解析 PDF 并建索引")
    p_build.add_argument("pdfs", nargs="+", type=Path)

    p_ask = sub.add_parser("ask", help="单轮提问")
    p_ask.add_argument("question")

    p_chat = sub.add_parser("chat", help="多轮对话")

    sub.add_parser("stats", help="库统计")
    sub.add_parser("reset", help="清空索引")

    p_eval = sub.add_parser("eval", help="跑评测：检索消融 + 答案准确率")
    p_eval.add_argument("--answers", action="store_true", help="同时评测端到端答案（会调用模型，较慢）")
    p_eval.add_argument("--no-compare", action="store_true", help="跳过消融对比")

    args = parser.parse_args(argv)
    cfg = Config()

    if args.cmd == "eval":
        from .eval import run as run_eval

        run_eval(answers=args.answers, do_compare=not args.no_compare, verbose=args.verbose)
        return 0

    if args.cmd == "build":
        missing = [p for p in args.pdfs if not p.exists()]
        if missing:
            print(f"找不到文件：{missing}")
            return 1
        kb = KnowledgeBase(cfg)
        stats = kb.build(args.pdfs)
        print(f"\n完成：{stats['docs']} 篇 / {stats['sections']} 节 / "
              f"{stats['chunks']} 块（去重 {stats['skipped_dupes']} 块）")
        print(f"库内共 {kb.store.count()} 块")
        return 0

    kb = KnowledgeBase(cfg)

    if args.cmd == "stats":
        print(f"向量库：{kb.store.count()} 块")
        docs = {}
        for r in kb.store.all_records():
            docs[r.doc] = docs.get(r.doc, 0) + 1
        for name, n in docs.items():
            print(f"  {name}: {n} 块")
        return 0

    if args.cmd == "reset":
        kb.store.reset()
        print("已清空向量库")
        return 0

    if args.cmd == "ask":
        ans = kb.answer(args.question, verbose=args.verbose)
        _print_answer(ans, args.verbose)
        return 0

    if args.cmd == "chat":
        memory = ConversationMemory(kb.llm, max_turns=cfg.memory_turns)
        print("多轮问答已启动，输入 exit 退出。")
        while True:
            try:
                q = input("\n你 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() in {"exit", "quit", "q"}:
                break
            ans = kb.answer(q, memory=memory, verbose=args.verbose)
            _print_answer(ans, args.verbose)
            memory.add(q, ans.text)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
