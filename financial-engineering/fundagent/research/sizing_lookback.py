# -*- coding: utf-8 -*-
"""ロット算出に使う値幅の参照期間を振る（前日値幅 n=1 〜 ATR60）。

lot = 口座 × リスク% ÷ (k × 値幅_n)
  n=1  … 前日の値幅そのもの（＝taichi案）
  n=20 … これまで使っていた ATR20

サイジング規則の目的は「リターンを増やすこと」ではなく
「狙った損失率を正確に実現すること」なので、そちらを主指標にする:
  - 実現ボラの安定性（20日実現ボラのばらつき。小さいほど良い）
  - 最悪日 / 狙い の比率（テールが狙いをどれだけ突き抜けたか）
  - ロットの日次変動率（実務上の手間と、心理的な扱いにくさ）

器は24時間ロール、方向はキャリー、8ペア等資本配分。決定的・先読みなし。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; MARKUP = 0.7; COST_PCT = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]
RISK = 1.0      # 1回あたりリスク(%)
K = 2.0         # SL幅 = K × 値幅_n

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


_CACHE = {}
_CYC = {}
def panel(pair):
    if pair in _CACHE: return _CACHE[pair]
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d.c.shift(1)
    tr = pd.concat([d.h-d.l, (d.h-pc).abs(), (d.l-pc).abs()], axis=1).max(axis=1)
    rng = d.h - d.l                       # 単純な値幅（ギャップを含まない）
    # 「前日動いた値幅」は建玉サイクル(定時→翌定時)の高安で定義する。
    # 暦日で取ると月曜が土曜JST(金曜NY終盤の数時間)を参照してしまい、値幅がほぼゼロになる。
    anc = df[df.jst.dt.hour == ENTRY_JST].index
    cyc_hi, cyc_lo = [], []
    for i in range(len(anc)-1):
        seg = df.loc[anc[i]:anc[i+1]]
        cyc_hi.append(seg.high.max()); cyc_lo.append(seg.low.min())
    cyc_hi.append(np.nan); cyc_lo.append(np.nan)
    a = df[df.jst.dt.hour == ENTRY_JST]
    px = a.set_index(a.jst.dt.normalize())["open"]
    gap = px.index.to_series().diff().dt.total_seconds()/3600
    ret = px.shift(-1)/px - 1
    idx = px.index
    diff = rate_steps(pair[:3], idx) - rate_steps(pair[3:], idx)
    sgn = np.sign(diff)
    held = (gap.shift(-1)/24).clip(lower=1)
    r = sgn*ret + np.maximum(0.0, diff.abs()-MARKUP)/365*held/100 - COST_PCT
    out = pd.DataFrame({"r": r, "px": px, "sgn": sgn, "gap": gap.shift(-1)})
    cyc = pd.Series(np.array(cyc_hi)-np.array(cyc_lo), index=idx)   # サイクル値幅
    out["tr"] = cyc.reindex(out.index if False else idx).reindex(idx)
    out["rng"] = rng.reindex(idx)
    _CYC[pair] = cyc
    out = out[(out.gap <= 80) & out.r.notna() & (out.sgn != 0)]
    _CACHE[pair] = (out, cyc, rng)
    return _CACHE[pair]


def build(n, use_tr=True, risk=RISK, k=K, lev_cap=None, floor_frac=None):
    """lev_cap: レバレッジ上限（実務上の防護柵）。floor_frac: 値幅の下限（中央値に対する比）。"""
    R, L = {}, {}
    for p in PAIRS:
        got = panel(p)
        if got is None: continue
        out, tr, rng = got
        src = (tr if use_tr else rng).reindex(out.index)   # ← 実際に取引したサイクルだけに絞る
        w = src.rolling(n).mean().shift(1)                  # ← shift(1) 先読み防止
        w_pct = w/out.px*100
        if floor_frac is not None:
            w_pct = w_pct.clip(lower=w_pct.median()*floor_frac)
        lev = risk/(k*w_pct)
        lev = lev.replace([np.inf, -np.inf], np.nan)
        if lev_cap is not None:
            lev = lev.clip(upper=lev_cap)
        R[p] = out.r; L[p] = lev
    R = pd.DataFrame(R); L = pd.DataFrame(L)
    daily = (L*R).mean(axis=1).dropna()
    lev = L.mean(axis=1).reindex(daily.index)
    turn = L.pct_change().abs().mean(axis=1).reindex(daily.index)
    return daily, lev, turn


def report(r, lev, turn, risk):
    eq = (1+r).cumprod(); n = len(r)
    cagr = (eq.iloc[-1]**(250/n)-1)*100 if eq.iloc[-1] > 0 else -100
    vol = r.std()*np.sqrt(250)*100
    rv = r.rolling(20).std()*np.sqrt(250)*100        # 20日実現ボラ
    stab = rv.std()/rv.mean()*100                     # 変動係数（小さいほど狙いが安定）
    return {"CAGR":cagr, "vol":vol, "sharpe":cagr/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100, "worst":r.min()*100,
            "skew":r.skew(), "lev":lev.mean(), "stab":stab,
            "turn":turn.mean()*100, "p99":-r.quantile(0.01)*100}


if __name__ == "__main__":
    print(f"## 値幅の参照期間を振る（1回リスク {RISK}% / SL幅 = {K}×値幅_n / 24時間ロール）\n")
    print("| 参照期間 | 平均レバ | CAGR | ボラ | Sharpe | 最大DD | 最悪日 | 歪度 | ボラ安定性 | ロット変動 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for n in (1,2,3,5,10,20,60):
        r,l,t = build(n)
        s = report(r,l,t,RISK)
        lab = "**前日値幅(n=1)**" if n==1 else ("**ATR20**" if n==20 else f"n={n}")
        print(f'| {lab} | {s["lev"]:.2f}倍 | {s["CAGR"]:+.2f}% | {s["vol"]:.1f}% | {s["sharpe"]:+.2f} | '
              f'{s["mdd"]:.1f}% | {s["worst"]:.2f}% | {s["skew"]:+.2f} | {s["stab"]:.0f}% | {s["turn"]:.1f}% |')
    print("\n※ ボラ安定性 = 20日実現ボラの変動係数。**小さいほど「狙った損失率」を安定して実現できている**")
    print("※ ロット変動 = ロットの日次変化率の平均。大きいほど毎日ロットを大きく変える必要がある")

    print("\n## 値幅の定義: True Range（ギャップ込み） vs 単純な高値-安値\n")
    print("| 定義 | 参照期間 | CAGR | Sharpe | 最大DD | 最悪日 | ボラ安定性 |")
    print("|---|---|---|---|---|---|---|")
    for use_tr in (True, False):
        for n in (1, 20):
            r,l,t = build(n, use_tr=use_tr); s = report(r,l,t,RISK)
            nm = "True Range" if use_tr else "高値-安値"
            print(f'| {nm} | n={n} | {s["CAGR"]:+.2f}% | {s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | '
                  f'{s["worst"]:.2f}% | {s["stab"]:.0f}% |')

    print(f"\n## 狙ったリスクは実現できているか（1回リスク {RISK}% の想定に対して）\n")
    print("| 参照期間 | 日次損失の1%点 | 最悪日 | 最悪日/狙い |")
    print("|---|---|---|---|")
    for n in (1,5,20,60):
        r,l,t = build(n); s = report(r,l,t,RISK)
        print(f'| n={n} | -{s["p99"]:.2f}% | {s["worst"]:.2f}% | {abs(s["worst"])/RISK:.1f}倍 |')
