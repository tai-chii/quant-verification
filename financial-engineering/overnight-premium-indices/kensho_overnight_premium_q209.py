#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q209: 株価指数・金の夜間（現物取引時間外）リターンは日中より高いか（夜間プレミアム・H1・2017 年以降）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Lou, Polk, Skouras (2019) "A tug of war: Overnight versus intraday expected returns" JFE 134(1) — 米株の平均リターンのほぼ全部が
  夜間（引け→翌寄り）に発生し、日中はゼロ近傍（表 1・図 1）。Knuteson (2016 以降の一連の SSRN 論文) も同じ観察。
  関連知見: Q173（為替の夜間→日中の逆張りは残らない）、Q176（日中モメンタムは公表後に残らない）。
  → 本案は CFD の 24 時間 H1 で、現物取引時間（UTC 14〜20 時）とそれ以外に分けて、平均リターンの差と「夜間だけ持つ」規則の純損益を測る。

【仮説（測る前に固定）】
H1: US500・USTECH の 1 日のリターンのうち、夜間（UTC 20 時→翌 14 時）の平均は日中（14→20 時）の平均より高い（2 指数の平均で帰無 z ≥ 2、前後半とも）。
H0: 差は 0 と区別できない。XAUUSD は記述（COMEX の時間が違う）。

【データ】US500・USTECH H1_dukascopy（2011-09〜2026-06）、XAUUSD H1_dukascopy（2008〜）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 日中窓: UTC 14:00〜20:00（夏時間の 13:30〜20:00 と冬時間の 14:30〜21:00 の近似。固定）。日中リターン = 14 時始値→20 時終値、夜間 = 20 時終値→翌 14 時始値（対数）。
- 統計量: 年ごとの夜間平均 − 日中平均 [bp/日]。2 指数の平均を年単位に → t。
- 帰無: 日中窓の開始時刻を 0〜23 からランダムに選ぶ（幅 6 時間を保つ）B 回 → 観測の差の z（「14〜20 時という特定の窓」が特別かを測る）。
- 売買可能性（記述）: 「夜間だけ買い持ち」（1 日 1 往復コスト）と「日中だけ買い持ち」の純損益、買い持ちとの比較。

【測るもの】夜間・日中の平均 bp/日、差の年単位 t と z（前後半）、夜間のみ・日中のみの純損益 t、XAUUSD の同じ数値。

【判定（事前固定・変更禁止）】
2 指数平均で前後半とも 差の t ≥ 2 かつ z ≥ 2 → H1 支持（夜間プレミアムあり）。前後半のどちらかで t < 2 → 棄却。
純損益（コスト後）が正かは別に記述（判定に使わない）。

【捨てた案の数】約 4: 夏冬時間の厳密な切替（Dukascopy の時刻の扱いが不確か）、現物ではなく先物時間、引け前 1 時間の分解、XAUUSD を判定に含める。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z・Lou 2019 表 1 の夜間・日中の値を返す。

【実装】自己完結。実行: python3 kensho_overnight_premium_q209.py（B=300、1 分以内）／--B 30／--smoke
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

QID = "Q209"
DEFAULT_B = 300
IDX = ["US500", "USTECH"]; EXTRA = ["XAUUSD"]
DAY_START, DAY_LEN = 14, 6


def split_day_night(h1, start, length):
    """各暦日（UTC）について、日中 = start 時の始値→(start+length) 時の終値、夜間 = 前日の (start+length) 時の終値→当日 start 時の始値（対数 bp）。"""
    df = h1.copy(); df["date"] = df["time"].dt.floor("D")
    o = df[df["hour"] == start].set_index("date")["open"]
    end_h = (start + length - 1) % 24
    c = df[df["hour"] == end_h].set_index("date")["close"]
    if end_h < start:  # 窓が日をまたぐ
        c.index = c.index - pd.Timedelta(days=1)
    d = pd.DataFrame({"o": o, "c": c}).dropna()
    d["day"] = np.log(d["c"] / d["o"]) * 1e4
    d["night"] = np.log(d["o"] / d["c"].shift(1)) * 1e4
    d = d.dropna(); d["year"] = d.index.year
    # 翌暦日が 1 日以上離れる（週末）夜間も含める（週末のリターンも夜間に帰属。記述に n を残す）
    return d


def yearly_diff(d, y0=0, y1=9999):
    x = d[(d["year"] >= y0) & (d["year"] < y1)].groupby("year")[["night", "day"]].mean()
    return x


def run(args, rng):
    syms, missing = syms_available(IDX + EXTRA, kind="H1_dukascopy", smoke=args.smoke)
    h1 = {s: load_h1(s, args.smoke, rng) for s in syms}
    obs = {}; store = {}
    for s in syms:
        d = split_day_night(h1[s], DAY_START, DAY_LEN); store[s] = d
        r = {"n_days": int(len(d))}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            x = yearly_diff(d, y0, y1)
            if x.empty:
                continue
            diff = x["night"] - x["day"]
            # 売買可能性: 夜間のみ買い（1 日 1 往復）・日中のみ買い
            cost_rt = COST_RT[s] / d["o"].mean() * 1e4
            dd = d[(d["year"] >= y0) & (d["year"] < y1)]
            yn = (dd["night"] - cost_rt).groupby(dd["year"]).mean(); yd = (dd["day"] - cost_rt).groupby(dd["year"]).mean()
            r[pn] = {"n_years": int(len(x)), "night_bp": float(x["night"].mean()), "day_bp": float(x["day"].mean()), "diff_bp": float(diff.mean()), "diff_t": tstat(diff.values),
                     "night_only_net_bp": float(yn.mean()), "night_only_net_t": tstat(yn.values), "day_only_net_bp": float(yd.mean()), "day_only_net_t": tstat(yd.values)}
        obs[s] = r
    # 2 指数の平均（判定用）
    avail_idx = [s for s in IDX if s in store]
    def idx_avg(dstore, y0, y1):
        xs = [yearly_diff(dstore[s], y0, y1) for s in avail_idx]
        if not xs or any(x.empty for x in xs):
            return pd.Series(dtype=float)
        return sum((x["night"] - x["day"]) for x in xs) / len(xs)
    obs_idx = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        dser = idx_avg(store, y0, y1)
        obs_idx[pn] = {"n_years": int(len(dser)), "diff_bp": float(dser.mean()) if len(dser) else float("nan"), "diff_t": tstat(dser.values)}
    null = {pn: [] for pn in obs_idx}
    for b in range(args.B):
        st = int(rng.integers(0, 24))
        dst = {s: split_day_night(h1[s], st, DAY_LEN) for s in avail_idx}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            dser = idx_avg(dst, y0, y1); null[pn].append(float(dser.mean()) if len(dser) else np.nan)
        if b % 50 == 0:
            print("null", b)
    summary_idx = {}
    for pn, v in obs_idx.items():
        z, _ = z_of(v["diff_bp"], null[pn]); summary_idx[pn] = {**{k: (f(x) if isinstance(x, float) else x) for k, x in v.items()}, "diff_z": f(z)}
    per_sym = {s: {k: ({kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in r.items()} for s, r in obs.items()}
    pre, post = summary_idx.get("pre", {}), summary_idx.get("post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "diff_t") >= 2 and g(p, "diff_z") >= 2 for p in (pre, post)):
        verdict = "支持: 株価指数の夜間リターンは日中より高い（夜間プレミアムあり）"
    elif g(pre, "diff_t") < 2 or g(post, "diff_t") < 2:
        verdict = "棄却: 前後半のどちらかで差の t<2"
    else:
        verdict = "未確定"
    res = {"question": "株価指数・金の夜間リターンは日中より高いか", "settings": {"day_window_utc": [DAY_START, DAY_START + DAY_LEN], "B": args.B}, "missing": missing,
           "index_average": summary_idx, "per_symbol": per_sym, "machine_verdict": verdict,
           "multiple_comparisons": "判定は 2 指数平均の前後半の t と z の 4 本。銘柄別・XAUUSD・純損益は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
