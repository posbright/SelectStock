#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取作业（独立运行）

职责：集中执行所有需要外部 API 的数据获取任务。
与 analysis_daily_job.py 配合使用，实现获取与分析解耦。

包含：
- 初始化数据库
- 历史K线缓存增量更新（Phase 1）
- 股票/ETF 实时行情入库（Phase 2）
- 综合选股数据入库
- 资金流向、龙虎榜等扩展数据（Phase 3）
- 收盘后数据（大宗交易等）

不包含：
- 技术指标计算、K线形态识别、策略选股（→ analysis_daily_job.py）
- GPT综合选股筛选（→ analysis_daily_job.py）
- 回测数据计算（→ analysis_daily_job.py）

设计原则：
- 所有外部 API 调用集中在此脚本
- 即使某个阶段失败，后续阶段仍会继续
- 可独立于分析任务运行
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
try:
    from instock.lib.log_config import setup_logging
    setup_logging('fetch')
except Exception:
    pass
import init_job as bj
import fetch_data_job as fdj
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import selection_data_daily_job as sddj

__author__ = 'InStock'
__date__ = '2026/02/14'


def main():
    start = time.time()
    logging.info("====== 数据获取任务开始 [%s] ======" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Phase 1: 初始化 + 历史K线缓存更新
    bj.main()
    fdj.main()

    # Phase 2: 实时行情入库
    try:
        hdj.main()
    except Exception as e:
        logging.error(f"数据获取 basic_data_daily 异常", exc_info=True)

    try:
        sddj.main()
    except Exception as e:
        logging.error(f"数据获取 selection_data 异常", exc_info=True)

    # Phase 3: 扩展数据
    try:
        hdtj.main()
    except Exception as e:
        logging.error(f"数据获取 basic_data_other 异常", exc_info=True)

    # Phase 5 (收盘后数据): 大宗交易等
    try:
        acdj.main()
    except Exception as e:
        logging.error(f"数据获取 after_close 异常", exc_info=True)

    # 释放单例
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
    except Exception:
        pass

    elapsed = time.time() - start
    logging.info("====== 数据获取任务完成，耗时 %.1f 秒 ======" % elapsed)


if __name__ == '__main__':
    main()
