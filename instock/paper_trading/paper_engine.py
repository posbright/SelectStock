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
from instock.core.backtest.data_feed import load_stock_data, load_benchmark_data
from .state_manager import serialize_portfolio, restore_portfolio

_INDEX_CODES = {
    '000002', '000003', '000016', '000300', '000688',
    '000852', '000905', '000906', '000985',
    '399001', '399006', '399300', '399905', '399951',
}


def _normalize_security_code(code):
    text = str(code or '').strip()
    return text.split('.')[0] if '.' in text else text


def _is_index_code(code):
    clean = _normalize_security_code(code)
    return clean in _INDEX_CODES or clean.startswith('399')


def _load_security_data(code, start_date=None, end_date=None):
    clean = _normalize_security_code(code)
    if _is_index_code(clean):
        return clean, load_benchmark_data(clean, start_date, end_date)
    return clean, load_stock_data(clean, start_date, end_date)

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


def run_paper_trading_daily(paper_id, scheduled=False, now=None):
    """
    执行指定模拟盘的每日交易。

    Args:
        paper_id: 模拟交易实例 ID

    Returns:
        dict: 执行结果 {'status': 'ok'/'error', 'message': str, 'trades': int}
    """
    import instock.lib.database as mdb
    import instock.lib.trade_time as trd

    started_at = datetime.datetime.now()
    result = None
    date_str = None

    try:
        # 1. 获取当前交易日
        run_date, run_date_nph = trd.get_trade_date_last()
        if not trd.is_trade_date(run_date_nph):
            result = {'status': 'skipped', 'message': '非交易日'}
            return result

        date_str = run_date_nph.strftime('%Y-%m-%d')

        # 2. 加载模拟盘信息
        _ensure_paper_table()
        rows = mdb.executeSqlFetch(
            'SELECT pt.id, pt.strategy_id, pt.initial_cash, pt.status, '
            'pt.last_run_date, pt.state_json, sc.code as strategy_code, '
            'pt.run_frequency, pt.start_at, pt.last_run_at '
            'FROM cn_stock_paper_trading pt '
            'JOIN cn_stock_strategy_code sc ON pt.strategy_id = sc.id '
            'WHERE pt.id = %s', (paper_id,))

        if not rows:
            result = {'status': 'error', 'message': f'模拟盘 {paper_id} 不存在'}
            return result

        row = rows[0]
        status = row[3]
        last_run_date = row[4]
        state_json = row[5]
        strategy_code = row[6]
        run_frequency = _normalize_run_frequency(row[7] if len(row) > 7 else 'daily')
        start_at = row[8] if len(row) > 8 else None
        last_run_at = row[9] if len(row) > 9 else None
        initial_cash = float(row[2]) if row[2] else 1000000

        if status != 'running':
            result = {'status': 'skipped', 'message': f'模拟盘状态为 {status}'}
            return result

        now_dt = now or datetime.datetime.now()
        due, reason = _is_paper_due(
            run_frequency, start_at, last_run_date, last_run_at,
            date_str, now_dt, scheduled=scheduled)
        if not due:
            result = {'status': 'skipped', 'message': reason}
            return result

        logging.info(f"[模拟交易] 执行模拟盘 #{paper_id}，日期 {date_str}")

        # 3. 编译策略
        try:
            strategy_funcs = compile_strategy(strategy_code)
        except Exception as e:
            _update_paper_error(paper_id, str(e))
            result = {'status': 'error', 'message': f'策略编译失败: {e}'}
            return result

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
                if isinstance(val, str):
                    clean = _normalize_security_code(val)
                    if len(clean) == 6 and clean.isdigit():
                        all_codes.add(clean)
                elif isinstance(val, (list, tuple, set)):
                    for item in val:
                        if isinstance(item, str):
                            clean = _normalize_security_code(item)
                            if len(clean) == 6 and clean.isdigit():
                                all_codes.add(clean)

        today_prices = {}
        pre_start = (pd.Timestamp(date_str) - pd.Timedelta(days=60)).strftime('%Y-%m-%d')

        # 优先从数据库批量加载当日行情（由定时任务每日写入 cn_stock_spot）
        from instock.core.backtest.data_feed import _batch_load_today_from_db
        stock_codes = [code for code in all_codes if not _is_index_code(code)]
        db_today = _batch_load_today_from_db(stock_codes, date_str) if stock_codes else {}

        for code in all_codes:
            code, df = _load_security_data(code, pre_start, date_str)
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
            code = _normalize_security_code(code)
            # 动态加载未预加载的股票数据
            if code not in context._engine._stock_data:
                code, df = _load_security_data(code, pre_start, date_str)
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
            if code not in today_prices and not _is_index_code(code):
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
                # 恢复运行时 initialize 仍需成功注册回调/参数。失败后继续执行会
                # 用半初始化状态撮合并覆盖 state_json，存在模拟盘状态污染风险。
                logging.error(f"[模拟交易] initialize 异常（恢复运行失败）: {e}")
                _update_paper_error(paper_id, f'initialize 异常: {e}')
                return {'status': 'error', 'message': f'initialize 异常: {e}'}

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

        with mdb.get_connection() as conn:
            conn.autocommit(False)
            try:
                cur = conn.cursor()

                # 8. 保存状态
                try:
                    cur.execute(
                        'UPDATE cn_stock_paper_trading SET last_run_date=%s, last_run_at=%s, '
                        'state_json=%s, current_cash=%s, current_value=%s WHERE id=%s',
                        (date_str, now_dt, new_state, context.portfolio.available_cash,
                         context.portfolio.total_value, paper_id))
                except Exception as update_error:
                    if 'last_run_at' not in str(update_error):
                        raise
                    logging.warning("[模拟交易] last_run_at 列不存在，使用旧表结构保存状态")
                    cur.execute(
                        'UPDATE cn_stock_paper_trading SET last_run_date=%s, '
                        'state_json=%s, current_cash=%s, current_value=%s WHERE id=%s',
                        (date_str, new_state,
                         float(context.portfolio.available_cash),
                         float(context.portfolio.total_value), paper_id))

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
                try:
                    conn.rollback()
                except Exception:
                    logging.exception(f"[模拟交易] 模拟盘 #{paper_id} 事务回滚失败")
                raise
            finally:
                try:
                    conn.autocommit(True)
                except Exception:
                    logging.warning(f"[模拟交易] 模拟盘 #{paper_id} 恢复 autocommit 失败", exc_info=True)

        logging.info(f"[模拟交易] 模拟盘 #{paper_id} 完成: "
                     f"交易 {len(trade_records)} 笔, "
                     f"总资产 {context.portfolio.total_value:.2f}")

        result = {
            'status': 'ok',
            'message': f'执行完成，{len(trade_records)} 笔交易',
            'trades': len(trade_records),
            'total_value': round(context.portfolio.total_value, 2),
        }
        return result

    except Exception as e:
        logging.error(f"[模拟交易] 模拟盘 #{paper_id} 异常", exc_info=True)
        result = {'status': 'error', 'message': str(e)}
        return result

    finally:
        # 无论成功/失败/跳过，都记录执行日志到 DB
        if result is not None:
            try:
                from instock.paper_trading.scheduler import (
                    _ensure_execution_log_table, _save_execution_log)
                _save_execution_log(
                    paper_id, date_str or str(datetime.date.today()),
                    started_at, result.get('status', 'unknown'),
                    result.get('message', ''),
                    trades=result.get('trades', 0),
                    total_value=result.get('total_value'))
            except Exception:
                logging.debug("[模拟交易] 记录执行日志失败", exc_info=True)


def run_all_paper_trading(scheduled=False):
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
            result = run_paper_trading_daily(paper_id, scheduled=scheduled)
        except Exception as e:
            logging.error(f"[模拟交易] #{paper_id} 执行异常", exc_info=True)
            result = {'status': 'error', 'message': str(e)}
        results.append({'id': paper_id, **result})
        logging.info(f"[模拟交易] #{paper_id}: {result.get('status')} - {result.get('message', '')}")

    return results


def _create_api(context, data_proxy, g):
    """创建策略 API 命名空间（兼容聚宽风格调用）"""

    def history(code, count, field='close'):
        code = _normalize_security_code(code)
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
        code = _normalize_security_code(code)
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

    # ── 基本面数据查询（基于实盘数据 cn_stock_selection / cn_stock_spot）──

    # 聚宽字段名 → cn_stock_selection 列名映射
    _JQ_FIELD_MAP = {
        # valuation
        'market_cap': 'total_market_cap',
        'pe_ratio': 'pe9',
        'pb_ratio': 'pbnewmrq',
        'circulating_market_cap': 'free_cap',
        # indicator
        'roe': 'roe_weight',
        'eps': 'basic_eps',
        'inc_total_revenue_year_on_year': 'toi_yoy_ratio',
        'inc_net_profit_year_on_year': 'netprofit_yoy_ratio',
        'inc_revenue_year_on_year': 'toi_yoy_ratio',
        'net_profit_margin': 'sale_npr',
        'gross_profit_margin': 'sale_gpr',
        # balance
        'total_liability': 'debt_asset_ratio',  # 近似：资产负债率
        'total_assets': None,  # cn_stock_selection 无此字段
        'total_current_assets': None,
        'total_current_liability': None,
        # cash_flow
        'net_operate_cash_flow': 'per_netcash_operate',  # 近似：每股经营现金流
        'net_invest_cash_flow': None,
        'net_finance_cash_flow': None,
    }

    def get_fundamentals(q, date=None):
        """从 cn_stock_selection 查询真实基本面数据（模拟交易专用）。

        cn_stock_selection 由每日定时任务从东方财富选股器 API 获取，
        包含 70+ 列真实基本面数据（PE/PB/ROE/毛利率/负债率/增长率等），
        与 GPT 综合选股策略使用完全相同的数据源。
        """
        query_date = date or context.current_dt
        date_str = query_date.strftime('%Y-%m-%d') if hasattr(query_date, 'strftime') else str(query_date)[:10]

        try:
            import instock.lib.database as mdb

            # 查询 cn_stock_selection 的最新日期（可能 date_str 当天还没获取到）
            date_rows = mdb.executeSqlFetch(
                'SELECT MAX(date) FROM cn_stock_selection WHERE date <= %s', (date_str,))
            if not date_rows or date_rows[0][0] is None:
                logging.warning(f"[模拟交易] cn_stock_selection 无 <= {date_str} 的数据")
                # 回退到 FundamentalDataProvider
                return _get_fundamentals_fallback(q, query_date)
            actual_date = date_rows[0][0]

            # 构建查询列（code 必选 + 策略请求的字段）
            select_cols = ['code', 'name']
            jq_to_db = {}  # jq_field → db_col 映射（用于结果列重命名）
            from instock.core.backtest.fundamentals import _FieldExpr
            for field_expr in q._fields:
                if isinstance(field_expr, _FieldExpr):
                    jq_name = field_expr._name
                    db_col = _JQ_FIELD_MAP.get(jq_name, jq_name)
                    if db_col and db_col not in select_cols:
                        select_cols.append(db_col)
                        jq_to_db[jq_name] = db_col

            # 同样处理过滤条件中引用的字段
            for f in q._filters:
                if isinstance(f, tuple) and len(f) >= 3:
                    jq_name = f[1]
                    db_col = _JQ_FIELD_MAP.get(jq_name, jq_name)
                    if db_col and db_col not in select_cols:
                        select_cols.append(db_col)
                        jq_to_db[jq_name] = db_col

            # 也加入估值相关常用列
            for extra in ['total_market_cap', 'free_cap', 'pe9', 'pbnewmrq',
                          'roe_weight', 'sale_gpr', 'sale_npr', 'debt_asset_ratio']:
                if extra not in select_cols:
                    select_cols.append(extra)

            cols_sql = ', '.join(f'`{c}`' for c in select_cols)
            rows = mdb.executeSqlFetch(
                f'SELECT {cols_sql} FROM cn_stock_selection WHERE date = %s AND new_price > 0',
                (actual_date,))

            if not rows or len(rows) == 0:
                logging.warning(f"[模拟交易] cn_stock_selection {actual_date} 无数据")
                return _get_fundamentals_fallback(q, query_date)

            result = pd.DataFrame(rows, columns=select_cols)

            # 数值列转 float
            for c in result.columns:
                if c not in ('code', 'name', 'date'):
                    result[c] = pd.to_numeric(result[c], errors='coerce')

            # 市值单位转换：cn_stock_selection 的 total_market_cap 单位是元 → 转为亿元
            if 'total_market_cap' in result.columns:
                result['total_market_cap'] = result['total_market_cap'] / 1e8  # 元 → 亿
            if 'free_cap' in result.columns:
                result['free_cap'] = result['free_cap'] / 1e8

            # 将 DB 列名映射回聚宽字段名，方便策略使用
            rename_map = {}
            for jq_name, db_col in jq_to_db.items():
                if db_col in result.columns and jq_name != db_col:
                    rename_map[db_col] = jq_name
            # 标准映射（回测引擎兼容）
            if 'total_market_cap' in result.columns:
                rename_map.setdefault('total_market_cap', 'market_cap')
            if 'pe9' in result.columns:
                rename_map.setdefault('pe9', 'pe_ratio')
            if 'pbnewmrq' in result.columns:
                rename_map.setdefault('pbnewmrq', 'pb_ratio')
            if 'free_cap' in result.columns:
                rename_map.setdefault('free_cap', 'circulating_market_cap')
            if 'roe_weight' in result.columns:
                rename_map.setdefault('roe_weight', 'roe')
            if 'basic_eps' in result.columns:
                rename_map.setdefault('basic_eps', 'eps')
            if 'sale_npr' in result.columns:
                rename_map.setdefault('sale_npr', 'net_profit_margin')
            if 'sale_gpr' in result.columns:
                rename_map.setdefault('sale_gpr', 'gross_profit_margin')
            if rename_map:
                result = result.rename(columns=rename_map)

            # 应用过滤条件
            # 构建反向映射: jq_name → db_col（已经 rename 过，所以用 jq_name）
            for f in q._filters:
                if not isinstance(f, tuple) or len(f) < 3:
                    continue
                op = f[0]
                # div_* 操作符处理 balance.total_liability / balance.total_assets 等
                if op.startswith('div_'):
                    # 对于 debt_asset_ratio 已在 cn_stock_selection 中，直接用
                    numerator, denominator = f[1], f[2]
                    threshold = f[3]
                    if numerator == 'total_liability' and denominator == 'total_assets':
                        col = 'debt_asset_ratio'
                        if col in result.columns:
                            cmp = op.replace('div_', '')
                            if cmp == 'lt':
                                result = result[result[col] < threshold * 100]  # 百分比
                            elif cmp == 'gt':
                                result = result[result[col] > threshold * 100]
                            elif cmp == 'le':
                                result = result[result[col] <= threshold * 100]
                            elif cmp == 'ge':
                                result = result[result[col] >= threshold * 100]
                    continue
                field = f[1]
                if field not in result.columns:
                    continue
                if op == 'between' and len(f) >= 4:
                    result = result[(result[field] >= f[2]) & (result[field] <= f[3])]
                elif op == 'gt':
                    result = result[result[field] > f[2]]
                elif op == 'lt':
                    result = result[result[field] < f[2]]
                elif op == 'ge':
                    result = result[result[field] >= f[2]]
                elif op == 'le':
                    result = result[result[field] <= f[2]]
                elif op == 'in_':
                    result = result[result[field].isin(f[2])]

            # 排序
            if q._order_by_clause is not None and isinstance(q._order_by_clause, tuple):
                direction, field = q._order_by_clause
                if field in result.columns:
                    result = result.sort_values(field, ascending=(direction == 'asc'))

            # 限制行数
            if q._limit_val is not None:
                result = result.head(q._limit_val)

            if len(result) > 0:
                logging.info(f"[模拟交易] get_fundamentals 从 cn_stock_selection({actual_date}) "
                             f"查得 {len(result)} 只股票")

            return result.reset_index(drop=True)

        except Exception as e:
            logging.warning(f"[模拟交易] get_fundamentals 查询异常: {e}")
            return _get_fundamentals_fallback(q, query_date)

    def _get_fundamentals_fallback(q, query_date):
        """回退到 FundamentalDataProvider（当 cn_stock_selection 不可用时）"""
        provider = _get_fundamental_provider(context._engine if hasattr(context, '_engine') else None)
        if provider is None:
            return pd.DataFrame()
        try:
            return provider.get_fundamentals(q, query_date)
        except Exception:
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
        'set_benchmark': lambda code: setattr(context, 'benchmark', _normalize_security_code(code)),
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


_RUN_FREQUENCY_MINUTES = {
    'daily': 24 * 60,
    'hourly': 60,
    '15m': 15,
}


def _normalize_run_frequency(value):
    value = (value or 'daily').strip() if isinstance(value, str) else 'daily'
    return value if value in _RUN_FREQUENCY_MINUTES else 'daily'


def _as_datetime(value):
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)
    if value:
        text = str(value).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.datetime.strptime(text[:19] if 'T' in text else text, fmt)
            except ValueError:
                continue
    return None


# 每日模拟盘等到收盘+数据落库后才执行；可通过 INSTOCK_PAPER_DAILY_AFTER_HOUR 调整
import os as _os
try:
    _PAPER_DAILY_AFTER_HOUR = int(_os.environ.get('INSTOCK_PAPER_DAILY_AFTER_HOUR', '16'))
except (TypeError, ValueError):
    _PAPER_DAILY_AFTER_HOUR = 16


def _is_paper_due(run_frequency, start_at, last_run_date, last_run_at,
                  date_str, now_dt, scheduled=False):
    start_dt = _as_datetime(start_at)
    if start_dt and now_dt < start_dt:
        return False, f'未到开始时间 ({start_dt.strftime("%Y-%m-%d %H:%M:%S")})'

    freq = _normalize_run_frequency(run_frequency)
    if freq == 'daily':
        if scheduled and now_dt.hour < _PAPER_DAILY_AFTER_HOUR:
            return False, f'等待今日收盘后执行 (≥ {_PAPER_DAILY_AFTER_HOUR:02d}:00)'
        if last_run_date and str(last_run_date) >= date_str:
            return False, f'今日已运行 ({last_run_date})'
        return True, 'ok'

    # hourly / 15m: 数据源仍是日级 K 线 + cn_stock_spot 日级快照，
    # 盘中并无分钟级行情；保留触发能力但避免盘前/午休空跑。
    last_dt = _as_datetime(last_run_at)
    if last_dt:
        interval = datetime.timedelta(minutes=_RUN_FREQUENCY_MINUTES[freq])
        next_dt = last_dt + interval
        if now_dt < next_dt:
            return False, f'未到下次运行时间 ({next_dt.strftime("%Y-%m-%d %H:%M:%S")})'
    return True, 'ok'


def _add_paper_column_safe(column_name, ddl):
    import instock.lib.database as mdb
    try:
        rows = mdb.executeSqlFetch(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cn_stock_paper_trading' "
            "AND COLUMN_NAME = %s", (column_name,))
        exists = rows and rows[0][0] > 0
        if not exists:
            mdb.executeSql(f'ALTER TABLE cn_stock_paper_trading ADD COLUMN {ddl}')
    except Exception as e:
        logging.warning(f"[模拟交易] 添加 cn_stock_paper_trading.{column_name} 失败/已存在: {e}")


def _ensure_paper_columns():
    _add_paper_column_safe('backtest_id', '`backtest_id` INT DEFAULT NULL AFTER `strategy_id`')
    _add_paper_column_safe('run_frequency', "`run_frequency` VARCHAR(20) DEFAULT 'daily' AFTER `status`")
    _add_paper_column_safe('start_at', '`start_at` DATETIME DEFAULT CURRENT_TIMESTAMP AFTER `run_frequency`')
    _add_paper_column_safe('last_run_at', '`last_run_at` DATETIME DEFAULT NULL AFTER `last_run_date`')


def _ensure_paper_table():
    import instock.lib.database as mdb
    if mdb.checkTableIsExist('cn_stock_paper_trading'):
        _ensure_paper_columns()
        return
    mdb.executeSql('''
        CREATE TABLE IF NOT EXISTS `cn_stock_paper_trading` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `strategy_id` INT NOT NULL,
            `backtest_id` INT DEFAULT NULL,
            `name` VARCHAR(100),
            `initial_cash` DECIMAL(15,2) DEFAULT 1000000.00,
            `current_cash` DECIMAL(15,2),
            `current_value` DECIMAL(15,2),
            `status` ENUM('running','paused','stopped') DEFAULT 'running',
            `run_frequency` VARCHAR(20) DEFAULT 'daily',
            `start_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `started_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `last_run_date` DATE,
            `last_run_at` DATETIME DEFAULT NULL,
            `state_json` LONGTEXT,
            INDEX `idx_strategy` (`strategy_id`),
            INDEX `idx_backtest` (`backtest_id`),
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
