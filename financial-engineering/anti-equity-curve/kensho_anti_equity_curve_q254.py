#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q254: 逆エクイティカーブ（直近20日損益が負なら規模1.5）は Q210 の負の自己相関を利益に変えるか（15銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q254 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- 知見 Q210（直近 20 日損益の符号で 1.5-0.5 に切り替えてもシャープは上がらず PnL は 20 日ブロックで負の自己相関）、LuxAlgo「Equity-curve-based Throttling」（解説）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "anti-equity curve trading negative autocorrelation strategy returns increase size after losses trend following"）:
  見つかったもの: LuxAlgo の解説、Quantpedia「Designing Robust Trend-Following System」、arXiv 2606.29591（株の反発）。
  未確認: 根拠にしない（ブログ中心）。Q210 の連鎖として 15 銘柄・前後半・20 日ブロック帰無で測る形は未確認（連鎖）。

【仮説（測る前に固定）】
H: Q210 の負の自己相関が本物なら、直近 20 日の純損益が負のとき規模 1.5・正のとき 0.5 にする逆エクイティカーブは、固定規模 1.0 より年ごとのシャープが高い。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
A: TSMOM60 固定規模。B: 逆エクイティカーブ（直近 20 日の純損益の和が負 → 1.5、正 → 0.5。規模はその日の終値で決め翌日に効く）。pnl_bp を規模倍（コストも倍）。

【測るもの】
年×銘柄のシャープの差 B−A（対応あり・年単位 t）、純損益差、最大下落の差。前後半・群別。

【帰無】
直近 20 日損益の符号ラベルを 20 日ブロックで年内並べ替え B=300 → シャープ差の帰無分布 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも シャープ差>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定（順エクイティカーブの側）。それ以外 → 棄却（Q210 の負の自己相関は利益にできない）。
多重比較: 判定は all15 のシャープ差の前後半 2 本。純損益・最大下落・群別は記述。

【捨てた案の数】
約3: 窓 60 日（Q210 は 20 日）、束の損益で規模を決める（銘柄別に固定）、規模 2.0-0。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_anti_equity_curve_q254.py            （B=300・小（B=300・1 分前後））
      python3 kensho_anti_equity_curve_q254.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q254"
DEFAULT_B = 300
L = 60
W = 20          # 直近 20 日の純損益
HI, LO = 1.5, 0.5
PERIODS = (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _scale_from_label(lab):
    """lab: +1（直近損益>0）→ 0.5、−1（<0）→ 1.5、0（定義なし/ちょうど0）→ 1.0。"""
    return np.where(lab < 0, HI, np.where(lab > 0, LO, 1.0))


def _block_perm_within_year(rng, x, year, block):
    out = x.copy()
    for y in np.unique(year):
        idx = np.where(year == y)[0]
        out[idx] = block_perm(rng, x[idx], block)
    return out


def _cell_sharpe_diff(year, sym_id, pnlA, pnlB, nsym):
    """年×銘柄のシャープ（日次 mean/std·√252）の差 B−A と、年×銘柄 id。"""
    key = year * nsym + sym_id
    c = np.bincount(key); ok = c > 1
    def sh(p):
        s = np.bincount(key, weights=p); s2 = np.bincount(key, weights=p * p)
        n = np.maximum(c, 1); mu = s / n; var = (s2 / n - mu ** 2) * n / np.maximum(n - 1, 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(ok & (var > 0), mu / np.sqrt(np.maximum(var, 1e-300)) * math.sqrt(252), np.nan)
    ids = np.arange(len(c))[ok]
    return ids // nsym, ids % nsym, (sh(pnlB) - sh(pnlA))[ok]


def _year_mean(cy, cv, y0, y1):
    m = (cy >= y0) & (cy < y1) & np.isfinite(cv)
    if not m.any():
        return float("nan")
    s = np.bincount(cy[m], weights=cv[m]); c = np.bincount(cy[m]); ok = c > 0
    return float((s[ok] / c[ok]).mean())


def run(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    per = {}
    for s in ok:
        df = load_d1(s, args.smoke, rng)
        c = df["close"].values.astype(float)
        posA = tsmom_pos(c, L); pnlA = pnl_bp(posA, c, cost_bp_oneway(s, c))
        roll = pd.Series(pnlA).rolling(W).sum().values
        lab = np.where(np.isfinite(roll), np.sign(roll), 0.0)   # 日 t の終値で決める
        scale_held = np.r_[1.0, _scale_from_label(lab)[:-1]]   # 翌日に効く
        pnlB = scale_held * pnlA                                 # 規模倍（コストも倍）
        per[s] = {"year": df["year"].values.astype(int), "pnlA": pnlA, "pnlB": pnlB, "lab": lab, "posA": posA}
    syms = list(per); nsym = len(syms)
    year_all = np.concatenate([per[s]["year"] for s in syms]); sym_all = np.concatenate([np.full(len(per[s]["year"]), i) for i, s in enumerate(syms)])
    pnlA_all = np.concatenate([per[s]["pnlA"] for s in syms]); pnlB_all = np.concatenate([per[s]["pnlB"] for s in syms])
    cy, cs, sd = _cell_sharpe_diff(year_all, sym_all, pnlA_all, pnlB_all, nsym)
    celldf = pd.DataFrame({"year": cy, "sym": [syms[i] for i in cs], "sharpe_diff": sd})
    key = year_all * nsym + sym_all; cnt = np.bincount(key); ids = cy * nsym + cs
    celldf["pnl_diff_bp"] = (np.bincount(key, weights=pnlB_all - pnlA_all) / np.maximum(cnt, 1))[ids]
    mdd = {}
    order = np.argsort(key, kind="stable"); ks = key[order]
    bounds = np.r_[0, np.where(np.diff(ks) != 0)[0] + 1, len(ks)]
    for i in range(len(bounds) - 1):
        sl = order[bounds[i]:bounds[i + 1]]
        mdd[ks[bounds[i]]] = (-max_drawdown(pnlB_all[sl])) - (-max_drawdown(pnlA_all[sl]))
    celldf["mdd_depth_diff_bp"] = [mdd[k] for k in ids]
    celldf["frac_scale_hi"] = (np.bincount(key, weights=np.concatenate([(per[s]["lab"] < 0).astype(float) for s in syms])) / np.maximum(cnt, 1))[ids]
    obs = {pn: _year_mean(cy, sd, y0, y1) for pn, y0, y1 in PERIODS}
    # 帰無: 直近 20 日損益の符号ラベルを 20 日ブロックで年内並べ替え
    null = {pn: [] for pn, _, _ in PERIODS}
    for b in range(args.B):
        pnlN = []
        for s in syms:
            d = per[s]
            lp = _block_perm_within_year(rng, d["lab"], d["year"], W)
            pnlN.append(np.r_[1.0, _scale_from_label(lp)[:-1]] * d["pnlA"])
        _, _, sdn = _cell_sharpe_diff(year_all, sym_all, pnlA_all, np.concatenate(pnlN), nsym)
        for pn, y0, y1 in PERIODS:
            null[pn].append(_year_mean(cy, sdn, y0, y1))
    summary = {}
    for g, gs in GROUPS.items():
        gd = celldf[celldf["sym"].isin(gs)]
        summary[g] = {}
        for pn, y0, y1 in PERIODS:
            st = by_year_stats(gd, "sharpe_diff", y0=y0, y1=y1); sp = by_year_stats(gd, "pnl_diff_bp", y0=y0, y1=y1); sm = by_year_stats(gd, "mdd_depth_diff_bp", y0=y0, y1=y1)
            sub = gd[(gd["year"] >= y0) & (gd["year"] < y1)]
            ent = {"n_years": st["n_years"], "sharpe_diff": f(st["mean"]), "t": f(st["t"]),
                   "pnl_diff_bp": f(sp["mean"]), "pnl_t": f(sp["t"]), "mdd_depth_diff_bp": f(sm["mean"]), "mdd_t": f(sm["t"]),
                   "frac_days_scale_1.5": f(sub["frac_scale_hi"].mean())}
            if g == "all15":
                z, pct = z_of(obs[pn], null[pn]); ent.update({"z": f(z), "pct": f(pct)})
            summary[g][pn] = ent
    a = summary["all15"]
    if any(a[pn][k] is None for pn in ("pre", "post") for k in ("sharpe_diff", "t", "z")):
        verdict = "未確定: 計算できない"
    elif all(a[pn]["sharpe_diff"] > 0 and a[pn]["t"] >= 2 and a[pn]["z"] >= 2 for pn in ("pre", "post")):
        verdict = "支持: 逆エクイティカーブは年ごとのシャープを上げる（前後半とも 差>0・t≥2・z≥2）"
    elif all(a[pn]["t"] <= -2 for pn in ("pre", "post")):
        verdict = "逆向きで確定: 順エクイティカーブの側（前後半とも t≤−2）"
    else:
        verdict = "棄却: Q210 の負の自己相関は利益にできない"
    res = {"question": "逆エクイティカーブ（直近 20 日純損益が負→規模 1.5・正→0.5）は固定規模より年ごとのシャープが高いか",
           "settings": {"L": L, "window": W, "scale_hi": HI, "scale_lo": LO, "split_year": SPLIT_YEAR, "B": args.B,
                        "pnlB": "scale[t−1]·pnlA[t]（規模はその日の終値で決め翌日に効く・コストも倍）",
                        "null": "直近 20 日損益の符号ラベルを 20 日ブロックで年内並べ替え → 規模を再構成",
                        "stat_for_z": "年×銘柄のシャープ差を年内で銘柄平均→年平均",
                        "mdd_unit": "年×銘柄の中の最大下落の深さ [bp]（正・差<0 が浅い）"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 のシャープ差の前後半 2 本。純損益・最大下落・群別は記述。"}
    return res, {"cells": celldf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
