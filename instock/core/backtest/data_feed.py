#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据加载层 — 从本地 K 线缓存 / EastMoney API 加载回测用数据

支持：
- 从 cache/hist/ 加载单只/多只股票的日 K 线
- 当缓存不足时自动从 EastMoney API 补全
- 加载基准指数（沪深300等）日 K 线
- 获取交易日历
"""

import os
import logging
import datetime
import time
import pandas as pd
import numpy as np

__author__ = 'InStock'
__date__ = '2026/03/16'

# 缓存目录
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          'cache', 'hist')


def _fetch_stock_from_eastmoney(code, start_date=None, end_date=None, adjust='qfq'):
    """
    从 EastMoney API 获取个股日 K 线，返回标准化的 DataFrame。

    Returns:
        DataFrame with columns [date, open, high, low, close, volume] or None
    """
    try:
        from instock.core.crawling.stock_hist_em import stock_zh_a_hist
        sd = pd.Timestamp(start_date).strftime('%Y%m%d') if start_date else '19700101'
        ed = pd.Timestamp(end_date).strftime('%Y%m%d') if end_date else '20500101'
        raw = stock_zh_a_hist(symbol=code, start_date=sd, end_date=ed,
                              period='daily', adjust=adjust)
        if raw is None or len(raw) == 0:
            return None

        # 东方财富返回中文列名，需映射
        col_map = {'日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume'}
        df = raw.rename(columns=col_map)
        for c in ['date', 'open', 'high', 'low', 'close', 'volume']:
            if c not in df.columns:
                logging.warning(f"EastMoney数据缺少 {c} 列: {code}")
                return None
        df['date'] = pd.to_datetime(df['date'])
        for c in ['open', 'high', 'low', 'close']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        df = df.sort_values('date').reset_index(drop=True)
        logging.info(f"从 EastMoney 获取 {code} K线数据: {len(df)} 条 "
                     f"({df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()})")
        return df
    except Exception as e:
        logging.debug(f"EastMoney 获取 {code} 数据失败: {e}")
        return None


def _save_cache(code, df):
    """保存 DataFrame 到缓存文件"""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(_CACHE_DIR, f"{code}.gzip.pickle")
        df.to_pickle(cache_file)
        logging.debug(f"缓存已更新: {code} ({len(df)} 条)")
    except Exception as e:
        logging.debug(f"缓存保存失败 {code}: {e}")


def load_stock_data(code, start_date=None, end_date=None):
    """
    加载股票日 K 线数据。优先从缓存加载，缓存不足时从 EastMoney 补全。

    Args:
        code: 6位股票代码（如 '000001'）
        start_date: 开始日期（str 'YYYY-MM-DD' 或 date 对象）
        end_date: 结束日期

    Returns:
        DataFrame: 包含 date/open/high/low/close/volume/pre_close 列，
                   按日期升序排列。无数据返回 None。
    """
    df = _load_from_cache(code)
    need_online = False

    if df is None or len(df) == 0:
        need_online = True
    elif end_date:
        # 缓存最后日期是否覆盖 end_date（允许3天宽松度，周末/节假日）
        cache_end = df['date'].max().date() if hasattr(df['date'].max(), 'date') else df['date'].max()
        req_end = pd.Timestamp(end_date).date()
        if cache_end < req_end - datetime.timedelta(days=3):
            need_online = True
            logging.info(f"{code} 缓存截止 {cache_end}，需要数据到 {req_end}，尝试在线获取")

    if need_online:
        online_df = _fetch_stock_from_eastmoney(code, start_date, end_date)
        if online_df is not None and len(online_df) > 0:
            df = online_df
            # 更新缓存（保存完整获取范围）
            _save_cache(code, df)

    if df is None or len(df) == 0:
        return None

    # 日期过滤
    if start_date:
        df = df[df['date'] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df['date'] <= pd.Timestamp(end_date)]

    if len(df) == 0:
        return None

    # 计算前收盘价
    df = df.sort_values('date').reset_index(drop=True)
    df['pre_close'] = df['close'].shift(1)
    return df


def _load_from_cache(code):
    """
    从本地 pickle 缓存加载，返回 DataFrame 或 None

    缓存搜索顺序：
    1. stockfetch 统一缓存路径: cache/hist/{code[:3]}/{code}qfq.gzip.pickle（压缩pickle）
    2. data_feed 旧缓存路径: cache/hist/{code}.gzip.pickle（普通pickle）
    """
    # 优先：stockfetch 统一路径
    cache_dir_unified = os.path.join(_CACHE_DIR, code[:3])
    cache_file_unified = os.path.join(cache_dir_unified, f"{code}qfq.gzip.pickle")
    if os.path.exists(cache_file_unified):
        try:
            df = pd.read_pickle(cache_file_unified, compression="gzip")
            df = _normalize_cache_df(df)
            if df is not None:
                return df
        except Exception as e:
            logging.debug(f"读取统一缓存失败 {code}: {e}")

    # 降级：旧 data_feed 路径
    cache_file = os.path.join(_CACHE_DIR, f"{code}.gzip.pickle")
    if not os.path.exists(cache_file):
        return None
    try:
        df = pd.read_pickle(cache_file)
        return _normalize_cache_df(df)
    except Exception as e:
        logging.warning(f"加载K线缓存异常 {code}: {e}")
        return None


def _load_index_from_cache(code):
    """
    从指数缓存目录加载，返回 DataFrame 或 None

    缓存路径: cache/hist/index/{code}.gzip.pickle
    """
    cache_file = os.path.join(_CACHE_DIR, 'index', f"{code}.gzip.pickle")
    if not os.path.exists(cache_file):
        return None
    try:
        df = pd.read_pickle(cache_file, compression="gzip")
        return _normalize_cache_df(df)
    except Exception as e:
        logging.debug(f"加载指数缓存异常 {code}: {e}")
        return None


def _normalize_cache_df(df):
    """标准化缓存 DataFrame，确保包含必需列"""
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
        return None

    # 检查必需列
    for c in ['open', 'high', 'low', 'close', 'volume']:
        if c not in df.columns:
            return None

    return df.sort_values('date').reset_index(drop=True)


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

    优先级：
    1. 指数专用缓存（cache/hist/index/{code}.gzip.pickle）
    2. 股票缓存（兼容旧路径，用于非指数代码）
    3. AkShare 在线获取（最终降级）

    Args:
        code: 指数代码（默认沪深300 = '000300'）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        DataFrame: 包含 date/close 列。无数据返回 None。
    """
    # 1. 优先从指数缓存加载
    df = _load_index_from_cache(code)
    if df is not None:
        # 日期过滤
        if start_date:
            df = df[df['date'] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df['date'] <= pd.Timestamp(end_date)]
        if len(df) > 0:
            df = df.sort_values('date').reset_index(drop=True)
            df['pre_close'] = df['close'].shift(1)
            logging.info(f"从指数缓存加载基准 {code} 数据: {len(df)} 条")
            return df

    # 2. 降级：尝试从股票缓存加载（兼容旧数据）
    df = load_stock_data(code, start_date, end_date)
    if df is not None:
        return df

    # 3. 最终降级：尝试用 AkShare 获取指数数据
    # 主要上证/中证指数（以 0 开头但属上海交易所）
    _SH_INDICES = {'000001', '000002', '000003', '000016', '000300',
                   '000688', '000852', '000905', '000906', '000985'}
    try:
        import akshare as ak
        # 确定 AkShare 所需的前缀
        if code in _SH_INDICES or code.startswith(('9', '5')):
            ak_code = f"sh{code}"
        elif code.startswith(('6', '1')):
            ak_code = f"sh{code}"
        else:
            ak_code = f"sz{code}"

        idx_df = ak.stock_zh_index_daily(symbol=ak_code)
        if idx_df is not None and len(idx_df) > 0:
            idx_df['date'] = pd.to_datetime(idx_df['date'])
            if start_date:
                idx_df = idx_df[idx_df['date'] >= pd.Timestamp(start_date)]
            if end_date:
                idx_df = idx_df[idx_df['date'] <= pd.Timestamp(end_date)]
            idx_df = idx_df.sort_values('date').reset_index(drop=True)
            if len(idx_df) > 0:
                logging.info(f"从 AkShare 获取基准指数 {code} ({ak_code}) 数据: {len(idx_df)} 条")
                return idx_df

        # 如果上面失败，尝试另一前缀
        alt_code = f"sh{code}" if ak_code.startswith('sz') else f"sz{code}"
        logging.debug(f"尝试替代前缀 {alt_code}")
        idx_df = ak.stock_zh_index_daily(symbol=alt_code)
        if idx_df is not None and len(idx_df) > 0:
            idx_df['date'] = pd.to_datetime(idx_df['date'])
            if start_date:
                idx_df = idx_df[idx_df['date'] >= pd.Timestamp(start_date)]
            if end_date:
                idx_df = idx_df[idx_df['date'] <= pd.Timestamp(end_date)]
            idx_df = idx_df.sort_values('date').reset_index(drop=True)
            if len(idx_df) > 0:
                logging.info(f"从 AkShare 获取基准指数 {code} ({alt_code}) 数据: {len(idx_df)} 条")
                return idx_df
    except Exception as e:
        logging.debug(f"AkShare 获取指数数据失败: {e}")

    logging.warning(f"无法获取基准指数 {code} 的数据")
    return None
