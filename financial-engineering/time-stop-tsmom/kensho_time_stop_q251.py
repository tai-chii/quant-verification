#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q251: 時間ストップ（N 日で強制手仕舞い・再合図まで待つ）は順張りの純損益と最大下落を改善するか（15銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q251 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Kaminski・Lo 2014（損切りの理論）、知見 Q204（ATR 損切り: 純損益は上がらず最大下落は浅い）、Q253 と対（トレンドの年齢）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "time stop exit trend following systematic strategy empirical effect holding period limit"）:
  見つかったもの: LuxAlgo・TurtleTrader・Katz の解説（ブログ・書籍の抄録）。
  未確認: 根拠にしない。15 銘柄・前後半・滞在率を保つ循環シフト帰無で測る形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: TSMOM60 の建玉を同じ向きで N=20 日持ったら手仕舞い（現金）、合図が反転するまで再建玉しない規則は、最大下落を浅くするが純損益は上げない（Q204 と同じ型）。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
A: TSMOM60。B: 時間ストップ N=20（主セル）。N=10・40 は副次。手仕舞い後は合図の符号が変わった日に新しい向きで建玉。pnl_bp。

【測るもの】
年×銘柄の純損益差 B−A [bp/日]（年単位 t）、最大下落の差（年ごと・対応あり t）、市場滞在率。前後半・群別。

【帰無】
手仕舞い日の位置を保ったまま「どの日から N 日か」を年内で循環シフト（滞在率を保つ）B=300 → 差の帰無分布 → z（純損益と最大下落の 2 本）。

【判定（事前固定・変更禁止）】
all15 で前後半とも 最大下落の差<0（浅い）かつ z≤−2 かつ 純損益差の |t|<2 → 支持（Q204 と同じ型）。純損益差が前後半とも t≥2 → 「時間ストップは純損益も上げる」で別の確定。最大下落の差が全期間 z>−2 → 棄却。それ以外 → 未確定。
多重比較: 判定は all15 の最大下落の差と純損益差の前後半（4 本）。N=10・40・群別は記述。

【捨てた案の数】
約3: N を ATR で可変にする、手仕舞い後すぐ再建玉する（Q136 と同じになる）、保有日数の分布だけ見る記述案。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_time_stop_q251.py            （B=300・小（B=300・1〜2 分））
      python3 kensho_time_stop_q251.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q251"
DEFAULT_B = 300
L = 60
N_MAIN = 20
NS = (10, 20, 40)
PERIODS = (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _time_stop_pos(sigA, N):
    """A の合図 sigA を N 日持ったら手仕舞い（0）。合図の符号が変わった日に新しい向きで建玉。
    建玉中に合図が反転したら新しい向きで建玉し直す（日数は 0 から）。"""
    n = len(sigA); pos = np.zeros(n); held = 0; cur = 0.0; exited_dir = 0.0
    for t in range(n):
        s = sigA[t]
        if s == 0:
            cur = 0.0; held = 0; exited_dir = 0.0
        elif cur != 0 and s != cur:
            cur = s; held = 1
        elif cur != 0 and s == cur:
            held += 1
            if held > N:
                exited_dir = cur; cur = 0.0; held = 0
        else:  # cur == 0
            if exited_dir == 0.0 or s != exited_dir:
                cur = s; held = 1; exited_dir = 0.0
        pos[t] = cur
    return pos


def _shift_within_year(rng, x, year):
    out = x.copy()
    for y in np.unique(year):
        idx = np.where(year == y)[0]
        if len(idx) > 2:
            out[idx] = circ_shift(rng, x[idx], 1)
    return out


def _year_cells(year, sym_id, vals, nsym):
    """日次値 → 年×銘柄平均（配列: cell_year, cell_sym, cell_val）。"""
    m = np.isfinite(vals)
    key = year[m] * nsym + sym_id[m]
    s = np.bincount(key, weights=vals[m]); c = np.bincount(key); ok = c > 0
    ids = np.arange(len(c))[ok]
    return ids // nsym, ids % nsym, s[ok] / c[ok]


def _year_mean(cy, cv, y0, y1):
    m = (cy >= y0) & (cy < y1) & np.isfinite(cv)
    if not m.any():
        return float("nan")
    s = np.bincount(cy[m], weights=cv[m]); c = np.bincount(cy[m]); ok = c > 0
    return float((s[ok] / c[ok]).mean())


def _mdd_cells(year, sym_id, pnl, nsym):
    """年×銘柄の最大下落の深さ（その年の中で・正の値。差<0 が「浅い」）。"""
    out = {}
    key = year * nsym + sym_id
    order = np.argsort(key, kind="stable")
    ks = key[order]; ps = pnl[order]
    bounds = np.r_[0, np.where(np.diff(ks) != 0)[0] + 1, len(ks)]
    for i in range(len(bounds) - 1):
        out[ks[bounds[i]]] = -max_drawdown(ps[bounds[i]:bounds[i + 1]])  # 下落の深さ（正）
    return out


def run(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    per = {}
    for s in ok:
        df = load_d1(s, args.smoke, rng)
        c = df["close"].values.astype(float); cost = cost_bp_oneway(s, c)
        posA = tsmom_pos(c, L); pnlA = pnl_bp(posA, c, cost)
        d = {"year": df["year"].values.astype(int), "close": c, "cost": cost, "posA": posA, "pnlA": pnlA, "posB": {}, "pnlB": {}}
        for N in NS:
            pB = _time_stop_pos(posA, N); d["posB"][N] = pB; d["pnlB"][N] = pnl_bp(pB, c, cost)
        per[s] = d
    syms = list(per); nsym = len(syms)
    year_all = np.concatenate([per[s]["year"] for s in syms]); sym_all = np.concatenate([np.full(len(per[s]["year"]), i) for i, s in enumerate(syms)])
    pnlA_all = np.concatenate([per[s]["pnlA"] for s in syms]); posA_all = np.concatenate([per[s]["posA"] for s in syms])
    mddA = _mdd_cells(year_all, sym_all, pnlA_all, nsym)
    # 年×銘柄セル
    cy, cs, _ = _year_cells(year_all, sym_all, pnlA_all, nsym)
    celldf = pd.DataFrame({"year": cy, "sym": [syms[i] for i in cs]})
    keys = cy * nsym + cs
    celldf["pnlA"] = _year_cells(year_all, sym_all, pnlA_all, nsym)[2]
    celldf["mddA"] = [mddA[k] for k in keys]
    for N in NS:
        pnlB_all = np.concatenate([per[s]["pnlB"][N] for s in syms]); posB_all = np.concatenate([per[s]["posB"][N] for s in syms])
        celldf[f"diff_{N}"] = _year_cells(year_all, sym_all, pnlB_all - pnlA_all, nsym)[2]
        mddB = _mdd_cells(year_all, sym_all, pnlB_all, nsym)
        celldf[f"mdd_diff_{N}"] = [mddB[k] - mddA[k] for k in keys]
        celldf[f"in_market_{N}"] = _year_cells(year_all, sym_all, (posB_all != 0).astype(float), nsym)[2]
        celldf["in_market_A"] = _year_cells(year_all, sym_all, (posA_all != 0).astype(float), nsym)[2]

    def stats_of(pnl_diff_all, mdd_cells_B):
        cy2, cs2, cv = _year_cells(year_all, sym_all, pnl_diff_all, nsym)
        k2 = cy2 * nsym + cs2
        md = np.array([mdd_cells_B[k] - mddA[k] for k in k2])
        return {pn: (_year_mean(cy2, cv, y0, y1), _year_mean(cy2, md, y0, y1)) for pn, y0, y1 in PERIODS}

    pnlB_main = np.concatenate([per[s]["pnlB"][N_MAIN] for s in syms])
    obs = stats_of(pnlB_main - pnlA_all, _mdd_cells(year_all, sym_all, pnlB_main, nsym))
    # 帰無: 手仕舞い（現金）の日の位置を年内で循環シフト（滞在率を保つ）
    null_pnl = {pn: [] for pn, _, _ in PERIODS}; null_mdd = {pn: [] for pn, _, _ in PERIODS}
    for b in range(args.B):
        pnlN = []
        for s in syms:
            d = per[s]
            flat = ((d["posB"][N_MAIN] == 0) & (d["posA"] != 0)).astype(float)
            fl = _shift_within_year(rng, flat, d["year"]) > 0.5
            pN = np.where(fl, 0.0, d["posA"])
            pnlN.append(pnl_bp(pN, d["close"], d["cost"]))
        pnlN = np.concatenate(pnlN)
        st = stats_of(pnlN - pnlA_all, _mdd_cells(year_all, sym_all, pnlN, nsym))
        for pn in st:
            null_pnl[pn].append(st[pn][0]); null_mdd[pn].append(st[pn][1])
    summary = {}
    for N in NS:
        summary[f"N_{N}"] = {}
        for g, gs in GROUPS.items():
            gd = celldf[celldf["sym"].isin(gs)]
            summary[f"N_{N}"][g] = {}
            for pn, y0, y1 in PERIODS:
                st = by_year_stats(gd, f"diff_{N}", y0=y0, y1=y1); sm = by_year_stats(gd, f"mdd_diff_{N}", y0=y0, y1=y1)
                sub = gd[(gd["year"] >= y0) & (gd["year"] < y1)]
                ent = {"n_years": st["n_years"], "pnl_diff_bp": f(st["mean"]), "pnl_t": f(st["t"]),
                       "mdd_diff_bp": f(sm["mean"]), "mdd_t": f(sm["t"]),
                       "in_market_B": f(sub[f"in_market_{N}"].mean()), "in_market_A": f(sub["in_market_A"].mean())}
                if N == N_MAIN and g == "all15":
                    z1, p1 = z_of(obs[pn][0], null_pnl[pn]); z2, p2 = z_of(obs[pn][1], null_mdd[pn])
                    ent.update({"pnl_z": f(z1), "pnl_pct": f(p1), "mdd_z": f(z2), "mdd_pct": f(p2)})
                summary[f"N_{N}"][g][pn] = ent
    a = summary[f"N_{N_MAIN}"]["all15"]
    need = [a[pn][k] for pn in ("all", "pre", "post") for k in ("pnl_t", "mdd_diff_bp", "mdd_z")]
    if any(v is None for v in need):
        verdict = "未確定: 計算できない"
    elif all(a[pn]["mdd_diff_bp"] < 0 and a[pn]["mdd_z"] <= -2 and abs(a[pn]["pnl_t"]) < 2 for pn in ("pre", "post")):
        verdict = "支持: 時間ストップは最大下落を浅くするが純損益は上げない（Q204 と同じ型）"
    elif all(a[pn]["pnl_t"] >= 2 for pn in ("pre", "post")):
        verdict = "別の確定: 時間ストップは純損益も上げる（前後半とも t≥2）"
    elif a["all"]["mdd_z"] > -2:
        verdict = "棄却: 最大下落の差が全期間 z>−2"
    else:
        verdict = "未確定"
    res = {"question": "時間ストップ（N=20 日で手仕舞い・再合図まで待つ）は TSMOM60 の純損益と最大下落を改善するか",
           "settings": {"L": L, "N_main": N_MAIN, "Ns": list(NS), "split_year": SPLIT_YEAR, "B": args.B,
                        "null": "現金の日（B=0 かつ A≠0）の位置を年内で循環シフトし A の建玉に当てる（滞在率を保つ）",
                        "stat_for_z": "純損益差・最大下落差（年×銘柄）を年内で銘柄平均→年平均",
                        "mdd_unit": "年×銘柄の中の最大下落の深さ [bp]（正の値・差<0 が浅い）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の最大下落の差と純損益差の前後半（4 本）。N=10・40・群別は記述。"}
    return res, {"cells": celldf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
