#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟交易 API Handler

提供模拟盘的创建、暂停、恢复、停止、状态查询等 API。
"""

import json
import logging
import datetime
from abc import ABC
from tornado import gen
import instock.web.base as webBase
import instock.lib.database as mdb

__author__ = 'InStock'
__date__ = '2026/03/13'


class CreatePaperTradingHandler(webBase.BaseHandler, ABC):
    """创建模拟盘"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            strategy_id = body.get('strategy_id')
            name = body.get('name', '')
            initial_cash = body.get('initial_cash', 1000000)

            if not strategy_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 strategy_id'}))
                return

            from instock.paper_trading.paper_engine import _ensure_paper_table
            _ensure_paper_table()

            mdb.executeSql(
                'INSERT INTO cn_stock_paper_trading '
                '(strategy_id, name, initial_cash, current_cash, current_value, status) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (strategy_id, name or f'模拟盘-{strategy_id}', initial_cash,
                 initial_cash, initial_cash, 'running'))

            row = mdb.executeSqlFetch('SELECT LAST_INSERT_ID()')
            paper_id = row[0][0] if row else None

            self.write(json.dumps({'code': 0, 'data': {'id': paper_id}}, ensure_ascii=False))
        except Exception as e:
            logging.error("CreatePaperTrading异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class PaperTradingActionHandler(webBase.BaseHandler, ABC):
    """暂停/恢复/停止模拟盘"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            paper_id = body.get('id')
            action = body.get('action')  # pause / resume / stop

            if not paper_id or action not in ('pause', 'resume', 'stop'):
                self.write(json.dumps({'code': -1, 'msg': '参数错误'}))
                return

            status_map = {'pause': 'paused', 'resume': 'running', 'stop': 'stopped'}
            new_status = status_map[action]

            mdb.executeSql(
                'UPDATE cn_stock_paper_trading SET status=%s WHERE id=%s',
                (new_status, paper_id))

            self.write(json.dumps({'code': 0}))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPaperTradingListHandler(webBase.BaseHandler, ABC):
    """获取模拟盘列表"""

    @gen.coroutine
    def get(self):
        try:
            from instock.paper_trading.paper_engine import _ensure_paper_table
            _ensure_paper_table()

            rows = mdb.executeSqlFetch(
                'SELECT pt.id, sc.name as strategy_name, pt.name, '
                'pt.initial_cash, pt.current_cash, pt.current_value, '
                'pt.status, pt.started_at, pt.last_run_date '
                'FROM cn_stock_paper_trading pt '
                'LEFT JOIN cn_stock_strategy_code sc ON pt.strategy_id = sc.id '
                'ORDER BY pt.id DESC LIMIT 50')

            data = []
            if rows:
                for r in rows:
                    initial = float(r[3]) if r[3] else 1000000
                    current = float(r[5]) if r[5] else initial
                    profit_rate = (current / initial - 1) * 100 if initial > 0 else 0
                    data.append({
                        'id': r[0],
                        'strategy_name': r[1] or '未知策略',
                        'name': r[2] or f'模拟盘-{r[0]}',
                        'initial_cash': initial,
                        'current_cash': float(r[4]) if r[4] else initial,
                        'current_value': current,
                        'profit_rate': round(profit_rate, 2),
                        'status': r[6],
                        'started_at': r[7].strftime('%Y-%m-%d') if r[7] else '',
                        'last_run_date': str(r[8]) if r[8] else '未运行',
                    })
            self.write(json.dumps({'code': 0, 'data': data}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPaperTradingDetailHandler(webBase.BaseHandler, ABC):
    """获取模拟盘详情（含持仓和最近交易）"""

    @gen.coroutine
    def get(self):
        try:
            paper_id = self.get_argument('id', None)
            if not paper_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 id'}))
                return

            # 基本信息
            rows = mdb.executeSqlFetch(
                'SELECT pt.id, sc.name, pt.name, pt.initial_cash, '
                'pt.current_cash, pt.current_value, pt.status, '
                'pt.started_at, pt.last_run_date '
                'FROM cn_stock_paper_trading pt '
                'LEFT JOIN cn_stock_strategy_code sc ON pt.strategy_id = sc.id '
                'WHERE pt.id = %s', (paper_id,))

            if not rows:
                self.write(json.dumps({'code': -1, 'msg': '模拟盘不存在'}))
                return

            r = rows[0]
            initial = float(r[3]) if r[3] else 1000000
            current = float(r[5]) if r[5] else initial

            info = {
                'id': r[0],
                'strategy_name': r[1] or '未知',
                'name': r[2],
                'initial_cash': initial,
                'current_cash': float(r[4]) if r[4] else initial,
                'current_value': current,
                'profit_rate': round((current / initial - 1) * 100, 2) if initial > 0 else 0,
                'status': r[6],
                'started_at': r[7].strftime('%Y-%m-%d') if r[7] else '',
                'last_run_date': str(r[8]) if r[8] else '',
            }

            # 当前持仓（最近日期的快照）
            positions = []
            if mdb.checkTableIsExist('cn_stock_backtest_position'):
                pos_rows = mdb.executeSqlFetch(
                    'SELECT code, name, amount, avg_cost, close_price, '
                    'market_value, profit, profit_rate, weight '
                    'FROM cn_stock_backtest_position '
                    'WHERE paper_id = %s AND date = ('
                    '  SELECT MAX(date) FROM cn_stock_backtest_position WHERE paper_id = %s'
                    ') ORDER BY market_value DESC', (paper_id, paper_id))
                if pos_rows:
                    for p in pos_rows:
                        positions.append({
                            'code': p[0], 'name': p[1] or '',
                            'amount': p[2],
                            'avg_cost': float(p[3]) if p[3] else 0,
                            'price': float(p[4]) if p[4] else 0,
                            'value': float(p[5]) if p[5] else 0,
                            'profit': float(p[6]) if p[6] else 0,
                            'profit_rate': round(float(p[7]) * 100, 2) if p[7] else 0,
                            'weight': round(float(p[8]) * 100, 2) if p[8] else 0,
                        })

            # 最近交易
            trades = []
            if mdb.checkTableIsExist('cn_stock_backtest_trade'):
                trade_rows = mdb.executeSqlFetch(
                    'SELECT date, code, name, direction, price, amount, value, commission, tax '
                    'FROM cn_stock_backtest_trade '
                    'WHERE paper_id = %s ORDER BY date DESC, id DESC LIMIT 100',
                    (paper_id,))
                if trade_rows:
                    for t in trade_rows:
                        trades.append({
                            'date': str(t[0]) if t[0] else '',
                            'code': t[1], 'name': t[2] or '',
                            'direction': t[3],
                            'price': float(t[4]) if t[4] else 0,
                            'amount': t[5],
                            'value': float(t[6]) if t[6] else 0,
                            'commission': float(t[7]) if t[7] else 0,
                            'tax': float(t[8]) if t[8] else 0,
                        })

            self.write(json.dumps({
                'code': 0,
                'data': {'info': info, 'positions': positions, 'trades': trades}
            }, ensure_ascii=False))
        except Exception as e:
            logging.error("GetPaperTradingDetail异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class RunPaperTradingHandler(webBase.BaseHandler, ABC):
    """手动触发模拟盘执行（测试用）"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            paper_id = body.get('id')
            if not paper_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 id'}))
                return

            from instock.paper_trading.paper_engine import run_paper_trading_daily
            result = run_paper_trading_daily(paper_id)
            self.write(json.dumps({'code': 0, 'data': result}, ensure_ascii=False, default=str))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))
