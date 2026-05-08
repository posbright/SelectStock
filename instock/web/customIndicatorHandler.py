"""
自定义综合指标 — DDL + 内置预设 seed（PR-1 后端基础）。

仅提供：
- `_ensure_custom_indicator_table()`  幂等建表
- `_seed_builtin_indicators()`         写入/更新三条内置预设
- `bootstrap()`                        启动时一次性调用

PR-2 / PR-3 会在此基础上挂 RequestHandler。
"""
from __future__ import annotations

import json
import logging

from instock.lib import database as mdb
from instock.core.composite.builtins import BUILTIN_PRESETS

_table_ready = False


def _ensure_custom_indicator_table() -> None:
    """幂等建表 — 详细字段见 phase9 dev plan §2.1。"""
    global _table_ready
    if _table_ready:
        return
    if not mdb.checkTableIsExist("cn_stock_custom_indicator"):
        mdb.executeSql("""
            CREATE TABLE IF NOT EXISTS `cn_stock_custom_indicator` (
              `id` INT AUTO_INCREMENT PRIMARY KEY,
              `indicator_id` VARCHAR(64) NOT NULL UNIQUE COMMENT '业务键（builtin 用稳定字符串）',
              `name` VARCHAR(200) NOT NULL,
              `kind` ENUM('primary_entry','watchlist_alert') NOT NULL DEFAULT 'watchlist_alert',
              `description` TEXT,
              `weights` JSON COMMENT '{字段名: 权重} 评分用',
              `smooth_ema` INT DEFAULT 0,
              `buy_th` DECIMAL(10,4) DEFAULT 0,
              `direction` ENUM('low','high') DEFAULT 'high',
              `extra_filter` TEXT COMMENT '可选 AST 表达式（与 hard_rules 同沙箱）',
              `hard_rules` TEXT COMMENT '硬规则 AST 表达式（替代/补充评分）',
              `risk_profile` JSON COMMENT '止损/止盈/最大持有/基本面卖出阈值',
              `is_builtin` TINYINT(1) DEFAULT 0,
              `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
              `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              INDEX `idx_kind` (`kind`),
              INDEX `idx_builtin` (`is_builtin`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        logging.info("[custom_indicator] 已创建表 cn_stock_custom_indicator")
    _table_ready = True


def _seed_builtin_indicators() -> int:
    """
    写入/更新三条内置预设（用 ON DUPLICATE KEY UPDATE）。
    返回受影响行数。
    """
    _ensure_custom_indicator_table()
    affected = 0
    sql = """
        INSERT INTO cn_stock_custom_indicator
          (indicator_id, name, kind, description, weights, smooth_ema, buy_th,
           direction, extra_filter, hard_rules, risk_profile, is_builtin)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          name=VALUES(name), kind=VALUES(kind), description=VALUES(description),
          weights=VALUES(weights), smooth_ema=VALUES(smooth_ema), buy_th=VALUES(buy_th),
          direction=VALUES(direction), extra_filter=VALUES(extra_filter),
          hard_rules=VALUES(hard_rules), risk_profile=VALUES(risk_profile),
          is_builtin=VALUES(is_builtin)
    """
    for p in BUILTIN_PRESETS:
        params = (
            p["indicator_id"], p["name"], p["kind"], p.get("description"),
            json.dumps(p.get("weights") or {}, ensure_ascii=False),
            int(p.get("smooth_ema", 0)),
            float(p.get("buy_th", 0)),
            p.get("direction", "high"),
            p.get("extra_filter"),
            p.get("hard_rules"),
            json.dumps(p.get("risk_profile") or {}, ensure_ascii=False),
            int(p.get("is_builtin", 1)),
        )
        try:
            mdb.executeSql(sql, params)
            affected += 1
        except Exception as e:
            logging.error(f"[custom_indicator] seed {p['indicator_id']} 失败: {e}")
    return affected


def bootstrap() -> None:
    _ensure_custom_indicator_table()
    n = _seed_builtin_indicators()
    logging.info(f"[custom_indicator] seeded {n} builtin presets")


__all__ = [
    "_ensure_custom_indicator_table",
    "_seed_builtin_indicators",
    "bootstrap",
]
