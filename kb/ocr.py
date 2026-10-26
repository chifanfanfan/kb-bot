"""扫描件 OCR：把 PDF 页面渲染成图，交给 DeepSeek 视觉模型逐字转录。

为什么不用 PaddleOCR/Tesseract：
- PaddleOCR 要装 paddlepaddle（数百 MB），Tesseract 要装二进制并配语言包；
- 本项目的模型已经支持图片输入，顺带就能读扫描件，零新增运行时。

代价：每页一次 API 调用（约 1~2 秒），所以只对"抽不出文字"的页面触发。
"""

from __future__ import annotations

import base64
from pathlib import Path

OCR_SYSTEM = "你是文档 OCR 引擎。只输出图片中的文字，逐字转录，不做总结、不解释、不补充。"
OCR_PROMPT = (
    "逐字转录这一页的全部文字。要求：\n"
    "1. 保留原有的标题层级和段落顺序，标题单独成行；\n"
    "2. 表格用「列1 | 列2」的形式逐行输出；\n"
    "3. 看不清的字用 □ 占位，不要猜测；\n"
    "4. 只输出正文，不要加任何说明性文字。"
)


def page_is_sparse(text: str, min_chars: int = 30) -> bool:
    return len(text.strip()) < min_chars


def ocr_pages(pdf_path: Path, page_indices: list[int], llm, dpi: int = 200) -> dict[int, str]:
    """批量 OCR，返回 {页序号(0-based): 文本}。"""
    if not page_indices:
        return {}
    import pymupdf

    results: dict[int, str] = {}
    with pymupdf.open(str(pdf_path)) as doc:
        for idx in page_indices:
            pix = doc[idx].get_pixmap(dpi=dpi)
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            results[idx] = llm.vision(OCR_SYSTEM, OCR_PROMPT, b64).strip()
    return results


def ocr_page(pdf_path: Path, page_index: int, llm, dpi: int = 200) -> str:
    return ocr_pages(pdf_path, [page_index], llm, dpi).get(page_index, "")
