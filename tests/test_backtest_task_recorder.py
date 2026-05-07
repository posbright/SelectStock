"""Tests for instock.core.backtest.task_recorder.

Uses monkeypatching to avoid hitting real DB.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from instock.core.backtest import task_recorder as tr


class _FakeCursor:
    def __init__(self, store):
        self.store = store
        self.lastrowid = None

    def execute(self, sql, params=None):
        self.store['executed'].append((sql, params))
        if 'LAST_INSERT_ID' in sql:
            self.store['fetched'] = (123,)

    def fetchone(self):
        return self.store.get('fetched')

    def fetchall(self):
        return self.store.get('rows', [])

    def __enter__(self): return self
    def __exit__(self, *a): pass


class _FakeConn:
    def __init__(self, store):
        self.store = store

    def cursor(self):
        return _FakeCursor(self.store)

    def __enter__(self): return self
    def __exit__(self, *a): pass


def _patch_db(store):
    return patch('instock.core.backtest.task_recorder.mdb.get_connection',
                 return_value=_FakeConn(store))


def test_record_completed_inserts_with_metrics():
    store = {'executed': []}
    with _patch_db(store), patch.object(tr, '_ensure_table', lambda: None):
        bt_id = tr.record_completed(
            strategy_id=1, strategy_name='S', start_date='2024-01-01',
            end_date='2024-12-31', initial_cash=100000, benchmark='000300',
            result={'status': 'completed', 'metrics': {'total_return': 0.12, 'sharpe_ratio': 1.5}},
        )
    assert bt_id == 123
    sql, params = store['executed'][0]
    assert 'INSERT INTO cn_stock_backtest_portfolio' in sql
    assert 'completed' in params  # status


def test_record_failed_writes_error_message_and_payload():
    store = {'executed': []}
    with _patch_db(store), patch.object(tr, '_ensure_table', lambda: None):
        bt_id = tr.record_failed(
            strategy_id=2, strategy_name='S2', start_date='2024-01-01',
            end_date='2024-06-30', initial_cash=50000, benchmark='000300',
            error_text='ZeroDivisionError', traceback_text='Traceback...\nfoo',
        )
    assert bt_id == 123
    sql, params = store['executed'][0]
    assert 'INSERT INTO cn_stock_backtest_portfolio' in sql
    assert 'failed' in params
    # error_message 字段必须包含 traceback
    assert any('Traceback' in str(p) for p in params)


def test_record_failed_truncates_long_error():
    store = {'executed': []}
    huge = 'x' * 50000
    with _patch_db(store), patch.object(tr, '_ensure_table', lambda: None):
        tr.record_failed(
            strategy_id=3, strategy_name=None, start_date='2024-01-01',
            end_date='2024-06-30', initial_cash=50000, benchmark='000300',
            error_text='boom', traceback_text=huge,
        )
    sql, params = store['executed'][0]
    long_field = next((p for p in params if isinstance(p, str) and 'x' * 100 in p), '')
    assert long_field
    assert len(long_field) <= tr._MAX_ERROR_LEN


def test_fetch_last_failure_returns_none_when_no_strategy_id():
    assert tr.fetch_last_failure(None) is None


def test_fetch_last_failure_parses_row():
    fake_rows = [(99, 'started', 'completed', 'NameError: g')]
    with patch('instock.core.backtest.task_recorder.mdb.executeSqlFetch',
               return_value=fake_rows):
        out = tr.fetch_last_failure(7)
    assert out == {
        'id': 99, 'started_at': 'started', 'completed_at': 'completed',
        'error_message': 'NameError: g',
    }


def test_fetch_last_failure_handles_empty():
    with patch('instock.core.backtest.task_recorder.mdb.executeSqlFetch',
               return_value=[]):
        assert tr.fetch_last_failure(7) is None


def test_fetch_last_failure_handles_db_error():
    with patch('instock.core.backtest.task_recorder.mdb.executeSqlFetch',
               side_effect=RuntimeError('db down')):
        assert tr.fetch_last_failure(7) is None
