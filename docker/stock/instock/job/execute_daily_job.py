#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import datetime
import concurrent.futures
import logging
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
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import indicators_data_daily_job as gdj
import strategy_data_daily_job as sdj
import backtest_data_daily_job as bdj
import klinepattern_data_daily_job as kdj
import selection_data_daily_job as sddj
import gpt_value_data_job as gptj

__author__ = 'myh '
__date__ = '2023/3/10 '


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("######## 任务执行时间: %s #######" % _start.strftime("%Y-%m-%d %H:%M:%S.%f"))
    # 第1步创建数据库
    bj.main()
    # 第2.1步创建股票基础数据表
    hdj.main()
    # 第2.2步创建综合股票数据表
    sddj.main()
    # 低内存模式：顺序执行，避免多个重量级Job同时运行导致OOM（适配2GB服务器）
    # indicators/klinepattern/strategy 各自内部已有多线程处理，无需外层再并行
    try:
        # 第3.1步创建股票其它基础数据表（I/O密集，内存占用低）
        hdtj.main()
    except Exception as e:
        logging.error(f"execute_daily_job basic_data_other异常：{e}")

    try:
        # 第3.2步执行GPT综合选股（轻量级，仅读DB+筛选）
        gptj.main()
    except Exception as e:
        logging.error(f"execute_daily_job gpt_value异常：{e}")

    try:
        # 第4步创建股票指标数据表（重量级：加载stock_hist_data + 计算指标）
        gdj.main()
    except Exception as e:
        logging.error(f"execute_daily_job indicators异常：{e}")

    try:
        # 第5步创建股票k线形态表（重量级：复用stock_hist_data + 形态识别）
        kdj.main()
    except Exception as e:
        logging.error(f"execute_daily_job klinepattern异常：{e}")

    try:
        # 第6步创建股票策略数据表（重量级：复用stock_hist_data + 策略计算）
        sdj.main()
    except Exception as e:
        logging.error(f"execute_daily_job strategy异常：{e}")

    # # # # 第6步创建股票回测
    bdj.main()

    # # # # 第7步创建股票闭盘后才有的数据
    acdj.main()

    logging.info("######## 完成任务, 使用时间: %s 秒 #######" % (time.time() - start))


# main函数入口
if __name__ == '__main__':
    main()
