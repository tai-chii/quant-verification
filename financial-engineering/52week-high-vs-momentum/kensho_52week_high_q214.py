#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q214: 52 週高値への近さは 15 銘柄の翌月リターンを 12 か月モメンタムより予測するか（George・Hwang 2004 の型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: George & Hwang (2004) "The 52-Week High and Momentum Investing" J. Finance 59(5) — 52 週高値への近さ（終値÷52 週高値）は
  12 か月モメンタムより翌月リターンをよく予測し、モメンタムの説明力の大部分を吸収する（表 II・表 III）。
  関連知見: Q147（翌日の方向の的中率は基準率を超えない）、Q186（週足の IC は負）。
  → 本案は横断（株式の銘柄間）ではなく、15 銘柄それぞれの時系列で「52 週高値への近さ」と「12 か月モメンタム」の翌 21 日リターンへの IC を比べる。

【仮説（測る前に固定）】
H1: X_t = close_t ÷ max(high_{t−251..t}) の翌 21 日リターンへの Spearman（銘柄×年）は正で帰無 z ≥ 2（前後半とも）、かつ
    12 か月モメンタム M_t = close_t ÷ close_{t−252} − 1 の IC より大きい（対応ありの年単位 t ≥ 2）。
H0: X の IC は 0 と区別できない、または M と差がない。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 翌 21 日リターン: close_{t+21} ÷ close_t − 1（重複あり。年の単位で平均するので重複の影響は帰無で吸収）。
- IC: 銘柄×年のセルで Spearman(X_t, r_{t→t+21})。M も同じ。年ごとに銘柄平均 → 年平均と t。
- 帰無: X（M）を銘柄内で循環シフト（最小 30 日）B 回 → IC の年平均の z。
- 売買（記述）: 21 日ごとに X の上位半分（年内の中央値より上）なら買い・下なら売り（純損益 bp/日、段階 1 のコスト）。M も同じ。

【測るもの】X・M の IC と z、差の t（前後半・群別）、売買の純損益。

【判定（事前固定・変更禁止）】
all15 で前後半とも X の IC > 0 かつ z ≥ 2、かつ IC(X) − IC(M) の年単位 t ≥ 2 → H1 支持。
前後半のどちらかで X の z < 2 → 棄却（52 週高値への近さに時系列の予測力なし）。差が t < 2 で X 単独が z ≥ 2 → 「予測力はあるがモメンタムと差がない」（未確定扱い・記述）。

【捨てた案の数】約 4: 52 週安値（対称性は別問題）、横断ランク（15 銘柄では少なすぎる）、翌 5 日・翌 63 日の格子、近さの 2 値化（上位 1/3）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・X の z・差の t・George 2004 表 II の係数を返す。

【実装】自己完結。実行: python3 kensho_52week_high_q214.py（B=300、1 分前後）／--B 30／--smoke
"""

# ============================================================================= 共通の土台（各スクリプトに同じものを埋め込む・自己完結）
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

QID = "Q214"
DEFAULT_B = 300
LB, H = 252, 21


def ics(cells, xcol):
    g = cells.groupby(["sym", "year"]).apply(lambda d: spearman(d[xcol].values, d["fwd"].values))
    return g.rename("ic").reset_index()


def summarize(icx, icm):
    both = icx.merge(icm, on=["sym", "year"], suffixes=("_x", "_m"))
    out = {}
    for gname, members in GROUPS.items():
        bg = both[both["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = bg[(bg["year"] >= y0) & (bg["year"] < y1)]
            if d.empty:
                continue
            yr = d.drop(columns="sym").groupby("year").mean(); dd = yr["ic_x"] - yr["ic_m"]
            out[f"{gname}_{pn}"] = {"n_years": int(len(yr)), "ic_x": float(yr["ic_x"].mean()), "ic_x_t": tstat(yr["ic_x"].values), "ic_m": float(yr["ic_m"].mean()),
                                    "ic_m_t": tstat(yr["ic_m"].values), "diff": float(dd.mean()), "diff_t": tstat(dd.values)}
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []; trade = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; h = df["high"].values
        X = c / pd.Series(h).rolling(LB).max().values; M = c / np.r_[np.full(LB, np.nan), c[:-LB]] - 1
        fwd = np.r_[c[H:] / c[:-H] - 1, np.full(H, np.nan)]
        d = pd.DataFrame({"sym": s, "year": df["year"].values, "X": X, "M": M, "fwd": fwd}); frames.append(d)
        # 売買（記述）: 21 日ごとに年内中央値（その時点までの展開中央値で先読み回避）で 2 値化
        cb = cost_bp_oneway(s, c)
        for name, sigv in (("X", X), ("M", M)):
            med = pd.Series(sigv).expanding(LB).median().values
            pos = np.where(np.isnan(sigv) | np.isnan(med), 0.0, np.where(sigv > med, 1.0, -1.0))
            hold = np.zeros(len(c)); last = 0.0
            for t in range(len(c)):
                if t % H == 0:
                    last = pos[t]
                hold[t] = last
            p = pnl_bp(hold, c, cb); yr = pd.Series(p).groupby(df["year"].values).mean()
            trade.extend({"sym": s, "year": int(y), "rule": name, "bp": float(v)} for y, v in yr.items())
    cells = pd.concat(frames, ignore_index=True).dropna()
    icx, icm = ics(cells, "X"), ics(cells, "M")
    obs = summarize(icx, icm)
    null = {k: {"x": [], "m": []} for k in obs}
    for b in range(args.B):
        parts = []
        for s, d in cells.groupby("sym"):
            d = d.copy(); d["X"] = circ_shift(rng, d["X"].values, 30); d["M"] = circ_shift(rng, d["M"].values, 30); parts.append(d)
        cp = pd.concat(parts); st = summarize(ics(cp, "X"), ics(cp, "M"))
        for k in obs:
            if k in st:
                null[k]["x"].append(st[k]["ic_x"]); null[k]["m"].append(st[k]["ic_m"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        zx, _ = z_of(v["ic_x"], null[k]["x"]); zm, _ = z_of(v["ic_m"], null[k]["m"])
        summary[k] = {**{kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}, "ic_x_z": f(zx), "ic_m_z": f(zm)}
    tr = pd.DataFrame(trade); trade_sum = {}
    for rule in ("X", "M"):
        for pn, (y0, y1) in (("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            st = by_year_stats(tr[tr["rule"] == rule], "bp", y0=y0, y1=y1); trade_sum[f"{rule}_{pn}"] = {k: (f(v) if isinstance(v, float) else v) for k, v in st.items()}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    x_ok = all(g(p, "ic_x") > 0 and g(p, "ic_x_z") >= 2 for p in (pre, post))
    if x_ok and all(g(p, "diff_t") >= 2 for p in (pre, post)):
        verdict = "支持: 52 週高値への近さはモメンタムより翌月を予測する"
    elif g(pre, "ic_x_z") < 2 or g(post, "ic_x_z") < 2:
        verdict = "棄却: 前後半のどちらかで X の IC の z<2"
    elif x_ok:
        verdict = "未確定: X に予測力はあるがモメンタムとの差は t<2"
    else:
        verdict = "未確定"
    res = {"question": "52 週高値への近さは翌月リターンを 12 か月モメンタムより予測するか", "settings": {"LB": LB, "H": H, "B": args.B}, "missing": missing,
           "summary": summary, "trade_reference": trade_sum, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の X の z と差の t の 4 本。群別・売買は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
