#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q224: 危機アルファ（原典の形）— 1・3・12 か月 TSMOM の等加重合成＋銘柄ごとの値幅目標（Q205 の形）で、US500 の下落局面（高値から −10% 超）単位の損益が正か。BTC 抜きを併記。
================================================================================

【出典】
- 計画（事前登録・新規）: Q207 の README「原典との差」を受け、Hurst・Ooi・Pedersen (2017) Exhibit 6
  "Time-Series Momentum during the 10 Worst Drawdowns for 60/40" の形に合わせる。
  原文: "the time-series momentum strategy experienced positive returns in 8 out of 10 of these stress periods"、
       戦略は "an equal-weighted combination of 1-month, 3-month, and 12-month time-series momentum strategies"、
       "annualized ex ante volatility target of 10%"。
- 値幅目標の形: Q205（Harvey ほか 2018 の追試・2026-10-10・支持・確定）が選んだ σ60 の逆数×CAP=4。
- Q207 と違う点: (1) 合図は L=252 単独でなく {21, 63, 252} の等加重合成、(2) 建玉を σ60 で規模調整（当日は含まない）、
  (3) 下落局面の単位は暦月の下位1割でなく「US500 が自身の最高値を割っている連続区間で最大下落 ≥ 10%」。

【仮説（測る前に固定）】
H1: 下落局面 N 件のうち、15 銘柄等加重の 1/3/12 か月 TSMOM 合成（σ60 で値幅目標）の累積純損益（bp）について、
    (a) 全局面の合計 > 0 かつ (b) 局面ごとの正の割合 > 50% かつ (c) 「平均局面損益」の帰無に対する z ≥ 1.645。
H0: 下落局面と区別のある効果はない（帰無: 局面の開始日を標本の中で一様に置き直す）。

【データ】15 銘柄 D1_fromH1（2011-10〜2026-06・約 3700 日）。US500 D1_fromH1 で高値・下落局面を決める。

【定義（1 通りに固定）】
- 合図: 銘柄ごとに signal = (sign(c-c[-21]) + sign(c-c[-63]) + sign(c-c[-252])) / 3。
- 値幅目標: w = min(TARGET=0.10 / σ60_ann, CAP=4)。σ60_ann = ret の 60 日 sd × sqrt(252)。
  σ60 と合図はいずれも当日の情報のみ、pnl_bp で建玉は 1 日ずらして翌日のリターンに当てる。
- 日次損益（bp）: 銘柄 s について pnl_s = pnl_bp(signal_s * w_s, close_s, cost_oneway_s)。
- ポートフォリオ損益（bp）: 日々の pnl_s の等加重平均（当該日の有効銘柄のみ）。
- 下落局面: US500 の D1 終値について、running peak を累積最大、below = (close < peak) として、
  below が True の連続区間 [i, j) のうち、区間内の最大下落 (close/peak − 1).min() ≤ −0.10 のものを拾う。
  区間の開始は「前回の最高値の翌日」、終了は「次に最高値に戻る前日」。
- 局面ごとの累積損益: 区間内のポートフォリオ損益 bp の合計。
- 帰無: 各局面を、長さを保ったまま標本の中で一様に置き直す（置き換えは重なってよい・B=1000）。
  観測統計量「局面ごとの平均累積 bp」の分布を作り、z と並び替え p 値を得る。

【判定（事前固定・変更禁止）】
all15 で、
- 支持: 合計 > 0 かつ 正の割合 > 50% かつ 平均の z ≥ 1.645。
- 棄却: 合計 ≤ 0。
- それ以外: 未確定。

副次（判定本数に数えない・記述のみ）:
- BTC 抜き（14 銘柄）、合成でなく L=252 単独（Q207 と同じ形で下落局面に当てた参照）、
  局面ごとの明細、銘柄別の寄与、buy-and-hold の値幅目標版（規模調整の統計的な偏りの点検）。

【捨てた案の数】約 3: (1) 下落局面の最低値までで切る（recovery まで含めない形）、(2) 判定を割合だけにする（局面 6 件では飽和しやすい）、(3) σ の推定を EWMA にする（Q205 と形を揃える目的）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Claude Opus（2026-10-10・/lab Q224）。実行と解釈も同じセッション。
                 返すもの: 設定・局面一覧・局面ごとの累積 bp・判定・JSON と README のパス。

【実装】自己完結。実行: python3 kensho_crisis_alpha_q224.py（B=1000、1 分前後）／--B 100／--smoke。
"""

# ============================================================================= 共通の土台（Q207 と同じ・自己完結）
import argparse
import datetime as _dt
import json
import math
import os
import unicodedata
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))


def _p(*parts):
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")
FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
SEED = 20261010


def _read(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return df


def _smoke_ohlc(sym, rng, n=2600, freq="D", start="2015-01-01"):
    rng = rng or np.random.default_rng(SEED)
    t = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(0.0001, 0.006, n)
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c})


def load_d1(sym, smoke=False, rng=None):
    if smoke:
        df = _smoke_ohlc(sym, rng)
    else:
        df = _read(os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv"))
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    df["year"] = df["time"].dt.year
    return df


def exists_sym(sym):
    return os.path.exists(os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv"))


def cost_bp_oneway(sym, close):
    return COST_RT[sym] / 2 / np.asarray(close, float) * 1e4


def tsmom_pos(close, L):
    c = np.asarray(close, float)
    s = np.zeros(len(c))
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def pnl_bp(pos, close, cost_oneway_bp):
    c = np.asarray(close, float); pos = np.asarray(pos, float)
    ret = np.zeros(len(c)); ret[1:] = c[1:] / c[:-1] - 1
    held = np.r_[0.0, pos[:-1]]
    prev = np.r_[0.0, held[:-1]]
    cost = np.abs(held - prev) * np.r_[0.0, cost_oneway_bp[:-1]]
    return held * ret * 1e4 - cost


def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def z_of(obs, null):
    null = np.asarray(null, float); null = null[np.isfinite(null)]
    if len(null) < 3 or null.std(ddof=1) == 0 or not np.isfinite(obs):
        return float("nan"), float("nan")
    return float((obs - null.mean()) / null.std(ddof=1)), float((null < obs).mean())


def f(x, nd=4):
    try:
        return None if x is None or not np.isfinite(x) else round(float(x), nd)
    except Exception:
        return None


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


# ============================================================================= Q224
QID = "Q224"
DEFAULT_B = 1000
LS = (21, 63, 252)
VOL_N = 60
TARGET = 0.10
CAP = 4.0
DD_THRESHOLD = -0.10


def drawdown_periods(close, dates):
    c = np.asarray(close, float)
    peak = np.maximum.accumulate(c)
    dd = c / peak - 1.0
    below = c < peak
    n = len(c)
    periods = []
    i = 0
    while i < n:
        if below[i]:
            j = i
            while j < n and below[j]:
                j += 1
            md = float(dd[i:j].min())
            if md <= DD_THRESHOLD:
                periods.append({"start_idx": i, "end_idx": j - 1, "n_days": j - i,
                                "start": str(pd.Timestamp(dates[i]).date()),
                                "end": str(pd.Timestamp(dates[j - 1]).date()),
                                "max_drawdown": md})
            i = j
        else:
            i += 1
    return periods


def build_daily_pnl(syms, smoke, rng):
    """銘柄ごとの日次 pnl（bp）と time を揃えた panel を返す。"""
    frames = {}
    for s in syms:
        df = load_d1(s, smoke, rng)
        c = df["close"].values
        cb = cost_bp_oneway(s, c)
        sd = pd.Series(df["ret"].values).rolling(VOL_N).std().values * math.sqrt(252)
        w = np.minimum(TARGET / np.where(sd > 0, sd, np.nan), CAP)
        w = np.nan_to_num(w)
        sig_combo = (tsmom_pos(c, 21) + tsmom_pos(c, 63) + tsmom_pos(c, 252)) / 3.0
        pnl_combo = pnl_bp(sig_combo * w, c, cb)
        pnl_L252 = pnl_bp(tsmom_pos(c, 252) * w, c, cb)
        pnl_combo[: max(LS) + 1] = np.nan
        pnl_L252[: 253] = np.nan
        frames[s] = pd.DataFrame({"time": df["time"].values, "combo": pnl_combo, "L252": pnl_L252}).set_index("time")
    return frames


def portfolio_daily(frames, members, col="combo"):
    p = pd.concat({s: frames[s][col] for s in members if s in frames}, axis=1)
    return p.mean(axis=1, skipna=True), p


def period_sums(daily, periods):
    """日次ポートフォリオ損益 bp と periods（index ベース）→ 局面ごとの累積 bp。"""
    x = daily.values
    out = []
    for p in periods:
        a, b = p["start_idx"], p["end_idx"] + 1
        s = np.nansum(x[a:b])
        out.append(float(s))
    return np.array(out, float)


def null_period_sums(daily_values, period_lengths, rng, B):
    """各局面を長さを保って標本の中で一様に置き直す → 「平均局面 bp」と「正の割合」の分布。"""
    n = len(daily_values)
    means = np.empty(B)
    frac_pos = np.empty(B)
    for b in range(B):
        sums = []
        for L in period_lengths:
            if n - L <= 0:
                sums.append(np.nan)
                continue
            start = int(rng.integers(0, n - L))
            sums.append(float(np.nansum(daily_values[start:start + L])))
        arr = np.array(sums, float)
        means[b] = np.nanmean(arr)
        frac_pos[b] = float(np.mean(arr > 0))
    return means, frac_pos


def run(args, rng):
    syms = [s for s in SYMS if (args.smoke or exists_sym(s))]
    missing = [s for s in SYMS if s not in syms]
    frames = build_daily_pnl(syms, args.smoke, rng)

    us = load_d1("US500", args.smoke, rng).set_index("time")["close"]
    # US500 の下落局面を決める（当日の情報のみ）
    us_dates = us.index.values
    periods = drawdown_periods(us.values, us_dates)

    all15_daily, _ = portfolio_daily(frames, SYMS, "combo")
    all15_daily = all15_daily.reindex(us.index)
    ex_btc_daily, _ = portfolio_daily(frames, [s for s in SYMS if s != "BTCUSD"], "combo")
    ex_btc_daily = ex_btc_daily.reindex(us.index)
    all15_L252_daily, _ = portfolio_daily(frames, SYMS, "L252")
    all15_L252_daily = all15_L252_daily.reindex(us.index)

    results = {}
    for label, daily in (("all15_combo", all15_daily), ("ex_btc_combo", ex_btc_daily), ("all15_L252_only", all15_L252_daily)):
        sums = period_sums(daily, periods)
        n_pos = int((sums > 0).sum())
        n_tot = len(sums)
        total = float(sums.sum())
        mean = float(sums.mean())
        t = tstat(sums)
        null_means, _ = null_period_sums(daily.values, [p["n_days"] for p in periods], np.random.default_rng(args.seed + 1), args.B)
        z, pv = z_of(mean, null_means)
        results[label] = {"n_periods": n_tot, "n_positive": n_pos, "frac_positive": f(n_pos / n_tot if n_tot else np.nan),
                          "total_bp": f(total), "mean_bp": f(mean), "t": f(t),
                          "null_mean_of_mean": f(float(np.nanmean(null_means))),
                          "null_sd_of_mean": f(float(np.nanstd(null_means, ddof=1))),
                          "z": f(z), "perm_p_right_tail": f(1 - pv if pv is not None and np.isfinite(pv) else np.nan),
                          "per_period_bp": [f(x, 2) for x in sums]}

    # 判定（事前固定・all15_combo のみ）
    v = results["all15_combo"]
    if (v["total_bp"] or 0) > 0 and (v["frac_positive"] or 0) > 0.5 and (v["z"] or 0) >= 1.645:
        verdict = "支持: 下落局面で原典型 TSMOM は正の損益（危機アルファあり）"
    elif (v["total_bp"] or 0) <= 0:
        verdict = "棄却: 下落局面の合計累積損益 ≤ 0"
    else:
        verdict = "未確定"

    # 銘柄別の寄与（記述）
    per_sym = {}
    for s in SYMS:
        if s not in frames:
            per_sym[s] = None; continue
        d = frames[s]["combo"].reindex(us.index).values
        sums = []
        for p in periods:
            sums.append(float(np.nansum(d[p["start_idx"]:p["end_idx"] + 1])))
        per_sym[s] = {"total_bp": f(float(np.nansum(sums))),
                      "per_period_bp": [f(x, 2) for x in sums]}

    res = {"question": "原典型（1/3/12か月合成・σ60値幅目標）で US500 の下落局面の TSMOM 累積損益は正か",
           "settings": {"LS": list(LS), "VOL_N": VOL_N, "TARGET": TARGET, "CAP": CAP,
                        "dd_threshold": DD_THRESHOLD, "B": args.B, "seed": args.seed},
           "missing": missing,
           "n_days": int(len(us)),
           "periods": periods,
           "results": results,
           "per_symbol_all15_combo": per_sym,
           "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15_combo の 3 本（合計>0・割合>50%・z≥1.645）のみ。ex_btc / L252単独 / 銘柄別 / 局面明細は記述。"}
    return res, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=DEFAULT_B)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    res, _ = run(args, rng)
    os.makedirs(OUT, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = f"smoke_{QID}" if args.smoke else QID
    path = os.path.join(OUT, f"{pre}_result_{ts}.json")
    with open(path, "w", encoding="utf-8") as fo:
        json.dump({"qid": QID, "smoke": args.smoke, "generated": ts, **res}, fo, ensure_ascii=False, indent=1, default=_json_default)
    print("wrote", os.path.relpath(path, HERE))
    print("machine_verdict:", res["machine_verdict"])


if __name__ == "__main__":
    main()
