"""生产模式启动：用 waitress（纯 Python WSGI，Windows/Linux 通用）。

Flask 自带的 dev server 是单进程调试用的，不适合给别人访问；
waitress 是多线程 WSGI 服务器，Windows 上也不需要 gunicorn。

    python server.py                      # 0.0.0.0:8000
    python server.py --port 8010
    python server.py --threads 8
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from waitress import serve  # noqa: E402

from web.app import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="以生产模式启动 kb-bot 网页服务")
    parser.add_argument("--host", default=os.environ.get("KB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("KB_PORT", "8000")))
    parser.add_argument("--threads", type=int, default=int(os.environ.get("KB_THREADS", "6")))
    args = parser.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[warn] 没有 DEEPSEEK_API_KEY，问答会失败（建库/统计不受影响）")

    print(f"kb-bot 生产模式：http://{args.host}:{args.port}  (threads={args.threads})")
    serve(app, host=args.host, port=args.port, threads=args.threads)


if __name__ == "__main__":
    main()
