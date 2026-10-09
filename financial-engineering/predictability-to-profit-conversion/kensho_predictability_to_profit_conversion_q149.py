#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q149: 分散比で「予測できる」と出た組は、次の期間にコスト後で儲かるか
（Alahmadi・Basingab 2026 §3.4.1 の変換率・15銘柄 D1・暦年）
================================================================================

【出典】
- 事前登録: /tmp/claude-0/specs20.py の Q149（Fable 2026-10-09）＝アイデア候補.md の行。
- 論文ノート: Alahmadi・Basingab 2026 弱い形の市場効率性検定の体系的レビュー（AI 系は統計的な予測可能性を見つけるが
  コスト後の収益は弱く時間で劣化する。「予測できる」が「儲かる」に変わる割合）、Neely・Weller 2003 為替の日中足テクニカル。

【仮説（測る前に固定）】
H: 年 t の分散比検定で有意（|z*| ≥ 1.96）だった（銘柄, 年）は、年 t+1 に VR の符号に合わせた 1 本の規則で
   コスト後に儲かる（＝予測可能性は翌年の利益に変換される）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄。暦年 2008〜2026
（年 t = 2008〜2025、年 t+1 = 2009〜2026。2026 は 7 月まで）。MIN_DAYS=100 未満の年は捨てる。無いファイルは除く。

【定義（1通りに固定）】
- 日次対数リターン r_t = ln(c_t / c_{t−1})。
- 年 t の分散比 VR(q=5) と不均一分散に頑健な z*（Lo–MacKinlay。Q148 と同じ実装）。
  「予測できる」= |z*| ≥ 1.96。符号: VR > 1 → 持続、VR < 1 → 反転。
- 年 t+1 の規則（1 本固定）: s_t = sign(c_t − c_{t−5})（TSMOM5）。VR_t > 1 なら pos = s（順張り）、VR_t < 1 なら pos = −s
  （逆張り）。翌日約定・片道コスト段階1（COST_RT の半分）。bp 換算は daily_net_pnl_bp のとおり。
  「予測できない」組にも同じ規則（VR の符号で向きを決める）を当てて比較する。
- セル = (銘柄, 年 t+1)。セルの純損益 = 年 t+1 の日次純損益の平均 [bp/日]。
- (a) 予測できる組のうち純損益 > 0 の割合。
- (b) 予測できる組の純損益の合算: 年 t+1 ごとに銘柄平均 → 年を単位にした平均と t。
- (c) 予測できる組の平均 − 予測できない組の平均（セルをプール）。
- 帰無: 年 t の判定ラベル（予測できる／できない）を期間内のセルで並べ替える B=500 回。(c) の帰無分布から z。
  参考に (a)(b) の帰無分布も出す。
- 期間: 前半 = 年 t+1 < 2017、後半 = 年 t+1 ≥ 2017、全期間。群: 全15・FX8・トレンド7（記述）。判定は 全15 の前半・後半。

【測るもの】
(a)(b)(c) と帰無の z（群×期間）、セルの表（VR・z*・ラベル・向き・純損益・日数）。

【判定（事前固定・変更禁止）】
- 期間ごとに: (a) ≥ 0.60 かつ (b) t ≥ 2 かつ (c) 差 > 0 で z ≥ 2 なら「予測可能性は翌年の利益に変換される」。
  (b) t < 2 なら「変換されない」（Alahmadi の整理を支持）。それ以外は未確定。
- 前半/後半で別々に出し、両方「変換される」なら支持、両方「変換されない」なら棄却、割れたら未確定。
- 多重比較: 3 条件 × 2 期間（判定は条件の積）。

【捨てた案の数】
約5: q を複数にして「どれかで有意」をラベルにする案（Q148 の設定依存と混ざる→q=5 の 1 本）、規則を TSMOM20 にする案
（VR(5) の持続と対応する 5 日に）、年 t+1 の最初の 5 日を捨てる案（前年の終値から連続して作れるので不要）、
ラベルを |z*| の大きさで段階にする案（記述に留める）、群別に判定する案（全15 のみ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。ラベルと規則は機械的で、相場観で結果を作れる余地は小さい。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、2026-10-09）。分散比と z* は自前実装（scipy 不要）。
実行と結果の解釈は Sonnet／Opus が後で行う。実行者は結論ではなく、結果 JSON のパス・(a)(b)(c) と z・原典の箇所を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_predictability_to_profit_conversion_q149.py            （B=500、数十秒）
      python3 kensho_predictability_to_profit_conversion_q149.py --B 50
      python3 kensho_predictability_to_profit_conversion_q149.py --smoke    （合成データで経路の確認。結果は捨てる）
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

VR_Q = 5
LOOKBACK = 5           # TSMOM5
ZCRIT = 1.96
YEARS_T = list(range(2008, 2026))
MIN_DAYS = 100
SPLIT_YEAR = 2017      # 年 t+1 で分ける
NULL_B = 500
SEED = 20261009


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
    pct = float((v < obs).mean())
    return float(z), pct


def lm_variance_ratio(r, q):
    """Lo–MacKinlay の分散比と不均一分散に頑健な z*（1 系列）。Q148 と同じ式。"""
    r = np.asarray(r, float); T = len(r)
    if T < 3 * q:
        return float("nan"), float("nan")
    mu = r.mean(); d = r - mu
    s2a = (d ** 2).sum() / (T - 1)
    cs = np.concatenate([[0.0], np.cumsum(r)])
    rq = cs[q:] - cs[:-q]
    m = q * (T - q + 1) * (1.0 - q / T)
    s2c = ((rq - q * mu) ** 2).sum() / m
    vr = s2c / s2a
    d2 = d ** 2; S = d2.sum()
    theta = 0.0
    for j in range(1, q):
        theta += (2.0 * (q - j) / q) ** 2 * (d2[j:] * d2[:-j]).sum() / (S ** 2)
    z = (vr - 1.0) / math.sqrt(theta) if theta > 0 else float("nan")
    return float(vr), float(z)


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


# ----------------------------------------------------------------------------- ルール
def tsmom_positions(c, L=LOOKBACK):
    n = len(c); s = np.zeros(n)
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def daily_net_pnl_bp(c, signal, cost_rt, warmup=LOOKBACK):
    """signal_t を翌日 t+1 に持つ。bp 単位の日次純損益（長さ n、先頭は 0）。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:warmup + 1] = 0.0
    return pnl


# ----------------------------------------------------------------------------- セル
def cells_for(sym, t, c, cost_rt):
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    yr = pd.DatetimeIndex(t).year.values
    s = tsmom_positions(c)
    pnl_trend = daily_net_pnl_bp(c, s, cost_rt)
    pnl_contra = daily_net_pnl_bp(c, -s, cost_rt)
    rows = []
    for y in YEARS_T:
        idx_t = np.flatnonzero(yr == y); idx_t = idx_t[idx_t >= 1]
        idx_n = np.flatnonzero(yr == y + 1); idx_n = idx_n[idx_n > LOOKBACK]
        if len(idx_t) < MIN_DAYS or len(idx_n) < MIN_DAYS:
            continue
        vr, z = lm_variance_ratio(r[idx_t], VR_Q)
        if not np.isfinite(z):
            continue
        direction = 1 if vr > 1.0 else -1
        pnl = pnl_trend[idx_n] if direction == 1 else pnl_contra[idx_n]
        rows.append(dict(sym=sym, year_t=int(y), year_next=int(y + 1), n_days_t=int(len(idx_t)), n_days_next=int(len(idx_n)),
                         VR5=vr, zstar=z, predictable=bool(abs(z) >= ZCRIT), direction=direction,
                         pnl_bp=float(pnl.mean()), pnl_trend_bp=float(pnl_trend[idx_n].mean()),
                         drift_bp=float(r[idx_n].mean() * 1e4)))
    return rows


def stats_for(tab, labels):
    """tab: セル表、labels: 予測できる (bool 配列)。(a)(b)(c) を返す。"""
    p = tab.pnl_bp.values
    pred = labels.astype(bool)
    out = {"n_pred": int(pred.sum()), "n_unpred": int((~pred).sum())}
    if pred.sum() == 0:
        out.update(a_share_positive=float("nan"), b_mean=float("nan"), b_t=float("nan"), b_n_years=0,
                   c_diff=float("nan"), pred_mean=float("nan"), unpred_mean=float("nan"))
        return out
    out["a_share_positive"] = float((p[pred] > 0).mean())
    per_year = pd.Series(p[pred]).groupby(tab.year_next.values[pred]).mean()
    m, tt, n = mean_t(per_year.values)
    out.update(b_mean=m, b_t=tt, b_n_years=n)
    pm = float(p[pred].mean()); um = float(p[~pred].mean()) if (~pred).sum() else float("nan")
    out.update(pred_mean=pm, unpred_mean=um, c_diff=float(pm - um) if np.isfinite(um) else float("nan"))
    return out


def evaluate(tab, B, rng):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    periods = {"前半": tab.year_next < SPLIT_YEAR, "後半": tab.year_next >= SPLIT_YEAR,
               "全期間": pd.Series(True, index=tab.index)}
    res = {}
    for gname, syms in groups.items():
        for per, pm in periods.items():
            g = tab[tab.sym.isin(syms) & pm.values].reset_index(drop=True)
            lab = g.predictable.values.astype(bool)
            o = stats_for(g, lab)
            o["n_cells"] = int(len(g))
            o["share_predictable"] = float(lab.mean()) if len(g) else float("nan")
            o["share_direction_trend"] = float((g.direction == 1).mean()) if len(g) else float("nan")
            # 帰無: ラベルの並べ替え
            na, nb, nc = [], [], []
            if len(g) and lab.sum() > 0 and (~lab).sum() > 0:
                for b in range(B):
                    lp = lab[rng.permutation(len(lab))]
                    s = stats_for(g, lp)
                    na.append(s["a_share_positive"]); nb.append(s["b_mean"]); nc.append(s["c_diff"])
            o["c_z"], o["c_pct"] = z_against_null(o["c_diff"], nc)
            o["a_z"], o["a_pct"] = z_against_null(o["a_share_positive"], na)
            o["b_z"], o["b_pct"] = z_against_null(o["b_mean"], nb)
            o["null_c_mean"] = float(np.nanmean(nc)) if nc else float("nan")
            o["null_c_sd"] = float(np.nanstd(nc, ddof=1)) if len(nc) > 1 else float("nan")
            res[f"{gname}|{per}"] = o
    return res


def judge(res):
    by = {}
    for per in ("前半", "後半"):
        r = res[f"全15|{per}"]
        conv = bool(np.isfinite(r["a_share_positive"]) and r["a_share_positive"] >= 0.60 and
                    np.isfinite(r["b_t"]) and r["b_t"] >= 2.0 and
                    np.isfinite(r["c_diff"]) and r["c_diff"] > 0 and np.isfinite(r["c_z"]) and r["c_z"] >= 2.0)
        notconv = bool(np.isfinite(r["b_t"]) and r["b_t"] < 2.0)
        by[per] = dict(a=r["a_share_positive"], b_t=r["b_t"], c_diff=r["c_diff"], c_z=r["c_z"],
                       label=("変換される" if conv else "変換されない" if notconv else "未確定"))
    labs = [by[p]["label"] for p in ("前半", "後半")]
    verdict = ("予測可能性は翌年の利益に変換される（支持）" if all(l == "変換される" for l in labs) else
               "変換されない（Alahmadi の整理を支持）" if all(l == "変換されない" for l in labs) else
               "未確定（前半/後半で割れた、または条件が一部欠けた）")
    return dict(by_period=by, verdict=verdict,
                note="事前固定の規則で機械的に付けた判定（全15、(a)≥0.60 かつ (b)t≥2 かつ (c)差>0・z≥2）。"
                     "解釈（確定／ノイズ／未確定）と群別の記述は実行者が記録する。")


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
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for lab, col in [(True, "tab:red"), (False, "tab:gray")]:
            g = tab[tab.predictable == lab]
            ax.scatter(g.zstar, g.pnl_bp, s=12, alpha=.6, c=col, label=("予測できる" if lab else "予測できない"))
        ax.axhline(0, lw=.6, c="k"); ax.axvline(ZCRIT, lw=.6, c="gray", ls="--"); ax.axvline(-ZCRIT, lw=.6, c="gray", ls="--")
        ax.set_xlabel("年 t の z*(q=5)"); ax.set_ylabel("年 t+1 の純損益（bp/日）"); ax.legend()
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

    rows = []
    for sym, (t, c) in series.items():
        rows.extend(cells_for(sym, t, c, COST_RT[sym]))
    tab = pd.DataFrame(rows)
    res = evaluate(tab, B, rng)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q149_cells_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(tab, os.path.join(OUT, f"{prefix}Q149_scatter_{stamp}.png"))
    out = dict(
        queue_id="Q149", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(time.time() - t0, 1),
        settings=dict(VR_Q=VR_Q, LOOKBACK=LOOKBACK, ZCRIT=ZCRIT, YEARS_T=[YEARS_T[0], YEARS_T[-1]], MIN_DAYS=MIN_DAYS,
                      SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=list(series.keys()),
                      missing_syms=missing, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_syms=len(series), n_missing=len(missing), n_cells=int(len(tab)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, scatter_png=png_path),
        multiple_comparisons="判定は 3 条件 × 2 期間（条件の積）。群別（FX8・トレンド7）と全期間は記述のみ",
    )
    jpath = os.path.join(OUT, f"{prefix}Q149_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else
                  (bool(o) if isinstance(o, np.bool_) else str(o)))

    print(f"[Q149] syms={len(series)} missing={missing} cells={len(tab)} B={B} smoke={args.smoke} elapsed={out['elapsed_sec']}s")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_cells']:3d} pred={r['n_pred']:3d}  (a)={r['a_share_positive']:.3f}  "
                  f"(b) mean={r['b_mean']:+.2f}bp t={r['b_t']:+.2f}  (c) diff={r['c_diff']:+.2f}bp z={r['c_z']:+.2f}")
    print("  判定(機械):", verdict["verdict"], "|", {p: v["label"] for p, v in verdict["by_period"].items()})
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
