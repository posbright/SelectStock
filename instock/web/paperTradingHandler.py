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

            with mdb.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'INSERT INTO cn_stock_paper_trading '
                        '(strategy_id, name, initial_cash, current_cash, current_value, status) '
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (strategy_id, name or f'模拟盘-{strategy_id}', initial_cash,
                         initial_cash, initial_cash, 'running'))
                    cur.execute('SELECT LAST_INSERT_ID()')
                    row = cur.fetchone()
                    paper_id = row[0] if row is not None else None

            if paper_id is None:
                self.write(json.dumps({'code': -1, 'msg': '创建模拟盘失败'}))
                return
            self.write(json.dumps({'code': 0, 'data': {'id': paper_id}}, ensure_ascii=False))
        except Exception as e:
            mdb._invalidate_shared_conn()  # 废弃可能损坏的连接
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
                # 批量获取所有模拟盘的 NAV 数据，用于计算年化收益、最大回撤、今日收益
                paper_ids = [r[0] for r in rows]
                nav_map = {}  # paper_id -> [(date, total_value), ...]
                if mdb.checkTableIsExist('cn_stock_paper_nav') and paper_ids:
                    placeholders = ','.join(['%s'] * len(paper_ids))
                    nav_rows = mdb.executeSqlFetch(
                        f'SELECT paper_id, date, total_value '
                        f'FROM cn_stock_paper_nav '
                        f'WHERE paper_id IN ({placeholders}) '
                        f'ORDER BY paper_id, date ASC', tuple(paper_ids))
                    if nav_rows:
                        for nr in nav_rows:
                            nav_map.setdefault(nr[0], []).append((nr[1], float(nr[2]) if nr[2] else 0))

                for r in rows:
                    initial = float(r[3]) if r[3] else 1000000
                    current = float(r[5]) if r[5] else initial
                    profit_rate = (current / initial - 1) * 100 if initial > 0 else 0

                    # 从 NAV 序列计算年化收益、最大回撤、今日收益
                    annual_return = 0
                    max_drawdown = 0
                    today_return = 0
                    nav_list = nav_map.get(r[0], [])
                    if len(nav_list) >= 2:
                        first_val = nav_list[0][1]
                        last_val = nav_list[-1][1]
                        first_date = nav_list[0][0]
                        last_date = nav_list[-1][0]
                        days = (last_date - first_date).days if hasattr(first_date, '__sub__') else 0

                        # 年化收益
                        if days > 0 and first_val > 0:
                            ann_factor = 365.0 / days
                            annual_return = round(((last_val / first_val) ** ann_factor - 1) * 100, 2)

                        # 最大回撤
                        peak = nav_list[0][1]
                        for _, v in nav_list:
                            if v > peak:
                                peak = v
                            dd = (peak - v) / peak * 100 if peak > 0 else 0
                            if dd > max_drawdown:
                                max_drawdown = dd
                        max_drawdown = round(max_drawdown, 2)

                        # 今日收益（最近两个 NAV 的变化率）
                        prev_val = nav_list[-2][1]
                        if prev_val > 0:
                            today_return = round((last_val / prev_val - 1) * 100, 2)

                    data.append({
                        'id': r[0],
                        'strategy_name': r[1] or '未知策略',
                        'name': r[2] or f'模拟盘-{r[0]}',
                        'initial_cash': initial,
                        'current_cash': float(r[4]) if r[4] else initial,
                        'current_value': current,
                        'profit_rate': round(profit_rate, 2),
                        'annual_return': annual_return,
                        'max_drawdown': max_drawdown,
                        'today_return': today_return,
                        'status': r[6],
                        'started_at': r[7].strftime('%Y-%m-%d') if r[7] else '',
                        'last_run_date': str(r[8]) if r[8] else '未运行',
                    })
            self.write(json.dumps({'code': 0, 'data': data}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


def _compute_paper_metrics(nav_rows, trade_rows):
    """
    从 NAV 序列和交易记录计算模拟盘绩效指标。

    Args:
        nav_rows: [(date, total_value, cash, position_value), ...]  按日期升序
        trade_rows: [(date, code, direction, price, amount, value, commission, tax), ...] 或
                    [(date, code, name, direction, price, amount, value, commission, tax), ...]

    Returns:
        dict 绩效指标
    """
    metrics = {
        'total_return': 0, 'annual_return': 0, 'max_drawdown': 0,
        'sharpe_ratio': 0, 'sortino_ratio': 0, 'win_rate': 0,
        'profit_loss_ratio': 0, 'trade_count': 0, 'running_days': 0,
        'today_return': 0,
    }

    if not nav_rows or len(nav_rows) < 2:
        return metrics

    values = [float(r[1]) for r in nav_rows]
    initial = values[0]
    final = values[-1]
    metrics['total_return'] = round((final / initial - 1) * 100, 2) if initial > 0 else 0

    first_date = nav_rows[0][0]
    last_date = nav_rows[-1][0]
    days = (last_date - first_date).days if hasattr(first_date, '__sub__') else 0
    metrics['running_days'] = days
    if days > 0 and initial > 0:
        ann_factor = 365.0 / days
        metrics['annual_return'] = round(((final / initial) ** ann_factor - 1) * 100, 2)

    # 最大回撤
    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    metrics['max_drawdown'] = round(max_dd, 2)

    # 今日收益（最近两个 NAV 的变化率）
    prev_val = values[-2]
    if prev_val > 0:
        metrics['today_return'] = round((final / prev_val - 1) * 100, 2)

    # 日收益率
    daily_returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            daily_returns.append(values[i] / values[i - 1] - 1)

    # 夏普比率
    if len(daily_returns) >= 5:
        rf_daily = 0.03 / 252
        mean_r = sum(daily_returns) / len(daily_returns)
        std_r = (sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        if std_r > 0:
            metrics['sharpe_ratio'] = round((mean_r - rf_daily) / std_r * (252 ** 0.5), 2)
        downside = [r for r in daily_returns if r < rf_daily]
        if len(downside) >= 2:
            down_std = (sum((r - rf_daily) ** 2 for r in downside) / len(downside)) ** 0.5
            if down_std > 0:
                metrics['sortino_ratio'] = round((mean_r - rf_daily) / down_std * (252 ** 0.5), 2)

    # 胜率 & 盈亏比
    if trade_rows:
        metrics['trade_count'] = len(trade_rows)
        buys = {}
        wins = 0
        losses = 0
        total_profit = 0
        total_loss = 0
        for t in trade_rows:
            # 兼容两种元组格式
            if len(t) >= 9:
                code, direction, price, amount = t[1], t[3], float(t[4]), int(t[5])
            else:
                code, direction, price, amount = t[1], t[2], float(t[3]), int(t[4])
            if direction == 'buy':
                buys.setdefault(code, []).append((price, amount))
            elif direction == 'sell' and code in buys and buys[code]:
                buy_price = buys[code][0][0]
                pnl = (price - buy_price) * amount
                if pnl >= 0:
                    wins += 1
                    total_profit += pnl
                else:
                    losses += 1
                    total_loss += abs(pnl)
                buys[code].pop(0)
        total_trades = wins + losses
        if total_trades > 0:
            metrics['win_rate'] = round(wins / total_trades * 100, 1)
        if losses > 0 and total_loss > 0:
            avg_win = total_profit / wins if wins > 0 else 0
            avg_loss = total_loss / losses
            metrics['profit_loss_ratio'] = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

    return metrics


class GetPaperTradingDetailHandler(webBase.BaseHandler, ABC):
    """获取模拟盘详情（含持仓、交易、NAV 曲线和绩效指标）"""

    @gen.coroutine
    def get(self):
        try:
            paper_id = self.get_argument('id', None)
            pos_date = self.get_argument('pos_date', None)
            if not paper_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 id'}))
                return

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

            # 当前持仓（支持按日期查询历史持仓）
            positions = []
            if mdb.checkTableIsExist('cn_stock_backtest_position'):
                if pos_date:
                    pos_rows = mdb.executeSqlFetch(
                        'SELECT code, name, amount, avg_cost, close_price, '
                        'market_value, profit, profit_rate, weight '
                        'FROM cn_stock_backtest_position '
                        'WHERE paper_id = %s AND date = %s '
                        'ORDER BY market_value DESC', (paper_id, pos_date))
                else:
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
                            'weight': round(float(p[8]), 2) if p[8] else 0,
                        })

            # 最近交易
            trades = []
            trade_rows_raw = []
            if mdb.checkTableIsExist('cn_stock_backtest_trade'):
                trade_rows_raw = mdb.executeSqlFetch(
                    'SELECT date, code, name, direction, price, amount, value, commission, tax '
                    'FROM cn_stock_backtest_trade '
                    'WHERE paper_id = %s ORDER BY date DESC, id DESC LIMIT 200',
                    (paper_id,))
                if trade_rows_raw:
                    for t in trade_rows_raw:
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

            # NAV 曲线
            nav = []
            nav_rows_raw = []
            if mdb.checkTableIsExist('cn_stock_paper_nav'):
                nav_rows_raw = mdb.executeSqlFetch(
                    'SELECT date, total_value, cash, position_value '
                    'FROM cn_stock_paper_nav '
                    'WHERE paper_id = %s ORDER BY date ASC', (paper_id,))
                if nav_rows_raw:
                    for n in nav_rows_raw:
                        nav.append({
                            'date': str(n[0]) if n[0] else '',
                            'total_value': float(n[1]) if n[1] else 0,
                            'cash': float(n[2]) if n[2] else 0,
                            'position_value': float(n[3]) if n[3] else 0,
                        })

            # 绩效指标
            metrics = _compute_paper_metrics(nav_rows_raw, trade_rows_raw)
            info.update(metrics)

            self.write(json.dumps({
                'code': 0,
                'data': {'info': info, 'positions': positions, 'trades': trades, 'nav': nav}
            }, ensure_ascii=False))
        except Exception as e:
            logging.error("GetPaperTradingDetail异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class DeletePaperTradingHandler(webBase.BaseHandler, ABC):
    """删除模拟盘及其关联数据"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body)
            paper_id = body.get('id')
            if not paper_id:
                self.write(json.dumps({'code': -1, 'msg': '缺少 id'}))
                return

            with mdb.get_connection() as conn:
                with conn.cursor() as cur:
                    if mdb.checkTableIsExist('cn_stock_paper_nav'):
                        cur.execute('DELETE FROM cn_stock_paper_nav WHERE paper_id=%s', (paper_id,))
                    if mdb.checkTableIsExist('cn_stock_backtest_position'):
                        cur.execute('DELETE FROM cn_stock_backtest_position WHERE paper_id=%s', (paper_id,))
                    if mdb.checkTableIsExist('cn_stock_backtest_trade'):
                        cur.execute('DELETE FROM cn_stock_backtest_trade WHERE paper_id=%s', (paper_id,))
                    cur.execute('DELETE FROM cn_stock_paper_trading WHERE id=%s', (paper_id,))
                conn.commit()

            self.write(json.dumps({'code': 0}))
        except Exception as e:
            logging.error("DeletePaperTrading异常", exc_info=True)
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

            started_at = datetime.datetime.now()
            from instock.paper_trading.paper_engine import run_paper_trading_daily
            result = run_paper_trading_daily(paper_id)

            # 记录执行日志
            try:
                from instock.paper_trading.scheduler import PaperTradingScheduler
                import instock.lib.trade_time as trd
                _, run_date_nph = trd.get_trade_date_last()
                PaperTradingScheduler._save_execution_log(
                    paper_id, run_date_nph, started_at,
                    result.get('status', 'unknown'),
                    result.get('message', ''),
                    trades=result.get('trades', 0),
                    total_value=result.get('total_value'))
            except Exception:
                logging.warning("记录手动执行日志失败", exc_info=True)

            self.write(json.dumps({'code': 0, 'data': result}, ensure_ascii=False, default=str))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPaperExecutionLogHandler(webBase.BaseHandler, ABC):
    """查询模拟盘执行日志"""

    @gen.coroutine
    def get(self):
        try:
            paper_id = self.get_argument('id', None)
            limit = int(self.get_argument('limit', '50'))
            limit = min(limit, 200)

            from instock.paper_trading.scheduler import _ensure_execution_log_table
            _ensure_execution_log_table()

            if paper_id:
                rows = mdb.executeSqlFetch(
                    'SELECT id, paper_id, trade_date, status, message, '
                    'trade_count, total_value, started_at, finished_at '
                    'FROM cn_stock_paper_execution_log '
                    'WHERE paper_id = %s ORDER BY trade_date DESC, id DESC '
                    'LIMIT %s', (paper_id, limit))
            else:
                rows = mdb.executeSqlFetch(
                    'SELECT id, paper_id, trade_date, status, message, '
                    'trade_count, total_value, started_at, finished_at '
                    'FROM cn_stock_paper_execution_log '
                    'ORDER BY trade_date DESC, id DESC LIMIT %s', (limit,))

            data = []
            if rows:
                for r in rows:
                    data.append({
                        'id': r[0],
                        'paper_id': r[1],
                        'trade_date': str(r[2]) if r[2] else '',
                        'status': r[3],
                        'message': r[4] or '',
                        'trade_count': r[5] or 0,
                        'total_value': float(r[6]) if r[6] else None,
                        'started_at': r[7].strftime('%Y-%m-%d %H:%M:%S') if r[7] else '',
                        'finished_at': r[8].strftime('%Y-%m-%d %H:%M:%S') if r[8] else '',
                    })

            self.write(json.dumps({'code': 0, 'data': data}, ensure_ascii=False))
        except Exception as e:
            self.write(json.dumps({'code': -1, 'msg': str(e)}))


class GetPaperCompareHandler(webBase.BaseHandler, ABC):
    """模拟盘多策略对比：NAV 曲线 + 绩效指标"""

    @gen.coroutine
    def get(self):
        try:
            ids_str = self.get_argument('ids', '')
            if not ids_str:
                self.write(json.dumps({'code': -1, 'msg': '缺少 ids 参数'}))
                return

            paper_ids = []
            for s in ids_str.split(','):
                s = s.strip()
                if s.isdigit():
                    paper_ids.append(int(s))
            if len(paper_ids) < 1 or len(paper_ids) > 10:
                self.write(json.dumps({'code': -1, 'msg': 'ids 数量需在 1-10 之间'}))
                return

            from instock.paper_trading.paper_engine import _ensure_paper_table, _ensure_nav_table
            _ensure_paper_table()
            _ensure_nav_table()

            placeholders = ','.join(['%s'] * len(paper_ids))

            info_rows = mdb.executeSqlFetch(
                f'SELECT pt.id, sc.name as strategy_name, pt.name, '
                f'pt.initial_cash, pt.current_value, pt.status, pt.started_at, pt.last_run_date '
                f'FROM cn_stock_paper_trading pt '
                f'LEFT JOIN cn_stock_strategy_code sc ON pt.strategy_id = sc.id '
                f'WHERE pt.id IN ({placeholders})', tuple(paper_ids))

            papers = {}
            if info_rows:
                for r in info_rows:
                    pid = r[0]
                    initial = float(r[3]) if r[3] else 1000000
                    current = float(r[4]) if r[4] else initial
                    papers[pid] = {
                        'id': pid,
                        'strategy_name': r[1] or '未知',
                        'name': r[2] or f'模拟盘-{pid}',
                        'initial_cash': initial,
                        'current_value': current,
                        'profit_rate': round((current / initial - 1) * 100, 2) if initial > 0 else 0,
                        'status': r[5],
                        'started_at': r[6].strftime('%Y-%m-%d') if r[6] else '',
                        'last_run_date': str(r[7]) if r[7] else '',
                        'nav': [],
                        'metrics': {},
                    }

            # NAV 曲线 + 绩效指标
            nav_by_paper = {}
            if mdb.checkTableIsExist('cn_stock_paper_nav'):
                nav_rows = mdb.executeSqlFetch(
                    f'SELECT paper_id, date, total_value, cash, position_value '
                    f'FROM cn_stock_paper_nav WHERE paper_id IN ({placeholders}) '
                    f'ORDER BY paper_id, date ASC', tuple(paper_ids))
                if nav_rows:
                    for n in nav_rows:
                        pid = n[0]
                        nav_by_paper.setdefault(pid, []).append(n[1:])
                        if pid in papers:
                            papers[pid]['nav'].append({
                                'date': str(n[1]),
                                'total_value': float(n[2]) if n[2] else 0,
                            })

            trade_by_paper = {}
            if mdb.checkTableIsExist('cn_stock_backtest_trade'):
                trade_rows = mdb.executeSqlFetch(
                    f'SELECT paper_id, date, code, direction, price, amount, value, commission, tax '
                    f'FROM cn_stock_backtest_trade WHERE paper_id IN ({placeholders}) '
                    f'ORDER BY paper_id, date ASC', tuple(paper_ids))
                if trade_rows:
                    for t in trade_rows:
                        trade_by_paper.setdefault(t[0], []).append(t[1:])

            for pid in paper_ids:
                if pid in papers:
                    papers[pid]['metrics'] = _compute_paper_metrics(
                        nav_by_paper.get(pid, []),
                        trade_by_paper.get(pid, []))

            result = [papers[pid] for pid in paper_ids if pid in papers]
            self.write(json.dumps({'code': 0, 'data': result}, ensure_ascii=False))
        except Exception as e:
            logging.error("GetPaperCompare异常", exc_info=True)
            self.write(json.dumps({'code': -1, 'msg': str(e)}))
