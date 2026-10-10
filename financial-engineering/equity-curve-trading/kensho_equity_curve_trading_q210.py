#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q210: エクイティカーブ・トレーディング（戦略の直近損益で規模を変える）は 15 銘柄の順張りの標本外成績を上げるか
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: 実務の通説「戦略の資産曲線が移動平均を下回ったら規模を落とす」。学術側では Rej, Seager, Bouchaud (2018) "You are in a drawdown. When should
  you start worrying?" Wilmott 2018(93) が下落の長さの統計を、Qian (2020 頃の SSRN) らが「equity-curve trading は損益の自己相関がなければ無効」と報告。
  関連知見: Q184（2 か月窓の順張り成績は窓のドリフトで説明され、腕と局面は分離できない）、Q144（直近成績の順位は次の窓で入れ替わる）。
  → 本案は「戦略の損益に正の自己相関があるか」と「それを使った規模調整が標本外の年ごとのシャープを上げるか」を同時に測る。

【仮説（測る前に固定）】
H1: 直近 20 日の戦略損益が正なら規模 1.5・負なら 0.5 にすると、規模 1 固定より年ごとのシャープが高い（戦略損益に正の自己相関がある）。
H0: 差は 0 と区別できない（損益の自己相関は 0）。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 基準: TSMOM L=60 の符号、規模 1。純損益 pnl_bp（段階 1 のコスト）。
- 規模: w_t = 1.5 if Σ_{t−19..t} pnl > 0 else 0.5（t の終値まで。t+1 に効く）。平均規模はほぼ 1。変種（記述）: 「負なら 0（休む）」。
- 指標: 銘柄×年のセルでシャープ（年率）と bp/日 → 年ごとに銘柄平均 → 対応ありの差の t。
- 自己相関: 銘柄×年のセルで戦略損益の 20 日合計と次の 20 日合計の相関（非重複ブロック）→ 年平均と t。
- 帰無: w_t を年内で並べ替え（過去損益との対応を壊す）B 回 → 差の z。

【測るもの】シャープの差の t と z（前後半）、bp/日の差、20 日ブロック損益の自己相関と t、「休む」変種の差。

【判定（事前固定・変更禁止）】
all15 で前後半とも シャープの差の年単位 t ≥ 2 かつ z ≥ 2 → H1 支持。前後半のどちらかで t < 2 → 棄却（規模の自己調整は効かない）。
自己相関は判定に数えない（記述・解釈の補助）。

【捨てた案の数】約 4: 資産曲線の移動平均（200 日）クロス、下落幅での停止、ポートフォリオ全体の曲線、損益の順位で 3 段階。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z・自己相関の t を返す。

【実装】自己完結。実行: python3 kensho_equity_curve_trading_q210.py（B=300、1 分前後）／--B 30／--smoke
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

QID = "Q210"
DEFAULT_B = 300
L_MOM, W_LOOK, HI, LO = 60, 20, 1.5, 0.5


def cell_stats(cells, cols):
    g = cells.groupby(["year", "sym"]); out = {}
    for c in cols:
        m = g[c].mean(); s = g[c].std(ddof=1)
        out[f"sharpe_{c}"] = (m / s * math.sqrt(252)).replace([np.inf, -np.inf], np.nan); out[f"bp_{c}"] = m
    return pd.DataFrame(out).reset_index()


def summarize(cs, a, b="fix"):
    out = {}
    for g, members in GROUPS.items():
        cg = cs[cs["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            yr = d.drop(columns="sym").groupby("year").mean()
            ds = yr[f"sharpe_{a}"] - yr[f"sharpe_{b}"]; db = yr[f"bp_{a}"] - yr[f"bp_{b}"]
            out[f"{g}_{pn}"] = {"n_years": int(len(yr)), f"sharpe_{a}": float(yr[f"sharpe_{a}"].mean()), f"sharpe_{b}": float(yr[f"sharpe_{b}"].mean()),
                                "sharpe_diff": float(ds.mean()), "sharpe_diff_t": tstat(ds.values), "bp_diff": float(db.mean()), "bp_diff_t": tstat(db.values)}
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []; store = {}; ac = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        sig = tsmom_pos(c, L_MOM); base = pnl_bp(sig, c, cb)
        roll = pd.Series(base).rolling(W_LOOK).sum().values
        w = np.where(np.isnan(roll), 1.0, np.where(roll > 0, HI, LO)); w0 = np.where(np.isnan(roll), 1.0, np.where(roll > 0, 1.0, 0.0))
        ect = pnl_bp(sig * w, c, cb); pause = pnl_bp(sig * w0, c, cb)
        frames.append(pd.DataFrame({"year": yr, "sym": s, "fix": base, "ect": ect, "pause": pause}))
        store[s] = (yr, sig, w, c, cb, base)
        # 20 日ブロックの自己相関（非重複）
        for y in np.unique(yr):
            x = base[yr == y]; nb = len(x) // W_LOOK
            if nb >= 4:
                blocks = x[: nb * W_LOOK].reshape(nb, W_LOOK).sum(axis=1)
                if blocks[:-1].std() > 0 and blocks[1:].std() > 0:
                    ac.append({"sym": s, "year": y, "ac": float(np.corrcoef(blocks[:-1], blocks[1:])[0, 1])})
    cells = pd.concat(frames, ignore_index=True)
    obs = summarize(cell_stats(cells, ["fix", "ect"]), "ect"); obs_pause = summarize(cell_stats(cells, ["fix", "pause"]), "pause")
    acd = pd.DataFrame(ac); ac_sum = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        st = by_year_stats(acd, "ac", y0=y0, y1=y1); ac_sum[pn] = {k: (f(v) if isinstance(v, float) else v) for k, v in st.items()}
    null = {k: [] for k in obs}
    for b in range(args.B):
        fr = []
        for s, (yr, sig, w, c, cb, base) in store.items():
            wp = perm_within(rng, w, yr); fr.append(pd.DataFrame({"year": yr, "sym": s, "fix": base, "ect": pnl_bp(sig * wp, c, cb)}))
        st = summarize(cell_stats(pd.concat(fr, ignore_index=True), ["fix", "ect"]), "ect")
        for k in obs:
            if k in st:
                null[k].append(st[k]["sharpe_diff"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["sharpe_diff"], null[k]); summary[k] = {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}; summary[k]["sharpe_diff_z"] = f(z)
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "sharpe_diff_t") >= 2 and g(p, "sharpe_diff_z") >= 2 for p in (pre, post)):
        verdict = "支持: 直近損益で規模を変えるとシャープが上がる"
    elif g(pre, "sharpe_diff_t") < 2 or g(post, "sharpe_diff_t") < 2:
        verdict = "棄却: 前後半のどちらかで t<2"
    else:
        verdict = "未確定"
    res = {"question": "エクイティカーブ・トレーディングは順張りの標本外成績を上げるか", "settings": {"L": L_MOM, "W_LOOK": W_LOOK, "HI": HI, "LO": LO, "B": args.B}, "missing": missing,
           "summary": summary, "pause_variant": {k: {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in obs_pause.items()},
           "pnl_block_autocorr": ac_sum, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半のシャープの差の t と z の 4 本。休む変種・自己相関・群別は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
