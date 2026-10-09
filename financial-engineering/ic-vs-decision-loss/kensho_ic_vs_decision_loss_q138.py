#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q138: 予測の当たりやすさ（IC）と決定の損失（コスト後の純損益）はどれだけ食い違うか
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q138（Fable 2026-10-09）＝ アイデア候補.md の行。
- 論文ノート: Alonso2026_意思決定理論とAI_回帰誤差とルーティング後悔（§6.3 p15: 相関や AUROC だけでは方策の価値は
  決まらない。式 15–17: 誤差は判断の境目をまたぐときだけ後悔になる）。
- Alahmadi・Basingab2026_弱い形の市場効率性検定の体系的レビュー §3.4.1（予測可能性と収益性は別）。

【仮説（測る前に固定）】
H: 銘柄×年のセルで、予測の当たりやすさ（IC・符号の的中率）の順位と、同じ予測器で売買したコスト後の純損益の順位は
一致しない（Alonso: 相関は方策の価値を決めない）。対立: 順位相関が高く、IC は決定の損失を代理する。

【データ】
15銘柄 `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足。列 time,open,high,low,close。値動きのない足は除く）。
無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 予測器 1 本: x_t = c_t / c_{t−20} − 1（20 日リターン。符号と大きさ）→ 標的 y_t = c_{t+1}/c_t − 1（翌日リターン）。
- セル = 銘柄 × 暦年（UTC）。x と y が定義される日が MIN_DAYS=100 未満のセルは捨てる。
- (a) IC = セル内の Spearman(x_t, y_t)。
- (b) 的中率 = セル内で sign(x_t) == sign(y_t) の割合（y_t=0 または x_t=0 の日は除く）。
- (c) 純損益 = 「|x_t| > u のときだけ sign(x_t) を翌日に持つ」規則の、コスト後の日次純損益の平均 [bp/日]。
  u = 片道コストの 2 倍（片道 = COST_RT/2 を価格で割った割合。u_t = COST_RT/c_t）。
  コスト = ポジション変化 × 片道コスト（bp 換算は COST_RT/2 / c_{t−1} × 1e4）。セル内の全日の平均（休みの日は 0）。
- セル間の順位相関 ρ_a = Spearman(IC, 純損益)、ρ_b = Spearman(的中率, 純損益)。
- 「境目」の集中度: 売買した日のうち |x_t| − u が小さい方から 25% の日（セル内で分位）が、純損益の損失合計（負の日の和）
  に占める割合。構造がなければ約 25%。

【測るもの】
期間: 前半（年 < 2017）／後半（年 ≥ 2017）／全期間。群: 全15・FX8・トレンド7（判定は全15）。
各期間で ρ_a・ρ_b と、帰無分布に対する z・パーセンタイル。境目の集中度。

【帰無】
各年の翌日リターン y_t を年内で並べ替え（予測 x_t との関係を壊す。x は実データのまま）。B=500。
並べ替えた y で (a)(c) を出し直し、ρ_a（と ρ_b）の帰無分布を作る。z = (ρ_obs − mean) / sd。

【判定（事前固定・変更禁止）】
全15・前半と後半のそれぞれで（ρ_a だけで判定）:
- ρ_a ≥ 0.5 →「IC は決定の損失を代理する」。
- ρ_a < 0.3 →「IC と純損益は別物」（Alonso の主張を支持）。
- 0.3 ≤ ρ_a < 0.5 → 未確定。
前半と後半で判定が割れたら 未確定。帰無の z・パーセンタイルは記述（判定に使わない）。ρ_b（的中率）は副次で判定に使わない。
多重比較: 指標 2（IC・的中率）× 期間 2 ＝ 4（判定は IC × 2 期間）。

【事前登録からの変更点】
事前登録では「ρ_a の z ≥ 2 かつ ρ_a ≥ 0.5 → 代理する／z < 2 または ρ_a < 0.3 → 別物」だった。帰無（翌日リターンの並べ替え）
でも IC と純損益は同じ翌日リターンから作るため ρ_a が機械的に高く（合成データで 0.7〜0.8）、z は判定に不向き。
判定は ρ_a だけで行い、z は記述に下げる（Fable 承認 2026-10-09）。「境目」の集中割合は記述のまま。

【捨てた案の数】
約5: 予測器を複数（5/10/60 日）にする案（1 本固定が登録）、閾値 u をコストの 1 倍・3 倍でも出す案（感度は実行者が
別途・登録は 2 倍）、純損益を「売買した日だけの平均」にする案（決定の価値は全日で測るべき → 全日平均）、
セルを半年にする案（IC の標本が 120 日で粗い → 年）、境目を |x|−u の絶対水準で切る案（銘柄でスケールが違う → 分位）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証は横断面（セル間の順位）の量で、特定の年の
相場観だけでは作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude Fable 5.1（この下請け）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（ρ_a・z・前後半）・原典の箇所（Alonso §6.3・式 15–17）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_ic_vs_decision_loss_q138.py            （B=500、数分）
      python3 kensho_ic_vs_decision_loss_q138.py --B 50     （軽い試走）
      python3 kensho_ic_vs_decision_loss_q138.py --smoke    （合成データで経路の確認。結果は results/smoke_*）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import unicodedata

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

LOOKBACK = 20
U_MULT = 2.0           # 閾値 u = 片道コスト × 2
MIN_DAYS = 100
SPLIT_YEAR = 2017
EDGE_Q = 0.25          # 「境目」= |x|−u の下位 25%
NULL_B = 500
SEED = 20261009
RHO_HI, RHO_LO = 0.5, 0.3     # 判定は ρ だけ（z は記述）


# ----------------------------------------------------------------------------- 基本の道具
def rank_avg(x):
    """平均順位（同順位は平均）。numpy だけ。"""
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    sx = x[order]
    i = 0; n = len(x)
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    rx = rank_avg(x); ry = rank_avg(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    d = math.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


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


# ----------------------------------------------------------------------------- 1銘柄の前処理
def prepare(sym, t, c):
    """決定日 t に揃えた配列: x_t（20日リターン）、y_t（翌日リターン）、u_t、cost_bp_t、year_t。"""
    n = len(c)
    x = np.full(n, np.nan); x[LOOKBACK:] = c[LOOKBACK:] / c[:-LOOKBACK] - 1.0
    y = np.full(n, np.nan); y[:-1] = c[1:] / c[:-1] - 1.0
    u = U_MULT * (COST_RT[sym] / 2.0) / c              # 割合
    cost_bp = (COST_RT[sym] / 2.0) / c * 1e4           # t 日の終値で換算した片道コスト [bp]
    years = pd.DatetimeIndex(t).year.values
    valid = np.isfinite(x) & np.isfinite(y)
    return dict(sym=sym, x=x, y=y, u=u, cost_bp=cost_bp, year=years, valid=valid)


def cell_metrics(d, y):
    """y（実データまたは並べ替え）で、銘柄の各年のセル量を出す。戻り: list of dict。"""
    x, u, cost_bp, years, valid = d["x"], d["u"], d["cost_bp"], d["year"], d["valid"]
    pos = np.where(valid & (np.abs(x) > u), np.sign(x), 0.0)
    pos_prev = np.concatenate([[0.0], pos[:-1]])
    pnl = pos * y * 1e4 - np.abs(pos - pos_prev) * cost_bp        # 決定日 t に帰属させた純損益
    pnl = np.where(valid, pnl, np.nan)
    rows = []
    for yr in np.unique(years):
        m = (years == yr) & valid
        if m.sum() < MIN_DAYS:
            continue
        xx, yy, pp = x[m], y[m], pnl[m]
        ic = spearman(xx, yy)
        nz = (xx != 0) & (yy != 0)
        hit = float((np.sign(xx[nz]) == np.sign(yy[nz])).mean()) if nz.sum() else float("nan")
        traded = pos[m] != 0
        # 境目の集中度: 売買した日のうち |x|−u が下位 EDGE_Q のものが、損失合計に占める割合
        edge_share = float("nan"); n_tr = int(traded.sum())
        if n_tr >= 8:
            gap = (np.abs(xx) - u[m])[traded]; pl = pp[traded]
            thr = np.quantile(gap, EDGE_Q)
            loss_all = pl[pl < 0].sum()
            if loss_all < 0:
                edge_share = float(pl[(pl < 0) & (gap <= thr)].sum() / loss_all)
        rows.append(dict(sym=d["sym"], year=int(yr), n=int(m.sum()), IC=ic, hit=hit, pnl_bp=float(np.nanmean(pp)),
                         traded_share=float(traded.mean()), n_traded=n_tr, edge_loss_share=edge_share))
    return rows


def shuffle_y(d, rng):
    """翌日リターン y_t を年内で並べ替える（valid な日だけ）。"""
    y2 = d["y"].copy()
    for yr in np.unique(d["year"]):
        idx = np.flatnonzero((d["year"] == yr) & d["valid"])
        if len(idx) > 1:
            y2[idx] = d["y"][rng.permutation(idx)]
    return y2


# ----------------------------------------------------------------------------- 統計
def rho_for(tab, syms, period):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    return dict(n_cells=int(len(g)), rho_ic=spearman(g.IC, g.pnl_bp), rho_hit=spearman(g.hit, g.pnl_bp),
                mean_IC=float(np.nanmean(g.IC)) if len(g) else float("nan"),
                mean_hit=float(np.nanmean(g.hit)) if len(g) else float("nan"),
                mean_pnl_bp=float(np.nanmean(g.pnl_bp)) if len(g) else float("nan"),
                mean_edge_loss_share=float(np.nanmean(g.edge_loss_share)) if len(g) else float("nan"),
                share_pnl_pos=float((g.pnl_bp > 0).mean()) if len(g) else float("nan"))


def evaluate(obs, nulls):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    res = {}
    for gname, syms in groups.items():
        for per in ("前半", "後半", "全期間"):
            o = rho_for(obs, syms, per)
            ns = [rho_for(nt, syms, per) for nt in nulls]
            na = [s["rho_ic"] for s in ns]; nb = [s["rho_hit"] for s in ns]
            o["z_ic"], o["pct_ic"] = z_against_null(o["rho_ic"], na)
            o["z_hit"], o["pct_hit"] = z_against_null(o["rho_hit"], nb)
            o["null_rho_ic_mean"] = float(np.nanmean(na)) if len(na) else float("nan")
            o["null_rho_ic_sd"] = float(np.nanstd(na, ddof=1)) if len(na) > 1 else float("nan")
            o["null_rho_ic_p975"] = float(np.nanpercentile(na, 97.5)) if len(na) else float("nan")
            o["null_edge_loss_share_mean"] = float(np.nanmean([s["mean_edge_loss_share"] for s in ns])) if ns else float("nan")
            res[f"{gname}|{per}"] = o
    return res


def judge(res):
    def one(r):
        rho = r["rho_ic"]
        if not np.isfinite(rho):
            return "判定不能"
        if rho >= RHO_HI:
            return "IC は決定の損失を代理する"
        if rho < RHO_LO:
            return "IC と純損益は別物（Alonso を支持）"
        return "未確定"
    by = {per: one(res[f"全15|{per}"]) for per in ("前半", "後半")}
    verdict = by["前半"] if by["前半"] == by["後半"] else "未確定（前半と後半で判定が割れた）"
    return dict(by_period=by, verdict=verdict, thresholds=dict(rho_hi=RHO_HI, rho_lo=RHO_LO),
                z_by_period={per: res[f"全15|{per}"]["z_ic"] for per in ("前半", "後半")},
                full_period_reference=one(res["全15|全期間"]),
                change_from_prereg="判定は ρ だけ。帰無でも同じ翌日リターンから作るため ρ が機械的に高く、z は判定に不向き（Fable 承認 2026-10-09）。z は記述。",
                note="事前固定の規則で機械的に付けた判定（全15・IC の ρ のみ。z・的中率は記述）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


def make_plot(obs, path):
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
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
        for a, (per, g) in zip(ax, [("前半", obs[obs.year < SPLIT_YEAR]), ("後半", obs[obs.year >= SPLIT_YEAR])]):
            fx = g[g.sym.isin(FX8)]; tr = g[g.sym.isin(TREND7)]
            a.scatter(fx.IC, fx.pnl_bp, s=12, alpha=.6, label="FX8"); a.scatter(tr.IC, tr.pnl_bp, s=12, alpha=.6, label="トレンド7")
            a.axhline(0, lw=.6, c="k"); a.axvline(0, lw=.6, c="k")
            a.set_xlabel("IC（Spearman: 20日リターン vs 翌日リターン）"); a.set_ylabel("純損益（bp/日・コスト後）")
            a.set_title(f"{per}: n={len(g)}  ρ={spearman(g.IC, g.pnl_bp):+.3f}"); a.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
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

    preps = {sym: prepare(sym, t, c) for sym, (t, c) in series.items()}
    obs = pd.DataFrame([row for d in preps.values() for row in cell_metrics(d, d["y"])])
    nulls = []
    for b in range(B):
        rows = []
        for d in preps.values():
            rows.extend(cell_metrics(d, shuffle_y(d, rng)))
        nulls.append(pd.DataFrame(rows))
    res = evaluate(obs, nulls)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q138_cells_{stamp}.csv"); obs.to_csv(csv_path, index=False)
    png_path = make_plot(obs, os.path.join(OUT, f"{prefix}Q138_scatter_{stamp}.png"))
    out = dict(
        queue_id="Q138", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, U_MULT=U_MULT, MIN_DAYS=MIN_DAYS, SPLIT_YEAR=SPLIT_YEAR, EDGE_Q=EDGE_Q,
                      NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      null="各年の翌日リターンを年内で並べ替え（予測 x は実データのまま）"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        missing=missing, n_symbols_used=len(series), n_cells=int(len(obs)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, scatter_png=png_path),
        multiple_comparisons="指標 2（IC・的中率）× 期間 2（前半・後半）＝ 4（判定は IC × 2 期間。群 FX8・トレンド7 は記述）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q138_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q138] cells={len(obs)}  B={B}  smoke={args.smoke}  missing={list(missing)}")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_cells']:3d}  ρ(IC,pnl)={r['rho_ic']:+.3f} z={r['z_ic']:+.2f} (null 97.5%={r['null_rho_ic_p975']:+.3f})  "
                  f"ρ(hit,pnl)={r['rho_hit']:+.3f} z={r['z_hit']:+.2f}  meanIC={r['mean_IC']:+.3f} meanPnL={r['mean_pnl_bp']:+.2f}bp  "
                  f"edge_loss_share={r['mean_edge_loss_share']:.2f} (null {r['null_edge_loss_share_mean']:.2f})")
    print("  判定(機械):", verdict["verdict"], "|", verdict["by_period"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
