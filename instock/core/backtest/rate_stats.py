#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import numpy as np
import pandas as pd

__author__ = 'InStock'
__date__ = '2026/02/14'

# ====================================================================
# 交易成本参数（A股）
# 用于回测时从收益率中扣除，模拟真实交易的摩擦成本。
#
# 佣金: 买卖各 0.025%（万2.5，大部分券商水平）
# 印花税: 卖出时 0.05%（2023年8月28日起减半）
# 滑点: 买卖各 0.05%（保守估计）
#
# 单次交易（买入+卖出）总成本:
#   买入: 佣金 0.025% + 滑点 0.05% = 0.075%
#   卖出: 佣金 0.025% + 印花税 0.05% + 滑点 0.05% = 0.125%
#   合计: 0.20%
# ====================================================================
import instock.lib.envconfig as _cfg
COMMISSION_RATE = _cfg.get_float('INSTOCK_COMMISSION_RATE', 0.00025)   # 佣金比例（单边）
STAMP_TAX_RATE = _cfg.get_float('INSTOCK_STAMP_TAX_RATE', 0.0005)     # 印花税（卖出方）
SLIPPAGE_RATE = _cfg.get_float('INSTOCK_SLIPPAGE_RATE', 0.0005)       # 滑点（单边）

# 单次交易（买入+卖出）总成本百分比
ROUND_TRIP_COST_PCT = (COMMISSION_RATE + SLIPPAGE_RATE +    # 买入侧
                       COMMISSION_RATE + STAMP_TAX_RATE + SLIPPAGE_RATE  # 卖出侧
                       ) * 100  # 转为百分比，约 0.20%


def get_rates(code_name, data, stock_column, threshold=101):
    """
    计算选股信号的 N 日收益率序列。

    修正说明（v2）：
    1. 买入价使用信号日 T+1 的开盘价（而非 T 日收盘价），
       因为信号在 T 日收盘后产生，实盘最早在 T+1 开盘买入。
    2. 扣除交易成本（佣金+印花税+滑点），使回测更贴近真实收益。
    3. 过滤涨停/跌停：T+1 开盘涨停（无法买入）时返回 None。

    参数:
        code_name: (date, code) 元组，date 为信号日
        data: 含 date/open/close/high/low 的 DataFrame（已前复权）
        stock_column: 返回 Series 的列名列表 [date, code, rate_1, rate_2, ...]
        threshold: 最大回测天数+1

    返回:
        pd.Series: [date, code, rate_1, ..., rate_N]，其中 rate_N 为扣费后百分比收益
        None: 数据不足或无法交易
    """
    if data is None:
        return None

    try:
        start_date = code_name[0]
        code = code_name[1]
        stock_data_list = [start_date, code]

        # 统一 date 类型：缓存数据的 date 列可能是 datetime64/Timestamp/datetime.date，
        # 而 start_date 来自 SQL 结果转字符串（如 '2026-03-09'），
        # 混合类型无法直接比较，需统一为 pd.Timestamp。
        if not pd.api.types.is_datetime64_any_dtype(data['date']):
            data['date'] = pd.to_datetime(data['date'])
        if not isinstance(start_date, (pd.Timestamp, datetime.datetime)):
            start_date = pd.Timestamp(start_date)

        mask = (data['date'] >= start_date)
        data = data.loc[mask].copy()
        data = data.head(n=threshold)

        # 至少需要信号日(T) + 执行日(T+1) = 2 行
        if len(data.index) <= 1:
            return None

        # ----- 修正1: 使用 T+1 开盘价作为买入基准 -----
        # data.iloc[0] = 信号日(T)，data.iloc[1] = 执行日(T+1)
        if 'open' in data.columns:
            buy_price = data.iloc[1]['open']
            # 涨停检测：T+1 开盘价 >= T 收盘价 * 1.095（接近10%涨停）
            # 涨停时实际无法买入，回测应跳过
            t_close = data.iloc[0]['close']
            if buy_price > 0 and t_close > 0:
                gap_pct = (buy_price - t_close) / t_close
                if gap_pct >= 0.095:  # 涨停开盘，无法买入
                    return None
        else:
            # 缓存数据无 open 列时降级为 T 日收盘价（不推荐）
            buy_price = data.iloc[0]['close']

        if buy_price <= 0 or np.isnan(buy_price):
            return None

        # ----- 修正2: 计算收益率（从 T+1 开始）并扣除交易成本 -----
        # rate_N = N日持有收益 = (close[T+N] - buy_price) / buy_price * 100 - 交易成本
        # 注意：data.iloc[1] 对应 rate_1（持有1天），data.iloc[2] 对应 rate_2，...
        future_closes = data['close'].values[1:]  # T+1, T+2, ...
        raw_rates = np.around(100 * (future_closes - buy_price) / buy_price, decimals=2)
        # 扣除交易成本（每笔交易固定扣除，不随持有天数增加）
        net_rates = np.around(raw_rates - ROUND_TRIP_COST_PCT, decimals=2)

        for rate in net_rates:
            stock_data_list.append(rate)

        # 不足的部分填 None
        _l = len(stock_column) - len(stock_data_list)
        for i in range(0, _l):
            stock_data_list.append(None)

        return pd.Series(stock_data_list, index=stock_column)
    except Exception as e:
        logging.error(f"rate_stats.get_rates处理异常：{code_name}代码", exc_info=True)
        return None
