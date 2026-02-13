#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import datetime
import numpy as np
import pandas as pd
import talib as tl
import concurrent.futures
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
import instock.core.crawling.stock_hist_tencent as sht  # 腾讯财经历史K线
import time
import random

__author__ = 'myh '

# 数据源重试配置（支持环境变量覆盖）
DATA_SOURCE_MAX_RETRIES = int(os.environ.get('DATA_SOURCE_MAX_RETRIES', 2))  # 单个数据源最大重试次数（失败后优先换源）
DATA_SOURCE_RETRY_INTERVAL = int(os.environ.get('DATA_SOURCE_RETRY_INTERVAL', 90))  # 基础重试间隔（秒），实际使用指数退避

# 历史数据配置（支持环境变量覆盖）
HIST_DATA_DEFAULT_YEARS = int(os.environ.get('HIST_DATA_DEFAULT_YEARS', 10))  # 默认获取历史数据年数


def _retry_sleep(retry_count, base_interval=None):
    """
    指数退避重试等待
    第1次重试等待 base_interval 秒，第2次等待 base_interval*2 秒，以此类推
    加入较大的随机抖动避免多线程同步重试（惊群效应）
    
    抖动范围为 base_interval 的 10%-30%，确保多线程重试时错开足够时间
    """
    if base_interval is None:
        base_interval = DATA_SOURCE_RETRY_INTERVAL
    base_delay = base_interval * (2 ** retry_count)
    jitter = random.uniform(base_delay * 0.1, base_delay * 0.3)
    delay = base_delay + jitter
    logging.info(f"等待{delay:.0f}秒后重试...")
    time.sleep(delay)

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
# 优先级: 东方财富 -> 腾讯财经 -> 新浪财经
def fetch_etfs(date):
    data = None
    source = None
    
    # 数据源列表，按优先级排序（东方财富更稳定，作为首选）
    data_sources = [
        ("东方财富", fee.fund_etf_spot_em),
        ("腾讯财经", etc.fund_etf_spot_tencent),
        ("新浪财经", esa.fund_etf_spot_sina),
    ]
    
    for source_name, fetch_func in data_sources:
        try:
            logging.info(f"尝试从{source_name}获取ETF数据...")
            data = fetch_func()
            if data is not None and len(data.index) > 0:
                source = source_name
                break
        except Exception as e:
            logging.warning(f"{source_name}ETF数据获取失败：{e}，切换下一个数据源")
            data = None
    
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
# 优先级: 东方财富 -> 腾讯财经 -> 新浪财经
def fetch_stocks(date):
    data = None
    source = None
    
    # 数据源列表，按优先级排序（东方财富更稳定，作为首选）
    data_sources = [
        ("东方财富", she.stock_zh_a_spot_em),
        ("腾讯财经", stc.stock_zh_a_spot_tencent),
        ("新浪财经", ssa.stock_zh_a_spot_sina),
    ]
    
    for source_name, fetch_func in data_sources:
        try:
            logging.info(f"尝试从{source_name}获取股票数据...")
            data = fetch_func()
            if data is not None and len(data.index) > 0:
                source = source_name
                break
        except Exception as e:
            logging.warning(f"{source_name}数据获取失败：{e}，切换下一个数据源")
            data = None
    
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
        try:
            logging.info(f"尝试从{source_name}获取选股数据...")
            data = fetch_func()
            if data is not None and len(data.index) > 0:
                source = source_name
                break
        except Exception as e:
            logging.warning(f"{source_name}选股数据获取失败：{e}，切换下一个数据源")
            data = None
    
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
        
        # 只保留表定义中存在的列，避免 INSERT 时列不匹配
        valid_columns = list(tbs.TABLE_CN_STOCK_SELECTION['columns'].keys())
        existing_columns = [col for col in valid_columns if col in data.columns]
        data = data[existing_columns]
        
        return data
    except Exception as e:
        logging.error(f"stockfetch.fetch_stocks_selection处理异常：{e}")
    return None


# 读取股票资金流向（支持多数据源：新浪财经 -> 东方财富）
def fetch_stocks_fund_flow(index):
    data = None
    source = None
    cn_flow = tbs.CN_STOCK_FUND_FLOW[index]
    
    # 数据源列表，按优先级排序（东方财富更稳定，作为首选）
    data_sources = [
        ("东方财富", lambda: sff.stock_individual_fund_flow_rank(indicator=cn_flow['cn'])),
        ("新浪财经", lambda: sfs.stock_individual_fund_flow_rank_sina(indicator=cn_flow['cn'])),
    ]
    
    for source_name, fetch_func in data_sources:
        try:
            logging.info(f"尝试从{source_name}获取资金流向数据...")
            data = fetch_func()
            if data is not None and len(data.index) > 0:
                source = source_name
                break
        except Exception as e:
            logging.warning(f"{source_name}资金流向数据获取失败：{e}，切换下一个数据源")
            data = None
    
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
        if data is None or data.empty:
            logging.warning(f"板块资金流向数据为空：sector={index_sector}, indicator={cn_flow['cn']}")
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
    
    # 数据源列表，按优先级排序（东方财富更稳定，作为首选）
    data_sources = [
        ("东方财富", lambda: sle.stock_lhb_detail_em(start_date, end_date)),
        ("新浪财经", lambda: sls.stock_lhb_detail_daily_sina(end_date)),
    ]
    
    for source_name, fetch_func in data_sources:
        try:
            logging.info(f"尝试从{source_name}获取龙虎榜数据...")
            data = fetch_func()
            if data is not None and len(data.index) > 0:
                source = source_name
                break
        except Exception as e:
            logging.warning(f"{source_name}龙虎榜数据获取失败：{e}，切换下一个数据源")
            data = None
    
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
#   date_start: 起始日期，格式 YYYYMMDD，默认为20年前
#   date_end: 结束日期，格式 YYYYMMDD，默认为当前日期
#   is_cache: 是否使用缓存
#   years: 历史数据年数，默认10年
# 数据单位说明：
#   缓存中的 volume = 手（100股），各数据源已统一
#   本函数返回的 volume = 股（手 × 100）
#   amount = 元
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


def _fetch_from_sources(code, fetch_start, date_end, adjust=''):
    """
    从多个数据源获取K线数据（东方财富 → 腾讯财经 → 新浪财经）
    
    所有数据源返回的数据格式已统一：
    - 列顺序：[date, open, close, high, low, volume, amount, amplitude, quote_change, ups_downs, turnover]
    - volume 单位：手（100股）
    - amount 单位：元
    - date 格式：YYYY-MM-DD
    
    参数：
        code: 股票代码
        fetch_start: 起始日期 YYYYMMDD
        date_end: 结束日期 YYYYMMDD
        adjust: 复权类型
    返回：
        DataFrame 或 None
    """
    data_sources = [
        ('东方财富', lambda: she.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=fetch_start, end_date=date_end, adjust=adjust
        )),
        ('腾讯财经', lambda: sht.stock_zh_a_hist_tencent(
            symbol=code, period="daily",
            start_date=fetch_start, end_date=date_end, adjust=adjust
        )),
        ('新浪财经', lambda: shs.stock_zh_a_hist_sina(
            symbol=code, period="daily",
            start_date=fetch_start, end_date=date_end, adjust=adjust
        ))
    ]

    for source_name, fetch_func in data_sources:
        for retry in range(DATA_SOURCE_MAX_RETRIES):
            try:
                new_data = fetch_func()
                if new_data is not None and len(new_data) > 0:
                    # 统一列名为 CN_STOCK_HIST_DATA 标准
                    new_data.columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
                    logging.debug(f"从{source_name}成功获取数据: {code} ({fetch_start}-{date_end})")
                    return new_data
            except (ConnectionError, ConnectionResetError, ConnectionAbortedError) as e:
                # 连接级错误（IP封禁/网络不可达）：立即跳到下一个数据源，不浪费时间重试
                logging.warning(f"从{source_name}获取数据失败(连接错误，跳过重试): {code} - {e}")
                break
            except Exception as e:
                err_str = str(e)
                # 检查是否为连接类错误（可能被包装在其他异常中）
                if 'RemoteDisconnected' in err_str or 'Connection aborted' in err_str or 'ConnectionReset' in err_str:
                    logging.warning(f"从{source_name}获取数据失败(连接错误，跳过重试): {code} - {e}")
                    break
                logging.warning(f"从{source_name}获取数据失败(尝试{retry+1}/{DATA_SOURCE_MAX_RETRIES}): {code} - {e}")
                if retry < DATA_SOURCE_MAX_RETRIES - 1:
                    _retry_sleep(retry)

        # 当前数据源所有重试都失败，尝试下一个
    return None


def _to_date_str(d):
    """将日期转为 YYYYMMDD 格式字符串"""
    if isinstance(d, str):
        return d.replace("-", "")
    return d.strftime("%Y%m%d")


def _to_dash_date(yyyymmdd):
    """将 YYYYMMDD 转为 YYYY-MM-DD"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def stock_hist_cache_incremental(code, date_start, date_end, is_cache=True, adjust=''):
    """
    增量更新的股票历史数据缓存（多数据源支持）
    
    支持三种增量场景：
    1. 尾部追加：缓存最后日期 < date_end，从缓存末尾向后拉取
    2. 向前补数据：date_start < 缓存最早日期，从 date_start 到缓存起始拉取
    3. 无缓存：全量拉取 date_start ~ date_end
    
    数据源优先级：东方财富 → 腾讯财经 → 新浪财经
    
    参数：
        code: 股票代码
        date_start: 起始日期 YYYYMMDD
        date_end: 结束日期 YYYYMMDD
        is_cache: 是否使用缓存
        adjust: 复权类型 qfq/hfq/''
    """
    # 标准列名（用于缓存统一）
    _standard_columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
    # 旧列名 → 新列名映射（兼容旧缓存数据）
    _column_rename_map = {
        'pct_chg': 'quote_change',
        'change': 'ups_downs',
    }
    cache_file = _get_cache_file_path(code, adjust)
    
    try:
        cached_data = None
        cache_first_date = None
        cache_last_date = None
        
        # 1. 读取缓存
        if is_cache and os.path.isfile(cache_file):
            try:
                cached_data = pd.read_pickle(cache_file, compression="gzip")
                if cached_data is not None and len(cached_data) > 0 and 'date' in cached_data.columns:
                    # 统一旧缓存列名（兼容 EastMoney 旧列名 pct_chg/change）
                    cached_data = cached_data.rename(columns=_column_rename_map)
                    # 合并重复列（旧缓存可能已含新旧两套列名，用 fillna 合并）
                    dup_mask = cached_data.columns.duplicated(keep=False)
                    if dup_mask.any():
                        for col_name in cached_data.columns[dup_mask].unique():
                            dup_cols = cached_data.loc[:, cached_data.columns == col_name]
                            merged = dup_cols.iloc[:, 0].fillna(dup_cols.iloc[:, 1])
                            cached_data = cached_data.loc[:, cached_data.columns != col_name]
                            cached_data[col_name] = merged
                    # 确保只保留标准列，丢弃多余列
                    valid_cols = [c for c in _standard_columns if c in cached_data.columns]
                    cached_data = cached_data[valid_cols]
                    cache_first_date = _to_date_str(cached_data['date'].min())
                    cache_last_date = _to_date_str(cached_data['date'].max())
                else:
                    cached_data = None
            except Exception as e:
                logging.warning(f"读取缓存失败，将重新获取: {code} - {e}")
                cached_data = None
        
        # 2. 确定需要拉取的区间
        fetch_ranges = []  # [(start, end), ...]
        
        if cached_data is not None:
            # 2a. 向前补数据：请求起始日期 < 缓存最早日期
            if date_start < cache_first_date:
                # 从 date_start 拉到缓存最早日期的前一天
                first_date_obj = datetime.datetime.strptime(cache_first_date, "%Y%m%d")
                prev_day = (first_date_obj - datetime.timedelta(days=1)).strftime("%Y%m%d")
                if date_start <= prev_day:
                    fetch_ranges.append((date_start, prev_day))
            
            # 2b. 尾部追加：缓存最后日期 < 请求结束日期
            if cache_last_date < date_end:
                last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
                next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
                if next_day <= date_end:
                    fetch_ranges.append((next_day, date_end))
        else:
            # 2c. 无缓存，全量拉取
            fetch_ranges.append((date_start, date_end))
        
        # 3. 执行数据拉取
        all_new_data = []
        for fetch_start, fetch_end in fetch_ranges:
            new_data = _fetch_from_sources(code, fetch_start, fetch_end, adjust)
            if new_data is not None and len(new_data) > 0:
                all_new_data.append(new_data)
        
        # 4. 合并数据
        parts = []
        if cached_data is not None:
            parts.append(cached_data)
        parts.extend(all_new_data)
        
        if not parts:
            return None
        
        if len(parts) == 1:
            combined_data = parts[0]
        else:
            combined_data = pd.concat(parts, ignore_index=True)
            combined_data = combined_data.drop_duplicates(subset=['date'], keep='last')
            combined_data = combined_data.sort_values(by='date').reset_index(drop=True)
        
        # 5. 保存更新后的缓存（有新数据时才写入）
        if is_cache and len(all_new_data) > 0 and combined_data is not None and len(combined_data) > 0:
            try:
                combined_data.to_pickle(cache_file, compression="gzip")
                if 'date' in combined_data.columns:
                    last_date = _to_date_str(combined_data['date'].max())
                    _write_cache_meta(code, last_date, adjust)
            except Exception as e:
                logging.warning(f"保存缓存失败: {code} - {e}")
        
        # 6. 过滤并返回请求范围内的数据
        result = combined_data[
            (combined_data['date'] >= _to_dash_date(date_start)) &
            (combined_data['date'] <= _to_dash_date(date_end))
        ].copy()
        
        return result if len(result) > 0 else None
        
    except Exception as e:
        logging.error(f"stockfetch.stock_hist_cache_incremental处理异常：{code}代码{e}")
    return None


def clean_expired_cache(expire_days=None):
    """
    智能清理缓存文件：
    1. 删除已退市股票（不在当前股票列表中）的缓存
    2. 删除除权除息后前复权数据已过时的缓存（以便下次运行时重新拉取正确的前复权数据）
    3. 删除损坏的缓存文件（无法解析的 .meta 文件）

    保留策略：
    - 活跃股票的缓存始终保留（历史数据不可变，具有分析价值）
    - 停牌股票的缓存保留（停牌结束后可继续增量更新）
    - 长假期间的缓存保留（不因未更新而误删）

    参数：
        expire_days: 兼容参数，不再使用（保留以避免调用方报错）
    """
    # 获取当前全部A股代码集合（包含停牌股，不过滤价格）
    # 注意：不能使用 fetch_stocks()，因为它会用 is_open 过滤掉停牌股（价格为NaN），
    #       导致停牌股被误判为退市而删除缓存
    active_codes = set()
    try:
        raw_data = she.stock_zh_a_spot_em()
        if raw_data is not None and len(raw_data) > 0:
            # 东方财富返回的列中，'代码'列（第11列，f12字段）包含股票代码
            code_col = '代码' if '代码' in raw_data.columns else raw_data.columns[10]
            all_codes = raw_data[code_col].astype(str).tolist()
            # 只保留A股代码
            active_codes = set(c for c in all_codes if is_a_stock(c))
            logging.info(f"获取到 {len(active_codes)} 只A股代码（含停牌股）")
        else:
            logging.warning("无法获取股票列表，跳过退市股票清理（避免误删）")
    except Exception as e:
        logging.warning(f"获取股票列表失败，跳过退市股票清理：{e}")

    # 获取近期已实施除权除息的股票代码（需要刷新前复权缓存）
    bonus_codes = set()
    try:
        bonus_data = fetch_stocks_bonus(None)
        if bonus_data is not None and len(bonus_data) > 0:
            # 只筛选除权除息日在最近35天内的股票（即上个月内已实施除权的）
            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=35)).strftime("%Y-%m-%d")
            ex_div_col = 'ex_dividend_date'
            if ex_div_col in bonus_data.columns:
                recent_bonus = bonus_data[
                    bonus_data[ex_div_col].notna() &
                    (bonus_data[ex_div_col].astype(str) >= cutoff_date)
                ]
                bonus_codes = set(recent_bonus['code'].tolist())
            if bonus_codes:
                logging.info(f"发现 {len(bonus_codes)} 只近期已除权除息的股票")
    except Exception:
        pass  # 获取失败不影响清理

    delisted_count = 0
    bonus_count = 0
    corrupt_count = 0

    try:
        for root, dirs, files in os.walk(stock_hist_cache_path):
            for file in files:
                if not file.endswith('.meta'):
                    continue

                meta_path = os.path.join(root, file)

                # 从文件名提取股票代码（格式：000001qfq.meta）
                code = None
                adjust = ''
                try:
                    base_name = file.replace('.meta', '')
                    # 代码为6位数字
                    if len(base_name) >= 6 and base_name[:6].isdigit():
                        code = base_name[:6]
                        adjust = base_name[6:]  # 如 'qfq', 'hfq', ''
                except Exception:
                    pass

                if code is None:
                    # 文件名格式无法解析，视为损坏文件
                    _remove_cache_pair(meta_path)
                    corrupt_count += 1
                    continue

                # 1. 清理退市股票缓存
                if active_codes and code not in active_codes:
                    _remove_cache_pair(meta_path)
                    delisted_count += 1
                    continue

                # 2. 清理有除权除息的股票的前复权缓存（以便重新拉取正确数据）
                if code in bonus_codes and adjust == 'qfq':
                    _remove_cache_pair(meta_path)
                    bonus_count += 1
                    continue

    except Exception as e:
        logging.error(f"清理缓存失败: {e}")

    total = delisted_count + bonus_count + corrupt_count
    if total > 0:
        logging.info(
            f"缓存清理完成：退市股票 {delisted_count} 个，"
            f"除权除息刷新 {bonus_count} 个，"
            f"损坏文件 {corrupt_count} 个，"
            f"共清理 {total} 个"
        )
    else:
        logging.info("缓存清理完成：无需清理")

    return total


def _remove_cache_pair(meta_path):
    """删除缓存文件对（.meta + .gzip.pickle）"""
    try:
        cache_file = meta_path.replace('.meta', '.gzip.pickle')
        if os.path.exists(cache_file):
            os.remove(cache_file)
        if os.path.exists(meta_path):
            os.remove(meta_path)
    except Exception as e:
        logging.warning(f"删除缓存文件失败: {meta_path} - {e}")


# 保留原有函数以兼容旧代码
def stock_hist_cache(code, date_start, date_end=None, is_cache=True, adjust=''):
    """
    兼容旧版本的缓存函数，内部调用增量更新版本
    """
    if date_end is None:
        date_end = datetime.datetime.now().strftime("%Y%m%d")
    return stock_hist_cache_incremental(code, date_start, date_end, is_cache, adjust)


def update_all_caches(stocks, date_start, date_end, workers=2):
    """
    批量更新所有股票的缓存文件（仅更新缓存，不保留在内存中）
    
    与 stock_hist_data 的区别：
    - stock_hist_data: 全部加载到内存的 dict 中（~1.6GB），供后续分析直接读取
    - update_all_caches: 仅触发增量缓存更新，处理完每只股票即释放内存
    
    5层限流防护策略：
    第1层 - 控制并发：默认 2 线程（最大 4），有效 QPS ≈ 1.0
    第2层 - 请求间隔：每次 API 请求后等待 1.0-3.0 秒（缓存命中零延迟）
    第3层 - 批次冷却：每 100 只股票暂停 8-15 秒，让连接池充分冷却
    第4层 - 限流检测：连续 3 次失败即触发暂停，渐进退避（120s→240s→480s）
    第5层 - 熔断保护：累计 3 次限流后终止任务，恢复后自动降速 50%
    
    参数：
        stocks: 股票列表 [(date, code), ...]
        date_start: 起始日期 YYYYMMDD
        date_end: 结束日期 YYYYMMDD
        workers: 并发线程数（默认2，不建议超过4）
    返回：
        (success_count, fail_count)
    """
    import threading
    
    success = 0
    fail = 0
    skip = 0                           # 缓存已最新，无需请求API
    consecutive_fails = 0              # 连续失败计数（用于检测限流）
    throttle_count = 0                 # 限流暂停累计触发次数
    _lock = threading.Lock()           # 保护所有共享计数器
    _throttle_event = threading.Event()  # 限流暂停信号
    _throttle_event.set()              # 初始状态：不暂停
    _abort = False                     # 熔断标志
    
    # ── 限流参数 ──
    CONSECUTIVE_FAIL_THRESHOLD = 3     # 连续失败阈值（尽早检测限流，避免浪费请求）
    BASE_THROTTLE_PAUSE = 120          # 首次限流暂停秒数（后续每次翻倍：120→240→480）
    MAX_THROTTLE_COUNT = 3             # 最多触发限流次数，超过后终止任务（疑似IP被封）
    BATCH_PAUSE_INTERVAL = 100         # 每处理 N 只股票后暂停
    BATCH_PAUSE_SECONDS = (8, 15)      # 批次暂停时间范围

    # 自适应请求延迟（每次限流恢复后自动加大 50%，上限 5-8 秒）
    request_delay = [1.0, 3.0]         # [最小, 最大] 秒
    
    def _update_one(stock):
        """更新单只股票的缓存，返回 'skip'/True/False"""
        nonlocal consecutive_fails
        code = stock[1]
        
        # 熔断检查：任务已终止则立即返回
        if _abort:
            return False
        
        # 预检查：缓存已最新则跳过（零延迟，不发起任何API请求）
        meta = _read_cache_meta(code, 'qfq')
        if meta and meta.get('last_date') and meta['last_date'] >= date_end:
            return 'skip'
        
        # 等待限流暂停恢复
        _throttle_event.wait()
        
        if _abort:
            return False
        
        try:
            data = stock_hist_cache_incremental(code, date_start, date_end, is_cache=True, adjust='qfq')
            ok = data is not None and len(data) > 0
            if ok:
                with _lock:
                    consecutive_fails = 0  # 成功时重置连续失败计数
            return ok
        except Exception as e:
            logging.error(f"update_all_caches处理异常：{code} - {e}")
            return False
        finally:
            # 仅在实际可能发起 API 请求时添加延迟
            # （预检查跳过的股票通过 return 'skip' 提前返回，不经过此路径）
            if not _abort:
                time.sleep(random.uniform(request_delay[0], request_delay[1]))
    
    # 限制并发数，避免过多线程同时请求 API
    workers = min(workers, 4)
    
    try:
        processed_total = 0
        api_processed = 0  # 实际发起 API 请求的数量（用于批次暂停计数）
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_stock = {executor.submit(_update_one, stock): stock for stock in stocks}
            for future in concurrent.futures.as_completed(future_to_stock):
                if _abort:
                    break
                
                try:
                    result = future.result()
                    if result == 'skip':
                        skip += 1
                    elif result:
                        success += 1
                        api_processed += 1
                    else:
                        fail += 1
                        api_processed += 1
                        # 限流检测：连续失败达到阈值时触发暂停
                        should_throttle = False
                        pause_time = 0
                        with _lock:
                            consecutive_fails += 1
                            # 仅当未处于限流暂停状态时才触发新的暂停
                            if consecutive_fails >= CONSECUTIVE_FAIL_THRESHOLD and _throttle_event.is_set():
                                throttle_count += 1
                                pause_time = BASE_THROTTLE_PAUSE * (2 ** (throttle_count - 1))
                                
                                if throttle_count >= MAX_THROTTLE_COUNT:
                                    logging.error(
                                        f"限流已触发 {throttle_count} 次，疑似 IP 被封禁，"
                                        f"终止任务以避免进一步封禁。"
                                        f"当前进度：成功={success}, 失败={fail}, 跳过={skip}"
                                    )
                                    _abort = True
                                    break
                                
                                should_throttle = True
                                _throttle_event.clear()  # 阻塞所有工作线程
                        
                        if should_throttle:
                            logging.warning(
                                f"连续 {CONSECUTIVE_FAIL_THRESHOLD} 次获取失败，"
                                f"第{throttle_count}次触发限流保护，暂停 {pause_time} 秒..."
                            )
                            time.sleep(pause_time)
                            with _lock:
                                consecutive_fails = 0
                                # 恢复后自动降速：请求间隔加大 50%（上限 5-8 秒）
                                request_delay[0] = min(request_delay[0] * 1.5, 5.0)
                                request_delay[1] = min(request_delay[1] * 1.5, 8.0)
                            _throttle_event.set()  # 恢复所有工作线程
                            logging.info(
                                f"限流暂停结束，恢复请求。"
                                f"请求间隔已调整为 {request_delay[0]:.1f}-{request_delay[1]:.1f} 秒"
                            )
                            
                except Exception as e:
                    fail += 1
                    api_processed += 1
                    stock = future_to_stock[future]
                    logging.error(f"update_all_caches处理异常：{stock[1]} - {e}")
                
                processed_total += 1
                # 每 N 次 API 请求后短暂暂停，让连接池冷却
                if api_processed > 0 and api_processed % BATCH_PAUSE_INTERVAL == 0:
                    pause = random.uniform(*BATCH_PAUSE_SECONDS)
                    remaining = len(stocks) - processed_total
                    logging.info(
                        f"已处理 {processed_total}/{len(stocks)}"
                        f"（成功={success}, 跳过={skip}），"
                        f"暂停 {pause:.0f} 秒，剩余 {remaining}"
                    )
                    time.sleep(pause)
    except Exception as e:
        logging.error(f"update_all_caches处理异常：{e}")
    
    logging.info(
        f"缓存更新完成：成功={success}, 失败={fail}, "
        f"缓存已最新={skip}, 限流触发={throttle_count}次"
    )
    
    return success + skip, fail


def read_stock_hist_from_cache(code, date_start, date_end):
    """
    从缓存文件读取单只股票的历史数据（流式处理用）
    
    与 fetch_stock_hist / stock_hist_cache_incremental 的区别：
    - fetch_stock_hist: 触发缓存增量更新 + API 拉取
    - stock_hist_cache_incremental: 读取缓存 + 按需发起 API 拉取
    - read_stock_hist_from_cache: **仅从已有缓存读取，绝不发起 API 请求**
    
    如果缓存文件不存在或数据为空，返回 None（不会 fallback 到 API）。
    返回的数据已包含 p_change 列和 volume 单位转换（股）。
    """
    try:
        # 标准列名和兼容映射
        _standard_columns = tuple(tbs.CN_STOCK_HIST_DATA['columns'])
        _column_rename_map = {
            'pct_chg': 'quote_change',
            'change': 'ups_downs',
        }
        cache_file = _get_cache_file_path(code, 'qfq')
        
        if not os.path.isfile(cache_file):
            return None
        
        data = pd.read_pickle(cache_file, compression="gzip")
        if data is None or len(data) == 0 or 'date' not in data.columns:
            return None
        
        # 统一旧缓存列名
        data = data.rename(columns=_column_rename_map)
        # 合并重复列
        dup_mask = data.columns.duplicated(keep=False)
        if dup_mask.any():
            for col_name in data.columns[dup_mask].unique():
                dup_cols = data.loc[:, data.columns == col_name]
                merged = dup_cols.iloc[:, 0].fillna(dup_cols.iloc[:, 1])
                data = data.loc[:, data.columns != col_name]
                data[col_name] = merged
        # 确保只保留标准列
        valid_cols = [c for c in _standard_columns if c in data.columns]
        data = data[valid_cols]
        
        # 按请求日期范围过滤
        data_dates = data['date'].apply(_to_date_str)
        mask = (data_dates >= date_start) & (data_dates <= date_end)
        data = data.loc[mask].copy()
        
        if len(data) == 0:
            return None
        
        # 添加 p_change 列和 volume 单位转换
        data['p_change'] = tl.ROC(data['close'].values, 1)
        data['p_change'] = data['p_change'].fillna(0.0)
        data['volume'] = data['volume'].astype('double') * 100
        return data
    except Exception as e:
        logging.error(f"read_stock_hist_from_cache处理异常：{code} - {e}")
    return None
