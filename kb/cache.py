"""答案缓存：同一个问题问第二遍，不该再跑一遍全链路。

两级思路里先做简单可靠的那级：
- **精确缓存**：问题归一化（去空格/标点/大小写）+ 文档版本 作为 key；
- 语义缓存（embedding 相似度）暂不做——收益不确定，但会引入"答非所问"的风险。

失效策略：key 里带文档版本（块数 + 文档名哈希），文档一变自动全部失效。
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path


def normalize(question: str) -> str:
    """归一化：全角转半角、去标点、去空白、转小写。"""
    s = question.strip().lower()
    table = str.maketrans("，。？！；：、（）【】“”‘’", ",.?!;;:()[]\"\"''")
    s = s.translate(table)
    s = re.sub(r"[\s,.?!;:()\[\]\"'`~]+", "", s)
    return s


class AnswerCache:
    def __init__(self, path: Path | str, ttl_days: int = 7) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_days * 86400
        self.hits = 0
        self.misses = 0
        self._data: dict[str, dict] = {}
        self._load()

    # ---------- 持久化 ----------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def _save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=1), "utf-8"
            )
        except OSError:
            pass  # 缓存写失败不该影响主流程

    # ---------- 读写 ----------
    def _key(self, question: str, doc_version: str) -> str:
        raw = f"{normalize(question)}|{doc_version}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get(self, question: str, doc_version: str) -> dict | None:
        item = self._data.get(self._key(question, doc_version))
        if not item:
            self.misses += 1
            return None
        if time.time() - item.get("ts", 0) > self.ttl:
            self.misses += 1
            return None
        item["hits"] = item.get("hits", 0) + 1
        self.hits += 1
        self._save()  # 命中计数落盘，成本报表要用
        return item.get("answer")

    def put(self, question: str, doc_version: str, answer: dict) -> None:
        key = self._key(question, doc_version)
        prev = self._data.get(key, {})
        self._data[key] = {
            "q": question[:120],
            "ts": time.time(),
            "hits": prev.get("hits", 0),
            "answer": answer,
        }
        self._save()

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def size(self) -> int:
        return len(self._data)
