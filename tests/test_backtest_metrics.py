#!/usr/bin/env python3
"""Test backtest API with all metrics"""
import urllib.request, json, time, sys

strategy_code = """
def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    security = context.security
    close_data = history(security, 21, 'close')
    if len(close_data) < 21:
        return
    MA5 = close_data[-5:].mean()
    MA20 = close_data.mean()
    cash = context.portfolio.available_cash
    if MA5 > MA20 and security not in context.portfolio.positions:
        order_value(security, cash * 0.95)
    elif MA5 < MA20 and security in context.portfolio.positions:
        order_target(security, 0)
"""

payload = json.dumps({
    'code': strategy_code,
    'start_date': '2024-01-01',
    'end_date': '2025-01-01',
    'initial_cash': 1000000,
    'benchmark': '000300',
}).encode()

req = urllib.request.Request(
    'http://localhost:9988/instock/api/backtest/portfolio/run',
    data=payload, headers={'Content-Type': 'application/json'}
)

t0 = time.time()
resp = urllib.request.urlopen(req, timeout=120)
result = json.loads(resp.read())
elapsed = time.time() - t0

data = result.get('data', {})
m = data.get('metrics', {})

print(f"Status: {data.get('status')}  Time: {elapsed:.1f}s")
print(f"Backtest ID: {data.get('backtest_id')}")
print()
print("=== 收益指标 ===")
print(f"  策略收益:     {m.get('total_return', 0):.2f}%")
print(f"  策略年化收益: {m.get('annual_return', 0):.2f}%")
print(f"  基准收益:     {m.get('benchmark_return', 0):.2f}%")
print(f"  超额收益:     {m.get('excess_return', 0):.2f}%")
print(f"  日均超额:     {m.get('avg_daily_excess', 0):.4f}%")
print()
print("=== 风险指标 ===")
print(f"  最大回撤:     {m.get('max_drawdown', 0):.2f}%")
print(f"  回撤区间:     {m.get('max_drawdown_start', '')} ~ {m.get('max_drawdown_end', '')}")
print(f"  策略波动率:   {m.get('strategy_volatility', 0):.2f}%")
print(f"  基准波动率:   {m.get('benchmark_volatility', 0):.2f}%")
print(f"  超额最大回撤: {m.get('excess_max_drawdown', 0):.2f}%")
print()
print("=== 风险调整收益 ===")
print(f"  Alpha:        {m.get('alpha', 0):.4f}")
print(f"  Beta:         {m.get('beta', 0):.4f}")
print(f"  夏普比率:     {m.get('sharpe_ratio', 0):.4f}")
print(f"  索提诺比率:   {m.get('sortino_ratio', 0):.4f}")
print(f"  超额夏普:     {m.get('excess_sharpe_ratio', 0):.4f}")
print(f"  信息比率:     {m.get('information_ratio', 0):.4f}")
print()
print("=== 交易统计 ===")
print(f"  日胜率:       {m.get('daily_win_rate', 0):.1f}%")
print(f"  盈亏比:       {m.get('profit_loss_ratio', 0):.3f}")
print(f"  交易次数:     {m.get('trade_count', 0)}")
print(f"  盈利次数:     {m.get('win_count', 0)}")
print(f"  亏损次数:     {m.get('loss_count', 0)}")
print(f"  交易日数:     {m.get('trading_days', 0)}")

# Check nav and trades data
nav = data.get('nav', [])
trades = data.get('trades', [])
print(f"\n每日数据: {len(nav)} 条")
print(f"交易记录: {len(trades)} 条")
if nav:
    print(f"首日: {nav[0]}")
    print(f"末日: {nav[-1]}")
if trades:
    print(f"首笔交易: {trades[0]}")

# Verify benchmark data is non-zero
bm_ret = m.get('benchmark_return', 0)
if abs(bm_ret) < 0.01:
    print("\n[FAIL] 基准收益为 0 — 基准数据加载失败!")
    sys.exit(1)
else:
    print(f"\n[PASS] 基准收益 {bm_ret:.2f}% — 基准数据加载成功!")

# Check detail API
bt_id = data.get('backtest_id')
if bt_id:
    detail_req = urllib.request.urlopen(
        f'http://localhost:9988/instock/api/backtest/portfolio/detail?id={bt_id}')
    detail = json.loads(detail_req.read())
    dm = detail.get('data', {}).get('metrics', {})
    print(f"\n[PASS] Detail API 返回 {len(dm)} 个指标字段:")
    for k, v in sorted(dm.items()):
        print(f"  {k}: {v}")
