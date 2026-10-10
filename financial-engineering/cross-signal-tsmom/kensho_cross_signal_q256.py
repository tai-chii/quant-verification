#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q256: クロス・シグナル（金→銀・WTI→UKOIL・US500→USTECH・BTC→ETH）の日足順張りは自身の合図より良いか
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q256 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- 知見 Q236（4 組の H1 リード・ラグ）、Quantpedia「Cross-Asset Price-Based Regimes for Gold」（要旨）、Moskowitz 2012
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "cross-asset signal gold momentum signal applied to silver lead-lag trading rule daily empirical"）:
  見つかったもの: Quantpedia「Cross-Asset Price-Based Regimes for Gold」、DeFi Trading Substack の商品リード・ラグ（ブログ）。
  未確認: 4 組の日足・主の合図を従に当てる形で 2 期間・循環シフト帰無・Holm は未確認（連鎖）。

【仮説（測る前に固定）】
H: 従（銀・UKOIL・USTECH・ETH）を主（金・WTI・US500・BTC）の TSMOM60 の合図で売買するクロス順張りは、従自身の合図の順張りと純損益 [bp/日] が変わらない（主はリードしない）。差 D=クロス−自身。

【データ】
XAUUSD・XAGUSD・WTI・UKOIL・US500・USTECH D1_fromH1、BTCUSD D1_fromH1、ETHUSD は H1 → h1_to_d1（2017〜2026）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
主の合図は主の終値（同じ UTC 日）で作り、従の翌日のリターンに当てる。自身の合図は従の TSMOM60。pnl_bp（ETH のコストは CRYPTO_COST_RT_REL）。

【測るもの】
4 組それぞれ年単位の D [bp/日] と t、4 組を束ねた年単位 t。合図の一致率。前後半（BTC→ETH は 2021 で分ける）。

【帰無】
主の合図を従のリターンに対し循環シフト B=500 → D の帰無分布 → z（組ごと・Holm 4 本）。

【判定（事前固定・変更禁止）】
4 組のうち Holm 後に前後半とも D>0 かつ z≥2 の組が 1 つ以上 → 支持（その組を書く）。4 組とも全期間 |z|<2 → 棄却（主はリードしない）。それ以外 → 未確定。
多重比較: 判定は 4 組 × 前後半 = 8 本（Holm は組の 4 本）。束ねた t・一致率は記述。

【捨てた案の数】
約3: 逆向き（従→主）も同時に測る（Q236 が H1 で済み）、両方の合図の AND、参照日数 20。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_cross_signal_q256.py            （B=500・小（B=500・1 分前後））
      python3 kensho_cross_signal_q256.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q256"
DEFAULT_B = 500
L = 60
PAIRS = [("XAUUSD", "XAGUSD", SPLIT_YEAR), ("WTI", "UKOIL", SPLIT_YEAR), ("US500", "USTECH", SPLIT_YEAR), ("BTCUSD", "ETHUSD", 2021)]
ETH_START = "2017-01-01"


def _load(sym, args, rng):
    """D1_fromH1。ETHUSD は H1_dukascopy → h1_to_d1（smoke は load_d1）。無ければ None。"""
    if sym == "ETHUSD":
        if args.smoke:
            return load_d1(sym, True, rng)
        if not exists_sym(sym, "H1_dukascopy"):
            return None
        h1 = load_h1(sym, False, rng)
        d = h1_to_d1(h1)
        return d[d["time"] >= pd.Timestamp(ETH_START)].reset_index(drop=True)
    if not args.smoke and not exists_sym(sym):
        return None
    return load_d1(sym, args.smoke, rng)


def _cost(sym, close):
    return cost_bp_oneway(sym, close, rel=CRYPTO_COST_RT_REL) if sym not in COST_RT else cost_bp_oneway(sym, close)


def _year_mean(year, vals, y0, y1):
    m = (year >= y0) & (year < y1) & np.isfinite(vals)
    if not m.any():
        return float("nan")
    s = np.bincount(year[m], weights=vals[m]); c = np.bincount(year[m]); ok = c > 0
    return float((s[ok] / c[ok]).mean())


def _p_two_sided(z):
    return float(math.erfc(abs(z) / math.sqrt(2))) if np.isfinite(z) else float("nan")


def run(args, rng):
    missing = []; pair_out = {}; cell_rows = []
    for lead, lag, split in PAIRS:
        a = _load(lead, args, rng); b = _load(lag, args, rng)
        if a is None or b is None:
            missing += [s for s, d in ((lead, a), (lag, b)) if d is None]
            pair_out[f"{lead}->{lag}"] = None; continue
        j = pd.merge(a[["time", "close"]], b[["time", "close"]], on="time", suffixes=("_lead", "_lag")).reset_index(drop=True)
        cl = j["close_lead"].values.astype(float); cg = j["close_lag"].values.astype(float)
        year = j["time"].dt.year.values.astype(int)
        pos_cross = tsmom_pos(cl, L); pos_own = tsmom_pos(cg, L); cost = _cost(lag, cg)
        pnl_cross = pnl_bp(pos_cross, cg, cost); pnl_own = pnl_bp(pos_own, cg, cost)
        diff = pnl_cross - pnl_own
        periods = (("all", 0, 9999), ("pre", 0, split), ("post", split, 9999))
        obs = {pn: _year_mean(year, diff, y0, y1) for pn, y0, y1 in periods}
        null = {pn: [] for pn, _, _ in periods}
        n = len(year)
        for bb in range(args.B):
            pc = circ_shift(rng, pos_cross, 1)
            dn = pnl_bp(pc, cg, cost) - pnl_own
            for pn, y0, y1 in periods:
                null[pn].append(_year_mean(year, dn, y0, y1))
        fr = pd.DataFrame({"year": year, "diff": diff, "cross": pnl_cross, "own": pnl_own,
                           "agree": np.where((pos_cross != 0) & (pos_own != 0), (pos_cross == pos_own).astype(float), np.nan)})
        yr = fr.groupby("year").agg(n=("diff", "size"), D=("diff", "mean"), cross=("cross", "mean"), own=("own", "mean"), agree=("agree", "mean")).reset_index()
        for _, r in yr.iterrows():
            cell_rows.append({"pair": f"{lead}->{lag}", **r.to_dict()})
        out = {"split_year": split, "n_days": int(n), "first": str(j["time"].iloc[0].date()), "last": str(j["time"].iloc[-1].date())}
        for pn, y0, y1 in periods:
            st = by_year_stats(yr, "D", y0=y0, y1=y1); z, pct = z_of(obs[pn], null[pn])
            sub = yr[(yr["year"] >= y0) & (yr["year"] < y1)]
            out[pn] = {"n_years": st["n_years"], "D_bp": f(st["mean"]), "t": f(st["t"]), "z": f(z), "pct": f(pct), "p_two_sided": f(_p_two_sided(z)),
                       "cross_bp": f(sub["cross"].mean()), "own_bp": f(sub["own"].mean()), "signal_agree": f(sub["agree"].mean())}
        pair_out[f"{lead}->{lag}"] = out
    celldf = pd.DataFrame(cell_rows)
    pooled = {}
    if len(celldf):
        cd = celldf.rename(columns={"pair": "sym"})
        for pn, y0, y1 in (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999)):
            st = by_year_stats(cd, "D", y0=y0, y1=y1); pooled[pn] = {"n_years": st["n_years"], "D_bp": f(st["mean"]), "t": f(st["t"])}
    # Holm（組の 4 本・前後半それぞれ）
    valid = [k for k, v in pair_out.items() if v is not None]
    holm_out = {}
    for pn in ("pre", "post", "all"):
        ps = np.array([pair_out[k][pn]["p_two_sided"] if pair_out[k][pn]["p_two_sided"] is not None else 1.0 for k in valid])
        adj = holm(ps) if len(ps) else np.array([])
        holm_out[pn] = {k: f(v) for k, v in zip(valid, adj)}
    supported = []
    for k in valid:
        okp = all(pair_out[k][pn]["D_bp"] is not None and pair_out[k][pn]["z"] is not None and pair_out[k][pn]["D_bp"] > 0 and pair_out[k][pn]["z"] >= 2
                  and holm_out[pn][k] is not None and holm_out[pn][k] < 0.05 for pn in ("pre", "post"))
        if okp:
            supported.append(k)
    zs_all = [pair_out[k]["all"]["z"] for k in valid]
    if not valid or any(z is None for z in zs_all):
        verdict = "未確定: 計算できない"
    elif supported:
        verdict = "支持: 主の合図が従をリードする組がある（" + "・".join(supported) + "）"
    elif len(valid) == 4 and all(abs(z) < 2 for z in zs_all):
        verdict = "棄却: 主はリードしない（4 組とも全期間 |z|<2）"
    else:
        verdict = "未確定"
    res = {"question": "クロス・シグナル（主の TSMOM60 を従に当てる）は従自身の合図より純損益が良いか（D=クロス−自身）",
           "settings": {"pairs": [f"{a}->{b}" for a, b, _ in PAIRS], "L": L, "split_year_default": SPLIT_YEAR, "split_year_btc_eth": 2021, "B": args.B,
                        "eth": "H1_dukascopy → h1_to_d1（UTC 0 時区切り）、コストは CRYPTO_COST_RT_REL", "dates": "主・従の共通 UTC 日のみ",
                        "null": "主の合図を従のリターンに対し循環シフト", "stat_for_z": "年ごとの D の平均（年単位）",
                        "holm": "組の 4 本（z の両側 p）を前後半それぞれで Holm 補正、判定は補正後 p<0.05 かつ z≥2 かつ D>0"},
           "missing": missing, "summary": {"pairs": pair_out, "pooled_year_t": pooled, "holm_adj_p": holm_out, "supported_pairs": supported},
           "machine_verdict": verdict,
           "multiple_comparisons": "判定は 4 組 × 前後半 = 8 本（Holm は組の 4 本）。束ねた t・一致率は記述。"}
    return res, {"cells": celldf} if len(celldf) else None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
