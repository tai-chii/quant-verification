#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q236: 4 組（XAU→XAG・WTI→UKOIL・BTC→ETH・US500→USTECH）の H1 リード・ラグは、両方向のどちらが強いか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q236 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q213（USTECH の直前 1 時間は BTC の次の 1 時間を予測しない・棄却）。Lo & MacKinlay (1990) 大型株→小型株のリード・ラグ。
  Sifat ほか (2019) "Lead-Lag relationship between Bitcoin and Ethereum: Evidence from hourly and daily data" RIBAF 50（要旨のみ）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "lead-lag gold silver hourly returns Brent WTI bitcoin ethereum lead lag cross-correlation"）:
  BTC–ETH の時間足（2019・2017〜2018 の標本）、為替のリード・ラグ（arXiv 1906.10388）、暗号資産の価格発見（arXiv 2506.08718）が見つかる。
  4 組を同じ設計・同じ帰無（循環シフト）・前後半で並べ、両方向を比べる形は未確認。移植＋条件の穴（2020 年以降）。

【仮説（測る前に固定）】
H: 「大きい・流動性の高い市場」（XAU・WTI・BTC・US500）の直前 1 時間のリターンは、「小さい市場」（XAG・UKOIL・ETH・USTECH）の
   次の 1 時間のリターンを正に予測し（順方向 IC > 0）、逆方向は予測しない。

【データ】各組の H1（Dukascopy・UTC）。共通時刻だけ。期間の区切り: 金銀・油・指数は 2017（前半 2011/2008〜2016）、BTC–ETH は 2022（ETH は 2017-12〜）。

【定義（1通りに固定）】
- 順方向 IC_f = Spearman(r_lead,t, r_lag,t+1)、逆方向 IC_r = Spearman(r_lag,t, r_lead,t+1)。年ごとに出し、年の平均と年単位の t。
- 同時相関 Spearman(r_lead,t, r_lag,t)（記述）。
- 売買（記述）: lag 銘柄を lead の直前 1 時間の符号で 1 時間持つ。純損益 [bp] = sign × r_lag,t+1 × 1e4 − 往復コスト（段階1）。

【帰無】lag 側の列を 48 本以上の循環シフト B=500 → IC_f・IC_r（全期間の年平均）の帰無分布 → z。

【判定（事前固定・変更禁止）】組ごとに:
- 順方向 IC_f > 0 かつ 前半・後半とも z ≥ 2、かつ 逆方向の z < 2（前後半とも）→ 「lead → lag」。
- 両方向とも z ≥ 2、または両方向とも z < 2 → その組は棄却（一方向の先導なし）。
- 逆方向だけ z ≥ 2 → 「向きが逆」（記述。仮説は棄却）。
総合: 4 組中 3 組以上で「lead → lag」なら支持。1 組以下なら棄却。2 組なら未確定。
多重比較: 4 組 × 2 方向 × 2 期間 = 16 本。

【捨てた案の数】約4: 2 時間先まで見る案、日足版（Q241 で商品通貨を扱う）、同時相関の高い組だけに絞る案、VAR のグレンジャー検定（Spearman に統一）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・組ごとの IC と z（両方向・前後半）を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_cross_market_leadlag_q236.py            （B=500・2 分前後）
      python3 kensho_cross_market_leadlag_q236.py --smoke
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

QID = "Q236"
DEFAULT_B = 500
PAIRS = {"xau_xag": ("XAUUSD", "XAGUSD", 2017), "wti_ukoil": ("WTI", "UKOIL", 2017), "btc_eth": ("BTCUSD", "ETHUSD", 2022), "us500_ustech": ("US500", "USTECH", 2017)}


def yearly_ic(year, a, b):
    """Spearman(a_t, b_t+1) を年ごとに。a,b: リターン列。"""
    df = pd.DataFrame({"year": year[:-1], "a": a[:-1], "b": b[1:]}).dropna()
    ic = df.groupby("year").apply(lambda d: spearman(d["a"].values, d["b"].values) if len(d) > 100 else np.nan)
    return ic.dropna()


def pstats(ic, split):
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, split)), ("post", (split, 9999))):
        v = ic[(ic.index >= y0) & (ic.index < y1)]
        out[pn] = {"n_years": int(len(v)), "ic": f(v.mean()) if len(v) else None, "t": f(tstat(v.values))}
    return out


def run(args, rng):
    summary = {}; missing = []
    for name, (lead, lag, split) in PAIRS.items():
        if not args.smoke and not (exists_sym(lead, "H1_dukascopy") and exists_sym(lag, "H1_dukascopy")):
            missing.append(name); continue
        A = load_h1(lead, args.smoke, rng, n=120000, start="2010-01-01"); Bf = load_h1(lag, args.smoke, rng, n=120000, start="2010-01-01")
        m = A[["time", "ret", "year"]].merge(Bf[["time", "ret", "close"]], on="time", suffixes=("_lead", "_lag")).dropna().reset_index(drop=True)
        yr = m["year"].values; rl = m["ret_lead"].values; rg = m["ret_lag"].values
        obs = {"forward": pstats(yearly_ic(yr, rl, rg), split), "reverse": pstats(yearly_ic(yr, rg, rl), split),
               "contemporaneous_rho": f(spearman(rl, rg))}
        cb = cost_bp_oneway(lag, m["close"].values) if lag in COST_RT else cost_bp_oneway(lag, m["close"].values, rel=CRYPTO_COST_RT_REL)
        sgn = np.r_[0.0, np.sign(rl[:-1])]; pnl = sgn * rg * 1e4 - np.abs(np.diff(np.r_[0.0, sgn])) * cb
        obs["trade_lag_by_lead_sign"] = {"net_bp_per_hour": f(pnl[1:].mean()), "t_nw": f(nw_t(pnl[1:], 24))}
        null = {d: {pn: [] for pn in ("all", "pre", "post")} for d in ("forward", "reverse")}
        for b in range(args.B):
            rg2 = np.roll(rg, int(rng.integers(48, len(rg) - 48)))
            fw = pstats(yearly_ic(yr, rl, rg2), split); rv = pstats(yearly_ic(yr, rg2, rl), split)
            for pn in ("all", "pre", "post"):
                null["forward"][pn].append(fw[pn]["ic"] if fw[pn]["ic"] is not None else np.nan)
                null["reverse"][pn].append(rv[pn]["ic"] if rv[pn]["ic"] is not None else np.nan)
        for d in ("forward", "reverse"):
            for pn in ("all", "pre", "post"):
                z, _ = z_of(obs[d][pn]["ic"] if obs[d][pn]["ic"] is not None else np.nan, null[d][pn]); obs[d][pn]["z"] = f(z)
        g = lambda d, pn, k: (obs[d][pn].get(k) if obs[d][pn].get(k) is not None else float("nan"))
        fwd_ok = all(g("forward", pn, "ic") > 0 and g("forward", pn, "z") >= 2 for pn in ("pre", "post"))
        rev_ok = all(g("reverse", pn, "z") >= 2 for pn in ("pre", "post"))
        if fwd_ok and not any(g("reverse", pn, "z") >= 2 for pn in ("pre", "post")):
            verdict = "lead → lag"
        elif rev_ok and not fwd_ok:
            verdict = "向きが逆（lag → lead）"
        else:
            verdict = "棄却: 一方向の先導なし"
        obs["verdict"] = verdict; obs["split_year"] = split; obs["n_hours"] = int(len(m))
        summary[name] = obs
    n_lead = sum(1 for v in summary.values() if v["verdict"] == "lead → lag")
    verdict = "支持: 3 組以上で lead → lag" if n_lead >= 3 else ("未確定: 2 組" if n_lead == 2 else "棄却: 1 組以下")
    res = {"question": "4 組の H1 リード・ラグは両方向のどちらが強いか", "settings": {"pairs": PAIRS, "B": args.B, "min_shift": 48}, "missing": missing,
           "summary": summary, "n_lead_to_lag": n_lead, "machine_verdict": verdict, "multiple_comparisons": "4 組 × 2 方向 × 2 期間 = 16 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
