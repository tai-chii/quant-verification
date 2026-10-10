#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q216: 出来高（ティック数）が多い日のリターンは翌日に続きやすく、少ない日は反転しやすいか（Campbell・Grossman・Wang 1993 の型・15 銘柄）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Campbell, Grossman, Wang (1993) "Trading Volume and Serial Correlation in Stock Returns" QJE 108(4) — 出来高が多い日のリターンは
  翌日に反転しやすい（1 次自己相関が出来高とともに下がる。表 II・式 (17)）。Conrad, Hameed, Niden (1994) J. Finance も同じ方向。
  一方 Llorente ほか (2002) RFS は情報取引が多い銘柄では高出来高で継続。関連知見: Q174（ボラの変化と逆張り）、Q016（超短期の平均回帰は消えた）。
  → 本案は Dukascopy のティック数を出来高の代理にして、15 銘柄の日足で r_{t+1} = a + b1·r_t + b2·r_t·V_t の b2 の符号を測る（CGW は b2 < 0）。

【仮説（測る前に固定）】
H1: b2 < 0（出来高が多い日のリターンは翌日に反転しやすい＝CGW）。帰無（V を年内で並べ替え）に対し z ≤ −2（前後半とも）。
対立の H1': b2 > 0（高出来高は継続）。z ≥ 2 で前後半とも揃えば「逆向きで確定」。
H0: b2 は 0 と区別できない。

【データ】15 銘柄 H1_dukascopy を UTC 0 時区切りの日足に束ね、volume（ティック数）を日ごとに合計（D1_fromH1 に volume が無いため）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- V_t = log(volume_t ÷ 直前 20 日の volume の平均)（当日を含まない）。
- 回帰: 銘柄×年のセルで OLS（r は bp）。b1（素の自己相関）と b2（交互作用）を年ごとに銘柄平均 → 年平均と t。
- 帰無: V_t を銘柄×年の中で並べ替え B 回 → b2 の年平均の z。
- 売買（記述）: 出来高上位 1/5 の日の翌日に逆張り（コスト後）と、下位 1/5 の日の翌日に逆張り。

【測るもの】b1・b2 の年平均と t・z（前後半・群別）、上位・下位 1/5 の逆張りの純損益。

【判定（事前固定・変更禁止）】
all15 で前後半とも b2 < 0 かつ z ≤ −2 → H1 支持（CGW の型）。前後半とも b2 > 0 かつ z ≥ 2 → 逆向きで確定（高出来高は継続）。
それ以外は棄却（出来高はリターンの続き方を変えない）。

【捨てた案の数】約 4: 実出来高（CFD のティック数しかない）、出来高の水準でなく変化、週次の集計、ボラとの同時制御（V とボラは相関。記述に ρ を残す）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・b2 の z（前後半）・CGW 1993 表 II の符号を返す。

【実装】自己完結。実行: python3 kensho_volume_interaction_q216.py（B=500、2 分前後）／--B 50／--smoke
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

QID = "Q216"
DEFAULT_B = 500
W_VOL = 20


def coefs(cells, vcol="V"):
    rows = []
    for (s, y), d in cells.groupby(["sym", "year"]):
        r, rn, v = d["r"].values, d["rn"].values, d[vcol].values
        m = np.isfinite(r) & np.isfinite(rn) & np.isfinite(v)
        if m.sum() < 60:
            continue
        X = np.c_[np.ones(m.sum()), r[m], r[m] * v[m]]
        beta = np.linalg.lstsq(X, rn[m], rcond=None)[0]
        rows.append({"sym": s, "year": y, "b1": beta[1], "b2": beta[2]})
    return pd.DataFrame(rows)


def summarize(cf):
    out = {}
    for g, members in GROUPS.items():
        cg = cf[cf["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            yr = d.drop(columns="sym").groupby("year").mean()
            out[f"{g}_{pn}"] = {"n_years": int(len(yr)), "b1": float(yr["b1"].mean()), "b1_t": tstat(yr["b1"].values), "b2": float(yr["b2"].mean()), "b2_t": tstat(yr["b2"].values)}
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, kind="H1_dukascopy", smoke=args.smoke)
    frames = []; trade = []
    for s in syms:
        d1 = h1_to_d1(load_h1(s, args.smoke, rng), 0)
        vol = d1["volume"].values.astype(float); vm = pd.Series(vol).shift(1).rolling(W_VOL).mean().values
        V = np.log(np.where((vol > 0) & (vm > 0), vol / vm, np.nan))
        r = d1["ret"].values * 1e4; rn = np.r_[r[1:], np.nan]
        frames.append(pd.DataFrame({"sym": s, "year": d1["year"].values, "r": r, "rn": rn, "V": V, "absr": np.abs(r)}))
        # 売買（記述）: 上位・下位 1/5 の翌日逆張り
        c = d1["close"].values; cb = cost_bp_oneway(s, c)
        q_hi = pd.Series(V).expanding(250).quantile(0.8).values; q_lo = pd.Series(V).expanding(250).quantile(0.2).values
        for name, sel in (("hi", V >= q_hi), ("lo", V <= q_lo)):
            pos = np.where(sel & np.isfinite(r), -np.sign(np.nan_to_num(r)), 0.0); p = pnl_bp(pos, c, cb)
            yr = pd.Series(p).groupby(d1["year"].values).mean(); trade.extend({"sym": s, "year": int(y), "rule": name, "bp": float(v)} for y, v in yr.items())
    cells = pd.concat(frames, ignore_index=True)
    rho_v_absr = float(cells[["V", "absr"]].dropna().corr().iloc[0, 1])
    obs = summarize(coefs(cells))
    key = cells["sym"].astype(str).values + cells["year"].astype(str).values
    null = {k: [] for k in obs}
    for b in range(args.B):
        cells["Vp"] = perm_within(rng, cells["V"].values, key); st = summarize(coefs(cells, "Vp"))
        for k in obs:
            if k in st:
                null[k].append(st[k]["b2"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["b2"], null[k]); summary[k] = {**{kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}, "b2_z": f(z)}
    tr = pd.DataFrame(trade); trade_sum = {}
    for rule in ("hi", "lo"):
        for pn, (y0, y1) in (("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            st = by_year_stats(tr[tr["rule"] == rule], "bp", y0=y0, y1=y1); trade_sum[f"reversal_after_{rule}_vol_{pn}"] = {k: (f(v) if isinstance(v, float) else v) for k, v in st.items()}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "b2") < 0 and g(p, "b2_z") <= -2 for p in (pre, post)):
        verdict = "支持: 高出来高の日のリターンは翌日に反転しやすい（CGW）"
    elif all(g(p, "b2") > 0 and g(p, "b2_z") >= 2 for p in (pre, post)):
        verdict = "逆向きで確定: 高出来高の日のリターンは翌日に続きやすい"
    else:
        verdict = "棄却: 出来高はリターンの続き方を前後半で揃って変えない"
    res = {"question": "出来高が多い日のリターンは翌日に続くか反転するか", "settings": {"W_VOL": W_VOL, "B": args.B}, "missing": missing, "corr_V_absret": f(rho_v_absr),
           "summary": summary, "trade_reference": trade_sum, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の b2 の z の 2 本（両側）。b1・群別・売買は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
