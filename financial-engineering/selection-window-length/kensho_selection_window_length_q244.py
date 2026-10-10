#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q244: 参照日数の選択窓の長さ（1・2・3・5・8 年）で、順張りの標本外純損益は変わるか（15 銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q244 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q177（選び直す頻度では標本外は変わらない）、知見 Q188（台地選択でも変わらない）、知見 Q139（候補数 J で楽観は増える）、
  知見 Q141（固定 3 年窓）、知見 Q155（エンバーゴ日数で標本外は単調に減る）。Pesaran & Timmermann (2007)（構造変化下の推定窓の選択・本文未読）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "lookback window length parameter selection out-of-sample trend following estimation window 1 year vs 10 years"）:
  Inoue・Jin・Rossi（UPF・ローリング窓の選択）、arXiv 2609.29887（コスト考慮の窓サイズ選択）、Quantpedia「Designing Robust Trend-Following System」。
  手元の 15 銘柄で窓の長さだけを 5 水準に動かし、同じセルで対応ありに比べ、ランダムな L を帰無に置く形は未確認。条件の穴（Q177・Q188 の続き）。

【仮説（測る前に固定）】
H: 選択窓を長くするほど、翌年（標本外）の純損益は高い（窓 W と標本外純損益の間に単調な関係がある）。
対立（Q177・Q188 と同じ）: 窓の長さでは変わらない。

【データ】15 銘柄の UTC 日足（D1_fromH1、2008〜2026-06）。

【定義（1通りに固定）】
- 候補 L ∈ {5, 10, …, 300}（60 通り）。TSMOM の日次純損益（片道コスト段階1）。
- テスト年 t に対し、窓 W ∈ {1, 2, 3, 5, 8} 年の直前 W 暦年で平均純損益が最大の L を選び、年 t の純損益（bp/日）を標本外とする。
- セル = (銘柄, t) で、**W=8 が取れるセルだけ**を全 W で共通に使う（FX8 は t ≥ 2016、油・指数は t ≥ 2020、BTC は手元の長さ次第）。
- 群 all15・fx8・trend7、期間: 前半（t ≤ 2020）／後半（t ≥ 2021）／全期間（テスト年が 2016〜2026 なので区切りは 2021）。

【測るもの】W ごとの標本外純損益の年平均、W=8 − W=1 の対応ありの差と年単位の t、W の 5 点と群平均の Spearman。
参考: ランダムな L の標本外（B=300）に対する各 W の z。

【帰無】各セルで L を一様ランダムに選ぶ B=300 → 標本外純損益の分布（どの W も選択がランダムに勝つかの参照）。

【判定（事前固定・変更禁止）】
- all15 で前半・後半とも Spearman(W, 群平均) ≥ 0.9 かつ W=8 − W=1 の t ≥ 2 → 支持（長い窓ほど良い）。
- 前半・後半とも Spearman ≤ −0.9 かつ t ≤ −2 → 逆向きで確定（短い窓ほど良い）。
- それ以外 → 棄却（窓の長さでは変わらない。Q177・Q188 と同じ）。
多重比較: 判定は all15 前後半の (Spearman, t) 4 本。群別・帰無の z は記述。

【捨てた案の数】約4: 拡大窓（W=全履歴）を足す案、月次で選び直す案（Q177）、半減期つきの重み（指数加重）、シャープで選ぶ案。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・W 別の標本外と Spearman・t を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_selection_window_length_q244.py            （B=300・1 分前後）
      python3 kensho_selection_window_length_q244.py --smoke
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

QID = "Q244"
DEFAULT_B = 300
LS = list(range(5, 301, 5))
WS_ = [1, 2, 3, 5, 8]
SPLIT_TEST = 2021
MIN_DAYS_PER_YEAR = 100


def yearly_pnl_matrix(df, sym):
    """年×L の純損益平均（bp/日）と年ごとの日数。"""
    c = df["close"].values; cb = cost_bp_oneway(sym, c); yr = df["year"].values
    years = sorted(set(yr)); M = np.full((len(years), len(LS)), np.nan); nd = np.zeros(len(years), int)
    for j, L in enumerate(LS):
        p = pnl_bp(tsmom_pos(c, L), c, cb); p[:L + 1] = np.nan
        s = pd.Series(p).groupby(yr).agg(["mean", "count"])
        for i, y in enumerate(years):
            if y in s.index and s.loc[y, "count"] >= MIN_DAYS_PER_YEAR:
                M[i, j] = s.loc[y, "mean"]; nd[i] = int(s.loc[y, "count"])
    return years, M


def cells_table(store):
    rows = []
    for sym, (years, M) in store.items():
        for i, t in enumerate(years):
            if i < 8 or np.isnan(M[i]).any():
                continue
            win_ok = all(not np.isnan(M[i - w: i]).any() for w in WS_)
            if not win_ok:
                continue
            rec = {"sym": sym, "year": t}
            for w in WS_:
                sel = M[i - w: i].mean(axis=0); j = int(np.nanargmax(sel)); rec[f"oos_W{w}"] = float(M[i, j]); rec[f"L_W{w}"] = LS[j]
            rec["oos_mean_random"] = float(np.nanmean(M[i]))  # ランダム L の期待値
            rows.append(rec)
    return pd.DataFrame(rows)


def summarize(cells):
    out = {}
    for g, members in GROUPS.items():
        cg = cells[cells["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_TEST)), ("post", (SPLIT_TEST, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            yr = d.groupby("year")[[f"oos_W{w}" for w in WS_] + ["oos_mean_random"]].mean()
            means = [float(yr[f"oos_W{w}"].mean()) for w in WS_]
            dd = (yr["oos_W8"] - yr["oos_W1"]).dropna()
            out[f"{g}_{pn}"] = {"n_cells": int(len(d)), "n_years": int(len(yr)), "oos_by_W_bp": {str(w): f(m) for w, m in zip(WS_, means)},
                                "spearman_W": f(spearman(WS_, means)), "diff_W8_W1_bp": f(dd.mean()), "diff_W8_W1_t": f(tstat(dd.values)),
                                "random_L_mean_bp": f(yr["oos_mean_random"].mean())}
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    store = {}
    for s in syms:
        if args.smoke:  # 合成データは 2008 年から長めに（W=8 のセルを作るため。判定には使わない）
            df = _smoke_ohlc(s, rng, n=5000, freq="D", start="2008-01-01"); df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
        else:
            df = load_d1(s)
        store[s] = yearly_pnl_matrix(df, s)
    cells = cells_table(store)
    if cells.empty:
        return {"question": "選択窓の長さ", "machine_verdict": "未確定: W=8 が取れるセルが無い", "missing": missing}, None
    obs = summarize(cells)
    # 帰無: ランダム L の標本外（セルごとに一様）
    null = {k: [] for k in obs}
    for b in range(args.B):
        c2 = cells.copy()
        rnd = []
        for _, r in cells.iterrows():
            years, M = store[r["sym"]]; i = years.index(int(r["year"])); rnd.append(float(M[i, rng.integers(len(LS))]))
        for w in WS_:
            c2[f"oos_W{w}"] = rnd
        st = summarize(c2)
        for k in obs:
            if k in st:
                null[k].append(st[k]["oos_by_W_bp"]["1"])
        if b % 100 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        summary[k] = {**v, "z_vs_random_by_W": {str(w): f(z_of(v["oos_by_W_bp"][str(w)], null[k])[0]) for w in WS_}}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, q: (p.get(q) if p.get(q) is not None else float("nan"))
    if all(g(p, "spearman_W") >= 0.9 and g(p, "diff_W8_W1_t") >= 2 for p in (pre, post)):
        verdict = "支持: 長い窓ほど標本外が良い"
    elif all(g(p, "spearman_W") <= -0.9 and g(p, "diff_W8_W1_t") <= -2 for p in (pre, post)):
        verdict = "逆向きで確定: 短い窓ほど良い"
    else:
        verdict = "棄却: 窓の長さでは変わらない（Q177・Q188 と同じ）"
    res = {"question": "参照日数の選択窓の長さで標本外純損益は変わるか", "settings": {"L": [LS[0], LS[-1], 5], "W": WS_, "split_test_year": SPLIT_TEST, "B": args.B}, "missing": missing,
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の (Spearman, t) 4 本。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
