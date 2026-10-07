"""15分足のヒゲの狩り: キリ番のすぐ外を刺して、15分以内に戻すか（Q018 の続き・引き継ぎメモ「分足でのヒゲの狩り」）  2026-10-04
=== 事前に固定した計画（M15 で数える前に書いた。H1 の Q018 の結果＝狩られ率の差なし・到達率はキリ番が高い、は既知） ===
問い  : H1 で見えなかった「足の中の数分〜15分で刺して戻す」動きが、15分足ならキリ番に多く見えるか。
データ: USDJPY・EURUSD の M15（Dukascopy、2021-01〜2026-07-14）。volume>0 の足。data_quality_audit.py で異常なしを確認済み。
水準  : キリ番＝円0.50・ユーロ0.0050 の倍数（00・50）。対照＝その中間（25・75）。定義は kensho_stophunt.py と同じ。
事象（下側。上側は鏡写し）: 前の足の終値 pc のすぐ下の水準 L に、この足の安値が届いた＝接近（上下両方に届いた足は除外、
        前の足と連続でない足は除外）。損切り S = L − d。刺さり: 安値 ≤ S。
主指標: 「同じ15分足のうちに刺さって、終値が L の内側に戻った」割合（刺さった事象のうち）＝足の中の狩られ率。d=2pip。
        キリ番 − 対照 の差と z（2標本の比率の差）。
副指標: 接近のうち「刺さって同じ足で戻った」割合（接近あたりのヒゲ狩り率）。到達率（接近のうち刺さった割合）。
感度  : d ∈ {1,2,3,5}pip × 戻りの猶予 N ∈ {1本(15分), 2本(30分), 4本(1時間)}。参考扱い。
期間  : 通し 2021-01〜2026-06 ／ 前半 2021–2023 ／ 後半 2024–2026H1。
判定（主指標・d=2・N=1）:
  支持 ＝ 通しで2ペアとも 差>0 かつ z>2、かつ前半・後半とも2ペアで 差>0。
  棄却 ＝ 上を満たさない。逆向き（差<0 かつ z<−2）は別に記録する。
多重比較: 主指標1本（2ペア）で判定。感度 4d×3N×2ペア×3期間は参考。
これは損益ではなく、損切りの刺さり方の頻度。先読みなし（t−1 の終値と t..t+N−1 だけ）。決定的。
"""
import numpy as np, pandas as pd
INST={'USDJPY':(0.5,0.01),'EURUSD':(0.005,0.0001)}
PERIODS=[('通し','2021-01-01','2026-07-01'),('前半2021-23','2021-01-01','2024-01-01'),('後半2024-26H1','2024-01-01','2026-07-01')]
DS=[1,2,3,5]; NS=[1,2,4]
def load(p):
    df=pd.read_csv(f'data_{p}_M15_dukascopy.csv',header=0,names=['t','o','h','l','c','v'])
    df['t']=pd.to_datetime(df.t,format='%Y-%m-%d %H:%M:%S'); return df[df.v>0].sort_values('t').reset_index(drop=True)
def events(df,step,offset,pip):
    t=df.t.values; h=df.h.values; l=df.l.values; c=df.c.values; one=np.timedelta64(15,'m'); n=len(df); Nmax=max(NS); out=[]
    for i in range(1,n-Nmax):
        if t[i]-t[i-1]!=one: continue
        pc=c[i-1]
        up=np.floor((pc-offset)/step)*step+offset+step; dn=np.ceil((pc-offset)/step)*step+offset-step
        if abs(up-pc)<1e-9: up+=step
        if abs(pc-dn)<1e-9: dn-=step
        tu=h[i]>=up; td=l[i]<=dn
        if tu==td: continue
        cont=[(t[i+k]-t[i])==k*one for k in range(Nmax)]
        rec={'t':t[i]}
        for d in DS:
            hit=(l[i]<=dn-d*pip) if td else (h[i]>=up+d*pip); rec[f'hit{d}']=float(hit)
            for N in NS:
                if (not hit) or (not all(cont[:N])): rec[f'hunt{d}_{N}']=np.nan; rec[f'wick{d}_{N}']=np.nan if not all(cont[:N]) else 0.0; continue
                cs=c[i:i+N]; back=float((cs>dn).any() if td else (cs<up).any())
                rec[f'hunt{d}_{N}']=back; rec[f'wick{d}_{N}']=back
        out.append(rec)
    return pd.DataFrame(out)
def zt(a,b):
    a=a.dropna(); b=b.dropna(); pa,pb=a.mean(),b.mean(); se=np.sqrt(pa*(1-pa)/len(a)+pb*(1-pb)/len(b))
    return len(a),len(b),pa,pb,pa-pb,(pa-pb)/se
rows=[]
for p,(step,pip) in INST.items():
    df=load(p); R0=events(df,step,0.0,pip); C0=events(df,step,step/2,pip)
    for name,a,b in PERIODS:
        R=R0[(R0.t>=a)&(R0.t<b)]; C=C0[(C0.t>=a)&(C0.t<b)]
        for d in DS:
            rc=zt(R[f'hit{d}'],C[f'hit{d}'])
            for N in NS:
                hn=zt(R[f'hunt{d}_{N}'],C[f'hunt{d}_{N}']); wk=zt(R[f'wick{d}_{N}'],C[f'wick{d}_{N}'])
                rows.append(dict(inst=p,period=name,d_pip=d,N=N,接近_キリ=len(R),接近_対照=len(C),到達_キリ=rc[2],到達_対照=rc[3],z到達=rc[5],
                    刺さり_キリ=hn[0],刺さり_対照=hn[1],狩られ_キリ=hn[2],狩られ_対照=hn[3],狩られ差=hn[4],z狩られ=hn[5],
                    ヒゲ狩り_キリ=wk[2],ヒゲ狩り_対照=wk[3],zヒゲ狩り=wk[5]))
res=pd.DataFrame(rows); res.to_csv('output/kensho_stophunt_m15.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
m=res[(res.d_pip==2)&(res.N==1)]
print(m.drop(columns=['d_pip','N']).round(4).to_string(index=False))
full=m[m.period=='通し']; sub=m[m.period!='通し']
ok=((full.狩られ差>0)&(full.z狩られ>2)).all() and (sub.狩られ差>0).all()
rev=((full.狩られ差<0)&(full.z狩られ<-2)).sum()
print(f"\n判定（d=2pip・N=1本）: {'支持' if ok else '棄却'}   逆向き(z<-2)の数（通し）: {rev}/2")
print('\n感度（通し）: 狩られ差 と z')
g=res[res.period=='通し']
print(g.pivot_table(index=['d_pip','N'],columns='inst',values=['狩られ差','z狩られ']).round(3).to_string())
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in fm.findSystemFonts():
    if 'NotoSansCJK' in f or 'Hiragino' in f or 'NotoSansJP' in f: fm.fontManager.addfont(f)
plt.rcParams['font.family']=[x.name for x in fm.fontManager.ttflist if 'CJK' in x.name or 'Hiragino' in x.name or 'Noto Sans JP' in x.name][:1] or ['sans-serif']
fig,ax=plt.subplots(1,2,figsize=(12,4.5))
for k,p in enumerate(INST):
    s=g[(g.inst==p)&(g.N==1)]
    ax[k].plot(s.d_pip,s.狩られ_キリ,'o-',label='キリ番(00・50)'); ax[k].plot(s.d_pip,s.狩られ_対照,'s--',label='対照(25・75)')
    ax[k].set_title(f'{p} M15 2021–2026H1: 刺さった後、同じ足で内側へ戻る割合'); ax[k].set_xlabel('損切りの距離 d (pip)'); ax[k].legend()
plt.tight_layout(); plt.savefig('output/kensho_stophunt_m15.png',dpi=120); print('saved')
