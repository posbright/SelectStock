#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式数据分析处理器（Phase 4 统一入口）

核心思想：单次遍历 + 按需读取 + 及时释放
- 从磁盘缓存逐只读取股票历史数据（~350 KB/只）
- 对每只股票同时运行：指标计算、K线形态识别、全部策略检测
- 结果分批写入数据库（每 BATCH_SIZE 只股票写入一次）
- 处理完即释放内存，峰值内存 < 100 MB（vs 原架构 ~1670 MB）

替代模块：
- indicators_data_daily_job.py（指标计算）
- klinepattern_data_daily_job.py（K线形态）
- strategy_data_daily_job.py（策略选股）

设计要点：
1. 零API调用：所有数据从 Phase 1 已更新的本地缓存读取
2. 单次遍历：4900 只股票 × 1 次缓存读取 = 4900 次 I/O
   （原架构：3 + 13 = 16 次遍历 × 4900 = 78400 次 I/O）
3. 容错：单只股票处理失败不影响其他股票
4. 批量写入：减少数据库连接开销
"""

import logging
import time
import gc
import concurrent.futures
import pandas as pd
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
import instock.core.tablestructure as tbs
import instock.lib.database as mdb
import instock.lib.trade_time as trd
import instock.core.stockfetch as stf
import instock.core.indicator.calculate_indicator as idr
import instock.core.pattern.pattern_recognitions as kpr
from instock.core.singleton_stock import stock_data
from instock.core.stockfetch import fetch_stock_top_entity_data

__author__ = 'InStock'
__date__ = '2025/7/10'

# 批量写入大小：每处理 BATCH_SIZE 只股票后统一写入数据库
BATCH_SIZE = 200


def streaming_analysis(date):
    """
    流式分析主函数：单次遍历所有股票，同时计算指标、K线形态和策略

    参数：
        date: 交易日期 (datetime.datetime)
    """
    start_time = time.time()
    date_str = date.strftime("%Y-%m-%d")
    logging.info(f"===== Phase 4: 流式分析开始 [{date_str}] =====")

    # 1. 获取股票列表
    try:
        spot = stock_data(date).get_data()
        if spot is None:
            logging.error("流式分析：stock_data 返回 None，无法获取股票列表")
            return
    except Exception as e:
        logging.error(f"流式分析：获取股票列表异常：{e}")
        return

    _subset = spot[list(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])]
    stocks = [tuple(x) for x in _subset.values]
    total_stocks = len(stocks)
    logging.info(f"流式分析：共 {total_stocks} 只股票待处理")

    # 2. 计算日期范围（用于从缓存读取）
    years = stf.HIST_DATA_DEFAULT_YEARS
    date_start, _ = trd.get_trade_hist_interval(date, years)
    date_end = date.strftime("%Y%m%d") if hasattr(date, 'strftime') else str(date).replace("-", "")

    # 3. 构建分析列定义
    # 指标列
    indicator_columns = list(tbs.STOCK_STATS_DATA['columns'])
    indicator_columns.insert(0, 'code')
    indicator_columns.insert(0, 'date')

    # K线形态列
    kline_columns = tbs.STOCK_KLINE_PATTERN_DATA['columns']

    # 策略列表 + 龙虎榜数据（check_high_tight 需要）
    strategies = tbs.TABLE_CN_STOCK_STRATEGIES
    stock_tops = None
    for strategy in strategies:
        if strategy['func'].__name__ == 'check_high_tight':
            try:
                stock_tops = fetch_stock_top_entity_data(date)
            except Exception as e:
                logging.warning(f"获取龙虎榜数据异常（不影响其他策略）：{e}")
            break

    # 4. 验证数据库表 schema（旧版表列数不足时自动重建）
    _ensure_table_schema(tbs.TABLE_CN_STOCK_INDICATORS['name'], tbs.TABLE_CN_STOCK_INDICATORS['columns'])
    _ensure_table_schema(tbs.TABLE_CN_STOCK_KLINE_PATTERN['name'], tbs.TABLE_CN_STOCK_KLINE_PATTERN['columns'])
    for strategy in strategies:
        _ensure_table_schema(strategy['name'], strategy['columns'])

    # 5. 准备数据库表（记录需要清理的表，延迟到首次写入时清理）
    # 采用延迟删除策略：不在开头一次性 DELETE 所有表的当日数据，
    # 而是在每个表首次写入前才 DELETE，避免中途崩溃导致数据丢失
    tables_cleaned = set()  # 记录已经清理过的表

    # 6. 初始化结果缓冲区
    indicator_results = {}      # {(date, code, name): pd.Series}
    kline_results = {}          # {(date, code, name): pd.Series}
    strategy_results = {s['name']: [] for s in strategies}  # {table_name: [(date, code, name)]}

    processed = 0
    skipped = 0
    errors = 0

    # 6. 逐只股票流式处理（多线程并发，但控制同时在内存中的数据量）
    # workers=4 意味着同时最多 4 只股票的历史数据在内存中（~1.4 MB）
    def _process_one_stock(stock):
        """单只股票的完整分析流程（在线程池内执行）"""
        code = stock[1]
        result = {
            'indicator': None,
            'kline': None,
            'strategies': {}  # {table_name: True/False}
        }

        hist_data = stf.read_stock_hist_from_cache(code, date_start, date_end)
        if hist_data is None or len(hist_data) == 0:
            return stock, 'skipped', result

        # --- 指标计算 ---
        try:
            indicator_result = idr.get_indicator(stock, hist_data, indicator_columns, date=date)
            if indicator_result is not None:
                result['indicator'] = indicator_result
        except Exception as e:
            logging.debug(f"指标计算异常：{code} - {e}")

        # --- K线形态识别 ---
        try:
            kline_result = kpr.get_pattern_recognition(stock, hist_data, kline_columns, date=date)
            if kline_result is not None:
                result['kline'] = kline_result
        except Exception as e:
            logging.debug(f"K线形态识别异常：{code} - {e}")

        # --- 策略检测 ---
        for strategy in strategies:
            try:
                func = strategy['func']
                if func.__name__ == 'check_high_tight' and stock_tops is not None:
                    matched = func(stock, hist_data, date=date, istop=(code in stock_tops))
                else:
                    matched = func(stock, hist_data, date=date)
                if matched:
                    result['strategies'][strategy['name']] = True
            except Exception as e:
                logging.debug(f"策略检测异常：{code} {strategy['name']} - {e}")

        return stock, 'ok', result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_stock = {executor.submit(_process_one_stock, stock): stock for stock in stocks}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock = future_to_stock[future]
            code = stock[1]
            try:
                _, status, result = future.result()
                if status == 'skipped':
                    skipped += 1
                    continue

                if result['indicator'] is not None:
                    indicator_results[stock] = result['indicator']
                if result['kline'] is not None:
                    kline_results[stock] = result['kline']
                for s_name, matched in result['strategies'].items():
                    if matched:
                        strategy_results[s_name].append(stock)

                processed += 1

            except Exception as e:
                errors += 1
                logging.error(f"流式分析处理异常：{code} - {e}")

            # 批量写入数据库
            if processed > 0 and processed % BATCH_SIZE == 0:
                _flush_results(indicator_results, kline_results, strategy_results, date_str, strategies, tables_cleaned)
                indicator_results.clear()
                kline_results.clear()
                for k in strategy_results:
                    strategy_results[k] = []
                gc.collect()
                logging.info(f"流式分析进度：{processed}/{total_stocks}（跳过 {skipped}，错误 {errors}）")

    # 7. 写入剩余结果
    _flush_results(indicator_results, kline_results, strategy_results, date_str, strategies, tables_cleaned)

    elapsed = time.time() - start_time
    logging.info(
        f"===== Phase 4: 流式分析完成 =====\n"
        f"  总数: {total_stocks}，处理: {processed}，跳过: {skipped}，错误: {errors}\n"
        f"  耗时: {elapsed:.1f}秒"
    )


def _prepare_tables(date_str, strategies):
    """清理当日旧数据，为批量写入做准备（已弃用，改为延迟删除）"""
    pass


def _clean_table_if_needed(table_name, date_str, tables_cleaned):
    """延迟清理：首次写入某表时才 DELETE 当日旧数据，避免中途崩溃丢数据"""
    if table_name not in tables_cleaned:
        try:
            if mdb.checkTableIsExist(table_name):
                del_sql = f"DELETE FROM `{table_name}` where `date` = '{date_str}'"
                mdb.executeSql(del_sql)
        except Exception as e:
            logging.warning(f"清理表 {table_name} 异常：{e}")
        tables_cleaned.add(table_name)


def _ensure_table_schema(table_name, expected_columns):
    """
    检查表的列是否与代码定义一致，不一致则重建表。
    解决旧版数据库 schema 与新版代码不兼容的问题。
    例如：旧版 cn_stock_indicators 只有 26 列，新版有 77 列。
    """
    if not mdb.checkTableIsExist(table_name):
        return  # 表不存在，后续 insert_db_from_df 会自动创建
    
    try:
        import pymysql
        with pymysql.connect(**mdb.MYSQL_CONN_DBAPI) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
                    (mdb.db_database, table_name)
                )
                db_columns = set(row[0] for row in cur.fetchall())
        
        code_columns = set(expected_columns.keys())
        
        # 检查是否有代码中定义但数据库缺失的列
        missing = code_columns - db_columns
        if missing:
            logging.warning(
                f"表 {table_name} schema 不兼容：缺少 {len(missing)} 列 "
                f"(如 {list(missing)[:5]})，将删除重建"
            )
            mdb.executeSql(f"DROP TABLE `{table_name}`")
            logging.info(f"已删除旧表 {table_name}，将在写入时自动重建")
    except Exception as e:
        logging.warning(f"检查表 {table_name} schema 异常：{e}")


def _flush_results(indicator_results, kline_results, strategy_results, date_str, strategies, tables_cleaned):
    """将缓冲区中的分析结果批量写入数据库"""

    # --- 写入指标数据 ---
    if indicator_results:
        try:
            _write_indicator_results(indicator_results, date_str, tables_cleaned)
        except Exception as e:
            logging.error(f"写入指标数据异常：{e}")

    # --- 写入K线形态数据 ---
    if kline_results:
        try:
            _write_kline_results(kline_results, date_str, tables_cleaned)
        except Exception as e:
            logging.error(f"写入K线形态数据异常：{e}")

    # --- 写入策略数据 ---
    for strategy in strategies:
        table_name = strategy['name']
        matched_stocks = strategy_results.get(table_name, [])
        if matched_stocks:
            try:
                _write_strategy_results(matched_stocks, table_name, date_str, tables_cleaned)
            except Exception as e:
                logging.error(f"写入策略数据异常：{table_name} - {e}")


def _write_indicator_results(results, date_str, tables_cleaned):
    """写入指标计算结果"""
    table_name = tbs.TABLE_CN_STOCK_INDICATORS['name']
    _clean_table_if_needed(table_name, date_str, tables_cleaned)
    cols_type = None
    if not mdb.checkTableIsExist(table_name):
        cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_INDICATORS['columns'])

    dataKey = pd.DataFrame(results.keys())
    _columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
    dataKey.columns = _columns

    dataVal = pd.DataFrame(results.values())
    dataVal.drop('date', axis=1, inplace=True, errors='ignore')

    data = pd.merge(dataKey, dataVal, on=['code'], how='left')
    if date_str != data.iloc[0]['date']:
        data['date'] = date_str
    mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")


def _write_kline_results(results, date_str, tables_cleaned):
    """写入K线形态识别结果"""
    table_name = tbs.TABLE_CN_STOCK_KLINE_PATTERN['name']
    _clean_table_if_needed(table_name, date_str, tables_cleaned)
    cols_type = None
    if not mdb.checkTableIsExist(table_name):
        cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_KLINE_PATTERN['columns'])

    dataKey = pd.DataFrame(results.keys())
    _columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
    dataKey.columns = _columns

    dataVal = pd.DataFrame(results.values())

    data = pd.merge(dataKey, dataVal, on=['code'], how='left')
    if date_str != data.iloc[0]['date']:
        data['date'] = date_str
    mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")


def _write_strategy_results(matched_stocks, table_name, date_str, tables_cleaned):
    """写入策略选股结果"""
    _clean_table_if_needed(table_name, date_str, tables_cleaned)
    cols_type = None
    if not mdb.checkTableIsExist(table_name):
        cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_STRATEGIES[0]['columns'])

    data = pd.DataFrame(matched_stocks)
    columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
    data.columns = columns
    _columns_backtest = tuple(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
    data = pd.concat([data, pd.DataFrame(columns=_columns_backtest)])
    if date_str != data.iloc[0]['date']:
        data['date'] = date_str
    mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")


def guess_indicators(date):
    """
    指标二次筛选：买入/卖出信号

    从已写入的指标表中筛选符合条件的股票，与流式分析独立运行。
    依赖 cn_stock_indicators 表已由 streaming_analysis 写入。
    """
    # 先验证 indicators 表是否存在且有数据
    _table_name = tbs.TABLE_CN_STOCK_INDICATORS['name']
    if not mdb.checkTableIsExist(_table_name):
        logging.info("guess_indicators: cn_stock_indicators 表不存在，跳过")
        return
    
    _guess_buy(date)
    _guess_sell(date)


def _guess_buy(date):
    """筛选买入信号股票"""
    try:
        _table_name = tbs.TABLE_CN_STOCK_INDICATORS['name']
        if not mdb.checkTableIsExist(_table_name):
            return

        _columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
        _selcol = '`,`'.join(_columns)
        sql = f'''SELECT `{_selcol}` FROM `{_table_name}` WHERE `date` = '{date}' and 
                `kdjk` >= 80 and `kdjd` >= 70 and `kdjj` >= 100 and `rsi_6` >= 80 and 
                `cci` >= 100 and `cr` >= 300 and `wr_6` >= -20 and `vr` >= 160'''
        data = pd.read_sql(sql=sql, con=mdb.engine())
        data = data.drop_duplicates(subset="code", keep="last")

        if len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_INDICATORS_BUY['name']
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_INDICATORS_BUY['columns'])

        _columns_backtest = tuple(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
        data = pd.concat([data, pd.DataFrame(columns=_columns_backtest)])
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"streaming_analysis_job._guess_buy处理异常：{e}")


def _guess_sell(date):
    """筛选卖出信号股票"""
    try:
        _table_name = tbs.TABLE_CN_STOCK_INDICATORS['name']
        if not mdb.checkTableIsExist(_table_name):
            return

        _columns = tuple(tbs.TABLE_CN_STOCK_FOREIGN_KEY['columns'])
        _selcol = '`,`'.join(_columns)
        sql = f'''SELECT `{_selcol}` FROM `{_table_name}` WHERE `date` = '{date}' and 
                `kdjk` < 20 and `kdjd` < 30 and `kdjj` < 10 and `rsi_6` < 20 and 
                `cci` < -100 and `cr` < 40 and `wr_6` < -80 and `vr` < 40'''
        data = pd.read_sql(sql=sql, con=mdb.engine())
        data = data.drop_duplicates(subset="code", keep="last")
        if len(data.index) == 0:
            return

        table_name = tbs.TABLE_CN_STOCK_INDICATORS_SELL['name']
        if mdb.checkTableIsExist(table_name):
            del_sql = f"DELETE FROM `{table_name}` where `date` = '{date}'"
            mdb.executeSql(del_sql)
            cols_type = None
        else:
            cols_type = tbs.get_field_types(tbs.TABLE_CN_STOCK_INDICATORS_SELL['columns'])

        _columns_backtest = tuple(tbs.TABLE_CN_STOCK_BACKTEST_DATA['columns'])
        data = pd.concat([data, pd.DataFrame(columns=_columns_backtest)])
        mdb.insert_db_from_df(data, table_name, cols_type, False, "`date`,`code`")
    except Exception as e:
        logging.error(f"streaming_analysis_job._guess_sell处理异常：{e}")


def main():
    """流式分析入口（兼容 run_with_args 调用模式）"""
    import instock.lib.run_template as runt
    runt.run_with_args(streaming_analysis)
    runt.run_with_args(guess_indicators)


# main函数入口
if __name__ == '__main__':
    main()
