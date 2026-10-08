# -*- coding: utf-8 -*-
"""持ちっぱなし＋1銘柄1ポジション制。

ルール:
- 定時(既定9:00 JST)にポジションを取る。ただし **そのペアで建玉があるなら何もしない**
- 決済は TP/SL に触れたときのみ。**時間切れなし**
- 決済した次の定時から、また入れるようになる

24時間ロール版との違い:
- 強制的に毎日建て替えないので、スプレッドを毎日払わない
- 建玉が続く限りスワップが積み上がる（キャリーには有利）
- 対称ブラケットなので価格部分の期待値はほぼゼロ。**スワップだけが残る構造**
- 代わりに、含み損のポジションが次のエントリーを塞ぐ（機会損失）

評価は日次マークトゥマーケット（建玉期間中の値洗い＋スワップ）で行い、
24時間ロール版とSharpe/DDを直接比較できるようにする。決定的。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9
MARKUP = 0.7
COST_PCT = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]

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


def rate_steps(cur, idx):
    s = pd.Series(np.nan, index=idx, dtype=float)
    for d, v in RATES[cur]:
        s.loc[s.index >= pd.Timestamp(d)] = v
    return s.ffill()


def prep(pair):
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df["day"] = df["jst"].dt.normalize()
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d.c.shift(1)
    tr = pd.concat([d.h-d.l,(d.h-pc).abs(),(d.l-pc).abs()],axis=1).max(axis=1)
    df["atr"] = df["day"].map(tr.rolling(20).mean().shift(1))
    days = pd.DatetimeIndex(sorted(df["day"].unique()))
    rb = rate_steps(pair[:3], days); rq = rate_steps(pair[3:], days)
    df["diff"] = df["day"].map(rb - rq)
    return df


def simulate(pair, k, entry_h=ENTRY_JST, markup=MARKUP):
    df = prep(pair)
    if df is None: return None, None
    jst = df.jst.values; hh = df.jst.dt.hour.values; day = df.day.values
    op, hi, lo, cl = df.open.values, df.high.values, df.low.values, df.close.values
    atr, dif = df.atr.values, df["diff"].values

    pnl = {}            # day -> 収益率(%)
    trades = []
    pos = 0; entry = tp = sl = np.nan; ent_i = 0; prev = np.nan
    for i in range(len(df)):
        d = day[i]
        if pos == 0:
            if hh[i] == entry_h and np.isfinite(atr[i]) and np.isfinite(dif[i]) and dif[i] != 0:
                pos = 1 if dif[i] > 0 else -1
                entry = op[i]; W = atr[i]*k
                tp, sl = entry + pos*W, entry - pos*W
                ent_i = i; prev = entry
                pnl[d] = pnl.get(d, 0.0) - COST_PCT*100          # 建てるとき1回だけコスト
            continue
        # 建玉あり: 値洗い
        htp = hi[i] >= tp if pos > 0 else lo[i] <= tp
        hsl = lo[i] <= sl if pos > 0 else hi[i] >= sl
        px = cl[i]; closed = False
        if hsl:  px = sl; closed = True                           # 同足両触れはSL優先（保守的）
        elif htp: px = tp; closed = True
        pnl[d] = pnl.get(d, 0.0) + pos*(px-prev)/entry*100
        # スワップ（1時間ぶん）
        pnl[d] = pnl.get(d, 0.0) + max(0.0, abs(dif[i])-markup)/365/24
        prev = px
        if closed:
            hold_h = (jst[i]-jst[ent_i]) / np.timedelta64(1,'h')
            trades.append({"entry_day": day[ent_i], "exit_day": d, "hold_days": hold_h/24,
                           "why": "sl" if hsl else "tp", "dir": pos})
            pos = 0
    s = pd.Series(pnl).sort_index()
    s.index = pd.DatetimeIndex(s.index)
    return s, pd.DataFrame(trades)


def stats(r_pct):
    r = r_pct/100
    eq = (1+r).cumprod(); n = len(r)
    ann = (eq.iloc[-1]**(250/n)-1)*100
    vol = r.std()*np.sqrt(250)*100
    return {"n":n, "ann":ann, "vol":vol, "sharpe":ann/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100, "worst":r.min()*100, "skew":r.skew()}


if __name__ == "__main__":
    for k in (0.5, 1.0, 2.0, 3.0):
        print(f"\n## ブラケット {k}×ATR20（持ちっぱなし・1銘柄1ポジション）\n")
        print("| ペア | 取引回数 | 平均保有 | 最長保有 | TP率 | 建玉率 | 年率 | Sharpe | 最大DD | 最悪日 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        cols = []
        for p in PAIRS:
            s, tr = simulate(p, k)
            if s is None or len(s) < 200: continue
            st = stats(s); cols.append(s.rename(p))
            expo = tr.hold_days.sum()/ (len(s)) *100 if len(tr) else 0
            print(f'| {p} | {len(tr)} | {tr.hold_days.mean():.1f}日 | {tr.hold_days.max():.0f}日 | '
                  f'{(tr.why=="tp").mean()*100:.0f}% | {min(expo,100):.0f}% | {st["ann"]:+.2f}% | '
                  f'{st["sharpe"]:+.2f} | {st["mdd"]:.1f}% | {st["worst"]:.2f}% |')
        pf = pd.concat(cols, axis=1).fillna(0).mean(axis=1)
        st = stats(pf); h = len(pf)//2
        print(f'\n**8ペア分散: 年率 {st["ann"]:+.2f}% / ボラ {st["vol"]:.1f}% / Sharpe {st["sharpe"]:+.2f} / '
              f'最大DD {st["mdd"]:.1f}% / 歪度 {st["skew"]:+.2f}**')
        print(f'前半 年率{stats(pf.iloc[:h])["ann"]:+.2f}%  後半 年率{stats(pf.iloc[h:])["ann"]:+.2f}%')
        y = (1+pf/100).groupby(pf.index.year).prod()-1
        print("年次: " + "  ".join(f"{a}:{b*100:+.2f}%" for a,b in y.items()))
        pf.to_csv(f"output/holduntilhit_k{k}.csv")
