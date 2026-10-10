#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q263: アルトコインの対 BTC 相対強弱（4 週）は翌週の相対リターンを予測するか（10 通貨の横断・順位並べ替え帰無）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q263 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Liu・Tsyvinski・Wu 2022、知見 Q218（横断と時系列の差は非有意）、Q262（時系列）、EUR の修士論文（横断モメンタムの暗号資産）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "altcoin relative strength versus bitcoin cross-sectional momentum weekly predicts returns"）:
  見つかったもの: EUR の修士論文（thesis.eur.nl 59629）、ETC Group・Block Scholes（ブログ）。
  未確認: 根拠にしない（ブログ中心）。対 BTC 比率の 4 週で 10 通貨・2022 分割・順位並べ替え帰無は未確認（移植）。

【仮説（測る前に固定）】
H: 週次（UTC 月曜 0 時区切り）で各アルトの対 BTC 比率の 4 週リターンで 10 通貨を並べ、上位 3 買い／下位 3 売り（対 BTC 相対）の翌週リターン [bp/週] は正。

【データ】
暗号資産 11 通貨 H1 → 週次終値（BTC で割った比率）。2018〜2026-09。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
比率 R_i = P_i/P_BTC。4 週リターンで順位づけ。翌週の上位 3 の平均 − 下位 3 の平均（対 BTC・コストは往復 CRYPTO_COST_RT_REL×2 を週ごとに引く）。

【測るもの】
週次の平均 [bp/週] と NW t（lag 4）、年単位 t。前半 〜2021／後半 2022–。

【帰無】
各週の順位を無作為に付け替え（順位並べ替え）B=2000 → 平均の帰無分布 → z。

【判定（事前固定・変更禁止）】
前後半とも 平均>0 かつ z≥2 → 支持。全期間 z<2 → 棄却。それ以外 → 未確定。
多重比較: 判定は前後半 2 本。年単位 t は記述。

【捨てた案の数】
約3: 1 週・12 週の参照（4 週に固定）、BTC 自身を含める（相対なので除く）、ドル建てで並べる（Q262 と混ざる）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_alt_btc_rs_q263.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_alt_btc_rs_q263.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q263"
DEFAULT_B = 2000
LOOKBACK_W = 4
TOPK = 3
SPLIT_CRYPTO = 2022
KIND = "H1_dukascopy"
BASE = "BTCUSD"
ALTS = [s for s in CRYPTO if s != BASE]
COST_BP_WEEK = CRYPTO_COST_RT_REL * 2 * 1e4  # 往復×2 を週ごとに引く


def weekly_close(h1):
    """UTC 月曜 0 時区切りの週次終値（ラベルは週の始まりの月曜）。"""
    s = h1.set_index("time")["close"]
    return s.resample("W-MON", closed="left", label="left").last()


def run(args, rng):
    syms, missing = syms_available(CRYPTO, KIND, args.smoke)
    if BASE not in syms:
        return {"question": "アルトの対 BTC 相対強弱（4 週）は翌週の相対リターンを予測するか", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない（BTC が無い）", "settings": {}, "multiple_comparisons": ""}, None
    wk = {}
    for s in syms:
        h1 = load_h1(s, args.smoke, rng, n=60000, start="2018-01-01")
        wk[s] = weekly_close(h1)
    W = pd.concat(wk, axis=1)
    alts = [s for s in ALTS if s in W.columns]
    R = W[alts].div(W[BASE], axis=0)                       # 対 BTC 比率
    past = R / R.shift(LOOKBACK_W) - 1                      # 4 週リターン（今週末まで）
    nxt = (R.shift(-1) / R - 1) * 1e4                      # 翌週の比率リターン [bp]
    P = past.values; N = nxt.values
    avail = np.isfinite(P) & np.isfinite(N)
    nav = avail.sum(1)
    ok = nav >= 2 * TOPK
    idx = np.where(ok)[0]
    if len(idx) < 20:
        return {"question": "アルトの対 BTC 相対強弱（4 週）は翌週の相対リターンを予測するか", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない（週が足りない）", "settings": {}, "multiple_comparisons": ""}, None
    P = P[idx]; N = N[idx]; A = avail[idx]; nav = nav[idx]
    N0 = np.where(A, N, 0.0)
    weeks = R.index[idx]
    years = weeks.year.values

    def ls_ret(keys):
        """keys（大きいほど上位）で並べ、上位 TOPK − 下位 TOPK の翌週リターン [bp]。利用不可は末尾に回す。"""
        k = np.where(A, keys, -np.inf)
        order = np.argsort(-k, axis=1)                      # 降順（-inf は最後）
        top = order[:, :TOPK]
        bot_pos = (nav[:, None] - TOPK + np.arange(TOPK)[None, :])
        bot = np.take_along_axis(order, bot_pos, axis=1)
        return np.take_along_axis(N0, top, axis=1).mean(1) - np.take_along_axis(N0, bot, axis=1).mean(1)

    y = ls_ret(P) - COST_BP_WEEK
    # 帰無: 各週の順位を無作為に付け替え（順位並べ替え）
    null = {"all": [], "pre": [], "post": []}
    pre_m = years < SPLIT_CRYPTO; post_m = ~pre_m
    for b in range(args.B):
        yb = ls_ret(rng.random(P.shape)) - COST_BP_WEEK
        null["all"].append(yb.mean()); null["pre"].append(yb[pre_m].mean() if pre_m.any() else np.nan)
        null["post"].append(yb[post_m].mean() if post_m.any() else np.nan)
    cells = pd.DataFrame({"week": weeks, "year": years, "y_bp": y, "n_avail": nav})
    summary = {}
    for p, m in (("all", np.ones(len(y), bool)), ("pre", pre_m), ("post", post_m)):
        if m.sum() < 3:
            summary[p] = {"n_weeks": int(m.sum()), "mean_bp_per_week": None, "nw_t": None, "z": None, "pct": None, "year_t": None, "n_years": 0}
            continue
        z, pct = z_of(y[m].mean(), null[p])
        yt = by_year_stats(cells[m], "y_bp")
        summary[p] = {"n_weeks": int(m.sum()), "mean_bp_per_week": f(y[m].mean()), "nw_t": f(nw_t(y[m], lag=4)), "z": f(z), "pct": f(pct),
                      "year_t": f(yt["t"]), "n_years": yt["n_years"], "gross_mean_bp_per_week": f(y[m].mean() + COST_BP_WEEK)}
    g = lambda p, k: summary[p].get(k)
    if any(g(p, k) is None for p in ("all", "pre", "post") for k in ("mean_bp_per_week", "z")):
        verdict = "未確定: 計算できない"
    elif all(g(p, "mean_bp_per_week") > 0 and g(p, "z") >= 2 for p in ("pre", "post")):
        verdict = "支持: 前後半とも 平均>0 かつ z≥2"
    elif g("all", "z") < 2:
        verdict = "棄却: 全期間 z<2"
    else:
        verdict = "未確定"
    res = {"question": "アルトコインの対 BTC 相対強弱（4 週）は翌週の相対リターンを予測するか（10 通貨の横断）",
           "settings": {"base": BASE, "alts": alts, "lookback_weeks": LOOKBACK_W, "top_k": TOPK, "week": "UTC 月曜 0 時区切り",
                        "cost_bp_per_week": COST_BP_WEEK, "split_year": SPLIT_CRYPTO, "B": args.B, "min_avail_per_week": 2 * TOPK,
                        "null": "各週の順位を無作為に付け替え（順位並べ替え）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は前後半 2 本。年単位 t・NW t は記述。"}
    return res, {"weekly": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
