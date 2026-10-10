#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q275: HAR の持続基準に対する優位は予測期間（1・5・22 日）で広がるか縮むか（15銘柄・QLIKE）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q275 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Corsi 2009、Andersen・Bollerslev・Diebold 2007、知見 Q222・Q195（持続基準線）、arXiv 2402.01354（動的持続モデル）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "HAR-RV forecast horizon 1 day 5 day 22 day versus random walk persistence benchmark relative accuracy horizon"）:
  見つかったもの: arXiv 2402.01354（エネルギーの動的持続）、arXiv 2605.24285（記憶と粗さ）、Financial Innovation 2022 の表。
  未確認: 改善率の h 依存を 15 銘柄・前後半・符号並べ替え帰無で事前固定の判定にかける形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 予測期間 h=1・5・22 日の実現分散（Parkinson の和）に対し、HAR の QLIKE の持続基準（直近 h 日の実現分散をそのまま使う）に対する改善率 Δ_h=(QLIKE_persist−QLIKE_HAR)/QLIKE_persist は h が長いほど大きい（Δ_22>Δ_1）。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
HAR は h ごとに目的変数を h 日先の和にして推定（拡大窓・年次ウォークフォワード）。非重複の h 日ブロックで評価。

【測るもの】
年×銘柄の Δ_1・Δ_5・Δ_22 と差 Δ_22−Δ_1（対応あり・年単位 t・all15）。前後半。

【帰無】
Δ_22−Δ_1 の符号を年×銘柄で無作為に反転 B=2000 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも Δ_22−Δ_1>0 かつ t≥2 かつ z≥2 → 支持（長いほど HAR が効く）。前後半とも t≤−2 → 逆向きで確定（短いほど効く）。それ以外 → 未確定。
多重比較: 判定は all15 の差の前後半 2 本。各 Δ_h は記述。

【捨てた案の数】
約3: h=66、直接法と反復法の両方（直接法に固定）、MSE での評価（QLIKE に統一）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_har_horizon_q275.py            （B=2000・小（B=2000・1〜2 分））
      python3 kensho_har_horizon_q275.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q275"
DEFAULT_B = 2000
START = "2008-01-01"
MIN_TRAIN = 500
HS = [1, 5, 22]


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=5000, freq="D", start=START)
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    else:
        df = load_d1(sym, False, rng)
    return df[df["time"] >= pd.Timestamp(START)].reset_index(drop=True)


def har_frame(df, sym):
    """t 行: 説明変数は t−1 までの対数 Parkinson 分散の lag1・mean5・mean22。
    目的変数 tgt_h = sum_{j=0..h−1} pv_{t+j}（t から h 日の実現分散の和・対数で回帰）。持続基準 pers_h = sum_{j=1..h} pv_{t−j}。"""
    pv = (np.log(df["high"].values / df["low"].values)) ** 2 / (4 * math.log(2))
    s = pd.Series(np.log(pv)); p = pd.Series(pv)
    X = pd.DataFrame({"sym": sym, "year": df["year"].values, "idx": np.arange(len(df)),
                      "lag1": s.shift(1).values, "m5": s.shift(1).rolling(5).mean().values, "m22": s.shift(1).rolling(22).mean().values})
    for h in HS:
        X[f"tgt_{h}"] = p.rolling(h).sum().shift(-(h - 1)).values
        X[f"pers_{h}"] = p.shift(1).rolling(h).sum().values
        # 目的変数の最終日の年（学習に使えるのは最終日が試験年より前の行）
        X[f"endyear_{h}"] = pd.Series(df["year"].values).shift(-(h - 1)).values
    return X


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    cols = ["lag1", "m5", "m22"]
    cells = []
    for s in syms:
        F = har_frame(load_sym(s, args, rng), s)
        years = sorted(F["year"].unique())
        for Y in years:
            te_all = F[F["year"] == Y]
            row = {"year": int(Y), "sym": s}
            ok = True
            for h in HS:
                tr = F[(F[f"endyear_{h}"] < Y)].dropna(subset=cols + [f"tgt_{h}"])
                if len(tr) < MIN_TRAIN:
                    ok = False; break
                A = np.c_[np.ones(len(tr)), tr[cols].values]
                beta, *_ = np.linalg.lstsq(A, np.log(tr[f"tgt_{h}"].values), rcond=None)
                te = te_all.dropna(subset=cols + [f"tgt_{h}", f"pers_{h}"])
                te = te[(te[f"endyear_{h}"] == Y)]  # 試験年の中で完結するブロック
                if len(te) < h:
                    ok = False; break
                te = te.iloc[::h]  # 非重複ブロック
                pred = np.exp(beta[0] + te[cols].values @ beta[1:])
                q_har = qlike(pred, te[f"tgt_{h}"].values); q_per = qlike(te[f"pers_{h}"].values, te[f"tgt_{h}"].values)
                if not (np.isfinite(q_har) and np.isfinite(q_per)) or q_per <= 0:
                    ok = False; break
                row[f"qlike_har_{h}"] = q_har; row[f"qlike_pers_{h}"] = q_per; row[f"n_blocks_{h}"] = int(len(te))
                row[f"delta_{h}"] = (q_per - q_har) / q_per
            if ok:
                row["d22_1"] = row["delta_22"] - row["delta_1"]
                cells.append(row)
    cdf = pd.DataFrame(cells)

    def stats(d, y0, y1):
        dd = d[(d["year"] >= y0) & (d["year"] < y1)]
        st = by_year_stats(dd, "d22_1")
        z = pct = float("nan")
        if len(dd) >= 3:
            yrs = dd["year"].values; yu = np.unique(yrs)
            M = (yrs[None, :] == yu[:, None]).astype(float); M /= M.sum(1, keepdims=True)
            S = rng.choice([-1.0, 1.0], size=(args.B, len(dd)))
            null = ((S * dd["d22_1"].values[None, :]) @ M.T).mean(1)
            z, pct = z_of(st["mean"], null)
        out = {"n_cells": int(len(dd)), "n_years": st["n_years"], "d22_1_mean": f(st["mean"]), "t": f(st["t"]), "z": f(z), "pct": f(pct)}
        for h in HS:
            sh = by_year_stats(dd, f"delta_{h}")
            out[f"delta_{h}_mean"] = f(sh["mean"]); out[f"delta_{h}_t"] = f(sh["t"])
            out[f"qlike_har_{h}_mean"] = f(dd[f"qlike_har_{h}"].mean(), 6) if len(dd) else None
            out[f"qlike_pers_{h}_mean"] = f(dd[f"qlike_pers_{h}"].mean(), 6) if len(dd) else None
        s5 = by_year_stats(dd.assign(x=dd["delta_5"] - dd["delta_1"]) if len(dd) else dd, "x") if len(dd) else {"mean": float("nan"), "t": float("nan")}
        out["d5_1_mean"] = f(s5["mean"]); out["d5_1_t"] = f(s5["t"])
        return out

    summary = {g: {pn: stats(cdf[cdf["sym"].isin(gs)], y0, y1) for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999)))}
               for g, gs in GROUPS.items()} if len(cdf) else {}
    a = summary.get("all15", {})
    g = lambda p, k: a.get(p, {}).get(k)
    if any(g(p, k) is None for p in ("pre", "post") for k in ("t", "z", "d22_1_mean")):
        verdict = "未確定: 計算できない（t または z が nan）"
    elif all(g(p, "d22_1_mean") > 0 and g(p, "t") >= 2 and g(p, "z") >= 2 for p in ("pre", "post")):
        verdict = "支持: all15 前後半とも Δ22−Δ1>0 かつ t≥2 かつ z≥2（長いほど HAR が効く）"
    elif all(g(p, "t") <= -2 for p in ("pre", "post")):
        verdict = "逆向きで確定: 前後半とも t≤−2（短いほど効く）"
    else:
        verdict = "未確定: 支持にも逆向きにも届かない"
    res = {"question": "HAR の持続基準に対する優位は予測期間（1・5・22 日）で広がるか縮むか",
           "settings": {"syms": SYMS, "start": START, "min_train": MIN_TRAIN, "horizons": HS, "split_year": SPLIT_YEAR, "B": args.B,
                        "model": "直接法: log(h 日先の Parkinson 分散の和) を lag1・mean5・mean22 に回帰（拡大窓・年次ウォークフォワード）",
                        "benchmark": "持続: 直近 h 日の Parkinson 分散の和", "eval": "試験年内の非重複 h 日ブロック・QLIKE",
                        "null": "Δ22−Δ1 の符号を年×銘柄で反転"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の差（Δ22−Δ1）の前後半 2 本。各 Δ_h・Δ5−Δ1 は記述。"}
    return res, {"cells": cdf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
