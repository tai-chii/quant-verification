#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q234: XAUUSD の実測スプレッドの変化は、HAR に足すと翌時間の実現ボラの QLIKE を下げるか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q234 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q222（Parkinson 入力の HAR が翌日 RV の QLIKE を下げる）、知見 Q081（XAUUSD の時間帯別スプレッドの実測）、知見 Q185（bid/ask で合図が変わる）。
- Corsi (2009) HAR-RV。流動性とボラの関係: Chordia・Roll・Subrahmanyam (2001) ほか（本文未読）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "bid-ask spread changes predict next hour realized volatility HAR model gold"）:
  金の HAR-RV（原油ショック・リスク回避の説明変数）はあるが、実測スプレッドの「同時刻の平常からのずれ」を時間足の HAR に足して
  歩進で QLIKE を比べた形は未確認。条件の穴。

【仮説（測る前に固定）】
H: 時刻 t のスプレッドの平常からのずれ（同じ時刻の過去 20 日の中央値に対する対数比）を HAR に足すと、翌 1 時間の
   Parkinson 分散の QLIKE が下がる（HAR+S − HAR < 0）。

【データ】`data_XAUUSD_H1_dukascopy.csv`（bid）と `data_XAUUSD_H1_dukascopy_ask.csv`（ask）、2008〜2026-06。共通時刻だけ。

【定義（1通りに固定）】
- 中値 m = (bid + ask)/2 の H・L から 1 時間の Parkinson 分散 v_t = ln(H/L)² / (4 ln 2)（H=L の足は除く）。
- 目的変数 y_{t+1} = ln v_{t+1}。説明変数: ln v_t、直前 24 本の平均、直前 120 本の平均（HAR）。
- スプレッド sp_t = (ask_close − bid_close) / m_close。ずれ S_t = ln sp_t − ln median{ sp_{同じ時刻, 直前 20 営業日} }（t までの値だけ）。
- 歩進: 年 Y の予測は Y より前の全データで OLS（最低 2 年）。予測分散 = exp(ŷ) × 平滑化係数（学習データの exp(残差) の平均）。
- QLIKE(年) を HAR と HAR+S で出し、対応ありの差 → 年単位 t。時刻帯別（アジア 0–7・欧州 7–13・米 13–21・他）の差も記述。

【測るもの】前半（年 < 2017）／後半（≥ 2017）／全期間。S の係数の符号（記述）。

【帰無】S の列を 24 本以上の循環シフト（自己相関と時刻の季節性は保つ）で同じ歩進（B=100。回帰 1 回が軽いので十分）→ QLIKE 差の帰無分布 → z。

【判定（事前固定・変更禁止）】
- 前半・後半とも QLIKE 差 < 0 かつ t ≤ −2 かつ z ≤ −2 → 支持。
- どちらかで t > −2 → 棄却。
多重比較: 判定は前後半の (t, z) 4 本。

【捨てた案の数】約4: スプレッドの水準そのもの（時刻の季節性と混ざる）、翌日の日次 RV を目的にする案（時間足で直接）、
GARCH-X、スプレッドを 2 段（広い/狭い）に刻む案。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・QLIKE 差の t と z を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_spread_change_vol_q234.py            （B=100・2 分前後）
      python3 kensho_spread_change_vol_q234.py --smoke
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

QID = "Q234"
DEFAULT_B = 100
MIN_TRAIN_YEARS = 2
EPS = 1e-12


def build(args, rng):
    if args.smoke:
        bid = _smoke_ohlc("XAUUSD", rng, n=60000, freq="h", start="2010-01-01")
        ask = bid.copy(); sp = np.abs(rng.normal(0.0003, 0.0001, len(bid))) * bid["close"].values
        for col in ("open", "high", "low", "close"):
            ask[col] = bid[col] + sp
    else:
        bid = _read(os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy.csv")); ask = _read(os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy_ask.csv"))
    m = bid.merge(ask, on="time", suffixes=("_b", "_a"))
    for col in ("open", "high", "low", "close"):
        m[col] = (m[col + "_b"] + m[col + "_a"]) / 2
    m = m[(m["high"] > m["low"]) & (m["close_a"] > m["close_b"])].reset_index(drop=True)
    m["v"] = np.log(m["high"] / m["low"]) ** 2 / (4 * math.log(2))
    m["lv"] = np.log(m["v"] + EPS)
    m["lv24"] = m["lv"].rolling(24).mean(); m["lv120"] = m["lv"].rolling(120).mean()
    m["sp"] = (m["close_a"] - m["close_b"]) / m["close"]
    m["hour"] = m["time"].dt.hour; m["date"] = m["time"].dt.floor("D"); m["year"] = m["time"].dt.year
    # 同じ時刻の直前 20 営業日の中央値（t を含まない）
    med = m.groupby("hour")["sp"].transform(lambda x: x.shift(1).rolling(20, min_periods=10).median())
    m["S"] = np.log(m["sp"]) - np.log(med)
    m["y"] = m["lv"].shift(-1); m["v_next"] = m["v"].shift(-1)
    m = m.dropna(subset=["lv24", "lv120", "S", "y"]).reset_index(drop=True)
    return m


def walk_forward(m, S_col):
    years = sorted(m["year"].unique()); out = {}
    X_base = ["lv", "lv24", "lv120"]
    for i, y in enumerate(years):
        tr = m[m["year"] < y]
        if tr["year"].nunique() < MIN_TRAIN_YEARS:
            continue
        te = m[m["year"] == y]
        res = {}
        for name, cols in (("har", X_base), ("har_s", X_base + [S_col])):
            A = np.c_[np.ones(len(tr)), tr[cols].values]; beta, *_ = np.linalg.lstsq(A, tr["y"].values, rcond=None)
            resid = tr["y"].values - A @ beta; smear = float(np.mean(np.exp(resid)))
            At = np.c_[np.ones(len(te)), te[cols].values]; pred = np.exp(At @ beta) * smear
            res[name] = qlike(pred, te["v_next"].values)
            if name == "har_s":
                res["coef_S"] = float(beta[-1])
        out[y] = res
    return out


def summarize(wf):
    df = pd.DataFrame(wf).T; df.index.name = "year"; df["diff"] = df["har_s"] - df["har"]
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        d = df[(df.index >= y0) & (df.index < y1)]
        if d.empty:
            continue
        out[pn] = {"n_years": int(len(d)), "qlike_har": f(d["har"].mean()), "qlike_har_s": f(d["har_s"].mean()), "diff": f(d["diff"].mean(), 5),
                   "diff_t": f(tstat(d["diff"].values)), "coef_S_mean": f(d["coef_S"].mean())}
    return out, df


def run(args, rng):
    m = build(args, rng)
    obs, df = summarize(walk_forward(m, "S"))
    null = {pn: [] for pn in obs}
    for b in range(args.B):
        m2 = m.copy()
        # S を 24 本以上の循環シフト（S の自己相関・時刻の季節性は保ち、翌時間のボラとの対応だけ壊す）
        m2["S_perm"] = np.roll(m["S"].values, int(rng.integers(24, len(m) - 24)))
        st, _ = summarize(walk_forward(m2, "S_perm"))
        for pn in obs:
            if pn in st:
                null[pn].append(st[pn]["diff"])
        if b % 20 == 0:
            print("null", b)
    summary = {}
    for pn, v in obs.items():
        z, pct = z_of(v["diff"], null[pn]); summary[pn] = {**v, "diff_z": f(z), "null_mean": f(np.nanmean(null[pn]), 5) if null[pn] else None}
    g = lambda p, k: (summary.get(p, {}).get(k) if summary.get(p, {}).get(k) is not None else float("nan"))
    if all(g(p, "diff") < 0 and g(p, "diff_t") <= -2 and g(p, "diff_z") <= -2 for p in ("pre", "post")):
        verdict = "支持: スプレッドのずれは翌時間の QLIKE を下げる"
    else:
        verdict = "棄却: 前後半のどちらかで t > −2 または z > −2"
    res = {"question": "XAUUSD の実測スプレッドの変化は HAR に足すと翌時間の実現ボラの QLIKE を下げるか",
           "settings": {"min_train_years": MIN_TRAIN_YEARS, "B": args.B, "null": "S を 24 本以上の循環シフト（日の塊を保つ近似）"},
           "n_obs": int(len(m)), "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は前後半の (t, z) 4 本。"}
    return res, {"by_year": df.reset_index()}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
