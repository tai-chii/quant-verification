# -*- coding: utf-8 -*-
"""金曜夜に全建玉を閉じるルールの検証。

構成:
  1. 週末ギャップの実測（この施策の効果の上限を決める）
  2. 持ちっぱなし(TP/SLのみ) vs +金曜クローズ の比較
  3. 24時間ロール vs +週末スキップ の比較

方向はキャリー、8ペア、ATR基準のTP/SL、決定的・先読みなし。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; FRI_EXIT_JST = 23; MARKUP = 0.7; COST_PCT = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]

RATES = {
 "USD":[("2021-01-01",0.25),("2022-03-17",0.50),("2022-05-05",1.00),("2022-06-16",1.75),
        ("2022-07-28",2.50),("2022-09-22",3.25),("2022-11-03",4.00),("2022-12-15",4.50),
        ("2023-02-02",4.75),("2023-03-23",5.00),("2023-05-04",5.25),("2023-07-27",5.50),
        ("2024-09-19",5.00),("2024-11-08",4.75),("2024-12-19",4.50),("2025-06-01",4.00),
        ("2026-01-01",4.25)],
 "JPY":[("2021-01-01",-0.10),("2024-03-19",0.00),("2024-07-31",0.25),("2025-01-24",0.50),
        ("2026-01-01",0.75)],
 "EUR":[("2021-01-01",-0.50),("2022-07-27",0.00),("2022-09-14",0.75),("2022-11-02",1.50),
        ("2022-12-21",2.00),("2023-02-08",2.50),("2023-03-22",3.00),("2023-05-10",3.25),
        ("2023-06-21",3.50),("2023-08-02",3.75),("2023-09-20",4.00),("2024-06-12",3.75),
        ("2024-09-18",3.50),("2024-10-23",3.25),("2024-12-18",3.00),("2025-06-01",2.00)],
 "GBP":[("2021-01-01",0.10),("2021-12-16",0.25),("2022-02-03",0.50),("2022-03-17",0.75),
        ("2022-05-05",1.00),("2022-06-16",1.25),("2022-08-04",1.75),("2022-09-22",2.25),
        ("2022-11-03",3.00),("2022-12-15",3.50),("2023-02-02",4.00),("2023-03-23",4.25),
        ("2023-05-11",4.50),("2023-06-22",5.00),("2023-08-03",5.25),("2024-08-01",5.00),
        ("2024-11-07",4.75),("2025-06-01",4.00),("2026-01-01",3.75)],
 "AUD":[("2021-01-01",0.10),("2022-05-03",0.35),("2022-08-02",1.85),("2022-11-01",2.85),
        ("2023-02-07",3.35),("2023-06-06",4.10),("2023-11-07",4.35),("2025-02-18",4.10),
        ("2025-08-01",3.60),("2026-01-01",3.35)],
 "CAD":[("2021-01-01",0.25),("2022-03-02",0.50),("2022-06-01",1.50),("2022-09-07",3.25),
        ("2022-12-07",4.25),("2023-07-12",5.00),("2024-06-05",4.75),("2024-12-11",3.25),
        ("2025-03-12",2.75),("2026-01-01",2.50)],
 "CHF":[("2021-01-01",-0.75),("2022-09-22",0.50),("2022-12-15",1.00),("2023-03-23",1.50),
        ("2023-06-22",1.75),("2024-03-21",1.50),("2024-09-26",1.00),("2024-12-12",0.50),
        ("2025-06-19",0.00)],
}


def rate_steps(cur, idx):
    s = pd.Series(np.nan, index=idx, dtype=float)
    for d, v in RATES[cur]: s.loc[s.index >= pd.Timestamp(d)] = v
    return s.ffill()


_C = {}
def prep(pair):
    if pair in _C: return _C[pair]
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df = df[df.jst >= "2021-01-01"]
    # 【重要】Dukascopy H1 は週末も出来高0のフィラー足で埋まっている（全体の約29%）。
    # 日曜JSTは100%、土曜は74%、月曜早朝は27%がフィラー。これを除かないと
    # 「動いていない日」を1日と数えてしまい、年率換算もボラも過小になる。
    if "volume" in df.columns:
        df = df[df.volume > 0]
    df = df.reset_index(drop=True)
    df["day"] = df["jst"].dt.normalize()
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d.c.shift(1)
    tr = pd.concat([d.h-d.l,(d.h-pc).abs(),(d.l-pc).abs()],axis=1).max(axis=1)
    df["atr"] = df["day"].map(tr.rolling(20).mean().shift(1))
    days = pd.DatetimeIndex(sorted(df["day"].unique()))
    df["diff"] = df["day"].map(rate_steps(pair[:3], days) - rate_steps(pair[3:], days))
    _C[pair] = df
    return df


def weekend_gaps():
    """金曜(または土曜早朝)の最終値 → 月曜最初の始値 のギャップ。キャリー方向で符号調整。"""
    rows = []
    for p in PAIRS:
        df = prep(p)
        if df is None: continue
        df = df.copy()
        df["wk"] = df.jst.dt.isocalendar().week.astype(int)
        df["yr"] = df.jst.dt.isocalendar().year.astype(int)
        for (y, w), g in df.groupby(["yr","wk"]):
            last = g.iloc[-1]
            nxt = df[df.jst > last.jst]
            if len(nxt) == 0: continue
            first = nxt.iloc[0]
            if (first.jst - last.jst) < pd.Timedelta(hours=20): continue   # 週末でない
            if (first.jst - last.jst) > pd.Timedelta(hours=80): continue   # 長期休場は除く
            s = np.sign(last["diff"])
            if s == 0 or not np.isfinite(s): continue
            rows.append({"pair": p, "gap_pct": s*(first.open-last.close)/last.close*100,
                         "hours": (first.jst-last.jst).total_seconds()/3600})
    return pd.DataFrame(rows)


def simulate(pair, k=2.0, fri_close=False):
    df = prep(pair)
    if df is None: return None
    jst = df.jst; hh = jst.dt.hour.values; dow = jst.dt.dayofweek.values; day = df.day.values
    op, hi, lo, cl = df.open.values, df.high.values, df.low.values, df.close.values
    atr, dif = df.atr.values, df["diff"].values
    pnl = {}; nheld = {}
    pos = 0; entry = tp = sl = prev = np.nan
    for i in range(len(df)):
        d = day[i]
        if pos != 0:
            htp = hi[i] >= tp if pos > 0 else lo[i] <= tp
            hsl = lo[i] <= sl if pos > 0 else hi[i] >= sl
            px = cl[i]; done = False
            if hsl: px = sl; done = True
            elif htp: px = tp; done = True
            # 金曜の指定時刻で強制クローズ
            if fri_close and not done and dow[i] == 4 and hh[i] >= FRI_EXIT_JST:
                px = cl[i]; done = True
            pnl[d] = pnl.get(d,0.0) + pos*(px-prev)/entry*100 \
                     + max(0.0, abs(dif[i])-MARKUP)/365/24
            prev = px
            nheld[d] = 1
            if done: pos = 0
        if pos == 0 and hh[i] == ENTRY_JST and np.isfinite(atr[i]) and np.isfinite(dif[i]) and dif[i] != 0:
            if fri_close and dow[i] == 4: pass          # 金曜は新規を建てない
            else:
                pos = 1 if dif[i] > 0 else -1
                entry = op[i]; W = atr[i]*k
                tp, sl = entry+pos*W, entry-pos*W; prev = entry
                pnl[d] = pnl.get(d,0.0) - COST_PCT*100
        nheld.setdefault(d, 0)
    s = pd.Series(pnl).sort_index(); s.index = pd.DatetimeIndex(s.index)
    e = pd.Series(nheld).sort_index(); e.index = pd.DatetimeIndex(e.index)
    return s, e


def stats(r):
    rr = r/100; eq = (1+rr).cumprod(); n = len(rr)
    return {"CAGR": (eq.iloc[-1]**(250/n)-1)*100, "vol": rr.std()*np.sqrt(250)*100,
            "sharpe": ((eq.iloc[-1]**(250/n)-1)*100)/(rr.std()*np.sqrt(250)*100),
            "mdd": (eq/eq.cummax()-1).min()*100, "worst": rr.min()*100, "skew": rr.skew()}


if __name__ == "__main__":
    g = weekend_gaps()
    print("## 1. 週末ギャップの実測（キャリー方向で符号調整・%）\n")
    print(f"サンプル {len(g)} 件（8ペア × 約285週）\n")
    q = g.gap_pct.describe(percentiles=[.01,.05,.25,.5,.75,.95,.99])
    print("| 統計量 | 値(%) |")
    print("|---|---|")
    for k_ in ["mean","std","1%","5%","25%","50%","75%","95%","99%","min","max"]:
        print(f"| {k_} | {q[k_]:+.3f} |")
    print(f"\n歪度 {g.gap_pct.skew():+.2f} ／ ギャップが -0.5%より悪い週 {(g.gap_pct<-0.5).mean()*100:.1f}% "
          f"／ -1.0%より悪い週 {(g.gap_pct<-1.0).mean()*100:.1f}%")
    print("\n### ペア別 平均ギャップ\n")
    print("| ペア | 平均(%) | 標準偏差 | 最悪(%) | 歪度 |")
    print("|---|---|---|---|---|")
    for p, gg in g.groupby("pair"):
        print(f"| {p} | {gg.gap_pct.mean():+.4f} | {gg.gap_pct.std():.3f} | "
              f"{gg.gap_pct.min():+.2f} | {gg.gap_pct.skew():+.2f} |")

    print("\n## 2. 金曜クローズあり / なし（持ちっぱなし・TP/SLのみ）\n")
    for k in (1.0, 2.0, 3.0):
        print(f"\n### ブラケット {k}×ATR20\n")
        print("| ルール | 建玉率 | CAGR | ボラ | Sharpe | 最大DD | 最悪日 | 歪度 |")
        print("|---|---|---|---|---|---|---|---|")
        for fc in (False, True):
            cols = []; expo = []
            for p in PAIRS:
                got = simulate(p, k=k, fri_close=fc)
                if got is None: continue
                s, e = got; cols.append(s.rename(p)); expo.append(e.mean())
            pf = pd.concat(cols, axis=1).fillna(0).mean(axis=1)
            st = stats(pf)
            print(f'| {"金曜クローズあり" if fc else "持ち越し"} | {np.mean(expo)*100:.0f}% | '
                  f'{st["CAGR"]:+.2f}% | {st["vol"]:.1f}% | {st["sharpe"]:+.2f} | '
                  f'{st["mdd"]:.1f}% | {st["worst"]:.2f}% | {st["skew"]:+.2f} |')
