"""
Phase-9 V6 — final portfolio-level validation.

Goal: instead of per-trade expectancy, build an actual equity curve assuming
realistic constraints:
  - capital = 1,000,000 CNY
  - max concurrent positions = 8
  - each position size = 12.5% of equity at entry
  - one position per code at a time
  - signals: S12 (primary) + T3 (secondary) -> dual-signal portfolio
  - hold horizon = 60d (medium) and 120d (long) — V4 winners
  - same simulator costs (0.36% round trip)
  - report: total return, CAGR, max drawdown, Sharpe, # trades

We compare:
  P_S12        — S12 only
  P_T3         — T3 only
  P_S12_T3     — S12 OR T3 (whichever fires first)
  P_M1_watch   — M1 (V5 winner) used as primary entry (control)
  P_BH         — buy & hold periodic basket (rebalance every 60d)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from _compare_composite_winrate_v2 import (   # noqa: E402
    enrich, signal_s12, T3, Composite, ROUND_TRIP_COST,
)
from _compare_composite_winrate_v3_fundamentals import load_universe  # noqa: E402
from _compare_composite_winrate_v5_master_fix import M1                # noqa: E402

INITIAL_CAPITAL   = 1_000_000.0
MAX_CONCURRENT    = 8
POSITION_FRACTION = 1.0 / MAX_CONCURRENT     # 12.5% at entry
HORIZONS          = [(60, 0.08, 0.20), (120, 0.12, 0.40)]


@dataclass
class PortTrade:
    code: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    capital_in: float
    pnl: float
    reason: str
    hold: int


def collect_signals(universe: dict[str, pd.DataFrame],
                    sig_fn) -> pd.DataFrame:
    """Return long-form DataFrame: code, bar_idx, date, open_next, high_seq, low_seq, close_seq."""
    rows = []
    for code, df in universe.items():
        d = enrich(df)
        sig = sig_fn(d)
        idx = np.flatnonzero(sig.values)
        for i in idx:
            if i + 1 >= len(d):
                continue
            rows.append({"code": code, "bar": i, "date": d["date"].iloc[i]})
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def simulate_portfolio(name: str,
                       universe: dict[str, pd.DataFrame],
                       sig_fn,
                       stop_loss: float,
                       take_profit: float,
                       max_hold: int) -> dict:
    """
    Walk forward day-by-day across the union of all dates; whenever a signal
    fires AND open_positions < MAX_CONCURRENT AND code not already held,
    open at next-bar open with POSITION_FRACTION * current_equity.
    Exit on stop / target / max_hold same as simulator. Cash earns 0%.
    """
    # 1. enrich each code once
    enriched: dict[str, pd.DataFrame] = {c: enrich(df).reset_index(drop=True) for c, df in universe.items()}
    # 2. build signal-bar map: code -> set of bar indices where signal fired
    sig_bars: dict[str, set] = {}
    for c, d in enriched.items():
        sig_bars[c] = set(np.flatnonzero(sig_fn(d).values).tolist())
    # 3. unified date axis
    all_dates = sorted({d for c in enriched for d in enriched[c]["date"].tolist()})
    bar_idx_for: dict[tuple[str, pd.Timestamp], int] = {}
    for c, d in enriched.items():
        for i, dt in enumerate(d["date"].tolist()):
            bar_idx_for[(c, dt)] = i

    cash = INITIAL_CAPITAL
    open_pos: dict[str, dict] = {}    # code -> {entry_bar, entry_price, shares, target, stop, exit_bar_max, capital_in}
    trades: list[PortTrade] = []
    equity_curve = []

    for dt in all_dates:
        # --- mark-to-market unrealised value
        unreal = 0.0
        for c, p in open_pos.items():
            i = bar_idx_for.get((c, dt))
            px = p["entry_price"] if i is None else float(enriched[c]["close"].iloc[i])
            unreal += p["shares"] * px
        equity = cash + unreal
        equity_curve.append((dt, equity))

        # --- exits first (check intraday hi/lo against stop/target, then time)
        to_close = []
        for c, p in list(open_pos.items()):
            i = bar_idx_for.get((c, dt))
            if i is None or i <= p["entry_bar"]:
                continue
            d = enriched[c]
            hi = float(d["high"].iloc[i]); lo = float(d["low"].iloc[i]); cl = float(d["close"].iloc[i])
            reason = None; price = None
            if lo <= p["stop"]:
                price = p["stop"]; reason = "stop-loss"
            elif hi >= p["target"]:
                price = p["target"]; reason = "win-target"
            elif i >= p["exit_bar_max"]:
                price = cl; reason = "time-exit"
            if reason:
                proceeds = p["shares"] * price * (1 - ROUND_TRIP_COST / 2)   # half cost on exit
                cash += proceeds
                pnl = proceeds - p["capital_in"]
                trades.append(PortTrade(
                    code=c, entry_date=p["entry_date"], exit_date=dt,
                    entry_price=p["entry_price"], exit_price=price,
                    capital_in=p["capital_in"], pnl=pnl, reason=reason,
                    hold=i - p["entry_bar"],
                ))
                to_close.append(c)
        for c in to_close:
            del open_pos[c]

        # --- new entries: find codes whose previous bar had a signal
        if len(open_pos) < MAX_CONCURRENT:
            for c, d in enriched.items():
                if c in open_pos:
                    continue
                i = bar_idx_for.get((c, dt))
                if i is None or i == 0:
                    continue
                prev = i - 1
                if prev not in sig_bars[c]:
                    continue
                entry_px = float(d["open"].iloc[i])
                if not np.isfinite(entry_px) or entry_px <= 0:
                    continue
                cap_alloc = equity * POSITION_FRACTION
                if cash < cap_alloc * 0.5:
                    break
                shares = (cap_alloc / entry_px) * (1 - ROUND_TRIP_COST / 2)   # half cost on entry
                cost = shares * entry_px / (1 - ROUND_TRIP_COST / 2)
                cash -= cost
                open_pos[c] = {
                    "entry_bar": i, "entry_date": dt, "entry_price": entry_px,
                    "shares": shares,
                    "target": entry_px * (1 + take_profit),
                    "stop":   entry_px * (1 - stop_loss),
                    "exit_bar_max": i + max_hold,
                    "capital_in": cost,
                }
                if len(open_pos) >= MAX_CONCURRENT:
                    break

    # --- close any leftover at last available close
    for c, p in open_pos.items():
        d = enriched[c]
        last_px = float(d["close"].iloc[-1])
        proceeds = p["shares"] * last_px * (1 - ROUND_TRIP_COST / 2)
        cash += proceeds
        trades.append(PortTrade(
            code=c, entry_date=p["entry_date"], exit_date=d["date"].iloc[-1],
            entry_price=p["entry_price"], exit_price=last_px,
            capital_in=p["capital_in"], pnl=proceeds - p["capital_in"],
            reason="end-of-data", hold=len(d) - 1 - p["entry_bar"],
        ))
    final_equity = cash

    eq = pd.DataFrame(equity_curve, columns=["date", "equity"]).drop_duplicates("date").set_index("date").sort_index()
    eq["equity"] = eq["equity"].ffill()
    eq["dd"] = eq["equity"] / eq["equity"].cummax() - 1.0
    rets = eq["equity"].pct_change().dropna()
    days = (eq.index[-1] - eq.index[0]).days
    cagr = (final_equity / INITIAL_CAPITAL) ** (365 / max(days, 1)) - 1
    sharpe = float(np.sqrt(252) * rets.mean() / rets.std()) if rets.std() > 0 else float("nan")
    max_dd = float(eq["dd"].min())

    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    return {
        "name": name,
        "trades": n,
        "win%": round(len(wins) / max(n, 1) * 100, 1),
        "total_ret%": round((final_equity / INITIAL_CAPITAL - 1) * 100, 2),
        "CAGR%": round(cagr * 100, 2),
        "max_dd%": round(max_dd * 100, 2),
        "Sharpe": round(sharpe, 2),
        "final_equity": round(final_equity, 0),
        "avg_hold": round(np.mean([t.hold for t in trades]) if trades else 0, 1),
    }


def signal_s12_or_t3(d):
    return signal_s12(d) | T3.signal(d)


def signal_bh_periodic(d):
    """Fire signal every 60 trading days starting from index 60."""
    s = pd.Series(False, index=d.index)
    s.iloc[60::60] = True
    return s


def main():
    universe = load_universe()
    if not universe:
        print("EMPTY universe"); return
    print(f"\nuniverse: {len(universe)} codes\n")

    strategies = [
        ("P_S12        S12 only",       signal_s12),
        ("P_T3         T3 only",        T3.signal),
        ("P_S12_T3     S12 OR T3",      signal_s12_or_t3),
        ("P_M1_watch   M1 (V5)",        M1.signal),
        ("P_BH         buy-hold 60d",   signal_bh_periodic),
    ]

    for hold, sl, tp in HORIZONS:
        print(f"\n========== Horizon: hold={hold}d  stop=-{int(sl*100)}%  target=+{int(tp*100)}% ==========")
        print(f"  {'strategy':<28} | trades | win% | total% |  CAGR% | maxDD% | Sharpe |  hold")
        for name, fn in strategies:
            r = simulate_portfolio(name, universe, fn, sl, tp, hold)
            print(f"  {r['name']:<28} | {r['trades']:>6} | {r['win%']:>4} | "
                  f"{r['total_ret%']:>6} | {r['CAGR%']:>6} | {r['max_dd%']:>6} | "
                  f"{r['Sharpe']:>6} | {r['avg_hold']:>5}")


if __name__ == "__main__":
    main()
