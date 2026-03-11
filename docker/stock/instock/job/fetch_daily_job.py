#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取作业（独立运行）

职责：集中执行所有需要外部 API 的数据获取任务。
与 analysis_daily_job.py 配合使用，实现获取与分析解耦。

执行顺序（按内存占用从低到高排列，确保轻量任务优先完成）：
1. 初始化数据库
2. 股票/ETF 实时行情入库 + 综合选股数据入库
3. 资金流向、龙虎榜等扩展数据（Phase 3 — 轻量API调用）
4. 收盘后数据（大宗交易等）
5. 历史K线缓存增量更新（Phase 1 — 内存密集型，放在最后）

设计原则：
- 轻量API调用优先于内存密集型操作
- 在 1.6GB 内存服务器上，K线缓存更新可能因 OOM 被杀，
  放在最后确保不影响其他数据入库
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
try:
    from instock.lib.log_config import setup_logging
    setup_logging('fetch')
except Exception:
    log_path = os.path.join(cpath_current, 'log')
    os.makedirs(log_path, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        filename=os.path.join(log_path, 'stock_fetch_job.log'),
        level=logging.INFO,
    )
import init_job as bj
import subprocess
import basic_data_daily_job as hdj
import selection_data_daily_job as sddj

__author__ = 'InStock'
__date__ = '2026/02/14'

_JOB_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_job_subprocess(script_name, label, timeout=1800):
    """以独立子进程运行 job 脚本，防止 OOM 波及当前进程"""
    script_path = os.path.join(_JOB_DIR, script_name)
    try:
        logging.info(f"{label}: 启动子进程 {script_name}")
        result = subprocess.run(
            [sys.executable, script_path],
            env={**os.environ, 'PYTHONPATH': cpath},
            timeout=timeout,
        )
        if result.returncode != 0:
            logging.warning(f"{label}: 子进程退出码 {result.returncode}（可能 OOM 被杀）")
        else:
            logging.info(f"{label}: 子进程执行成功")
    except subprocess.TimeoutExpired:
        logging.error(f"{label}: 子进程执行超时（{timeout}秒）")
    except Exception as e:
        logging.error(f"{label}: 子进程启动异常", exc_info=True)


def main():
    start = time.time()
    logging.info("====== 数据获取任务开始 [%s] ======" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Phase 0: 初始化数据库
    try:
        bj.main()
    except Exception as e:
        logging.error(f"数据获取 init_job 异常", exc_info=True)

    # Phase 2: 实时行情入库（轻量，优先执行以确保基础数据可用）
    try:
        hdj.main()
    except Exception as e:
        logging.error(f"数据获取 basic_data_daily 异常", exc_info=True)

    try:
        sddj.main()
    except Exception as e:
        logging.error(f"数据获取 selection_data 异常", exc_info=True)

    # Phase 3: 扩展数据（资金流向、龙虎榜等 — 轻量API调用，优先于重量级K线更新）
    # 以独立子进程运行，防止 OOM 波及当前进程
    _run_job_subprocess('basic_data_other_daily_job.py', '数据获取 basic_data_other')

    # Phase 5 (收盘后数据): 大宗交易等 — 独立子进程
    _run_job_subprocess('basic_data_after_close_daily_job.py', '数据获取 after_close')

    # 释放可能的缓存，为 Phase 1 腾出内存
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
    except Exception:
        logging.debug("释放单例缓存异常", exc_info=True)

    # Phase 1: 历史K线缓存更新（内存密集型，放在最后执行）
    # 以独立子进程运行：该步骤处理 ~5000 只股票的K线缓存，
    # 在 1.6GB 内存服务器上经常因 OOM 被杀（exit code 137）。
    # 即使此子进程被杀，上面的轻量级数据已经成功入库。
    _run_job_subprocess('fetch_data_job.py', '数据获取 fetch_data(K线缓存)', timeout=36000)

    elapsed = time.time() - start
    logging.info("====== 数据获取任务完成，耗时 %.1f 秒 ======" % elapsed)


if __name__ == '__main__':
    main()
