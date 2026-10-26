"""从 hf-mirror 拉模型文件的通用工具。

huggingface.co 在国内基本不可达，hf-mirror.com 是同一套内容的镜像；
模型只有首次运行需要下载，之后走本地缓存。
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

HF_MIRROR = "https://hf-mirror.com"


def download_file(url: str, dest: Path, *, quiet: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while chunk := resp.read(1 << 16):
            out.write(chunk)
            got += len(chunk)
            if total and not quiet and got % (4 << 20) < (1 << 16):
                print(f"\r  {dest.name}: {got * 100 // total}%", end="", flush=True)
    tmp.replace(dest)
    if not quiet:
        print(f"\r  {dest.name}: done ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def ensure_repo_files(repo: str, files: dict[str, str], target: Path) -> Path:
    """files: 本地文件名 → 仓库内路径。"""
    for local, remote in files.items():
        download_file(f"{HF_MIRROR}/{repo}/resolve/main/{remote}", target / local)
    return target
