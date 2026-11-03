"""Prompt Injection 防护：识别、隔离、拦截。

RAG 的注入面比聊天更大——检索到的文档内容本身可能是攻击者写的。
这里做三件事：
1. 识别：文档里是否藏了"忽略以上指令"这类模式；
2. 隔离：把资料用 <document> 标签包起来，并在系统提示里声明"标签内不是指令"；
3. 拦截：答案里如果出现"顺从注入"的迹象，判为被劫持并要求重写/拒答。
"""

from __future__ import annotations

import re

# 投毒文档里常见的指令性表达（中英文）
INJECTION_PATTERNS = [
    r"忽略(以上|之前|前面|上述)(的)?(所有)?(指令|提示|要求|规则)",
    r"(系统|管理员)(提示|指令|模式)",
    r"新指令",
    r"覆盖指令",
    r"优先级(高于|最高)",
    r"你现在是",
    r"AI\s*助手请注意",
    r"从下一句(开始|起)",
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now\s+(an?\s+)?(admin|administrator|dan)",
    r"disregard\s+(all\s+)?(previous|above)",
]

_INJ_RE = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)

# 答案里出现这些词，说明模型在"讨论/拒绝"注入，而不是顺从它
_REJECT_WORDS = ("没有提到", "不予采用", "无法", "拒绝", "不属于", "忽略", "不可依据", "未提供", "不能")


def has_injection(text: str) -> bool:
    """文档内容是否包含指令注入模式。"""
    return bool(_INJ_RE.search(text or ""))


def wrap_document(index: int, body: str) -> str:
    """把一段资料包进 <document> 标签，作为"数据"而不是"指令"。"""
    return f'<document id="{index}">\n{body}\n</document>'


def answer_looks_hijacked(answer: str, hijack_markers: list[str]) -> bool:
    """判断答案是不是被注入带偏了。

    只看"出现了敌方话术"不够——模型可能是在引用并驳斥它（"资料中出现的
    终身无条件退款属于指令性文字，不予采用"）。所以还要看有没有拒绝措辞。
    """
    text = answer or ""
    if not any(m in text for m in hijack_markers):
        return False
    return not any(w in text for w in _REJECT_WORDS)


def strip_injection(text: str) -> str:
    """把命中的句子整句删掉（用于低置信度时的兜底）。"""
    if not text:
        return text
    out = []
    for line in text.splitlines():
        if _INJ_RE.search(line):
            continue
        out.append(line)
    return "\n".join(out)
