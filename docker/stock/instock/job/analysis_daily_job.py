#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据分析作业（独立运行）

职责：基于本地缓存和数据库数据执行所有分析、筛选、回测任务。
与 fetch_daily_job.py 配合使用，实现获取与分析解耦。

包含：
- GPT综合选股（从 cn_stock_selection 表筛选）
- 基本面选股（PE/PB/ROE筛选，从 cn_stock_spot 表读取）
- 流式分析（技术指标 + K线形态 + 策略选股）
- 回测数据计算

不包含：
- 任何外部 API 调用
- 所有数据来源：磁盘缓存 + 数据库

设计原则：
- 零 API 调用，纯本地计算
- 依赖 fetch_daily_job.py 已更新的缓存，但即使缓存未更新也能用历史缓存运行
- 峰值内存 < 50 MB（通过环境变量可调节并发度和批量大小）
- 每个子任务记录开始/结束日志及耗时
- 可独立于数据获取任务运行
"""

import time
import datetime
import logging
import gc
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
try:
    from instock.lib.log_config import setup_logging
    setup_logging('analysis')
except Exception:
    log_path = os.path.join(cpath_current, 'log')
    os.makedirs(log_path, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        filename=os.path.join(log_path, 'stock_analysis_job.log'),
        level=logging.INFO,
    )
import instock.lib.database as mdb
import instock.lib.trade_time as trd
import gpt_value_data_job as gptj
import streaming_analysis_job as saj
import backtest_data_daily_job as bdj
from instock.lib.job_tracker import record_task_start, record_task_end, record_task_skipped

__author__ = 'InStock'
__date__ = '2026/03/12'

# 分析数据跳过阈值：cn_stock_indicators 今日行数 >= 此值时认为分析已完成
# 正常交易日约 4800+ 条，设 1000 作为安全阈值避免误跳过部分完成的情况
ANALYSIS_DONE_THRESHOLD = int(os.environ.get('INSTOCK_ANALYSIS_DONE_THRESHOLD', '1000'))

_JOB_NAME = 'run_analysis'


def _is_analysis_done(date_str):
    """
    检查今日分析数据是否已由其他节点（如本地计算机）完成。
    
    检查 cn_stock_indicators 表的今日行数：
    - >= ANALYSIS_DONE_THRESHOLD → 已完成，跳过
    - < ANALYSIS_DONE_THRESHOLD → 未完成或部分完成，需要执行
    
    用于服务器 cron 回退模式：当本地已执行完分析任务后，
    服务器 cron 触发时自动跳过，避免低内存环境重复计算。
    可通过 INSTOCK_FORCE_ANALYSIS=1 环境变量强制执行。
    """
    if os.environ.get('INSTOCK_FORCE_ANALYSIS', '').strip() == '1':
        logging.info("检测到 INSTOCK_FORCE_ANALYSIS=1，强制执行分析任务")
        return False

    try:
        table_name = 'cn_stock_indicators'
        if not mdb.checkTableIsExist(table_name):
            return False
        row = mdb.executeSqlFetch(
            f"SELECT COUNT(*) FROM `{table_name}` WHERE `date` = %s",
            (date_str,)
        )
        count = row[0][0] if row else 0
        if count >= ANALYSIS_DONE_THRESHOLD:
            logging.info(
                f"今日分析数据已存在（{table_name} 有 {count} 条 >= 阈值 {ANALYSIS_DONE_THRESHOLD}），"
                f"跳过分析任务。设置 INSTOCK_FORCE_ANALYSIS=1 可强制执行。"
            )
            return True
        logging.info(f"今日分析数据不足（{table_name} 有 {count} 条 < 阈值 {ANALYSIS_DONE_THRESHOLD}），继续执行")
        return False
    except Exception as e:
        logging.warning(f"检查分析数据是否完成时异常（将继续执行）：{e}")
        return False


def _run_stock_spot_buy(date):
    """
    基本面选股：从 cn_stock_spot 筛选 PE<20、PB<10、ROE>=15% 的股票。
    
    原位于 basic_data_other_daily_job.py（龙虎榜附带操作），
    现移至分析流程，在 GPT 综合选股后执行。
    """
    import pandas as pd
    import instock.core.tablestructure as tbs

    try:
        _table_name = tbs.TABLE_CN_STOCK_SPOT['name']
        if not mdb.checkTableIsExist(_table_name):
            logging.warning("基本面选股：cn_stock_spot 表不存在，跳过")
            return

        date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
        sql = f'''SELECT * FROM `{_table_name}` WHERE `date` = %s and 
                `pe9` > 0 and `pe9` <= 20 and `pbnewmrq` <= 10 and `roe_weight` >= 15'''
        data = pd.read_sql(sql=sql, con=mdb.engine(), params=(date_str,))
        data = data.drop_duplicates(subset="code", keep="last")
        if len(data.index) == 0:
            logging.info("基本面选股：无符合条件的股票")
            return

        table_name = tbs.TABLE_CN_STOCK_SPOT_BUY['name']
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` WHERE `date` = %s"
            mdb.executeSql(del_sql, (date_str,))
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_SPOT_BUY['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
        logging.info(f"基本面选股：筛选出 {len(data)} 只股票写入 {table_name}")
    except Exception as e:
        logging.error(f"基本面选股处理异常", exc_info=True)


def main():
    start = time.time()
    logging.info("====== 数据分析任务开始 [%s] ======" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 检查今日分析是否已由其他节点完成（本地计算机优先模式）
    try:
        run_date, run_date_nph = trd.get_trade_date_last()
        date_str = run_date_nph.strftime("%Y-%m-%d")
        if _is_analysis_done(date_str):
            elapsed = time.time() - start
            logging.info("====== 数据分析任务跳过（已完成），耗时 %.1f 秒 ======" % elapsed)
            return
    except Exception as e:
        logging.warning(f"检查分析完成状态异常（将继续执行）：{e}")
        run_date, run_date_nph = trd.get_trade_date_last()
        date_str = run_date_nph.strftime("%Y-%m-%d")

    overall_start = record_task_start(_JOB_NAME, '__overall__', run_date_nph)

    # Step 1: GPT综合选股（纯 DB 读取 + 筛选，无 API）
    t1 = record_task_start(_JOB_NAME, 'gpt_value', run_date_nph)
    try:
        gptj.main()
        record_task_end(_JOB_NAME, 'gpt_value', run_date_nph, t1, success=True)
    except Exception as e:
        logging.error("数据分析 gpt_value 异常", exc_info=True)
        record_task_end(_JOB_NAME, 'gpt_value', run_date_nph, t1, success=False, message=str(e))
    gc.collect()

    # Step 2: 基本面选股（从 cn_stock_spot 筛选 PE/PB/ROE）
    t2 = record_task_start(_JOB_NAME, 'stock_spot_buy', run_date_nph)
    try:
        _run_stock_spot_buy(run_date_nph)
        record_task_end(_JOB_NAME, 'stock_spot_buy', run_date_nph, t2, success=True)
    except Exception as e:
        logging.error("数据分析 stock_spot_buy 异常", exc_info=True)
        record_task_end(_JOB_NAME, 'stock_spot_buy', run_date_nph, t2, success=False, message=str(e))
    gc.collect()

    # Step 3: 流式分析：指标计算 + K线形态识别 + 策略选股（从磁盘缓存读取）
    t3 = record_task_start(_JOB_NAME, 'streaming_analysis', run_date_nph)
    try:
        saj.main()
        record_task_end(_JOB_NAME, 'streaming_analysis', run_date_nph, t3, success=True)
    except Exception as e:
        logging.error("数据分析 streaming_analysis 异常", exc_info=True)
        record_task_end(_JOB_NAME, 'streaming_analysis', run_date_nph, t3, success=False, message=str(e))
    gc.collect()

    # Step 4: 策略回测（从磁盘缓存按需读取）
    t4 = record_task_start(_JOB_NAME, 'backtest', run_date_nph)
    try:
        bdj.main()
        record_task_end(_JOB_NAME, 'backtest', run_date_nph, t4, success=True)
    except Exception as e:
        logging.error("数据分析 backtest 异常", exc_info=True)
        record_task_end(_JOB_NAME, 'backtest', run_date_nph, t4, success=False, message=str(e))
    gc.collect()

    # 释放可能加载的单例
    try:
        from instock.core.singleton_stock import stock_data, stock_hist_data
        stock_data.release()
        stock_hist_data.release()
        gc.collect()
    except Exception as e:
        logging.debug(f"释放单例跳过: {e}")

    elapsed = time.time() - start
    record_task_end(
        _JOB_NAME, '__overall__', run_date_nph, overall_start,
        success=True, message=f"总耗时 {elapsed:.1f}s"
    )
    logging.info("====== 数据分析任务完成，耗时 %.1f 秒 ======" % elapsed)


if __name__ == '__main__':
    main()
