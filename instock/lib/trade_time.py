#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
from instock.core.singleton_trade_date import stock_trade_date

__author__ = 'InStock'
__date__ = '2026/02/14'


def is_trade_date(date=None):
    trade_date = stock_trade_date().get_data()
    if trade_date is None:
        return False
    if date in trade_date:
        return True
    else:
        return False


def get_previous_trade_date(date, count=1):
    while True:
        date =  get_one_previous_trade_date(date)
        count -= 1
        if count == 0:
            break
    return date

def get_one_previous_trade_date(date):
    trade_date = stock_trade_date().get_data()
    if trade_date is None:
        return date
    tmp_date = date
    for _ in range(365):  # 最多向前找1年
        tmp_date += datetime.timedelta(days=-1)
        if tmp_date in trade_date:
            return tmp_date
    logging.warning(f"get_one_previous_trade_date: 未找到{date}之前的交易日")
    return date


def get_next_trade_date(date):
    trade_date = stock_trade_date().get_data()
    if trade_date is None:
        return date
    tmp_date = date
    for _ in range(365):  # 最多向后找1年
        tmp_date += datetime.timedelta(days=1)
        if tmp_date in trade_date:
            return tmp_date
    logging.warning(f"get_next_trade_date: 未找到{date}之后的交易日")
    return date


OPEN_TIME = (
    (datetime.time(9, 15, 0), datetime.time(11, 30, 0)),
    (datetime.time(13, 0, 0), datetime.time(15, 0, 0)),
)


def is_tradetime(now_time):
    now = now_time.time()
    for begin, end in OPEN_TIME:
        if begin <= now < end:
            return True
    else:
        return False


PAUSE_TIME = (
    (datetime.time(11, 30, 0), datetime.time(12, 59, 30)),
)


def is_pause(now_time):
    now = now_time.time()
    for b, e in PAUSE_TIME:
        if b <= now < e:
            return True
    return False


CONTINUE_TIME = (
    (datetime.time(12, 59, 30), datetime.time(13, 0, 0)),
)


def is_continue(now_time):
    now = now_time.time()
    for b, e in CONTINUE_TIME:
        if b <= now < e:
            return True
    return False


CLOSE_TIME = (
    datetime.time(15, 0, 0),
)


def is_closing(now_time, start=datetime.time(14, 54, 30)):
    now = now_time.time()
    for close in CLOSE_TIME:
        if start <= now < close:
            return True
    return False


def is_close(now_time):
    now = now_time.time()
    for close in CLOSE_TIME:
        if now >= close:
            return True
    return False


def is_open(now_time):
    now = now_time.time()
    if now >= datetime.time(9, 30, 0):
        return True
    return False


def get_trade_hist_interval(date, years=10):
    """
    获取历史数据的时间区间
    
    参数：
        date: 结束日期，支持以下格式：
              - datetime对象
              - 字符串 YYYY-MM-DD
              - 字符串 YYYYMMDD
        years: 历史数据年数，默认10年
    
    返回：
        (date_start, is_cache): 起始日期YYYYMMDD格式，是否可以缓存
    """
    # 处理不同的日期格式
    if isinstance(date, datetime.datetime):
        date_end = date
    elif isinstance(date, datetime.date):
        date_end = datetime.datetime.combine(date, datetime.time())
    elif isinstance(date, str):
        if "-" in date:
            tmp_year, tmp_month, tmp_day = date.split("-")
        else:
            # YYYYMMDD格式
            tmp_year = date[:4]
            tmp_month = date[4:6]
            tmp_day = date[6:8]
        date_end = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day))
    else:
        raise ValueError(f"不支持的日期格式: {type(date)}")
    
    date_start = (date_end + datetime.timedelta(days=-(365 * years))).strftime("%Y%m%d")

    now_time = datetime.datetime.now()
    now_date = now_time.date()
    is_trade_date_open_close_between = False
    if date_end.date() == now_date:
        if is_trade_date(now_date):
            if is_open(now_time) and not is_close(now_time):
                is_trade_date_open_close_between = True

    return date_start, not is_trade_date_open_close_between


def get_trade_date_last():
    now_time = datetime.datetime.now()
    run_date = now_time.date()
    run_date_nph = run_date
    if is_trade_date(run_date):
        if not is_close(now_time):
            run_date = get_previous_trade_date(run_date)
            if not is_open(now_time):
                run_date_nph = run_date
    else:
        run_date = get_previous_trade_date(run_date)
        run_date_nph = run_date
    return run_date, run_date_nph


def get_quarterly_report_date():
    now_time = datetime.datetime.now()
    year = now_time.year
    month = now_time.month
    if 1 <= month <= 3:
        year -= 1  # Q1查的是上一年Q4的报告
        month_day = '1231'
    elif 4 <= month <= 6:
        month_day = '0331'
    elif 7 <= month <= 9:
        month_day = '0630'
    else:
        month_day = '0930'
    return f"{year}{month_day}"


def get_bonus_report_date():
    now_time = datetime.datetime.now()
    year = now_time.year
    month = now_time.month
    if 2 <= month <= 6:
        year -= 1
        month_day = '1231'
    elif 8 <= month <= 12:
        month_day = '0630'
    elif month == 7:
        if now_time.day > 25:
            month_day = '0630'
        else:
            year -= 1
            month_day = '1231'
    else:
        year -= 1
        if now_time.day > 25:
            month_day = '1231'
        else:
            month_day = '0630'
    return f"{year}{month_day}"
