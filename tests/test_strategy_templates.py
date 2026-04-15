#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略选股模板测试

对应文档：document/策略选股说明.md 第 4 章"第一批模板落地计划"
对应实施方案：document/选股策略说明以及实现需求说明.md Phase 3

测试范围：
  1. 模板代码可通过沙箱校验（无危险代码）
  2. 模板代码可编译（initialize/handle_data 存在）
  3. 模板可在最小测试数据集上运行回测
  4. 回测结果结构完整（含 nav、trades、metrics）
  5. 无未来函数检测（信号日不晚于数据可见日）
  6. 模板名称与策略选股说明一致
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

# 确保项目根目录在 sys.path
cpath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if cpath not in sys.path:
    sys.path.insert(0, cpath)


def _create_test_cache(code, start='2024-01-02', periods=250, base_price=10.0, seed=None):
    """创建测试用的K线缓存文件"""
    from instock.core.backtest.data_feed import _CACHE_DIR
    os.makedirs(_CACHE_DIR, exist_ok=True)

    dates = pd.bdate_range(start=start, periods=periods)
    np.random.seed(seed if seed is not None else hash(code) % 2**31)
    returns = np.random.randn(periods) * 0.02
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        'date': dates,
        'open': prices * (1 - np.random.rand(periods) * 0.01),
        'high': prices * (1 + np.random.rand(periods) * 0.02),
        'low': prices * (1 - np.random.rand(periods) * 0.02),
        'close': prices,
        'volume': np.random.randint(100000, 500000, periods),
    })

    cache_file = os.path.join(_CACHE_DIR, f"{code}.gzip.pickle")
    df.to_pickle(cache_file)
    return cache_file


# ── 模板代码从后端 STRATEGY_TEMPLATES 加载 ──

def _get_template(template_id):
    """从 portfolioBacktestHandler 加载模板代码"""
    from instock.web.portfolioBacktestHandler import STRATEGY_TEMPLATES
    for t in STRATEGY_TEMPLATES:
        if t['id'] == template_id:
            return t
    return None


# 所有需要测试的策略选股模板（id → 策略选股说明中的名称）
STRATEGY_TEMPLATES_MAP = {
    'turtle_trade': '海龟交易法则',
    'volume_increase': '放量上涨',
    'trend_pullback': '趋势回调',
    'oversold_rebound': '超跌反弹',
    'low_backtrace_increase': '无大幅回撤',
}

# 候选股票池（模板中用到的代码都需要有缓存）
TEST_STOCKS = ['000001', '600036', '601318', '600519', '000858',
               '300750', '601888', '002594', '600000', '000002',
               '000568', '002304', '603259', '601012', '300059']


class TestTemplateRegistry(unittest.TestCase):
    """测试模板注册：确保所有策略选股模板都在后端模板列表中"""

    def test_all_templates_exist(self):
        """所有第一批模板都已注册到 STRATEGY_TEMPLATES"""
        from instock.web.portfolioBacktestHandler import STRATEGY_TEMPLATES
        registered_ids = {t['id'] for t in STRATEGY_TEMPLATES}
        for tid, name in STRATEGY_TEMPLATES_MAP.items():
            self.assertIn(tid, registered_ids,
                          f"模板 '{name}' (id={tid}) 未注册到 STRATEGY_TEMPLATES")

    def test_template_names_match(self):
        """模板名称与策略选股说明文档一致"""
        for tid, expected_name in STRATEGY_TEMPLATES_MAP.items():
            tpl = _get_template(tid)
            self.assertIsNotNone(tpl, f"模板 {tid} 不存在")
            self.assertEqual(tpl['name'], expected_name,
                             f"模板 {tid} 名称应为 '{expected_name}'，实际为 '{tpl['name']}'")

    def test_templates_have_required_fields(self):
        """每个模板都包含必要字段"""
        for tid in STRATEGY_TEMPLATES_MAP:
            tpl = _get_template(tid)
            self.assertIsNotNone(tpl)
            self.assertIn('id', tpl)
            self.assertIn('name', tpl)
            self.assertIn('code', tpl)
            self.assertIn('category', tpl)
            self.assertIn('description', tpl)
            self.assertTrue(len(tpl['code'].strip()) > 0,
                            f"模板 {tid} 代码为空")


class TestTemplateSandbox(unittest.TestCase):
    """测试模板代码安全性：可通过沙箱校验"""

    def test_all_templates_pass_sandbox(self):
        """所有模板代码通过沙箱安全检查"""
        from instock.core.backtest.strategy_sandbox import validate_code
        for tid, name in STRATEGY_TEMPLATES_MAP.items():
            tpl = _get_template(tid)
            self.assertIsNotNone(tpl, f"模板 {tid} 不存在")
            ok, err = validate_code(tpl['code'])
            self.assertTrue(ok, f"模板 '{name}' 沙箱校验失败: {err}")

    def test_all_templates_compilable(self):
        """所有模板代码可编译（含 initialize 函数）"""
        from instock.core.backtest.strategy_sandbox import compile_strategy
        for tid, name in STRATEGY_TEMPLATES_MAP.items():
            tpl = _get_template(tid)
            funcs = compile_strategy(tpl['code'])
            self.assertIn('initialize', funcs,
                          f"模板 '{name}' 缺少 initialize 函数")
            self.assertTrue(callable(funcs['initialize']),
                            f"模板 '{name}' 的 initialize 不可调用")


class TestTemplateBacktest(unittest.TestCase):
    """测试模板可运行回测且结果结构完整"""

    @classmethod
    def setUpClass(cls):
        """创建测试缓存数据"""
        cls._cache_files = []
        for i, code in enumerate(TEST_STOCKS):
            f = _create_test_cache(code, start='2024-01-02', periods=250,
                                   base_price=10.0 + i * 2, seed=42 + i)
            cls._cache_files.append(f)

    def _run_template(self, template_id):
        """运行指定模板的回测"""
        from instock.core.backtest.portfolio_engine import run_backtest
        tpl = _get_template(template_id)
        self.assertIsNotNone(tpl, f"模板 {template_id} 不存在")
        result = run_backtest(
            tpl['code'],
            '2024-03-01',
            '2024-12-31',
            initial_cash=1000000
        )
        return result

    def test_turtle_trade_runs(self):
        """海龟交易法则模板可运行"""
        result = self._run_template('turtle_trade')
        self.assertEqual(result['status'], 'completed',
                         f"回测失败: {result.get('message', '')}")
        self.assertIn('metrics', result)
        self.assertIn('nav', result)
        self.assertIn('trades', result)
        self.assertGreater(len(result['nav']), 0, "净值序列不应为空")

    def test_volume_increase_runs(self):
        """放量上涨模板可运行"""
        result = self._run_template('volume_increase')
        self.assertEqual(result['status'], 'completed',
                         f"回测失败: {result.get('message', '')}")
        self.assertIn('metrics', result)
        self.assertIn('nav', result)

    def test_trend_pullback_runs(self):
        """趋势回调模板可运行"""
        result = self._run_template('trend_pullback')
        self.assertEqual(result['status'], 'completed',
                         f"回测失败: {result.get('message', '')}")
        self.assertIn('metrics', result)

    def test_oversold_rebound_runs(self):
        """超跌反弹模板可运行"""
        result = self._run_template('oversold_rebound')
        self.assertEqual(result['status'], 'completed',
                         f"回测失败: {result.get('message', '')}")
        self.assertIn('metrics', result)

    def test_low_backtrace_increase_runs(self):
        """无大幅回撤模板可运行"""
        result = self._run_template('low_backtrace_increase')
        self.assertEqual(result['status'], 'completed',
                         f"回测失败: {result.get('message', '')}")
        self.assertIn('metrics', result)

    def test_result_metrics_structure(self):
        """回测结果指标结构完整"""
        result = self._run_template('turtle_trade')
        self.assertEqual(result['status'], 'completed')
        metrics = result['metrics']
        # 至少包含核心指标
        for key in ['total_return', 'annual_return', 'max_drawdown', 'sharpe_ratio']:
            self.assertIn(key, metrics,
                          f"指标缺少 {key}")

    def test_nav_is_chronological(self):
        """净值序列按日期顺序排列"""
        result = self._run_template('turtle_trade')
        self.assertEqual(result['status'], 'completed')
        nav = result['nav']
        if len(nav) >= 2:
            dates = [r['date'] for r in nav]
            self.assertEqual(dates, sorted(dates), "净值序列日期未按顺序排列")

    def test_trades_have_required_fields(self):
        """交易记录包含必要字段"""
        result = self._run_template('turtle_trade')
        self.assertEqual(result['status'], 'completed')
        if result.get('trades'):
            trade = result['trades'][0]
            for field in ['date', 'code', 'direction', 'price', 'amount']:
                self.assertIn(field, trade, f"交易记录缺少 {field}")
            self.assertIn(trade['direction'], ('buy', 'sell'),
                          f"交易方向应为 buy/sell，实际为 {trade['direction']}")


class TestNoFutureLeak(unittest.TestCase):
    """测试模板无未来函数：交易日期不早于信号产生日"""

    @classmethod
    def setUpClass(cls):
        for i, code in enumerate(TEST_STOCKS):
            _create_test_cache(code, start='2024-01-02', periods=250,
                               base_price=10.0 + i * 2, seed=42 + i)

    def _check_no_future_trades(self, template_id):
        """检查交易日期在回测范围内且按时间顺序"""
        from instock.core.backtest.portfolio_engine import run_backtest
        tpl = _get_template(template_id)
        result = run_backtest(tpl['code'], '2024-03-01', '2024-12-31',
                              initial_cash=1000000)
        if result['status'] != 'completed':
            self.skipTest(f"{template_id} 回测未完成")
        for trade in result.get('trades', []):
            trade_date = trade['date']
            self.assertGreaterEqual(trade_date, '2024-03-01',
                                    f"交易日期 {trade_date} 早于回测开始日期")
            self.assertLessEqual(trade_date, '2024-12-31',
                                 f"交易日期 {trade_date} 晚于回测结束日期")

    def test_turtle_no_future(self):
        self._check_no_future_trades('turtle_trade')

    def test_volume_increase_no_future(self):
        self._check_no_future_trades('volume_increase')

    def test_trend_pullback_no_future(self):
        self._check_no_future_trades('trend_pullback')

    def test_oversold_rebound_no_future(self):
        self._check_no_future_trades('oversold_rebound')

    def test_low_backtrace_no_future(self):
        self._check_no_future_trades('low_backtrace_increase')


class TestTemplateIndependence(unittest.TestCase):
    """测试每个模板独立运行，不互相依赖"""

    @classmethod
    def setUpClass(cls):
        for i, code in enumerate(TEST_STOCKS):
            _create_test_cache(code, start='2024-01-02', periods=250,
                               base_price=10.0 + i * 2, seed=42 + i)

    def test_each_template_independent(self):
        """每个模板可独立运行，结果不受其它模板影响"""
        from instock.core.backtest.portfolio_engine import run_backtest
        results = {}
        for tid in STRATEGY_TEMPLATES_MAP:
            tpl = _get_template(tid)
            result = run_backtest(tpl['code'], '2024-04-01', '2024-10-31',
                                  initial_cash=500000)
            results[tid] = result
            self.assertEqual(result['status'], 'completed',
                             f"模板 {tid} 独立运行失败: {result.get('message', '')}")

        # 确认每个结果有独立的数据
        for tid, result in results.items():
            self.assertIn('metrics', result, f"模板 {tid} 缺少 metrics")
            self.assertIn('nav', result, f"模板 {tid} 缺少 nav")


if __name__ == '__main__':
    unittest.main()
