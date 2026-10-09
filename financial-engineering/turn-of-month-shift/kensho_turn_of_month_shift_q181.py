#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q181: 月替わり効果の窓は2017年以降に前倒しされたか（QuanterLab 2026・US500／USTECH／SPX）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 論文ノート: ブログ_QuanterLab_2026_月替わり効果は月末4営業日前に前倒しされ有名な4日は平凡になった（ブログ。論文の出口では根拠にしない）。
  入荷台帳 ID98「The turn of the month effect tested: whe…」（未カード化）。関連: Arnott2019-3（公表後の減衰）、Q063（公表後の残り方）。
  → 「古典的な窓（月末最終日〜翌月 3 営業日）の超過は 2017 年以降に平凡になり、その前（月末 4〜2 営業日前）に移ったか」。

【仮説（測る前に固定）】
H1（ブログ）: 後半（2017–）では「前倒し窓（−4..−2）」の平均日次リターンが「古典窓（−1..+3）」を上回り、前半（2008–2016）では逆。
H0: 窓の差は期間で変わらない（差の差が 0 と区別できない）。

【データ】US500・USTECH（D1_fromH1、2011〜）、SPX（D1_long_yahoo、2008〜2026-07）。3 系列（SPX と US500 は同じ指数の別データ源なので「2 指数 3 系列」と記す）。

【定義（1通りに固定）】
- 各日の「月末からの営業日位置」k: 月の最終営業日 = −1、その前 = −2…、翌月の最初の営業日 = +1、+2…。
- 古典窓 C = {−1, +1, +2, +3}。前倒し窓 S = {−4, −3, −2}。その他 O = それ以外。
- 日次リターン [bp]（終値→終値）。各系列・各期間で、mean(S) − mean(C)、mean(C) − mean(O)、mean(S) − mean(O)。
- 差の差 DiD = [mean(S)−mean(C)]後半 − [mean(S)−mean(C)]前半。
- 帰無: 月の中で位置ラベルを並べ替え（各月のリターンの集合は保つ）B=1000 → 各差と DiD の z。
- 期間: 前半 2008(2011)–2016／後半 2017–2026-07。3 系列の合算（日ごとの平均。SPX と US500 の重複は認識したうえで記述）。

【測るもの】系列×期間の各窓の平均 [bp/日]、差、DiD と z。

【判定（事前固定・変更禁止）】
3 系列の過半（SPX・USTECH の 2 つ以上）で、後半 mean(S) − mean(C) > 0 かつ z ≥ 2、かつ DiD > 0 で z ≥ 2 →「前倒しを支持」。
後半 mean(S) − mean(C) の z < 2 が過半 → 棄却（古典窓と前倒し窓の差は見えない）。それ以外は未確定。
古典窓が後半でも mean(C) − mean(O) の z ≥ 2 なら「有名な 4 日は平凡になっていない」を併記。

【捨てた案の数】約3: 窓の長さの格子（ブログの定義に固定）、月末の位置を暦日で取る案（営業日で）、配当込み（データなし・価格のみ。明記）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。2026-07 の 1 か月分は締め切り後。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・系列別の差と z・ブログの図（前倒しの主張の箇所）を返す。

【実装】自己完結。実行: python3 kensho_turn_of_month_shift_q181.py（B=1000、1分前後）／--B 100／--smoke
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


QID = "Q181"
DEFAULT_B = 1000
SERIES = {"SPX": "SPX_D1_long_yahoo", "US500": "US500_D1_fromH1", "USTECH": "USTECH_D1_fromH1"}
C_WIN = {-1, 1, 2, 3}; S_WIN = {-4, -3, -2}


def _positions(df):
    d = df.copy(); d["ym"] = d["time"].dt.year * 100 + d["time"].dt.month
    d["k_from_start"] = d.groupby("ym").cumcount() + 1
    d["k_from_end"] = -(d.groupby("ym").cumcount(ascending=False) + 1)
    # 月の先頭 3 営業日は +k、それ以外は月末基準の −k
    d["k"] = np.where(d["k_from_start"] <= 3, d["k_from_start"], d["k_from_end"])
    d["ret"] = d["close"].pct_change() * 1e4; d["year"] = d["time"].dt.year
    d["win"] = np.where(d["k"].isin(C_WIN), "C", np.where(d["k"].isin(S_WIN), "S", "O"))
    return d.dropna(subset=["ret"])


def _diffs(d, win_col="win"):
    m = d.groupby(win_col)["ret"].mean()
    return {"S_minus_C": m.get("S", np.nan) - m.get("C", np.nan), "C_minus_O": m.get("C", np.nan) - m.get("O", np.nan), "S_minus_O": m.get("S", np.nan) - m.get("O", np.nan),
            "mean_C": m.get("C", np.nan), "mean_S": m.get("S", np.nan), "mean_O": m.get("O", np.nan)}


def run(args, rng):
    out = {}; missing = []
    for name, fn in SERIES.items():
        if not args.smoke and not os.path.exists(os.path.join(DATA_DIR, f"data_{fn}.csv")):
            missing.append(name); continue
        d = _positions(load_csv(fn, args.smoke, rng, freq="B", n=4000, start="2010-01-01"))
        d = d[d["high"] != d["low"]] if "high" in d else d
        pre, post = d[d["year"] < SPLIT_YEAR], d[d["year"] >= SPLIT_YEAR]
        o_pre, o_post = _diffs(pre), _diffs(post); did = o_post["S_minus_C"] - o_pre["S_minus_C"]
        null = {"pre_SC": [], "post_SC": [], "post_CO": [], "did": []}
        for _ in range(args.B):
            dd = d.copy(); dd["winp"] = perm_within_labels(rng, dd["win"].values, dd["ym"].values)
            np_, pp_ = _diffs(dd[dd["year"] < SPLIT_YEAR], "winp"), _diffs(dd[dd["year"] >= SPLIT_YEAR], "winp")
            null["pre_SC"].append(np_["S_minus_C"]); null["post_SC"].append(pp_["S_minus_C"]); null["post_CO"].append(pp_["C_minus_O"]); null["did"].append(pp_["S_minus_C"] - np_["S_minus_C"])
        out[name] = {"n_pre": int(len(pre)), "n_post": int(len(post)),
                     "pre": {k: f(v) for k, v in o_pre.items()}, "post": {k: f(v) for k, v in o_post.items()}, "did_S_minus_C": f(did),
                     "z_pre_SC": f(z_of(o_pre["S_minus_C"], null["pre_SC"])[0]), "z_post_SC": f(z_of(o_post["S_minus_C"], null["post_SC"])[0]),
                     "z_post_CO": f(z_of(o_post["C_minus_O"], null["post_CO"])[0]), "z_did": f(z_of(did, null["did"])[0])}
        print(name, out[name]["post"], "z_post_SC", out[name]["z_post_SC"], "z_did", out[name]["z_did"])
    ok = [n for n in out if (out[n]["post"]["S_minus_C"] or 0) > 0 and (out[n]["z_post_SC"] or 0) >= 2 and (out[n]["did_S_minus_C"] or 0) > 0 and (out[n]["z_did"] or 0) >= 2]
    weak = [n for n in out if (out[n]["z_post_SC"] or 0) < 2]
    if len(ok) >= 2:
        verdict = "支持: 前倒し"
    elif len(weak) >= 2:
        verdict = "棄却: 古典窓と前倒し窓の差は見えない"
    else:
        verdict = "未確定"
    classic_alive = [n for n in out if (out[n]["z_post_CO"] or 0) >= 2]
    res = {"question": "月替わり効果の窓は2017年以降に前倒しされたか", "settings": {"C_WIN": sorted(C_WIN), "S_WIN": sorted(S_WIN), "split": SPLIT_YEAR, "B": args.B}, "missing": missing,
           "per_series": out, "machine_verdict": verdict, "classic_window_still_significant_post": classic_alive, "note": "価格のみ（配当なし）。SPX と US500 は同じ指数の別データ源。",
           "multiple_comparisons": "判定は系列 3×（後半 S−C の z・DiD の z）。"}
    return res, None


def perm_within_labels(rng, labels, groups):
    lab = np.asarray(labels).copy(); g = np.asarray(groups)
    for v in np.unique(g):
        idx = np.where(g == v)[0]; lab[idx] = lab[rng.permutation(idx)]
    return lab


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
