# -*- coding: utf-8 -*-
"""Phase 2 — 交易信号 / 决策明细 / 指标快照 / 候选筛选快照 持久化。

本模块只负责落库，绝不调用通知或交易主流程。设计要点：

- DDL 与 ``_ensure_*_table`` 在首次写入时按需创建，遵循项目其它表 (``cn_stock_paper_trading`` 等) 的迁移风格。
- 整体写入用单独事务；任意步骤异常都不会传播到调用方（策略主事务），仅记录 warning。
- ``persist_signal_with_relations`` 是聚合入口：写 signal -> decision -> indicator_snapshot -> selection_snapshot。
- ``link_signal_to_trade`` 在 ``cn_stock_backtest_trade`` 行入库后回填 ``trade_id``。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from .trade_decision import serialize_for_db

SIGNAL_TABLE = "cn_stock_trade_signal"
DECISION_TABLE = "cn_stock_trade_decision"
INDICATOR_SNAPSHOT_TABLE = "cn_stock_trade_indicator_snapshot"
SELECTION_SNAPSHOT_TABLE = "cn_stock_trade_selection_snapshot"

_TABLES_ENSURED = False


def _get_db():
    import instock.lib.database as mdb  # 延迟导入，避免测试 import 时连库
    return mdb


def ensure_trade_signal_tables():
    """幂等创建 4 张 Phase 2 表。若 mdb 不可用直接返回（测试场景）。"""
    global _TABLES_ENSURED
    if _TABLES_ENSURED:
        return
    try:
        mdb = _get_db()
    except Exception as exc:
        logging.debug("[trade_signal_store] database 模块加载失败，跳过表创建: %s", exc)
        return

    ddls = [
        # 与 dev_plan §5.1 一致；AI 相关列在 Phase 4 写入，本期保持 NULL。
        f"""
        CREATE TABLE IF NOT EXISTS `{SIGNAL_TABLE}` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `source_type` VARCHAR(32) NOT NULL COMMENT 'backtest/paper/live',
            `source_id` BIGINT NOT NULL COMMENT '回测ID、模拟盘ID或实盘策略ID',
            `run_id` VARCHAR(64) DEFAULT NULL COMMENT '单次运行ID',
            `strategy_id` BIGINT DEFAULT NULL,
            `strategy_name` VARCHAR(128) DEFAULT NULL,
            `trade_id` BIGINT DEFAULT NULL COMMENT '成交记录ID，撮合后回填',
            `signal_date` DATE NOT NULL,
            `code` VARCHAR(20) NOT NULL,
            `name` VARCHAR(64) DEFAULT NULL,
            `direction` VARCHAR(16) NOT NULL COMMENT 'buy/sell',
            `order_api` VARCHAR(64) DEFAULT NULL,
            `requested_amount` DECIMAL(20,4) DEFAULT NULL COMMENT '策略请求数量变化',
            `requested_value` DECIMAL(20,4) DEFAULT NULL COMMENT '策略请求金额变化',
            `target_amount` DECIMAL(20,4) DEFAULT NULL COMMENT '目标持仓数量',
            `target_percent` DECIMAL(12,6) DEFAULT NULL COMMENT '目标仓位比例',
            `reason` TEXT DEFAULT NULL,
            `reason_source` VARCHAR(32) DEFAULT 'strategy' COMMENT 'strategy/generated/manual/imported',
            `ai_score_id` BIGINT DEFAULT NULL COMMENT 'Phase4关联 cn_stock_trade_ai_score.id',
            `ai_score` DECIMAL(8,4) DEFAULT NULL,
            `ai_action` VARCHAR(32) DEFAULT NULL,
            `ai_gate_result` VARCHAR(32) DEFAULT NULL COMMENT 'not_enabled/pass/reject/fallback/error',
            `signal_hash` VARCHAR(64) NOT NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY `uk_signal_hash` (`signal_hash`),
            KEY `idx_source_run` (`source_type`, `source_id`, `run_id`),
            KEY `idx_trade_id` (`trade_id`),
            KEY `idx_ai_score_id` (`ai_score_id`),
            KEY `idx_code_date` (`code`, `signal_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略交易信号表'
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{DECISION_TABLE}` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `signal_id` BIGINT NOT NULL,
            `rule_group` VARCHAR(64) DEFAULT NULL,
            `rule_name` VARCHAR(128) NOT NULL,
            `indicator_key` VARCHAR(64) DEFAULT NULL,
            `threshold_expr` VARCHAR(255) DEFAULT NULL,
            `threshold_value` JSON DEFAULT NULL,
            `actual_value` JSON DEFAULT NULL,
            `passed` TINYINT(1) DEFAULT NULL,
            `weight` DECIMAL(10,4) DEFAULT NULL,
            `score` DECIMAL(10,4) DEFAULT NULL,
            `note` TEXT DEFAULT NULL,
            `sort_order` INT DEFAULT 0,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY `idx_signal_id` (`signal_id`),
            KEY `idx_rule_group` (`signal_id`, `rule_group`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        # 与 dev_plan §5.3 一致：结构化 OHLCV + 各指标 JSON。
        f"""
        CREATE TABLE IF NOT EXISTS `{INDICATOR_SNAPSHOT_TABLE}` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `signal_id` BIGINT NOT NULL,
            `period` VARCHAR(16) DEFAULT 'daily' COMMENT 'daily/weekly/monthly',
            `kline_date` DATE DEFAULT NULL COMMENT '指标对应K线日期',
            `open` DECIMAL(20,6) DEFAULT NULL,
            `high` DECIMAL(20,6) DEFAULT NULL,
            `low` DECIMAL(20,6) DEFAULT NULL,
            `close` DECIMAL(20,6) DEFAULT NULL,
            `volume` DECIMAL(24,4) DEFAULT NULL,
            `amount` DECIMAL(24,4) DEFAULT NULL,
            `ma` JSON DEFAULT NULL,
            `boll` JSON DEFAULT NULL,
            `rsi` JSON DEFAULT NULL,
            `macd` JSON DEFAULT NULL,
            `kdj` JSON DEFAULT NULL,
            `extra` JSON DEFAULT NULL COMMENT '策略自定义指标',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY `uk_signal_period` (`signal_id`, `period`),
            KEY `idx_signal_date` (`signal_id`, `kline_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易时点指标快照表'
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{SELECTION_SNAPSHOT_TABLE}` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `signal_id` BIGINT NOT NULL,
            `stage` VARCHAR(64) NOT NULL,
            `candidate_count_before` INT DEFAULT NULL,
            `candidate_count_after` INT DEFAULT NULL,
            `rank_value` DECIMAL(20,6) DEFAULT NULL,
            `rank_position` INT DEFAULT NULL,
            `filter_expr` VARCHAR(255) DEFAULT NULL,
            `actual_value` JSON DEFAULT NULL,
            `passed` TINYINT(1) DEFAULT NULL,
            `note` TEXT DEFAULT NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY `idx_signal_stage` (`signal_id`, `stage`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]
    for ddl in ddls:
        try:
            mdb.executeSql(ddl)
        except Exception as exc:
            logging.warning("[trade_signal_store] 建表失败(将在下次写入时重试): %s", exc)
            return
    _TABLES_ENSURED = True


def persist_signal_with_relations(
    *,
    source_type: str,
    source_id: int,
    run_id: Optional[str],
    strategy_id: Optional[int],
    strategy_name: Optional[str],
    signal_date,
    code: str,
    name: Optional[str],
    direction: str,
    order_api: Optional[str],
    requested_amount: Optional[float],
    requested_value: Optional[float],
    reason: str,
    reason_source: str,
    signal_hash: str,
    target_amount: Optional[float] = None,
    target_percent: Optional[float] = None,
    decision_rules: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[Dict[str, Any]] = None,
    selection: Optional[List[Dict[str, Any]]] = None,
) -> Optional[int]:
    """聚合写入。返回 signal_id 或 None（失败时静默，不抛出）。"""
    try:
        ensure_trade_signal_tables()
        mdb = _get_db()
    except Exception as exc:
        logging.debug("[trade_signal_store] 跳过持久化(无法获取 DB): %s", exc)
        return None

    try:
        with mdb.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO `{SIGNAL_TABLE}` "
                    "(source_type, source_id, run_id, strategy_id, strategy_name, "
                    " signal_date, code, name, direction, order_api, "
                    " requested_amount, requested_value, target_amount, target_percent, "
                    " reason, reason_source, signal_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE reason=VALUES(reason), reason_source=VALUES(reason_source), "
                    " requested_amount=VALUES(requested_amount), requested_value=VALUES(requested_value), "
                    " target_amount=VALUES(target_amount), target_percent=VALUES(target_percent), "
                    " strategy_name=VALUES(strategy_name)",
                    (
                        source_type, int(source_id or 0), run_id, strategy_id, strategy_name,
                        signal_date, code, name, direction, order_api,
                        requested_amount, requested_value, target_amount, target_percent,
                        reason, reason_source, signal_hash,
                    ),
                )
                cur.execute(
                    f"SELECT id FROM `{SIGNAL_TABLE}` WHERE signal_hash=%s LIMIT 1",
                    (signal_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                signal_id = int(row[0])

                # decision rules
                if decision_rules:
                    cur.execute(f"DELETE FROM `{DECISION_TABLE}` WHERE signal_id=%s", (signal_id,))
                    for rule in decision_rules:
                        cur.execute(
                            f"INSERT INTO `{DECISION_TABLE}` "
                            "(signal_id, rule_group, rule_name, indicator_key, threshold_expr, "
                            " threshold_value, actual_value, passed, weight, score, note, sort_order) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                signal_id, rule.get("rule_group"), rule.get("rule_name"),
                                rule.get("indicator_key"), rule.get("threshold_expr"),
                                serialize_for_db(rule.get("threshold_value")),
                                serialize_for_db(rule.get("actual_value")),
                                rule.get("passed"), rule.get("weight"), rule.get("score"),
                                rule.get("note"), int(rule.get("sort_order") or 0),
                            ),
                        )

                # indicator snapshot：拆分 OHLCV / ma / boll / rsi / macd / kdj / extra
                if indicators:
                    ind = indicators if isinstance(indicators, dict) else {}
                    ohlcv_keys = {"open", "high", "low", "close", "volume", "amount"}
                    json_keys = {"ma", "boll", "rsi", "macd", "kdj"}
                    extra = {k: v for k, v in ind.items()
                            if k not in ohlcv_keys and k not in json_keys and k != "kline_date"}
                    cur.execute(
                        f"INSERT INTO `{INDICATOR_SNAPSHOT_TABLE}` "
                        "(signal_id, period, kline_date, `open`, high, low, `close`, volume, amount, "
                        " ma, boll, rsi, macd, kdj, extra) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE kline_date=VALUES(kline_date), "
                        " `open`=VALUES(`open`), high=VALUES(high), low=VALUES(low), `close`=VALUES(`close`), "
                        " volume=VALUES(volume), amount=VALUES(amount), "
                        " ma=VALUES(ma), boll=VALUES(boll), rsi=VALUES(rsi), macd=VALUES(macd), "
                        " kdj=VALUES(kdj), extra=VALUES(extra)",
                        (
                            signal_id, "daily", ind.get("kline_date") or signal_date,
                            ind.get("open"), ind.get("high"), ind.get("low"), ind.get("close"),
                            ind.get("volume"), ind.get("amount"),
                            serialize_for_db(ind.get("ma")),
                            serialize_for_db(ind.get("boll")),
                            serialize_for_db(ind.get("rsi")),
                            serialize_for_db(ind.get("macd")),
                            serialize_for_db(ind.get("kdj")),
                            serialize_for_db(extra) if extra else None,
                        ),
                    )

                # selection snapshot
                if selection:
                    cur.execute(f"DELETE FROM `{SELECTION_SNAPSHOT_TABLE}` WHERE signal_id=%s", (signal_id,))
                    for stage in selection:
                        cur.execute(
                            f"INSERT INTO `{SELECTION_SNAPSHOT_TABLE}` "
                            "(signal_id, stage, candidate_count_before, candidate_count_after, "
                            " rank_value, rank_position, filter_expr, actual_value, passed, note) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                signal_id, stage.get("stage"),
                                stage.get("candidate_count_before"), stage.get("candidate_count_after"),
                                stage.get("rank_value"), stage.get("rank_position"),
                                stage.get("filter_expr"),
                                serialize_for_db(stage.get("actual_value")),
                                stage.get("passed"), stage.get("note"),
                            ),
                        )
                conn.commit()
                return signal_id
    except Exception as exc:
        logging.warning("[trade_signal_store] persist_signal_with_relations 失败 code=%s dir=%s: %s",
                        code, direction, exc)
        return None


def link_signal_to_trade(signal_id: int, trade_id: int) -> bool:
    """成交行入库后回填 trade_id；失败仅 warning。"""
    if not signal_id or not trade_id:
        return False
    try:
        mdb = _get_db()
        mdb.executeSql(
            f"UPDATE `{SIGNAL_TABLE}` SET trade_id=%s WHERE id=%s",
            (int(trade_id), int(signal_id)),
        )
        return True
    except Exception as exc:
        logging.warning("[trade_signal_store] 回填 trade_id 失败 signal_id=%s trade_id=%s: %s",
                        signal_id, trade_id, exc)
        return False


def fetch_signal_with_decision(signal_id: int) -> Dict[str, Any]:
    """供通知模板/详情接口读取。失败返回空 dict。"""
    if not signal_id:
        return {}
    try:
        mdb = _get_db()
        signal_rows = mdb.executeSqlFetch(
            f"SELECT id, reason, reason_source, code, name, direction, signal_date, "
            f" requested_amount, requested_value, order_api FROM `{SIGNAL_TABLE}` WHERE id=%s",
            (int(signal_id),),
        ) or []
        if not signal_rows:
            return {}
        s = signal_rows[0]
        rules = mdb.executeSqlFetch(
            f"SELECT rule_group, rule_name, threshold_expr, threshold_value, actual_value, passed, note "
            f"FROM `{DECISION_TABLE}` WHERE signal_id=%s ORDER BY sort_order ASC, id ASC",
            (int(signal_id),),
        ) or []
        return {
            "signal_id": int(s[0]),
            "reason": s[1] or "",
            "reason_source": s[2] or "strategy",
            "code": s[3], "name": s[4], "direction": s[5],
            "signal_date": s[6],
            "requested_amount": s[7], "requested_value": s[8],
            "order_api": s[9],
            "rules": [
                {
                    "rule_group": r[0], "rule_name": r[1], "threshold_expr": r[2],
                    "threshold_value": r[3], "actual_value": r[4],
                    "passed": r[5], "note": r[6],
                }
                for r in rules
            ],
        }
    except Exception as exc:
        logging.warning("[trade_signal_store] 读取 signal 失败 id=%s: %s", signal_id, exc)
        return {}
