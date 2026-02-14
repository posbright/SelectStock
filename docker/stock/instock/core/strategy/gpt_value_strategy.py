#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT综合选股策略

基于 ChatGP选股策略文档.md v3.0 中定义的五层过滤标准：
1. 财务安全过滤 - 资产负债率 < 60%, 每股经营现金流 > 0, 流动比率 >= 1.0, 速动比率 >= 0.7
2. 盈利能力筛选 - ROE >= 15%, 毛利率 >= 25%, 净利率 >= 8%, ROA >= 4%
3. 成长质量筛选 - 营收3年CAGR > 8%, 净利润3年CAGR > 8%, 扣非净利润增长率 > 0%
4. 估值约束 - PE(TTM) 0 < PE <= 50, PB(MRQ) <= 10

这个策略使用 cn_stock_selection 表中的财务数据进行筛选。
"""

import logging
import math
import pandas as pd

__author__ = 'InStock'
__date__ = '2026/02/14'


# ========== 默认参数值 ==========
_DEFAULT_PARAMS = {
    # 第一层：财务安全
    "debt_asset_ratio_max": 60,
    "per_netcash_operate_min": 0,
    "current_ratio_min": 1.0,
    "speed_ratio_min": 0.7,
    # 第二层：盈利能力
    "roe_weight_min": 15,
    "sale_gpr_min": 25,
    "sale_npr_min": 8,
    "jroa_min": 4,
    # 第三层：成长质量
    "income_growthrate_3y_min": 8,
    "netprofit_growthrate_3y_min": 8,
    "deduct_netprofit_growthrate_min": 0,
    # 第五层：估值约束
    "pe_min": 0,
    "pe_max": 50,
    "pbnewmrq_max": 10,
}


def _load_params():
    """加载用户配置的参数，失败时使用默认值"""
    try:
        from instock.web.strategyParamsHandler import get_gpt_filter_values
        return get_gpt_filter_values()
    except Exception as e:
        logging.debug(f"加载策略参数失败，使用默认值: {e}")
        return _DEFAULT_PARAMS.copy()


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


def check_gpt_value_from_selection(stock_row, params=None):
    """
    从 cn_stock_selection 数据中检查是否满足GPT综合选股条件
    
    Args:
        stock_row: pd.Series, cn_stock_selection 表中的一行数据
        params: dict, 筛选参数。为None时自动从数据库加载用户配置
        
    Returns:
        bool: 是否满足所有条件
    """
    if params is None:
        params = _load_params()
    
    def _is_valid_number(val):
        """检查值是否为有效的有限数值（排除None、NaN、inf、-inf）"""
        return val is not None and not pd.isna(val) and math.isfinite(float(val))

    try:
        # ===== 第一层：财务安全过滤 =====
        debt_ratio = stock_row.get('debt_asset_ratio', None)
        if not _is_valid_number(debt_ratio) or debt_ratio >= params["debt_asset_ratio_max"]:
            return False
        
        cashflow = stock_row.get('per_netcash_operate', None)
        if not _is_valid_number(cashflow) or cashflow <= params["per_netcash_operate_min"]:
            return False
        
        current_r = stock_row.get('current_ratio', None)
        if _is_valid_number(current_r) and current_r < params.get("current_ratio_min", 1.0):
            return False
        
        speed_r = stock_row.get('speed_ratio', None)
        if _is_valid_number(speed_r) and speed_r < params.get("speed_ratio_min", 0.7):
            return False
        
        # ===== 第二层：盈利能力筛选 =====
        roe = stock_row.get('roe_weight', None)
        if not _is_valid_number(roe) or roe < params["roe_weight_min"]:
            return False
        
        gpr = stock_row.get('sale_gpr', None)
        if not _is_valid_number(gpr) or gpr < params["sale_gpr_min"]:
            return False
        
        npr = stock_row.get('sale_npr', None)
        if not _is_valid_number(npr) or npr < params["sale_npr_min"]:
            return False
        
        roa = stock_row.get('jroa', None)
        if _is_valid_number(roa) and roa < params.get("jroa_min", 4):
            return False
        
        # ===== 第三层：成长质量筛选 =====
        revenue_growth = stock_row.get('income_growthrate_3y', None)
        if not _is_valid_number(revenue_growth) or revenue_growth <= params["income_growthrate_3y_min"]:
            return False
        
        profit_growth = stock_row.get('netprofit_growthrate_3y', None)
        if not _is_valid_number(profit_growth) or profit_growth <= params["netprofit_growthrate_3y_min"]:
            return False
        
        deduct_growth = stock_row.get('deduct_netprofit_growthrate', None)
        if _is_valid_number(deduct_growth) and deduct_growth <= params.get("deduct_netprofit_growthrate_min", 0):
            return False
        
        # ===== 第五层：估值约束 =====
        pe = stock_row.get('pe9', None)
        if not _is_valid_number(pe) or pe <= params["pe_min"] or pe > params["pe_max"]:
            return False
        
        pb = stock_row.get('pbnewmrq', None)
        if _is_valid_number(pb) and pb > params.get("pbnewmrq_max", 10):
            return False
        
        # 通过所有筛选
        return True
        
    except Exception:
        return False


def filter_gpt_value_stocks(selection_data):
    """
    批量筛选满足GPT综合选股条件的股票
    
    使用数据库中保存的用户自定义参数进行筛选。
    
    Args:
        selection_data: pd.DataFrame, cn_stock_selection 表的数据
        
    Returns:
        pd.DataFrame: 满足条件的股票
    """
    if selection_data is None or len(selection_data) == 0:
        return pd.DataFrame()
    
    # 加载一次参数，供所有行复用
    params = _load_params()
    mask = selection_data.apply(lambda row: check_gpt_value_from_selection(row, params), axis=1)
    return selection_data[mask].copy()
