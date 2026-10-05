"""exp_012 の準備: exp_009 と同じ設定で OOF の予測（oof_cache.pkl）を作り直す。
元の oof_cache.pkl は残っていない（実行環境 /root/hull が消えた）。
LightGBM の版が違うと予測がわずかに変わりうるので、exp_010・011 のスコアとの一致を確かめてから使う。"""
import numpy as np, pandas as pd, lightgbm as lgb, pickle
import hull_lib as H
df = H.data(); feats = [c for c in df.columns if c not in H.TRAIN_ONLY + ["date_id"]]
folds = H.make_folds(len(df)); EMB = 1
oof = []
for va_s, va_e in folds:
    tr_end = va_s - EMB
    X_va = df.loc[va_s:va_e-1, feats]
    ranks = []
    for name, (mode, p) in H.CANDIDATES.items():
        idx = (df.index[(df.date_id >= p) & (df.index < tr_end)] if mode == "abs"
               else df.index[(df.index >= max(0, tr_end-p)) & (df.index < tr_end)])
        Xtr, ytr = df.loc[idx, feats], df.loc[idx, H.EVAL_TARGET]
        pr = np.zeros(len(X_va))
        for sd in (42, 43, 44):
            pr += lgb.LGBMRegressor(random_state=sd, **H.DEFAULT_PARAMS).fit(Xtr, ytr).predict(X_va)
        ranks.append(pd.Series(pr/3).rank(pct=True).values)
    oof.append(dict(rank=np.mean(ranks, axis=0),
                    fr=df.loc[va_s:va_e-1, "forward_returns"].values,
                    rf=df.loc[va_s:va_e-1, "risk_free_rate"].values,
                    y=df.loc[va_s:va_e-1, H.EVAL_TARGET].values))
    print("fold", va_s, flush=True)
pickle.dump(oof, open("oof_cache.pkl", "wb"))
print("lightgbm", lgb.__version__)
