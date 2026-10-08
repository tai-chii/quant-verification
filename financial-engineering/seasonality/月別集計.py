# 週次終値_6銘柄.csv から月別騰落率（素の値・日経平均との差・前半後半）を集計する
import statistics as st, math
T={'6367':'ダイキン','2502':'アサヒ','2503':'キリン','5909':'コロナ','5951':'ダイニチ','N225':'日経平均'}
import csv
_rows=list(csv.DictReader(open('週次終値_6銘柄.csv',encoding='utf-8')))
def load(k):
    me={}
    for r in _rows:
        if r['コード']!=k: continue
        y,m,_=r['日付'].split('-'); me[(int(y),int(m))]=float(r['調整後終値'])
    ks=sorted(me); return {ks[i]:me[ks[i]]/me[ks[i-1]]-1 for i in range(1,len(ks))}
R={k:load(k) for k in T}
def s(v):
    mu=st.mean(v); sd=st.stdev(v); return mu*100, sum(x>0 for x in v)/len(v)*100, mu/(sd/math.sqrt(len(v)))
print('--- raw mean%/t by month')
for k in T:
    print(T[k].ljust(6), ' '.join(f"{m:>2}:{s([R[k][x] for x in R[k] if x[1]==m])[0]:+5.1f}({s([R[k][x] for x in R[k] if x[1]==m])[2]:+.1f})" for m in range(1,13)))
print('--- excess vs N225')
for k in T:
    if k=='N225':continue
    print(T[k].ljust(6), ' '.join(f"{m:>2}:{s([R[k][x]-R['N225'][x] for x in R[k] if x[1]==m and x in R['N225']])[0]:+5.1f}({s([R[k][x]-R['N225'][x] for x in R[k] if x[1]==m and x in R['N225']])[2]:+.1f})" for m in range(1,13)))
print('--- split halves (excess vs N225), selected')
for k,m in [('6367',11),('6367',5),('6367',2),('2503',3),('5909',4),('5951',5),('5951',9)]:
    for a,b in [(2005,2015),(2016,2026)]:
        v=[R[k][x]-R['N225'][x] for x in R[k] if x[1]==m and a<=x[0]<=b]
        mu,w,t=s(v); print(T[k],m,f'{a}-{b}',f'{mu:+.1f}% win{w:.0f}% t{t:+.2f} n{len(v)}')
# count |t|>=2 in excess
c=0
for k in T:
    if k=='N225':continue
    for m in range(1,13):
        v=[R[k][x]-R['N225'][x] for x in R[k] if x[1]==m and x in R['N225']]
        if abs(s(v)[2])>=2:c+=1
print('excess |t|>=2 count of 60:',c)
