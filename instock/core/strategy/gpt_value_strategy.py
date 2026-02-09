#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT综合选股策略

基于 ChatGP选股策略文档.md 中定义的选股标准：
1. 财务安全过滤 - 资产负债率 < 60%, 每股经营现金流 > 0
2. 盈利能力筛选 - ROE >= 15%, 毛利率 >= 30%, 净利率 >= 10%
3. 成长质量筛选 - 营收3年CAGR > 10%, 净利润3年CAGR > 10%
4. 估值约束 - PE(TTM) 在合理范围

这个策略使用 cn_stock_selection 表中的财务数据进行筛选。
"""

import pandas as pd

__author__ = 'InStock'
__date__ = '2026/02/09'


def check_gpt_value(code_name, data, date=None, threshold=60):
    """
    GPT综合选股策略检查函数
    
    由于这是一个基本面策略，需要使用 cn_stock_selection 表的数据，
    而不是历史K线数据。此函数用于兼容现有的策略框架。
    
    实际筛选逻辑在 selection_data_job 中执行。
    
    Args:
        code_name: (date, code, name) 元组
        data: K线历史数据 DataFrame
        date: 日期
        threshold: 最小数据长度要求
        
    Returns:
        bool: 是否满足条件
    """
    # 基本面策略无法使用K线数据判断
    # 这里返回False，实际筛选通过专门的 job 完成
    return False


def check_gpt_value_from_selection(stock_row):
    """
    从 cn_stock_selection 数据中检查是否满足GPT综合选股条件
    
    Args:
        stock_row: pd.Series, cn_stock_selection 表中的一行数据
        
    Returns:
        bool: 是否满足所有条件
    """
    try:
        # ===== 第一层：财务安全过滤 =====
        # 资产负债率 < 60%
        debt_ratio = stock_row.get('debt_asset_ratio', None)
        if debt_ratio is None or pd.isna(debt_ratio) or debt_ratio >= 60:
            return False
        
        # 每股经营现金流 > 0
        cashflow = stock_row.get('per_netcash_operate', None)
        if cashflow is None or pd.isna(cashflow) or cashflow <= 0:
            return False
        
        # ===== 第二层：盈利能力筛选 =====
        # ROE >= 15%
        roe = stock_row.get('roe_weight', None)
        if roe is None or pd.isna(roe) or roe < 15:
            return False
        
        # 毛利率 >= 30%
        gpr = stock_row.get('sale_gpr', None)
        if gpr is None or pd.isna(gpr) or gpr < 30:
            return False
        
        # 净利率 >= 10%
        npr = stock_row.get('sale_npr', None)
        if npr is None or pd.isna(npr) or npr < 10:
            return False
        
        # ===== 第三层：成长质量筛选 =====
        # 营收3年CAGR > 10%
        revenue_growth = stock_row.get('income_growthrate_3y', None)
        if revenue_growth is None or pd.isna(revenue_growth) or revenue_growth <= 10:
            return False
        
        # 净利润3年CAGR > 10%
        profit_growth = stock_row.get('netprofit_growthrate_3y', None)
        if profit_growth is None or pd.isna(profit_growth) or profit_growth <= 10:
            return False
        
        # ===== 第四层：估值约束 =====
        # PE(TTM) 在合理范围 (0, 50]
        pe = stock_row.get('pe9', None)
        if pe is None or pd.isna(pe) or pe <= 0 or pe > 50:
            return False
        
        # 通过所有筛选
        return True
        
    except Exception:
        return False


def filter_gpt_value_stocks(selection_data):
    """
    批量筛选满足GPT综合选股条件的股票
    
    Args:
        selection_data: pd.DataFrame, cn_stock_selection 表的数据
        
    Returns:
        pd.DataFrame: 满足条件的股票
    """
    if selection_data is None or len(selection_data) == 0:
        return pd.DataFrame()
    
    mask = selection_data.apply(check_gpt_value_from_selection, axis=1)
    return selection_data[mask].copy()
