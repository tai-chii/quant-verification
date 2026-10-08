# -*- coding: utf-8 -*-
"""キャリー方向 × テクニカル方向 の組み合わせ。

taichi案: 金利差でプラススワップになる方向に絞り、テクニカルが同方向の日だけ建てる。
          どちらかが反転したら定時に閉じる。

検証の核心は「Sharpeが上がったか」ではなく
**「同意日のリターンが、全日のリターンより有意に高いか」**。
建玉率が下がっただけならレバレッジ調整で代替でき、価値がない（本セッションの原則1）。

テクニカルは2種:
  MA   … 終値 > SMA(n) なら上昇トレンド
  DON  … 終値が過去n日の高値圏(上位1/3)なら上昇（水平線・ブレイクの客観版）
決定的・先読みなし（すべて shift(1)）・週末フィラー足除外。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; MARKUP = 0.7; COST = 0.002/100
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
def panel(pair):
    if pair in _C: return _C[pair]
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df = df[df.jst >= "2021-01-01"]
    if "volume" in df.columns: df = df[df.volume > 0]
    a = df[df.jst.dt.hour == ENTRY_JST]
    px = a.set_index(a.jst.dt.normalize())["open"]
    px = px[~px.index.duplicated()]
    idx = px.index
    gap = idx.to_series().diff().dt.total_seconds()/3600
    ret = (px.shift(-1)/px - 1)*100
    diff = rate_steps(pair[:3], idx) - rate_steps(pair[3:], idx)
    held = (gap.shift(-1)/24).clip(lower=1)
    out = pd.DataFrame({"px": px, "ret": ret, "diff": diff, "held": held, "gap": gap.shift(-1)})
    out = out[(out.gap <= 80) & out.ret.notna() & out["diff"].notna()]
    _C[pair] = out
    return out


def tech_signal(px, kind, n):
    """先読み防止: すべて shift(1)（前日までの情報だけで当日の方向を決める）"""
    if kind == "MA":
        return np.sign(px - px.rolling(n).mean()).shift(1)
    if kind == "DON":
        hi = px.rolling(n).max(); lo = px.rolling(n).min()
        pos = (px-lo)/(hi-lo)                       # 0=安値圏 1=高値圏
        sig = pd.Series(np.where(pos > 2/3, 1.0, np.where(pos < 1/3, -1.0, 0.0)),
                        index=px.index)
        return sig.shift(1)
    raise ValueError(kind)


def combo(kind, n):
    """A: キャリーのみ / T: テクニカルのみ / AND: 同意日のみ / DIS: 不同意日のみ"""
    res = {k: {} for k in ("A","T","AND","DIS")}
    diag = []
    for p in PAIRS:
        d = panel(p)
        if d is None: continue
        sw = np.maximum(0.0, d["diff"].abs()-MARKUP)/365*d.held
        c = np.sign(d["diff"])
        t = tech_signal(d.px, kind, n).reindex(d.index)
        rc = c*d.ret + sw - COST*100
        rt = t*d.ret - COST*100
        agree = (c == t) & (t != 0)
        res["A"][p] = rc
        res["T"][p] = rt
        res["AND"][p] = rc.where(agree, 0.0)
        res["DIS"][p] = rc.where(~agree & (t != 0), 0.0)
        diag.append(pd.DataFrame({"rc": rc, "agree": agree, "tnz": t != 0}))
    D = pd.concat(diag)
    out = {k: pd.DataFrame(v).mean(axis=1) for k, v in res.items()}
    agr_rate = D.agree[D.tnz].mean()*100
    ag = D.rc[D.agree]; dg = D.rc[D.tnz & ~D.agree]
    se = np.sqrt(ag.var()/len(ag) + dg.var()/len(dg))
    return out, {"agree_rate": agr_rate, "n_ag": len(ag), "n_dg": len(dg),
                 "m_ag": ag.mean(), "m_dg": dg.mean(),
                 "m_all": D.rc[D.tnz].mean(), "t": (ag.mean()-dg.mean())/se}


def perf(r, lo=None, hi=None):
    x = r.dropna()
    if lo: x = x[x.index >= lo]
    if hi: x = x[x.index < hi]
    rr = x/100; eq = (1+rr).cumprod(); n = len(rr)
    ann = (eq.iloc[-1]**(250/n)-1)*100; vol = rr.std()*np.sqrt(250)*100
    return {"n":n,"ann":ann,"vol":vol,"sharpe":ann/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100,"skew":rr.skew(),
            "expo":(x!=0).mean()*100}


if __name__ == "__main__":
    print("## 1. 核心の診断: 同意日のリターンは不同意日より高いか\n")
    print("| テクニカル | 同意率 | 同意日 平均(%) | 不同意日 平均(%) | 差 | **t値** |")
    print("|---|---|---|---|---|---|")
    for kind, n in [("MA",10),("MA",20),("MA",50),("MA",100),("MA",200),
                    ("DON",10),("DON",20),("DON",50),("DON",100)]:
        _, dg = combo(kind, n)
        print(f'| {kind}{n} | {dg["agree_rate"]:.0f}% | {dg["m_ag"]:+.4f} | {dg["m_dg"]:+.4f} | '
              f'{dg["m_ag"]-dg["m_dg"]:+.4f} | **{dg["t"]:+.2f}** |')
    print("\n※ t値が +2 を超えなければ、テクニカルは方向の情報を持っていない")

    print("\n## 2. 戦略としての成績（全期間）\n")
    print("| 構成 | 建玉率 | 年率 | ボラ | Sharpe | 最大DD | 歪度 |")
    print("|---|---|---|---|---|---|---|")
    base, _ = combo("MA", 50)
    for lab, key in (("キャリーのみ","A"), ("テクニカルのみ","T")):
        s = perf(base[key])
        print(f'| {lab} | {s["expo"]:.0f}% | {s["ann"]:+.2f}% | {s["vol"]:.1f}% | '
              f'{s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["skew"]:+.2f} |')
    for kind, n in [("MA",20),("MA",50),("MA",100),("MA",200),("DON",20),("DON",50)]:
        o, _ = combo(kind, n)
        s = perf(o["AND"])
        print(f'| **同意のみ {kind}{n}** | {s["expo"]:.0f}% | {s["ann"]:+.2f}% | {s["vol"]:.1f}% | '
              f'{s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["skew"]:+.2f} |')

    print("\n## 3. 期間別 Sharpe\n")
    print("| 構成 | 2021-2023 | 2024 | 2025-2026 |")
    print("|---|---|---|---|")
    rows = [("キャリーのみ", base["A"]), ("テクニカルのみ(MA50)", base["T"])]
    for kind, n in [("MA",50),("MA",100),("DON",50)]:
        o, _ = combo(kind, n); rows.append((f"同意のみ {kind}{n}", o["AND"]))
    for lab, r in rows:
        a = perf(r,"2021-01-01","2024-01-01")["sharpe"]
        b = perf(r,"2024-01-01","2025-01-01")["sharpe"]
        c = perf(r,"2025-01-01",None)["sharpe"]
        print(f"| {lab} | {a:+.2f} | {b:+.2f} | {c:+.2f} |")
