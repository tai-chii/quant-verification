# -*- coding: utf-8 -*-
"""金利差の「使い方」を5通り比べる。方向シグナルを金利差だけに限定したまま。

  A) 符号のみ            … 各ペアで高金利側を買う（これまでのベースライン）
  B) 金利差の大きさで加重 … 差が小さいペアは小さく張る
  C) クロスセクショナル   … 通貨をランク付けし、高金利上位を買い・低金利下位を売り（ドル中立）
  D) リスク調整キャリー   … 金利差 ÷ ボラ で加重（carry-to-risk）
  E) 金利差の変化         … 水準でなく3ヶ月変化の符号を使う

あわせて「8ペアは本当に8つの独立な賭けか」を相関から測る。
週末フィラー足は volume>0 で除外済み。決定的・先読みなし。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; MARKUP = 0.7; COST = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]
VS_USD = {"EUR":("EURUSD",1),"GBP":("GBPUSD",1),"AUD":("AUDUSD",1),
          "JPY":("USDJPY",-1),"CAD":("USDCAD",-1),"CHF":("USDCHF",-1)}

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
def pair_daily(pair):
    """24時間ロールの日次: 価格リターン(%)・金利差・ボラ。週末フィラー除外。"""
    if pair in _C: return _C[pair]
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df = df[(df.jst >= "2021-01-01")]
    if "volume" in df.columns: df = df[df.volume > 0]        # ← フィラー足除外
    a = df[df.jst.dt.hour == ENTRY_JST]
    px = a.set_index(a.jst.dt.normalize())["open"]
    px = px[~px.index.duplicated()]
    gap = px.index.to_series().diff().dt.total_seconds()/3600
    ret = (px.shift(-1)/px - 1)*100
    idx = px.index
    diff = rate_steps(pair[:3], idx) - rate_steps(pair[3:], idx)
    held = (gap.shift(-1)/24).clip(lower=1)
    out = pd.DataFrame({"ret": ret, "diff": diff, "held": held, "gap": gap.shift(-1)})
    out = out[(out.gap <= 80) & out.ret.notna() & out["diff"].notna()]
    out["vol"] = out.ret.rolling(60).std().shift(1)
    _C[pair] = out
    return out


def cur_panel():
    """各通貨のUSDに対する日次リターン(%)と政策金利。"""
    R, Rt = {}, {}
    for c, (pair, s) in VS_USD.items():
        d = pair_daily(pair)
        if d is None: continue
        R[c] = s*d.ret
    R = pd.DataFrame(R).dropna(how="all")
    R["USD"] = 0.0
    for c in list(R.columns):
        Rt[c] = rate_steps(c, R.index)
    return R, pd.DataFrame(Rt)


def perf(r, label, lo=None, hi=None):
    x = r.dropna()
    if lo is not None: x = x[(x.index >= lo)]
    if hi is not None: x = x[(x.index < hi)]
    if len(x) < 60: return None
    rr = x/100; eq = (1+rr).cumprod(); n = len(rr)
    ann = (eq.iloc[-1]**(250/n)-1)*100
    vol = rr.std()*np.sqrt(250)*100
    return {"label":label,"n":n,"ann":ann,"vol":vol,"sharpe":ann/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100,"skew":rr.skew()}


def build_variants():
    out = {}
    # --- ペア単位（A,B,D,E） ---
    cols_A, cols_B, cols_D, cols_E = {}, {}, {}, {}
    for p in PAIRS:
        d = pair_daily(p)
        if d is None: continue
        sw = np.maximum(0.0, d["diff"].abs()-MARKUP)/365*d.held
        sgn = np.sign(d["diff"])
        base = sgn*d.ret + sw - COST*100
        cols_A[p] = base
        w = (d["diff"].abs()/2.0).clip(upper=2.0)              # 金利差2%で等倍、上限2倍
        cols_B[p] = w*base
        cr = (d["diff"].abs()/d["vol"]).replace([np.inf,-np.inf],np.nan)
        cols_D[p] = (cr/cr.median()).clip(upper=3.0)*base
        chg = np.sign(d["diff"] - d["diff"].shift(60))
        cols_E[p] = chg*(d.ret) - COST*100                     # 金利差の変化方向に賭ける
    out["A 符号のみ"] = pd.DataFrame(cols_A).mean(axis=1)
    out["B 金利差の大きさで加重"] = pd.DataFrame(cols_B).mean(axis=1)
    out["D リスク調整キャリー"] = pd.DataFrame(cols_D).mean(axis=1)
    out["E 金利差の変化"] = pd.DataFrame(cols_E).mean(axis=1)
    # --- クロスセクショナル（C） ---
    R, Rt = cur_panel()
    Rt = Rt.reindex(R.index).ffill()
    rk = Rt.rank(axis=1, ascending=False)
    K = 2
    longw = (rk <= K).astype(float); shortw = (rk > len(Rt.columns)-K).astype(float)
    longw = longw.div(longw.sum(axis=1), axis=0); shortw = shortw.div(shortw.sum(axis=1), axis=0)
    carry = (Rt*longw).sum(axis=1) - (Rt*shortw).sum(axis=1)
    px_ret = (R*longw).sum(axis=1) - (R*shortw).sum(axis=1)
    out["C クロスセクショナル(上位2買い下位2売り)"] = px_ret + np.maximum(0, carry-MARKUP)/365 - COST*100*2
    return out, pd.DataFrame(cols_A)


if __name__ == "__main__":
    V, A_cols = build_variants()
    print("## 1. 8ペアは本当に「8つの独立な賭け」か\n")
    c = A_cols.dropna().corr()
    iu = np.triu_indices_from(c, 1)
    ev = np.linalg.eigvalsh(c.values)
    eff = (ev.sum()**2)/(ev**2).sum()
    print(f"ペア間相関の平均 {c.values[iu].mean():+.2f}（最大 {c.values[iu].max():+.2f}）")
    print(f"**実効的な独立ベット数 ≒ {eff:.1f}**（名目8ペア）\n")
    print("| | " + " | ".join(c.columns) + " |")
    print("|" + "---|"*(len(c.columns)+1))
    for i, row in c.iterrows():
        print(f"| {i} | " + " | ".join(f"{v:+.2f}" for v in row) + " |")

    for lo, hi, nm in ((None, None, "全期間 2021-2026"),
                       ("2021-01-01", "2024-01-01", "前半 2021-2023"),
                       ("2024-01-01", "2025-01-01", "2024年"),
                       ("2025-01-01", None, "**2025-2026（直近）**")):
        print(f"\n## {nm}\n")
        print("| 使い方 | n | 年率 | ボラ | Sharpe | 最大DD | 歪度 |")
        print("|---|---|---|---|---|---|---|")
        for k, v in V.items():
            s = perf(v, k, lo, hi)
            if s is None: continue
            print(f'| {k} | {s["n"]} | {s["ann"]:+.2f}% | {s["vol"]:.1f}% | '
                  f'{s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["skew"]:+.2f} |')
