#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q223: 参照日数の集合（20・60・120・250 の合図平均）は最良単一の参照日数より標本外で良いか（Baltas・Kosowski の型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Baltas & Kosowski (2013/2020) "Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and Pairwise Correlations"
  （SSRN 2140091）— 複数の参照期間の合図を平均すると単一より安定（§4）。Hurst・Ooi・Pedersen (2017) も 1・3・12 か月の等加重（§2）。
  関連知見: Q171（参照日数 60 通りから選ぶと PBO 0.88）、Q177（選び直す頻度を変えても標本外は変わらず事後選択は帰無より負）、Q188（台地選択は最良 1 点と変わらない）。
  → 本案は「パラメータを平均する（Q188）」でも「選び直す頻度（Q177）」でもなく、「合図そのものを平均する」ことが、前年までで選んだ最良単一を標本外で上回るかを測る。

【仮説（測る前に固定）】
H1: 4 つの参照日数の合図（符号）の平均を建玉にする規則の年ごとの純損益（bp/日・平均露出で割った単位露出あたり）は、
    前年までの束のシャープで選んだ最良単一の参照日数（歩進）より高い（対応ありの年単位 t ≥ 2、前後半とも）。
H0: 差は 0 と区別できない。参考: 各参照日数の固定規則、毎年ランダムに 1 つ選ぶ規則（帰無）。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017（最初の 2 年は選択の学習に使うため判定は 2010 年以降）。

【定義（1 通りに固定）】
- 合図: sign(close_t − close_{t−L})、L ∈ {20, 60, 120, 250}。集合: 4 本の平均（−1・−0.5・0・0.5・1）。
- 損益: pnl_bp（段階 1 のコスト。建玉の変化分にコスト）。単位露出あたり = 銘柄×年の bp/日 ÷ その年の平均 |建玉|。
- 最良単一（歩進）: 年 y の L は、y より前の全年の 15 銘柄プールのシャープが最大のもの（最低 2 年）。
- 統計量: 銘柄×年のセル → 年ごとに銘柄平均 → 年単位の対応ありの差（集合 − 最良単一）と t。
- 帰無: 年ごとに L を無作為に 1 つ選ぶ規則 B 回 → 集合の純損益の z（「集合は無作為な単一より良いか」）。

【測るもの】集合・最良単一・各固定 L の bp/日（単位露出あたり）、差の t と z（前後半・群別）、最良単一が選んだ L の推移、平均露出。

【判定（事前固定・変更禁止）】
all15 で前後半とも 差の t ≥ 2 かつ z ≥ 2 → H1 支持（合図の平均は選択より良い）。前後半とも t ≤ −2 → 逆向きで確定。それ以外は「差なし（ノイズ）」で確定。

【捨てた案の数】約 4: 10 本以上の密な格子（Q171 と重なる）、ボラ調整つき合図、符号でなく連続値（z スコア）の平均、相関で重みづけ。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z（前後半）・選ばれた L の推移を返す。

【実装】自己完結。実行: python3 kensho_lookback_ensemble_q223.py（B=500、1 分以内）／--B 50／--smoke
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

QID = "Q223"
DEFAULT_B = 500
LS = [20, 60, 120, 250]
MIN_SEL_YEARS = 2


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        sigs = {L: tsmom_pos(c, L) for L in LS}; ens = np.mean([sigs[L] for L in LS], axis=0)
        rec = {"time": df["time"].values, "year": yr, "sym": s, "ens": pnl_bp(ens, c, cb), "ens_exp": np.abs(np.r_[0.0, ens[:-1]])}
        for L in LS:
            rec[f"L{L}"] = pnl_bp(sigs[L], c, cb); rec[f"L{L}_exp"] = np.abs(np.r_[0.0, sigs[L][:-1]])
        d = pd.DataFrame(rec); d.loc[: max(LS), [k for k in rec if k not in ("time", "year", "sym")]] = np.nan; frames.append(d)
    cells = pd.concat(frames, ignore_index=True)
    # 銘柄×年: 単位露出あたり bp/日
    sy = cells.drop(columns="time").groupby(["year", "sym"]).mean()
    per = pd.DataFrame({"ens": sy["ens"] / sy["ens_exp"].replace(0, np.nan)})
    for L in LS:
        per[f"L{L}"] = sy[f"L{L}"] / sy[f"L{L}_exp"].replace(0, np.nan)
    per = per.reset_index()
    years = sorted(per["year"].unique())
    # 最良単一（歩進）: プールのシャープ（年×銘柄セルの bp を日次で近似せず、プールの日次損益から）
    daily_pool = cells.groupby("time")[[f"L{L}" for L in LS]].mean()  # 日付ごとの 15 銘柄プール平均
    pool_years = daily_pool.index.year.values
    chosen = {}
    for y in years:
        prior = [yy for yy in years if yy < y]
        if len(prior) < MIN_SEL_YEARS:
            continue
        m = np.isin(pool_years, prior)
        sh = {L: sharpe_ann(daily_pool.loc[m, f"L{L}"].dropna().values) for L in LS}
        chosen[y] = max(sh, key=lambda L: (sh[L] if np.isfinite(sh[L]) else -np.inf))
    per["best_wf"] = [row[f"L{chosen[y]}"] if y in chosen else np.nan for y, row in zip(per["year"], per.to_dict("records"))]
    per = per[per["year"].isin(chosen.keys())]

    def summarize(per, col_a="ens", col_b="best_wf"):
        out = {}
        for g, members in GROUPS.items():
            pg = per[per["sym"].isin(members)]
            for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
                d = pg[(pg["year"] >= y0) & (pg["year"] < y1)]
                if d.empty:
                    continue
                yr = d.drop(columns="sym").groupby("year").mean(); dd = yr[col_a] - yr[col_b]
                r = {"n_years": int(len(yr)), "ens_bp": float(yr["ens"].mean()), "ens_t": tstat(yr["ens"].values), "best_wf_bp": float(yr["best_wf"].mean()),
                     "diff_bp": float(dd.mean()), "diff_t": tstat(dd.values)}
                for L in LS:
                    r[f"L{L}_bp"] = float(yr[f"L{L}"].mean())
                out[f"{g}_{pn}"] = r
        return out
    obs = summarize(per)
    null = {k: [] for k in obs}
    yrs_sel = sorted(chosen.keys())
    for b in range(args.B):
        pick = {y: LS[int(rng.integers(0, len(LS)))] for y in yrs_sel}
        per["rand"] = [row[f"L{pick[y]}"] for y, row in zip(per["year"], per.to_dict("records"))]
        st = summarize(per, "ens", "rand")
        for k in obs:
            if k in st:
                null[k].append(st[k]["diff_bp"])
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["diff_bp"], null[k]); summary[k] = {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}; summary[k]["ens_minus_random_z"] = f(z)
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "diff_t") >= 2 and g(p, "ens_minus_random_z") >= 2 for p in (pre, post)):
        verdict = "支持: 合図の平均は最良単一の選択より標本外で良い"
    elif g(pre, "diff_t") <= -2 and g(post, "diff_t") <= -2:
        verdict = "逆向きで確定: 合図の平均は最良単一より悪い"
    else:
        verdict = "ノイズ: 前後半で揃った差はない"
    res = {"question": "参照日数の合図平均は最良単一の参照日数より標本外で良いか", "settings": {"L": LS, "min_sel_years": MIN_SEL_YEARS, "B": args.B}, "missing": missing,
           "chosen_L_by_year": {int(y): int(L) for y, L in chosen.items()}, "mean_exposure": {"ens": f(cells["ens_exp"].mean()), **{f"L{L}": f(cells[f"L{L}_exp"].mean()) for L in LS}},
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の差の t と z の 4 本。固定 L・群別は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
