"""
Empirical win-rate comparison: 3 composite-indicator templates vs S11/S12 baselines.

Methodology
-----------
- Universe: all locally cached stocks under instock/cache/hist/
- For each strategy, walk every bar; if buy condition fires, record forward
  5-day, 10-day, 20-day return.  Ignore signals where forward window is incomplete.
- Win rate = #(forward_return > 0) / #signals.  Reported alongside count, mean
  return, median return, and profit factor (sum win / abs sum loss).

Caveats
-------
- Cache only has 15 stocks x 250 days (2024), so absolute win-rate numbers are
  noisy.  RELATIVE ranking between strategies is the meaningful output.
- Signals are not de-duplicated by holding period; same code can fire on
  consecutive days.  This favors high-frequency strategies on the count but
  not on the win-rate metric.
"""
from __future__ import annotations

import glob
import os
import pickle
from dataclasses import dataclass, field
from typing import Callable, List

import numpy as np
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "instock", "cache", "hist")
HORIZONS = (5, 10, 20)


# ---------- data loading ----------
def load_universe() -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for path in sorted(glob.glob(os.path.join(CACHE_DIR, "*.gzip.pickle"))):
        code = os.path.basename(path).split(".")[0]
        try:
            with open(path, "rb") as fh:
                df = pickle.load(fh)
        except Exception:
            continue
        if not isinstance(df, pd.DataFrame) or len(df) < 80:
            continue
        df = df.sort_values("date").reset_index(drop=True)
        out[code] = df
    return out


# ---------- indicator helpers (vectorised, return full Series) ----------
def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    avg_g = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9):
    ll = low.rolling(n).min()
    hh = high.rolling(n).max()
    rsv = ((close - ll) / (hh - ll).replace(0, np.nan) * 100).fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def wr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    return (-100 * (hh - close) / (hh - ll).replace(0, np.nan)).fillna(-50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif, dea, (dif - dea) * 2


def boll(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid - k * sd, mid, mid + k * sd


def supertrend_score(high, low, close, atr_period=10, mult=3.0) -> pd.Series:
    """+1 trending up, -1 trending down (simplified)."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    direction = pd.Series(1, index=close.index, dtype=int)
    for i in range(1, len(close)):
        if close.iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction


def vol_ratio(volume: pd.Series, n: int = 5) -> pd.Series:
    return volume / volume.rolling(n).mean().replace(0, np.nan)


# ---------- normalisation ----------
def norm_linear(s: pd.Series) -> pd.Series:
    return s.clip(0, 100)


def norm_wr_invert(s: pd.Series) -> pd.Series:
    return (100 + s).clip(0, 100)


def norm_rolling_rank(s: pd.Series, win: int = 60) -> pd.Series:
    return s.rolling(win).rank(pct=True) * 100


def norm_supertrend(s: pd.Series) -> pd.Series:
    return ((s + 1) / 2) * 100


def norm_boll_pct_b(close, lower, upper) -> pd.Series:
    return ((close - lower) / (upper - lower).replace(0, np.nan) * 100).clip(0, 100)


# ---------- enrich ----------
def enrich(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ma20"] = d["close"].rolling(20).mean()
    d["ma60"] = d["close"].rolling(60).mean()
    d["rsi14"] = rsi(d["close"], 14)
    k, dd, j = kdj(d["high"], d["low"], d["close"], 9)
    d["kdj_k"], d["kdj_d"], d["kdj_j"] = k, dd, j
    d["wr14"] = wr(d["high"], d["low"], d["close"], 14)
    dif, dea, hist = macd(d["close"])
    d["macd_dif"], d["macd_dea"], d["macd_hist"] = dif, dea, hist
    bl, bm, bu = boll(d["close"], 20, 2)
    d["boll_lower"], d["boll_mid"], d["boll_upper"] = bl, bm, bu
    d["boll_pct_b"] = norm_boll_pct_b(d["close"], bl, bu)
    d["trend"] = supertrend_score(d["high"], d["low"], d["close"])
    d["vol_ratio_5"] = vol_ratio(d["volume"], 5)

    # Composite normalised columns for the 3 templates
    d["n_rsi14"] = norm_linear(d["rsi14"])
    d["n_kdj_k"] = norm_linear(d["kdj_k"])
    d["n_kdj_j"] = norm_linear(d["kdj_j"].clip(-50, 150))
    d["n_wr14"] = norm_wr_invert(d["wr14"])
    d["n_macd_hist"] = norm_rolling_rank(d["macd_hist"], 60)
    d["n_trend"] = norm_supertrend(d["trend"])
    d["n_vol_ratio"] = norm_rolling_rank(d["vol_ratio_5"], 60)
    d["n_boll_pct_b"] = norm_linear(d["boll_pct_b"])
    d["n_ma_trend"] = ((d["ma20"] > d["ma60"]).astype(int) * 100)
    d["n_atr_pct_inv"] = norm_rolling_rank(
        -((d["high"] - d["low"]) / d["close"]).rolling(14).mean(), 60
    )
    return d


# ---------- composite definition ----------
@dataclass
class Composite:
    name: str
    weights: dict       # column -> weight
    smooth_ema: int = 0
    buy_th: float = 30
    require_uptrend: bool = False  # extra optional filter

    def value(self, d: pd.DataFrame) -> pd.Series:
        wsum = sum(self.weights.values())
        out = sum(d[k] * w for k, w in self.weights.items()) / wsum
        if self.smooth_ema > 0:
            out = out.ewm(span=self.smooth_ema, adjust=False).mean()
        return out

    def signal(self, d: pd.DataFrame) -> pd.Series:
        v = self.value(d)
        sig = (v.shift(1) >= self.buy_th) & (v < self.buy_th)
        if self.require_uptrend:
            sig &= d["trend"] == 1
        return sig.fillna(False)


TEMPLATES = [
    Composite(
        name="T1 稳健-趋势确认",
        weights={
            "n_ma_trend": 0.30,
            "n_macd_hist": 0.20,
            "n_rsi14": 0.15,
            "n_vol_ratio": 0.20,
            "n_atr_pct_inv": 0.15,
        },
        smooth_ema=5,
        buy_th=30,
        require_uptrend=True,
    ),
    Composite(
        name="T2 进攻-超跌反弹",
        weights={
            "n_rsi14": 0.30,
            "n_wr14": 0.20,
            "n_boll_pct_b": 0.20,
            "n_macd_hist": 0.15,
            "n_vol_ratio": 0.15,
        },
        smooth_ema=2,
        buy_th=20,
    ),
    Composite(
        name="T3 动量共振-平衡",
        weights={
            "n_rsi14": 0.20,
            "n_kdj_k": 0.15,
            "n_wr14": 0.15,
            "n_trend": 0.30,
            "n_vol_ratio": 0.20,
        },
        smooth_ema=3,
        buy_th=25,
    ),
]


# ---------- baseline strategies ----------
def signal_s11(d: pd.DataFrame) -> pd.Series:
    """趋势回调: MA20>MA60, |close-MA20|/MA20<3%, 35<=RSI14<=55, vol < 0.8 * vol_ma5."""
    vol_ma5 = d["volume"].shift(1).rolling(5).mean()
    cond = (
        (d["ma20"] > d["ma60"])
        & ((d["close"] - d["ma20"]).abs() / d["ma20"] <= 0.03)
        & (d["rsi14"].between(35, 55))
        & (d["volume"] < vol_ma5 * 0.8)
    )
    return cond.fillna(False)


def signal_s12(d: pd.DataFrame) -> pd.Series:
    """超跌反弹: RSI<30, 近5日触及下轨, 收盘>下轨, 阳线, 量>1.2x vol_ma5."""
    vol_ma5 = d["volume"].shift(1).rolling(5).mean()
    touched = (d["low"].rolling(5).min() <= d["boll_lower"] * 1.01)
    cond = (
        (d["rsi14"] < 30)
        & touched
        & (d["close"] > d["boll_lower"])
        & (d["close"] > d["open"])
        & (d["volume"] > vol_ma5 * 1.2)
    )
    return cond.fillna(False)


# ---------- evaluation ----------
@dataclass
class Result:
    name: str
    n_signals: int = 0
    forward_returns: dict[int, list[float]] = field(default_factory=lambda: {h: [] for h in HORIZONS})

    def add(self, ret_by_h: dict[int, float]):
        self.n_signals += 1
        for h, r in ret_by_h.items():
            if r is not None and not np.isnan(r):
                self.forward_returns[h].append(r)

    def summary(self) -> dict:
        out = {"strategy": self.name, "signals": self.n_signals}
        for h in HORIZONS:
            arr = np.array(self.forward_returns[h])
            if len(arr) == 0:
                out[f"win{h}"] = None
                out[f"avg{h}"] = None
                out[f"med{h}"] = None
                out[f"pf{h}"] = None
            else:
                wins = arr[arr > 0].sum()
                losses = -arr[arr < 0].sum()
                out[f"win{h}"] = round(float((arr > 0).mean() * 100), 2)
                out[f"avg{h}"] = round(float(arr.mean() * 100), 3)
                out[f"med{h}"] = round(float(np.median(arr) * 100), 3)
                out[f"pf{h}"] = round(float(wins / losses), 2) if losses > 0 else None
        return out


def evaluate(name: str, signal_fn: Callable[[pd.DataFrame], pd.Series],
             universe: dict[str, pd.DataFrame]) -> Result:
    res = Result(name)
    for code, df in universe.items():
        d = enrich(df)
        sig = signal_fn(d)
        idx = np.flatnonzero(sig.values)
        closes = d["close"].values
        for i in idx:
            ret_by_h = {}
            for h in HORIZONS:
                j = i + h
                if j >= len(closes):
                    ret_by_h[h] = None
                else:
                    ret_by_h[h] = (closes[j] - closes[i]) / closes[i]
            res.add(ret_by_h)
    return res


def main():
    universe = load_universe()
    print(f"universe: {len(universe)} codes, "
          f"{sum(len(v) for v in universe.values())} total bars\n")

    strategies: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = [
        ("S11 趋势回调 (baseline)", signal_s11),
        ("S12 超跌反弹 (baseline)", signal_s12),
    ]
    for tpl in TEMPLATES:
        strategies.append((tpl.name, tpl.signal))

    rows = [evaluate(name, fn, universe).summary() for name, fn in strategies]
    df = pd.DataFrame(rows)
    cols = ["strategy", "signals",
            "win5", "avg5", "med5", "pf5",
            "win10", "avg10", "med10", "pf10",
            "win20", "avg20", "med20", "pf20"]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
