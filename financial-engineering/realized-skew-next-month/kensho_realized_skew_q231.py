#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q231: H1 から作る月次の実現歪度は翌月リターンを負に予測するか（Amaya ほか 2015 の型・15 銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q231 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Amaya, Christoffersen, Jacobs & Vasquez (2015) "Does realized skewness predict the cross-section of equity returns?" JFE 118
  （日中データから作る週次の実現歪度が高い株ほど翌週のリターンが低い。本文未読・要旨のみ）。
- [[Farag2024-1_暗号資産の5分足の流動性供給の見返りはボラや暴落リスクで説明できる]]（高次モーメントと短期の見返り）、知見 Q174（ボラの変化と 1 日逆張り）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "realized skewness predicts next month returns currencies commodities intraday data Amaya"）:
  株の横断面（Amaya 2015）と商品のインプライド歪度（AUT・SMU のワーキングペーパー）が見つかる。為替 8＋商品・指数・BTC の 15 銘柄で
  H1 から作った月次の実現歪度を時系列と横断面の両方で測る形は未確認。移植。

【仮説（測る前に固定）】
H: 月 m の実現歪度 RSk_m（H1 リターンから）が高いほど、翌月 m+1 のリターンは低い（負の関係）。

【データ】15 銘柄の H1（Dukascopy・UTC、2008〜2026-06。油・指数は 2011-09〜、BTC は 2017〜）。無い銘柄は除いて missing に書く。

【定義（1通りに固定）】
- 月 m の H1 リターン r_i（n 本）。実現分散 RV = Σ r_i²、実現歪度 RSk = √n · Σ r_i³ / RV^{3/2}（Amaya 式）。n < 200 の月は除く。
- 翌月リターン R_{m+1} = ln(月末終値_{m+1} / 月末終値_m)（H1 の最後の終値）[bp]。
- (a) 時系列・プール: 全 (銘柄, 月) で Spearman(RSk_m, R_{m+1})。銘柄ごとの Spearman も出す。
- (b) 横断面: 各月に 15 銘柄で Spearman(RSk_m, R_{m+1})（銘柄数 ≥ 8 の月だけ）→ 月平均と t。
- (c) 売買（記述）: 各月、歪度の下位 1/3 を買い・上位 1/3 を売り（等加重）、翌月の純損益（片道コスト段階1・月 1 回の入替）。

【測るもの】前半（月 < 2017）／後半（≥ 2017）／全期間の (a)(b)(c)。

【帰無】(a): 翌月リターンを銘柄内で並べ替え B=500。(b): 月内で銘柄を並べ替え B=500。

【判定（事前固定・変更禁止）】
- (a) のプール Spearman が前半・後半とも < 0 かつ z ≤ −2 → 支持（歪度は翌月リターンを負に予測）。
- 前半・後半のどちらかで z > −2 → 棄却。
- (b)(c) は記述（横断面は 15 銘柄で検出力が低い）。
多重比較: 判定は (a) の前後半 2 本。

【捨てた案の数】約4: 週次（Amaya の形。月次に統一して標本の重なりを避ける）、歪度の代わりに尖度、M15 で作る案（M15 は 3 銘柄だけ）、
歪度を 3 か月の移動平均にする案。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパスと (a) の ρ・z（前後半）を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_realized_skew_q231.py            （B=500・1 分前後）
      python3 kensho_realized_skew_q231.py --smoke
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

QID = "Q231"
DEFAULT_B = 500
MIN_BARS = 200
MIN_SYMS_CS = 8


def monthly_table(args, rng):
    rows = []; missing = []
    for s in SYMS:
        if not args.smoke and not exists_sym(s, "H1_dukascopy"):
            missing.append(s); continue
        df = load_h1(s, args.smoke, rng, n=150000, start="2008-01-01")
        df = df.dropna(subset=["ret"]).copy(); df["ym"] = df["time"].dt.to_period("M")
        g = df.groupby("ym")
        n = g["ret"].size(); rv = g["ret"].apply(lambda x: float((x ** 2).sum())); r3 = g["ret"].apply(lambda x: float((x ** 3).sum()))
        close = g["close"].last()
        rsk = np.sqrt(n) * r3 / np.power(rv, 1.5)
        m = pd.DataFrame({"n": n, "rsk": rsk, "close": close})
        m["R_next"] = np.log(m["close"].shift(-1) / m["close"]) * 1e4
        m = m[m["n"] >= MIN_BARS].dropna(subset=["rsk", "R_next"])
        m["sym"] = s; m["year"] = [p.year for p in m.index]; m["ym"] = [str(p) for p in m.index]
        # コスト（記述用）: 月末の終値に対する片道 bp
        m["cost_bp"] = cost_bp_oneway(s, m["close"].values) if s in COST_RT else np.nan
        rows.append(m.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True), missing


def pooled_rho(df):
    return spearman(df["rsk"].values, df["R_next"].values)


def cs_ic(df):
    ics = []
    for ym, d in df.groupby("ym"):
        if len(d) >= MIN_SYMS_CS:
            ics.append(spearman(d["rsk"].values, d["R_next"].values))
    ics = np.array(ics, float)
    return {"n_months": int(len(ics)), "mean_ic": f(np.nanmean(ics)) if len(ics) else None, "t": f(tstat(ics))}


def ls_pnl(df):
    out = []
    for ym, d in df.groupby("ym"):
        if len(d) < MIN_SYMS_CS:
            continue
        d = d.sort_values("rsk"); k = max(1, len(d) // 3)
        lo = d.iloc[:k]; hi = d.iloc[-k:]
        gross = lo["R_next"].mean() - hi["R_next"].mean()
        cost = 2 * (lo["cost_bp"].mean() + hi["cost_bp"].mean()) / 2  # 往復（月 1 回の入替・近似）
        out.append(gross - cost)
    out = np.array(out, float)
    return {"n_months": int(len(out)), "net_bp_per_month": f(np.nanmean(out)) if len(out) else None, "t": f(tstat(out))}


def run(args, rng):
    tab, missing = monthly_table(args, rng)
    summary = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        d = tab[(tab["year"] >= y0) & (tab["year"] < y1)].copy()
        if d.empty:
            continue
        rho = pooled_rho(d)
        null_a = []; null_b = []
        for b in range(args.B):
            d2 = d.copy(); d2["R_next"] = perm_within(rng, d2["R_next"].values, d2["sym"].values)
            null_a.append(pooled_rho(d2))
            d3 = d.copy(); d3["R_next"] = perm_within(rng, d3["R_next"].values, d3["ym"].values)
            ic = cs_ic(d3); null_b.append(ic["mean_ic"] if ic["mean_ic"] is not None else np.nan)
        z_a, _ = z_of(rho, null_a)
        ic = cs_ic(d); z_b, _ = z_of(ic["mean_ic"] if ic["mean_ic"] is not None else np.nan, null_b)
        per_sym = {s: f(spearman(dd["rsk"].values, dd["R_next"].values)) for s, dd in d.groupby("sym")}
        summary[pn] = {"n_obs": int(len(d)), "pooled_rho": f(rho), "pooled_z": f(z_a), "per_sym_rho": per_sym,
                       "n_sym_negative": int(sum(1 for v in per_sym.values() if v is not None and v < 0)),
                       "cs": {**ic, "z": f(z_b)}, "long_short": ls_pnl(d)}
    g = lambda p, k: (summary.get(p, {}).get(k) if summary.get(p, {}).get(k) is not None else float("nan"))
    if all(g(p, "pooled_rho") < 0 and g(p, "pooled_z") <= -2 for p in ("pre", "post")):
        verdict = "支持: 実現歪度は翌月リターンを負に予測する"
    elif any(np.isnan(g(p, "pooled_z")) for p in ("pre", "post")):
        verdict = "未確定: 期間の標本が無い"
    else:
        verdict = "棄却: 前後半のどちらかで z > −2"
    res = {"question": "H1 から作る月次の実現歪度は翌月リターンを負に予測するか", "settings": {"min_bars": MIN_BARS, "B": args.B, "split_year": SPLIT_YEAR},
           "missing": missing, "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は (a) プール Spearman の前後半 2 本。横断面・売買・銘柄別は記述。"}
    return res, {"monthly": tab[["sym", "ym", "n", "rsk", "R_next"]]}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
