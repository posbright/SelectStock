#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组合回测 & 策略管理 API Handler

提供策略代码 CRUD、组合回测运行、回测结果查询等 API。
"""

import json
import logging
import datetime
import traceback
from abc import ABC
from tornado import gen
import instock.web.base as webBase
import instock.lib.database as mdb

__author__ = 'InStock'
__date__ = '2026/03/13'

# ── 内置策略模板 ──
STRATEGY_TEMPLATES = [
    {
        'id': 'small_cap',
        'name': '小市值策略',
        'category': 'stock',
        'description': '每月初选出市值最小的5只股票等权买入，月末调仓',
        'code': '''# 小市值策略
# 思路：长期来看小市值股票超额收益显著
# 每月初调仓：卖出持仓，买入市值最小的N只

def initialize(context):
    # 候选股票池
    context.stocks = ['000001', '000002', '600000', '600036', '601318',
                      '600519', '000858', '002594', '300750', '601888',
                      '000568', '002304', '603259', '601012', '300059']
    context.hold_num = 5  # 持仓数量
    context.day_count = 0

def handle_data(context, data):
    context.day_count += 1
    # 每20个交易日调仓一次（约一个月）
    if context.day_count % 20 != 1:
        return

    # 获取各股票最新价格，按价格排序（模拟市值排序）
    prices = {}
    for code in context.stocks:
        if code in data and data[code].close > 0:
            prices[code] = data[code].close

    if len(prices) < context.hold_num:
        return

    # 选出价格最低的N只（模拟小市值）
    selected = sorted(prices, key=prices.get)[:context.hold_num]

    # 卖出不在选中列表中的股票
    for code in list(context.portfolio.positions.keys()):
        if code not in selected:
            order_target(code, 0)
            log.info("卖出 " + code)

    # 等权买入选中的股票
    target_value = context.portfolio.total_value / context.hold_num
    for code in selected:
        order_target_value(code, target_value)

    log.info("调仓完成，持仓: " + str(selected))
''',
    },
    {
        'id': 'dual_ma',
        'name': '双均线策略',
        'category': 'stock',
        'description': '5日均线上穿20日均线（金叉）买入，下穿（死叉）卖出',
        'code': '''# 双均线策略
# 经典技术分析策略：利用短期和长期均线的交叉信号
# 金叉（短期上穿长期）买入，死叉（短期下穿长期）卖出

def initialize(context):
    context.security = '000001'  # 平安银行

def handle_data(context, data):
    security = context.security
    # 获取收盘价
    close_data = history(security, 21, 'close')
    if len(close_data) < 21:
        return

    # 计算5日和20日均线
    MA5 = close_data[-5:].mean()
    MA20 = close_data.mean()

    # 取得当前价格和现金
    current_price = data[security].close
    cash = context.portfolio.available_cash

    # 金叉：5日均线上穿20日均线，买入
    if MA5 > MA20 and security not in context.portfolio.positions:
        order_value(security, cash * 0.95)
        log.info("金叉买入 " + security + " 价格: " + str(round(current_price, 2)))

    # 死叉：5日均线下穿20日均线，卖出
    elif MA5 < MA20 and security in context.portfolio.positions:
        order_target(security, 0)
        log.info("死叉卖出 " + security + " 价格: " + str(round(current_price, 2)))
''',
    },
    {
        'id': 'bank_rotation',
        'name': '银行股轮动策略(聚宽)',
        'category': 'stock',
        'description': '持有中证银行指数(399951)成份股中PB最低的银行股，每周一轮动',
        'code': '''# 银行股轮动策略（聚宽风格）
# 策略来源：聚宽 JoinQuant 经典银行轮动策略
# 原理：在中证银行指数(399951)成份股中选择PB最低的1只持有，每周一轮动
# 低PB银行股通常具有更高的安全边际和股息率

def initialize(context):
    set_benchmark('399951.XSHE')  # 中证银行指数
    set_option('use_real_price', True)
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    ), type='stock')
    run_weekly(check_stocks, weekday=1, time='before_open')
    run_weekly(trade, weekday=1, time='open')

def check_stocks(context):
    g.stocks = get_index_stocks('399951.XSHE')
    if len(g.stocks) > 0:
        g.df = get_fundamentals(
            query(
                valuation.code,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(g.stocks)
            ).order_by(
                valuation.pb_ratio.asc()
            )
        )
        if len(g.df) > 0:
            g.code = g.df["code"].iloc[0]
            log.info("选股: " + g.code + " PB=" + str(round(g.df["pb_ratio"].iloc[0], 3)))

def trade(context):
    if not hasattr(g, "code") or not hasattr(g, "stocks"):
        return
    if len(g.stocks) > 0:
        code = g.code
        for stock in list(context.portfolio.positions.keys()):
            if stock != code:
                order_target(stock, 0)
                log.info("轮出 " + stock)
        if len(context.portfolio.positions) > 0:
            return
        else:
            order_value(code, context.portfolio.cash)
            log.info("买入 " + code + " 金额=" + str(round(context.portfolio.cash)))
''',
    },
    {
        'id': 'equal_weight',
        'name': '多股票等权配置',
        'category': 'portfolio',
        'description': '将资金等分配置到多只股票，定期再平衡',
        'code': '''# 多股票等权配置策略
def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750']
    context.rebalance_days = 0

def handle_data(context, data):
    context.rebalance_days += 1
    if context.rebalance_days % 20 != 1:
        return
    target = context.portfolio.total_value / len(context.stocks)
    for code in context.stocks:
        if code in data:
            order_target_value(code, target)
    log.info("调仓: 目标每只 " + str(round(target)) + " 元")
''',
    },
    {
        'id': 'momentum',
        'name': '动量策略',
        'category': 'multi_factor',
        'description': '买入近20日涨幅最大的股票，持有20日后换仓',
        'code': '''# 动量策略
def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750',
                      '000001', '600000', '601888', '002594', '300059']
    context.hold_days = 0

def handle_data(context, data):
    context.hold_days += 1
    if context.hold_days % 20 != 1:
        return
    momentum = {}
    for code in context.stocks:
        h = history(code, 20, 'close')
        if len(h) >= 20 and h.iloc[0] > 0:
            momentum[code] = (h.iloc[-1] / h.iloc[0] - 1)
    if not momentum:
        return
    top3 = sorted(momentum, key=momentum.get, reverse=True)[:3]
    for code in list(context.portfolio.positions.keys()):
        if code not in top3:
            order_target(code, 0)
    target = context.portfolio.total_value / 3
    for code in top3:
        order_target_value(code, target)
    log.info("动量选股: " + str(top3))
''',
    },
    {
        'id': 'small_cap_jq',
        'name': '小市值策略(聚宽)',
        'category': 'stock',
        'description': '筛选市值介于20-30亿的股票，选取市值最小的3只，持有5个交易日后调仓（需要基本面数据支持）',
        'code': '''# 小市值策略(聚宽)
# 筛选出市值介于20-30亿的股票，选取其中市值最小的三只股票
# 每天开盘买入，持有五个交易日，然后调仓

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('order_volume_ratio', 1)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    g.stocknum = 3
    g.days = 0
    g.refresh_rate = 5
    run_daily(trade, 'every_bar')

def check_stocks(context):
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.market_cap.between(20, 30)
    ).order_by(
        valuation.market_cap.asc()
    )
    df = get_fundamentals(q)
    buylist = list(df['code'])
    buylist = filter_paused_stock(buylist)
    return buylist[:g.stocknum]

def trade(context):
    if g.days % g.refresh_rate == 0:
        sell_list = list(context.portfolio.positions.keys())
        if len(sell_list) > 0:
            for stock in sell_list:
                order_target_value(stock, 0)

        if len(context.portfolio.positions) < g.stocknum:
            Num = g.stocknum - len(context.portfolio.positions)
            Cash = context.portfolio.cash / Num
        else:
            Cash = 0

        stock_list = check_stocks(context)

        for stock in stock_list:
            if len(context.portfolio.positions.keys()) < g.stocknum:
                order_value(stock, Cash)

        g.days = 1
    else:
        g.days += 1

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]
''',
    },
]


class GetStrategyTemplatesHandler(webBase.BaseHandler, ABC):
    """获取内置策略模板列表"""

    @gen.coroutine
    def get(self):
        try:
            self.write(json.dumps({
                'code': 0,
                'data': STRATEGY_TEMPLATES
            }, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class SaveStrategyCodeHandler(webBase.BaseHandler, ABC):
    """保存/更新策略代码"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            name = body.get('name', '').strip()
            code = body.get('code', '').strip()
            description = body.get('description', '')
            strategy_id = body.get('id')
            category = body.get('category', 'stock')
            folder_id = body.get('folder_id', 0)
            initial_cash = body.get('initial_cash', 1000000)
            benchmark = body.get('benchmark', '000300')
            commission = body.get('commission_rate', 0.0003)
            tax = body.get('stamp_tax_rate', 0.001)
            slippage = body.get('slippage', 0.0005)

            if not name:
                self.write(json.dumps({'code': -1, 'msg': '策略名称不能为空'}))
                return
            if not code:
                self.write(json.dumps({'code': -1, 'msg': '策略代码不能为空'}))
                return

            # 验证代码安全性
            from instock.core.backtest.strategy_sandbox import validate_code
            ok, err = validate_code(code)
            if not ok:
                self.write(json.dumps({'code': -1, 'msg': f'代码验证失败: {err}'}, ensure_ascii=False))
                return

            _ensure_strategy_table()

            if strategy_id:
                # 更新
                mdb.executeSql(
                    'UPDATE cn_stock_strategy_code SET name=%s, code=%s, description=%s, '
                    'category=%s, initial_cash=%s, benchmark=%s, commission_rate=%s, '
                    'stamp_tax_rate=%s, slippage=%s, status=%s WHERE id=%s',
                    (name, code, description, category, initial_cash, benchmark,
                     commission, tax, slippage, 'active', strategy_id))
                result_id = strategy_id
            else:
                # 新增
                result_id = _insert_and_get_id(
                    'INSERT INTO cn_stock_strategy_code '
                    '(name, code, description, category, folder_id, initial_cash, '
                    'benchmark, commission_rate, stamp_tax_rate, slippage, status) '
                    'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (name, code, description, category, folder_id, initial_cash,
                     benchmark, commission, tax, slippage, 'active'))

            self.write(json.dumps({'code': 0, 'data': {'id': result_id}}, ensure_ascii=False))
        except Exception as e:
            logging.error("SaveStrategyCode异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetStrategyCodeListHandler(webBase.BaseHandler, ABC):
    """获取策略列表（含文件夹）"""

    @gen.coroutine
    def get(self):
        try:
            _ensure_strategy_table()
            folder_id = self.get_argument('folder_id', None)

            # 获取文件夹列表
            folders = []
            folder_rows = mdb.executeSqlFetch(
                'SELECT id, name, created_at FROM cn_stock_strategy_folder ORDER BY name')
            if folder_rows:
                for r in folder_rows:
                    folders.append({
                        'id': r[0], 'name': r[1], 'type': 'folder',
                        'created_at': r[2].strftime('%Y-%m-%d %H:%M') if r[2] else '',
                    })

            # 获取策略列表
            where = 'WHERE status != %s'
            params = ['archived']
            if folder_id is not None:
                where += ' AND folder_id = %s'
                params.append(int(folder_id))

            rows = mdb.executeSqlFetch(
                f'SELECT id, name, description, category, folder_id, initial_cash, benchmark, '
                f'compile_count, backtest_count, status, created_at, updated_at '
                f'FROM cn_stock_strategy_code {where} ORDER BY updated_at DESC', tuple(params))
            data = []
            if rows:
                for r in rows:
                    data.append({
                        'id': r[0], 'name': r[1], 'description': r[2] or '',
                        'category': r[3] or 'stock',
                        'folder_id': r[4] or 0,
                        'initial_cash': float(r[5]) if r[5] else 1000000,
                        'benchmark': r[6] or '000300',
                        'compile_count': r[7] or 0,
                        'backtest_count': r[8] or 0,
                        'status': r[9],
                        'created_at': r[10].strftime('%Y-%m-%d %H:%M:%S') if r[10] else '',
                        'updated_at': r[11].strftime('%Y-%m-%d %H:%M:%S') if r[11] else '',
                        'type': 'strategy',
                    })
            self.write(json.dumps({
                'code': 0, 'data': {'strategies': data, 'folders': folders}
            }, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetStrategyCodeDetailHandler(webBase.BaseHandler, ABC):
    """获取策略详情（含代码）"""

    @gen.coroutine
    def get(self):
        try:
            strategy_id = self.get_argument('id', None)
            if not strategy_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少参数 id'}))
                return
            _ensure_strategy_table()
            rows = mdb.executeSqlFetch(
                'SELECT id, name, code, description, initial_cash, benchmark, '
                'commission_rate, stamp_tax_rate, slippage, status '
                'FROM cn_stock_strategy_code WHERE id = %s', (strategy_id,))
            if not rows:
                self.write(json.dumps({'code': -1, 'msg': '策略不存在'}))
                return
            r = rows[0]
            self.write(json.dumps({'code': 0, 'data': {
                'id': r[0], 'name': r[1], 'code': r[2],
                'description': r[3],
                'initial_cash': float(r[4]) if r[4] else 1000000,
                'benchmark': r[5] or '000300',
                'commission_rate': float(r[6]) if r[6] else 0.0003,
                'stamp_tax_rate': float(r[7]) if r[7] else 0.001,
                'slippage': float(r[8]) if r[8] else 0.0005,
                'status': r[9],
            }}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class DeleteStrategyCodeHandler(webBase.BaseHandler, ABC):
    """删除策略（标记为 archived）"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_id = body.get('id')
            if not strategy_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少参数 id'}))
                return
            mdb.executeSql(
                'UPDATE cn_stock_strategy_code SET status=%s WHERE id=%s',
                ('archived', strategy_id))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class RunPortfolioBacktestHandler(webBase.BaseHandler, ABC):
    """运行组合回测（结果持久化到 DB）— 使用线程池避免阻塞 IOLoop"""

    # 共享线程池：限制并发回测数量，避免资源耗尽
    _executor = None

    @classmethod
    def _get_executor(cls):
        if cls._executor is None:
            from concurrent.futures import ThreadPoolExecutor
            cls._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='backtest')
        return cls._executor

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_code = body.get('code', '')
            strategy_id = body.get('strategy_id')
            start_date = body.get('start_date', '')
            end_date = body.get('end_date', '')
            initial_cash = body.get('initial_cash', 1000000)
            benchmark = body.get('benchmark', '000300')
            commission = body.get('commission_rate', 0.0003)
            tax = body.get('stamp_tax_rate', 0.001)
            slippage = body.get('slippage', 0.002)

            if not strategy_code or not start_date or not end_date:
                self.write(json.dumps({'code': -1, 'msg': '缺少必填参数'}, ensure_ascii=False))
                return

            from instock.core.backtest.portfolio_engine import run_backtest
            from tornado.ioloop import IOLoop

            # 在线程池中运行回测，不阻塞 Tornado IOLoop
            result = yield IOLoop.current().run_in_executor(
                self._get_executor(),
                lambda: run_backtest(
                    strategy_code, start_date, end_date,
                    initial_cash=initial_cash, benchmark=benchmark,
                    commission=commission, tax=tax, slippage=slippage)
            )

            # 持久化到 DB
            bt_id = None
            if result.get('status') == 'completed':
                try:
                    _ensure_backtest_table()
                    m = result.get('metrics', {})
                    now = datetime.datetime.now()
                    bt_id = _insert_and_get_id(
                        'INSERT INTO cn_stock_backtest_portfolio '
                        '(strategy_id, start_date, end_date, initial_cash, status, '
                        'started_at, completed_at, total_return, annual_return, '
                        'max_drawdown, sharpe_ratio, alpha, beta, win_rate, trade_count, '
                        'result_json) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (strategy_id, start_date, end_date, initial_cash, 'completed',
                         now, now, m.get('total_return'), m.get('annual_return'),
                         m.get('max_drawdown'), m.get('sharpe_ratio'),
                         m.get('alpha'), m.get('beta'),
                         m.get('daily_win_rate'), m.get('trade_count'),
                         json.dumps(result, ensure_ascii=False, default=str)))
                    # 更新策略的 backtest_count 和 compile_count
                    if strategy_id:
                        try:
                            mdb.executeSql(
                                'UPDATE cn_stock_strategy_code SET backtest_count=backtest_count+1, '
                                'compile_count=compile_count+1 WHERE id=%s', (strategy_id,))
                        except Exception as e:
                            logging.debug(f"backtest_count 更新异常（不影响回测结果）: strategy_id={strategy_id} - {e}")
                except Exception as e:
                    logging.warning(f"回测结果持久化异常: {e}")

            result['backtest_id'] = bt_id
            self.write(json.dumps({'code': 0, 'data': result}, ensure_ascii=False, default=str))
        except Exception as e:
            logging.error("RunPortfolioBacktest异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPortfolioBacktestListHandler(webBase.BaseHandler, ABC):
    """获取历史回测列表（支持按策略ID筛选）"""

    @gen.coroutine
    def get(self):
        try:
            _ensure_backtest_table()
            strategy_id = self.get_argument('strategy_id', None)

            where = ''
            params = []
            if strategy_id:
                where = 'WHERE bp.strategy_id = %s'
                params.append(int(strategy_id))

            rows = mdb.executeSqlFetch(
                f'SELECT bp.id, bp.strategy_id, sc.name as strategy_name, '
                f'bp.start_date, bp.end_date, bp.initial_cash, bp.status, '
                f'bp.total_return, bp.annual_return, bp.max_drawdown, '
                f'bp.sharpe_ratio, bp.alpha, bp.beta, bp.win_rate, '
                f'bp.trade_count, bp.completed_at, bp.result_json '
                f'FROM cn_stock_backtest_portfolio bp '
                f'LEFT JOIN cn_stock_strategy_code sc ON bp.strategy_id = sc.id '
                f'{where} ORDER BY bp.id DESC LIMIT 100', tuple(params) if params else None)
            data = []
            if rows:
                for r in rows:
                    # 从 result_json 提取扩展指标
                    extra_metrics = {}
                    elapsed = ''
                    if r[16]:
                        try:
                            rj = json.loads(r[16]) if isinstance(r[16], str) else r[16]
                            m = rj.get('metrics', {})
                            extra_metrics = {
                                'benchmark_return': float(m.get('benchmark_return', 0)),
                                'excess_return': float(m.get('excess_return', 0)),
                                'excess_max_drawdown': float(m.get('excess_max_drawdown', 0)),
                                'excess_sharpe_ratio': float(m.get('excess_sharpe_ratio', 0)),
                                'benchmark_annual_return': float(m.get('benchmark_annual_return', 0)),
                            }
                            elapsed = rj.get('elapsed', '')
                        except Exception as e:
                            logging.debug(f"result_json 解析异常（回测列表）: id={r[0]} - {e}")
                    item = {
                        'id': r[0],
                        'strategy_id': r[1],
                        'strategy_name': r[2] or '临时策略',
                        'start_date': str(r[3]) if r[3] else '',
                        'end_date': str(r[4]) if r[4] else '',
                        'initial_cash': float(r[5]) if r[5] else 0,
                        'status': r[6] or 'unknown',
                        'total_return': float(r[7]) if r[7] else 0,
                        'annual_return': float(r[8]) if r[8] else 0,
                        'max_drawdown': float(r[9]) if r[9] else 0,
                        'sharpe_ratio': float(r[10]) if r[10] else 0,
                        'alpha': float(r[11]) if r[11] else 0,
                        'beta': float(r[12]) if r[12] else 0,
                        'win_rate': float(r[13]) if r[13] else 0,
                        'trade_count': r[14] or 0,
                        'completed_at': r[15].strftime('%Y-%m-%d %H:%M:%S') if r[15] else '',
                        'elapsed': elapsed,
                    }
                    item.update(extra_metrics)
                    data.append(item)
            self.write(json.dumps({'code': 0, 'data': data}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPortfolioBacktestDetailHandler(webBase.BaseHandler, ABC):
    """获取回测详情（含完整的净值/交易/持仓数据）"""

    @gen.coroutine
    def get(self):
        try:
            bt_id = self.get_argument('id', None)
            if not bt_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 id'}))
                return

            _ensure_backtest_table()
            rows = mdb.executeSqlFetch(
                'SELECT bp.id, bp.strategy_id, sc.name, bp.start_date, bp.end_date, '
                'bp.initial_cash, bp.status, bp.total_return, bp.annual_return, '
                'bp.max_drawdown, bp.sharpe_ratio, bp.alpha, bp.beta, bp.win_rate, '
                'bp.trade_count, bp.completed_at, bp.result_json '
                'FROM cn_stock_backtest_portfolio bp '
                'LEFT JOIN cn_stock_strategy_code sc ON bp.strategy_id = sc.id '
                'WHERE bp.id = %s', (bt_id,))

            if not rows:
                self.write(json.dumps({'code': -1, 'msg': '回测记录不存在'}))
                return

            r = rows[0]
            info = {
                'id': r[0], 'strategy_id': r[1],
                'strategy_name': r[2] or '临时策略',
                'start_date': str(r[3]) if r[3] else '',
                'end_date': str(r[4]) if r[4] else '',
                'initial_cash': float(r[5]) if r[5] else 0,
                'status': r[6],
                'metrics': {
                    'total_return': float(r[7]) if r[7] else 0,
                    'annual_return': float(r[8]) if r[8] else 0,
                    'max_drawdown': float(r[9]) if r[9] else 0,
                    'sharpe_ratio': float(r[10]) if r[10] else 0,
                    'alpha': float(r[11]) if r[11] else 0,
                    'beta': float(r[12]) if r[12] else 0,
                    'daily_win_rate': float(r[13]) if r[13] else 0,
                    'trade_count': r[14] or 0,
                },
                'completed_at': r[15].strftime('%Y-%m-%d %H:%M:%S') if r[15] else '',
            }

            # 尝试从 result_json 恢复完整数据（净值/交易/持仓）
            result_json = r[16]
            full_data = {}
            if result_json:
                try:
                    full_data = json.loads(result_json)
                except Exception as e:
                    logging.warning(f"result_json 解析失败（回测详情）: backtest_id={r[0]} - {e}")

            # 如果 result_json 中有完整 metrics，用它覆盖（字段更全）
            if full_data.get('metrics'):
                info['metrics'] = full_data['metrics']

            info['nav'] = full_data.get('nav', [])
            info['trades'] = full_data.get('trades', [])
            info['positions'] = full_data.get('positions', [])
            info['logs'] = full_data.get('logs', [])

            self.write(json.dumps({'code': 0, 'data': info}, ensure_ascii=False, default=str))
        except Exception as e:
            logging.error("GetPortfolioBacktestDetail异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetBacktestCompareHandler(webBase.BaseHandler, ABC):
    """回测对比：接收多个回测ID，返回对比数据（指标+曲线+策略代码）"""

    @gen.coroutine
    def get(self):
        try:
            ids_str = self.get_argument('ids', '')
            if not ids_str:
                self.write(json.dumps({'code': -1, 'msg': '缺少 ids 参数'}))
                return

            bt_ids = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
            if len(bt_ids) < 2:
                self.write(json.dumps({'code': -1, 'msg': '至少选择2个回测进行对比'}))
                return
            if len(bt_ids) > 10:
                self.write(json.dumps({'code': -1, 'msg': '最多支持10个回测对比'}))
                return

            _ensure_backtest_table()
            placeholders = ','.join(['%s'] * len(bt_ids))
            rows = mdb.executeSqlFetch(
                f'SELECT bp.id, bp.strategy_id, sc.name, bp.start_date, bp.end_date, '
                f'bp.initial_cash, bp.status, bp.total_return, bp.annual_return, '
                f'bp.max_drawdown, bp.sharpe_ratio, bp.alpha, bp.beta, bp.win_rate, '
                f'bp.trade_count, bp.completed_at, bp.result_json, sc.code as strategy_code '
                f'FROM cn_stock_backtest_portfolio bp '
                f'LEFT JOIN cn_stock_strategy_code sc ON bp.strategy_id = sc.id '
                f'WHERE bp.id IN ({placeholders}) ORDER BY bp.id',
                tuple(bt_ids))

            if not rows or len(rows) < 2:
                self.write(json.dumps({'code': -1, 'msg': '回测记录不足，无法对比'}))
                return

            backtests = []
            for r in rows:
                full_data = {}
                result_json = r[16]
                if result_json:
                    try:
                        full_data = json.loads(result_json) if isinstance(result_json, str) else result_json
                    except Exception:
                        pass

                metrics = full_data.get('metrics', {})
                if not metrics:
                    metrics = {
                        'total_return': float(r[7]) if r[7] else 0,
                        'annual_return': float(r[8]) if r[8] else 0,
                        'max_drawdown': float(r[9]) if r[9] else 0,
                        'sharpe_ratio': float(r[10]) if r[10] else 0,
                        'alpha': float(r[11]) if r[11] else 0,
                        'beta': float(r[12]) if r[12] else 0,
                        'daily_win_rate': float(r[13]) if r[13] else 0,
                        'trade_count': r[14] or 0,
                    }

                bt_item = {
                    'id': r[0],
                    'strategy_id': r[1],
                    'strategy_name': r[2] or '临时策略',
                    'start_date': str(r[3]) if r[3] else '',
                    'end_date': str(r[4]) if r[4] else '',
                    'initial_cash': float(r[5]) if r[5] else 0,
                    'status': r[6] or 'unknown',
                    'metrics': metrics,
                    'nav': full_data.get('nav', []),
                    'trades': full_data.get('trades', []),
                    'strategy_code': r[17] or '',
                    'completed_at': r[15].strftime('%Y-%m-%d %H:%M:%S') if r[15] else '',
                    'params': full_data.get('params', {}),
                }
                backtests.append(bt_item)

            self.write(json.dumps({'code': 0, 'data': {'backtests': backtests}},
                                  ensure_ascii=False, default=str))
        except Exception as e:
            logging.error("GetBacktestCompare异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class DeleteBacktestHandler(webBase.BaseHandler, ABC):
    """批量删除回测记录"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            ids = body.get('ids', [])
            if not ids or not isinstance(ids, list):
                self.write(json.dumps({'code': -1, 'msg': '缺少 ids 参数'}))
                return
            # 过滤合法整数
            bt_ids = [int(x) for x in ids if isinstance(x, (int, float, str)) and str(x).strip().isdigit()]
            if not bt_ids:
                self.write(json.dumps({'code': -1, 'msg': 'ids 参数无效'}))
                return

            _ensure_backtest_table()
            placeholders = ','.join(['%s'] * len(bt_ids))
            mdb.executeSql(
                f'DELETE FROM cn_stock_backtest_portfolio WHERE id IN ({placeholders})',
                tuple(bt_ids))
            self.write(json.dumps({'code': 0, 'data': {'deleted': len(bt_ids)}}))
        except Exception as e:
            logging.error("DeleteBacktest异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPortfolioBacktestListPageHandler(webBase.BaseHandler, ABC):
    """获取历史回测列表（分页版本）"""

    @gen.coroutine
    def get(self):
        try:
            _ensure_backtest_table()
            strategy_id = self.get_argument('strategy_id', None)
            page = int(self.get_argument('page', '1'))
            page_size = int(self.get_argument('page_size', '20'))
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 200:
                page_size = 20
            offset = (page - 1) * page_size

            where = ''
            params = []
            if strategy_id:
                where = 'WHERE bp.strategy_id = %s'
                params.append(int(strategy_id))

            # 总数
            count_row = mdb.executeSqlFetch(
                f'SELECT COUNT(*) FROM cn_stock_backtest_portfolio bp {where}',
                tuple(params) if params else None)
            total = count_row[0][0] if count_row else 0

            rows = mdb.executeSqlFetch(
                f'SELECT bp.id, bp.strategy_id, sc.name as strategy_name, '
                f'bp.start_date, bp.end_date, bp.initial_cash, bp.status, '
                f'bp.total_return, bp.annual_return, bp.max_drawdown, '
                f'bp.sharpe_ratio, bp.alpha, bp.beta, bp.win_rate, '
                f'bp.trade_count, bp.completed_at, bp.result_json '
                f'FROM cn_stock_backtest_portfolio bp '
                f'LEFT JOIN cn_stock_strategy_code sc ON bp.strategy_id = sc.id '
                f'{where} ORDER BY bp.id DESC LIMIT %s OFFSET %s',
                tuple(params + [page_size, offset]) if params else (page_size, offset))
            data = []
            if rows:
                for r in rows:
                    extra_metrics = {}
                    elapsed = ''
                    if r[16]:
                        try:
                            rj = json.loads(r[16]) if isinstance(r[16], str) else r[16]
                            m = rj.get('metrics', {})
                            extra_metrics = {
                                'benchmark_return': float(m.get('benchmark_return', 0)),
                                'excess_return': float(m.get('excess_return', 0)),
                                'excess_max_drawdown': float(m.get('excess_max_drawdown', 0)),
                                'excess_sharpe_ratio': float(m.get('excess_sharpe_ratio', 0)),
                                'benchmark_annual_return': float(m.get('benchmark_annual_return', 0)),
                            }
                            elapsed = rj.get('elapsed', '')
                        except Exception as e:
                            logging.debug(f"result_json 解析异常（回测列表分页）: id={r[0]} - {e}")
                    item = {
                        'id': r[0],
                        'strategy_id': r[1],
                        'strategy_name': r[2] or '临时策略',
                        'start_date': str(r[3]) if r[3] else '',
                        'end_date': str(r[4]) if r[4] else '',
                        'initial_cash': float(r[5]) if r[5] else 0,
                        'status': r[6] or 'unknown',
                        'total_return': float(r[7]) if r[7] else 0,
                        'annual_return': float(r[8]) if r[8] else 0,
                        'max_drawdown': float(r[9]) if r[9] else 0,
                        'sharpe_ratio': float(r[10]) if r[10] else 0,
                        'alpha': float(r[11]) if r[11] else 0,
                        'beta': float(r[12]) if r[12] else 0,
                        'win_rate': float(r[13]) if r[13] else 0,
                        'trade_count': r[14] or 0,
                        'completed_at': r[15].strftime('%Y-%m-%d %H:%M:%S') if r[15] else '',
                        'elapsed': elapsed,
                    }
                    item.update(extra_metrics)
                    data.append(item)
            self.write(json.dumps({
                'code': 0,
                'data': data,
                'total': total,
                'page': page,
                'page_size': page_size,
            }, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


# ── 辅助函数 ──

def _insert_and_get_id(sql, params=()):
    """INSERT 并返回 LAST_INSERT_ID()，在同一个连接中完成。
    线程安全，带错误处理和连接失效保护。"""
    try:
        with mdb.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cur.execute('SELECT LAST_INSERT_ID()')
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("LAST_INSERT_ID() 返回 None，INSERT 可能未成功")
                return row[0]
    except Exception:
        mdb._invalidate_shared_conn()
        raise


_strategy_table_ready = False

def _ensure_strategy_table():
    """确保策略表存在（含 folder/category 扩展字段）—— 仅首次调用时执行"""
    global _strategy_table_ready
    if _strategy_table_ready:
        return
    if not mdb.checkTableIsExist('cn_stock_strategy_code'):
        mdb.executeSql('''
            CREATE TABLE IF NOT EXISTS `cn_stock_strategy_code` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `name` VARCHAR(100) NOT NULL,
                `code` TEXT NOT NULL,
                `description` TEXT,
                `category` VARCHAR(30) DEFAULT 'stock' COMMENT '分类: stock/multi_factor/portfolio/blank',
                `folder_id` INT DEFAULT 0 COMMENT '文件夹ID,0=根目录',
                `initial_cash` DECIMAL(15,2) DEFAULT 1000000.00,
                `benchmark` VARCHAR(20) DEFAULT '000300',
                `commission_rate` DECIMAL(8,6) DEFAULT 0.000300,
                `stamp_tax_rate` DECIMAL(8,6) DEFAULT 0.001000,
                `slippage` DECIMAL(8,6) DEFAULT 0.000500,
                `compile_count` INT DEFAULT 0 COMMENT '历史编译运行次数',
                `backtest_count` INT DEFAULT 0 COMMENT '历史回测次数',
                `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `status` ENUM('draft','active','archived') DEFAULT 'draft'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
    else:
        # 增量添加新字段（通过 INFORMATION_SCHEMA 检查列是否存在，避免 ALTER TABLE 报错）
        def _column_exists(table_name, column_name):
            """通过 INFORMATION_SCHEMA 检查列是否存在（MySQL 全版本兼容）"""
            try:
                with mdb.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                            (table_name, column_name)
                        )
                        return cur.fetchone() is not None
            except Exception as e:
                logging.warning(f"检查列是否存在异常：{table_name}.{column_name} - {e}")
                return True  # 出错时保守地认为列已存在，避免重复 ALTER

        def _add_col_safe(table_name, col_name, col_def):
            """安全添加列：先检查再 ALTER，避免静默异常"""
            if _column_exists(table_name, col_name):
                return  # 列已存在，无需操作
            try:
                with mdb.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f'ALTER TABLE `{table_name}` ADD COLUMN {col_def}')
                logging.info(f"成功添加列：{table_name}.{col_name}")
            except Exception as e:
                logging.warning(f"ALTER TABLE ADD COLUMN 异常：{table_name}.{col_name} - {e}")

        _add_col_safe('cn_stock_strategy_code', 'category', '`category` VARCHAR(30) DEFAULT "stock" AFTER `description`')
        _add_col_safe('cn_stock_strategy_code', 'folder_id', '`folder_id` INT DEFAULT 0 AFTER `category`')
        _add_col_safe('cn_stock_strategy_code', 'compile_count', '`compile_count` INT DEFAULT 0 AFTER `slippage`')
        _add_col_safe('cn_stock_strategy_code', 'backtest_count', '`backtest_count` INT DEFAULT 0 AFTER `compile_count`')

    # 确保文件夹表存在
    if not mdb.checkTableIsExist('cn_stock_strategy_folder'):
        mdb.executeSql('''
            CREATE TABLE IF NOT EXISTS `cn_stock_strategy_folder` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `name` VARCHAR(100) NOT NULL,
                `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
    _strategy_table_ready = True


class CreateFolderHandler(webBase.BaseHandler, ABC):
    """创建文件夹"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            name = body.get('name', '').strip()
            if not name:
                self.write(json.dumps({'code': -1, 'msg': '文件夹名称不能为空'}))
                return
            _ensure_strategy_table()
            folder_id = _insert_and_get_id(
                'INSERT INTO cn_stock_strategy_folder (name) VALUES (%s)', (name,))
            self.write(json.dumps({'code': 0, 'data': {'id': folder_id}}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class RenameFolderHandler(webBase.BaseHandler, ABC):
    """重命名文件夹"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            folder_id = body.get('id')
            name = body.get('name', '').strip()
            if not folder_id or not name:
                self.write(json.dumps({'code': -1, 'msg': '参数错误'}))
                return
            mdb.executeSql('UPDATE cn_stock_strategy_folder SET name=%s WHERE id=%s', (name, folder_id))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class DeleteFolderHandler(webBase.BaseHandler, ABC):
    """删除文件夹（策略移到根目录）"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            folder_id = body.get('id')
            if not folder_id:
                self.write(json.dumps({'code': -1, 'msg': '参数错误'}))
                return
            mdb.executeSql('UPDATE cn_stock_strategy_code SET folder_id=0 WHERE folder_id=%s', (folder_id,))
            mdb.executeSql('DELETE FROM cn_stock_strategy_folder WHERE id=%s', (folder_id,))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class MoveStrategyHandler(webBase.BaseHandler, ABC):
    """将策略移动到指定文件夹"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_ids = body.get('ids', [])
            folder_id = body.get('folder_id', 0)
            if not strategy_ids:
                self.write(json.dumps({'code': -1, 'msg': '未选择策略'}))
                return
            placeholders = ','.join(['%s'] * len(strategy_ids))
            mdb.executeSql(
                f'UPDATE cn_stock_strategy_code SET folder_id=%s WHERE id IN ({placeholders})',
                (folder_id, *strategy_ids))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class BatchDeleteStrategyHandler(webBase.BaseHandler, ABC):
    """批量删除策略"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            ids = body.get('ids', [])
            if not ids:
                self.write(json.dumps({'code': -1, 'msg': '未选择策略'}))
                return
            placeholders = ','.join(['%s'] * len(ids))
            mdb.executeSql(
                f'UPDATE cn_stock_strategy_code SET status=%s WHERE id IN ({placeholders})',
                ('archived', *ids))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class RenameStrategyHandler(webBase.BaseHandler, ABC):
    """重命名策略"""
    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_id = body.get('id')
            name = body.get('name', '').strip()
            if not strategy_id or not name:
                self.write(json.dumps({'code': -1, 'msg': '参数错误'}))
                return
            mdb.executeSql('UPDATE cn_stock_strategy_code SET name=%s WHERE id=%s', (name, strategy_id))
            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


_backtest_table_ready = False

def _ensure_backtest_table():
    """确保回测任务表存在——仅首次调用时执行"""
    global _backtest_table_ready
    if _backtest_table_ready:
        return
    if not mdb.checkTableIsExist('cn_stock_backtest_portfolio'):
        mdb.executeSql('''
            CREATE TABLE IF NOT EXISTS `cn_stock_backtest_portfolio` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `strategy_id` INT,
                `start_date` DATE,
                `end_date` DATE,
                `initial_cash` DECIMAL(15,2),
                `status` ENUM('pending','running','completed','failed') DEFAULT 'pending',
                `started_at` DATETIME,
                `completed_at` DATETIME,
                `error_message` TEXT,
                `total_return` DECIMAL(10,4),
                `annual_return` DECIMAL(10,4),
                `max_drawdown` DECIMAL(10,4),
                `sharpe_ratio` DECIMAL(10,4),
                `alpha` DECIMAL(10,4),
                `beta` DECIMAL(10,4),
                `win_rate` DECIMAL(10,4),
                `trade_count` INT,
                `result_json` LONGTEXT COMMENT '完整回测结果JSON',
                INDEX `idx_strategy` (`strategy_id`),
                INDEX `idx_status` (`status`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
    else:
        # 使用 _column_exists（在 _ensure_strategy_table 中定义）检查后再 ALTER
        try:
            _col_check_sql = (
                "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cn_stock_backtest_portfolio' "
                "AND COLUMN_NAME = 'result_json'"
            )
            with mdb.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(_col_check_sql)
                    if cur.fetchone() is None:
                        cur.execute('ALTER TABLE cn_stock_backtest_portfolio '
                                    'ADD COLUMN `result_json` LONGTEXT AFTER `trade_count`')
                        logging.info("成功添加列：cn_stock_backtest_portfolio.result_json")
        except Exception as e:
            logging.warning(f"ALTER TABLE cn_stock_backtest_portfolio 异常：{e}")
    _backtest_table_ready = True
