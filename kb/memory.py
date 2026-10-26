"""对话记忆：最近 N 轮原文 + 更早内容的滚动摘要 + 追问改写。

只存原文会越聊越贵，只存摘要会丢细节，所以两段式：
- 最近 memory_turns 轮原样保留（保证指代、数字不丢）；
- 更早的轮次压缩成一段摘要，随对话滚动更新。
另外，多轮 RAG 的关键不是"记住"，而是把"它多少钱？"改写成
"北极星 Pro 的订阅价格是多少？"，否则检索一定跑偏。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .llm import LLM

# 出现这些信号才值得改写：代词、指示词、"那…呢"这类省略
FOLLOWUP = re.compile(r"[它他她]|这(个|些|里|样|边)|那(个|些|里|样|么)|该(系统|模块|字段|表)|上述|前面|刚才|呢[？?]?$")


def needs_condense(question: str) -> bool:
    """自包含的问题不需要改写——改写了反而可能把问题带偏。"""
    return bool(FOLLOWUP.search(question.strip()))

CONDENSE_PROMPT = """把用户最新的问题改写成不依赖上下文、可以独立检索的问句。
规则：
- 补全代词和省略（它/这个/那个/上面说的），用对话里出现过的具体名词替换；
- 保留原始意图和关键限定（数字、时间、型号、条件）；
- 不要回答问题，不要添加对话里没有的信息；
- 只输出改写后的问句一行，不要引号、不要解释。"""

SUMMARY_PROMPT = """把下面的对话压缩成不超过 200 字的摘要，保留：用户关心的实体、已确认的事实、
尚未解决的问题。用第三人称陈述，不要评论。"""


@dataclass
class Turn:
    question: str
    answer: str


@dataclass
class ConversationMemory:
    llm: LLM
    max_turns: int = 6
    summary: str = ""
    turns: list[Turn] = field(default_factory=list)

    def add(self, question: str, answer: str) -> None:
        self.turns.append(Turn(question, answer))
        if len(self.turns) > self.max_turns:
            self._compact()

    def _compact(self) -> None:
        overflow = self.turns[: -self.max_turns]
        self.turns = self.turns[-self.max_turns:]
        transcript = "\n".join(f"用户：{t.question}\n助手：{t.answer[:300]}" for t in overflow)
        base = f"已有摘要：{self.summary}\n" if self.summary else ""
        self.summary = self.llm.chat(SUMMARY_PROMPT, base + transcript).strip()

    def condense(self, question: str) -> str:
        if not self.turns or not needs_condense(question):
            return question
        history = "\n".join(f"用户：{t.question}\n助手：{t.answer[:200]}" for t in self.turns[-3:])
        try:
            rewritten = self.llm.chat(CONDENSE_PROMPT, f"对话：\n{history}\n\n最新问题：{question}")
            rewritten = rewritten.strip().splitlines()[0].strip()
            return rewritten or question
        except Exception:
            return question

    def as_messages(self) -> list[dict]:
        msgs: list[dict] = []
        if self.summary:
            msgs.append({"role": "system", "content": f"早前对话摘要：{self.summary}"})
        for t in self.turns:
            msgs.append({"role": "user", "content": t.question})
            msgs.append({"role": "assistant", "content": t.answer})
        return msgs
