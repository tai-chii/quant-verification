#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q277: リスクオフ日（US500 下位 5%）の金・円・フラン・豪ドルのベータは前後半で安定か（安全資産の役割）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q277 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Ranaldo・Söderlind 2010（Review of Finance・安全資産通貨）、Baur・Lucey 2010（金）、RIETI DP 19-E-048、知見 Q241・Q236
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "safe haven gold yen Swiss franc beta to equity market crash days stability over time 2008-2024 empirical"）:
  見つかったもの: RIETI DP 19-E-048、Financial Innovation 2024、CEPR DP7249（Ranaldo・Söderlind）、EMU の安全資産論文。
  未確認: 4 銘柄 CFD の下位 5% 条件つきベータの前後半差を Holm・年内並べ替えで判定する形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: US500 の日次リターンが拡大窓の下位 5% の日（リスクオフ日）に、XAUUSD・USDJPY・USDCHF・AUDUSD の同日リターンを US500 のリターンに回帰したベータ β_off は、前半 2012–2016 と後半 2017–2026 で符号が同じで差が 2se 未満（役割は安定）。

【データ】
US500・XAUUSD・USDJPY・USDCHF・AUDUSD D1_fromH1（2011-09〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
リスクオフ日: t−1 までの拡大窓（最短 250 日）の 5% 分位以下。β_off を前後半で OLS（HC1 の se）。β_normal（それ以外の日）も記述。

【測るもの】
4 銘柄の β_off（前後半）と差の z=(β_post−β_pre)/√(se²+se²)。Holm 4 本。

【帰無】
リスクオフ日ラベルを年内で並べ替え B=1000 → β_off の帰無分布（通常日との差）→ z（記述）。

【判定（事前固定・変更禁止）】
4 銘柄とも 前後半で β_off 同符号かつ Holm 後の差 |z|<2 → 支持（安定）。1 つ以上で符号が逆または Holm 後 |z|≥2 → 棄却（どの銘柄が変わったかを書く）。前後半のどちらかで β_off が 0 と区別できない銘柄がある → 未確定。
多重比較: 差の検定 4 本を Holm で補正。並べ替え z は記述。

【捨てた案の数】
約3: VIX 条件（無い）、H1 の同時相関、EURCHF（手元に無い）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_safe_haven_beta_q277.py            （B=1000・小（B=1000・30 秒））
      python3 kensho_safe_haven_beta_q277.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q277"
DEFAULT_B = 1000
START = "2012-01-01"
MKT = "US500"
SYMS4 = ["XAUUSD", "USDJPY", "USDCHF", "AUDUSD"]
MIN_HIST, Q = 250, 0.05
P_Z2 = math.erfc(2 / math.sqrt(2))  # |z|=2 の両側 p（≈0.0455）。Holm 後 |z|<2 ⇔ Holm 後 p > P_Z2


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=4000, freq="D", start="2011-09-01")
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
        return df
    return load_d1(sym, False, rng)


def ols_hc1(x, y):
    """y = a + b x。b と HC1 の se。"""
    n = len(x)
    if n < 5 or np.var(x) == 0:
        return float("nan"), float("nan")
    X = np.c_[np.ones(n), x]
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    meat = (X * (e ** 2)[:, None]).T @ X
    V = XtX_inv @ meat @ XtX_inv * n / (n - 2)
    return float(b[1]), float(math.sqrt(max(V[1, 1], 0)))


def slopes_from_mask(M, x, y):
    """M: B × n の bool。各行の True 部分と False 部分の OLS 傾き（ベクトル化）。"""
    Mf = M.astype(float); Mc = 1.0 - Mf
    out = []
    for W in (Mf, Mc):
        n = W.sum(1); Sx = W @ x; Sy = W @ y; Sxx = W @ (x * x); Sxy = W @ (x * y)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append((Sxy - Sx * Sy / n) / (Sxx - Sx * Sx / n))
    return out[0], out[1]


def p_two_sided(z):
    return float(math.erfc(abs(z) / math.sqrt(2))) if np.isfinite(z) else float("nan")


def run(args, rng):
    need = [MKT] + SYMS4
    syms, missing = syms_available(need, "D1_fromH1", args.smoke)
    if MKT not in syms:
        res = {"question": "リスクオフ日の安全資産ベータは前後半で安定か", "settings": {}, "missing": missing, "summary": {},
               "machine_verdict": "未確定: 計算できない（US500 が無い）", "multiple_comparisons": "Holm 4 本"}
        return res, None
    mk = load_sym(MKT, args, rng)[["time", "ret", "year"]].rename(columns={"ret": "rm"}).dropna()
    thr = mk["rm"].shift(1).expanding(min_periods=MIN_HIST).quantile(Q)
    mk["riskoff"] = (mk["rm"] <= thr) & thr.notna()
    mk = mk[mk["time"] >= pd.Timestamp(START)].reset_index(drop=True)
    summary = {}; zs = {}; cells = []
    syms4 = [s for s in SYMS4 if s in syms]
    for s in syms4:
        d = load_sym(s, args, rng)[["time", "ret"]].rename(columns={"ret": "ry"}).dropna()
        d = mk.merge(d, on="time", how="inner")
        summary[s] = {}
        for pn, (y0, y1) in (("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999)), ("all", (0, 9999))):
            dd = d[(d["year"] >= y0) & (d["year"] < y1)]
            off = dd[dd["riskoff"]]; nor = dd[~dd["riskoff"]]
            b_off, se_off = ols_hc1(off["rm"].values, off["ry"].values)
            b_nor, se_nor = ols_hc1(nor["rm"].values, nor["ry"].values)
            # 帰無: リスクオフ日ラベルを年内で並べ替え → β_off − β_normal
            z = pct = float("nan")
            if len(off) >= 5 and len(nor) >= 5:
                lab = dd["riskoff"].values; yrs = dd["year"].values
                M = np.empty((args.B, len(dd)), dtype=bool)
                for y in np.unique(yrs):
                    idx = np.where(yrs == y)[0]
                    perm = rng.random((args.B, len(idx))).argsort(axis=1)
                    M[:, idx] = lab[idx][perm]
                so, sn = slopes_from_mask(M, dd["rm"].values, dd["ry"].values)
                z, pct = z_of(b_off - b_nor, so - sn)
            summary[s][pn] = {"n_off": int(len(off)), "n_normal": int(len(nor)), "beta_off": f(b_off), "se_off": f(se_off),
                              "t_off": f(b_off / se_off) if np.isfinite(se_off) and se_off > 0 else None,
                              "beta_normal": f(b_nor), "se_normal": f(se_nor),
                              "diff_off_minus_normal": f(b_off - b_nor), "perm_z": f(z), "perm_pct": f(pct)}
            cells.append({"sym": s, "period": pn, "n_off": int(len(off)), "beta_off": b_off, "se_off": se_off, "beta_normal": b_nor, "se_normal": se_nor})
        bp, sp = summary[s]["pre"]["beta_off"], summary[s]["pre"]["se_off"]; bq, sq = summary[s]["post"]["beta_off"], summary[s]["post"]["se_off"]
        if None in (bp, sp, bq, sq) or (sp ** 2 + sq ** 2) <= 0:
            zs[s] = float("nan")
        else:
            zs[s] = (bq - bp) / math.sqrt(sp ** 2 + sq ** 2)
        summary[s]["diff_z"] = f(zs[s]); summary[s]["diff_p"] = f(p_two_sided(zs[s]), 5)
    pv = np.array([p_two_sided(zs[s]) for s in syms4])
    adj = holm(np.where(np.isfinite(pv), pv, 1.0)) if len(pv) else np.array([])
    for s, p in zip(syms4, adj):
        summary[s]["diff_p_holm"] = f(p, 5)
        summary[s]["holm_abs_z_ge2"] = bool(np.isfinite(zs[s]) and p <= P_Z2)
        summary[s]["same_sign"] = bool(summary[s]["pre"]["beta_off"] is not None and summary[s]["post"]["beta_off"] is not None
                                       and np.sign(summary[s]["pre"]["beta_off"]) == np.sign(summary[s]["post"]["beta_off"]))
        summary[s]["beta_off_distinct_from_0_both"] = bool(all(summary[s][p]["t_off"] is not None and abs(summary[s][p]["t_off"]) >= 2 for p in ("pre", "post")))
    if len(syms4) < 4:
        verdict = "未確定: 銘柄が揃わない（missing=%s）" % missing
    elif any(not np.isfinite(zs[s]) for s in syms4):
        verdict = "未確定: 計算できない（差の z が nan）"
    else:
        # 符号が逆・Holm 後 |z|≥2 → 棄却。ただし「符号が逆」だけで β_off が 0 と区別できない銘柄は未確定側に回す
        #（0 付近の符号の入れ替わりを役割の変化と呼ばないため。Holm 後 |z|≥2 は β の有意性に関わらず棄却）。
        weak = [s for s in syms4 if not summary[s]["beta_off_distinct_from_0_both"]]
        changed = [s for s in syms4 if summary[s]["holm_abs_z_ge2"] or ((not summary[s]["same_sign"]) and s not in weak)]
        desc = lambda ss: "・".join(f"{s}: pre={summary[s]['pre']['beta_off']} post={summary[s]['post']['beta_off']} z={summary[s]['diff_z']} p_holm={summary[s]['diff_p_holm']}" for s in ss)
        if changed:
            verdict = "棄却: 符号が逆または Holm 後 |z|≥2 の銘柄あり（" + desc(changed) + "）"
        elif weak:
            verdict = "未確定: 前後半のどちらかで β_off が 0 と区別できない銘柄あり（" + desc(weak) + "）"
        else:
            verdict = "支持: 4 銘柄とも前後半で β_off 同符号かつ Holm 後 |z|<2（役割は安定）"
    res = {"question": "リスクオフ日（US500 下位 5%）の金・円・フラン・豪ドルのベータは前後半で安定か",
           "settings": {"market": MKT, "syms": SYMS4, "start": START, "min_hist": MIN_HIST, "q": Q, "split_year": SPLIT_YEAR, "B": args.B,
                        "se": "HC1", "diff_z": "(β_post−β_pre)/√(se_pre²+se_post²)", "holm": "4 本・|z|<2 ⇔ Holm 後 p > %.5f" % P_Z2,
                        "null": "リスクオフ日ラベルを年内で並べ替え → β_off−β_normal（記述）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "差の検定 4 本を Holm で補正。並べ替え z・β_normal・全期間は記述。"}
    return res, {"betas": pd.DataFrame(cells)}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
