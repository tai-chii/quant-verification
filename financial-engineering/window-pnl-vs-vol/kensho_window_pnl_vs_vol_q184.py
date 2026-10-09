#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q184: 2か月窓の順張り成績は、その窓の実現ボラとドリフトで説明できるか（Rashid ほか 2026-1・Q144 の続き）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Rashid2026-1_2か月の短期ライブ成績はボラティリティに左右され実力と局面の運を切り分けられない。
  知見 Q144（2 か月窓の成績はランダム売買の上位 5% に入る割合 0.8%・順位は入れ替わる）。
  → Q144 は「運と区別できない」まで。本案は「窓の成績がどれだけ窓の局面（実現ボラ・|ドリフト|）で説明できるか」を R² で測る。

【仮説（測る前に固定）】
H1: 2 か月窓の順張りの純損益は、その窓の |ドリフト|（＝順張りが取りやすいトレンドの大きさ）と実現ボラで半分以上が説明できる（R² ≥ 0.3）。
H0: R² < 0.1（局面では説明できない）。

【データ】15銘柄 D1_fromH1。規則 = TSMOM20（1 本）。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- 窓 = 42 営業日、21 日ずつずらす（Q144 と同じ）。窓ごとに: P = 純損益 [bp/日]、σ = 日次リターンの標準偏差 [bp]、|μ| = 平均日次リターンの絶対値 [bp]、
  トレンド強度 = |累積リターン| ÷ (σ√42)（符号なし）。
- (a) 銘柄ごとに Spearman(P, σ)・Spearman(P, |μ|)・Spearman(P, トレンド強度)。15 銘柄の平均と t（銘柄を単位）。
- (b) プール（銘柄×窓）で P を [σ, |μ|] に回帰（銘柄ダミーなし・標準化）した R²、σ だけの R²、|μ| だけの R²。
- 帰無: 窓の中でリターンを並べ替え（順張りの合図は壊れ、σ と μ は保たれる）B=300 → 帰無の P でも同じ R² を計算（局面だけで出る R² の水準）。
  観測の R² − 帰無の R² の差と z。
- 前後半でも出す。

【測るもの】(a) の平均と t、(b) の R²、帰無の R² との差と z。

【判定（事前固定・変更禁止）】
all15 の (b) の R²（σ+|μ|）≥ 0.3 かつ 帰無の R² との差の z ≥ 2 →「窓の成績は局面で説明できる（しかも並べ替えより強く）」＝H1 支持。
R² < 0.1 → H0。その間は未確定。σ だけ・|μ| だけの寄与は記述（Rashid の「ボラに左右される」が σ 側か |μ| 側か）。

【捨てた案の数】約3: 窓を 21・126 日にする格子（42 のみ）、銘柄固定効果つき回帰（記述に回さず省く）、ランダム売買の分布（Q144 で済み）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・R² と z・Rashid 2026 の該当箇所を返す。

【実装】自己完結。実行: python3 kensho_window_pnl_vs_vol_q184.py（B=300、1分前後）／--B 30／--smoke
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


QID = "Q184"
DEFAULT_B = 300
W, STEP, L = 42, 21, 20


def _windows(pnl, ret, yrs):
    rows = []
    for a in range(L + 1, len(pnl) - W, STEP):
        p = pnl[a:a + W]; r = ret[a:a + W]
        sd = r.std(ddof=1) * 1e4; mu = abs(r.mean()) * 1e4; cum = abs(np.log1p(r).sum()) * 1e4
        rows.append((p.mean(), sd, mu, cum / (sd * math.sqrt(W)) if sd > 0 else np.nan, yrs[a]))
    return rows


def _r2(y, X):
    X = np.column_stack([np.ones(len(y)), X]); beta = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ beta
    return float(1 - e.var() / y.var()) if y.var() > 0 else float("nan")


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    obs_rows = []; null_rows = {b: [] for b in range(args.B)}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yrs = df["year"].values
        ret = np.r_[0.0, c[1:] / c[:-1] - 1]
        pnl = pnl_bp(tsmom_pos(c, L), c, cb)
        for row in _windows(pnl, ret, yrs):
            obs_rows.append((s, *row))
        for b in range(args.B):
            rp = ret.copy()
            for a in range(L + 1, len(pnl) - W, STEP):
                rp[a:a + W] = rp[a:a + W][rng.permutation(W)]
            cp = c[0] * np.cumprod(1 + np.r_[0.0, rp[1:]])
            pn = pnl_bp(tsmom_pos(cp, L), cp, cost_bp_oneway(s, cp))
            for row in _windows(pn, rp, yrs):
                null_rows[b].append((s, *row))
        print(s, "done")
    cols = ["sym", "P", "sigma", "abs_mu", "trend", "year"]
    obs = pd.DataFrame(obs_rows, columns=cols)
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        sub = obs[(obs["year"] >= y0) & (obs["year"] < y1)].dropna()
        if len(sub) < 50:
            continue
        rho = {k: [spearman(g["P"], g[k]) for _, g in sub.groupby("sym")] for k in ("sigma", "abs_mu", "trend")}
        y = sub["P"].values
        r2 = {"sigma+abs_mu": _r2(y, sub[["sigma", "abs_mu"]].values), "sigma": _r2(y, sub[["sigma"]].values), "abs_mu": _r2(y, sub[["abs_mu"]].values), "trend": _r2(y, sub[["trend"]].values)}
        nr2 = []
        for b in range(args.B):
            nb = pd.DataFrame(null_rows[b], columns=cols); nb = nb[(nb["year"] >= y0) & (nb["year"] < y1)].dropna()
            nr2.append(_r2(nb["P"].values, nb[["sigma", "abs_mu"]].values))
        z, _ = z_of(r2["sigma+abs_mu"], nr2)
        out[pn] = {"n_windows": int(len(sub)), "rho_mean": {k: f(np.nanmean(v)) for k, v in rho.items()}, "rho_t_over_syms": {k: f(tstat(v)) for k, v in rho.items()},
                   "r2": {k: f(v) for k, v in r2.items()}, "null_r2_mean": f(np.nanmean(nr2)), "r2_minus_null_z": f(z)}
        print(pn, out[pn]["r2"], "z", out[pn]["r2_minus_null_z"])
    a = out.get("all", {}); r2a = (a.get("r2") or {}).get("sigma+abs_mu")
    if r2a is not None and r2a >= 0.3 and (a.get("r2_minus_null_z") or 0) >= 2:
        verdict = "支持: 窓の成績は局面で説明できる"
    elif r2a is not None and r2a < 0.1:
        verdict = "H0: 局面では説明できない"
    else:
        verdict = "未確定"
    res = {"question": "2か月窓の順張り成績はその窓の実現ボラとドリフトで説明できるか", "settings": {"W": W, "STEP": STEP, "L": L, "B": args.B}, "missing": missing, "summary": out, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all の R²（σ+|μ|）と z の 2 本。"}
    return res, {"windows": obs}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
