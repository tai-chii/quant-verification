"""
exp_005: 学習期間候補は「競合」ではなく「アンサンブル軸」ではないか
====================================================================
exp_001-004 の結果: A/B/C/D の IC 平均差はすべて se 未満 = 測定では区別できない。
しかし fold毎のパターンは候補ごとに大きく違う（Aはfold5で失敗、Cはfold0で失敗）。

仮説: 候補間の予測が脱相関しているなら、平均すると分散が下がる。
      つまり「どれを選ぶか」ではなく「全部混ぜる」が正解の可能性がある。

判定: 単体最良 vs アンサンブル を fold毎の対応あり比較にかける。
"""
import numpy as np, pandas as pd, lightgbm as lgb, json
from scipy.stats import spearmanr
from itertools import combinations

TRAIN="/root/hull/train.csv"; TARGET="market_forward_excess_returns"
TRAIN_ONLY=["forward_returns","risk_free_rate","market_forward_excess_returns"]
EMBARGO=5; N_FOLDS=6; FOLD_LEN=250; SEEDS=[42,43,44]
PARAMS=dict(objective="regression",num_leaves=15,learning_rate=0.03,n_estimators=300,
            feature_fraction=0.7,bagging_fraction=0.8,bagging_freq=1,
            min_child_samples=50,verbose=-1,n_jobs=4)
CANDIDATES={"A_from1661":("abs",1661),"B_from3450":("abs",3450),
            "C_last4000":("rel",4000),"D_last2000":("rel",2000)}

def ic_by_fold(pred_folds, y_folds):
    return [spearmanr(p,y).statistic for p,y in zip(pred_folds,y_folds)]

def paired(a,b):
    d=np.array(a)-np.array(b); se=d.std(ddof=1)/np.sqrt(len(d))
    return d.mean(), se, d.mean()/se

df=pd.read_csv(TRAIN).sort_values("date_id").reset_index(drop=True)
feats=[c for c in df.columns if c not in TRAIN_ONLY+["date_id"]]
n=len(df); eval_start=n-N_FOLDS*FOLD_LEN
folds=[(eval_start+i*FOLD_LEN, eval_start+(i+1)*FOLD_LEN) for i in range(N_FOLDS)]
y_folds=[df.loc[a:b-1,TARGET].values for a,b in folds]

P={}   # 候補 -> fold毎の予測
for name,(mode,param) in CANDIDATES.items():
    pf=[]
    for va_s,va_e in folds:
        tr_end=va_s-EMBARGO
        if mode=="abs": idx=df.index[(df.date_id>=param)&(df.index<tr_end)]
        else:           idx=df.index[(df.index>=max(0,tr_end-param))&(df.index<tr_end)]
        Xtr,ytr=df.loc[idx,feats],df.loc[idx,TARGET]
        Xva=df.loc[va_s:va_e-1,feats]
        pr=np.zeros(len(Xva))
        for sd in SEEDS:
            pr+=lgb.LGBMRegressor(random_state=sd,**PARAMS).fit(Xtr,ytr).predict(Xva)
        pf.append(pr/len(SEEDS))
    P[name]=pf
    print(f"{name} done")

# 予測どうしの相関（脱相関しているか）
print("\n=== 候補間の予測相関（OOF全体, Spearman）===")
flat={k:np.concatenate(v) for k,v in P.items()}
ks=list(CANDIDATES)
print("        "+"".join(f"{k[:10]:>12}" for k in ks))
for a in ks:
    print(f"{a[:10]:>8}"+"".join(f"{spearmanr(flat[a],flat[b]).statistic:>12.3f}" for b in ks))

# 単体 + 全アンサンブル組み合わせ
res={}
for k,v in P.items(): res[k]=ic_by_fold(v,y_folds)
for r in (2,3,4):
    for combo in combinations(ks,r):
        # ランク平均で合成（スケール差を消す）
        pf=[np.mean([pd.Series(P[c][i]).rank(pct=True).values for c in combo],axis=0)
            for i in range(N_FOLDS)]
        res["+".join(c[0] for c in combo)]=ic_by_fold(pf,y_folds)

print("\n=== IC（平均 ± fold標準偏差）===")
rows=sorted(res.items(), key=lambda kv:-np.mean(kv[1]))
for k,v in rows:
    v=np.array(v)
    print(f"  {k:16s} IC {v.mean():+.4f} ± {v.std(ddof=1):.4f}   "
          f"最悪fold {v.min():+.4f}   正のfold {int((v>0).sum())}/{len(v)}")

best_single=max(ks,key=lambda k:np.mean(res[k]))
best_all=rows[0][0]
print(f"\n=== 対応あり比較: {best_all} vs 各単体 ===")
for k in ks:
    m,se,t=paired(res[best_all],res[k])
    verdict="有意差あり" if m>2*se else ("保留" if m>se else "差なし")
    print(f"  {best_all} - {k:14s}: {m:+.4f}  se_d {se:.4f}  比 {t:+.2f}  → {verdict}")

json.dump({k:list(map(float,v)) for k,v in res.items()},
          open("/root/hull/exp005_results.json","w"),indent=1)
print("\nsaved")
