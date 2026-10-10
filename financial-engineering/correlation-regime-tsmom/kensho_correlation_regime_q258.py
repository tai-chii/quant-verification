#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q258: 15銘柄の直近60日平均ペア相関が高い月は順張り束のシャープが低いか（相関レジーム）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q258 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Graham Capital「Market Diversification」2017、CME「Return dispersion…」（解説）、知見 Q207（危機の月の束の相関）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "trend following performance when cross-asset correlation is high diversification regime empirical CTA"）:
  見つかったもの: Graham Capital 2017、CME Group 教育資料、HedgeNordic・Substack（ブログ）。
  未確認: 運用会社の資料のみで検定なし。15 銘柄 CFD・翌月・ブロック並べ替え帰無で事前固定の判定は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 15 銘柄の日次リターンの直近 60 日の平均ペア相関 ρ̄ が拡大窓中央値より高い月は、翌月の束（σ60 規模調整・等加重）のシャープ（月内の日次から）が低い。D=高−低<0。

【データ】
15銘柄 D1_fromH1（2011-09〜 全銘柄がそろう期間）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
ρ̄_t: 月末時点の 60 日ペア相関の平均（105 組）。高／低: 拡大窓（最短 24 か月）の中央値で分ける。翌月の束の月次シャープ = 日次平均/日次標準偏差·√252。

【測るもの】
D（年単位 t は月を年に束ねる）、翌月の純損益の差。前半 2012–2016／後半 2017–。

【帰無】
高／低ラベルを 6 か月ブロックで年内並べ替え B=2000 → D の帰無分布 → z。

【判定（事前固定・変更禁止）】
前後半とも D<0 かつ z≤−2 → 支持。全期間 z>−1 → 棄却。それ以外 → 未確定。
多重比較: 判定は D の前後半 2 本。純損益の差は記述。

【捨てた案の数】
約3: 相関の変化率で分ける、同月（先読み）で分ける、絶対相関 0.3 の固定境界。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_correlation_regime_q258.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_correlation_regime_q258.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q258"
DEFAULT_B = 2000
L = 60
START = "2011-09-01"
VOL_TARGET = 0.10
MIN_MONTHS = 24
BLOCK_MONTHS = 6
PRE_START = 2012
PERIODS = (("all", 0, 9999), ("pre", PRE_START, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _load_long(sym, args, rng):
    """D1。smoke は 2011 年始まりの長い合成データ（前後半を通す）。"""
    if not args.smoke:
        return load_d1(sym, False, rng)
    df = _smoke_ohlc(sym, rng, n=4000, freq="D", start="2011-01-01")
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    return df


def _block_perm_within_year(rng, lab, year, block):
    out = lab.copy()
    for y in np.unique(year):
        idx = np.where(year == y)[0]
        out[idx] = block_perm(rng, lab[idx], block)
    return out


def _D_year(year, lab, val, y0, y1):
    """年ごとに 高−低 を取り、その平均（年単位）。高か低が無い年は除く。"""
    ds = []
    for y in np.unique(year):
        if y < y0 or y >= y1:
            continue
        m = year == y
        hi = val[m & (lab == 1)]; lo = val[m & (lab == 0)]
        if len(hi) and len(lo):
            ds.append(hi.mean() - lo.mean())
    return np.array(ds)


def run(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    rets = {}; scaled = {}
    for s in ok:
        df = _load_long(s, args, rng)
        c = df["close"].values.astype(float)
        pos = tsmom_pos(c, L); pnl = pnl_bp(pos, c, cost_bp_oneway(s, c))
        lr = np.r_[np.nan, np.diff(np.log(c))]
        sig = pd.Series(lr).rolling(L).std(ddof=1).values * math.sqrt(252)
        w = np.r_[np.nan, (VOL_TARGET / sig)[:-1]]
        rets[s] = pd.Series(df["ret"].values, index=df["time"].values)
        scaled[s] = pd.Series(w * pnl, index=df["time"].values)
    R = pd.concat(rets, axis=1); R = R[R.index >= pd.Timestamp(START)].dropna(how="all")
    P = pd.concat(scaled, axis=1); P = P[P.index >= pd.Timestamp(START)]
    bund = P.mean(axis=1, skipna=True).dropna()
    ym_b = pd.PeriodIndex(bund.index, freq="M")
    g = bund.groupby(ym_b)
    monthly = pd.DataFrame({"sharpe": g.apply(lambda x: sharpe_ann(x.values)), "pnl_bp": g.mean(), "n_days": g.size()})
    # 月末時点の 60 日平均ペア相関
    Rv = R.values; dates = R.index
    ym_r = pd.PeriodIndex(dates, freq="M")
    month_end_idx = pd.Series(np.arange(len(dates)), index=ym_r).groupby(level=0).last()
    rho = {}
    for per_, i in month_end_idx.items():
        if i + 1 < L:
            continue
        win = R.iloc[i + 1 - L:i + 1]
        win = win.dropna(axis=1, thresh=int(L * 0.8))
        if win.shape[1] < 3:
            continue
        cm = win.corr().values
        iu = np.triu_indices(cm.shape[0], 1)
        v = cm[iu]; v = v[np.isfinite(v)]
        if len(v):
            rho[per_] = float(v.mean())
    rho = pd.Series(rho).sort_index()
    med = rho.expanding(MIN_MONTHS).median()
    lab_cur = pd.Series(np.where(rho > med, 1.0, np.where(rho <= med, 0.0, np.nan)), index=rho.index)
    # 翌月に当てる
    nxt = pd.DataFrame({"rho": rho, "lab": lab_cur})
    nxt.index = nxt.index + 1
    m = monthly.join(nxt, how="inner").dropna(subset=["lab", "sharpe"])
    m = m[m["n_days"] >= 10]
    m["year"] = m.index.year
    year = m["year"].values.astype(int); lab = m["lab"].values.astype(int); sh = m["sharpe"].values.astype(float); pl = m["pnl_bp"].values.astype(float)
    obs = {pn: _D_year(year, lab, sh, y0, y1) for pn, y0, y1 in PERIODS}
    null = {pn: [] for pn, _, _ in PERIODS}
    for b in range(args.B):
        lp = _block_perm_within_year(rng, lab, year, BLOCK_MONTHS)
        for pn, y0, y1 in PERIODS:
            d = _D_year(year, lp, sh, y0, y1)
            null[pn].append(float(d.mean()) if len(d) else np.nan)
    summary = {}
    for pn, y0, y1 in PERIODS:
        sub = m[(m["year"] >= y0) & (m["year"] < y1)]
        d = obs[pn]; dp = _D_year(year, lab, pl, y0, y1)
        Dm = float(d.mean()) if len(d) else float("nan")
        z, pct = z_of(Dm, null[pn])
        hi = sub[sub["lab"] == 1]; lo = sub[sub["lab"] == 0]
        summary[pn] = {"n_months": int(len(sub)), "n_hi": int(len(hi)), "n_lo": int(len(lo)), "n_years": int(len(d)),
                       "D_sharpe_hi_minus_lo": f(Dm), "t": f(tstat(d)), "z": f(z), "pct": f(pct),
                       "D_pooled_months": f(hi["sharpe"].mean() - lo["sharpe"].mean()) if len(hi) and len(lo) else None,
                       "sharpe_hi": f(hi["sharpe"].mean()) if len(hi) else None, "sharpe_lo": f(lo["sharpe"].mean()) if len(lo) else None,
                       "pnl_diff_bp_per_day": f(dp.mean()) if len(dp) else None, "pnl_t": f(tstat(dp)),
                       "rho_mean": f(sub["rho"].mean())}
    if any(summary[pn][k] is None for pn in ("all", "pre", "post") for k in ("D_sharpe_hi_minus_lo", "z")):
        verdict = "未確定: 計算できない"
    elif all(summary[pn]["D_sharpe_hi_minus_lo"] < 0 and summary[pn]["z"] <= -2 for pn in ("pre", "post")):
        verdict = "支持: 相関の高い月の翌月は束のシャープが低い（前後半とも D<0・z≤−2）"
    elif summary["all"]["z"] > -1:
        verdict = "棄却: 全期間 z>−1"
    else:
        verdict = "未確定"
    res = {"question": "15銘柄の直近60日平均ペア相関が拡大窓中央値より高い月は、翌月の順張り束のシャープが低いか（D=高−低<0）",
           "settings": {"L": L, "start": START, "vol_target": VOL_TARGET, "min_months_for_median": MIN_MONTHS, "block_months": BLOCK_MONTHS,
                        "pre": f"{PRE_START}–{SPLIT_YEAR - 1}", "post": f"{SPLIT_YEAR}–", "B": args.B,
                        "rho": "月末時点・直近 60 営業日の日次リターンの相関行列の上三角平均（その窓に 48 日以上ある銘柄）",
                        "label": "ρ̄ > 拡大窓（最短 24 か月）の中央値 → 高（1）。翌月の束に当てる",
                        "bundle": "各銘柄 pnl_bp×(目標/年率σ60) の等加重、月次シャープ = 日次 mean/std·√252",
                        "null": "高／低ラベルを 6 か月ブロックで年内並べ替え", "stat_for_z": "年ごとの（高−低）の平均（年単位）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は D の前後半 2 本。純損益の差は記述。"}
    out = m.reset_index().rename(columns={"index": "month"}); out["month"] = out["month"].astype(str)
    return res, {"monthly": out}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
