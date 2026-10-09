#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q190: 仲値後のドル円の売りは、仲値前に上がった五十日だけ効くか（Bessho ほか 2023-2・2008〜2026）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Bessho2023-2_仲値の後の売りは仲値前に上がった五十日だけ効き日本企業の富が為替の売買者へ漏れる、Bessho2023-1。
  知見: ドル円の五十日の仲値前のドル高は2020年までは再現するが2023年以降は消えた（Q0xx）。関連: Q063（公表後の残り方）、Krohn2024-1（フィキシング後の反落）。
  → 既存の検証は「仲値前」だけ。本案は「仲値後の売り」が、(i) 五十日かつ仲値前に上がった日だけに効くという条件つきの主張を、
     2×2（五十日×仲値前の向き）で測り、公表（2023-01）前後で分ける。

【仮説（測る前に固定）】
H1（Bessho）: 仲値後（10:00→16:00 JST）の売りの損益は、「五十日かつ仲値前が上昇」のセルでだけ正で、他の 3 セルより大きい（2008–2022）。
H2（公表後）: 2023 年以降はそのセルでも 0 と区別できない。

【データ】USDJPY H1（Dukascopy、UTC）。2008-01〜2026-06。

【定義（1通りに固定）】
- 五十日 = Q179 と同じ（日本時間の日付、土日は直前の平日、祝日は考えない）。
- 仲値前 r_pre = 前日 18:00 UTC（日本 3:00）の足の始値 → 01:00 UTC（日本 10:00）の始値。仲値後 r_post = 01:00 → 07:00 UTC（日本 16:00）の始値 [bp]。
- 売りの損益 = −r_post − 往復コスト（段階1の COST_RT／価格、bp）。粗利も出す。
- セル: 五十日 × (r_pre > 0)。各セルの平均・Welch の差。主差 D = セル(五十日・上昇) − 他 3 セルの平均。
- 期間（固定）: 2008–2016／2017–2022／2023–2026-06。
- 帰無: 月の中で五十日のラベルを並べ替え B=500 → D の z。r_pre の向きは実データのまま（上昇の条件づけ自体は漏れではない。明記）。

【測るもの】4 セルの売りの損益（粗利・コスト後）、D と z、期間別。

【判定（事前固定・変更禁止）】
2008–2016 と 2017–2022 の両方で、セル(五十日・上昇) のコスト後の平均 > 0 かつ D > 0 で z ≥ 2 →「Bessho-2 の条件つき主張を再現」＝H1 支持。
どちらかで z < 2 → H1 棄却。H1 支持のうえで 2023– の z < 2 → H2 支持（公表後に消えた）、z ≥ 2 → H2 棄却（残っている）。

【捨てた案の数】約3: M15 で 9:55 を厳密に取る案（2021〜しかない）、他の 4 セルの組合せ（上昇の閾値を bp で刻む）、クロス円（Q179 に回す）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。公表日（2023-01）も締め切り前。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・セル別の値と z・Bessho 2023 の該当表（仲値後の売りの条件つき結果）を返す。

【実装】自己完結。実行: python3 kensho_post_fix_conditional_sell_q190.py（B=500、1分前後）／--B 50／--smoke
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


QID = "Q190"
DEFAULT_B = 500
PERIODS = {"2008-2016": (2008, 2017), "2017-2022": (2017, 2023), "2023-2026": (2023, 9999)}
H_PRE_START, H_FIX, H_POST_END = 18, 1, 7


def _gotobi_flags(dates):
    s = pd.Series(dates); d = s.dt.day; last = (s + pd.offsets.MonthEnd(0)).dt.day
    base = d.isin([5, 10, 15, 20, 25]) | (d == last)
    flags = pd.Series(False, index=s.values)
    for dt_, b in zip(s, base):
        if not b:
            continue
        x = dt_
        while x.weekday() >= 5:
            x -= pd.Timedelta(days=1)
        if x in flags.index:
            flags[x] = True
    return flags.values


def _windows(df):
    d = df.copy(); d["hour"] = d["time"].dt.hour; d["jst_date"] = (d["time"] + pd.Timedelta(hours=9)).dt.normalize()
    p_pre = d[d["hour"] == H_PRE_START].set_index("jst_date")["open"]; p_fix = d[d["hour"] == H_FIX].set_index("jst_date")["open"]; p_post = d[d["hour"] == H_POST_END].set_index("jst_date")["open"]
    x = pd.DataFrame({"p_pre": p_pre, "p_fix": p_fix, "p_post": p_post}).dropna(); x = x[x.index.weekday < 5]
    x["r_pre"] = (x["p_fix"] / x["p_pre"] - 1) * 1e4; x["r_post"] = (x["p_post"] / x["p_fix"] - 1) * 1e4
    x["gotobi"] = _gotobi_flags(x.index); x["up"] = x["r_pre"] > 0; x["year"] = x.index.year; x["ym"] = x.index.year * 100 + x.index.month
    x["sell_gross"] = -x["r_post"]; x["sell_net"] = x["sell_gross"] - COST_RT["USDJPY"] / x["p_fix"] * 1e4
    return x


def _D(x, lab):
    g = x[lab & x["up"].values]["sell_net"].mean(); others = x[~(lab & x["up"].values)]["sell_net"].mean()
    return g - others


def run(args, rng):
    if not args.smoke and not exists_sym("USDJPY", "H1_dukascopy"):
        return {"error": "data_USDJPY_H1_dukascopy.csv が無い"}, None
    x = _windows(load_csv("USDJPY_H1_dukascopy", args.smoke, rng, freq="h", n=120000, start="2008-01-01"))
    out = {}
    for pn, (y0, y1) in PERIODS.items():
        sub = x[(x["year"] >= y0) & (x["year"] < y1)]
        if len(sub) < 200:
            continue
        cells = {}
        for gname, gm in (("gotobi", sub["gotobi"]), ("other", ~sub["gotobi"])):
            for uname, um in (("up", sub["up"]), ("down", ~sub["up"])):
                cs = sub[gm & um]
                cells[f"{gname}_{uname}"] = {"n": int(len(cs)), "sell_gross": f(cs["sell_gross"].mean()), "sell_net": f(cs["sell_net"].mean()), "sell_net_t": f(nw_t(cs["sell_net"].values, 1))}
        D = _D(sub, sub["gotobi"].values)
        null = [_D(sub, perm_within(rng, sub["gotobi"].values.astype(float), sub["ym"].values).astype(bool)) for _ in range(args.B)]
        z, pct = z_of(D, null)
        out[pn] = {"cells": cells, "D_gotobi_up_minus_others": f(D), "z": f(z), "pct": f(pct)}
        print(pn, cells["gotobi_up"], "D", out[pn]["D_gotobi_up_minus_others"], "z", out[pn]["z"])
    def ok(pn): return pn in out and (out[pn]["cells"]["gotobi_up"]["sell_net"] or 0) > 0 and (out[pn]["D_gotobi_up_minus_others"] or 0) > 0 and (out[pn]["z"] or 0) >= 2
    if ok("2008-2016") and ok("2017-2022"):
        h1 = "支持: Bessho-2 の条件つき主張を再現"
        h2 = "H2 支持: 公表後に消えた" if (out.get("2023-2026", {}).get("z") or 9) < 2 else "H2 棄却: 残っている"
    else:
        h1 = "棄却: 2008–2016／2017–2022 のどちらかで z<2"; h2 = "—（H1 が棄却）"
    res = {"question": "仲値後のドル円の売りは仲値前に上がった五十日だけ効くか", "settings": {"periods": PERIODS, "window_utc": [H_PRE_START, H_FIX, H_POST_END], "B": args.B},
           "summary": out, "machine_verdict": f"H1: {h1}／H2: {h2}", "note": "仲値の窓は H1 で近似（18:00→01:00→07:00 UTC）。祝日は考えない。", "multiple_comparisons": "判定は期間 3 の z 3 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
