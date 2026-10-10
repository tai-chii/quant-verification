#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q207: 危機アルファ — US500 の最悪 1 割の月に 15 銘柄の順張りは正の損益か、束の相関はその月に上がるか（Hurst・Ooi・Pedersen 2017 の型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Hurst, Ooi, Pedersen (2017) "A Century of Evidence on Trend-Following Investing" J. Portfolio Management 44(1) — 株式の最悪の下落局面
  （10 件）でトレンドフォローは平均して正の収益（表 3「crisis alpha」）。Moskowitz・Ooi・Pedersen (2012) 図 4 の「TSMOM スマイル」。
  関連知見: Q097・Q151（順張りの下落の軽さはタイミング）、Q141（悪い時期重視の目的関数）。
  → 本案は手元の 15 銘柄・2011 年以降（US500 の H1 が 2011-09 から）で、株の最悪 1 割の月に順張りの損益が正か、と束の分散効果がその月に消えるかを測る。

【仮説（測る前に固定）】
H1a: US500 の月次リターンが下位 1 割の月で、15 銘柄等加重の順張り（TSMOM 252）の月次純損益の平均は正（t ≥ 2）で、残りの月より高い（帰無 z ≥ 2）。
H1b: その月の 15 戦略の日次損益の平均ペア相関は、残りの月より高い（分散効果が落ちる）。
H0: 差は 0 と区別できない。

【データ】15 銘柄 D1_fromH1 と US500 D1_fromH1（2011-10〜2026-06、約 177 か月）。期間が短いので判定は全期間、前後半（<2017／≥2017）は記述。

【定義（1 通りに固定）】
- 合図: TSMOM L=252。純損益は共通 pnl_bp。日次の 15 銘柄等加重（その日に合図がある銘柄の平均）→ 月次合計 [bp]。
- 危機月: US500 の月次リターン（月末終値）の下位 10%（約 18 か月）。
- H1b: 各月の 15 戦略の日次損益の相関行列の非対角平均。
- 帰無: 月ラベル（危機／非危機）を並べ替え B 回 → 「危機 − 非危機」の z（H1a・H1b とも）。副次: L=120・60 は記述。

【測るもの】危機月の平均損益と t、危機 − 非危機の差と z、平均ペア相関の差と z、US500 の同じ月の平均リターン、順張りスマイル（US500 月次リターン 5 分位ごとの平均損益）。

【判定（事前固定・変更禁止）】
全期間で、危機月の平均純損益 > 0 かつ t ≥ 2 かつ 差の z ≥ 2 → H1a 支持（危機アルファあり）。危機月の平均純損益 ≤ 0 → 棄却。それ以外は未確定。
H1b は差の z ≥ 2 で「相関上昇あり」と記述（判定本数に数えない）。

【捨てた案の数】約 4: 日次の下位 1% の日（1 日では順張りの効き方が測れない）、US500 以外の基準（XAUUSD・ドル）、下落の「速さ」での分類（Q098 と重なる）、VIX（データなし）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・危機月の平均損益と t・差の z・Hurst 2017 表 3 の該当値を返す。

【実装】自己完結。実行: python3 kensho_crisis_alpha_q207.py（B=1000、1 分以内）／--B 100／--smoke
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

QID = "Q207"
DEFAULT_B = 1000
LS = [252, 120, 60]
Q_CRISIS = 0.10


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    daily = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c)
        d = pd.DataFrame({"time": df["time"].values})
        for L in LS:
            d[f"L{L}"] = pnl_bp(tsmom_pos(c, L), c, cb)
            d.loc[: L, f"L{L}"] = np.nan
        daily[s] = d.set_index("time")
    us = load_d1("US500", args.smoke, rng).set_index("time")["close"]
    m_us = us.resample("ME").last().pct_change().dropna()
    m_us = m_us[m_us.index >= "2011-10-01"] if not args.smoke else m_us
    start = m_us.index.min() - pd.offsets.MonthBegin(1)
    panel = {L: pd.concat({s: daily[s][f"L{L}"] for s in syms}, axis=1) for L in LS}
    panel = {L: p[p.index >= start] for L, p in panel.items()}
    port = {L: panel[L].mean(axis=1, skipna=True) for L in LS}
    monthly = pd.DataFrame({f"L{L}": port[L].resample("ME").sum(min_count=5) for L in LS})
    monthly["us500"] = m_us
    monthly = monthly.dropna()
    thr = monthly["us500"].quantile(Q_CRISIS)
    crisis = (monthly["us500"] <= thr).values
    # 相関: 月ごとの非対角平均
    corr = []
    for mend in monthly.index:
        p = panel[252][(panel[252].index > mend - pd.offsets.MonthEnd(1)) & (panel[252].index <= mend)].dropna(axis=1, how="all")
        if p.shape[1] >= 5 and len(p) >= 10:
            cm = p.corr().values; k = cm.shape[0]; corr.append(float((cm.sum() - np.trace(cm)) / (k * (k - 1))))
        else:
            corr.append(np.nan)
    monthly["corr"] = corr

    def stats(cr):
        out = {}
        for L in LS:
            x = monthly[f"L{L}"].values
            out[f"L{L}"] = {"crisis_mean_bp": float(np.nanmean(x[cr])), "crisis_t": tstat(x[cr]), "n_crisis": int(cr.sum()),
                            "rest_mean_bp": float(np.nanmean(x[~cr])), "diff_bp": float(np.nanmean(x[cr]) - np.nanmean(x[~cr]))}
        cc = monthly["corr"].values
        out["corr"] = {"crisis": float(np.nanmean(cc[cr])), "rest": float(np.nanmean(cc[~cr])), "diff": float(np.nanmean(cc[cr]) - np.nanmean(cc[~cr]))}
        return out
    obs = stats(crisis)
    null = {f"L{L}": [] for L in LS}; null["corr"] = []
    for b in range(args.B):
        cr = rng.permutation(crisis); st = stats(cr)
        for L in LS:
            null[f"L{L}"].append(st[f"L{L}"]["diff_bp"])
        null["corr"].append(st["corr"]["diff"])
    summary = {}
    for L in LS:
        v = obs[f"L{L}"]; z, _ = z_of(v["diff_bp"], null[f"L{L}"]); summary[f"L{L}"] = {**{k: f(x) if isinstance(x, float) else x for k, x in v.items()}, "diff_z": f(z)}
    zc, _ = z_of(obs["corr"]["diff"], null["corr"]); summary["corr"] = {**{k: f(x) for k, x in obs["corr"].items()}, "diff_z": f(zc)}
    # スマイル（5 分位）と前後半（記述）
    q = pd.qcut(monthly["us500"], 5, labels=False)
    smile = {f"q{i + 1}": {"us500_mean": f(monthly["us500"][q == i].mean()), "L252_mean_bp": f(monthly["L252"][q == i].mean())} for i in range(5)}
    halves = {}
    for pn, m in (("pre", monthly.index.year < SPLIT_YEAR), ("post", monthly.index.year >= SPLIT_YEAR)):
        cr = crisis & m; rs = (~crisis) & m
        halves[pn] = {"n_crisis": int(cr.sum()), "crisis_mean_bp": f(monthly["L252"].values[cr].mean() if cr.sum() else np.nan), "rest_mean_bp": f(monthly["L252"].values[rs].mean() if rs.sum() else np.nan)}
    v = summary["L252"]
    if (v["crisis_mean_bp"] or 0) > 0 and (v["crisis_t"] or 0) >= 2 and (v["diff_z"] or 0) >= 2:
        verdict = "支持: 危機月に順張りは正の損益（危機アルファあり）"
    elif (v["crisis_mean_bp"] or 0) <= 0:
        verdict = "棄却: 危機月の平均純損益 ≤ 0"
    else:
        verdict = "未確定"
    res = {"question": "US500 の最悪 1 割の月に順張りは正の損益か・束の相関は上がるか", "settings": {"L": LS, "q_crisis": Q_CRISIS, "B": args.B, "threshold_us500": f(thr)},
           "missing": missing, "n_months": int(len(monthly)), "summary": summary, "smile_L252": smile, "halves_L252": halves, "machine_verdict": verdict,
           "multiple_comparisons": "判定は L=252 の全期間 3 本（平均>0・t・z）。L=120/60・相関・スマイル・前後半は記述。"}
    return res, {"monthly": monthly.reset_index()}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
