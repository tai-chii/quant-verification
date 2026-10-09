#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q141: 悪い時期を重くする目的関数で選んだ順張りは、標本外の最大下落が小さいか（TradeGrad の CPRO の型）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q141（Fable 2026-10-09）＝ アイデア候補.md の行。
- 論文ノート: Yang ほか 2026_TradeGrad_テキスト勾配による売買戦略の最適化（要旨: 悪い時期を重く見る CPRO。本文未読のため
  「型」だけ借りる）。
- Tokajuk・Chudziak 2026（目的関数の比較は水準と順位を分ける）。

【仮説（測る前に固定）】
H: 選択期間で「悪い時期を重くする」目的関数（B: 下位 20% の日の平均、C: 平均 − 最大下落/日数）で参照日数 L を選ぶと、
   標本外（翌年）の最大下落が、平均純損益（A）で選んだときより浅い。かつ純損益は A に劣らない。

【データ】
15銘柄 `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足。値動きのない足は除く）。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 候補 = TSMOM の参照日数 L ∈ {5, 10, …, 300}（60 通り）。s_t = sign(c_t − c_{t−L})、翌日のポジション。
  日次純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（COST_RT/2 を bp 換算）。L 日未満の日は未定義（nan）。
- 選択窓 = テスト年 t の直前 3 暦年（t−3, t−2, t−1。拡大しない固定窓）。テスト = 年 t（標本外）。
  選択窓の定義済み日数が MIN_SEL=500 未満、またはテスト年が MIN_TEST=100 未満の (銘柄, t) は捨てる。
- 目的関数（選択窓の日次純損益 x から）:
  A = mean(x)、B = 下位 20% の日の平均（CVaR 型）、C = mean(x) − MDD(x)/len(x)。
  MDD = 累積和（bp）の山からの最大下落（bp・正の値で深さ）。各目的関数で最大の L を選ぶ。
- 標本外の指標（テスト年）: 最大下落 MDD [bp]、純損益の平均 [bp/日]、シャープ = mean/sd × √252。
- 差 = 対応あり（同じ (銘柄, t)）の B − A、C − A。最大下落は「A − B」（正なら B が浅い）。
  年を単位の t: 年ごとに銘柄平均 → 年数で t。

【測るもの】
期間: 前半（t < 2017）／後半（t ≥ 2017）／全期間。群: 全15・FX8・トレンド7（判定は全15）。
各目的関数の標本外指標の平均、差の平均と年単位の t、選んだ L の分布、帰無（ランダムな L）の標本外 MDD の分布に対する
各目的関数の z・パーセンタイル。

【帰無】
選択をランダムにした L（各 (銘柄, t) で 60 候補から一様に 1 つ）B=300 → 標本外の最大下落の分布（平均の分布）。

【判定（事前固定・変更禁止）】
目的関数 X ∈ {B, C} ごと、前半・後半のそれぞれで:
- 標本外 MDD の差（A − X）> 0 で 年単位の t ≥ 2、かつ 純損益の差（X − A）の t > −2 → X は「悪い時期を重くする選択は下落を抑える」。
- MDD の差の t < 2 → 棄却。
- MDD の t ≥ 2 だが純損益の t ≤ −2 → 未確定（下落は浅いが損益で劣る）。
総合: B か C のどちらかが前半・後半とも支持なら「支持」。両方とも前後半のどこかで棄却なら「棄却」。それ以外は未確定。
多重比較: 目的関数 3 × 指標 3 ＝ 9（判定は MDD と純損益の差 × 2 目的関数 × 2 期間）。

【捨てた案の数】
約5: 拡大窓で選ぶ案（登録は固定 3 年）、B の分位を 10%・30% でも出す案（感度は実行者が別途）、C を Calmar 比にする案
（比は分母が 0 近くで暴れる → 差の形）、シャープで選ぶ目的関数を加える案（3 本固定）、選択窓を 5 年にする案（前半の標本が減る）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。目的関数と候補は固定で、相場観は使わない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude Fable 5.1（この下請け）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（B−A・C−A の MDD と純損益の差・t・前後半）・原典（TradeGrad 要旨）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定のランダム選択だけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_bad_period_weighted_selection_q141.py            （B=300、1 分前後）
      python3 kensho_bad_period_weighted_selection_q141.py --B 30     （軽い試走）
      python3 kensho_bad_period_weighted_selection_q141.py --smoke    （合成データで経路の確認。結果は results/smoke_*）
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
# 段階1の保守的な往復コスト（価格単位）。kensho_donchian_regime.py と同じ値。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LS = list(range(5, 305, 5))
SEL_YEARS = 3
CVAR_Q = 0.20
MIN_SEL, MIN_TEST = 500, 100
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009
OBJS = ["A", "B", "C"]
METRICS = ["mdd", "pnl", "sharpe"]


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


def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def mdd_bp(x):
    """累積和の山からの最大下落（bp・正の深さ）。nan は 0 として扱わず除く。"""
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    cum = np.cumsum(x); peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    return float((peak - cum).max())


def mdd_matrix(M):
    """列ごとの MDD（nan は行ごとに全列同じ位置と仮定せず、列ごとに除く）。"""
    return np.array([mdd_bp(M[:, j]) for j in range(M.shape[1])])


# ----------------------------------------------------------------------------- ルール（60 候補をまとめて）
def pnl_matrix(c, cost_rt):
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


def objectives(X):
    """選択窓の純損益行列 X (days × 60) → A, B, C（各 60）。未定義が多い候補は nan。"""
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
    return dict(A=A, B=B, C=C)


def oos_metrics(Y):
    """テスト年の純損益行列 Y (days × 60) → mdd, pnl, sharpe（各 60）。"""
    n_ok = np.isfinite(Y).sum(axis=0)
    mu = np.nanmean(Y, axis=0); sd = np.nanstd(Y, axis=0, ddof=1)
    sharpe = np.where(sd > 0, mu / sd * math.sqrt(252), np.nan)
    mdd = mdd_matrix(Y)
    ok = n_ok >= MIN_TEST
    return dict(mdd=np.where(ok, mdd, np.nan), pnl=np.where(ok, mu, np.nan), sharpe=np.where(ok, sharpe, np.nan), n_ok=n_ok)


# ----------------------------------------------------------------------------- 本体の表
def build_cells(series):
    """(銘柄, テスト年) ごとに: 選んだ L（A/B/C）、標本外指標（選んだ L）と全候補の標本外指標（帰無用）。"""
    cells, oos_all = [], {}
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        M = pnl_matrix(c, COST_RT[sym])
        for yt in np.unique(years):
            sel = (years >= yt - SEL_YEARS) & (years < yt)
            tst = years == yt
            if sel.sum() < MIN_SEL or tst.sum() < MIN_TEST:
                continue
            obj = objectives(M[sel])
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
    for o in ("B", "C"):
        d = {}
        # MDD: A − X（正なら X が浅い）。純損益・シャープ: X − A。
        for m, sign in (("mdd", -1.0), ("pnl", 1.0), ("sharpe", 1.0)):
            diff = sign * (g[f"{m}_{o}"] - g[f"{m}_A"])
            per_year = pd.DataFrame({"year": g.year, "d": diff}).dropna().groupby("year")["d"].mean()
            mu, tt, ny = mean_t(per_year.values)
            d[m] = dict(diff_mean=float(np.nanmean(diff)) if len(g) else float("nan"), diff_year_mean=mu, t_year=tt, n_years=ny,
                        share_better=float((diff > 0).mean()) if len(g) else float("nan"))
        out[f"{o}_minus_A"] = d
    return out


def null_mdd_means(tab, oos_all, syms, period, B, rng):
    """ランダムな L の標本外 MDD の平均（セル平均）の分布。pnl の平均も添える。"""
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    keys = [(s, y) for s, y in zip(g.sym, g.year) if (s, y) in oos_all]
    if not keys:
        return np.array([]), np.array([])
    MDD = np.array([oos_all[k]["mdd"] for k in keys]); PNL = np.array([oos_all[k]["pnl"] for k in keys])
    # 各セルで定義済みの候補だけから一様に選ぶ
    out_m, out_p = np.zeros(B), np.zeros(B)
    valid = np.isfinite(MDD)
    for b in range(B):
        picks = np.array([rng.choice(np.flatnonzero(valid[i])) if valid[i].any() else -1 for i in range(len(keys))])
        sel = picks >= 0
        out_m[b] = MDD[np.flatnonzero(sel), picks[sel]].mean(); out_p[b] = PNL[np.flatnonzero(sel), picks[sel]].mean()
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
                o[ob]["mdd_z_vs_random"] = z; o[ob]["mdd_pct_vs_random"] = pct   # pct 小 = 浅い側
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
    by = {o: {per: one(res[f"全15|{per}"], o) for per in ("前半", "後半")} for o in ("B", "C")}
    sup = {o: all(v.startswith("支持") for v in by[o].values()) for o in by}
    rej = {o: any(v == "棄却" for v in by[o].values()) for o in by}
    if sup["B"] or sup["C"]:
        verdict = "支持: 悪い時期を重くする選択は下落を抑える（" + "・".join(o for o in by if sup[o]) + "）"
    elif rej["B"] and rej["C"]:
        verdict = "棄却（B・C とも最大下落の差の t<2 の期間あり）"
    else:
        verdict = "未確定"
    return dict(by_objective_period=by, supported=sup, verdict=verdict, thresholds=dict(t_mdd=2.0, t_pnl_floor=-2.0),
                note="事前固定の規則で機械的に付けた判定（全15・年単位の t）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
        fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
        pers = ["前半", "後半", "全期間"]; x = np.arange(len(pers))
        for a, m, lab in zip(ax, METRICS, ("標本外 最大下落 bp（小さいほど良い）", "標本外 純損益 bp/日", "標本外 シャープ")):
            for k, o in enumerate(OBJS):
                a.bar(x + (k - 1) * .27, [res[f"全15|{p}"][o][m] for p in pers], width=.27, label=o)
            if m == "mdd":
                a.plot(x, [res[f"全15|{p}"]["null_random_L"]["mdd_mean"] for p in pers], "kx", label="ランダム L")
            a.set_xticks(x); a.set_xticklabels(pers); a.set_title(lab); a.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無（ランダム L）の回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
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
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
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
    csv_path = os.path.join(OUT, f"{prefix}Q141_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q141_bars_{stamp}.png"))
    out = dict(
        queue_id="Q141", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, SEL_YEARS=SEL_YEARS, CVAR_Q=CVAR_Q, MIN_SEL=MIN_SEL, MIN_TEST=MIN_TEST, SPLIT_YEAR=SPLIT_YEAR,
                      NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      objectives=dict(A="mean", B=f"lowest {CVAR_Q:.0%} days mean (CVaR)", C="mean − MDD/days"),
                      null="各 (銘柄, 年) で L を一様ランダムに選ぶ（B 回）→ 標本外 MDD の平均の分布"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        missing=missing, n_symbols_used=len(series), n_cells=int(len(tab)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, bars_png=png_path),
        multiple_comparisons="目的関数 3 × 指標 3 ＝ 9（判定は MDD と純損益の差 × 目的関数 B/C × 期間 2）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q141_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))

    print(f"[Q141] cells={len(tab)}  B={B}  smoke={args.smoke}  missing={list(missing)}")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_cells']:3d}  " + "  ".join(
                f"{o}: mdd={r[o]['mdd']:.0f} pnl={r[o]['pnl']:+.2f} sh={r[o]['sharpe']:+.2f} L={r[o]['L_median']:.0f}" for o in OBJS)
                  + f"  | random L mdd={r['null_random_L']['mdd_mean']:.0f}")
            for o in ("B", "C"):
                d = r[f"{o}_minus_A"]
                print(f"        {o}−A: mdd(A−{o})={d['mdd']['diff_year_mean']:+.1f}bp t={d['mdd']['t_year']:+.2f}  pnl={d['pnl']['diff_year_mean']:+.2f} t={d['pnl']['t_year']:+.2f}  "
                      f"sharpe={d['sharpe']['diff_year_mean']:+.2f} t={d['sharpe']['t_year']:+.2f}  (better share mdd={d['mdd']['share_better']:.2f})")
    print("  判定(機械):", verdict["verdict"], "|", verdict["by_objective_period"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
