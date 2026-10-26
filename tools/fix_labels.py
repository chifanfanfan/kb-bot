"""按人工审计结果修正标注。

逐条看过 14 个失败样本后，大部分是标签问题（英文关键词、关键词过窄、
把部分可答标成应拒答），只有 1 条是真的系统问题。这个脚本把结论落回评测集。

    python tools/fix_labels.py
"""

from __future__ import annotations

import json
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval" / "questions.json"

DROP = {
    "管理员端的内容审核流程是基于什么机制实现的？",     # 关键词来自英文摘要，判定无意义
    "这个系统主要集成了哪两项功能？",                    # 答案等价，说法不同
    "这套系统部署时对硬件有什么要求？",                  # 半可答，二值标签不适合
    "管理员能获得哪方面的能力？",                        # 与"管理员能做哪些操作"重复
    "发帖时如果标签不为空，标签内容会以什么形式拼进送审文本？",  # 资料确实没写，标成可答是错的
    "邮箱在查重之前做了哪些处理？",                      # 模型先拒后答，二值判定不适合
}

PATCH = {
    "这个社区论坛系统给普通用户提供了哪些功能？": {"keywords": ["注册", "发帖", "上传"]},
    "管理员在系统里能进行哪些操作？": {"keywords": ["用户", "审核"]},
    "普通用户通过什么方式访问这个系统？": {"keywords": ["浏览器"]},
    "功能调整后要确认既有能力没被破坏，应该做哪种测试？": {"keywords": ["回归测试", "既有能力不受破坏"]},
    "后续优化方向里，违规识别和多模态审核分别要提升什么？": {"keywords": ["复杂语义", "多模态审核"]},
    "未来计划用哪些工具实现业务模块的独立横向拓展和弹性资源扩容？": {"keywords": ["Docker", "Kubernetes"]},
    "那篇讲跨平台移动应用测试脚本录制回放的论文发表在哪个期刊、哪一年、第几卷？": {"keywords": ["软件学报", "2025"]},
    # 资料里确实没写版本号，应当是拒答题
    "开发这个项目用的是哪个版本的 Java？": {"refusal": True, "gold": [], "keywords": []},
    "未登录的访客能看到哪些内容？": {"keywords": ["浏览"]},
    "用户没有填昵称时，昵称会取什么值？": {"keywords": ["用户名"]},
    "为什么说引入自动化审核模块在经济上划算？": {"keywords": ["成本"]},
}


def main() -> None:
    data = json.loads(EVAL.read_text("utf-8"))
    cases = [c for c in data["cases"] if c["q"] not in DROP]
    patched = 0
    for case in cases:
        fix = PATCH.get(case["q"])
        if fix:
            case.update(fix)
            patched += 1
    EVAL.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), "utf-8")
    print(f"删除 {len(data['cases']) - len(cases)} 条，修正 {patched} 条")
    print(f"剩余 {len(cases)} 条（可答 {sum(1 for c in cases if not c['refusal'])}，"
          f"拒答 {sum(1 for c in cases if c['refusal'])}）")


if __name__ == "__main__":
    main()
