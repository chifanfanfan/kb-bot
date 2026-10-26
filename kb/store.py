"""Chroma 向量库封装：写入、查询、统计。

只存 child chunk 的向量；parent_text 作为元数据一起存，
生成阶段用它替换 child 文本，省一次查库。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings

from .chunker import Chunk

COLLECTION = "kb_chunks"


@dataclass
class Record:
    id: str
    text: str
    parent_text: str
    doc: str
    section: str
    page: int
    page_end: int


class VectorStore:
    def __init__(self, path: Path | str, collection: str = COLLECTION) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)  # chromadb 不会自己建目录
        self.client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._name = collection
        self.collection = self._open()

    def _open(self):
        return self.client.get_or_create_collection(
            name=self._name, metadata={"hnsw:space": "cosine"}
        )

    def _alive(self):
        """集合句柄可能被别的进程 reset 掉（比如命令行清了库），失效就重连。"""
        try:
            self.collection.count()
        except Exception:
            self.collection = self._open()
        return self.collection

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._alive().add(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "doc": c.doc,
                    "section": c.section,
                    "page": c.page,
                    "page_end": c.page_end,
                    "parent_id": c.parent_id,
                    "parent_text": c.parent_text,
                    "index": c.index,
                }
                for c in chunks
            ],
        )

    def query(self, embedding: list[float], k: int, where: dict | None = None):
        return self._alive().query(
            query_embeddings=[embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def all_records(self) -> list[Record]:
        got = self._alive().get(include=["documents", "metadatas"])
        out: list[Record] = []
        for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
            out.append(
                Record(
                    id=cid,
                    text=text or "",
                    parent_text=(meta or {}).get("parent_text", text or ""),
                    doc=(meta or {}).get("doc", ""),
                    section=(meta or {}).get("section", ""),
                    page=int((meta or {}).get("page", 0)),
                    page_end=int((meta or {}).get("page_end", 0)),
                )
            )
        return out

    def get_by_ids(self, ids: list[str]) -> dict[str, Record]:
        if not ids:
            return {}
        got = self._alive().get(ids=ids, include=["documents", "metadatas"])
        out: dict[str, Record] = {}
        for cid, text, meta in zip(got["ids"], got["documents"], got["metadatas"]):
            out[cid] = Record(
                id=cid,
                text=text or "",
                parent_text=(meta or {}).get("parent_text", text or ""),
                doc=(meta or {}).get("doc", ""),
                section=(meta or {}).get("section", ""),
                page=int((meta or {}).get("page", 0)),
                page_end=int((meta or {}).get("page_end", 0)),
            )
        return out

    def count(self) -> int:
        return self._alive().count()

    def reset(self) -> None:
        try:
            self.client.delete_collection(self._name)
        except Exception:
            pass  # 已经被别的进程删掉了
        self.collection = self._open()
