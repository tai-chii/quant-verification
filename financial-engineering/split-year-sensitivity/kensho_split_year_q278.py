#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q278: 前後半の分割年を 2014〜2020 で動かすと「前後半とも同符号 t≥2」の判定は何割割れるか（基盤・簡単な規則群）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q278 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Hansen・Timmermann 2012（EUI・分割点の選択）、Rossi・Inoue 2012、知見 Q146（B の安定）・Q175（クラスタ t）・Q154（WRC/SPA の割れ）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "sample split point sensitivity in-sample out-of-sample split date choice anomaly robustness backtest multiple splits"）:
  見つかったもの: Hansen・Timmermann「Choice of Sample Split in Out-of-Sample Forecast Evaluation」（EUI 2012）、Rossi・Inoue、Coventry／Tilburg「Out-of-sample equity premium predictability and sample split–invariant inference」。
  未確認: 予測評価の分割点理論は確立。自前の『前後半とも t≥2』判定を 7 分割で割れ率として帰無と比べる形は未確認（基盤）。

【仮説（測る前に固定）】
H: 15 銘柄 × 規則 5 本（TSMOM20・60・120・SMA200・RSI14 逆張り）= 75 セルで、「前後半とも同符号かつ両方 t≥2」の判定が分割年 2014〜2020 の 7 通りのうち一致しない（判定が割れる）セルの割合は、年内並べ替えの帰無で出る割合と同程度（基盤の決まりの妥当性）。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
セルごとに純損益の年×銘柄 t を分割年ごとに計算。判定: 支持（両方 t≥2 同符号）／棄却／他。割れ = 7 通りの判定が全部同じでない。

【測るもの】
割れる割合 F（観測）、帰無の F 分布、支持になる分割年の数の分布。

【帰無】
リターンを年内で並べ替え B=300 → 同じ手順で F → 帰無分布 → z。

【判定（事前固定・変更禁止）】
観測 F が帰無の 95 点以下 → 支持（分割依存は偽陽性の水準を超えない）。95 点超 → 棄却（分割年に依存する。どの規則かを書く）。帰無の F が 0 近くで比較不能 → 未確定。
多重比較: 判定は F の 1 本。75 セルは判定の材料で個別には検定しない。

【捨てた案の数】
約3: 分割を 3 期に増やす、t の閾値 1.5（2 に固定）、WRC を各分割で（重い）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_split_year_q278.py            （B=300・中（B=300×75 セル×7 分割・2〜3 分））
      python3 kensho_split_year_q278.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q278"
DEFAULT_B = 300
START = "2008-01-01"
SPLITS = list(range(2014, 2021))  # 分割年 2014〜2020（後半は分割年から）
RULES = ["tsmom20", "tsmom60", "tsmom120", "sma200", "rsi14_contra"]
T_THR = 2.0


def load_sym(sym, args, rng):
    if args.smoke:
        df = _smoke_ohlc(sym, rng, n=5000, freq="D", start=START)
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        df["ret"] = df["close"].pct_change(); df["year"] = df["time"].dt.year
    else:
        df = load_d1(sym, False, rng)
    return df[df["time"] >= pd.Timestamp(START)].reset_index(drop=True)


def rsi_contra_pos(close, n=14, lo=30, hi=70):
    """RSI14 逆張り: RSI<30 で +1、RSI>70 で −1、それ以外は前日の建玉を維持（最初は 0）。"""
    r = rsi(close, n)
    raw = np.where(r < lo, 1.0, np.where(r > hi, -1.0, np.nan))
    return pd.Series(raw).ffill().fillna(0.0).values


def positions(close):
    return {"tsmom20": tsmom_pos(close, 20), "tsmom60": tsmom_pos(close, 60), "tsmom120": tsmom_pos(close, 120),
            "sma200": sma_pos(close, 200), "rsi14_contra": rsi_contra_pos(close)}


def year_means(close, years, sym, yu):
    """規則ごとの純損益の年平均（len(yu) × n_rules）。年のない行は nan。"""
    cost = cost_bp_oneway(sym, close)
    out = np.full((len(yu), len(RULES)), np.nan)
    pos = positions(close)
    inv = np.searchsorted(yu, years)
    cnt = np.bincount(inv, minlength=len(yu))
    for j, r in enumerate(RULES):
        p = pnl_bp(pos[r], close, cost)
        s = np.bincount(inv, weights=p, minlength=len(yu))
        out[:, j] = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)
    return out


def verdict_codes(Y, yu):
    """Y: n_years × n_cells の年平均。分割年ごとにセルの判定（1=支持・−1=棄却（逆向き）・0=他）。返り値 n_splits × n_cells。"""
    out = np.zeros((len(SPLITS), Y.shape[1]), dtype=int)
    for i, S in enumerate(SPLITS):
        pre = Y[yu < S]; post = Y[yu >= S]
        def tvec(Z):
            n = np.sum(np.isfinite(Z), axis=0)
            mu = np.nanmean(Z, axis=0); sd = np.nanstd(Z, axis=0, ddof=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                t = np.where((n >= 2) & (sd > 0), mu / (sd / np.sqrt(np.maximum(n, 1))), np.nan)
            return t, mu
        tp, mp = tvec(pre); tq, mq = tvec(post)
        sup = (tp >= T_THR) & (tq >= T_THR) & (mp > 0) & (mq > 0)
        rej = (tp <= -T_THR) & (tq <= -T_THR) & (mp < 0) & (mq < 0)
        out[i] = np.where(sup, 1, np.where(rej, -1, 0))
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    data = {s: load_sym(s, args, rng) for s in syms}
    yu = np.unique(np.concatenate([d["year"].values for d in data.values()]))
    # 観測
    Y = np.full((len(yu), len(syms) * len(RULES)), np.nan)
    for k, s in enumerate(syms):
        d = data[s]
        Y[:, k * len(RULES):(k + 1) * len(RULES)] = year_means(d["close"].values, d["year"].values, s, yu)
    V = verdict_codes(Y, yu)
    split_cell = (V != V[0:1]).any(axis=0)
    F_obs = float(split_cell.mean())
    n_support = (V == 1).sum(axis=0)
    # 帰無: リターンを年内で並べ替え → 終値を作り直し → 同じ手順で F
    F_null = np.full(args.B, np.nan); n_support_null = np.zeros((args.B, len(RULES)))
    for b in range(args.B):
        Yb = np.full_like(Y, np.nan)
        for k, s in enumerate(syms):
            d = data[s]
            r = d["ret"].values.copy(); r[0] = 0.0
            rp = perm_within(rng, r, d["year"].values)
            cp = d["close"].values[0] * np.cumprod(1 + rp)
            Yb[:, k * len(RULES):(k + 1) * len(RULES)] = year_means(cp, d["year"].values, s, yu)
        Vb = verdict_codes(Yb, yu)
        F_null[b] = float((Vb != Vb[0:1]).any(axis=0).mean())
        n_support_null[b] = (Vb == 1).sum(axis=0).reshape(len(syms), len(RULES)).mean(axis=0)
    z, pct = z_of(F_obs, F_null)
    p95 = float(np.nanpercentile(F_null, 95)) if np.isfinite(F_null).sum() >= 3 else float("nan")
    # 規則別・銘柄別の割れ
    cell_tab = pd.DataFrame({"sym": np.repeat(syms, len(RULES)), "rule": np.tile(RULES, len(syms)), "split": split_cell, "n_support_of_7": n_support})
    for i, S in enumerate(SPLITS):
        cell_tab[f"verdict_{S}"] = V[i]
    by_rule = cell_tab.groupby("rule")["split"].mean().to_dict(); by_sym = cell_tab.groupby("sym")["split"].mean().to_dict()
    summary = {"all": {"n_cells": int(V.shape[1]), "F_obs": f(F_obs), "n_split_cells": int(split_cell.sum()),
                       "F_null_mean": f(np.nanmean(F_null)), "F_null_p95": f(p95), "F_null_max": f(np.nanmax(F_null)), "z": f(z), "pct": f(pct),
                       "n_support_hist": {str(k): int((n_support == k).sum()) for k in range(len(SPLITS) + 1)},
                       "n_support_null_mean_per_rule": {r: f(n_support_null[:, j].mean()) for j, r in enumerate(RULES)},
                       "split_frac_by_rule": {r: f(v) for r, v in by_rule.items()}, "split_frac_by_sym": {s: f(v) for s, v in by_sym.items()},
                       "support_count_by_split_year": {str(S): int((V[i] == 1).sum()) for i, S in enumerate(SPLITS)},
                       "reject_count_by_split_year": {str(S): int((V[i] == -1).sum()) for i, S in enumerate(SPLITS)}}}
    if not np.isfinite(F_obs) or not np.isfinite(p95):
        verdict = "未確定: 計算できない（F または帰無が nan）"
    elif p95 <= 0:
        verdict = "未確定: 帰無の F が 0 近く（95 点=0）で比較不能"
    elif F_obs <= p95:
        verdict = f"支持: 観測 F={F_obs:.3f} ≤ 帰無の 95 点 {p95:.3f}（分割依存は偽陽性の水準を超えない）"
    else:
        worst = sorted(by_rule.items(), key=lambda kv: -kv[1])
        verdict = f"棄却: 観測 F={F_obs:.3f} > 帰無の 95 点 {p95:.3f}（分割年に依存。割れの多い規則: " + "・".join(f"{r}={v:.2f}" for r, v in worst[:3]) + "）"
    res = {"question": "前後半の分割年を 2014〜2020 で動かすと「前後半とも同符号 t≥2」の判定は何割割れるか",
           "settings": {"syms": SYMS, "rules": RULES, "start": START, "splits": SPLITS, "t_thr": T_THR, "B": args.B,
                       "cell_verdict": "支持=前後半とも平均>0 かつ t≥2・棄却=前後半とも平均<0 かつ t≤−2・他",
                       "null": "リターンを年内で並べ替え（perm_within）→ 終値を作り直し → 同じ手順で F"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は F の 1 本。75 セルは判定の材料で個別には検定しない。"}
    return res, {"cells": cell_tab, "null_F": pd.DataFrame({"b": np.arange(args.B), "F": F_null})}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
