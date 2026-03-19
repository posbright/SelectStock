#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive tests for instock/paper_trading/ modules.

Covers:
  - state_manager.serialize_portfolio / restore_portfolio
  - paper_engine._create_api / _ensure_*_table / _update_paper_error
  - paper_engine.run_paper_trading_daily / run_all_paper_trading
"""

import sys
import os
import json
import datetime
from unittest import mock
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from instock.core.backtest.strategy_context import (
    Context, Portfolio, Position, GlobalVars, DataProxy, TradeRecord, NavRecord,
)
from instock.paper_trading.state_manager import serialize_portfolio, restore_portfolio
from instock.paper_trading.paper_engine import (
    _create_api,
    _update_paper_error,
    _ensure_paper_table,
    _ensure_trade_table,
    _ensure_position_table,
    run_paper_trading_daily,
    run_all_paper_trading,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context_with_positions(cash=500000, positions_data=None):
    """Build a Context with optional positions for testing."""
    ctx = Context(initial_cash=1000000)
    ctx.portfolio.available_cash = cash
    ctx.current_dt = datetime.date(2026, 3, 18)
    ctx.benchmark = '000300'
    ctx.commission_rate = 0.0003
    ctx.stamp_tax_rate = 0.001
    ctx.slippage_rate = 0.002

    if positions_data:
        for d in positions_data:
            pos = Position(d['code'], d.get('name', ''))
            pos.amount = d.get('amount', 0)
            pos.closeable_amount = d.get('closeable_amount', 0)
            pos.avg_cost = d.get('avg_cost', 0.0)
            pos.price = d.get('price', 0.0)
            pos.value = pos.amount * pos.price
            if pos.amount > 0:
                ctx.portfolio.positions[d['code']] = pos

    ctx.portfolio._update_value()

    # Attach a minimal engine + g so serialize_portfolio can inspect g
    g = GlobalVars()
    ctx._engine = type('E', (), {
        'g': g,
        '_stock_data': {},
        '_pending_orders': [],
        '_trade_records': [],
        '_log_messages': [],
        '_custom_records': {},
    })()
    return ctx, g


# ===========================================================================
#  1. serialize_portfolio tests
# ===========================================================================

class TestSerializePortfolio:
    """Tests for state_manager.serialize_portfolio"""

    def test_empty_portfolio(self):
        """Serialize context with no positions."""
        ctx, _g = _make_context_with_positions(cash=1000000)
        result = serialize_portfolio(ctx)
        state = json.loads(result)

        assert state['available_cash'] == 1000000
        assert state['positions'] == {}
        assert state['benchmark'] == '000300'
        assert state['commission_rate'] == 0.0003
        assert state['stamp_tax_rate'] == 0.001
        assert state['slippage_rate'] == 0.002

    def test_single_position(self):
        """Serialize context with one position."""
        ctx, _g = _make_context_with_positions(
            cash=800000,
            positions_data=[
                {'code': '600519', 'name': '贵州茅台', 'amount': 100,
                 'closeable_amount': 100, 'avg_cost': 1800.0, 'price': 1900.0},
            ],
        )
        result = serialize_portfolio(ctx)
        state = json.loads(result)

        assert state['available_cash'] == 800000
        assert '600519' in state['positions']
        pos = state['positions']['600519']
        assert pos['code'] == '600519'
        assert pos['name'] == '贵州茅台'
        assert pos['amount'] == 100
        assert pos['closeable_amount'] == 100
        assert pos['avg_cost'] == 1800.0
        assert pos['price'] == 1900.0

    def test_multiple_positions(self):
        """Serialize context with multiple positions."""
        ctx, _g = _make_context_with_positions(
            cash=300000,
            positions_data=[
                {'code': '600519', 'name': '贵州茅台', 'amount': 100,
                 'closeable_amount': 100, 'avg_cost': 1800.0, 'price': 1900.0},
                {'code': '000001', 'name': '平安银行', 'amount': 500,
                 'closeable_amount': 500, 'avg_cost': 15.0, 'price': 16.0},
                {'code': '300750', 'name': '宁德时代', 'amount': 200,
                 'closeable_amount': 200, 'avg_cost': 220.0, 'price': 225.5},
            ],
        )
        result = serialize_portfolio(ctx)
        state = json.loads(result)

        assert len(state['positions']) == 3
        codes = set(state['positions'].keys())
        assert codes == {'600519', '000001', '300750'}

    def test_zero_amount_positions_excluded(self):
        """Positions with amount == 0 should not appear in the JSON."""
        ctx, _g = _make_context_with_positions(cash=1000000)
        pos = Position('999999', 'empty')
        pos.amount = 0
        ctx.portfolio.positions['999999'] = pos

        result = serialize_portfolio(ctx)
        state = json.loads(result)
        assert '999999' not in state['positions']

    def test_g_vars_serialized(self):
        """GlobalVars basic types are serialized."""
        ctx, g = _make_context_with_positions(cash=1000000)
        g.my_flag = True
        g.my_count = 42
        g.my_name = 'test_strategy'
        g.my_list = [1, 2, 3]

        result = serialize_portfolio(ctx)
        state = json.loads(result)

        assert state['g_vars']['my_flag'] is True
        assert state['g_vars']['my_count'] == 42
        assert state['g_vars']['my_name'] == 'test_strategy'
        assert state['g_vars']['my_list'] == [1, 2, 3]

    def test_g_vars_non_serializable_skipped(self):
        """Non-basic types on g should be silently skipped."""
        ctx, g = _make_context_with_positions(cash=1000000)
        g.ok_var = 'keep'
        g.bad_var = lambda x: x  # not serializable

        result = serialize_portfolio(ctx)
        state = json.loads(result)

        assert 'ok_var' in state['g_vars']
        assert 'bad_var' not in state['g_vars']

    def test_current_dt_serialized(self):
        """current_dt is converted to string."""
        ctx, _g = _make_context_with_positions(cash=1000000)
        ctx.current_dt = datetime.date(2026, 3, 18)

        result = serialize_portfolio(ctx)
        state = json.loads(result)
        assert state['current_dt'] == '2026-03-18'

    def test_output_is_valid_json(self):
        """Result is a valid JSON string."""
        ctx, _g = _make_context_with_positions(cash=1000000)
        result = serialize_portfolio(ctx)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


# ===========================================================================
#  2. restore_portfolio tests
# ===========================================================================

class TestRestorePortfolio:
    """Tests for state_manager.restore_portfolio"""

    def test_restore_empty_state(self):
        """Restore from None/empty state_json is a no-op."""
        ctx = Context(1000000)
        restore_portfolio(ctx, None)
        assert ctx.portfolio.available_cash == 1000000
        assert len(ctx.portfolio.positions) == 0

        restore_portfolio(ctx, '')
        assert ctx.portfolio.available_cash == 1000000

    def test_restore_cash(self):
        """Cash is restored correctly."""
        state = json.dumps({'available_cash': 750000, 'positions': {}})
        ctx = Context(1000000)
        restore_portfolio(ctx, state)
        assert ctx.portfolio.available_cash == 750000

    def test_restore_single_position(self):
        """Restore one position from JSON."""
        state = json.dumps({
            'available_cash': 800000,
            'positions': {
                '600519': {
                    'code': '600519', 'name': '贵州茅台',
                    'amount': 100, 'closeable_amount': 100,
                    'avg_cost': 1800.0, 'price': 1900.0,
                },
            },
        })
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        assert '600519' in ctx.portfolio.positions
        pos = ctx.portfolio.positions['600519']
        assert pos.code == '600519'
        assert pos.name == '贵州茅台'
        assert pos.amount == 100
        assert pos.closeable_amount == 100
        assert pos.avg_cost == 1800.0
        assert pos.price == 1900.0
        assert pos.value == 100 * 1900.0

    def test_restore_multiple_positions(self):
        """Restore multiple positions."""
        state = json.dumps({
            'available_cash': 300000,
            'positions': {
                '600519': {'code': '600519', 'name': 'A', 'amount': 100,
                           'closeable_amount': 100, 'avg_cost': 100, 'price': 110},
                '000001': {'code': '000001', 'name': 'B', 'amount': 200,
                           'closeable_amount': 200, 'avg_cost': 10, 'price': 12},
            },
        })
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        assert len(ctx.portfolio.positions) == 2
        assert ctx.portfolio.available_cash == 300000

    def test_restore_clears_existing_positions(self):
        """Restore should clear any pre-existing positions."""
        ctx = Context(1000000)
        ctx.portfolio.positions['OLD'] = Position('OLD', 'old_stock')
        ctx.portfolio.positions['OLD'].amount = 500

        state = json.dumps({
            'available_cash': 500000,
            'positions': {
                '600519': {'code': '600519', 'name': 'A', 'amount': 100,
                           'closeable_amount': 100, 'avg_cost': 100, 'price': 110},
            },
        })
        restore_portfolio(ctx, state)
        assert 'OLD' not in ctx.portfolio.positions
        assert '600519' in ctx.portfolio.positions

    def test_restore_g_vars(self):
        """GlobalVars are restored."""
        state = json.dumps({
            'available_cash': 1000000,
            'positions': {},
            'g_vars': {'my_flag': True, 'my_count': 42},
        })
        ctx = Context(1000000)
        g = GlobalVars()
        restore_portfolio(ctx, state, g)

        assert g.my_flag is True
        assert g.my_count == 42

    def test_restore_trade_costs(self):
        """Commission, tax, slippage are restored."""
        state = json.dumps({
            'available_cash': 1000000,
            'positions': {},
            'benchmark': '000905',
            'commission_rate': 0.001,
            'stamp_tax_rate': 0.002,
            'slippage_rate': 0.005,
        })
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        assert ctx.benchmark == '000905'
        assert ctx.commission_rate == 0.001
        assert ctx.stamp_tax_rate == 0.002
        assert ctx.slippage_rate == 0.005

    def test_restore_invalid_json(self):
        """Invalid JSON string should not raise, just warn."""
        ctx = Context(1000000)
        restore_portfolio(ctx, '{bad json}')
        # Should still have default state
        assert ctx.portfolio.available_cash == 1000000

    def test_restore_total_value_updated(self):
        """After restore, total_value = cash + market_value."""
        state = json.dumps({
            'available_cash': 500000,
            'positions': {
                '600519': {'code': '600519', 'name': 'A', 'amount': 100,
                           'closeable_amount': 100, 'avg_cost': 100, 'price': 150},
            },
        })
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        expected_market = 100 * 150
        assert ctx.portfolio.market_value == expected_market
        assert ctx.portfolio.total_value == 500000 + expected_market


# ===========================================================================
#  3. Round-trip serialize → restore tests
# ===========================================================================

class TestSerializeRestoreRoundTrip:
    """Round-trip: serialize → restore → verify equality."""

    def test_roundtrip_empty(self):
        ctx1, _g1 = _make_context_with_positions(cash=1000000)
        json_str = serialize_portfolio(ctx1)

        ctx2 = Context(1000000)
        restore_portfolio(ctx2, json_str)

        assert ctx2.portfolio.available_cash == ctx1.portfolio.available_cash
        assert len(ctx2.portfolio.positions) == 0

    def test_roundtrip_with_positions(self):
        ctx1, g1 = _make_context_with_positions(
            cash=500000,
            positions_data=[
                {'code': '600519', 'name': '贵州茅台', 'amount': 100,
                 'closeable_amount': 100, 'avg_cost': 1800.0, 'price': 1900.0},
                {'code': '000001', 'name': '平安银行', 'amount': 500,
                 'closeable_amount': 300, 'avg_cost': 15.0, 'price': 16.0},
            ],
        )
        g1.counter = 7
        g1.active = True

        json_str = serialize_portfolio(ctx1)

        ctx2 = Context(1000000)
        g2 = GlobalVars()
        restore_portfolio(ctx2, json_str, g2)

        assert ctx2.portfolio.available_cash == 500000
        assert len(ctx2.portfolio.positions) == 2

        p1 = ctx2.portfolio.positions['600519']
        assert p1.amount == 100
        assert p1.avg_cost == 1800.0
        assert p1.price == 1900.0

        p2 = ctx2.portfolio.positions['000001']
        assert p2.amount == 500
        assert p2.avg_cost == 15.0

        assert g2.counter == 7
        assert g2.active is True

    def test_roundtrip_preserves_costs(self):
        ctx1, _g1 = _make_context_with_positions(cash=1000000)
        ctx1.commission_rate = 0.0005
        ctx1.stamp_tax_rate = 0.0015
        ctx1.slippage_rate = 0.003

        json_str = serialize_portfolio(ctx1)
        ctx2 = Context(1000000)
        restore_portfolio(ctx2, json_str)

        assert ctx2.commission_rate == 0.0005
        assert ctx2.stamp_tax_rate == 0.0015
        assert ctx2.slippage_rate == 0.003


# ===========================================================================
#  4. _create_api tests
# ===========================================================================

class TestCreateApi:
    """Tests for paper_engine._create_api"""

    def test_api_namespace_keys(self):
        """API namespace contains all expected functions."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        dp = DataProxy()
        g = GlobalVars()

        ns = _create_api(ctx, dp, g)

        expected_keys = {'history', 'get_price', 'log', 'g', 'record',
                         'set_benchmark', 'set_order_cost'}
        assert expected_keys.issubset(set(ns.keys()))

    def test_g_reference(self):
        """The namespace 'g' is the same GlobalVars object passed in."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        g = GlobalVars()
        g.x = 99

        ns = _create_api(ctx, DataProxy(), g)
        assert ns['g'] is g
        assert ns['g'].x == 99

    def test_set_benchmark(self):
        """set_benchmark updates context.benchmark."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        ns['set_benchmark']('000905')
        assert ctx.benchmark == '000905'

    def test_set_order_cost(self):
        """set_order_cost updates context cost attributes."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        ns['set_order_cost'](commission=0.001, tax=0.002, slippage=0.005)
        assert ctx.commission_rate == 0.001
        assert ctx.stamp_tax_rate == 0.002
        assert ctx.slippage_rate == 0.005

    def test_record_is_callable(self):
        """record() should be a no-op callable."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        # Should not raise
        ns['record'](value=1.0, nav=1.05)

    def test_log_has_methods(self):
        """log object has info/warn/error/debug."""
        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        log = ns['log']
        assert callable(getattr(log, 'info', None))
        assert callable(getattr(log, 'warn', None))
        assert callable(getattr(log, 'error', None))
        assert callable(getattr(log, 'debug', None))

    def test_history_returns_series(self):
        """history() returns a pandas Series (empty when no data)."""
        import pandas as pd

        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ctx.current_dt = datetime.date(2026, 3, 18)
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        result = ns['history']('600519', 10)
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_history_with_data(self):
        """history() returns correct trailing data."""
        import pandas as pd

        ctx = Context(1000000)
        dates = pd.date_range('2026-03-01', periods=10, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'close': range(100, 110),
            'open': range(99, 109),
            'high': range(101, 111),
            'low': range(98, 108),
            'volume': [1000] * 10,
        })
        ctx._engine = type('E', (), {'_stock_data': {'600519': df}})()
        ctx.current_dt = dates[-1]

        ns = _create_api(ctx, DataProxy(), GlobalVars())
        result = ns['history']('600519', 5)
        assert len(result) == 5
        assert result.iloc[-1] == 109  # last close

    def test_get_price_returns_dataframe(self):
        """get_price() returns a DataFrame (empty when no data)."""
        import pandas as pd

        ctx = Context(1000000)
        ctx._engine = type('E', (), {'_stock_data': {}})()
        ns = _create_api(ctx, DataProxy(), GlobalVars())

        result = ns['get_price']('600519')
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_get_price_with_data_and_filter(self):
        """get_price() returns filtered data by date range."""
        import pandas as pd

        ctx = Context(1000000)
        dates = pd.date_range('2026-03-01', periods=10, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'close': range(100, 110),
            'open': range(99, 109),
        })
        ctx._engine = type('E', (), {'_stock_data': {'600519': df}})()

        ns = _create_api(ctx, DataProxy(), GlobalVars())
        result = ns['get_price']('600519', start_date='2026-03-05', end_date='2026-03-10')
        assert len(result) > 0
        # All dates should be within range
        for d in result['date']:
            assert pd.Timestamp('2026-03-05') <= d <= pd.Timestamp('2026-03-10')


# ===========================================================================
#  5. _ensure_*_table tests
# ===========================================================================

class TestEnsureTables:
    """Tests for _ensure_paper_table, _ensure_trade_table, _ensure_position_table."""

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    def test_ensure_paper_table_exists(self, mock_exec, mock_check):
        """If table exists, no CREATE TABLE issued."""
        _ensure_paper_table()
        mock_check.assert_called_once_with('cn_stock_paper_trading')
        mock_exec.assert_not_called()

    @patch('instock.lib.database.checkTableIsExist', return_value=False)
    @patch('instock.lib.database.executeSql')
    def test_ensure_paper_table_creates(self, mock_exec, mock_check):
        """If table doesn't exist, CREATE TABLE is issued."""
        _ensure_paper_table()
        mock_exec.assert_called_once()
        sql = mock_exec.call_args[0][0]
        assert 'CREATE TABLE' in sql
        assert 'cn_stock_paper_trading' in sql
        assert 'strategy_id' in sql
        assert 'initial_cash' in sql
        assert 'state_json' in sql

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    def test_ensure_trade_table_exists(self, mock_exec, mock_check):
        _ensure_trade_table()
        mock_check.assert_called_once_with('cn_stock_backtest_trade')
        mock_exec.assert_not_called()

    @patch('instock.lib.database.checkTableIsExist', return_value=False)
    @patch('instock.lib.database.executeSql')
    def test_ensure_trade_table_creates(self, mock_exec, mock_check):
        _ensure_trade_table()
        mock_exec.assert_called_once()
        sql = mock_exec.call_args[0][0]
        assert 'CREATE TABLE' in sql
        assert 'cn_stock_backtest_trade' in sql
        assert 'direction' in sql
        assert 'paper_id' in sql

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    def test_ensure_position_table_exists(self, mock_exec, mock_check):
        _ensure_position_table()
        mock_check.assert_called_once_with('cn_stock_backtest_position')
        mock_exec.assert_not_called()

    @patch('instock.lib.database.checkTableIsExist', return_value=False)
    @patch('instock.lib.database.executeSql')
    def test_ensure_position_table_creates(self, mock_exec, mock_check):
        _ensure_position_table()
        mock_exec.assert_called_once()
        sql = mock_exec.call_args[0][0]
        assert 'CREATE TABLE' in sql
        assert 'cn_stock_backtest_position' in sql
        assert 'avg_cost' in sql
        assert 'weight' in sql


# ===========================================================================
#  6. _update_paper_error tests
# ===========================================================================

class TestUpdatePaperError:
    """Tests for paper_engine._update_paper_error"""

    @patch('instock.lib.database.executeSql')
    def test_updates_status_to_stopped(self, mock_exec):
        _update_paper_error(42, 'compile failed')
        mock_exec.assert_called_once()
        sql = mock_exec.call_args[0][0]
        params = mock_exec.call_args[0][1]
        assert 'UPDATE' in sql
        assert 'cn_stock_paper_trading' in sql
        assert 'stopped' in params
        assert 42 in params

    @patch('instock.lib.database.executeSql', side_effect=Exception('db down'))
    def test_db_error_suppressed(self, mock_exec):
        """DB errors in _update_paper_error are silently suppressed."""
        # Should not raise
        _update_paper_error(99, 'some error')


# ===========================================================================
#  7. run_paper_trading_daily tests
# ===========================================================================

class TestRunPaperTradingDaily:
    """Tests for paper_engine.run_paper_trading_daily"""

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=False)
    def test_non_trade_day_skipped(self, mock_is_td, mock_get_td, mock_fetch,
                                   mock_exec, mock_check):
        """Non-trade day returns 'skipped'."""
        mock_get_td.return_value = (datetime.date(2026, 3, 14), datetime.date(2026, 3, 14))
        result = run_paper_trading_daily(1)
        assert result['status'] == 'skipped'
        assert '非交易日' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch', return_value=[])
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    def test_paper_not_found(self, mock_is_td, mock_get_td, mock_fetch,
                             mock_exec, mock_check):
        """Paper ID not in DB returns error."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        result = run_paper_trading_daily(999)
        assert result['status'] == 'error'
        assert '不存在' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    def test_paper_paused_skipped(self, mock_is_td, mock_get_td, mock_fetch,
                                  mock_exec, mock_check):
        """Paused paper returns 'skipped'."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        # row: id, strategy_id, initial_cash, status, last_run_date, state_json, strategy_code
        mock_fetch.return_value = [(1, 10, 1000000, 'paused', None, None, 'pass')]
        result = run_paper_trading_daily(1)
        assert result['status'] == 'skipped'
        assert 'paused' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    def test_already_run_today_skipped(self, mock_is_td, mock_get_td, mock_fetch,
                                       mock_exec, mock_check):
        """Paper that already ran today returns 'skipped'."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        mock_fetch.return_value = [(1, 10, 1000000, 'running', '2026-03-18', None, 'pass')]
        result = run_paper_trading_daily(1)
        assert result['status'] == 'skipped'
        assert '已运行' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy', side_effect=SyntaxError('bad code'))
    def test_compile_error(self, mock_compile, mock_is_td, mock_get_td,
                           mock_fetch, mock_exec, mock_check):
        """Strategy compile failure returns error and updates DB."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        mock_fetch.return_value = [(1, 10, 1000000, 'running', None, None, 'invalid code')]
        result = run_paper_trading_daily(1)
        assert result['status'] == 'error'
        assert '编译失败' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy')
    @patch('instock.paper_trading.paper_engine.load_stock_data', return_value=None)
    def test_successful_run_no_trades(self, mock_load, mock_compile, mock_is_td,
                                      mock_get_td, mock_fetch, mock_exec, mock_check):
        """Successful run with empty strategy (no orders)."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))

        # First call: load paper info. Subsequent: other queries
        state_json = json.dumps({
            'available_cash': 1000000,
            'positions': {},
            'g_vars': {},
            'benchmark': '000300',
            'commission_rate': 0.0003,
            'stamp_tax_rate': 0.001,
            'slippage_rate': 0.002,
        })
        mock_fetch.return_value = [(1, 10, 1000000, 'running', '2026-03-17',
                                    state_json, 'def handle_data(context, data): pass')]

        # compile returns dict with handle_data
        def _noop_handle(ctx, data):
            pass
        mock_compile.return_value = {
            'initialize': lambda ctx: None,
            'handle_data': _noop_handle,
            'before_trading_start': None,
            'after_trading_end': None,
        }

        result = run_paper_trading_daily(1)
        assert result['status'] == 'ok'
        assert result['trades'] == 0

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy')
    @patch('instock.paper_trading.paper_engine.load_stock_data', return_value=None)
    def test_first_run_calls_initialize(self, mock_load, mock_compile, mock_is_td,
                                        mock_get_td, mock_fetch, mock_exec, mock_check):
        """First run (no state_json) should call initialize."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        mock_fetch.return_value = [(1, 10, 1000000, 'running', None, None,
                                    'def initialize(ctx): pass')]

        init_called = {'count': 0}

        def _init(ctx):
            init_called['count'] += 1

        def _handle(ctx, data):
            pass

        mock_compile.return_value = {
            'initialize': _init,
            'handle_data': _handle,
            'before_trading_start': None,
            'after_trading_end': None,
        }

        result = run_paper_trading_daily(1)
        assert result['status'] == 'ok'
        assert init_called['count'] == 1

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy')
    @patch('instock.paper_trading.paper_engine.load_stock_data', return_value=None)
    def test_initialize_exception_returns_error(self, mock_load, mock_compile,
                                                 mock_is_td, mock_get_td,
                                                 mock_fetch, mock_exec, mock_check):
        """initialize() exception returns error status."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        mock_fetch.return_value = [(1, 10, 1000000, 'running', None, None,
                                    'def initialize(ctx): raise ValueError("bad")')]

        def _bad_init(ctx):
            raise ValueError('bad init')

        mock_compile.return_value = {
            'initialize': _bad_init,
            'handle_data': lambda ctx, data: None,
            'before_trading_start': None,
            'after_trading_end': None,
        }

        result = run_paper_trading_daily(1)
        assert result['status'] == 'error'
        assert 'initialize' in result['message']

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy')
    @patch('instock.paper_trading.paper_engine.load_stock_data', return_value=None)
    def test_state_saved_after_run(self, mock_load, mock_compile, mock_is_td,
                                   mock_get_td, mock_fetch, mock_exec, mock_check):
        """After successful run, state is saved via executeSql UPDATE."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        state_json = json.dumps({
            'available_cash': 1000000, 'positions': {},
            'g_vars': {}, 'benchmark': '000300',
            'commission_rate': 0.0003, 'stamp_tax_rate': 0.001, 'slippage_rate': 0.002,
        })
        mock_fetch.return_value = [(1, 10, 1000000, 'running', '2026-03-17',
                                    state_json, 'def handle_data(c,d): pass')]
        mock_compile.return_value = {
            'initialize': lambda c: None,
            'handle_data': lambda c, d: None,
            'before_trading_start': None,
            'after_trading_end': None,
        }

        run_paper_trading_daily(1)

        # Check UPDATE was called with state_json
        update_calls = [c for c in mock_exec.call_args_list
                        if 'UPDATE cn_stock_paper_trading' in str(c)]
        assert len(update_calls) >= 1

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    @patch('instock.paper_trading.paper_engine.compile_strategy')
    @patch('instock.paper_trading.paper_engine.load_stock_data')
    def test_run_with_existing_position_and_prices(self, mock_load, mock_compile,
                                                    mock_is_td, mock_get_td,
                                                    mock_fetch, mock_exec, mock_check):
        """Run with an existing position; prices are loaded and portfolio updated."""
        import pandas as pd

        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))

        state_json = json.dumps({
            'available_cash': 800000,
            'positions': {
                '600519': {
                    'code': '600519', 'name': '贵州茅台',
                    'amount': 100, 'closeable_amount': 100,
                    'avg_cost': 1800.0, 'price': 1850.0,
                },
            },
            'g_vars': {},
            'benchmark': '000300',
            'commission_rate': 0.0003,
            'stamp_tax_rate': 0.001,
            'slippage_rate': 0.002,
        })
        mock_fetch.return_value = [(1, 10, 1000000, 'running', '2026-03-17',
                                    state_json, 'def handle_data(c,d): pass')]

        # Provide price data for 600519
        dates = pd.date_range('2026-03-01', '2026-03-18', freq='B')
        df = pd.DataFrame({
            'date': dates,
            'close': [1900.0] * len(dates),
            'open': [1890.0] * len(dates),
            'high': [1910.0] * len(dates),
            'low': [1880.0] * len(dates),
            'volume': [10000] * len(dates),
            'pre_close': [1895.0] * len(dates),
        })
        mock_load.return_value = df

        mock_compile.return_value = {
            'initialize': lambda c: None,
            'handle_data': lambda c, d: None,
            'before_trading_start': None,
            'after_trading_end': None,
        }

        result = run_paper_trading_daily(1)
        assert result['status'] == 'ok'

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch')
    @patch('instock.lib.trade_time.get_trade_date_last')
    @patch('instock.lib.trade_time.is_trade_date', return_value=True)
    def test_unexpected_exception_returns_error(self, mock_is_td, mock_get_td,
                                                 mock_fetch, mock_exec, mock_check):
        """Unexpected exception in run_paper_trading_daily returns error dict."""
        mock_get_td.return_value = (datetime.date(2026, 3, 18), datetime.date(2026, 3, 18))
        mock_fetch.side_effect = RuntimeError('db exploded')

        result = run_paper_trading_daily(1)
        assert result['status'] == 'error'
        assert 'db exploded' in result['message']


# ===========================================================================
#  8. run_all_paper_trading tests
# ===========================================================================

class TestRunAllPaperTrading:
    """Tests for paper_engine.run_all_paper_trading"""

    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch', return_value=[])
    def test_no_running_papers(self, mock_fetch, mock_exec, mock_check):
        """No running papers → returns None."""
        result = run_all_paper_trading()
        assert result is None

    @patch('instock.paper_trading.paper_engine.run_paper_trading_daily')
    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch', return_value=[(1,), (2,), (3,)])
    def test_runs_each_paper(self, mock_fetch, mock_exec, mock_check, mock_run):
        """Calls run_paper_trading_daily for each active paper."""
        mock_run.return_value = {'status': 'ok', 'message': 'done', 'trades': 0}

        results = run_all_paper_trading()

        assert len(results) == 3
        mock_run.assert_any_call(1)
        mock_run.assert_any_call(2)
        mock_run.assert_any_call(3)

    @patch('instock.paper_trading.paper_engine.run_paper_trading_daily')
    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch', return_value=[(10,)])
    def test_result_includes_id(self, mock_fetch, mock_exec, mock_check, mock_run):
        """Each result dict includes the paper id."""
        mock_run.return_value = {'status': 'ok', 'message': 'done', 'trades': 2}

        results = run_all_paper_trading()
        assert results[0]['id'] == 10
        assert results[0]['status'] == 'ok'

    @patch('instock.paper_trading.paper_engine.run_paper_trading_daily')
    @patch('instock.lib.database.checkTableIsExist', return_value=True)
    @patch('instock.lib.database.executeSql')
    @patch('instock.lib.database.executeSqlFetch', return_value=[(1,), (2,)])
    def test_mixed_results(self, mock_fetch, mock_exec, mock_check, mock_run):
        """Handles mix of success/error results."""
        mock_run.side_effect = [
            {'status': 'ok', 'message': 'done', 'trades': 1},
            {'status': 'error', 'message': 'failed'},
        ]

        results = run_all_paper_trading()
        assert results[0]['status'] == 'ok'
        assert results[1]['status'] == 'error'


# ===========================================================================
#  9. Context / Portfolio / Position integration edge-case tests
# ===========================================================================

class TestContextPositionEdgeCases:
    """Edge-case tests ensuring serialize/restore handle boundary conditions."""

    def test_position_profit_and_profit_rate(self):
        """Position.profit and profit_rate computed correctly after restore."""
        state = json.dumps({
            'available_cash': 500000,
            'positions': {
                '600519': {'code': '600519', 'name': 'A', 'amount': 100,
                           'closeable_amount': 100, 'avg_cost': 100.0, 'price': 120.0},
            },
        })
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        pos = ctx.portfolio.positions['600519']
        assert pos.profit == (120.0 - 100.0) * 100
        assert abs(pos.profit_rate - 0.20) < 1e-9

    def test_zero_cost_position_profit_rate(self):
        """profit_rate is 0 when avg_cost is 0."""
        pos = Position('000001')
        pos.amount = 100
        pos.avg_cost = 0.0
        pos.price = 10.0
        assert pos.profit_rate == 0.0

    def test_empty_position_profit(self):
        """profit is 0 when amount is 0."""
        pos = Position('000001')
        pos.amount = 0
        pos.avg_cost = 50.0
        pos.price = 60.0
        assert pos.profit == 0.0

    def test_roundtrip_large_portfolio(self):
        """Round-trip with many positions."""
        positions_data = [
            {'code': f'{600000 + i:06d}', 'name': f'Stock{i}', 'amount': 100 * (i + 1),
             'closeable_amount': 100 * (i + 1), 'avg_cost': 10.0 + i,
             'price': 11.0 + i}
            for i in range(20)
        ]
        ctx1, g1 = _make_context_with_positions(cash=100000, positions_data=positions_data)
        g1.iteration = 99

        json_str = serialize_portfolio(ctx1)
        ctx2 = Context(1000000)
        g2 = GlobalVars()
        restore_portfolio(ctx2, json_str, g2)

        assert len(ctx2.portfolio.positions) == 20
        assert g2.iteration == 99
        assert ctx2.portfolio.available_cash == 100000

    def test_restore_defaults_when_keys_missing(self):
        """Missing keys in JSON should fall back to defaults."""
        state = json.dumps({'available_cash': 999999})
        ctx = Context(1000000)
        restore_portfolio(ctx, state)

        assert ctx.portfolio.available_cash == 999999
        assert len(ctx.portfolio.positions) == 0
        # Defaults should be the standard values
        assert ctx.benchmark == '000300'
        assert ctx.commission_rate == 0.0003

    def test_portfolio_update_value(self):
        """_update_value correctly sums market_value + cash."""
        ctx, _g = _make_context_with_positions(
            cash=400000,
            positions_data=[
                {'code': '600519', 'name': 'A', 'amount': 100,
                 'closeable_amount': 100, 'avg_cost': 100, 'price': 200},
                {'code': '000001', 'name': 'B', 'amount': 200,
                 'closeable_amount': 200, 'avg_cost': 50, 'price': 60},
            ],
        )
        assert ctx.portfolio.market_value == 100 * 200 + 200 * 60
        assert ctx.portfolio.total_value == 400000 + 100 * 200 + 200 * 60
