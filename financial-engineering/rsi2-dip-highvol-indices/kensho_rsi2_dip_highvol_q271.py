#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q271: US500・USTECH の RSI2 押し目買いは高ボラのときだけコスト後に残るか（QuanterLab 2026-3 の追試・CFD 日足）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q271 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- [[ブログQuanterLab2026-1_SP500のRSI2押し目買いの20日後の上昇はほとんどが市場全体の分]]、[[ブログQuanterLab2026-2_RSI2押し目買いは片道0.05パーセントのコストでSPYとの差が消えた]]、[[ブログQuanterLab2026-3_VIXが高いときだけの押し目買いはコスト後も残ったが差の大半は2020年からの3年間]]、知見「為替の押し目の逆張りは荒れた相場に限っても…戻らない」
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "RSI2 dip buying S&P 500 conditional on high volatility regime after costs backtest 2010-2025"）:
  見つかったもの: AQR「Hold the Dip」、SentimenTrader・CMC（ブログ）、Coutts。
  未確認: QuanterLab 2026-3 の VIX 条件を Parkinson σ で代用し CFD 2 指数・前後半・月ブロック帰無で追試する形は未確認（追試）。

【仮説（測る前に固定）】
H: RSI(2)<10 で買い・RSI(2)>70 で手仕舞いの押し目買いは、σ20（Parkinson 日次ボラ・年率）が拡大窓の上位 3 分の 1 の局面に限ると、コスト後の建玉あたり純損益 [bp] が正で、全局面より高い。

【データ】
US500・USTECH D1_fromH1（2011-09〜2026-06）。VIX は手元に無いので Parkinson σ20 で代用（差し替え用 `--vix_csv`）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
A: 全局面の RSI2 押し目買い。B: 高ボラ局面に限る。純損益 = 保有中の日次リターンの和 − 往復コスト [bp]。買い持ちの同期間（露出調整）も記述。

【測るもの】
B の年単位 t と建玉数、B−A の差（建玉あたり）。前後半 2012–2016／2017–、2020–2022 を除いた副次。

【帰無】
高ボラ局面ラベルを暦月ブロックで年内並べ替え B=1000 → B の純損益の帰無分布 → z。

【判定（事前固定・変更禁止）】
2 指数とも前後半とも B>0 かつ z≥2 → 支持。両方 全期間 z<1 → 棄却。それ以外 → 未確定（2020–2022 を除いた結果を併記）。
多重比較: 判定は 2 指数 × 前後半 = 4 本。A との差・露出調整は記述。

【捨てた案の数】
約3: VIX 実データ（無い）、SPY 現物（CFD で代用）、RSI(3)。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_rsi2_dip_highvol_q271.py            （B=1000・小（B=1000・30 秒））
      python3 kensho_rsi2_dip_highvol_q271.py --smoke    （合成データで経路の確認。判定には使わない）
"""
import argparse
import datetime as _dt
import itertools
import json
import math
import os
import sys
import unicodedata
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # ワークスペース


def _p(*parts):
    """macOS 共有の NFD 名に対応（NFC で無ければ NFD で探す）。"""
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")
FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
FX6 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD"]  # ドル建て先進国（Q019・Q054 と同じ）
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
CRYPTO = ["BTCUSD", "ETHUSD", "XRPUSD", "LTCUSD", "ADAUSD", "BCHUSD", "XLMUSD", "EOSUSD", "LNKUSD", "DOTUSD", "SOLUSD"]
# 往復コスト（価格単位・段階1の保守値。Q136〜Q190 と同じ表）
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
CRYPTO_COST_RT_REL = 30e-4  # 暗号資産: 往復 30bp の仮置き（Q152 と同じ）
SPLIT_YEAR = 2017
SEED = 20261010
GROUPS = {"all15": SYMS, "fx8": FX8, "trend7": TREND7}


# ----------------------------------------------------------------------------- データ
def _read(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return df


def load_d1(sym, smoke=False, rng=None):
    """UTC 日足（D1_fromH1）。値動きのない足（high==low）は除く。列: time, open, high, low, close, ret, year"""
    if smoke:
        df = _smoke_ohlc(sym, rng, n=2600, freq="D", start="2015-01-01")
    else:
        df = _read(os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv"))
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    df["year"] = df["time"].dt.year
    return df


def load_csv(name, smoke=False, rng=None, freq="h", n=20000, start="2015-01-01"):
    """任意の data_<name>.csv（H1/H4/M15/yahoo/ask）。"""
    if smoke:
        return _smoke_ohlc(name, rng, n=n, freq=freq, start=start)
    return _read(os.path.join(DATA_DIR, f"data_{name}.csv"))


def load_h1(sym, smoke=False, rng=None, n=60000, start="2015-01-01"):
    """UTC 1時間足（H1_dukascopy）。値動きのない足は除く。列: time, open, high, low, close, volume, ret, year, hour, dow"""
    df = load_csv(f"{sym}_H1_dukascopy", smoke, rng, freq="h", n=n, start=start)
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    df["year"] = df["time"].dt.year
    df["hour"] = df["time"].dt.hour
    df["dow"] = df["time"].dt.dayofweek
    return df


def h1_to_d1(h1, cutoff_hour=0):
    """H1 を「cutoff_hour（UTC）始まり」の日足に束ねる。日付ラベルは区間の開始日。"""
    t = h1["time"] - pd.Timedelta(hours=cutoff_hour)
    key = t.dt.floor("D")
    g = h1.groupby(key)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                      "volume": g["volume"].sum() if "volume" in h1 else g["close"].size(), "nbars": g["close"].size()})
    d.index.name = "time"; d = d.reset_index()
    d = d[(d["high"] != d["low"]) & (d["nbars"] >= 6)].reset_index(drop=True)
    d["ret"] = d["close"].pct_change(); d["year"] = d["time"].dt.year
    return d


def _smoke_ohlc(sym, rng, n, freq, start):
    """合成データ（GBM）。判定には使わない。"""
    rng = rng or np.random.default_rng(SEED)
    t = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(0.0001, 0.006, n)
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    v = np.abs(rng.lognormal(8, 0.5, n))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v})


def exists_sym(sym, kind="D1_fromH1"):
    return os.path.exists(os.path.join(DATA_DIR, f"data_{sym}_{kind}.csv"))


def cost_bp_oneway(sym, close, rel=None):
    """片道コスト [bp]（価格に対する比）。rel を渡せば相対コスト（往復）を使う。"""
    if rel is not None:
        return np.full(len(close), rel / 2 * 1e4)
    return COST_RT[sym] / 2 / np.asarray(close, float) * 1e4


# ----------------------------------------------------------------------------- 合図と損益
def tsmom_pos(close, L):
    c = np.asarray(close, float)
    s = np.zeros(len(c))
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def sma_pos(close, n):
    c = pd.Series(np.asarray(close, float))
    m = c.rolling(n).mean().values
    s = np.sign(c.values - m)
    s[np.isnan(m)] = 0.0
    return s


def atr(high, low, close, n=20):
    h = np.asarray(high, float); l = np.asarray(low, float); c = np.asarray(close, float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    return pd.Series(tr).rolling(n).mean().values


def rsi(close, n):
    c = pd.Series(np.asarray(close, float))
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).values


def pnl_bp(pos, close, cost_oneway_bp):
    """pos[t] は t の終値で決めて t+1 のリターンに効く。pnl[t+1] = pos[t]*ret[t+1]*1e4 − |pos[t]−pos[t−1]|*片道[bp]。先頭は 0。"""
    c = np.asarray(close, float); pos = np.asarray(pos, float)
    ret = np.zeros(len(c)); ret[1:] = c[1:] / c[:-1] - 1
    held = np.r_[0.0, pos[:-1]]
    prev = np.r_[0.0, held[:-1]]
    cost = np.abs(held - prev) * np.r_[0.0, cost_oneway_bp[:-1]]
    return held * ret * 1e4 - cost


# ----------------------------------------------------------------------------- 統計
def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def nw_t(x, lag=5):
    """Newey-West（Bartlett）の t。"""
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")
    e = x - x.mean()
    s = (e ** 2).sum()
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * (e[k:] * e[:-k]).sum()
    se = math.sqrt(max(s, 1e-300)) / n
    return float(x.mean() / se) if se > 0 else float("nan")


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    rx = np.array(pd.Series(x).rank().values, float); ry = np.array(pd.Series(y).rank().values, float)
    rx -= rx.mean(); ry -= ry.mean()
    d = math.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def max_drawdown(pnl):
    cum = np.cumsum(np.asarray(pnl, float)); peak = np.maximum.accumulate(cum)
    return float((cum - peak).min()) if len(cum) else float("nan")


def sharpe_ann(pnl, per_year=252):
    x = np.asarray(pnl, float); x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(per_year)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def qlike(s2_pred, r2):
    """QLIKE 損失（小さいほど良い）。r2: 実現分散、s2_pred: 予測分散。"""
    s2 = np.asarray(s2_pred, float); r2 = np.asarray(r2, float)
    m = np.isfinite(s2) & np.isfinite(r2) & (s2 > 0) & (r2 > 0)
    return float(np.mean(r2[m] / s2[m] - np.log(r2[m] / s2[m]) - 1)) if m.sum() > 2 else float("nan")


def z_of(obs, null):
    null = np.asarray(null, float); null = null[np.isfinite(null)]
    if len(null) < 3 or null.std(ddof=1) == 0 or not np.isfinite(obs):
        return float("nan"), float("nan")
    return float((obs - null.mean()) / null.std(ddof=1)), float((null < obs).mean())


def perm_within(rng, x, groups):
    """groups（例: 年）の中で x を並べ替える。"""
    x = np.asarray(x, float).copy(); g = np.asarray(groups)
    for v in np.unique(g):
        idx = np.where(g == v)[0]
        x[idx] = x[rng.permutation(idx)]
    return x


def block_perm(rng, x, block):
    """block 本ごとの塊を並べ替える（塊の中の順序は保つ）。"""
    x = np.asarray(x, float); n = len(x); nb = int(math.ceil(n / block))
    order = rng.permutation(nb)
    out = np.concatenate([x[b * block:(b + 1) * block] for b in order])
    return out[:n]


def circ_shift(rng, x, min_shift=1):
    """循環シフト（合図とリターンの対応を壊し、合図の自己相関は保つ）。"""
    x = np.asarray(x, float); n = len(x)
    k = int(rng.integers(min_shift, max(min_shift + 1, n - min_shift)))
    return np.roll(x, k)


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p); order = np.argsort(p); adj = np.empty(m)
    run = 0.0
    for i, k in enumerate(order):
        run = max(run, (m - i) * p[k]); adj[k] = min(1.0, run)
    return adj


def by_year_stats(df, col, year_col="year", y0=0, y1=9999):
    """年を単位にした平均と t（銘柄は年の中で平均してから）。df: year, sym, col。"""
    d = df[(df[year_col] >= y0) & (df[year_col] < y1)]
    if d.empty:
        return {"n_years": 0, "mean": float("nan"), "t": float("nan")}
    if "sym" in d.columns:
        yr = d.groupby([year_col, "sym"])[col].mean().groupby(level=0).mean()
    else:
        yr = d.groupby(year_col)[col].mean()
    yr = yr.dropna()
    return {"n_years": int(len(yr)), "mean": float(yr.mean()) if len(yr) else float("nan"), "t": tstat(yr.values)}


# ----------------------------------------------------------------------------- 入出力
def parse_args(default_B=300, extra=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=default_B, help="帰無の回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路の確認（判定に使わない）")
    ap.add_argument("--seed", type=int, default=SEED)
    if extra:
        extra(ap)
    return ap.parse_args()


def write_result(qid, res, smoke, extra_csv=None):
    os.makedirs(OUT, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = f"smoke_{qid}" if smoke else qid
    path = os.path.join(OUT, f"{pre}_result_{ts}.json")
    res = {"qid": qid, "smoke": smoke, "generated": ts, **res}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=_json_default)
    print("wrote", os.path.relpath(path, HERE))
    if extra_csv is not None:
        for name, df in extra_csv.items():
            cp = os.path.join(OUT, f"{pre}_{name}_{ts}.csv"); df.to_csv(cp, index=False); print("wrote", os.path.relpath(cp, HERE))
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, _dt.datetime, _dt.date)):
        return str(o)
    return str(o)


def f(x, nd=4):
    try:
        return None if x is None or not np.isfinite(x) else round(float(x), nd)
    except Exception:
        return None


def syms_available(syms, kind="D1_fromH1", smoke=False):
    if smoke:
        return list(syms), []
    ok = [s for s in syms if exists_sym(s, kind)]
    return ok, [s for s in syms if s not in ok]
# ============================================================================= 共通の土台ここまで
# ============================================================================= 共通の土台ここまで

QID = "Q271"
DEFAULT_B = 1000
START = "2012-01-01"
SYMS2 = ["US500", "USTECH"]
RSI_N, RSI_IN, RSI_OUT = 2, 10, 70
VOL_WIN, MIN_HIST, TOP_Q = 20, 250, 2.0 / 3.0
EXCL_YEARS = (2020, 2021, 2022)


def _extra(ap):
    ap.add_argument("--vix_csv", type=str, default=None, help="VIX の表（列 date,close）。Parkinson σ20 の代わりに高ボラ判定に使う")


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=4000, freq="D", start="2011-09-01")
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
        return df
    return load_d1(sym, False, rng)


def vol_series(df, args):
    """高ボラ判定に使う系列（既定: Parkinson σ20・年率）。--vix_csv なら VIX の終値を日付で合わせる。"""
    if args.vix_csv:
        v = pd.read_csv(args.vix_csv); v["date"] = pd.to_datetime(v["date"]).dt.normalize()
        s = pd.Series(v["close"].values, index=v["date"])
        return s.reindex(df["time"].dt.normalize()).ffill().values, "vix_csv"
    pk = (np.log(df["high"].values / df["low"].values)) ** 2 / (4 * math.log(2))
    s20 = np.sqrt(pd.Series(pk).rolling(VOL_WIN).mean().values * 252)
    return s20, "parkinson_sigma20_ann"


def high_vol_label(v):
    """t 日の値が t−1 までの拡大窓（最短 MIN_HIST）の上位 3 分の 1 か。"""
    s = pd.Series(v)
    thr = s.shift(1).expanding(min_periods=MIN_HIST).quantile(TOP_Q).values
    lab = (v >= thr) & np.isfinite(thr) & np.isfinite(v)
    return lab.astype(bool)


def rsi2_position(close):
    """RSI(2)<10 で買い（翌日から）、RSI(2)>70 で手仕舞い。pos[t] は t の終値で決める。"""
    r = rsi(close, RSI_N)
    pos = np.zeros(len(close))
    hold = 0.0
    for i in range(len(close)):
        if not np.isfinite(r[i]):
            pos[i] = hold; continue
        if hold == 0.0 and r[i] < RSI_IN:
            hold = 1.0
        elif hold == 1.0 and r[i] > RSI_OUT:
            hold = 0.0
        pos[i] = hold
    return pos


def trades_of(df, sym):
    """建玉ごとの表: entry_idx（合図の日）, exit_idx, days, gross_bp, cost_bp, net_bp, year（建玉の年）。"""
    pos = rsi2_position(df["close"].values)
    c = df["close"].values; cost1 = cost_bp_oneway(sym, c)
    ret_bp = np.r_[0.0, (c[1:] / c[:-1] - 1) * 1e4]
    rows = []
    i = 0; n = len(pos)
    while i < n:
        if pos[i] == 1.0 and (i == 0 or pos[i - 1] == 0.0):
            j = i
            while j + 1 < n and pos[j + 1] == 1.0:
                j += 1
            # 保有: i+1 ... j+1 のリターン（pos[i] は i+1 のリターンに効く）
            lo, hi = i + 1, min(j + 1, n - 1)
            if lo <= hi:
                gross = float(ret_bp[lo:hi + 1].sum())
                cost = float(cost1[i] + cost1[hi])
                rows.append({"sym": sym, "entry_idx": i, "exit_idx": hi, "entry_date": df["time"].iloc[i], "year": int(df["year"].iloc[i]),
                             "month": int(df["time"].iloc[i].month), "days": hi - lo + 1, "gross_bp": gross, "cost_bp": cost, "net_bp": gross - cost})
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(rows), pos


def month_block_perm_labels(rng, lab, years, months, B):
    """高ボラの日次ラベルを暦月ブロックのまま年内で並べ替えた B 本（B × n の bool）。"""
    out = np.empty((B, len(lab)), dtype=bool)
    for y in np.unique(years):
        idx = np.where(years == y)[0]
        mo = months[idx]
        blocks = [idx[mo == m] for m in np.unique(mo)]
        for b in range(B):
            order = rng.permutation(len(blocks))
            src = np.concatenate([blocks[k] for k in order])
            out[b, idx] = lab[src][:len(idx)]
    return out


def period_stats(tr, labcol, y0, y1, excl=None):
    d = tr[(tr["year"] >= y0) & (tr["year"] < y1)]
    if excl:
        d = d[~d["year"].isin(excl)]
    A = d; Bv = d[d[labcol]]
    sa = by_year_stats(A, "net_bp"); sb = by_year_stats(Bv, "net_bp")
    return A, Bv, sa, sb


def run(args, rng):
    syms, missing = syms_available(SYMS2, "D1_fromH1", args.smoke)
    summary = {}; tr_all = []
    for sym in syms:
        df = load_sym(sym, args, rng)
        v, vol_kind = vol_series(df, args)
        lab = high_vol_label(v)
        tr, pos = trades_of(df, sym)
        if tr.empty:
            summary[sym] = {"n_trades": 0}; continue
        tr["highvol"] = lab[tr["entry_idx"].values]
        bh_daily = float(np.nanmean(df["ret"].values[df["time"] >= pd.Timestamp(START)]) * 1e4)
        tr["bh_same_days_bp"] = tr["days"] * bh_daily  # 露出調整: 同じ日数の買い持ちの期待値（無条件の日次平均×日数）
        tr = tr[tr["entry_date"] >= pd.Timestamp(START)].reset_index(drop=True)
        tr_all.append(tr)
        years = df["year"].values; months = df["time"].dt.month.values
        labs_null = month_block_perm_labels(rng, lab, years, months, args.B)
        summary[sym] = {"vol_kind": vol_kind, "n_trades_A": int(len(tr)), "n_trades_B": int(tr["highvol"].sum()),
                        "frac_days_highvol": f(lab[df["time"] >= pd.Timestamp(START)].mean())}
        periods = {"all": ((0, 9999), None), "pre": ((0, SPLIT_YEAR), None), "post": ((SPLIT_YEAR, 9999), None),
                   "all_ex2020_2022": ((0, 9999), EXCL_YEARS), "post_ex2020_2022": ((SPLIT_YEAR, 9999), EXCL_YEARS)}
        for pn, ((y0, y1), excl) in periods.items():
            A, Bv, sa, sb = period_stats(tr, "highvol", y0, y1, excl)
            z = pct = float("nan")
            if len(A) >= 3 and sb["n_years"] >= 2:
                ent = A["entry_idx"].values; pnl = A["net_bp"].values; yrs = A["year"].values
                L = labs_null[:, ent]  # B × n_trades
                # 年×銘柄の平均を年で平均（建玉あり年のみ）
                yu = np.unique(yrs); My = (yrs[None, :] == yu[:, None]).astype(float)
                num = (L * pnl[None, :]) @ My.T; den = L.astype(float) @ My.T
                with np.errstate(invalid="ignore", divide="ignore"):
                    ym = np.where(den > 0, num / np.maximum(den, 1), np.nan)
                null = np.nanmean(ym, axis=1)
                z, pct = z_of(sb["mean"], null)
            summary[sym][pn] = {"n_A": int(len(A)), "n_B": int(len(Bv)), "n_years_B": sb["n_years"],
                                "B_net_mean_bp": f(sb["mean"]), "B_t": f(sb["t"]), "B_z": f(z), "B_pct": f(pct),
                                "A_net_mean_bp": f(sa["mean"]), "A_t": f(sa["t"]),
                                "B_minus_A_bp": f(Bv["net_bp"].mean() - A["net_bp"].mean()) if len(Bv) and len(A) else None,
                                "B_gross_mean_bp": f(Bv["gross_bp"].mean()) if len(Bv) else None,
                                "B_bh_same_days_bp": f(Bv["bh_same_days_bp"].mean()) if len(Bv) else None,
                                "A_bh_same_days_bp": f(A["bh_same_days_bp"].mean()) if len(A) else None,
                                "B_mean_days": f(Bv["days"].mean()) if len(Bv) else None}
    g = lambda s, p, k: summary.get(s, {}).get(p, {}).get(k)
    if len(syms) < 2:
        verdict = "未確定: 銘柄が揃わない（missing=%s）" % missing
    elif any(g(s, p, "B_z") is None for s in syms for p in ("all", "pre", "post")):
        verdict = "未確定: 計算できない（z が nan）"
    elif all(g(s, p, "B_net_mean_bp") > 0 and g(s, p, "B_z") >= 2 for s in syms for p in ("pre", "post")):
        verdict = "支持: 2 指数とも前後半とも B>0 かつ z≥2"
    elif all(g(s, "all", "B_z") < 1 for s in syms):
        verdict = "棄却: 2 指数とも全期間 z<1"
    else:
        ex = "・".join(f"{s}: ex2020-22 B={g(s, 'all_ex2020_2022', 'B_net_mean_bp')} z={g(s, 'all_ex2020_2022', 'B_z')}" for s in syms)
        verdict = "未確定: 支持にも棄却にも届かない（" + ex + "）"
    res = {"question": "US500・USTECH の RSI2 押し目買いは高ボラ（σ20 上位 1/3）のときだけコスト後に残るか",
           "settings": {"syms": SYMS2, "start": START, "rsi": [RSI_N, RSI_IN, RSI_OUT], "vol_window": VOL_WIN, "min_hist": MIN_HIST, "top_q": TOP_Q,
                        "vix_csv": args.vix_csv, "split_year": SPLIT_YEAR, "excl_years": EXCL_YEARS, "B": args.B,
                        "null": "高ボラの日次ラベルを暦月ブロックで年内並べ替え → B の純損益（年単位平均）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は 2 指数 × 前後半 = 4 本。A との差・露出調整・2020–2022 除外は記述。"}
    trades = pd.concat(tr_all, ignore_index=True) if tr_all else None
    return res, ({"trades": trades.drop(columns=["entry_idx", "exit_idx"])} if trades is not None else None)


def main():
    args = parse_args(default_B=DEFAULT_B, extra=_extra)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
