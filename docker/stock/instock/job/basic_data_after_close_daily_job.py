#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import sys
import time as _time

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.lib.run_template as runt
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
import instock.core.stockfetch as stf

__author__ = 'InStock'
__date__ = '2026/02/14'


def _fetch_with_retry(fetch_func, name, retries=1, delay=10):
    """带重试的API获取包装器，降低因网络瞬断或限流导致的数据丢失"""
    for attempt in range(1 + retries):
        try:
            data = fetch_func()
            if data is not None and len(data) > 0:
                return data
            if attempt < retries:
                logging.warning(f"{name}: 第{attempt+1}次获取为空，{delay}秒后重试")
                _time.sleep(delay)
        except Exception as e:
            if attempt < retries:
                logging.warning(f"{name}: 第{attempt+1}次获取异常（{e}），{delay}秒后重试")
                _time.sleep(delay)
            else:
                raise
    return None


# 每日股票大宗交易
def save_after_close_stock_blocktrade_data(date):
    try:
        data = _fetch_with_retry(lambda: stf.fetch_stock_blocktrade_data(date), "大宗交易")
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_BLOCKTRADE['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` WHERE `date` = %s"
            mdb.executeSql(del_sql, (date,))
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_BLOCKTRADE['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_after_close_daily_job.save_stock_blocktrade_data处理异常", exc_info=True)

# 每日尾盘抢筹
def save_after_close_stock_chip_race_end_data(date):
    try:
        data = _fetch_with_retry(lambda: stf.fetch_stock_chip_race_end(date), "尾盘抢筹")
        if data is None or len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_CHIP_RACE_END['name']
        # 删除老数据。
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` WHERE `date` = %s"
            mdb.executeSql(del_sql, (date,))
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_CHIP_RACE_END['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"basic_data_after_close_daily_job.save_after_close_stock_chip_race_end_data", exc_info=True)

def main():
    runt.run_with_args(save_after_close_stock_blocktrade_data)
    _time.sleep(30)  # 防限流延迟
    runt.run_with_args(save_after_close_stock_chip_race_end_data)


# main函数入口
if __name__ == '__main__':
    main()
