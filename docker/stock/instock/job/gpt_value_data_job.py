#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT综合选股作业

基于 cn_stock_selection 表中的财务数据，执行基本面筛选策略。
筛选条件基于 ChatGP选股策略文档.md 定义的标准。
"""

import logging
import pandas as pd
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.lib.run_template as runt
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
from instock.core.strategy.gpt_value_strategy import filter_gpt_value_stocks

__author__ = 'InStock'
__date__ = '2026/02/09'


def prepare(date):
    """
    执行GPT综合选股
    
    从 cn_stock_selection 表读取数据，执行基本面筛选，
    将结果保存到 cn_stock_strategy_gpt_value 表。
    """
    try:
        date_str = date.strftime("%Y-%m-%d")
        table_name = tbs.TABLE_CN_STOCK_STRATEGY_GPT_VALUE['name']
        source_table = 'cn_stock_selection'
        
        # 检查源表是否存在
        if not mdb.checkTableIsExist(source_table):
            logging.warning(f"源表 {source_table} 不存在，跳过GPT综合选股")
            return
        
        # 从 cn_stock_selection 读取数据
        sql = f"SELECT * FROM `{source_table}` WHERE `date` = %s"
        selection_data = pd.read_sql(sql, mdb.engine(), params=[date_str])
        
        if selection_data is None or len(selection_data) == 0:
            logging.info(f"GPT综合选股：{date_str} 无选股数据")
            return
        
        # 执行基本面筛选
        filtered = filter_gpt_value_stocks(selection_data)
        
        if filtered is None or len(filtered) == 0:
            logging.info(f"GPT综合选股：{date_str} 无符合条件的股票")
            return
        
        logging.info(f"GPT综合选股：{date_str} 筛选出 {len(filtered)} 只股票")
        
        # 准备结果数据（只保留基础字段）
        result_columns = ['date', 'code', 'name']
        result_data = filtered[result_columns].copy()
        
        # 删除老数据
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` WHERE `date` = %s"
            mdb.executeSql(del_sql, (date_str,))
            cols_type = None
        else:
            # 获取列类型定义
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_STRATEGY_GPT_VALUE['columns'])
        
        # 添加回测字段（空值）
        _columns_backtest = tuple(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
        result_data = pd.concat([result_data, pd.DataFrame(columns=_columns_backtest)])
        
        # 插入数据
        mdb.insert_db_from_df(result_data, table_name, cols_type, False, "`date`,`code`")
        
        logging.info(f"GPT综合选股：{date_str} 成功保存 {len(result_data)} 条记录")
        
    except Exception as e:
        logging.error(f"gpt_value_data_job.prepare 处理异常：{e}")


def main():
    """执行GPT综合选股作业"""
    runt.run_with_args(prepare)


if __name__ == '__main__':
    main()
