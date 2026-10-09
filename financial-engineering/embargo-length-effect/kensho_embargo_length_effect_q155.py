#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q155: 検証とテストの間のエンバーゴ日数で順張りの標本外成績はどれだけ変わるか（Siper 2026 の評価の作法）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q155（Fable 2026-10-09）。アイデア候補.md の該当行。
- 論文ノート: Siper2026_方策探索の表現を変えるとLLMの売買方針探索は効率が上がるか（ローリングオリジン 5 分割・10 日
  エンバーゴ・Holm）、Baileyほか2017_バックテスト過剰適合の確率、kaggle 版 改善判定（embargo の偽陽性の実例 2026-09-08）。
  → 「選択期間とテスト期間の間に e 日の空白を置くと、選んだ順張りの標本外成績はどれだけ動くか。e=0 は楽観か」。

【仮説（測る前に固定）】
H1: e=0（空白なし）で選んだ L のテスト純損益は、e=20 で選んだものより高い（e=0 は楽観）＝差が e について単調に減る。
H0（規則の帰結）: 差の |t|<2 かつ単調でなければ、この規則ではエンバーゴは結論を変えない。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無い銘柄は除いて件数を JSON に書く。

【定義（1通りに固定）】
- 候補 = TSMOM の参照日数 L ∈ {5,10,…,300}（60 通り）。s_t = sign(c_t − c_{t−L})、翌日のポジション = s_t（買い・売り両方）。
- 日次純損益 [bp] = pos × (c_t/c_{t−1} − 1) × 1e4 − |Δpos| × 片道コスト[bp]（段階1の往復 COST_RT の半分）。
- ローリングオリジン: テスト期間 = 暦年 Y（その銘柄の営業日が TEST_MIN_DAYS=100 以上）。選択期間 = テスト開始の
  e 営業日前で終わる直前の SEL_DAYS=756 営業日（3 年）。e ∈ {0, 1, 5, 10, 20, 60}。テスト期間は e によらず同じ（対応ありの差が
  テスト期間の違いを含まないようにする）。選択期間の先頭が t ≤ 300（全 L が定義されない）なら、その (銘柄, 年) は捨てる。
- 選択 = 選択期間の平均純損益 [bp/日] が最大の L（同点は小さい L）。
- テストの量 = テスト年の平均純損益 [bp/日] と最大下落 [bp]（テスト年内の累積純損益の高値からの最大の落ち）。
- 集計 = 年ごとに銘柄平均 → 年を単位に平均と t（対応ありの差 e − e=0 も同様）。全15・FX8・トレンド7、
  テスト年 前半(<2017)/後半(≥2017) でも出す（記述）。
- L の大きさ別: e=0 で選ばれた L を {≤50, 51〜150, >150} に分け、差 (e=20 − e=0) の平均と (銘柄, 年) をプールした t。
  あわせて e=0 と e の選択 L が一致した割合。
- 帰無: L をランダムに選ぶ（各 (銘柄, 年) で一様）B=300 回 → 年を単位に集計したテスト純損益の分布。選択の効果が
  0 のときの水準。各 e の観測値の z を出す（e によらず同じ分布）。

【測るもの】
e ごとのテスト純損益・最大下落（年単位の平均・t）、e=0 との対応ありの差の平均・t、e に対する単調性
（6 点の Spearman）、L の大きさ別の差、帰無に対する z。

【判定（事前固定・変更禁止）】
e=0 と e=20 のテスト純損益の差の |t|<2 かつ 単調でなければ（|Spearman(e, 平均純損益)| < 0.8）
「エンバーゴは結論を変えない（この規則では）」。
差が単調（|Spearman| ≥ 0.8）で |t| ≥ 2 かつ e=20 − e=0 < 0 なら「e=0 は楽観」＝基盤の決まりに e≥L を追加する根拠。
（登録の文言「Spearman ≥0.8 で t≥2」は、差の向き＝e=0 が良い方向を想定したものとして、符号を明示して実装。
 単調で |t|≥2 だが e=20 の方が良い場合は「e=0 は悲観（想定外）」として記述。それ以外は「どちらにも当てはまらない」。）

【捨てた案の数】
約5: 選択期間を固定してテスト期間を e だけ後ろにずらす案（テスト期間が変わり対応ありの差にならない）、拡大窓の選択
（3 年固定窓に統一）、選択の目的関数にシャープを使う案（平均純損益 1 本）、Holm での個別有意判定（問いは差の t）、
e を L の関数（e=L）にする案（登録の 6 点に固定・L 別の差で代替）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。エンバーゴの効果は選択とテストの機械的な手順で決まり、
相場観の後知恵では作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、下請け）。実行と解釈は後で Sonnet／Opus。
実行者は結論ではなく、JSON のパス・e ごとの純損益と差の t・Spearman・原典の箇所（Siper 2026 の目次、kaggle 版 改善判定）を本体に返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_embargo_length_effect_q155.py            （B=300、1 分前後）
      python3 kensho_embargo_length_effect_q155.py --B 30     （軽い試走）
      python3 kensho_embargo_length_effect_q155.py --smoke    （合成データで経路の確認。結果は捨てる）
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

LS = list(range(5, 301, 5))
LMAX = max(LS)
EMBARGOS = [0, 1, 5, 10, 20, 60]
SEL_DAYS = 756
TEST_MIN_DAYS = 100
SPLIT_YEAR = 2017
L_BINS = [(0, 50, "L<=50"), (51, 150, "51<=L<=150"), (151, 300, "L>150")]
NULL_B = 300
SEED = 20261009


# ----------------------------------------------------------------------------- 基本の道具
def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    rx = pd.Series(x).rank().values; ry = pd.Series(y).rank().values
    rx = rx - rx.mean(); ry = ry - ry.mean()
    d = math.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


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


def pnl_matrix(c, cost_rt):
    """n × 60 の日次純損益 [bp]（TSMOM、買い売り両方）。"""
    n = len(c)
    S = np.zeros((n, len(LS)))
    for j, L in enumerate(LS):
        S[L:, j] = np.sign(c[L:] - c[:-L])
    pos = np.vstack([np.zeros((1, len(LS))), S[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos * ret[:, None] * 1e4
    dpos = np.abs(np.diff(np.vstack([np.zeros((1, len(LS))), pos]), axis=0))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    return gross - dpos * cost_bp[:, None]


# ----------------------------------------------------------------------------- ローリングオリジン
def rolling_cells(sym, t, P):
    """(銘柄, テスト年) ごとに、e ごとの 選択 L・テスト純損益・最大下落 と、全 L のテスト純損益（帰無用）を返す。"""
    years = pd.DatetimeIndex(t).year.values
    rows = []
    for Y in np.unique(years):
        test = np.flatnonzero(years == Y)
        if len(test) < TEST_MIN_DAYS:
            continue
        i0 = int(test[0])
        row = dict(sym=sym, year=int(Y), n_test=int(len(test)))
        ok = True
        for e in EMBARGOS:
            a, b = i0 - e - SEL_DAYS, i0 - e
            if a <= LMAX:
                ok = False; break
            sel_mean = P[a:b].mean(axis=0)
            j = int(np.argmax(sel_mean))            # 同点は小さい L
            row[f"L_e{e}"] = LS[j]
            row[f"pnl_e{e}"] = float(P[test, j].mean())
            row[f"dd_e{e}"] = max_drawdown_bp(P[test, j])
            row[f"selpnl_e{e}"] = float(sel_mean[j])
        if not ok:
            continue
        row["test_pnl_all_L"] = P[test].mean(axis=0)   # 帰無用（60,）
        rows.append(row)
    return rows


def aggregate(tab, syms, year_lo=None, year_hi=None):
    g = tab[tab.sym.isin(syms)]
    if year_lo is not None:
        g = g[g.year >= year_lo]
    if year_hi is not None:
        g = g[g.year < year_hi]
    out = {"n_cells": int(len(g)), "n_years": int(g.year.nunique())}
    if len(g) == 0:
        return out
    per_year = g.groupby("year")
    by_e = {}
    for e in EMBARGOS:
        m, tt, n = mean_t(per_year[f"pnl_e{e}"].mean().values)
        md, _, _ = mean_t(per_year[f"dd_e{e}"].mean().values)
        d = {"pnl_mean": m, "pnl_t": tt, "dd_mean": md, "L_mean": float(g[f"L_e{e}"].mean()),
             "share_same_L_as_e0": float((g[f"L_e{e}"] == g["L_e0"]).mean())}
        if e != 0:
            diff = (g[f"pnl_e{e}"] - g["pnl_e0"]).groupby(g.year).mean().values
            dm, dt, dn = mean_t(diff)
            ddiff = (g[f"dd_e{e}"] - g["dd_e0"]).groupby(g.year).mean().values
            d.update(diff_vs_e0_mean=dm, diff_vs_e0_t=dt, diff_dd_vs_e0_mean=mean_t(ddiff)[0])
        by_e[str(e)] = d
    out["by_e"] = by_e
    out["spearman_e_vs_pnl"] = spearman(EMBARGOS, [by_e[str(e)]["pnl_mean"] for e in EMBARGOS])
    out["spearman_e_vs_dd"] = spearman(EMBARGOS, [by_e[str(e)]["dd_mean"] for e in EMBARGOS])
    # L の大きさ別（e=0 の選択 L で分ける）: 差 (e=20 − e=0)
    by_L = {}
    for lo, hi, name in L_BINS:
        h = g[(g.L_e0 >= lo) & (g.L_e0 <= hi)]
        if len(h) == 0:
            by_L[name] = dict(n=0); continue
        diff = (h.pnl_e20 - h.pnl_e0).values
        m, tt, n = mean_t(diff)
        by_L[name] = dict(n=int(len(h)), diff_e20_vs_e0_mean=m, diff_t_pooled=tt,
                          share_same_L=float((h.L_e20 == h.L_e0).mean()))
    out["by_L_bin_e0"] = by_L
    return out


def judge(agg):
    e20 = agg["by_e"]["20"]
    t20 = e20["diff_vs_e0_t"]; d20 = e20["diff_vs_e0_mean"]; rho = agg["spearman_e_vs_pnl"]
    mono = np.isfinite(rho) and abs(rho) >= 0.8
    sig = np.isfinite(t20) and abs(t20) >= 2.0
    if (not sig) and (not mono):
        v = "エンバーゴは結論を変えない（この規則では）"
    elif mono and sig and d20 < 0:
        v = "e=0 は楽観（基盤の決まりに e≥L を追加する根拠）"
    elif mono and sig and d20 > 0:
        v = "e=0 は悲観（想定外・記述）"
    else:
        v = "どちらの規則にも当てはまらない（単調か有意の片方だけ）"
    return dict(diff_e20_vs_e0_mean=d20, diff_e20_vs_e0_t=t20, spearman_e_vs_pnl=rho, monotone=bool(mono), significant=bool(sig),
                verdict=v, note="事前固定の規則で機械的に付けた判定（全15・全テスト年）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
        for g in ("全15", "FX8", "トレンド7"):
            a = res[f"{g}|全期間"]
            if "by_e" not in a:
                continue
            ax[0].plot(EMBARGOS, [a["by_e"][str(e)]["pnl_mean"] for e in EMBARGOS], "-o", label=g)
            ax[1].plot(EMBARGOS, [a["by_e"][str(e)]["dd_mean"] for e in EMBARGOS], "-o", label=g)
        ax[0].set_xlabel("エンバーゴ e（営業日）"); ax[0].set_ylabel("テスト純損益（bp/日・年平均）"); ax[0].axhline(0, lw=.6, c="k"); ax[0].legend()
        ax[1].set_xlabel("エンバーゴ e（営業日）"); ax[1].set_ylabel("テスト最大下落（bp・年平均）"); ax[1].legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無（ランダムな L）の回数")
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

    rows = []
    for sym, (t, c) in series.items():
        rows.extend(rolling_cells(sym, t, pnl_matrix(c, COST_RT[sym])))
    tab = pd.DataFrame(rows)
    if len(tab) == 0:
        print("[Q155] セルがありません"); sys.exit(1)
    all_L = np.vstack(tab.pop("test_pnl_all_L").values)      # cells × 60

    groups = {"全15": [s for s in SYMS if s in series], "FX8": [s for s in FX8 if s in series], "トレンド7": [s for s in TREND7 if s in series]}
    periods = {"全期間": (None, None), "前半": (None, SPLIT_YEAR), "後半": (SPLIT_YEAR, None)}
    res = {}
    for gname, syms in groups.items():
        for pname, (lo, hi) in periods.items():
            res[f"{gname}|{pname}"] = aggregate(tab, syms, lo, hi)

    # 帰無: ランダムな L（各セルで一様）→ 年単位の集計の平均
    null = {key: [] for key in res}
    years = tab.year.values; symv = tab.sym.values
    for b in range(B):
        j = rng.integers(0, len(LS), size=len(tab))
        v = all_L[np.arange(len(tab)), j]
        tmp = pd.DataFrame(dict(sym=symv, year=years, v=v))
        for gname, syms in groups.items():
            for pname, (lo, hi) in periods.items():
                h = tmp[tmp.sym.isin(syms)]
                if lo is not None:
                    h = h[h.year >= lo]
                if hi is not None:
                    h = h[h.year < hi]
                null[f"{gname}|{pname}"].append(float(h.groupby("year").v.mean().mean()) if len(h) else float("nan"))
    for key in res:
        if "by_e" not in res[key]:
            continue
        v = np.asarray(null[key], float)
        res[key]["null_random_L"] = dict(mean=float(np.nanmean(v)), sd=float(np.nanstd(v, ddof=1)) if len(v) > 1 else float("nan"))
        for e in EMBARGOS:
            res[key]["by_e"][str(e)]["z_vs_random_L"], res[key]["by_e"][str(e)]["pct_vs_random_L"] = \
                z_against_null(res[key]["by_e"][str(e)]["pnl_mean"], v)

    verdict = judge(res["全15|全期間"])
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q155_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q155_by_e_{stamp}.png"))
    out = dict(
        queue_id="Q155", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, EMBARGOS=EMBARGOS, SEL_DAYS=SEL_DAYS, TEST_MIN_DAYS=TEST_MIN_DAYS, SPLIT_YEAR=SPLIT_YEAR,
                      L_BINS=[b[2] for b in L_BINS], NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=list(series), data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()), n=int(len(series[s][1])))
                   for s in series},
        missing=missing, n_cells=int(len(tab)), test_years=sorted(int(y) for y in tab.year.unique()),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, png=png_path),
        multiple_comparisons="e 6 点 × 指標 2（純損益・最大下落）× 群 3 × 期間 3 = 108 本（判定は 全15・全期間 の e=20−e=0 の純損益 1 本と 6 点の Spearman）",
        deviations_from_prereg=["テスト期間を暦年に固定し、選択期間の終わりを e 日だけ前にずらす（対応ありの差がテスト期間の違いを含まないため）",
                                "判定の『単調（Spearman ≥0.8）で t≥2』は |Spearman|≥0.8 かつ |t|≥2 かつ e=20−e=0<0（e=0 が良い）として符号を明示"],
    )
    jpath = os.path.join(OUT, f"{prefix}Q155_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else (int(o) if isinstance(o, np.integer) else (bool(o) if isinstance(o, np.bool_) else str(o))))

    print(f"[Q155] syms={len(series)} cells={len(tab)} years={tab.year.min()}..{tab.year.max()}  B={B}  smoke={args.smoke}  missing={missing}")
    for key in ("全15|全期間", "全15|前半", "全15|後半", "FX8|全期間", "トレンド7|全期間"):
        a = res[key]
        if "by_e" not in a:
            print(f"  {key}: (セルなし)"); continue
        print(f"  {key}: n={a['n_cells']} years={a['n_years']} rho(e,pnl)={a['spearman_e_vs_pnl']:+.2f} nullL={a['null_random_L']['mean']:+.2f}")
        for e in EMBARGOS:
            d = a["by_e"][str(e)]
            extra = f" diff={d['diff_vs_e0_mean']:+.3f} t={d['diff_vs_e0_t']:+.2f}" if e != 0 else ""
            print(f"    e={e:2d}: pnl={d['pnl_mean']:+.3f}bp (t{d['pnl_t']:+.2f}, z{d['z_vs_random_L']:+.2f}) dd={d['dd_mean']:.0f} L̄={d['L_mean']:.0f} sameL={d['share_same_L_as_e0']:.2f}{extra}")
        print("    L別(e20−e0):", {k: (v.get("n"), round(v.get("diff_e20_vs_e0_mean", float("nan")), 3)) for k, v in a["by_L_bin_e0"].items()})
    print("  判定(機械):", verdict["verdict"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
