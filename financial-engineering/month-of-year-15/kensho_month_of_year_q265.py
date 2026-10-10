#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q265: 15銘柄の月別季節性（month-of-year）は Holm 後に前後半で同符号で残るか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q265 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- 知見 Q206（曜日効果は残らない）・Q238（ハロウィン）・Q181（月替わり）、arXiv 2003.11027（金の年末効果）、Consensus Economics の季節パターン（解説）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "month of the year seasonality currencies gold oil stock indices December dollar effect 2008-2024 multiple testing"）:
  見つかったもの: arXiv 2003.11027（金の年末）、CXO「Gold seasonality drivers」、DailyFX・Forex.com の季節性（ブログ）。
  未確認: 15 銘柄 × 12 か月を Holm・前後半同符号・年内並べ替え帰無で一括判定する形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 15 銘柄 × 12 か月 = 180 本の「その月の平均日次リターン − 他の月の平均」を Holm で補正すると、前後半で同符号かつ両方 Holm 有意に残る (銘柄, 月) は 0。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
セル (s, m): 月 m の日次リターン平均 − 他の月の平均 [bp/日]。p は月ラベルの年内並べ替え（perm_within・年）B=1000 の両側。Holm は 180 本で。

【測るもの】
前後半それぞれ Holm 有意の本数、両期間で同符号かつ両方有意の本数。

【帰無】
月ラベルを年内で並べ替え B=5000（セルごとの p。Holm 180 本の最小 0.05/180≈0.00028 に届くよう B≥4000）。

【判定（事前固定・変更禁止）】
両期間で同符号かつ Holm 有意の本数 = 0 → 支持（季節性は残らない）。≥3 → 棄却（残る。セルを書く）。1〜2 → 未確定。
多重比較: 180 本 × 2 期間を Holm で補正。判定は本数 1 本。

【捨てた案の数】
約3: 旧暦・四半期、月内の半分（Q181 と混ざる）、ドル因子で合成。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_month_of_year_q265.py            （B=5000・中（B=5000×15 銘柄・2〜3 分））
      python3 kensho_month_of_year_q265.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q265"
DEFAULT_B = 5000
ALPHA = 0.05


def month_cells(r, month, year, rng, B):
    """12 セルの 観測 [bp/日]（その月の平均 − 他の月の平均）と、月ラベルの年内並べ替えによる両側 p。
    行列化: 月の one-hot M（n×12）→ 和 = r @ M。"""
    n = len(r)
    tot = r.sum()
    M = np.zeros((n, 12)); M[np.arange(n), month - 1] = 1.0
    cnt = M.sum(0)
    def stat(Mx):
        sm = r @ Mx
        c = Mx.sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where((c > 0) & (n - c > 0), sm / c - (tot - sm) / (n - c), np.nan)
    obs = stat(M)
    ge = np.zeros(12)
    for b in range(B):
        mp = perm_within(rng, month.astype(float), year).astype(int)
        Mp = np.zeros((n, 12)); Mp[np.arange(n), mp - 1] = 1.0
        nb = stat(Mp)
        ge += (np.abs(nb) >= np.abs(obs)).astype(float)
    p = (ge + 1) / (B + 1)
    return obs, p, cnt


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    rows = []
    periods = {"pre": (0, SPLIT_YEAR), "post": (SPLIT_YEAR, 9999)}
    for s in syms:
        if args.smoke:
            df = _smoke_ohlc(s, rng, n=5000, freq="D", start="2008-01-01")
            df = df[df["high"] != df["low"]].reset_index(drop=True); df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
        else:
            df = load_d1(s, args.smoke, rng)
        df = df.dropna(subset=["ret"])
        r_all = df["ret"].values * 1e4; mo_all = df["time"].dt.month.values; yr_all = df["year"].values
        for p, (y0, y1) in periods.items():
            m = (yr_all >= y0) & (yr_all < y1)
            if m.sum() < 250:
                continue
            obs, pv, cnt = month_cells(r_all[m], mo_all[m], yr_all[m], rng, args.B)
            for k in range(12):
                rows.append({"sym": s, "month": k + 1, "period": p, "diff_bp": obs[k], "p_perm": pv[k], "n_days": int(cnt[k])})
    cells = pd.DataFrame(rows)
    if cells.empty:
        return {"question": "月の季節性は Holm 補正後に前後半で残るか", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない", "settings": {}, "multiple_comparisons": ""}, None
    cells["p_holm"] = np.nan
    for p in periods:
        m = (cells["period"] == p) & np.isfinite(cells["p_perm"])
        cells.loc[m, "p_holm"] = holm(cells.loc[m, "p_perm"].values)
    cells["sig"] = cells["p_holm"] < ALPHA
    wide = cells.pivot(index=["sym", "month"], columns="period", values=["diff_bp", "sig", "p_holm"])
    have_both = all(p in wide["sig"].columns for p in periods)
    summary = {}
    for p in periods:
        sub = cells[cells["period"] == p]
        summary[p] = {"n_cells": int(len(sub)), "n_holm_sig": int(sub["sig"].sum()), "min_p_holm": f(sub["p_holm"].min()),
                      "sig_cells": [f"{r.sym}-{r.month:02d}({r.diff_bp:+.1f}bp)" for r in sub[sub["sig"]].itertuples()]}
    if have_both:
        both = wide[(wide["sig"]["pre"] == True) & (wide["sig"]["post"] == True) &
                    (np.sign(wide["diff_bp"]["pre"]) == np.sign(wide["diff_bp"]["post"]))]
        n_both = int(len(both))
        both_list = [f"{s}-{m:02d}(pre {a:+.1f}, post {b:+.1f} bp)" for (s, m), a, b in zip(both.index, both["diff_bp"]["pre"], both["diff_bp"]["post"])]
        # 符号だけの一致（参考）
        same_sign = int((np.sign(wide["diff_bp"]["pre"]) == np.sign(wide["diff_bp"]["post"])).sum())
    else:
        n_both = None; both_list = []; same_sign = None
    summary["both"] = {"n_same_sign_and_both_sig": n_both, "cells": both_list, "n_same_sign_any": same_sign,
                       "n_cells_compared": int(len(wide)) if have_both else 0}
    if n_both is None:
        verdict = "未確定: 計算できない"
    elif n_both == 0:
        verdict = "支持: 両期間で同符号かつ Holm 有意の本数 = 0（季節性は残らない）"
    elif n_both >= 3:
        verdict = f"棄却: 本数 {n_both} ≥3（残る）: " + "; ".join(both_list)
    else:
        verdict = f"未確定: 本数 {n_both}（1〜2）: " + "; ".join(both_list)
    res = {"question": "15 銘柄 × 12 か月の季節性は Holm 補正後に前後半で同符号・両方有意で残るか",
           "settings": {"syms": SYMS, "split_year": SPLIT_YEAR, "B": args.B, "alpha": ALPHA, "n_tests_per_period": 180,
                        "null": "月ラベルを年内で並べ替え（perm_within・年）・両側 p=(k+1)/(B+1)", "min_days_per_period": 250},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "180 本 × 2 期間を期間ごとに Holm で補正。判定は本数 1 本。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
