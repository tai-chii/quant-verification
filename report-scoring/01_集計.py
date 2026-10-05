# 01_集計.py  (2026-10-04) 00_計画.md の判定どおりに AUC を出す（採点後にラベルと突き合わせる）
import json, csv, numpy as np, pandas as pd
S=pd.DataFrame(json.load(open("scores_blind.json",encoding="utf-8")))
K=json.load(open("key_map.json",encoding="utf-8")); S["id"]=S.key.map(K)
L=pd.DataFrame(list(csv.DictReader(open("labels.csv",encoding="utf-8"))))
D=S.merge(L,on="id"); D["残った"]=(D.ラベル=="残った").astype(int)
D["7月"]=D.見出し.str.startswith("2026-07")
def auc(x,y):
    p=x[y==1]; n=x[y==0]
    if len(p)==0 or len(n)==0: return np.nan
    return np.mean([(a>b)+0.5*(a==b) for a in p for b in n])
def boot(x,y,B=2000,seed=1):
    r=np.random.default_rng(seed); v=[]
    for _ in range(B):
        i=r.integers(0,len(x),len(x)); a=auc(x[i],y[i])
        if not np.isnan(a): v.append(a)
    return np.percentile(v,[2.5,97.5])
out=[]
for lab,sub in [("全体",D),("7月だけ",D[D["7月"]]),("8月以降",D[~D["7月"]])]:
    x=sub.total.values.astype(float); y=sub.残った.values
    a=auc(x,y); lo,hi=boot(x,y) if len(set(y))>1 else (np.nan,np.nan)
    out.append(dict(範囲=lab,回数=len(sub),覆った=int((y==0).sum()),AUC=round(a,3) if a==a else None,区間=f"{lo:.2f}〜{hi:.2f}",
                   残った平均点=round(x[y==1].mean(),2) if (y==1).any() else None,覆った平均点=round(x[y==0].mean(),2) if (y==0).any() else None))
R=pd.DataFrame(out); print(R.to_string(index=False))
items=["R1","R2","R3","R4","R5","R6","R7","R8"]
print("\n項目別（満たした割合: 残った／覆った）")
for it in items:
    print(f"  {it}: {(D[D.残った==1][it]>0).mean():.0%} ／ {(D[D.残った==0][it]>0).mean():.0%}")
D.sort_values("id")[["id","total","ラベル","見出し"]].to_csv("結果_回ごと.csv",index=False)
R.to_csv("結果_AUC.csv",index=False)
g=R.iloc[0]; print("\n判定（主）:", "予測する傾向あり" if (g.AUC>0.5 and float(g.区間.split('〜')[0])>0.5) else "区別できない")
