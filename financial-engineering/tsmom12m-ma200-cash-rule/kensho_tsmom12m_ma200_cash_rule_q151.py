#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q151: 12か月リターン>0 かつ 200日線上で保有・外れたら現金の規則は、循環シフトの帰無より下落が浅いか
（Korzan 2026 式1 の規則を 15銘柄 D1 で・Q097 の型）
================================================================================

【出典】
- 事前登録: /tmp/claude-0/specs20.py の Q151（Fable 2026-10-09）＝アイデア候補.md の行。
- 論文ノート: Korzan 2026 二周期の株式ローテーション戦略_凍結した規則の評価（式1: 252 日リターン > 0 かつ SMA200 超え）、
  知見（Q097）: トレンドフォローの最大下落の軽さは市場滞在時間が同じ無作為なタイミングより浅い（循環シフト検定で支持・2026-10-08）、
  ブログ QuanterLab 2026b-2: SPY 全期間で 200 日線は最大下落を抑える。

【仮説（測る前に固定）】
H: Korzan 式1 の保有／現金の規則は、露出（市場滞在時間）と切替回数を保った無作為なタイミング（循環シフト）より
   最大下落が浅い。これが SPX 固有でなく、トレンド 7 銘柄の過半で前後半とも再現する。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄。
買い持ちの対象になる トレンド7（XAUUSD XAGUSD WTI UKOIL US500 USTECH BTCUSD）を主、FX8 は対照（記述）。無いファイルは除く。

【定義（1通りに固定）】
- 規則（1 本固定・Korzan 式1）: 終値 c_t で判定。保有 = (c_t / c_{t−252} − 1 > 0) かつ (c_t > SMA200_t)、それ以外は現金（pos=0）。
  翌日約定（t 日の引けの合図を t+1 に持つ）。片道コスト段階1（COST_RT の半分）。現金の金利は 0 と置く（Korzan と違う点）。
  日次純損益 [bp] は daily_net_pnl_bp のとおり（warmup=252）。
- 評価の量（Q097 と同じ）: 日次純損益（bp）の累積和の最大下落 MDD [bp]（ピークからの最大の落ち込み、負の値）と、
  日次純損益の下位 5% の平均 CVaR5 [bp]。あわせて純損益の平均 [bp/日]、買い持ち（pos=1 固定・コストなし）との差、露出・切替回数。
- 帰無（循環シフト・露出と切替回数を保つ）: 評価期間内の合図の列 pos_t を s 日（252 ≤ s ≤ n−252）だけ循環シフトし、同じ期間の
  リターンに当てて MDD・CVaR5 を出す。s は許される範囲から無作為に B=2000 個（重複なし。範囲が B より狭ければ全部）。
  観測の MDD が帰無の浅い側 5% 以内 = 帰無の MDD のうち観測より浅い（絶対値が小さい）ものの割合 ≤ 0.05。
- 期間: 前半 = year < 2017、後半 = year ≥ 2017、全期間（記述）。シフトは各期間の中で行う。

【測るもの】
銘柄×期間で、MDD・CVaR5・純損益・買い持ちの差・露出・切替回数・帰無の分位（浅い側の割合）と z。

【判定（事前固定・変更禁止）】
- トレンド7 のうち、前半・後半の両方で MDD が循環シフトの浅い側 5% 以内の銘柄が 5 以上なら「タイミングによる防御は複数資産で再現」。
  3 以下なら「SPX 固有」。4 は未確定。
- 純リターンが買い持ちを上回るかは記述（Q097 と同じく判定に使わない）。CVaR5 も記述。FX8 は対照として記述。
- 多重比較: 15 銘柄 × 2 期間 × 2 指標（判定はトレンド7 × 2 期間 × MDD）。

【捨てた案の数】
約5: ブロック・ブートストラップの帰無（露出が変わるので循環シフトに）、複利の MDD（bp の累積和に統一・Q097 と同じ）、
現金に短期金利を付ける案（データが無い・0 と明記）、SMA200 だけの規則（Korzan 式1 に固定）、売り側も持つ案（買い／現金のみ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。2020 年・2022 年の下落を知っている可能性はあるが、規則は固定で
帰無はその銘柄自身の列の循環シフトなので、相場観で結果を作る余地は小さい。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、2026-10-09）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は結論ではなく、結果 JSON のパス・トレンド7 の MDD の分位（前半/後半）・原典の箇所（Korzan 式1、Q097）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定のシフトの抽出だけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_tsmom12m_ma200_cash_rule_q151.py            （B=2000、1 分前後）
      python3 kensho_tsmom12m_ma200_cash_rule_q151.py --B 200
      python3 kensho_tsmom12m_ma200_cash_rule_q151.py --smoke    （合成データで経路の確認。結果は捨てる）
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
# 段階1の保守的な往復コスト（価格単位）。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

MOM_N = 252
SMA_N = 200
WARMUP = 252
MIN_SHIFT = 252
CVAR_Q = 0.05
SPLIT_YEAR = 2017
NULL_B = 2000
SEED = 20261009
MIN_DAYS = 600         # 評価期間に要る最小日数（シフト範囲が空にならないよう 2×MIN_SHIFT より大きく）


# ----------------------------------------------------------------------------- 基本の道具
def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


def max_drawdown(P):
    """P: (B, n) 日次損益。累積和のピークからの最大の落ち込み（負の値）。"""
    cs = np.cumsum(P, axis=1)
    cs = np.concatenate([np.zeros((cs.shape[0], 1)), cs], axis=1)
    peak = np.maximum.accumulate(cs, axis=1)
    return (cs - peak).min(axis=1)


def cvar(P, q=CVAR_Q):
    """下位 q の平均（負の値）。"""
    k = max(1, int(math.floor(P.shape[1] * q)))
    part = np.partition(P, k - 1, axis=1)[:, :k]
    return part.mean(axis=1)


# ----------------------------------------------------------------------------- データ
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def synthetic_series(syms):
    """合成: AR(1) の対数リターン（φ を銘柄ごとに変える・トレンド群は正のドリフト）。経路の確認だけが目的。"""
    g = np.random.default_rng(1)
    dates = pd.bdate_range("2008-02-01", "2026-07-14")
    out = {}
    for k, sym in enumerate(syms):
        phi = -0.1 + 0.3 * (k / (len(syms) - 1))
        drift = 0.0003 if sym in TREND7 else 0.0
        e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
        for i in range(1, len(dates)):
            r[i] = phi * r[i - 1] + e[i]
        base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
        out[sym] = (dates.values, base * np.exp(np.cumsum(r + drift)))
    return out


# ----------------------------------------------------------------------------- ルール
def korzan_positions(c):
    """保有 = 252 日リターン > 0 かつ c > SMA200。長さ n、未定義は 0。"""
    n = len(c); pos = np.zeros(n)
    sma = pd.Series(c).rolling(SMA_N).mean().values
    mom = np.full(n, np.nan); mom[MOM_N:] = c[MOM_N:] / c[:-MOM_N] - 1.0
    ok = np.isfinite(sma) & np.isfinite(mom)
    pos[ok] = ((mom[ok] > 0) & (c[ok] > sma[ok])).astype(float)
    return pos


def pnl_from_positions(ret, cost_bp, POS):
    """POS: (B, n) t 日のポジション（翌日に持つ量ではなく、t 日に持っている量）。ret, cost_bp: 長さ n。
    純損益 = pos_t × ret_t × 1e4 − |pos_t − pos_{t−1}| × cost_bp_t。"""
    gross = POS * ret[None, :] * 1e4
    prev = np.concatenate([np.zeros((POS.shape[0], 1)), POS[:, :-1]], axis=1)
    dpos = np.abs(POS - prev)
    return gross - dpos * cost_bp[None, :]


# ----------------------------------------------------------------------------- 1銘柄×1期間
def period_stats(ret, cost_bp, held, B, rng):
    """held: 期間内の t 日に持っているポジション（合図は前日の引け）。循環シフトの帰無と比べる。"""
    n = len(ret)
    out = {"n_days": int(n)}
    if n < MIN_DAYS:
        out.update(mdd=float("nan"), cvar5=float("nan"), mean_bp=float("nan"), bh_mean_bp=float("nan"), bh_mdd=float("nan"),
                   exposure=float("nan"), n_switches=int(0), mdd_share_null_shallower=float("nan"), mdd_z=float("nan"),
                   cvar_share_null_shallower=float("nan"), cvar_z=float("nan"), n_shifts=0)
        return out
    obs = pnl_from_positions(ret, cost_bp, held[None, :])[0]
    bh = ret * 1e4
    out.update(mdd=float(max_drawdown(obs[None, :])[0]), cvar5=float(cvar(obs[None, :])[0]), mean_bp=float(obs.mean()),
               bh_mean_bp=float(bh.mean()), bh_mdd=float(max_drawdown(bh[None, :])[0]), bh_cvar5=float(cvar(bh[None, :])[0]),
               exposure=float(held.mean()), n_switches=int(np.abs(np.diff(held)).sum()))
    out["net_minus_bh_bp"] = out["mean_bp"] - out["bh_mean_bp"]
    # 帰無: 循環シフト
    shifts_all = np.arange(MIN_SHIFT, n - MIN_SHIFT + 1)
    if len(shifts_all) > B:
        shifts = rng.choice(shifts_all, size=B, replace=False)
    else:
        shifts = shifts_all
    idx = (np.arange(n)[None, :] - shifts[:, None]) % n
    POS = held[idx]
    # メモリを抑えるため分割
    mdd_n = np.empty(len(shifts)); cv_n = np.empty(len(shifts)); mean_n = np.empty(len(shifts))
    step = 500
    for i in range(0, len(shifts), step):
        Pn = pnl_from_positions(ret, cost_bp, POS[i:i + step])
        mdd_n[i:i + step] = max_drawdown(Pn); cv_n[i:i + step] = cvar(Pn); mean_n[i:i + step] = Pn.mean(axis=1)
    out["n_shifts"] = int(len(shifts))
    out["mdd_share_null_shallower"] = float((mdd_n > out["mdd"]).mean())      # 帰無のほうが浅い割合（小さいほど観測が浅い）
    out["mdd_z"], _ = z_against_null(out["mdd"], mdd_n)
    out["mdd_null_mean"] = float(mdd_n.mean()); out["mdd_null_p05_shallow"] = float(np.percentile(mdd_n, 95))
    out["cvar_share_null_shallower"] = float((cv_n > out["cvar5"]).mean())
    out["cvar_z"], _ = z_against_null(out["cvar5"], cv_n)
    out["cvar_null_mean"] = float(cv_n.mean())
    out["mean_share_null_higher"] = float((mean_n > out["mean_bp"]).mean())
    out["mean_null_mean"] = float(mean_n.mean())
    out["mdd_shallow_5pct"] = bool(out["mdd_share_null_shallower"] <= 0.05)
    out["cvar_shallow_5pct"] = bool(out["cvar_share_null_shallower"] <= 0.05)
    return out


def run(series, B, rng):
    cells = {}; rows = []
    for sym, (t, c) in series.items():
        sig = korzan_positions(c)
        n = len(c)
        held = np.concatenate([[0.0], sig[:-1]])                     # t 日に持っている量
        ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
        cost_bp = np.zeros(n); cost_bp[1:] = (COST_RT[sym] / 2.0) / c[:-1] * 1e4
        yr = pd.DatetimeIndex(t).year.values
        valid = np.arange(n) > WARMUP
        masks = {"前半": valid & (yr < SPLIT_YEAR), "後半": valid & (yr >= SPLIT_YEAR), "全期間": valid}
        for per, m in masks.items():
            idx = np.flatnonzero(m)
            st = period_stats(ret[idx], cost_bp[idx], held[idx], B, rng)
            cells[f"{sym}|{per}"] = st
            rows.append(dict(sym=sym, period=per, group=("トレンド7" if sym in TREND7 else "FX8"), **st))
    return pd.DataFrame(rows), cells


def judge(tab):
    tr = tab[tab.sym.isin(TREND7) & tab.period.isin(["前半", "後半"])]
    both = {}
    for sym in TREND7:
        g = tr[tr.sym == sym]
        flags = {per: bool(g[g.period == per].mdd_shallow_5pct.iloc[0]) if (g.period == per).any() else False
                 for per in ("前半", "後半")}
        both[sym] = dict(**flags, both=bool(flags["前半"] and flags["後半"]))
    n_both = int(sum(v["both"] for v in both.values()))
    verdict = ("タイミングによる防御は複数資産で再現" if n_both >= 5 else
               "SPX 固有" if n_both <= 3 else "未確定（4 銘柄）")
    fx = tab[tab.sym.isin(FX8) & tab.period.isin(["前半", "後半"])]
    n_fx_both = int(sum(bool(fx[(fx.sym == s) & (fx.period == "前半")].mdd_shallow_5pct.any()) and
                        bool(fx[(fx.sym == s) & (fx.period == "後半")].mdd_shallow_5pct.any()) for s in FX8 if (fx.sym == s).any()))
    beats_bh = {per: int((tab[(tab.period == per) & tab.sym.isin(TREND7)].net_minus_bh_bp > 0).sum()) for per in ("前半", "後半", "全期間")}
    return dict(trend7_by_sym=both, n_trend7_both_periods_shallow5pct=n_both, verdict=verdict,
                fx8_both_periods_shallow5pct=n_fx_both,
                trend7_n_net_beats_buyhold=beats_bh,
                note="事前固定の規則で機械的に付けた判定（トレンド7 × 前後半 × MDD の浅い側 5%）。純リターン vs 買い持ち・CVaR5・FX8 は記述。"
                     "解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
            g = tab[tab.period == per].set_index("sym").reindex(SYMS)
            cols = ["tab:orange" if s in TREND7 else "tab:blue" for s in SYMS]
            a.bar(range(len(SYMS)), g.mdd_share_null_shallower.values, color=cols)
            a.axhline(0.05, lw=.8, c="k", ls="--")
            a.set_xticks(range(len(SYMS))); a.set_xticklabels(SYMS, rotation=90, fontsize=7)
            a.set_title(f"{per}: 帰無（循環シフト）のうち観測より MDD が浅い割合（≤0.05 で支持）")
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:  # 図は任意
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="循環シフトの本数")
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
    csv_path = os.path.join(OUT, f"{prefix}Q151_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(tab, os.path.join(OUT, f"{prefix}Q151_mdd_pct_{stamp}.png"))
    out = dict(
        queue_id="Q151", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(time.time() - t0, 1),
        settings=dict(MOM_N=MOM_N, SMA_N=SMA_N, WARMUP=WARMUP, MIN_SHIFT=MIN_SHIFT, CVAR_Q=CVAR_Q, SPLIT_YEAR=SPLIT_YEAR,
                      NULL_B=B, SEED=SEED, MIN_DAYS=MIN_DAYS, cash_rate=0.0, COST_RT=COST_RT, syms=list(series.keys()),
                      missing_syms=missing, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_syms=len(series), n_missing=len(missing),
        cells=cells, judgement=verdict,
        files=dict(cells_csv=csv_path, mdd_pct_png=png_path),
        multiple_comparisons="15 銘柄 × 2 期間 × 2 指標（MDD・CVaR5）＝60。判定はトレンド7 × 2 期間 × MDD",
    )
    jpath = os.path.join(OUT, f"{prefix}Q151_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else
                  (bool(o) if isinstance(o, np.bool_) else str(o)))

    print(f"[Q151] syms={len(series)} missing={missing} B={B} smoke={args.smoke} elapsed={out['elapsed_sec']}s")
    for per in ("前半", "後半", "全期間"):
        print(f"  --- {per}")
        for sym in series:
            r = cells[f"{sym}|{per}"]
            print(f"  {sym:7s} n={r['n_days']:4d} 露出={r['exposure']:.2f} 切替={r['n_switches']:3d}  MDD={r['mdd']:8.0f}bp "
                  f"(帰無が浅い割合={r['mdd_share_null_shallower']:.3f} z={r['mdd_z']:+.2f})  CVaR5={r['cvar5']:7.1f} "
                  f"(浅い割合={r['cvar_share_null_shallower']:.3f})  純={r['mean_bp']:+.2f} 買持={r['bh_mean_bp']:+.2f} bp/日")
    print("  判定(機械):", verdict["verdict"], "| トレンド7 で前後半とも浅い側5%:", verdict["n_trend7_both_periods_shallow5pct"],
          "| FX8:", verdict["fx8_both_periods_shallow5pct"], "| 買い持ちを上回る数:", verdict["trend7_n_net_beats_buyhold"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
