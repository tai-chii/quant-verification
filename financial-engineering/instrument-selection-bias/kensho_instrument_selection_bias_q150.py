#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q150: 15銘柄から成績の良い 8 銘柄を事後に選ぶと順張りの成績はどれだけ膨らむか
（Korzan 2026 §6 の銘柄選択バイアス・TSMOM20・15銘柄 D1）
================================================================================

【出典】
- 事前登録: /tmp/claude-0/specs20.py の Q150（Fable 2026-10-09）＝アイデア候補.md の行。
- 論文ノート: Korzan 2026 二周期の株式ローテーション戦略_凍結した規則の評価（§6: 8 銘柄は point-in-time の銘柄一覧から
  選んでいない。検証するなら: 大きな集合で走らせ 8 銘柄の突出を測る）、Bailey ほか 2017 バックテスト過剰適合の確率、
  知見（Q036）: 多数の設定から選んだ最良は補正後に基準と区別できない。

【仮説（測る前に固定）】
H: 選択期間の成績で選んだ上位 k 銘柄の等ウェイト・シャープは、後半で全 15 銘柄の等ウェイトと区別できない
   （＝事後の銘柄選択は後半で残らない＝選択バイアス）。膨らみ (a)−(b) は、選択が運のときの帰無の範囲に入る。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄。
選択期間 = 2008〜2016（year < 2017）、後半 = 2017〜2026（year ≥ 2017、2026 は 7 月まで）。無いファイルは除く。

【定義（1通りに固定）】
- 規則 = TSMOM20（1 本）: s_t = sign(c_t − c_{t−20})、翌日のポジション。片道コスト段階1（COST_RT の半分）。
  日次純損益 [bp] は daily_net_pnl_bp のとおり。
- 銘柄のシャープ = 期間内の日次純損益の 平均/標準偏差 × √252（bp 単位なので無次元）。
- 等ウェイト・ポートフォリオの日次純損益 = 選んだ銘柄の日次純損益（bp）の単純平均（その日にデータのある銘柄で）。
  カレンダーは 15 銘柄の UTC 日付の和集合で揃える（無い日は欠損として平均から除く）。
- 上位 k ∈ {3, 5, 8}: 選択期間の銘柄シャープの上位 k。
- (a) 選択期間の、選んだ k 銘柄の等ウェイト・シャープ。(b) 後半の同じ k 銘柄の等ウェイト・シャープ。(c) 後半の全 15 の等ウェイト・シャープ。
- 膨らみ = (a) − (b)。選択の効果 = (b) − (c)。
- 年を単位の t: 年ごとの等ウェイト・ポートフォリオのシャープ（その年の 平均/標準偏差 × √252）を使い、
  (b)−(c) は後半の年で対応ありの差の t、(a)−(b) は選択期間の年 vs 後半の年の Welch の t。
- 帰無: 選択が運のとき (a)−(b) がどれだけ出るか。選択期間の銘柄の成績（ラベル）を並べ替え（＝後半で見る k 銘柄が
  無作為になる）B=500 回。(a) は観測と同じ、(b) は無作為 k 銘柄の後半シャープ。(a)−(b) と (b)−(c) の帰無分布・95% 点・z。
- Bailey の期待最大シャープ: E[max_N SR] ≈ E[SR] + SD[SR] × [(1−γ) Φ⁻¹(1−1/N) + γ Φ⁻¹(1−1/(N e))]、γ=0.5772、N=15。
  E[SR]・SD[SR] は選択期間の 15 銘柄のシャープの横断面の平均・標準偏差（記述）。Φ⁻¹ は自前（二分法）。

【測るもの】
k ごとの (a)(b)(c)・膨らみ・選択の効果・年単位の t・帰無の 95% 点と z・選んだ銘柄。Bailey の期待最大。

【判定（事前固定・変更禁止）】
k ごとに:
- (b)−(c) が 0 と区別できなければ（年単位 |t| < 2）「事後の銘柄選択は後半で残らない」＝選択バイアス。
- (a)−(b) が帰無の 95% 点以内なら「膨らみは運の範囲」。
- (b)−(c) が t ≥ 2 なら「銘柄の持続的な差がある」（未確定・条件の穴として記録）。
題名の k=8（Korzan の 8 銘柄）を主、k=3・5 は記述。多重比較: 3 k × 2 差。

【捨てた案の数】
約5: 純損益の平均で選ぶ案（シャープに統一）、bp でなく R 倍数で等ウェイトにする案、ブートストラップで年を再抽出する案、
Bailey の SD を推定誤差 √((1+SR²/2)/T) にする案（横断面の SD を主に・記述）、選択期間を拡大窓にする案。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。後半の各銘柄の値動き（金・BTC の上昇など）を知っている
可能性があるが、選択は選択期間の数値だけで機械的に行うので、相場観で選ぶ余地はない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、2026-10-09）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は結論ではなく、結果 JSON のパス・k=8 の (a)(b)(c)・t・帰無の 95% 点・原典の箇所（Korzan §6）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_instrument_selection_bias_q150.py            （B=500、数秒）
      python3 kensho_instrument_selection_bias_q150.py --smoke    （合成データで経路の確認。結果は捨てる）
事前登録からの変更点: なし（k=8 を主とするのは題名に従った運用上の注記で、k=3・5 の判定も同じ規則で出す）。
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

LOOKBACK = 20
KS = [3, 5, 8]
MAIN_K = 8
SPLIT_YEAR = 2017
ANN = 252
NULL_B = 500
SEED = 20261009
EULER_GAMMA = 0.5772156649


# ----------------------------------------------------------------------------- 基本の道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def welch_t(x, y):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    y = np.asarray(y, float); y = y[np.isfinite(y)]
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    se = math.sqrt(x.var(ddof=1) / len(x) + y.var(ddof=1) / len(y))
    return float((x.mean() - y.mean()) / se) if se > 0 else float("nan")


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


def norm_ppf(p):
    """標準正規の分位点（二分法・scipy 不要）。"""
    if not (0.0 < p < 1.0):
        return float("nan")
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if 0.5 * math.erfc(-mid / math.sqrt(2.0)) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def sharpe(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 20:
        return float("nan")
    s = x.std(ddof=1)
    return float(x.mean() / s * math.sqrt(ANN)) if s > 0 else float("nan")


def bailey_expected_max(sr_mean, sr_sd, N):
    return float(sr_mean + sr_sd * ((1 - EULER_GAMMA) * norm_ppf(1 - 1.0 / N) + EULER_GAMMA * norm_ppf(1 - 1.0 / (N * math.e))))


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
def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def daily_net_pnl_bp(c, signal, cost_rt):
    """signal_t を翌日 t+1 に持つ。bp 単位の日次純損益（長さ n、先頭は 0）。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:LOOKBACK + 1] = 0.0
    return pnl


# ----------------------------------------------------------------------------- 本体
def pnl_panel(series):
    """日付 × 銘柄 の日次純損益（bp）。無い日は NaN。"""
    cols = {}
    for sym, (t, c) in series.items():
        p = daily_net_pnl_bp(c, tsmom_positions(c), COST_RT[sym])
        s = pd.Series(p, index=pd.DatetimeIndex(t))
        s = s.iloc[LOOKBACK + 1:]
        cols[sym] = s
    return pd.DataFrame(cols).sort_index()


def ew(panel, syms):
    return panel[list(syms)].mean(axis=1, skipna=True)


def yearly_sharpe(s):
    return s.groupby(s.index.year).apply(sharpe)


def evaluate(panel, B, rng):
    syms = list(panel.columns)
    sel = panel[panel.index.year < SPLIT_YEAR]; tst = panel[panel.index.year >= SPLIT_YEAR]
    sr_sel = pd.Series({s: sharpe(sel[s].values) for s in syms}).sort_values(ascending=False)
    sr_tst = pd.Series({s: sharpe(tst[s].values) for s in syms})
    c_series = ew(tst, syms); c_all = sharpe(c_series.values); c_yearly = yearly_sharpe(c_series)
    bailey = dict(N=len(syms), sr_mean=float(sr_sel.mean()), sr_sd_cross=float(sr_sel.std(ddof=1)),
                  expected_max_sr=bailey_expected_max(float(sr_sel.mean()), float(sr_sel.std(ddof=1)), len(syms)),
                  observed_max_sr=float(sr_sel.max()), observed_max_sym=str(sr_sel.idxmax()))
    res = {}
    for k in KS:
        if k > len(syms):
            continue
        chosen = list(sr_sel.index[:k])
        a_series = ew(sel, chosen); b_series = ew(tst, chosen)
        a = sharpe(a_series.values); b = sharpe(b_series.values)
        a_y = yearly_sharpe(a_series); b_y = yearly_sharpe(b_series)
        d_bc = (b_y - c_yearly).dropna()
        m_bc, t_bc, n_bc = mean_t(d_bc.values)
        t_ab = welch_t(a_y.values, b_y.values)
        # 帰無: 後半で見る k 銘柄を無作為に
        null_ab = np.empty(B); null_bc = np.empty(B)
        for i in range(B):
            rs = [syms[j] for j in rng.permutation(len(syms))[:k]]
            bn = sharpe(ew(tst, rs).values)
            null_ab[i] = a - bn; null_bc[i] = bn - c_all
        z_ab, pct_ab = z_against_null(a - b, null_ab); z_bc, pct_bc = z_against_null(b - c_all, null_bc)
        res[f"k{k}"] = dict(
            k=k, chosen=chosen, chosen_sr_selection={s: float(sr_sel[s]) for s in chosen},
            chosen_sr_test={s: float(sr_tst[s]) for s in chosen},
            a_sharpe_selection=a, b_sharpe_test=b, c_sharpe_test_all=c_all,
            inflation_a_minus_b=float(a - b), selection_effect_b_minus_c=float(b - c_all),
            t_a_minus_b_welch_years=t_ab, n_years_a=int(a_y.notna().sum()), n_years_b=int(b_y.notna().sum()),
            bc_yearly_diff_mean=m_bc, t_b_minus_c_paired_years=t_bc, n_years_bc=n_bc,
            null_ab_mean=float(null_ab.mean()), null_ab_p95=float(np.percentile(null_ab, 95)), null_ab_z=z_ab, null_ab_pct=pct_ab,
            null_bc_mean=float(null_bc.mean()), null_bc_p95=float(np.percentile(null_bc, 95)), null_bc_z=z_bc, null_bc_pct=pct_bc,
            yearly_a={int(y): float(v) for y, v in a_y.items()}, yearly_b={int(y): float(v) for y, v in b_y.items()},
            yearly_c={int(y): float(v) for y, v in c_yearly.items()},
        )
    return res, dict(selection_sr={s: float(v) for s, v in sr_sel.items()}, test_sr={s: float(v) for s, v in sr_tst.items()},
                     spearman_sel_vs_test=float(pd.Series(sr_sel).rank().corr(pd.Series(sr_tst).rank())),
                     c_sharpe_test_all=c_all, c_sharpe_selection_all=sharpe(ew(sel, syms).values), bailey=bailey)


def judge(res):
    by = {}
    for key, r in res.items():
        t_bc = r["t_b_minus_c_paired_years"]
        no_persist = bool(np.isfinite(t_bc) and abs(t_bc) < 2.0)
        persist = bool(np.isfinite(t_bc) and t_bc >= 2.0)
        luck = bool(np.isfinite(r["inflation_a_minus_b"]) and r["inflation_a_minus_b"] <= r["null_ab_p95"])
        by[key] = dict(k=r["k"], t_b_minus_c=t_bc, selection_bias_no_persistence=no_persist,
                       inflation_within_luck_p95=luck, persistent_difference_t_ge2=persist,
                       label=("事後の銘柄選択は後半で残らない（選択バイアス）" if no_persist else
                              "銘柄の持続的な差がある（未確定・条件の穴）" if persist else "未確定（t<−2: 選んだ銘柄が後半でむしろ劣る）"),
                       inflation_label=("膨らみは運の範囲" if luck else "膨らみは帰無の 95% 点を超える"))
    main = by.get(f"k{MAIN_K}", {})
    return dict(by_k=by, main_k=MAIN_K, verdict=f"k={MAIN_K}: {main.get('label', 'nan')} / {main.get('inflation_label', 'nan')}",
                note="事前固定の規則で機械的に付けた判定（k ごと。主は k=8）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


def make_plot(res, extra, path):
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
        s1 = extra["selection_sr"]; s2 = extra["test_sr"]
        ax[0].scatter([s1[s] for s in s1], [s2[s] for s in s1], s=18)
        for s in s1:
            ax[0].annotate(s, (s1[s], s2[s]), fontsize=7)
        ax[0].axhline(0, lw=.6, c="k"); ax[0].axvline(0, lw=.6, c="k")
        ax[0].set_xlabel("選択期間のシャープ"); ax[0].set_ylabel("後半のシャープ")
        ax[0].set_title(f"銘柄ごと Spearman={extra['spearman_sel_vs_test']:+.2f}")
        ks = list(res.keys()); x = np.arange(len(ks))
        ax[1].bar(x - 0.25, [res[k]["a_sharpe_selection"] for k in ks], width=0.25, label="(a) 選択期間・選んだ k")
        ax[1].bar(x, [res[k]["b_sharpe_test"] for k in ks], width=0.25, label="(b) 後半・同じ k")
        ax[1].bar(x + 0.25, [res[k]["c_sharpe_test_all"] for k in ks], width=0.25, label="(c) 後半・全15")
        ax[1].set_xticks(x); ax[1].set_xticklabels(ks); ax[1].axhline(0, lw=.6, c="k"); ax[1].legend(fontsize=8)
        ax[1].set_ylabel("等ウェイト・シャープ")
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
    if len(series) < max(KS):
        print("銘柄が足りません:", len(series), DATA_DIR); sys.exit(1)

    panel = pnl_panel(series)
    res, extra = evaluate(panel, B, rng)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q150_sym_sharpe_{stamp}.csv")
    pd.DataFrame(dict(selection_sr=extra["selection_sr"], test_sr=extra["test_sr"])).to_csv(csv_path, index_label="sym")
    png_path = make_plot(res, extra, os.path.join(OUT, f"{prefix}Q150_sharpe_{stamp}.png"))
    out = dict(
        queue_id="Q150", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(time.time() - t0, 1),
        settings=dict(LOOKBACK=LOOKBACK, KS=KS, MAIN_K=MAIN_K, SPLIT_YEAR=SPLIT_YEAR, ANN=ANN, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, syms=list(series.keys()), missing_syms=missing, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_syms=len(series), n_missing=len(missing),
        per_symbol=extra, results=res, judgement=verdict,
        files=dict(sym_sharpe_csv=csv_path, sharpe_png=png_path),
        multiple_comparisons="3 k × 2 差（(a)−(b)、(b)−(c)）＝6。主は k=8",
    )
    jpath = os.path.join(OUT, f"{prefix}Q150_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else
                  (bool(o) if isinstance(o, np.bool_) else str(o)))

    print(f"[Q150] syms={len(series)} missing={missing} B={B} smoke={args.smoke} elapsed={out['elapsed_sec']}s")
    print(f"  Bailey: 期待最大 SR={extra['bailey']['expected_max_sr']:+.2f} 観測最大={extra['bailey']['observed_max_sr']:+.2f} "
          f"({extra['bailey']['observed_max_sym']})  銘柄 SR の Spearman(選択,後半)={extra['spearman_sel_vs_test']:+.2f}")
    for key, r in res.items():
        print(f"  {key}: 選択={r['chosen']}")
        print(f"       (a)={r['a_sharpe_selection']:+.2f} (b)={r['b_sharpe_test']:+.2f} (c)={r['c_sharpe_test_all']:+.2f}  "
              f"膨らみ={r['inflation_a_minus_b']:+.2f} (null95={r['null_ab_p95']:+.2f}, t_welch={r['t_a_minus_b_welch_years']:+.2f})  "
              f"選択効果={r['selection_effect_b_minus_c']:+.2f} (t_年={r['t_b_minus_c_paired_years']:+.2f}, z={r['null_bc_z']:+.2f})")
    print("  判定(機械):", verdict["verdict"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
