# -*- coding: utf-8 -*-
"""定時エントリー→翌日同時刻クローズ→即ロール（24時間保有・常時ポジション）。

日計り版(carry_multipair.py)との違い:
- ロールオーバーをまたぐので **スワップが付く**
- 深夜〜早朝のドリフトも取れる
- 代わりに常時エクスポージャーを持つため、クラッシュリスクをまともに受ける

スワップは概算（金利差 − 業者マークアップ）/365。実額は業者ごとに違うので要確認。
決定的。先読みなし（ATRは shift(1)、金利は当日時点の公表値）。
"""
import os
import pandas as pd, numpy as np

DIR = os.path.expanduser("~/mnt/ワークスペース/検証/学問/金融工学/作業/FX/システムトレード")
ENTRY_JST = 9
MARKUP = 0.7          # スワップの業者マークアップ（年率%）。0.0〜1.0で感度を見る
PAIRS = ["USDJPY","EURJPY","GBPJPY","EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF"]
COST_PCT = 0.002/100  # 往復スプレッド（ロールしない場合は建て替え不要だが保守的に毎日計上）


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
# ※ 政策金利は概算のステップ関数。符号だけを使う設計。2025〜2026の水準は不確実。

_RCACHE = {}
def rate_at(cur, ts):
    """金利のステップ関数。日付キーでキャッシュして高速化。"""
    k = (cur, ts)
    v = _RCACHE.get(k)
    if v is not None: return v
    v = np.nan
    for d, x in RATES[cur]:
        if ts >= pd.Timestamp(d): v = x
    _RCACHE[k] = v
    return v


def load(pair):
    p = f"{DIR}/data_{pair}_H1_dukascopy.csv"
    if not os.path.exists(p): return None
    df = pd.read_csv(p, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    return df


def atr20(df):
    d = df.set_index("jst").resample("1D").agg(h=("high","max"),l=("low","min"),c=("close","last")).dropna()
    pc = d.c.shift(1)
    tr = pd.concat([d.h-d.l,(d.h-pc).abs(),(d.l-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(20).mean().shift(1)


def run(pair, entry_h=ENTRY_JST, bracket_k=None, markup=MARKUP):
    df = load(pair)
    if df is None: return None
    base, quote = pair[:3], pair[3:]
    a = atr20(df)
    pos = np.flatnonzero((df.jst.dt.hour == entry_h).values)
    anchors = df.iloc[pos].reset_index(drop=True)
    idx = pos
    rows = []
    for i in range(len(anchors)-1):
        t0, t1 = anchors.jst[i], anchors.jst[i+1]
        gap_h = (t1-t0).total_seconds()/3600
        if gap_h > 80: continue                      # 長い休場は飛ばす
        seg = df.iloc[idx[i]:idx[i+1]+1]
        if len(seg) < 5: continue
        day = t0.normalize()
        diff = rate_at(base, day) - rate_at(quote, day)
        if not np.isfinite(diff) or diff == 0: continue
        s = 1 if diff > 0 else -1
        entry = float(seg.iloc[0].open); exitp = float(seg.iloc[-1].close)
        px_ret = s*(exitp-entry)/entry*100
        why = "time"
        if bracket_k:
            W = a.get(day, np.nan)*bracket_k
            if np.isfinite(W) and W > 0:
                tp, sl = entry+s*W, entry-s*W
                hi, lo = seg.high.values, seg.low.values
                for j in range(len(hi)):
                    htp = hi[j] >= tp if s>0 else lo[j] <= tp
                    hsl = lo[j] <= sl if s>0 else hi[j] >= sl
                    if hsl: px_ret, why = -W/entry*100, "sl"; break
                    if htp: px_ret, why = +W/entry*100, "tp"; break
        # スワップ: 保有日数ぶん（金利差 − マークアップ）/365
        days = max(1.0, gap_h/24)
        sw = max(0.0, abs(diff)-markup)/365*days
        rows.append({"day":day,"px":px_ret,"swap":sw,"R":px_ret+sw-COST_PCT*100,"why":why})
    return pd.DataFrame(rows)


def stats(t):
    r = t.R/100
    eq = (1+r).cumprod()
    dd = (eq/eq.cummax()-1).min()*100
    n = len(r)
    ann = (eq.iloc[-1]**(250/n)-1)*100
    vol = r.std()*np.sqrt(250)*100
    return {"n":n,"ann":ann,"vol":vol,"sharpe":ann/vol if vol else np.nan,
            "mdd":dd,"worst":r.min()*100,"skew":r.skew(),
            "px":t.px.mean()*250,"swap":t.swap.mean()*250}


if __name__ == "__main__":
    print(f"## 24時間保有・毎日ロール（{ENTRY_JST}:00 JST基準・キャリー方向）\n")
    print(f"スワップ = (金利差 − マークアップ{MARKUP}%)/365。実額は業者ごとに要確認。\n")
    print("| ペア | n | 年率 | うち価格 | うちスワップ | 年率ボラ | Sharpe | 最大DD | 最悪日 | 歪度 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    port = []
    for p in PAIRS:
        t = run(p)
        if t is None or len(t) < 100: continue
        s = stats(t); port.append(t.set_index("day").R.rename(p))
        print(f'| {p} | {s["n"]} | {s["ann"]:+.2f}% | {s["px"]:+.2f}% | {s["swap"]:+.2f}% | '
              f'{s["vol"]:.1f}% | {s["sharpe"]:+.2f} | {s["mdd"]:.1f}% | {s["worst"]:.2f}% | {s["skew"]:+.2f} |')
    pf = pd.concat(port, axis=1).mean(axis=1).dropna().to_frame("R")
    pf["px"]=0; pf["swap"]=0
    s = stats(pf)
    print(f'\n**8ペア等ウェイト分散: 年率 {s["ann"]:+.2f}% / ボラ {s["vol"]:.1f}% / '
          f'Sharpe {s["sharpe"]:+.2f} / 最大DD {s["mdd"]:.1f}% / 最悪日 {s["worst"]:.2f}% / 歪度 {s["skew"]:+.2f}**')
    h=len(pf)//2
    print(f'前半 年率{stats(pf.iloc[:h])["ann"]:+.2f}%  後半 年率{stats(pf.iloc[h:])["ann"]:+.2f}%')

    print("\n## ブラケットを付けた場合（USDJPY・24h保有）\n")
    print("| ブラケット | 年率 | 最大DD | 最悪日 | TP | SL | 時間切れ |")
    print("|---|---|---|---|---|---|---|")
    for k in (None,0.5,1.0,2.0,3.0):
        t = run("USDJPY", bracket_k=k)
        s = stats(t); w=t.why.value_counts(normalize=True)*100
        lab = "なし" if k is None else f"{k}×ATR20"
        print(f'| {lab} | {s["ann"]:+.2f}% | {s["mdd"]:.1f}% | {s["worst"]:.2f}% | '
              f'{w.get("tp",0):.0f}% | {w.get("sl",0):.0f}% | {w.get("time",0):.0f}% |')

    print("\n## エントリー時刻の感度（USDJPY・ブラケットなし）\n")
    print("| 時刻(JST) | 年率 | 最大DD |")
    print("|---|---|---|")
    for h in (0,3,6,7,9,12,15,18,21):
        t = run("USDJPY", entry_h=h)
        if t is None or len(t)<100: continue
        s = stats(t)
        print(f'| {h:02d}時 | {s["ann"]:+.2f}% | {s["mdd"]:.1f}% |')

    print("\n## スワップ・マークアップの感度（8ペア平均の年率）\n")
    for mk in (0.0,0.5,0.7,1.0,1.5):
        tot=[]
        for p in PAIRS:
            t=run(p,markup=mk)
            if t is not None and len(t)>=100: tot.append(stats(t)["ann"])
        print(f"  マークアップ{mk:.1f}% → 平均年率 {np.mean(tot):+.2f}%")
