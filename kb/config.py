"""全局配置：分块、检索、生成三类参数都集中在这里，方便做 A/B 对比。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STORE_DIR = ROOT / "chroma"
MODEL_DIR = ROOT / "models" / "bge-small-zh-v1.5"
RERANK_DIR = ROOT / "models" / "bge-reranker-base"


@dataclass
class ChunkConfig:
    """分块参数。

    size 按"字符数"算而不是 token：中文一个字基本等于一个 token 的 1/1.5，
    用字符数更直观，也避免不同 tokenizer 之间的差异。
    """

    size: int = 600            # 真实论文语料扫出来的甜点（见 README 第九章），450 是合成语料的值
    overlap: int = 90          # ≈ size 的 15%
    min_chunk: int = 80        # 太碎的块直接丢弃，避免污染召回
    parent_size: int = 3000    # 父块上限：整节要多带一些，否则长节里的表格会被截掉
    embed_with_title: bool = False  # 实测无收益（0.73→0.72），默认关


@dataclass
class RetrieveConfig:
    top_k_vector: int = 20
    top_k_bm25: int = 20
    top_k_final: int = 6
    rrf_k: int = 60            # RRF 融合常数
    fusion: str = 'score'      # 'rrf' 按名次融合；'score' 按归一化分数融合（实测 hit@1 0.73→0.81）
    fusion_alpha: float = 0.5  # 分数融合里向量路的权重
    variant_weight: float = 1.0  # 多查询变体在融合时的权重（1.0 = 等权）
    mmr_lambda: float = 0.7    # 1.0 = 纯相关度，越小越强调多样性
    min_score: float = 0.30    # 低于该向量相似度视为"资料里没有"
    use_bm25: bool = True      # 关掉就退化成纯向量检索（用于消融对比）
    use_mmr: bool = False      # 实测在本语料上有损（hit@1 0.94→0.82），默认关；语料高度重复时再开
    use_rerank: bool = True    # 107 块基准上 hit@1 0.86→0.92；与多查询合用端到端 94.5%→98.4%
    rerank_pool: int = 8       # 送进交叉编码器的候选数（越多越慢，8 是延迟/精度的折中）
    use_multi_query: bool = True   # 与重排合用 hit@1 0.86→0.93；端到端 +3.9pp，代价 +1.8s
    query_instruction: str = "为这个句子生成表示以用于检索相关文章："  # 实测 hit@1 0.73→0.76，零延迟代价


@dataclass
class LLMConfig:
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0.0
    max_tokens: int = 1200
    api_key: str = field(default_factory=lambda: _resolve_key())


@dataclass
class Config:
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    retrieve: RetrieveConfig = field(default_factory=RetrieveConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    collection: str = "kb_chunks"
    memory_turns: int = 6          # 保留最近几轮原文
    verify_min_chars: int = 0      # 条件校验：64 条子集上省 1.5s，255 条上只省 0.2s 且掉 1 题，已回退
    memory_summary_chars: int = 1200


def _resolve_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    cred = Path.home() / ".dsh" / ".credentials.yaml"
    if cred.exists():
        import re

        m = re.search(r"DEEPSEEK_API_KEY\s*:\s*(\S+)", cred.read_text("utf-8"))
        if m:
            return m.group(1)
    raise SystemExit("未找到 DEEPSEEK_API_KEY，请先设置环境变量")
