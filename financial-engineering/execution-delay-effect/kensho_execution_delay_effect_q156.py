#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q156: 約定を1〜2営業日遅らせると順張りの成績はどう変わるか（Korzan 2026 表5 では遅れで改善した）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q156（Fable 2026-10-09）。アイデア候補.md の該当行。
- 論文ノート: Korzan2026_二周期の株式ローテーション戦略_凍結した規則の評価（表5: 1営業日遅れで +94.41%、基準 +84.80%）、
  FX改善ログ 2026-07-13(1)（確定ラグでの EV 上昇は約定価格の下駄）、Neely・Weller2003_為替の日中足テクニカル。
  → 「合図から約定までの遅れ d で順張りの純損益はどう動くか。遅れて改善するなら合図の直後に逆行（短期の反転）があるのか、
     それとも運か。d=0（同じ足の終値）は先読みの大きさ」。

【仮説（測る前に固定）】
H1: d=2,3 の純損益が d=1 より高い（銘柄, 規則）が過半で、合算の年単位 t≥2 ＝ 合図の直後に逆行がある。
H0: 改善は並べ替え帰無の範囲（Korzan の遅れでの改善は運）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無い銘柄は除いて件数を JSON に書く。

【定義（1通りに固定）】
- 規則 2 本: TSMOM20（s_t = sign(c_t − c_{t−20})）、ドンチャン簡略版 55/20（終値が直前55日高値を上抜けで買い・直前20日安値
  割れで手仕舞い、売りは対称、損切りなし）。合図 s_t は t の終値で決まる。
- 約定の遅れ d ∈ {0, 1, 2, 3, 5}: 合図 s_t を t+d の終値で約定し、t+d → t+d+1 のリターンから持つ。
  ＝ 日 t のポジション pos_t(d) = s_{t−1−d}。d=0 は「合図と同じ足の終値で約定」（登録の呼び方では先読みの参考。
  お手本 kensho_trend_persistence_q136.py の `daily_net_pnl_bp` は d=0 に当たる＝要確認）。d=1 が既定（翌日の終値で約定）。
- 日次純損益 [bp] = pos_t × (c_t/c_{t−1} − 1) × 1e4 − |Δpos_t| × 片道コスト[bp]（段階1の往復 COST_RT の半分）。
  有効日 = t > DON_ENTRY + max(d) + 1（全規則・全 d が定義される日）。
- セル = 銘柄 × 規則（30）。年ごとの平均純損益 [bp/日]、全期間の最大下落 [bp]（累積純損益の高値からの最大の落ち）。
- 集計 = 年ごとにセル平均 → 年を単位に平均と t。d − d=1 の対応ありの差も年単位（合算の t）。
  改善セル数 = 全期間の平均純損益が d=1 より大きい（銘柄, 規則）の数（30 中）。
- 帰無: 各銘柄の半年の組の中で日次対数リターンを並べ替えて価格を作り直し（自己相関 0・ドリフトとボラは同じ）、
  同じ量（合算の差・改善セル数）を B=500 回 → z とパーセンタイル。
- 群・期間: 全15・FX8・トレンド7 × 全期間・前半(<2017)・後半(≥2017)、規則別も記述。判定は 全15・両規則・全期間。

【測るもの】
d ごとの純損益（年単位の平均・t）・最大下落、d=1 との差（年単位の t）、改善セル数、帰無の z・パーセンタイル。
d=0 − d=1（先読みの大きさ）も同じ形で記述。

【判定（事前固定・変更禁止）】
d=2 と d=3 の両方で、d=1 より改善する（銘柄, 規則）が過半（≥16/30）かつ合算の年単位 t≥2 なら
「合図の直後に逆行がある（短期の反転）」＝新しい条件の穴として記録。
改善が帰無の範囲（合算の差が帰無の 95% 点以内）なら「Korzan の遅れでの改善は運」。
d=0 が d=1 より大きく良ければ（差の t≥2）先読みの大きさとして記述（判定に使わない）。
（登録の「d=2,3 で…過半かつ t≥2」は d=2 と d=3 の両方で満たすこととして実装。片方だけなら「部分的」として記述。）

【捨てた案の数】
約5: 約定を翌日の始値にする案（始値列は信頼性が低いので終値で統一）、d を 10 まで伸ばす案（登録の 5 点に固定）、
最大下落を年ごとに出して t を取る案（全期間 1 本で記述）、ボラ調整したポジション（±1 に固定）、
帰無をブロック・ブートストラップにする案（並べ替えで統一）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。遅れの効果は機械的な手順で決まり、相場観の後知恵では作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、下請け）。実行と解釈は後で Sonnet／Opus。
実行者は結論ではなく、JSON のパス・d ごとの純損益と差の t・改善セル数・帰無の z・原典の箇所（Korzan 表5）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_execution_delay_effect_q156.py            （B=500、数分）
      python3 kensho_execution_delay_effect_q156.py --B 50     （軽い試走）
      python3 kensho_execution_delay_effect_q156.py --smoke    （合成データで経路の確認。結果は捨てる）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import unicodedata
import warnings

import numpy as np
import pandas as pd

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
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20
DON_ENTRY, DON_EXIT = 55, 20
DELAYS = [0, 1, 2, 3, 5]
D_REF = 1
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261009
RULES = ["tsmom", "donchian"]
VALID_FROM = DON_ENTRY + max(DELAYS) + 2


# ----------------------------------------------------------------------------- 基本の道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    return float(z), float((v < obs).mean())


def max_drawdown_bp(pnl):
    cum = np.cumsum(pnl); peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float((peak - cum).max()) if len(pnl) else float("nan")


# ----------------------------------------------------------------------------- データ・ルール
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d.time.values, d.close.values.astype(float)


def half_year_id(t):
    ts = pd.Series(t)
    return (ts.dt.year * 10 + np.where(ts.dt.month <= 6, 1, 2)).values


def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def donchian_positions(c):
    n = len(c); pos = np.zeros(n)
    cs = pd.Series(c)
    hiE = cs.rolling(DON_ENTRY).max().shift(1).values; loE = cs.rolling(DON_ENTRY).min().shift(1).values
    hiX = cs.rolling(DON_EXIT).max().shift(1).values; loX = cs.rolling(DON_EXIT).min().shift(1).values
    p = 0
    for i in range(n):
        if p == 1 and np.isfinite(loX[i]) and c[i] < loX[i]:
            p = 0
        elif p == -1 and np.isfinite(hiX[i]) and c[i] > hiX[i]:
            p = 0
        if p == 0:
            if np.isfinite(hiE[i]) and c[i] > hiE[i]:
                p = 1
            elif np.isfinite(loE[i]) and c[i] < loE[i]:
                p = -1
        pos[i] = p
    return pos


SIGNALS = {"tsmom": tsmom_positions, "donchian": donchian_positions}


def delayed_pnl_matrix(c, signal, cost_rt):
    """n × len(DELAYS) の日次純損益 [bp]。列 d: pos_t = s_{t−1−d}。先頭 VALID_FROM 日は 0。"""
    n = len(c)
    pos = np.zeros((n, len(DELAYS)))
    for j, d in enumerate(DELAYS):
        k = 1 + d
        pos[k:, j] = signal[:-k]
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos * ret[:, None] * 1e4
    dpos = np.abs(np.diff(np.vstack([np.zeros((1, len(DELAYS))), pos]), axis=0))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp[:, None]
    pnl[:VALID_FROM] = 0.0
    return pnl


def shuffled_prices(t, c, rng):
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    hid = half_year_id(t)
    r2 = r.copy()
    for b in np.unique(hid):
        idx = np.flatnonzero(hid == b); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    return np.exp(np.log(c[0]) + np.cumsum(r2))


# ----------------------------------------------------------------------------- 集計
def cell_tables(series):
    """年表（sym, rule, year, pnl_d*）と 全期間表（sym, rule, mean_d*, dd_d*）。"""
    yrows, frows = [], []
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        valid = np.arange(len(c)) >= VALID_FROM
        for rule in RULES:
            P = delayed_pnl_matrix(c, SIGNALS[rule](c), COST_RT[sym])
            for Y in np.unique(years[valid]):
                m = valid & (years == Y)
                if m.sum() < 50:
                    continue
                yrows.append(dict(sym=sym, rule=rule, year=int(Y), n=int(m.sum()), **{f"pnl_d{d}": float(P[m, j].mean()) for j, d in enumerate(DELAYS)}))
            frows.append(dict(sym=sym, rule=rule, n=int(valid.sum()),
                              **{f"mean_d{d}": float(P[valid, j].mean()) for j, d in enumerate(DELAYS)},
                              **{f"dd_d{d}": max_drawdown_bp(P[valid, j]) for j, d in enumerate(DELAYS)}))
    return pd.DataFrame(yrows), pd.DataFrame(frows)


def aggregate(ytab, ftab, syms, rules, year_lo=None, year_hi=None):
    g = ytab[ytab.sym.isin(syms) & ytab.rule.isin(rules)]
    f = ftab[ftab.sym.isin(syms) & ftab.rule.isin(rules)]
    if year_lo is not None:
        g = g[g.year >= year_lo]
    if year_hi is not None:
        g = g[g.year < year_hi]
    out = {"n_cells": int(len(f)), "n_years": int(g.year.nunique()), "by_d": {}}
    if len(g) == 0:
        return out
    py = g.groupby("year")
    ref = py[f"pnl_d{D_REF}"].mean()
    for d in DELAYS:
        m, tt, n = mean_t(py[f"pnl_d{d}"].mean().values)
        full = year_lo is None and year_hi is None
        e = dict(pnl_mean=m, pnl_t=tt, dd_mean=float(f[f"dd_d{d}"].mean()) if full else float("nan"))   # 最大下落は全期間だけ
        if d != D_REF:
            diff_year = (g[f"pnl_d{d}"] - g[f"pnl_d{D_REF}"]).groupby(g.year).mean().values
            dm, dt, dn = mean_t(diff_year)
            # 改善セル数は期間内の年平均で判定（全期間なら ftab の全期間平均と同じ）
            cell_mean = g.groupby(["sym", "rule"])[[f"pnl_d{d}", f"pnl_d{D_REF}"]].mean()
            n_imp = int((cell_mean[f"pnl_d{d}"] > cell_mean[f"pnl_d{D_REF}"]).sum())
            e.update(diff_vs_d1_mean=dm, diff_vs_d1_t=dt, n_improve_vs_d1=n_imp, n_cells_for_improve=int(len(cell_mean)),
                     dd_diff_vs_d1=float((f[f"dd_d{d}"] - f[f"dd_d{D_REF}"]).mean()) if full else float("nan"))
        out["by_d"][str(d)] = e
    return out


def null_stats(series, rng):
    """1 回の並べ替え: 全15・両規則・全期間の 合算の差 (d − d=1) と改善セル数。"""
    sh = {s: (t, shuffled_prices(t, c, rng)) for s, (t, c) in series.items()}
    ytab, ftab = cell_tables(sh)
    a = aggregate(ytab, ftab, list(series), RULES)
    return {d: (a["by_d"][str(d)]["diff_vs_d1_mean"], a["by_d"][str(d)]["n_improve_vs_d1"]) for d in DELAYS if d != D_REF}


def judge(a):
    res = {}
    for d in (2, 3):
        e = a["by_d"][str(d)]
        n_cells = e["n_cells_for_improve"]
        majority = e["n_improve_vs_d1"] > n_cells / 2.0
        sig = np.isfinite(e["diff_vs_d1_t"]) and e["diff_vs_d1_t"] >= 2.0
        within_null = np.isfinite(e.get("null_pct", float("nan"))) and e["null_pct"] < 0.95
        res[f"d{d}"] = dict(n_improve=e["n_improve_vs_d1"], n_cells=n_cells, majority=bool(majority), t=e["diff_vs_d1_t"],
                            t_ge2=bool(sig), null_pct=e.get("null_pct"), within_null_95=bool(within_null))
    both = all(res[f"d{d}"]["majority"] and res[f"d{d}"]["t_ge2"] for d in (2, 3))
    some = any(res[f"d{d}"]["majority"] and res[f"d{d}"]["t_ge2"] for d in (2, 3))
    luck = all(res[f"d{d}"]["within_null_95"] for d in (2, 3))
    if both:
        v = "合図の直後に逆行がある（短期の反転）＝新しい条件の穴"
    elif luck:
        v = "Korzan の遅れでの改善は運（帰無の範囲）"
    elif some:
        v = "部分的（d=2,3 の片方だけ過半かつ t≥2）"
    else:
        v = "遅れで改善しない（過半でも t≥2 でもない・帰無の外）"
    e0 = a["by_d"]["0"]
    lookahead = dict(diff_d0_vs_d1_mean=e0["diff_vs_d1_mean"], t=e0["diff_vs_d1_t"],
                     note="d=0（同じ足の終値）が d=1 より t≥2 で良ければ先読みの大きさとして記述（判定に使わない）")
    return dict(by_d=res, lookahead_d0=lookahead, verdict=v,
                note="事前固定の規則で機械的に付けた判定（全15・両規則・全期間）。解釈（確定／ノイズ／未確定、規則別・群別の読み）は実行者が記録する。")


def make_plot(res, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"]:
            if os.path.exists(p):
                font_manager.fontManager.addfont(p)
                matplotlib.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name(); break
        matplotlib.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        for key in ("全15|both|全期間", "FX8|both|全期間", "トレンド7|both|全期間", "全15|tsmom|全期間", "全15|donchian|全期間"):
            a = res[key]
            if not a["by_d"]:
                continue
            ax[0].plot(DELAYS, [a["by_d"][str(d)]["pnl_mean"] for d in DELAYS], "-o", label=key)
            ax[1].plot(DELAYS, [a["by_d"][str(d)]["dd_mean"] for d in DELAYS], "-o", label=key)
        ax[0].set_xlabel("約定の遅れ d（営業日）"); ax[0].set_ylabel("純損益（bp/日・年平均）"); ax[0].axhline(0, lw=.6, c="k"); ax[0].legend(fontsize=7)
        ax[1].set_xlabel("約定の遅れ d（営業日）"); ax[1].set_ylabel("最大下落（bp・セル平均）"); ax[1].legend(fontsize=7)
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    series, missing = {}, []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
            for i in range(1, len(dates)):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            got = load_daily(sym)
            if got is None:
                missing.append(sym); continue
            series[sym] = got
        B = args.B

    ytab, ftab = cell_tables(series)
    groups = {"全15": [s for s in SYMS if s in series], "FX8": [s for s in FX8 if s in series], "トレンド7": [s for s in TREND7 if s in series]}
    rule_sets = {"both": RULES, "tsmom": ["tsmom"], "donchian": ["donchian"]}
    periods = {"全期間": (None, None), "前半": (None, SPLIT_YEAR), "後半": (SPLIT_YEAR, None)}
    res = {}
    for gname, syms in groups.items():
        for rname, rules in rule_sets.items():
            for pname, (lo, hi) in periods.items():
                res[f"{gname}|{rname}|{pname}"] = aggregate(ytab, ftab, syms, rules, lo, hi)

    # 帰無（全15・両規則・全期間の合算の差と改善セル数）
    null = {d: {"diff": [], "n_improve": []} for d in DELAYS if d != D_REF}
    for b in range(B):
        ns = null_stats(series, rng)
        for d, (dm, ni) in ns.items():
            null[d]["diff"].append(dm); null[d]["n_improve"].append(ni)
    main_key = "全15|both|全期間"
    for d in DELAYS:
        if d == D_REF:
            continue
        e = res[main_key]["by_d"][str(d)]
        e["null_z"], e["null_pct"] = z_against_null(e["diff_vs_d1_mean"], null[d]["diff"])
        e["null_diff_mean"] = float(np.nanmean(null[d]["diff"])) if B else float("nan")
        e["null_diff_p95"] = float(np.nanpercentile(null[d]["diff"], 95)) if B else float("nan")
        e["null_n_improve_mean"] = float(np.nanmean(null[d]["n_improve"])) if B else float("nan")
        e["null_n_improve_p95"] = float(np.nanpercentile(null[d]["n_improve"], 95)) if B else float("nan")

    verdict = judge(res[main_key])
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    ycsv = os.path.join(OUT, f"{prefix}Q156_by_year_{stamp}.csv"); ytab.to_csv(ycsv, index=False)
    fcsv = os.path.join(OUT, f"{prefix}Q156_cells_{stamp}.csv"); ftab.to_csv(fcsv, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q156_by_delay_{stamp}.png"))
    out = dict(
        queue_id="Q156", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT, DELAYS=DELAYS, D_REF=D_REF, VALID_FROM=VALID_FROM,
                      SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=list(series), data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()), n=int(len(series[s][1])))
                   for s in series},
        missing=missing,
        results=res, cells=ftab.to_dict(orient="records"), judgement=verdict,
        files=dict(by_year_csv=ycsv, cells_csv=fcsv, png=png_path),
        multiple_comparisons="d 4 点（d=1 との差）× 群 3 × 規則 3 × 期間 3 = 108 本（判定は 全15・両規則・全期間 の d=2, d=3 の 2 本）",
        deviations_from_prereg=["d の定義: pos_t = s_{t−1−d}（d=0 = 合図と同じ足の終値で約定 = お手本 q136 の `daily_net_pnl_bp` と同じ）。登録の『d=1 既定』はお手本より 1 日遅い約定＝要確認",
                                "『d=2,3 で過半かつ t≥2』は d=2 と d=3 の両方で満たすこととして実装（片方だけは『部分的』）",
                                "最大下落は全期間 1 本（セル平均）で記述"],
    )
    jpath = os.path.join(OUT, f"{prefix}Q156_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else (int(o) if isinstance(o, np.integer) else (bool(o) if isinstance(o, np.bool_) else str(o))))

    print(f"[Q156] syms={len(series)} cells={len(ftab)}  B={B}  smoke={args.smoke}  missing={missing}")
    for key in (main_key, "全15|tsmom|全期間", "全15|donchian|全期間", "FX8|both|全期間", "トレンド7|both|全期間", "全15|both|前半", "全15|both|後半"):
        a = res[key]
        if not a["by_d"]:
            print(f"  {key}: (セルなし)"); continue
        print(f"  {key}: cells={a['n_cells']} years={a['n_years']}")
        for d in DELAYS:
            e = a["by_d"][str(d)]
            extra = ""
            if d != D_REF:
                extra = f" diff={e['diff_vs_d1_mean']:+.3f} t={e['diff_vs_d1_t']:+.2f} improve={e['n_improve_vs_d1']}/{e['n_cells_for_improve']}"
                if "null_z" in e:
                    extra += f" z={e['null_z']:+.2f} pct={e['null_pct']:.3f}"
            print(f"    d={d}: pnl={e['pnl_mean']:+.3f}bp (t{e['pnl_t']:+.2f}) dd={e['dd_mean']:.0f}{extra}")
    print("  判定(機械):", verdict["verdict"], "| d2", verdict["by_d"]["d2"], "| d3", verdict["by_d"]["d3"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
