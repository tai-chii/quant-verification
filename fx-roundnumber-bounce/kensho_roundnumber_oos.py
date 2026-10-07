"""キリ番では終値で抜けやすいか — 独立データでの追試（検証キュー Q016）  2026-10-01
事前に固定した仮説: 反転率の差（キリ番−対照）＜0。Q015（主要8通貨H1）とは別のデータで確かめる。
 ① XAUUSD H1（刻み10ドル）・XAGUSD H1（刻み0.50ドル） 期間 2015-2020 / 2021-2026H1
 ② USDJPY M15（刻み0.50円）・EURUSD M15（刻み0.0050） 期間 2021-2026H1
棄却条件: ①②の過半（4組中3組以上）で差＜0にならない、または差が0と区別できない。定義は kensho_roundnumber.py と同じ。
"""
import numpy as np, pandas as pd
def load(p,tf):
    df=pd.read_csv(f'data_{p}_{tf}_dukascopy.csv',header=0,names=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t,format='%Y-%m-%d %H:%M:%S'); return df[df.v>0].sort_values('t').reset_index(drop=True)
def rej_rate(df,step,offset,bar):
    t=df.t.values; h=df.h.values; l=df.l.values; c=df.c.values; one=np.timedelta64(bar,'m'); rej=[]
    for i in range(1,len(df)):
        if t[i]-t[i-1]!=one: continue
        pc=c[i-1]
        up=np.floor((pc-offset)/step)*step+offset+step; dn=np.ceil((pc-offset)/step)*step+offset-step
        if abs(up-pc)<1e-12: up+=step
        if abs(pc-dn)<1e-12: dn-=step
        hu=h[i]>=up; hd=l[i]<=dn
        if hu==hd: continue
        rej.append(c[i]<up if hu else c[i]>dn)
    r=np.array(rej); return r.mean(),len(r)
CASES=[('XAUUSD','H1',10.0,60,'2015-2020','2015-01-01','2021-01-01'),('XAUUSD','H1',10.0,60,'2021-2026H1','2021-01-01','2026-07-01'),
       ('XAGUSD','H1',0.5,60,'2015-2020','2015-01-01','2021-01-01'),('XAGUSD','H1',0.5,60,'2021-2026H1','2021-01-01','2026-07-01'),
       ('USDJPY','M15',0.5,15,'2021-2026H1','2021-01-01','2026-07-01'),('EURUSD','M15',0.005,15,'2021-2026H1','2021-01-01','2026-07-01')]
rows=[]; cache={}
for p,tf,step,bar,name,a,b in CASES:
    if (p,tf) not in cache: cache[(p,tf)]=load(p,tf)
    d=cache[(p,tf)]; d=d[(d.t>=a)&(d.t<b)].reset_index(drop=True)
    pr,nr=rej_rate(d,step,0.0,bar); pc,nc=rej_rate(d,step,step/2,bar)
    se=np.sqrt(pr*(1-pr)/nr+pc*(1-pc)/nc); z=(pr-pc)/se
    rows.append([p,tf,name,nr,nc,round(pr,4),round(pc,4),round(pr-pc,4),round(z,2)])
res=pd.DataFrame(rows,columns=['inst','tf','period','n_round','n_ctrl','rej_round','rej_ctrl','rej_diff','z'])
res.to_csv('output/kensho_roundnumber_oos.csv',index=False); print(res.to_string(index=False))
grp=res.groupby(['inst','tf']).rej_diff.apply(lambda s:(s<0).all())
print('組ごとに全期間で差<0:',grp.to_dict()); print('差<0 の行:',int((res.rej_diff<0).sum()),'/',len(res),' z<-2:',int((res.z<-2).sum()),' z>2:',int((res.z>2).sum()))
