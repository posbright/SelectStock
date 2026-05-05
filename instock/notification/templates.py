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
    details = (
        f"\n## 详情\n\n"
        f"- 成交时间：{_fmt_dt(event.get('executed_at'))}\n"
        f"- 佣金：{_fmt_money(event.get('commission'))}\n"
        f"- 印花税：{_fmt_money(event.get('tax'))}\n"
        f"- 事件去重：{event.get('dedupe_key') or '-'}\n"
        f"\n> 本通知来自模拟交易成交落库后的 outbox 事件。策略详细指标与 AI 评分将在后续阶段接入。"
    )
    return {"title": title, "markdown": summary + details}