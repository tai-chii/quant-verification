# 暖房株 春の空売り検証（2026-09-30）
# 入力: 週次終値_6銘柄.csv（コロナ・ダイニチ・日経平均ほか）、月末値_追試.csv（長府・リンナイ）
# ルール: 3月末の週の終値で空売り＋日経平均をベータ分買い → 5月末の週の終値で手じまい。コスト0.4%/回
import csv, numpy as np
ME={}
for r in csv.DictReader(open('週次終値_6銘柄.csv',encoding='utf-8')):
    y,m,_=r['日付'].split('-'); ME.setdefault(r['コード'],{})[(int(y),int(m))]=float(r['調整後終値'])
for r in csv.DictReader(open('月末値_追試.csv',encoding='utf-8')):
    ME.setdefault(r['コード'],{})[(int(r['年']),int(r['月']))]=float(r['月末の週の終値'])
COST=0.004; YRS=range(2005,2027)
def ret(k,y,m0,m1):
    a=(y,m0) if m0>0 else (y-1,12); b=(y,m1) if m1<=12 else (y+1,m1-12)
    return ME[k][b]/ME[k][a]-1 if a in ME[k] and b in ME[k] else None
def mrets(k):
    ks=sorted(ME[k]); return {ks[i]:ME[k][ks[i]]/ME[k][ks[i-1]]-1 for i in range(1,len(ks))}
N=mrets('N225'); beta={}
for k in ['5909','5951','5946','5947']:
    R=mrets(k); c=[x for x in R if x in N]; x=np.array([N[i] for i in c]); yv=np.array([R[i] for i in c]); beta[k]=np.cov(x,yv)[0,1]/x.var(ddof=1)
def pnl(ks,y,m0=3,m1=5,mode='beta'):
    rs=[ret(k,y,m0,m1) for k in ks]; n=ret('N225',y,m0,m1)
    if None in rs or n is None: return None
    h={'raw':lambda k:0,'one':lambda k:1,'beta':lambda k:beta[k]}[mode]
    return np.mean([-(r-h(k)*n) for r,k in zip(rs,ks)])-COST
def summ(v):
    v=np.array(v)
    rng=np.random.default_rng(0); bs=[rng.choice(v,len(v)).mean() for _ in range(10000)]
    return f"平均{v.mean()*100:+.2f}% 勝ち{(v>0).sum()}/{len(v)} t{v.mean()/(v.std(ddof=1)/np.sqrt(len(v))):+.2f} 95%[{np.percentile(bs,2.5)*100:+.2f},{np.percentile(bs,97.5)*100:+.2f}]"
print('beta',{k:round(v,2) for k,v in beta.items()})
for name,ks in [('コロナ＋ダイニチ',['5909','5951']),('長府',['5946']),('リンナイ',['5947'])]:
    for mode in ['beta','one','raw']:
        v=[pnl(ks,y,mode=mode) for y in YRS]; v=[x for x in v if x is not None]
        print(name,mode,summ(v))
