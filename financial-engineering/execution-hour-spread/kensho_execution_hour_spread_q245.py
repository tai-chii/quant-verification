#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q245: XAUUSD 順張りの約定時刻を、実測スプレッドの狭い時間に移すと純損益は上がるか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q245 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q081（XAUUSD の時間帯別スプレッド: アジア時間が広い）、知見 Q140（XAUUSD 順張りの損益分岐は実測の約 2 倍）、知見 Q211（日足の区切り時刻で
  純損益は変わらない）、知見 Q156（約定の遅れは損）。[[Feng2026-1_純アルファはコスト容量遅延統制を全部引いた後に残るもの]]。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "execution timing intraday spread gold trading cost hour of day rebalancing cheapest hour"）:
  Talos（BTC の約定時刻）、PlanSponsor（執行コストと時刻）、MQL5 のフォーラム。XAUUSD の実測 bid/ask で「合図は 0 UTC・約定だけ安い時間へ」の
  差を、遅れの損と分けて測る形は未確認。条件の穴。

【仮説（測る前に固定）】
H: 合図（UTC 0 時の日足終値で決める TSMOM60）は変えず、約定だけを「過去 60 日の時刻別スプレッド中央値が最も狭い時刻」（翌日の中で）に
   移すと、スプレッド代の節約が、遅れによる損（Q156）を上回り、純損益が上がる。

【データ】`data_XAUUSD_H1_dukascopy.csv`（bid）・`data_XAUUSD_H1_dukascopy_ask.csv`（ask）、2008〜2026-06。

【定義（1通りに固定）】
- 中値 m = (bid+ask)/2。日足 = UTC 0 時区切りの中値終値。合図 s_d = sign(m_d − m_{d−60})、ポジションの変更は合図が変わった日だけ。
- 既定（A）: 変更を翌日 0 時台の足の終値（= 1:00 UTC の値）で約定。コスト = その足の実測半スプレッド（(ask−bid)/2/m）。
- 移動（B）: 変更を翌日の時刻 h* の足の終値で約定。h* = 直前 60 日の時刻別スプレッド中央値が最小の時刻（t までの値だけ・毎日更新）。
  コストはその足の実測半スプレッド。
- 両者とも保有中の損益は中値の変化（約定時刻から次の約定時刻まで）。純損益 [bp/日] を年×（A, B）で出し、差 B − A の年単位 t。
- 分解（記述）: コストの差（節約分）と、価格の差（0 時→h* の間の動き × 向き）。

【帰無】約定時刻を毎回ランダム（0〜23 時）に選ぶ B=300 → 差（ランダム − A）の分布 → z（B − A がランダムより良いか）。

【判定（事前固定・変更禁止）】
- 前半（<2017）・後半（≥2017）とも 差 B−A > 0 かつ t ≥ 2 かつ z ≥ 2 → 支持。
- それ以外 → 棄却。
多重比較: 判定は前後半の (t, z) 4 本。分解は記述。

【捨てた案の数】約4: 合図も h* で作る案（Q211 と混ざる）、スプレッドの平均（中央値に統一）、指値で待つ案（約定の保証がない）、15 銘柄（ask は XAUUSD だけ）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・差と t・z（前後半）・h* の分布を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_execution_hour_spread_q245.py            （B=300・2 分前後）
      python3 kensho_execution_hour_spread_q245.py --smoke
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

QID = "Q245"
DEFAULT_B = 300
L_MOM = 60
WIN_SP = 60


def load_mid(args, rng):
    if args.smoke:
        bid = _smoke_ohlc("XAUUSD", rng, n=90000, freq="h", start="2010-01-01"); ask = bid.copy()
        hrs = bid["time"].dt.hour.values; sp = bid["close"].values * (0.0002 + 0.0003 * ((hrs < 7) | (hrs > 21))) * np.exp(rng.normal(0, 0.2, len(bid)))
        for col in ("open", "high", "low", "close"):
            ask[col] = bid[col] + sp
    else:
        bid = _read(os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy.csv")); ask = _read(os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy_ask.csv"))
    m = bid[["time", "close"]].merge(ask[["time", "close"]], on="time", suffixes=("_b", "_a"))
    m = m[m["close_a"] > m["close_b"]].reset_index(drop=True)
    m["mid"] = (m["close_a"] + m["close_b"]) / 2; m["half_sp"] = (m["close_a"] - m["close_b"]) / 2 / m["mid"] * 1e4  # 半スプレッド [bp]
    m["date"] = m["time"].dt.floor("D"); m["hour"] = m["time"].dt.hour; m["year"] = m["time"].dt.year
    return m


def build_index(m):
    idx = {(d, h): i for i, (d, h) in enumerate(zip(m["date"].values, m["hour"].values))}
    first = {}
    for i, d in enumerate(m["date"].values):
        if d not in first:
            first[d] = i
    return idx, first


def simulate(m, exec_hour_by_day, daily_sig, days, idx, first):
    """exec_hour_by_day: {date: hour}。合図の変更日 d の翌日 (days の次) の時刻 h の足で約定。損益は約定時点の中値の差。"""
    mid = m["mid"].values; hsp = m["half_sp"].values; n = len(m)
    pos = np.zeros(n); cost = np.zeros(n)
    cur = 0.0; events = []
    for k in range(len(days) - 1):
        d = days[k]; s = daily_sig[k]
        if s == cur or s == 0:
            continue
        nd = days[k + 1]; h = exec_hour_by_day.get(nd, 0)
        i = idx.get((nd, h))
        if i is None:  # その時刻の足が無ければ、その日の最初の足
            i = first.get(nd)
            if i is None:
                continue
        cost[i] += abs(s - cur) * hsp[i]; events.append((i, cur, s)); cur = s
        pos[i:] = s
    held = np.r_[0.0, pos[:-1]]
    r = np.r_[0.0, mid[1:] / mid[:-1] - 1]
    pnl = held * r * 1e4 - cost
    return pnl, cost, events


def yearly(m, pnl, cost):
    df = pd.DataFrame({"year": m["year"].values, "pnl": pnl, "cost": cost}); g = df.groupby("year")
    return pd.DataFrame({"pnl_per_day": g["pnl"].sum() / g.size() * 24, "cost_per_day": g["cost"].sum() / g.size() * 24})


def run(args, rng):
    m = load_mid(args, rng)
    # 日足（UTC 0 時区切り）の中値終値 → 合図
    daily = m.groupby("date").agg(close=("mid", "last")); days = list(daily.index); c = daily["close"].values
    sig = tsmom_pos(c, L_MOM)
    # A: 翌日 0 時台の足。B: 直前 60 日の時刻別スプレッド中央値が最小の時刻
    spd = m.pivot_table(index="date", columns="hour", values="half_sp", aggfunc="median").reindex(days)
    roll = spd.shift(1).rolling(WIN_SP, min_periods=30).median()
    vals = np.where(np.isnan(roll.values), np.inf, roll.values); ok = np.isfinite(vals).any(axis=1)
    hcols = np.array(roll.columns, int); hstar = np.where(ok, hcols[np.argmin(vals, axis=1)], 0)
    hB = {d: int(h) for d, h in zip(days, hstar)}
    hA = {d: 0 for d in days}
    idx, first = build_index(m)
    pA, cA, evA = simulate(m, hA, sig, days, idx, first); pB, cB, evB = simulate(m, hB, sig, days, idx, first)
    yA = yearly(m, pA, cA); yB = yearly(m, pB, cB)
    obs = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        a = yA[(yA.index >= y0) & (yA.index < y1)]; b = yB.reindex(a.index)
        if a.empty:
            continue
        dd = b["pnl_per_day"] - a["pnl_per_day"]
        obs[pn] = {"n_years": int(len(a)), "A_bp_per_day": f(a["pnl_per_day"].mean()), "B_bp_per_day": f(b["pnl_per_day"].mean()), "diff_bp": f(dd.mean()), "diff_t": f(tstat(dd.values)),
                   "cost_saving_bp_per_day": f((a["cost_per_day"] - b["cost_per_day"]).mean()), "price_effect_bp_per_day": f(dd.mean() - (a["cost_per_day"] - b["cost_per_day"]).mean())}
    null = {pn: [] for pn in obs}
    for bb in range(args.B):
        hR = {d: int(rng.integers(0, 24)) for d in days}
        pR, cR, _ = simulate(m, hR, sig, days, idx, first); yR = yearly(m, pR, cR)
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            if pn in obs:
                a = yA[(yA.index >= y0) & (yA.index < y1)]; null[pn].append(float((yR.reindex(a.index)["pnl_per_day"] - a["pnl_per_day"]).mean()))
        if bb % 50 == 0:
            print("null", bb)
    summary = {}
    for pn, v in obs.items():
        z, _ = z_of(v["diff_bp"], null[pn]); summary[pn] = {**v, "diff_z": f(z), "random_hour_diff_mean_bp": f(np.nanmean(null[pn])) if null[pn] else None}
    hdist = pd.Series([hB[d] for d in days]).value_counts().sort_index()
    g = lambda p, k: (summary.get(p, {}).get(k) if summary.get(p, {}).get(k) is not None else float("nan"))
    if all(g(p, "diff_bp") > 0 and g(p, "diff_t") >= 2 and g(p, "diff_z") >= 2 for p in ("pre", "post")):
        verdict = "支持: 狭い時刻への移動で純損益が上がる"
    else:
        verdict = "棄却: 前後半のどちらかで t<2 または z<2"
    res = {"question": "XAUUSD 順張りの約定時刻を実測スプレッドの狭い時間に移すと純損益は上がるか", "settings": {"L": L_MOM, "win_spread": WIN_SP, "B": args.B},
           "n_switches_A": len(evA), "n_switches_B": len(evB), "hstar_distribution": {str(int(k)): int(v) for k, v in hdist.items()}, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は前後半の (t, z) 4 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
