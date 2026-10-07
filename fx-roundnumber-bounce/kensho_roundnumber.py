"""キリ番（00・50）での反転と、抜けた後の継続（Osler 2003 の移植）  2026-10-01
事前に固定した仮説と判定（アイデア候補 2026-10-01 の行）:
  キリ番（下2桁00・50）では、対照の水準（25・75）より
   (1) 反転率が高い: 前の足の終値が水準の手前 → この足の高値/安値が水準に届いた → 終値は水準の手前に戻った割合
   (2) 抜けた後の継続が大きい: 終値で水準を抜けた足の終値から、次の4本（4時間）の抜けた向きへの平均リターン
  判定期間: 2015-2020 / 2021-2026H1。棄却条件: キリ番−対照の差が両期間で通貨ペアの過半で同じ符号にならない、または0と区別できない。
水準の間隔: ドル円・クロス円は0.50円、その他は0.0050（キリ番=間隔の整数倍、対照=整数倍+間隔/2）。
先読みなし（使うのは t-1 の終値と t の高値・安値・終値、継続は t+1..t+4）。決定的。
"""
import numpy as np, pandas as pd
PAIRS=['EURUSD','GBPUSD','USDJPY','USDCHF','AUDUSD','USDCAD','EURJPY','GBPJPY']
PERIODS=[('2008-2014','2008-01-01','2015-01-01'),('2015-2020','2015-01-01','2021-01-01'),('2021-2026H1','2021-01-01','2026-07-01')]
H=4
def load(p):
    df=pd.read_csv(f'data_{p}_H1_dukascopy.csv',header=0,names=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t,format='%Y-%m-%d %H:%M:%S'); df=df[df.v>0].sort_values('t').reset_index(drop=True)
    return df
def events(df,step,offset):
    t=df.t.values; h=df.h.values; l=df.l.values; c=df.c.values
    one=np.timedelta64(1,'h')
    res=[]  # (dir, rejected, cont_ret or nan)
    for i in range(1,len(df)-H):
        if t[i]-t[i-1]!=one: continue
        pc=c[i-1]
        up=np.floor((pc-offset)/step)*step+offset+step   # 上の最も近い水準
        dn=np.ceil((pc-offset)/step)*step+offset-step    # 下の最も近い水準
        if abs(up-pc)<1e-12: up+=step
        if abs(pc-dn)<1e-12: dn-=step
        hit_up=h[i]>=up; hit_dn=l[i]<=dn
        if hit_up==hit_dn: continue   # 届かない or 両方（大きな足）は除外
        ok_next=(t[i+H]-t[i])==H*one
        if hit_up:
            rej=c[i]<up; cont=(np.log(c[i+H]/c[i]) if (not rej and ok_next) else np.nan)
            res.append((1,rej,cont))
        else:
            rej=c[i]>dn; cont=(-np.log(c[i+H]/c[i]) if (not rej and ok_next) else np.nan)
            res.append((-1,rej,cont))
    return pd.DataFrame(res,columns=['dir','rej','cont'])
rows=[]
for p in PAIRS:
    df=load(p); step=0.5 if p.endswith('JPY') else 0.005
    for name,a,b in PERIODS:
        d=df[(df.t>=a)&(df.t<b)].reset_index(drop=True)
        R=events(d,step,0.0); C=events(d,step,step/2)
        # 反転率の差（2標本の比率）
        pr,pc_=R.rej.mean(),C.rej.mean(); nr,nc=len(R),len(C)
        se=np.sqrt(pr*(1-pr)/nr+pc_*(1-pc_)/nc); zr=(pr-pc_)/se
        # 継続の差（平均の差、bp）
        cr,cc=R.cont.dropna(),C.cont.dropna()
        dm=(cr.mean()-cc.mean())*1e4; sem=np.sqrt(cr.var()/len(cr)+cc.var()/len(cc))*1e4; zc=dm/sem
        rows.append([p,name,nr,nc,round(pr,4),round(pc_,4),round(pr-pc_,4),round(zr,2),len(cr),len(cc),round(cr.mean()*1e4,2),round(cc.mean()*1e4,2),round(dm,2),round(zc,2)])
res=pd.DataFrame(rows,columns=['pair','period','n_round','n_ctrl','rej_round','rej_ctrl','rej_diff','z_rej','n_cont_round','n_cont_ctrl','cont_round_bp','cont_ctrl_bp','cont_diff_bp','z_cont'])
res.to_csv('output/kensho_roundnumber.csv',index=False)
pd.set_option('display.width',220); pd.set_option('display.max_columns',20)
print(res[['pair','period','n_round','rej_round','rej_ctrl','rej_diff','z_rej','cont_round_bp','cont_ctrl_bp','cont_diff_bp','z_cont']].to_string(index=False))
for name in ['2015-2020','2021-2026H1']:
    g=res[res.period==name]
    print(name,'反転差>0:',int((g.rej_diff>0).sum()),'/8  z>2:',int((g.z_rej>2).sum()),'  z<-2:',int((g.z_rej<-2).sum()),
          '| 継続差>0:',int((g.cont_diff_bp>0).sum()),'/8  z>2:',int((g.z_cont>2).sum()),'  z<-2:',int((g.z_cont<-2).sum()))
