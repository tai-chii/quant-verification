#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q179: 五十日の仲値前の円安は、クロス円（EURJPY・GBPJPY）でも出て、2021年以降に消えたか（Bessho ほか 2023 の移植）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Bessho2023-1_五十日は3時に買って仲値の9時55分に売るとプロフィットファクター1.46で五十日でない日は0.51だった、
  Bessho2023-2_仲値の後の売りは仲値前に上がった五十日だけ効き日本企業の富が為替の売買者へ漏れる。
  知見: ドル円の五十日の仲値前のドル高は2020年までは再現するが2023年以降は消えた（Q0xx・kensho_gotobi.py）。
  → 「五十日の仲値前の円安（＝ドル買い需要）は USDJPY だけでなくクロス円（EURJPY・GBPJPY）でも出ていたか。同じ時期に消えたか」。
     クロス円で出れば『円売り需要』、USDJPY だけなら『ドル買い需要』の区別になる（条件の穴）。

【仮説（測る前に固定）】
H1: 五十日の仲値前の窓で、クロス円も USDJPY と同じ向き（円安）に動き、2008–2016 で有意、2023 年以降は消える（USDJPY と同じ減衰）。
対立: クロス円では出ない（五十日はドル固有の需要）。

【データ】USDJPY・EURJPY・GBPJPY の H1（Dukascopy、UTC）。2008-01〜2026-06。

【定義（1通りに固定）】
- 五十日 = 日本時間の日付の日が 5・10・15・20・25・月末。土日なら直前の平日（Bessho の慣行。祝日は考えない・明記）。
- 仲値前の窓（H1 で近似）: 前日 18:00 UTC（＝日本 3:00）の足の始値 → 01:00 UTC（＝日本 10:00。仲値 9:55 の直後）の足の始値。リターン [bp]（円安 = 正）。
- 比較 = 五十日の窓の平均 − 五十日でない平日の窓の平均 [bp]。NW(5) の t。
- 期間（固定）: 2008–2016／2017–2022／2023–2026-06（知見の区切りに合わせる）。
- 帰無: 月の中で五十日のラベルを並べ替え（日数は保つ）B=500 → 差の z。
- 副次: 仲値の後の窓（01:00 → 07:00 UTC）の平均も出す（Q190 の問いと接続・記述）。

【測るもの】通貨×期間の差・t・z、USDJPY との比。

【判定（事前固定・変更禁止）】
EURJPY・GBPJPY の両方で、2008–2016 の差 > 0 かつ z ≥ 2、かつ 2023– の差の z < 2 →「クロス円でも出て同じく消えた」＝H1 支持。
2008–2016 で両方とも z < 2（USDJPY は z ≥ 2）→「ドル固有」＝対立を支持。それ以外は未確定。

【捨てた案の数】約3: 日本の祝日の扱い、M15 で 9:55 を正確に取る案（M15 は 2021〜のみ）、EURUSD・GBPUSD の同じ窓（ドル成分の分離。記述に回す）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・通貨×期間の差と z・Bessho 2023 の表（五十日／非五十日の PF）を返す。

【実装】自己完結。実行: python3 kensho_gotobi_cross_jpy_q179.py（B=500、1分前後）／--B 50／--smoke
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


QID = "Q179"
DEFAULT_B = 500
PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
PERIODS = {"2008-2016": (2008, 2017), "2017-2022": (2017, 2023), "2023-2026": (2023, 9999)}
H_PRE_START, H_PRE_END, H_POST_END = 18, 1, 7


def _gotobi_flags(dates):
    """dates: 日本時間の日付（pd.DatetimeIndex）。五十日（土日なら直前の平日）に True。"""
    s = pd.Series(dates); d = s.dt.day; last = (s + pd.offsets.MonthEnd(0)).dt.day
    base = d.isin([5, 10, 15, 20, 25]) | (d == last)
    # 土日に当たる五十日を直前の平日へ
    flags = pd.Series(False, index=s.values)
    cal = pd.Series(s.values, index=s.values)
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
    d = df.copy(); d["hour"] = d["time"].dt.hour
    d["jst_date"] = (d["time"] + pd.Timedelta(hours=9)).dt.normalize()
    p_pre = d[d["hour"] == H_PRE_START].assign(jst_date=lambda x: x["jst_date"] + pd.Timedelta(days=0)).set_index("jst_date")["open"]  # 日本 3:00 は同じ日本日付
    p_fix = d[d["hour"] == H_PRE_END].set_index("jst_date")["open"]; p_post = d[d["hour"] == H_POST_END].set_index("jst_date")["open"]
    x = pd.DataFrame({"p_pre": p_pre, "p_fix": p_fix, "p_post": p_post}).dropna()
    x = x[x.index.weekday < 5]
    x["r_pre"] = (x["p_fix"] / x["p_pre"] - 1) * 1e4; x["r_post"] = (x["p_post"] / x["p_fix"] - 1) * 1e4
    x["gotobi"] = _gotobi_flags(x.index); x["year"] = x.index.year; x["ym"] = x.index.year * 100 + x.index.month
    return x


def run(args, rng):
    syms, missing = syms_available(PAIRS, kind="H1_dukascopy", smoke=args.smoke)
    out = {}
    for s in syms:
        df = load_csv(f"{s}_H1_dukascopy", args.smoke, rng, freq="h", n=120000, start="2008-01-01")
        x = _windows(df); out[s] = {}
        for pn, (y0, y1) in PERIODS.items():
            sub = x[(x["year"] >= y0) & (x["year"] < y1)]
            if len(sub) < 200:
                continue
            g, ng = sub[sub["gotobi"]], sub[~sub["gotobi"]]
            diff = g["r_pre"].mean() - ng["r_pre"].mean()
            # 2標本の差の t（NW ではなく、日次の窓は重ならないので素朴な Welch）
            se = math.sqrt(g["r_pre"].var(ddof=1) / len(g) + ng["r_pre"].var(ddof=1) / len(ng)); t = diff / se if se > 0 else float("nan")
            null = []
            for _ in range(args.B):
                lab = perm_within(rng, sub["gotobi"].values.astype(float), sub["ym"].values).astype(bool)
                null.append(sub["r_pre"].values[lab].mean() - sub["r_pre"].values[~lab].mean())
            z, pct = z_of(diff, null)
            out[s][pn] = {"n_gotobi": int(len(g)), "n_other": int(len(ng)), "pre_mean_gotobi": f(g["r_pre"].mean()), "pre_mean_other": f(ng["r_pre"].mean()), "diff_bp": f(diff), "t": f(t), "z": f(z), "pct": f(pct),
                          "post_mean_gotobi": f(g["r_post"].mean()), "post_mean_other": f(ng["r_post"].mean())}
            print(s, pn, out[s][pn]["diff_bp"], out[s][pn]["z"])
    def ok_early(s): return (out.get(s, {}).get("2008-2016", {}).get("diff_bp") or 0) > 0 and (out.get(s, {}).get("2008-2016", {}).get("z") or 0) >= 2
    def gone_late(s): return (out.get(s, {}).get("2023-2026", {}).get("z") or 9) < 2
    cross = ["EURJPY", "GBPJPY"]
    if all(ok_early(s) and gone_late(s) for s in cross):
        verdict = "支持: クロス円でも出て同じく消えた"
    elif all(not ok_early(s) for s in cross) and ok_early("USDJPY"):
        verdict = "対立を支持: ドル固有"
    else:
        verdict = "未確定"
    res = {"question": "五十日の仲値前の円安はクロス円でも出て2021年以降に消えたか", "settings": {"periods": PERIODS, "window_utc": [H_PRE_START, H_PRE_END, H_POST_END], "B": args.B}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "note": "仲値前の窓は H1 で 18:00→01:00 UTC に近似。祝日は考えない。", "multiple_comparisons": "判定はクロス円2×期間2の z 4 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
