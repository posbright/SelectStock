#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据加载层 — 从本地 K 线缓存加载回测用数据

支持：
- 从 cache/hist/ 加载单只/多只股票的日 K 线
- 加载基准指数（沪深300等）日 K 线
- 获取交易日历
"""

import os
import logging
import datetime
import pandas as pd
import numpy as np

__author__ = 'InStock'
__date__ = '2026/03/13'

# 缓存目录
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          'cache', 'hist')


def load_stock_data(code, start_date=None, end_date=None):
    """
    从本地缓存加载股票日 K 线数据。

    Args:
        code: 6位股票代码（如 '000001'）
        start_date: 开始日期（str 'YYYY-MM-DD' 或 date 对象）
        end_date: 结束日期

    Returns:
        DataFrame: 包含 date/open/high/low/close/volume/p_change 列，
                   按日期升序排列。无数据返回 None。
    """
    cache_file = os.path.join(_CACHE_DIR, f"{code}.gzip.pickle")
    if not os.path.exists(cache_file):
        logging.debug(f"缓存文件不存在: {cache_file}")
        return None

    try:
        df = pd.read_pickle(cache_file)
        if df is None or len(df) == 0:
            return None

        # 确保日期列
        if 'date' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'])
        elif df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={df.columns[0]: 'date'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])

        if 'date' not in df.columns:
            logging.warning(f"K线数据缺少 date 列: {code}")
            return None

        df = df.sort_values('date').reset_index(drop=True)

        # 日期过滤
        if start_date:
            start = pd.Timestamp(start_date)
            df = df[df['date'] >= start]
        if end_date:
            end = pd.Timestamp(end_date)
            df = df[df['date'] <= end]

        if len(df) == 0:
            return None

        # 标准化列名
        col_map = {
            'open': 'open', 'high': 'high', 'low': 'low',
            'close': 'close', 'volume': 'volume',
        }
        for need_col in col_map.values():
            if need_col not in df.columns:
                logging.warning(f"K线数据缺少 {need_col} 列: {code}")
                return None

        # 计算前收盘价
        df['pre_close'] = df['close'].shift(1)

        return df.reset_index(drop=True)

    except Exception as e:
        logging.warning(f"加载K线缓存异常 {code}: {e}")
        return None


def load_multiple_stocks(codes, start_date=None, end_date=None):
    """
    批量加载多只股票数据。

    Args:
        codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        dict: {code: DataFrame}，无数据的股票不包含
    """
    result = {}
    for code in codes:
        df = load_stock_data(code, start_date, end_date)
        if df is not None and len(df) > 0:
            result[code] = df
    return result


def get_trading_dates(start_date, end_date):
    """
    获取交易日列表。

    优先从数据库 cn_stock_trade_date 获取，
    降级为从任一股票的 K 线缓存提取。

    Returns:
        list[datetime.date]: 交易日列表，升序
    """
    # 尝试从数据库获取
    try:
        import instock.lib.trade_time as trd
        from instock.core.singleton_trade_date import stock_trade_date
        all_dates = stock_trade_date().get_data()
        if all_dates:
            start = pd.Timestamp(start_date).date() if isinstance(start_date, str) else start_date
            end = pd.Timestamp(end_date).date() if isinstance(end_date, str) else end_date
            dates = sorted([d for d in all_dates if start <= d <= end])
            if dates:
                return dates
    except Exception:
        pass

    # 降级：从沪深300或000001的缓存提取交易日
    for code in ['000001', '600000', '000300']:
        df = load_stock_data(code, start_date, end_date)
        if df is not None and len(df) > 0:
            dates = sorted(df['date'].dt.date.tolist())
            return dates

    # 最终降级：pd.bdate_range
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    return [d.date() for d in pd.bdate_range(start, end)]


def load_benchmark_data(code='000300', start_date=None, end_date=None):
    """
    加载基准指数 K 线数据。

    首先尝试从缓存加载，如果没有则尝试从 AkShare 获取。

    Args:
        code: 指数代码（默认沪深300 = '000300'）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        DataFrame: 包含 date/close 列。无数据返回 None。
    """
    # 尝试从缓存加载
    df = load_stock_data(code, start_date, end_date)
    if df is not None:
        return df

    # 尝试用 AkShare 获取指数数据
    try:
        import akshare as ak
        # AkShare 的指数代码不同：沪市前缀 sh，深市前缀 sz
        if code.startswith('0'):
            ak_code = f"sz{code}"
        else:
            ak_code = f"sh{code}"

        start_str = pd.Timestamp(start_date).strftime('%Y%m%d') if start_date else '20150101'
        end_str = pd.Timestamp(end_date).strftime('%Y%m%d') if end_date else datetime.datetime.now().strftime('%Y%m%d')

        idx_df = ak.stock_zh_index_daily(symbol=ak_code)
        if idx_df is not None and len(idx_df) > 0:
            idx_df = idx_df.rename(columns={'date': 'date'})
            idx_df['date'] = pd.to_datetime(idx_df['date'])
            if start_date:
                idx_df = idx_df[idx_df['date'] >= pd.Timestamp(start_date)]
            if end_date:
                idx_df = idx_df[idx_df['date'] <= pd.Timestamp(end_date)]
            idx_df = idx_df.sort_values('date').reset_index(drop=True)
            if len(idx_df) > 0:
                logging.info(f"从 AkShare 获取基准指数 {code} 数据: {len(idx_df)} 条")
                return idx_df
    except Exception as e:
        logging.debug(f"AkShare 获取指数数据失败: {e}")

    logging.warning(f"无法获取基准指数 {code} 的数据")
    return None
