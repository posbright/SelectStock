#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABC
from tornado import gen
import logging
import instock.core.stockfetch as stf
import instock.core.kline.visualization as vis
import instock.web.base as webBase

__author__ = 'InStock'
__date__ = '2026/02/14'


# 获得页面数据。
class GetDataIndicatorsHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        code = self.get_argument("code", default=None, strip=False)
        date = self.get_argument("date", default=None, strip=False)
        name = self.get_argument("name", default=None, strip=False)
        comp_list = []
        try:
            if code is None:
                return
            # 仅从本地缓存读取历史数据，不发起外部API请求
            stock = stf.read_hist_from_cache((date, code))
            if stock is None:
                logging.warning(f"指标页面：{code} 缓存无数据，请确认数据采集任务已运行")
                return

            pk = vis.get_plot_kline(code, stock, date, name)
            if pk is None:
                return

            comp_list.append(pk)
        except Exception as e:
            logging.error(f"dataIndicatorsHandler.GetDataIndicatorsHandler处理异常", exc_info=True)

        self.render("stock_indicators.html", comp_list=comp_list,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 关注股票。
class SaveCollectHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        import datetime
        import instock.core.tablestructure as tbs
        code = self.get_argument("code", default=None, strip=False)
        otype = self.get_argument("otype", default=None, strip=False)
        try:
            table_name = tbs.TABLE_CN_STOCK_ATTENTION['name']
            if otype == '1':
                sql = f"DELETE FROM `{table_name}` WHERE `code` = %s"
                self.db.execute(sql, code)
            else:
                sql = f"INSERT INTO `{table_name}`(`datetime`, `code`) VALUE(%s, %s)"
                self.db.execute(sql, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), code)
        except Exception as e:
            logging.warning(f"SaveCollectHandler处理异常: {e}")
        self.write("{\"data\":[{}]}")