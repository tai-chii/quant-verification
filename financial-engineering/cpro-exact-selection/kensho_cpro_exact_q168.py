#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q168: FX 15銘柄 D1 TSMOM L=5〜300 の参照日数選択で、CPRO 本式（Yang 2026 TradeGrad の
GitHub 実装式）が、Q141 の近似（B: 下位 20% 平均、C: 平均 − MDD/日数）やランダムより、翌年の最大下落を
浅くするか。
================================================================================

【出典】
- Yang ほか 2026（arXiv 2510.XXXX）TradeGrad: Trading Strategy Optimization via Textual Gradient。
  §CPRO と GitHub `src/loss.py` + `src/evaluate.py`。本文入手は Q167。
- Q141 スクリプト（`../bad-period-weighted-selection/kensho_bad_period_weighted_selection_q141.py`）: 設計の
  雛形。選択窓・コスト・判定の鉄則をそのまま踏襲し、D のみ差し替える。
- Q166-C2: 接続ログ「CPRO の近似ではなく本体式で測り直す」。

【仮説（測る前に固定）】
H: 選択窓で CPRO 本式（下記 D）で L を選ぶと、標本外（翌年）の最大下落が、平均純損益（A）で選んだ
   ときより浅い。かつ純損益は A に劣らない。副: D は Q141 の B・C（近似）とも区別がつく（下落で勝つ）。

【データ】
Q141 と同じ 15 銘柄（FX8 + トレンド7）の `data_<SYM>_D1_fromH1.csv`。無いファイルは除外。

【定義（1通りに固定）】
- 候補 L ∈ {5, 10, …, 300}（60 通り）、TSMOM、翌日ポジション、片道コスト段階1、`pnl_matrix` は Q141 と同じ式。
- 選択窓 = テスト年 t の直前 3 暦年（t−3, t−2, t−1）、拡大しない固定窓。
- 目的関数:
    A = 日次 pnl の平均（Q141 と同じ）
    B = 下位 20% の日の平均 CVaR 型（Q141 と同じ）
    C = 平均 − MDD/日数（Q141 と同じ）
    D = **CPRO 本式**: 選択窓の 3 暦年を暦年 non-overlapping で区切り、各年に対し
          AR[%]  = 累積 pnl[bp] / 100
          MDD[%] = MDD_bp / 100
          ar_score  = σ(0.11 × (AR_pct − 20))
          mdd_score = σ(−0.22 × (MDD_pct − 15))
          combined  = 100 × ar_score^0.5 × mdd_score^0.5
        CPRO = 下位 ⌈0.3 × N⌉ 窓の combined の平均（N = 選択窓の暦年数 = 3 → 下位 1 窓 = 最悪の年）。
        **gate は 1 に固定**（取引頻度ペナルティは原著の `FREQ_FLOOR`・`FREQ_SHARPNESS` の値が LLM 設定
        依存で TSMOM に当てはめにくいため、入れない。CPRO の AR/MDD 部分だけを問う。）
- 選択窓の必要日数 MIN_SEL=500、暦年当たり MIN_YEAR_DAYS=120（CPRO の各年スコアに必要）。
- 標本外（テスト年）の指標・差・年単位 t: Q141 と同じ。
- 帰無: ランダム L（60 候補から一様）B=300 → 標本外 MDD の平均の分布（Q141 と同じ乱数経路）。

【判定（事前固定・変更禁止）】
D について、前半（t<2017）・後半（t≥2017）それぞれで:
- 標本外 MDD の差（A − D）> 0 で 年単位の t ≥ 2、かつ純損益の差（D − A）の t > −2 → 支持。
- MDD の差の t < 2 → 棄却。
- MDD の t ≥ 2 だが純損益の t ≤ −2 → 未確定。
総合: 前後半とも支持 → D 支持。前半・後半のどちらかで棄却 → D 棄却。それ以外 → 未確定。
副問（B・C との差別化）: D と B、D と C の OOS MDD の年単位 t が ≥ 2 の期間があるかを記述する
（主結論の判定には使わない）。
多重比較: 目的関数 B/C/D × 指標 MDD/pnl × 期間 前半/後半 = 12（判定は MDD × D × 2期間 の 2 本）。

【捨てた案の数】
約4:
 - 選択窓を 6 年にして ⌈0.3×6⌉=2 を取る（paper の正格設定）: 前半（<2017）の標本年が 2 年に減るため不採用。
 - gate を実装（取引回数で割引）: FREQ_FLOOR 等の値が LLM 設定依存で TSMOM に移すと恣意的。入れない。
 - AR を幾何複利に揃える: Q141 の加法 bp 会計と整合しないため、加法で統一（1年の bp 合計は AR[%] の近似）。
 - CVaR のパーセンタイルを 20%・40% で感度: Q141 と重複するため実行しない。

【知識の締め切り】
Claude の知識の締め切り: 2026-06 ごろ。データは 2026-07 まで。目的関数と候補は固定で、相場観は使わない。

【委託の確かめ方】
設計の原型 = Q141（Fable 2026-10-09）。D の実装は Yang 2026 の GitHub コード（`src/loss.py`・
`src/evaluate.py`）を直接参照して書く。実行者は結果 JSON のパスと、D−A の MDD・pnl の年単位 t を本体に返す。

【実装】自己完結・決定的（乱数 seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_cpro_exact_q168.py            （B=300、1 分前後）
      python3 kensho_cpro_exact_q168.py --B 30     （軽い試走）
      python3 kensho_cpro_exact_q168.py --smoke    （合成データ・results/smoke_*、判定には使わない）

【CPRO 式の整合確認（単体テスト・main 冒頭で検査）】
- AR=20, MDD=15 → ar_score=0.5, mdd_score=0.5, combined=100*0.5^0.5*0.5^0.5=50.0。
- AR=100, MDD=0 → ar_score→1, mdd_score→σ(0.22*15)=σ(3.3)≈0.964, combined≈98.2。
- AR=−50, MDD=50 → ar_score=σ(0.11*(−70))=σ(−7.7)≈4.5e−4, mdd_score=σ(−0.22*35)=σ(−7.7)≈4.5e−4,
  combined≈0.045（ごく小さい）。
いずれも GitHub コードと一致（手計算）。
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
    """macOS 共有の NFD 名に対応。"""
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")

FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7

# Q141 と同じ段階1の往復コスト（価格単位）。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LS = list(range(5, 305, 5))
SEL_YEARS = 3
CVAR_Q = 0.20
MIN_SEL, MIN_TEST = 500, 100
MIN_YEAR_DAYS = 120     # CPRO: 各暦年に必要な日数（商い停止年を除く）
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009
OBJS = ["A", "B", "C", "D"]
METRICS = ["mdd", "pnl", "sharpe"]

# CPRO 式の参照値（Yang 2026 TradeGrad GitHub `src/evaluate.py`）
CPRO_AR_REF = 20.0        # ar_score = σ(0.11*(AR_pct − 20))
CPRO_AR_K = 0.11
CPRO_MDD_REF = 15.0       # mdd_score = σ(−0.22*(MDD_pct − 15))
CPRO_MDD_K = 0.22
CPRO_WORST_RATIO = 0.30


# ----------------------------------------------------------------------------- 基本の道具
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


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


def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def mdd_bp(x):
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    cum = np.cumsum(x); peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float((peak - cum).max())


def mdd_matrix(M):
    return np.array([mdd_bp(M[:, j]) for j in range(M.shape[1])])


# ----------------------------------------------------------------------------- ルール（60 候補）
def pnl_matrix(c, cost_rt):
    """Q141 と同じ TSMOM の pnl 行列。"""
    n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    M = np.full((n, len(LS)), np.nan)
    for j, L in enumerate(LS):
        s = np.full(n, np.nan); s[L:] = np.sign(c[L:] - c[:-L])
        pos_prev = np.concatenate([[np.nan], s[:-1]])
        pp = np.where(np.isfinite(pos_prev), pos_prev, 0.0)
        dpos = np.abs(np.diff(np.concatenate([[0.0], pp])))
        pnl = pp * ret * 1e4 - dpos * cost_bp
        pnl[:L + 1] = np.nan
        M[:, j] = pnl
    return M


def cpro_score(pnl_bp_1d):
    """1 候補（1 列）の選択窓 pnl から、各暦年の combined を返して CPRO = 下位 ⌈0.3N⌉ の平均。
    呼び出し元が暦年を切り分けて渡す（この関数は 1 暦年の combined を返す）。"""
    v = pnl_bp_1d[np.isfinite(pnl_bp_1d)]
    if len(v) < MIN_YEAR_DAYS:
        return float("nan")
    ar_pct = float(np.sum(v)) / 100.0           # bp を % に（加法会計）
    mdd_pct = mdd_bp(v) / 100.0                 # 同
    ar_score = sigmoid(CPRO_AR_K * (ar_pct - CPRO_AR_REF))
    mdd_score = sigmoid(-CPRO_MDD_K * (mdd_pct - CPRO_MDD_REF))
    return float(100.0 * math.sqrt(ar_score) * math.sqrt(mdd_score))


def objective_D(sel_years, M_sel):
    """選択窓の pnl 行列（days × 60）と、各行の暦年ラベル sel_years から D（CPRO）を 60 候補分計算。"""
    uy = np.unique(sel_years)
    N = len(uy)
    n_worst = max(1, int(math.ceil(CPRO_WORST_RATIO * N)))
    D = np.full(len(LS), np.nan)
    for j in range(len(LS)):
        col = M_sel[:, j]
        if np.isfinite(col).sum() < MIN_SEL:
            continue
        year_scores = []
        for y in uy:
            yc = col[sel_years == y]
            s = cpro_score(yc)
            year_scores.append(s)
        year_scores = np.asarray(year_scores, float)
        year_scores = year_scores[np.isfinite(year_scores)]
        if len(year_scores) < max(1, N - 1):   # 1 暦年までの欠落は許容、2 以上は不定（候補除外）
            continue
        n_pick = min(n_worst, len(year_scores))
        D[j] = float(np.sort(year_scores)[:n_pick].mean())
    return D


def objectives(sel_years, M_sel):
    """A/B/C/D を 60 候補分で返す。A/B/C は Q141 と同じ。"""
    X = M_sel
    n_ok = np.isfinite(X).sum(axis=0)
    A = np.nanmean(X, axis=0)
    B = np.full(len(LS), np.nan); C = np.full(len(LS), np.nan)
    for j in range(len(LS)):
        col = X[:, j]; col = col[np.isfinite(col)]
        if len(col) < MIN_SEL:
            A[j] = np.nan; continue
        k = max(1, int(math.floor(CVAR_Q * len(col))))
        B[j] = float(np.sort(col)[:k].mean())
        C[j] = float(col.mean() - mdd_bp(col) / len(col))
    A = np.where(n_ok >= MIN_SEL, A, np.nan)
    D = objective_D(sel_years, X)
    return dict(A=A, B=B, C=C, D=D)


def oos_metrics(Y):
    n_ok = np.isfinite(Y).sum(axis=0)
    mu = np.nanmean(Y, axis=0); sd = np.nanstd(Y, axis=0, ddof=1)
    sharpe = np.where(sd > 0, mu / sd * math.sqrt(252), np.nan)
    mdd = mdd_matrix(Y)
    ok = n_ok >= MIN_TEST
    return dict(mdd=np.where(ok, mdd, np.nan), pnl=np.where(ok, mu, np.nan),
                sharpe=np.where(ok, sharpe, np.nan), n_ok=n_ok)


def build_cells(series):
    cells, oos_all = [], {}
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        M = pnl_matrix(c, COST_RT[sym])
        for yt in np.unique(years):
            sel = (years >= yt - SEL_YEARS) & (years < yt)
            tst = years == yt
            if sel.sum() < MIN_SEL or tst.sum() < MIN_TEST:
                continue
            obj = objectives(years[sel], M[sel])
            if not np.isfinite(obj["A"]).any():
                continue
            oos = oos_metrics(M[tst])
            rec = dict(sym=sym, year=int(yt), n_sel=int(sel.sum()), n_test=int(tst.sum()))
            ok_any = False
            for o in OBJS:
                v = obj[o]
                if not np.isfinite(v).any():
                    rec[f"L_{o}"] = np.nan
                    for m in METRICS:
                        rec[f"{m}_{o}"] = np.nan
                    continue
                j = int(np.nanargmax(v))
                rec[f"L_{o}"] = LS[j]
                for m in METRICS:
                    rec[f"{m}_{o}"] = float(oos[m][j])
                ok_any = ok_any or np.isfinite(oos["mdd"][j])
            if not ok_any:
                continue
            cells.append(rec)
            oos_all[(sym, int(yt))] = oos
    return pd.DataFrame(cells), oos_all


def summarize(tab, syms, period):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    out = {"n_cells": int(len(g)), "n_years": int(g.year.nunique())}
    for o in OBJS:
        out[o] = {m: float(np.nanmean(g[f"{m}_{o}"])) if len(g) else float("nan") for m in METRICS}
        out[o]["L_median"] = float(np.nanmedian(g[f"L_{o}"])) if len(g) else float("nan")
    for o in ("B", "C", "D"):
        d = {}
        for m, sign in (("mdd", -1.0), ("pnl", 1.0), ("sharpe", 1.0)):
            diff = sign * (g[f"{m}_{o}"] - g[f"{m}_A"])
            per_year = pd.DataFrame({"year": g.year, "d": diff}).dropna().groupby("year")["d"].mean()
            mu, tt, ny = mean_t(per_year.values)
            d[m] = dict(diff_mean=float(np.nanmean(diff)) if len(g) else float("nan"),
                        diff_year_mean=mu, t_year=tt, n_years=ny,
                        share_better=float((diff > 0).mean()) if len(g) else float("nan"))
        out[f"{o}_minus_A"] = d
    # 副: D と B、D と C の差（記述のみ・判定には使わない）
    for pair in (("D", "B"), ("D", "C")):
        o1, o2 = pair; d = {}
        for m, sign in (("mdd", -1.0), ("pnl", 1.0), ("sharpe", 1.0)):
            diff = sign * (g[f"{m}_{o1}"] - g[f"{m}_{o2}"])
            per_year = pd.DataFrame({"year": g.year, "d": diff}).dropna().groupby("year")["d"].mean()
            mu, tt, ny = mean_t(per_year.values)
            d[m] = dict(diff_year_mean=mu, t_year=tt, n_years=ny,
                        share_better=float((diff > 0).mean()) if len(g) else float("nan"))
        out[f"{o1}_minus_{o2}"] = d
    return out


def null_mdd_means(tab, oos_all, syms, period, B, rng):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    keys = [(s, y) for s, y in zip(g.sym, g.year) if (s, y) in oos_all]
    if not keys:
        return np.array([]), np.array([])
    MDD = np.array([oos_all[k]["mdd"] for k in keys]); PNL = np.array([oos_all[k]["pnl"] for k in keys])
    out_m, out_p = np.zeros(B), np.zeros(B)
    valid = np.isfinite(MDD)
    for b in range(B):
        picks = np.array([rng.choice(np.flatnonzero(valid[i])) if valid[i].any() else -1 for i in range(len(keys))])
        sel = picks >= 0
        out_m[b] = MDD[np.flatnonzero(sel), picks[sel]].mean()
        out_p[b] = PNL[np.flatnonzero(sel), picks[sel]].mean()
    return out_m, out_p


def evaluate(tab, oos_all, B, rng):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    res = {}
    for gname, syms in groups.items():
        for per in ("前半", "後半", "全期間"):
            o = summarize(tab, syms, per)
            nm, npn = null_mdd_means(tab, oos_all, syms, per, B, rng)
            o["null_random_L"] = dict(mdd_mean=float(nm.mean()) if len(nm) else float("nan"),
                                      mdd_p05=float(np.percentile(nm, 5)) if len(nm) else float("nan"),
                                      pnl_mean=float(npn.mean()) if len(npn) else float("nan"))
            for ob in OBJS:
                z, pct = z_against_null(o[ob]["mdd"], nm)
                o[ob]["mdd_z_vs_random"] = z; o[ob]["mdd_pct_vs_random"] = pct
                z2, pct2 = z_against_null(o[ob]["pnl"], npn)
                o[ob]["pnl_z_vs_random"] = z2; o[ob]["pnl_pct_vs_random"] = pct2
            res[f"{gname}|{per}"] = o
    return res


def judge(res):
    def one(r, o):
        d = r[f"{o}_minus_A"]
        tm, tp = d["mdd"]["t_year"], d["pnl"]["t_year"]
        if not (np.isfinite(tm) and np.isfinite(tp)):
            return "判定不能"
        if d["mdd"]["diff_year_mean"] > 0 and tm >= 2.0 and tp > -2.0:
            return "支持（下落を抑える）"
        if tm < 2.0:
            return "棄却"
        return "未確定（下落は浅いが損益で劣る）"
    by_D = {per: one(res[f"全15|{per}"], "D") for per in ("前半", "後半")}
    # 主結論は D のみ。B・C も比較のため記述。
    by_BC = {o: {per: one(res[f"全15|{per}"], o) for per in ("前半", "後半")} for o in ("B", "C")}
    sup = all(v.startswith("支持") for v in by_D.values())
    rej = any(v == "棄却" for v in by_D.values())
    if sup:
        verdict = "支持: CPRO 本式で選んだ順張りは翌年の最大下落を浅くする"
    elif rej:
        verdict = "棄却: CPRO 本式でも翌年の最大下落は A と区別がつかない"
    else:
        verdict = "未確定"
    return dict(by_D=by_D, by_BC_reference=by_BC, supported=sup, verdict=verdict,
                thresholds=dict(t_mdd=2.0, t_pnl_floor=-2.0),
                note="判定対象は D のみ（事前固定）。B・C は Q141 の近似の参照値として併記。解釈は実行者が記録する。")


def make_plot(res, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for p in ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
            if os.path.exists(p):
                font_manager.fontManager.addfont(p)
                matplotlib.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name(); break
        matplotlib.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(1, 3, figsize=(14, 4.3))
        pers = ["前半", "後半", "全期間"]; x = np.arange(len(pers))
        for a, m, lab in zip(ax, METRICS, ("標本外 最大下落 bp（小さいほど良い）",
                                            "標本外 純損益 bp/日", "標本外 シャープ")):
            for k, o in enumerate(OBJS):
                a.bar(x + (k - 1.5) * .20, [res[f"全15|{p}"][o][m] for p in pers], width=.20, label=o)
            if m == "mdd":
                a.plot(x, [res[f"全15|{p}"]["null_random_L"]["mdd_mean"] for p in pers], "kx",
                       label="ランダム L")
            a.set_xticks(x); a.set_xticklabels(pers); a.set_title(lab); a.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def _unit_tests():
    """CPRO 式の基準点を確認（AR=20, MDD=15 → 50）。"""
    tol = 1e-9
    s1 = 100.0 * math.sqrt(sigmoid(CPRO_AR_K * (20 - 20))) * math.sqrt(sigmoid(-CPRO_MDD_K * (15 - 15)))
    assert abs(s1 - 50.0) < tol, f"CPRO 基準点が 50 ではない: {s1}"
    # 大儲け（AR=100, MDD=0）
    s2 = 100.0 * math.sqrt(sigmoid(CPRO_AR_K * (100 - 20))) * math.sqrt(sigmoid(-CPRO_MDD_K * (0 - 15)))
    assert s2 > 95.0, f"大儲け時に 95 を超えない: {s2}"
    # 大損（AR=−50, MDD=50）
    s3 = 100.0 * math.sqrt(sigmoid(CPRO_AR_K * (-50 - 20))) * math.sqrt(sigmoid(-CPRO_MDD_K * (50 - 15)))
    assert s3 < 1.0, f"大損時に 1 を下回らない: {s3}"


def main():
    _unit_tests()
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    warnings.simplefilter("ignore", RuntimeWarning)
    rng = np.random.default_rng(SEED)

    series, missing = {}, {}
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
            for i in range(1, len(dates)):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20,
                    "WTI": 60, "UKOIL": 65, "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
            if not os.path.exists(f):
                missing[sym] = "ファイルなし"; continue
            try:
                d = load_daily(sym)
            except Exception as e:
                missing[sym] = str(e); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B

    tab, oos_all = build_cells(series)
    res = evaluate(tab, oos_all, B, rng)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q168_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q168_bars_{stamp}.png"))
    out = dict(
        queue_id="Q168", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, SEL_YEARS=SEL_YEARS, CVAR_Q=CVAR_Q, MIN_SEL=MIN_SEL, MIN_TEST=MIN_TEST,
                      MIN_YEAR_DAYS=MIN_YEAR_DAYS, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      objectives=dict(A="mean", B=f"lowest {CVAR_Q:.0%} days mean (CVaR)",
                                      C="mean − MDD/days",
                                      D=f"CPRO: lowest ⌈{CPRO_WORST_RATIO:.0%}×N⌉ calendar-year combined score "
                                        f"(gate=1, AR_ref={CPRO_AR_REF}, MDD_ref={CPRO_MDD_REF})"),
                      null="各 (銘柄, 年) で L を一様ランダムに選ぶ（B 回）→ 標本外 MDD の平均の分布",
                      cpro_formula=dict(ar_score="sigmoid(0.11*(AR_pct - 20))",
                                        mdd_score="sigmoid(-0.22*(MDD_pct - 15))",
                                        combined="100 * ar_score^0.5 * mdd_score^0.5 * gate",
                                        gate=1.0,
                                        aggregation=f"mean of lowest ceil(0.3*N) calendar-year scores (N={SEL_YEARS})")),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()),
                           end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        missing=missing, n_symbols_used=len(series), n_cells=int(len(tab)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, bars_png=png_path),
        multiple_comparisons="目的関数 B/C/D × 指標 MDD/pnl × 期間 2 ＝ 12（判定は MDD × D × 2期間 ＝ 2）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q168_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1,
                  default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))

    print(f"[Q168] cells={len(tab)}  B={B}  smoke={args.smoke}  missing={list(missing)}")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_cells']:3d}  " + "  ".join(
                f"{o}: mdd={r[o]['mdd']:.0f} pnl={r[o]['pnl']:+.2f} sh={r[o]['sharpe']:+.2f} L={r[o]['L_median']:.0f}"
                for o in OBJS)
                  + f"  | random L mdd={r['null_random_L']['mdd_mean']:.0f}")
            for o in ("B", "C", "D"):
                d = r[f"{o}_minus_A"]
                print(f"        {o}−A: mdd(A−{o})={d['mdd']['diff_year_mean']:+.1f}bp t={d['mdd']['t_year']:+.2f}  "
                      f"pnl={d['pnl']['diff_year_mean']:+.2f} t={d['pnl']['t_year']:+.2f}  "
                      f"sharpe={d['sharpe']['diff_year_mean']:+.2f} t={d['sharpe']['t_year']:+.2f}  "
                      f"(better share mdd={d['mdd']['share_better']:.2f})")
    print("  判定(機械・D):", verdict["verdict"], "|", verdict["by_D"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
