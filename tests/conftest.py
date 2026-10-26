"""测试全局配置：把 TMP 指到项目内，避免用到不可写的系统临时目录。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_PROJECT_TMP = Path(__file__).resolve().parent.parent / ".tmp-test"


def pytest_configure(config):
    _PROJECT_TMP.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = str(_PROJECT_TMP)
    os.environ["TEMP"] = str(_PROJECT_TMP)
    tempfile.tempdir = str(_PROJECT_TMP)


def pytest_unconfigure(config):
    shutil.rmtree(_PROJECT_TMP, ignore_errors=True)


@pytest.fixture()
def anyio_backend():
    return "asyncio"
