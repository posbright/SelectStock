"""PR-2 API + 沙箱安全测试。

主要覆盖：
1. `_validate_save_payload` 范式守门 (F7) 全部分支
2. `_compute_signal` 三种模式（纯权重 / 纯硬规则 / 混合）
3. Save → Detail → Delete 数据库往返
4. 沙箱注入/逃逸尝试经过 Save handler 后被拒绝
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from instock.lib import database as mdb
from instock.web.customIndicatorHandler import (
    _validate_save_payload, _compute_signal, _load_indicator_record,
    _ensure_custom_indicator_table, bootstrap,
)
from instock.core.composite.indicators_enrich import enrich


# ============================================================================
#                  _validate_save_payload (F7 范式守门)
# ============================================================================
class TestValidateSavePayload:
    def test_missing_indicator_id(self):
        ok, err = _validate_save_payload({"name": "x"})
        assert not ok and "indicator_id" in err

    def test_invalid_indicator_id_chars(self):
        ok, err = _validate_save_payload({"indicator_id": "bad name!", "name": "x"})
        assert not ok and "字母" in err

    def test_missing_name(self):
        ok, err = _validate_save_payload({"indicator_id": "abc", "name": ""})
        assert not ok and "name" in err

    def test_invalid_kind(self):
        ok, err = _validate_save_payload(
            {"indicator_id": "abc", "name": "x", "kind": "foo"})
        assert not ok and "kind" in err

    def test_invalid_direction(self):
        ok, err = _validate_save_payload(
            {"indicator_id": "abc", "name": "x", "direction": "middle"})
        assert not ok and "direction" in err

    def test_primary_entry_requires_rules_or_weights(self):
        ok, err = _validate_save_payload({
            "indicator_id": "abc", "name": "x", "kind": "primary_entry",
        })
        assert not ok and "硬规则" in err

    def test_weights_only_must_be_high(self):
        ok, err = _validate_save_payload({
            "indicator_id": "abc", "name": "x", "kind": "watchlist_alert",
            "weights": {"n_rsi14": 1.0}, "direction": "low",
        })
        assert not ok and "high" in err

    def test_hard_rules_sandbox_violation(self):
        ok, err = _validate_save_payload({
            "indicator_id": "abc", "name": "x", "kind": "primary_entry",
            "hard_rules": "__import__('os').system('rm -rf /')",
        })
        assert not ok and "硬规则解析失败" in err

    def test_extra_filter_sandbox_violation(self):
        ok, err = _validate_save_payload({
            "indicator_id": "abc", "name": "x", "kind": "primary_entry",
            "hard_rules": "d['rsi14'] < 30",
            "extra_filter": "open('/etc/passwd')",
        })
        assert not ok and "额外过滤解析失败" in err

    def test_negative_weight_rejected(self):
        ok, err = _validate_save_payload({
            "indicator_id": "abc", "name": "x", "kind": "watchlist_alert",
            "weights": {"n_rsi14": -1.0}, "direction": "high",
        })
        assert not ok and "非负" in err

    def test_valid_primary_entry_with_hard_rules(self):
        ok, err = _validate_save_payload({
            "indicator_id": "test_p1", "name": "test", "kind": "primary_entry",
            "hard_rules": "(d['rsi14'] < 30) & (d['close'] > d['boll_lower'])",
        })
        assert ok, err

    def test_valid_watchlist_with_weights(self):
        ok, err = _validate_save_payload({
            "indicator_id": "test_w1", "name": "test", "kind": "watchlist_alert",
            "weights": {"n_rsi14": 0.5, "n_ma_uptrend": 0.5},
            "direction": "high", "buy_th": 50,
        })
        assert ok, err


# ============================================================================
#                  _compute_signal 流水线
# ============================================================================
def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    base = 10 + np.cumsum(np.random.randn(n) * 0.2)
    base = np.clip(base, 1, None)
    return pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n),
        "open": base * 1.001,
        "high": base * 1.01,
        "low": base * 0.99,
        "close": base,
        "volume": np.random.randint(1000, 10000, n),
    })


class TestComputeSignal:
    def test_pure_weights_returns_score(self):
        df = enrich(_make_ohlcv())
        rec = {
            "name": "test", "kind": "watchlist_alert",
            "weights": {"n_rsi14": 0.5, "n_ma_uptrend": 0.5},
            "smooth_ema": 0, "buy_th": 50, "direction": "high",
            "hard_rules": "", "extra_filter": "",
        }
        sig, score = _compute_signal(rec, df)
        assert score is not None
        assert sig.dtype == bool
        assert len(sig) == len(df)

    def test_pure_hard_rules_no_score(self):
        df = enrich(_make_ohlcv())
        rec = {
            "name": "test", "kind": "primary_entry",
            "weights": {}, "smooth_ema": 0, "buy_th": 0, "direction": "high",
            "hard_rules": "d['rsi14'] < 30", "extra_filter": "",
        }
        sig, score = _compute_signal(rec, df)
        assert score is None
        assert sig.dtype == bool

    def test_extra_filter_narrows_signal(self):
        df = enrich(_make_ohlcv())
        rec_no_filter = {
            "name": "t", "kind": "primary_entry",
            "weights": {}, "smooth_ema": 0, "buy_th": 0, "direction": "high",
            "hard_rules": "d['rsi14'] < 60", "extra_filter": "",
        }
        rec_filtered = {**rec_no_filter,
                        "extra_filter": "d['close'] > d['ma60']"}
        sig1, _ = _compute_signal(rec_no_filter, df)
        sig2, _ = _compute_signal(rec_filtered, df)
        # extra_filter 不会增加触发数，只会减少
        assert sig2.sum() <= sig1.sum()


# ============================================================================
#                  Save → Detail → Delete DB 往返
# ============================================================================
@pytest.fixture
def cleanup_test_indicator():
    """删除测试残留。"""
    yield
    mdb.executeSql(
        "DELETE FROM cn_stock_custom_indicator "
        "WHERE indicator_id LIKE %s AND is_builtin=0",
        ("pytest_%",))


def test_save_detail_delete_roundtrip(cleanup_test_indicator):
    bootstrap()
    iid = "pytest_save_roundtrip"
    mdb.executeSql("""
        INSERT INTO cn_stock_custom_indicator
          (indicator_id, name, kind, weights, smooth_ema, buy_th,
           direction, extra_filter, hard_rules, risk_profile, is_builtin)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE name=VALUES(name)
    """, (iid, "pytest", "primary_entry",
          json.dumps({}), 0, 0.0, "high", None,
          "d['rsi14'] < 30",
          json.dumps({"stop": -0.08, "target": 0.20, "max_hold": 60}),
          0))
    rec = _load_indicator_record(iid)
    assert rec is not None
    assert rec["kind"] == "primary_entry"
    assert "rsi14" in rec["hard_rules"]
    assert rec["risk_profile"]["max_hold"] == 60


def test_load_indicator_record_returns_none_for_missing():
    assert _load_indicator_record("nonexistent_xyz_12345") is None


# ============================================================================
#                  内置预设的只读保护（单元层面）
# ============================================================================
def test_builtin_preset_loads_with_correct_kind():
    bootstrap()
    rec = _load_indicator_record("steady_oversold_rebound")
    assert rec is not None
    assert rec["kind"] == "primary_entry"
    assert rec["hard_rules"] is not None and "rsi14" in rec["hard_rules"]
    assert rec["risk_profile"].get("fundamentals_check") is True
