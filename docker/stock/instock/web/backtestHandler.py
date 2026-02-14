#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义回测 API Handler

支持用户指定股票代码、策略、回测时长来执行回测并返回结果。
"""

import json
import logging
import datetime
import numpy as np
import pandas as pd
from abc import ABC
from tornado import gen
import instock.web.base as webBase
import instock.core.stockfetch as stf
import instock.core.tablestructure as tbs
import instock.core.indicator.calculate_indicator as idr
import instock.core.pattern.pattern_recognitions as kpr
import instock.lib.trade_time as trd
import instock.lib.database as mdb

__author__ = 'InStock'
__date__ = '2026/02/14'


# 可选回测周期
BACKTEST_PERIODS = {
    '1w': {'label': '1周', 'days': 5},
    '2w': {'label': '2周', 'days': 10},
    '1m': {'label': '1个月', 'days': 20},
    '3m': {'label': '3个月', 'days': 60},
    '6m': {'label': '6个月', 'days': 120},
    '1y': {'label': '1年', 'days': 250},
}

# 可选策略列表
STRATEGY_LIST = []
for s in tbs.TABLE_CN_STOCK_STRATEGIES:
    STRATEGY_LIST.append({
        'name': s['name'],
        'cn': s['cn'],
        'type': 'strategy'
    })
STRATEGY_LIST.append({
    'name': 'indicators_buy',
    'cn': '指标买入信号',
    'type': 'indicator'
})
STRATEGY_LIST.append({
    'name': 'indicators_sell',
    'cn': '指标卖出信号',
    'type': 'indicator'
})


class GetBacktestConfigHandler(webBase.BaseHandler, ABC):
    """获取回测配置（可选周期、策略列表）"""
    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        response = {
            'periods': [{'value': k, 'label': v['label'], 'days': v['days']} for k, v in BACKTEST_PERIODS.items()],
            'strategies': STRATEGY_LIST,
        }
        self.write(json.dumps(response, ensure_ascii=False))


class RunBacktestHandler(webBase.BaseHandler, ABC):
    """执行自定义回测"""
    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        
        code = self.get_argument("code", default=None, strip=True)
        strategy = self.get_argument("strategy", default=None, strip=True)
        period = self.get_argument("period", default="1m", strip=True)
        start_date = self.get_argument("start_date", default=None, strip=True)
        end_date = self.get_argument("end_date", default=None, strip=True)
        
        try:
            result = _run_backtest(code, strategy, period, start_date, end_date)
            self.write(json.dumps(result, ensure_ascii=False, default=_json_default))
        except Exception as e:
            logging.error(f"RunBacktestHandler处理异常", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({"error": str(e)}, ensure_ascii=False))


class RunBatchBacktestHandler(webBase.BaseHandler, ABC):
    """批量回测：对某策略在指定时间段内的所有选股记录进行回测"""
    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        
        strategy = self.get_argument("strategy", default=None, strip=True)
        period = self.get_argument("period", default="1m", strip=True)
        limit = self.get_argument("limit", default="30", strip=True)
        
        if not strategy:
            self.set_status(400)
            self.write(json.dumps({"error": "缺少 strategy 参数"}, ensure_ascii=False))
            return
        
        try:
            result = _run_batch_backtest(strategy, period, int(limit))
            self.write(json.dumps(result, ensure_ascii=False, default=_json_default))
        except Exception as e:
            logging.error(f"RunBatchBacktestHandler处理异常", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({"error": str(e)}, ensure_ascii=False))


def _json_default(obj):
    """JSON 序列化辅助"""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return round(float(obj), 4) if not np.isnan(obj) else None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if pd.isna(obj):
        return None
    return str(obj)


def _run_backtest(code, strategy, period, start_date_str, end_date_str):
    """
    对单只股票执行回测
    
    参数：
        code: 股票代码（如 "000001"）
        strategy: 策略名称（如 "cn_stock_strategy_enter"）或 None（只看收益）
        period: 回测周期（"1w"/"2w"/"1m"/"3m"/"6m"/"1y"）
        start_date_str: 起始日期 YYYY-MM-DD（可选）
        end_date_str: 结束日期 YYYY-MM-DD（可选）
    
    返回：
        {
            code, name, period,
            buy_date, buy_price,
            returns: [{days, rate, price}, ...],  # 各周期收益率
            strategy_result: True/False,  # 策略是否命中
            indicators: {kdjk, rsi_6, ...}  # 关键指标值
        }
    """
    if not code:
        return {"error": "缺少股票代码参数"}
    
    period_info = BACKTEST_PERIODS.get(period, BACKTEST_PERIODS['1m'])
    max_days = period_info['days']
    
    # 计算日期范围
    now = datetime.datetime.now()
    years = stf.HIST_DATA_DEFAULT_YEARS
    cache_start, _ = trd.get_trade_hist_interval(now, years)
    cache_end = now.strftime("%Y%m%d")
    
    # 读取历史数据
    hist = stf.read_stock_hist_from_cache(code, cache_start, cache_end)
    if hist is None or len(hist) == 0:
        return {"error": f"股票 {code} 无缓存数据，请先执行数据获取"}
    
    # 确定买入日期
    if start_date_str:
        buy_date = start_date_str
    else:
        # 默认使用有足够后续数据的日期（倒数第 max_days+1 天）
        # 避免选最后一天导致 "之后无足够交易数据" 错误
        idx = max(0, len(hist) - max_days - 1)
        buy_date = hist['date'].iloc[idx]
    
    # 获取买入日及之后的数据
    mask = hist['date'] >= buy_date
    future_data = hist.loc[mask].head(max_days + 1)
    
    if len(future_data) <= 1:
        return {"error": f"买入日 {buy_date} 之后无足够交易数据"}
    
    buy_price = future_data.iloc[0]['close']
    buy_date_actual = future_data.iloc[0]['date']
    
    # 计算各天收益率
    returns = []
    checkpoints = [1, 3, 5, 10, 20, 40, 60, 120, 250]
    for days in checkpoints:
        if days > max_days:
            break
        if days < len(future_data):
            sell_price = future_data.iloc[days]['close']
            rate = round(100 * (sell_price - buy_price) / buy_price, 2)
            sell_date = future_data.iloc[days]['date']
            returns.append({
                'days': days,
                'rate': rate,
                'price': round(float(sell_price), 2),
                'date': sell_date
            })
    
    # 计算区间最高/最低
    if len(future_data) > 1:
        high_price = float(future_data['high'].max())
        low_price = float(future_data['low'].min())
        max_return = round(100 * (high_price - buy_price) / buy_price, 2)
        max_drawdown = round(100 * (low_price - buy_price) / buy_price, 2)
    else:
        max_return = 0
        max_drawdown = 0
    
    # 策略检测
    strategy_result = None
    if strategy:
        strategy_result = _check_strategy(strategy, code, hist, buy_date)
    
    # 计算关键指标
    indicators = _calc_key_indicators(hist, buy_date)
    
    # 获取股票名称
    stock_name = _get_stock_name(code)
    
    result = {
        'code': code,
        'name': stock_name,
        'period': period_info['label'],
        'buy_date': buy_date_actual,
        'buy_price': round(float(buy_price), 2),
        'returns': returns,
        'max_return': max_return,
        'max_drawdown': max_drawdown,
        'strategy': strategy,
        'strategy_result': strategy_result,
        'indicators': indicators,
        'data_points': len(future_data) - 1,
    }
    return result


def _run_batch_backtest(strategy_name, period, limit=30):
    """
    批量回测：从策略表读取历史选股记录，计算各周期收益
    
    返回：
        {
            strategy, period, total, success_count, success_rate,
            avg_returns: {1d, 5d, 10d, 20d},
            details: [{date, stock_count, avg_rate, success_rate}, ...]
        }
    """
    period_info = BACKTEST_PERIODS.get(period, BACKTEST_PERIODS['1m'])
    max_days = period_info['days']
    
    # 查找策略对应的表名
    table_name = None
    strategy_cn = strategy_name
    for s in tbs.TABLE_CN_STOCK_STRATEGIES:
        if s['name'] == strategy_name:
            table_name = s['name']
            strategy_cn = s['cn']
            break
    if table_name is None:
        if strategy_name == 'indicators_buy':
            table_name = tbs.TABLE_CN_STOCK_INDICATORS_BUY['name']
            strategy_cn = '指标买入信号'
        elif strategy_name == 'indicators_sell':
            table_name = tbs.TABLE_CN_STOCK_INDICATORS_SELL['name']
            strategy_cn = '指标卖出信号'
        else:
            return {"error": f"未知策略: {strategy_name}"}
    
    if not mdb.checkTableIsExist(table_name):
        return {"error": f"策略表 {table_name} 不存在"}
    
    # 读取策略表中有回测数据的记录
    try:
        # 获取每日汇总
        rate_col = f'rate_{min(max_days, 20)}'
        sql = f"""SELECT `date`, COUNT(*) as stock_count,
                  ROUND(AVG(`rate_1`), 2) as avg_1d,
                  ROUND(AVG(`rate_5`), 2) as avg_5d,
                  ROUND(AVG(`rate_10`), 2) as avg_10d,
                  ROUND(AVG(`rate_20`), 2) as avg_20d,
                  SUM(CASE WHEN `{rate_col}` > 0 THEN 1 ELSE 0 END) as success_count
                  FROM `{table_name}` 
                  WHERE `rate_1` IS NOT NULL
                  GROUP BY `date` ORDER BY `date` DESC LIMIT {limit}"""
        data = pd.read_sql(sql=sql, con=mdb.engine())
    except Exception as e:
        return {"error": f"查询失败: {e}"}
    
    if data is None or len(data) == 0:
        return {"error": "无回测数据，请先执行策略计算和回测"}
    
    # 汇总统计
    total_stocks = int(data['stock_count'].sum())
    total_success = int(data['success_count'].sum())
    overall_success_rate = round(100 * total_success / total_stocks, 2) if total_stocks > 0 else 0
    
    details = []
    for _, row in data.iterrows():
        sc = int(row['stock_count'])
        succ = int(row['success_count'])
        details.append({
            'date': row['date'],
            'stock_count': sc,
            'success_count': succ,
            'success_rate': round(100 * succ / sc, 2) if sc > 0 else 0,
            'avg_1d': row['avg_1d'],
            'avg_5d': row['avg_5d'],
            'avg_10d': row['avg_10d'],
            'avg_20d': row['avg_20d'],
        })
    
    result = {
        'strategy': strategy_cn,
        'strategy_name': strategy_name,
        'period': period_info['label'],
        'total_stocks': total_stocks,
        'total_days': len(data),
        'success_count': total_success,
        'success_rate': overall_success_rate,
        'avg_returns': {
            '1d': round(float(data['avg_1d'].mean()), 2) if not data['avg_1d'].isna().all() else 0,
            '5d': round(float(data['avg_5d'].mean()), 2) if not data['avg_5d'].isna().all() else 0,
            '10d': round(float(data['avg_10d'].mean()), 2) if not data['avg_10d'].isna().all() else 0,
            '20d': round(float(data['avg_20d'].mean()), 2) if not data['avg_20d'].isna().all() else 0,
        },
        'details': details,
    }
    return result


def _check_strategy(strategy_name, code, hist_data, buy_date):
    """检测某策略是否在买入日命中"""
    try:
        date_obj = datetime.datetime.strptime(buy_date, "%Y-%m-%d").date() if isinstance(buy_date, str) else buy_date
        stock = (date_obj, code)
        
        for s in tbs.TABLE_CN_STOCK_STRATEGIES:
            if s['name'] == strategy_name:
                return bool(s['func'](stock, hist_data, date=date_obj))
        
        return None  # 不支持/未找到
    except Exception as e:
        logging.debug(f"策略检测异常：{code} {strategy_name} - {e}")
        return None


def _calc_key_indicators(hist_data, buy_date):
    """计算买入日的关键技术指标"""
    try:
        result = idr.get_indicators(hist_data, end_date=buy_date, threshold=1, calc_threshold=90)
        if result is None or len(result) == 0:
            return {}
        
        row = result.iloc[-1]
        return {
            'kdjk': _safe_round(row.get('kdjk')),
            'kdjd': _safe_round(row.get('kdjd')),
            'rsi_6': _safe_round(row.get('rsi_6')),
            'macd': _safe_round(row.get('macd')),
            'cci': _safe_round(row.get('cci')),
            'cr': _safe_round(row.get('cr')),
            'wr_6': _safe_round(row.get('wr_6')),
            'vr': _safe_round(row.get('vr')),
            'atr': _safe_round(row.get('atr')),
        }
    except Exception:
        return {}


def _safe_round(val, decimals=2):
    """安全取整"""
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return None
    return round(float(val), decimals)


def _get_stock_name(code):
    """通过数据库查询股票名称"""
    try:
        table = tbs.TABLE_CN_STOCK_SPOT['name']
        if mdb.checkTableIsExist(table):
            sql = f"SELECT `name` FROM `{table}` WHERE `code` = %s LIMIT 1"
            result = pd.read_sql(sql, mdb.engine(), params=(code,))
            if result is not None and len(result) > 0:
                return result.iloc[0]['name']
    except Exception:
        pass
    return code
