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
        'id': 'ma_breakout',
        'name': '均线突破策略',
        'description': '价格突破5日均线1%时买入，跌破时卖出',
        'code': '''def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    code = context.security
    price = data[code].close
    if price <= 0:
        return
    ma5 = history(code, 5, 'close')
    if len(ma5) < 5:
        return
    ma_val = ma5.mean()

    if price > ma_val * 1.01 and code not in context.portfolio.positions:
        order_value(code, context.portfolio.available_cash * 0.9)
        log.info(f"买入 {code} @ {price:.2f}")
    elif price < ma_val * 0.99 and code in context.portfolio.positions:
        order_target(code, 0)
        log.info(f"卖出 {code} @ {price:.2f}")
''',
    },
    {
        'id': 'dual_ma',
        'name': '双均线策略',
        'description': '5日均线上穿20日均线（金叉）买入，下穿（死叉）卖出',
        'code': '''def initialize(context):
    context.security = '600519'

def handle_data(context, data):
    code = context.security
    ma5 = history(code, 5, 'close')
    ma20 = history(code, 20, 'close')
    if len(ma5) < 5 or len(ma20) < 20:
        return

    if ma5.mean() > ma20.mean():
        if code not in context.portfolio.positions:
            order_value(code, context.portfolio.available_cash * 0.9)
            log.info(f"金叉买入 {code}")
    else:
        if code in context.portfolio.positions:
            order_target(code, 0)
            log.info(f"死叉卖出 {code}")
''',
    },
    {
        'id': 'equal_weight',
        'name': '多股票等权配置',
        'description': '将资金等分配置到多只股票，每日再平衡',
        'code': '''def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750']
    context.rebalance_days = 0

def handle_data(context, data):
    context.rebalance_days += 1
    if context.rebalance_days % 20 != 1:  # 每20个交易日调仓一次
        return

    target = context.portfolio.total_value / len(context.stocks)
    for code in context.stocks:
        if code in data:
            order_target_value(code, target)
    log.info(f"调仓: 目标每只 {target:.0f} 元")
''',
    },
    {
        'id': 'momentum',
        'name': '动量策略',
        'description': '买入近20日涨幅最大的股票，持有20日后换仓',
        'code': '''def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750',
                      '000001', '600000', '601888', '002594', '300059']
    context.hold_days = 0

def handle_data(context, data):
    context.hold_days += 1
    if context.hold_days % 20 != 1:
        return

    # 计算各股票20日涨幅
    momentum = {}
    for code in context.stocks:
        h = history(code, 20, 'close')
        if len(h) >= 20 and h.iloc[0] > 0:
            momentum[code] = (h.iloc[-1] / h.iloc[0] - 1)

    if not momentum:
        return

    # 选涨幅最大的3只
    top3 = sorted(momentum, key=momentum.get, reverse=True)[:3]

    # 卖出不在top3中的持仓
    for code in list(context.portfolio.positions.keys()):
        if code not in top3:
            order_target(code, 0)

    # 等权买入top3
    target = context.portfolio.total_value / 3
    for code in top3:
        order_target_value(code, target)
    log.info(f"动量选股: {top3}")
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
                with mdb.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            'INSERT INTO cn_stock_strategy_code '
                            '(name, code, description, category, folder_id, initial_cash, '
                            'benchmark, commission_rate, stamp_tax_rate, slippage, status) '
                            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                            (name, code, description, category, folder_id, initial_cash,
                             benchmark, commission, tax, slippage, 'active'))
                        cur.execute('SELECT LAST_INSERT_ID()')
                        result_id = cur.fetchone()[0]

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
    """运行组合回测"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_code = body.get('code', '')
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
            result = run_backtest(
                strategy_code, start_date, end_date,
                initial_cash=initial_cash, benchmark=benchmark,
                commission=commission, tax=tax, slippage=slippage)

            self.write(json.dumps({'code': 0, 'data': result}, ensure_ascii=False, default=str))
        except Exception as e:
            logging.error("RunPortfolioBacktest异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPortfolioBacktestListHandler(webBase.BaseHandler, ABC):
    """获取历史回测任务列表"""

    @gen.coroutine
    def get(self):
        try:
            _ensure_backtest_table()
            rows = mdb.executeSqlFetch(
                'SELECT bp.id, sc.name as strategy_name, bp.start_date, bp.end_date, '
                'bp.initial_cash, bp.status, bp.total_return, bp.max_drawdown, '
                'bp.sharpe_ratio, bp.trade_count, bp.completed_at '
                'FROM cn_stock_backtest_portfolio bp '
                'LEFT JOIN cn_stock_strategy_code sc ON bp.strategy_id = sc.id '
                'ORDER BY bp.id DESC LIMIT 50')
            data = []
            if rows:
                for r in rows:
                    data.append({
                        'id': r[0],
                        'strategy_name': r[1] or '临时策略',
                        'start_date': str(r[2]) if r[2] else '',
                        'end_date': str(r[3]) if r[3] else '',
                        'initial_cash': float(r[4]) if r[4] else 0,
                        'status': r[5],
                        'total_return': float(r[6]) if r[6] else 0,
                        'max_drawdown': float(r[7]) if r[7] else 0,
                        'sharpe_ratio': float(r[8]) if r[8] else 0,
                        'trade_count': r[9] or 0,
                        'completed_at': r[10].strftime('%Y-%m-%d %H:%M') if r[10] else '',
                    })
            self.write(json.dumps({'code': 0, 'data': data}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


# ── 辅助函数 ──

def _ensure_strategy_table():
    """确保策略表存在（含 folder/category 扩展字段）"""
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
        # 增量添加新字段（兼容已有表，MySQL 8.0 不支持 IF NOT EXISTS）
        def _add_col(col_def):
            try:
                mdb.executeSql(f'ALTER TABLE cn_stock_strategy_code ADD COLUMN {col_def}')
            except Exception:
                pass  # 列已存在时忽略 (1060 Duplicate column)
        _add_col('`category` VARCHAR(30) DEFAULT "stock" AFTER `description`')
        _add_col('`folder_id` INT DEFAULT 0 AFTER `category`')
        _add_col('`compile_count` INT DEFAULT 0 AFTER `slippage`')
        _add_col('`backtest_count` INT DEFAULT 0 AFTER `compile_count`')

    # 确保文件夹表存在
    if not mdb.checkTableIsExist('cn_stock_strategy_folder'):
        mdb.executeSql('''
            CREATE TABLE IF NOT EXISTS `cn_stock_strategy_folder` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `name` VARCHAR(100) NOT NULL,
                `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')


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
            with mdb.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO cn_stock_strategy_folder (name) VALUES (%s)', (name,))
                    cur.execute('SELECT LAST_INSERT_ID()')
                    folder_id = cur.fetchone()[0]
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


def _ensure_backtest_table():
    """确保回测任务表存在"""
    if mdb.checkTableIsExist('cn_stock_backtest_portfolio'):
        return
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
            INDEX `idx_strategy` (`strategy_id`),
            INDEX `idx_status` (`status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')
