"""交叉编码器重排：bge-reranker-base（ONNX）。

和双塔 embedding 不同，reranker 把「问题+段落」拼在一起过一遍模型，
输出一个相关性分数。它更准，但只能对少量候选做（本项目取 12 条），
所以流程是：召回 20+20 → RRF → 取 12 → reranker → 取 6。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from .config import RERANK_DIR
from .hf import ensure_repo_files

REPO = "Xenova/bge-reranker-base"
FILES = {
    "tokenizer.json": "tokenizer.json",
    "tokenizer_config.json": "tokenizer_config.json",
    "model.onnx": "onnx/model_quantized.onnx",
}


class CrossEncoderReranker:
    def __init__(self, model_dir: Path = RERANK_DIR, max_length: int = 384) -> None:
        ensure_repo_files(REPO, FILES, model_dir)
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # reranker 在小 batch 下开多线程反而更慢
        so.intra_op_num_threads = 4
        self.session = ort.InferenceSession(
            str(model_dir / "model.onnx"), sess_options=so, providers=["CPUExecutionProvider"]
        )
        self.input_names = {i.name for i in self.session.get_inputs()}

    def score(self, query: str, passages: list[str], batch_size: int = 8) -> list[float]:
        if not passages:
            return []
        scores: list[float] = []
        for start in range(0, len(passages), batch_size):
            batch = passages[start : start + batch_size]
            encodings = self.tokenizer.encode_batch([(query, p) for p in batch])
            ids = np.array([e.ids for e in encodings], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
            logits = self.session.run(None, feed)[0]
            flat = logits.reshape(len(batch), -1)[:, 0]
            # bge-reranker 输出原始 logit，sigmoid 后当相关度
            scores.extend((1.0 / (1.0 + np.exp(-flat))).tolist())
        return scores
