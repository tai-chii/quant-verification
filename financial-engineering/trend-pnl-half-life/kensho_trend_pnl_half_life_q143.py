#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q143: 順張りの純損益の減衰は指数か、それとも最初から0か
（Feng・Cardozo・Xia 2026 の「半減期」を為替8・トレンド7 の年次純損益で）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q143（Fable 2026-10-09）。
  検証/学問/金融工学/知識/文献/アイデア候補.md の同日の行。
- 論文ノート: Feng・Cardozo・Xia2026_定量株式運用50年のサーベイ_アルファ減衰と実装の壁
  （検証するなら: ローリングの純成績に exp(−λt) を当て、λ の区間が 0 と区別できるか。減った理由の4分類）、
  Arnott・Harvey・Markowitz2019、知見 Q063（為替の時刻アノマリーの公表後の残り方: フィキシング約3割・五十日0）。
- 既存の知見: FX8 の日足順張りは 2016 年以降も補正後に有意 0 本（Q019・Q054）。
  → 「減衰して 0 になった」のか「最初から 0」なのかを、年次の純損益の形で分ける。

【仮説（測る前に固定）】
H_decay: 順張り（TSMOM20・ドンチャン簡略版）の年次純損益 y_t は t とともに指数で減る（λ>0 が 0 と区別できる）。
H_flat : y_t は最初から一定（FX8 では 0 近辺）で、指数減衰モデルは一定モデルに AIC で勝たない。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 規則2本固定: TSMOM20（s_t = sign(c_t − c_{t−20})、翌日に持つ）、ドンチャン簡略版 55/20（終値が直前55日高値の上抜けで買い、
  直前20日安値の下抜けで手仕舞い。売りは対称。損切りなし）。日次純損益 [bp] = pos × (c_{t+1}/c_t − 1) × 1e4 − |Δpos| × 片道コスト
  （段階1の保守値 COST_RT/2 を価格で割って bp）。
- 年次純損益 y_t = 暦年 t の日次純損益の平均 [bp/日]。日数 MIN_DAYS=100 未満の年は捨てる。t = 年 − 最初の年（0,1,2,…）。
- (i) 一定モデル y = c（k=1）。 (ii) 指数減衰 y = a·exp(−λt) + b（k=3）。
  (ii) は λ のグリッド（[LAM_MIN, LAM_MAX] を LAM_STEP 刻み）ごとに a,b を線形最小二乗で解き、RSS 最小の λ を選ぶ
  （非線形最小二乗を scipy なしで決定的に実装。グリッドの刻みは 0.005）。
- AIC = n·ln(RSS/n) + 2k。ΔAIC = AIC_(i) − AIC_(ii)（正なら減衰モデルが良い）。
- λ の区間: 年のペア (t, y_t) を復元抽出するブートストラップ B 回の λ の 2.5・97.5 パーセンタイル（年ブロック・ブートストラップ）。
- 帰無: y_t の年の順序を並べ替え（B 回）、同じ当てはめで λ の分布。観測 λ がその 95 パーセンタイルより上なら「帰無の上位5%より外」。
- 群: FX8・トレンド7（全15 は記述）。群ごとに λ の平均（観測）と、判定の条件を満たす銘柄数。

【測るもの】
銘柄×規則ごとに: y_t の系列、c、a、b、λ、ΔAIC、λ の区間 [lo, hi]、帰無の λ の 95 点、半減期 ln2/λ（λ>0 のとき）。
群ごとに: λ の平均、「λ の区間が 0 を含まず（lo>0）かつ 帰無の上位5%より外」の銘柄数、「ΔAIC<2」の銘柄数。

【判定（事前固定・変更禁止）】
群（FX8・トレンド7）×規則ごとに:
- 「減衰している」 = 群の過半の銘柄で λ の区間が 0 を含まず（lo>0）かつ 観測 λ が帰無の 95 パーセンタイルより上。
- 「最初から0（減衰ではない）」 = FX8 で (i) が (ii) に AIC で負けない（ΔAIC<2）銘柄が過半（トレンド7 では「一定（減衰ではない）」と表記）。
- それ以外は未確定（Q063 と同じ）。
主の判定は TSMOM20。ドンチャン簡略版は副（判定は同じ規則で機械的に出すが、報告では副として扱う）。
多重比較: 規則2 × 群2（銘柄 15 本の個別は記述）。

【捨てた案の数】
約6: ローリング3年窓の純損益を y_t にする案（重なりで自己相関が強く、年ブロックの意味が薄れる→暦年）、
scipy.optimize.curve_fit（依存を増やさない→グリッド）、λ を [0,∞) に制限する案（区間が 0 を含むかを問えなくなる→負も許す）、
半減期を直接ブートストラップする案（λ≤0 で発散→λ の区間を主に）、シャープ比を y_t にする案（bp/日 の方がコストと比べやすい）、
群全体をプールして1本の λ を当てる案（銘柄の差を消す→銘柄ごと＋群の平均）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。年次の形（例: 2008 年の順張りの好成績）を知っている可能性があり、
後知恵を完全には排除できない。ただし規則・モデル・判定は事前固定で、選ぶ余地は λ のグリッドだけ。

【委託の確かめ方】
設計は Fable（specs20.py）、コードは Claude（Fable 5.1 下請け、2026-10-09）、実行と解釈は Sonnet／Opus が後で行う。
実行者は結果 JSON のパス・主要な数値（群ごとの λ 平均・条件を満たす銘柄数・ΔAIC）・原典の箇所を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定のブートストラップと並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_trend_pnl_half_life_q143.py            （B=500。ブートストラップと帰無の両方に同じ B）
      python3 kensho_trend_pnl_half_life_q143.py --B 50
      python3 kensho_trend_pnl_half_life_q143.py --smoke
事前登録からの変更点: なし（非線形最小二乗は λ グリッド＋線形 LS で実装。λ の探索範囲 [−0.5, 3] は実装上の固定値）。
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
DON_ENTRY, DON_EXIT = 55, 20
MIN_DAYS = 100
LAM_MIN, LAM_MAX, LAM_STEP = -0.5, 3.0, 0.005
NULL_B = 500
SEED = 20261009
QID = "Q143"
RULES = ["TSMOM20", "DONCHIAN55_20"]


# ----------------------------------------------------------------------------- 道具
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


def daily_net_pnl_bp(c, signal, cost_rt, warm=LOOKBACK):
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:warm + 1] = 0.0
    return pnl


def yearly_series(t, pnl, warm):
    years = pd.Series(t).dt.year.values
    idx_ok = np.arange(len(pnl)) > warm
    rows = []
    for y in np.unique(years):
        m = (years == y) & idx_ok
        if m.sum() >= MIN_DAYS:
            rows.append((int(y), float(pnl[m].mean()), int(m.sum())))
    return rows


LAM_GRID = np.arange(LAM_MIN, LAM_MAX + 1e-9, LAM_STEP)


def fit_exp(tt, y, grid=LAM_GRID):
    """y = a·exp(−λt) + b を λ グリッド × 線形 LS で。(λ, a, b, RSS)。"""
    tt = np.asarray(tt, float); y = np.asarray(y, float)
    n = len(y)
    X = np.exp(-np.outer(grid, tt))                      # (nλ, n)
    xm = X.mean(axis=1, keepdims=True); ym = y.mean()
    xc = X - xm; yc = y - ym
    sxx = (xc ** 2).sum(axis=1); sxy = (xc * yc).sum(axis=1)
    ok = sxx > 1e-12 * max(1.0, (X ** 2).sum(axis=1).max())
    a = np.where(ok, sxy / np.where(ok, sxx, 1.0), 0.0)
    rss = (yc ** 2).sum() - np.where(ok, a * sxy, 0.0)
    rss = np.where(ok, rss, np.inf)
    k = int(np.argmin(rss))
    lam = float(grid[k]); aa = float(a[k]); bb = float(ym - aa * xm[k, 0])
    return lam, aa, bb, float(max(rss[k], 1e-18))


def fit_const(y):
    y = np.asarray(y, float)
    return float(y.mean()), float(max(((y - y.mean()) ** 2).sum(), 1e-18))


def aic(rss, n, k):
    return float(n * math.log(rss / n) + 2 * k)


def analyze_symbol(tt, y, B, rng):
    n = len(y)
    c, rss_c = fit_const(y)
    lam, a, b, rss_e = fit_exp(tt, y)
    out = dict(n_years=int(n), c=c, a=a, b=b, lam=lam, rss_const=rss_c, rss_exp=rss_e,
               aic_const=aic(rss_c, n, 1), aic_exp=aic(rss_e, n, 3))
    out["dAIC_const_minus_exp"] = out["aic_const"] - out["aic_exp"]
    out["half_life_years"] = float(math.log(2) / lam) if lam > 0 else float("nan")
    # 年ブロック・ブートストラップ（ペア復元抽出）
    boots = []
    for _ in range(B):
        ix = rng.integers(0, n, n)
        if len(np.unique(tt[ix])) < 3:
            continue
        boots.append(fit_exp(tt[ix], y[ix])[0])
    boots = np.asarray(boots)
    if len(boots) >= 10:
        out["lam_ci_lo"] = float(np.percentile(boots, 2.5)); out["lam_ci_hi"] = float(np.percentile(boots, 97.5))
    else:
        out["lam_ci_lo"] = out["lam_ci_hi"] = float("nan")
    # 帰無: 年の並べ替え
    nulls = np.array([fit_exp(tt, y[rng.permutation(n)])[0] for _ in range(B)])
    if len(nulls) >= 10:
        out["lam_null_p95"] = float(np.percentile(nulls, 95)); out["lam_null_mean"] = float(nulls.mean())
        out["lam_null_pct"] = float((nulls < lam).mean())
    else:
        out["lam_null_p95"] = out["lam_null_mean"] = out["lam_null_pct"] = float("nan")
    out["ci_excludes_zero_pos"] = bool(np.isfinite(out["lam_ci_lo"]) and out["lam_ci_lo"] > 0)
    out["above_null_p95"] = bool(np.isfinite(out["lam_null_p95"]) and lam > out["lam_null_p95"])
    out["decay_ok"] = bool(out["ci_excludes_zero_pos"] and out["above_null_p95"])
    out["flat_ok"] = bool(out["dAIC_const_minus_exp"] < 2.0)
    return out


def judge(per, groups):
    """per: {rule: {sym: dict}}。群×規則ごとに機械判定。"""
    res = {}
    for rule in RULES:
        for gname, syms in groups.items():
            if gname == "全15":
                continue
            rows = [per[rule][s] for s in syms if s in per[rule]]
            n = len(rows)
            n_decay = sum(r["decay_ok"] for r in rows); n_flat = sum(r["flat_ok"] for r in rows)
            lam_mean = float(np.mean([r["lam"] for r in rows])) if rows else float("nan")
            lam_median = float(np.median([r["lam"] for r in rows])) if rows else float("nan")
            n_boundary = int(sum((r["lam"] <= LAM_MIN + 1e-9) or (r["lam"] >= LAM_MAX - 1e-9) for r in rows))
            c_mean = float(np.mean([r["c"] for r in rows])) if rows else float("nan")
            decay = n > 0 and n_decay > n / 2
            flat = n > 0 and n_flat > n / 2
            if decay:
                v = "減衰している"
            elif flat:
                v = "最初から0（減衰ではない）" if gname == "FX8" else "一定（減衰ではない）"
            else:
                v = "未確定（Q063 と同じ）"
            res[f"{rule}|{gname}"] = dict(n_syms=n, n_decay_ok=int(n_decay), n_flat_ok=int(n_flat), lam_mean=lam_mean,
                                          lam_median=lam_median, n_lam_at_boundary=n_boundary,
                                          c_mean_bp=c_mean, verdict=v)
    return dict(by_rule_group=res, primary=RULES[0],
                rule="減衰=群の過半で λ の区間が0を含まず(lo>0)かつ帰無の95点より上。最初から0=ΔAIC(一定−指数)<2 の銘柄が過半。他は未確定",
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定、減った理由の4分類の当てはめ）は実行者が記録する。")


def make_plot(yearly, per, path):
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
        syms = [s for s in SYMS if s in per["TSMOM20"]]
        fig, axes = plt.subplots(3, 5, figsize=(15, 8), sharex=False)
        for ax, sym in zip(axes.ravel(), syms):
            g = yearly[(yearly.sym == sym) & (yearly.rule == "TSMOM20")]
            r = per["TSMOM20"][sym]
            ax.plot(g.year, g.y, "o-", ms=3, lw=.8)
            tt = g.year.values - g.year.values[0]
            ax.plot(g.year, r["a"] * np.exp(-r["lam"] * tt) + r["b"], "r--", lw=.8)
            ax.axhline(r["c"], c="gray", lw=.6); ax.axhline(0, c="k", lw=.4)
            ax.set_title(f"{sym} λ={r['lam']:.2f} ΔAIC={r['dAIC_const_minus_exp']:+.1f}", fontsize=9)
        fig.suptitle("TSMOM20 年次純損益（bp/日）と指数減衰の当てはめ"); fig.tight_layout()
        fig.savefig(path, dpi=110); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="ブートストラップ回数＝帰無の並べ替え回数")
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
            decay = np.exp(-np.arange(n) / 2000.0) * (0.15 if k % 2 else 0.0)   # 偶数番は最初から0、奇数番は減衰
            for i in range(1, n):
                r[i] = phi * decay[i] * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
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

    yearly_rows = []; per = {r: {} for r in RULES}
    for sym, (t, c) in series.items():
        sigs = {"TSMOM20": (tsmom_positions(c), LOOKBACK), "DONCHIAN55_20": (donchian_positions(c), DON_ENTRY)}
        for rule, (sig, warm) in sigs.items():
            pnl = daily_net_pnl_bp(c, sig, COST_RT[sym], warm)
            ys = yearly_series(t, pnl, warm)
            if len(ys) < 5:
                continue
            years = np.array([a for a, _, _ in ys]); y = np.array([b for _, b, _ in ys])
            tt = (years - years[0]).astype(float)
            for yr, val, nd in ys:
                yearly_rows.append(dict(sym=sym, rule=rule, year=yr, y=val, n_days=nd))
            r = analyze_symbol(tt, y, B, rng)
            r["first_year"] = int(years[0]); r["last_year"] = int(years[-1])
            per[rule][sym] = r
    yearly = pd.DataFrame(yearly_rows)
    verdict = judge(per, groups)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_yearly_{stamp}.csv"); yearly.to_csv(csv_path, index=False)
    fit_rows = [dict(sym=s, rule=rule, **v) for rule in RULES for s, v in per[rule].items()]
    fit_csv = os.path.join(OUT, f"{prefix}{QID}_fits_{stamp}.csv"); pd.DataFrame(fit_rows).to_csv(fit_csv, index=False)
    png_path = make_plot(yearly, per, os.path.join(OUT, f"{prefix}{QID}_fits_{stamp}.png"))
    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(LOOKBACK=LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT, MIN_DAYS=MIN_DAYS,
                      LAM_GRID=[LAM_MIN, LAM_MAX, LAM_STEP], B=B, SEED=SEED, COST_RT=COST_RT, rules=RULES,
                      syms=syms_used, missing_syms=missing, n_missing=len(missing), data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        per_symbol=per, judgement=verdict,
        files=dict(yearly_csv=csv_path, fits_csv=fit_csv, fits_png=png_path),
        multiple_comparisons="規則2 × 群2 = 4（主は TSMOM20 × 群2。銘柄15本の個別は記述）",
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(syms_used)} missing={missing} B={B} smoke={args.smoke} elapsed={elapsed:.1f}s")
    for rule in RULES:
        for sym in syms_used:
            r = per[rule].get(sym)
            if r is None:
                continue
            print(f"  {rule:13s} {sym:7s} n={r['n_years']:2d} c={r['c']:+.2f} λ={r['lam']:+.3f} [{r['lam_ci_lo']:+.2f},{r['lam_ci_hi']:+.2f}] "
                  f"null95={r['lam_null_p95']:+.2f} ΔAIC={r['dAIC_const_minus_exp']:+.2f} decay={int(r['decay_ok'])} flat={int(r['flat_ok'])}")
    for k, v in verdict["by_rule_group"].items():
        print(f"  判定(機械) {k}: {v['verdict']} (decay {v['n_decay_ok']}/{v['n_syms']}, flat {v['n_flat_ok']}/{v['n_syms']}, λ平均={v['lam_mean']:+.3f})")
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
