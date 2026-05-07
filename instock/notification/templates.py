#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
from typing import Any, Dict


def _fmt_money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "-"


def _fmt_number(value) -> str:
    try:
        return f"{float(value):,.3f}"
    except Exception:
        return "-"


def _fmt_dt(value) -> str:
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime.datetime) else value.strftime("%Y-%m-%d")
    return str(value or "-")


def _format_value(value, max_len: int = 80) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        try:
            return _fmt_number(value)
        except Exception:
            return str(value)[:max_len]
    if isinstance(value, str):
        return value[:max_len]
    try:
        import json as _json
        return _json.dumps(value, ensure_ascii=False, default=str)[:max_len]
    except Exception:
        return str(value)[:max_len]


def _build_reason_block(event: Dict[str, Any]) -> str:
    """Phase 2: 渲染策略真实理由块。来源必须明确标注。"""
    reason = (event.get("reason") or "").strip()
    if not reason:
        return ""
    source = event.get("reason_source") or "strategy"
    source_label = "策略真实理由" if source == "strategy" else "系统兜底说明（非策略显式提供）"
    return f"\n## 交易理由（来源：{source_label}）\n\n> {reason}\n"


def _build_decision_block(event: Dict[str, Any], max_rules: int = 5) -> str:
    """Phase 2: 渲染规则阈值 vs 实际值表格。最多展示 ``max_rules`` 行。"""
    rules = event.get("decision_rules") or []
    if not rules:
        return ""
    head = (
        "\n## 决策规则对比\n\n"
        "| 规则 | 阈值 | 实际值 | 结果 |\n"
        "|---|---|---|---|\n"
    )
    body_lines = []
    for rule in rules[:max_rules]:
        name = (rule.get("rule_name") or "rule")[:48]
        threshold_repr = rule.get("threshold_expr") or _format_value(rule.get("threshold_value"))
        actual_repr = _format_value(rule.get("actual_value"))
        passed = rule.get("passed")
        if passed == 1 or passed is True:
            result_label = "通过"
        elif passed == 0 or passed is False:
            result_label = "未通过"
        else:
            result_label = "—"
        body_lines.append(f"| {name} | {threshold_repr or '-'} | {actual_repr} | {result_label} |")
    extra = ""
    if len(rules) > max_rules:
        extra = f"\n> 仅展示前 {max_rules} 条，剩余 {len(rules) - max_rules} 条可在系统详情页查看。"
    return head + "\n".join(body_lines) + extra + "\n"


def _build_ai_block(event: Dict[str, Any], max_evidence: int = 3, max_risks: int = 3) -> str:
    """Phase 4: 渲染 AI 综合研判摘要块（可选）。

    仅展示 score / action / gate_result / reason_summary / 关键证据 / 风险提示；
    完整 prompt、密钥、长 K 线均不进入通知（§3.7 / §7.4）。
    AI 字段不存在时返回空串，不影响 Phase 1/2/3 通知行为。
    """
    score = event.get("ai_score")
    action = event.get("ai_action")
    gate = event.get("ai_gate_result")
    reason_summary = event.get("ai_reason_summary")
    if score is None and not action and not gate and not reason_summary:
        return ""
    lines = ["\n## AI 综合研判（仅供参考）\n"]
    head_parts = []
    if score is not None:
        try:
            head_parts.append(f"评分 {float(score):.2f}/100")
        except Exception:
            head_parts.append(f"评分 {score}")
    if action:
        head_parts.append(f"建议 {action}")
    confidence = event.get("ai_confidence")
    if confidence is not None:
        try:
            head_parts.append(f"置信度 {float(confidence):.2f}")
        except Exception:
            pass
    if gate:
        gate_label = {
            "not_enabled": "Gate 未启用",
            "pass": "Gate 通过",
            "reject": "Gate 拒绝",
            "fallback": "Gate 回退（AI 失败放行）",
            "error": "Gate 错误",
        }.get(str(gate), str(gate))
        head_parts.append(gate_label)
    if head_parts:
        lines.append("- " + "，".join(head_parts))
    if reason_summary:
        lines.append(f"- 摘要：{str(reason_summary)[:200]}")
    evidence = event.get("ai_evidence") or []
    if isinstance(evidence, list) and evidence:
        lines.append("- 关键依据：")
        for ev in evidence[:max_evidence]:
            text = ev if isinstance(ev, str) else _format_value(ev, 100)
            lines.append(f"  - {text}")
    risk_flags = event.get("ai_risk_flags") or []
    if isinstance(risk_flags, list) and risk_flags:
        lines.append("- 风险提示：")
        for rf in risk_flags[:max_risks]:
            text = rf if isinstance(rf, str) else _format_value(rf, 100)
            lines.append(f"  - {text}")
    lines.append("> AI 评分仅作辅助研判，不代表交易建议；完整证据请到系统详情页查看。")
    return "\n".join(lines) + "\n"


def _truncate(text, max_len: int = 80) -> str:
    if not text:
        return ""
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def _direction_label(direction: str) -> str:
    if direction == "buy":
        return "买入"
    if direction == "sell":
        return "卖出"
    return direction or ""


def _build_summary_block(event: Dict[str, Any]) -> str:
    """§7 摘要总结：方向 / AI评分 / 成交金额+仓位 / 核心理由 / 关键风险。"""
    direction = event.get("direction") or ""
    direction_text = _direction_label(direction)
    code = event.get("code") or ""
    name = event.get("name") or ""
    stock_label = f"{code} {name}".strip()
    lines = ["## 摘要\n"]
    if stock_label:
        lines.append(f"- 标的：{stock_label}")
    lines.append(f"- 方向：{direction_text or '-'}")

    score = event.get("ai_score")
    action = event.get("ai_action")
    gate = event.get("ai_gate_result")
    if score is not None or action or (gate and gate != "not_enabled"):
        ai_parts = []
        if score is not None:
            try:
                ai_parts.append(f"{float(score):.2f}/100")
            except Exception:
                ai_parts.append(str(score))
        if action:
            ai_parts.append(f"建议 {action}")
        if gate:
            gate_label = {
                "pass": "Gate 通过",
                "reject": "Gate 拒绝",
                "fallback": "Gate 回退",
                "error": "Gate 错误",
                "not_enabled": "",
            }.get(str(gate), str(gate))
            if gate_label:
                ai_parts.append(gate_label)
        if ai_parts:
            lines.append(f"- AI 评分：{'，'.join(ai_parts)}")

    value_part = f"{_fmt_money(event.get('value'))} 元"
    pos_after = event.get("position_after_pct")
    if pos_after is not None:
        try:
            value_part += f"，成交后仓位 {float(pos_after) * 100:.2f}%" if float(pos_after) <= 1.5 else f"，成交后仓位 {float(pos_after):.2f}%"
        except Exception:
            pass
    if direction == "sell" and event.get("close_profit") not in (None, 0, 0.0):
        try:
            cp = float(event.get("close_profit"))
            sign = "+" if cp >= 0 else ""
            value_part += f"，平仓盈亏 {sign}{_fmt_money(cp)} 元"
            rr = event.get("return_rate")
            if rr is not None:
                rr_v = float(rr)
                value_part += f"，收益率 {'+' if rr_v >= 0 else ''}{rr_v:.2f}%"
        except Exception:
            pass
    label = "成交金额" if direction == "buy" else "成交/平仓金额"
    lines.append(f"- {label}：{value_part}")

    reason = (event.get("reason") or "").strip()
    if reason:
        lines.append(f"- 核心理由：{_truncate(reason, 80)}")

    risk_flags = event.get("ai_risk_flags") or []
    if isinstance(risk_flags, list) and risk_flags:
        rf = risk_flags[0]
        rf_text = rf if isinstance(rf, str) else _format_value(rf, 80)
        lines.append(f"- 关键风险：{_truncate(rf_text, 80)}")
    return "\n".join(lines) + "\n"


def _build_identity_block(event: Dict[str, Any]) -> str:
    """模拟盘 / 策略 / 日期 / 运行ID。"""
    lines = []
    paper_id = event.get("paper_id")
    paper_name = event.get("paper_name")
    if paper_name:
        lines.append(f"- 模拟盘：{paper_name}（#{paper_id}）" if paper_id else f"- 模拟盘：{paper_name}")
    elif paper_id:
        lines.append(f"- 模拟盘：#{paper_id}")
    strategy_name = event.get("strategy_name") or event.get("strategy_code")
    if strategy_name:
        lines.append(f"- 策略：{strategy_name}")
    if event.get("trade_date"):
        lines.append(f"- 交易日：{event.get('trade_date')}")
    if event.get("run_id"):
        lines.append(f"- 运行 ID：{event.get('run_id')}")
    if not lines:
        return ""
    return "\n## 标的与运行\n\n" + "\n".join(lines) + "\n"


def _build_execution_block(event: Dict[str, Any]) -> str:
    """成交信息：与文档 §7.1 / §7.2 一一对应。"""
    direction = event.get("direction") or ""
    direction_text = _direction_label(direction)
    lines = ["\n## 成交信息\n"]
    lines.append(f"- 方向：{direction_text or '-'}")
    lines.append(f"- 成交时间：{_fmt_dt(event.get('executed_at'))}")
    lines.append(f"- 成交价：{_fmt_number(event.get('price'))}")
    try:
        amount_int = int(event.get("amount") or 0)
    except Exception:
        amount_int = 0
    lines.append(f"- 数量：{amount_int:,} 股")
    lines.append(f"- 成交金额：{_fmt_money(event.get('value'))} 元")
    if event.get("commission") is not None:
        lines.append(f"- 佣金：{_fmt_money(event.get('commission'))} 元")
    tax_v = event.get("tax")
    # 印花税仅卖出方向通常 > 0；买入侧若为 0 则隐藏避免噪声
    if tax_v not in (None, 0, 0.0) or direction == "sell":
        lines.append(f"- 印花税：{_fmt_money(tax_v)} 元")
    if event.get("slippage_cost") is not None:
        lines.append(f"- 滑点成本：{_fmt_money(event.get('slippage_cost'))} 元")
    pos_after = event.get("position_after_pct")
    if pos_after is not None:
        try:
            v = float(pos_after)
            pct = v * 100 if v <= 1.5 else v
            lines.append(f"- 成交后仓位：{pct:.2f}%")
        except Exception:
            pass
    if direction == "sell":
        cp = event.get("close_profit")
        if cp is not None:
            try:
                cp_v = float(cp)
                lines.append(f"- 平仓盈亏：{'+' if cp_v >= 0 else ''}{_fmt_money(cp_v)} 元")
            except Exception:
                pass
        rr = event.get("return_rate")
        if rr is not None:
            try:
                rr_v = float(rr)
                lines.append(f"- 收益率：{'+' if rr_v >= 0 else ''}{rr_v:.2f}%")
            except Exception:
                pass
    if event.get("dedupe_key"):
        lines.append(f"- 事件去重：{event.get('dedupe_key')}")
    return "\n".join(lines) + "\n"


def _build_link_block(event: Dict[str, Any]) -> str:
    """末尾详情链接。base url 来自 ``INSTOCK_WEB_BASE_URL``，未配置时省略。"""
    import os
    base = (os.environ.get("INSTOCK_WEB_BASE_URL") or "").rstrip("/")
    if not base:
        return ""
    paper_id = event.get("paper_id")
    signal_id = event.get("signal_id")
    lines = ["\n## 查看详情\n"]
    if paper_id:
        lines.append(f"- 模拟盘详情：{base}/algo/paper?id={paper_id}")
    if signal_id:
        lines.append(f"- 信号详情：{base}/trade/signal?signal_id={signal_id}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines) + "\n"


def build_trade_markdown(event: Dict[str, Any]) -> Dict[str, str]:
    direction = event.get("direction") or ""
    direction_text = _direction_label(direction)
    code = event.get("code") or "-"
    name = event.get("name") or ""
    stock_label = f"{code} {name}".strip()
    # §7.1 / §7.2 标题：【模拟盘买入信号】CODE NAME
    title = f"【模拟盘{direction_text}信号】{stock_label}".strip() if direction_text \
        else f"【模拟盘交易信号】{stock_label}".strip()

    summary = _build_summary_block(event)
    identity_block = _build_identity_block(event)
    reason_block = _build_reason_block(event)
    decision_block = _build_decision_block(event)
    ai_block = _build_ai_block(event)
    execution_block = _build_execution_block(event)
    link_block = _build_link_block(event)

    footer_lines = []
    if event.get("signal_id"):
        footer_lines.append(f"\n> 信号 ID：{event.get('signal_id')} | 通知摘要在前、详情在后；完整指标快照与 AI 证据请到系统详情页查看。")
    else:
        footer_lines.append("\n> 通知摘要在前、详情在后；完整指标快照与 AI 证据请到系统详情页查看。")
    footer = "\n".join(footer_lines)

    # §7 章节顺序：标题 -> 摘要 -> 标的与运行 -> 理由 -> 决策对比 -> AI -> 详情(成交信息) -> 链接 -> 脚注
    # NOTE: 必须保留 "## 摘要" 在 "## 详情" 之前（旧测试断言）；为了兼容把成交信息标题命名为 "## 详情"
    # 由 _build_execution_block 输出，保持 anchor 不变。
    body = (
        summary
        + identity_block
        + reason_block
        + decision_block
        + ai_block
        # 成交信息块标题改为 "## 详情" 以兼容现有 phase1/phase2/phase4 用例
        + execution_block.replace("## 成交信息", "## 详情", 1)
        + link_block
        + footer
    )
    return {"title": title, "markdown": body}


def build_trade_text(event: Dict[str, Any]) -> Dict[str, str]:
    """§7.3 plain-text 降级（用于不支持 markdown 表格的渠道）。

    暂未在生产链路使用（DingTalk 一期统一走 markdown），先暴露 API 供后续 wecom/qq 适配。
    """
    md = build_trade_markdown(event)["markdown"]
    # 简单去除 markdown 标记
    plain = (
        md.replace("## ", "").replace("# ", "")
          .replace("|---|---|---|---|", "").replace("**", "").replace("> ", "")
    )
    return {"title": build_trade_markdown(event)["title"], "text": plain}
