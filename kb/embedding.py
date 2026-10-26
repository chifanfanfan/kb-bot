"""本地中文 Embedding：bge-small-zh-v1.5（ONNX）。

不依赖 sentence-transformers / torch：只用 onnxruntime + tokenizers，
模型权重首次运行时从 hf-mirror 下载（huggingface.co 在国内基本不可达）。

BGE v1.5 系列的句向量取 [CLS] 位置并做 L2 归一化，不是 mean pooling。
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from .config import MODEL_DIR

HF_BASE = "https://hf-mirror.com/Xenova/bge-small-zh-v1.5/resolve/main/"
FILES = {
    "config.json": "config.json",
    "tokenizer.json": "tokenizer.json",
    "tokenizer_config.json": "tokenizer_config.json",
    "model.onnx": "onnx/model_quantized.onnx",
}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while chunk := resp.read(1 << 16):
            out.write(chunk)
            got += len(chunk)
            if total and got % (1 << 20) < (1 << 16):
                print(f"\r  {dest.name}: {got * 100 // total}%", end="", flush=True)
    tmp.replace(dest)
    print(f"\r  {dest.name}: done ({dest.stat().st_size / 1e6:.1f} MB)")


def ensure_model(model_dir: Path = MODEL_DIR) -> Path:
    for local, remote in FILES.items():
        target = model_dir / local
        if target.exists() and target.stat().st_size > 0:
            continue
        print(f"下载 {remote} ...")
        _download(HF_BASE + remote, target)
    return model_dir / "model.onnx"


class BGEEmbedding:
    """批量把文本编码成归一化向量。"""

    def __init__(self, model_dir: Path = MODEL_DIR, max_length: int = 512) -> None:
        ensure_model(model_dir)
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(model_dir / "model.onnx"), sess_options=so, providers=["CPUExecutionProvider"]
        )
        self.input_names = {i.name for i in self.session.get_inputs()}

    @property
    def dim(self) -> int:
        return int(self.session.get_outputs()[0].shape[-1])

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encodings = self.tokenizer.encode_batch(batch)
            ids = np.array([e.ids for e in encodings], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
            hidden = self.session.run(None, feed)[0]
            if hidden.ndim == 3:
                # BGE 用 [CLS]；attention_mask 已保证首 token 有效
                pooled = hidden[:, 0, :]
            else:
                pooled = hidden
            norm = np.linalg.norm(pooled, axis=1, keepdims=True)
            vectors.append(pooled / np.clip(norm, 1e-12, None))
        return np.vstack(vectors)

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0].tolist()
