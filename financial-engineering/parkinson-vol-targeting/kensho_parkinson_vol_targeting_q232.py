#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q232: Parkinson レンジボラでのボラ・ターゲティングは終値 σ60 版よりシャープが高いか（Q222 × Q205 の連鎖）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q232 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q222（Parkinson のレンジ入力 HAR は終値二乗入力より翌日 RV の QLIKE を下げる・支持）、知見 Q205（σ60 逆数・CAP=4 の
  ボラ・ターゲティングは順張りのシャープを +0.09 上げる・支持）→ 連鎖: 「よりよいボラ予測 → よりよいボラ・ターゲティング」。
- Parkinson (1980)、Harvey ほか (2018) "The Impact of Volatility Targeting"。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "volatility targeting range-based Parkinson estimator trend following Sharpe improvement"）:
  レンジ推定量の性質（arXiv 2312.01426 ほか）は多いが、順張りのボラ・ターゲティングの入力をレンジに替えて標本外のシャープを
  対応ありで比べた研究は未確認。連鎖。

【仮説（測る前に固定）】
H: 規模 w_t = min(CAP, σ_target / σ̂_t) の σ̂ を、終値の 60 日標準偏差（CC）から Parkinson の 60 日（PK）に替えると、
   順張り（TSMOM60）の年ごとのシャープが上がる（対応ありの差 PK − CC > 0）。

【データ】15 銘柄の UTC 日足（D1_fromH1、高値・安値あり、2008〜2026-06）。

【定義（1通りに固定）】
- 合図 s_t = sign(c_t − c_{t−60})。σ_target = 10%/√252（日次）。CAP = 4（Q205 と同じ）。
- σ̂_CC,t = std(日次リターン の直前 60 日)、σ̂_PK,t = √( mean_{60日} ln(H/L)² / (4 ln 2) )。どちらも t までの値だけ（先読みなし）。
- pos_t = s_t × w_t。純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（段階1）。
- 年×銘柄のシャープ（√252）→ 年の平均 → 対応ありの差の年単位 t。あわせて 実現ボラ÷目標 の 1 からのずれ |RV/target − 1| の平均（どちらが目標に近いか・記述）。

【測るもの】群 all15・fx8・trend7 × 前半（<2017）／後半（≥2017）／全期間: sharpe_CC・sharpe_PK・差・t・z、純損益の差、ずれの差。

【帰無】各銘柄の日次の Parkinson 分散を年内で並べ替えてから 60 日平均を取る（レンジと翌日のボラの対応を壊し、分布は保つ）B=300
→ 差 PK−CC の帰無分布 → z。

【判定（事前固定・変更禁止）】
- all15 で前半・後半とも シャープの差 > 0 かつ t ≥ 2 かつ z ≥ 2 → 支持。
- all15 で前半・後半とも t ≤ −2 → 逆向きで確定（レンジ版は劣る）。
- それ以外 → 棄却（改善は見えない）。
多重比較: 判定は all15 前後半の (t, z) 4 本。群別・純損益・ずれは記述。

【捨てた案の数】約4: Garman-Klass や Rogers-Satchell を並べる案（PK 1 本）、HAR 予測を入力にする案（単純な 60 日に統一）、
σ_target を 15% にする案、CAP なし。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・差の t と z（前後半）を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_parkinson_vol_targeting_q232.py            （B=300・1 分前後）
      python3 kensho_parkinson_vol_targeting_q232.py --smoke
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

QID = "Q232"
DEFAULT_B = 300
L_MOM = 60
WIN = 60
CAP = 4.0
SIG_TARGET = 0.10 / math.sqrt(252)


def weights(sig_hat):
    w = SIG_TARGET / np.asarray(sig_hat, float)
    w[~np.isfinite(w)] = 0.0
    return np.minimum(CAP, w)


def pk_var_daily(high, low):
    return (np.log(np.asarray(high, float) / np.asarray(low, float)) ** 2) / (4 * math.log(2))


def roll_mean(x, n):
    return pd.Series(x).rolling(n).mean().values


def yearly(cells):
    """cells: DataFrame(year, sym, pnl_cc, pnl_pk) → 群×期間の年単位の統計。"""
    out = {}
    for g, members in GROUPS.items():
        cg = cells[cells["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            sy = d.groupby(["year", "sym"]).agg(sh_cc=("pnl_cc", sharpe_ann), sh_pk=("pnl_pk", sharpe_ann), p_cc=("pnl_cc", "mean"), p_pk=("pnl_pk", "mean"),
                                                 rv_cc=("pnl_cc", lambda x: abs(np.std(x, ddof=1) / 1e4 / SIG_TARGET - 1)),
                                                 rv_pk=("pnl_pk", lambda x: abs(np.std(x, ddof=1) / 1e4 / SIG_TARGET - 1))).reset_index()
            yr = sy.groupby("year").mean(numeric_only=True)
            dd = (yr["sh_pk"] - yr["sh_cc"]).dropna()
            out[f"{g}_{pn}"] = {"n_years": int(len(yr)), "sharpe_cc": f(yr["sh_cc"].mean()), "sharpe_pk": f(yr["sh_pk"].mean()),
                                "sharpe_diff": f(dd.mean()), "sharpe_diff_t": f(tstat(dd.values)),
                                "pnl_diff_bp": f((yr["p_pk"] - yr["p_cc"]).mean()), "pnl_diff_t": f(tstat((yr["p_pk"] - yr["p_cc"]).values)),
                                "dev_from_target_cc": f(yr["rv_cc"].mean()), "dev_from_target_pk": f(yr["rv_pk"].mean())}
    return out


def build_cells(store, pk_override=None):
    rows = []
    for s, (yr, sig, c, cb, r, pkv) in store.items():
        pkv2 = pk_override[s] if pk_override is not None else pkv
        scc = pd.Series(r).rolling(WIN).std(ddof=1).values
        spk = np.sqrt(roll_mean(pkv2, WIN))
        rows.append(pd.DataFrame({"year": yr, "sym": s, "pnl_cc": pnl_bp(sig * weights(scc), c, cb), "pnl_pk": pnl_bp(sig * weights(spk), c, cb)}))
    return pd.concat(rows, ignore_index=True)


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    store = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        r = np.r_[np.nan, c[1:] / c[:-1] - 1]
        store[s] = (yr, tsmom_pos(c, L_MOM), c, cb, r, pk_var_daily(df["high"].values, df["low"].values))
    obs = yearly(build_cells(store))
    null = {k: [] for k in obs}
    for b in range(args.B):
        ov = {s: perm_within(rng, np.nan_to_num(v[5], nan=np.nanmedian(v[5])), v[0]) for s, v in store.items()}
        st = yearly(build_cells(store, ov))
        for k in obs:
            if k in st:
                null[k].append(st[k]["sharpe_diff"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, pct = z_of(v["sharpe_diff"] if v["sharpe_diff"] is not None else np.nan, null[k])
        summary[k] = {**v, "sharpe_diff_z": f(z), "null_mean": f(np.nanmean(null[k])) if null[k] else None}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, q: (p.get(q) if p.get(q) is not None else float("nan"))
    if all(g(p, "sharpe_diff") > 0 and g(p, "sharpe_diff_t") >= 2 and g(p, "sharpe_diff_z") >= 2 for p in (pre, post)):
        verdict = "支持: Parkinson 入力のボラ・ターゲティングはシャープを上げる"
    elif all(g(p, "sharpe_diff_t") <= -2 for p in (pre, post)):
        verdict = "逆向きで確定: レンジ版は劣る"
    else:
        verdict = "棄却: 改善は見えない"
    res = {"question": "Parkinson レンジボラでのボラ・ターゲティングは終値 σ60 版よりシャープが高いか",
           "settings": {"L": L_MOM, "win": WIN, "cap": CAP, "sig_target_daily": SIG_TARGET, "B": args.B}, "missing": missing,
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の (t, z) 4 本。群別・純損益・目標からのずれは記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
