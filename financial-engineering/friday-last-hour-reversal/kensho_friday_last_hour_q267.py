#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q267: 金曜の最終1時間（NY 16時前）のリターンは週の向きと逆か（週末前の手仕舞い・FX8＋トレンド7 H1）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q267 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Krohn・Mueller・Whelan 2018（FX premia around the clock）、[[Dao2016-1_為替は週末の窓が大きいとその週のうちに逆向きに戻る]]、知見 Q051・Q248
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "Friday last hour before weekend reversal position squaring FX futures intraday return opposite to weekly return empirical"）:
  見つかったもの: Krohn・Mueller・Whelan 2018、Dao ほか 2016（週末の過剰反応）、Bank of Canada SWP 2021-48。
  未確認: 週の向きで条件づけた金曜最終 1 時間を 15 銘柄・前後半・符号付け替え帰無で測る形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 金曜 NY 時刻 15 時台（15:00→16:00・週の最終 1 時間）のリターン r_F は、その週（月曜 0 時 UTC〜金曜 15 時 NY）のリターン r_W と逆符号: E[sign(r_W)·r_F]<0。

【データ】
FX8＋トレンド7 の H1_dukascopy（2008/2011〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
NY 時刻は America/New_York（夏時間込み）。r_F は金曜の NY 15 時台の足。r_W はその週の月曜最初の足の始値から金曜 15 時 NY の足の始値まで。y=sign(r_W)·r_F [bp]。対照: 金曜以外の 15 時台で同じ y。

【測るもの】
年×銘柄の y の年単位 t（all15/fx8/trend7）、対照との差。前後半。

【帰無】
sign(r_W) を週で無作為に付け替え B=2000 → y の平均の帰無分布 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも y<0 かつ t≤−2 かつ z≤−2 → 支持。全期間 z>−1 → 棄却。それ以外 → 未確定。
多重比較: 判定は all15 の前後半 2 本。群別・対照は記述。

【捨てた案の数】
約3: 最終 2 時間、ロンドン 16 時台（Krohn の fix と混ざる）、翌週月曜の続き（Q248 と混ざる）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_friday_last_hour_q267.py            （B=2000・小（B=2000・1 分前後））
      python3 kensho_friday_last_hour_q267.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q267"
DEFAULT_B = 2000
NY_HOUR = 15
KIND = "H1_dukascopy"


def week_table(df):
    """週（UTC 月曜 0 時区切り）ごとの 最初の足の始値と、NY 15 時台の足（曜日別）。"""
    t_utc = pd.DatetimeIndex(df["time"])
    ny = t_utc.tz_localize("UTC").tz_convert("America/New_York")
    wk = (t_utc - pd.to_timedelta(t_utc.dayofweek, unit="D")).normalize()
    d = pd.DataFrame({"wk": wk, "open": df["open"].values, "close": df["close"].values, "ny_hour": ny.hour, "ny_dow": ny.dayofweek,
                      "year": t_utc.year})
    first_open = d.groupby("wk")["open"].first()
    bars = d[d["ny_hour"] == NY_HOUR].copy()
    bars["w_open"] = bars["wk"].map(first_open).values
    bars["r_W"] = bars["open"] / bars["w_open"] - 1               # 週の最初の足の始値 → その足の始値
    bars["r_F"] = (bars["close"] / bars["open"] - 1) * 1e4         # その足のリターン [bp]
    bars = bars[np.isfinite(bars["r_W"]) & (bars["r_W"] != 0)]
    bars["y"] = np.sign(bars["r_W"]) * bars["r_F"]
    return bars


def run(args, rng):
    syms, missing = syms_available(SYMS, KIND, args.smoke)
    fri_parts = []; ctl_parts = []; per = {}
    for s in syms:
        df = load_h1(s, args.smoke, rng, n=120000, start="2008-01-01")
        bars = week_table(df)
        fri = bars[bars["ny_dow"] == 4].copy(); ctl = bars[bars["ny_dow"] != 4].copy()
        fri["sym"] = s; ctl["sym"] = s
        fri_parts.append(fri); ctl_parts.append(ctl)
        per[s] = {"s": np.sign(fri["r_W"].values), "rF": fri["r_F"].values, "year": fri["year"].values}
    if not fri_parts:
        return {"question": "金曜 NY 15 時台のリターンは週のリターンと逆か", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない", "settings": {}, "multiple_comparisons": ""}, None
    F = pd.concat(fri_parts); C = pd.concat(ctl_parts)
    periods = {"all": (0, 9999), "pre": (0, SPLIT_YEAR), "post": (SPLIT_YEAR, 9999)}

    # 帰無: sign(r_W) を週で無作為に付け替え（銘柄ごと）→ all15 の y の年単位平均
    # 行列化: 年×銘柄の平均を bincount で
    keys = []; ylab = []
    for s, d in per.items():
        keys.append(d); ylab.append(d["year"])
    all_years = np.unique(np.concatenate(ylab))
    ymap = {y: i for i, y in enumerate(all_years)}
    null = {p: [] for p in periods}
    pre_i = np.array([ymap[y] for y in all_years if y < SPLIT_YEAR]); post_i = np.array([ymap[y] for y in all_years if y >= SPLIT_YEAR])
    for b in range(args.B):
        acc = np.zeros(len(all_years)); cnt = np.zeros(len(all_years))
        for d in keys:
            yv = rng.permutation(d["s"]) * d["rF"]
            yi = np.array([ymap[y] for y in d["year"]]) if "yi" not in d else d["yi"]
            d["yi"] = yi
            sm = np.bincount(yi, weights=yv, minlength=len(all_years)); n = np.bincount(yi, minlength=len(all_years))
            m = n > 0
            acc[m] += sm[m] / n[m]; cnt[m] += 1          # 銘柄を年の中で平均するための積算
        ymean = np.where(cnt > 0, acc / np.where(cnt > 0, cnt, 1), np.nan)
        null["all"].append(np.nanmean(ymean)); null["pre"].append(np.nanmean(ymean[pre_i]) if len(pre_i) else np.nan)
        null["post"].append(np.nanmean(ymean[post_i]) if len(post_i) else np.nan)

    summary = {}
    for g, gs in GROUPS.items():
        summary[g] = {}
        fs = F[F["sym"].isin(gs)]; cs = C[C["sym"].isin(gs)]
        for p, (y0, y1) in periods.items():
            st = by_year_stats(fs, "y", y0=y0, y1=y1); ct = by_year_stats(cs, "y", y0=y0, y1=y1)
            z, pct = z_of(st["mean"], null[p]) if g == "all15" else (float("nan"), float("nan"))
            summary[g][p] = {"n_years": st["n_years"], "n_weeks": int(len(fs[(fs["year"] >= y0) & (fs["year"] < y1)])),
                             "y_bp": f(st["mean"]), "t": f(st["t"]), "z": f(z), "pct": f(pct),
                             "ctrl_y_bp": f(ct["mean"]), "ctrl_t": f(ct["t"]),
                             "diff_vs_ctrl_bp": f(st["mean"] - ct["mean"]) if np.isfinite(st["mean"]) and np.isfinite(ct["mean"]) else None,
                             "mean_rF_bp": f(fs[(fs["year"] >= y0) & (fs["year"] < y1)]["r_F"].mean())}
    a = summary["all15"]
    vals = [a[p][k] for p in ("pre", "post") for k in ("y_bp", "t", "z")] + [a["all"]["z"]]
    if any(v is None for v in vals):
        verdict = "未確定: 計算できない"
    elif all(a[p]["y_bp"] < 0 and a[p]["t"] <= -2 and a[p]["z"] <= -2 for p in ("pre", "post")):
        verdict = "支持: all15 前後半とも y<0 かつ t≤−2 かつ z≤−2"
    elif a["all"]["z"] > -1:
        verdict = "棄却: 全期間 z>−1"
    else:
        verdict = "未確定"
    cells = F.groupby(["sym", "year"])["y"].agg(["mean", "size"]).reset_index().rename(columns={"mean": "y_bp", "size": "n_weeks"})
    res = {"question": "金曜 NY 15 時台（週の最終 1 時間）のリターンは、その週のリターンと逆符号か",
           "settings": {"syms": SYMS, "kind": KIND, "ny_hour": NY_HOUR, "tz": "America/New_York", "week": "UTC 月曜 0 時区切り",
                        "r_W": "週の最初の足の始値 → 金曜 NY 15 時台の足の始値", "r_F": "その足の close/open−1 [bp]", "y": "sign(r_W)·r_F",
                        "control": "金曜以外の NY 15 時台で同じ y", "split_year": SPLIT_YEAR, "B": args.B,
                        "null": "sign(r_W) を週で無作為に付け替え（銘柄ごと）→ all15 の年単位平均"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の前後半 2 本。群別・対照は記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
