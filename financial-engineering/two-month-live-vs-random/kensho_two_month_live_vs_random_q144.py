#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q144: 2か月の成績はランダム売買の分布のどこに入るか、順位は次の2か月で入れ替わるか
（Rashid・Hong ほか 2026 の「約2か月のライブ成績」を 15銘柄 D1・TSMOM20 で）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q144（Fable 2026-10-09）。
  検証/学問/金融工学/知識/文献/アイデア候補.md の同日の行。
- 論文ノート: Rashid・Hongほか2026_FinAnalyst_LLM専門家とルール信号の売買エージェント（検証するなら: 約2か月のライブ成績は
  ランダム売買の分布の中に入る／中間と最終で順位が入れ替わる）、Korzan2026（最終検証3年で t<2）、
  Yeほか2026（LLMトレードエージェントの報告されたアルファは配備の証拠にならない）。

【仮説（測る前に固定）】
H: 42営業日（約2か月）の窓では、固定規則（TSMOM20）の純損益は「同じ売買回数のランダムな符号の戦略」の分布から
   ほとんど区別できず（上位5%に入る窓は少ない）、銘柄の順位も次の窓で入れ替わる（連続する窓の順位相関は低い）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄 = FX8 + トレンド7。2008-02〜2026-07。
値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 規則1本: TSMOM20。s_t = sign(c_t − c_{t−20})、翌日 t+1 のポジション = s_t。
  日次純損益 [bp] = pos × (c_{t+1}/c_t − 1) × 1e4 − |Δpos| × 片道コスト（段階1の保守値 COST_RT/2 を価格で割って bp）。
- 窓: 全銘柄の日付の和集合（マスター日付）上で、長さ W=42 日の窓を STEP=21 日ずつずらす。各窓の各銘柄は、その窓の日付に
  含まれる自分の日（W/2 日以上あるものだけ）。副（記述）: W=126（STEP=63）、W=252（STEP=126）。
- 窓の成績 = 窓内の日次純損益の合計 [bp]（比較は同じ窓内なので合計でよい。表には bp/日 も出す）。
- ランダム売買の帰無（同じ売買回数）: 窓内で規則が持ち替えた回数 K（|Δpos|>0 の日数）と同じ K 回、窓内の相異なる日を一様に
  選んで符号を反転する ±1 の戦略（初期符号は等確率）。コストは反転日に |Δpos|=2 × 片道コスト。B=500 本、seed 固定。
  パーセンタイル p = (ランダム B 本の純損益 < 規則の純損益) の割合。
- (a) p ≥ 0.95 の（銘柄, 窓）の割合。 (b) 銘柄の順位（窓の純損益 bp/日）の Spearman（銘柄 ≥ MIN_CS=8 の窓対だけ）の平均。
  判定に使う (b) = 重なりのない隣の窓対 (w, w+2)。登録どおりの連続する窓対 (w, w+1)（半分重なる）は記述として残す。
- 期間: 前半 = 窓の開始が 2017 年より前、後半 = それ以降（記述）。群: 全15・FX8・トレンド7（(a) の記述）。

【測るもの】
W=42 の (a)(b)（判定）。W=126・252 の (a)(b)（記述: 窓を長くすると (a) が単調に上がるか）。前後半・群ごとの (a)。

【判定（事前固定・変更禁止）】
支持 = W=42 で (a) < 10% かつ (b)（重なりのない窓対）の平均 < 0.3 →「2か月では実力と運を分けられず順位も入れ替わる」。
棄却 = (a) ≥ 25%。
間（10% ≤ (a) < 25%、または (a)<10% だが (b) ≥ 0.3）は未確定。
窓を長くしたときの (a) の単調性は記述（判定に使わない）。多重比較: 窓3通り（判定は W=42 のみ）。

【捨てた案の数】
約5: 日次リターンの並べ替えを帰無にする案（規則の売買回数と合わなくなる→同じ K の符号反転）、
シャープで比べる案（42日のシャープは分散の推定が粗い→合計 bp）、窓を暦の2か月にする案（月の営業日数の差→42日固定）、
順位相関を p の順位で取る案（規則の純損益の順位を主、p の順位は副として併記）、ドンチャン簡略版も入れる案（1本固定）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。特定の2か月の相場を知っている可能性はあるが、
本検証は全窓（約220窓×15銘柄）をプールした割合で、特定の窓の知識では作れない。

【委託の確かめ方】
設計は Fable（specs20.py）、コードは Claude（Fable 5.1 下請け、2026-10-09）、実行と解釈は Sonnet／Opus が後で行う。
実行者は結果 JSON のパス・主要な数値（(a)(b) と W ごとの並び）・原典の箇所を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定のランダム戦略だけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_two_month_live_vs_random_q144.py            （B=500）
      python3 kensho_two_month_live_vs_random_q144.py --B 50
      python3 kensho_two_month_live_vs_random_q144.py --smoke
事前登録からの変更点:
(1) 判定の (b) を「重なりのない窓対 (w, w+2) の順位相関の平均」に変更。登録の「連続する窓」（半分重なる）には重なりの機械的な
    下駄があり（実力差ゼロの合成 AR(1) で ≈0.44）、閾値 <0.3 が意味を持たないため（Fable 承認 2026-10-09）。閾値 <0.3 はそのまま。
    重なりあり (b) は記述として JSON に残す（b_rank_rho_mean）。
(2) W=126・252 の STEP は W/2（事前登録は 42/21 の比を長い窓にも適用。21 日固定だと重なりが大きく (b) が膨らむため）。
"""
import argparse
import datetime as _dt
import json
import math
import os
import time
import unicodedata

import numpy as np
import pandas as pd

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

LOOKBACK = 20
WINDOWS = [(42, 21), (126, 63), (252, 126)]   # (W, STEP)。判定は W=42
MIN_CS = 8
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261009
QID = "Q144"


# ----------------------------------------------------------------------------- 道具
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


def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def daily_parts(c, signal, cost_rt):
    """日ごとの (pos_prev, ret, cost_bp(片道), dpos, net_pnl_bp)。先頭 LOOKBACK+1 日は無効。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = pos_prev * ret * 1e4 - dpos * cost_bp
    valid = np.arange(n) > LOOKBACK
    return pos_prev, ret, cost_bp, dpos, pnl, valid


def random_strategy_pnls(ret, cost_bp, K, B, rng):
    """窓内（長さ n）で K 回符号を反転する ±1 戦略 B 本の純損益 [bp]。"""
    n = len(ret)
    K = int(min(K, n))
    s0 = rng.choice([-1.0, 1.0], size=B)
    flips = np.zeros((B, n))
    if K > 0:
        u = rng.random((B, n))
        idx = np.argpartition(u, K - 1, axis=1)[:, :K]      # 相異なる K 日
        np.put_along_axis(flips, idx, 1.0, axis=1)
    pos = s0[:, None] * np.where(np.cumsum(flips, axis=1) % 2 == 0, 1.0, -1.0)
    gross = pos @ (ret * 1e4)
    cost = flips @ (2.0 * cost_bp)
    return gross - cost


# ----------------------------------------------------------------------------- 本体
def run_windows(series, parts, W, STEP, B, rng):
    master = np.unique(np.concatenate([np.asarray(t, "datetime64[ns]") for t, _ in series.values()]))
    rows = []
    starts = list(range(0, len(master) - W + 1, STEP))
    for wi, s0 in enumerate(starts):
        d0, d1 = master[s0], master[s0 + W - 1]
        for sym, (t, c) in series.items():
            tt = np.asarray(t, "datetime64[ns]")
            pos_prev, ret, cost_bp, dpos, pnl, valid = parts[sym]
            m = (tt >= d0) & (tt <= d1) & valid
            n = int(m.sum())
            if n < W // 2:
                continue
            K = int(round(dpos[m].sum() / 2.0))      # 持ち替え回数（±1 の反転は |Δpos|=2）
            rule = float(pnl[m].sum())
            rnd = random_strategy_pnls(ret[m], cost_bp[m], K, B, rng)
            pct = float((rnd < rule).mean())
            rows.append(dict(W=W, win=wi, start=str(pd.Timestamp(d0).date()), end=str(pd.Timestamp(d1).date()),
                             year=int(pd.Timestamp(d0).year), sym=sym, n_days=n, K=K, rule_sum_bp=rule,
                             rule_bp_per_day=rule / n, rnd_mean=float(rnd.mean()), rnd_sd=float(rnd.std(ddof=1)) if B > 1 else float("nan"),
                             pct=pct))
    return pd.DataFrame(rows)


def summarize(tab, syms_used, groups):
    out = {}
    for W in sorted(tab.W.unique()):
        g = tab[tab.W == W]
        d = {}
        for per in ("全期間", "前半", "後半"):
            gg = g if per == "全期間" else (g[g.year < SPLIT_YEAR] if per == "前半" else g[g.year >= SPLIT_YEAR])
            e = {"n_cells": int(len(gg))}
            for gname, syms in groups.items():
                h = gg[gg.sym.isin(syms)]
                e[f"a_share_pct_ge95_{gname}"] = float((h.pct >= 0.95).mean()) if len(h) else float("nan")
                e[f"a_share_pct_le05_{gname}"] = float((h.pct <= 0.05).mean()) if len(h) else float("nan")
                e[f"mean_pct_{gname}"] = float(h.pct.mean()) if len(h) else float("nan")
            # (b) 連続する窓の順位相関
            rhos = []; rhos_p = []
            wins = sorted(gg.win.unique())
            piv = gg.pivot(index="win", columns="sym", values="rule_bp_per_day")
            pivp = gg.pivot(index="win", columns="sym", values="pct")
            for w0, w1 in zip(wins[:-1], wins[1:]):
                if w1 != w0 + 1:
                    continue
                a, b = piv.loc[w0], piv.loc[w1]
                m = np.isfinite(a.values) & np.isfinite(b.values)
                if m.sum() >= MIN_CS:
                    rhos.append(spearman(a.values[m], b.values[m]))
                    rhos_p.append(spearman(pivp.loc[w0].values[m], pivp.loc[w1].values[m]))
            m_, t_, n_ = mean_t(rhos)
            e.update(b_rank_rho_mean=m_, b_rank_rho_t=t_, b_n_pairs=n_)
            m_, t_, n_ = mean_t(rhos_p)
            e.update(b_pct_rank_rho_mean=m_, b_pct_rank_rho_t=t_)
            # 参考: 重なりのない隣の窓（w, w+2）。STEP=W/2 なので連続する窓は半分重なり、(b) には機械的な下駄がある
            rhos_no = []
            for w0 in wins:
                w2 = w0 + 2
                if w2 in piv.index:
                    a, b = piv.loc[w0], piv.loc[w2]
                    m = np.isfinite(a.values) & np.isfinite(b.values)
                    if m.sum() >= MIN_CS:
                        rhos_no.append(spearman(a.values[m], b.values[m]))
            m_, t_, n_ = mean_t(rhos_no)
            e.update(b_nonoverlap_rank_rho_mean=m_, b_nonoverlap_rank_rho_t=t_, b_nonoverlap_n_pairs=n_)
            d[per] = e
        out[f"W{W}"] = d
    return out


def judge(summ):
    r = summ["W42"]["全期間"]
    a = r["a_share_pct_ge95_全15"]; b = r["b_nonoverlap_rank_rho_mean"]   # 判定の (b) は重なりのない窓対（Fable 承認 2026-10-09）
    b_overlap = r["b_rank_rho_mean"]
    fin = lambda v: v is not None and np.isfinite(v)
    if fin(a) and a >= 0.25:
        v = "棄却（(a) ≥ 25%）"
    elif fin(a) and fin(b) and a < 0.10 and b < 0.3:
        v = "支持（2か月では実力と運を分けられず順位も入れ替わる）"
    else:
        v = "未確定（(a) が 10〜25%、または (b) ≥ 0.3）"
    a_by_W = {k: summ[k]["全期間"]["a_share_pct_ge95_全15"] for k in summ}
    vals = [a_by_W[k] for k in sorted(a_by_W, key=lambda s: int(s[1:]))]
    mono = bool(all(np.isfinite(vals)) and all(x <= y for x, y in zip(vals[:-1], vals[1:])))
    return dict(a_W42=a, b_W42_nonoverlap=b, b_W42_overlap_descriptive=b_overlap, verdict=v, a_by_W=a_by_W, a_monotone_in_W=mono,
                rule="支持=(a)<10% かつ (b: 重なりのない窓対 w,w+2 の順位相関の平均)<0.3。棄却=(a)≥25%。間は未確定。重なりあり (b) は記述。W の単調性は記述",
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
        Ws = sorted(tab.W.unique())
        fig, ax = plt.subplots(1, len(Ws), figsize=(4.5 * len(Ws), 3.8))
        ax = np.atleast_1d(ax)
        for a, W in zip(ax, Ws):
            g = tab[tab.W == W]
            a.hist(g.pct, bins=20, range=(0, 1), color="tab:blue", alpha=.7)
            a.axvline(0.95, c="r", lw=.8, ls="--")
            a.set_title(f"W={W}: 規則のパーセンタイル（n={len(g)}）"); a.set_xlabel("ランダム売買の分布内の位置")
        fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="ランダム戦略の本数")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    series = {}; missing = []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            n = len(dates); e = g.normal(0, 0.006, n); r = np.zeros(n)
            for i in range(1, n):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            keep = g.random(n) > 0.03                        # 日付の欠けを模す
            series[sym] = (dates.values[keep], (base * np.exp(np.cumsum(r)))[keep])
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            d = load_daily(sym)
            if d is None or len(d) < 300:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    syms_used = list(series.keys())
    groups = {"全15": syms_used, "FX8": [s for s in FX8 if s in series], "トレンド7": [s for s in TREND7 if s in series]}
    parts = {sym: daily_parts(c, tsmom_positions(c), COST_RT[sym]) for sym, (t, c) in series.items()}

    tabs = [run_windows(series, parts, W, STEP, B, rng) for W, STEP in WINDOWS]
    tab = pd.concat(tabs, ignore_index=True)
    summ = summarize(tab, syms_used, groups)
    verdict = judge(summ)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_windows_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(tab, os.path.join(OUT, f"{prefix}{QID}_pct_hist_{stamp}.png"))
    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(LOOKBACK=LOOKBACK, WINDOWS=WINDOWS, MIN_CS=MIN_CS, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, syms=syms_used, missing_syms=missing, n_missing=len(missing), data_dir=DATA_DIR,
                      null_def="同じ持ち替え回数 K の ±1 ランダム符号戦略（反転日は窓内で一様・相異なる）"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_cells_by_W={f"W{W}": int((tab.W == W).sum()) for W, _ in WINDOWS},
        results=summ, judgement=verdict,
        files=dict(windows_csv=csv_path, pct_hist_png=png_path),
        multiple_comparisons="窓3通り（W=42/126/252）× 期間3 × 群3（判定は W=42×全期間×全15 のみ）",
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(syms_used)} missing={missing} B={B} smoke={args.smoke} elapsed={elapsed:.1f}s")
    for Wk, d in summ.items():
        for per, e in d.items():
            print(f"  {Wk:5s} {per:3s} cells={e['n_cells']:5d}  (a) ≥95%: 全15={e['a_share_pct_ge95_全15']:.3f} "
                  f"FX8={e['a_share_pct_ge95_FX8']:.3f} トレンド7={e['a_share_pct_ge95_トレンド7']:.3f}  ≤5%: {e['a_share_pct_le05_全15']:.3f}  "
                  f"mean pct={e['mean_pct_全15']:.3f}  (b) rho={e['b_rank_rho_mean']:+.3f} t={e['b_rank_rho_t']:+.2f} n={e['b_n_pairs']} "
                  f"(pct順位 rho={e['b_pct_rank_rho_mean']:+.3f}, 重なりなし rho={e['b_nonoverlap_rank_rho_mean']:+.3f})")
    print(f"  判定(機械): {verdict['verdict']} | a={verdict['a_W42']:.3f} b(重なりなし)={verdict['b_W42_nonoverlap']:+.3f} b(重なりあり・記述)={verdict['b_W42_overlap_descriptive']:+.3f}")
    print("  a_by_W", {k: round(v, 3) for k, v in verdict["a_by_W"].items()}, "| 単調", verdict["a_monotone_in_W"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
