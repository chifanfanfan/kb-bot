#!/usr/bin/env bash
# 启动脚本：库是空的就先建库，再起服务。
#
# 为什么需要它：
#   服务启动时如果向量库是空的，进程会缓存一个空集合句柄；
#   之后再用命令行建库，服务**不会**自动看到新数据
#   （chromadb 按路径缓存 system 单例，同进程重连读不到别的进程写入）。
#   所以正确顺序是：先建库，再起服务。
set -e

cd "$(dirname "$0")/.."

echo "== 检查向量库 =="
COUNT=$(python - <<'PY'
from kb import KnowledgeBase
try:
    print(KnowledgeBase().store.count())
except Exception:
    print(0)
PY
)
echo "   当前块数：$COUNT"

if [ "$COUNT" = "0" ]; then
  echo "== 库是空的，先建库（data/synthetic）=="
  python -m kb build data/synthetic
else
  echo "== 库已有数据，跳过建库 =="
fi

echo "== 启动服务 =="
exec python server.py --host 0.0.0.0 --port 8000
