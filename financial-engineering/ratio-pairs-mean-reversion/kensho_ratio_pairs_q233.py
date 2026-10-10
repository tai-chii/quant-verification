#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q233: 金銀比・Brent−WTI の z スコア逆張り（ペアトレード）は 2015 年以降コスト後に残るか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q233 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Gatev, Goetzmann & Rouwenhorst (2006) "Pairs Trading: Performance of a Relative-Value Arbitrage Rule"（距離法・本文未読）、
  `pair-trading/`（IEF/TLT・NVDA/AMD の共和分検証・手元）、知見 Q042（為替の押し目逆張りは戻らない）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "gold silver ratio mean reversion pairs trading z-score backtest transaction costs Brent WTI spread"）:
  ブログ・TradingView のスクリプト・QuantConnect の個別バックテストが多数。前後半＋循環シフト帰無＋コスト込みで同じ規則を
  2 組に当てて事前固定で判定する形は未確認。条件の穴（ブログは根拠にしない）。

【仮説（測る前に固定）】
H: 比の対数 s_t = ln P1 − ln P2 の 60 日 z スコアが ±2 を超えたら比の縮小に賭ける（|z| < 0.5 で手仕舞い）規則は、
   コスト後の純損益が正で、合図を循環シフトした帰無より大きい。

【データ】UTC 日足（D1_fromH1）: 組 A = (XAUUSD, XAGUSD) 2008〜、組 B = (UKOIL, WTI) 2011-09〜（共通日だけ）。

【定義（1通りに固定）】
- z_t = (s_t − mean_{60}(s)) / std_{60}(s)（t までの値だけ）。
- 建玉: z_t > +2 → 比の売り（P1 売り・P2 買い）、z_t < −2 → 比の買い。|z_t| < 0.5 で手仕舞い。t の終値で決めて t+1 のリターンに効く。
- 組の純損益 [bp] = pos × (r1 − r2) × 1e4 − |Δpos| × (片道コスト1 + 片道コスト2)（段階1の保守値）。
- 年単位の t（年の平均）、シャープ、取引回数、平均保有日数、比の半減期（AR(1) から・記述）。

【測るもの】組ごとに 前半（<2017）／後半（≥2017）／全期間。

【帰無】合図（pos の列）の循環シフト（≥252 日）B=300 → 純損益の帰無分布 → z。

【判定（事前固定・変更禁止）】
- 組ごとに、前半・後半とも 純損益 > 0 かつ 年単位 t ≥ 2 かつ z ≥ 2 → その組は「残る」。
- 2 組とも残らなければ 棄却。1 組だけ残れば 未確定（組依存）。2 組とも残れば 支持。
多重比較: 2 組 × 2 期間 × (t, z) = 8 本。

【捨てた案の数】約4: 共和分検定を事前の関門にする案（規則を 1 本に固定）、z の閾値 1.5/2.5 の格子、保有上限日数、ドル円×ユーロ円のような為替の組。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・組ごとの純損益・t・z を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_ratio_pairs_q233.py            （B=300・30 秒）
      python3 kensho_ratio_pairs_q233.py --smoke
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

QID = "Q233"
DEFAULT_B = 300
PAIRS = {"gold_silver": ("XAUUSD", "XAGUSD"), "brent_wti": ("UKOIL", "WTI")}
WIN = 60
Z_IN, Z_OUT = 2.0, 0.5


def zscore_signal(s):
    m = pd.Series(s).rolling(WIN).mean().values; sd = pd.Series(s).rolling(WIN).std(ddof=1).values
    z = (s - m) / sd
    pos = np.zeros(len(s)); p = 0.0
    for t in range(len(s)):
        if not np.isfinite(z[t]):
            pos[t] = 0.0; continue
        if p == 0.0:
            if z[t] > Z_IN:
                p = -1.0
            elif z[t] < -Z_IN:
                p = 1.0
        elif abs(z[t]) < Z_OUT:
            p = 0.0
        pos[t] = p
    return pos, z


def pair_pnl(pos, c1, c2, cb1, cb2):
    r1 = np.r_[0.0, c1[1:] / c1[:-1] - 1]; r2 = np.r_[0.0, c2[1:] / c2[:-1] - 1]
    held = np.r_[0.0, pos[:-1]]; prev = np.r_[0.0, held[:-1]]
    cost = np.abs(held - prev) * np.r_[0.0, (cb1 + cb2)[:-1]]
    return held * (r1 - r2) * 1e4 - cost


def half_life(s):
    x = np.asarray(s, float); x = x[np.isfinite(x)]
    if len(x) < 30:
        return float("nan")
    dx = np.diff(x); xl = x[:-1] - x[:-1].mean()
    beta = float((xl * (dx - dx.mean())).sum() / (xl ** 2).sum())
    return float(-math.log(2) / math.log(1 + beta)) if -1 < beta < 0 else float("inf")


def period_stats(year, pnl, pos):
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        m = (year >= y0) & (year < y1)
        if m.sum() < 60:
            continue
        df = pd.DataFrame({"year": year[m], "pnl": pnl[m]})
        st = by_year_stats(df, "pnl")
        held = np.r_[0.0, pos[m][:-1]]; chg = np.abs(np.diff(np.r_[0.0, held])) > 0
        n_tr = int(chg.sum()); exposure = float((held != 0).mean())
        out[pn] = {"n_years": st["n_years"], "pnl_bp": f(st["mean"]), "t": f(st["t"]), "sharpe": f(sharpe_ann(pnl[m])),
                   "n_switches": n_tr, "exposure": f(exposure)}
    return out


def run(args, rng):
    summary = {}; missing = []
    for name, (a, b) in PAIRS.items():
        if not args.smoke and not (exists_sym(a) and exists_sym(b)):
            missing.append(name); continue
        d1 = load_d1(a, args.smoke, rng); d2 = load_d1(b, args.smoke, rng)
        m = d1.merge(d2, on="time", suffixes=("_1", "_2"))
        c1 = m["close_1"].values; c2 = m["close_2"].values; yr = m["time"].dt.year.values
        s = np.log(c1) - np.log(c2); pos, z = zscore_signal(s)
        cb1 = cost_bp_oneway(a, c1); cb2 = cost_bp_oneway(b, c2)
        pnl = pair_pnl(pos, c1, c2, cb1, cb2)
        obs = period_stats(yr, pnl, pos)
        null = {pn: [] for pn in obs}
        for bb in range(args.B):
            p2 = circ_shift(rng, pos, 252); st = period_stats(yr, pair_pnl(p2, c1, c2, cb1, cb2), p2)
            for pn in obs:
                if pn in st:
                    null[pn].append(st[pn]["pnl_bp"])
        for pn in obs:
            zz, pct = z_of(obs[pn]["pnl_bp"], null[pn]); obs[pn]["z"] = f(zz); obs[pn]["null_mean_bp"] = f(np.nanmean(null[pn])) if null[pn] else None
        summary[name] = {"n_days": int(len(m)), "half_life_days": f(half_life(s)), "periods": obs}
    survive = {}
    for name, v in summary.items():
        p = v["periods"]; g = lambda pn, k: (p.get(pn, {}).get(k) if p.get(pn, {}).get(k) is not None else float("nan"))
        survive[name] = bool(all(g(pn, "pnl_bp") > 0 and g(pn, "t") >= 2 and g(pn, "z") >= 2 for pn in ("pre", "post")))
    n_s = sum(survive.values())
    verdict = "支持: 2 組とも残る" if n_s == 2 else ("未確定: 1 組だけ残る（組依存）" if n_s == 1 else "棄却: どの組も残らない")
    res = {"question": "金銀比・Brent−WTI の z スコア逆張りは 2015 年以降コスト後に残るか", "settings": {"pairs": PAIRS, "win": WIN, "z_in": Z_IN, "z_out": Z_OUT, "B": args.B},
           "missing": missing, "summary": summary, "survive": survive, "machine_verdict": verdict, "multiple_comparisons": "2 組 × 2 期間 × (t, z) = 8 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
