"""评测：检索指标（hit@k / MRR）+ 答案指标（关键词 / 拒答）+ 消融对比。

没有评测的调参都是玄学——这个模块的作用就是把"感觉好多"变成一张表。

    python -m kb eval                  # 检索消融（不花 token，几秒）
    python -m kb eval --answers        # 端到端（调模型，几十秒）
    python -m kb eval --compare        # 两种都跑
"""

from __future__ import annotations

import json
import time
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

from .config import ROOT, Config
from .rag import KnowledgeBase
from .retriever import HybridRetriever

EVAL_FILE = ROOT / "eval" / "questions.json"


@dataclass
class Case:
    q: str
    gold: list[str]
    keywords: list[str]
    refusal: bool
    tag: str


def load_cases(path: Path | None = None) -> list[Case]:
    import os

    path = path or Path(os.environ.get("KB_EVAL_FILE", EVAL_FILE))
    raw = json.loads(path.read_text("utf-8"))
    return [
        Case(
            q=c["q"],
            gold=c.get("gold", []),
            keywords=c.get("keywords", []),
            refusal=bool(c.get("refusal")),
            tag=c.get("tag", ""),
        )
        for c in raw["cases"]
    ]


_PUNCT = " \t\n\r，。、；：？！,.;:?!\"'“”‘’（）()[]【】<>《》~`|/\\-_"


def _norm(text: str) -> str:
    """归一化：全角转半角、去标点与千分位、转小写。

    解决三类"看着一样但字符串不同"：
    - `1,990` / `1990`  （千分位）
    - `99.9%` / `99.9`  （百分号）
    - `ＴＬＳ` / `TLS`    （全角）
    """
    s = unicodedata.normalize("NFKC", text or "")
    s = "".join(ch for ch in s if ch not in _PUNCT)
    return s.lower()


def _squash(text: str) -> str:
    """保留旧名字，内部改成完整归一化。"""
    return _norm(text)


# 否定词：出现关键词前面 4 个字内，视为"没命中"（避免"不支持 X"被判成支持 X）
_NEGATIONS = ("不", "没", "无", "未", "非", "勿", "免", "不能", "无法", "并非", "不支持", "未提供")


def _negated(text: str, keyword: str) -> bool:
    """关键词虽然出现，但被否定了。"""
    t = _norm(text)
    k = _norm(keyword)
    if not k:
        return False
    idx = t.find(k)
    while idx != -1:
        window = t[max(0, idx - 4):idx]
        if not any(window.endswith(neg) or neg in window for neg in _NEGATIONS):
            return False  # 找到一处没被否定的命中
        idx = t.find(k, idx + 1)
    return True


def _contains(text: str, keyword: str) -> bool:
    if _norm(keyword) not in _norm(text):
        return False
    return not _negated(text, keyword)


def is_refusal(text: str) -> bool:
    head = text.strip()[:40]
    return head.startswith("资料中没有") or "资料中没有找到" in head


def _rank_of_gold(hits, gold: list[str]) -> int | None:
    """返回第一个命中 gold 小节的排名（1-based），没命中返回 None。"""
    for rank, hit in enumerate(hits, start=1):
        section = hit.section or ""
        if any(g == section or g in section or section in g for g in gold):
            return rank
    return None


# ---------------- 检索指标 ----------------
def eval_retrieval(retriever: HybridRetriever, cases: list[Case], k_max: int = 5, llm=None):
    rows = []
    hits_at = {1: 0, 3: 0, 5: 0}
    mrr = 0.0
    latencies = []
    n = 0

    for case in cases:
        if case.refusal or not case.gold:
            continue
        n += 1
        t0 = time.perf_counter()
        extra = []
        if getattr(retriever.cfg, "use_multi_query", False) and llm is not None:
            from .expand import expand_queries

            extra = expand_queries(llm, case.q)
        hits = retriever.search(case.q, k=k_max, extra_queries=extra)
        latencies.append((time.perf_counter() - t0) * 1000)

        rank = _rank_of_gold(hits, case.gold)
        rows.append({"q": case.q, "rank": rank, "tag": case.tag})
        if rank:
            mrr += 1.0 / rank
            for k in hits_at:
                if rank <= k:
                    hits_at[k] += 1

    if n == 0:
        return {"n": 0}

    return {
        "n": n,
        "hit@1": hits_at[1] / n,
        "hit@3": hits_at[3] / n,
        "hit@5": hits_at[5] / n,
        "mrr": mrr / n,
        "latency_ms": sum(latencies) / len(latencies),
        "rows": rows,
    }


# ---------------- 答案指标 ----------------
def eval_answers(kb: KnowledgeBase, cases: list[Case]):
    correct = 0
    refusal_ok = 0
    refusal_total = 0
    grounded = 0
    cited = 0
    answerable = 0
    latencies = []
    details = []

    for case in cases:
        t0 = time.perf_counter()
        ans = kb.answer(case.q)
        latencies.append((time.perf_counter() - t0) * 1000)
        refused = is_refusal(ans.text)

        if case.refusal:
            refusal_total += 1
            ok = refused
            refusal_ok += int(ok)
        else:
            answerable += 1
            missing = [k for k in case.keywords if not _contains(ans.text, k)]
            ok = (not refused) and not missing
            if answered := (not refused):
                cited += int(bool(ans.citations))
                grounded += int(ans.grounded)
            details.append({"q": case.q, "ok": ok, "refused": refused,
                            "missing": missing, "answer": ans.text[:80]})
        correct += int(ok)

    return {
        "n": len(cases),
        "correct": correct,
        "accuracy": correct / max(len(cases), 1),
        "refusal_ok": refusal_ok,
        "refusal_total": refusal_total,
        "answerable": answerable,
        "cited_rate": cited / max(answerable, 1),
        "grounded_rate": grounded / max(answerable, 1),
        "latency_ms": sum(latencies) / max(len(latencies), 1),
        "details": details,
    }


# ---------------- 消融对比 ----------------
VARIANTS = [
    ("纯向量", {"use_bm25": False, "use_mmr": False, "use_rerank": False}),
    ("+ BM25 (RRF)", {"use_bm25": True, "use_mmr": False, "use_rerank": False}),
    ("+ MMR", {"use_bm25": True, "use_mmr": True, "use_rerank": False}),
    ("+ 重排 (完整)", {"use_bm25": True, "use_mmr": True, "use_rerank": True}),
]


def compare(kb: KnowledgeBase, cases: list[Case]) -> list[dict]:
    base = kb.cfg.retrieve
    results = []
    for name, overrides in VARIANTS:
        kb.retriever.cfg = replace(base, **overrides)
        metrics = eval_retrieval(kb.retriever, cases)
        metrics["name"] = name
        results.append(metrics)
    kb.retriever.cfg = base
    return results


def _print_retrieval_table(results: list[dict]) -> None:
    print(f"{'配置':<16}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>8}{'耗时':>10}")
    print("-" * 58)
    for r in results:
        print(
            f"{r['name']:<16}{r['hit@1']:>8.2f}{r['hit@3']:>8.2f}"
            f"{r['hit@5']:>8.2f}{r['mrr']:>8.3f}{r['latency_ms']:>8.0f} ms"
        )
    print("-" * 58)
    print(f"样本 {results[0]['n']} 条（不含拒答类）")


def _print_misses(result: dict) -> None:
    missed = [r for r in result["rows"] if not r["rank"]]
    if missed:
        print("\n未命中：")
        for r in missed:
            print(f"  [{r['tag']}] {r['q']}")
    missed3 = [r for r in result["rows"] if r["rank"] and r["rank"] > 3]
    if missed3:
        print("\n命中但排在 3 名之后：")
        for r in missed3:
            print(f"  [{r['tag']}] rank={r['rank']}  {r['q']}")


def run(answers: bool = False, do_compare: bool = True, verbose: bool = False) -> None:
    cases = load_cases()
    print(f"评测集：{len(cases)} 条（可答 {sum(1 for c in cases if not c.refusal)}，"
          f"拒答 {sum(1 for c in cases if c.refusal)}）\n")

    kb = KnowledgeBase()
    if kb.store.count() == 0:
        print("向量库为空，先建库：python -m kb build data/*.pdf")
        return

    if do_compare:
        results = compare(kb, cases)
        _print_retrieval_table(results)
        if verbose:
            _print_misses(results[-1])

    if answers:
        print()
        r = eval_answers(kb, cases)
        print(f"答案正确率：{r['correct']}/{r['n']} = {r['accuracy']:.1%}")
        print(f"拒答正确：{r['refusal_ok']}/{r['refusal_total']}，"
              f"可答题中给出引用：{r['cited_rate']:.0%}，校验通过：{r['grounded_rate']:.0%}")
        print(f"平均端到端耗时：{r['latency_ms'] / 1000:.1f} s")
        bad = [d for d in r["details"] if not d["ok"]]
        if bad:
            print("\n答错的题：")
            for d in bad:
                reason = "误拒答" if d["refused"] else f"缺关键词 {d['missing']}"
                print(f"  - {d['q']}  → {reason}")
                print(f"    {d['answer']}")


if __name__ == "__main__":
    import sys

    run(answers="--answers" in sys.argv, do_compare="--no-compare" not in sys.argv,
        verbose="-v" in sys.argv)
