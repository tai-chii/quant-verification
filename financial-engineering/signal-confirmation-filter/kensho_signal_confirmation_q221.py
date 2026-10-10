#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q221: 合図の確認フィルタ（k 日連続同符号で入る）は 15 銘柄の順張りのホイップソーを減らし純損益を上げるか
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: 実務の定番「ダマシ避けの確認（数日続いてから入る）」。学術側では Han, Yang, Zhou (2013) RFS "A New Anomaly: The Cross-Sectional Profitability
  of Technical Analysis" が MA 規則の取引頻度と損益の関係を、Zakamulin (2014) J. Asset Management が MA 規則の「確認」は遅れの一種で平均的には損だと報告。
  関連知見: Q156（約定の遅れは純損益を下げる＝遅れそのものは損）、Q182（複数指標の一致は最良単独を上回らない）。
  → 本案は「遅れ」ではなく「ホイップソー（短い保有の反復）の除去」が狙いの確認フィルタで、取引回数・短い保有の割合・純損益が同時にどう動くかを測る。

【仮説（測る前に固定）】
H1: TSMOM 60 の符号が k=3 日連続で同じになってから入り、反転したら即座に出る規則は、基準（毎日の符号）より取引回数を減らし、
    年ごとの純損益（bp/日）を上げる（年単位 t ≥ 2・帰無 z ≥ 2、前後半とも）。
H0: 差は 0 と区別できない（Q156 の「遅れは損」が勝つなら t ≤ −2）。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 基準: pos = sign(close_t − close_{t−60})。確認 k: 直近 k 日の符号がすべて同じならその符号、違えば直前の建玉を保つ（ただし建玉と逆の符号が出たら 0 にする）。k=3 判定、k=5 記述。
- 損益: pnl_bp（段階 1 のコスト）。銘柄×年のセルで bp/日と取引回数・保有 ≤3 日の取引の割合 → 年ごとに銘柄平均 → 年単位の対応ありの差と t。
- 帰無: Q156 と同じ考え方で「k−1 日の単純な遅れ」（合図を k−1 日遅らせる）を対照にし、確認 − 遅れ の差も報告。
  帰無分布は、基準の建玉のうち確認で外れた日（基準≠確認）の集合を年内で並べ替えた「同じ日数だけ 0 にする」規則 B 回 → z。

【測るもの】k=3 の差の t と z、取引回数の比、短い保有の割合、確認 − 遅れ の差、k=5。

【判定（事前固定・変更禁止）】
all15 で前後半とも 差の t ≥ 2 かつ z ≥ 2 → H1 支持。前後半とも t ≤ −2 → 逆向きで確定（確認は損）。それ以外は未確定。

【捨てた案の数】約 4: 確認を「終値が k 日連続で MA の上」に（規則が変わる）、確認後の遅れ再参入、出口にも確認を入れる（出口の遅れは Q204 の損切りと交錯）、k の格子。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z（前後半）・取引回数の比を返す。

【実装】自己完結。実行: python3 kensho_signal_confirmation_q221.py（B=300、1 分前後）／--B 30／--smoke
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

QID = "Q221"
DEFAULT_B = 300
L_MOM = 60
KS = [3, 5]


def confirm(sig, k):
    pos = np.zeros(len(sig)); p = 0.0
    for t in range(len(sig)):
        if t < k - 1:
            pos[t] = 0.0; continue
        w = sig[t - k + 1: t + 1]
        if p != 0 and sig[t] != p:
            p = 0.0  # 建玉と逆の符号（または 0）が出たら出る
        if p == 0 and w[0] != 0 and np.all(w == w[0]):
            p = w[0]
        pos[t] = p
    return pos


def trade_stats(pos):
    held = np.r_[0.0, pos[:-1]]; chg = np.r_[False, held[1:] != held[:-1]]
    n_tr = int(chg.sum()); lens = np.diff(np.r_[np.where(chg)[0], len(pos)]) if n_tr else np.array([])
    return n_tr, float((lens <= 3).mean()) if len(lens) else float("nan")


def summarize(cells, cols):
    sy = cells.groupby(["year", "sym"]).agg({c: "mean" for c in cols}).reset_index(); out = {}
    for g, members in GROUPS.items():
        cg = sy[sy["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            yr = d.drop(columns="sym").groupby("year").mean(); r = {"n_years": int(len(yr)), "base_bp": float(yr["base"].mean())}
            for c in cols:
                if c != "base":
                    dd = yr[c] - yr["base"]; r[f"{c}_bp"] = float(yr[c].mean()); r[f"diff_{c}_bp"] = float(dd.mean()); r[f"diff_{c}_t"] = tstat(dd.values)
            out[f"{g}_{pn}"] = r
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []; store = {}; tstats = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        sig = tsmom_pos(c, L_MOM); rec = {"year": yr, "sym": s, "base": pnl_bp(sig, c, cb)}
        n0, sh0 = trade_stats(sig); tstats.append({"sym": s, "rule": "base", "n_trades": n0, "short_share": sh0})
        for k in KS:
            pc = confirm(sig, k); rec[f"conf{k}"] = pnl_bp(pc, c, cb)
            lag = np.r_[np.zeros(k - 1), sig[: -(k - 1)]]; rec[f"lag{k}"] = pnl_bp(lag, c, cb)
            n1, sh1 = trade_stats(pc); tstats.append({"sym": s, "rule": f"conf{k}", "n_trades": n1, "short_share": sh1})
            if k == 3:
                store[s] = (yr, sig, pc, c, cb)
        frames.append(pd.DataFrame(rec))
    cells = pd.concat(frames, ignore_index=True)
    cols = ["base"] + [f"conf{k}" for k in KS] + [f"lag{k}" for k in KS]
    obs = summarize(cells, cols)
    null = {k: [] for k in obs}
    for b in range(args.B):
        fr = []
        for s, (yr, sig, pc, c, cb) in store.items():
            off = (sig != pc).astype(float); offp = perm_within(rng, off, yr).astype(bool)
            p = sig.copy(); p[offp] = 0.0
            fr.append(pd.DataFrame({"year": yr, "sym": s, "base": pnl_bp(sig, c, cb), "conf3": pnl_bp(p, c, cb)}))
        st = summarize(pd.concat(fr, ignore_index=True), ["base", "conf3"])
        for k in obs:
            if k in st:
                null[k].append(st[k]["diff_conf3_bp"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["diff_conf3_bp"], null[k]); summary[k] = {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}; summary[k]["diff_conf3_z"] = f(z)
        summary[k]["conf3_minus_lag3_bp"] = f(v["conf3_bp"] - v["lag3_bp"])
    ts = pd.DataFrame(tstats).groupby("rule")[["n_trades", "short_share"]].mean()
    trade_summary = {r: {"n_trades_mean": f(ts.loc[r, "n_trades"]), "short_hold_share": f(ts.loc[r, "short_share"])} for r in ts.index}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "diff_conf3_t") >= 2 and g(p, "diff_conf3_z") >= 2 for p in (pre, post)):
        verdict = "支持: 確認フィルタは順張りの純損益を上げる"
    elif g(pre, "diff_conf3_t") <= -2 and g(post, "diff_conf3_t") <= -2:
        verdict = "逆向きで確定: 確認フィルタは純損益を下げる"
    else:
        verdict = "未確定"
    res = {"question": "合図の確認フィルタはホイップソーを減らし純損益を上げるか", "settings": {"L": L_MOM, "k": KS, "B": args.B}, "missing": missing,
           "summary": summary, "trade_counts": trade_summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の k=3 の差の t と z の 4 本。k=5・遅れ対照・取引回数は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
