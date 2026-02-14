#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据分析作业（独立运行）

职责：基于本地缓存和数据库数据执行所有分析、筛选、回测任务。
与 fetch_daily_job.py 配合使用，实现获取与分析解耦。

包含：
- GPT综合选股（从 cn_stock_selection 表筛选）
- 流式分析（技术指标 + K线形态 + 策略选股）
- 回测数据计算

不包含：
- 任何外部 API 调用
- 所有数据来源：磁盘缓存 + 数据库

设计原则：
- 零 API 调用，纯本地计算
- 依赖 fetch_daily_job.py 已更新的缓存，但即使缓存未更新也能用历史缓存运行
- 峰值内存 < 100 MB
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
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(format='%(asctime)s %(message)s', filename=os.path.join(log_path, 'stock_execute_job.log'))
logging.getLogger().setLevel(logging.INFO)
import gpt_value_data_job as gptj
import streaming_analysis_job as saj
import backtest_data_daily_job as bdj

__author__ = 'InStock'
__date__ = '2026/02/14'


def main():
    start = time.time()
    logging.info("====== 数据分析任务开始 [%s] ======" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # GPT综合选股（纯 DB 读取 + 筛选，无 API）
    try:
        gptj.main()
    except Exception as e:
        logging.error(f"数据分析 gpt_value 异常：{e}")

    # 流式分析：指标计算 + K线形态识别 + 策略选股（从磁盘缓存读取）
    try:
        saj.main()
    except Exception as e:
        logging.error(f"数据分析 streaming_analysis 异常：{e}")

    # 策略回测（从磁盘缓存按需读取）
    try:
        bdj.main()
    except Exception as e:
        logging.error(f"数据分析 backtest 异常：{e}")

    # 释放可能加载的单例
    try:
        from instock.core.singleton_stock import stock_data, stock_hist_data
        stock_data.release()
        stock_hist_data.release()
        gc.collect()
    except Exception:
        pass

    elapsed = time.time() - start
    logging.info("====== 数据分析任务完成，耗时 %.1f 秒 ======" % elapsed)


if __name__ == '__main__':
    main()
