#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2026/1/30
Desc: 新浪财经-个股资金流向数据
作为东方财富API的备选数据源
"""
import time
import random
import requests
import pandas as pd
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from instock.core.singleton_proxy import proxys

__author__ = 'InStock'
__date__ = '2026/1/30'


def stock_individual_fund_flow_rank_sina(indicator: str = "5日") -> pd.DataFrame:
    """
    新浪财经-资金流向排名
    http://vip.stock.finance.sina.com.cn/moneyflow/
    :param indicator: choice of {"今日", "3日", "5日", "10日"}
    :type indicator: str
    :return: 指定 indicator 资金流向排行
    :rtype: pandas.DataFrame
    """
    # 新浪资金流向页面
    indicator_map = {
        "今日": "1",
        "3日": "3", 
        "5日": "5",
        "10日": "10",
    }
    
    day = indicator_map.get(indicator, "5")
    all_stocks = []
    
    try:
        # 使用新浪资金流向接口
        url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_bkzj_zjlrqs"
        params = {
            "page": 1,
            "num": 5000,
            "sort": "netamount",
            "asc": 0,
            "fenlei": 0,
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://vip.stock.finance.sina.com.cn/',
        }
        
        response = requests.get(url, params=params, headers=headers, proxies=proxys().get_proxies(), timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        
        # 解析新浪返回的数据
        text = response.text
        if not text or text == 'null':
            return pd.DataFrame()
        
        # 新浪返回的是JSON格式
        import json
        data = json.loads(text)
        
        if not data:
            return pd.DataFrame()
        
        stocks = []
        for item in data:
            try:
                stock = {
                    '代码': item.get('symbol', '')[2:],  # 去掉sh/sz前缀
                    '名称': item.get('name', ''),
                    '最新价': _safe_float(item.get('trade', 0)),
                    '涨跌幅': _safe_float(item.get('changeratio', 0)) * 100,
                    '主力净流入': _safe_float(item.get('netamount', 0)),
                    '主力净流入占比': _safe_float(item.get('ratioamount', 0)) * 100,
                    '超大单净流入': 0,
                    '超大单净流入占比': 0,
                    '大单净流入': 0,
                    '大单净流入占比': 0,
                    '中单净流入': 0,
                    '中单净流入占比': 0,
                    '小单净流入': 0,
                    '小单净流入占比': 0,
                }
                stocks.append(stock)
            except Exception:
                continue
        
        if not stocks:
            return pd.DataFrame()
        
        temp_df = pd.DataFrame(stocks)
        return temp_df
        
    except Exception as e:
        print(f"新浪资金流向获取失败: {e}")
        return pd.DataFrame()


def _safe_float(value):
    """安全转换为浮点数"""
    try:
        if value is None or value == '' or value == '-':
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value):
    """安全转换为整数"""
    try:
        if value is None or value == '' or value == '-':
            return 0
        return int(float(value))
    except (ValueError, TypeError):
        return 0
