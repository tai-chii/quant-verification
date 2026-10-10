#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q249: 順張りの合図強度（|ret_L|/σ）の3分位で翌日の純損益は単調に増えるか（15銘柄・sign と強度の対比）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q249 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Moskowitz・Ooi・Pedersen 2012（JFE・符号の合図）、Baltas・Kosowski 2020（連続の合図）、知見 Q136（TSMOM60 の基準）・Q205（σ60 の規模調整）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "time series momentum signal strength volatility scaled continuous signal versus sign monotonic returns"）:
  見つかったもの: Baltas・Kosowski 2020／WisdomTree・QuantConnect の商品先物の改良型（ブログ）。
  未確認: 15 銘柄・前後半・年内並べ替え帰無で強さの3分位の単調性を事前固定で測る形は未確認（追試＋条件の穴）。

【仮説（測る前に固定）】
H: 合図の強さ s=|ln(C_t/C_{t−60})|/(σ60·√60) を各銘柄の拡大窓の3分位（T1 弱・T2 中・T3 強）に分けると、翌日の順張り純損益 [bp] は T1<T2<T3 と単調で、T3−T1>0。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。往復コストは段階1の表。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
合図: TSMOM60 の符号。強さ s: 上の式。3分位の境界は各銘柄で t 日までの拡大窓（最短 250 日）の 1/3・2/3 分位（先読みなし）。純損益 pnl_bp（翌日の終値で約定・片道コスト）。

【測るもの】
年×銘柄で T3−T1 の純損益差 [bp/日]（年単位 t・all15/fx8/trend7）。T1<T2<T3 の単調が成り立つ年×銘柄の割合。前半 2008–2016／後半 2017–。

【帰無】
強さの3分位ラベルを年内で並べ替え（perm_within・年×銘柄）B=500 → T3−T1 の帰無分布 → z。

【判定（事前固定・変更禁止）】
all15 で前半・後半とも T3−T1>0 かつ t≥2 かつ z≥2 → 支持。全期間で t<0 または全期間 z<1 → 棄却。それ以外 → 未確定。
多重比較: 判定は all15 の T3−T1 の前後半 2 本。fx8/trend7・単調割合は記述。

【捨てた案の数】
約3: tanh(s) で連続規模にする案（Q205 と混ざる）、5 分位（年×銘柄あたりの日数が薄い）、参照日数 20 と 120 の同時（1 本に固定）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_signal_strength_q249.py            （B=500・小（B=500・1 分前後））
      python3 kensho_signal_strength_q249.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q249"
DEFAULT_B = 500
L = 60
MIN_WIN = 250
PERIODS = (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _year_mean_of_cells(cell_year, cell_val, y0, y1):
    """年×銘柄セルの値 → 年内で銘柄平均 → 年平均。"""
    m = (cell_year >= y0) & (cell_year < y1) & np.isfinite(cell_val)
    if not m.any():
        return float("nan")
    s = np.bincount(cell_year[m], weights=cell_val[m]); c = np.bincount(cell_year[m])
    ok = c > 0
    return float((s[ok] / c[ok]).mean())


def _cell_tercile_means(cell, lab, pnl, ncell):
    key = cell * 3 + lab
    s = np.bincount(key, weights=pnl, minlength=ncell * 3).reshape(ncell, 3)
    c = np.bincount(key, minlength=ncell * 3).reshape(ncell, 3)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / np.maximum(c, 1), np.nan)


def build(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    rows = []
    for s in ok:
        df = load_d1(s, args.smoke, rng)
        c = df["close"].values.astype(float)
        lr = np.r_[np.nan, np.diff(np.log(c))]
        sig60 = pd.Series(lr).rolling(L).std(ddof=1).values
        m = np.full(len(c), np.nan); m[L:] = np.log(c[L:] / c[:-L])
        strength = np.abs(m) / (sig60 * math.sqrt(L))
        pos = tsmom_pos(c, L)
        pnl = pnl_bp(pos, c, cost_bp_oneway(s, c))
        st = pd.Series(strength)
        q1 = st.expanding(MIN_WIN).quantile(1 / 3).values
        q2 = st.expanding(MIN_WIN).quantile(2 / 3).values
        lab = np.full(len(c), -1)
        valid = np.isfinite(strength) & np.isfinite(q1) & np.isfinite(q2) & (pos != 0)
        lab[valid & (strength <= q1)] = 0
        lab[valid & (strength > q1) & (strength <= q2)] = 1
        lab[valid & (strength > q2)] = 2
        # 日 t の合図/強度 → 日 t+1 の純損益
        d = pd.DataFrame({"time": df["time"].values[1:], "year": df["year"].values[1:], "sym": s,
                          "lab": lab[:-1], "pnl": pnl[1:], "strength": strength[:-1]})
        rows.append(d[d["lab"] >= 0])
    data = pd.concat(rows, ignore_index=True)
    return data, missing


def run(args, rng):
    data, missing = build(args, rng)
    data["cell"] = data["year"].astype(str) + "_" + data["sym"]
    cells = pd.Index(data["cell"].unique())
    cell_id = cells.get_indexer(data["cell"].values)
    ncell = len(cells)
    cell_year = np.array([int(x.split("_")[0]) for x in cells]); cell_sym = np.array([x.split("_")[1] for x in cells])
    lab = data["lab"].values.astype(int); pnl = data["pnl"].values.astype(float)
    tm = _cell_tercile_means(cell_id, lab, pnl, ncell)
    D = tm[:, 2] - tm[:, 0]
    mono = (tm[:, 0] < tm[:, 1]) & (tm[:, 1] < tm[:, 2])
    celldf = pd.DataFrame({"year": cell_year, "sym": cell_sym, "T1": tm[:, 0], "T2": tm[:, 1], "T3": tm[:, 2], "D": D, "mono": mono.astype(float)})
    # 帰無: 強度ラベルを年×銘柄の中で並べ替え
    null = {pn: [] for pn, _, _ in PERIODS}
    for b in range(args.B):
        lab_p = perm_within(rng, lab, cell_id).astype(int)
        tmp = _cell_tercile_means(cell_id, lab_p, pnl, ncell)
        Dp = tmp[:, 2] - tmp[:, 0]
        for pn, y0, y1 in PERIODS:
            null[pn].append(_year_mean_of_cells(cell_year, Dp, y0, y1))
    summary = {}
    for g, syms in GROUPS.items():
        gd = celldf[celldf["sym"].isin(syms)]
        summary[g] = {}
        for pn, y0, y1 in PERIODS:
            st = by_year_stats(gd, "D", y0=y0, y1=y1)
            sub = gd[(gd["year"] >= y0) & (gd["year"] < y1)]
            ent = {"n_years": st["n_years"], "n_cells": int(len(sub)), "D_T3_minus_T1_bp": f(st["mean"]), "t": f(st["t"]),
                   "T1_bp": f(sub["T1"].mean()), "T2_bp": f(sub["T2"].mean()), "T3_bp": f(sub["T3"].mean()),
                   "mono_frac": f(sub["mono"].mean())}
            if g == "all15":
                obs = _year_mean_of_cells(cell_year, D, y0, y1)
                z, pct = z_of(obs, null[pn])
                ent.update({"z": f(z), "pct": f(pct)})
            summary[g][pn] = ent
    a = summary["all15"]
    def ok_(pn):
        e = a[pn]
        return e["D_T3_minus_T1_bp"] is not None and e["t"] is not None and e["z"] is not None and e["D_T3_minus_T1_bp"] > 0 and e["t"] >= 2 and e["z"] >= 2
    if any(a[pn][k] is None for pn in ("all", "pre", "post") for k in ("t", "z")):
        verdict = "未確定: 計算できない"
    elif ok_("pre") and ok_("post"):
        verdict = "支持: 合図の強い3分位ほど翌日の順張り純損益が高い（前後半とも T3−T1>0・t≥2・z≥2）"
    elif a["all"]["t"] < 0 or a["all"]["z"] < 1:
        verdict = "棄却: 全期間で t<0 または z<1"
    else:
        verdict = "未確定"
    res = {"question": "順張りの合図強度（|ret_60|/σ）の3分位で翌日の純損益は単調に増えるか（T3−T1>0）",
           "settings": {"L": L, "min_window": MIN_WIN, "split_year": SPLIT_YEAR, "B": args.B, "null": "強度ラベルを年×銘柄内で並べ替え（perm_within）",
                        "stat_for_z": "年×銘柄の T3−T1 を年内で銘柄平均し年平均したもの"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の T3−T1 の前後半 2 本。fx8/trend7・単調割合は記述。"}
    return res, {"cells": celldf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
