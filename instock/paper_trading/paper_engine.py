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
        else:
            # 首次运行，执行 initialize
            api_ns = _create_api(context, data_proxy, g)
            try:
                strategy_funcs['initialize'].__globals__.update(api_ns)
                strategy_funcs['initialize'](context)
            except Exception as e:
                _update_paper_error(paper_id, f'initialize 异常: {e}')
                return {'status': 'error', 'message': f'initialize 异常: {e}'}

        context.current_dt = run_date_nph
        context._engine = type('E', (), {'g': g, '_stock_data': {}, '_pending_orders': [],
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

        # before_trading_start
        if strategy_funcs.get('before_trading_start'):
            try:
                strategy_funcs['before_trading_start'].__globals__.update(api_ns)
                strategy_funcs['before_trading_start'](context)
            except Exception as e:
                logging.warning(f"[模拟交易] before_trading_start 异常: {e}")

        # handle_data
        try:
            strategy_funcs['handle_data'].__globals__.update(api_ns)
            strategy_funcs['handle_data'](context, data_proxy)
        except Exception as e:
            logging.warning(f"[模拟交易] handle_data 异常: {e}")

        # 7. 撮合订单
        trade_records = []
        for order_info in pending_orders:
            code = order_info['code']
            if code not in today_prices:
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

        # 8. 保存状态
        new_state = serialize_portfolio(context)
        mdb.executeSql(
            'UPDATE cn_stock_paper_trading SET last_run_date=%s, state_json=%s, '
            'current_cash=%s, current_value=%s WHERE id=%s',
            (date_str, new_state, context.portfolio.available_cash,
             context.portfolio.total_value, paper_id))

        # 9. 记录交易
        _ensure_trade_table()
        for t in trade_records:
            mdb.executeSql(
                'INSERT INTO cn_stock_backtest_trade '
                '(paper_id, date, code, name, direction, price, amount, value, commission, tax) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (paper_id, date_str, t.code, t.name, t.direction,
                 t.price, t.amount, t.value, t.commission, t.tax))

        # 10. 持仓快照
        _ensure_position_table()
        for code, pos in context.portfolio.positions.items():
            if pos.amount > 0:
                weight = pos.value / context.portfolio.total_value * 100 if context.portfolio.total_value > 0 else 0
                mdb.executeSql(
                    'INSERT INTO cn_stock_backtest_position '
                    '(paper_id, date, code, name, amount, avg_cost, close_price, '
                    'market_value, profit, profit_rate, weight) '
                    'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (paper_id, date_str, code, pos.name, pos.amount,
                     round(pos.avg_cost, 3), round(pos.price, 3),
                     round(pos.value, 2), round(pos.profit, 2),
                     round(pos.profit_rate, 6), round(weight, 6)))

        # 11. 每日 NAV 记录
        _ensure_nav_table()
        position_value = context.portfolio.total_value - context.portfolio.available_cash
        mdb.executeSql(
            'INSERT INTO cn_stock_paper_nav '
            '(paper_id, date, total_value, cash, position_value) '
            'VALUES (%s,%s,%s,%s,%s) '
            'ON DUPLICATE KEY UPDATE total_value=VALUES(total_value), '
            'cash=VALUES(cash), position_value=VALUES(position_value)',
            (paper_id, date_str,
             round(context.portfolio.total_value, 2),
             round(context.portfolio.available_cash, 2),
             round(position_value, 2)))

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
        result = run_paper_trading_daily(paper_id)
        results.append({'id': paper_id, **result})
        logging.info(f"[模拟交易] #{paper_id}: {result.get('status')} - {result.get('message', '')}")

    return results


def _create_api(context, data_proxy, g):
    """创建策略 API 命名空间"""

    def history(code, count, field='close'):
        df = context._engine._stock_data.get(code) if hasattr(context, '_engine') and context._engine else None
        if df is None:
            return pd.Series(dtype=float)
        mask = df['date'] <= pd.Timestamp(context.current_dt)
        subset = df.loc[mask].tail(count)
        if field in subset.columns:
            return subset[field].reset_index(drop=True)
        return pd.Series(dtype=float)

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

    def set_order_cost(commission=0.0003, tax=0.001, slippage=0.002):
        context.commission_rate = commission
        context.stamp_tax_rate = tax
        context.slippage_rate = slippage

    class _Log:
        def info(self, msg): logging.info(f"[模拟盘策略] {msg}")
        def warn(self, msg): logging.warning(f"[模拟盘策略] {msg}")
        def error(self, msg): logging.error(f"[模拟盘策略] {msg}")
        def debug(self, msg): logging.debug(f"[模拟盘策略] {msg}")

    return {
        'history': history,
        'get_price': get_price,
        'log': _Log(),
        'g': g,
        'record': lambda **kw: None,
        'set_benchmark': lambda code: setattr(context, 'benchmark', code),
        'set_order_cost': set_order_cost,
    }


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
