#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q222: Parkinson のレンジボラは終値ボラより翌日の実現ボラをよく予測するか（15 銘柄・QLIKE・HAR 型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Parkinson (1980) J. Business 53(1) — 高値・安値のレンジによる分散推定は終値のみの推定より効率が約 5 倍高い（式 (9)）。
  Alizadeh, Brandt, Diebold (2002) J. Finance 57(3) — レンジは市場のミクロ構造ノイズに強い。Corsi (2009) J. Financial Econometrics の HAR-RV が枠。
  関連知見: Q187（為替のボラ予測ではモデル族の差が損失関数の差より大きい）、Q195・Q196（ML 梯子の HAR-RV）。
  → 本案は「同じ HAR の形で、入力を終値の二乗リターンにするか Parkinson のレンジ分散にするか」だけを変え、翌日の実現分散（H1 の二乗和）への QLIKE を比べる。

【仮説（測る前に固定）】
H1: HAR（ラグ 1・5・22 の平均）の入力を Parkinson レンジ分散にした予測の QLIKE は、終値二乗リターンを入力にした予測より小さい（対応ありの年単位 t ≥ 2、前後半とも）。
H0: 差は 0 と区別できない。参考: 入力を実現分散（H1 の二乗和）にした HAR-RV（上限の目安）と、両方を入れた HAR。

【データ】15 銘柄 H1_dukascopy を UTC 0 時区切りの日足に束ね、実現分散 RV_t = Σ(時間足の対数リターン)²、Parkinson PK_t = (ln(H/L))² ÷ (4 ln 2)、終値 CC_t = (ln(C_t/C_{t−1}))²。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 予測対象: RV_{t+1}。モデル: OLS で RV_{t+1} = a + b1·X_t + b5·mean(X_{t−4..t}) + b22·mean(X_{t−21..t})（X = CC・PK・RV・[CC と PK の両方]）。
- 歩進: 各銘柄で年 y の予測は y より前の全データ（最低 3 年）で推定。予測が非正なら訓練期間の RV の 1 パーセンタイルで下限。
- 損失: QLIKE（銘柄×年）→ 年ごとに銘柄平均 → 対応ありの差（PK − CC）の年単位 t。群別。
- 帰無: 対応ありの t（年を単位）で判定。並べ替えは行わない（予測の比較に帰無の並べ替えは不要）。

【測るもの】4 モデルの QLIKE（前後半・群別）、PK − CC の差の t、PK − RV の差（上限との距離）、両方 − PK の差。

【判定（事前固定・変更禁止）】
all15 で前後半とも PK − CC の QLIKE の差 < 0 かつ年単位 t ≤ −2 → H1 支持（レンジは終値よりよく予測する）。
前後半のどちらかで t > −2 → 棄却。参考モデルは記述。

【捨てた案の数】約 4: Garman-Klass（始値・終値も使う。Parkinson で主張を純化）、対数 HAR（非負制約の扱いが変わる）、翌 5 日の RV、GARCH（道具なし）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t（前後半）・Parkinson 1980 の効率比を返す。

【実装】自己完結。実行: python3 kensho_parkinson_vol_q222.py（1 分前後。--B は使わない）／--smoke
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

QID = "Q222"
DEFAULT_B = 1
MIN_TRAIN_YEARS = 3


def har_feats(x):
    s = pd.Series(x)
    return np.c_[x, s.rolling(5).mean().values, s.rolling(22).mean().values]


def walk_forward(feats, target, years):
    pred = np.full(len(target), np.nan)
    for y in np.unique(years):
        tr = (years < y) & np.isfinite(target) & np.all(np.isfinite(feats), axis=1)
        if len(np.unique(years[tr])) < MIN_TRAIN_YEARS:
            continue
        X = np.c_[np.ones(tr.sum()), feats[tr]]; beta = np.linalg.lstsq(X, target[tr], rcond=None)[0]
        te = years == y; Xt = np.c_[np.ones(te.sum()), feats[te]]; p = Xt @ beta
        floor = np.nanpercentile(target[tr], 1); p = np.where(np.isfinite(p) & (p > floor), p, floor); pred[te] = p
    return pred


def run(args, rng):
    syms, missing = syms_available(SYMS, kind="H1_dukascopy", smoke=args.smoke)
    rows = []
    for s in syms:
        h1 = load_h1(s, args.smoke, rng); h1["lr2"] = np.log(h1["close"] / h1["close"].shift(1)) ** 2
        key = h1["time"].dt.floor("D"); g = h1.groupby(key)
        d = pd.DataFrame({"rv": g["lr2"].sum(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(), "n": g["close"].size()})
        d = d[(d["n"] >= 6) & (d["high"] > d["low"])]
        d["pk"] = np.log(d["high"] / d["low"]) ** 2 / (4 * math.log(2)); d["cc"] = np.log(d["close"] / d["close"].shift(1)) ** 2
        d["year"] = d.index.year; target = np.r_[d["rv"].values[1:], np.nan]; yrs = d["year"].values
        preds = {"CC": walk_forward(har_feats(d["cc"].values), target, yrs), "PK": walk_forward(har_feats(d["pk"].values), target, yrs),
                 "RV": walk_forward(har_feats(d["rv"].values), target, yrs), "BOTH": walk_forward(np.c_[har_feats(d["cc"].values), har_feats(d["pk"].values)], target, yrs)}
        for y in np.unique(yrs):
            m = yrs == y
            if np.isfinite(preds["CC"][m]).sum() < 50:
                continue
            rows.append({"sym": s, "year": int(y), **{f"q_{k}": qlike(v[m], target[m]) for k, v in preds.items()}})
        print("done", s)
    cells = pd.DataFrame(rows)
    out = {}
    for gname, members in GROUPS.items():
        cg = cells[cells["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            yr = d.drop(columns="sym").groupby("year").mean()
            r = {"n_years": int(len(yr))}
            for k in ("CC", "PK", "RV", "BOTH"):
                r[f"qlike_{k}"] = f(yr[f"q_{k}"].mean())
            for a, b in (("PK", "CC"), ("PK", "RV"), ("BOTH", "PK")):
                dd = yr[f"q_{a}"] - yr[f"q_{b}"]; r[f"diff_{a}_minus_{b}"] = f(dd.mean()); r[f"diff_{a}_minus_{b}_t"] = f(tstat(dd.values))
            out[f"{gname}_{pn}"] = r
    pre, post = out.get("all15_pre", {}), out.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if all(g(p, "diff_PK_minus_CC") < 0 and g(p, "diff_PK_minus_CC_t") <= -2 for p in (pre, post)):
        verdict = "支持: Parkinson のレンジは終値より翌日の実現ボラをよく予測する"
    elif g(pre, "diff_PK_minus_CC_t") > -2 or g(post, "diff_PK_minus_CC_t") > -2:
        verdict = "棄却: 前後半のどちらかで差の t>−2"
    else:
        verdict = "未確定"
    res = {"question": "Parkinson のレンジボラは終値ボラより翌日の実現ボラをよく予測するか", "settings": {"min_train_years": MIN_TRAIN_YEARS, "har_lags": [1, 5, 22]}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の PK−CC の t の 2 本。RV・BOTH・群別は記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
