#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import sys
import threading
from abc import ABC

import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado import gen

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
try:
    from instock.lib.log_config import setup_logging
    setup_logging('web')
except Exception:
    log_path = os.path.join(cpath_current, 'log')
    os.makedirs(log_path, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        filename=os.path.join(log_path, 'stock_web.log'),
        level=logging.WARNING,
    )
import instock.lib.torndb as torndb
import instock.lib.database as mdb
import instock.lib.envconfig as _cfg
import instock.lib.version as version
import instock.web.dataTableHandler as dataTableHandler
import instock.web.dataIndicatorsHandler as dataIndicatorsHandler
import instock.web.strategyParamsHandler as strategyParamsHandler
import instock.web.backtestHandler as backtestHandler
import instock.web.backtestDashboardHandler as backtestDashboardHandler
import instock.web.klineHandler as klineHandler
import instock.web.portfolioBacktestHandler as portfolioBacktestHandler
import instock.web.paperTradingHandler as paperTradingHandler
import instock.web.tradeSignalHandler as tradeSignalHandler
import instock.web.notificationAdminHandler as notificationAdminHandler
import instock.web.notificationConfigHandler as notificationConfigHandler
import instock.web.aiDecisionConfigHandler as aiDecisionConfigHandler
import instock.web.imCommandHandler as imCommandHandler
import instock.web.liveTradingHandler as liveTradingHandler
import instock.web.customIndicatorHandler as customIndicatorHandler
import instock.web.base as webBase

__author__ = 'InStock'
__date__ = '2026/02/14'


class RobotsTxtHandler(tornado.web.RequestHandler, ABC):
    """返回 robots.txt，避免搜索引擎爬虫产生大量 404 日志"""
    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write("User-agent: *\nDisallow: /instock/\nDisallow: /api/\n")


class Application(tornado.web.Application):
    def __init__(self):
        static_path = os.path.join(os.path.dirname(__file__), "static")
        handlers = [
            # ── robots.txt（避免搜索引擎爬虫产生大量 404 日志） ──
            (r"/robots\.txt", RobotsTxtHandler),
            # ── JSON API 路由（Vue SPA 通过 AJAX 调用）──
            (r"/instock/api_data", dataTableHandler.GetStockDataHandler),
            (r"/instock/api/trade_date", dataTableHandler.GetTradeDateHandler),
            # 获得股票指标数据（Bokeh 图表API，返回 HTML 片段）
            (r"/instock/data/indicators", dataIndicatorsHandler.GetDataIndicatorsHandler),
            # 加入关注
            (r"/instock/control/attention", dataIndicatorsHandler.SaveCollectHandler),
            # 策略参数管理
            (r"/instock/api/strategy/params", strategyParamsHandler.GetStrategyParamsHandler),
            (r"/instock/api/strategy/params/save", strategyParamsHandler.SaveStrategyParamsHandler),
            (r"/instock/api/strategy/params/reset", strategyParamsHandler.ResetStrategyParamsHandler),
            (r"/instock/api/strategy/params/history", strategyParamsHandler.GetParamsHistoryHandler),
            (r"/instock/api/strategy/params/diff", strategyParamsHandler.GetParamsDiffHandler),
            (r"/instock/api/strategy/filter", strategyParamsHandler.FilterStocksHandler),
            # K线数据JSON API
            (r"/instock/api/kline", klineHandler.GetKlineDataHandler),
            # 回测验证
            (r"/instock/api/backtest/config", backtestHandler.GetBacktestConfigHandler),
            (r"/instock/api/backtest/run", backtestHandler.RunBacktestHandler),
            (r"/instock/api/backtest/batch", backtestHandler.RunBatchBacktestHandler),
            # 回测看板
            (r"/instock/api/backtest/dashboard/overview", backtestDashboardHandler.DashboardOverviewHandler),
            (r"/instock/api/backtest/dashboard/strategy_detail", backtestDashboardHandler.StrategyDetailHandler),
            (r"/instock/api/backtest/dashboard/distribution", backtestDashboardHandler.ReturnDistributionHandler),
            (r"/instock/api/backtest/dashboard/timeline", backtestDashboardHandler.PerformanceTimelineHandler),
            (r"/instock/api/backtest/dashboard/trade_pairs", backtestDashboardHandler.TradePairHandler),
            # 组合回测 & 策略管理
            (r"/instock/api/strategy/code", portfolioBacktestHandler.SaveStrategyCodeHandler),
            (r"/instock/api/strategy/code/list", portfolioBacktestHandler.GetStrategyCodeListHandler),
            (r"/instock/api/strategy/code/detail", portfolioBacktestHandler.GetStrategyCodeDetailHandler),
            (r"/instock/api/strategy/code/delete", portfolioBacktestHandler.DeleteStrategyCodeHandler),
            (r"/instock/api/strategy/templates", portfolioBacktestHandler.GetStrategyTemplatesHandler),
            (r"/instock/api/strategy/sync_templates", portfolioBacktestHandler.SyncStrategyTemplatesHandler),
            (r"/instock/api/backtest/portfolio/run", portfolioBacktestHandler.RunPortfolioBacktestHandler),
            (r"/instock/api/backtest/portfolio/start", portfolioBacktestHandler.StartPortfolioBacktestHandler),
            (r"/instock/api/backtest/portfolio/log_stream", portfolioBacktestHandler.BacktestLogStreamHandler),
            (r"/instock/api/backtest/portfolio/task_result", portfolioBacktestHandler.BacktestTaskResultHandler),
            (r"/instock/api/backtest/portfolio/list", portfolioBacktestHandler.GetPortfolioBacktestListHandler),
            (r"/instock/api/backtest/portfolio/detail", portfolioBacktestHandler.GetPortfolioBacktestDetailHandler),
            (r"/instock/api/backtest/portfolio/compare", portfolioBacktestHandler.GetBacktestCompareHandler),
            (r"/instock/api/backtest/portfolio/delete", portfolioBacktestHandler.DeleteBacktestHandler),
            (r"/instock/api/backtest/portfolio/list_page", portfolioBacktestHandler.GetPortfolioBacktestListPageHandler),
            # 策略文件夹管理
            (r"/instock/api/strategy/folder/create", portfolioBacktestHandler.CreateFolderHandler),
            (r"/instock/api/strategy/folder/rename", portfolioBacktestHandler.RenameFolderHandler),
            (r"/instock/api/strategy/folder/delete", portfolioBacktestHandler.DeleteFolderHandler),
            # 策略批量操作
            (r"/instock/api/strategy/move", portfolioBacktestHandler.MoveStrategyHandler),
            (r"/instock/api/strategy/batch_delete", portfolioBacktestHandler.BatchDeleteStrategyHandler),
            (r"/instock/api/strategy/rename", portfolioBacktestHandler.RenameStrategyHandler),
            # 模拟交易
            (r"/instock/api/paper/create", paperTradingHandler.CreatePaperTradingHandler),
            (r"/instock/api/paper/action", paperTradingHandler.PaperTradingActionHandler),
            (r"/instock/api/paper/update", paperTradingHandler.UpdatePaperTradingHandler),
            (r"/instock/api/paper/list", paperTradingHandler.GetPaperTradingListHandler),
            (r"/instock/api/paper/detail", paperTradingHandler.GetPaperTradingDetailHandler),
            (r"/instock/api/paper/run", paperTradingHandler.RunPaperTradingHandler),
            (r"/instock/api/paper/execution_log", paperTradingHandler.GetPaperExecutionLogHandler),
            # Phase 3: 交易信号/决策/指标快照/候选筛选快照统一详情（回测与模拟交易复用）
            (r"/instock/api/trade/signal/list", tradeSignalHandler.GetTradeSignalListHandler),
            (r"/instock/api/trade/signal/detail", tradeSignalHandler.GetTradeSignalDetailHandler),
            # Phase 3 扩展：通知事件后台查看（钉钉发送记录、payload、错误信息）
            (r"/instock/api/notification/event/list", notificationAdminHandler.GetNotificationEventListHandler),
            (r"/instock/api/notification/event/detail", notificationAdminHandler.GetNotificationEventDetailHandler),
            # Phase 5: 通知配置 CRUD + 测试发送 + 单事件重试（仅引用环境变量名，不存密钥明文）
            (r"/instock/api/notification/config/list", notificationConfigHandler.GetNotificationConfigListHandler),
            (r"/instock/api/notification/config/detail", notificationConfigHandler.GetNotificationConfigDetailHandler),
            (r"/instock/api/notification/config/save", notificationConfigHandler.SaveNotificationConfigHandler),
            (r"/instock/api/notification/config/delete", notificationConfigHandler.DeleteNotificationConfigHandler),
            (r"/instock/api/notification/config/test_send", notificationConfigHandler.TestSendNotificationHandler),
            (r"/instock/api/notification/event/retry", notificationConfigHandler.RetryNotificationEventHandler),
            # Phase 5: AI 决策配置 CRUD（前端调整 prompt/阈值/数据包范围；密钥仅引用环境变量名）
            (r"/instock/api/ai/config/list", aiDecisionConfigHandler.GetAIDecisionConfigListHandler),
            (r"/instock/api/ai/config/detail", aiDecisionConfigHandler.GetAIDecisionConfigDetailHandler),
            (r"/instock/api/ai/config/save", aiDecisionConfigHandler.SaveAIDecisionConfigHandler),
            (r"/instock/api/ai/config/delete", aiDecisionConfigHandler.DeleteAIDecisionConfigHandler),
            # Phase 6: IM 指令确认（默认关闭，由 INSTOCK_IM_COMMAND_ENABLED=1 启用；仅落库 trade_command，不直接调券商）
            (r"/instock/api/im/status", imCommandHandler.IMStatusHandler),
            (r"/instock/api/im/dingtalk/callback", imCommandHandler.DingtalkCallbackHandler),
            (r"/instock/api/im/command/list", imCommandHandler.ListTradeCommandsHandler),
            (r"/instock/api/im/command/detail", imCommandHandler.GetTradeCommandDetailHandler),
            (r"/instock/api/im/operator/list", imCommandHandler.ListOperatorsHandler),
            (r"/instock/api/im/operator/save", imCommandHandler.SaveOperatorHandler),
            (r"/instock/api/im/operator/delete", imCommandHandler.DeleteOperatorHandler),
            # Phase 7: 实盘交易连接（默认关闭，由 INSTOCK_LIVE_TRADING_ENABLED=1 启用；默认 broker=dry_run）
            (r"/instock/api/live/status", liveTradingHandler.LiveStatusHandler),
            (r"/instock/api/live/execute_pending", liveTradingHandler.ExecutePendingCommandsHandler),
            (r"/instock/api/paper/compare", paperTradingHandler.GetPaperCompareHandler),
            (r"/instock/api/paper/delete", paperTradingHandler.DeletePaperTradingHandler),
            # Phase 9: 自定义综合指标 CRUD + 回测 + 关注榜 + K 线叠加序列
            (r"/instock/api/custom_indicator/list", customIndicatorHandler.ListCustomIndicatorHandler),
            (r"/instock/api/custom_indicator/detail", customIndicatorHandler.GetCustomIndicatorHandler),
            (r"/instock/api/custom_indicator/save", customIndicatorHandler.SaveCustomIndicatorHandler),
            (r"/instock/api/custom_indicator/delete", customIndicatorHandler.DeleteCustomIndicatorHandler),
            (r"/instock/api/custom_indicator/backtest", customIndicatorHandler.BacktestCustomIndicatorHandler),
            (r"/instock/api/custom_indicator/watchlist", customIndicatorHandler.WatchlistTodayHandler),
            (r"/instock/api/custom_indicator/series", customIndicatorHandler.IndicatorSeriesHandler),
            # ── Vue SPA 路由 ──
            # 静态资源（assets/）
            (r"/assets/(.*)", tornado.web.StaticFileHandler, {"path": os.path.join(static_path, "assets")}),
            # 所有非 API 路径 fallback 到 Vue SPA 的 index.html（支持前端路由）
            (r"/(.*)", SPAHandler, {"static_path": static_path}),
        ]
        settings = dict(  # 配置
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=static_path,
            xsrf_cookies=False,  # True,
            # cookie加密
            cookie_secret="027bb1b670eddf0392cdda8709268a17b58b7",
            debug=False,
        )
        super(Application, self).__init__(handlers, **settings)
        # Have one global connection to the blog DB across all handlers
        try:
            self.db = torndb.Connection(**mdb.MYSQL_CONN_TORNDB)
        except Exception as e:
            logging.warning(f"数据库连接失败，部分功能不可用: {e}")
            self.db = None


class SPAHandler(tornado.web.RequestHandler, ABC):
    """Vue SPA 的 fallback handler：所有非 API 路径都返回 index.html"""

    def initialize(self, static_path):
        self.spa_path = static_path

    @gen.coroutine
    def get(self, path=""):
        # 如果请求的是一个实际存在的静态文件，直接返回
        full_path = os.path.join(self.spa_path, path)
        # 安全检查：防止路径遍历攻击（如 ../../etc/passwd）
        real_spa = os.path.realpath(self.spa_path)
        real_full = os.path.realpath(full_path)
        if not real_full.startswith(real_spa + os.sep) and real_full != real_spa:
            self.set_status(403)
            self.write("Forbidden")
            return
        if path and os.path.isfile(full_path):
            # 根据扩展名设置 Content-Type
            import mimetypes
            content_type, _ = mimetypes.guess_type(full_path)
            if content_type:
                self.set_header("Content-Type", content_type)
            with open(full_path, "rb") as f:
                self.write(f.read())
            return
        # 否则返回 Vue SPA 的 index.html（前端路由处理）
        index_path = os.path.join(self.spa_path, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            self.write(f.read())


def _sync_strategy_templates_in_background():
    try:
        sync_result = portfolioBacktestHandler.sync_strategy_templates_to_db()
        logging.info(f"内置策略模板已同步: {sync_result}")
    except Exception as e:
        logging.warning(f"内置策略模板同步失败（不影响 Web 服务启动）: {e}", exc_info=True)


def main():
    # tornado.options.parse_command_line()
    tornado.options.options.logging = None

    http_server = tornado.httpserver.HTTPServer(Application())
    port = _cfg.get_int('INSTOCK_WEB_PORT', 9988)
    http_server.listen(port)

    logging.info(f"服务已启动，web地址 : http://localhost:{port}/")
    print(f"服务已启动，web地址 : http://localhost:{port}/")  # 控制台通知运维人员

    threading.Thread(target=_sync_strategy_templates_in_background, name="strategy-template-sync", daemon=True).start()

    # Phase 9: 自定义综合指标 — 启动时确保表存在 + seed 内置预设
    try:
        customIndicatorHandler.bootstrap()
    except Exception as e:
        logging.warning(f"自定义指标 bootstrap 失败（不影响其他功能）: {e}")

    # 启动模拟交易自动调度器（每个交易日收盘后自动执行）
    try:
        from instock.paper_trading.scheduler import PaperTradingScheduler
        _paper_scheduler = PaperTradingScheduler()
        _paper_scheduler.start()
    except Exception as e:
        logging.warning(f"模拟交易调度器启动失败（不影响其他功能）: {e}")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
