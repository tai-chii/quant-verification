#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q257: 順張り束の月次損益は US500 月次リターンの 2 次関数（スマイル）か（Fung・Hsieh 2001／Moskowitz 2012 の型）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q257 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Fung・Hsieh 2001（RFS・トレンドフォロワーの lookback straddle）、Moskowitz・Ooi・Pedersen 2012 図（TSMOM smile）、知見 Q207・Q224（危機アルファは再現しない）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "time series momentum smile quadratic equity market return option-like payoff Moskowitz Fung Hsieh lookback straddle"）:
  見つかったもの: arXiv 2607.19497「The Science and Practice of Trend-Following Systems」、Columbia（djk 2019）、UCD WP19-06。
  未確認: 原典は先物の長期。手元 CFD 15 銘柄・2011–2026・月ブロック帰無で c の有意性を事前固定で測る形は未確認（追試＋条件の穴）。

【仮説（測る前に固定）】
H: 15 銘柄等加重の TSMOM60 束の月次純損益 y を US500 の月次リターン x に y=a+bx+cx² で回帰すると c>0（スマイル）。

【データ】
15銘柄 D1_fromH1 → 月次。US500 D1_fromH1 → 月次リターン（2011-09〜）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
束の月次純損益: 各銘柄 pnl_bp を σ60 で規模調整（Q205 型）し等加重した日次の月内和。x: ln(US500 月末/前月末)。OLS（Newey-West 3 か月）。

【測るもの】
c の NW t、c の符号、|x|>5% の月の平均 y と |x|≤5% の月の平均 y の差。前半 2011–2016／後半 2017–／全期間。

【帰無】
月次 y を月ブロックで並べ替え（x との対応を壊す）B=2000 → c の帰無分布 → z。

【判定（事前固定・変更禁止）】
全期間 c>0 かつ NW t≥2 かつ z≥2、かつ前後半とも c>0 → 支持（スマイル）。全期間 z<1 → 棄却。それ以外 → 未確定。
多重比較: 判定は全期間 c の 1 本（前後半の符号は条件）。裾の月の差は記述。

【捨てた案の数】
約3: 参照日数 1/3/12 か月の合成（Q224 で済み）、週次の回帰（点が少ない）、US500 以外の x（ドル・金）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_tsmom_smile_q257.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_tsmom_smile_q257.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q257"
DEFAULT_B = 2000
L = 60
START = "2011-09-01"
VOL_TARGET = 0.10   # σ60 規模調整の目標（年率）。pnl を (目標/年率σ60) 倍
NW_LAG = 3
TAIL = 0.05
PERIODS = (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _load_long(sym, args, rng):
    """D1。smoke は 2011 年始まりの長い合成データ（前後半を通す）。"""
    if not args.smoke:
        return load_d1(sym, False, rng)
    df = _smoke_ohlc(sym, rng, n=4000, freq="D", start="2011-01-01")
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    return df


def _ols_nw(X, y, lag):
    """OLS と Newey-West（Bartlett）の係数 t。戻り: beta, t。"""
    X = np.asarray(X, float); y = np.asarray(y, float); n, k = X.shape
    if n <= k + 2:
        return np.full(k, np.nan), np.full(k, np.nan)
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for j in range(1, min(lag, n - 1) + 1):
        G = Xu[j:].T @ Xu[:-j]
        S += (1 - j / (lag + 1)) * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0))
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    return beta, t


def _c_only(X, y):
    beta = np.linalg.pinv(X.T @ X) @ X.T @ y
    return float(beta[2])


def run(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    daily = {}
    for s in ok:
        df = _load_long(s, args, rng)
        c = df["close"].values.astype(float)
        pos = tsmom_pos(c, L); pnl = pnl_bp(pos, c, cost_bp_oneway(s, c))
        lr = np.r_[np.nan, np.diff(np.log(c))]
        sig = pd.Series(lr).rolling(L).std(ddof=1).values * math.sqrt(252)
        w = np.r_[np.nan, (VOL_TARGET / sig)[:-1]]      # 前日までの σ60 で決める
        daily[s] = pd.Series(w * pnl, index=df["time"].values)
    bund = pd.concat(daily, axis=1)
    bund = bund[bund.index >= pd.Timestamp(START)]
    y_d = bund.mean(axis=1, skipna=True).dropna()
    ym = pd.PeriodIndex(y_d.index, freq="M")
    y_m = y_d.groupby(ym).sum()
    n_days = y_d.groupby(ym).size()
    # US500 月次リターン
    if not args.smoke and not exists_sym("US500"):
        raise SystemExit("US500 が無い")
    us = _load_long("US500", args, rng)
    us = us[us["time"] >= pd.Timestamp(START) - pd.offsets.MonthBegin(1)]
    me = us.groupby(pd.PeriodIndex(us["time"], freq="M"))["close"].last()
    x_m = np.log(me / me.shift(1)).dropna()
    m = pd.DataFrame({"y": y_m, "x": x_m, "n_days": n_days}).dropna()
    m = m[m["n_days"] >= 10]
    m["year"] = m.index.year
    X_all = np.c_[np.ones(len(m)), m["x"].values, m["x"].values ** 2]

    def fit(sub):
        if len(sub) < 8:
            return {"n_months": int(len(sub)), "a": None, "b": None, "c": None, "c_nw_t": None}
        X = np.c_[np.ones(len(sub)), sub["x"].values, sub["x"].values ** 2]
        beta, t = _ols_nw(X, sub["y"].values, NW_LAG)
        return {"n_months": int(len(sub)), "a": f(beta[0]), "b": f(beta[1]), "c": f(beta[2]), "c_nw_t": f(t[2])}

    summary = {}
    for pn, y0, y1 in PERIODS:
        sub = m[(m["year"] >= y0) & (m["year"] < y1)]
        ent = fit(sub)
        tail = sub[np.abs(sub["x"]) > TAIL]["y"]; mid = sub[np.abs(sub["x"]) <= TAIL]["y"]
        ent.update({"mean_y_tail_bp": f(tail.mean()) if len(tail) else None, "n_tail": int(len(tail)),
                    "mean_y_mid_bp": f(mid.mean()) if len(mid) else None, "n_mid": int(len(mid)),
                    "tail_minus_mid_bp": f(tail.mean() - mid.mean()) if len(tail) and len(mid) else None,
                    "corr_y_x": f(np.corrcoef(sub["x"], sub["y"])[0, 1]) if len(sub) > 3 else None})
        if pn == "all" and len(sub) >= 8:
            X = np.c_[np.ones(len(sub)), sub["x"].values, sub["x"].values ** 2]; yv = sub["y"].values
            c_obs = _c_only(X, yv)
            null = [_c_only(X, rng.permutation(yv)) for b in range(args.B)]
            z, pct = z_of(c_obs, null); ent.update({"c_z": f(z), "c_pct": f(pct)})
        summary[pn] = ent
    a = summary["all"]
    if a.get("c") is None or a.get("c_nw_t") is None or a.get("c_z") is None or summary["pre"]["c"] is None or summary["post"]["c"] is None:
        verdict = "未確定: 計算できない"
    elif a["c"] > 0 and a["c_nw_t"] >= 2 and a["c_z"] >= 2 and summary["pre"]["c"] > 0 and summary["post"]["c"] > 0:
        verdict = "支持: スマイル（全期間 c>0・NW t≥2・z≥2、前後半とも c>0）"
    elif a["c_z"] < 1:
        verdict = "棄却: 全期間 z<1"
    else:
        verdict = "未確定"
    res = {"question": "順張り束（σ60 規模調整・等加重）の月次純損益は US500 月次リターンの 2 次関数（c>0 のスマイル）か",
           "settings": {"L": L, "start": START, "vol_target": VOL_TARGET, "nw_lag_months": NW_LAG, "tail_abs_x": TAIL, "split_year": SPLIT_YEAR, "B": args.B,
                        "y": "各銘柄 pnl_bp×(目標/年率σ60) の等加重（その日ある銘柄の平均）を月内で和 [bp]", "x": "ln(US500 月末終値/前月末終値)",
                        "null": "月次 y を並べ替え（x との対応を壊す）→ c の帰無分布", "month_filter": "日数 10 未満の月は除く"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は全期間 c の 1 本（前後半の符号は条件）。裾の月の差は記述。"}
    out = m.reset_index().rename(columns={"index": "month"}); out["month"] = out["month"].astype(str)
    return res, {"monthly": out}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
