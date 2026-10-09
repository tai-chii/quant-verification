#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q137: データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q137（Fable 2026-10-09）＝ アイデア候補.md の行。
- 論文ノート: Korzan2026_二周期の株式ローテーション戦略_凍結した規則の評価（§5.1: Nasdaq の価格でシグナルを
  作り直すと目標が一致した日は 49.51%・不合格）。
- FX改善ログ 2026-07-14（XAUUSD の yahoo 差は先物ベーシス）。

【仮説（測る前に固定）】
記述の問い。「同じ規則を Dukascopy と Yahoo の日足で走らせたとき、合図の一致率と純損益の差はどれだけか」。
Korzan の 49.51% のような「データ源が規則の定義の一部」になる状況が、手元の為替・金でも起きるかを測る。

【データ】
- `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足。列 time,open,high,low,close）
- `data_<SYM>_D1_yahoo.csv`（Yahoo 日足。列 time,open,high,low,close）
- 対象: EURUSD GBPUSD AUDUSD USDJPY EURJPY GBPJPY XAUUSD のうち両方のファイルがある銘柄。無い銘柄は除いて
  件数を JSON に書く。両ソースの共通の日付だけ使う（値動きのない足 high==low は除いた後で共通化）。

【定義（1通りに固定）】
- 合図 (i) SMA200: s_t = sign(c_t − SMA200_t)（共通日付の系列で 200 日単純移動平均）。
- 合図 (ii) TSMOM20: s_t = sign(c_t − c_{t−20})。
- 一致率 = 両ソースの s_t が定義されている日のうち、同じ符号（0 も含めて同じ値）の日の割合。不一致率 = 1 − 一致率。
- 純損益: 各ソースの終値で同じ規則を走らせ、翌日のポジション × 翌日リターン（bp）− ポジション変化 × 片道コスト（段階1
  の保守値 COST_RT の半分を bp に換算）。日次純損益の差 Δ_t = Dukascopy − Yahoo。
- 年差の t: 年ごとに Δ_t を平均し、年を単位に平均/標準誤差（年数 ≥ 3）。
- 終値差 = (c_yahoo / c_duka − 1) × 1e4 [bp] の分布（平均・中央値・SD・5/95%点・|差|の平均）。
- 参考（帰無の代わり）: 同じソース（Dukascopy）で合図を 1 日ずらした自分自身との一致率。

【測るもの】
銘柄 × 合図2本で: 一致率・不一致率・純損益の年差の平均と t・終値差の分布・1 日ずらしの自己一致率。
合算（銘柄平均）も出す。期間: 全期間。前半（<2017）/ 後半（≥2017）は記述。

【判定（事前固定・変更禁止）】
判定の対象は XAUUSD を除く銘柄（XAUUSD は先物ベーシスの既知の差があるので別枠で記述）。合図2本の両方で評価。
- 全銘柄で一致率 ≥ 99% かつ 純損益の年差の |t| < 2（全ての銘柄・合図）→「データ源は結論を変えない」。
- 1 銘柄でも一致率 < 95%（どちらかの合図）→「データ源は規則の定義の一部」（Korzan と同じ）。
- 間 → 未確定。
多重比較: 銘柄（最大6）× 合図 2 の t を見る。判定は上の規則で機械的に付け、解釈は実行者。

【捨てた案の数】
約4: 日付の対応を ±1 日の許容で合わせる案（Yahoo の日付規約がソースで違うと一致率が人工的に上がる → 共通日付の厳密一致に）、
ドンチャン 55/20 を 3 本目に加える案（取引が少なく一致率が粗い → 2 本固定）、Yahoo の調整終値を使う案（FX には無い）、
高値安値の差も出す案（規則が終値だけ使う → 終値差のみ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証は記述で、相場観は使わない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude Fable 5.1（この下請け）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（銘柄×合図の一致率・年差の t）・原典の箇所（Korzan §5.1）を本体に返す。

【実装】自己完結・決定的（乱数は使わない。--B は他スクリプトとの互換のためだけに受け、未使用）。
依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_data_source_signal_agreement_q137.py           （数秒）
      python3 kensho_data_source_signal_agreement_q137.py --smoke   （合成データで経路確認。結果は results/smoke_*）
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

SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURJPY", "GBPJPY", "XAUUSD"]
JUDGE_SYMS = [s for s in SYMS if s != "XAUUSD"]      # XAUUSD は別枠で記述
# 段階1の保守的な往復コスト（価格単位）。kensho_donchian_regime.py と同じ値。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20
SMA_N = 200
SPLIT_YEAR = 2017
MIN_YEARS = 3
SEED = 20261009
AGREE_HI, AGREE_LO, T_TH = 0.99, 0.95, 2.0   # 判定の閾値（事前固定）


# ----------------------------------------------------------------------------- 基本の道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def load_csv(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d["time"] = pd.to_datetime(d["time"]).dt.tz_localize(None).dt.normalize()
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


# ----------------------------------------------------------------------------- ルール
def tsmom_signal(c, L=LOOKBACK):
    n = len(c); s = np.full(n, np.nan)
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def sma_signal(c, N=SMA_N):
    sma = pd.Series(c).rolling(N).mean().values
    return np.sign(c - sma)          # SMA が nan の先頭は nan


def daily_net_pnl_bp(c, signal, cost_rt, warm):
    """signal_t を翌日 t+1 に持つ。bp 単位の日次純損益（長さ n、先頭 warm+1 日は 0）。"""
    n = len(c)
    sig = np.where(np.isfinite(signal), signal, 0.0)
    pos_prev = np.concatenate([[0.0], sig[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:warm + 1] = 0.0
    return pnl


# ----------------------------------------------------------------------------- 1銘柄の評価
def evaluate_symbol(sym, t, c_duk, c_yah):
    """共通日付に揃えた2系列から、合図2本の一致率・純損益差・終値差を出す。"""
    years = pd.DatetimeIndex(t).year
    out = {"n_days": int(len(t)), "start": str(pd.Timestamp(t[0]).date()), "end": str(pd.Timestamp(t[-1]).date())}
    # 終値差の分布
    diff_bp = (c_yah / c_duk - 1.0) * 1e4
    out["close_diff_bp"] = dict(mean=float(diff_bp.mean()), median=float(np.median(diff_bp)), sd=float(diff_bp.std(ddof=1)),
                                p05=float(np.percentile(diff_bp, 5)), p95=float(np.percentile(diff_bp, 95)),
                                mean_abs=float(np.abs(diff_bp).mean()))
    for name, fn, warm in (("SMA200", sma_signal, SMA_N), ("TSMOM20", tsmom_signal, LOOKBACK)):
        s_d = fn(c_duk); s_y = fn(c_yah)
        m = np.isfinite(s_d) & np.isfinite(s_y)
        agree = float((s_d[m] == s_y[m]).mean()) if m.sum() else float("nan")
        # 参考: 1 日ずらした自分自身との一致率（Dukascopy）
        m1 = np.isfinite(s_d[1:]) & np.isfinite(s_d[:-1])
        self_lag1 = float((s_d[1:][m1] == s_d[:-1][m1]).mean()) if m1.sum() else float("nan")
        p_d = daily_net_pnl_bp(c_duk, s_d, COST_RT[sym], warm)
        p_y = daily_net_pnl_bp(c_yah, s_y, COST_RT[sym], warm)
        valid = np.arange(len(c_duk)) > warm
        d = p_d - p_y
        per_year = pd.DataFrame({"year": years[valid], "diff": d[valid], "duk": p_d[valid], "yah": p_y[valid]}).groupby("year").mean()
        mean_diff, t_diff, n_years = mean_t(per_year["diff"].values)
        rec = dict(agree_rate=agree, disagree_rate=(1.0 - agree) if np.isfinite(agree) else float("nan"),
                   n_compared=int(m.sum()), self_lag1_agree_rate=self_lag1,
                   pnl_duk_bp=float(p_d[valid].mean()), pnl_yah_bp=float(p_y[valid].mean()),
                   diff_year_mean_bp=mean_diff, diff_year_t=t_diff, n_years=n_years,
                   per_year_diff_bp={int(k): float(v) for k, v in per_year["diff"].items()})
        for per, mask in (("前半", years < SPLIT_YEAR), ("後半", years >= SPLIT_YEAR)):
            mm = m & mask
            rec[f"agree_rate_{per}"] = float((s_d[mm] == s_y[mm]).mean()) if mm.sum() else float("nan")
            py = per_year[(per_year.index < SPLIT_YEAR) if per == "前半" else (per_year.index >= SPLIT_YEAR)]
            md, td, ny = mean_t(py["diff"].values)
            rec[f"diff_year_t_{per}"] = td; rec[f"diff_year_mean_bp_{per}"] = md; rec[f"n_years_{per}"] = ny
        out[name] = rec
    return out


# ----------------------------------------------------------------------------- 判定
def judge(res, syms_judged):
    rules = ("SMA200", "TSMOM20")
    agree_all = [res[s][r]["agree_rate"] for s in syms_judged for r in rules]
    t_all = [res[s][r]["diff_year_t"] for s in syms_judged for r in rules]
    detail = {s: {r: dict(agree=res[s][r]["agree_rate"], t=res[s][r]["diff_year_t"]) for r in rules} for s in syms_judged}
    if not syms_judged:
        return dict(verdict="判定不能（対象銘柄なし）", detail=detail, note="判定対象の銘柄が 0。")
    fin_a = [a for a in agree_all if np.isfinite(a)]
    fin_t = [x for x in t_all if np.isfinite(x)]
    cond_same = bool(fin_a and all(a >= AGREE_HI for a in fin_a) and all(abs(x) < T_TH for x in fin_t))
    cond_part = bool(any(a < AGREE_LO for a in fin_a))
    if cond_part:
        verdict = "データ源は規則の定義の一部（Korzan と同じ）"
    elif cond_same:
        verdict = "データ源は結論を変えない"
    else:
        verdict = "未確定"
    return dict(verdict=verdict, judged_syms=list(syms_judged), min_agree=float(min(fin_a)) if fin_a else float("nan"),
                max_abs_t=float(max(abs(x) for x in fin_t)) if fin_t else float("nan"),
                thresholds=dict(agree_hi=AGREE_HI, agree_lo=AGREE_LO, t=T_TH), detail=detail,
                xauusd_separately=("XAUUSD" in res),
                note="事前固定の規則で機械的に付けた判定（XAUUSD は除外・別枠で記述）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
        syms = list(res.keys())
        x = np.arange(len(syms))
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        for k, r in enumerate(("SMA200", "TSMOM20")):
            ax[0].bar(x + (k - 0.5) * 0.4, [res[s][r]["agree_rate"] for s in syms], width=0.4, label=r)
            ax[1].bar(x + (k - 0.5) * 0.4, [res[s][r]["diff_year_t"] for s in syms], width=0.4, label=r)
        ax[0].axhline(AGREE_HI, c="gray", ls="--", lw=.7); ax[0].axhline(AGREE_LO, c="gray", ls=":", lw=.7)
        ax[0].set_ylim(0.8, 1.0); ax[0].set_title("合図の一致率（Dukascopy vs Yahoo）"); ax[0].set_xticks(x); ax[0].set_xticklabels(syms, rotation=45)
        ax[1].axhline(2, c="gray", ls="--", lw=.7); ax[1].axhline(-2, c="gray", ls="--", lw=.7); ax[1].axhline(0, c="k", lw=.6)
        ax[1].set_title("純損益の年差の t（Duka − Yahoo）"); ax[1].set_xticks(x); ax[1].set_xticklabels(syms, rotation=45)
        ax[0].legend(); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:  # 図は任意
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 本体
def synth_pair(sym, k, g):
    """合成: Dukascopy は AR(1)、Yahoo は同じ系列＋小さな雑音＋一部の日が欠ける。"""
    dates = pd.bdate_range("2008-02-01", "2026-07-14")
    phi = -0.1 + 0.3 * (k / 6)
    e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
    for i in range(1, len(dates)):
        r[i] = phi * r[i - 1] + e[i]
    base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500}.get(sym, 1.2)
    c = base * np.exp(np.cumsum(r))
    noise = 0.0003 * (3 if sym == "XAUUSD" else 1)
    cy = c * np.exp(g.normal(0, noise, len(dates)) + (0.002 if sym == "XAUUSD" else 0.0))
    keep = g.random(len(dates)) > 0.02
    d_duk = pd.DataFrame(dict(time=dates, open=c, high=c * 1.001, low=c * 0.999, close=c))
    d_yah = pd.DataFrame(dict(time=dates[keep], open=cy[keep], high=cy[keep] * 1.001, low=cy[keep] * 0.999, close=cy[keep]))
    return d_duk, d_yah


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=0, help="未使用（帰無なし・互換のため）")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    res, spans, missing = {}, {}, {}
    for k, sym in enumerate(SYMS):
        if args.smoke:
            d_duk, d_yah = synth_pair(sym, k, np.random.default_rng(1 + k))
        else:
            f_d = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
            f_y = os.path.join(DATA_DIR, f"data_{sym}_D1_yahoo.csv")
            if not (os.path.exists(f_d) and os.path.exists(f_y)):
                missing[sym] = dict(fromH1=os.path.exists(f_d), yahoo=os.path.exists(f_y)); continue
            try:
                d_duk, d_yah = load_csv(f_d), load_csv(f_y)
            except Exception as e:
                missing[sym] = dict(error=str(e)); continue
        j = pd.merge(d_duk[["time", "close"]], d_yah[["time", "close"]], on="time", suffixes=("_duk", "_yah")).sort_values("time")
        if len(j) < SMA_N + 50:
            missing[sym] = dict(common_days=int(len(j)), reason="共通日付が少なすぎる"); continue
        t = j.time.values; c_d = j.close_duk.values.astype(float); c_y = j.close_yah.values.astype(float)
        res[sym] = evaluate_symbol(sym, t, c_d, c_y)
        spans[sym] = dict(duk_n=int(len(d_duk)), yahoo_n=int(len(d_yah)), common_n=int(len(j)),
                          start=str(pd.Timestamp(t[0]).date()), end=str(pd.Timestamp(t[-1]).date()))

    judged = [s for s in JUDGE_SYMS if s in res]
    verdict = judge(res, judged)
    # 合算（銘柄平均・判定対象のみ）
    summary = {}
    for r in ("SMA200", "TSMOM20"):
        a = [res[s][r]["agree_rate"] for s in judged]; tt = [res[s][r]["diff_year_t"] for s in judged]
        summary[r] = dict(mean_agree=float(np.nanmean(a)) if a else float("nan"), min_agree=float(np.nanmin(a)) if a else float("nan"),
                          mean_abs_t=float(np.nanmean(np.abs(tt))) if tt else float("nan"),
                          mean_self_lag1=float(np.nanmean([res[s][r]["self_lag1_agree_rate"] for s in judged])) if judged else float("nan"))

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    rows = [dict(sym=s, rule=r, **{k: v for k, v in res[s][r].items() if k != "per_year_diff_bp"}) for s in res for r in ("SMA200", "TSMOM20")]
    csv_path = os.path.join(OUT, f"{prefix}Q137_table_{stamp}.csv"); pd.DataFrame(rows).to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q137_bars_{stamp}.png")) if res else "(図なし: 銘柄なし)"
    out = dict(
        queue_id="Q137", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, SMA_N=SMA_N, SPLIT_YEAR=SPLIT_YEAR, SEED=SEED, COST_RT=COST_RT,
                      syms=SYMS, judge_syms=JUDGE_SYMS, data_dir=DATA_DIR, null="なし（記述の問い。参考に 1 日ずらしの自己一致率）"),
        data_span=spans, missing=missing, n_symbols_used=len(res), n_symbols_missing=len(missing),
        results=res, summary_judged=summary, judgement=verdict,
        xauusd_note=("XAUUSD は先物ベーシスの既知の差（FX改善ログ 2026-07-14）があるため判定から除外し、results['XAUUSD'] で別枠に記述"),
        files=dict(table_csv=csv_path, bars_png=png_path),
        multiple_comparisons=f"銘柄 {len(judged)} × 合図 2 ＝ {2 * len(judged)} 本の t（判定は一致率と |t|<2 の全条件）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q137_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q137] symbols={len(res)} missing={list(missing)} smoke={args.smoke}")
    for s in res:
        for r in ("SMA200", "TSMOM20"):
            x = res[s][r]
            print(f"  {s:7s} {r:8s} agree={x['agree_rate']:.4f} (lag1 self={x['self_lag1_agree_rate']:.4f})  "
                  f"pnl duk={x['pnl_duk_bp']:+.2f} yah={x['pnl_yah_bp']:+.2f}  year diff={x['diff_year_mean_bp']:+.2f}bp t={x['diff_year_t']:+.2f} (n={x['n_years']})"
                  + ("  [別枠]" if s == "XAUUSD" else ""))
        cd = res[s]["close_diff_bp"]
        print(f"          close diff bp: mean={cd['mean']:+.1f} median={cd['median']:+.1f} sd={cd['sd']:.1f} |mean|={cd['mean_abs']:.1f}")
    print("  判定(機械):", verdict["verdict"], "| min agree=", round(verdict.get("min_agree", float("nan")), 4), "| max|t|=", round(verdict.get("max_abs_t", float("nan")), 2))
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
