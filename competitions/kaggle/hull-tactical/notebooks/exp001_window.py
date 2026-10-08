"""
exp_001-004: 学習期間の下限を測定で決める
=========================================
論点: 学習に使う期間をどこから取るか（レジーム多様性 vs 特徴量の完全性）

設計上の要点:
  * 4候補すべてを **同一の評価fold** で評価する。学習データの遡り方だけを変える。
    （評価期間まで変えると、比較が「期間の違い」と混ざって無意味になる）
  * LightGBM は欠損をネイティブに扱うため、補完は行わない（補完方法という
    未決定の選択肢を比較に混入させないため）
  * seed平均でノイズを落とし、fold毎スコアを残して対応あり比較にかける
     （kaggle/_playbook/改善判定.md）

主指標: out-of-fold Spearman IC（予測と実現超過リターンの順位相関）
  配分マッピングが未決定なので、Sharpeを主指標にすると
  「期間の良し悪し」と「マッピングの良し悪し」が混ざる。ICは配分設計から独立。
副指標: 単純マッピングでのSharpe（参考値）
"""
import numpy as np, pandas as pd, lightgbm as lgb, json, sys
from scipy.stats import spearmanr

TRAIN = "/root/hull/train.csv"
TARGET = "market_forward_excess_returns"
TRAIN_ONLY = ["forward_returns", "risk_free_rate", "market_forward_excess_returns"]

# ---- 暫定パラメータ（測定なしで決めた = 技術的負債。EDA.md 暫定判断ログに記録）----
EMBARGO = 5        # ラベルは1日先を見る。特徴量のローリング窓を考慮して余裕を取った
N_FOLDS = 6
FOLD_LEN = 250     # 約1年
SEEDS = [42, 43, 44]
PARAMS = dict(objective="regression", num_leaves=15, learning_rate=0.03,
              n_estimators=300, feature_fraction=0.7, bagging_fraction=0.8,
              bagging_freq=1, min_child_samples=50, verbose=-1, n_jobs=4)

CANDIDATES = {
    "A_from1661":  ("abs", 1661),   # 欠損<20% 以降すべて
    "B_from3450":  ("abs", 3450),   # 欠損<10% 以降すべて
    "C_last4000":  ("rel", 4000),   # fold直前から4000行
    "D_last2000":  ("rel", 2000),   # fold直前から2000行
}

def main():
    df = pd.read_csv(TRAIN).sort_values("date_id").reset_index(drop=True)
    feats = [c for c in df.columns if c not in TRAIN_ONLY + ["date_id"]]
    n = len(df)

    # 評価fold: 末尾 N_FOLDS*FOLD_LEN 行を等分（全候補共通）
    eval_start = n - N_FOLDS * FOLD_LEN
    folds = [(eval_start + i*FOLD_LEN, eval_start + (i+1)*FOLD_LEN) for i in range(N_FOLDS)]
    print(f"train {df.shape}  特徴量 {len(feats)}")
    print(f"評価fold: 行 {eval_start}〜{n}  (date_id {df.date_id[eval_start]}〜{df.date_id[n-1]})")
    for i,(a,b) in enumerate(folds):
        print(f"  fold{i}: 行{a}-{b}  date_id {df.date_id[a]}-{df.date_id[b-1]}")
    print(f"embargo={EMBARGO}日  seeds={SEEDS}\n")

    results = {}
    for name, (mode, param) in CANDIDATES.items():
        ics, shps, ntr = [], [], []
        for fi, (va_s, va_e) in enumerate(folds):
            tr_end = va_s - EMBARGO                      # purge + embargo
            tr_start = param if mode == "abs" else max(0, tr_end - param)
            tr_start = max(tr_start, 0)
            idx_tr = df.index[(df.index >= tr_start) & (df.index < tr_end)]
            if mode == "abs":
                idx_tr = df.index[(df.date_id >= param) & (df.index < tr_end)]
            Xtr, ytr = df.loc[idx_tr, feats], df.loc[idx_tr, TARGET]
            Xva, yva = df.loc[va_s:va_e-1, feats], df.loc[va_s:va_e-1, TARGET]

            preds = np.zeros(len(Xva))
            for sd in SEEDS:
                m = lgb.LGBMRegressor(random_state=sd, **PARAMS)
                m.fit(Xtr, ytr)
                preds += m.predict(Xva)
            preds /= len(SEEDS)

            ic = spearmanr(preds, yva).statistic
            # 参考: 予測符号ベースの単純配分 (0/1/2) での日次Sharpe
            alloc = np.clip(1 + np.sign(preds), 0, 2)
            r = alloc * yva.values
            shp = r.mean() / (r.std(ddof=1) + 1e-12) * np.sqrt(252)
            ics.append(ic); shps.append(shp); ntr.append(len(idx_tr))
        results[name] = dict(ic=ics, sharpe=shps, n_train=ntr)
        print(f"{name:14s} 学習行数 {int(np.mean(ntr)):>5}  "
              f"IC {np.mean(ics):+.4f} ± {np.std(ics, ddof=1):.4f}  "
              f"Sharpe {np.mean(shps):+.3f}")
        print(f"{'':14s} fold毎IC: {['%+.4f'%v for v in ics]}")

    # ---- 対応あり比較（改善判定.md の手続き）----
    print("\n=== 対応あり比較: 各候補 vs 最良候補 (IC, fold毎の差) ===")
    best = max(results, key=lambda k: np.mean(results[k]["ic"]))
    print(f"最良: {best}\n")
    bic = np.array(results[best]["ic"])
    for name in CANDIDATES:
        if name == best: continue
        d = bic - np.array(results[name]["ic"])
        se = d.std(ddof=1)/np.sqrt(len(d))
        verdict = "有意差あり" if d.mean() > 2*se else ("保留" if d.mean() > se else "差なし")
        print(f"  {best} - {name:14s}: {d.mean():+.4f}  se_d {se:.4f}  "
              f"比 {d.mean()/se:+.2f}  → {verdict}")

    json.dump(results, open("/root/hull/exp001_results.json","w"), indent=1)
    print("\nsaved /root/hull/exp001_results.json")

if __name__ == "__main__":
    main()
