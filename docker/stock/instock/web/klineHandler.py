#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K线数据JSON API

提供前端ECharts所需的K线数据（OHLCV + 技术指标），
用于替代Bokeh服务端渲染方式。
"""

import json
import logging
import datetime
import numpy as np
from abc import ABC

import instock.core.stockfetch as stf
import instock.web.base as webBase

__author__ = 'InStock'
__date__ = '2026/02/14'


def _safe_float(val):
    """将 numpy/pandas 数值转为 Python float，NaN 转 None"""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _compute_ma(closes, period):
    """计算移动平均线"""
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            avg = sum(closes[i - period + 1:i + 1]) / period
            result.append(round(avg, 4))
    return result


def _compute_ema(closes, period):
    """计算指数移动平均线"""
    result = []
    k = 2.0 / (period + 1)
    ema = None
    for c in closes:
        if c is None:
            result.append(None)
            continue
        if ema is None:
            ema = c
        else:
            ema = c * k + ema * (1 - k)
        result.append(round(ema, 4))
    return result


def _compute_boll(closes, period=20, nbdev=2):
    """计算布林带 (上轨, 中轨, 下轨)"""
    upper, middle, lower = [], [], []
    for i in range(len(closes)):
        if i < period - 1:
            upper.append(None)
            middle.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            ma = sum(window) / period
            std = (sum((x - ma) ** 2 for x in window) / period) ** 0.5
            middle.append(round(ma, 4))
            upper.append(round(ma + nbdev * std, 4))
            lower.append(round(ma - nbdev * std, 4))
    return upper, middle, lower


def _compute_rsi(closes, period=14):
    """计算RSI"""
    result = [None]
    for i in range(1, len(closes)):
        if i < period:
            result.append(None)
            continue
        gains, losses = 0.0, 0.0
        for j in range(i - period + 1, i + 1):
            diff = closes[j] - closes[j - 1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))
    return result


def _compute_macd(closes, fast=12, slow=26, signal=9):
    """计算MACD (DIF, DEA, MACD柱)"""
    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)
    dif = []
    for ef, es in zip(ema_fast, ema_slow):
        if ef is None or es is None:
            dif.append(None)
        else:
            dif.append(round(ef - es, 4))
    # DEA = EMA(DIF, signal)
    dea = _compute_ema([d if d is not None else 0 for d in dif], signal)
    macd_hist = []
    for d, a in zip(dif, dea):
        if d is None or a is None:
            macd_hist.append(None)
        else:
            macd_hist.append(round(2 * (d - a), 4))
    return dif, dea, macd_hist


def _resample_to_period(df, period):
    """
    将日线数据重采样为周线/月线/季线/年线
    period: 'W' / 'M' / 'Q' / 'Y'
    """
    import pandas as pd
    if df is None or df.empty:
        return df

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')

    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }
    # 只聚合存在的列
    agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

    if period == 'W':
        resampled = df.resample('W-FRI').agg(agg_dict)
    elif period == 'M':
        resampled = df.resample('ME').agg(agg_dict)
    elif period == 'Q':
        resampled = df.resample('QE').agg(agg_dict)
    elif period == 'Y':
        resampled = df.resample('YE').agg(agg_dict)
    else:
        return df.reset_index()

    resampled = resampled.dropna(subset=['open'])
    resampled = resampled.reset_index()
    resampled['date'] = resampled['date'].dt.strftime('%Y-%m-%d')
    return resampled


class GetKlineDataHandler(webBase.BaseHandler, ABC):
    """
    K线数据JSON API

    参数:
        code: 股票代码 (必填)
        date: 日期 (可选, 默认今天)
        period: 周期 (可选, 默认 'daily')
                可选值: daily / weekly / monthly / quarterly / yearly
        days: 返回天数 (可选, 默认根据period自动设置)

    返回:
        {
            code, name, period,
            dates: [...],
            ohlc: [[open, close, low, high], ...],
            volumes: [...],
            ma: {ma5: [...], ma10: [...], ma20: [...], ma60: [...]},
            boll: {upper: [...], middle: [...], lower: [...]},
            rsi: [...],
            macd: {dif: [...], dea: [...], histogram: [...]},
        }
    """

    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        code = self.get_argument("code", default=None, strip=True)
        date = self.get_argument("date", default=None, strip=True)
        period = self.get_argument("period", default="daily", strip=True)
        days = self.get_argument("days", default=None, strip=True)
        name = self.get_argument("name", default="", strip=True)

        if not code:
            self.set_status(400)
            self.write(json.dumps({"error": "缺少 code 参数"}, ensure_ascii=False))
            return

        try:
            if date is None:
                date = datetime.datetime.now().strftime('%Y-%m-%d')

            # 获取历史K线
            if code.startswith(('1', '5')):
                stock = stf.fetch_etf_hist((date, code))
            else:
                stock = stf.fetch_stock_hist((date, code))

            if stock is None or stock.empty:
                self.write(json.dumps({"error": "无K线数据", "code": code}, ensure_ascii=False))
                return

            # 根据 period 重采样
            period_map = {
                'daily': None,
                'weekly': 'W',
                'monthly': 'M',
                'quarterly': 'Q',
                'yearly': 'Y',
            }
            resample_key = period_map.get(period)
            if resample_key:
                stock = _resample_to_period(stock, resample_key)

            # 截取数据天数
            if days:
                try:
                    n = int(days)
                    if n > 0 and n < len(stock):
                        stock = stock.tail(n).reset_index(drop=True)
                except (ValueError, TypeError):
                    pass
            else:
                # 默认天数: daily=120, weekly=104, monthly=60, quarterly=40, yearly=20
                default_days = {
                    'daily': 120, 'weekly': 104, 'monthly': 60,
                    'quarterly': 40, 'yearly': 20
                }
                n = default_days.get(period, 120)
                if n < len(stock):
                    stock = stock.tail(n).reset_index(drop=True)

            # 提取数据
            dates = stock['date'].astype(str).tolist()
            opens = [_safe_float(v) for v in stock['open'].tolist()]
            closes = [_safe_float(v) for v in stock['close'].tolist()]
            highs = [_safe_float(v) for v in stock['high'].tolist()]
            lows = [_safe_float(v) for v in stock['low'].tolist()]
            volumes = [int(v) if v == v else 0 for v in stock['volume'].tolist()]

            # OHLC 格式 (ECharts candlestick: [open, close, low, high])
            ohlc = []
            for o, c, l, h in zip(opens, closes, lows, highs):
                ohlc.append([o, c, l, h])

            # 用于计算指标的 close 数组（None->0）
            closes_clean = [c if c is not None else 0 for c in closes]

            # 计算指标
            ma5 = _compute_ma(closes_clean, 5)
            ma10 = _compute_ma(closes_clean, 10)
            ma20 = _compute_ma(closes_clean, 20)
            ma60 = _compute_ma(closes_clean, 60)
            boll_upper, boll_middle, boll_lower = _compute_boll(closes_clean, 20, 2)
            rsi = _compute_rsi(closes_clean, 14)
            macd_dif, macd_dea, macd_hist = _compute_macd(closes_clean, 12, 26, 9)

            result = {
                "code": code,
                "name": name,
                "period": period,
                "total": len(dates),
                "dates": dates,
                "ohlc": ohlc,
                "volumes": volumes,
                "ma": {
                    "ma5": ma5,
                    "ma10": ma10,
                    "ma20": ma20,
                    "ma60": ma60,
                },
                "boll": {
                    "upper": boll_upper,
                    "middle": boll_middle,
                    "lower": boll_lower,
                },
                "rsi": rsi,
                "macd": {
                    "dif": macd_dif,
                    "dea": macd_dea,
                    "histogram": macd_hist,
                },
            }

            self.write(json.dumps(result, ensure_ascii=False))

        except Exception as e:
            logging.error(f"klineHandler.GetKlineDataHandler处理异常", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({"error": str(e)}, ensure_ascii=False))
