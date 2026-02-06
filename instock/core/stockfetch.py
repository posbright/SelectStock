#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import datetime
import numpy as np
import pandas as pd
import talib as tl
import instock.core.tablestructure as tbs
import instock.lib.trade_time as trd
import instock.core.crawling.trade_date_hist as tdh
import instock.core.crawling.fund_etf_em as fee
import instock.core.crawling.stock_selection as sst
import instock.core.crawling.stock_lhb_em as sle
import instock.core.crawling.stock_lhb_sina as sls
import instock.core.crawling.stock_dzjy_em as sde
import instock.core.crawling.stock_hist_em as she
import instock.core.crawling.stock_fund_em as sff
import instock.core.crawling.stock_fhps_em as sfe
import instock.core.crawling.stock_chip_race as scr
import instock.core.crawling.stock_limitup_reason as slr
import instock.core.crawling.stock_tencent as stc  # 腾讯财经备选
import instock.core.crawling.stock_sina as ssa  # 新浪财经备选
import instock.core.crawling.etf_tencent as etc  # ETF腾讯财经备选
import instock.core.crawling.etf_sina as esa  # ETF新浪财经备选
import instock.core.crawling.stock_fund_sina as sfs  # 新浪财经资金流向
import instock.core.crawling.stock_hist_sina as shs  # 新浪财经历史K线
import time

__author__ = 'myh '

# 数据源重试配置（支持环境变量覆盖）
DATA_SOURCE_MAX_RETRIES = int(os.environ.get('DATA_SOURCE_MAX_RETRIES', 2))  # 最大重试次数
DATA_SOURCE_RETRY_INTERVAL = int(os.environ.get('DATA_SOURCE_RETRY_INTERVAL', 30))  # 重试间隔（秒）

# 历史数据配置（支持环境变量覆盖）
HIST_DATA_DEFAULT_YEARS = int(os.environ.get('HIST_DATA_DEFAULT_YEARS', 3))  # 默认获取历史数据年数
HIST_DATA_CACHE_EXPIRE_DAYS = int(os.environ.get('HIST_DATA_CACHE_EXPIRE_DAYS', 7))  # 缓存过期天数

__date__ = '2023/3/10 '

# 设置基础目录，每次加载使用。
cpath_current = os.path.dirname(os.path.dirname(__file__))
stock_hist_cache_path = os.path.join(cpath_current, 'cache', 'hist')
if not os.path.exists(stock_hist_cache_path):
    os.makedirs(stock_hist_cache_path)  # 创建多个文件夹结构。


# 600 601 603 605开头的股票是上证A股
# 600开头的股票是上证A股，属于大盘股，其中6006开头的股票是最早上市的股票，
# 6016开头的股票为大盘蓝筹股；900开头的股票是上证B股；
# 688开头的是上证科创板股票；
# 000开头的股票是深证A股，001、002开头的股票也都属于深证A股，
# 其中002开头的股票是深证A股中小企业股票；
# 200开头的股票是深证B股；
# 300、301开头的股票是创业板股票；400开头的股票是三板市场股票。
# 430、83、87开头的股票是北证A股
def is_a_stock(code):
    # 上证A股  # 深证A股
    return code.startswith(('600', '601', '603', '605', '000', '001', '002', '003', '300', '301'))


# 过滤掉 st 股票。
def is_not_st(name):
    return not name.startswith(('*ST', 'ST'))


# 过滤价格，如果没有基本上是退市了。
def is_open(price):
    return not np.isnan(price)


def is_open_with_line(price):
    return price != '-'


# 读取股票交易日历数据
def fetch_stocks_trade_date():
    try:
        data = tdh.tool_trade_date_hist_sina()
        if data is None or len(data.index) == 0:
            return None
        data_date = set(data['trade_date'].values.tolist())
        return data_date
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_trade_date处理异常：{e}")
    return None


# 读取当天ETF数据（支持多数据源自动切换）
# 优先级: 新浪财经 -> 腾讯财经 -> 东方财富
def fetch_etfs(date):
    data = None
    source = None
    
    # 数据源列表，按优先级排序
    data_sources = [
        ("新浪财经", esa.fund_etf_spot_sina),
        ("腾讯财经", etc.fund_etf_spot_tencent),
        ("东方财富", fee.fund_etf_spot_em),
    ]
    
    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                logging.info(f"尝试从{source_name}获取ETF数据... (第{retry + 1}次)")
                data = fetch_func()
                if data is not None and len(data.index) > 0:
                    source = source_name
                    break
            except Exception as e:
                logging.warning(f"{source_name}ETF数据获取失败 (第{retry + 1}次)：{e}")
                data = None
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    logging.info(f"等待{DATA_SOURCE_RETRY_INTERVAL}秒后重试...")
                    time.sleep(DATA_SOURCE_RETRY_INTERVAL)
        
        if data is not None and len(data.index) > 0:
            break
    
    # 所有数据源都失败
    if data is None or len(data.index) == 0:
        logging.error("所有ETF数据源均获取失败")
        return None
    
    try:
        logging.info(f"成功从{source}获取 {len(data)} 条ETF数据")
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_ETF_SPOT['columns'])
        data = data.loc[data['new_price'].apply(is_open)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_etfs处理异常：{e}")
    return None


# 读取当天股票数据（支持多数据源自动切换）
# 优先级: 新浪财经 -> 腾讯财经 -> 东方财富
def fetch_stocks(date):
    data = None
    source = None
    
    # 数据源列表，按优先级排序
    data_sources = [
        ("新浪财经", ssa.stock_zh_a_spot_sina),
        ("腾讯财经", stc.stock_zh_a_spot_tencent),
        ("东方财富", she.stock_zh_a_spot_em),
    ]
    
    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                logging.info(f"尝试从{source_name}获取股票数据... (第{retry + 1}次)")
                data = fetch_func()
                if data is not None and len(data.index) > 0:
                    source = source_name
                    break
            except Exception as e:
                logging.warning(f"{source_name}数据获取失败 (第{retry + 1}次)：{e}")
                data = None
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    logging.info(f"等待{DATA_SOURCE_RETRY_INTERVAL}秒后重试...")
                    time.sleep(DATA_SOURCE_RETRY_INTERVAL)
        
        if data is not None and len(data.index) > 0:
            break
    
    # 所有数据源都失败
    if data is None or len(data.index) == 0:
        logging.error("所有数据源均获取失败")
        return None
    
    try:
        logging.info(f"成功从{source}获取 {len(data)} 条股票数据")
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_SPOT['columns'])
        data = data.loc[data['code'].apply(is_a_stock)].loc[data['new_price'].apply(is_open)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks处理异常：{e}")
    return None


# 选股器（支持多数据源：东方财富选股器 -> 新浪财经基础数据）
def fetch_stock_selection():
    data = None
    source = None
    
    # 数据源列表，按优先级排序
    # 东方财富提供更完整的数据（包含换手率等），作为首选
    # 新浪财经作为备选（不提供换手率、量比等）
    data_sources = [
        ("东方财富", sst.stock_selection),
        ("新浪财经", ssa.stock_zh_a_spot_sina),
    ]
    
    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                logging.info(f"尝试从{source_name}获取选股数据... (第{retry + 1}次)")
                data = fetch_func()
                if data is not None and len(data.index) > 0:
                    source = source_name
                    break
            except Exception as e:
                logging.warning(f"{source_name}选股数据获取失败 (第{retry + 1}次)：{e}")
                data = None
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    logging.info(f"等待{DATA_SOURCE_RETRY_INTERVAL}秒后重试...")
                    time.sleep(DATA_SOURCE_RETRY_INTERVAL)
        
        if data is not None and len(data.index) > 0:
            break
    
    if data is None or len(data.index) == 0:
        logging.error("所有选股数据源均获取失败")
        return None
    
    try:
        logging.info(f"成功从{source}获取 {len(data)} 条选股数据")
        
        # 先做一次 copy() 去碎片化，避免 PerformanceWarning
        data = data.copy()
        
        if source == "东方财富":
            # 东方财富返回的列名是大写的API字段名（map值），需要映射回数据库字段名
            cols = tbs.TABLE_CN_STOCK_SELECTION['columns']
            rename_map = {cols[k]['map']: k for k in cols if 'map' in cols[k]}
            data = data.rename(columns=rename_map)
            # 东方财富API不返回涨跌额，需要计算: ups_downs = new_price - pre_close
            if 'new_price' in data.columns and 'pre_close' in data.columns:
                data['ups_downs'] = (data['new_price'] - data['pre_close']).round(4)
        elif source == "新浪财经":
            # 新浪财经数据需要重命名列名为英文，与数据库字段一致
            data = data.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'new_price',
                '涨跌幅': 'change_rate',
                '涨跌额': 'ups_downs',
                '成交量': 'volume',
                '成交额': 'turnover',
                '振幅': 'amplitude',
                '换手率': 'turnoverrate',
                '量比': 'volume_ratio',
                '今开': 'open',
                '最高': 'high',
                '最低': 'low',
                '昨收': 'pre_close',
            })
        
        # 添加 date 列（如果不存在）
        if 'date' not in data.columns:
            import datetime
            data['date'] = datetime.date.today()
        
        if 'code' in data.columns:
            data.drop_duplicates('code', keep='last', inplace=True)
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_selection处理异常：{e}")
    return None


# 读取股票资金流向（支持多数据源：新浪财经 -> 东方财富）
def fetch_stocks_fund_flow(index):
    data = None
    source = None
    cn_flow = tbs.CN_STOCK_FUND_FLOW[index]
    
    # 数据源列表，按优先级排序
    data_sources = [
        ("新浪财经", lambda: sfs.stock_individual_fund_flow_rank_sina(indicator=cn_flow['cn'])),
        ("东方财富", lambda: sff.stock_individual_fund_flow_rank(indicator=cn_flow['cn'])),
    ]
    
    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                logging.info(f"尝试从{source_name}获取资金流向数据... (第{retry + 1}次)")
                data = fetch_func()
                if data is not None and len(data.index) > 0:
                    source = source_name
                    break
            except Exception as e:
                logging.warning(f"{source_name}资金流向数据获取失败 (第{retry + 1}次)：{e}")
                data = None
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    logging.info(f"等待{DATA_SOURCE_RETRY_INTERVAL}秒后重试...")
                    time.sleep(DATA_SOURCE_RETRY_INTERVAL)
        
        if data is not None and len(data.index) > 0:
            break
    
    if data is None or len(data.index) == 0:
        logging.error("所有资金流向数据源均获取失败")
        return None
    
    try:
        logging.info(f"成功从{source}获取 {len(data)} 条资金流向数据")
        data.columns = list(cn_flow['columns'])
        data = data.loc[data['code'].apply(is_a_stock)].loc[data['new_price'].apply(is_open_with_line)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_fund_flow处理异常：{e}")
    return None


# 读取板块资金流向
def fetch_stocks_sector_fund_flow(index_sector, index_indicator):
    try:
        cn_flow = tbs.CN_STOCK_SECTOR_FUND_FLOW[1][index_indicator]
        data = sff.stock_sector_fund_flow_rank(indicator=cn_flow['cn'], sector_type=tbs.CN_STOCK_SECTOR_FUND_FLOW[0][index_sector])
        if data is None or len(data.index) == 0:
            return None
        data.columns = list(cn_flow['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_sector_fund_flow处理异常：{e}")
    return None


# 读取股票分红配送
def fetch_stocks_bonus(date):
    try:
        data = sfe.stock_fhps_em(date=trd.get_bonus_report_date())
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_BONUS['columns'])
        data = data.loc[data['code'].apply(is_a_stock)]
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_bonus处理异常：{e}")
    return None


# 股票近三月上龙虎榜且必须有2次以上机构参与的
def fetch_stock_top_entity_data(date):
    run_date = date + datetime.timedelta(days=-90)
    start_date = run_date.strftime("%Y%m%d")
    end_date = date.strftime("%Y%m%d")
    code_name = '代码'
    entity_amount_name = '买方机构数'
    try:
        data = sle.stock_lhb_jgmmtj_em(start_date, end_date)
        if data is None or len(data.index) == 0:
            return None

        # 机构买入次数大于1计算方法，首先：每次要有买方机构数(>0),然后：这段时间买方机构数求和大于1
        mask = (data[entity_amount_name] > 0)  # 首先：每次要有买方机构数(>0)
        data = data.loc[mask]

        if len(data.index) == 0:
            return None

        grouped = data.groupby(by=data[code_name])
        data_series = grouped[entity_amount_name].sum()
        data_code = set(data_series[data_series > 1].index.values)  # 然后：这段时间买方机构数求和大于1

        if not data_code:
            return None

        return data_code
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_top_entity_data处理异常：{e}")
    return None

# 描述: 获取龙虎榜-个股上榜统计（支持多数据源：新浪财经 -> 东方财富）
def fetch_stock_lhb_data(date, count=12):
    data = None
    source = None
    start_date = trd.get_previous_trade_date(date, count).strftime("%Y%m%d")
    end_date = date.strftime("%Y%m%d")
    
    # 数据源列表，按优先级排序
    data_sources = [
        ("新浪财经", lambda: sls.stock_lhb_detail_daily_sina(end_date)),
        ("东方财富", lambda: sle.stock_lhb_detail_em(start_date, end_date)),
    ]
    
    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                logging.info(f"尝试从{source_name}获取龙虎榜数据... (第{retry + 1}次)")
                data = fetch_func()
                if data is not None and len(data.index) > 0:
                    source = source_name
                    break
            except Exception as e:
                logging.warning(f"{source_name}龙虎榜数据获取失败 (第{retry + 1}次)：{e}")
                data = None
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    logging.info(f"等待{DATA_SOURCE_RETRY_INTERVAL}秒后重试...")
                    time.sleep(DATA_SOURCE_RETRY_INTERVAL)
        
        if data is not None and len(data.index) > 0:
            break
    
    if data is None or len(data.index) == 0:
        logging.error("所有龙虎榜数据源均获取失败")
        return None
    
    try:
        logging.info(f"成功从{source}获取 {len(data)} 条龙虎榜数据")
        
        # 根据数据源处理列名
        if source == "新浪财经":
            # 新浪数据需要特殊处理
            data = data.rename(columns={
                '股票代码': 'code',
                '股票名称': 'name',
                '收盘价': 'new_price',
            })
            if 'date' not in data.columns:
                if date is None:
                    data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
                else:
                    data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        else:
            _columns = list(tbs.TABLE_CN_STOCK_lHB['columns'])
            _columns.pop(0)
            data.columns = _columns
            if date is None:
                data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
            else:
                data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop_duplicates('code', keep='last', inplace=True)
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_lhb_data处理异常：{e}")
    return None

# 描述: 获取新浪财经-龙虎榜-个股上榜统计
def fetch_stock_top_data(date):
    try:
        data = sls.stock_lhb_ggtj_sina()
        if data is None or len(data.index) == 0:
            return None
        _columns = list(tbs.TABLE_CN_STOCK_TOP['columns'])
        _columns.pop(0)
        data.columns = _columns
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop_duplicates('code', keep='last', inplace=True)
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_top_data处理异常：{e}")
    return None


# 描述: 获取东方财富网-数据中心-大宗交易-每日统计
def fetch_stock_blocktrade_data(date):
    date_str = date.strftime("%Y%m%d")
    try:
        data = sde.stock_dzjy_mrtj(start_date=date_str, end_date=date_str)
        if data is None or len(data.index) == 0:
            return None

        columns = list(tbs.TABLE_CN_STOCK_BLOCKTRADE['columns'])
        columns.insert(0, 'index')
        data.columns = columns
        data = data.loc[data['code'].apply(is_a_stock)]
        data.drop('index', axis=1, inplace=True)
        return data
    except TypeError:
        logging.error("处理异常：目前还没有大宗交易数据，请17:00点后再获取！")
        return None
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_blocktrade_data处理异常：{e}")
    return None

# 读取早盘抢筹
def fetch_stock_chip_race_open(date):
    try:
        date_str =""
        if date != datetime.datetime.now().date():
            date_str = date.strftime("%Y%m%d")
        data = scr.stock_chip_race_open(date_str)
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_CHIP_RACE_OPEN['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_chip_race_open处理异常：{e}")
    return None

# 读取尾盘抢筹
def fetch_stock_chip_race_end(date):
    try:
        date_str =""
        if date != datetime.datetime.now().date():
            date_str = date.strftime("%Y%m%d")
        data = scr.stock_chip_race_end(date_str)
        if data is None or len(data.index) == 0:
            return None
        if date is None:
            data.insert(0, 'date', datetime.datetime.now().strftime("%Y-%m-%d"))
        else:
            data.insert(0, 'date', date.strftime("%Y-%m-%d"))
        data.columns = list(tbs.TABLE_CN_STOCK_CHIP_RACE_END['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_chip_race_end处理异常：{e}")
    return None

# 读取涨停原因
def fetch_stock_limitup_reason(date):

    try:
        data = slr.stock_limitup_reason(date.strftime("%Y-%m-%d"))
        if data is None or len(data.index) == 0:
            return None
        data.columns = list(tbs.TABLE_CN_STOCK_LIMITUP_REASON['columns'])
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_limitup_reason处理异常：{e}")
    return None

# 读取股票历史数据
def fetch_etf_hist(data_base, date_start=None, date_end=None, adjust='qfq'):
    date = data_base[0]
    code = data_base[1]

    if date_start is None:
        date_start, is_cache = trd.get_trade_hist_interval(date)  # 提高运行效率，只运行一次
    try:
        if date_end is not None:
            data = fee.fund_etf_hist_em(symbol=code, period="daily", start_date=date_start, end_date=date_end,
                                        adjust=adjust)
        else:
            data = fee.fund_etf_hist_em(symbol=code, period="daily", start_date=date_start, adjust=adjust)

        if data is None or len(data.index) == 0:
            return None
        data.columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
        data = data.sort_index()  # 将数据按照日期排序下。
        if data is not None:
            data = data.copy()  # 创建副本避免只读数组问题
            data['p_change'] = tl.ROC(data['close'].values, 1)
            data['p_change'] = data['p_change'].fillna(0.0)
            data['volume'] = data['volume'].astype('double') * 100  # 成交量单位从手变成股。
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_etf_hist处理异常：{e}")
    return None


# 读取股票历史数据（支持增量更新）
# 参数说明：
#   data_base: (date, code) 元组
#   date_start: 起始日期，格式 YYYYMMDD，默认为3年前
#   date_end: 结束日期，格式 YYYYMMDD，默认为当前日期
#   is_cache: 是否使用缓存
#   years: 历史数据年数，默认3年
def fetch_stock_hist(data_base, date_start=None, date_end=None, is_cache=True, years=None):
    date = data_base[0]
    code = data_base[1]

    if years is None:
        years = HIST_DATA_DEFAULT_YEARS
    
    if date_start is None:
        date_start, is_cache = trd.get_trade_hist_interval(date, years)
    
    if date_end is None:
        if isinstance(date, str):
            date_end = date.replace("-", "")
        else:
            date_end = date.strftime("%Y%m%d")
    
    try:
        data = stock_hist_cache_incremental(code, date_start, date_end, is_cache, 'qfq')
        if data is not None:
            # 创建数据副本以避免修改只读数组
            data = data.copy()
            data['p_change'] = tl.ROC(data['close'].values, 1)
            data['p_change'] = data['p_change'].fillna(0.0)
            data['volume'] = data['volume'].astype('double') * 100  # 成交量单位从手变成股。
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stock_hist处理异常：{e}")
    return None


def _get_cache_file_path(code, adjust=''):
    """获取缓存文件路径（按股票代码组织）"""
    cache_dir = os.path.join(stock_hist_cache_path, code[:3])  # 按代码前3位分组
    try:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    except Exception:
        pass
    return os.path.join(cache_dir, f"{code}{adjust}.gzip.pickle")


def _get_cache_meta_path(code, adjust=''):
    """获取缓存元数据文件路径"""
    cache_dir = os.path.join(stock_hist_cache_path, code[:3])
    return os.path.join(cache_dir, f"{code}{adjust}.meta")


def _read_cache_meta(code, adjust=''):
    """读取缓存元数据（最后更新日期）"""
    meta_path = _get_cache_meta_path(code, adjust)
    try:
        if os.path.isfile(meta_path):
            with open(meta_path, 'r') as f:
                content = f.read().strip()
                parts = content.split(',')
                return {
                    'last_date': parts[0] if len(parts) > 0 else None,
                    'update_time': parts[1] if len(parts) > 1 else None
                }
    except Exception:
        pass
    return None


def _write_cache_meta(code, last_date, adjust=''):
    """写入缓存元数据"""
    meta_path = _get_cache_meta_path(code, adjust)
    try:
        with open(meta_path, 'w') as f:
            f.write(f"{last_date},{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
    except Exception:
        pass


def stock_hist_cache_incremental(code, date_start, date_end, is_cache=True, adjust=''):
    """
    增量更新的股票历史数据缓存（多数据源支持）
    
    逻辑：
    1. 检查是否有缓存
    2. 如果有缓存，检查缓存的最后日期
    3. 只获取缓存最后日期之后的增量数据
    4. 合并增量数据到缓存
    
    数据源优先级：新浪财经 → 东方财富
    
    参数：
        code: 股票代码
        date_start: 起始日期 YYYYMMDD
        date_end: 结束日期 YYYYMMDD
        is_cache: 是否使用缓存
        adjust: 复权类型 qfq/hfq/''
    """
    cache_file = _get_cache_file_path(code, adjust)
    
    try:
        cached_data = None
        cache_last_date = None
        
        # 检查缓存是否存在
        if is_cache and os.path.isfile(cache_file):
            try:
                cached_data = pd.read_pickle(cache_file, compression="gzip")
                if cached_data is not None and len(cached_data) > 0:
                    # 获取缓存中的最后日期
                    if 'date' in cached_data.columns:
                        cache_last_date = cached_data['date'].max()
                        if isinstance(cache_last_date, str):
                            cache_last_date = cache_last_date.replace("-", "")
                        else:
                            cache_last_date = cache_last_date.strftime("%Y%m%d")
            except Exception as e:
                logging.warning(f"读取缓存失败，将重新获取: {code} - {e}")
                cached_data = None
        
        # 确定需要获取的日期范围
        fetch_start = date_start
        need_fetch = True
        
        if cached_data is not None and cache_last_date is not None:
            # 如果缓存的最后日期 >= 请求的结束日期，直接返回缓存
            if cache_last_date >= date_end:
                # 过滤并返回请求范围内的数据
                result = cached_data[
                    (cached_data['date'] >= date_start[:4] + '-' + date_start[4:6] + '-' + date_start[6:]) &
                    (cached_data['date'] <= date_end[:4] + '-' + date_end[4:6] + '-' + date_end[6:])
                ].copy()
                return result if len(result) > 0 else None
            
            # 只需要获取增量数据
            # 从缓存最后日期的下一天开始获取
            last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
            next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
            fetch_start = next_day
            
            # 如果增量起始日期 > 结束日期，说明不需要获取新数据
            if fetch_start > date_end:
                need_fetch = False
        
        new_data = None
        if need_fetch:
            # 多数据源获取，优先级：新浪财经 → 东方财富
            data_sources = [
                ('新浪财经', lambda: shs.stock_zh_a_hist_sina(
                    symbol=code, 
                    period="daily", 
                    start_date=fetch_start, 
                    end_date=date_end,
                    adjust=adjust
                )),
                ('东方财富', lambda: she.stock_zh_a_hist(
                    symbol=code, 
                    period="daily", 
                    start_date=fetch_start, 
                    end_date=date_end,
                    adjust=adjust
                ))
            ]
            
            for source_name, fetch_func in data_sources:
                for retry in range(DATA_SOURCE_MAX_RETRIES):
                    try:
                        new_data = fetch_func()
                        if new_data is not None and len(new_data) > 0:
                            # 新浪数据已经是标准格式，东方财富需要转换列名
                            if source_name == '东方财富':
                                new_data.columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
                            logging.debug(f"从{source_name}成功获取增量数据: {code}")
                            break
                    except Exception as e:
                        logging.warning(f"从{source_name}获取增量数据失败(尝试{retry+1}/{DATA_SOURCE_MAX_RETRIES}): {code} - {e}")
                        if retry < DATA_SOURCE_MAX_RETRIES - 1:
                            time.sleep(DATA_SOURCE_RETRY_INTERVAL)
                        new_data = None
                
                if new_data is not None and len(new_data) > 0:
                    break
        
        # 合并数据
        if cached_data is not None and new_data is not None and len(new_data) > 0:
            # 合并缓存和新数据
            combined_data = pd.concat([cached_data, new_data], ignore_index=True)
            combined_data = combined_data.drop_duplicates(subset=['date'], keep='last')
            combined_data = combined_data.sort_values(by='date').reset_index(drop=True)
        elif cached_data is not None:
            combined_data = cached_data
        elif new_data is not None and len(new_data) > 0:
            combined_data = new_data
        else:
            return None
        
        # 保存更新后的缓存
        if is_cache and combined_data is not None and len(combined_data) > 0:
            try:
                combined_data.to_pickle(cache_file, compression="gzip")
                # 更新元数据
                if 'date' in combined_data.columns:
                    last_date = combined_data['date'].max()
                    if isinstance(last_date, str):
                        _write_cache_meta(code, last_date.replace("-", ""), adjust)
                    else:
                        _write_cache_meta(code, last_date.strftime("%Y%m%d"), adjust)
            except Exception as e:
                logging.warning(f"保存缓存失败: {code} - {e}")
        
        # 过滤并返回请求范围内的数据
        result = combined_data[
            (combined_data['date'] >= date_start[:4] + '-' + date_start[4:6] + '-' + date_start[6:]) &
            (combined_data['date'] <= date_end[:4] + '-' + date_end[4:6] + '-' + date_end[6:])
        ].copy()
        
        return result if len(result) > 0 else None
        
    except Exception as e:
        logging.error(f"stockfetch.stock_hist_cache_incremental处理异常：{code}代码{e}")
    return None


def clean_expired_cache(expire_days=None):
    """
    清理过期的缓存文件
    
    参数：
        expire_days: 过期天数，超过此天数未更新的缓存将被删除
    """
    if expire_days is None:
        expire_days = HIST_DATA_CACHE_EXPIRE_DAYS
    
    expire_time = datetime.datetime.now() - datetime.timedelta(days=expire_days)
    cleaned_count = 0
    
    try:
        for root, dirs, files in os.walk(stock_hist_cache_path):
            for file in files:
                if file.endswith('.meta'):
                    meta_path = os.path.join(root, file)
                    try:
                        with open(meta_path, 'r') as f:
                            content = f.read().strip()
                            parts = content.split(',')
                            if len(parts) > 1:
                                update_time = datetime.datetime.strptime(parts[1], "%Y%m%d%H%M%S")
                                if update_time < expire_time:
                                    # 删除缓存文件和元数据文件
                                    cache_file = meta_path.replace('.meta', '.gzip.pickle')
                                    if os.path.exists(cache_file):
                                        os.remove(cache_file)
                                    os.remove(meta_path)
                                    cleaned_count += 1
                    except Exception:
                        pass
    except Exception as e:
        logging.error(f"清理缓存失败: {e}")
    
    if cleaned_count > 0:
        logging.info(f"已清理 {cleaned_count} 个过期缓存文件")
    
    return cleaned_count


# 保留原有函数以兼容旧代码
def stock_hist_cache(code, date_start, date_end=None, is_cache=True, adjust=''):
    """
    兼容旧版本的缓存函数，内部调用增量更新版本
    """
    if date_end is None:
        date_end = datetime.datetime.now().strftime("%Y%m%d")
    return stock_hist_cache_incremental(code, date_start, date_end, is_cache, adjust)
