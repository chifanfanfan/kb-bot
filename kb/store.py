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
        self._path = str(path)
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

    def reopen(self) -> None:
        """重建 client + collection。

        场景：服务启动时库是空的，另一进程后来建了库，
        当前进程缓存的是一个指向空磁盘的 hnsw 句柄，查询会报
        "Error creating hnsw segment reader: Nothing found on disk"。
        """
        # chromadb 按路径缓存了 system 单例，不清掉的话新建 client 拿到的还是旧句柄
        try:
            from chromadb.api.shared_system_client import SharedSystemClient
            SharedSystemClient._identifier_to_system.clear()
        except Exception:
            pass
        try:
            self.client = chromadb.PersistentClient(
                path=self._path,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
        except Exception:
            pass
        self.collection = self._open()

    def _retry_on_stale(self, fn):
        """执行 fn(collection)；遇到 hnsw 句柄失效就重开一次再试。"""
        coll = self._alive()
        try:
            return fn(coll)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "hnsw" in msg or "nothing found on disk" in msg or "segment reader" in msg:
                self.reopen()
                return fn(self.collection)
            raise

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
        return self._retry_on_stale(
            lambda coll: coll.query(
                query_embeddings=[embedding],
                n_results=k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        )

    def all_records(self) -> list[Record]:
        got = self._retry_on_stale(lambda coll: coll.get(include=["documents", "metadatas"]))
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
        return self._retry_on_stale(lambda coll: coll.count())

    def reset(self) -> None:
        try:
            self.client.delete_collection(self._name)
        except Exception:
            pass  # 已经被别的进程删掉了
        self.collection = self._open()
