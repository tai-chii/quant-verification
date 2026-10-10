#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q212: 暗号資産の週末（土日）はリターン・ボラ・順張りの損益が平日と違うか（11 通貨 H1）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Caporale & Plastun (2019) "The day of the week effect in the cryptocurrency market" Finance Research Letters 28 — BTC の月曜に異常リターン
  （表 2）、他通貨では見えない。Kinateder & Papavassiliou (2021) FRL 38 — 週末のボラは低く、週末効果は年で変わる。
  関連知見: Q152（順張りの買い側は暗号資産に偏る）、Q183（暗号資産の 1 時間足の逆張りは後半で小さくなる）。
  → 本案は 11 通貨 H1 で、週末（UTC 土日）のリターン・ボラ・順張り（24 本）の損益が平日と違うかを、曜日ラベルを日ごとに並べ替えた帰無で測る。

【仮説（測る前に固定）】
H1a: 週末の時間あたり平均リターンは平日と違う（両側。前後半で同符号・|z| ≥ 2）。
H1b: 週末の順張り（TSMOM 24 本）の粗利は平日より低い（流動性が薄く値動きが小さい）。
H0: 差は 0 と区別できない。ボラ比（週末÷平日）は記述（既知の低さの大きさだけ測る）。

【データ】11 通貨 H1_dukascopy（BTC 2017-05〜、ETH 2017-12〜、SOL 2024-03〜 など）。前半 <2022／後半 ≥2022（暗号資産用の分割）。

【定義（1 通りに固定）】
- 週末: UTC の土・日（dayofweek 5・6）の 48 本。平日: それ以外。
- 統計量: 銘柄×年のセルで「週末の平均リターン(bp/本) − 平日」「週末の TSMOM 24 の粗利(bp/本) − 平日」「sd 比」→ 年ごとに銘柄平均 → 年平均と t。
- 帰無: 曜日ラベルを「日」の単位で銘柄×年の中で並べ替え（週末の日数を保つ）B 回 → z。
- コスト: 順張りは粗利で比べる（週末の建玉の持ち越しはコストが変わらないため）。純損益は記述（往復 30bp）。

【測るもの】H1a の差と z（前後半）、H1b の差と z、sd 比、BTC 単独の同じ数値。

【判定（事前固定・変更禁止）】
H1a: 前後半とも 同符号かつ |z| ≥ 2 → 「週末のリターンに差あり」。どちらかで |z| < 2 → 棄却。
H1b: 前後半とも 差 < 0 かつ z ≤ −2 → 「週末の順張りは弱い」。どちらかで z > −2 → 棄却。（判定本数 4）

【捨てた案の数】約 4: 曜日 7 本の個別検定（多重比較。曜日効果は Q206 で株・為替）、週末明け月曜の反転、取引所別の時刻、週末のボラを判定に使う。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・H1a/H1b の z（前後半）・Caporale 2019 表 2 の値を返す。

【実装】自己完結。実行: python3 kensho_crypto_weekend_q212.py（B=300、2 分前後）／--B 30／--smoke
"""

# ============================================================================= 共通の土台（各スクリプトに同じものを埋め込む・自己完結）
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

QID = "Q212"
DEFAULT_B = 300
L_MOM = 24
SPLIT_C = 2022


def cell_stats(df, wk_col="wk"):
    g = df.groupby(["sym", "year", wk_col])
    m = g["ret_bp"].mean().unstack(wk_col); sd = g["ret_bp"].std(ddof=1).unstack(wk_col); gp = g["gross"].mean().unstack(wk_col)
    out = pd.DataFrame({"ret_diff": m.get(1) - m.get(0), "sd_ratio": sd.get(1) / sd.get(0), "mom_diff": gp.get(1) - gp.get(0)}).reset_index()
    return out


def summarize(cs):
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_C)), ("post", (SPLIT_C, 9999))):
        d = cs[(cs["year"] >= y0) & (cs["year"] < y1)]
        if d.empty:
            continue
        yr = d.drop(columns="sym").groupby("year").mean()
        out[pn] = {"n_years": int(len(yr)), "ret_diff_bp": float(yr["ret_diff"].mean()), "ret_diff_t": tstat(yr["ret_diff"].values),
                   "mom_diff_bp": float(yr["mom_diff"].mean()), "mom_diff_t": tstat(yr["mom_diff"].values), "sd_ratio": float(yr["sd_ratio"].mean())}
    return out


def run(args, rng):
    syms, missing = syms_available(CRYPTO, kind="H1_dukascopy", smoke=args.smoke)
    frames = []
    for s in syms:
        h1 = load_h1(s, args.smoke, rng, n=40000, start="2018-01-01"); c = h1["close"].values
        gross = pnl_bp(tsmom_pos(c, L_MOM), c, np.zeros(len(c)))
        d = pd.DataFrame({"sym": s, "year": h1["year"].values, "date": h1["time"].dt.floor("D").values, "wk": (h1["dow"].values >= 5).astype(int),
                          "ret_bp": h1["ret"].values * 1e4, "gross": gross}).dropna()
        frames.append(d)
    cells = pd.concat(frames, ignore_index=True)
    obs = summarize(cell_stats(cells)); obs_btc = summarize(cell_stats(cells[cells["sym"] == "BTCUSD"])) if "BTCUSD" in syms else {}
    # 日単位の並べ替え
    days = cells.drop_duplicates(["sym", "date"])[["sym", "year", "date", "wk"]].reset_index(drop=True)
    key = days["sym"].astype(str).values + days["year"].astype(str).values
    null = {pn: {"ret": [], "mom": []} for pn in obs}
    for b in range(args.B):
        days["wk_p"] = perm_within(rng, days["wk"].values.astype(float), key).astype(int)
        m = cells.merge(days[["sym", "date", "wk_p"]], on=["sym", "date"], how="left")
        st = summarize(cell_stats(m, "wk_p"))
        for pn in obs:
            if pn in st:
                null[pn]["ret"].append(st[pn]["ret_diff_bp"]); null[pn]["mom"].append(st[pn]["mom_diff_bp"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for pn, v in obs.items():
        zr, _ = z_of(v["ret_diff_bp"], null[pn]["ret"]); zm, _ = z_of(v["mom_diff_bp"], null[pn]["mom"])
        summary[pn] = {**{k: (f(x) if isinstance(x, float) else x) for k, x in v.items()}, "ret_diff_z": f(zr), "mom_diff_z": f(zm)}
    pre, post = summary.get("pre", {}), summary.get("post", {})
    g = lambda p, k: (p.get(k) or 0)
    a_ok = abs(g(pre, "ret_diff_z")) >= 2 and abs(g(post, "ret_diff_z")) >= 2 and np.sign(g(pre, "ret_diff_bp")) == np.sign(g(post, "ret_diff_bp"))
    b_ok = g(pre, "mom_diff_z") <= -2 and g(post, "mom_diff_z") <= -2 and g(pre, "mom_diff_bp") < 0 and g(post, "mom_diff_bp") < 0
    verdict = ("H1a 支持: 週末のリターンに差あり" if a_ok else "H1a 棄却") + "／" + ("H1b 支持: 週末の順張りは弱い" if b_ok else "H1b 棄却")
    res = {"question": "暗号資産の週末はリターン・ボラ・順張りの損益が平日と違うか", "settings": {"L": L_MOM, "split": SPLIT_C, "B": args.B}, "missing": missing,
           "summary": summary, "btc_only": {k: {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in obs_btc.items()},
           "machine_verdict": verdict, "multiple_comparisons": "判定は前後半 × (H1a, H1b) の 4 本。sd 比・BTC 単独は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
