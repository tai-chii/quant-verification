# -*- coding: utf-8 -*-
"""
検証キュー Q088: リバランス頻度の「支配」は推定窓の交絡か（株・米国セクターETF）
================================================================================

【出典】
Shah, Malhotra, Salotra & Pinsky (2026) "Rebalancing Frequency Dominates Risk-Proxy
Choice", Risks 14(10):229. 米国セクターETF9本・1999-2025年で、リバランス頻度
（月次/四半期/半年/年次）の違いによる成績差が、リスク尺度（分散/MAD/IQR/P95）
の違いによる成績差より大きい（H1支持）、という結果。

接続ログ 2026-10-07（Q087, 矛盾の行）: Shahほかは「頻度を変えると推定窓も
保有期間に連動して変わる」設計（§3.7.4, p.10-11）。一方 Macrosynergy (2026)
のリバランス頻度の検証は推定窓を変えずに頻度だけ変えている。つまり同じ
「リバランス頻度」でも操作が違う可能性がある。

【仮説（測る前に固定）】
H: Shahほかの中心結論（H1: 頻度間の成績差 > リスク尺度間の成績差）は、
   推定窓の長さをリバランス頻度に連動させず固定しても残る。
   → 残らなければ、原論文のH1の少なくとも一部は「推定窓が短くなること」の
     効果であり、「リバランス頻度そのもの」の効果ではない、という含意になる。

【測る前に固定する棄却条件】
統計量 D = R_f − R_p
  R_f = 頻度間の幅（各リスク尺度で頻度4通りの年率シャープの max − min を
        出し、尺度について平均）
  R_p = リスク尺度間の幅（各頻度でリスク尺度2通りの年率シャープの max − min
        を出し、頻度について平均）
を、
  - 原設計: 推定窓をリバランス頻度に連動（保有期間と同じ長さ）
  - 固定窓: 推定窓を252営業日に固定
の両方で計算し、比 D_fixed / D_orig を出す。

  - 原設計で D_orig <= 0（頻度の支配がそもそも再現しない）→ 未確定（データ・
    実装の違いを書く。この時点で D_fixed/D_orig の比は解釈しない）
  - D_orig > 0 のとき:
      D_fixed / D_orig <= 0.5 → 支持（頻度の支配は主に推定窓の効果）
      D_fixed / D_orig >= 0.8 → 棄却（推定窓によらず頻度そのものが効く）
      0.5 < 比 < 0.8          → 未確定
  - ブロックブートストラップ（月ブロック、B=2000）の D の95%区間が0を
    含む場合は、点推定でどちらに転んでも「確定」とは書かない
    （Shahほか自身が原論文で「一様に0と区別できない」と明記しているため）。

【捨てた案の数】
この案にたどり着くまでに検討して捨てたもの（概数）:
  - IQR・P95を含む4尺度すべての再現（解析的に解きにくい分位点制約の実装コスト
    が高く、今回は分散・MADの2尺度に減らした。契機: アイデア候補の時点で
    「IQR・P95が解けなければ分散・MADの2つに減らし、減らしたことを書く」と
    事前に明記済み）
  - 推定窓を3水準以上に振る案（64通り×12位相で計算量が増えすぎるため、
    「連動」「252日固定」の2水準に絞った）
  - リバランス時のウェイトのドリフトを考慮する案（実装が複雑になるため、
    簡略化してリバランス間はウェイト固定とした。この簡略化が結果に与える
    影響は未評価＝限界として記録する）

【LLMの知識の締め切りとの関係】
この仮説・設計は Claude（知識の締め切り およそ 2026-06）が、2026-10-02公開の
Shahほか(2026)論文と2026-10-05にtaichiが収集したMacrosynergyのブログ記事を
読んだ上で、2026-10-07に新たに立てたもの。検証対象のデータ（1999-2025年の
株価）自体は締め切り以前の期間を含むが、「2論文の矛盾を突く」という問いの
立て方そのものは締め切り後の情報に基づく。

【委託の確かめ方】
この設計は Opus サブエージェントが接続ログ・アイデア候補への追記を行い、
taichi役のセッション（sonnet本体）が接続ログ・アイデア候補・入荷台帳の
実際の変更内容を確認した上でキューに登録した（2026-10-07）。このスクリプト
自体はサブエージェントを介さず sonnet 本体が直接書いている。

【この環境について】
このスクリプトはネットワーク経由で市場データ（yfinance）を取得するため、
Claudeのクラウドコンテナからは実行できない。taichi自身のPC（夜間キュー
経由、yoru.sh/yoru.ps1）で実行すること。
    pip install yfinance scipy pandas numpy
    python3 kensho_rebalance_window.py [--out 出力ディレクトリ]

【実行時間の見積もり】
9資産×27年の日次データ取得（数秒〜数十秒）＋ 頻度4×窓2×尺度2×位相（最大12）
の最適化ループ（1リバランス時点あたりSLSQPで数十ミリ秒、合計で数千回）＋
ブロックブートストラップ B=2000。手元の見積もりでは十数分程度だが、
データ取得の遅延やネットワーク状況次第で前後する。安全のため制限時間は
長めに取ること（夜間キューの制限時間は90分を推奨）。
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
START = "1999-01-04"
END = "2025-12-30"
RISK_BUDGET_ANNUAL = 0.10       # 年率リスク予算 10%
FREQUENCIES_MONTHS = [1, 3, 6, 12]   # リバランス頻度（月）
ESTIMATION_WINDOW_FIXED_DAYS = 252   # 固定窓（営業日）
TRADING_DAYS_PER_YEAR = 252
N_BOOTSTRAP = 2000
BOOTSTRAP_BLOCK_MONTHS = 1       # 月ブロック
RANDOM_SEED = 20261007


# --------------------------------------------------------------------------
# 1. データ取得
# --------------------------------------------------------------------------
def fetch_prices(tickers=TICKERS, start=START, end=END, cache_path=None):
    """配当込み調整後終値の日次価格を取得する。cache_path があればそこに
    CSVとして保存/読み込みし、2回目以降の実行を速くする。"""
    if cache_path and os.path.exists(cache_path):
        px = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if set(tickers).issubset(set(px.columns)):
            return px[tickers]

    import yfinance as yf

    px = yf.download(
        tickers, start=start, end=end, auto_adjust=True, progress=False
    )["Close"]
    px = px[tickers].dropna(how="all")
    # 個別銘柄の欠損は前方補完しない。欠損日は行ごと落とす（全銘柄が揃う日だけ使う）
    px = px.dropna(how="any")
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        px.to_csv(cache_path)
    return px


# --------------------------------------------------------------------------
# 2. ポートフォリオ最適化（ロングのみ・フルインベスト）
# --------------------------------------------------------------------------
def min_variance_weights(returns_window: np.ndarray) -> np.ndarray:
    """returns_window: (T, N) の日次リターン行列。分散最小化の重みを返す。"""
    from scipy.optimize import minimize

    n = returns_window.shape[1]
    cov = np.cov(returns_window, rowvar=False)
    cov = cov + np.eye(n) * 1e-10  # 数値安定化

    def obj(w):
        return w @ cov @ w

    def grad(w):
        return 2 * cov @ w

    w0 = np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0)] * n
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    res = minimize(obj, w0, jac=grad, bounds=bounds, constraints=cons,
                    method="SLSQP", options={"maxiter": 200, "ftol": 1e-12})
    w = res.x
    w = np.clip(w, 0, None)
    s = w.sum()
    return w / s if s > 0 else w0


def min_mad_weights(returns_window: np.ndarray) -> np.ndarray:
    """returns_window: (T, N)。平均絶対偏差（MAD）最小化の重みを返す。
    厳密なLP定式化ではなく、非線形最適化（SLSQP）で近似的に解く。"""
    from scipy.optimize import minimize

    n = returns_window.shape[1]
    r = returns_window

    def obj(w):
        port = r @ w
        return np.mean(np.abs(port - port.mean()))

    w0 = np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0)] * n
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    res = minimize(obj, w0, bounds=bounds, constraints=cons,
                    method="SLSQP", options={"maxiter": 200, "ftol": 1e-10})
    w = res.x
    w = np.clip(w, 0, None)
    s = w.sum()
    return w / s if s > 0 else w0


RISK_PROXIES = {
    "variance": min_variance_weights,
    "mad": min_mad_weights,
}


# --------------------------------------------------------------------------
# 3. リスク予算（年率ボラ目標へのスケーリング）
# --------------------------------------------------------------------------
def scale_to_risk_budget(w: np.ndarray, returns_window: np.ndarray,
                          target_annual_vol: float) -> float:
    """推定窓のリターンから見たポートフォリオの年率予測ボラに対し、
    目標に合わせるスケール係数（レバレッジ、残りはキャッシュ=0%リターン、
    上限1.0＝キャッシュへのショートは取らない）を返す。"""
    port_ret = returns_window @ w
    daily_vol = port_ret.std(ddof=1)
    if daily_vol <= 0 or np.isnan(daily_vol):
        return 0.0
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    scale = target_annual_vol / annual_vol
    return float(np.clip(scale, 0.0, 1.0))


# --------------------------------------------------------------------------
# 4. 1系列のバックテスト（頻度・窓・尺度・位相を固定して実行）
# --------------------------------------------------------------------------
def backtest_one(returns: pd.DataFrame, freq_months: int, window_mode: str,
                  proxy_name: str, phase: int) -> pd.Series:
    """returns: 日次リターンのDataFrame（index=日付, columns=銘柄）。
    window_mode: "coupled"（保有期間に連動）または "fixed"（252営業日固定）。
    phase: リバランス日をずらす位相（0〜freq_months-1、月単位）。
    戻り値: ポートフォリオの日次リターン（Series）。"""
    weight_fn = RISK_PROXIES[proxy_name]
    idx = returns.index
    month_key = idx.to_period("M")
    unique_months = month_key.unique()

    # リバランス月の決定（位相付き）
    rebal_months = set(unique_months[phase::freq_months])

    port_returns = pd.Series(0.0, index=idx)
    current_w = None
    current_scale = 0.0

    # 推定窓の長さ（営業日換算）。連動モードは「保有期間」= freq_months*21日 相当
    coupled_window_days = max(freq_months * 21, 42)  # 最低42営業日は確保

    for i, date in enumerate(idx):
        this_month = month_key[i]
        is_rebal_day = (this_month in rebal_months) and (
            i == 0 or month_key[i - 1] != this_month
        )
        if is_rebal_day:
            window_days = (
                coupled_window_days if window_mode == "coupled"
                else ESTIMATION_WINDOW_FIXED_DAYS
            )
            hist = returns.iloc[max(0, i - window_days):i]
            if len(hist) >= max(20, window_days // 4):
                w = weight_fn(hist.values)
                scale = scale_to_risk_budget(w, hist.values, RISK_BUDGET_ANNUAL)
                current_w, current_scale = w, scale
        if current_w is not None:
            port_returns.iloc[i] = float(returns.iloc[i].values @ current_w) * current_scale
        # else: まだ最初のリバランス前 → キャッシュ(0%)のまま

    return port_returns


def backtest_averaged_over_phase(returns: pd.DataFrame, freq_months: int,
                                  window_mode: str, proxy_name: str) -> pd.Series:
    """位相（リバランス日のずらし）を全通り計算し、日次リターンを平均する
    （timing luck の統制）。"""
    phases = range(freq_months)
    series_list = [
        backtest_one(returns, freq_months, window_mode, proxy_name, p)
        for p in phases
    ]
    return pd.concat(series_list, axis=1).mean(axis=1)


# --------------------------------------------------------------------------
# 5. シャープレシオと D 統計量
# --------------------------------------------------------------------------
def annualized_sharpe(daily_returns: pd.Series) -> float:
    mu = daily_returns.mean() * TRADING_DAYS_PER_YEAR
    sd = daily_returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(mu / sd) if sd > 0 else float("nan")


def compute_D(sharpe_table: dict) -> float:
    """sharpe_table: {(freq, proxy): sharpe}。
    R_f = 頻度間の幅（各尺度でfreq間のmax-min、尺度について平均）
    R_p = 尺度間の幅（各頻度でproxy間のmax-min、頻度について平均）
    D = R_f - R_p"""
    proxies = sorted(set(p for (_, p) in sharpe_table))
    freqs = sorted(set(f for (f, _) in sharpe_table))

    freq_spreads = []
    for p in proxies:
        vals = [sharpe_table[(f, p)] for f in freqs]
        freq_spreads.append(max(vals) - min(vals))
    R_f = float(np.mean(freq_spreads))

    proxy_spreads = []
    for f in freqs:
        vals = [sharpe_table[(f, p)] for p in proxies]
        proxy_spreads.append(max(vals) - min(vals))
    R_p = float(np.mean(proxy_spreads))

    return R_f - R_p


# --------------------------------------------------------------------------
# 6. ブロックブートストラップ
# --------------------------------------------------------------------------
def block_bootstrap_D(daily_return_series: dict, n_boot=N_BOOTSTRAP,
                       block_months=BOOTSTRAP_BLOCK_MONTHS, seed=RANDOM_SEED):
    """daily_return_series: {(freq, proxy): pd.Series(日次リターン)}。
    月ブロックで共通の月インデックスをリサンプリングし、D の分布を出す。
    全系列で同じ月の並びを使う（系列間の相関構造を保つ）。"""
    rng = np.random.default_rng(seed)
    keys = list(daily_return_series.keys())
    # 共通のインデックスに揃える
    common_index = None
    for s in daily_return_series.values():
        common_index = s.index if common_index is None else common_index.intersection(s.index)
    aligned = {k: daily_return_series[k].reindex(common_index) for k in keys}

    months = common_index.to_period("M")
    unique_months = months.unique()
    month_to_positions = {m: np.where(months == m)[0] for m in unique_months}
    n_months = len(unique_months)

    D_samples = []
    for _ in range(n_boot):
        sampled_months = rng.choice(unique_months, size=n_months, replace=True)
        positions = np.concatenate([month_to_positions[m] for m in sampled_months])
        sharpe_table = {}
        for k in keys:
            r = aligned[k].values[positions]
            sharpe_table[k] = annualized_sharpe(pd.Series(r))
        D_samples.append(compute_D(sharpe_table))

    D_samples = np.array(D_samples)
    lo, hi = np.percentile(D_samples, [2.5, 97.5])
    return float(lo), float(hi), D_samples


# --------------------------------------------------------------------------
# 7. メイン
# --------------------------------------------------------------------------
def run(out_dir: str, cache_path: str):
    print(f"[{datetime.now():%H:%M:%S}] データ取得中…")
    px = fetch_prices(cache_path=cache_path)
    returns = px.pct_change().dropna(how="any")
    print(f"[{datetime.now():%H:%M:%S}] データ取得完了: {returns.shape[0]}営業日 "
          f"({returns.index[0].date()} 〜 {returns.index[-1].date()})、{returns.shape[1]}銘柄")

    results = {}  # window_mode -> {(freq, proxy): daily_return_series}
    sharpe_tables = {}  # window_mode -> {(freq, proxy): sharpe}

    for window_mode in ["coupled", "fixed"]:
        results[window_mode] = {}
        sharpe_tables[window_mode] = {}
        for freq in FREQUENCIES_MONTHS:
            for proxy in RISK_PROXIES:
                print(f"[{datetime.now():%H:%M:%S}] window={window_mode} "
                      f"freq={freq}ヶ月 proxy={proxy} 計算中…")
                series = backtest_averaged_over_phase(returns, freq, window_mode, proxy)
                results[window_mode][(freq, proxy)] = series
                sharpe_tables[window_mode][(freq, proxy)] = annualized_sharpe(series)

    D_orig = compute_D(sharpe_tables["coupled"])
    D_fixed = compute_D(sharpe_tables["fixed"])

    print(f"[{datetime.now():%H:%M:%S}] D_orig={D_orig:.4f}  D_fixed={D_fixed:.4f}")
    print(f"[{datetime.now():%H:%M:%S}] ブロックブートストラップ中（B={N_BOOTSTRAP}）…")

    lo_orig, hi_orig, _ = block_bootstrap_D(results["coupled"])
    lo_fixed, hi_fixed, _ = block_bootstrap_D(results["fixed"])

    # 判定（測る前に固定した基準どおり）
    if D_orig <= 0:
        verdict = "未確定（原設計でD>0が再現しない。頻度の支配自体が再現できていない）"
        ratio = None
    else:
        ratio = D_fixed / D_orig
        interval_includes_zero = (lo_orig <= 0 <= hi_orig) or (lo_fixed <= 0 <= hi_fixed)
        if ratio <= 0.5:
            verdict = "支持（頻度の支配は主に推定窓の効果）"
        elif ratio >= 0.8:
            verdict = "棄却（推定窓によらず頻度そのものが効く）"
        else:
            verdict = "未確定（比が0.5〜0.8の間）"
        if interval_includes_zero:
            verdict += "　※ただしブートストラップ区間が0を含むため、点推定どまりで『確定』とは書かない"

    report = {
        "検証": "Q088 リバランス頻度の支配は推定窓の交絡か（株・米国セクターETF）",
        "実行日時": datetime.now().isoformat(timespec="seconds"),
        "データ期間": f"{returns.index[0].date()} - {returns.index[-1].date()}",
        "銘柄": TICKERS,
        "尺度": list(RISK_PROXIES.keys()) + ["（IQR・P95は実装コストのため省略。分散・MADの2尺度に縮小）"],
        "シャープレシオ表": {
            mode: {f"{f}ヶ月_{p}": round(v, 4) for (f, p), v in table.items()}
            for mode, table in sharpe_tables.items()
        },
        "D_orig（連動窓）": round(D_orig, 4),
        "D_orig_95%区間": [round(lo_orig, 4), round(hi_orig, 4)],
        "D_fixed（固定窓252日）": round(D_fixed, 4),
        "D_fixed_95%区間": [round(lo_fixed, 4), round(hi_fixed, 4)],
        "比(D_fixed/D_orig)": round(ratio, 4) if ratio is not None else None,
        "判定": verdict,
        "限界": [
            "リスク尺度は分散・MADの2つのみ（IQR・P95は未実装）",
            "リバランス間のウェイトのドリフトは考慮していない（リバランス時点で固定し直す簡略化）",
            "リスク予算は年率10%の1水準のみ（原論文は5/10/15%の3水準）",
            "位相は月単位でのみ平均している",
            "連動窓は1ヶ月頻度でも最低42営業日を確保（9資産の共分散行列の数値安定性のため）。"
            "原論文の『1ヶ月スケジュールは約21営業日で推定』（§3.7.4）とは厳密には異なる",
        ],
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"Q088_result_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now():%H:%M:%S}] 結果を書き出した: {out_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    parser.add_argument("--cache", default=os.path.join(os.path.dirname(__file__), "data", "sector_etf_prices.csv"))
    args = parser.parse_args()
    run(args.out, args.cache)
