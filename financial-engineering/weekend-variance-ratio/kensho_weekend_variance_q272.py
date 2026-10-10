#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q272: 月曜（週末跨ぎ）のリターン分散は他の曜日の何倍か（取引時間 vs 暦時間・French・Roll 1986・15銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q272 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- French・Roll 1986（JFE・取引時間仮説）、知見 Q206（曜日効果）・Q212（暗号資産の週末）・Q209（夜間）、Purdue「Day of the Week Effects in Financial Futures」
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "French Roll 1986 trading time calendar time weekend variance Monday return variance ratio FX gold futures recent evidence"）:
  見つかったもの: French・Roll 1986 原論文、Boston Fed WP98-6、Purdue（McConnell）の金融先物の曜日効果、ASU「volatility during trading and nontrading hours」。
  未確認: CFD 15 銘柄の 2008–2026 で前後半・曜日並べ替え帰無で比を事前固定の判定にかける形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 15 銘柄の UTC 日足で、月曜（金曜終値→月曜終値・暦 3 日分）のリターン分散は火〜金の分散の 3 倍ではなく 1.0〜1.3 倍（取引時間仮説）。比 R = Var(月) / Var(火〜金)。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。暗号資産は 24/7 なので対照として BTC は別に書く。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
R を年×銘柄で推定（年内の分散比）。群別・全期間の中央値。

【測るもの】
R の年×銘柄の対数の平均と年単位 t（log R=0 に対し、log 3 に対し）、群別。前後半。

【帰無】
曜日ラベルを年内で並べ替え B=1000 → log R の帰無分布（=0 付近）→ z。

【判定（事前固定・変更禁止）】
all15 で log R の年単位平均が log 1.3 未満かつ log 3 に対し t≤−2 → 支持（取引時間仮説）。log R≥log 2 かつ z≥2 → 棄却（暦時間に近い）。それ以外 → 未確定。
多重比較: 判定は all15 の 1 本（2 つの帰無値）。群別・BTC は記述。

【捨てた案の数】
約3: 祝日跨ぎ（Q239 と混ざる）、H1 の週末跨ぎ足（Q248）、絶対リターン。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_weekend_variance_q272.py            （B=1000・小（B=1000・1 分前後））
      python3 kensho_weekend_variance_q272.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q272"
DEFAULT_B = 1000
START = "2008-01-01"
MIN_MON, MIN_OTH = 20, 60
LOG13, LOG2, LOG3 = math.log(1.3), math.log(2.0), math.log(3.0)


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=5000, freq="D", start=START)
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    else:
        df = load_d1(sym, False, rng)
    df = df[df["time"] >= pd.Timestamp(START)].dropna(subset=["ret"]).reset_index(drop=True)
    df["dow"] = df["time"].dt.dayofweek
    return df


def log_ratio(r, is_mon):
    a = r[is_mon]; b = r[~is_mon]
    if len(a) < MIN_MON or len(b) < MIN_OTH or b.var(ddof=1) <= 0 or a.var(ddof=1) <= 0:
        return float("nan")
    return float(math.log(a.var(ddof=1) / b.var(ddof=1)))


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    cells = []; nulls = {}  # nulls[(year, sym)] = B 本の帰無 log R
    for sym in syms:
        df = load_sym(sym, args, rng)
        df = df[df["dow"] <= 4].copy()  # 土日の足は除く（暗号資産）→ 月曜のリターンは金曜終値→月曜終値に揃える
        df["ret"] = df["close"].pct_change(); df = df.dropna(subset=["ret"])
        for y, d in df.groupby("year"):
            r = d["ret"].values; mon = (d["dow"].values == 0)
            lr = log_ratio(r, mon)
            cells.append({"year": int(y), "sym": sym, "logR": lr, "n_mon": int(mon.sum()), "n_oth": int((~mon).sum())})
            if np.isfinite(lr):
                # 曜日ラベルを年内で並べ替え: 月曜の数 k を保ったまま位置を無作為に
                k = int(mon.sum()); n = len(r)
                order = rng.random((args.B, n)).argsort(axis=1)
                pick = np.zeros((args.B, n), dtype=bool)
                np.put_along_axis(pick, order[:, :k], True, axis=1)
                va = np.where(pick, r[None, :], np.nan); vb = np.where(pick, np.nan, r[None, :])
                with np.errstate(invalid="ignore", divide="ignore"):
                    nulls[(int(y), sym)] = np.log(np.nanvar(va, axis=1, ddof=1) / np.nanvar(vb, axis=1, ddof=1))
    cdf = pd.DataFrame(cells)

    def stats(d, y0, y1):
        dd = d[(d["year"] >= y0) & (d["year"] < y1)].dropna(subset=["logR"])
        st = by_year_stats(dd, "logR")
        dd3 = dd.assign(logR3=dd["logR"] - LOG3); st3 = by_year_stats(dd3, "logR3")
        z = pct = float("nan")
        if len(dd):
            keys = list(zip(dd["year"], dd["sym"]))
            N = np.vstack([nulls[k] for k in keys])  # n_cells × B
            yrs = dd["year"].values; yu = np.unique(yrs)
            M = (yrs[None, :] == yu[:, None]).astype(float); M /= M.sum(1, keepdims=True)
            null = (M @ N).mean(0)
            z, pct = z_of(st["mean"], null)
        return {"n_cells": int(len(dd)), "n_years": st["n_years"], "logR_mean": f(st["mean"]), "R_mean_exp": f(math.exp(st["mean"])) if np.isfinite(st["mean"]) else None,
                "logR_median": f(dd["logR"].median()) if len(dd) else None, "t_vs_0": f(st["t"]), "t_vs_log3": f(st3["t"]),
                "t_vs_log13": f(by_year_stats(dd.assign(x=dd["logR"] - LOG13), "x")["t"]), "z": f(z), "pct": f(pct)}

    summary = {}
    groups = dict(GROUPS); groups["BTC_only"] = ["BTCUSD"]; groups["all15_exBTC"] = [s for s in SYMS if s != "BTCUSD"]
    for gname, gs in groups.items():
        d = cdf[cdf["sym"].isin(gs)]
        summary[gname] = {pn: stats(d, y0, y1) for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999)))}
    a = summary.get("all15", {}).get("all", {})
    m, t3, z = a.get("logR_mean"), a.get("t_vs_log3"), a.get("z")
    if m is None or t3 is None or z is None:
        verdict = "未確定: 計算できない（平均・t・z が nan）"
    elif m < LOG13 and t3 <= -2:
        verdict = "支持: all15 の log R の年単位平均が log1.3 未満かつ log3 に対し t≤−2（取引時間仮説）"
    elif m >= LOG2 and z >= 2:
        verdict = "棄却: log R≥log2 かつ z≥2（暦時間に近い）"
    else:
        verdict = "未確定: log1.3 と log2 の間、または t・z が閾値に届かない"
    res = {"question": "月曜（週末跨ぎ）のリターン分散は他の曜日の何倍か（取引時間 vs 暦時間）",
           "settings": {"syms": SYMS, "start": START, "split_year": SPLIT_YEAR, "min_days": [MIN_MON, MIN_OTH], "B": args.B,
                        "null": "曜日ラベル（月曜）を年内で並べ替え", "ratio": "R = Var(月曜 ret) / Var(火〜金 ret)、年×銘柄"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の 1 本（帰無値 log1.3・log3）。群別・BTC・前後半は記述。"}
    return res, {"cells": cdf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
