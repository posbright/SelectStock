#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import datetime
import hashlib
import hmac
import json
from urllib.parse import quote_plus

from instock.core.backtest.strategy_context import TradeRecord
from instock.notification.channels.dingtalk import DingTalkChannel
from instock.notification.service import build_trade_dedupe_key, notify_trade_records
from instock.notification.templates import build_trade_markdown


def test_dingtalk_signed_url_matches_official_algorithm():
    webhook = "https://oapi.dingtalk.com/robot/send?access_token=abc"
    secret = "SEC-test"
    timestamp = 1760000000000
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected_sign = quote_plus(base64.b64encode(digest))

    signed_url = DingTalkChannel.build_signed_url(webhook, secret, timestamp)

    assert f"timestamp={timestamp}" in signed_url
    assert f"sign={expected_sign}" in signed_url


def test_trade_markdown_summary_is_before_details():
    message = build_trade_markdown({
        "paper_id": 4,
        "trade_date": "2026-04-30",
        "executed_at": datetime.datetime(2026, 4, 30, 15, 1),
        "code": "600016",
        "name": "民生银行",
        "direction": "buy",
        "price": 4.321,
        "amount": 1000,
        "value": 4321,
        "dedupe_key": "abc",
    })

    assert "## 摘要" in message["markdown"]
    assert "## 详情" in message["markdown"]
    assert message["markdown"].index("## 摘要") < message["markdown"].index("## 详情")
    assert "600016 民生银行" in message["markdown"]


def test_trade_dedupe_key_is_stable_and_channel_scoped():
    trade = TradeRecord(datetime.date(2026, 4, 30), "600016", "民生银行", "buy", 4.32, 1000)

    key1 = build_trade_dedupe_key(4, trade, "2026-04-30", "dingtalk")
    key2 = build_trade_dedupe_key(4, trade, "2026-04-30", "dingtalk")
    key3 = build_trade_dedupe_key(4, trade, "2026-04-30", "other")

    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 64


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self.rowcount = 0
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=()):
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("INSERT IGNORE"):
            dedupe_key = params[0]
            if dedupe_key in self.state["dedupe"]:
                self.rowcount = 0
            else:
                self.state["dedupe"].add(dedupe_key)
                self.state["last_id"] += 1
                self.rowcount = 1
                self.state["events"].append({
                    "id": self.state["last_id"],
                    "dedupe_key": dedupe_key,
                    "status": params[7],
                    "payload": json.loads(params[8]),
                    "error": params[9],
                })
        elif sql_upper.startswith("SELECT LAST_INSERT_ID"):
            self._row = (self.state["last_id"],)
        elif sql_upper.startswith("UPDATE"):
            self.state["updates"].append((sql, params))
            self.rowcount = 1

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return _FakeCursor(self.state)


def test_enqueue_creates_skipped_event_and_dedupes_without_webhook(monkeypatch):
    import instock.lib.database as mdb
    import instock.notification.service as service

    state = {"dedupe": set(), "last_id": 0, "events": [], "updates": []}
    monkeypatch.delenv("INSTOCK_DINGTALK_WEBHOOK", raising=False)
    monkeypatch.setattr(mdb, "checkTableIsExist", lambda table: True)
    monkeypatch.setattr(mdb, "executeSql", lambda sql, params=(): state["updates"].append((sql, params)))
    monkeypatch.setattr(mdb, "executeSqlFetch", lambda sql, params=(): [])
    monkeypatch.setattr(mdb, "get_connection", lambda: _FakeConnection(state))

    trade = TradeRecord(datetime.date(2026, 4, 30), "600016", "民生银行", "buy", 4.32, 1000)
    first = service.enqueue_trade_notification(4, trade, "2026-04-30", send_now=True)
    second = service.enqueue_trade_notification(4, trade, "2026-04-30", send_now=True)

    assert first["created"] is True
    assert first["status"] == "skipped"
    assert second["created"] is False
    assert len(state["events"]) == 1
    assert state["events"][0]["payload"]["msgtype"] == "markdown"


def test_notify_trade_records_isolation_when_single_event_raises(monkeypatch):
    import instock.notification.service as service

    trade = TradeRecord(datetime.date(2026, 4, 30), "600016", "民生银行", "sell", 4.32, 1000)

    def _raise(*args, **kwargs):
        raise RuntimeError("webhook down")

    monkeypatch.setattr(service, "enqueue_trade_notification", _raise)

    stats = notify_trade_records(4, [trade], "2026-04-30")

    assert stats["failed"] == 1
    assert stats["created"] == 0
    assert stats["sent"] == 0


def test_process_pending_notifications_sends_due_outbox_event(monkeypatch):
    import instock.lib.database as mdb
    import instock.notification.service as service

    payload = {"msgtype": "markdown", "markdown": {"title": "t", "text": "body"}}
    calls = []

    monkeypatch.setattr(service, "ensure_notification_tables", lambda: None)
    monkeypatch.setattr(
        mdb,
        "executeSqlFetch",
        lambda sql, params=(): [(11, 4, "paper_trade", json.dumps(payload, ensure_ascii=False))]
        if "payload_json" in sql else [("sent",)],
    )
    monkeypatch.setattr(
        service,
        "_send_payload_for_event",
        lambda event_id, paper_id, event_type, event_payload: calls.append(
            (event_id, paper_id, event_type, event_payload)
        ) or True,
    )

    stats = service.process_pending_notifications(limit=5)

    assert stats == {"processed": 1, "sent": 1, "failed": 0, "skipped": 0}
    assert calls == [(11, 4, "paper_trade", payload)]