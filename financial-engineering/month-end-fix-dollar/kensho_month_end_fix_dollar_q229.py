#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q229: 月末のロンドン16時フィキシング前のドルの向きは、その月の US500 リターンと逆か（Melvin・Prins 2015 の型）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q229 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Melvin, M. & Prins, J. (2015) "Equity hedging and exchange rates at the London 4pm fix", J. Financial Markets 22
  （月末に外国人投資家が米国株のヘッジを調整するため、その月に米国株が上がるとフィキシングに向けてドルが売られる。本文未読・
  ECB 第3回 FX ワークショップの発表スライド 2013-11 の要旨のみ）。
- [[Krohn2024-1_ドルはフィキシングに向けて上がりその後に下がり一日の中でW字になる]]・知見 Q056（フィキシングの V 字は 2020 年以降弱い）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "month-end London 4pm fix dollar return equity rebalancing Melvin Prins"）:
  原論文と銀行のレポート（Barclays・BofA の月末モデル）が見つかる。手元の Dukascopy H1 で 2012〜2026 を前後半に分けて
  条件つき（その月の株の向き）で測る形は未確認。追試＋条件の穴（2017 年以降）。

【仮説（測る前に固定）】
H: 月末（その月の最後の営業日）のロンドン 15:00〜16:00（フィキシング前の 1 時間）のドルのリターンは、
   その月の US500 のリターンが正のとき負（ドル売り）、負のとき正（ドル買い）。差 D = E[usd | 上げ月] − E[usd | 下げ月] < 0。

【データ】
- FX6（EURUSD・GBPUSD・AUDUSD・USDJPY・USDCHF・USDCAD）の H1（Dukascopy・UTC）2012-01〜2026-06。
- US500 の UTC 日足（D1_fromH1・2011-09〜）。月のリターンは「前月末の終値 → 月末日の前日の終値」（フィキシングの前に分かる値だけ）。
- 無い銘柄は除き JSON の missing に書く。

【定義（1通りに固定）】
- ドルのリターン [bp]: ドルが分子の組（USDJPY・USDCHF・USDCAD）は +ret、分母の組（EURUSD・GBPUSD・AUDUSD）は −ret。
  時刻ごとに利用できる組の平均（等加重）。
- 時刻: UTC をロンドン時刻（Europe/London・夏時間込み）に直し、ロンドン時刻 15 時台の足（15:00→16:00）をフィキシング前、
  16 時台をフィキシング後（記述）とする。
- 月末日: ロンドン日付で、その月に 15 時台の足がある最後の日。
- 対照: 月末でない日の 15 時台のドルのリターン（同じ月の月初〜前日の US500 リターンで同じ条件づけ）。

【測るもの】
- D（月末・前） と D_ctrl（非月末・前）、回帰の傾き（usd_prefix ～ 月のリターン）。前半 2012〜2016／後半 2017〜2026／全期間。
- 月末の 16 時台（後）の D も記述。

【帰無】
月末日の「上げ月／下げ月」のラベルを並べ替える（B=2000）→ D の帰無分布 → z。

【判定（事前固定・変更禁止）】
- 前半・後半とも D < 0 かつ z ≤ −2 → 支持（月末のフィキシング前のドルはその月の株と逆に動く）。
- 全期間の z > −2 → 棄却。
- それ以外 → 未確定。
多重比較: 判定は D の前後半 2 本。D_ctrl・後の時間帯・傾きは記述。

【捨てた案の数】
約4: 全 FX8（クロス円はドル成分が無いので除外）、15:30 までの 30 分（H1 なので不可）、ドルインデックスを連鎖で作る案
（組の平均で代用）、US500 の月次を H1 で作る案（日足で足りる）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。規則は固定で相場観は使わない。

【委託の確かめ方】
設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・D と z（前後半）・原典の箇所を返す。

【実装】自己完結・決定的（乱数は並べ替えのみ seed 固定）。依存: python3 + numpy/pandas（tz は zoneinfo/pytz）。
実行: python3 kensho_month_end_fix_dollar_q229.py            （B=2000・1 分以内）
      python3 kensho_month_end_fix_dollar_q229.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q229"
DEFAULT_B = 2000
START = "2012-01-01"
PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": +1, "USDCHF": +1, "USDCAD": +1}
PRE_HOUR, POST_HOUR = 15, 16  # ロンドン時刻


def usd_hourly(args, rng):
    """時刻ごとのドルのリターン [bp]（組の平均）。index: UTC time。"""
    cols = {}; missing = []
    for s, sgn in PAIRS.items():
        if not args.smoke and not exists_sym(s, "H1_dukascopy"):
            missing.append(s); continue
        df = load_h1(s, args.smoke, rng, n=120000, start=START)
        df = df[df["time"] >= pd.Timestamp(START)]
        cols[s] = pd.Series(sgn * df["ret"].values * 1e4, index=df["time"].values)
    usd = pd.concat(cols, axis=1).mean(axis=1, skipna=True).dropna()
    return usd, missing


def run(args, rng):
    usd, missing = usd_hourly(args, rng)
    t = pd.DatetimeIndex(usd.index).tz_localize("UTC").tz_convert("Europe/London")
    d = pd.DataFrame({"usd": usd.values, "ldate": t.tz_localize(None).normalize(), "lhour": t.hour})
    d["ym"] = d["ldate"].dt.to_period("M")
    # US500 の月のリターン（前月末の終値 → 月末日の前日の終値）
    if args.smoke:
        us = _smoke_ohlc("US500", rng, n=4000, freq="D", start="2011-09-01")
    else:
        us = _read(os.path.join(DATA_DIR, "data_US500_D1_fromH1.csv"))
    us = us[us["high"] != us["low"]].reset_index(drop=True)
    us["ym"] = us["time"].dt.to_period("M")
    pre = d[d["lhour"] == PRE_HOUR].copy(); post = d[d["lhour"] == POST_HOUR].copy()
    last_day = pre.groupby("ym")["ldate"].max()
    pre["is_me"] = pre["ldate"].values == pre["ym"].map(last_day).values
    post["is_me"] = post["ldate"].values == post["ym"].map(last_day).values
    # 月のリターン: その日までに分かる値（前日の終値まで）
    us_c = us.set_index("time")["close"]
    prev_me_close = us.groupby("ym")["close"].last().shift(1)  # 前月末の終値

    def month_ret(row):
        c = us_c[us_c.index < row["ldate"]]
        if len(c) == 0 or row["ym"] not in prev_me_close.index or not np.isfinite(prev_me_close[row["ym"]]):
            return np.nan
        return float(np.log(c.iloc[-1] / prev_me_close[row["ym"]]))

    for fr in (pre, post):
        fr["mret"] = fr.apply(month_ret, axis=1)
        fr["year"] = fr["ldate"].dt.year
    pre = pre.dropna(subset=["mret"]); post = post.dropna(subset=["mret"])

    def D_of(fr):
        up = fr[fr["mret"] > 0]["usd"]; dn = fr[fr["mret"] < 0]["usd"]
        if len(up) < 3 or len(dn) < 3:
            return float("nan"), int(len(up)), int(len(dn))
        return float(up.mean() - dn.mean()), int(len(up)), int(len(dn))

    def slope(fr):
        x = fr["mret"].values; y = fr["usd"].values
        if len(x) < 5 or x.std() == 0:
            return float("nan")
        return float(np.cov(x, y)[0, 1] / x.var(ddof=1))

    summary = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        me = pre[pre["is_me"] & (pre["year"] >= y0) & (pre["year"] < y1)]
        ct = pre[(~pre["is_me"]) & (pre["year"] >= y0) & (pre["year"] < y1)]
        mp = post[post["is_me"] & (post["year"] >= y0) & (post["year"] < y1)]
        D, nu, nd = D_of(me); Dc, _, _ = D_of(ct); Dp, _, _ = D_of(mp)
        null = []
        if np.isfinite(D):
            lab = (me["mret"].values > 0); y = me["usd"].values
            for b in range(args.B):
                l2 = rng.permutation(lab)
                null.append(y[l2].mean() - y[~l2].mean())
        z, pct = z_of(D, null) if null else (float("nan"), float("nan"))
        summary[pn] = {"n_month_end": int(len(me)), "n_up": nu, "n_down": nd, "D_bp": f(D), "D_z": f(z), "D_pct": f(pct),
                       "mean_usd_prefix_me_bp": f(me["usd"].mean()) if len(me) else None,
                       "slope_bp_per_logret": f(slope(me)), "D_ctrl_nonmonthend_bp": f(Dc), "n_ctrl": int(len(ct)),
                       "D_postfix_me_bp": f(Dp)}
    g = lambda p, k: summary.get(p, {}).get(k)
    if all((g(p, "D_bp") or 0) < 0 and (g(p, "D_z") or 0) <= -2 for p in ("pre", "post")):
        verdict = "支持: 月末のフィキシング前のドルはその月の株と逆に動く"
    elif (g("all", "D_z") if g("all", "D_z") is not None else 0) > -2:
        verdict = "棄却: 全期間の z > −2"
    else:
        verdict = "未確定"
    res = {"question": "月末のロンドン16時フィキシング前のドルの向きは、その月の US500 リターンと逆か",
           "settings": {"pairs": PAIRS, "pre_hour_london": PRE_HOUR, "post_hour_london": POST_HOUR, "start": START, "split_year": SPLIT_YEAR, "B": args.B},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は D の前後半 2 本。対照（非月末）・後の時間帯・傾きは記述。"}
    cells = pre[pre["is_me"]][["ldate", "ym", "usd", "mret"]].copy(); cells["ym"] = cells["ym"].astype(str)
    return res, {"monthend": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
