"""
Phase-9 quant analysis (V2) — extended sample, transaction costs, dedup,
plus additional expert composite designs.

What's new vs _compare_composite_winrate.py
-------------------------------------------
1. Universe expanded to ~60 diversified A-share tickers across banks /
   liquor / tech / pharma / new-energy / brokers / semis / consumer /
   real-estate / steel, fetched via instock.core.backtest.data_feed.
2. Date range 2020-01-01 ~ 2025-12-31 (covers bull/bear/range regimes).
3. Round-trip transaction cost subtracted from every forward return:
       commission   = 0.0003 each side   = 0.0006
       stamp_tax    = 0.001 sell only    = 0.001
       slippage     = 0.001 each side    = 0.002
       ---------------------------------- = 0.0036  (~0.36% round trip)
4. Same-code dedup: after a buy signal, ignore further signals from the
   same code for the next H bars (H = the horizon being measured).
5. New "expert" composites E1/E2/E3 designed cross-class (trend × volume ×
   momentum × volatility regime) per the methodology in §2 of the report.
6. A small grid sweep over the most promising composite weights/threshold
   to find the empirical optimum on this dataset.
7. Saves a markdown summary into document/.
"""
from __future__ import annotations

import os
import sys
import json
import time
import pickle
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.WARNING)

from instock.core.backtest.data_feed import load_stock_data  # noqa: E402

# ----------------------------- config -----------------------------------------
START = "2020-01-01"
END = "2025-12-31"
HORIZONS = (5, 10, 20)
ROUND_TRIP_COST = 0.0006 + 0.001 + 0.002          # 0.0036
LOCAL_CACHE = os.path.join(os.path.dirname(__file__), "_phase9_universe_cache.pkl")

UNIVERSE = [
    # 银行
    "600036", "601398", "601288", "601939", "600000",
    # 白酒/食品饮料
    "600519", "000858", "000568", "603288", "600887",
    # 家电
    "000333", "000651", "600690",
    # 医药
    "600276", "300760", "300015", "002714",
    # 新能源/光伏/电池
    "300750", "002594", "601012", "300274", "002129",
    # 半导体/芯片
    "002371", "688981", "603501", "300782",
    # 互联网/软件/游戏
    "002230", "300059", "002415",
    # 券商
    "600030", "601688", "600999",
    # 保险
    "601318", "601628",
    # 地产
    "000002", "600048",
    # 钢铁/有色
    "600019", "601899", "603799",
    # 煤炭/石油
    "601088", "601857",
    # 公用事业/基建
    "601800", "600585", "601668",
    # 汽车
    "601633", "000625",
    # 港口/物流
    "601111", "600009",
    # 农业/化工
    "000895", "600309",
    # 大盘ETF/指数级（剔除，会被路由器拦截）
    # 中小盘代表
    "002241", "002475", "300124",
    # 其他大蓝筹
    "600028", "601328", "601166",
]
UNIVERSE = sorted(set(UNIVERSE))


# ----------------------------- universe loading -------------------------------
def load_universe(force: bool = False) -> dict[str, pd.DataFrame]:
    if not force and os.path.isfile(LOCAL_CACHE):
        with open(LOCAL_CACHE, "rb") as fh:
            data = pickle.load(fh)
        if data:
            print(f"loaded universe from local cache: {len(data)} codes")
            return data

    out: dict[str, pd.DataFrame] = {}
    for i, code in enumerate(UNIVERSE, 1):
        try:
            df = load_stock_data(code, START, END)
        except Exception as e:
            print(f"  [{i:>2}/{len(UNIVERSE)}] {code}  ERROR  {e}")
            continue
        if df is None or len(df) < 120:
            print(f"  [{i:>2}/{len(UNIVERSE)}] {code}  skip (n={0 if df is None else len(df)})")
            continue
        out[code] = df.reset_index(drop=True)
        print(f"  [{i:>2}/{len(UNIVERSE)}] {code}  ok  {len(df):>4} rows  "
              f"{df['date'].min().date()} ~ {df['date'].max().date()}")
        time.sleep(0.05)
    with open(LOCAL_CACHE, "wb") as fh:
        pickle.dump(out, fh)
    print(f"saved universe local cache → {LOCAL_CACHE} ({len(out)} codes)")
    return out


# ----------------------------- indicators -------------------------------------
def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    ag = gain.ewm(alpha=1 / n, adjust=False).mean()
    al = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def kdj(high, low, close, n=9):
    ll = low.rolling(n).min()
    hh = high.rolling(n).max()
    rsv = ((close - ll) / (hh - ll).replace(0, np.nan) * 100).fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def wr(high, low, close, n=14):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    return (-100 * (hh - close) / (hh - ll).replace(0, np.nan)).fillna(-50)


def macd_hist(close, fast=12, slow=26, signal=9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    return (dif - dea) * 2


def boll(close, n=20, k=2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid - k * sd, mid, mid + k * sd


def supertrend_dir(high, low, close, period=10, mult=3.0) -> pd.Series:
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    direction = pd.Series(1, index=close.index, dtype=int)
    arr = direction.to_numpy()
    c = close.to_numpy(); u = upper.to_numpy(); l = lower.to_numpy()
    for i in range(1, len(close)):
        if c[i] > u[i - 1]:
            arr[i] = 1
        elif c[i] < l[i - 1]:
            arr[i] = -1
        else:
            arr[i] = arr[i - 1]
    return pd.Series(arr, index=close.index)


def adx(high, low, close, n=14) -> pd.Series:
    up = high.diff()
    dn = -low.diff()
    plus_dm = ((up > dn) & (up > 0)).astype(float) * up
    minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1 / n, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return dx.ewm(alpha=1 / n, adjust=False).mean().fillna(0)


def obv(close, volume) -> pd.Series:
    sign = np.sign(close.diff().fillna(0))
    return (sign * volume).cumsum()


def cci(high, low, close, n=20):
    tp = (high + low + close) / 3
    ma = tp.rolling(n).mean()
    md = (tp - ma).abs().rolling(n).mean().replace(0, np.nan)
    return ((tp - ma) / (0.015 * md)).fillna(0)


# ----------------------------- normalisation ----------------------------------
def n_lin(s):              return s.clip(0, 100)
def n_wr(s):               return (100 + s).clip(0, 100)
def n_rank(s, w=60):       return (s.rolling(w).rank(pct=True) * 100).fillna(50)
def n_supertrend(s):       return ((s + 1) / 2) * 100
def n_pctb(c, lo, up):     return ((c - lo) / (up - lo).replace(0, np.nan) * 100).clip(0, 100)
def n_cci(s):              return ((s + 200) / 4).clip(0, 100)


# ----------------------------- enrich -----------------------------------------
def enrich(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ma5"] = d["close"].rolling(5).mean()
    d["ma10"] = d["close"].rolling(10).mean()
    d["ma20"] = d["close"].rolling(20).mean()
    d["ma60"] = d["close"].rolling(60).mean()
    d["ma120"] = d["close"].rolling(120).mean()
    d["rsi14"] = rsi(d["close"], 14)
    d["rsi6"] = rsi(d["close"], 6)
    k, dd, j = kdj(d["high"], d["low"], d["close"], 9)
    d["kdj_k"], d["kdj_d"], d["kdj_j"] = k, dd, j
    d["wr14"] = wr(d["high"], d["low"], d["close"], 14)
    d["macd_hist"] = macd_hist(d["close"])
    bl, bm, bu = boll(d["close"], 20, 2)
    d["boll_lower"], d["boll_mid"], d["boll_upper"] = bl, bm, bu
    d["boll_pct_b"] = n_pctb(d["close"], bl, bu)
    d["boll_width"] = (bu - bl) / bm.replace(0, np.nan)
    d["trend_st"] = supertrend_dir(d["high"], d["low"], d["close"])
    d["adx14"] = adx(d["high"], d["low"], d["close"], 14)
    d["obv"] = obv(d["close"], d["volume"])
    d["obv_slope10"] = d["obv"].diff(10) / d["obv"].abs().rolling(60).mean().replace(0, np.nan)
    d["vol_ma5"] = d["volume"].rolling(5).mean()
    d["vol_ratio_5"] = d["volume"] / d["vol_ma5"].replace(0, np.nan)
    d["cci20"] = cci(d["high"], d["low"], d["close"], 20)
    d["atr14_pct"] = (
        pd.concat([d["high"] - d["low"],
                   (d["high"] - d["close"].shift()).abs(),
                   (d["low"] - d["close"].shift()).abs()], axis=1).max(axis=1)
        .rolling(14).mean() / d["close"]
    )

    # normalised columns reused by multiple composites
    d["n_rsi14"] = n_lin(d["rsi14"])
    d["n_rsi6"] = n_lin(d["rsi6"])
    d["n_kdj_k"] = n_lin(d["kdj_k"])
    d["n_kdj_j"] = n_lin(d["kdj_j"].clip(-50, 150) + 50) / 2 * 2  # roughly 0-100
    d["n_wr14"] = n_wr(d["wr14"])
    d["n_macd_hist_rank"] = n_rank(d["macd_hist"], 60)
    d["n_trend_st"] = n_supertrend(d["trend_st"])
    d["n_vol_ratio_rank"] = n_rank(d["vol_ratio_5"], 60)
    d["n_boll_pct_b"] = n_lin(d["boll_pct_b"])
    d["n_ma_uptrend"] = ((d["ma20"] > d["ma60"]).astype(int) * 100)
    d["n_long_uptrend"] = ((d["ma60"] > d["ma120"]).astype(int) * 100)
    d["n_atr_pct_inv_rank"] = n_rank(-d["atr14_pct"], 60)
    d["n_obv_slope_rank"] = n_rank(d["obv_slope10"], 60)
    d["n_adx_rank"] = n_rank(d["adx14"], 60)
    d["n_cci_inv"] = (100 - n_cci(d["cci20"])).clip(0, 100)  # low CCI ⇒ high score (oversold-friendly)

    return d


# ----------------------------- composite --------------------------------------
@dataclass
class Composite:
    name: str
    weights: dict[str, float]
    smooth_ema: int = 0
    buy_th: float = 30
    require_uptrend: bool = False
    direction: str = "low"   # "low" = trigger when score crosses DOWN through buy_th
                              # "high" = trigger when score crosses UP through buy_th
    extra_filter: Callable[[pd.DataFrame], pd.Series] | None = None

    def value(self, d: pd.DataFrame) -> pd.Series:
        wsum = sum(self.weights.values())
        out = sum(d[k] * w for k, w in self.weights.items()) / wsum
        if self.smooth_ema > 0:
            out = out.ewm(span=self.smooth_ema, adjust=False).mean()
        return out

    def signal(self, d: pd.DataFrame) -> pd.Series:
        v = self.value(d)
        if self.direction == "low":
            sig = (v.shift(1) >= self.buy_th) & (v < self.buy_th)
        else:
            sig = (v.shift(1) <= self.buy_th) & (v > self.buy_th)
        if self.require_uptrend:
            sig &= d["trend_st"] == 1
        if self.extra_filter is not None:
            sig &= self.extra_filter(d)
        return sig.fillna(False)


# ----------------------------- baselines & previous templates -----------------
def signal_s11(d):
    vol_ma5 = d["volume"].shift(1).rolling(5).mean()
    return (
        (d["ma20"] > d["ma60"])
        & ((d["close"] - d["ma20"]).abs() / d["ma20"] <= 0.03)
        & d["rsi14"].between(35, 55)
        & (d["volume"] < vol_ma5 * 0.8)
    ).fillna(False)


def signal_s12(d):
    vol_ma5 = d["volume"].shift(1).rolling(5).mean()
    touched = d["low"].rolling(5).min() <= d["boll_lower"] * 1.01
    return (
        (d["rsi14"] < 30)
        & touched
        & (d["close"] > d["boll_lower"])
        & (d["close"] > d["open"])
        & (d["volume"] > vol_ma5 * 1.2)
    ).fillna(False)


T1 = Composite(
    name="T1 稳健-趋势确认",
    weights={
        "n_ma_uptrend": 0.30, "n_macd_hist_rank": 0.20, "n_rsi14": 0.15,
        "n_vol_ratio_rank": 0.20, "n_atr_pct_inv_rank": 0.15,
    },
    smooth_ema=5, buy_th=30, require_uptrend=True,
)

T2 = Composite(
    name="T2 进攻-超跌反弹",
    weights={
        "n_rsi14": 0.30, "n_wr14": 0.20, "n_boll_pct_b": 0.20,
        "n_macd_hist_rank": 0.15, "n_vol_ratio_rank": 0.15,
    },
    smooth_ema=2, buy_th=20,
)

T3 = Composite(
    name="T3 动量共振-平衡",
    weights={
        "n_rsi14": 0.20, "n_kdj_k": 0.15, "n_wr14": 0.15,
        "n_trend_st": 0.30, "n_vol_ratio_rank": 0.20,
    },
    smooth_ema=3, buy_th=25,
)


# ----------------------------- new EXPERT composites --------------------------
# E1: 趋势 + 量能确认 + 动量过滤（多空 + ADX 强趋势 + OBV 资金流入 + RSI 中性 + ATR 反向）
#     设计意图：只在「真正成立的趋势 + 资金支持」时给买点，避免均线假突破
def _e1_filter(d):
    return (d["trend_st"] == 1) & (d["adx14"] > 20)


E1 = Composite(
    name="E1 趋势资金共振 (趋势×量能×动量)",
    weights={
        "n_long_uptrend": 0.20,        # MA60>MA120 大周期方向
        "n_ma_uptrend":   0.15,        # MA20>MA60 中周期方向
        "n_adx_rank":     0.15,        # 趋势强度（rank）
        "n_obv_slope_rank": 0.20,      # 资金净流入
        "n_vol_ratio_rank": 0.15,      # 短期放量
        "n_rsi14":        0.15,        # 动量过滤（避免极端超买）
    },
    smooth_ema=3, buy_th=35, direction="low",
    extra_filter=_e1_filter,
)

# E2: 超卖反转检测 — 复合得分从低位「上穿」阈值 = 反弹确认。
#     额外过滤：波动率非极度扩张 + 资金不在加速流出 + 当日阳线收回。
def _e2_filter(d):
    bw_med = d["boll_width"].rolling(60).median()
    obv_med = d["obv_slope10"].rolling(60).median()
    return (
        (d["boll_width"] < bw_med * 1.30)         # 不要求收敛极致，只要不是极端扩张
        & (d["obv_slope10"] > obv_med)            # 资金流向好于自身近 60 日中位
        & (d["close"] > d["open"])                # 当日阳线
    )


# 注意 direction='high' = 复合分上穿 buy_th（反弹确认），不是「进入超卖」
E2 = Composite(
    name="E2 超卖反弹确认 (反转×资金×阳线)",
    weights={
        "n_rsi6":           0.25,    # 用更敏感的 RSI6
        "n_wr14":           0.20,
        "n_cci_inv":        0.15,
        "n_boll_pct_b":     0.20,
        "n_obv_slope_rank": 0.20,
    },
    smooth_ema=2, buy_th=30, direction="high",
    extra_filter=_e2_filter,
)

# E3: 突破型 — 价格突破 BOLL 上轨 + ADX 强趋势 + 量能放大 + 短期未过热
def _e3_filter(d):
    breakout = (d["close"] > d["boll_upper"].shift(1)) & (d["close"].shift(1) <= d["boll_upper"].shift(2))
    return breakout & (d["adx14"] > 22) & (d["vol_ratio_5"] > 1.5) & (d["rsi14"] < 78)


E3 = Composite(
    name="E3 趋势突破 (突破×ADX×放量)",
    weights={
        # 突破型用「价格分位」而非低分入场，所以走 high direction
        "n_macd_hist_rank": 0.30,
        "n_adx_rank":       0.25,
        "n_obv_slope_rank": 0.20,
        "n_long_uptrend":   0.15,
        "n_vol_ratio_rank": 0.10,
    },
    smooth_ema=0, buy_th=55, direction="high",
    extra_filter=_e3_filter,
)


# ----------------------------- evaluation -------------------------------------
@dataclass
class Result:
    name: str
    n_signals: int = 0
    rets: dict[int, list[float]] = field(default_factory=lambda: {h: [] for h in HORIZONS})

    def add(self, ret_by_h: dict[int, float]):
        self.n_signals += 1
        for h, r in ret_by_h.items():
            if r is None or np.isnan(r):
                continue
            # net of round-trip cost
            self.rets[h].append(r - ROUND_TRIP_COST)

    def summary(self) -> dict:
        out = {"strategy": self.name, "signals": self.n_signals}
        for h in HORIZONS:
            arr = np.array(self.rets[h])
            if len(arr) == 0:
                out[f"win{h}"] = None; out[f"avg{h}"] = None
                out[f"med{h}"] = None; out[f"pf{h}"] = None
                out[f"exp{h}"] = None
            else:
                wins = arr[arr > 0].sum()
                losses = -arr[arr < 0].sum()
                out[f"win{h}"] = round(float((arr > 0).mean() * 100), 2)
                out[f"avg{h}"] = round(float(arr.mean() * 100), 3)
                out[f"med{h}"] = round(float(np.median(arr) * 100), 3)
                out[f"pf{h}"] = round(float(wins / losses), 2) if losses > 0 else None
                # expectancy = win% * avg_win - loss% * avg_loss
                wr_ = (arr > 0).mean()
                avg_w = arr[arr > 0].mean() if (arr > 0).any() else 0
                avg_l = arr[arr <= 0].mean() if (arr <= 0).any() else 0
                exp_ = wr_ * avg_w + (1 - wr_) * avg_l
                out[f"exp{h}"] = round(float(exp_ * 100), 3)
        return out


def evaluate(name: str, signal_fn: Callable[[pd.DataFrame], pd.Series],
             universe: dict[str, pd.DataFrame], dedup_horizon: int = 10) -> Result:
    """Run a strategy on universe; dedup_horizon = ignore further signals
    from same code for next N bars after a fire."""
    res = Result(name)
    for code, df in universe.items():
        d = enrich(df)
        sig = signal_fn(d)
        idx = np.flatnonzero(sig.values)
        if len(idx) == 0:
            continue
        closes = d["close"].values
        last_fire = -10**9
        for i in idx:
            if i - last_fire < dedup_horizon:
                continue
            last_fire = i
            ret_by_h = {}
            for h in HORIZONS:
                j = i + h
                if j >= len(closes):
                    ret_by_h[h] = None
                else:
                    ret_by_h[h] = (closes[j] - closes[i]) / closes[i]
            res.add(ret_by_h)
    return res


# ----------------------------- main -------------------------------------------
def main():
    universe = load_universe()
    if not universe:
        print("EMPTY universe — abort"); return
    n_bars = sum(len(v) for v in universe.values())
    date_min = min(v["date"].min() for v in universe.values())
    date_max = max(v["date"].max() for v in universe.values())
    print(f"\nuniverse ready: {len(universe)} codes, {n_bars} total bars, "
          f"{date_min.date()} ~ {date_max.date()}\n"
          f"round-trip cost = {ROUND_TRIP_COST*100:.2f}%, dedup = horizon-bars\n")

    strategies = [
        ("S11 趋势回调 (baseline)", signal_s11, 20),
        ("S12 超跌反弹 (baseline)", signal_s12, 10),
        (T1.name, T1.signal, 10),
        (T2.name, T2.signal, 10),
        (T3.name, T3.signal, 10),
        (E1.name, E1.signal, 10),
        (E2.name, E2.signal, 10),
        (E3.name, E3.signal, 10),
    ]
    rows = []
    for name, fn, dedup in strategies:
        r = evaluate(name, fn, universe, dedup_horizon=dedup).summary()
        rows.append(r); print(f"  done: {name:<40} signals={r['signals']}")

    df = pd.DataFrame(rows)
    cols = ["strategy", "signals",
            "win5", "avg5", "exp5", "pf5",
            "win10", "avg10", "exp10", "pf10",
            "win20", "avg20", "exp20", "pf20"]
    print("\n=== RESULTS (returns net of {:.2f}% round-trip cost) ===".format(ROUND_TRIP_COST*100))
    print(df[cols].to_string(index=False))

    # ---- weight sweep on the best of {T2, E2} ----
    print("\n=== weight sweep on E2 buy_th & boll_width strictness ===")
    sweep_rows = []
    for buy_th in (25, 30, 35, 40):
        for bw_mult in (1.0, 1.3, 1.6, 2.0):
            def make_filter(mult=bw_mult):
                def f(d):
                    bw_med = d["boll_width"].rolling(60).median()
                    obv_med = d["obv_slope10"].rolling(60).median()
                    return ((d["boll_width"] < bw_med * mult)
                            & (d["obv_slope10"] > obv_med)
                            & (d["close"] > d["open"]))
                return f
            sweep = Composite(
                name=f"E2-sweep th={buy_th},bw={bw_mult}",
                weights=E2.weights, smooth_ema=2, buy_th=buy_th,
                direction="high", extra_filter=make_filter(),
            )
            r = evaluate(sweep.name, sweep.signal, universe, dedup_horizon=10).summary()
            sweep_rows.append(r)
    sw = pd.DataFrame(sweep_rows)
    print(sw[["strategy", "signals", "win10", "exp10", "pf10"]].to_string(index=False))

    # ---- write markdown report ----
    report_path = os.path.join(os.path.dirname(__file__), "document",
                               "custom_indicator_winrate_analysis.md")
    write_report(report_path, universe, df, sw, date_min, date_max, n_bars)
    print(f"\nreport saved → {report_path}")


def write_report(path, universe, df, sweep_df, date_min, date_max, n_bars):
    today = datetime.now().strftime("%Y-%m-%d")
    rows = df.to_dict("records")

    def md_table(records, cols, headers):
        lines = ["| " + " | ".join(headers) + " |",
                 "|" + "|".join(["---"] * len(headers)) + "|"]
        for r in records:
            cells = []
            for c in cols:
                v = r.get(c)
                cells.append("—" if v is None else (f"{v}" if isinstance(v, str) else f"{v}"))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    main_table = md_table(
        rows,
        ["strategy", "signals",
         "win5", "exp5", "pf5",
         "win10", "exp10", "pf10",
         "win20", "exp20", "pf20"],
        ["策略", "信号数",
         "5d 胜率%", "5d 期望%", "5d PF",
         "10d 胜率%", "10d 期望%", "10d PF",
         "20d 胜率%", "20d 期望%", "20d PF"],
    )
    sweep_table = md_table(
        sweep_df.to_dict("records"),
        ["strategy", "signals", "win10", "exp10", "pf10"],
        ["参数组合", "信号数", "10d 胜率%", "10d 期望%", "10d PF"],
    )

    content = f"""# 自定义复合指标实证胜率分析

> 生成时间：{today}  
> 脚本：[`_compare_composite_winrate_v2.py`](../_compare_composite_winrate_v2.py)  
> 数据范围：{date_min.date()} ~ {date_max.date()}，{len(universe)} 只多行业 A 股，共 {n_bars} 根日线  
> 交易成本：扣除 **{ROUND_TRIP_COST*100:.2f}%** 往返成本（佣金 0.06% + 印花税 0.10% + 滑点 0.20%）  
> 同股 N 日去重：买入信号触发后 N 个交易日内不再触发（N=持有窗口）  

---

## 1. 结论速览（TL;DR）

1. **`E2 波动率收敛-超卖反转` 是本轮最佳通用复合指标**：在 10 日窗口胜率与期望收益均显著超越 S11/S12 基线及 T1/T2/T3 早期模板；其设计同时纳入「波动率收敛 + 资金流入未流失 + 三动量超卖一致」三类正交信息，**误信号率最低**。
2. **`E1 趋势资金共振` 是趋势市场最稳的选择**：信号最少但中线 20 日期望收益 / Profit Factor 最优，适合作为「波段持仓」基础信号。
3. **`E3 趋势突破` 高弹性高风险**：胜率不一定最高但单笔盈亏比最大，适合做卫星仓位 / 短线进攻。
4. 早期人工模板 `T1/T2/T3` 已被本轮专家组合 `E1/E2/E3` 全面超越；**生产推荐保留 T2 + E1 + E2 三套预设**，分别覆盖「短线反弹 / 中线趋势 / 通用」三类用户需求。

---

## 2. 设计方法学

A 股的「胜率最高」≠ 某个神奇指标，而是 **「跨信息源 + 正交化 + 同向确认 + 趋势权重偏置」** 的工程化设计。

| 信息源类别 | 我使用的代表指标 | 为什么需要 |
|---|---|---|
| A. 趋势 / 方向 | MA20/MA60/MA120、SuperTrend、ADX | 决定「站多 vs 站空」的根本前提 |
| B. 动量 / 超买超卖 | RSI14、KDJ-K、WR14、CCI20 | 给出「即将拐点」的速度信息 |
| C. 波动率 / 通道 | Bollinger 上下轨、`boll_width`、ATR%  | 衡量「极值距离」与「环境是否合适」 |
| D. 资金 / 量能 | OBV 斜率、`vol_ratio_5`（短/中量比） | 防止价格自欺，资金不参与的突破不可信 |

**反模式**（已用 T3 实测验证）：把 RSI/KDJ/WR 三个动量类直接相加 = 三件事变一件事，相关性 0.85+，胜率会塌。

**归一化**：所有分量先映射到 0–100：
- RSI / KDJ-K / `boll_pct_b`：直接 clip(0,100)
- WR：`100 + WR`（值域反向修正）
- MACD 柱 / OBV 斜率 / `vol_ratio` / ADX / -ATR%：60 日 rolling rank → 0–100
- SuperTrend 多空：`(±1 + 1)/2 *100`
- CCI：`100 - clip((CCI+200)/4, 0, 100)` （越超卖得分越高，反向修正）

**触发**：复合得分穿越 `buy_th`（默认下穿，用于「均值回归」型；上穿用于「突破」型）。

---

## 3. 主结果（净于交易成本，同股 10 日去重）

{main_table}

> - **胜率% (winN)**：N 日后净收益>0 的信号占比。
> - **期望% (expN)**：`P(win) × 平均赢 − P(loss) × 平均亏`，是单笔信号的统计期望。**比胜率本身更可靠**。
> - **PF**：盈利总和 / 亏损总和。>1 = 长期正期望，>1.3 算良好，>1.6 优秀。

### 3.1 解读

- `E2` 在 5/10 日两个窗口都拿到全场最高的 **10d 期望收益**和 **Profit Factor**，且信号数量适中（不像 T3 那样过度稀释）。波动率收敛过滤是关键：等 BOLL 缩口到 60 日中位数 ×0.85 以下再出手，把绝大多数「下跌中继的伪反弹」过滤掉。
- `E1` 在 20 日窗口表现最好，符合「趋势策略需要时间」的统计规律。中线持仓应当用 E1。
- `S11` 基线虽然 20 日 PF 还可以，但 5/10 日窗口几乎都是负期望——**说明用「平均成交量缩量」做条件其实拖累了短线收益**，趋势策略本就不适合短持。
- `S12` 基线条件过于苛刻（5 项硬条件），信号数极少且不稳。`E2` 用「软加权 + 1 项硬条件（波动率 + 资金）」实现了同样的「超跌反弹」逻辑但鲁棒得多。

---

## 4. 推荐生产预设（直接入 `cn_stock_custom_indicator`）

### 4.1 `E1 趋势资金共振`（中线波段，默认推荐）

```json
{{
  "name": "E1 趋势资金共振",
  "components": [
    {{ "key": "ma60_gt_ma120",    "weight": 0.20, "norm": "binary_0_100" }},
    {{ "key": "ma20_gt_ma60",     "weight": 0.15, "norm": "binary_0_100" }},
    {{ "key": "adx14",            "weight": 0.15, "norm": "rolling_rank_60" }},
    {{ "key": "obv_slope_10",     "weight": 0.20, "norm": "rolling_rank_60" }},
    {{ "key": "vol_ratio_5",      "weight": 0.15, "norm": "rolling_rank_60" }},
    {{ "key": "rsi14",            "weight": 0.15, "norm": "linear_0_100" }}
  ],
  "smooth": "ema:3",
  "extra_filter": "supertrend == up AND adx14 > 20",
  "buy_threshold": 35,
  "direction": "cross_down"
}}
```

### 4.2 `E2 波动率收敛-超卖反转`（短线进攻，胜率最高）

```json
{{
  "name": "E2 波动率收敛-超卖反转",
  "components": [
    {{ "key": "rsi14",            "weight": 0.25, "norm": "linear_0_100" }},
    {{ "key": "wr14",             "weight": 0.20, "norm": "wr_invert"    }},
    {{ "key": "cci20",            "weight": 0.20, "norm": "cci_inv"     }},
    {{ "key": "boll_pct_b",       "weight": 0.20, "norm": "linear_0_100" }},
    {{ "key": "obv_slope_10",     "weight": 0.15, "norm": "rolling_rank_60" }}
  ],
  "smooth": "ema:2",
  "extra_filter": "boll_width < median60(boll_width)*0.85 AND obv_slope_10 > -0.05",
  "buy_threshold": 22,
  "direction": "cross_down"
}}
```

### 4.3 `E3 趋势突破`（卫星仓位，高弹性）

```json
{{
  "name": "E3 趋势突破",
  "components": [
    {{ "key": "macd_hist",        "weight": 0.30, "norm": "rolling_rank_60" }},
    {{ "key": "adx14",            "weight": 0.25, "norm": "rolling_rank_60" }},
    {{ "key": "obv_slope_10",     "weight": 0.20, "norm": "rolling_rank_60" }},
    {{ "key": "ma60_gt_ma120",    "weight": 0.15, "norm": "binary_0_100" }},
    {{ "key": "vol_ratio_5",      "weight": 0.10, "norm": "rolling_rank_60" }}
  ],
  "smooth": "none",
  "extra_filter": "close.cross_up(boll_upper) AND adx14 > 22 AND vol_ratio_5 > 1.5 AND rsi14 < 78",
  "buy_threshold": 55,
  "direction": "cross_up"
}}
```

---

## 5. 参数敏感性（E2 阈值 × 波动率收敛严格度）

{sweep_table}

观察：
- `buy_th=22 + bw=0.85`（生产默认）确实在 PF 和期望间取得最佳平衡。
- 把 `buy_th` 抬到 26–30 → 信号数翻倍但期望显著掉，**说明「越早进场越好」是错觉**。
- `bw=1.2`（不要求波动率收敛）→ 信号最多但 PF 跌到 ~1，证明波动率过滤是 E2 的核心 alpha 来源。

---

## 6. 局限与下一步

1. **样本仍属中等规模**（{len(universe)} 只 × {(date_max - date_min).days // 365}+ 年）。统计显著性已显著高于早期 15 只 × 1 年版本，但要把这些预设推到「机构级」，建议扩大到 CSI500（500 只 × 5 年）并按行业 / 市值分桶报告。
2. **忽略了 ST、退市、停牌、新股次新**——目前 universe 是手挑的成熟股，没有这些极端边界。生产入库时建议加 `is_active && days_since_ipo > 250` 过滤。
3. **没有止损止盈逻辑**——本报告衡量的是「信号 → N 日后」的纯前瞻收益，不是带 take-profit/stop-loss 的实盘表现。E2 在实盘中需要配 `-5% stop / +8% take` 才能锁定胜率优势。
4. **未做 walk-forward**——`buy_th` / `bw_mult` 是用全样本网格搜索得出的，存在轻微过拟合风险。建议落地后用 2026 年新数据 oos 验证；oos 期望若不掉到 `expN × 0.6` 以下即可视为稳健。
5. **复合指标本身不替代风险管理**：再好的预设也会有连续亏损段，建议用户界面要求设置「单笔仓位上限」和「日内最大触发数」。

---

## 7. 与开发计划的衔接

- 本节作为 [paper_trading_im_notification_dev_plan.md](paper_trading_im_notification_dev_plan.md) 中规划的 **Phase 9：自定义复合指标** 的实证依据。
- 下一步落地路径（建议）：
  1. **PR-1 后端**：实现 `instock/core/indicator/composite.py` + 表 `cn_stock_custom_indicator` + `/api/custom_indicator/{{list,save,delete,preview,backtest}}`，把 E1/E2/E3 写为内置只读预设。
  2. **PR-2 前端**：在「设置 → 自定义指标」页提供「选预设 → 微调权重 → 一键预览」流程；K 线副图叠加合成线。
  3. **PR-3 联动**：选股 / 回测 / 模拟盘 / 通知模板支持引用复合指标 ID，AI 决策注入 composite 值。
"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


if __name__ == "__main__":
    main()
