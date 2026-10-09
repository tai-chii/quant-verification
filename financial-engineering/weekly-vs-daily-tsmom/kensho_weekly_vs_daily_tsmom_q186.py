#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q186: 週足の順張りは日足より強いか（Neely・Weller 2003-3・15銘柄・2008〜2026）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Neely2003-3_為替のトレンドは週次月次では強いが日中足にはない。
  知見: 為替の超短期の平均回帰は2015年以降の1時間足では消えた（週次の自己相関も正にならず）、先進国通貨の日足テクニカルは 2016 年以降 0 本（Q019）。
  → 「同じ参照期間の順張りを、日足で毎日判定して 1 日持つのと、週足で毎週判定して 1 週持つのとで、どちらが情報係数と純損益（bp/日）で強いか」。
     週足は判定と約定の回数が 1/5 なのでコストも 1/5 になる（コストの効果と情報の効果を分けて記述）。

【仮説（測る前に固定）】
H1（Neely）: 週足の順張りの IC と純損益（bp/日換算）は、同じ参照期間の日足の順張りより大きい（為替で）。
H0: 差は 0 と区別できない。

【データ】15銘柄 D1_fromH1 → 週足（金曜の終値。その週に金曜がなければ最後の営業日）。2008〜2026-06。

【定義（1通りに固定）】
- 参照期間の対応: 週足 Lw ∈ {4, 8, 13, 26, 52} 週 ⇔ 日足 L = 5·Lw 営業日。
- 日足: 毎日 sign(c_t − c_{t−L}) を翌日持つ。週足: 毎週末 sign(c_w − c_{w−Lw}) を翌週持つ（週の中は固定）。
- IC: 合図（±1）と次の期間のリターンの Spearman。銘柄×年で出して年単位で平均と t。
- 純損益 [bp/日]: 日足はそのまま、週足は週次損益 ÷ 5。コストは段階1（週足は週 1 回の |Δpos|）。粗利も出す。
- 差 = 週足 − 日足（同じ Lw の組）。5 組の平均と組ごと。年単位の t。群別（FX8・トレンド7）・前後半。
- 帰無: 日次リターンを年内で並べ替え（週足も同じ並べ替えから作る）B=300 → 差の z。

【測るもの】IC の差・純損益の差（粗利・コスト後）と t・z、群別・前後半。

【判定（事前固定・変更禁止）】
FX8 で、前後半とも 純損益（コスト後）の差 > 0 かつ年単位 t ≥ 2 かつ z ≥ 2、かつ IC の差 > 0 →「週足の順張りは日足より強い（情報としても）」＝H1 支持。
純損益の差が t ≥ 2 でも IC の差が 0 以下 →「差はコストの回数の分だけ（情報は同じ）」と記述し H1 は棄却。
前後半のどちらかで |t| < 2 → 棄却。それ以外は未確定。

【捨てた案の数】約3: 月足（標本が少ない）、週の切り方を曜日ごとに変える案（金曜固定）、週足の合図を毎日更新する案（週足の定義から外れる）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z・Neely & Weller 2003 の該当表（週次・月次のルールの結果）を返す。

【実装】自己完結。実行: python3 kensho_weekly_vs_daily_tsmom_q186.py（B=300、数分）／--B 30／--smoke
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


QID = "Q186"
DEFAULT_B = 300
LWS = [4, 8, 13, 26, 52]


def _weekly(df):
    d = df.copy(); d["week"] = d["time"].dt.to_period("W-FRI")
    w = d.groupby("week").agg(time=("time", "last"), close=("close", "last"), year=("year", "last")).reset_index(drop=True)
    return w


def _metrics(c, cost_oneway, L, per_day_div):
    pos = tsmom_pos(c, L); pnl = pnl_bp(pos, c, cost_oneway) / per_day_div; gross = pnl_bp(pos, c, np.zeros(len(c))) / per_day_div
    ret_next = np.r_[c[1:] / c[:-1] - 1, np.nan]
    return pos, pnl, gross, ret_next


def _cells(df, sym, smoke_cost=None):
    rows = []
    c = df["close"].values; yrs = df["year"].values; cb = cost_bp_oneway(sym, c)
    w = _weekly(df); cw = w["close"].values; yw = w["year"].values; cbw = cost_bp_oneway(sym, cw)
    for Lw in LWS:
        pd_, pnl_d, g_d, rn_d = _metrics(c, cb, 5 * Lw, 1.0)
        pw_, pnl_w, g_w, rn_w = _metrics(cw, cbw, Lw, 5.0)
        for y in np.unique(yrs):
            md = yrs == y; mw = yw == y
            if md.sum() < 100 or mw.sum() < 20:
                continue
            rows.append({"sym": sym, "year": int(y), "Lw": Lw, "ic_d": spearman(pd_[md][:-1], rn_d[md][:-1]), "ic_w": spearman(pw_[mw][:-1], rn_w[mw][:-1]),
                         "pnl_d": pnl_d[md].mean(), "pnl_w": pnl_w[mw].mean(), "gross_d": g_d[md].mean(), "gross_w": g_w[mw].mean()})
    return rows


def _summ(cells):
    out = {}
    for g, members in GROUPS.items():
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            sub = cells[cells["sym"].isin(members) & (cells["year"] >= y0) & (cells["year"] < y1)]
            if sub.empty:
                continue
            by = sub.groupby("year")[["ic_d", "ic_w", "pnl_d", "pnl_w", "gross_d", "gross_w"]].mean()
            out[f"{g}_{pn}"] = {"n_years": int(len(by)), "ic_diff": float((by["ic_w"] - by["ic_d"]).mean()), "ic_diff_t": tstat((by["ic_w"] - by["ic_d"]).values),
                                "pnl_diff": float((by["pnl_w"] - by["pnl_d"]).mean()), "pnl_diff_t": tstat((by["pnl_w"] - by["pnl_d"]).values),
                                "gross_diff": float((by["gross_w"] - by["gross_d"]).mean()), "gross_diff_t": tstat((by["gross_w"] - by["gross_d"]).values),
                                "pnl_d": float(by["pnl_d"].mean()), "pnl_w": float(by["pnl_w"].mean()), "ic_d": float(by["ic_d"].mean()), "ic_w": float(by["ic_w"].mean()),
                                "by_Lw_pnl_diff": {int(Lw): float((lambda g2: (g2["pnl_w"] - g2["pnl_d"]).mean())(sub[sub["Lw"] == Lw].groupby("year")[["pnl_w", "pnl_d"]].mean())) for Lw in LWS}}
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    data = {s: load_d1(s, args.smoke, rng) for s in syms}
    cells = pd.DataFrame([r for s in syms for r in _cells(data[s], s)])
    obs = _summ(cells)
    null = {k: {"pnl": [], "ic": []} for k in obs}
    for b in range(args.B):
        rows = []
        for s in syms:
            df = data[s].copy(); c = df["close"].values; r = np.r_[0.0, c[1:] / c[:-1] - 1]
            rp = perm_within(rng, r, df["year"].values); df["close"] = c[0] * np.cumprod(1 + np.r_[0.0, rp[1:]])
            rows += _cells(df, s)
        st = _summ(pd.DataFrame(rows))
        for k in obs:
            if k in st:
                null[k]["pnl"].append(st[k]["pnl_diff"]); null[k]["ic"].append(st[k]["ic_diff"])
        if b % 20 == 0:
            print("null", b)
    summary = {k: {**{kk: (f(vv) if not isinstance(vv, dict) else {a: f(b_) for a, b_ in vv.items()}) for kk, vv in v.items()}, "n_years": v["n_years"],
                   "pnl_diff_z": f(z_of(v["pnl_diff"], null[k]["pnl"])[0]), "ic_diff_z": f(z_of(v["ic_diff"], null[k]["ic"])[0])} for k, v in obs.items()}
    pre, post = summary.get("fx8_pre", {}), summary.get("fx8_post", {})
    ok = lambda p: (p.get("pnl_diff") or 0) > 0 and (p.get("pnl_diff_t") or 0) >= 2 and (p.get("pnl_diff_z") or 0) >= 2
    if ok(pre) and ok(post) and (pre.get("ic_diff") or 0) > 0 and (post.get("ic_diff") or 0) > 0:
        verdict = "支持: 週足の順張りは日足より強い（情報としても）"
    elif ok(pre) and ok(post):
        verdict = "棄却: 差はコストの回数の分だけ（IC の差は 0 以下）"
    elif abs(pre.get("pnl_diff_t") or 0) < 2 or abs(post.get("pnl_diff_t") or 0) < 2:
        verdict = "棄却: 前後半のどちらかで |t|<2"
    else:
        verdict = "未確定"
    res = {"question": "週足の順張りは日足より強いか", "settings": {"LWS": LWS, "B": args.B}, "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は FX8 前後半の純損益の差の t・z と IC の差の符号。群別・Lw 別は記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
