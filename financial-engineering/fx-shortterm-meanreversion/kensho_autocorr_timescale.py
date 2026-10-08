"""時間軸ごとの1次自己相関（Neely & Weller 2003 の追試）  2026-10-01
仮説（事前に固定）: 為替の1時間足リターンの1次自己相関は負（平均回帰）、週次は正（トレンド）。
判定は 2015年以降。決定的（乱数なし）。データ: Dukascopy H1（検証/学問/金融工学/作業/FX/システムトレード/data_*_H1_dukascopy.csv）。
欠損補完の足（出来高0）と、1時間ちょうどでない間隔のリターンは除く。t値は不均一分散に頑健な形（sum r_t r_{t-1} / sqrt(sum r_t^2 r_{t-1}^2)）。
"""
import numpy as np, pandas as pd, os
PAIRS=['EURUSD','GBPUSD','USDJPY','USDCHF','AUDUSD','USDCAD','EURJPY','GBPJPY']
PERIODS=[('2008-2014','2008-01-01','2015-01-01'),('2015-2020','2015-01-01','2021-01-01'),('2021-2026H1','2021-01-01','2026-07-01')]
def load(p,tf='H1'):
    df=pd.read_csv(f'data_{p}_{tf}_dukascopy.csv',header=0,names=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t,format='%Y-%m-%d %H:%M:%S')
    return df.sort_values('t').reset_index(drop=True)
def lag1(r):
    r=r-r.mean(); x,y=r[1:],r[:-1]
    rho=float(np.sum(x*y)/np.sum(r*r)); t=float(np.sum(x*y)/np.sqrt(np.sum((x*y)**2)))
    return rho,t,len(r)
def intraday_returns(df,step,hours=None):
    df=df[df.v>0].copy()
    r=np.log(df.c).diff(); dt=df.t.diff()
    ok=(dt==pd.Timedelta(step))
    out=pd.DataFrame({'t':df.t,'r':r,'ok':ok})
    if hours: 
        h=out.t.dt.hour; out=out[(h>=hours[0])&(h<hours[1])]
        out['ok']=out.ok&(out.t.diff()==pd.Timedelta(step))
    return out
def series_lag1(out):
    # 連続した区間内のペアだけを使う
    r=out.r.values; ok=out.ok.values
    pair_ok=ok[1:]&ok[:-1]
    x=r[1:][pair_ok]; y=r[:-1][pair_ok]
    m=np.nanmean(r[ok]); x=x-m; y=y-m
    rho=float(np.sum(x*y)/np.sqrt(np.sum(x*x)*np.sum(y*y))); t=float(np.sum(x*y)/np.sqrt(np.sum((x*y)**2)))
    return rho,t,int(pair_ok.sum())
rows=[]
for p in PAIRS:
    df=load(p)
    wk=df[df.v>0].set_index('t').c.resample('W-FRI').last().dropna()
    for name,a,b in PERIODS:
        d=df[(df.t>=a)&(df.t<b)]
        if len(d)<1000: continue
        for lab,hrs in [('H1_全時間',None),('H1_07-20UTC',(7,20))]:
            rho,t,n=series_lag1(intraday_returns(d,'1h',hrs)); rows.append([p,name,lab,rho,t,n])
        w=wk[(wk.index>=a)&(wk.index<b)]; rw=np.log(w).diff().dropna().values
        rho,t,n=lag1(rw); rows.append([p,name,'週次',rho,t,n])
for p in ['USDJPY','EURUSD']:
    d=load(p,'M15'); d=d[d.t<'2026-07-01']
    rho,t,n=series_lag1(intraday_returns(d,'15min')); rows.append([p,'2021-2026H1','M15_全時間',rho,t,n])
res=pd.DataFrame(rows,columns=['pair','period','tf','rho1','t_robust','n'])
os.makedirs('output',exist_ok=True); res.to_csv('output/kensho_autocorr_timescale.csv',index=False)
pd.set_option('display.width',200)
print(res.pivot_table(index=['tf','pair'],columns='period',values='rho1').round(3))
print(res.pivot_table(index=['tf','pair'],columns='period',values='t_robust').round(1))
# 符号の集計（2015年以降）
post=res[res.period.isin(['2015-2020','2021-2026H1'])]
for tf,g in post.groupby('tf'):
    print(tf,'負の数',int((g.rho1<0).sum()),'/',len(g),' t<-2 の数',int((g.t_robust<-2).sum()),' t>2 の数',int((g.t_robust>2).sum()))
