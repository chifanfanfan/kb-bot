"""A/B：小节内是否先按段落切分再打包。

    python tools/ab_paragraph.py

只跑检索指标，两套索引各建一次。
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.chunker import build_chunks  # noqa: E402
from kb.config import ChunkConfig, ROOT, RetrieveConfig  # noqa: E402
from kb.embedding import BGEEmbedding  # noqa: E402
from kb.eval import eval_retrieval, load_cases  # noqa: E402
from kb.pdf_loader import parse_pdf  # noqa: E402
from kb.retriever import HybridRetriever  # noqa: E402
from kb.store import VectorStore  # noqa: E402

PDF = ROOT / "data" / "毕业论文_脱敏.pdf"


def main() -> None:
    cases = load_cases()
    cfg = ChunkConfig()
    docs = parse_pdf(PDF)
    emb = BGEEmbedding()
    print(f"评测集 {len(cases)} 条\n")
    print(f"{'配置':<18}{'块数':>6}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}")
    print("-" * 54)

    for label, para in (("按长度打包", False), ("先按段落切", True)):
        chunks = build_chunks(docs.sections, cfg, "thesis", paragraph_first=para)
        store = VectorStore(ROOT / f"chroma_para_{int(para)}")
        store.reset()
        store.add(chunks, [v.tolist() for v in emb.encode([c.text for c in chunks])])
        r = HybridRetriever(
            store, emb, replace(RetrieveConfig(), use_mmr=False, use_rerank=False, use_multi_query=False)
        )
        r.refresh()
        m = eval_retrieval(r, cases)
        print(f"{label:<18}{len(chunks):>6}{m['hit@1']:>8.2f}{m['hit@3']:>8.2f}"
              f"{m['hit@5']:>8.2f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
