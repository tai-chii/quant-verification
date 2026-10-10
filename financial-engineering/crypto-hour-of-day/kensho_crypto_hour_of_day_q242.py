#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q242: 暗号資産 11 通貨の UTC 時刻効果は、Holm 補正後に前後半で同符号で残るか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q242 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q212（暗号資産の週末はボラが低く、順張りの損益は変わらない）、知見 Q153（為替 M15 の時刻別自己相関は Holm 後に残らない）、
  知見 Q056（フィキシングの V 字は 2020 年以降弱い）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "cryptocurrency intraday hour-of-day seasonality returns bitcoin time-of-day effect"）:
  UWA の "Bitcoin Time-of-Day, Day-of-Week and Month-of-Year Effects"、Quantpedia「Intraday Seasonality in Bitcoin」、arXiv 2009.04200
  （HFT の日中パターン）。11 通貨を束ね、日内の並べ替え帰無と Holm で前後半の再現を見る形は未確認。追試＋条件の穴（アルト・2022 年以降）。

【仮説（測る前に固定）】
H: UTC の時刻ごとの平均リターンに、11 通貨を束ねて Holm 補正後も有意で、前半（<2022）と後半（≥2022）で同符号の時刻がある。

【データ】暗号資産 11 通貨の H1（Dukascopy・UTC、2017〜2026-09）。

【定義（1通りに固定）】
- 各通貨・各時刻 h（0〜23）の平均リターン [bp]。束ね = 通貨の等加重平均（通貨ごとに標準化はしない）。
- p 値: 日内で時刻ラベルを並べ替えた帰無（各日の 24 本をシャッフル。日の効果は保つ）B=1000 → 両側 p → Holm（24 本）。
- 期間ごとに別々に計算。

【測るもの】前半（<2022）／後半（≥2022）／全期間: 時刻別の平均・z・Holm p。両期間で Holm p<0.05 かつ同符号の時刻の数。
副次（記述）: 時刻別の実現ボラ（|r| の平均）。

【判定（事前固定・変更禁止）】
- 前半・後半とも Holm p < 0.05 で、符号が同じ時刻が 1 つ以上 → 支持（時刻効果が残る）。
- 0 → 棄却。
多重比較: 24 時刻 × 2 期間を Holm で補正。

【捨てた案の数】約4: 曜日×時刻の 168 セル（検出力が落ちる）、BTC だけ、取引所の時刻（Dukascopy は UTC で統一）、ボラで標準化した平均。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-09 まで（締め切り後 3 か月を含む）。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・残った時刻とその p を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_crypto_hour_of_day_q242.py            （B=1000・2 分前後）
      python3 kensho_crypto_hour_of_day_q242.py --smoke
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

QID = "Q242"
DEFAULT_B = 1000
SPLIT_CRYPTO = 2022


def to_matrices(d):
    """期間の DataFrame → {sym: 行=日, 列=時刻(24) の行列（欠けは NaN）}。"""
    mats = {}
    for s, g in d.groupby("sym"):
        m = g.pivot_table(index="day", columns="hour", values="ret", aggfunc="mean").reindex(columns=range(24))
        mats[s] = m.values.astype(float)
    return mats


def hour_means(mats):
    """時刻別の通貨平均（24）。通貨ごとに日の平均 → 通貨の等加重平均。"""
    per = np.array([np.nanmean(m, axis=0) for m in mats.values()])
    return np.nanmean(per, axis=0)


def permute_within_day(rng, mats):
    """各行（日）の中で 24 本をシャッフル（日の効果は保つ・ラベルの交換可能性）。"""
    out = {}
    for s, m in mats.items():
        keys = rng.random(m.shape); order = np.argsort(keys, axis=1)
        out[s] = np.take_along_axis(m, order, axis=1)
    return out


def run(args, rng):
    rows = []; missing = []
    for s in CRYPTO:
        if not args.smoke and not exists_sym(s, "H1_dukascopy"):
            missing.append(s); continue
        d = load_h1(s, args.smoke, rng, n=60000, start="2018-01-01").dropna(subset=["ret"])
        rows.append(pd.DataFrame({"sym": s, "time": d["time"].values, "year": d["year"].values, "hour": d["hour"].values, "ret": d["ret"].values * 1e4, "absr": np.abs(d["ret"].values) * 1e4}))
    df = pd.concat(rows, ignore_index=True); df["day"] = pd.DatetimeIndex(df["time"]).floor("D")
    summary = {}; sig_hours = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_CRYPTO)), ("post", (SPLIT_CRYPTO, 9999))):
        d = df[(df["year"] >= y0) & (df["year"] < y1)].copy()
        if d.empty:
            continue
        mats = to_matrices(d); obs = hour_means(mats); null = np.zeros((args.B, 24))
        for b in range(args.B):
            null[b] = hour_means(permute_within_day(rng, mats))
            if b % 200 == 0:
                print(pn, "null", b)
        z = (obs - null.mean(axis=0)) / null.std(axis=0, ddof=1)
        p_two = np.array([min(1.0, 2 * min((null[:, h] >= obs[h]).mean(), (null[:, h] <= obs[h]).mean()) + 1.0 / args.B) for h in range(24)])
        adj = holm(p_two)
        vol = d.groupby("hour")["absr"].mean().reindex(range(24)).values
        summary[pn] = {"n_hours": int(len(d)), "hour_mean_bp": [f(x) for x in obs], "z": [f(x) for x in z], "p_holm": [f(x) for x in adj],
                       "abs_ret_by_hour_bp": [f(x) for x in vol], "sig_hours": [int(h) for h in range(24) if adj[h] < 0.05]}
        sig_hours[pn] = {int(h): float(np.sign(obs[h])) for h in range(24) if adj[h] < 0.05}
    common = [h for h in sig_hours.get("pre", {}) if h in sig_hours.get("post", {}) and sig_hours["pre"][h] == sig_hours["post"][h]]
    verdict = f"支持: 前後半とも Holm p<0.05 で同符号の時刻 {common}" if common else "棄却: 前後半で同符号に残る時刻は 0"
    res = {"question": "暗号資産 11 通貨の UTC 時刻効果は Holm 後に前後半で同符号で残るか", "settings": {"split_year": SPLIT_CRYPTO, "B": args.B}, "missing": missing,
           "summary": summary, "common_sig_hours": common, "machine_verdict": verdict, "multiple_comparisons": "24 時刻 × 2 期間を Holm で補正。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
