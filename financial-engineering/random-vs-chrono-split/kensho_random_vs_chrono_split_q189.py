#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q189: ランダム分割の交差検証は、時系列分割より順張り選択の楽観をどれだけ膨らませるか（Roelofs ほか 2019-2）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Roelofs2019-2_公開と非公開の差が大きかったコンペはデータの分け方が独立でないかテストが小さかった、
  White2000-3（Reality Check の交差検証への拡張は未解決）、Bailey2017-1。知見 Q155（エンバーゴ）、Q139（候補 J の楽観）。
  → 「同じ 4 年の窓で、(a) 時系列分割（前 3 年で選び 4 年目で測る）と (b) ランダム日分割（4 年の日を無作為に 75/25 に分け、75 で選び 25 で測る）の
     『テスト側の成績』を、本当の翌年（5 年目）の成績と比べる。ランダム分割のテスト成績は本当の翌年よりどれだけ楽観か」。
     順張りの合図は過去 L 日の価格から作るので、ランダム分割では選択側と評価側の日が重なり情報が漏れる（Roelofs の『独立でない分け方』）。

【仮説（測る前に固定）】
H1: ランダム分割のテスト成績（選んだ L の 25% 側の純損益）は、本当の翌年の純損益より高く（楽観）、その差は時系列分割のテスト成績の差より大きい。
H0: 両者の楽観に差はない（|t| < 2）。

【データ】15銘柄 D1_fromH1。候補 = TSMOM の参照日数 L ∈ {5,…,300}（60）。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- 窓 = 4 暦年（Y−4..Y−1）、本当の翌年 = Y。暦年ごとにずらす。
- (a) 時系列: Y−4..Y−2 で平均純損益が最大の L を選び、Y−1 の純損益をテスト成績 T_a。本当の成績 R_a = その L の Y の純損益。
- (b) ランダム: 4 年の日を無作為に 75%（選択）/25%（テスト）に分け（seed 固定・1 回）、選択側の平均純損益が最大の L を選び、テスト側の純損益を T_b。
  本当の成績 R_b = その L の Y の純損益。合図は分割前の全系列で作る（漏れをそのまま測る。明記）。
- 楽観 O_a = T_a − R_a、O_b = T_b − R_b。差 O_b − O_a。年ごとに銘柄平均 → 年単位の平均と t。群別・前後半。
- 帰無: L をランダムに選ぶ（B=300）→ O_a・O_b の分布（選択に情報がないときの楽観）→ z。
- 副次: ランダム分割を 5 回（seed を変える）して平均（記述）。

【測るもの】O_a・O_b・差の平均と t・z、群別・前後半。

【判定（事前固定・変更禁止）】
all15 で前後半とも O_b − O_a > 0 かつ年単位 t ≥ 2 →「ランダム分割は楽観を膨らませる（Roelofs の整理と整合）」＝H1 支持。
|t| < 2 → H0。それ以外は未確定。O_b 自体の z は記述（選択がなくても漏れだけで楽観が出るか）。

【捨てた案の数】約3: K 分割（75/25 の 1 回に固定）、ブロックランダム分割（週・月単位。中間的なので省く）、学習パラメータのあるモデル（候補の格子だけ）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z・Roelofs 2019 の該当箇所（独立でない分割の例）を返す。

【実装】自己完結。実行: python3 kensho_random_vs_chrono_split_q189.py（B=300、数分）／--B 30／--smoke
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


QID = "Q189"
DEFAULT_B = 300
LS = list(range(5, 301, 5))
TEST_MIN = 100
N_RANDOM_REPEATS = 5


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    rows = []; null_rows = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yrs = df["year"].values
        M = np.column_stack([pnl_bp(tsmom_pos(c, L), c, cb) for L in LS])
        years = sorted(np.unique(yrs))
        for Y in years:
            win = np.where((yrs >= Y - 4) & (yrs <= Y - 1))[0]; te = np.where(yrs == Y)[0]
            if len(te) < TEST_MIN or len(win) < 4 * TEST_MIN or win[0] < LS[-1] or len(set(yrs[win])) < 4:
                continue
            sel_a = win[yrs[win] <= Y - 2]; test_a = win[yrs[win] == Y - 1]
            kA = int(np.argmax(M[sel_a].mean(axis=0))); T_a = M[test_a, kA].mean(); R_a = M[te, kA].mean()
            Ob = []; Tb = []; Rb = []
            for rep in range(N_RANDOM_REPEATS):
                perm = rng.permutation(len(win)); n_sel = int(0.75 * len(win)); sel_b = win[perm[:n_sel]]; test_b = win[perm[n_sel:]]
                kB = int(np.argmax(M[sel_b].mean(axis=0))); Tb.append(M[test_b, kB].mean()); Rb.append(M[te, kB].mean()); Ob.append(Tb[-1] - Rb[-1])
            rows.append({"sym": s, "year": int(Y), "LA": LS[kA], "T_a": T_a, "R_a": R_a, "O_a": T_a - R_a, "T_b": Tb[0], "R_b": Rb[0], "O_b": Ob[0], "O_b_mean5": float(np.mean(Ob))})
            for b in range(args.B):
                k = int(rng.integers(0, len(LS)))
                perm = rng.permutation(len(win)); n_sel = int(0.75 * len(win)); test_b = win[perm[n_sel:]]
                null_rows.append({"b": b, "sym": s, "year": int(Y), "O_a": M[test_a, k].mean() - M[te, k].mean(), "O_b": M[test_b, k].mean() - M[te, k].mean()})
        print(s, "done")
    cells = pd.DataFrame(rows); nul = pd.DataFrame(null_rows)
    out = {}
    for g, members in GROUPS.items():
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            sub = cells[cells["sym"].isin(members) & (cells["year"] >= y0) & (cells["year"] < y1)]
            if sub.empty:
                continue
            by = sub.groupby("year")[["O_a", "O_b", "O_b_mean5", "T_a", "T_b", "R_a", "R_b"]].mean(); d = (by["O_b"] - by["O_a"]).values
            ns = nul[nul["sym"].isin(members) & (nul["year"] >= y0) & (nul["year"] < y1)].groupby(["b", "year"])[["O_a", "O_b"]].mean().groupby("b").mean()
            out[f"{g}_{pn}"] = {"n_years": int(len(by)), "n_cells": int(len(sub)), "O_a_mean": f(by["O_a"].mean()), "O_a_t": f(tstat(by["O_a"].values)), "O_b_mean": f(by["O_b"].mean()), "O_b_t": f(tstat(by["O_b"].values)),
                                "O_b_mean5": f(by["O_b_mean5"].mean()), "diff_Ob_minus_Oa": f(d.mean()), "diff_t": f(tstat(d)),
                                "z_O_a": f(z_of(by["O_a"].mean(), ns["O_a"].values)[0]), "z_O_b": f(z_of(by["O_b"].mean(), ns["O_b"].values)[0]),
                                "z_diff": f(z_of(d.mean(), (ns["O_b"] - ns["O_a"]).values)[0]), "T_a": f(by["T_a"].mean()), "T_b": f(by["T_b"].mean()), "R_a": f(by["R_a"].mean()), "R_b": f(by["R_b"].mean())}
    pre, post = out.get("all15_pre", {}), out.get("all15_post", {})
    tp, tq = pre.get("diff_t") or 0, post.get("diff_t") or 0
    if (pre.get("diff_Ob_minus_Oa") or 0) > 0 and tp >= 2 and (post.get("diff_Ob_minus_Oa") or 0) > 0 and tq >= 2:
        verdict = "支持: ランダム分割は楽観を膨らませる"
    elif abs(tp) < 2 or abs(tq) < 2:
        verdict = "H0: 両者の楽観に差はない"
    else:
        verdict = "未確定"
    res = {"question": "ランダム分割の交差検証は時系列分割より順張り選択の楽観をどれだけ膨らませるか", "settings": {"LS": LS, "window_years": 4, "random_frac": 0.75, "B": args.B}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "note": "合図は分割前の全系列で作る（漏れをそのまま測る）。", "multiple_comparisons": "判定は all15 前後半の差の t 2 本。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
