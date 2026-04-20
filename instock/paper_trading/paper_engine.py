#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟交易引擎

每日执行策略逻辑，使用当日真实行情数据模拟成交，
持仓和资金状态在每日收盘后持久化到数据库。

核心流程：
1. 从 DB 加载策略代码和上次运行状态
2. 恢复 Context / Portfolio / g 对象
3. 加载当日行情数据
4. 执行 before_trading_start → handle_data → after_trading_end
5. 撮合订单（使用当日收盘价）
6. 保存状态到 DB
7. 记录交易和持仓快照
"""

import logging
import time
import datetime
import json
import pandas as pd

from instock.core.backtest.strategy_context import (
    Context, GlobalVars, DataProxy, TradeRecord, NavRecord,
)
from instock.core.backtest.strategy_sandbox import compile_strategy
from instock.core.backtest.data_feed import load_stock_data
from .state_manager import serialize_portfolio, restore_portfolio

# 基本面数据提供器（延迟初始化，仅在策略需要时加载）
_fundamental_provider = None

def _get_fundamental_provider(engine_obj=None):
    """获取或创建基本面数据提供器单例"""
    global _fundamental_provider
    if _fundamental_provider is None:
        try:
            from instock.core.backtest.fundamentals import FundamentalDataProvider
            _fundamental_provider = FundamentalDataProvider(engine_obj)
        except Exception as e:
            logging.warning(f"[模拟交易] 基本面数据提供器加载失败: {e}")
    elif engine_obj is not None:
        # 更新引擎引用，确保 context.current_dt 是最新的
        _fundamental_provider._engine = engine_obj
    return _fundamental_provider

__author__ = 'InStock'
__date__ = '2026/03/13'


def run_paper_trading_daily(paper_id):
    """
    执行指定模拟盘的每日交易。

    Args:
        paper_id: 模拟交易实例 ID

    Returns:
        dict: 执行结果 {'status': 'ok'/'error', 'message': str, 'trades': int}
    """
    import instock.lib.database as mdb
    import instock.lib.trade_time as trd

    try:
        # 1. 获取当前交易日
        run_date, run_date_nph = trd.get_trade_date_last()
        if not trd.is_trade_date(run_date_nph):
            return {'status': 'skipped', 'message': '非交易日'}

        date_str = run_date_nph.strftime('%Y-%m-%d')

        # 2. 加载模拟盘信息
        _ensure_paper_table()
        rows = mdb.executeSqlFetch(
            'SELECT pt.id, pt.strategy_id, pt.initial_cash, pt.status, '
            'pt.last_run_date, pt.state_json, sc.code as strategy_code '
            'FROM cn_stock_paper_trading pt '
            'JOIN cn_stock_strategy_code sc ON pt.strategy_id = sc.id '
            'WHERE pt.id = %s', (paper_id,))

        if not rows:
            return {'status': 'error', 'message': f'模拟盘 {paper_id} 不存在'}

        row = rows[0]
        status = row[3]
        last_run_date = row[4]
        state_json = row[5]
        strategy_code = row[6]
        initial_cash = float(row[2]) if row[2] else 1000000

        if status != 'running':
            return {'status': 'skipped', 'message': f'模拟盘状态为 {status}'}

        # 防止重复运行
        if last_run_date and str(last_run_date) >= date_str:
            return {'status': 'skipped', 'message': f'今日已运行 ({last_run_date})'}

        logging.info(f"[模拟交易] 执行模拟盘 #{paper_id}，日期 {date_str}")

        # 3. 编译策略
        try:
            strategy_funcs = compile_strategy(strategy_code)
        except Exception as e:
            _update_paper_error(paper_id, str(e))
            return {'status': 'error', 'message': f'策略编译失败: {e}'}

        # 4. 初始化/恢复上下文
        context = Context(initial_cash)
        g = GlobalVars()
        data_proxy = DataProxy()

        if state_json:
            # 恢复之前的状态
            restore_portfolio(context, state_json, g)
            logging.info(f"[模拟交易] 恢复状态: 现金={context.portfolio.available_cash:.2f}, "
                         f"持仓={len(context.portfolio.positions)}只")

        context.current_dt = run_date_nph
        context._engine = type('E', (), {'g': g, 'context': context, '_stock_data': {},
                                          '_pending_orders': [],
                                          '_trade_records': [], '_log_messages': [],
                                          '_custom_records': {}})()

        # 5. 加载持仓股票的当日行情
        all_codes = set(context.portfolio.positions.keys())
        # 从 context 和 g 中发现更多股票代码
        for obj in [context, g]:
            for attr in dir(obj):
                if attr.startswith('_'):
                    continue
                val = getattr(obj, attr, None)
                if isinstance(val, str) and len(val) == 6 and val.isdigit():
                    all_codes.add(val)
                elif isinstance(val, (list, tuple, set)):
                    for item in val:
                        if isinstance(item, str) and len(item) == 6 and item.isdigit():
                            all_codes.add(item)

        today_prices = {}
        pre_start = (pd.Timestamp(date_str) - pd.Timedelta(days=60)).strftime('%Y-%m-%d')

        # 优先从数据库批量加载当日行情（由定时任务每日写入 cn_stock_spot）
        from instock.core.backtest.data_feed import _batch_load_today_from_db
        db_today = _batch_load_today_from_db(list(all_codes), date_str) if all_codes else {}

        for code in all_codes:
            df = load_stock_data(code, pre_start, date_str)
            if df is not None:
                context._engine._stock_data[code] = df
                data_proxy._set_history(code, df)
                today_row = df[df['date'] == pd.Timestamp(date_str)]
                if len(today_row) > 0:
                    row_data = today_row.iloc[0]
                    today_prices[code] = row_data['close']
                    data_proxy._set_current(code, {
                        'open': row_data.get('open', row_data['close']),
                        'high': row_data.get('high', row_data['close']),
                        'low': row_data.get('low', row_data['close']),
                        'close': row_data['close'],
                        'volume': row_data.get('volume', 0),
                        'pre_close': row_data.get('pre_close', row_data['close']),
                    })
                elif code in db_today:
                    # K线缓存有历史数据但缺今日，用 DB 行情补全
                    spot = db_today[code]
                    today_prices[code] = spot['close']
                    data_proxy._set_current(code, {
                        'open': spot['open'],
                        'high': spot['high'],
                        'low': spot['low'],
                        'close': spot['close'],
                        'volume': spot['volume'],
                        'pre_close': spot.get('pre_close', spot['close']),
                    })
            elif code in db_today:
                # 完全无缓存，但 DB 有今日行情（至少可参与撮合）
                spot = db_today[code]
                today_prices[code] = spot['close']
                data_proxy._set_current(code, {
                    'open': spot['open'],
                    'high': spot['high'],
                    'low': spot['low'],
                    'close': spot['close'],
                    'volume': spot['volume'],
                    'pre_close': spot.get('pre_close', spot['close']),
                })

        # 更新持仓价格 + T+1
        context.portfolio._on_new_day(today_prices)

        # 6. 执行策略
        api_ns = _create_api(context, data_proxy, g)
        pending_orders = []

        def _order_proxy(code, amount=None, value=None):
            # 动态加载未预加载的股票数据
            if code not in context._engine._stock_data:
                df = load_stock_data(code, pre_start, date_str)
                if df is not None:
                    context._engine._stock_data[code] = df
                    data_proxy._set_history(code, df)
                    today_row = df[df['date'] == pd.Timestamp(date_str)]
                    if len(today_row) > 0:
                        row_data = today_row.iloc[0]
                        today_prices[code] = row_data['close']
                        data_proxy._set_current(code, {
                            'open': row_data.get('open', row_data['close']),
                            'high': row_data.get('high', row_data['close']),
                            'low': row_data.get('low', row_data['close']),
                            'close': row_data['close'],
                            'volume': row_data.get('volume', 0),
                            'pre_close': row_data.get('pre_close', row_data['close']),
                        })
            # 如果仍无今日价格，尝试从 DB 单只加载
            if code not in today_prices:
                from instock.core.backtest.data_feed import _load_today_from_db
                db_row = _load_today_from_db(code, date_str)
                if db_row is not None:
                    spot = db_row.iloc[0]
                    today_prices[code] = float(spot['close'])
                    data_proxy._set_current(code, {
                        'open': float(spot['open']),
                        'high': float(spot['high']),
                        'low': float(spot['low']),
                        'close': float(spot['close']),
                        'volume': int(spot['volume']),
                        'pre_close': float(spot['pre_close']) if pd.notna(spot.get('pre_close')) else float(spot['close']),
                    })
            pending_orders.append({'code': code, 'amount': amount, 'value': value})

        def _get_current_amount(code):
            pos = context.portfolio.positions.get(code)
            return pos.amount if pos else 0

        def _get_current_value(code):
            pos = context.portfolio.positions.get(code)
            return pos.value if pos and pos.amount > 0 else 0

        api_ns['order'] = lambda code, amount: _order_proxy(code, amount=int(amount))
        api_ns['order_target'] = lambda code, target: _order_proxy(
            code, amount=int(target) - _get_current_amount(code))
        api_ns['order_value'] = lambda code, value: _order_proxy(code, value=float(value))
        api_ns['order_target_value'] = lambda code, target_value: _order_proxy(
            code, value=float(target_value) - _get_current_value(code))
        api_ns['order_target_percent'] = lambda code, percent: _order_proxy(
            code, value=float(percent) * context.portfolio.total_value - _get_current_value(code))

        # 每次都执行 initialize（注册 run_daily/run_weekly 回调 + 设置 context 参数）
        try:
            strategy_funcs['initialize'].__globals__.update(api_ns)
            strategy_funcs['initialize'](context)
        except Exception as e:
            if not state_json:
                # 首次运行 initialize 失败是致命的
                _update_paper_error(paper_id, f'initialize 异常: {e}')
                return {'status': 'error', 'message': f'initialize 异常: {e}'}
            else:
                logging.warning(f"[模拟交易] initialize 异常（恢复运行）: {e}")

        # before_trading_start
        if strategy_funcs.get('before_trading_start'):
            try:
                strategy_funcs['before_trading_start'].__globals__.update(api_ns)
                strategy_funcs['before_trading_start'](context)
            except Exception as e:
                logging.warning(f"[模拟交易] before_trading_start 异常: {e}")

        # handle_data
        if strategy_funcs.get('handle_data'):
            try:
                strategy_funcs['handle_data'].__globals__.update(api_ns)
                strategy_funcs['handle_data'](context, data_proxy)
            except Exception as e:
                logging.warning(f"[模拟交易] handle_data 异常: {e}")

        # 执行 run_weekly 注册的回调
        if api_ns.get('_weekly_callbacks'):
            py_weekday = run_date_nph.weekday() if hasattr(run_date_nph, 'weekday') else pd.Timestamp(run_date_nph).weekday()
            jq_weekday = py_weekday + 1  # 聚宽: 1=Mon ... 5=Fri
            for (cb, wd) in api_ns['_weekly_callbacks']:
                if jq_weekday == wd:
                    try:
                        cb.__globals__.update(api_ns)
                        cb(context)
                    except Exception as e:
                        cb_name = getattr(cb, '__name__', str(cb))
                        logging.warning(f"[模拟交易] run_weekly({cb_name}) 异常: {e}")

        # 执行 run_daily 注册的回调
        for cb in api_ns.get('_daily_callbacks', []):
            try:
                cb.__globals__.update(api_ns)
                cb(context)
            except Exception as e:
                cb_name = getattr(cb, '__name__', str(cb))
                logging.warning(f"[模拟交易] run_daily({cb_name}) 异常: {e}")

        # 7. 撮合订单
        trade_records = []
        for order_info in pending_orders:
            code = order_info['code']
            if code not in today_prices:
                logging.warning(f"[模拟交易] 股票 {code} 无当日行情数据，跳过订单")
                continue

            exec_price = today_prices[code]
            amount = order_info.get('amount')

            if amount is None and order_info.get('value') is not None:
                value = order_info['value']
                if value > 0:
                    amount = int(value / exec_price / 100) * 100
                else:
                    amount = -int(abs(value) / exec_price / 100) * 100

            if not amount or amount == 0:
                continue

            if amount > 0:
                # 买入
                amount = int(amount / 100) * 100
                if amount <= 0:
                    continue
                actual_price = exec_price * (1 + context.slippage_rate)
                total_cost = actual_price * amount
                commission = max(total_cost * context.commission_rate, 5.0)
                if total_cost + commission > context.portfolio.available_cash:
                    affordable = context.portfolio.available_cash / (actual_price * (1 + context.commission_rate))
                    amount = int(affordable / 100) * 100
                    if amount <= 0:
                        continue
                    total_cost = actual_price * amount
                    commission = max(total_cost * context.commission_rate, 5.0)
                    # 防御：最低佣金5元可能导致超支
                    if total_cost + commission > context.portfolio.available_cash:
                        continue

                pos = context.portfolio._get_or_create_position(code)
                pos._on_buy(amount, actual_price, commission)
                pos._update_price(exec_price)  # 用市场收盘价估值，而非含滑点的成交价
                context.portfolio.available_cash -= (total_cost + commission)

                trade = TradeRecord(run_date_nph, code, pos.name, 'buy', exec_price, amount)
                trade.commission = round(commission, 2)
                trade_records.append(trade)

            elif amount < 0:
                # 卖出
                sell_amount = abs(amount)
                pos = context.portfolio.positions.get(code)
                if not pos or pos.closeable_amount <= 0:
                    continue
                sell_amount = min(sell_amount, pos.closeable_amount)
                if sell_amount <= 0:
                    continue

                actual_price = exec_price * (1 - context.slippage_rate)
                total_income = actual_price * sell_amount
                commission = max(total_income * context.commission_rate, 5.0)
                tax = total_income * context.stamp_tax_rate

                pos._on_sell(sell_amount, exec_price)  # 剩余持仓以市场收盘价估值
                context.portfolio.available_cash += (total_income - commission - tax)

                trade = TradeRecord(run_date_nph, code, pos.name, 'sell', exec_price, sell_amount)
                trade.commission = round(commission, 2)
                trade.tax = round(tax, 2)
                trade_records.append(trade)

        context.portfolio._update_value()

        # after_trading_end
        if strategy_funcs.get('after_trading_end'):
            try:
                strategy_funcs['after_trading_end'].__globals__.update(api_ns)
                strategy_funcs['after_trading_end'](context)
            except Exception as e:
                logging.warning(f"[模拟交易] after_trading_end 异常: {e}")

        # 8–11: 保存状态、交易、持仓、NAV（在单个事务中执行）
        _ensure_trade_table()
        _ensure_position_table()
        _ensure_nav_table()

        new_state = serialize_portfolio(context)
        position_value = context.portfolio.total_value - context.portfolio.available_cash

        conn_ctx = mdb.get_connection()
        conn = conn_ctx.__enter__()
        try:
            conn.autocommit(False)
            cur = conn.cursor()

            # 8. 保存状态
            cur.execute(
                'UPDATE cn_stock_paper_trading SET last_run_date=%s, state_json=%s, '
                'current_cash=%s, current_value=%s WHERE id=%s',
                (date_str, new_state, context.portfolio.available_cash,
                 context.portfolio.total_value, paper_id))

            # 9. 记录交易
            for t in trade_records:
                cur.execute(
                    'INSERT INTO cn_stock_backtest_trade '
                    '(paper_id, date, code, name, direction, price, amount, value, commission, tax) '
                    'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (paper_id, date_str, t.code, t.name, t.direction,
                     t.price, t.amount, t.value, t.commission, t.tax))

            # 10. 持仓快照
            for code, pos in context.portfolio.positions.items():
                if pos.amount > 0:
                    weight = pos.value / context.portfolio.total_value * 100 if context.portfolio.total_value > 0 else 0
                    cur.execute(
                        'INSERT INTO cn_stock_backtest_position '
                        '(paper_id, date, code, name, amount, avg_cost, close_price, '
                        'market_value, profit, profit_rate, weight) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (paper_id, date_str, code, pos.name, pos.amount,
                         round(pos.avg_cost, 3), round(pos.price, 3),
                         round(pos.value, 2), round(pos.profit, 2),
                         round(pos.profit_rate, 6), round(weight, 6)))

            # 11. 每日 NAV 记录
            cur.execute(
                'INSERT INTO cn_stock_paper_nav '
                '(paper_id, date, total_value, cash, position_value) '
                'VALUES (%s,%s,%s,%s,%s) '
                'ON DUPLICATE KEY UPDATE total_value=VALUES(total_value), '
                'cash=VALUES(cash), position_value=VALUES(position_value)',
                (paper_id, date_str,
                 round(context.portfolio.total_value, 2),
                 round(context.portfolio.available_cash, 2),
                 round(position_value, 2)))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit(True)
            conn_ctx.__exit__(None, None, None)

        logging.info(f"[模拟交易] 模拟盘 #{paper_id} 完成: "
                     f"交易 {len(trade_records)} 笔, "
                     f"总资产 {context.portfolio.total_value:.2f}")

        return {
            'status': 'ok',
            'message': f'执行完成，{len(trade_records)} 笔交易',
            'trades': len(trade_records),
            'total_value': round(context.portfolio.total_value, 2),
        }

    except Exception as e:
        logging.error(f"[模拟交易] 模拟盘 #{paper_id} 异常", exc_info=True)
        return {'status': 'error', 'message': str(e)}


def run_all_paper_trading():
    """
    执行所有状态为 running 的模拟盘。

    可由 cron 定时触发，每个交易日收盘后执行。
    """
    import instock.lib.database as mdb

    _ensure_paper_table()
    rows = mdb.executeSqlFetch(
        'SELECT id FROM cn_stock_paper_trading WHERE status = %s', ('running',))

    if not rows:
        logging.info("[模拟交易] 无运行中的模拟盘")
        return

    results = []
    for row in rows:
        paper_id = row[0]
        try:
            result = run_paper_trading_daily(paper_id)
        except Exception as e:
            logging.error(f"[模拟交易] #{paper_id} 执行异常", exc_info=True)
            result = {'status': 'error', 'message': str(e)}
        results.append({'id': paper_id, **result})
        logging.info(f"[模拟交易] #{paper_id}: {result.get('status')} - {result.get('message', '')}")

    return results


def _create_api(context, data_proxy, g):
    """创建策略 API 命名空间（兼容聚宽风格调用）"""

    def history(code, count, field='close'):
        df = context._engine._stock_data.get(code) if hasattr(context, '_engine') and context._engine else None
        if df is None:
            return pd.Series(dtype=float)
        mask = df['date'] <= pd.Timestamp(context.current_dt)
        subset = df.loc[mask].tail(count)
        if field in subset.columns:
            return subset[field].reset_index(drop=True)
        return pd.Series(dtype=float)

    def attribute_history(security, count, unit='1d', fields=None,
                          skip_paused=True, df=True, fq='pre'):
        """聚宽 attribute_history 兼容"""
        code = security.split('.')[0] if '.' in security else security
        stock_df = context._engine._stock_data.get(code) if hasattr(context, '_engine') and context._engine else None
        if stock_df is None:
            cols = fields or ['close']
            return pd.DataFrame(columns=cols)
        mask = stock_df['date'] <= pd.Timestamp(context.current_dt)
        subset = stock_df.loc[mask].tail(count)
        if fields:
            cols = [f for f in fields if f in subset.columns]
            return subset[cols].reset_index(drop=True)
        return subset[['open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)

    def get_price(code, start_date=None, end_date=None, fields=None):
        df = context._engine._stock_data.get(code) if hasattr(context, '_engine') and context._engine else None
        if df is None:
            return pd.DataFrame()
        result = df.copy()
        if start_date:
            result = result[result['date'] >= pd.Timestamp(start_date)]
        if end_date:
            result = result[result['date'] <= pd.Timestamp(end_date)]
        if fields:
            cols = ['date'] + [f for f in fields if f in result.columns]
            result = result[cols]
        return result.reset_index(drop=True)

    def set_order_cost(cost_obj=None, type='stock', **kwargs):
        """兼容聚宽 set_order_cost(OrderCost(...), type='stock') 及关键字参数"""
        if cost_obj is not None and isinstance(cost_obj, dict):
            context.commission_rate = cost_obj.get('open_commission', 0.0003)
            context.stamp_tax_rate = cost_obj.get('close_tax', 0.001)
        elif cost_obj is not None and hasattr(cost_obj, '_data'):
            # _OrderCost object
            context.commission_rate = cost_obj._data.get('open_commission', 0.0003)
            context.stamp_tax_rate = cost_obj._data.get('close_tax', 0.001)
        elif isinstance(cost_obj, (int, float)):
            context.commission_rate = cost_obj
        # 支持关键字参数：commission, tax, slippage
        if 'commission' in kwargs:
            context.commission_rate = kwargs['commission']
        if 'tax' in kwargs:
            context.stamp_tax_rate = kwargs['tax']
        if 'slippage' in kwargs:
            context.slippage_rate = kwargs['slippage']

    class _OrderCost:
        """聚宽 OrderCost 兼容"""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self._data = kwargs
        def get(self, key, default=None):
            return self._data.get(key, default)

    # run_daily 回调注册
    _daily_callbacks = []
    _weekly_callbacks = []

    def run_daily(func, time='every_bar', reference_security=None):
        _daily_callbacks.append(func)

    def run_weekly(func, weekday=1, time='every_bar', reference_security=None):
        _weekly_callbacks.append((func, weekday))

    def run_monthly(func, monthday=1, time='every_bar', reference_security=None):
        _daily_callbacks.append(func)

    class _Log:
        def info(self, msg): logging.info(f"[模拟盘策略] {msg}")
        def warn(self, msg): logging.warning(f"[模拟盘策略] {msg}")
        def warning(self, msg): logging.warning(f"[模拟盘策略] {msg}")
        def error(self, msg): logging.error(f"[模拟盘策略] {msg}")
        def debug(self, msg): logging.debug(f"[模拟盘策略] {msg}")
        def set_level(self, *args, **kwargs): pass

    def get_all_cached_stocks():
        try:
            from instock.core.backtest.data_feed import get_all_cached_stocks as _gacs
            return _gacs()
        except Exception:
            return []

    # ── 基本面数据查询 ──
    def get_fundamentals(q, date=None):
        provider = _get_fundamental_provider(context._engine if hasattr(context, '_engine') else None)
        if provider is None:
            logging.warning("[模拟交易] 基本面数据不可用，返回空 DataFrame")
            return pd.DataFrame()
        query_date = date or context.current_dt
        try:
            return provider.get_fundamentals(q, query_date)
        except Exception as e:
            logging.warning(f"[模拟交易] get_fundamentals 异常: {e}")
            return pd.DataFrame()

    # ── 指数成份股查询 ──
    _INDEX_STOCKS = {
        '399951': [
            '601398', '601939', '601288', '601988', '600036', '601166',
            '000001', '601328', '601818', '600016', '601009', '600000',
            '601229', '002142', '600015', '601838', '601916', '601998',
            '600926', '601169', '601077', '600908', '601658', '601528',
            '601860', '601963', '601187', '002839', '002936', '002948',
            '002966', '600919',
        ],
    }

    def get_index_stocks(index_code, date=None):
        clean = index_code.split('.')[0] if '.' in index_code else index_code
        stocks = _INDEX_STOCKS.get(clean, [])
        if not stocks:
            logging.warning(f"[模拟交易] 未知指数 {index_code}，返回空列表")
        return stocks

    # ── get_all_securities ──
    def get_all_securities(types=None, date=None):
        codes = get_all_cached_stocks()
        if codes:
            return pd.DataFrame({'code': codes, 'display_name': codes, 'type': 'stock'}).set_index('code')
        return pd.DataFrame(columns=['display_name', 'type'])

    # ── get_current_data ──
    def get_current_data():
        provider = _get_fundamental_provider(context._engine if hasattr(context, '_engine') else None)
        if provider is not None:
            try:
                from instock.core.backtest.fundamentals import _CurrentDataProxy
                return _CurrentDataProxy(provider, context._engine if hasattr(context, '_engine') else None)
            except Exception:
                pass
        return {}

    # ── 聚宽 query DSL 对象 ──
    try:
        from instock.core.backtest.fundamentals import valuation, indicator, balance, cash_flow, query as jq_query
        _valuation = valuation
        _indicator = indicator
        _balance = balance
        _cash_flow = cash_flow
        _query = jq_query
    except Exception:
        _valuation = None
        _indicator = None
        _balance = None
        _cash_flow = None
        _query = lambda *a, **kw: None

    ns = {
        'history': history,
        'attribute_history': attribute_history,
        'get_price': get_price,
        'log': _Log(),
        'g': g,
        'record': lambda **kw: None,
        'set_benchmark': lambda code: setattr(context, 'benchmark', code),
        'set_option': lambda *a, **kw: None,
        'set_order_cost': set_order_cost,
        'OrderCost': lambda **kw: kw,
        'run_daily': run_daily,
        'run_weekly': run_weekly,
        'run_monthly': run_monthly,
        'order_target': lambda code, amount: None,
        'order_value': lambda code, value: None,
        'order': lambda code, amount: None,
        'order_target_percent': lambda code, percent: None,
        'get_index_stocks': get_index_stocks,
        'get_all_securities': get_all_securities,
        'get_all_cached_stocks': get_all_cached_stocks,
        'get_fundamentals': get_fundamentals,
        'get_current_data': get_current_data,
        'get_security_info': lambda code: type('Info', (), {'start_date': None, 'display_name': '', 'name': ''})(),
        'normalize_code': lambda code: code.split('.')[0] if '.' in code else code,
        '_daily_callbacks': _daily_callbacks,
        '_weekly_callbacks': _weekly_callbacks,
    }
    # 注入聚宽 query DSL 对象
    if _valuation is not None:
        ns['valuation'] = _valuation
        ns['indicator'] = _indicator
        ns['balance'] = _balance
        ns['cash_flow'] = _cash_flow
        ns['query'] = _query
    return ns


def _update_paper_error(paper_id, message):
    """更新模拟盘错误状态"""
    import instock.lib.database as mdb
    try:
        mdb.executeSql(
            'UPDATE cn_stock_paper_trading SET status=%s WHERE id=%s',
            ('stopped', paper_id))
    except Exception:
        pass


def _ensure_paper_table():
    import instock.lib.database as mdb
    if mdb.checkTableIsExist('cn_stock_paper_trading'):
        return
    mdb.executeSql('''
        CREATE TABLE IF NOT EXISTS `cn_stock_paper_trading` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `strategy_id` INT NOT NULL,
            `name` VARCHAR(100),
            `initial_cash` DECIMAL(15,2) DEFAULT 1000000.00,
            `current_cash` DECIMAL(15,2),
            `current_value` DECIMAL(15,2),
            `status` ENUM('running','paused','stopped') DEFAULT 'running',
            `started_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `last_run_date` DATE,
            `state_json` LONGTEXT,
            INDEX `idx_strategy` (`strategy_id`),
            INDEX `idx_status` (`status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')


def _ensure_trade_table():
    import instock.lib.database as mdb
    if mdb.checkTableIsExist('cn_stock_backtest_trade'):
        return
    mdb.executeSql('''
        CREATE TABLE IF NOT EXISTS `cn_stock_backtest_trade` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `backtest_id` INT DEFAULT NULL,
            `paper_id` INT DEFAULT NULL,
            `date` DATE NOT NULL,
            `code` VARCHAR(6) NOT NULL,
            `name` VARCHAR(20),
            `direction` ENUM('buy','sell') NOT NULL,
            `price` DECIMAL(10,3) NOT NULL,
            `amount` INT NOT NULL,
            `value` DECIMAL(15,2),
            `commission` DECIMAL(10,2),
            `tax` DECIMAL(10,2),
            INDEX `idx_bt_date` (`backtest_id`, `date`),
            INDEX `idx_paper_date` (`paper_id`, `date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')


def _ensure_position_table():
    import instock.lib.database as mdb
    if mdb.checkTableIsExist('cn_stock_backtest_position'):
        return
    mdb.executeSql('''
        CREATE TABLE IF NOT EXISTS `cn_stock_backtest_position` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `backtest_id` INT DEFAULT NULL,
            `paper_id` INT DEFAULT NULL,
            `date` DATE NOT NULL,
            `code` VARCHAR(6) NOT NULL,
            `name` VARCHAR(20),
            `amount` INT NOT NULL,
            `avg_cost` DECIMAL(10,3),
            `close_price` DECIMAL(10,3),
            `market_value` DECIMAL(15,2),
            `profit` DECIMAL(15,2),
            `profit_rate` DECIMAL(10,6),
            `weight` DECIMAL(10,6),
            INDEX `idx_bt_date` (`backtest_id`, `date`),
            INDEX `idx_paper_date` (`paper_id`, `date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')


def _ensure_nav_table():
    """确保模拟盘每日 NAV 记录表存在"""
    import instock.lib.database as mdb
    if mdb.checkTableIsExist('cn_stock_paper_nav'):
        return
    mdb.executeSql('''
        CREATE TABLE IF NOT EXISTS `cn_stock_paper_nav` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `paper_id` INT NOT NULL,
            `date` DATE NOT NULL,
            `total_value` DECIMAL(15,2) NOT NULL,
            `cash` DECIMAL(15,2),
            `position_value` DECIMAL(15,2),
            `benchmark_value` DECIMAL(10,6) DEFAULT 1.0,
            UNIQUE KEY `uq_paper_date` (`paper_id`, `date`),
            INDEX `idx_paper` (`paper_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
