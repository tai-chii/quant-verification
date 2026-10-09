#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q171: 順張りの参照日数 60 通り（TSMOM L ∈ {5,…,300}）を 15 銘柄プール日足で検証したときの
過剰適合の確率 PBO はいくつか（Bailey ほか 2017, Combinatorially Symmetric Cross-Validation, CSCV）
================================================================================

【出典】
- Bailey, Borwein, Lopez de Prado, Zhu 2017 "The Probability of Backtest Overfitting"
  J. Comp. Finance 20(4): アルゴリズム 2.3 p10-11、例1・例2 p25-27、§3-4（PBO・SD・PD）。
  主張ノート: 学問/金融工学/知識/文献/主張/Bailey2017-1_…PBO....md、Bailey2017-2_…CSCVの誤用.md。
- Q139（selection-optimism-vs-J）: 60 候補・15 銘柄・コスト・pnl 計算の雛形。これを踏襲する。

【仮説（測る前に固定）】
H: 60 候補の TSMOM の中から日次 Sharpe で最良を選ぶバックテストは、PBO ≥ 0.5 である（＝選ばれた候補の
   期間外成績は半分以上の場合に中央値以下に落ちる）。CSCV の S=16 で測る。

【データ】
15 銘柄 `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足。値動きのない足は除く）。無いファイルは除外し JSON に書く。
銘柄をまたいだ等ウェイトプール（1日ごとに定義されている銘柄の平均）で、1 本の日次損益系列を候補ごとに作る。

【定義（1 通りに固定）】
- 候補 N=60: L ∈ {5, 10, …, 300}、TSMOM、翌日ポジション、片道コスト段階1、損益は Q139 と同じ式（bp/日）。
- 等ウェイトプール: 日 t と候補 L で、15 銘柄のうち pnl が定義されている銘柄の平均を取る。1 銘柄も
  定義されていない日は候補 L で未定義。
- 期間:
    全期間: データのある全日
    前半: 日付の年 < 2017
    後半: 日付の年 ≥ 2017
- 各期間でブロック分け: 日を時系列順に S 個の等サイズブロックに切る（最後のブロックは余りを含む）。
  全期間 S=16（Bailey の推奨）。前半・後半は S=14（CSCV のブロック長を 300 日前後に保つため）。
- 評価指標: ブロック群の平均日次損益 ÷ 日次標準偏差（アニュアライズ無し、ddof=1）。
  日数が 20 日未満の候補列は Sharpe を nan にして除外（スライス全体ではその日の候補列を落とす）。
- CSCV: C(S, S/2) の全組み合わせで IS と OS を半分ずつに分ける。各組で、
  (a) 60 候補の IS Sharpe を計算 → IS で最良の候補 L* を特定（上位 1 本）、
  (b) 60 候補の OS Sharpe を計算 → L* の OS 順位 r（1 = 最低、N = 最高、同順位は平均順位）、
  (c) 正規化順位 ω = r / (N+1)、λ = log(ω / (1-ω))。
- PBO = 全組の中で λ ≤ 0 となる割合（＝ L* が OS で中央値以下に落ちた割合）。

【測るもの】
- 期間ごと（全・前・後）:
    PBO、λ の中央値・平均、CI、L* の OS Sharpe の平均・中央値、
    性能劣化（Performance Degradation）: 散布図の線形回帰の傾き b と切片 a、
    確率的優越（Stochastic Dominance）: IS-best の OS Sharpe が ≤0 になる割合、
    IS-best の L の分布（最頻 L）。
- 帰無: 各日の 60 候補の列を無作為に並べ替え、同じ CSCV を回したときの PBO 分布 B=100。
  期待値はおよそ 0.5。実測 PBO と帰無の z スコア。

【判定（事前固定・変更禁止）】
主判定（全期間の PBO）:
- PBO ≥ 0.5 かつ 帰無 z ≥ 1 → **支持（過剰適合は半分を超える）**
- PBO ≤ 0.1 → **棄却（過剰適合は小さい）**
- 上の間 → **未確定**
一貫性（前半・後半）:
- 前半 PBO と後半 PBO が主判定と同じバケットなら主判定を採用。
- どちらかが異なるバケットなら **未確定（期間依存）** に差し替える。
補助: 回帰傾き b。負なら「IS で勝つほど OS で負ける（典型の過剰適合）」。|b| ≥ 0.3 を記述。
多重比較: 3 期間 × 1 指標（PBO）。帰無で名目サイズも報告する。

【捨てた案の数】
約4:
 - S=14 を主にする（S=16 で安定化。Bailey 推奨）
 - 候補を Sharpe で選ばず mean で選ぶ（分散正規化で候補間を比較する Bailey §4 の例に合わせて Sharpe）
 - 銘柄ごとに CSCV を回して平均する（まずは等ウェイトプール＝ Bailey §4 の実装規格と整合）
 - ブロックの境界を暦年末に合わせる（等サイズブロックのほうが C(S,S/2) の対称性と Bailey の記述に忠実）

【知識の締め切り】
Claude の知識の締め切り: 2026-06 ごろ。データは 2026-07 まで。CSCV の数値は 18 年の時系列構造に依存するが、
特定の年の相場観だけでは再現できない。

【委託の確かめ方】
原型のアイデア: アイデア候補 第2弾（Fable 2026-10-09）。CSCV の実装は Bailey 2017 のアルゴリズム 2.3 を
直接写す。実行者は結果 JSON のパスと、PBO（全・前・後）、λ の中央値、傾き b、null-z を本体に返す。

【実装】自己完結・決定的（乱数 seed 固定）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_pbo_cscv_tsmom_q171.py            （帰無 B=100、1 分前後）
      python3 kensho_pbo_cscv_tsmom_q171.py --B 10     （軽い試走）
      python3 kensho_pbo_cscv_tsmom_q171.py --smoke    （合成データで経路の確認。結果は results/smoke_*）
"""
import argparse
import datetime as _dt
import itertools
import json
import math
import os
import sys
import unicodedata
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))


def _p(*parts):
    """macOS 共有の NFD 名に対応。"""
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

LS = list(range(5, 305, 5))             # 60 候補
N_LS = len(LS)
MIN_BLOCK_DAYS = 20                     # 1 スライス内で Sharpe を取る最低日数
SPLIT_YEAR = 2017
NULL_B = 100
SEED = 20261009
S_FULL = 16                             # 全期間の S（C(16,8)=12870）
S_HALF = 14                             # 半期間の S（C(14,7)=3432）
PBO_HI = 0.5                            # 支持（過剰適合）
PBO_LO = 0.1                            # 棄却（過剰適合は小さい）
PD_SLOPE_FLAG = 0.3                     # |b| 以上なら記述


# ----------------------------------------------------------------------------- 基本の道具
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def pnl_matrix(c, cost_rt):
    """全候補 L の日次純損益 [bp]（n × 60）。未定義の日は nan。Q139 と同じ式。"""
    n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    M = np.full((n, N_LS), np.nan)
    for j, L in enumerate(LS):
        s = np.full(n, np.nan); s[L:] = np.sign(c[L:] - c[:-L])
        pos_prev = np.concatenate([[np.nan], s[:-1]])
        pp = np.where(np.isfinite(pos_prev), pos_prev, 0.0)
        dpos = np.abs(np.diff(np.concatenate([[0.0], pp])))
        pnl = pp * ret * 1e4 - dpos * cost_bp
        pnl[:L + 1] = np.nan
        M[:, j] = pnl
    return M


def pool_equal_weight(series):
    """15 銘柄の pnl_matrix を日付でそろえ、各 (日, 候補) で定義されている銘柄平均を取る。
    戻り値: dates (ndarray[datetime64[ns]])、M (n_days × 60)。"""
    all_dates = sorted(set().union(*[set(pd.to_datetime(t)) for (t, _) in series.values()]))
    all_dates = pd.DatetimeIndex(all_dates)
    acc = np.zeros((len(all_dates), N_LS))
    cnt = np.zeros((len(all_dates), N_LS), dtype=int)
    for sym, (t, c) in series.items():
        M = pnl_matrix(c, COST_RT[sym])
        dt = pd.DatetimeIndex(pd.to_datetime(t))
        idx = all_dates.get_indexer(dt)
        ok = idx >= 0
        if not ok.all():
            # 本来は全部ヒットする想定（all_dates は union）だが安全策
            M = M[ok]; idx = idx[ok]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            good = np.isfinite(M)
        acc[idx] += np.where(good, M, 0.0)
        cnt[idx] += good.astype(int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pooled = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    return all_dates.values, pooled


def _block_aggregates(M, block_mat):
    """M: (T, N)（nan 可）、block_mat: (S, T)。
    戻り: block_sum, block_sq, block_cnt いずれも (S, N)。"""
    finite = np.isfinite(M)
    M0 = np.where(finite, M, 0.0)
    block_sum = block_mat @ M0
    block_sq = block_mat @ (M0 * M0)
    block_cnt = block_mat @ finite.astype(float)
    return block_sum, block_sq, block_cnt


def _sharpe_from_agg(sum_, sq, cnt):
    """ブロック和から Sharpe（mean/std, ddof=1）。cnt<MIN_BLOCK_DAYS または var<=0 は nan。"""
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = sum_ / cnt
        var_pop = sq / cnt - mean * mean
        var = var_pop * cnt / np.where(cnt > 1, cnt - 1, np.nan)
        sh = mean / np.sqrt(np.where(var > 0, var, np.nan))
    ok = (cnt >= MIN_BLOCK_DAYS) & np.isfinite(sh)
    return np.where(ok, sh, np.nan)


def _rank_rows(X):
    """X: (num_combos, N)（nan 可）。各行の順位（1=最低、N_valid=最高、同順位は平均順位、nan は nan のまま）。
    pandas の rank をかけたのと同じ結果を numpy で返す。"""
    # argsort で順位を作る。nan は最大値（末尾）に。
    out = np.full(X.shape, np.nan)
    for i in range(X.shape[0]):
        row = X[i]
        valid = np.isfinite(row)
        if valid.sum() == 0:
            continue
        r = pd.Series(row[valid]).rank(method="average").values
        tmp = np.full(row.shape, np.nan)
        tmp[valid] = r
        out[i] = tmp
    return out


def pbo_from_matrix(M, S, label):
    """M: (T, N)。S 等分のブロックに切り CSCV で PBO を測る。ベクトル化版。"""
    T, N = M.shape
    if T < S * MIN_BLOCK_DAYS:
        return dict(label=label, S=int(S), T=int(T), N=int(N), n_combos=0, n_lambdas=0,
                    pbo=float("nan"), lambda_mean=float("nan"), lambda_median=float("nan"),
                    lambda_p05=float("nan"), lambda_p95=float("nan"),
                    is_best_sharpe_mean=float("nan"), os_best_sharpe_mean=float("nan"),
                    os_best_sharpe_median=float("nan"), pd_slope=float("nan"), pd_intercept=float("nan"),
                    pd_r2=float("nan"), sd_prob_loss_os=float("nan"), best_L_mode=None, best_L_counts={})
    # 日→ブロック番号 → block_mat (S, T)
    boundaries = np.linspace(0, T, S + 1, dtype=int)
    block_of_day = np.zeros(T, dtype=int)
    for b in range(S):
        block_of_day[boundaries[b]:boundaries[b + 1]] = b
    block_mat = np.zeros((S, T))
    block_mat[block_of_day, np.arange(T)] = 1.0
    b_sum, b_sq, b_cnt = _block_aggregates(M, block_mat)   # 各 (S, N)
    combos = list(itertools.combinations(range(S), S // 2))
    num = len(combos)
    combo_mask = np.zeros((num, S))
    for i, cb in enumerate(combos):
        combo_mask[i, list(cb)] = 1.0
    os_mask = 1.0 - combo_mask
    IS_sum = combo_mask @ b_sum;  OS_sum = os_mask @ b_sum
    IS_sq = combo_mask @ b_sq;    OS_sq = os_mask @ b_sq
    IS_cnt = combo_mask @ b_cnt;  OS_cnt = os_mask @ b_cnt
    sh_is_mat = _sharpe_from_agg(IS_sum, IS_sq, IS_cnt)
    sh_os_mat = _sharpe_from_agg(OS_sum, OS_sq, OS_cnt)
    # 行ごと最大の列（nan は無視）
    valid_is_row = np.isfinite(sh_is_mat).any(axis=1)
    valid_os_row = np.isfinite(sh_os_mat).any(axis=1)
    valid_row = valid_is_row & valid_os_row
    sh_is_rep = np.where(np.isfinite(sh_is_mat), sh_is_mat, -np.inf)
    best_idx = np.argmax(sh_is_rep, axis=1)
    rows_idx = np.arange(num)
    is_best = sh_is_mat[rows_idx, best_idx]
    os_best = sh_os_mat[rows_idx, best_idx]
    # 順位（OS Sharpe の中で IS-best の順位）
    rank_mat = _rank_rows(sh_os_mat)
    rank_of_best = rank_mat[rows_idx, best_idx]
    n_valid = np.isfinite(sh_os_mat).sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        omega = rank_of_best / (n_valid + 1.0)
        omega = np.clip(omega, 1e-9, 1 - 1e-9)
        lam = np.log(omega / (1 - omega))
    ok = valid_row & np.isfinite(rank_of_best) & np.isfinite(lam)
    lam_v = lam[ok]
    is_best_v = is_best[ok]
    os_best_v = os_best[ok]
    best_idx_v = best_idx[ok]
    pbo = float((lam_v <= 0).mean()) if len(lam_v) else float("nan")
    # PD 回帰
    b_slope = a_intercept = pd_r2 = float("nan")
    m2 = np.isfinite(is_best_v) & np.isfinite(os_best_v)
    if m2.sum() >= 10:
        xa, ya = is_best_v[m2], os_best_v[m2]
        vx = ((xa - xa.mean()) ** 2).sum()
        if vx > 0:
            b_slope = float(((xa - xa.mean()) * (ya - ya.mean())).sum() / vx)
            a_intercept = float(ya.mean() - b_slope * xa.mean())
            yhat = a_intercept + b_slope * xa
            ss_res = ((ya - yhat) ** 2).sum()
            ss_tot = ((ya - ya.mean()) ** 2).sum()
            pd_r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    best_L_counts = np.bincount(best_idx_v, minlength=N) if len(best_idx_v) else np.zeros(N, dtype=int)
    best_L_mode_idx = int(np.argmax(best_L_counts)) if best_L_counts.sum() > 0 else -1
    best_L_mode = LS[best_L_mode_idx] if best_L_mode_idx >= 0 else None
    sd_prob_loss = float((os_best_v <= 0).mean()) if len(os_best_v) else float("nan")
    return dict(
        label=label, S=int(S), T=int(T), N=int(N),
        n_combos=int(num), n_lambdas=int(len(lam_v)),
        pbo=pbo,
        lambda_mean=float(lam_v.mean()) if len(lam_v) else float("nan"),
        lambda_median=float(np.median(lam_v)) if len(lam_v) else float("nan"),
        lambda_p05=float(np.quantile(lam_v, 0.05)) if len(lam_v) else float("nan"),
        lambda_p95=float(np.quantile(lam_v, 0.95)) if len(lam_v) else float("nan"),
        is_best_sharpe_mean=float(np.nanmean(is_best_v)) if len(is_best_v) else float("nan"),
        os_best_sharpe_mean=float(np.nanmean(os_best_v)) if len(os_best_v) else float("nan"),
        os_best_sharpe_median=float(np.nanmedian(os_best_v)) if len(os_best_v) else float("nan"),
        pd_slope=b_slope, pd_intercept=a_intercept, pd_r2=pd_r2,
        sd_prob_loss_os=sd_prob_loss,
        best_L_mode=best_L_mode,
        best_L_counts={int(LS[i]): int(c) for i, c in enumerate(best_L_counts) if c > 0},
    )


def null_pbo(M, S, B, rng, label):
    """各日の候補 60 列を無作為に並べ替えた帰無で PBO を B 回計算する。ベクトル化版。"""
    T, N = M.shape
    pbos = []
    for b in range(B):
        idx = np.argsort(rng.random((T, N)), axis=1)
        M2 = np.take_along_axis(M, idx, axis=1)
        r = pbo_from_matrix(M2, S, f"{label}|null_{b}")
        if np.isfinite(r["pbo"]):
            pbos.append(r["pbo"])
    pbos = np.asarray(pbos, float)
    return dict(
        n=int(len(pbos)),
        null_pbo_mean=float(np.nanmean(pbos)) if len(pbos) else float("nan"),
        null_pbo_sd=float(np.nanstd(pbos, ddof=1)) if len(pbos) > 1 else float("nan"),
        null_pbo_p05=float(np.quantile(pbos, 0.05)) if len(pbos) else float("nan"),
        null_pbo_p95=float(np.quantile(pbos, 0.95)) if len(pbos) else float("nan"),
        null_pbo_values=pbos.tolist(),
    )


def judge_period(res_obs, res_null):
    pbo = res_obs["pbo"]
    nm, ns = res_null["null_pbo_mean"], res_null["null_pbo_sd"]
    z = (pbo - nm) / ns if (np.isfinite(pbo) and np.isfinite(ns) and ns > 0) else float("nan")
    if np.isfinite(pbo) and pbo >= PBO_HI and (not np.isfinite(z) or z >= 1):
        bucket = "支持（過剰適合）"
    elif np.isfinite(pbo) and pbo <= PBO_LO:
        bucket = "棄却（過剰適合は小さい）"
    else:
        bucket = "未確定"
    return dict(pbo=pbo, null_pbo_mean=nm, null_z=float(z), bucket=bucket)


def make_plot(by_period, path):
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
        fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
        for a, (per, (obs, nul)) in zip(ax, by_period.items()):
            a.axvline(obs["pbo"], color="r", lw=1.5, label=f"PBO={obs['pbo']:.3f}")
            if nul["null_pbo_values"]:
                a.hist(nul["null_pbo_values"], bins=15, color="gray", alpha=0.6, label=f"null (B={nul['n']})")
            a.axvline(0.5, color="k", lw=.5, linestyle=":")
            a.set_title(f"{per} S={obs['S']} T={obs['T']} 傾き={obs['pd_slope']:+.2f}")
            a.set_xlabel("PBO")
            a.set_xlim(0, 1); a.legend()
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

    if not series:
        print("[Q171] データなし。中断。", file=sys.stderr); sys.exit(1)

    dates, M_full = pool_equal_weight(series)
    years = pd.DatetimeIndex(dates).year.values

    # 最低限、全候補が有限値を持つ日だけに絞ることはしない（CSCV のブロック内で各候補が十分日数持つかを見る）。
    # 期間フィルタのため、まずは「どの候補も未定義」の日（開始部）を落とす
    any_valid = np.isfinite(M_full).any(axis=1)
    M = M_full[any_valid]
    dates_v = dates[any_valid]
    years_v = pd.DatetimeIndex(dates_v).year.values

    def slice_by_period(M, years, per):
        if per == "全期間":
            m = np.ones(len(years), bool)
        elif per == "前半":
            m = years < SPLIT_YEAR
        else:  # 後半
            m = years >= SPLIT_YEAR
        return M[m]

    by_period = {}
    for per in ("全期間", "前半", "後半"):
        Mp = slice_by_period(M, years_v, per)
        S = S_FULL if per == "全期間" else S_HALF
        obs = pbo_from_matrix(Mp, S, per)
        # 各期間ごと帰無。全期間だけ B=指定、半期間は B//2 で妥協（計算量削減）
        Bp = B if per == "全期間" else max(10, B // 2)
        nul = null_pbo(Mp, S, Bp, rng, per)
        by_period[per] = (obs, nul)

    # 判定
    judge_each = {per: judge_period(o, n) for per, (o, n) in by_period.items()}
    primary = judge_each["全期間"]["bucket"]
    if judge_each["前半"]["bucket"] != primary or judge_each["後半"]["bucket"] != primary:
        verdict = "未確定（期間依存）"
    else:
        verdict = primary

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    png_path = make_plot({per: (o, n) for per, (o, n) in by_period.items()},
                         os.path.join(OUT, f"{prefix}Q171_pbo_{stamp}.png"))

    out = dict(
        queue_id="Q171", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, N=N_LS, S_FULL=S_FULL, S_HALF=S_HALF,
                      MIN_BLOCK_DAYS=MIN_BLOCK_DAYS, SPLIT_YEAR=SPLIT_YEAR,
                      NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      null="各日の 60 候補列を無作為に並べ替える（候補ラベルの入れ替え）"),
        data_span=dict(start=str(pd.Timestamp(dates_v[0]).date()), end=str(pd.Timestamp(dates_v[-1]).date()),
                       n_days=int(len(dates_v))),
        n_symbols_used=len(series), missing=missing,
        by_period={per: dict(obs=obs, null=nul) for per, (obs, nul) in by_period.items()},
        judgement=dict(verdict=verdict, per_period=judge_each,
                       thresholds=dict(pbo_high=PBO_HI, pbo_low=PBO_LO, pd_slope_flag=PD_SLOPE_FLAG),
                       note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定）は実行者が記録する。"),
        files=dict(pbo_png=png_path),
        multiple_comparisons="3 期間 × 1 指標（PBO）= 3。主判定は全期間、前後半は一貫性チェック。帰無で名目5%も報告。",
    )
    jpath = os.path.join(OUT, f"{prefix}Q171_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q171] T={len(dates_v)} days  B={B}  smoke={args.smoke}  missing={list(missing)}")
    for per in ("全期間", "前半", "後半"):
        obs, nul = by_period[per]
        j = judge_each[per]
        print(f"  {per:4s}  S={obs['S']}  T={obs['T']}  combos={obs['n_combos']}  PBO={obs['pbo']:.3f}  "
              f"λ中央={obs['lambda_median']:+.2f}  傾き b={obs['pd_slope']:+.2f}  "
              f"OS Sharpe(IS-best)={obs['os_best_sharpe_mean']:+.3f}  "
              f"best_L_mode={obs['best_L_mode']}  SD(prob_loss_OS)={obs['sd_prob_loss_os']:.3f}  "
              f"null_PBO={nul['null_pbo_mean']:.3f}±{nul['null_pbo_sd']:.3f}  z={j['null_z']:+.2f}  → {j['bucket']}")
    print(f"  判定(機械・全体): {verdict}")
    print(f"  JSON: {jpath}")


if __name__ == "__main__":
    main()
