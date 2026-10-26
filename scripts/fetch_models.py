"""一键准备：把两个模型下载到 models/（约 306 MB），已存在则跳过。

    python scripts/fetch_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kb.hf import ensure_repo_files  # noqa: E402

EMBED = {
    "repo": "Xenova/bge-small-zh-v1.5",
    "files": {
        "config.json": "config.json",
        "tokenizer.json": "tokenizer.json",
        "tokenizer_config.json": "tokenizer_config.json",
        "model.onnx": "onnx/model_quantized.onnx",
    },
    "dir": ROOT / "models" / "bge-small-zh-v1.5",
}

RERANK = {
    "repo": "Xenova/bge-reranker-base",
    "files": {
        "tokenizer.json": "tokenizer.json",
        "tokenizer_config.json": "tokenizer_config.json",
        "model.onnx": "onnx/model_quantized.onnx",
    },
    "dir": ROOT / "models" / "bge-reranker-base",
}


def main() -> None:
    for spec in (EMBED, RERANK):
        target: Path = spec["dir"]
        print(f"\n== {target.name} ==")
        ensure_repo_files(spec["repo"], spec["files"], target)
        size = sum(f.stat().st_size for f in target.iterdir() if f.is_file())
        print(f"   就绪：{size / 1e6:.1f} MB")
    print("\n模型准备完成。")


if __name__ == "__main__":
    main()
