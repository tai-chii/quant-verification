"""損切りの置き場所: キリ番のすぐ外は狩られやすいか（Q018・Osler 2005 の移植）  2026-10-01
事前に固定した仮説と判定（アイデア候補 2026-10-01「損切りの置き場所」の行。測る前に固定）:
  仮説: 水準のすぐ外に置いた仮想の損切りが「刺されて、すぐ水準の内側へ戻る」割合（狩られ率）は、
        キリ番（00・50）のほうが対照（25・75）より高い。
  事象（下側。上側は鏡写し）: 前の足の終値 pc の、すぐ下の水準 L（同じ集合の中で最も近いもの）について、
        この足 t の安値が L に届いた（l_t <= L）＝「接近」。損切り S = L − d。
        到達: l_t <= S。狩られ: 到達し、かつ t..t+N−1 のどれかの終値が L より上（内側）に戻る。
        同じ足で上下両方の水準に届いた足は除外。t−1..t+N−1 が連続した1時間足でない事象は除外。
  主指標: d=2pip（円0.02・他0.0002・金0.20ドル）、N=3本。感度: d∈{1,3}pip、N∈{1,6}。
  銘柄: 主要8通貨＋金（XAUUSD）の H1（Dukascopy）。水準の間隔: 円0.50、他0.0050、金10ドル。
  期間: 2015-2020 / 2021-2026H1（＋通し）。
  判定（主指標で）: 支持 = 通し期間で 9銘柄中5以上が 差>0 かつ z>2、かつ両期間とも5以上で 差>0。
        棄却 = 上を満たさない。逆向き（差<0・z<-2 が5以上）は別に記録する。
  多重比較: 主指標1本で判定。感度の 3d×3N×9銘柄×2期間 は参考扱い。
  コスト: これは売買の損益ではなく損切りの刺さり方の頻度を測るもの。d=2pip はおおむね通常スプレッドの大きさ。
先読みなし（使うのは t−1 の終値と t..t+N−1 の値）。決定的。
"""
import numpy as np, pandas as pd
INST=['EURUSD','GBPUSD','USDJPY','USDCHF','AUDUSD','USDCAD','EURJPY','GBPJPY','XAUUSD']
PERIODS=[('2015-2020','2015-01-01','2021-01-01'),('2021-2026H1','2021-01-01','2026-07-01'),('通し','2015-01-01','2026-07-01')]
DS=[1,2,3]; NS=[1,3,6]
def spec(p):
    if p=='XAUUSD': return 10.0,0.1
    if p.endswith('JPY'): return 0.5,0.01
    return 0.005,0.0001
def load(p):
    df=pd.read_csv(f'data_{p}_H1_dukascopy.csv',header=0,names=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t,format='%Y-%m-%d %H:%M:%S'); df=df[df.v>0].sort_values('t').reset_index(drop=True)
    return df
def events(df,step,offset,pip):
    t=df.t.values; h=df.h.values; l=df.l.values; c=df.c.values; one=np.timedelta64(1,'h'); n=len(df)
    Nmax=max(NS); out=[]
    for i in range(1,n-Nmax):
        if t[i]-t[i-1]!=one: continue
        pc=c[i-1]
        up=np.floor((pc-offset)/step)*step+offset+step
        dn=np.ceil((pc-offset)/step)*step+offset-step
        if abs(up-pc)<1e-12: up+=step
        if abs(pc-dn)<1e-12: dn-=step
        tu=h[i]>=up; td=l[i]<=dn
        if tu==td: continue
        cont=[(t[i+k]-t[i])==k*one for k in range(Nmax)]
        rec={}
        for d in DS:
            if td: hit=l[i]<=dn-d*pip
            else:  hit=h[i]>=up+d*pip
            rec[f'hit{d}']=hit
            for N in NS:
                if not all(cont[:N]): rec[f'hunt{d}_{N}']=np.nan; continue
                if not hit: rec[f'hunt{d}_{N}']=np.nan; continue
                cs=c[i:i+N]
                rec[f'hunt{d}_{N}']=float((cs>dn).any() if td else (cs<up).any())
        out.append(rec)
    return pd.DataFrame(out)
def ztest(a,b):
    a=a.dropna(); b=b.dropna(); pa,pb=a.mean(),b.mean()
    se=np.sqrt(pa*(1-pa)/len(a)+pb*(1-pb)/len(b)); return len(a),len(b),pa,pb,pa-pb,(pa-pb)/se
rows=[]
for p in INST:
    df=load(p); step,pip=spec(p)
    for name,a,b in PERIODS:
        d_=df[(df.t>=a)&(df.t<b)].reset_index(drop=True)
        R=events(d_,step,0.0,pip); C=events(d_,step,step/2,pip)
        for d in DS:
            reach=ztest(R[f'hit{d}'].astype(float),C[f'hit{d}'].astype(float))
            for N in NS:
                hn=ztest(R[f'hunt{d}_{N}'],C[f'hunt{d}_{N}'])
                rows.append([p,name,d,N,len(R),len(C),round(reach[2],4),round(reach[3],4),round(reach[5],2),
                             hn[0],hn[1],round(hn[2],4),round(hn[3],4),round(hn[4],4),round(hn[5],2)])
res=pd.DataFrame(rows,columns=['inst','period','d_pip','N','n_touch_round','n_touch_ctrl','reach_round','reach_ctrl','z_reach',
                               'n_hit_round','n_hit_ctrl','hunt_round','hunt_ctrl','hunt_diff','z_hunt'])
res.to_csv('output/kensho_stophunt.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_columns',20)
m=res[(res.d_pip==2)&(res.N==3)]
print(m.drop(columns=['d_pip','N']).to_string(index=False))
print('\n== 主指標 d=2 N=3 ==')
for name in ['2015-2020','2021-2026H1','通し']:
    g=m[m.period==name]
    print(name,'差>0:',int((g.hunt_diff>0).sum()),'/9  z>2:',int((g.z_hunt>2).sum()),' z<-2:',int((g.z_hunt<-2).sum()),
          '| 到達 z>2:',int((g.z_reach>2).sum()),' z<-2:',int((g.z_reach<-2).sum()))
print('\n== 感度（通し）: 差>0 の数 / z>2 / z<-2 ==')
g=res[res.period=='通し']
print(g.groupby(['d_pip','N']).apply(lambda x: f"{int((x.hunt_diff>0).sum())}/9  {int((x.z_hunt>2).sum())}  {int((x.z_hunt<-2).sum())}").to_string())
