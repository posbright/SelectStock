#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取作业（Phase 1）

职责：集中执行所有外部API数据获取，将获取与分析彻底分离。
- 预加载 stock_data 单例（实时行情）
- 批量更新历史K线缓存（低内存模式，不保留在内存中）
- 清理过期/退市/除权缓存

设计原则：
1. 本脚本是唯一主动发起大量API请求的入口
2. 后续分析脚本（indicators/klinepattern/strategy）从磁盘缓存按需读取单只股票数据
3. 数据获取失败不影响后续分析（如缓存中有历史数据仍可使用）
4. 支持独立运行（可单独 python fetch_data_job.py 手动触发数据预热）

数据源优先级：
- 实时行情: 东方财富 → 腾讯财经 → 新浪财经
- 历史K线: 东方财富 → 腾讯财经 → 新浪财经
"""

import logging
import time
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.lib.run_template as runt
import instock.core.stockfetch as stf
from instock.core.singleton_stock import stock_data

__author__ = 'InStock'
__date__ = '2026/2/10'


def fetch_all_data(date):
    """
    集中获取所有股票数据
    
    执行顺序：
    1. 清理过期缓存（退市股票、除权除息数据）
    2. 预加载实时行情（stock_data 单例）
    3. 批量更新历史K线缓存（仅更新磁盘缓存，不保留在内存中）
    
    参数：
        date: 交易日期
    
    注意：本函数不使用 before 参数，因为它是数据预加载步骤（不写入数据库），
    应始终执行。run_with_args 对非 save_nph_ 前缀的函数不传递 before 参数。
    """

    start_time = time.time()
    logging.info(f"===== Phase 1: 数据获取开始 [{date}] =====")

    # Step 1: 清理过期缓存
    try:
        logging.info("Step 1/3: 清理过期缓存...")
        cleaned = stf.clean_expired_cache()
        logging.info(f"缓存清理完成，清理了 {cleaned} 个文件")
    except Exception as e:
        logging.warning(f"缓存清理异常（不影响后续执行）：{e}")

    # Step 2: 预加载实时行情（stock_data 单例）
    try:
        logging.info("Step 2/3: 预加载实时行情数据...")
        spot_start = time.time()
        spot = stock_data(date).get_data()
        if spot is not None:
            logging.info(f"实时行情加载成功：{len(spot)} 只股票，耗时 {time.time() - spot_start:.1f}秒")
        else:
            logging.error("实时行情加载失败：stock_data 返回 None")
            return
    except Exception as e:
        logging.error(f"实时行情加载异常", exc_info=True)
        return

    # Step 3: 批量更新历史K线缓存（低内存模式）
    # 仅触发缓存增量更新，每只股票处理完后即释放内存
    # 后续 Phase 4 分析时从缓存按需读取，峰值内存 < 100MB
    try:
        logging.info("Step 3/3: 批量更新历史K线缓存（低内存模式）...")
        hist_start = time.time()
        
        import instock.core.tablestructure as tbs
        import instock.lib.trade_time as trd
        
        _subset = spot[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
        stocks = [tuple(x) for x in _subset.values]
        
        years = stf.HIST_DATA_DEFAULT_YEARS
        date_start, _ = trd.get_trade_hist_interval(stocks[0][0], years)
        # 统一日期格式为 YYYYMMDD（兼容 str/datetime/date/Timestamp）
        raw_date = stocks[0][0]
        if hasattr(raw_date, 'strftime'):
            date_end = raw_date.strftime("%Y%m%d")
        else:
            date_end = str(raw_date).replace("-", "").replace("/", "")[:8]
        
        success, fail = stf.update_all_caches(stocks, date_start, date_end, workers=2)
        elapsed_hist = time.time() - hist_start
        logging.info(f"历史K线缓存更新完成：成功 {success}，失败 {fail}，耗时 {elapsed_hist:.1f}秒")
    except Exception as e:
        logging.error(f"历史K线缓存更新异常", exc_info=True)

    elapsed = time.time() - start_time
    logging.info(f"===== Phase 1: 数据获取完成，总耗时 {elapsed:.1f}秒 =====")


def main():
    """入口函数，通过 run_template 获取交易日期并执行"""
    runt.run_with_args(fetch_all_data)


# main函数入口
if __name__ == '__main__':
    main()
