#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import concurrent.futures
import instock.core.stockfetch as stf
import instock.core.tablestructure as tbs
import instock.lib.trade_time as trd
from instock.lib.singleton_type import singleton_type

__author__ = 'myh '
__date__ = '2023/3/10 '


# 读取当天股票数据
class stock_data(metaclass=singleton_type):
    def __init__(self, date):
        self.data = None
        try:
            self.data = stf.fetch_stocks(date)
        except Exception as e:
            logging.error(f"singleton.stock_data处理异常：{e}")

    def get_data(self):
        return self.data


# 读取股票历史数据（支持增量更新和自定义时间范围）
class stock_hist_data(metaclass=singleton_type):
    def __init__(self, date=None, stocks=None, workers=8, years=3, date_start=None, date_end=None):
        """
        初始化股票历史数据
        
        参数：
            date: 基准日期
            stocks: 股票列表，格式 [(date, code), ...]
            workers: 并发线程数
            years: 历史数据年数，默认3年
            date_start: 自定义起始日期 YYYYMMDD
            date_end: 自定义结束日期 YYYYMMDD
        """
        if stocks is None:
            _spot = stock_data(date).get_data()
            if _spot is None:
                logging.error("stock_hist_data初始化失败：stock_data返回None，无法获取股票列表")
                self.data = None
                return
            _subset = _spot[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
            stocks = [tuple(x) for x in _subset.values]
        if stocks is None or len(stocks) == 0:
            logging.error("stock_hist_data初始化失败：股票列表为空")
            self.data = None
            return
        
        logging.info(f"stock_hist_data开始初始化：{len(stocks)}只股票，{workers}线程，{years}年历史数据")
        
        # 获取时间区间
        if date_start is None:
            date_start, is_cache = trd.get_trade_hist_interval(stocks[0][0], years)
        else:
            is_cache = True
        
        if date_end is None:
            date_end = stocks[0][0].replace("-", "") if isinstance(stocks[0][0], str) else stocks[0][0].strftime("%Y%m%d")
        
        _data = {}
        try:
            # max_workers是None还是没有给出，将默认为机器cup个数*5
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_stock = {
                    executor.submit(stf.fetch_stock_hist, stock, date_start, date_end, is_cache, years): stock 
                    for stock in stocks
                }
                for future in concurrent.futures.as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    try:
                        __data = future.result()
                        if __data is not None:
                            _data[stock] = __data
                    except Exception as e:
                        logging.error(f"singleton.stock_hist_data处理异常：{stock[1]}代码{e}")
        except Exception as e:
            logging.error(f"singleton.stock_hist_data处理异常：{e}")
        if not _data:
            logging.error(f"stock_hist_data初始化完成但数据为空：{len(stocks)}只股票全部获取失败")
            self.data = None
        else:
            logging.info(f"stock_hist_data初始化完成：成功获取{len(_data)}/{len(stocks)}只股票的历史数据")
            self.data = _data

    def get_data(self):
        return self.data
