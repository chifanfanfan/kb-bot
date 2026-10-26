"""用评测集给真实语料扫 chunk_size，而不是拍脑袋定 450。

    python tools/chunk_sweep.py 300 450 600 800

每个尺寸重建一次索引，只跑检索指标（不调模型），几十秒出结果。
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.eval import eval_retrieval, load_cases  # noqa: E402

PDF = Path(__file__).resolve().parent.parent / "data" / "毕业论文_脱敏.pdf"


def main() -> None:
    sizes = [int(x) for x in sys.argv[1:]] or [300, 450, 600, 800]
    cases = load_cases()
    print(f"语料：{PDF.name}｜评测集 {len(cases)} 条\n")
    print(f"{'chunk_size':>10}{'overlap':>9}{'块数':>6}{'hit@1':>8}{'hit@3':>8}{'MRR':>8}")
    print("-" * 51)

    kb = KnowledgeBase()
    for size in sizes:
        overlap = max(30, int(size * 0.15))
        kb.cfg.chunk = replace(kb.cfg.chunk, size=size, overlap=overlap)
        kb.store.reset()
        kb.build([PDF], verbose=False, ocr=False)
        kb.retriever.cfg = replace(kb.retriever.cfg, use_rerank=False, use_mmr=False)
        m = eval_retrieval(kb.retriever, cases)
        print(f"{size:>10}{overlap:>9}{kb.store.count():>6}"
              f"{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
