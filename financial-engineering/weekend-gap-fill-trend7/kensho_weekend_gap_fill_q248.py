#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q248: トレンド群（金・銀・原油 2・株価指数 2）の週末の窓は週内に埋まるか（Dao 2016 の FX 以外への条件の穴）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q248 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- [[Dao2016-1_為替は週末の窓が大きいとその週のうちに逆向きに戻る]]・[[Dao2016-2_週末の窓の逆張りは期間外の2007年から2014年にコストと金利を引いても残る]]、
  知見 Q051（為替の週末の窓の逆張りは公表後に有意でない）、知見 Q209（夜間プレミアムは区間の長さで説明）、知見 Q212（暗号資産の週末）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "weekend gap fill probability stock index futures gold oil Monday open gap reversal empirical"）:
  Harbourfront Quant「Are weekend gaps always filled」（ブログ）、MQL5 の記事、TradingView の XAUUSD 週末ギャップ指標、UJ の論文（price gaps and volatility）。
  Dao の定義で金・銀・原油・指数の CFD を 2 期間・符号並べ替え帰無で測る形は未確認。移植（FX → 商品・指数）。

【仮説（測る前に固定）】
H: 週末の窓 g = ln(月曜の始値 / 金曜の終値) の向きと逆に、その週（月曜始値→金曜終値）のリターンが動く（戻り = −sign(g) × R_week > 0）。
   特に |g| が大きい週（中央値より上）で強い。

【データ】金・銀・原油 2・株価指数 2 の H1（Dukascopy・UTC）→ 金曜の最後の足の終値と月曜の最初の足の始値。BTC は週末も動くので除く。
期間: 金銀 2008〜、油・指数 2011-09〜2026-06。

【定義（1通りに固定）】
- 週 w: 金曜の最後の足の終値 c_F、翌週の最初の足（月曜）の始値 o_M、その週の金曜の最後の足の終値 c_F'。g = ln(o_M/c_F)、R_week = ln(c_F'/o_M) [bp]。
- 戻り rev_w = −sign(g) × R_week。埋まった = 週内（月〜金の足）の安値 ≤ c_F（g>0）または高値 ≥ c_F（g<0）。
- 条件: |g| > 当該銘柄のそれまでの |g| の中央値（拡大窓・先読みなし）。
- 純損益（記述）: rev − 往復コスト（段階1）。

【測るもの】群 6 銘柄（等加重）× 前半（<2017）／後半（≥2017）／全期間: 件数、rev の平均・年単位 t・z、埋まった割合（全部と |g| 大）。銘柄別も出す。

【帰無】g の符号を週ごとに無作為に付け替える（|g| の分布と R_week は保つ）B=2000 → rev の平均の帰無分布 → z。

【判定（事前固定・変更禁止）】
- 群で前半・後半とも |g| 大の rev > 0 かつ z ≥ 2 → 支持（週末の窓は戻る）。
- 全期間の z < 2 → 棄却。
- それ以外 → 未確定。
多重比較: 判定は |g| 大の前後半 2 本。全件・埋まった割合・銘柄別は記述。

【捨てた案の数】約4: 月曜 1 日だけの戻り、閾値を上位 1/4 にする案、金利差の控除（CFD の金利は手元にない）、FX8（Q051 で済み）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・rev と z（前後半）・埋まった割合を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_weekend_gap_fill_q248.py            （B=2000・1 分前後）
      python3 kensho_weekend_gap_fill_q248.py --smoke
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

QID = "Q248"
DEFAULT_B = 2000
SYMS6 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH"]


def weekly_table(h1, sym):
    d = h1.copy(); d["week"] = d["time"].dt.to_period("W-SUN").astype(str)  # 月曜始まりの週
    rows = []
    weeks = list(d.groupby("week"))
    for k in range(1, len(weeks)):
        prev = weeks[k - 1][1]; cur = weeks[k][1]
        if prev["dow"].iloc[-1] != 4 or cur["dow"].iloc[0] != 0:  # 金曜で終わり月曜で始まる週だけ
            continue
        cF = float(prev["close"].iloc[-1]); oM = float(cur["open"].iloc[0]); cF2 = float(cur["close"].iloc[-1])
        if cur["dow"].iloc[-1] != 4:
            continue
        g = math.log(oM / cF); R = math.log(cF2 / oM) * 1e4
        filled = bool(cur["low"].min() <= cF) if g > 0 else bool(cur["high"].max() >= cF)
        rows.append({"sym": sym, "week": weeks[k][0], "year": int(cur["time"].iloc[0].year), "g": g, "abs_g": abs(g), "R_week": R, "rev": -np.sign(g) * R, "filled": int(filled),
                     "cost_rt": float(2 * cost_bp_oneway(sym, np.array([oM]))[0])})
    t = pd.DataFrame(rows)
    if not t.empty:
        t["big"] = t["abs_g"] > t["abs_g"].expanding().median().shift(1)  # 拡大窓の中央値（先読みなし）
    return t


def stats(df):
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        d = df[(df["year"] >= y0) & (df["year"] < y1)]
        if len(d) < 30:
            continue
        big = d[d["big"] == True]
        out[pn] = {"n_weeks": int(len(d)), "n_big": int(len(big)), "rev_all_bp": f(d["rev"].mean()), "rev_big_bp": f(big["rev"].mean()) if len(big) else None,
                   "rev_big_year_t": f(by_year_stats(big, "rev")["t"]) if len(big) else None, "fill_rate_all": f(d["filled"].mean()), "fill_rate_big": f(big["filled"].mean()) if len(big) else None,
                   "net_big_bp": f((big["rev"] - big["cost_rt"]).mean()) if len(big) else None}
    return out


def run(args, rng):
    tabs = []; missing = []
    for s in SYMS6:
        if not args.smoke and not exists_sym(s, "H1_dukascopy"):
            missing.append(s); continue
        h1 = load_h1(s, args.smoke, rng, n=100000, start="2010-01-01")
        if args.smoke:  # 合成データは週末も連続なので、土日の足を落とす
            h1 = h1[h1["dow"] < 5].reset_index(drop=True)
        tabs.append(weekly_table(h1, s))
    df = pd.concat(tabs, ignore_index=True)
    obs = stats(df); null = {pn: [] for pn in obs}
    for b in range(args.B):
        d2 = df.copy(); sgn = rng.choice([-1.0, 1.0], size=len(d2)); d2["rev"] = -sgn * d2["R_week"].values
        st = stats(d2)
        for pn in obs:
            if pn in st:
                null[pn].append(st[pn]["rev_big_bp"] if st[pn]["rev_big_bp"] is not None else np.nan)
        if b % 500 == 0:
            print("null", b)
    summary = {}
    for pn, v in obs.items():
        z, _ = z_of(v["rev_big_bp"] if v["rev_big_bp"] is not None else np.nan, null[pn]); summary[pn] = {**v, "rev_big_z": f(z)}
    per_sym = {s: stats(d).get("all") for s, d in df.groupby("sym")}
    g = lambda p, k: (summary.get(p, {}).get(k) if summary.get(p, {}).get(k) is not None else float("nan"))
    if all(g(p, "rev_big_bp") > 0 and g(p, "rev_big_z") >= 2 for p in ("pre", "post")):
        verdict = "支持: 大きな週末の窓は週内に戻る"
    elif g("all", "rev_big_z") < 2:
        verdict = "棄却: 全期間の z < 2"
    else:
        verdict = "未確定"
    res = {"question": "トレンド群の週末の窓は週内に埋まるか", "settings": {"syms": SYMS6, "B": args.B}, "missing": missing, "summary": summary, "per_sym": per_sym,
           "machine_verdict": verdict, "multiple_comparisons": "判定は |g| 大の前後半 z 2 本。"}
    return res, {"weeks": df}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
