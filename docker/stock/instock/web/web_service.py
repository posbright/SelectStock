#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import sys
from abc import ABC

import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado import gen

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
log_path = os.path.join(cpath_current, 'log')
if not os.path.exists(log_path):
    os.makedirs(log_path)
logging.basicConfig(format='%(asctime)s %(message)s', filename=os.path.join(log_path, 'stock_web.log'))
logging.getLogger().setLevel(logging.ERROR)
import instock.lib.torndb as torndb
import instock.lib.database as mdb
import instock.lib.version as version
import instock.web.dataTableHandler as dataTableHandler
import instock.web.dataIndicatorsHandler as dataIndicatorsHandler
import instock.web.strategyParamsHandler as strategyParamsHandler
import instock.web.backtestHandler as backtestHandler
import instock.web.klineHandler as klineHandler
import instock.web.base as webBase

__author__ = 'InStock'
__date__ = '2026/02/14'


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            # 设置路由
            (r"/", HomeHandler),
            (r"/instock/", HomeHandler),
            # 使用datatable 展示报表数据模块。
            (r"/instock/api_data", dataTableHandler.GetStockDataHandler),
            (r"/instock/api/trade_date", dataTableHandler.GetTradeDateHandler),
            (r"/instock/data", dataTableHandler.GetStockHtmlHandler),
            # 获得股票指标数据。
            (r"/instock/data/indicators", dataIndicatorsHandler.GetDataIndicatorsHandler),
            # 加入关注
            (r"/instock/control/attention", dataIndicatorsHandler.SaveCollectHandler),
            # 策略参数管理
            (r"/instock/api/strategy/params", strategyParamsHandler.GetStrategyParamsHandler),
            (r"/instock/api/strategy/params/save", strategyParamsHandler.SaveStrategyParamsHandler),
            (r"/instock/api/strategy/params/reset", strategyParamsHandler.ResetStrategyParamsHandler),
            (r"/instock/api/strategy/filter", strategyParamsHandler.FilterStocksHandler),
            # K线数据JSON API
            (r"/instock/api/kline", klineHandler.GetKlineDataHandler),
            # 回测验证
            (r"/instock/api/backtest/config", backtestHandler.GetBacktestConfigHandler),
            (r"/instock/api/backtest/run", backtestHandler.RunBacktestHandler),
            (r"/instock/api/backtest/batch", backtestHandler.RunBatchBacktestHandler),
        ]
        settings = dict(  # 配置
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,  # True,
            # cookie加密
            cookie_secret="027bb1b670eddf0392cdda8709268a17b58b7",
            debug=False,
        )
        super(Application, self).__init__(handlers, **settings)
        # Have one global connection to the blog DB across all handlers
        self.db = torndb.Connection(**mdb.MYSQL_CONN_TORNDB)


# 首页handler。
class HomeHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        self.render("index.html",
                    stockVersion=version.__version__,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


def main():
    # tornado.options.parse_command_line()
    tornado.options.options.logging = None

    http_server = tornado.httpserver.HTTPServer(Application())
    port = 9988
    http_server.listen(port)

    print(f"服务已启动，web地址 : http://localhost:{port}/")
    logging.info(f"服务已启动，web地址 : http://localhost:{port}/")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
