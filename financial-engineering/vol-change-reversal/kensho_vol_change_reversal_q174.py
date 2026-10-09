#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q174: ボラの変化は1日逆張りの翌日リターンを予測するか（DellaCorte ほか 2015-3・15銘柄）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: DellaCorte2015-3_先物ではボラの変化が全資産でリバーサルの収益を予測し夜間のボラの増え方は通貨だけ無効。
  関連知見: Q042（荒れた相場に限っても為替の押し目の逆張りは戻らない。ボラの「水準」の条件）。
  → 本案はボラの「水準」ではなく「変化」（短期ボラ÷長期ボラ）が、1日逆張りの翌日の損益を予測するか。Q042 と条件が違う（明記）。

【仮説（測る前に固定）】
H1: ボラの変化（直前20日ボラ÷直前60日ボラ の対数）が大きい日ほど、翌日の1日逆張り（前日の符号の逆）の損益が大きい（正の関係）。
H0: 関係は 0 と区別できない。

【データ】15銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1通りに固定）】
- 逆張りの損益 R_{t+1} = −sign(r_t) × r_{t+1} × 1e4 − 往復コスト [bp]（毎日往復・段階1。粗利も出す）。
- ボラの変化 V_t = log( sd(r_{t−19..t}) / sd(r_{t−59..t}) )。
- (a) 銘柄×年のセルで Spearman(V_t, R_{t+1})、年ごとに銘柄平均 → 年を単位に平均と t。群別（all15・FX8・トレンド7）、前後半。
- (b) 条件つき: 各銘柄・各年で V_t が上位 1/5 の日だけ逆張り（コスト後の bp/日）と、残りの日の差。年単位の t。
- 帰無: V_t を年内で並べ替え（R との関係を壊す）て (a)(b) を B=500 回 → z。

【測るもの】(a) の平均と t・z、(b) の差と t・z、群別・前後半、粗利／コスト後。

【判定（事前固定・変更禁止）】
all15 で、前後半とも (a) の Spearman の平均 > 0 かつ z ≥ 2、かつ (b) の差（コスト後）の年単位 t ≥ 2 →「ボラの変化は逆張りの損益を予測する」＝H1 支持。
前後半のどちらかで (a) の z < 2 → 棄却。それ以外は未確定。(b) の上位1/5のコスト後の水準が正かは記述（売買に使えるかは別問題）。

【捨てた案の数】約4: ボラの水準（Q042 と重なる）、5分位の全刻み（上位1/5 だけ）、夜間ボラの分解（為替スポットの夜間の定義が別案 Q173 にある）、
GARCH の条件付き分散（道具なし）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・(a)(b) の t と z・DellaCorte 2015 の該当表を返す。

【実装】自己完結。実行: python3 kensho_vol_change_reversal_q174.py（B=500、1分前後）／--B 50／--smoke
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
# 往復コスト（価格単位・段階1の保守値。Q136〜Q156 と同じ表）
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
CRYPTO_COST_RT_REL = 30e-4  # 暗号資産: 往復 30bp の仮置き（Q152 と同じ）
SPLIT_YEAR = 2017
SEED = 20261009
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


def _smoke_ohlc(sym, rng, n, freq, start):
    """合成データ（GBM）。判定には使わない。"""
    rng = rng or np.random.default_rng(SEED)
    t = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(0.0001, 0.006, n)
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})


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


def donchian_pos(high, low, close, n_in=55, n_out=20):
    """ドンチャン簡略版（両方向）: n_in 本高値更新で買い・安値更新で売り、n_out 本の逆側で手仕舞い。終値で判定。"""
    h = pd.Series(np.asarray(high, float)); l = pd.Series(np.asarray(low, float)); c = np.asarray(close, float)
    hi_in = h.rolling(n_in).max().shift(1).values; lo_in = l.rolling(n_in).min().shift(1).values
    hi_out = h.rolling(n_out).max().shift(1).values; lo_out = l.rolling(n_out).min().shift(1).values
    pos = np.zeros(len(c)); p = 0.0
    for t in range(len(c)):
        if np.isnan(hi_in[t]) or np.isnan(hi_out[t]):
            pos[t] = 0.0; continue
        if p == 1 and c[t] < lo_out[t]:
            p = 0.0
        elif p == -1 and c[t] > hi_out[t]:
            p = 0.0
        if p == 0:
            if c[t] > hi_in[t]:
                p = 1.0
            elif c[t] < lo_in[t]:
                p = -1.0
        pos[t] = p
    return pos


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
    x = np.asarray(pnl, float)
    return float(x.mean() / x.std(ddof=1) * math.sqrt(per_year)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


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


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p); order = np.argsort(p); adj = np.empty(m)
    run = 0.0
    for i, k in enumerate(order):
        run = max(run, (m - i) * p[k]); adj[k] = min(1.0, run)
    return adj


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


QID = "Q174"
DEFAULT_B = 500
W_SHORT, W_LONG = 20, 60


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); r = df["ret"].values
        rs = pd.Series(r)
        V = np.log(rs.rolling(W_SHORT).std() / rs.rolling(W_LONG).std()).values
        pos = -np.sign(np.nan_to_num(r))
        c = df["close"].values; cb = cost_bp_oneway(s, c)
        gross = pnl_bp(pos, c, np.zeros(len(c))); net = pnl_bp(pos, c, cb)
        d = pd.DataFrame({"sym": s, "year": df["year"].values, "V": np.r_[np.nan, V[:-1]], "gross": gross, "net": net})  # V は前日の値を翌日の損益に対応
        frames.append(d.dropna())
    cells = pd.concat(frames, ignore_index=True)

    groups_idx = {k: v.index.values for k, v in cells.groupby(["year", "sym"])}  # (year, sym) → 行番号
    NET = cells["net"].values; GROSS = cells["gross"].values

    def stats(cells, V_col="V"):
        Vv = cells[V_col].values
        cell_stats = {}  # (year, sym) → (rho, top_net, rest_net, top_gross)
        for (y, s), idx in groups_idx.items():
            v = Vv[idx]; n = NET[idx]; gr = GROSS[idx]
            q = np.nanquantile(v, 0.8); top = v >= q
            cell_stats[(y, s)] = (spearman(v, n), n[top].mean(), n[~top].mean(), gr[top].mean())
        out = {}
        for g, members in GROUPS.items():
            for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
                by_year = {}
                for (y, s), st in cell_stats.items():
                    if s in members and y0 <= y < y1:
                        by_year.setdefault(y, []).append(st)
                if not by_year:
                    continue
                yr = np.array([np.nanmean(np.array(v, float), axis=0) for v in by_year.values()])  # 年ごとの銘柄平均
                rho = yr[:, 0]; diff = yr[:, 1] - yr[:, 2]
                out[f"{g}_{pn}"] = {"n_years": int(len(yr)), "rho_mean": float(np.nanmean(rho)), "rho_t": tstat(rho), "top_minus_rest_net": float(np.nanmean(diff)), "top_minus_rest_t": tstat(diff),
                                    "top_net_level": float(np.nanmean(yr[:, 1])), "top_gross_level": float(np.nanmean(yr[:, 3]))}
        return out
    obs = stats(cells)
    null = {k: {"rho": [], "diff": []} for k in obs}
    for b in range(args.B):
        cells["Vp"] = perm_within(rng, cells["V"].values, cells["sym"].astype(str).values + cells["year"].astype(str).values)
        st = stats(cells, "Vp")
        for k in obs:
            if k in st:
                null[k]["rho"].append(st[k]["rho_mean"]); null[k]["diff"].append(st[k]["top_minus_rest_net"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        zr, _ = z_of(v["rho_mean"], null[k]["rho"]); zd, _ = z_of(v["top_minus_rest_net"], null[k]["diff"])
        summary[k] = {**{kk: f(vv) for kk, vv in v.items()}, "n_years": v["n_years"], "rho_z": f(zr), "diff_z": f(zd)}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    ok = lambda p: (p.get("rho_mean") or 0) > 0 and (p.get("rho_z") or 0) >= 2 and (p.get("top_minus_rest_t") or 0) >= 2
    if ok(pre) and ok(post):
        verdict = "支持: ボラの変化は逆張りの損益を予測する"
    elif (pre.get("rho_z") or 0) < 2 or (post.get("rho_z") or 0) < 2:
        verdict = "棄却: 前後半のどちらかで (a) の z<2"
    else:
        verdict = "未確定"
    res = {"question": "ボラの変化は1日逆張りの翌日リターンを予測するか", "settings": {"W_SHORT": W_SHORT, "W_LONG": W_LONG, "B": args.B}, "missing": missing,
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 の前後半 (a) z と (b) t の 4 本。群別は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
