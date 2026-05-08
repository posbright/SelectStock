"""
Phase-9 V5 — validate the proposed MASTER_MID_LONG corrections.

V4 finding: MASTER (§7) under-performed S12 across all hold horizons because
its trigger uses direction='low' + buy_th=35 + smooth_ema=3 — designed for
short-term oversold dip-buying, not for mid/long trend confirmation.

V5 hypothesis (proposed in document/medium_long_term_holding_analysis.md §7):
    direction='high'  + buy_th=50  + smooth_ema=5
    + extra_filter:  ma60>ma120  AND  adx14>18

V5 also tests several variants around that point so we can see which
single change drives the improvement (rather than just blindly trusting
the recommended bundle):

    M0 = baseline (V4 MASTER, direction='low' th=35 ema=3)
    M1 = direction='high' only (th=50 ema=5)
    M2 = M1 + adx>18 filter
    M3 = M1 + ma60>ma120 filter
    M4 = M1 + (ma60>ma120 AND adx>18)         <- the documented "correction"
    M5 = M4 + buy_th=55 (more strict)
    M6 = M4 + smooth_ema=8 (smoother)

Compared against V4 winners (S12, T3) on the same 4 hold horizons.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from _compare_composite_winrate_v2 import (   # noqa: E402
    Composite, signal_s12,
)
from _compare_composite_winrate_v3_fundamentals import (  # noqa: E402
    load_universe, evaluate,
)
from _compare_composite_winrate_v2 import T3   # noqa: E402

WEIGHTS = {
    "n_ma_uptrend":         0.15,
    "n_macd_hist_rank":     0.15,
    "n_boll_pct_b":         0.15,
    "n_atr_pct_inv_rank":   0.10,
    "n_obv_slope_rank":     0.20,
    "n_vol_ratio_rank":     0.15,
    "n_rsi14":              0.10,
}


def _f_adx(d):    return d["adx14"] > 18
def _f_ma(d):     return d["ma60"] > d["ma120"]
def _f_both(d):   return (d["adx14"] > 18) & (d["ma60"] > d["ma120"])


M0 = Composite("M0 MASTER 原版 (V4)",            WEIGHTS, smooth_ema=3, buy_th=35, direction="low",
               extra_filter=lambda d: (d["ma60"] > d["ma120"]) | (d["close"] >= d["boll_lower"] * 1.02))
M1 = Composite("M1 +direction=high th=50 ema=5", WEIGHTS, smooth_ema=5, buy_th=50, direction="high")
M2 = Composite("M2 = M1 + adx>18",               WEIGHTS, smooth_ema=5, buy_th=50, direction="high",
               extra_filter=_f_adx)
M3 = Composite("M3 = M1 + ma60>ma120",           WEIGHTS, smooth_ema=5, buy_th=50, direction="high",
               extra_filter=_f_ma)
M4 = Composite("M4 = M1 + ma & adx (推荐修正)",   WEIGHTS, smooth_ema=5, buy_th=50, direction="high",
               extra_filter=_f_both)
M5 = Composite("M5 = M4 + buy_th=55 (严格)",     WEIGHTS, smooth_ema=5, buy_th=55, direction="high",
               extra_filter=_f_both)
M6 = Composite("M6 = M4 + ema=8 (更平滑)",        WEIGHTS, smooth_ema=8, buy_th=50, direction="high",
               extra_filter=_f_both)

VARIANTS = [M0, M1, M2, M3, M4, M5, M6]

RUNS = [
    ("S  短期",   0.05, 0.10,  20),
    ("M  中期",   0.08, 0.20,  60),
    ("L  长期",   0.12, 0.40, 120),
    ("XL 超长",   0.15, 0.60, 250),
]


def _row(r: dict) -> str:
    if r.get("trades", 0) == 0:
        return f"  {r.get('strategy','?'):<32}  trades=   0"
    return (f"  {r['strategy']:<32}  trades={r['trades']:>5}  "
            f"win%={r['win%']:>5}  exp%={r['expectancy%']:>7}  PF={r['PF']}  "
            f"hold={r['avg_hold']:>4}d")


def main():
    universe = load_universe()
    if not universe:
        print("EMPTY universe"); return
    print(f"\nuniverse: {len(universe)} codes\n")

    strategies: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = (
        [(c.name, c.signal) for c in VARIANTS]
        + [("S12 (V4 中长期冠军)", signal_s12),
           (f"T3* {T3.name}", T3.signal)]
    )

    all_rows: dict[str, list[dict]] = {}
    for label, sl, tp, hold in RUNS:
        print(f"\n=== Run {label}: stop=-{int(sl*100)}% tp=+{int(tp*100)}% hold={hold}d ===")
        rows = []
        for name, fn in strategies:
            r = evaluate(name, fn, universe, sl, tp, hold).summary()
            rows.append(r)
            print(_row(r))
        all_rows[label] = rows

    # ---- pivot --------------------------------------------------------------
    print("\n========== PIVOT (expectancy% per trade) ==========")
    print(f"  {'strategy':<34}" + "".join(f"{lbl[:8]:>10}" for lbl, *_ in RUNS))
    for i, (name, _) in enumerate(strategies):
        cells = []
        for label, *_ in RUNS:
            r = all_rows[label][i]
            cells.append(f"{r.get('expectancy%','-'):>10}" if r.get('trades') else f"{'(0)':>10}")
        print(f"  {name:<34}" + "".join(cells))

    print("\n========== PIVOT (PF) ==========")
    print(f"  {'strategy':<34}" + "".join(f"{lbl[:8]:>10}" for lbl, *_ in RUNS))
    for i, (name, _) in enumerate(strategies):
        cells = []
        for label, *_ in RUNS:
            r = all_rows[label][i]
            cells.append(f"{r.get('PF','-'):>10}" if r.get('trades') else f"{'(0)':>10}")
        print(f"  {name:<34}" + "".join(cells))

    print("\n========== PIVOT (trades) ==========")
    print(f"  {'strategy':<34}" + "".join(f"{lbl[:8]:>10}" for lbl, *_ in RUNS))
    for i, (name, _) in enumerate(strategies):
        cells = []
        for label, *_ in RUNS:
            r = all_rows[label][i]
            cells.append(f"{r.get('trades',0):>10}")
        print(f"  {name:<34}" + "".join(cells))


if __name__ == "__main__":
    main()
