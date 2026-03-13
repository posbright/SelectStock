#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组合回测引擎 — 聚宽风格的事件驱动回测

核心流程：
1. 用户提交策略代码（Python 字符串）
2. 沙箱编译提取 initialize / handle_data 等函数
3. 按交易日逐日驱动：加载行情 → 执行策略 → 撮合订单 → 记录净值
4. 回测完成后计算风险指标，返回结构化结果

支持：
- 多股票组合回测
- T+1 交易规则
- A股涨跌停限制
- 佣金 + 印花税 + 滑点
- 基准对比（沪深300）
- 完整的交易记录和持仓快照
"""

import logging
import datetime
import time
import numpy as np
import pandas as pd

from .strategy_context import (
    Context, GlobalVars, DataProxy, Portfolio, Position,
    TradeRecord, NavRecord,
)
from .strategy_sandbox import compile_strategy, validate_code
from .data_feed import load_stock_data, load_multiple_stocks, get_trading_dates, load_benchmark_data
from .risk_metrics import calculate_metrics

__author__ = 'InStock'
__date__ = '2026/03/13'


class PortfolioBacktestEngine:
    """
    组合回测引擎

    使用方式：
        engine = PortfolioBacktestEngine()
        result = engine.run(
            strategy_code='def initialize(context): ...',
            start_date='2024-01-01',
            end_date='2025-01-01',
            initial_cash=1000000,
        )
    """

    def __init__(self):
        self.context = None
        self.data_proxy = None
        self.g = None
        self._strategy_funcs = None
        self._stock_data = {}          # {code: DataFrame}
        self._benchmark_data = None    # DataFrame
        self._nav_records = []         # [NavRecord]
        self._trade_records = []       # [TradeRecord]
        self._position_snapshots = []  # [{date, positions: [...]}]
        self._custom_records = {}      # record() 记录的自定义指标
        self._log_messages = []        # 策略日志
        self._pending_orders = []      # 待执行订单
        self._all_codes = set()        # 策略涉及的所有股票代码

    def run(self, strategy_code, start_date, end_date,
            initial_cash=1000000.0, benchmark='000300',
            commission=0.0003, tax=0.001, slippage=0.002):
        """
        运行回测。

        Args:
            strategy_code: Python 策略代码字符串
            start_date: 回测开始日期 'YYYY-MM-DD'
            end_date: 回测结束日期 'YYYY-MM-DD'
            initial_cash: 初始资金
            benchmark: 基准指数代码（默认沪深300）
            commission: 佣金率（双边，默认万三）
            tax: 印花税率（卖方，默认千一）
            slippage: 滑点率（默认千二）

        Returns:
            dict: 回测结果，包含 metrics/nav/trades/positions
        """
        start_time = time.time()
        logging.info(f"[回测引擎] 开始回测: {start_date} ~ {end_date}, 初始资金={initial_cash}")

        # 1. 编译策略
        try:
            self._strategy_funcs = compile_strategy(strategy_code)
        except (ValueError, SyntaxError) as e:
            return {'status': 'error', 'message': str(e)}

        # 2. 初始化上下文
        self.context = Context(initial_cash)
        self.context.benchmark = benchmark
        self.context.commission_rate = commission
        self.context.stamp_tax_rate = tax
        self.context.slippage_rate = slippage
        self.context._engine = self
        self.data_proxy = DataProxy()
        self.g = GlobalVars()

        # 3. 获取交易日列表
        # 预留20个交易日的前导数据供 history() 使用
        pre_start = (pd.Timestamp(start_date) - pd.Timedelta(days=40)).strftime('%Y-%m-%d')
        trading_dates = get_trading_dates(start_date, end_date)
        if not trading_dates:
            return {'status': 'error', 'message': f'无交易日: {start_date} ~ {end_date}'}
        logging.info(f"[回测引擎] 交易日: {len(trading_dates)} 天")

        # 4. 注入策略 API 到函数命名空间
        api_ns = self._create_strategy_api()

        # 5. 执行 initialize
        try:
            self._call_with_api(self._strategy_funcs['initialize'], [self.context], api_ns)
        except Exception as e:
            return {'status': 'error', 'message': f'initialize 执行错误: {e}'}

        # 6. 预加载策略涉及的股票数据
        self._discover_and_load_stocks(pre_start, end_date)

        # 7. 加载基准数据
        self._benchmark_data = load_benchmark_data(benchmark, start_date, end_date)
        benchmark_prices = {}
        if self._benchmark_data is not None:
            for _, row in self._benchmark_data.iterrows():
                d = row['date'].date() if hasattr(row['date'], 'date') else row['date']
                benchmark_prices[d] = row['close']

        # 8. 主回测循环
        prev_nav = 1.0
        prev_bm_nav = 1.0
        initial_bm_price = None

        for i, date in enumerate(trading_dates):
            self.context.current_dt = date
            self.context.previous_dt = trading_dates[i - 1] if i > 0 else None

            # 8a. 加载当日行情
            today_prices = self._load_day_prices(date)
            self.context.portfolio._on_new_day(today_prices)

            # 8b. before_trading_start
            if self._strategy_funcs.get('before_trading_start'):
                try:
                    self._call_with_api(self._strategy_funcs['before_trading_start'],
                                        [self.context], api_ns)
                except Exception as e:
                    logging.warning(f"[回测] {date} before_trading_start 异常: {e}")

            # 8c. handle_data
            try:
                self._call_with_api(self._strategy_funcs['handle_data'],
                                    [self.context, self.data_proxy], api_ns)
            except Exception as e:
                logging.warning(f"[回测] {date} handle_data 异常: {e}")

            # 8d. 执行待处理订单（使用当日开盘价/收盘价）
            self._execute_pending_orders(date, today_prices)

            # 8e. 更新组合价值（使用收盘价）
            self.context.portfolio._update_value()

            # 8f. after_trading_end
            if self._strategy_funcs.get('after_trading_end'):
                try:
                    self._call_with_api(self._strategy_funcs['after_trading_end'],
                                        [self.context], api_ns)
                except Exception as e:
                    logging.warning(f"[回测] {date} after_trading_end 异常: {e}")

            # 8g. 记录净值
            nav = self.context.portfolio.total_value / initial_cash
            daily_return = (nav / prev_nav - 1) if prev_nav > 0 else 0

            # 基准净值
            bm_price = benchmark_prices.get(date)
            if bm_price and initial_bm_price is None:
                initial_bm_price = bm_price
            bm_nav = bm_price / initial_bm_price if bm_price and initial_bm_price else prev_bm_nav
            bm_return = (bm_nav / prev_bm_nav - 1) if prev_bm_nav > 0 else 0

            self._nav_records.append(NavRecord(
                date=date, nav=nav, benchmark_nav=bm_nav,
                cash=self.context.portfolio.available_cash,
                market_value=self.context.portfolio.market_value,
                total_value=self.context.portfolio.total_value,
                daily_return=daily_return,
                benchmark_return=bm_return,
            ))

            # 8h. 持仓快照
            pos_snap = []
            for code, pos in self.context.portfolio.positions.items():
                if pos.amount > 0:
                    pos_snap.append({
                        'code': code, 'name': pos.name,
                        'amount': pos.amount, 'avg_cost': round(pos.avg_cost, 3),
                        'price': round(pos.price, 3),
                        'value': round(pos.value, 2),
                        'profit': round(pos.profit, 2),
                        'profit_rate': round(pos.profit_rate * 100, 2),
                        'weight': round(pos.value / self.context.portfolio.total_value * 100, 2)
                        if self.context.portfolio.total_value > 0 else 0,
                    })
            if pos_snap:
                self._position_snapshots.append({'date': date, 'positions': pos_snap})

            prev_nav = nav
            prev_bm_nav = bm_nav

        # 9. 计算风险指标
        nav_values = [r.nav for r in self._nav_records]
        bm_values = [r.benchmark_nav for r in self._nav_records]
        metrics = calculate_metrics(nav_values, bm_values, self._trade_records)

        elapsed = time.time() - start_time
        logging.info(f"[回测引擎] 完成: 收益={metrics['total_return']:.2f}%, "
                     f"最大回撤={metrics['max_drawdown']:.2f}%, "
                     f"夏普={metrics['sharpe_ratio']:.2f}, 耗时={elapsed:.1f}s")

        return {
            'status': 'completed',
            'metrics': metrics,
            'nav': [r.to_dict() for r in self._nav_records],
            'trades': [t.to_dict() for t in self._trade_records],
            'positions': self._position_snapshots,
            'logs': self._log_messages[-200:],  # 最后200条日志
            'elapsed': round(elapsed, 1),
            'params': {
                'start_date': start_date,
                'end_date': end_date,
                'initial_cash': initial_cash,
                'benchmark': benchmark,
                'commission': commission,
                'tax': tax,
                'slippage': slippage,
            }
        }

    # ── 策略 API 函数 ──

    def _create_strategy_api(self):
        """创建策略可调用的 API 函数集"""
        engine = self

        def order(code, amount):
            """按股数下单（正=买入，负=卖出）"""
            engine._submit_order(code, amount=int(amount))

        def order_target(code, target_amount):
            """调整到目标持仓股数"""
            pos = engine.context.portfolio.positions.get(code)
            current = pos.amount if pos else 0
            diff = int(target_amount) - current
            if diff != 0:
                engine._submit_order(code, amount=diff)

        def order_value(code, value):
            """按金额下单"""
            engine._submit_order(code, value=float(value))

        def order_target_value(code, target_value):
            """调整到目标持仓金额"""
            pos = engine.context.portfolio.positions.get(code)
            current_value = pos.value if pos and pos.amount > 0 else 0
            diff = float(target_value) - current_value
            if abs(diff) > 100:  # 忽略过小的调整
                engine._submit_order(code, value=diff)

        def history(code, count, field='close'):
            """获取最近 N 个交易日的数据"""
            df = engine._stock_data.get(code)
            if df is None:
                return pd.Series(dtype=float)
            current_date = engine.context.current_dt
            mask = df['date'] <= pd.Timestamp(current_date)
            subset = df.loc[mask].tail(count)
            if field in subset.columns:
                return subset[field].reset_index(drop=True)
            return pd.Series(dtype=float)

        def get_price(code, start_date=None, end_date=None, fields=None):
            """获取指定区间的历史数据"""
            df = engine._stock_data.get(code)
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

        def set_benchmark(code):
            """设定基准指数"""
            engine.context.benchmark = code

        def set_order_cost(commission=0.0003, tax=0.001, slippage=0.002):
            """设定交易成本"""
            engine.context.commission_rate = commission
            engine.context.stamp_tax_rate = tax
            engine.context.slippage_rate = slippage

        def record(**kwargs):
            """记录自定义指标"""
            date = engine.context.current_dt
            for key, val in kwargs.items():
                engine._custom_records.setdefault(key, []).append({
                    'date': str(date), 'value': val,
                })

        class _Log:
            def info(self, msg):
                engine._log_messages.append(f"[{engine.context.current_dt}] [INFO] {msg}")
            def warn(self, msg):
                engine._log_messages.append(f"[{engine.context.current_dt}] [WARN] {msg}")
            def error(self, msg):
                engine._log_messages.append(f"[{engine.context.current_dt}] [ERROR] {msg}")
            def debug(self, msg):
                engine._log_messages.append(f"[{engine.context.current_dt}] [DEBUG] {msg}")

        return {
            'order': order,
            'order_target': order_target,
            'order_value': order_value,
            'order_target_value': order_target_value,
            'history': history,
            'get_price': get_price,
            'set_benchmark': set_benchmark,
            'set_order_cost': set_order_cost,
            'record': record,
            'log': _Log(),
            'g': self.g,
        }

    def _call_with_api(self, func, args, api_ns):
        """注入 API 到函数的全局命名空间后调用"""
        if func is None:
            return
        func.__globals__.update(api_ns)
        func(*args)

    # ── 订单管理 ──

    def _submit_order(self, code, amount=None, value=None):
        """提交订单（延迟到当日行情加载后执行）"""
        # 动态加载该股票数据
        if code not in self._stock_data:
            self._load_single_stock(code)
            self._all_codes.add(code)

        self._pending_orders.append({
            'code': code,
            'amount': amount,
            'value': value,
        })

    def _execute_pending_orders(self, date, prices):
        """执行当轮所有挂单（使用收盘价模拟成交）"""
        for order_info in self._pending_orders:
            code = order_info['code']
            if code not in prices:
                self._log_messages.append(
                    f"[{date}] [WARN] {code} 无行情数据，订单取消")
                continue

            bar = prices[code]
            exec_price = bar  # 使用收盘价

            # 涨跌停检测
            df = self._stock_data.get(code)
            if df is not None:
                today_row = df[df['date'] == pd.Timestamp(date)]
                if len(today_row) > 0:
                    row = today_row.iloc[0]
                    exec_price = row['close']
                    pre_close = row.get('pre_close', exec_price)
                    if pre_close and pre_close > 0:
                        change_pct = (exec_price - pre_close) / pre_close
                        # 涨跌停阈值：科创板(688)/创业板(300)=20%，其他=10%
                        limit_pct = 0.195 if code.startswith(('688', '300')) else 0.095

                        # 涨停检测（买入）
                        order_amount = order_info.get('amount')
                        order_value_v = order_info.get('value')
                        is_buy = (order_amount is not None and order_amount > 0) or \
                                 (order_value_v is not None and order_value_v > 0)
                        is_sell = (order_amount is not None and order_amount < 0) or \
                                  (order_value_v is not None and order_value_v < 0)

                        if is_buy and change_pct >= limit_pct:
                            self._log_messages.append(
                                f"[{date}] [WARN] {code} 涨停({change_pct*100:.1f}%)，买入取消")
                            continue
                        # 跌停检测（卖出）
                        if is_sell and change_pct <= -limit_pct:
                            self._log_messages.append(
                                f"[{date}] [WARN] {code} 跌停({change_pct*100:.1f}%)，卖出取消")
                            continue

            # 确定成交数量
            amount = order_info.get('amount')
            if amount is None and order_info.get('value') is not None:
                value = order_info['value']
                if value > 0:
                    # 买入：按金额计算股数（取整百）
                    amount = int(value / exec_price / 100) * 100
                else:
                    # 卖出：按金额计算股数
                    amount = -int(abs(value) / exec_price / 100) * 100

            if amount is None or amount == 0:
                continue

            # 买入
            if amount > 0:
                amount = int(amount / 100) * 100  # 取整百
                if amount <= 0:
                    continue
                # 含滑点的实际成交价
                actual_price = exec_price * (1 + self.context.slippage_rate)
                total_cost = actual_price * amount
                commission = max(total_cost * self.context.commission_rate, 5.0)  # 最低5元
                required = total_cost + commission

                if required > self.context.portfolio.available_cash:
                    # 资金不足，减少买入量
                    affordable = self.context.portfolio.available_cash / (actual_price * (1 + self.context.commission_rate))
                    amount = int(affordable / 100) * 100
                    if amount <= 0:
                        continue
                    total_cost = actual_price * amount
                    commission = max(total_cost * self.context.commission_rate, 5.0)

                # 执行买入
                pos = self.context.portfolio._get_or_create_position(code)
                pos._on_buy(amount, exec_price, commission)
                self.context.portfolio.available_cash -= (total_cost + commission)

                trade = TradeRecord(date, code, pos.name, 'buy', exec_price, amount)
                trade.commission = round(commission, 2)
                trade.slippage_cost = round(exec_price * self.context.slippage_rate * amount, 2)
                self._trade_records.append(trade)

            # 卖出
            elif amount < 0:
                sell_amount = abs(amount)
                pos = self.context.portfolio.positions.get(code)
                if not pos or pos.closeable_amount <= 0:
                    continue

                sell_amount = min(sell_amount, pos.closeable_amount)
                sell_amount = int(sell_amount / 100) * 100
                if sell_amount <= 0:
                    # 可能不足100股但有余股，允许卖出
                    sell_amount = pos.closeable_amount

                actual_price = exec_price * (1 - self.context.slippage_rate)
                total_income = actual_price * sell_amount
                commission = max(total_income * self.context.commission_rate, 5.0)
                tax = total_income * self.context.stamp_tax_rate

                # 执行卖出
                pos._on_sell(sell_amount, exec_price)
                self.context.portfolio.available_cash += (total_income - commission - tax)

                trade = TradeRecord(date, code, pos.name, 'sell', exec_price, sell_amount)
                trade.commission = round(commission, 2)
                trade.tax = round(tax, 2)
                trade.slippage_cost = round(exec_price * self.context.slippage_rate * sell_amount, 2)
                self._trade_records.append(trade)

        self._pending_orders.clear()

    # ── 数据管理 ──

    def _discover_and_load_stocks(self, pre_start, end_date):
        """
        发现策略涉及的股票并预加载数据。
        初始化时从 context 的属性中提取股票代码。
        """
        # 从 context 中发现股票代码
        codes = set()
        for attr in dir(self.context):
            val = getattr(self.context, attr, None)
            if isinstance(val, str) and len(val) == 6 and val.isdigit():
                codes.add(val)
            elif isinstance(val, (list, tuple, set)):
                for item in val:
                    if isinstance(item, str) and len(item) == 6 and item.isdigit():
                        codes.add(item)

        # 也从 g 对象中发现
        for attr in dir(self.g):
            if attr.startswith('_'):
                continue
            val = getattr(self.g, attr, None)
            if isinstance(val, str) and len(val) == 6 and val.isdigit():
                codes.add(val)
            elif isinstance(val, (list, tuple, set)):
                for item in val:
                    if isinstance(item, str) and len(item) == 6 and item.isdigit():
                        codes.add(item)

        if codes:
            logging.info(f"[回测引擎] 预加载 {len(codes)} 只股票数据")
            self._stock_data = load_multiple_stocks(codes, pre_start, end_date)
            self._all_codes = codes

            # 设置历史数据到 data_proxy
            for code, df in self._stock_data.items():
                self.data_proxy._set_history(code, df)

    def _load_single_stock(self, code):
        """延迟加载单只股票"""
        if code in self._stock_data:
            return
        # 使用更早的开始日期来提供 history() 数据
        pre_start = None
        if self.context.current_dt:
            pre_start = (pd.Timestamp(self.context.current_dt) - pd.Timedelta(days=400)).strftime('%Y-%m-%d')
        df = load_stock_data(code, start_date=pre_start)
        if df is not None:
            self._stock_data[code] = df
            self.data_proxy._set_history(code, df)

    def _load_day_prices(self, date):
        """加载当日所有股票的收盘价，更新 data_proxy"""
        prices = {}
        ts_date = pd.Timestamp(date)

        for code, df in self._stock_data.items():
            mask = df['date'] == ts_date
            if mask.any():
                row = df.loc[mask].iloc[0]
                prices[code] = row['close']
                bar = {
                    'open': row.get('open', row['close']),
                    'high': row.get('high', row['close']),
                    'low': row.get('low', row['close']),
                    'close': row['close'],
                    'volume': row.get('volume', 0),
                    'pre_close': row.get('pre_close', row['close']),
                }
                self.data_proxy._set_current(code, bar)

        return prices


def run_backtest(strategy_code, start_date, end_date,
                 initial_cash=1000000, benchmark='000300',
                 commission=0.0003, tax=0.001, slippage=0.002):
    """
    便捷函数：运行回测并返回结果。

    用法：
        from instock.core.backtest.portfolio_engine import run_backtest
        result = run_backtest(strategy_code, '2024-01-01', '2025-01-01')
    """
    engine = PortfolioBacktestEngine()
    return engine.run(strategy_code, start_date, end_date,
                      initial_cash, benchmark, commission, tax, slippage)
