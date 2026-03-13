#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险指标计算

从每日净值序列计算回测风险指标：
- 累计收益率 / 年化收益率
- 最大回撤
- 夏普比率
- Alpha / Beta
- 胜率 / 交易统计
"""

import numpy as np
import pandas as pd

__author__ = 'InStock'
__date__ = '2026/03/13'

# 每年交易日数
_TRADING_DAYS_PER_YEAR = 245
# 无风险年化利率（1年定期存款约1.5%）
_RISK_FREE_RATE = 0.015


def calculate_metrics(nav_series, benchmark_series=None, trades=None, risk_free_rate=_RISK_FREE_RATE):
    """
    计算回测风险指标。

    Args:
        nav_series: list/array of daily NAV values (从1.0开始)
        benchmark_series: list/array of benchmark NAV values (可选)
        trades: list of TradeRecord (可选)
        risk_free_rate: 年化无风险利率

    Returns:
        dict: 风险指标字典
    """
    nav = np.array(nav_series, dtype=float)
    n_days = len(nav)

    if n_days < 2:
        return _empty_metrics()

    # ---- 收益率 ----
    total_return = (nav[-1] / nav[0] - 1) * 100
    n_years = n_days / _TRADING_DAYS_PER_YEAR
    annual_return = ((nav[-1] / nav[0]) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # ---- 日收益率 ----
    daily_returns = np.diff(nav) / nav[:-1]

    # ---- 最大回撤 ----
    peak = np.maximum.accumulate(nav)
    drawdown = (nav - peak) / peak
    max_drawdown = abs(float(np.min(drawdown))) * 100

    # ---- 夏普比率 ----
    daily_rf = risk_free_rate / _TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf
    sharpe = 0.0
    if len(excess_returns) > 1 and np.std(excess_returns) > 0:
        sharpe = float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(_TRADING_DAYS_PER_YEAR))

    # ---- 日胜率 ----
    win_days = int(np.sum(daily_returns > 0))
    total_days = len(daily_returns)
    daily_win_rate = win_days / total_days * 100 if total_days > 0 else 0

    # ---- Alpha / Beta ----
    alpha = 0.0
    beta = 0.0
    benchmark_return = 0.0
    if benchmark_series is not None and len(benchmark_series) == n_days:
        bm = np.array(benchmark_series, dtype=float)
        benchmark_return = (bm[-1] / bm[0] - 1) * 100
        bm_daily = np.diff(bm) / bm[:-1]
        if len(bm_daily) > 1 and np.std(bm_daily) > 0:
            cov = np.cov(daily_returns, bm_daily)
            beta = float(cov[0, 1] / cov[1, 1])
            alpha_daily = np.mean(daily_returns) - daily_rf - beta * (np.mean(bm_daily) - daily_rf)
            alpha = float(alpha_daily * _TRADING_DAYS_PER_YEAR * 100)

    # ---- 交易统计 ----
    trade_count = 0
    trade_win_count = 0
    if trades:
        # 计算配对交易的胜率
        buy_records = {}  # {code: [buy_price, ...]}
        sell_records = []
        for t in trades:
            if t.direction == 'buy':
                buy_records.setdefault(t.code, []).append(t.price)
            elif t.direction == 'sell' and t.code in buy_records and buy_records[t.code]:
                buy_price = buy_records[t.code].pop(0)
                sell_records.append((buy_price, t.price))
                trade_count += 1
                if t.price > buy_price:
                    trade_win_count += 1
        trade_win_rate = trade_win_count / trade_count * 100 if trade_count > 0 else 0
    else:
        trade_win_rate = 0

    total_trades = len(trades) if trades else 0

    return {
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'benchmark_return': round(benchmark_return, 4),
        'max_drawdown': round(max_drawdown, 4),
        'sharpe_ratio': round(sharpe, 4),
        'alpha': round(alpha, 4),
        'beta': round(beta, 4),
        'daily_win_rate': round(daily_win_rate, 2),
        'trade_win_rate': round(trade_win_rate, 2),
        'trade_count': total_trades,
        'win_count': trade_win_count,
        'trading_days': n_days,
    }


def _empty_metrics():
    return {
        'total_return': 0, 'annual_return': 0, 'benchmark_return': 0,
        'max_drawdown': 0, 'sharpe_ratio': 0, 'alpha': 0, 'beta': 0,
        'daily_win_rate': 0, 'trade_win_rate': 0, 'trade_count': 0,
        'win_count': 0, 'trading_days': 0,
    }
