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
import fetch_data_job as fdj
import basic_data_daily_job as hdj
import basic_data_other_daily_job as hdtj
import basic_data_after_close_daily_job as acdj
import streaming_analysis_job as saj
import backtest_data_daily_job as bdj
import selection_data_daily_job as sddj
import gpt_value_data_job as gptj

__author__ = 'InStock'
__date__ = '2026/02/14'


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
        logging.error(f"execute_daily_job basic_data_daily异常", exc_info=True)

    try:
        sddj.main()  # 综合选股数据入库（需要API获取选股器数据）
    except Exception as e:
        logging.error(f"execute_daily_job selection_data异常", exc_info=True)

    # ================================================================
    # Phase 3: 扩展数据获取与入库（独立API：资金流向、龙虎榜等）
    # ================================================================
    try:
        hdtj.main()  # 资金流向、龙虎榜、筹码等（I/O密集，内存占用低）
    except Exception as e:
        logging.error(f"execute_daily_job basic_data_other异常", exc_info=True)

    try:
        gptj.main()  # GPT综合选股（纯DB读取+筛选，无API调用）
    except Exception as e:
        logging.error(f"execute_daily_job gpt_value异常", exc_info=True)

    # 释放 stock_data 单例：如果 Phase 2 API 失败，单例缓存了 None，
    # Phase 4 流式分析调用 stock_data(date).get_data() 会得到缓存的 None 从而跳过。
    # 此处释放单例，让 Phase 4 有机会重新发起 API 请求获取股票列表。
    try:
        from instock.core.singleton_stock import stock_data
        _sd = getattr(stock_data, '_instance', None)
        if _sd is not None and _sd.data is None:
            stock_data.release()
            logging.warning("Phase 2 stock_data 返回 None，已释放单例以允许 Phase 4 重试")
    except Exception:
        logging.debug("释放 stock_data 单例异常", exc_info=True)

    # ================================================================
    # Phase 4: 数据分析（流式处理 — 低内存模式）
    # 从磁盘缓存逐只读取股票历史数据，同时计算指标+K线形态+策略
    # 峰值内存 < 100 MB（vs 原架构 ~1670 MB 全量加载）
    # 无任何外部API调用，数据来源：Phase 1 已更新的本地缓存
    # ================================================================
    try:
        saj.main()   # 流式分析：指标计算 + K线形态识别 + 策略选股（单次遍历）
    except Exception as e:
        logging.error(f"execute_daily_job streaming_analysis异常", exc_info=True)

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

    try:
        bdj.main()   # 策略回测（重新加载stock_hist_data，但此时缓存已热，无API调用）
    except Exception as e:
        logging.error(f"execute_daily_job backtest异常", exc_info=True)

    try:
        acdj.main()  # 闭盘后数据（大宗交易等，需要API）
    except Exception as e:
        logging.error(f"execute_daily_job after_close异常", exc_info=True)

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
                        f"SELECT COUNT(*) AS cnt FROM `{table}` WHERE `date` = '{date_str}'"
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
