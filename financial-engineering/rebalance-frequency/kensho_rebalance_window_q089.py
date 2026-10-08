# -*- coding: utf-8 -*-
"""
検証キュー Q089: Q088の続き — リバランス頻度×推定窓の頑健性
（米国セクターETF9本・1999-2025・分散/MAD）
================================================================================

【このファイルの位置づけ】
Q088（kensho_rebalance_window.py）は D_fixed/D_orig = 0.0201（≤0.5 → 支持）の
点推定を出したが、D_fixed の95%区間が0を含むため「確定」と書けなかった。
Q089 はその「未確定」の原因を次の4点で潰す:
  ① 前半(1999-2012)/後半(2013-2025)の期間分割（アウトオブサンプル）
  ② 同じリサンプル上での D_orig − D_fixed と 比 の区間（ペアード・ブートストラップ）
  ③ 同じ頻度の「位相間の幅」と「頻度間の幅 R_f」の比較（timing luck の大きさ）
  ④ 幅（max−min）統計量のブートストラップの上方偏りの確認
加えて、検証の鉄則の「コスト込」を Q088 は通していなかったので、片道10bpの
売買コスト込みでも①②の点推定を出す（判定に使う、後述）。

Q088 の再現性を壊さないため、元ファイルは一切変更せず、元ファイルの関数
（最適化・リスク予算・シャープ・D）を import して使う。バックテストの日次
ループだけは「位相ごとの系列」と「ターンオーバー」を同時に取り出す必要が
あるので、元の backtest_one と同じロジックを numpy 配列で書き直した
（backtest_one_detailed）。起動時に Q088 のシャープ表（グロス・位相平均）を
再計算して Q088 の JSON と突き合わせ、再現できているかを結果に書く。

【出典の参照箇所】
Shah, Malhotra, Salotra & Pinsky (2026) "Rebalancing Frequency Dominates
Risk-Proxy Choice", Risks 14(10):229.
  - §3.7.4 (p.10-11): 推定窓を保有期間に連動させる設計（1ヶ月スケジュールは
    約21営業日で推定）。Q088 の「連動窓」はこれを模したもの（ただし最低42日）。
  - 原論文は頻度効果について「一様に0と区別できない」と自ら書いている
    （Q088 の docstring より）。だから点推定だけで「確定」と書かない。
Macrosynergy (2026) のリバランス頻度の検証は推定窓を固定したまま頻度だけを
動かしている（接続ログ 2026-10-07, Q087）。

================================================================================
【測る前に固定する判定ルール】（2026-10-07、計算前に記入。以後変更しない）
================================================================================
記号: D = R_f − R_p（Q088と同じ定義）。D_orig=連動窓、D_fixed=252日固定窓。
      比 = D_fixed / D_orig。Δ = D_orig − D_fixed（推定窓の連動が D を
      どれだけ押し上げているか。Δ>0 が「支持」側）。
帰無仮説 H0: Δ = 0（推定窓を連動させても固定しても D は変わらない）。
ベンチマーク: 1/N 等ウェイト（月次リバランス、同じリスク予算スケーリング
      なし）のシャープを参考値として併記する（判定には使わない）。

期間:
  全期間 = データ全体（1999-01-05〜2025-12-29、約324ヶ月）
  前半   = 1999-01-04〜2012-12-31（約168ヶ月）
  後半   = 2013-01-01〜2025-12-30（約156ヶ月）
  前半/後半とも n ≥ 40ヶ月なので分割してよい（鉄則: n<40 では割らない）。
  期間分割は「全期間で回したバックテストの日次リターンを切り出す」方式。
  各リバランス時点のウェイトはその時点より前のデータだけで決まっている
  ので、切り出しても先読みは入らない（後半の初回推定に2012年末のデータを
  使うのは正当な「過去」）。

ブートストラップ:
  月ブロック（Q088と同じ: 1ヶ月を1ブロックとして月を復元抽出）、B=2000、
  seed=20261007。全期間・前半・後半のそれぞれで、その期間の月だけを
  リサンプルする。全系列（連動/固定 × 頻度4 × 尺度2）に同じ月の並びを使う
  （＝ペアード）。感度分析として 6ヶ月の移動ブロックも出すが、判定には
  使わない（判定点を増やさないため）。

多重比較の扱い:
  判定点は ①②③④ の4つ。さらに ② は全期間・前半・後半の3つの区間を見る。
  - ② の Δ の区間は Bonferroni で 3 区間分を補正した 98.33%（=1−0.05/3）
    区間で判定する。95%区間は参考として併記する。
  - 4つの判定点がすべて「支持」側に揃い、かつコスト込でも比の区分が変わら
    ない場合に限り「支持（確定）」と書く。1つでも外れたら「未確定」。
    後から良いセル（特定の頻度・尺度・期間）を選んで有意と言わない。

① 期間分割（前半/後半で D_orig, D_fixed, 比）
  - どちらかの期間で D_orig ≤ 0 → その期間では比を解釈しない。①は「未確定」
    （連動窓での頻度支配自体が期間で再現しない）。
  - 両期間で D_orig > 0 かつ 比 ≤ 0.5 → ①は「支持」側。
  - 両期間で 比 ≥ 0.8 → ①は「棄却」側。
  - 片方でも 比 ≥ 0.8（両方ではない）、またはそれ以外 → ①は「未確定」。

② ペアード・ブートストラップ（同じ draw 内で Δ と 比）
  - Δ の 98.33% パーセンタイル区間と 98.33% ベーシック区間（2θ̂−q、④の
    上方偏りを打ち消す区間）の両方の下限が全期間で 0 より大きい → Δ>0 は
    0と区別できる。
  - 加えて前半・後半それぞれで P(Δ*>0) ≥ 0.9 を要求する（期間ごとの区間
    までは要求しない＝サンプルが半分なので）。
  - 比 の区間は D_orig* > 0 の draw のみで計算し、その割合を併記する。
    D_orig* ≤ 0 の draw が 2.5% を超える期間では比の区間を「定義できない」
    とし、Δ だけで判定する。比の区間が定義できる場合は、全期間の比の
    97.5% 点 ≤ 0.8 も要求する（＝比が「棄却」域に入る確率が小さい）。
  - 上を全部満たせば②は「支持」側。全期間の Δ の区間が両方とも 0 を含む
    なら②は「未確定」。Δ の区間上限が 0 未満なら「逆向き（棄却）」。

③ 位相間の幅 vs 頻度間の幅
  - 各 (窓, 頻度∈{3,6,12}, 尺度) で、位相 0〜freq−1 ごとの単独シャープの
    max−min を W(窓,頻度,尺度) とする（頻度1は位相が1つなので対象外）。
  - 位相ごとに初回リバランス時期が違い、遅い位相ほど冒頭のキャッシュ期間が
    長くなる（機械的にシャープが下がる）。この作り物の差を除くため、全系列
    が投資済みになった日以降の「共通期間」で W と R_f を計算し、判定はこの
    共通期間の値で行う（全期間の値も併記）。
  - 判定（連動窓について。固定窓は参考）:
      R_f ≥ 2 × mean(W)  → 頻度間の幅は位相の運より十分大きい（③「支持」側
                           ＝ D_orig の頻度支配はノイズではない）
      R_f ≤ 1 × mean(W)  → 頻度間の幅は位相の運と同程度（③「未確定」＝
                           Q088 の D_orig 自体がタイミングラック並みの大きさ）
      その間             → ③「未確定」
    R_f は尺度について平均したもの、mean(W) は頻度{3,6,12}×尺度2 の平均。

④ 上方偏りの確認（max−min のブートストラップ）
  - 全期間について、D_orig* の分布の平均・中央値と、点推定 D_orig が分布の
    何パーセンタイルにあるかを出す（D_fixed*, Δ* も同様）。
  - 点推定が 25 パーセンタイル未満 → 「上方偏りあり」。このとき Q088 の
    パーセンタイル区間 ［0.0117, 0.2325］ は上にずれていると判断し、
    ベーシック区間を併記した②の判定（両方の下限 > 0）を正とする。
  - 25〜75 パーセンタイル → 偏りは小さい。
  - ④自体は「支持/棄却」の判定点ではなく、②の区間の読み方を決める診断。
    ただし D_orig のベーシック 95% 区間が 0 を含む場合は、④は「未確定」側
    に数える（＝Q088 の D_orig>0 の区間自体が偏りの産物だった可能性）。

コスト（鉄則の「コスト込」）
  - リバランス日に、片道 10bp × Σ|scale_new·w_new − scale_old·w_old| を差し
    引く（リバランス間のドリフトは Q088 と同じく無視）。
  - コスト込の全期間・前半・後半の比が、グロスと同じ区分（≤0.5 / 0.5〜0.8 /
    ≥0.8）に入ること。区分が変わったら「確定」とは書かない。

総合判定（コードで機械的に出す）
  - 支持（確定）: ①②③が「支持」側、④が「未確定」側でない、コスト込でも
    区分が変わらない、の全部。
  - 棄却側: ①が「棄却」側、または②が「逆向き」。
  - それ以外は「未確定」（どの判定点が外れたかを列挙する）。

【捨てた案】
  - 位相ごとに別々に D を出して位相間の D の幅を見る案（判定点が12倍に増え、
    後から良い位相を選べてしまうので、W を「幅の大きさの目安」にとどめた）
  - 推定窓を3水準以上に振る案（Q088と同じ理由で見送り）
  - 期間分割で前半/後半それぞれバックテストを最初から回し直す案（後半の
    冒頭に人工的なキャッシュ期間ができるため。切り出し方式にした）
  - ブロック長を判定に使う案（判定点が増えるので感度分析に回した）

【実行】
  python3 kensho_rebalance_window_q089.py [--out results] [--cache data/sector_etf_prices.csv]
  ネットワーク不要（キャッシュCSVを読む）。scipy/pandas/numpy が必要。
  所要: 最適化 約5000回 + ブートストラップ（ベクトル化）。数分〜十数分。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import unicodedata
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kensho_rebalance_window as base  # noqa: E402  Q088本体（変更しない）

FIRST_HALF = ("1999-01-04", "2012-12-31")
SECOND_HALF = ("2013-01-01", "2025-12-30")
COST_ONE_WAY = 0.0010          # 片道10bp
ALPHA_BONF = 0.05 / 3          # ②の Bonferroni（全期間・前半・後半）
SENSITIVITY_BLOCK_MONTHS = 6   # 感度分析のみ
MODES = ["coupled", "fixed"]


# --------------------------------------------------------------------------
# A. 位相ごとの系列とターンオーバーを出すバックテスト
#    （ロジックは base.backtest_one と同一。グロス系列は一致するはず）
# --------------------------------------------------------------------------
def backtest_one_detailed(returns: pd.DataFrame, freq_months: int, window_mode: str,
                          proxy_name: str, phase: int):
    weight_fn = base.RISK_PROXIES[proxy_name]
    idx = returns.index
    R = returns.values
    month_key = idx.to_period("M")
    unique_months = month_key.unique()
    rebal_months = set(unique_months[phase::freq_months])
    mk = np.asarray(month_key)

    gross = np.zeros(len(idx))
    cost = np.zeros(len(idx))
    current_w = None
    current_scale = 0.0
    held = np.zeros(R.shape[1])  # 実際の保有（scale·w）
    first_invested = None

    coupled_window_days = max(freq_months * 21, 42)
    window_days = (coupled_window_days if window_mode == "coupled"
                   else base.ESTIMATION_WINDOW_FIXED_DAYS)

    for i in range(len(idx)):
        this_month = mk[i]
        is_rebal_day = (this_month in rebal_months) and (i == 0 or mk[i - 1] != this_month)
        if is_rebal_day:
            hist = R[max(0, i - window_days):i]
            if len(hist) >= max(20, window_days // 4):
                w = weight_fn(hist)
                scale = base.scale_to_risk_budget(w, hist, base.RISK_BUDGET_ANNUAL)
                current_w, current_scale = w, scale
                new_held = w * scale
                cost[i] = COST_ONE_WAY * np.abs(new_held - held).sum()
                held = new_held
                if first_invested is None:
                    first_invested = i
        if current_w is not None:
            gross[i] = float(R[i] @ current_w) * current_scale

    return pd.Series(gross, index=idx), pd.Series(gross - cost, index=idx), first_invested


# --------------------------------------------------------------------------
# B. 月集計を使ったベクトル化ブートストラップ
#    シャープ = 月ごとの Σr, Σr², 日数 から再構成（base.annualized_sharpe と同値）
# --------------------------------------------------------------------------
def month_aggregates(series_dict: dict, index: pd.DatetimeIndex):
    months = index.to_period("M")
    uniq = months.unique()
    codes = pd.Index(uniq).get_indexer(months)
    keys = list(series_dict.keys())
    M, K = len(uniq), len(keys)
    S1 = np.zeros((M, K)); S2 = np.zeros((M, K))
    cnt = np.bincount(codes, minlength=M).astype(float)
    for j, k in enumerate(keys):
        v = series_dict[k].reindex(index).values
        S1[:, j] = np.bincount(codes, weights=v, minlength=M)
        S2[:, j] = np.bincount(codes, weights=v * v, minlength=M)
    return keys, uniq, cnt, S1, S2


def sharpe_from_counts(C: np.ndarray, cnt, S1, S2):
    """C: (B, M) 各drawでの各月の採用回数。戻り: (B, K) の年率シャープ。"""
    N = C @ cnt                     # (B,)
    s1 = C @ S1                     # (B,K)
    s2 = C @ S2
    mean = s1 / N[:, None]
    var = (s2 - N[:, None] * mean ** 2) / (N[:, None] - 1)
    sd = np.sqrt(np.maximum(var, 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        sh = (mean * base.TRADING_DAYS_PER_YEAR) / (sd * np.sqrt(base.TRADING_DAYS_PER_YEAR))
    return sh


def draw_counts(M: int, n_boot: int, block: int, seed: int):
    """block=1 は base.block_bootstrap_D と同じ乱数列（rng.choice(M個, M, replace)）。"""
    rng = np.random.default_rng(seed)
    C = np.zeros((n_boot, M))
    for b in range(n_boot):
        if block == 1:
            # base は rng.choice(unique_months, size=n, replace=True)。整数版も同じ乱数を消費する
            pos = rng.choice(np.arange(M), size=M, replace=True)
        else:
            n_blocks = int(np.ceil(M / block))
            starts = rng.integers(0, M - block + 1, size=n_blocks)
            pos = (starts[:, None] + np.arange(block)[None, :]).ravel()[:M]
        C[b] = np.bincount(pos, minlength=M)
    return C


def D_from_sharpe_matrix(sh: np.ndarray, keys: list, mode: str):
    """sh: (B,K)。keys は (mode, freq, proxy)。D を (B,) で返す。"""
    freqs = base.FREQUENCIES_MONTHS
    proxies = list(base.RISK_PROXIES.keys())
    col = {k: j for j, k in enumerate(keys)}
    f_spreads = []
    for p in proxies:
        m = np.stack([sh[:, col[(mode, f, p)]] for f in freqs], axis=1)
        f_spreads.append(m.max(1) - m.min(1))
    p_spreads = []
    for f in freqs:
        m = np.stack([sh[:, col[(mode, f, p)]] for p in proxies], axis=1)
        p_spreads.append(m.max(1) - m.min(1))
    return np.mean(f_spreads, axis=0) - np.mean(p_spreads, axis=0)


def pct_interval(x, alpha):
    lo, hi = np.percentile(x, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def basic_interval(theta, x, alpha):
    lo_q, hi_q = pct_interval(x, alpha)
    return float(2 * theta - hi_q), float(2 * theta - lo_q)


def percentile_of(theta, x):
    return float(np.mean(x < theta) * 100 + 0.5 * np.mean(x == theta) * 100)


def paired_bootstrap(series_dict, index, D_o_hat, D_f_hat, n_boot, block, seed):
    keys, uniq, cnt, S1, S2 = month_aggregates(series_dict, index)
    C = draw_counts(len(uniq), n_boot, block, seed)
    sh = sharpe_from_counts(C, cnt, S1, S2)
    Do = D_from_sharpe_matrix(sh, keys, "coupled")
    Df = D_from_sharpe_matrix(sh, keys, "fixed")
    delta = Do - Df
    delta_hat = D_o_hat - D_f_hat
    pos = Do > 0
    ratio = np.where(pos, Df / np.where(pos, Do, 1), np.nan)
    ratio_ok = ratio[pos]
    frac_nonpos = float(1 - pos.mean())
    out = {
        "月数": int(len(uniq)),
        "B": int(n_boot),
        "ブロック長(月)": int(block),
        "Δ点推定(D_orig−D_fixed)": r4(delta_hat),
        "Δ_95%パーセンタイル区間": r4l(pct_interval(delta, 0.05)),
        "Δ_98.33%パーセンタイル区間": r4l(pct_interval(delta, ALPHA_BONF)),
        "Δ_95%ベーシック区間": r4l(basic_interval(delta_hat, delta, 0.05)),
        "Δ_98.33%ベーシック区間": r4l(basic_interval(delta_hat, delta, ALPHA_BONF)),
        "P(Δ*>0)": r4(float(np.mean(delta > 0))),
        "D_orig*≤0の割合": r4(frac_nonpos),
        "比_95%区間(D_orig*>0のdrawのみ)": (r4l(pct_interval(ratio_ok, 0.05))
                                         if len(ratio_ok) > 10 else None),
        "比_中央値(D_orig*>0のdrawのみ)": r4(float(np.median(ratio_ok))) if len(ratio_ok) else None,
        "P(比*≤0.5 | D_orig*>0)": r4(float(np.mean(ratio_ok <= 0.5))) if len(ratio_ok) else None,
        "P(比*≥0.8 | D_orig*>0)": r4(float(np.mean(ratio_ok >= 0.8))) if len(ratio_ok) else None,
        "D_orig*_95%区間": r4l(pct_interval(Do, 0.05)),
        "D_fixed*_95%区間": r4l(pct_interval(Df, 0.05)),
        "D_orig_95%ベーシック区間": r4l(basic_interval(D_o_hat, Do, 0.05)),
        "D_fixed_95%ベーシック区間": r4l(basic_interval(D_f_hat, Df, 0.05)),
        # ④ 上方偏りの診断
        "上方偏り": {
            "D_orig": bias_block(D_o_hat, Do),
            "D_fixed": bias_block(D_f_hat, Df),
            "Δ": bias_block(delta_hat, delta),
        },
    }
    return out, (Do, Df, delta, ratio_ok, frac_nonpos)


def bias_block(theta, x):
    return {
        "点推定": r4(theta),
        "分布平均": r4(float(np.mean(x))),
        "分布中央値": r4(float(np.median(x))),
        "平均−点推定": r4(float(np.mean(x) - theta)),
        "点推定のパーセンタイル位置": round(percentile_of(theta, x), 1),
    }


def r4(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 4)


def r4l(t):
    return [r4(t[0]), r4(t[1])]


# --------------------------------------------------------------------------
# C. 点推定（期間を切って D を出す）
# --------------------------------------------------------------------------
def sharpe_table_in(series_dict, mode, start=None, end=None):
    tab = {}
    for (m, f, p), s in series_dict.items():
        if m != mode:
            continue
        ss = s.loc[start:end] if (start or end) else s
        tab[(f, p)] = base.annualized_sharpe(ss)
    return tab


def ratio_class(r):
    if r is None:
        return "解釈しない(D_orig≤0)"
    if r <= 0.5:
        return "≤0.5"
    if r >= 0.8:
        return "≥0.8"
    return "0.5〜0.8"


def point_block(series_dict, start, end):
    t_o = sharpe_table_in(series_dict, "coupled", start, end)
    t_f = sharpe_table_in(series_dict, "fixed", start, end)
    Do, Df = base.compute_D(t_o), base.compute_D(t_f)
    ratio = Df / Do if Do > 0 else None
    return {
        "D_orig": r4(Do), "D_fixed": r4(Df),
        "比(D_fixed/D_orig)": r4(ratio) if ratio is not None else None,
        "比の区分": ratio_class(ratio),
        "シャープ表_coupled": {f"{f}ヶ月_{p}": r4(v) for (f, p), v in t_o.items()},
        "シャープ表_fixed": {f"{f}ヶ月_{p}": r4(v) for (f, p), v in t_f.items()},
    }, Do, Df, ratio


# --------------------------------------------------------------------------
# D. メイン
# --------------------------------------------------------------------------
def run(out_dir, cache_path, n_boot=base.N_BOOTSTRAP):
    t0 = datetime.now()
    log = lambda s: print(f"[{datetime.now():%H:%M:%S}] {s}", flush=True)
    px = base.fetch_prices(cache_path=cache_path)
    returns = px.pct_change().dropna(how="any")
    idx = returns.index
    log(f"データ: {len(idx)}営業日 ({idx[0].date()}〜{idx[-1].date()})")

    proxies = list(base.RISK_PROXIES.keys())
    phase_gross, phase_net, first_inv = {}, {}, {}
    for mode in MODES:
        for f in base.FREQUENCIES_MONTHS:
            for p in proxies:
                for ph in range(f):
                    g, n, fi = backtest_one_detailed(returns, f, mode, p, ph)
                    phase_gross[(mode, f, p, ph)] = g
                    phase_net[(mode, f, p, ph)] = n
                    first_inv[(mode, f, p, ph)] = fi
                log(f"window={mode} freq={f} proxy={p} 位相{f}本 完了")

    def avg(d):
        out = {}
        for mode in MODES:
            for f in base.FREQUENCIES_MONTHS:
                for p in proxies:
                    out[(mode, f, p)] = pd.concat([d[(mode, f, p, ph)] for ph in range(f)],
                                                  axis=1).mean(axis=1)
        return out

    gross = avg(phase_gross)
    net = avg(phase_net)

    # ---- Q088 再現チェック
    q088_path = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "results", "Q088_result_*.json")))
    repro = {"Q088のJSON": None}
    if q088_path:
        with open(q088_path[-1], encoding="utf-8") as fh:
            # Mac由来のJSONはキーがNFDのことがあるのでNFCに揃える
            q088 = json.loads(unicodedata.normalize("NFC", fh.read()))
        diffs = []
        for mode in MODES:
            for (f, p), v in sharpe_table_in(gross, mode).items():
                ref = q088["シャープレシオ表"][mode][f"{f}ヶ月_{p}"]
                diffs.append(abs(round(v, 4) - ref))
        repro = {"Q088のJSON": os.path.basename(q088_path[-1]),
                 "シャープ表の最大絶対差": r4(max(diffs)),
                 "一致(≤0.0001)": bool(max(diffs) <= 0.0001)}
    log(f"Q088再現チェック: {repro}")

    # ---- ① 期間分割（グロス、コスト込）
    periods = {"全期間": (None, None), "前半1999-2012": FIRST_HALF, "後半2013-2025": SECOND_HALF}
    point = {}
    point_net = {}
    hats = {}
    for name, (s, e) in periods.items():
        point[name], Do, Df, rt = point_block(gross, s, e)
        hats[name] = (Do, Df, rt)
        point_net[name], *_ = point_block(net, s, e)
        log(f"① {name}: D_orig={Do:.4f} D_fixed={Df:.4f} 比={rt}")

    # ---- ② ペアード・ブートストラップ（④の偏りもここで出す）
    boot = {}
    boot_sens = {}
    for name, (s, e) in periods.items():
        sub_idx = idx if s is None else idx[(idx >= s) & (idx <= e)]
        Do, Df, _ = hats[name]
        boot[name], _ = paired_bootstrap(gross, sub_idx, Do, Df, n_boot, 1, base.RANDOM_SEED)
        boot_sens[name], _ = paired_bootstrap(gross, sub_idx, Do, Df, n_boot,
                                              SENSITIVITY_BLOCK_MONTHS, base.RANDOM_SEED)
        log(f"② {name}: Δ98.33%pct={boot[name]['Δ_98.33%パーセンタイル区間']} "
            f"basic={boot[name]['Δ_98.33%ベーシック区間']} P(Δ>0)={boot[name]['P(Δ*>0)']}")

    # ---- ③ 位相間の幅 vs 頻度間の幅
    common_start = idx[max(first_inv.values())]
    phase_res = {}
    for label, start in [("共通期間(判定用)", common_start), ("全期間(参考)", None)]:
        per_mode = {}
        for mode in MODES:
            W = {}
            phase_sh = {}
            for f in base.FREQUENCIES_MONTHS:
                for p in proxies:
                    shs = [base.annualized_sharpe(phase_gross[(mode, f, p, ph)].loc[start:])
                           for ph in range(f)]
                    phase_sh[f"{f}ヶ月_{p}"] = [r4(v) for v in shs]
                    if f > 1:
                        W[(f, p)] = max(shs) - min(shs)
            tab = sharpe_table_in(gross, mode, start, None)
            R_f = float(np.mean([max(tab[(f, p)] for f in base.FREQUENCIES_MONTHS)
                                 - min(tab[(f, p)] for f in base.FREQUENCIES_MONTHS)
                                 for p in proxies]))
            R_p = float(np.mean([max(tab[(f, p)] for p in proxies)
                                 - min(tab[(f, p)] for p in proxies)
                                 for f in base.FREQUENCIES_MONTHS]))
            meanW = float(np.mean(list(W.values())))
            maxW = float(max(W.values()))
            per_mode[mode] = {
                "位相ごとのシャープ": phase_sh,
                "位相間の幅W": {f"{f}ヶ月_{p}": r4(v) for (f, p), v in W.items()},
                "mean(W)": r4(meanW), "max(W)": r4(maxW),
                "頻度間の幅R_f(位相平均系列)": r4(R_f),
                "尺度間の幅R_p": r4(R_p),
                "D(=R_f−R_p,この期間)": r4(R_f - R_p),
                "R_f/mean(W)": r4(R_f / meanW) if meanW > 0 else None,
                "R_f/max(W)": r4(R_f / maxW) if maxW > 0 else None,
            }
        phase_res[label] = per_mode
    phase_res["共通期間の開始日"] = str(common_start.date())

    # ---- 参考: 1/N ベンチマーク（月次、スケーリングなし、グロス）
    ew = returns.mean(axis=1)
    bench = {name: r4(base.annualized_sharpe(ew.loc[s:e] if s else ew))
             for name, (s, e) in periods.items()}

    # ======================================================================
    # 判定（docstringで固定したルールどおり）
    # ======================================================================
    reasons = []
    # ①
    h1 = hats["前半1999-2012"]; h2 = hats["後半2013-2025"]
    if h1[0] <= 0 or h2[0] <= 0:
        j1 = "未確定"; reasons.append("① どちらかの期間で D_orig≤0")
    elif h1[2] <= 0.5 and h2[2] <= 0.5:
        j1 = "支持"
    elif h1[2] >= 0.8 and h2[2] >= 0.8:
        j1 = "棄却"; reasons.append("① 両期間で比≥0.8")
    else:
        j1 = "未確定"; reasons.append("① 両期間で比≤0.5が揃わない")
    # ②
    bf = boot["全期間"]
    lo_p = bf["Δ_98.33%パーセンタイル区間"][0]; lo_b = bf["Δ_98.33%ベーシック区間"][0]
    hi_p = bf["Δ_98.33%パーセンタイル区間"][1]; hi_b = bf["Δ_98.33%ベーシック区間"][1]
    halves_ok = all(boot[k]["P(Δ*>0)"] >= 0.9 for k in ["前半1999-2012", "後半2013-2025"])
    ratio_ok = True
    if bf["D_orig*≤0の割合"] <= 0.025 and bf["比_95%区間(D_orig*>0のdrawのみ)"] is not None:
        ratio_ok = bf["比_95%区間(D_orig*>0のdrawのみ)"][1] <= 0.8
        ratio_note = "比の区間は定義可能"
    else:
        ratio_note = "D_orig*≤0のdrawが2.5%超のため比の区間は定義できない（Δのみで判定）"
    if hi_p < 0 and hi_b < 0:
        j2 = "逆向き（棄却）"; reasons.append("② Δの区間上限<0")
    elif lo_p > 0 and lo_b > 0 and halves_ok and ratio_ok:
        j2 = "支持"
    else:
        j2 = "未確定"
        if not (lo_p > 0 and lo_b > 0):
            reasons.append("② 全期間のΔの98.33%区間（パーセンタイル/ベーシックのどちらか）が0を含む")
        if not halves_ok:
            reasons.append("② 前半か後半で P(Δ*>0)<0.9")
        if not ratio_ok:
            reasons.append("② 全期間の比の97.5%点>0.8")
    # ③
    c = phase_res["共通期間(判定用)"]["coupled"]
    rr = c["R_f/mean(W)"]
    if rr is not None and rr >= 2:
        j3 = "支持"
    else:
        j3 = "未確定"; reasons.append(f"③ 連動窓の R_f/mean(W)={rr}（<2）")
    # ④
    pct_pos = bf["上方偏り"]["D_orig"]["点推定のパーセンタイル位置"]
    upward = pct_pos < 25
    basic_o = bf["D_orig_95%ベーシック区間"]
    if basic_o[0] <= 0:
        j4 = "未確定"; reasons.append("④ D_origの95%ベーシック区間が0を含む")
    else:
        j4 = "問題なし"
    j4_note = (f"D_orig点推定は分布の{pct_pos}パーセンタイル。"
               + ("25未満→上方偏りあり" if upward else "25以上→偏りは小さい"))
    # コスト
    cost_same = all(point[k]["比の区分"] == point_net[k]["比の区分"] for k in periods)
    if not cost_same:
        reasons.append("コスト込で比の区分が変わる期間がある")

    if j1 == "棄却" or j2.startswith("逆向き"):
        overall = "棄却側"
    elif j1 == "支持" and j2 == "支持" and j3 == "支持" and j4 != "未確定" and cost_same:
        overall = "支持（確定）"
    else:
        overall = "未確定"

    report = {
        "検証": "Q089 リバランス頻度×推定窓の頑健性（米国セクターETF・分散/MAD）— Q088の続き",
        "実行日時": datetime.now().isoformat(timespec="seconds"),
        "所要秒": round((datetime.now() - t0).total_seconds(), 1),
        "データ期間": f"{idx[0].date()} - {idx[-1].date()}",
        "銘柄": base.TICKERS,
        "尺度": proxies,
        "Q088再現チェック": repro,
        "①期間分割_グロス": point,
        "①期間分割_コスト込(片道10bp)": {k: {kk: v[kk] for kk in
                                         ["D_orig", "D_fixed", "比(D_fixed/D_orig)", "比の区分"]}
                                    for k, v in point_net.items()},
        "②ペアードブートストラップ(月ブロック=1,判定用)": boot,
        "②感度分析(6ヶ月移動ブロック,判定に使わない)": {
            k: {kk: v[kk] for kk in ["Δ_95%パーセンタイル区間", "Δ_95%ベーシック区間", "P(Δ*>0)",
                                     "D_orig*≤0の割合", "比_95%区間(D_orig*>0のdrawのみ)"]}
            for k, v in boot_sens.items()},
        "③位相間の幅vs頻度間の幅": phase_res,
        "参考_1/Nベンチマークのシャープ(スケーリングなし)": bench,
        "判定": {
            "①期間分割": j1,
            "②ペアード": j2, "②注記": ratio_note,
            "③位相vs頻度": j3,
            "④上方偏り": j4, "④注記": j4_note,
            "コスト込で区分不変": cost_same,
            "総合": overall,
            "外れた判定点": reasons,
            "多重比較": "判定点4つ（①②③④）＋②は3区間。②はBonferroni 98.33%区間。全部揃わない限り『確定』と書かない",
        },
        "限界": [
            "リスク尺度は分散・MADの2つのみ（Q088と同じ）",
            "リバランス間のウェイトのドリフトは無視（Q088と同じ）。コストもこの簡略化の上で計算",
            "コストは片道10bpの1水準のみ",
            "期間分割は全期間バックテストの切り出し（前半冒頭はQ088と同じくキャッシュ期間を含む）",
            "位相間の幅Wは単独位相のシャープの幅で、位相平均系列のR_fより本質的にノイズが大きい比較である",
            "MAD最小化はSLSQP（数値微分・非平滑な目的関数）で解いており、scipyのバージョンで解が変わる。"
            "分散の系列はQ088と完全一致するが、MADのシャープはQ088（Mac実行）と最大0.0043ずれる（Q088再現チェック参照）",
        ],
    }
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"Q089_result_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    log(f"結果を書き出した: {out_path}")
    print(json.dumps(report["判定"], ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(here, "results"))
    ap.add_argument("--cache", default=os.path.join(here, "data", "sector_etf_prices.csv"))
    ap.add_argument("--boot", type=int, default=base.N_BOOTSTRAP)
    a = ap.parse_args()
    run(a.out, a.cache, a.boot)
