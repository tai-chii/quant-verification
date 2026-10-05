"""
Hull Tactical 共通評価ハーネス
==============================
kaggle/_playbook/改善判定.md の対応あり比較を前提に、
「1回1変更」で設定を差し替えられるようにしたもの。

確定済みの設計（exp_001-005）:
  * 学習期間は選ばない。A/B/C/D の4本を学習し予測をランク平均する
  * 欠損補完はしない（LightGBMのネイティブ処理に任せる）
  * 評価は全設定で同一fold・同一seed
"""
import numpy as np, pandas as pd, lightgbm as lgb
from scipy.stats import spearmanr

import os
TRAIN = os.environ.get("HULL_TRAIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "train.csv"))
TRAIN_ONLY = ["forward_returns", "risk_free_rate", "market_forward_excess_returns"]
EVAL_TARGET = "market_forward_excess_returns"      # 評価は常にこれで固定
CANDIDATES = {"A_from1661": ("abs", 1661), "B_from3450": ("abs", 3450),
              "C_last4000": ("rel", 4000), "D_last2000": ("rel", 2000)}
DEFAULT_PARAMS = dict(objective="regression", num_leaves=15, learning_rate=0.03,
                      n_estimators=300, feature_fraction=0.7, bagging_fraction=0.8,
                      bagging_freq=1, min_child_samples=50, verbose=-1, n_jobs=2)

_df = None
def data():
    global _df
    if _df is None:
        _df = pd.read_csv(TRAIN).sort_values("date_id").reset_index(drop=True)
    return _df

def make_folds(n, n_folds=6, fold_len=250):
    start = n - n_folds * fold_len
    return [(start + i*fold_len, start + (i+1)*fold_len) for i in range(n_folds)]

def run(train_target=EVAL_TARGET, embargo=1, n_folds=6, fold_len=250,
        seeds=(42, 43, 44), params=None, label=""):
    """確定パイプライン（A/B/C/D ランク平均）を1設定で回し、fold毎ICを返す。"""
    df = data(); params = {**DEFAULT_PARAMS, **(params or {})}
    feats = [c for c in df.columns if c not in TRAIN_ONLY + ["date_id"]]
    folds = make_folds(len(df), n_folds, fold_len)
    ens_ic, per_cand = [], {k: [] for k in CANDIDATES}

    for va_s, va_e in folds:
        tr_end = va_s - embargo
        y_va = df.loc[va_s:va_e-1, EVAL_TARGET].values
        X_va = df.loc[va_s:va_e-1, feats]
        ranks = []
        for name, (mode, p) in CANDIDATES.items():
            if mode == "abs":
                idx = df.index[(df.date_id >= p) & (df.index < tr_end)]
            else:
                idx = df.index[(df.index >= max(0, tr_end - p)) & (df.index < tr_end)]
            Xtr, ytr = df.loc[idx, feats], df.loc[idx, train_target]
            pr = np.zeros(len(X_va))
            for sd in seeds:
                pr += lgb.LGBMRegressor(random_state=sd, **params).fit(Xtr, ytr).predict(X_va)
            pr /= len(seeds)
            per_cand[name].append(spearmanr(pr, y_va).statistic)
            ranks.append(pd.Series(pr).rank(pct=True).values)
        ens_ic.append(spearmanr(np.mean(ranks, axis=0), y_va).statistic)

    return dict(label=label, ic=ens_ic, per_candidate=per_cand,
                mean=float(np.mean(ens_ic)), std=float(np.std(ens_ic, ddof=1)),
                worst=float(np.min(ens_ic)), n_pos=int(np.sum(np.array(ens_ic) > 0)))

def paired(a, b):
    """対応あり比較。(差の平均, se_d, 比, 判定)"""
    d = np.array(a) - np.array(b)
    se = d.std(ddof=1) / np.sqrt(len(d))
    r = d.mean() / se
    v = "有意差あり" if abs(r) > 2 else ("保留" if abs(r) > 1 else "差なし")
    return d.mean(), se, r, v

def report(results, base_key):
    print(f"\n{'設定':<26}{'IC':>10}{'std':>9}{'最悪fold':>10}{'正fold':>8}")
    for k, r in results.items():
        print(f"  {k:<24}{r['mean']:>+10.4f}{r['std']:>9.4f}{r['worst']:>+10.4f}"
              f"{r['n_pos']:>6}/{len(r['ic'])}")
    print(f"\n=== 対応あり比較（基準: {base_key}）===")
    for k, r in results.items():
        if k == base_key: continue
        m, se, t, v = paired(r["ic"], results[base_key]["ic"])
        print(f"  {k:<24} vs {base_key}: {m:+.4f}  se_d {se:.4f}  比 {t:+.2f}  → {v}")
