"""从 HF 拉模型文件：带总时长上限 + 多端点回退。

原先的问题：
- 只有 socket 超时（60s），服务端若"龟速滴流"，读循环会永远不结束
  → CI 里 `docker build` 卡了 6 小时才被 GitHub 强制杀掉。
现在：
- 每个文件有总时长上限（默认 10 分钟），超时抛异常换下一个端点；
- 端点按 `HF_ENDPOINT` → huggingface.co 依次回退。
"""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

# 国内默认走镜像；海外/CI 通过 HF_ENDPOINT 覆盖
_PRIMARY = os.environ.get("HF_ENDPOINT") or "https://hf-mirror.com"
ENDPOINTS = [_PRIMARY]
for _alt in ("https://huggingface.co",):
    if _alt not in ENDPOINTS:
        ENDPOINTS.append(_alt)

# 兼容旧名字
HF_MIRROR = _PRIMARY


def download_file(url: str, dest: Path, *, quiet: bool = False,
                  max_seconds: int = 600) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    started = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while chunk := resp.read(1 << 16):
            out.write(chunk)
            got += len(chunk)
            if time.time() - started > max_seconds:
                tmp.unlink(missing_ok=True)
                raise TimeoutError(f"下载超时 {max_seconds}s：{url}")
            if total and not quiet and got % (4 << 20) < (1 << 16):
                print(f"\r  {dest.name}: {got * 100 // total}%", end="", flush=True)
    tmp.replace(dest)
    if not quiet:
        print(f"\r  {dest.name}: done ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def ensure_repo_files(repo: str, files: dict[str, str], target: Path) -> Path:
    """files: 本地文件名 → 仓库内路径。逐个文件按端点回退。"""
    for local, remote in files.items():
        last_err: Exception | None = None
        for base in ENDPOINTS:
            url = f"{base}/{repo}/resolve/main/{remote}"
            try:
                download_file(url, target / local)
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                print(f"  [warn] {base} 失败（{type(exc).__name__}），换下一个端点")
        if last_err is not None:
            raise SystemExit(f"模型下载失败：{repo}/{remote} — {last_err}")
    return target
