#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q246: ADX(14) > 25 の局面に限ると、順張りの純損益は上がるか（15 銘柄・月ブロック並べ替え帰無）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q246 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Wilder (1978) "New Concepts in Technical Trading Systems"（ADX の原典・本文未読）。知見 Q142（高ボラ局面では順張りは変わらない）、
  知見 Q182（複数指標の一致は的中率を上げない）、知見 Q221（確認フィルタは純損益を上げない）、知見 Q136（トレンド持続時間と損益は無関係）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "ADX filter trend following backtest ADX above 25 improves performance empirical multi-asset"）:
  LiberatedStockTrader・oxfordstrat・MQL5 のバックテスト記事。15 銘柄・前後半・局面ラベルの月ブロック並べ替え帰無・コスト込みで
  事前固定の判定をする形は未確認。条件の穴（ブログは根拠にしない）。

【仮説（測る前に固定）】
H: ADX(14) > 25 の日だけ順張り（TSMOM60）を持ち、それ以外は現金にすると、年ごとのシャープが無条件より高い。

【データ】15 銘柄の UTC 日足（D1_fromH1、高値・安値あり、2008〜2026-06）。

【定義（1通りに固定）】
- ADX(14): Wilder の平滑化（+DM・−DM・TR の 14 日 Wilder 平均 → DI → DX → ADX の 14 日 Wilder 平均）。t までの値だけ。
- 無条件 A: pos = s_t。フィルタ B: pos = s_t × 1[ADX_t > 25]。純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（段階1）。
- 年×銘柄のシャープ（√252）と純損益（bp/日）→ 年の平均 → B − A の対応ありの差と年単位の t。局面の割合（ADX>25 の日の割合）も出す。

【測るもの】群 all15・fx8・trend7 × 前半（<2017）／後半（≥2017）／全期間。

【帰無】ADX>25 のラベルを月ブロック（暦月）単位で年内に並べ替え（割合と塊は保つ）B=300 → シャープの差の帰無分布 → z。

【判定（事前固定・変更禁止）】
- all15 で前半・後半とも シャープの差 > 0 かつ t ≥ 2 かつ z ≥ 2 → 支持。
- all15 で前半・後半とも t ≤ −2 → 逆向きで確定（ADX のフィルタは害）。
- それ以外 → 棄却（Q142・Q221 と同じ: 局面フィルタでは変わらない）。
多重比較: 判定は all15 前後半の (t, z) 4 本。純損益・群別・局面の割合は記述。

【捨てた案の数】約4: 閾値 20・30 の格子、ADX の向き（上昇中だけ）、ADX で規模を変える案（0/1 に統一）、DI の向きを合図にする案（別の規則になる）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・差の t と z（前後半）を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_adx_filter_q246.py            （B=300・1 分前後）
      python3 kensho_adx_filter_q246.py --smoke
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

QID = "Q246"
DEFAULT_B = 300
L_MOM = 60
N_ADX = 14
TH = 25.0


def wilder(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    s = np.nansum(x[:n]); out[n - 1] = s / n
    for t in range(n, len(x)):
        out[t] = (out[t - 1] * (n - 1) + x[t]) / n
    return out


def adx(high, low, close, n=N_ADX):
    h = np.asarray(high, float); l = np.asarray(low, float); c = np.asarray(close, float)
    up = np.r_[np.nan, h[1:] - h[:-1]]; dn = np.r_[np.nan, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[np.nan, c[:-1]]; tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    pdm[0] = mdm[0] = tr[0] = np.nan
    atr_ = wilder(np.nan_to_num(tr), n); pdi = 100 * wilder(np.nan_to_num(pdm), n) / atr_; mdi = 100 * wilder(np.nan_to_num(mdm), n) / atr_
    dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx[~np.isfinite(dx)] = np.nan
    out = np.full(len(c), np.nan); valid = np.where(np.isfinite(dx))[0]
    if len(valid) >= n:
        a = wilder(dx[valid], n); out[valid] = a
    return out


def summarize(cells):
    out = {}
    for g, members in GROUPS.items():
        cg = cells[cells["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
            if d.empty:
                continue
            sy = d.groupby(["year", "sym"]).agg(sh_a=("pnl_a", sharpe_ann), sh_b=("pnl_b", sharpe_ann), p_a=("pnl_a", "mean"), p_b=("pnl_b", "mean"), on=("on", "mean")).reset_index()
            yr = sy.groupby("year").mean(numeric_only=True); dd = (yr["sh_b"] - yr["sh_a"]).dropna()
            out[f"{g}_{pn}"] = {"n_years": int(len(yr)), "sharpe_base": f(yr["sh_a"].mean()), "sharpe_adx": f(yr["sh_b"].mean()), "sharpe_diff": f(dd.mean()), "sharpe_diff_t": f(tstat(dd.values)),
                                "pnl_base_bp": f(yr["p_a"].mean()), "pnl_adx_bp": f(yr["p_b"].mean()), "pnl_diff_t": f(tstat((yr["p_b"] - yr["p_a"]).values)), "share_on": f(yr["on"].mean())}
    return out


def build(store, on_override=None):
    rows = []
    for s, (yr, sig, c, cb, on, ym) in store.items():
        o = on_override[s] if on_override is not None else on
        rows.append(pd.DataFrame({"year": yr, "sym": s, "pnl_a": pnl_bp(sig, c, cb), "pnl_b": pnl_bp(sig * o, c, cb), "on": o}))
    return pd.concat(rows, ignore_index=True)


def month_block_perm(rng, on, ym, yr):
    """暦月のブロックを年内で並べ替える（ブロックの中身は保つ）。"""
    out = on.copy()
    df = pd.DataFrame({"i": np.arange(len(on)), "ym": ym, "yr": yr})
    for y, d in df.groupby("yr"):
        months = list(d.groupby("ym")["i"].apply(list)); perm = rng.permutation(len(months))
        src = np.concatenate([months[k] for k in perm]); dst = np.concatenate(months)
        n = min(len(src), len(dst)); out[dst[:n]] = on[src[:n]]
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    store = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        a = adx(df["high"].values, df["low"].values, c); on = (a > TH).astype(float)
        store[s] = (yr, tsmom_pos(c, L_MOM), c, cb, on, df["time"].dt.to_period("M").astype(str).values)
    obs = summarize(build(store)); null = {k: [] for k in obs}
    for b in range(args.B):
        ov = {s: month_block_perm(rng, v[4], v[5], v[0]) for s, v in store.items()}
        st = summarize(build(store, ov))
        for k in obs:
            if k in st:
                null[k].append(st[k]["sharpe_diff"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["sharpe_diff"] if v["sharpe_diff"] is not None else np.nan, null[k]); summary[k] = {**v, "sharpe_diff_z": f(z), "null_mean": f(np.nanmean(null[k])) if null[k] else None}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, q: (p.get(q) if p.get(q) is not None else float("nan"))
    if all(g(p, "sharpe_diff") > 0 and g(p, "sharpe_diff_t") >= 2 and g(p, "sharpe_diff_z") >= 2 for p in (pre, post)):
        verdict = "支持: ADX>25 に限るとシャープが上がる"
    elif all(g(p, "sharpe_diff_t") <= -2 for p in (pre, post)):
        verdict = "逆向きで確定: ADX のフィルタは害"
    else:
        verdict = "棄却: 局面フィルタでは変わらない（Q142・Q221 と同じ）"
    res = {"question": "ADX(14)>25 の局面に限ると順張り純損益は上がるか", "settings": {"L": L_MOM, "n_adx": N_ADX, "threshold": TH, "B": args.B}, "missing": missing,
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の (t, z) 4 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
