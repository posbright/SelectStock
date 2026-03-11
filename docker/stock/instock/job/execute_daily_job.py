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
try:
    from instock.lib.log_config import setup_logging
    setup_logging('execute')
except Exception:
    # 兼容旧环境：log_config 不可用时降级为 basicConfig
    log_path = os.path.join(cpath_current, 'log')
    os.makedirs(log_path, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        filename=os.path.join(log_path, 'stock_execute_job.log'),
        level=logging.INFO,
    )
import init_job as bj
import subprocess
import basic_data_daily_job as hdj
import streaming_analysis_job as saj
import backtest_data_daily_job as bdj
import selection_data_daily_job as sddj
import gpt_value_data_job as gptj
import instock.lib.database as mdb
import instock.lib.trade_time as trd

__author__ = 'InStock'
__date__ = '2026/02/14'

# 分析数据跳过阈值（同 analysis_daily_job.py）
ANALYSIS_DONE_THRESHOLD = int(os.environ.get('INSTOCK_ANALYSIS_DONE_THRESHOLD', '1000'))

_JOB_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_job_subprocess(script_name, label, timeout=1800):
    """以独立子进程运行 job 脚本，防止 OOM 波及当前进程。

    Returns:
        bool: True 表示子进程正常退出（exit code 0），False 表示失败/超时/异常。
    """
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
            return False
        else:
            logging.info(f"{label}: 子进程执行成功")
            return True
    except subprocess.TimeoutExpired:
        logging.error(f"{label}: 子进程执行超时（{timeout}秒）")
        return False
    except Exception as e:
        logging.error(f"{label}: 子进程启动异常", exc_info=True)
        return False


def _is_analysis_done():
    """
    检查今日分析数据是否已由其他节点完成。
    用于 execute_daily_job 中跳过 Phase 3/4（分析+回测），
    但仍执行 Phase 0/1/2（初始化+轻量数据+K线缓存）。
    可通过 INSTOCK_FORCE_ANALYSIS=1 强制执行。
    """
    if os.environ.get('INSTOCK_FORCE_ANALYSIS', '').strip() == '1':
        return False
    try:
        run_date, run_date_nph = trd.get_trade_date_last()
        date_str = run_date_nph.strftime("%Y-%m-%d")
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
                f"分析数据已存在（{count} 条 >= {ANALYSIS_DONE_THRESHOLD}），"
                f"Phase 3/4 将跳过。设置 INSTOCK_FORCE_ANALYSIS=1 可强制执行。"
            )
            return True
        return False
    except Exception as e:
        logging.warning(f"检查分析完成状态异常（将继续执行）：{e}")
        return False


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("######## 任务执行时间: %s #######" % _start.strftime("%Y-%m-%d %H:%M:%S.%f"))

    # ================================================================
    # Phase 0: 初始化
    # ================================================================
    bj.main()   # 初始化数据库

    # ================================================================
    # Phase 1: 轻量级数据入库（优先执行，耗时短、内存低）
    # 设计原则：先完成所有轻量 API 调用和入库操作，确保即使后续重量级
    # K线缓存更新因 OOM 被杀，这些关键数据（综合选股、GPT选股等）
    # 已经安全写入数据库，不会因 K线更新失败而全部丢失。
    # ================================================================

    # Phase 1a: 实时行情预加载
    # 单独预加载 stock_data 单例，供后续 Phase 1b 直接使用
    # （K线缓存批量更新已移至 Phase 2 子进程执行）
    try:
        import instock.lib.run_template as runt
        import instock.lib.trade_time as trd
        import instock.core.stockfetch as stf
        from instock.core.singleton_stock import stock_data as sd_cls

        run_date, run_date_nph = trd.get_trade_date_last()
        spot = sd_cls(run_date_nph).get_data()
        if spot is not None:
            logging.info(f"Phase 1a: 实时行情预加载成功，{len(spot)} 只股票")
        else:
            logging.error("Phase 1a: 实时行情预加载失败（stock_data 返回 None）")
    except Exception as e:
        logging.error(f"execute_daily_job Phase 1a 行情预加载异常", exc_info=True)

    # Phase 1b: 基础数据入库（从 stock_data 单例读取，无额外API调用）
    try:
        hdj.main()   # 股票/ETF实时行情入库
    except Exception as e:
        logging.error(f"execute_daily_job basic_data_daily异常", exc_info=True)

    # Phase 1c: 综合选股数据（轻量API：东方财富选股器，~10页，<30秒）
    try:
        sddj.main()  # 综合选股数据入库
    except Exception as e:
        logging.error(f"execute_daily_job selection_data异常", exc_info=True)

    # Phase 1d: 扩展数据（资金流向、龙虎榜等，轻量API调用）
    # 以独立子进程运行，防止 OOM 波及当前进程
    _run_job_subprocess('basic_data_other_daily_job.py', 'execute_daily_job basic_data_other')

    # Phase 1e: GPT综合选股（纯DB读取+筛选，无API调用，依赖 Phase 1c 的选股数据）
    try:
        gptj.main()  # GPT综合选股
    except Exception as e:
        logging.error(f"execute_daily_job gpt_value异常", exc_info=True)

    # Phase 1f: 收盘后数据（大宗交易等，轻量API）
    # 以独立子进程运行，防止 OOM 波及当前进程
    _run_job_subprocess('basic_data_after_close_daily_job.py', 'execute_daily_job after_close')

    # ================================================================
    # Phase 2: 重量级数据获取 — K线缓存批量更新
    # 处理 ~5000 只股票的历史K线增量缓存，内存密集型操作。
    # 在 1.6GB 内存服务器上可能因 OOM 被杀，因此放在轻量级任务之后。
    # 即使此步骤失败，Phase 1 的关键数据已安全入库。
    # ================================================================
    # 释放 stock_data 单例以腾出内存给 K线缓存更新
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
        logging.info("Phase 2: 已释放 stock_data 单例，回收内存")
    except Exception:
        logging.debug("释放 stock_data 单例异常", exc_info=True)

    # 以独立子进程运行：该步骤处理 ~5000 只股票的K线缓存，
    # 在 1.6GB 内存服务器上经常因 OOM 被杀（exit code 137）。
    # 即使此子进程被杀，Phase 1 的关键数据已安全入库。
    phase2_ok = _run_job_subprocess('fetch_data_job.py', 'execute_daily_job K线缓存更新', timeout=36000)
    if not phase2_ok:
        logging.warning(
            "⚠ Phase 2 K线缓存更新失败！Phase 3 将使用可能过期的缓存数据运行。"
            "指标/策略结果基于最后一次成功缓存的K线，结果可能与当日实际行情不符。"
        )
        # 设置环境变量：让 streaming_analysis_job 能感知 Phase 2 失败
        os.environ['INSTOCK_PHASE2_FAILED'] = '1'
    else:
        os.environ.pop('INSTOCK_PHASE2_FAILED', None)

    # 释放 stock_data 单例：如果预加载失败，单例缓存了 None，
    # Phase 3 流式分析调用 stock_data(date).get_data() 会得到缓存的 None 从而跳过。
    # 此处释放单例，让 Phase 3 有机会重新发起 API 请求获取股票列表。
    try:
        from instock.core.singleton_stock import stock_data
        _sd = getattr(stock_data, '_instance', None)
        if _sd is not None and _sd.data is None:
            stock_data.release()
            logging.warning("stock_data 返回 None，已释放单例以允许 Phase 3 重试")
    except Exception:
        logging.debug("释放 stock_data 单例异常", exc_info=True)

    # ================================================================
    # Phase 3: 数据分析（流式处理 — 低内存模式）
    # 从磁盘缓存逐只读取股票历史数据，同时计算指标+K线形态+策略
    # 峰值内存 < 100 MB（vs 原架构 ~1670 MB 全量加载）
    # 无任何外部API调用，数据来源：Phase 2 已更新的本地缓存
    # ================================================================
    # 检查分析数据是否已由其他节点完成（本地优先模式）
    analysis_already_done = _is_analysis_done()

    if analysis_already_done:
        logging.info("Phase 3 跳过：分析数据已由其他节点完成")
    else:
        try:
            saj.main()   # 流式分析：指标计算 + K线形态识别 + 策略选股（单次遍历）
        except Exception as e:
            logging.error(f"execute_daily_job streaming_analysis异常", exc_info=True)

    # ================================================================
    # Phase 4: 回测与收尾
    # ================================================================
    # 释放 stock_data 单例（流式架构不再使用 stock_hist_data 单例）
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
        logging.info("已释放 stock_data 单例，回收内存")
    except Exception as e:
        logging.warning(f"释放单例异常（不影响后续执行）：{e}")

    if analysis_already_done:
        logging.info("Phase 4 跳过：回测数据已由其他节点完成")
    else:
        try:
            bdj.main()   # 策略回测（重新加载stock_hist_data，但此时缓存已热，无API调用）
        except Exception as e:
            logging.error(f"execute_daily_job backtest异常", exc_info=True)

    # ================================================================
    # 数据健康检查：在流水线结束后，检查各表是否有今日数据
    # 方便排查"页面无数据"问题
    # ================================================================
    _data_health_check(start)

    logging.info("######## 完成任务, 使用时间: %s 秒 #######" % (time.time() - start))


def _data_health_check(pipeline_start):
    """流水线结束后，检查核心表是否有当日数据"""
    try:
        import instock.lib.database as mdb
        import instock.lib.trade_time as trd
        run_date, run_date_nph = trd.get_trade_date_last()
        date_str = run_date_nph.strftime("%Y-%m-%d")

        tables_to_check = [
            ('cn_stock_spot', '实时行情'),
            ('cn_stock_selection', '综合选股'),
            ('cn_stock_indicators', '技术指标'),
            ('cn_stock_kline_pattern', 'K线形态'),
            ('cn_stock_strategy_enter', '放量上涨(策略)'),
            ('cn_stock_strategy_gpt_value', 'GPT综合选股'),
            ('cn_stock_backtest', '回测汇总'),
        ]
        results = []
        for table, label in tables_to_check:
            try:
                if not mdb.checkTableIsExist(table):
                    results.append(f"  {label}({table}): 表不存在")
                    continue
                row = mdb.executeSqlFetch(
                    f"SELECT COUNT(*) AS cnt, MAX(`date`) AS latest FROM `{table}`"
                )
                if row:
                    cnt_today_row = mdb.executeSqlFetch(
                        f"SELECT COUNT(*) AS cnt FROM `{table}` WHERE `date` = %s",
                        (date_str,)
                    )
                    cnt_today = cnt_today_row[0][0] if cnt_today_row else 0
                    latest = row[0][1]
                    latest_str = latest.strftime("%Y-%m-%d") if hasattr(latest, 'strftime') else str(latest)
                    total = row[0][0]
                    results.append(f"  {label}: 今日({date_str})={cnt_today}条, 最近日期={latest_str}, 总计={total}条")
                else:
                    results.append(f"  {label}({table}): 空表")
            except Exception as e:
                results.append(f"  {label}({table}): 查询异常 {e}")

        health = "\n".join(results)
        logging.info(f"===== 数据健康检查 [{date_str}] =====\n{health}")
    except Exception as e:
        logging.warning(f"数据健康检查异常（不影响任务结果）：{e}")


# main函数入口
if __name__ == '__main__':
    main()
