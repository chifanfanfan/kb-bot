"""DeepSeek 调用封装：普通补全、流式、结构化输出。"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from pathlib import Path

from openai import OpenAI

from .config import LLMConfig


class LLM:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        # token 记账：每次调用累加，写 JSONL 供成本报表使用
        self.usage_path = Path(__file__).resolve().parent.parent / "cache" / "usage.jsonl"
        self.stats = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def _record(self, resp, kind: str = "chat") -> None:
        u = getattr(resp, "usage", None)
        pt = getattr(u, "prompt_tokens", 0) or 0
        ct = getattr(u, "completion_tokens", 0) or 0
        self.stats["calls"] += 1
        self.stats["prompt_tokens"] += pt
        self.stats["completion_tokens"] += ct
        try:
            self.usage_path.parent.mkdir(parents=True, exist_ok=True)
            with self.usage_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "kind": kind,
                                     "prompt": pt, "completion": ct}) + "\n")
        except OSError:
            pass

    def chat(self, system: str, user: str, *, temperature: float | None = None,
             max_tokens: int | None = None) -> str:
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.cfg.temperature if temperature is None else temperature,
            max_tokens=self.cfg.max_tokens if max_tokens is None else max_tokens,
        )
        self._record(resp)
        return resp.choices[0].message.content or ""

    def chat_messages(self, messages: list[dict], **kw) -> str:
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=kw.get("temperature", self.cfg.temperature),
            max_tokens=kw.get("max_tokens", self.cfg.max_tokens),
        )
        return resp.choices[0].message.content or ""

    def vision(self, system: str, prompt: str, image_b64: str, *, mime: str = "image/png") -> str:
        """图片理解：用于扫描件 OCR，也用于让模型直接看图表。"""
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content or ""

    def stream(self, system: str, user: str) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def json_chat(self, system: str, user: str, *, fallback: dict | None = None) -> dict:
        """要求模型输出 JSON；解析失败时退化为正则抽取。"""
        text = self.chat(system + "\n只输出 JSON，不要解释，不要代码块围栏。", user,
                         temperature=0.0, max_tokens=600)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return fallback or {}
