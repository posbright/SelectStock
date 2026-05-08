"""
Phase-9 quant analysis (V4) — medium- to long-term holding-period study.

Question
--------
"如果只做中长期交易，不做短期交易，收益率会有相应的提升吗？"

Setup (reuses V3 fundamentals universe + simulator)
---------------------------------------------------
- Universe = 89 fundamentally-prefiltered A-share codes (top of cn_stock_selection)
- K-line history 2020-01-01 ~ 2025-12-31, qfq, T+1 entry at next-bar open
- One open position per code; round-trip cost 0.36% deducted; same simulator
- Same 9 strategies as V3 (S11/S12/T1-3/E1-3/P3-tight) + the new MASTER combo
- Scaling stop / target with hold horizon (otherwise long-hold is dominated by
  short-stops being hit on intraday noise — that would be apples-to-oranges)

Hold-horizon presets
--------------------
Run S  (V3 baseline, short-term)   stop -5%   target +10%   max_hold  20 d
Run M  (medium-term)               stop -8%   target +20%   max_hold  60 d
Run L  (long-term)                 stop -12%  target +40%   max_hold 120 d
Run XL (very long / position)      stop -15%  target +60%   max_hold 250 d
Run BH (buy & hold benchmark)      no signal — every code, every Monday open;
                                   one position at a time per code; 60/120/250 d

Reports per (strategy, run): trades, win%, avg%, med%, expectancy%, PF,
avg_hold_days, exit-reason breakdown.
"""
from __future__ import annotations

import os
import sys
import pickle
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from _compare_composite_winrate_v2 import (   # noqa: E402
    enrich, signal_s11, signal_s12, T1, T2, T3, E1, E2, E3, Composite,
    ROUND_TRIP_COST,
)
from _compare_composite_winrate_v3_fundamentals import (  # noqa: E402
    P3_TIGHT, load_universe, simulate, evaluate, StrategyResult, Trade,
)


# -------------------- MASTER composite (from indicator guide §7) --------------
def _master_filter(d):
    return (d["ma60"] > d["ma120"]) | (d["close"] >= d["boll_lower"] * 1.02)


MASTER = Composite(
    name="MASTER 综合 (技术指南 §7)",
    weights={
        "n_ma_uptrend":         0.15,
        "n_macd_hist_rank":     0.15,
        "n_boll_pct_b":         0.15,
        "n_atr_pct_inv_rank":   0.10,   # boll_width 反向用 ATR 反向 rank 近似
        "n_obv_slope_rank":     0.20,
        "n_vol_ratio_rank":     0.15,
        "n_rsi14":              0.10,
    },
    smooth_ema=3,
    buy_th=35,
    direction="low",     # 评分跌穿 35 ⇒ 买入（低估 + 资金流入）
    extra_filter=_master_filter,
)


# -------------------- Buy & Hold benchmark ------------------------------------
def benchmark_buyhold(universe: dict[str, pd.DataFrame], hold_days: int,
                      cadence_days: int = 5) -> StrategyResult:
    """
    每隔 cadence_days 个交易日（≈每周一开盘）开仓持有 hold_days，
    净收益扣 0.36% 双边成本。同一只股票同一时间只持一仓。
    用作"完全不择时"的中长期基准。
    """
    name = f"基准: 定投持有 {hold_days}d (cadence={cadence_days})"
    res = StrategyResult(name)
    for code, df in universe.items():
        n = len(df)
        if n < hold_days + 5:
            continue
        opn = df["open"].values
        cls = df["close"].values
        dts = df["date"].values
        i = 0
        while i < n - hold_days - 1:
            eb = i + 1
            entry = opn[eb]
            if not np.isfinite(entry) or entry <= 0:
                i += cadence_days
                continue
            ob = min(eb + hold_days, n - 1)
            exit_p = cls[ob]
            gross = (exit_p - entry) / entry
            net = gross - ROUND_TRIP_COST
            res.trades.append(Trade(
                code=code, entry_bar=eb, entry_date=dts[eb], entry_price=float(entry),
                exit_bar=ob, exit_date=dts[ob], exit_price=float(exit_p),
                reason="time-exit",
                gross_ret=float(gross), net_ret=float(net),
                hold_days=int(ob - eb),
            ))
            i = ob + 1   # next position starts after exit
    return res


# -------------------- main ----------------------------------------------------
RUNS = [
    ("S  短期 (V3 基线)",    0.05, 0.10,  20),
    ("M  中期",              0.08, 0.20,  60),
    ("L  长期",              0.12, 0.40, 120),
    ("XL 超长期 / 仓位",     0.15, 0.60, 250),
]


def _row(r: dict) -> str:
    if r.get("trades", 0) == 0:
        return f"  {r.get('strategy','?'):<32}  trades=   0"
    return (f"  {r['strategy']:<32}  trades={r['trades']:>4}  "
            f"win%={r['win%']:>5}  avg%={r['avg%']:>6}  "
            f"exp%={r['expectancy%']:>6}  PF={r['PF']}  "
            f"hold={r['avg_hold']:>4}d  "
            f"stop/tp/time={r['stop%']}/{r['tp%']}/{r['time%']}")


def main():
    universe = load_universe()
    if not universe:
        print("EMPTY universe"); return
    n_bars = sum(len(v) for v in universe.values())
    dmin = min(v["date"].min() for v in universe.values())
    dmax = max(v["date"].max() for v in universe.values())
    print(f"\nuniverse: {len(universe)} codes (基本面预筛 top), "
          f"{n_bars} bars, {dmin.date()} ~ {dmax.date()}\n")

    strategies: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = [
        ("S11 趋势回调",          signal_s11),
        ("S12 超跌反弹",          signal_s12),
        (T1.name,                  T1.signal),
        (T2.name,                  T2.signal),
        (T3.name,                  T3.signal),
        (E1.name,                  E1.signal),
        (E2.name,                  E2.signal),
        (E3.name,                  E3.signal),
        (P3_TIGHT.name,            P3_TIGHT.signal),
        (MASTER.name,              MASTER.signal),
    ]

    all_rows: dict[str, list[dict]] = {}
    for label, sl, tp, hold in RUNS:
        print(f"\n=== Run {label}: stop=-{int(sl*100)}%, target=+{int(tp*100)}%, max_hold={hold}d ===")
        rows = []
        for name, fn in strategies:
            r = evaluate(name, fn, universe, sl, tp, hold).summary()
            rows.append(r)
            print(_row(r))
        all_rows[label] = rows

    print("\n=== Run BH: 定投持有基准（不择时） ===")
    bh_rows = []
    for hd in (60, 120, 250):
        r = benchmark_buyhold(universe, hd).summary()
        bh_rows.append(r)
        print(_row(r))
    all_rows["BH"] = bh_rows

    # ---- pivot summary ------------------------------------------------------
    print("\n\n========== PIVOT (expectancy% per trade across horizons) ==========")
    print(f"  {'strategy':<32} | " + " | ".join(f"{lbl[:14]:>14}" for lbl, *_ in RUNS))
    for i, (name, _) in enumerate(strategies):
        cells = []
        for label, *_ in RUNS:
            r = all_rows[label][i]
            cells.append(f"{r.get('expectancy%','-'):>14}" if r.get('trades') else f"{'(0)':>14}")
        print(f"  {name:<32} | " + " | ".join(cells))

    print("\n========== PIVOT (PF) ==========")
    print(f"  {'strategy':<32} | " + " | ".join(f"{lbl[:14]:>14}" for lbl, *_ in RUNS))
    for i, (name, _) in enumerate(strategies):
        cells = []
        for label, *_ in RUNS:
            r = all_rows[label][i]
            cells.append(f"{r.get('PF','-'):>14}" if r.get('trades') else f"{'(0)':>14}")
        print(f"  {name:<32} | " + " | ".join(cells))

    print("\n========== Buy&Hold benchmark ==========")
    for r in bh_rows:
        print(_row(r))


if __name__ == "__main__":
    main()
