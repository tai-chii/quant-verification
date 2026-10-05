# -*- coding: utf-8 -*-
"""朝入り・±0.5円ブラケット・夕/夜クローズ という執行構造だけを検証する。

目的: 「方向シグナルが何%当たれば損益分岐するか」を先に数字で出す。
方向の中身（銀行の見通し等）はまだ測れないが、器の性質は今すぐ測れる。

設計:
- データ: Dukascopy M15（時刻はUTC。JST = UTC+9）
- エントリー: 指定時刻(JST)の足の始値
- 利確/損切: エントリー ± 0.5円（対称ブラケット）
- 時間切れ: 指定時刻(JST)の足の終値で強制決済
- 同一足内でTPとSLの両水準に触れた場合は **SL優先**（保守的仮定）
- コスト: 往復 0.3銭 = 0.003円

決定的（乱数なし）。同じCSVで同じ結果。
"""
import os, sys
import pandas as pd, numpy as np

CSV = os.path.expanduser("~/mnt/ワークスペース/vault/40_市場/FX/システムトレード/data_USDJPY_M15_dukascopy.csv")
BRACKET = 0.50      # 円
COST = 0.003        # 円（往復）
ENTRY_JST = 9       # 朝の定時
EXIT_JST_LIST = [15, 17, 21, 23]   # 夜の定時（複数比較）


def load():
    df = pd.read_csv(CSV, parse_dates=["time"]).sort_values("time")
    df["jst"] = df["time"] + pd.Timedelta(hours=9)
    df["day"] = df["jst"].dt.normalize()
    return df


def simulate(df, entry_h, exit_h):
    """1日1トレード。long/short 両方の結果を返す。"""
    rows = []
    for day, g in df.groupby("day", sort=True):
        g = g[(g["jst"].dt.hour >= entry_h) & (g["jst"].dt.hour < exit_h)]
        if len(g) < 4:
            continue
        first = g.iloc[0]
        if first["jst"].hour != entry_h:      # その日の寄りが無い（休場明け等）
            continue
        entry = float(first["open"])
        last_close = float(g.iloc[-1]["close"])
        hi, lo = g["high"].values, g["low"].values

        rec = {"day": day, "entry": entry, "close": last_close,
               "range": float(g["high"].max() - g["low"].min())}

        for side in ("long", "short"):
            sgn = 1 if side == "long" else -1
            tp = entry + sgn * BRACKET
            sl = entry - sgn * BRACKET
            out, why = None, "time"
            for i in range(len(hi)):
                hit_tp = hi[i] >= tp if sgn > 0 else lo[i] <= tp
                hit_sl = lo[i] <= sl if sgn > 0 else hi[i] >= sl
                if hit_tp and hit_sl:
                    out, why = -BRACKET, "both"      # 保守的にSL優先
                    break
                if hit_sl:
                    out, why = -BRACKET, "sl"
                    break
                if hit_tp:
                    out, why = +BRACKET, "tp"
                    break
            if out is None:
                out = sgn * (last_close - entry)
            rec[f"R_{side}"] = out - COST
            rec[f"why_{side}"] = why
        # 両水準に到達したか（経路依存で勝敗が決まる日）
        rec["both_touch"] = bool((hi.max() >= entry + BRACKET) and (lo.min() <= entry - BRACKET))
        rec["real_dir"] = "long" if last_close > entry else "short"
        rows.append(rec)
    return pd.DataFrame(rows)


def summarize(t, entry_h, exit_h):
    n = len(t)
    L = []
    L.append(f"## エントリー {entry_h}:00 JST → 決済 {exit_h}:00 JST  (n={n}営業日)")
    L.append("")
    both = t["both_touch"].mean() * 100
    L.append(f"- **両水準タッチ率 {both:.1f}%** … 上下0.5円の両方に到達した日。"
             f"どちらが先かは経路依存で、方向予測とほぼ無関係")
    # 方向は合っていたのにSLで刈られた割合
    hit_sl_though_right = (
        ((t["real_dir"] == "long") & (t["why_long"].isin(["sl", "both"]))) |
        ((t["real_dir"] == "short") & (t["why_short"].isin(["sl", "both"])))
    ).mean() * 100
    L.append(f"- **方向は当たっていたのに損切りされた日 {hit_sl_though_right:.1f}%**")
    L.append("")
    L.append("| 戦略 | 平均損益(円) | 勝率 | TP | SL | 時間切れ |")
    L.append("|---|---|---|---|---|---|")
    for side in ("long", "short"):
        r = t[f"R_{side}"]
        w = t[f"why_{side}"]
        L.append(f'| 常に{"買い" if side=="long" else "売り"} | {r.mean():+.4f} | '
                 f'{(r>0).mean()*100:.1f}% | {(w=="tp").mean()*100:.0f}% | '
                 f'{w.isin(["sl","both"]).mean()*100:.0f}% | {(w=="time").mean()*100:.0f}% |')
    rnd = (t["R_long"] + t["R_short"]) / 2
    best = t[["R_long", "R_short"]].max(axis=1)
    worst = t[["R_long", "R_short"]].min(axis=1)
    L.append(f'| ランダム方向 | {rnd.mean():+.4f} | - | - | - | - |')
    L.append(f'| 完全予知（上限） | {best.mean():+.4f} | - | - | - | - |')
    L.append("")
    eb, ew = best.mean(), worst.mean()
    if eb > ew:
        p = -ew / (eb - ew) * 100
        L.append(f"**損益分岐に必要な方向的中率: {p:.1f}%**")
        L.append(f"（当たった日 {eb:+.3f}円 / 外した日 {ew:+.3f}円 から逆算）")
    L.append("")
    return "\n".join(L), {"exit": exit_h, "n": n, "both": both,
                          "ev_long": t["R_long"].mean(), "ev_rand": rnd.mean(),
                          "p_be": p if eb > ew else float("nan")}


if __name__ == "__main__":
    df = load()
    out = ["# 朝入り・±0.5円ブラケット・夜クローズ の構造検証", "",
           f"データ: USDJPY M15 (Dukascopy) {df['jst'].min().date()} 〜 {df['jst'].max().date()}",
           f"ブラケット ±{BRACKET}円 / 往復コスト {COST}円 / 同一足内の両触れはSL優先（保守的）", ""]
    summ = []
    for ex in EXIT_JST_LIST:
        t = simulate(df, ENTRY_JST, ex)
        txt, s = summarize(t, ENTRY_JST, ex)
        out.append(txt)
        summ.append(s)
        t.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "output", f"trades_{ENTRY_JST}_{ex}.csv"), index=False)
    print("\n".join(out))
