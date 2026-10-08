# -*- coding: utf-8 -*-
"""リスク%固定サイジング（1回の損失＝口座のx%）の検証。

比較する3つ:
  A) 固定ロット            … 常に同じ通貨量。これまでの検証の前提
  B) リスク%固定 × ATR幅   … lot = 口座×r% ÷ (k×ATR)。ボラ逆比例＝ボラターゲティング
  C) リスク%固定 × 価格%幅 … lot = 口座×r% ÷ (c×価格)。SL幅が一定なので **レバ一定**

Cが「ATRを使わない形」。Bとの差が「ボラに応じて幅を変える価値」そのものになる。
いずれも複利（口座残高に比例）なので、負けるとロットが縮む＝構造的に破産しない。
器は24時間ロール（標準）。方向はキャリー。決定的・先読みなし。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; MARKUP = 0.7; COST_PCT = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]
K_ATR = 2.0          # SL幅 = K_ATR × ATR20
C_FIX = 0.60         # SL幅 = C_FIX % of price（ATR20の平均が概ね0.3%なので 2.0×ATR 相当）

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


def daily_panel(pair):
    """24時間ロールの日次リターン(%)と、その日のATR%(先読みなし)を返す。"""
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d.c.shift(1)
    tr = pd.concat([d.h-d.l,(d.h-pc).abs(),(d.l-pc).abs()],axis=1).max(axis=1)
    atr = tr.rolling(20).mean().shift(1)
    a = df[df.jst.dt.hour == ENTRY_JST].set_index(df[df.jst.dt.hour == ENTRY_JST].jst.dt.normalize())
    px = a["open"]
    gap = px.index.to_series().diff().dt.total_seconds()/3600
    ret = px.shift(-1)/px - 1                                    # 24時間後の価格変化率
    idx = px.index
    diff = rate_steps(pair[:3], idx) - rate_steps(pair[3:], idx)
    sgn = np.sign(diff)
    days_held = (gap.shift(-1)/24).clip(lower=1)
    swap = np.maximum(0.0, diff.abs()-MARKUP)/365*days_held/100
    r = sgn*ret + swap - COST_PCT                                # 1単位あたりの収益率
    out = pd.DataFrame({"r": r, "atr_pct": atr.reindex(idx)/px*100, "sgn": sgn,
                        "gap": gap.shift(-1)})
    out = out[(out.gap <= 80) & out.r.notna() & out.atr_pct.notna() & (out.sgn != 0)]
    return out[["r","atr_pct"]]


def portfolio(mode, risk_pct, k=K_ATR, c=C_FIX):
    """mode: 'fixed'(固定ロット) / 'atr'(リスク%×ATR幅) / 'pct'(リスク%×価格%幅)

    risk_pct / k / c はいずれも「%の数値」で渡す（例: 0.5 = 0.5%）。単位を揃えること。
    """
    panels = {p: daily_panel(p) for p in PAIRS}
    panels = {p: v for p, v in panels.items() if v is not None and len(v) > 200}
    R = pd.concat({p: v.r for p, v in panels.items()}, axis=1)
    A = pd.concat({p: v.atr_pct for p, v in panels.items()}, axis=1)
    if mode == "fixed":
        lev = pd.DataFrame(1.0, index=R.index, columns=R.columns)
    elif mode == "atr":
        lev = risk_pct / (k*A)                      # SL幅 = k×ATR%
    else:
        lev = pd.DataFrame(risk_pct/c, index=R.index, columns=R.columns)
    daily = (lev*R).mean(axis=1).dropna()           # 8ペア等資本配分
    return daily, lev.mean(axis=1).reindex(daily.index)


def stats(r, lev=None):
    eq = (1+r).cumprod(); n = len(r)
    cagr = (eq.iloc[-1]**(250/n)-1)*100 if eq.iloc[-1] > 0 else -100.0
    vol = r.std()*np.sqrt(250)*100
    d = {"CAGR":cagr, "vol":vol, "sharpe":cagr/vol if vol else np.nan,
         "mdd":(eq/eq.cummax()-1).min()*100, "worst":r.min()*100, "skew":r.skew(),
         "final":eq.iloc[-1]}
    if lev is not None: d["lev"] = lev.mean()
    return d


if __name__ == "__main__":
    print("## A) 固定ロット（これまでの前提・基準）\n")
    r, l = portfolio("fixed", None); s = stats(r, l)
    print(f'CAGR {s["CAGR"]:+.2f}% / ボラ {s["vol"]:.1f}% / Sharpe {s["sharpe"]:+.2f} / '
          f'最大DD {s["mdd"]:.1f}% / 最悪日 {s["worst"]:.2f}% / 5.5年で資産 {s["final"]:.3f}倍')

    print("\n## B) リスク%固定 × ATR幅（ボラターゲティング）\n")
    print("| 1回リスク | 平均レバ | CAGR | ボラ | Sharpe | 最大DD | 最悪日 | 5.5年倍率 |")
    print("|---|---|---|---|---|---|---|---|")
    for rp in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0):
        r, l = portfolio("atr", rp); s = stats(r, l)
        print(f'| {rp:.2f}% | {s["lev"]:.2f}倍 | {s["CAGR"]:+.2f}% | {s["vol"]:.1f}% | '
              f'{s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["worst"]:.2f}% | {s["final"]:.3f}倍 |')

    print("\n## C) リスク%固定 × 価格%幅（ATRを使わない＝レバ一定）\n")
    print("| 1回リスク | 平均レバ | CAGR | ボラ | Sharpe | 最大DD | 最悪日 | 5.5年倍率 |")
    print("|---|---|---|---|---|---|---|---|")
    for rp in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0):
        r, l = portfolio("pct", rp); s = stats(r, l)
        print(f'| {rp:.2f}% | {s["lev"]:.2f}倍 | {s["CAGR"]:+.2f}% | {s["vol"]:.1f}% | '
              f'{s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["worst"]:.2f}% | {s["final"]:.3f}倍 |')

    print("\n## B vs C を同じ平均レバで揃えて比較（ボラ連動に価値があるか）\n")
    rb, lb = portfolio("atr", 0.5)
    target = lb.mean()
    rc, lc = portfolio("pct", 0.5)
    rc = rc * (target/lc.mean())
    sb, sc = stats(rb), stats(rc)
    print("| サイジング | CAGR | ボラ | Sharpe | 最大DD | 最悪日 | 歪度 |")
    print("|---|---|---|---|---|---|---|")
    for nm, s in (("B: ATR連動幅", sb), ("C: 価格%固定幅", sc)):
        print(f'| {nm} | {s["CAGR"]:+.2f}% | {s["vol"]:.1f}% | {s["sharpe"]:+.2f} | '
              f'{s["mdd"]:.1f}% | {s["worst"]:.2f}% | {s["skew"]:+.2f} |')
