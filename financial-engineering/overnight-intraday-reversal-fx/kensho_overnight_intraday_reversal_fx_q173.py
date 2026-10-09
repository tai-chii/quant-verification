#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q173: 為替の夜間→日中の逆張りは、2015年以降の主要8通貨でコスト後に残るか（DellaCorte・Kosowski・Wang 2015）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: DellaCorte2015-1_夜間リターンで作る逆張りは米国株で従来の短期リバーサルの約5倍の収益だった、
  DellaCorte2015-2_従来の短期リバーサルが効かない通貨先物でも夜間から日中への逆張りは有意だった。
  関連: Krohn2024-1（フィキシング前後の W 字）、知見「為替の超短期の平均回帰は2015年以降の1時間足では消えた」。
  → 「為替のスポット（Dukascopy H1）で、夜間（NY 引け→ロンドン寄付）のリターンの逆を日中（ロンドン寄付→NY 引け）に持つと、
     2015年以降もコスト後に残るか。従来の短期リバーサル（前の日中の逆）と比べて何倍か」。

【仮説（測る前に固定）】
H1: 夜間→日中の逆張りは 2015 年以降の主要8通貨でもコスト後にプラスで、従来の短期リバーサル（前日の日中の逆）より大きい。
H0: コスト後に 0 と区別できない（知見「超短期の平均回帰は消えた」と整合）。

【データ】主要8通貨 H1（Dukascopy、UTC）。2015-01〜2026-06。前半 2015–2020／後半 2021–2026。

【定義（1通りに固定）】
- 夜間 r_n = 21:00 UTC の足の始値 → 翌 07:00 UTC の足の始値（NY 引け→ロンドン寄付。夏時間は考慮しない・固定）。
- 日中 r_d = 07:00 の始値 → 21:00 の始値。
- 戦略 A（夜間→日中の逆張り）: 07:00 に −sign(r_n) を持ち、21:00 に手仕舞い（毎日往復 1 回）。
- 戦略 B（従来の短期リバーサル）: 07:00 に −sign(前日の r_d) を持ち、21:00 に手仕舞い。
- 日次の損益 [bp] = pos × r_d × 1e4 − 往復コスト [bp]（段階1の COST_RT／07:00 の価格）。
- 統計: 通貨ごとの平均 [bp/日] と Newey-West(5) の t。8通貨の合算（日ごとの平均）の t。前後半。
- 帰無: r_n を年の中で並べ替えて（夜間と日中の繋がりを壊す）戦略 A の合算の平均を B=500 回 → z。
- 副次: A÷B の比（DellaCorte の「約5倍」）。粗利でも出す。

【判定（事前固定・変更禁止）】
8通貨合算のコスト後の平均が、前後半とも t ≥ 2 かつ z ≥ 2、かつ通貨の過半で同符号（正）→「夜間→日中の逆張りは為替スポットで公表後も残る」＝H1 支持。
前後半のどちらかで t < 2（または負）→ 棄却。それ以外は未確定。A÷B の比は記述（判定に使わない）。

【捨てた案の数】約5: 夏時間で窓をずらす案（固定で単純化）、閾値つき（|r_n| 上位のみ）、保有を翌 07:00 まで延ばす案、
30分足を使う案（H1 のみ）、金利差（キャリー）の控除（データなし。明記）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。2015 年以降の期間のうち 2026-07 以降は含まない。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・合算の t と z・
DellaCorte ほか 2015 の通貨先物の表（Table に相当）の箇所を返す。

【実装】自己完結。実行: python3 kensho_overnight_intraday_reversal_fx_q173.py（B=500、1分前後）／--B 50／--smoke
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


QID = "Q173"
DEFAULT_B = 500
NIGHT_START, DAY_START = 21, 7
START, SPLIT = 2015, 2021


def _sessions(df):
    """H1 → 日ごとの (date, p21_prev, p07, p21)。夜間 r_n = p07/p21_prev −1、日中 r_d = p21/p07 −1。"""
    df = df.copy(); df["date"] = df["time"].dt.date; df["hour"] = df["time"].dt.hour
    p07 = df[df["hour"] == DAY_START].set_index("date")["open"]
    p21 = df[df["hour"] == NIGHT_START].set_index("date")["open"]
    d = pd.DataFrame({"p07": p07, "p21": p21}).dropna()
    d["p21_prev"] = d["p21"].shift(1)
    d["gap_days"] = (pd.to_datetime(pd.Series(d.index)).diff().dt.days.values)
    d = d[(d["gap_days"] <= 3)].dropna()  # 週末明け（金→月）も1つの「夜間」として許す。3日超の穴は除く。
    d["r_n"] = d["p07"] / d["p21_prev"] - 1; d["r_d"] = d["p21"] / d["p07"] - 1
    d["year"] = pd.to_datetime(pd.Series(d.index)).dt.year.values
    return d.reset_index().rename(columns={"index": "date"})


def _strat(d, sym, sig):
    pos = -np.sign(sig)
    cost = COST_RT[sym] / d["p07"].values * 1e4  # 往復（毎日）
    gross = pos * d["r_d"].values * 1e4
    return gross, gross - np.abs(pos) * cost


def run(args, rng):
    syms, missing = syms_available(FX8, kind="H1_dukascopy", smoke=args.smoke)
    per = {}; daily = {}
    for s in syms:
        df = load_csv(f"{s}_H1_dukascopy", args.smoke, rng, freq="h", n=60000, start="2014-06-01")
        d = _sessions(df); d = d[d["year"] >= START].reset_index(drop=True)
        gA, nA = _strat(d, s, d["r_n"].values)
        prev_rd = np.r_[np.nan, d["r_d"].values[:-1]]
        gB, nB = _strat(d, s, np.nan_to_num(prev_rd))
        d["A_gross"], d["A_net"], d["B_gross"], d["B_net"] = gA, nA, gB, nB
        daily[s] = d
        per[s] = {}
        for pn, msk in (("all", d["year"] >= START), ("pre", d["year"] < SPLIT), ("post", d["year"] >= SPLIT)):
            sub = d[msk]
            per[s][pn] = {"n": int(len(sub)), "A_net_mean": f(sub["A_net"].mean()), "A_net_t": f(nw_t(sub["A_net"].values)),
                          "A_gross_mean": f(sub["A_gross"].mean()), "B_net_mean": f(sub["B_net"].mean()), "B_net_t": f(nw_t(sub["B_net"].values))}
        print(s, per[s]["all"])
    # 合算（日ごとの平均）
    allA = pd.concat([daily[s].set_index("date")[["A_net", "A_gross", "B_net", "year"]].rename(columns={"A_net": f"A_{s}", "A_gross": f"G_{s}", "B_net": f"B_{s}"}) for s in syms], axis=1)
    yrs = allA["year"].iloc[:, 0] if isinstance(allA["year"], pd.DataFrame) else allA["year"]
    A = allA[[c for c in allA.columns if c.startswith("A_")]].mean(axis=1); B = allA[[c for c in allA.columns if c.startswith("B_")]].mean(axis=1)
    G = allA[[c for c in allA.columns if c.startswith("G_")]].mean(axis=1)
    pooled = {}
    bounds = {"all": (START, 9999), "pre": (START, SPLIT), "post": (SPLIT, 9999)}
    for pn, (y0, y1) in bounds.items():
        msk = (yrs >= y0) & (yrs < y1)
        a = A[msk].dropna(); b = B[msk].dropna(); g = G[msk].dropna()
        # 帰無: 各通貨の r_n を年内で並べ替え（夜間と日中の繋がりを壊す）→ A の合算平均
        null = []
        for _ in range(args.B):
            vals = []
            for s in syms:
                d = daily[s]; dm = d[(d["year"] >= y0) & (d["year"] < y1)]
                rn = perm_within(rng, dm["r_n"].values, dm["year"].values)
                vals.append(_strat(dm, s, rn)[1].mean())
            null.append(np.mean(vals))
        z, pct = z_of(a.mean(), null)
        gB = np.mean([per[s][pn]["B_net_mean"] or 0 for s in syms])
        pooled[pn] = {"n_days": int(len(a)), "A_net_mean": f(a.mean()), "A_net_t": f(nw_t(a.values)), "A_gross_mean": f(g.mean()), "A_gross_t": f(nw_t(g.values)),
                      "B_net_mean": f(b.mean()), "B_net_t": f(nw_t(b.values)),
                      "ratio_A_over_B_net": f(a.mean() / b.mean()) if b.mean() != 0 else None,
                      "null_z": f(z), "null_pct": f(pct), "n_pos_syms": int(sum(1 for s in syms if (per[s][pn]["A_net_mean"] or 0) > 0))}
    gpre, gpost = pooled["pre"], pooled["post"]
    ok = lambda p: (p["A_net_t"] or -9) >= 2 and (p["null_z"] or -9) >= 2 and p["n_pos_syms"] > len(syms) / 2
    if ok(gpre) and ok(gpost):
        verdict = "支持: 夜間→日中の逆張りは為替スポットで公表後も残る"
    elif (gpre["A_net_t"] or 0) < 2 or (gpost["A_net_t"] or 0) < 2:
        verdict = "棄却: 前後半のどちらかでコスト後 t<2"
    else:
        verdict = "未確定"
    res = {"question": "為替の夜間→日中の逆張りは2015年以降の主要8通貨でコスト後に残るか", "settings": {"night_start_utc": NIGHT_START, "day_start_utc": DAY_START, "start": START, "split": SPLIT, "B": args.B},
           "missing": missing, "per_symbol": per, "pooled": pooled, "machine_verdict": verdict,
           "note": "夏時間は固定で扱う。金利差は控除していない。A÷B の比は per_symbol の粗利から読む（記述）。",
           "multiple_comparisons": "判定は合算の前後半 2 本（t と z）。通貨別は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
