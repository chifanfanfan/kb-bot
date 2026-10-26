"""生成第二份语料《北极星服务条款》，与产品手册共享大量词汇（退款、席位、SLA、
赔偿），用来检验检索是否真的能区分，而不是碰巧命中。
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

FONT = "C:/Windows/Fonts/simhei.ttf"
OUT = Path(__file__).resolve().parent.parent / "data" / "北极星服务条款.pdf"

SECTIONS: list[tuple[str, list[str]]] = [
    ("第1章 定义与解释", [
        "本条款中的「服务」指北极星系列软件即服务，「客户」指完成注册并支付费用的主体，「席位」指一个可独立登录的账号。",
        "本条款与《北极星 Pro 产品手册》共同构成完整协议；两者冲突时，以本条款为准。",
    ]),
    ("第2章 服务开通与终止", [
        "服务自客户完成首次支付之日起开通，开通后即时生效，无需人工审核。",
        "客户可随时终止服务；终止后账号在 30 天内保留只读访问权限，30 天后转入冻结状态。",
        "若客户连续 90 天未登录且未续费，服务商有权回收席位并清除数据，清除前 15 天会发送邮件提醒。",
    ]),
    ("第3章 退款处理流程", [
        "退款申请需由客户的管理员账号在控制台提交，并注明订单号与退款原因。",
        "服务商在收到完整材料后的 10 个工作日内完成审核，审核通过后 5 个工作日内退回原支付账户。",
        "退款金额以实际支付金额为准，已使用的服务按日单价扣除；代金券、赠送时长不予退还。",
        "跨境支付产生的汇兑损失与手续费由客户承担。",
    ]),
    ("第4章 数据所有权与保密", [
        "客户数据的所有权归客户所有，服务商仅在提供服务所必需的范围内处理数据。",
        "双方对在合作过程中知悉的对方商业秘密负有保密义务，保密期为协议终止后 3 年。",
        "服务商不得将客户数据用于训练模型，除非客户以书面形式明确授权。",
    ]),
    ("第5章 违约责任", [
        "因服务商原因导致服务中断的，赔偿责任以客户当年度实际支付服务费的 50% 为上限。",
        "因客户违反使用条款导致的损失，由客户自行承担；服务商有权暂停服务且不退还费用。",
        "因不可抗力导致的服务中断，双方均不承担违约责任，但服务商应及时通知并顺延服务期。",
    ]),
    ("第6章 条款变更与通知", [
        "服务商可在提前 30 天通过站内信与邮件通知的情况下变更本条款。",
        "客户在变更生效后继续使用服务的，视为接受变更；不接受的可在生效前终止服务并按比例退款。",
    ]),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("simhei", "", FONT)
    pdf.add_page()

    pdf.set_font("simhei", size=20)
    pdf.multi_cell(0, 12, "北极星 服务条款")
    pdf.ln(2)
    pdf.set_font("simhei", size=10)
    pdf.multi_cell(0, 6, "生效日期 2026-01-01 ｜ 版本 v2.3")
    pdf.ln(4)

    for heading, paragraphs in SECTIONS:
        pdf.set_font("simhei", size=14)
        pdf.multi_cell(0, 9, heading)
        pdf.ln(1)
        pdf.set_font("simhei", size=11)
        for para in paragraphs:
            pdf.multi_cell(0, 7, para)
            pdf.ln(1)
        pdf.ln(2)

    pdf.output(str(OUT))
    print(f"saved: {OUT} ({OUT.stat().st_size / 1024:.1f} KB, {pdf.pages_count} pages)")


if __name__ == "__main__":
    main()
