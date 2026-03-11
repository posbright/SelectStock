#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import instock.core.stockfetch as stf
from instock.lib.singleton_type import singleton_type

__author__ = 'InStock'
__date__ = '2026/02/14'


# 读取股票交易日历数据
# 单例模式：进程内只创建一次。为防止 Web 服务器跨午夜运行导致交易日历过期，
# get_data() 每次调用会检查是否跨日，跨日时自动刷新。
class stock_trade_date(metaclass=singleton_type):
    def __init__(self):
        self.data = None
        self._loaded_date = None  # 记录数据加载时的日期
        self._refresh()

    def _refresh(self):
        try:
            self.data = stf.fetch_stocks_trade_date()
            self._loaded_date = datetime.date.today()
        except Exception as e:
            self.data = None
            logging.error(f"singleton.stock_trade_date处理异常", exc_info=True)

    def get_data(self):
        # 跨日检测：Web 服务器可能运行数天不重启，
        # 若当前日期与加载日期不同，重新获取交易日历
        today = datetime.date.today()
        if self._loaded_date is not None and today != self._loaded_date:
            logging.info(f"stock_trade_date: 检测到跨日({self._loaded_date} → {today})，刷新交易日历")
            self._refresh()
        return self.data
