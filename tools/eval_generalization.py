"""泛化测试：同一套系统、同一套参数，换到完全不同的语料（政策法规）能答对多少。

    python tools/eval_generalization.py

用法：
1. 先跑 tools/build_second_corpus.py 建库；
2. 再跑这个脚本。

15 道题全部人工从三份政府公开文件里挑事实出题，keywords 是该事实的关键数字/短语。
不含负样本（这一轮只测"能不能答对"，拒答能力在主评测集里测）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import KnowledgeBase  # noqa: E402
from kb.config import Config  # noqa: E402
from kb.eval import Case, eval_answers, is_refusal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "eval" / "general" / "chroma"

CASES = [
    Case(q="个人信息保护法是什么时候通过的？", keywords=["2021年8月20日"], refusal=False, gold=["正文"], tag="个保法"),
    Case(q="通过个人信息保护法的是第几届全国人大常委会第几次会议？", keywords=["十三届", "第三十次"],
         refusal=False, gold=["正文"], tag="个保法"),
    Case(q="处理个人信息应当遵循哪些基本原则？", keywords=["合法", "正当", "必要", "诚信"],
         refusal=False, gold=["个人信息处理规则"], tag="个保法"),
    Case(q="匿名化处理后的信息受个人信息保护法保护吗？", keywords=["匿名化"], refusal=False, gold=["正文"], tag="个保法"),
    Case(q="个人信息的处理包括哪些环节？", keywords=["收集", "存储", "加工", "删除"],
         refusal=False, gold=["正文"], tag="个保法"),
    Case(q="在境外处理境内自然人个人信息的哪些情形适用本法？", keywords=["产品或者服务", "分析、评估"],
         refusal=False, gold=["正文"], tag="个保法"),
    Case(q="处理个人信息前，应当向个人告知哪些事项？", keywords=["处理目的", "保存期限"],
         refusal=False, gold=["个人信息处理规则"], tag="个保法"),
    Case(q="个人不同意处理其个人信息，处理者能否拒绝提供服务？", keywords=["不得", "拒绝提供产品或者服务"],
         refusal=False, gold=["个人信息处理规则"], tag="个保法"),
    Case(q="委托处理个人信息时，受托人能否转委托他人？", keywords=["不得", "转委托"],
         refusal=False, gold=["个人信息处理规则"], tag="个保法"),
    Case(q="履行个人信息保护职责的部门是这部法律的第几章？", keywords=["第六章"], refusal=False, gold=["正文"], tag="个保法"),
    Case(q="2025 年数字经济核心产业增加值占 GDP 比重要达到多少？", keywords=["10%"],
         refusal=False, gold=["数字经济"], tag="数字经济"),
    Case(q="十四五数字经济发展规划提出到哪一年的发展目标？", keywords=["2025"], refusal=False, gold=["数字经济"], tag="数字经济"),
    Case(q="数字中国建设整体布局规划提出到哪一年的目标？", keywords=["2035"], refusal=False, gold=["数字中国"], tag="数字中国"),
    Case(q="数字中国建设提到哪两大基础？", keywords=["数字"], refusal=False, gold=["数字中国"], tag="数字中国"),
    Case(q="数据安全在数字经济发展规划中提到了哪些方面？", keywords=["数据"], refusal=False, gold=["数字经济"], tag="数字经济"),
]


def main() -> None:
    if not STORE.exists():
        raise SystemExit("第二语料库不存在，先跑 tools/build_second_corpus.py")

    cfg = Config()
    cfg.store_dir = STORE
    cfg.collection = "kb_general"
    cfg.use_cache = False
    kb = KnowledgeBase(cfg)
    print(f"第二语料库：{kb.store.count()} 块\n")

    result = eval_answers(kb, CASES)
    print(f"泛化正确率：{result['correct']}/{result['n']} = {result['accuracy']:.1%}")
    print(f"平均延迟：{result['latency_ms']/1000:.1f}s")

    print("\n逐题：")
    for d in result["details"]:
        flag = "OK  " if d["ok"] else "FAIL"
        extra = f" 缺 {d['missing']}" if d["missing"] else ""
        refused = " [拒答]" if d["refused"] else ("" if d["ok"] else " [调取]")
        print(f"  [{flag}] {d['q'][:34]:36s}{refused}{extra}")


if __name__ == "__main__":
    main()
