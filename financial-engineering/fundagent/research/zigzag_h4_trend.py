# -*- coding: utf-8 -*-
"""H4 ZigZag++ による Dow 的トレンド定義を、方向シグナルとして検証する。

【先読み防止が最重要】
ZigZagのピボットは「未来を見て」確定する。FX/CLAUDE.md の鉄則:
  「ZigZagのピボット(H/L)は未来を見て確定する=先読み。
    母数はその瞬間に判定できるトリガーで取る」
よって本実装は **因果版**:
  - ピボットは「価格が閾値ぶん逆行した瞬間」に確定したものとして扱う
  - トレンド判定に使えるのは confirm_time <= 現在時刻 のピボットだけ
  - ATR も shift(1)。SMMA も shift(1)

トレンド定義（Dow）: 確定済みピボットの直近2高値・2安値で
  上昇 = 高値切り上げ かつ 安値切り上げ
  下降 = 高値切り下げ かつ 安値切り下げ
  それ以外 = レンジ(0)

データ: H1(volume>0)から H4 を合成。72時間超の穴でセグメント分割してから
        ローリング計算する（データ品質監査_2026-09-13 の指示）。
決定的。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9; MARKUP = 0.7; COST = 0.002/100
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]
CLEAN4 = ["USDJPY","GBPUSD","AUDUSD","EURUSD"]      # 欠損の少ない4ペア

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


def load_h4(pair):
    """H1(volume>0) → H4 合成。72時間超の穴でセグメント分割。"""
    f = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(f): return None
    df = pd.read_csv(f, parse_dates=["time"]).sort_values("time")
    df = df[df.time >= "2020-06-01"]                       # 助走ぶん余分に取る
    if "volume" in df.columns: df = df[df.volume > 0]
    df = df.set_index("time")
    h4 = df.resample("4h").agg(open=("open","first"), high=("high","max"),
                               low=("low","min"), close=("close","last")).dropna()
    gap = h4.index.to_series().diff().dt.total_seconds()/3600
    h4["seg"] = (gap > 72).cumsum()
    # ATR14 と 25SMMA はセグメント内で計算（穴をまたがせない）
    def _seg(g):
        pc = g.close.shift(1)
        tr = pd.concat([g.high-g.low, (g.high-pc).abs(), (g.low-pc).abs()], axis=1).max(axis=1)
        g = g.copy()
        g["atr"] = tr.rolling(14).mean().shift(1)           # shift(1)=先読み防止
        g["smma"] = g.close.ewm(alpha=1/25, adjust=False).mean().shift(1)
        return g
    return h4.groupby("seg", group_keys=False).apply(_seg)


def zigzag_causal(h4, k=2.0):
    """ATR×k を反転閾値とする ZigZag++ 的ピボット抽出（因果版）。

    返り値: トレンド状態のSeries（各H4バー終値時点で判定できる値）
            +1=上昇 / -1=下降 / 0=レンジ or 未確定
    """
    state = pd.Series(0.0, index=h4.index)
    for seg, g in h4.groupby("seg"):
        hi, lo, cl, atr = g.high.values, g.low.values, g.close.values, g.atr.values
        n = len(g)
        dirn = 0                 # +1=上げレッグ探索中 / -1=下げレッグ探索中
        cand_i = 0; cand_p = np.nan
        highs = []; lows = []    # 確定済みピボット（価格のみ・時系列順）
        st = np.zeros(n)
        for i in range(n):
            th = atr[i]*k
            if not np.isfinite(th) or th <= 0:
                st[i] = st[i-1] if i else 0
                continue
            if dirn == 0:
                dirn = 1; cand_i = i; cand_p = hi[i]
            elif dirn == 1:
                if hi[i] > cand_p: cand_i, cand_p = i, hi[i]
                elif cand_p - lo[i] >= th:
                    highs.append(cand_p)                   # ← この瞬間に確定
                    dirn = -1; cand_i, cand_p = i, lo[i]
            else:
                if lo[i] < cand_p: cand_i, cand_p = i, lo[i]
                elif hi[i] - cand_p >= th:
                    lows.append(cand_p)
                    dirn = 1; cand_i, cand_p = i, hi[i]
            if len(highs) >= 2 and len(lows) >= 2:
                up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
                dn = highs[-1] < highs[-2] and lows[-1] < lows[-2]
                st[i] = 1.0 if up else (-1.0 if dn else 0.0)
            else:
                st[i] = 0.0
        state.loc[g.index] = st
    return state


def daily_panel(pair, k=2.0, use_smma=False):
    h4 = load_h4(pair)
    if h4 is None: return None
    trend = zigzag_causal(h4, k)
    if use_smma:
        above = np.sign(h4.close.shift(1) - h4.smma)        # shift済みSMMAと前バー終値
        trend = trend.where(trend == above, 0.0)            # 向きが一致しなければレンジ扱い
    # H4状態 → 日次エントリー時刻(9:00 JST = 0:00 UTC)へ as-of で写す
    f = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    df = pd.read_csv(f, parse_dates=["time"]).sort_values("time")
    df["jst"] = df.time + pd.Timedelta(hours=9)
    df = df[df.jst >= "2021-01-01"]
    if "volume" in df.columns: df = df[df.volume > 0]
    a = df[df.jst.dt.hour == ENTRY_JST]
    px = a.set_index(a.jst.dt.normalize())["open"]; px = px[~px.index.duplicated()]
    ts = a.set_index(a.jst.dt.normalize())["time"]; ts = ts[~ts.index.duplicated()]
    tr = pd.Series(pd.merge_asof(ts.reset_index().rename(columns={"time":"t"}).sort_values("t"),
                                 trend.rename("tr").reset_index().sort_values("time"),
                                 left_on="t", right_on="time",
                                 direction="backward")["tr"].values, index=ts.index)
    idx = px.index
    gap = idx.to_series().diff().dt.total_seconds()/3600
    ret = (px.shift(-1)/px - 1)*100
    diff = rate_steps(pair[:3], idx) - rate_steps(pair[3:], idx)
    out = pd.DataFrame({"ret": ret, "diff": diff, "trend": tr,
                        "held": (gap.shift(-1)/24).clip(lower=1), "gap": gap.shift(-1)})
    return out[(out.gap <= 80) & out.ret.notna() & out["diff"].notna() & out.trend.notna()]


def diagnose(pairs, k=2.0, use_smma=False):
    rows = []; series = {"C":{}, "T":{}, "AND":{}}
    for p in pairs:
        d = daily_panel(p, k, use_smma)
        if d is None or len(d) < 200: continue
        sw = np.maximum(0.0, d["diff"].abs()-MARKUP)/365*d.held
        c = np.sign(d["diff"]); t = d.trend
        rc = c*d.ret + sw - COST*100
        series["C"][p] = rc
        series["T"][p] = (t*d.ret - COST*100).where(t != 0, 0.0)
        series["AND"][p] = rc.where((c == t) & (t != 0), 0.0)
        rows.append(pd.DataFrame({"rc": rc, "agree": (c == t) & (t != 0), "tnz": t != 0,
                                  "trend": t}))
    D = pd.concat(rows)
    ag = D.rc[D.agree]; dg = D.rc[D.tnz & ~D.agree]
    se = np.sqrt(ag.var()/len(ag) + dg.var()/len(dg))
    stat = {"trend_rate": D.tnz.mean()*100, "agree_rate": D.agree[D.tnz].mean()*100,
            "n_ag": len(ag), "n_dg": len(dg), "m_ag": ag.mean(), "m_dg": dg.mean(),
            "t": (ag.mean()-dg.mean())/se}
    return {k2: pd.DataFrame(v).mean(axis=1) for k2, v in series.items()}, stat


def perf(r, lo=None, hi=None):
    x = r.dropna()
    if lo: x = x[x.index >= lo]
    if hi: x = x[x.index < hi]
    if len(x) < 60: return None
    rr = x/100; eq = (1+rr).cumprod(); n = len(rr)
    ann = (eq.iloc[-1]**(250/n)-1)*100; vol = rr.std()*np.sqrt(250)*100
    return {"n":n,"ann":ann,"vol":vol,"sharpe":ann/vol if vol else np.nan,
            "mdd":(eq/eq.cummax()-1).min()*100,"skew":rr.skew()}
