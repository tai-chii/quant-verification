#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q274: 15銘柄をプールしたパネル HAR は銘柄別 HAR より翌日の QLIKE を下げるか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q274 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Bollerslev・Hood・Huss・Pedersen 2018（RFS・Risk Everywhere・パネル HAR）、Corsi 2009、知見 Q222（Parkinson HAR）・Q187
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "pooled panel HAR model versus individual asset HAR realized volatility forecasting QLIKE cross-asset"）:
  見つかったもの: Bollerslev ほか 2018「Risk Everywhere」、arXiv 2406.08041「HARd to Beat」、METU「Forecasting volatility with HAR-RV: commodities, currencies, equities」。
  未確認: Risk Everywhere は先物の高頻度 RV。手元 CFD 15 銘柄・Parkinson・年次ウォークフォワード・符号並べ替え帰無は未確認（追試＋移植）。

【仮説（測る前に固定）】
H: 対数 Parkinson 分散の HAR（1・5・22 日）を 15 銘柄でプール（係数共通・銘柄固定効果）して推定すると、銘柄別推定より翌日の QLIKE が低い（係数の推定誤差が減る）。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
年ごとのウォークフォワード（前年までの拡大窓・最短 500 日で推定し翌年を予測）。A: 銘柄別 OLS。B: プール OLS（固定効果）。予測は exp(log 予測)（補正なし・両者同じ）。

【測るもの】
年×銘柄の QLIKE 差 B−A（対応あり・年単位 t・all15/fx8/trend7）。前後半。

【帰無】
差の符号を年×銘柄で無作為に反転（符号並べ替え）B=2000 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも QLIKE 差<0 かつ t≤−2 かつ z≤−2 → 支持。前後半とも t≥2 → 逆向きで確定（プールは害）。それ以外 → 棄却（差は見えない）。
多重比較: 判定は all15 の前後半 2 本。群別は記述。

【捨てた案の数】
約3: 群別プール（fx8・trend7 で別々）、縮小推定（プールと個別の中間）、5 日先。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_pooled_har_q274.py            （B=2000・小（B=2000・1 分前後））
      python3 kensho_pooled_har_q274.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q274"
DEFAULT_B = 2000
START = "2008-01-01"
MIN_TRAIN = 500


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=5000, freq="D", start=START)
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    else:
        df = load_d1(sym, False, rng)
    return df[df["time"] >= pd.Timestamp(START)].reset_index(drop=True)


def har_frame(df, sym):
    """対数 Parkinson 分散 v と HAR の説明変数（lag1・mean5・mean22、すべて t−1 まで）。"""
    pv = (np.log(df["high"].values / df["low"].values)) ** 2 / (4 * math.log(2))
    v = np.log(pv)
    s = pd.Series(v)
    X = pd.DataFrame({"sym": sym, "year": df["year"].values, "v": v, "pv": pv,
                      "lag1": s.shift(1).values, "m5": s.shift(1).rolling(5).mean().values, "m22": s.shift(1).rolling(22).mean().values})
    return X.dropna().reset_index(drop=True)


def ols_fit(X, y):
    A = np.c_[np.ones(len(X)), X]
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    frames = [har_frame(load_sym(s, args, rng), s) for s in syms]
    panel = pd.concat(frames, ignore_index=True)
    cols = ["lag1", "m5", "m22"]
    years = sorted(panel["year"].unique())
    cells = []
    for Y in years:
        tr = panel[panel["year"] < Y]; te = panel[panel["year"] == Y]
        cnt = tr.groupby("sym").size()
        ok = [s for s in syms if cnt.get(s, 0) >= MIN_TRAIN and (te["sym"] == s).any()]
        if not ok:
            continue
        trp = tr[tr["sym"].isin(ok)]
        # B: プール OLS（銘柄固定効果 = 銘柄内で平均を引く within 推定）
        mx = trp.groupby("sym")[cols].transform("mean"); my = trp.groupby("sym")["v"].transform("mean")
        Xd = (trp[cols] - mx).values; yd = (trp["v"] - my).values
        bp, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
        gm = trp.groupby("sym")[cols + ["v"]].mean()
        for s in ok:
            trs = trp[trp["sym"] == s]; tes = te[te["sym"] == s]
            ba = ols_fit(trs[cols].values, trs["v"].values)
            pred_a = np.exp(ba[0] + tes[cols].values @ ba[1:])
            alpha_s = gm.loc[s, "v"] - gm.loc[s, cols].values @ bp
            pred_b = np.exp(alpha_s + tes[cols].values @ bp)
            qa = qlike(pred_a, tes["pv"].values); qb = qlike(pred_b, tes["pv"].values)
            cells.append({"year": int(Y), "sym": s, "n_test": int(len(tes)), "n_train": int(len(trs)),
                          "qlike_A_indiv": qa, "qlike_B_pooled": qb, "diff": qb - qa})
    cdf = pd.DataFrame(cells).dropna(subset=["diff"])

    def stats(d, y0, y1):
        dd = d[(d["year"] >= y0) & (d["year"] < y1)]
        st = by_year_stats(dd, "diff")
        z = pct = float("nan")
        if len(dd) >= 3:
            yrs = dd["year"].values; yu = np.unique(yrs)
            M = (yrs[None, :] == yu[:, None]).astype(float); M /= M.sum(1, keepdims=True)
            S = rng.choice([-1.0, 1.0], size=(args.B, len(dd)))
            null = ((S * dd["diff"].values[None, :]) @ M.T).mean(1)
            z, pct = z_of(st["mean"], null)
        return {"n_cells": int(len(dd)), "n_years": st["n_years"], "diff_mean": f(st["mean"], 6), "t": f(st["t"]), "z": f(z), "pct": f(pct),
                "qlike_A_mean": f(dd["qlike_A_indiv"].mean(), 6) if len(dd) else None, "qlike_B_mean": f(dd["qlike_B_pooled"].mean(), 6) if len(dd) else None,
                "frac_cells_B_better": f((dd["diff"] < 0).mean()) if len(dd) else None}

    summary = {g: {pn: stats(cdf[cdf["sym"].isin(gs)], y0, y1) for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999)))}
               for g, gs in GROUPS.items()}
    a = summary.get("all15", {})
    g = lambda p, k: a.get(p, {}).get(k)
    if any(g(p, k) is None for p in ("pre", "post") for k in ("t", "z", "diff_mean")):
        verdict = "未確定: 計算できない（t または z が nan）"
    elif all(g(p, "diff_mean") < 0 and g(p, "t") <= -2 and g(p, "z") <= -2 for p in ("pre", "post")):
        verdict = "支持: all15 前後半とも QLIKE 差<0 かつ t≤−2 かつ z≤−2（プールが良い）"
    elif all(g(p, "t") >= 2 for p in ("pre", "post")):
        verdict = "逆向きで確定: 前後半とも t≥2（プールは害）"
    else:
        verdict = "棄却: 差は見えない（支持にも逆向きにも届かない）"
    res = {"question": "15 銘柄をプールしたパネル HAR は銘柄別 HAR より翌日の QLIKE を下げるか",
           "settings": {"syms": SYMS, "start": START, "min_train": MIN_TRAIN, "split_year": SPLIT_YEAR, "B": args.B,
                        "model": "log Parkinson 分散の HAR(1,5,22)・年次ウォークフォワード（拡大窓）・予測 exp(log 予測)",
                        "pooled": "係数共通＋銘柄固定効果（within 推定）", "null": "差の符号を年×銘柄で反転"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の前後半 2 本。群別は記述。"}
    return res, {"cells": cdf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
