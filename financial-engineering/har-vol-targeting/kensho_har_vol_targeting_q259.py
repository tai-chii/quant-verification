#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q259: HAR 予測の分散でのボラ・ターゲティングは σ60 版よりシャープが高いか（Q222×Q205 の連鎖）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q259 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Corsi 2009（HAR）、Harvey ほか 2018（ボラ・ターゲティング）、知見 Q205（σ60 でシャープ +0.09）・Q222（Parkinson HAR）・Q232
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "volatility targeting using HAR-RV forecast versus trailing realized volatility Sharpe improvement"）:
  見つかったもの: Alpha Architect「Volatility targeting improves risk-adjusted returns」、Macrosynergy「The point of volatility targeting」、arXiv 2604.02743（オプション情報の RV 予測）。
  未確認: HAR 予測を規模に使ったときの差を 15 銘柄・前後半・循環シフト帰無で測る形は未確認（連鎖）。

【仮説（測る前に固定）】
H: 規模 = 目標σ／予測σ の予測σに、HAR（1・5・22 日の対数 Parkinson 分散・拡大窓で年ごとに再推定）の 1 日先予測を使うと、σ60（終値の 60 日標準偏差）より年×銘柄のシャープが高い。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
A: σ60 版（Q205 と同じ）。B: HAR 版（係数は前年までの拡大窓 OLS・最短 500 日・予測は exp(log 予測)）。目標σ=年率 10%。順張りは TSMOM60。pnl_bp を規模倍。

【測るもの】
年×銘柄のシャープ差 B−A（対応あり・年単位 t）、純損益差、規模の変動係数。前後半・群別。

【帰無】
HAR 予測を年内で循環シフト（予測の分布を保ち時点との対応を壊す）B=300 → シャープ差の帰無分布 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも シャープ差>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定。それ以外 → 棄却（差は見えない）。
多重比較: 判定は all15 のシャープ差の前後半 2 本。純損益・群別は記述。

【捨てた案の数】
約3: 5 日先予測で規模を週次更新、GARCH 版（HAR に統一）、目標σを年ごとに合わせ込む（Q030 と混ざる）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_har_vol_targeting_q259.py            （B=300・小（B=300・1〜2 分））
      python3 kensho_har_vol_targeting_q259.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q259"
DEFAULT_B = 300
L_TSMOM = 60
SIG_WIN = 60
TARGET_ANN = 0.10
MIN_TRAIN = 500
LAGS = (1, 5, 22)


def har_forecast(logpv, years):
    """HAR（1・5・22 日の対数 Parkinson 分散）。係数は前年までの拡大窓 OLS（最短 500 日）・年ごとに再推定。
    返り値 pred[t] = t までの情報で作った t+1 の log 分散の予測（学習データが無い年は nan）。"""
    y = np.asarray(logpv, float); n = len(y)
    s = pd.Series(y)
    x1 = s.values
    x5 = s.rolling(LAGS[1]).mean().values
    x22 = s.rolling(LAGS[2]).mean().values
    X = np.c_[np.ones(n), x1, x5, x22]            # 特徴は t まで（t+1 を予測）
    target = np.r_[y[1:], np.nan]                 # y[t+1]
    ok = np.isfinite(X).all(axis=1) & np.isfinite(target)
    pred = np.full(n, np.nan)
    coefs = {}
    for yr in np.unique(years):
        train = ok & (years < yr)
        if train.sum() < MIN_TRAIN:
            continue
        beta, *_ = np.linalg.lstsq(X[train], target[train], rcond=None)
        coefs[int(yr)] = beta
        m = (years == yr) & np.isfinite(X).all(axis=1)
        pred[m] = X[m] @ beta
    return pred, coefs


def yearly_sharpe(pnl, years):
    """年ごとの年率シャープ（Series: year → sharpe）。"""
    return pd.Series(pnl).groupby(years).apply(lambda v: sharpe_ann(v.values))


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    per = {}       # sym → 前計算
    rows = []      # year × sym の行
    coef_rows = []
    for s in syms:
        if args.smoke:  # 2008 開始が要る（HAR の最短学習 500 日 → 前半が空にならないように）
            df = _smoke_ohlc(s, rng, n=5000, freq="D", start="2008-01-01")
            df = df[df["high"] != df["low"]].reset_index(drop=True); df["year"] = df["time"].dt.year
        else:
            df = load_d1(s, args.smoke, rng)
        c = df["close"].values; h = df["high"].values; l = df["low"].values
        yrs = df["year"].values
        n = len(c)
        if n < MIN_TRAIN + 300:
            missing.append(s); continue
        cost = cost_bp_oneway(s, c)
        pos = tsmom_pos(c, L_TSMOM)
        # A: σ60（終値リターンの 60 日標準偏差・年率）
        ret = pd.Series(c).pct_change()
        sigA = ret.rolling(SIG_WIN).std(ddof=1).values * math.sqrt(252)
        # B: HAR（対数 Parkinson 分散）
        pv = (np.log(h / l) ** 2) / (4 * math.log(2))
        pv = np.where(pv > 0, pv, np.nan)
        logpv = np.log(pv)
        pred, coefs = har_forecast(logpv, yrs)
        sigB = np.sqrt(np.exp(pred)) * math.sqrt(252)
        for yr, b in coefs.items():
            coef_rows.append({"sym": s, "year": yr, "const": b[0], "b1": b[1], "b5": b[2], "b22": b[3]})
        valid = np.isfinite(sigA) & np.isfinite(sigB) & (sigA > 0) & (sigB > 0)
        scaleA = np.where(valid, TARGET_ANN / np.where(sigA > 0, sigA, np.nan), 0.0)
        scaleB = np.where(valid, TARGET_ANN / np.where(sigB > 0, sigB, np.nan), 0.0)
        scaleA = np.nan_to_num(scaleA); scaleB = np.nan_to_num(scaleB)
        pnlA = pnl_bp(pos * scaleA, c, cost)
        pnlB = pnl_bp(pos * scaleB, c, cost)
        use = valid  # 両方の規模が定義できる日だけ比べる
        shA = yearly_sharpe(np.where(use, pnlA, np.nan), yrs)
        shB = yearly_sharpe(np.where(use, pnlB, np.nan), yrs)
        pA = pd.Series(np.where(use, pnlA, np.nan)).groupby(yrs).mean()
        pB = pd.Series(np.where(use, pnlB, np.nan)).groupby(yrs).mean()
        cvA = pd.Series(np.where(use, scaleA, np.nan)).groupby(yrs).apply(lambda v: v.std() / v.mean() if v.mean() > 0 else np.nan)
        cvB = pd.Series(np.where(use, scaleB, np.nan)).groupby(yrs).apply(lambda v: v.std() / v.mean() if v.mean() > 0 else np.nan)
        nuse = pd.Series(use.astype(float)).groupby(yrs).sum()
        for yr in shA.index:
            if nuse[yr] < 60:
                continue
            rows.append({"sym": s, "year": int(yr), "sharpe_A": shA[yr], "sharpe_B": shB[yr], "d_sharpe": shB[yr] - shA[yr],
                         "pnl_A": pA[yr], "pnl_B": pB[yr], "d_pnl": pB[yr] - pA[yr], "cv_A": cvA[yr], "cv_B": cvB[yr], "n_days": int(nuse[yr])})
        per[s] = {"c": c, "cost": cost, "pos": pos, "yrs": yrs, "use": use, "sigB": sigB, "shA": shA, "nuse": nuse}
    cells = pd.DataFrame(rows)
    if cells.empty:
        return {"question": "HAR 予測でのボラ・ターゲティングは σ60 版よりシャープが高いか", "missing": missing,
                "summary": {}, "machine_verdict": "未確定: 計算できない", "settings": {}, "multiple_comparisons": ""}, None

    periods = {"all": (0, 9999), "pre": (0, SPLIT_YEAR), "post": (SPLIT_YEAR, 9999)}

    def year_mean_diff(df, col, y0, y1):
        return by_year_stats(df, col, y0=y0, y1=y1)

    # 帰無: HAR 予測を年内で循環シフト（銘柄ごと・年ごと）→ シャープ差の年単位平均（all15）
    null = {p: [] for p in periods}
    for b in range(args.B):
        nrows = []
        for s, d in per.items():
            sig = d["sigB"].copy(); yrs = d["yrs"]
            for yr in np.unique(yrs):
                idx = np.where(yrs == yr)[0]
                if len(idx) > 2:
                    sig[idx] = circ_shift(rng, sig[idx])
            valid = d["use"] & np.isfinite(sig) & (sig > 0)
            sc = np.nan_to_num(np.where(valid, TARGET_ANN / np.where(sig > 0, sig, np.nan), 0.0))
            pnlB = pnl_bp(d["pos"] * sc, d["c"], d["cost"])
            shB = yearly_sharpe(np.where(d["use"], pnlB, np.nan), yrs)
            for yr in shB.index:
                if d["nuse"][yr] >= 60:
                    nrows.append({"sym": s, "year": int(yr), "d": shB[yr] - d["shA"][yr]})
        nd = pd.DataFrame(nrows)
        for p, (y0, y1) in periods.items():
            null[p].append(by_year_stats(nd, "d", y0=y0, y1=y1)["mean"])

    summary = {}
    for g, gs in GROUPS.items():
        sub = cells[cells["sym"].isin(gs)]
        summary[g] = {}
        for p, (y0, y1) in periods.items():
            st = year_mean_diff(sub, "d_sharpe", y0, y1)
            pn = year_mean_diff(sub, "d_pnl", y0, y1)
            sa = year_mean_diff(sub, "sharpe_A", y0, y1); sb = year_mean_diff(sub, "sharpe_B", y0, y1)
            ca = year_mean_diff(sub, "cv_A", y0, y1); cb = year_mean_diff(sub, "cv_B", y0, y1)
            z, pct = z_of(st["mean"], null[p]) if g == "all15" else (float("nan"), float("nan"))
            summary[g][p] = {"n_years": st["n_years"], "n_cells": int(len(sub[(sub["year"] >= y0) & (sub["year"] < y1)])),
                             "d_sharpe": f(st["mean"]), "d_sharpe_t": f(st["t"]), "d_sharpe_z": f(z), "d_sharpe_pct": f(pct),
                             "sharpe_A": f(sa["mean"]), "sharpe_B": f(sb["mean"]),
                             "d_pnl_bp": f(pn["mean"]), "d_pnl_t": f(pn["t"]),
                             "cv_scale_A": f(ca["mean"]), "cv_scale_B": f(cb["mean"])}
    a = summary["all15"]
    vals = [a[p][k] for p in ("pre", "post") for k in ("d_sharpe", "d_sharpe_t", "d_sharpe_z")]
    if any(v is None for v in vals):
        verdict = "未確定: 計算できない"
    elif all(a[p]["d_sharpe"] > 0 and a[p]["d_sharpe_t"] >= 2 and a[p]["d_sharpe_z"] >= 2 for p in ("pre", "post")):
        verdict = "支持: all15 前後半とも シャープ差>0 かつ t≥2 かつ z≥2"
    elif all(a[p]["d_sharpe_t"] <= -2 for p in ("pre", "post")):
        verdict = "逆向きで確定: 前後半とも t≤−2（HAR 版の方がシャープが低い）"
    else:
        verdict = "棄却: 差は見えない"
    res = {"question": "HAR 予測の分散でのボラ・ターゲティングは σ60 版よりシャープが高いか",
           "settings": {"L_tsmom": L_TSMOM, "sigma_window": SIG_WIN, "target_ann": TARGET_ANN, "har_lags": LAGS, "min_train_days": MIN_TRAIN,
                        "har_target": "log Parkinson variance = log((ln(H/L))^2/(4 ln 2))", "split_year": SPLIT_YEAR, "B": args.B,
                        "null": "HAR 予測を年内で循環シフト（銘柄×年）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 のシャープ差の前後半 2 本。純損益・群別・規模の変動係数は記述。"}
    return res, {"cells": cells, "har_coefs": pd.DataFrame(coef_rows)}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
