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


def build_trade_markdown(event: Dict[str, Any]) -> Dict[str, str]:
    direction = event.get("direction") or ""
    direction_text = "买入" if direction == "buy" else "卖出" if direction == "sell" else direction
    code = event.get("code") or "-"
    name = event.get("name") or ""
    stock_label = f"{code} {name}".strip()
    title = f"模拟交易{direction_text}通知 {stock_label}".strip()

    summary = (
        f"## 摘要\n\n"
        f"- 事件：模拟交易{direction_text}\n"
        f"- 标的：{stock_label}\n"
        f"- 成交：{_fmt_number(event.get('price'))} x {int(event.get('amount') or 0)}，金额 {_fmt_money(event.get('value'))}\n"
        f"- 模拟盘：#{event.get('paper_id')}，交易日：{event.get('trade_date') or '-'}\n"
    )
    reason_block = _build_reason_block(event)
    decision_block = _build_decision_block(event)
    ai_block = _build_ai_block(event)
    details = (
        f"\n## 详情\n\n"
        f"- 成交时间：{_fmt_dt(event.get('executed_at'))}\n"
        f"- 佣金：{_fmt_money(event.get('commission'))}\n"
        f"- 印花税：{_fmt_money(event.get('tax'))}\n"
        f"- 事件去重：{event.get('dedupe_key') or '-'}\n"
    )
    footer_lines = []
    if event.get("signal_id"):
        footer_lines.append(f"- 信号 ID：{event.get('signal_id')}")
    footer_lines.append(
        "\n> 通知摘要在前、详情在后；策略原始指标快照与 AI 评分将在 Phase 3+ 详情链接中查看。"
    )
    footer = "\n" + "\n".join(footer_lines) if footer_lines else ""
    return {"title": title, "markdown": summary + reason_block + decision_block + ai_block + details + footer}