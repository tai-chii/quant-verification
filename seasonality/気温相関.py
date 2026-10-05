import numpy as np, json
import csv
ME={}
for r in csv.DictReader(open('週次終値_6銘柄.csv',encoding='utf-8')):
    y,m,_=r['日付'].split('-'); ME.setdefault(r['コード'],{})[(int(y),int(m))]=float(r['調整後終値'])
for r in csv.DictReader(open('月末値_追試.csv',encoding='utf-8')):
    ME.setdefault(r['コード'],{})[(int(r['年']),int(r['月']))]=float(r['月末の週の終値'])
TA={}
for l in [x for x in open('気温偏差_日本_月別.csv',encoding='utf-8') if x[:1].isdigit()]:
    p=l.strip().replace('−','-').split(','); y=int(p[0])
    for i,v in enumerate(p[1:]):
        if v: TA[(y,i+1)]=float(v)
def mr(k):
    ks=sorted(ME[k]); return {ks[i]:ME[k][ks[i]]/ME[k][ks[i-1]]-1 for i in range(1,len(ks))}
R={k:mr(k) for k in ['6367','5909','5951','5946','5947','2502','2503','N225']}
N=R['N225']
beta={}
for k in R:
    if k=='N225':continue
    c=[x for x in R[k] if x in N]; a=np.array([N[i] for i in c]); b=np.array([R[k][i] for i in c]); beta[k]=np.cov(a,b)[0,1]/a.var(ddof=1)
def exr(k,y,m0,m1): # beta-adjusted excess, end of m0 -> end of m1 (m0 can be <=0 for prev year)
    a=(y,m0) if m0>0 else (y-1,12+m0); b=(y,m1)
    if a not in ME[k] or b not in ME[k] or a not in ME['N225'] or b not in ME['N225']: return None
    r=ME[k][b]/ME[k][a]-1; n=ME['N225'][b]/ME['N225'][a]-1; return (r-beta[k]*n)*100
def tavg(y,months): # months list of (dy,m)
    v=[TA.get((y+dy,m)) for dy,m in months]; return None if None in v else np.mean(v)
def corr(x,y,nperm=20000):
    x=np.array(x);y=np.array(y);r=np.corrcoef(x,y)[0,1];rng=np.random.default_rng(1)
    ps=np.array([np.corrcoef(x,rng.permutation(y))[0,1] for _ in range(nperm)]);p=(np.abs(ps)>=abs(r)).mean()
    sl=np.polyfit(x,y,1)[0];return r,p,sl
SUMMER=[(0,6),(0,7),(0,8)]; WINTER=[(-1,12),(0,1),(0,2)]
tests=[]
# (label, stocks, temp months, return window m0,m1, expected sign)
spec=[('夏の気温 × 夏の株価（6〜8月）','summer',SUMMER,5,8),
      ('夏の気温 × 秋の株価（9〜11月）','summer_next',SUMMER,8,11),
      ('冬の気温 × 冬の株価（12〜2月）','winter',WINTER,-1,2),
      ('冬の気温 × 春の株価（3〜5月）','winter_next',WINTER,2,5)]
names={'6367':'ダイキン','5909':'コロナ','5951':'ダイニチ','5946':'長府','5947':'リンナイ','2502':'アサヒ','2503':'キリン'}
res={}
for lab,key,tm,m0,m1 in spec:
    for k in names:
        xs,ys,yr=[],[],[]
        for y in range(2005,2027):
            t=tavg(y,tm); r=exr(k,y,m0,m1)
            if t is None or r is None: continue
            xs.append(t);ys.append(r);yr.append(y)
        r,p,sl=corr(xs,ys)
        res[f'{key}|{k}']={'label':lab,'r':round(r,3),'p':round(p,4),'slope':round(sl,2),'n':len(xs),'pts':[[yy,round(a,2),round(b,2)] for yy,a,b in zip(yr,xs,ys)]}
        print(f'{lab:22} {names[k]:5} n{len(xs)} r{r:+.2f} p{p:.3f} slope{sl:+.2f}%/℃')
# monthly pooled: cooling months Jun-Sep; heating months Nov-Feb
print('--- monthly pooled (same-month temp anomaly vs same-month excess)')
for k in names:
    for lab,ms in [('夏月(6-9)',[6,7,8,9]),('冬月(11-2)',[11,12,1,2])]:
        xs,ys=[],[]
        for (y,m),t in TA.items():
            if m not in ms or y<2005: continue
            r=exr(k,y,m-1,m) if m>1 else exr(k,y,0,1)
            if r is None: continue
            xs.append(t);ys.append(r)
        r,p,sl=corr(xs,ys,5000);print(f'{names[k]:5} {lab} n{len(xs)} r{r:+.2f} p{p:.3f}')
        res[f'm_{lab}|{k}']={'r':round(r,3),'p':round(p,4),'n':len(xs)}
json.dump({'res':res,'beta':{k:round(v,2) for k,v in beta.items()}},open('気温相関_結果.json','w'),ensure_ascii=False)
print('--- winter excess -> spring excess (reversal)')
for k in ['5909','5951','5946']:
    xs,ys=[],[]
    for y in range(2006,2027):
        a=exr(k,y,-1,2);b=exr(k,y,2,5)
        if a is None or b is None:continue
        xs.append(a);ys.append(b)
    r,p,sl=corr(xs,ys);print(names[k],f'n{len(xs)} r{r:+.2f} p{p:.3f}')
    res[f'rev|{k}']={'r':round(r,3),'p':round(p,4),'n':len(xs),'pts':[[round(a,2),round(b,2)] for a,b in zip(xs,ys)]}
json.dump({'res':res,'beta':{k:round(v,2) for k,v in beta.items()}},open('気温相関_結果.json','w'),ensure_ascii=False)
