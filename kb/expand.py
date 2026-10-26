"""多查询改写：把一个问题扩成几个"检索视角"，分别召回后融合。

真实文档里，用户的措辞和原文往往对不上——问"审核怎么做的"，原文写的是
"审核流水线设计"。单条查询容易漏，扩成 3 条能覆盖同义词、上位词和
"问题→文档用语"的转换。

代价是一次额外的 LLM 调用（约 1 秒），所以默认关闭，由评测决定开不开。
"""

from __future__ import annotations

import json
import re

PROMPT = """把用户的问题改写成 {n} 个用于检索的问句。

要求：
1. 语义必须与原问题一致，不要扩展成新的问题；
2. 分别从不同角度改写：同义说法、更书面/更术语化的说法、把口语换成文档常用表述；
3. 每条不超过 30 字，不要编号，不要解释；
4. 输出 JSON 数组，例如 ["...", "...", "..."]

【问题】{q}
"""

_cache: dict[str, list[str]] = {}


def expand_queries(llm, question: str, n: int = 3) -> list[str]:
    key = f"{question}|{n}"
    if key in _cache:
        return _cache[key]
    try:
        raw = llm.chat(PROMPT.format(n=n, q=question), "只输出 JSON 数组。", max_tokens=300)
        text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        items = json.loads(text)
        queries = [q.strip() for q in items if isinstance(q, str) and 3 <= len(q.strip()) <= 40]
    except Exception:
        queries = []
    # 去重、去空、去掉与原句相同的
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        if q not in seen and q != question:
            seen.add(q)
            out.append(q)
    _cache[key] = out
    return out
