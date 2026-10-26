"""一次调用同时产出「独立问句」和「检索变体」。

之前是两次 LLM：`memory.condense()` 把追问改成独立问句，`expand_queries()`
再把它扩成 3 条变体。两件事其实是一件事——都是"把用户的话翻译成检索用语"，
合并后每轮少一次网络往返（约 0.8 秒）。
"""

from __future__ import annotations

import json
import re

PROMPT = """你在帮检索系统理解用户的问题。给你一段对话历史和最新问题，请输出 JSON：

{{
  "standalone": "把最新问题改写成不依赖上下文、可独立检索的一句问句",
  "variants": ["变体1", "变体2", "变体3"]
}}

规则：
- standalone：补全代词和省略（它/这个/那…呢），用历史里出现过的具体名词替换；保留数字、时间、型号等限定；不要回答问题。
- variants：语义与原问题一致，但换用不同说法（同义词、更术语化、更接近文档用语的表述），每条不超过 30 字。
- 如果最新问题本身已经完整（不依赖上文），standalone **原样返回**，不要画蛇添足；variants 仍给 2~3 条同义改写。
- 只输出 JSON，不要解释。

【对话历史】
{history}

【最新问题】
{question}
"""

_cache: dict[str, tuple[str, list[str]]] = {}
# 冻结文件：把改写结果落到磁盘，评测时不再调 LLM，从而可复现、可对比。
_frozen: dict[str, tuple[str, list[str]]] = {}
_frozen_path: str = ""
_dirty = False


def load_frozen(path: str) -> int:
    """从 JSON 载入冻结的改写结果（键为 question|history 的哈希）。"""
    global _frozen_path, _frozen
    import os
    import json
    from hashlib import sha1

    if not path or not os.path.exists(path):
        _frozen_path = path or ""
        return 0
    raw = json.loads(open(path, encoding="utf-8").read())
    _frozen = {k: (v[0], v[1]) for k, v in raw.items()}
    _frozen_path = path
    return len(_frozen)


def _key(question: str, history: str, n: int) -> str:
    from hashlib import sha1

    return sha1(f"{question}|{history[-200:]}|{n}".encode()).hexdigest()[:16]


def dump_frozen(path: str) -> int:
    """把本次运行产生的改写结果写盘。"""
    import json

    data = {k: [v[0], v[1]] for k, v in _frozen.items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return len(data)


def rewrite(llm, question: str, history: str = "", n_variants: int = 3) -> tuple[str, list[str]]:
    """返回 (独立问句, 变体列表)。失败时退化为 (原问题, [])。"""
    key = f"{question}|{history[-200:] if history else ''}|{n_variants}"
    if key in _cache:
        return _cache[key]
    fkey = _key(question, history, n_variants)
    if fkey in _frozen:
        _cache[key] = _frozen[fkey]
        return _frozen[fkey]

    try:
        raw = llm.chat(PROMPT.format(history=history or "（无）", question=question),
                       "只输出 JSON。", max_tokens=400)
        text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        standalone = (data.get("standalone") or question).strip() or question
        variants = [v.strip() for v in data.get("variants", [])
                    if isinstance(v, str) and 3 <= len(v.strip()) <= 40 and v.strip() != standalone]
    except Exception:
        standalone, variants = question, []

    seen: set[str] = set()
    clean: list[str] = []
    for v in variants:
        if v not in seen and v != standalone:
            seen.add(v)
            clean.append(v)

    result = (standalone, clean[:n_variants])
    _cache[key] = result
    if _frozen_path:
        _frozen[fkey] = result
    return result
