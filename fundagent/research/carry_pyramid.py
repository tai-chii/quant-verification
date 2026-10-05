# -*- coding: utf-8 -*-
"""定時ごとに建玉を「追加してよい」ルール（積み増し／ピラミッディング）。

前提の違い:
- [[持ちっぱなし1銘柄1ポジション]] … 建玉があれば新規を取らない
- 本スクリプト                     … 定時が来たら建玉の有無に関係なく1単位追加する

各ポジションは自分のTP/SL（建てた時点のATR基準）を持ち、独立に決済される。
同時建玉数＝実質レバレッジになるので、その分布を必ず出す。
決定的・先読みなし。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/vault/40_市場/FX/システムトレード")
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
    df["diff"] = df["day"].map(rate_steps(pair[:3], days) - rate_steps(pair[3:], days))
    return df


def simulate(pair, k, cap=None, entry_h=ENTRY_JST, markup=MARKUP):
    """cap: 同時建玉数の上限。Noneなら無制限。"""
    df = prep(pair)
    if df is None: return None, None, None
    hh = df.jst.dt.hour.values; day = df.day.values
    op, hi, lo, cl = df.open.values, df.high.values, df.low.values, df.close.values
    atr, dif = df.atr.values, df["diff"].values

    pnl = {}; nopen = {}; closed = []
    book = []          # [dir, entry, tp, sl, prev]
    for i in range(len(df)):
        d = day[i]
        # --- 既存建玉の値洗い＆決済判定 ---
        still = []
        tot = 0.0
        for pos, entry, tp, sl, prev in book:
            htp = hi[i] >= tp if pos > 0 else lo[i] <= tp
            hsl = lo[i] <= sl if pos > 0 else hi[i] >= sl
            px = cl[i]; done = False
            if hsl:  px = sl; done = True        # 同足両触れはSL優先（保守的）
            elif htp: px = tp; done = True
            tot += pos*(px-prev)/entry*100
            tot += max(0.0, abs(dif[i])-markup)/365/24     # スワップ1時間ぶん
            if done: closed.append({"day": d, "why": "sl" if hsl else "tp"})
            else:    still.append([pos, entry, tp, sl, px])
        book = still
        if tot: pnl[d] = pnl.get(d, 0.0) + tot
        # --- 定時なら1単位追加 ---
        if hh[i] == entry_h and np.isfinite(atr[i]) and np.isfinite(dif[i]) and dif[i] != 0:
            if cap is None or len(book) < cap:
                pos = 1 if dif[i] > 0 else -1
                W = atr[i]*k
                book.append([pos, op[i], op[i]+pos*W, op[i]-pos*W, op[i]])
                pnl[d] = pnl.get(d, 0.0) - COST_PCT*100
        nopen[d] = max(nopen.get(d, 0), len(book))
    s = pd.Series(pnl).sort_index(); s.index = pd.DatetimeIndex(s.index)
    no = pd.Series(nopen).sort_index(); no.index = pd.DatetimeIndex(no.index)
    return s, no, pd.DataFrame(closed)


def stats(r_pct):
    r = r_pct/100
    eq = (1+r).cumprod(); n = len(r)
    ann = (eq.iloc[-1]**(250/n)-1)*100 if eq.iloc[-1] > 0 else float("nan")
    vol = r.std()*np.sqrt(250)*100
    return {"n":n,"ann":ann,"vol":vol,"sharpe":ann/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100,"worst":r.min()*100,"skew":r.skew()}


if __name__ == "__main__":
    for k in (0.5, 1.0, 2.0, 3.0):
        print(f"\n## ブラケット {k}×ATR20 ／ 定時ごとに1単位追加（上限なし）\n")
        print("| ペア | 同時建玉 平均 | 最大 | 年率 | ボラ | Sharpe | 最大DD | 最悪日 | 歪度 |")
        print("|---|---|---|---|---|---|---|---|---|")
        cols = []; mx = 0
        for p in PAIRS:
            s, no, tr = simulate(p, k)
            if s is None or len(s) < 200: continue
            st = stats(s); cols.append(s.rename(p)); mx = max(mx, no.max())
            print(f'| {p} | {no.mean():.1f} | **{no.max()}** | {st["ann"]:+.2f}% | {st["vol"]:.1f}% | '
                  f'{st["sharpe"]:+.2f} | {st["mdd"]:.1f}% | {st["worst"]:.2f}% | {st["skew"]:+.2f} |')
        pf = pd.concat(cols, axis=1).fillna(0).mean(axis=1)
        st = stats(pf); h = len(pf)//2
        print(f'\n**8ペア分散: 年率 {st["ann"]:+.2f}% / ボラ {st["vol"]:.1f}% / Sharpe {st["sharpe"]:+.2f} / '
              f'最大DD {st["mdd"]:.1f}% / 最悪日 {st["worst"]:.2f}% / 歪度 {st["skew"]:+.2f}**')
        print(f'前半 年率{stats(pf.iloc[:h])["ann"]:+.2f}%  後半 年率{stats(pf.iloc[h:])["ann"]:+.2f}%')
        y = (1+pf/100).groupby(pf.index.year).prod()-1
        print("年次: " + "  ".join(f"{a}:{b*100:+.2f}%" for a,b in y.items()))
