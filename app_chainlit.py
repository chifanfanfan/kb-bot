"""Chainlit 界面：把 kb.answer 包成「带过程trace的对话」。

启动：
    chainlit run app_chainlit.py -p 8020
或：
    python -m chainlit run app_chainlit.py -p 8020
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chainlit as cl  # noqa: E402

from kb import ConversationMemory, KnowledgeBase  # noqa: E402

WELCOME = """### PDF 知识库问答

直接提问，或拖一个 PDF 进来建库。

- **本地向量模型**（bge-small-zh，ONNX）+ Chroma
- **混合检索**：向量 + BM25 分数融合 → 交叉编码器重排
- **带引用**：每个结论都能追溯到页码和小节
- **会拒答**：资料里没有的，直接说没有
"""

kb = KnowledgeBase()


@cl.on_chat_start
async def on_start() -> None:
    count = await cl.make_async(kb.store.count)()
    docs = await cl.make_async(lambda: {r.doc for r in kb.store.all_records()})()
    cl.user_session.set("memory", ConversationMemory(kb.llm, max_turns=6))
    await cl.Message(
        content=f"{WELCOME}\n当前库内 **{count}** 个块 / **{len(docs)}** 份文档。"
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    # ---- 上传 PDF ----
    files = [e for e in (message.elements or []) if str(getattr(e, "path", "")).lower().endswith(".pdf")]
    if files:
        for f in files:
            async with cl.Step(name=f"建立索引 · {Path(f.path).name}", type="tool") as step:
                step.output = "解析 → 分块 → 向量化…"
                stats = await cl.make_async(kb.build)([Path(f.path)])
                step.output = (
                    f"{stats['pages']} 页 → {stats['sections']} 节 → "
                    f"{stats['chunks']} 块" + (f"（OCR {stats['ocr_pages']} 页）" if stats["ocr_pages"] else "")
                )
        await cl.Message(content="建库完成，可以开始提问了。").send()
        return

    question = (message.content or "").strip()
    if not question:
        return

    memory = cl.user_session.get("memory")

    async with cl.Step(name="检索与生成", type="tool") as step:
        step.output = "改写追问 → 向量召回 + BM25 → 分数融合 → 重排…"
        ans = await cl.make_async(kb.answer)(question, memory=memory)
        if ans.hits:
            lines = [
                f"{i}. 《{h.doc}》{h.section} p{h.page} · 分数 {h.score:.3f}"
                for i, h in enumerate(ans.hits[:5], 1)
            ]
            step.output = "召回 top5：\n" + "\n".join(lines)
        else:
            step.output = "没有召回结果"

    if memory is not None:
        memory.add(question, ans.text)

    elements = []
    for c in ans.citations[:6]:
        elements.append(
            cl.Text(
                name=f"[{c['n']}] {c['doc']} · p{c['page']} · {c['section']}",
                content=f"**相关度**：{c['score']}\n\n> {c['snippet']}",
                display="side",
            )
        )

    footer = ""
    if not ans.grounded:
        footer = "\n\n> ⚠️ 这条回答未通过接地校验，请核对引用。"
    if ans.note:
        footer += f"\n\n> ℹ️ {ans.note}"

    await cl.Message(content=ans.text + footer, elements=elements).send()
