# -*- coding: utf-8 -*-
"""ブラケット幅・スリッページ・ロット正規化の感度を測る。

bracket_daytrade.py の続き。器の細部が結論をどれだけ動かすかを確認する。
先読み防止: ATRは「前日までの」日足から計算する。
決定的（乱数なし）。
"""
import os
import pandas as pd, numpy as np

CSV = os.path.expanduser("~/mnt/ワークスペース/vault/40_市場/FX/システムトレード/data_USDJPY_M15_dukascopy.csv")
ENTRY_JST, EXIT_JST = 9, 23
COST = 0.003


def load():
    df = pd.read_csv(CSV, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df["day"] = df["jst"].dt.normalize()
    return df


def daily_atr(df, n=20):
    """日足ATR。shift(1)で前日までの情報のみ使う（先読み防止）。"""
    d = df.set_index("jst").resample("1D").agg(
        h=("high", "max"), l=("low", "min"), c=("close", "last")).dropna()
    pc = d["c"].shift(1)
    tr = pd.concat([d["h"] - d["l"], (d["h"] - pc).abs(), (d["l"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().shift(1)          # ← shift(1) が要


def sessions(df):
    out = []
    for day, g in df.groupby("day", sort=True):
        g = g[(g["jst"].dt.hour >= ENTRY_JST) & (g["jst"].dt.hour < EXIT_JST)]
        if len(g) < 4 or g.iloc[0]["jst"].hour != ENTRY_JST:
            continue
        out.append((day, float(g.iloc[0]["open"]), float(g.iloc[-1]["close"]),
                    g["high"].values, g["low"].values))
    return out


def run(sess, width_fn, slip=0.0):
    """slip: SL約定を不利側にずらす幅（円）。TPは指値なので滑らない前提。"""
    rows = []
    for day, entry, lastc, hi, lo in sess:
        W = width_fn(day, entry)
        if W is None or not np.isfinite(W) or W <= 0:
            continue
        rec = {"day": day, "W": W, "entry": entry}
        for side in ("long", "short"):
            s = 1 if side == "long" else -1
            tp, sl = entry + s * W, entry - s * W
            out, why = None, "time"
            for i in range(len(hi)):
                htp = hi[i] >= tp if s > 0 else lo[i] <= tp
                hsl = lo[i] <= sl if s > 0 else hi[i] >= sl
                if hsl or (htp and hsl):
                    out, why = -(W + slip), "sl"
                    break
                if htp:
                    out, why = +W, "tp"
                    break
            if out is None:
                out = s * (lastc - entry)
            rec[f"R_{side}"] = out - COST
            rec[f"why_{side}"] = why
        rec["both"] = bool(hi.max() >= entry + W and lo.min() <= entry - W)
        rec["up"] = lastc > entry
        rows.append(rec)
    t = pd.DataFrame(rows)
    best = t[["R_long", "R_short"]].max(axis=1)
    worst = t[["R_long", "R_short"]].min(axis=1)
    p_be = -worst.mean() / (best.mean() - worst.mean()) * 100
    return {"n": len(t), "W": t["W"].mean(), "both": t["both"].mean() * 100,
            "long": t["R_long"].mean(), "rand": ((t.R_long + t.R_short) / 2).mean(),
            "best": best.mean(), "worst": worst.mean(), "p_be": p_be,
            "tp": (t.why_long == "tp").mean() * 100, "sl": (t.why_long == "sl").mean() * 100,
            "time": (t.why_long == "time").mean() * 100, "t": t}


if __name__ == "__main__":
    df = load()
    atr = daily_atr(df)
    sess = sessions(df)
    print(f"n={len(sess)}営業日  {sess[0][0].date()} 〜 {sess[-1][0].date()}\n")

    print("## 1. ブラケット幅の感度（固定幅）\n")
    print("| 幅(円) | 両水準タッチ | TP | SL | 時間切れ | 常に買い | ランダム | 当たり | 外れ | 必要的中率 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for W in (0.15, 0.25, 0.35, 0.50, 0.75, 1.00, 1.50):
        r = run(sess, lambda d, e, W=W: W)
        print(f'| {W:.2f} | {r["both"]:.1f}% | {r["tp"]:.0f}% | {r["sl"]:.0f}% | {r["time"]:.0f}% | '
              f'{r["long"]:+.4f} | {r["rand"]:+.4f} | {r["best"]:+.3f} | {r["worst"]:+.3f} | '
              f'**{r["p_be"]:.1f}%** |')

    print("\n## 2. ATR連動の可変幅\n")
    print("| 幅 | 平均幅(円) | 両水準タッチ | 時間切れ | ランダム | 必要的中率 |")
    print("|---|---|---|---|---|---|")
    for k in (0.3, 0.5, 0.7, 1.0):
        r = run(sess, lambda d, e, k=k: atr.get(d, np.nan) * k)
        print(f'| {k}×ATR20 | {r["W"]:.3f} | {r["both"]:.1f}% | {r["time"]:.0f}% | '
              f'{r["rand"]:+.4f} | **{r["p_be"]:.1f}%** |')

    print("\n## 3. スリッページの影響（幅0.5円固定・SL約定を不利側にずらす）\n")
    print("| SLスリッページ | ランダム | 当たり | 外れ | 必要的中率 | 50.5%からの悪化 |")
    print("|---|---|---|---|---|---|")
    base = None
    for s in (0.0, 0.005, 0.010, 0.020, 0.050):
        r = run(sess, lambda d, e: 0.50, slip=s)
        if base is None:
            base = r["p_be"]
        print(f'| {s*100:.1f}銭 | {r["rand"]:+.4f} | {r["best"]:+.3f} | {r["worst"]:+.3f} | '
              f'**{r["p_be"]:.1f}%** | {r["p_be"]-base:+.1f}pt |')

    print("\n## 4. ロットをボラで正規化したときの検出力\n")
    r = run(sess, lambda d, e: 0.50)
    t = r["t"].copy()
    t["atr"] = t["day"].map(atr)
    t = t.dropna(subset=["atr"])
    fixed = t["R_long"]
    scaled = t["R_long"] / t["atr"] * t["atr"].mean()      # ボラ逆比例ロット
    print("『常に買い』を仮の方向シグナルに見立てて、固定ロットとボラ正規化ロットのt値を比べる。")
    print("（このシグナルの中身は円安ドリフト。エッジがボラに比例するかの確認が目的）\n")
    print("| ロット | n | 平均(円/日) | 標準偏差 | t値 |")
    print("|---|---|---|---|---|")
    for nm, v in (("固定ロット", fixed), ("ボラ正規化", scaled)):
        tv = v.mean() / (v.std() / np.sqrt(len(v)))
        print(f"| {nm} | {len(v)} | {v.mean():+.4f} | {v.std():.4f} | **{tv:+.2f}** |")
