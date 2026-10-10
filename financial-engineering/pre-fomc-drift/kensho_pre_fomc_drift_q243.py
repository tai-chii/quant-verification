#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q243: FOMC 前日ドリフトは US500 H1 で 2015 年以降も残るか（Lucca・Moench 2015／Kurov ほか 2021 の追試）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q243 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Lucca & Moench (2015) "The Pre-FOMC Announcement Drift" JF 70（発表前 24 時間の S&P500 の超過リターンが大きい・1994〜2011）。
- Kurov, Wolfe & Gilbert (2021) "The disappearing pre-FOMC announcement drift" Finance Research Letters 40（2016 年以降は消えた）。本文未読・要旨。
- 知見 Q219（NFP 直後の反応は続かない）、知見 Q056（公表後の時刻アノマリーは弱まる）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "pre-FOMC announcement drift disappeared after 2015 Lucca Moench update"）:
  Kurov ほか 2021、Applied Economics 2025 の再検討（ideas.repec v57 i17）、R-bloggers 2015 の更新。CFD の H1 で 2012〜2026 を
  前後半（2017 区切り）に分け、ランダムな日の同じ窓を帰無にする形は未確認。追試（公表後）。

【仮説（測る前に固定）】
H（Lucca・Moench）: FOMC 声明の発表（米東部 14:00）前 24 時間の US500 のリターンは、他の日の同じ窓より高い。
対立（Kurov ほか）: 2017 年以降は 0 と区別できない。

【データ】`data_US500_H1_dukascopy.csv`（2011-09〜2026-06・UTC）。FOMC の定例会合の発表日は下の表（2012〜2026・Fable の知識から・緊急会合は除く）。
**実行者は federalreserve.gov の会合日程と照合し、違いがあれば `--fomc_csv`（列: date）で差し替えてから走らせる。**

【定義（1通りに固定）】
- 米東部時刻（America/New_York）に直し、発表日の 14:00 で終わる足の終値 c_ann と、前日の 14:00 で終わる足の終値 c_prev の対数リターン [bp]。
  （H1 なので 13:00〜14:00 の足の終値 = 14:00 の値。発表はその直後なので先読みなし。）
- 対照: 全取引日（FOMC 日を除く）の同じ 24 時間窓のリターン。
- 差 = FOMC 窓の平均 − 対照の平均。

【測るもの】前半（2012〜2016）／後半（2017〜2026）／全期間: 件数・平均 [bp]・差・z。発表後 1 時間・翌日までの反応も記述。

【帰無】対照の日から FOMC と同じ件数を無作為に選ぶ B=2000 → 平均の帰無分布 → z。

【判定（事前固定・変更禁止）】
- 後半で 差 > 0 かつ z ≥ 2 → 「残っている」（Kurov ほかを棄却）。
- 後半で z < 2 → 「消えた」（対立を支持。前半で z ≥ 2 なら「再現したうえで消えた」、前半も z < 2 なら「手元のデータでは元々見えない」と書く）。
多重比較: 判定は後半の z 1 本。前半・発表後は記述。

【捨てた案の数】約4: SPX 日足（14:00 の窓が切れない）、FOMC 以外のイベント（CPI・NFP は Q219）、VIX 条件（手元にない）、週単位の累積。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。会合日程は 2026-12 まで知識から書いた（要照合）。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・後半の差と z・照合した会合日程の出典を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas（tz は zoneinfo/pytz）。
実行: python3 kensho_pre_fomc_drift_q243.py            （B=2000・30 秒）
      python3 kensho_pre_fomc_drift_q243.py --fomc_csv path/to/fomc.csv
      python3 kensho_pre_fomc_drift_q243.py --smoke
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

QID = "Q243"
DEFAULT_B = 2000
FOMC_DATES = """
2012-01-25 2012-03-13 2012-04-25 2012-06-20 2012-08-01 2012-09-13 2012-10-24 2012-12-12
2013-01-30 2013-03-20 2013-05-01 2013-06-19 2013-07-31 2013-09-18 2013-10-30 2013-12-18
2014-01-29 2014-03-19 2014-04-30 2014-06-18 2014-07-30 2014-09-17 2014-10-29 2014-12-17
2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17
"""
ANN_HOUR_NY = 14


def fomc_dates(path=None):
    if path:
        return pd.to_datetime(pd.read_csv(path)["date"]).dt.normalize().unique()
    return pd.to_datetime(FOMC_DATES.split()).normalize().unique()


def run(args, rng):
    if args.smoke:
        h1 = _smoke_ohlc("US500", rng, n=120000, freq="h", start="2012-01-01")
    else:
        h1 = _read(os.path.join(DATA_DIR, "data_US500_H1_dukascopy.csv"))
    h1 = h1[h1["close"] > 0].reset_index(drop=True)
    ny = pd.DatetimeIndex(h1["time"]).tz_localize("UTC").tz_convert("America/New_York")
    # 足の終値の時刻 = time + 1h。14:00 で終わる足 = NY 時刻 13 時台の足
    h1["ny_date"] = ny.tz_localize(None).normalize(); h1["ny_hour"] = ny.hour
    bars = h1[h1["ny_hour"] == ANN_HOUR_NY - 1].drop_duplicates("ny_date").set_index("ny_date")["close"]
    win = pd.DataFrame({"ret_bp": np.log(bars / bars.shift(1)) * 1e4, "gap_days": bars.index.to_series().diff().dt.days})
    win = win[(win["gap_days"] >= 1) & (win["gap_days"] <= 4)].dropna()  # 前日 14:00 からの窓だけ（週末またぎは最大 4 日）
    win["year"] = win.index.year
    dates = fomc_dates(getattr(args, "fomc_csv", None))
    win["fomc"] = win.index.isin(dates)
    # 発表後 1 時間（記述）: 14:00→15:00
    post_bars = h1[h1["ny_hour"] == ANN_HOUR_NY].drop_duplicates("ny_date").set_index("ny_date")["close"]
    post1 = (np.log(post_bars / bars.reindex(post_bars.index)) * 1e4).reindex(win.index)
    win["post1h_bp"] = post1
    summary = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        d = win[(win["year"] >= y0) & (win["year"] < y1)]; a = d[d["fomc"]]; b = d[~d["fomc"]]
        if len(a) < 5:
            continue
        null = [b["ret_bp"].values[rng.choice(len(b), len(a), replace=False)].mean() for _ in range(args.B)]
        z, pct = z_of(a["ret_bp"].mean(), null)
        summary[pn] = {"n_fomc": int(len(a)), "n_control": int(len(b)), "fomc_mean_bp": f(a["ret_bp"].mean()), "control_mean_bp": f(b["ret_bp"].mean()),
                       "diff_bp": f(a["ret_bp"].mean() - b["ret_bp"].mean()), "z": f(z), "pct": f(pct), "fomc_t": f(tstat(a["ret_bp"].values)),
                       "share_positive": f((a["ret_bp"] > 0).mean()), "post_1h_fomc_bp": f(a["post1h_bp"].mean()), "post_1h_control_bp": f(b["post1h_bp"].mean())}
    g = lambda p, k: (summary.get(p, {}).get(k) if summary.get(p, {}).get(k) is not None else float("nan"))
    if g("post", "diff_bp") > 0 and g("post", "z") >= 2:
        verdict = "残っている: 後半（2017〜）も FOMC 前 24 時間のドリフトが対照より高い（Kurov ほかを棄却）"
    elif g("post", "z") < 2:
        verdict = "消えた: 後半の z < 2" + ("（前半で再現したうえで消えた）" if g("pre", "z") >= 2 else "（前半も z < 2 で手元のデータでは元々見えない）")
    else:
        verdict = "未確定"
    n_matched = int(win["fomc"].sum())
    res = {"question": "FOMC 前日ドリフトは US500 H1 で 2015 年以降も残るか", "settings": {"ann_hour_ny": ANN_HOUR_NY, "B": args.B, "n_fomc_dates_listed": int(len(dates)), "n_fomc_matched_in_data": n_matched,
           "note": "FOMC の日程は Fable の知識から。実行者は federalreserve.gov と照合すること"}, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は後半の z 1 本。"}
    return res, {"windows": win.reset_index()}


def main():
    args = parse_args(default_B=DEFAULT_B, extra=lambda ap: ap.add_argument("--fomc_csv", default=None, help="列 date の CSV で会合日程を差し替える"))
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
