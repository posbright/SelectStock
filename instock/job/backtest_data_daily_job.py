#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略回测作业（Phase 5）

流式版本：逐只股票从磁盘缓存读取历史数据进行回测，不加载全量单例
- 内存占用：~50 MB（vs 原架构 ~1670 MB）
- 仅处理需要回测的股票（DB 中 backtest 列为 NULL 的记录）
"""


import logging
import concurrent.futures
import pandas as pd
import os.path
import sys
import datetime

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
import instock.lib.trade_time as trd
import instock.core.stockfetch as stf
import instock.core.backtest.rate_stats as rate

__author__ = 'myh '
__date__ = '2023/3/10 '


# 股票策略回归测试。
def prepare():
    tables = [tbs.TABLE_CN_STOCK_INDICATORS_BUY, tbs.TABLE_CN_STOCK_INDICATORS_SELL]
    tables.extend(tbs.TABLE_CN_STOCK_STRATEGIES)
    # GPT综合选股独立于策略列表，单独加入回测
    tables.append(tbs.TABLE_CN_STOCK_STRATEGY_GPT_VALUE)
    backtest_columns = list(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
    backtest_columns.insert(0, 'code')
    backtest_columns.insert(0, 'date')
    backtest_column = backtest_columns

    # 计算缓存读取的日期范围
    now = datetime.datetime.now()
    years = stf.HIST_DATA_DEFAULT_YEARS
    date_start, _ = trd.get_trade_hist_interval(now, years)
    date_end = now.strftime("%Y%m%d")

    # 回归测试表，限制并发数以控制内存占用（适配2GB服务器）
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        for table in tables:
            executor.submit(process, table, date_start, date_end, backtest_column)


def process(table, date_start, date_end, backtest_column):
    table_name = table['name']
    if not mdb.checkTableIsExist(table_name):
        return

    column_tail = tuple(table['columns'])[-1]
    now_date = datetime.datetime.now().date()
    sql = f"SELECT * FROM `{table_name}` WHERE `date` < '{now_date}' AND `{column_tail}` is NULL"
    try:
        data = pd.read_sql(sql=sql, con=mdb.engine())
        if data is None or len(data.index) == 0:
            return

        subset = data[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
        subset = subset.astype({'date': 'string'})
        stocks = [tuple(x) for x in subset.values]

        results = run_check(stocks, date_start, date_end, backtest_column)
        if results is None:
            return

        data_new = pd.DataFrame(results.values())
        mdb.update_db_from_df(data_new, table_name, ('date', 'code'))

    except Exception as e:
        logging.error(f"backtest_data_daily_job.process处理异常：{table}表{e}")


def run_check(stocks, date_start, date_end, backtest_column, workers=4):
    """
    逐只股票从缓存读取历史数据并计算回测收益率
    
    与原版的区别：
    - 原版：从内存 dict 直接查 data_all.get((date, code, name))
    - 新版：从磁盘缓存按需读取 read_stock_hist_from_cache(code, ...)
    
    注意：缓存读取在线程内部执行，避免主线程一次性加载所有数据到内存
    """
    data = {}

    def _process_stock(stock):
        """在线程内读取缓存+计算回测，避免主线程内存堆积"""
        code = stock[1]
        hist_data = stf.read_stock_hist_from_cache(code, date_start, date_end)
        if hist_data is None or len(hist_data) == 0:
            return None
        return rate.get_rates(stock, hist_data, backtest_column, len(backtest_column) - 1)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_stock = {executor.submit(_process_stock, stock): stock for stock in stocks}
            for future in concurrent.futures.as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    _data_ = future.result()
                    if _data_ is not None:
                        data[stock] = _data_
                except Exception as e:
                    logging.error(f"backtest_data_daily_job.run_check处理异常：{stock[1]}代码{e}")
    except Exception as e:
        logging.error(f"backtest_data_daily_job.run_check处理异常：{e}")
    if not data:
        return None
    else:
        return data


def main():
    prepare()


# main函数入口
if __name__ == '__main__':
    main()
