"""半自动生成评测集：模型出题 + 规则校验，人只做抽查。

为什么不让模型直接写"标准答案"：那等于让模型自己判卷。这里只让它出**问题**，
标注（gold 小节、关键词）由语料本身决定，校验规则是机械的：

1. 关键词必须逐字出现在该小节原文里 —— 保证"这题确实能从这段答出来"；
2. 关键词不能是"服务/数据/平台"这类泛词 —— 否则关键词判定形同虚设；
3. 问题去重（字符二元组 Jaccard > 0.8 视为重复）；
4. 拒答题单独生成，并且要求不得命中任何小节。

    python tools/gen_eval.py            # 生成并写入 eval/generated.json
    python tools/gen_eval.py --merge    # 再合并进 eval/questions.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "eval" / "generated.json"

GEN_SYSTEM = "你是 RAG 评测集的标注员，负责根据给定原文出题。只输出 JSON。"
GEN_PROMPT = """下面是一段文档原文。请出 {n} 个"只能靠这段回答"的问题。

要求：
1. 问题像真实用户会问的，可以改写措辞，但不要引入原文没有的专有名词；
2. 每个问题给 1~3 个"答案中必须出现的关键词"：必须是原文里逐字出现的**具体**词
   （数字、型号、百分比、动作短语），绝不能用"服务""数据""平台""系统"这类泛词；
3. 不要问"这段讲了什么"这种开放式问题，不要出现"根据原文"之类的话；
4. 问题之间不要重复；
5. 输出 JSON 数组，每项形如 {{"q": "...", "keywords": ["..."], "tag": "numeric|paraphrase|multi-hop"}}

【原文】
{text}
"""

ABSENT_SYSTEM = "你是 RAG 评测集标注员。只输出 JSON。"
ABSENT_PROMPT = """围绕"北极星"这个虚构的 SaaS 产品，写 {n} 个**文档里没有答案**的问题。

要求：
1. 问题要具体、像真实用户会问的，例如价格折扣、竞品对比、团队规模、融资情况；
2. 不要问这个语料里已经写到的主题（价格、退款、SLA、加密、备份、限流、迁移、故障分级）；
3. 输出 JSON 数组：[{{"q": "..."}}]
"""

GENERIC = {"服务", "数据", "平台", "系统", "客户", "用户", "支持", "提供", "可以", "需要", "进行"}
# 目录页出不了有价值的问题；封面/声明这类也无意义
SKIP_SECTIONS = {"目录", "正文"}


def _norm(q: str) -> str:
    return re.sub(r"\s+", "", q)


def _bigrams(q: str) -> set[str]:
    s = _norm(q)
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _jaccard(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    return len(A & B) / max(len(A | B), 1)


def _valid_keywords(keywords: list[str], text: str) -> bool:
    if not keywords or len(keywords) > 3:
        return False
    for k in keywords:
        k = k.strip()
        if len(k) < 2 or k in GENERIC:
            return False
        if k not in text:
            return False
        # "Java-based asynchronous concurrent processing mechanism" 这种整句英文
        # 作为关键词没有判定意义；"Spring Boot"/"Element Plus" 这类两词术语要保留
        if k.count(" ") >= 2 or len(k) > 20:
            return False
    return True


def main() -> None:
    merge = "--merge" in sys.argv
    limit = 0
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    kb = KnowledgeBase()

    # 按小节聚合（同一小节可能被切成多个块）
    sections: dict[tuple[str, str], list[str]] = {}
    for rec in kb.store.all_records():
        sections.setdefault((rec.doc, rec.section), []).append(rec.parent_text)

    print(f"共 {len(sections)} 个小节，开始出题...")
    cases: list[dict] = []
    seen: list[str] = []
    rejected = 0
    done = 0

    for (doc, section), texts in sections.items():
        if limit and done >= limit:
            break
        if section in SKIP_SECTIONS:
            continue
        text = max(texts, key=len)
        if len(text) < 100:
            continue
        done += 1
        try:
            raw = kb.llm.json_chat(GEN_SYSTEM, GEN_PROMPT.format(n=3, text=text), fallback=[])
        except Exception as exc:
            print(f"  [warn] {section}: {exc}")
            continue
        items = raw if isinstance(raw, list) else raw.get("items", [])
        for item in items:
            q = (item.get("q") or "").strip()
            kws = [str(k).strip() for k in (item.get("keywords") or [])]
            if not (6 <= len(q) <= 60):
                rejected += 1
                continue
            if not _valid_keywords(kws, text):
                rejected += 1
                continue
            if any(_jaccard(q, prev) > 0.8 for prev in seen):
                rejected += 1
                continue
            seen.append(q)
            cases.append({
                "q": q, "gold": [section], "keywords": kws,
                "refusal": False, "tag": item.get("tag", "auto"),
                "doc": doc, "source": "auto",
            })

    # 拒答题
    try:
        absent = kb.llm.json_chat(ABSENT_SYSTEM, ABSENT_PROMPT.format(n=12), fallback=[])
        items = absent if isinstance(absent, list) else absent.get("items", [])
        for item in items:
            q = (item.get("q") or "").strip()
            if 6 <= len(q) <= 60 and not any(_jaccard(q, prev) > 0.8 for prev in seen):
                seen.append(q)
                cases.append({"q": q, "gold": [], "keywords": [], "refusal": True,
                              "tag": "absent", "doc": "", "source": "auto"})
    except Exception as exc:
        print(f"  [warn] 拒答题生成失败: {exc}")

    OUT.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), "utf-8")
    print(f"生成 {len(cases)} 条（可答 {sum(1 for c in cases if not c['refusal'])}，"
          f"拒答 {sum(1 for c in cases if c['refusal'])}），规则拒绝 {rejected} 条")
    print(f"写入 {OUT}")

    if merge:
        main_file = OUT.parent / "questions.json"
        data = json.loads(main_file.read_text("utf-8"))
        existing = [c for c in data["cases"] if c.get("source") != "auto"]
        merged = existing + cases
        main_file.write_text(json.dumps({"cases": merged}, ensure_ascii=False, indent=2), "utf-8")
        print(f"已合并：人工 {len(existing)} + 自动 {len(cases)} = {len(merged)} 条 → {main_file}")


if __name__ == "__main__":
    main()
