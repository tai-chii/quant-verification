# -*- coding: utf-8 -*-
"""キャリー方向（高金利通貨を買う）を方向シグナルにして、複数ペアで器に載せる。

重要な前提:
- 朝入り・夜決済ではロールオーバーをまたがないので **スワップは付かない**。
  ここで測っているのは「金利差が日中のドリフト方向を示すか」であって、キャリー収益ではない。
- 比較のため、同じ方向で持ちっぱなしにした場合（buy&hold）も併記する。
  日計りがキャリーを捨てているなら、その差に出る。

政策金利は概算のステップ関数（下記 RATES）。**符号だけが効く設計**にしてある。
ブラケット = 0.5 × ATR20（先読み防止のため shift(1)）。決定的。
"""
import os, glob
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/vault/40_市場/FX/システムトレード")
ENTRY_JST, EXIT_JST = 9, 23
COST_PCT = 0.002 / 100        # 往復コスト（価格比）
ATR_K = 0.5

# 政策金利の概算（%）。(発効日, 水準) のステップ。出典: 各中銀の公表値をもとにした概算。
# 2025〜2026は不確実性が高い。**符号（どちらが高いか）だけを使う**方針。
RATES = {
 "USD": [("2021-01-01",0.25),("2022-03-17",0.50),("2022-05-05",1.00),("2022-06-16",1.75),
         ("2022-07-28",2.50),("2022-09-22",3.25),("2022-11-03",4.00),("2022-12-15",4.50),
         ("2023-02-02",4.75),("2023-03-23",5.00),("2023-05-04",5.25),("2023-07-27",5.50),
         ("2024-09-19",5.00),("2024-11-08",4.75),("2024-12-19",4.50),("2025-06-01",4.00),
         ("2026-01-01",4.25)],
 "JPY": [("2021-01-01",-0.10),("2024-03-19",0.00),("2024-07-31",0.25),("2025-01-24",0.50),
         ("2026-01-01",0.75)],
 "EUR": [("2021-01-01",-0.50),("2022-07-27",0.00),("2022-09-14",0.75),("2022-11-02",1.50),
         ("2022-12-21",2.00),("2023-02-08",2.50),("2023-03-22",3.00),("2023-05-10",3.25),
         ("2023-06-21",3.50),("2023-08-02",3.75),("2023-09-20",4.00),("2024-06-12",3.75),
         ("2024-09-18",3.50),("2024-10-23",3.25),("2024-12-18",3.00),("2025-06-01",2.00)],
 "GBP": [("2021-01-01",0.10),("2021-12-16",0.25),("2022-02-03",0.50),("2022-03-17",0.75),
         ("2022-05-05",1.00),("2022-06-16",1.25),("2022-08-04",1.75),("2022-09-22",2.25),
         ("2022-11-03",3.00),("2022-12-15",3.50),("2023-02-02",4.00),("2023-03-23",4.25),
         ("2023-05-11",4.50),("2023-06-22",5.00),("2023-08-03",5.25),("2024-08-01",5.00),
         ("2024-11-07",4.75),("2025-06-01",4.00),("2026-01-01",3.75)],
 "AUD": [("2021-01-01",0.10),("2022-05-03",0.35),("2022-08-02",1.85),("2022-11-01",2.85),
         ("2023-02-07",3.35),("2023-06-06",4.10),("2023-11-07",4.35),("2025-02-18",4.10),
         ("2025-08-01",3.60),("2026-01-01",3.35)],
 "CAD": [("2021-01-01",0.25),("2022-03-02",0.50),("2022-06-01",1.50),("2022-09-07",3.25),
         ("2022-12-07",4.25),("2023-07-12",5.00),("2024-06-05",4.75),("2024-12-11",3.25),
         ("2025-03-12",2.75),("2026-01-01",2.50)],
 "CHF": [("2021-01-01",-0.75),("2022-09-22",0.50),("2022-12-15",1.00),("2023-03-23",1.50),
         ("2023-06-22",1.75),("2024-03-21",1.50),("2024-09-26",1.00),("2024-12-12",0.50),
         ("2025-06-19",0.00)],
}
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]


def rate_series(cur, idx):
    s = pd.Series(np.nan, index=idx, dtype=float)
    for d, v in RATES[cur]:
        s.loc[s.index >= pd.Timestamp(d)] = v
    return s.ffill()


def load(pair):
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df["day"] = df["jst"].dt.normalize()
    return df


def atr20(df):
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d["c"].shift(1)
    tr = pd.concat([d.h-d.l,(d.h-pc).abs(),(d.l-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(20).mean().shift(1)


def run(pair):
    df = load(pair)
    if df is None: return None
    base, quote = pair[:3], pair[3:]
    a = atr20(df)
    days = sorted(df["day"].unique())
    rb = rate_series(base, pd.DatetimeIndex(days))
    rq = rate_series(quote, pd.DatetimeIndex(days))
    rows=[]
    for day, g in df.groupby("day", sort=True):
        g = g[(g.jst.dt.hour>=ENTRY_JST)&(g.jst.dt.hour<EXIT_JST)]
        if len(g)<6 or g.iloc[0].jst.hour!=ENTRY_JST: continue
        W = a.get(day, np.nan)*ATR_K
        if not np.isfinite(W) or W<=0: continue
        diff = rb.get(day,np.nan)-rq.get(day,np.nan)
        if not np.isfinite(diff) or diff==0: continue
        s = 1 if diff>0 else -1              # 高金利通貨を買う
        entry=float(g.iloc[0].open); lastc=float(g.iloc[-1].close)
        hi,lo=g.high.values,g.low.values
        tp,sl = entry+s*W, entry-s*W
        out,why,amb=None,"time",False
        for i in range(len(hi)):
            htp = hi[i]>=tp if s>0 else lo[i]<=tp
            hsl = lo[i]<=sl if s>0 else hi[i]>=sl
            if htp and hsl: out,why,amb=-W,"sl",True; break
            if hsl: out,why=-W,"sl"; break
            if htp: out,why=+W,"tp"; break
        if out is None: out = s*(lastc-entry)
        r_pct = out/entry*100 - COST_PCT*100
        bh_pct = s*(lastc-entry)/entry*100 - COST_PCT*100   # 同方向・ブラケット無し
        rows.append({"day":day,"diff":diff,"dir":s,"R":r_pct,"BH":bh_pct,"why":why,
                     "amb":amb,"W_pct":W/entry*100})
    return pd.DataFrame(rows)


if __name__=="__main__":
    print("## キャリー方向（高金利通貨を買う）× 8ペア\n")
    print(f"9:00→23:00 JST / ブラケット={ATR_K}×ATR20 / 往復コスト{COST_PCT*100:.3f}% / H1足\n")
    print("| ペア | n | 方向 | 平均(%/日) | 年率換算 | 勝率 | 持ちっぱなし | 同足曖昧 | 幅(%) |")
    print("|---|---|---|---|---|---|---|---|---|")
    store={}
    for p in PAIRS:
        t=run(p)
        if t is None or len(t)==0: print(f"| {p} | データなし |"); continue
        store[p]=t
        d = "買い" if t.dir.iloc[-1]>0 else "売り"
        flip = (t.dir.diff().fillna(0)!=0).sum()-0
        dtxt = f"{d}" + (f"(符号反転{flip}回)" if flip>0 else "(固定)")
        print(f'| {p} | {len(t)} | {dtxt} | {t.R.mean():+.4f} | {t.R.mean()*250:+.2f}% | '
              f'{(t.R>0).mean()*100:.1f}% | {t.BH.mean()*250:+.2f}% | {t.amb.mean()*100:.1f}% | {t.W_pct.mean():.2f} |')
    print("\n## 前半 / 後半（アウトオブサンプル）平均(%/日)\n")
    print("| ペア | 前半 | 後半 | 判定 |")
    print("|---|---|---|---|")
    for p,t in store.items():
        h=len(t)//2; f1,f2=t.R.iloc[:h].mean(),t.R.iloc[h:].mean()
        v = "維持" if (f1>0 and f2>0 and f2>f1*0.5) else ("反転" if f1*f2<0 else "減衰/元々マイナス")
        print(f"| {p} | {f1:+.4f} | {f2:+.4f} | {v} |")
    print("\n## 年別 平均(%/日)\n")
    yrs=sorted({d.year for t in store.values() for d in t.day})
    print("| ペア | "+" | ".join(str(y) for y in yrs)+" |")
    print("|"+"---|"*(len(yrs)+1))
    for p,t in store.items():
        t=t.copy(); t["y"]=t.day.dt.year
        cells=[f"{t[t.y==y].R.mean():+.3f}" if (t.y==y).any() else "-" for y in yrs]
        print(f"| {p} | "+" | ".join(cells)+" |")
    print("\n## 全ペア合算（等ウェイト・1日8トレード相当）\n")
    allR=pd.concat([t.R for t in store.values()])
    n=len(allR); m=allR.mean(); sd=allR.std(); se=sd/np.sqrt(n)
    print(f"n={n}  平均{m:+.4f}%/日  標準偏差{sd:.4f}  標準誤差{se:.4f}  t={m/se:+.2f}")
    print(f"勝率 {(allR>0).mean()*100:.1f}%")
    allBH=pd.concat([t.BH for t in store.values()])
    print(f"持ちっぱなし版: 平均{allBH.mean():+.4f}%/日  t={allBH.mean()/(allBH.std()/np.sqrt(len(allBH))):+.2f}")
