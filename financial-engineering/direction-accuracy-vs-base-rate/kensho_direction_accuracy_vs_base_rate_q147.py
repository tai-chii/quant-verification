#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q147: 翌日の方向の的中率は「常に上」「前日の符号」の基準率を超えるか
（HSAT の基準の置き方・15銘柄 D1）
================================================================================

【出典】
- 事前登録: /tmp/claude-0/specs20.py の Q147（Fable 2026-10-09）＝アイデア候補.md の行。
- 論文ノート: Mustafa・Daneshwar 2026 HSAT（トレンド分類と終値回帰を同時に予測する Transformer）。
  検証するなら:「常に Up」「前日の符号」を比較対象に入れ、F1 0.70 がそれを超えるか。日本株は Up 45.7% と偏る。
- 既存の知見: 為替の超短期の平均回帰は 2015 年以降の 1 時間足では消えた。

【仮説（測る前に固定）】
H: 固定した 4 本の予測器の翌日の方向の的中率は、基準率 max(p_up, 1−p_up) を 1 ポイント以上・有意に超えない。
（超える（銘柄, 予測器, 期間）が Holm 補正後に 0 なら「方向の的中率は基準率を超えない」）

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 目的変数 y_t = sign(c_{t+1} − c_t)。0 の日は除く。
- 予測器（t 日の引けまでの情報で t+1 の符号を当てる）:
  (a) 常に上: +1。 (b) 前日の符号: sign(c_t − c_{t−1})。 (c) TSMOM20: sign(c_t − c_{t−20})。 (d) 200日線: sign(c_t − SMA200_t)。
  4 本とも同じ日の集合で評価する: t ≥ WARMUP=200 かつ y_t ≠ 0 かつ 4 本の予測がすべて非 0 の日。
- 的中 h_t = 1[pred_t == y_t]。的中率 acc = mean(h_t)。
- 基準率 base = max(p_up, 1 − p_up)、p_up = 同じ日の集合での y_t = +1 の割合（その銘柄×期間）。
- 差 = acc − base。t = (acc − base) / NW_se(h_t)、Newey-West 5 ラグ（的中 0/1 の日次系列）。
- 期間: 前半 = year < 2017、後半 = year ≥ 2017（t 日の UTC 日付）。全期間も記述。
- Holm 補正: 片側（超える方向）の p = 1 − Φ(t) を 15銘柄 × 4本 × 2期間 = 120 本でまとめて Holm（α=0.05）。
- 帰無: 翌日の符号 y_t を（銘柄×期間の中で）並べ替える B=500 回。予測の列は固定。基準率だけが残る。
  各（銘柄, 予測器, 期間）の acc の帰無分布から z と片側パーセンタイル。

【測るもの】
銘柄×前半/後半で、4 本の acc・p_up・base・acc−base・NW の t・Holm 後の p・帰無の z。

【判定（事前固定・変更禁止）】
- Holm 補正後に有意（p_holm < 0.05、片側）かつ acc − base ≥ 0.01 の（銘柄, 予測器, 期間）が 0 なら
  「方向の的中率は基準率を超えない」。
- トレンド7 で (c) または (d) が上を満たす銘柄（どちらかの期間）が 3 以上なら、「上昇相場の基準率で説明できるか」を
  p_up との比較（acc と p_up の差、(a) の acc との差）で記述する（判定には使わない）。
- 多重比較: 15 × 4 × 2 = 120（Holm でまとめる）。

【捨てた案の数】
約5: F1 を主にする案（F1 は陽性クラスの定義に依存・的中率で統一）、予測器ごとに別々の日集合で評価する案（基準率が
ずれるので共通集合に）、両側の p にする案（問いは「超えるか」なので片側）、月ブロックの t（NW で代用）、
Up の偏りを月ごとに測る案（記述に留める）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。各銘柄の大まかな値動きを知っている可能性はあるが、
本検証は固定した 4 本の規則の的中率を機械的に数えるだけで、相場観で結果を作れる余地は小さい。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、2026-10-09）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は結論ではなく、結果 JSON のパス・主要な数値（超えた組の数、トレンド7 の (c)(d) の数、p_up）・原典の箇所を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_direction_accuracy_vs_base_rate_q147.py            （B=500、1分前後）
      python3 kensho_direction_accuracy_vs_base_rate_q147.py --B 50
      python3 kensho_direction_accuracy_vs_base_rate_q147.py --smoke    （合成データで経路の確認。結果は捨てる）
事前登録からの変更点: なし。
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import time
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
# 段階1の保守的な往復コスト（価格単位）。本検証では売買しないので参考値（JSON に記録するだけ）。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20
SMA_N = 200
WARMUP = 200
NW_LAGS = 5
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261009
ALPHA = 0.05
MIN_POINTS = 0.01     # 「1 ポイント以上」
PRED_NAMES = ["a_always_up", "b_prev_sign", "c_tsmom20", "d_sma200"]


# ----------------------------------------------------------------------------- 基本の道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def nw_se(x, lags=NW_LAGS):
    """平均の Newey-West 標準誤差（Bartlett 核）。"""
    x = np.asarray(x, float); n = len(x)
    if n < 3:
        return float("nan")
    d = x - x.mean()
    g0 = (d * d).sum() / n
    s = g0
    for l in range(1, min(lags, n - 1) + 1):
        gl = (d[l:] * d[:-l]).sum() / n
        s += 2.0 * (1.0 - l / (lags + 1.0)) * gl
    return float(math.sqrt(max(s, 0.0) / n))


def norm_sf(t):
    return 0.5 * math.erfc(t / math.sqrt(2.0)) if np.isfinite(t) else float("nan")


def holm(pvals, alpha=ALPHA):
    """Holm の段階的補正。返り値: 補正後 p（単調化済み）と有意フラグ。nan は m に数えるが有意にしない。"""
    p = np.asarray(pvals, float); m = len(p)
    pf = np.where(np.isfinite(p), p, 1.0)
    order = np.argsort(pf)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        v = min(1.0, (m - rank) * pf[i])
        run = max(run, v)
        adj[i] = run
    sig = (adj < alpha) & np.isfinite(p)
    return adj, sig


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


# ----------------------------------------------------------------------------- データ
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def synthetic_series(syms):
    """合成: AR(1) の対数リターン（φ を銘柄ごとに変える）。経路の確認だけが目的。"""
    g = np.random.default_rng(1)
    dates = pd.bdate_range("2008-02-01", "2026-07-14")
    out = {}
    for k, sym in enumerate(syms):
        phi = -0.1 + 0.3 * (k / (len(syms) - 1))
        e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
        for i in range(1, len(dates)):
            r[i] = phi * r[i - 1] + e[i]
        base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
        out[sym] = (dates.values, base * np.exp(np.cumsum(r)))
    return out


# ----------------------------------------------------------------------------- 予測器
def predictors(c):
    """4 本の予測（t 日の引けで作る t+1 の符号）。長さ n、未定義は 0。"""
    n = len(c)
    a = np.ones(n)
    b = np.zeros(n); b[1:] = np.sign(c[1:] - c[:-1])
    cc = np.zeros(n); cc[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    sma = pd.Series(c).rolling(SMA_N).mean().values
    d = np.where(np.isfinite(sma), np.sign(c - np.nan_to_num(sma)), 0.0)
    P = np.vstack([a, b, cc, d])
    P[:, :WARMUP] = 0.0
    return P


def target(c):
    n = len(c); y = np.zeros(n)
    y[:-1] = np.sign(c[1:] - c[:-1])
    return y


# ----------------------------------------------------------------------------- 1銘柄×1期間
def cell_stats(P, y, mask, B, rng):
    """P: 4×n 予測、y: 目的、mask: 期間。共通の有効日で acc・base・NW t・帰無 z。"""
    valid = mask & (y != 0) & np.all(P != 0, axis=0)
    idx = np.flatnonzero(valid)
    out = {"n_days": int(len(idx))}
    if len(idx) < 50:
        for nm in PRED_NAMES:
            out[nm] = dict(acc=float("nan"), diff=float("nan"), t_nw=float("nan"), p_one_sided=float("nan"),
                           null_z=float("nan"), null_pct=float("nan"), null_mean=float("nan"))
        out.update(p_up=float("nan"), base=float("nan"))
        return out
    yy = y[idx]; PP = P[:, idx]
    p_up = float((yy > 0).mean()); base = max(p_up, 1.0 - p_up)
    out.update(p_up=p_up, base=float(base))
    # 帰無: y を並べ替え（予測は固定）
    Yn = np.empty((B, len(idx)))
    for b in range(B):
        Yn[b] = yy[rng.permutation(len(idx))]
    null_acc = (Yn[:, None, :] == PP[None, :, :]).mean(axis=2)   # B × 4
    for k, nm in enumerate(PRED_NAMES):
        h = (PP[k] == yy).astype(float)
        acc = float(h.mean()); se = nw_se(h)
        t = (acc - base) / se if (se and se > 0) else float("nan")
        z, pct = z_against_null(acc, null_acc[:, k])
        out[nm] = dict(acc=acc, diff=float(acc - base), t_nw=float(t), p_one_sided=norm_sf(t),
                       null_z=z, null_pct=pct, null_mean=float(null_acc[:, k].mean()))
    return out


# ----------------------------------------------------------------------------- 本体
def run(series, B, rng):
    cells = {}
    rows = []
    for sym, (t, c) in series.items():
        P = predictors(c); y = target(c)
        yr = pd.DatetimeIndex(t).year.values
        masks = {"前半": yr < SPLIT_YEAR, "後半": yr >= SPLIT_YEAR, "全期間": np.ones(len(c), bool)}
        for per, m in masks.items():
            st = cell_stats(P, y, m, B, rng)
            cells[f"{sym}|{per}"] = st
            for nm in PRED_NAMES:
                r = st[nm]
                rows.append(dict(sym=sym, period=per, predictor=nm, n_days=st["n_days"], p_up=st["p_up"], base=st["base"],
                                 acc=r["acc"], diff=r["diff"], t_nw=r["t_nw"], p_one_sided=r["p_one_sided"],
                                 null_z=r["null_z"], null_pct=r["null_pct"]))
    tab = pd.DataFrame(rows)
    # Holm: 前半/後半 × 15 × 4（全期間は記述・補正に入れない）
    fam = tab.period.isin(["前半", "後半"])
    adj, sig = holm(tab.loc[fam, "p_one_sided"].values)
    tab["p_holm"] = np.nan; tab["holm_sig"] = False
    tab.loc[fam, "p_holm"] = adj; tab.loc[fam, "holm_sig"] = sig
    tab["exceeds"] = tab.holm_sig & (tab["diff"] >= MIN_POINTS)
    return tab, cells


def judge(tab):
    fam = tab[tab.period.isin(["前半", "後半"])]
    n_exceed = int(fam.exceeds.sum())
    ex = fam[fam.exceeds]
    trend_cd = ex[ex.sym.isin(TREND7) & ex.predictor.isin(["c_tsmom20", "d_sma200"])]
    n_trend_cd_syms = int(trend_cd.sym.nunique())
    verdict = ("方向の的中率は基準率を超えない" if n_exceed == 0 else
               f"基準率を 1 ポイント以上・有意に超える組が {n_exceed} 組（Holm 後）")
    describe_pup = n_trend_cd_syms >= 3
    # 記述用: 超えた組の acc と p_up・(a) の acc の比較
    cmp_rows = []
    for _, r in trend_cd.iterrows():
        a_acc = fam[(fam.sym == r.sym) & (fam.period == r.period) & (fam.predictor == "a_always_up")].acc.values
        cmp_rows.append(dict(sym=r.sym, period=r.period, predictor=r.predictor, acc=float(r.acc), p_up=float(r.p_up),
                             acc_minus_p_up=float(r.acc - r.p_up),
                             acc_minus_always_up=float(r.acc - a_acc[0]) if len(a_acc) else float("nan")))
    return dict(n_tests_holm=int(len(fam)), n_exceed_after_holm=n_exceed,
                exceeding=ex[["sym", "period", "predictor", "acc", "base", "diff", "t_nw", "p_holm", "null_z"]].to_dict("records"),
                trend7_cd_exceeding_syms=sorted(trend_cd.sym.unique().tolist()), n_trend7_cd_syms=n_trend_cd_syms,
                describe_vs_p_up=bool(describe_pup), trend7_cd_vs_p_up=cmp_rows, verdict=verdict,
                note="事前固定の規則で機械的に付けた判定（Holm 片側 α=0.05 かつ acc−base≥0.01）。"
                     "解釈（確定／ノイズ／未確定、上昇相場の基準率で説明できるか）は実行者が記録する。")


def make_plot(tab, path):
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
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        for a, per in zip(ax, ["前半", "後半"]):
            g = tab[tab.period == per]
            for k, nm in enumerate(PRED_NAMES):
                gg = g[g.predictor == nm].set_index("sym").reindex(SYMS)
                a.bar(np.arange(len(SYMS)) + (k - 1.5) * 0.2, gg["diff"].values * 100, width=0.2, label=nm)
            a.axhline(0, lw=.6, c="k"); a.axhline(1.0, lw=.6, c="gray", ls="--")
            a.set_xticks(range(len(SYMS))); a.set_xticklabels(SYMS, rotation=90, fontsize=7)
            a.set_title(f"{per}: 的中率 − 基準率（ポイント）"); a.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:  # 図は任意
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    missing = []
    if args.smoke:
        series = synthetic_series(SYMS); B = min(args.B, 10)
    else:
        series = {}
        for sym in SYMS:
            d = load_daily(sym)
            if d is None:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    if not series:
        print("データがありません:", DATA_DIR); sys.exit(1)

    tab, cells = run(series, B, rng)
    verdict = judge(tab)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q147_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(tab, os.path.join(OUT, f"{prefix}Q147_diff_{stamp}.png"))
    # 群ごとの要約（記述）
    summary = {}
    for per in ("前半", "後半", "全期間"):
        for gname, syms in {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}.items():
            g = tab[(tab.period == per) & tab.sym.isin(syms)]
            summary[f"{gname}|{per}"] = {nm: dict(mean_acc=float(g[g.predictor == nm].acc.mean()),
                                                  mean_diff=float(g[g.predictor == nm]["diff"].mean()),
                                                  n_exceed=int(g[g.predictor == nm].exceeds.sum()))
                                         for nm in PRED_NAMES}
            summary[f"{gname}|{per}"]["mean_p_up"] = float(g[g.predictor == "a_always_up"].p_up.mean())
    out = dict(
        queue_id="Q147", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(time.time() - t0, 1),
        settings=dict(LOOKBACK=LOOKBACK, SMA_N=SMA_N, WARMUP=WARMUP, NW_LAGS=NW_LAGS, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B,
                      SEED=SEED, ALPHA=ALPHA, MIN_POINTS=MIN_POINTS, COST_RT=COST_RT, predictors=PRED_NAMES,
                      syms=list(series.keys()), missing_syms=missing, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_syms=len(series), n_missing=len(missing),
        cells=cells, group_summary=summary, judgement=verdict,
        files=dict(cells_csv=csv_path, diff_png=png_path),
        multiple_comparisons=f"15銘柄 × 4予測器 × 2期間 = {int(tab.period.isin(['前半','後半']).sum())} 本を Holm（片側 α=0.05）。全期間は記述のみ",
    )
    jpath = os.path.join(OUT, f"{prefix}Q147_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else
                  (bool(o) if isinstance(o, np.bool_) else str(o)))

    print(f"[Q147] syms={len(series)} missing={missing} B={B} smoke={args.smoke} elapsed={out['elapsed_sec']}s")
    for per in ("前半", "後半"):
        for gname in ("全15", "FX8", "トレンド7"):
            s = summary[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} p_up={s['mean_p_up']:.3f}  " +
                  "  ".join(f"{nm[:1]}:acc={s[nm]['mean_acc']:.3f} diff={s[nm]['mean_diff']*100:+.2f}pt n_ex={s[nm]['n_exceed']}"
                            for nm in PRED_NAMES))
    print("  判定(機械):", verdict["verdict"], "| 超えた組:", verdict["n_exceed_after_holm"],
          "| トレンド7 (c)(d) 銘柄数:", verdict["n_trend7_cd_syms"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
