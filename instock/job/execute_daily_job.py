#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整每日任务（获取 + 分析，服务器回退模式）

执行流程：
Phase 0: 初始化数据库
Phase 1: 轻量级数据入库（行情 + 选股 + 扩展数据 + 收盘后数据）
Phase 2: K线缓存批量更新（内存密集型，独立子进程）
Phase 3: 数据分析（GPT选股 + 基本面选股 + 流式分析）
Phase 4: 回测

设计原则：
- 轻量任务优先完成，确保关键数据安全入库
- K线缓存以独立子进程运行，OOM 不影响已入库数据
- 每个阶段/子任务记录开始/结束日志及耗时
- 分析阶段支持"已完成跳过"（本地优先模式）
- 作业状态通过 cn_job_status 表追踪
"""

import time
import datetime
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
from instock.lib.job_tracker import (
    record_task_start, record_task_end, record_task_skipped,
    is_data_fresh,
)
import instock.lib.envconfig as _cfg

__author__ = 'InStock'
__date__ = '2026/03/12'

# 分析数据跳过阈值（同 analysis_daily_job.py）
ANALYSIS_DONE_THRESHOLD = _cfg.get_int('INSTOCK_ANALYSIS_DONE_THRESHOLD', 1000)

_JOB_DIR = os.path.dirname(os.path.abspath(__file__))
_JOB_NAME = 'run_workdayly'

# 子进程超时（秒）
_JOB_TIMEOUT = _cfg.get_int('INSTOCK_JOB_TIMEOUT', 1800)
_KLINE_JOB_TIMEOUT = _cfg.get_int('INSTOCK_KLINE_JOB_TIMEOUT', 36000)

# 数据新鲜度阈值
_FRESHNESS_THRESHOLDS = {
    'cn_stock_spot': _cfg.get_int('INSTOCK_FRESH_STOCK_SPOT', 3000),
    'cn_stock_selection': _cfg.get_int('INSTOCK_FRESH_SELECTION', 100),
}


def _run_job_subprocess(script_name, label, timeout=_JOB_TIMEOUT):
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
    if _cfg.get_bool('INSTOCK_FORCE_ANALYSIS', False):
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


def _check_and_skip(table_name, date_str, task_label):
    """检查数据新鲜度，决定是否跳过该任务。"""
    if _cfg.get_bool('INSTOCK_FORCE_FETCH', False):
        return False
    threshold = _FRESHNESS_THRESHOLDS.get(table_name, 1)
    fresh, count = is_data_fresh(table_name, date_str, threshold)
    if fresh:
        logging.info(f"[{task_label}] 数据已完整（{table_name}: {count} 条 >= {threshold}），跳过")
        return True
    return False


def _run_stock_spot_buy(date):
    """基本面选股：从 cn_stock_spot 筛选 PE<20、PB<10、ROE>=15% 的股票。"""
    import pandas as pd
    import instock.core.tablestructure as tbs

    try:
        _table_name = tbs.TABLE_CN_STOCK_SPOT['name']
        if not mdb.checkTableIsExist(_table_name):
            return

        date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
        sql = f'''SELECT * FROM `{_table_name}` WHERE `date` = %s and 
                `pe9` > 0 and `pe9` <= 20 and `pbnewmrq` <= 10 and `roe_weight` >= 15'''
        data = pd.read_sql(sql=sql, con=mdb.engine(), params=(date_str,))
        data = data.drop_duplicates(subset="code", keep="last")
        if len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_SPOT_BUY['name']
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` WHERE `date` = %s"
            mdb.executeSql(del_sql, (date_str,))
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_SPOT_BUY['columns'])

        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
        logging.info(f"基本面选股：筛选出 {len(data)} 只股票")
    except Exception as e:
        logging.error(f"基本面选股处理异常", exc_info=True)


def main():
    start = time.time()
    _start = datetime.datetime.now()
    logging.info("######## 任务执行时间: %s #######" % _start.strftime("%Y-%m-%d %H:%M:%S.%f"))

    # 获取交易日期
    try:
        run_date, run_date_nph = trd.get_trade_date_last()
        date_str = run_date_nph.strftime("%Y-%m-%d")
    except Exception as e:
        logging.error("获取交易日期失败，无法继续", exc_info=True)
        return

    overall_start = record_task_start(_JOB_NAME, '__overall__', run_date_nph)

    # ================================================================
    # Phase 0: 初始化
    # ================================================================
    t0 = record_task_start(_JOB_NAME, 'init_db', run_date_nph)
    try:
        bj.main()   # 初始化数据库
        record_task_end(_JOB_NAME, 'init_db', run_date_nph, t0, success=True)
    except Exception as e:
        logging.error(f"execute_daily_job init_job 异常", exc_info=True)
        record_task_end(_JOB_NAME, 'init_db', run_date_nph, t0, success=False, message=str(e))

    # ================================================================
    # Phase 1: 轻量级数据入库
    # ================================================================

    # Phase 1a: 实时行情预加载
    t1a = record_task_start(_JOB_NAME, 'spot_preload', run_date_nph)
    try:
        from instock.core.singleton_stock import stock_data as sd_cls
        spot = sd_cls(run_date_nph).get_data()
        if spot is not None:
            logging.info(f"Phase 1a: 实时行情预加载成功，{len(spot)} 只股票")
            record_task_end(_JOB_NAME, 'spot_preload', run_date_nph, t1a, success=True,
                            rows_affected=len(spot))
        else:
            logging.error("Phase 1a: 实时行情预加载失败（stock_data 返回 None）")
            record_task_end(_JOB_NAME, 'spot_preload', run_date_nph, t1a, success=False)
    except Exception as e:
        logging.error(f"execute_daily_job Phase 1a 行情预加载异常", exc_info=True)
        record_task_end(_JOB_NAME, 'spot_preload', run_date_nph, t1a, success=False, message=str(e))

    # Phase 1b: 基础数据入库
    if _check_and_skip('cn_stock_spot', date_str, '股票行情'):
        record_task_skipped(_JOB_NAME, 'stock_spot', run_date_nph, '数据已完整')
    else:
        t1b = record_task_start(_JOB_NAME, 'stock_spot', run_date_nph)
        try:
            hdj.main()
            record_task_end(_JOB_NAME, 'stock_spot', run_date_nph, t1b, success=True)
        except Exception as e:
            logging.error(f"execute_daily_job basic_data_daily异常", exc_info=True)
            record_task_end(_JOB_NAME, 'stock_spot', run_date_nph, t1b, success=False, message=str(e))

    # Phase 1c: 综合选股数据
    if _check_and_skip('cn_stock_selection', date_str, '综合选股'):
        record_task_skipped(_JOB_NAME, 'selection_data', run_date_nph, '数据已完整')
    else:
        t1c = record_task_start(_JOB_NAME, 'selection_data', run_date_nph)
        try:
            sddj.main()
            record_task_end(_JOB_NAME, 'selection_data', run_date_nph, t1c, success=True)
        except Exception as e:
            logging.error(f"execute_daily_job selection_data异常", exc_info=True)
            record_task_end(_JOB_NAME, 'selection_data', run_date_nph, t1c, success=False, message=str(e))

    # Phase 1d: 扩展数据（资金流向、龙虎榜等）
    t1d = record_task_start(_JOB_NAME, 'basic_data_other', run_date_nph)
    ok = _run_job_subprocess('basic_data_other_daily_job.py', 'execute_daily_job basic_data_other')
    record_task_end(_JOB_NAME, 'basic_data_other', run_date_nph, t1d, success=ok)

    # Phase 1e: GPT综合选股 + 基本面选股
    t1e = record_task_start(_JOB_NAME, 'gpt_value', run_date_nph)
    try:
        gptj.main()
        record_task_end(_JOB_NAME, 'gpt_value', run_date_nph, t1e, success=True)
    except Exception as e:
        logging.error(f"execute_daily_job gpt_value异常", exc_info=True)
        record_task_end(_JOB_NAME, 'gpt_value', run_date_nph, t1e, success=False, message=str(e))

    t1e2 = record_task_start(_JOB_NAME, 'stock_spot_buy', run_date_nph)
    try:
        _run_stock_spot_buy(run_date_nph)
        record_task_end(_JOB_NAME, 'stock_spot_buy', run_date_nph, t1e2, success=True)
    except Exception as e:
        logging.error(f"execute_daily_job stock_spot_buy异常", exc_info=True)
        record_task_end(_JOB_NAME, 'stock_spot_buy', run_date_nph, t1e2, success=False, message=str(e))

    # Phase 1f: 收盘后数据
    t1f = record_task_start(_JOB_NAME, 'after_close', run_date_nph)
    ok = _run_job_subprocess('basic_data_after_close_daily_job.py', 'execute_daily_job after_close')
    record_task_end(_JOB_NAME, 'after_close', run_date_nph, t1f, success=ok)

    # ================================================================
    # Phase 2: K线缓存批量更新（独立子进程）
    # ================================================================
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
        logging.info("Phase 2: 已释放 stock_data 单例，回收内存")
    except Exception:
        logging.debug("释放 stock_data 单例异常", exc_info=True)

    t2 = record_task_start(_JOB_NAME, 'kline_cache', run_date_nph)
    phase2_ok = _run_job_subprocess('kline_cache_daily_job.py', 'execute_daily_job K线缓存更新', timeout=_KLINE_JOB_TIMEOUT)
    record_task_end(_JOB_NAME, 'kline_cache', run_date_nph, t2, success=phase2_ok)
    if not phase2_ok:
        logging.warning(
            "⚠ Phase 2 K线缓存更新失败！Phase 3 将使用可能过期的缓存数据运行。"
            "指标/策略结果基于最后一次成功缓存的K线，结果可能与当日实际行情不符。"
        )
        os.environ['INSTOCK_PHASE2_FAILED'] = '1'
    else:
        os.environ.pop('INSTOCK_PHASE2_FAILED', None)

    # 释放 stock_data 单例（可能缓存了 None）
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
    # ================================================================
    analysis_already_done = _is_analysis_done()

    if analysis_already_done:
        logging.info("Phase 3 跳过：分析数据已由其他节点完成")
        record_task_skipped(_JOB_NAME, 'streaming_analysis', run_date_nph, '已由其他节点完成')
    else:
        t3 = record_task_start(_JOB_NAME, 'streaming_analysis', run_date_nph)
        try:
            saj.main()
            record_task_end(_JOB_NAME, 'streaming_analysis', run_date_nph, t3, success=True)
        except Exception as e:
            logging.error(f"execute_daily_job streaming_analysis异常", exc_info=True)
            record_task_end(_JOB_NAME, 'streaming_analysis', run_date_nph, t3, success=False, message=str(e))

    # ================================================================
    # Phase 4: 回测与收尾
    # ================================================================
    try:
        from instock.core.singleton_stock import stock_data
        stock_data.release()
        gc.collect()
    except Exception as e:
        logging.warning(f"释放单例异常（不影响后续执行）：{e}")

    if analysis_already_done:
        logging.info("Phase 4 跳过：回测数据已由其他节点完成")
        record_task_skipped(_JOB_NAME, 'backtest', run_date_nph, '已由其他节点完成')
    else:
        t4 = record_task_start(_JOB_NAME, 'backtest', run_date_nph)
        try:
            bdj.main()
            record_task_end(_JOB_NAME, 'backtest', run_date_nph, t4, success=True)
        except Exception as e:
            logging.error(f"execute_daily_job backtest异常", exc_info=True)
            record_task_end(_JOB_NAME, 'backtest', run_date_nph, t4, success=False, message=str(e))

    # ================================================================
    # 数据健康检查
    # ================================================================
    _data_health_check(start)

    elapsed = time.time() - start
    record_task_end(_JOB_NAME, '__overall__', run_date_nph, overall_start,
                    success=True, message=f"总耗时 {elapsed:.1f}s")
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
