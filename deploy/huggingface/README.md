---
title: PDF 知识库问答（RAG）
emoji: 🐋
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# PDF 知识库问答（RAG）

中文文档问答：上传 PDF → 提问 → 带页码引用的回答。

- 本地 ONNX 向量模型（bge-small-zh）+ Chroma
- 向量 + BM25 分数融合 → 交叉编码器重排
- 自建 255 条评测集，答案准确率 98.4%
- 查不到会直接说"资料中没有"

源码：https://github.com/chifanfanfan/kb-bot

## 需要配置的 Secret

在 Space 设置里加 `DEEPSEEK_API_KEY`（Settings → Variables and secrets）。
