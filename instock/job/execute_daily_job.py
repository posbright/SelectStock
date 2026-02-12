#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import datetime
import concurrent.futures
import logging
import gc
import os.path
import sys

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(format='%(asctime)s %(message)s', filename=os.path.join(log_path, 'stock_execute_job.log'))
logging.getLogger().setLevel(logging.INFO)
import init_job as bj
import fetch_data_job as fdj
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import streaming_analysis_job as saj
import backtest_data_daily_job as bdj
import selection_data_daily_job as sddj
import gpt_value_data_job as gptj

__author__ = 'myh '
__date__ = '2023/3/10 '


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("######## 任务执行时间: %s #######" % _start.strftime("%Y-%m-%d %H:%M:%S.%f"))

    # ================================================================
    # Phase 1: 数据获取（外部API调用 — 唯一的API密集阶段）
    # 批量更新本地缓存（低内存模式：仅更新磁盘文件，不保留在内存中）
    # 后续所有分析任务从磁盘缓存按需读取，不再发起API请求
    # ================================================================
    bj.main()   # 初始化数据库
    fdj.main()  # 集中获取数据：实时行情 + 历史K线 + 缓存清理

    # ================================================================
    # Phase 2: 基础数据入库（读取已加载的单例/少量API调用）
    # ================================================================
    try:
        hdj.main()   # 股票/ETF实时行情入库（从 stock_data 单例读取）
    except Exception as e:
        logging.error(f"execute_daily_job basic_data_daily异常：{e}")

    try:
        sddj.main()  # 综合选股数据入库（需要API获取选股器数据）
    except Exception as e:
        logging.error(f"execute_daily_job selection_data异常：{e}")

    # ================================================================
    # Phase 3: 扩展数据获取与入库（独立API：资金流向、龙虎榜等）
    # ================================================================
    try:
        hdtj.main()  # 资金流向、龙虎榜、筹码等（I/O密集，内存占用低）
    except Exception as e:
        logging.error(f"execute_daily_job basic_data_other异常：{e}")

    try:
        gptj.main()  # GPT综合选股（纯DB读取+筛选，无API调用）
    except Exception as e:
        logging.error(f"execute_daily_job gpt_value异常：{e}")

    # ================================================================
    # Phase 4: 数据分析（流式处理 — 低内存模式）
    # 从磁盘缓存逐只读取股票历史数据，同时计算指标+K线形态+策略
    # 峰值内存 < 100 MB（vs 原架构 ~1670 MB 全量加载）
    # 无任何外部API调用，数据来源：Phase 1 已更新的本地缓存
    # ================================================================
    try:
        saj.main()   # 流式分析：指标计算 + K线形态识别 + 策略选股（单次遍历）
    except Exception as e:
        logging.error(f"execute_daily_job streaming_analysis异常：{e}")

    # ================================================================
    # Phase 5: 回测与收尾
    # ================================================================
    # 释放 stock_data 单例（流式架构不再使用 stock_hist_data 单例）
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
        logging.info("已释放 stock_data 单例，回收内存")
    except Exception as e:
        logging.warning(f"释放单例异常（不影响后续执行）：{e}")

    bdj.main()   # 策略回测（重新加载stock_hist_data，但此时缓存已热，无API调用）
    acdj.main()  # 闭盘后数据（大宗交易等，需要API）

    logging.info("######## 完成任务, 使用时间: %s 秒 #######" % (time.time() - start))


# main函数入口
if __name__ == '__main__':
    main()
