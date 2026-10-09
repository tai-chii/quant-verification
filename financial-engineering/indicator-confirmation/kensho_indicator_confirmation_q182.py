#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q182: 複数の順張り指標が一致したときだけ売買すると、的中率と純損益は上がるか（Loubaris・Koraich 2026-2・15銘柄）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Loubaris2026-2_複数指標の確認は個別指標より的中率が高い傾向があるが有意差なし（500 日・1 銘柄）。
  関連知見: Q147（翌日の方向の的中率は基準率を超えない）、Q142（高ボラ局面）。
  → 標本を 15 銘柄×18 年に増やして、「一致したときだけ」の的中率と純損益（売買した日あたり・暦日あたり）が単独の指標を上回るか。

【仮説（測る前に固定）】
H1: 3 指標が一致した日だけ売買すると、売買した日あたりの純損益は最良の単独指標より高い（年単位 t ≥ 2）。
H0: 差は 0 と区別できない（Loubaris と同じ非有意）。暦日あたり（売買しない日を 0 で含む）は、機会が減るぶん下がる。

【データ】15銘柄 D1_fromH1。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- 指標 3 本（固定）: (1) 終値 > SMA200 で +1・以下で −1、(2) TSMOM20 の符号、(3) ドンチャン簡略版 55/20 の状態（0 もある）。
- 単独: 各指標の符号をそのまま持つ。一致（2/3）: 3 本の符号の和の符号（多数決。和が 0 なら持たない）。一致（3/3）: 3 本が同符号のときだけ持つ。
- 的中率 = 持った日のうち翌日の符号が合った割合。純損益 = (a) 持った日あたり [bp]、(b) 暦日あたり [bp]（持たない日は 0）。
- 集計: 銘柄×年 → 年ごとに銘柄平均 → 年単位の平均と t。差 = 一致(3/3) − max(単独の 3 本)（年単位の対応ありの差）。群別・前後半。
- 帰無: 翌日リターンを年内で並べ替え B=500 → 差の分布の z。

【測るもの】各戦略の的中率・(a)(b) の純損益、差の t・z、持った日の割合。

【判定（事前固定・変更禁止）】
all15 で前後半とも 一致(3/3) − 最良単独 の (a) の差 > 0 かつ年単位 t ≥ 2 かつ z ≥ 2 →「一致で売買した日あたりの成績は上がる」＝H1 支持。
どちらかで |t| < 2 → 棄却（Loubaris と同じ非有意）。(b) 暦日あたりが下がるかは記述。的中率の差も記述（判定に使わない）。

【捨てた案の数】約4: 指標を 5 本に増やす案（多数決の解釈が曖昧）、RSI を混ぜる案（逆張り指標が混ざる）、重みづけ、保有日数を延ばす案。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・差の t と z・Loubaris 2026 の該当表（複数指標の的中率）を返す。

【実装】自己完結。実行: python3 kensho_indicator_confirmation_q182.py（B=500、1分前後）／--B 50／--smoke
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


QID = "Q182"
DEFAULT_B = 500
STRATS = ["SMA200", "TSMOM20", "DONCH55_20", "MAJ2of3", "ALL3"]


def _positions(df):
    c, h, l = df["close"].values, df["high"].values, df["low"].values
    s1 = sma_pos(c, 200); s2 = tsmom_pos(c, 20); s3 = donchian_pos(h, l, c, 55, 20)
    tot = s1 + s2 + s3
    maj = np.sign(tot); maj[np.abs(tot) < 2] = 0.0  # 2/3 以上の一致（0 を含む 3 本の和が ±1 なら持たない）
    all3 = np.where((s1 == s2) & (s2 == s3) & (s1 != 0), s1, 0.0)
    return {"SMA200": s1, "TSMOM20": s2, "DONCH55_20": s3, "MAJ2of3": maj, "ALL3": all3}


def _cell_stats(POS, c, cb, yrs, ret_next):
    rows = []
    for name, pos in POS.items():
        pnl = pnl_bp(pos, c, cb); held = np.r_[0.0, pos[:-1]]
        for y in np.unique(yrs):
            m = (yrs == y) & (held != 0); mall = yrs == y
            if mall.sum() < 100:
                continue
            hit = float((np.sign(ret_next[m]) == held[m]).mean()) if m.sum() > 0 else np.nan
            rows.append({"strat": name, "year": int(y), "hit": hit, "pnl_held": float(pnl[m].mean()) if m.sum() > 0 else np.nan, "pnl_cal": float(pnl[mall].mean()), "frac_held": float(m.sum() / mall.sum())})
    return rows


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    rows = []; nulls = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yrs = df["year"].values
        ret = np.r_[0.0, c[1:] / c[:-1] - 1]
        POS = _positions(df)
        for r_ in _cell_stats(POS, c, cb, yrs, ret):
            rows.append({"sym": s, **r_})
        # 帰無: 翌日リターンを年内で並べ替え（合図は固定）→ pnl_held の差
        for b in range(args.B):
            rp = perm_within(rng, ret, yrs); cp = c[0] * np.cumprod(1 + np.r_[0.0, rp[1:]])
            # 合図は元の価格で作ったまま、損益だけ並べ替えた価格で
            for name, pos in POS.items():
                pnl = pnl_bp(pos, cp, cost_bp_oneway(s, cp)); held = np.r_[0.0, pos[:-1]]
                for y in np.unique(yrs):
                    m = (yrs == y) & (held != 0)
                    if (yrs == y).sum() >= 100 and m.sum() > 0:
                        nulls.append({"b": b, "sym": s, "strat": name, "year": int(y), "pnl_held": float(pnl[m].mean())})
        print(s, "done")
    cells = pd.DataFrame(rows); nul = pd.DataFrame(nulls)
    out = {}
    for g, members in GROUPS.items():
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            sub = cells[cells["sym"].isin(members) & (cells["year"] >= y0) & (cells["year"] < y1)]
            if sub.empty:
                continue
            by = sub.groupby(["year", "strat"])[["hit", "pnl_held", "pnl_cal", "frac_held"]].mean().unstack("strat")
            best_single = max(["SMA200", "TSMOM20", "DONCH55_20"], key=lambda k: by["pnl_held"][k].mean())
            diff = (by["pnl_held"]["ALL3"] - by["pnl_held"][best_single]).values
            ns = nul[nul["sym"].isin(members) & (nul["year"] >= y0) & (nul["year"] < y1)]
            nb = ns.groupby(["b", "year", "strat"])["pnl_held"].mean().groupby(["b", "strat"]).mean().unstack("strat")
            ndiff = (nb["ALL3"] - nb[best_single]).values if "ALL3" in nb else []
            out[f"{g}_{pn}"] = {"n_years": int(len(by)), "best_single": best_single,
                                "hit": {k: f(by["hit"][k].mean()) for k in STRATS}, "pnl_held": {k: f(by["pnl_held"][k].mean()) for k in STRATS},
                                "pnl_cal": {k: f(by["pnl_cal"][k].mean()) for k in STRATS}, "frac_held": {k: f(by["frac_held"][k].mean()) for k in STRATS},
                                "diff_all3_minus_best_single_held": f(np.nanmean(diff)), "diff_t": f(tstat(diff)), "diff_z": f(z_of(np.nanmean(diff), ndiff)[0]),
                                "hit_diff_all3_minus_best": f((by["hit"]["ALL3"] - by["hit"][best_single]).mean())}
    pre, post = out.get("all15_pre", {}), out.get("all15_post", {})
    ok = lambda p: (p.get("diff_all3_minus_best_single_held") or 0) > 0 and (p.get("diff_t") or 0) >= 2 and (p.get("diff_z") or 0) >= 2
    if ok(pre) and ok(post):
        verdict = "支持: 一致で売買した日あたりの成績は上がる"
    elif abs(pre.get("diff_t") or 0) < 2 or abs(post.get("diff_t") or 0) < 2:
        verdict = "棄却: Loubaris と同じ非有意"
    else:
        verdict = "未確定"
    res = {"question": "複数の順張り指標が一致したときだけ売買すると的中率と純損益は上がるか", "settings": {"B": args.B}, "missing": missing, "summary": out, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 前後半の差の t と z（4 本）。群別・的中率・暦日あたりは記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
