#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q146: 並べ替え帰無の z は何回で安定するか（B と seed のぶれ。検証基盤の決まりを決めるため）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q146（Fable 2026-10-09）。
  検証/学問/金融工学/知識/文献/アイデア候補.md の同日の行。
- 論文ノート: Chen・Wang2026（繰り返し生成のぶれを誤差として数える）、
  Jedrzejewska・Drachal2026_RCtest（B=999 の推奨・Davidson & MacKinnon 2000）、_基盤/知識/検証方法論/改善判定。
- 題材: Q136 系と同じ帰無（銘柄 × 半年の組内で日次リターンを並べ替え）で、TSMOM20 の全15合算のドリフト除去後 t。

【仮説（測る前に固定）】
この検証は帰無分布そのものの性質（B と seed による z のぶれ）を測る。仮説の支持／棄却ではなく、基盤の既定値 B を決める。
参考の理論値: 帰無の平均と SD を B 個の標本から推定したときの z の標準誤差 ≈ √((1 + z²/2)/B)（正規近似）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄 = FX8 + トレンド7。2008-02〜2026-07。
値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- TSMOM20: s_t = sign(c_t − c_{t−20})、翌日 t+1 のポジション = s_t。
  日次純損益 [bp] = pos × (c_{t+1}/c_t − 1) × 1e4 − |Δpos| × 片道コスト（段階1 COST_RT/2 を価格で割って bp）。
- 組 g = 銘柄 × 暦の半年。ドリフト除去: pnl_adj_t = pnl_t − pos_t × μ_g × 1e4（μ_g = 組 g の日次単純リターンの平均）。
- 合算: マスター日付（全銘柄の日付の和集合）ごとに、その日に有効な銘柄の pnl_adj の平均 d_t。
  t_obs = mean(d) / (sd(d)/√n)（素の t。依存は帰無の側で扱う）。
- 帰無 1 回 = 各銘柄で組内の日次対数リターンを並べ替えて価格を作り直し、同じ手順で t を出す。
- z(B, seed) = (t_obs − mean(t_null[1..B])) / sd(t_null[1..B])。帰無の 97.5 パーセンタイル q975(B, seed) も記録。
- B ∈ {20, 50, 100, 200, 500, 1000} × seed 20 通り（seed = SEED + k）。
  実装: seed ごとに 1000 回の帰無を順に生成し、先頭 B 回で z を出す（入れ子）。seed 間は独立。
  各 B の計算時間 = 先頭 B 回を生成し終えた時点までの累積時間（seed ごとに記録し平均）。

【測るもの】
B ごとに: z の seed 間の平均と標準偏差 SD(z)、q975 の seed 間の SD、理論値 √((1+z̄²/2)/B)（z̄ は B=1000 の平均 z）、
実測 SD(z) / 理論値、計算時間（秒）。

【判定（事前固定・変更禁止）】
- SD(z) < 0.1 になる最小の B を「基盤の既定値」として提案（どの B でも満たさなければ「B=1000 でも 0.1 未満にならない」と記録）。
- B=500 で SD(z) ≥ 0.2 なら、既存の B=500 の判定（Q136 以降）の z は ±0.2 の幅を見込む、と記録。
- 理論値との比（実測/理論）を記述。多重比較: なし（記述の検証）。

【捨てた案の数】
約4: seed ごとに B を別々に生成する案（入れ子より 3.7 倍の計算で、推定量は同じ→入れ子）、
題材を Q136 の Spearman ρ にする案（組ごとの表の再計算が重い→合算 t）、月単位の組にする案（Q136 と揃える→半年）、
ブロック・ブートストラップとの比較（別の問い）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証は帰無分布の数値的な安定性の問いで、相場観は関係しない。

【委託の確かめ方】
設計は Fable（specs20.py）、コードは Claude（Fable 5.1 下請け、2026-10-09）、実行と解釈は Sonnet／Opus が後で行う。
実行者は結果 JSON のパス・主要な数値（B ごとの SD(z)・提案する B・理論値との比・時間）を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas。
実行: python3 kensho_permutation_null_stability_q146.py                 （B 最大 1000 × seed 20。数分〜十数分）
      python3 kensho_permutation_null_stability_q146.py --seeds 5       （軽い試走）
      python3 kensho_permutation_null_stability_q146.py --smoke         （合成データで経路の確認）
事前登録からの変更点: B × seed の帰無を「seed ごとに 1000 回生成し先頭 B 回を使う入れ子」で実装（推定量は同じ・計算量を減らすため）。
"""
import argparse
import datetime as _dt
import json
import math
import os
import time
import unicodedata

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))


def _p(*parts):
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")

FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20
B_LIST = [20, 50, 100, 200, 500, 1000]
N_SEEDS = 20
SEED = 20261009
QID = "Q146"


# ----------------------------------------------------------------------------- 道具
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def pnl_adj_from_logret(r, c0, cost_rt, gcode, ngroups):
    """対数リターン r（先頭 0）から価格を作り、TSMOM20 のドリフト除去後の日次純損益 [bp] を返す（先頭 LOOKBACK+1 日は 0）。"""
    c = c0 * np.exp(np.cumsum(r))
    n = len(c)
    sig = tsmom_positions(c)
    pos_prev = np.concatenate([[0.0], sig[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = pos_prev * ret * 1e4 - dpos * cost_bp
    # 組ごとの平均単純リターン（組内の日 t≥1）
    w = np.ones(n); w[0] = 0.0
    gs = np.bincount(gcode, weights=ret * w, minlength=ngroups); gn = np.bincount(gcode, weights=w, minlength=ngroups)
    mu = np.where(gn > 0, gs / np.where(gn > 0, gn, 1.0), 0.0)
    adj = pnl - pos_prev * mu[gcode] * 1e4
    adj[:LOOKBACK + 1] = 0.0
    return adj


class Pooled:
    """15銘柄をマスター日付に合算して t を出す。"""

    def __init__(self, series):
        self.master = np.unique(np.concatenate([np.asarray(t, "datetime64[ns]") for t, _ in series.values()]))
        T = len(self.master); self.T = T
        self.syms = list(series.keys())
        self.ix = {}; self.valid = {}; self.r = {}; self.c0 = {}; self.g = {}; self.ng = {}
        cnt = np.zeros(T)
        for sym, (t, c) in series.items():
            tt = np.asarray(t, "datetime64[ns]")
            ix = np.searchsorted(self.master, tt)
            v = np.arange(len(c)) > LOOKBACK
            self.ix[sym] = ix; self.valid[sym] = v
            r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
            self.r[sym] = r; self.c0[sym] = float(c[0])
            ts = pd.Series(tt)
            hid = ts.dt.year.values * 10 + np.where(ts.dt.month.values <= 6, 1, 2)
            codes, uniq = pd.factorize(hid)
            self.g[sym] = codes.astype(np.int64); self.ng[sym] = int(len(uniq))
            cnt[ix[v]] += 1
        self.cnt = cnt
        self.days = cnt > 0

    def t_stat(self, rs):
        """rs: {sym: 対数リターン列}。合算のドリフト除去後 t。"""
        acc = np.zeros(self.T)
        for sym in self.syms:
            adj = pnl_adj_from_logret(rs[sym], self.c0[sym], COST_RT[sym], self.g[sym], self.ng[sym])
            v = self.valid[sym]
            acc[self.ix[sym][v]] += adj[v]
        d = acc[self.days] / self.cnt[self.days]
        n = len(d); s = d.std(ddof=1)
        return float(d.mean() / (s / math.sqrt(n))) if s > 0 else float("nan")

    def permuted(self, rng):
        """組内で対数リターンを並べ替え（lexsort で1回）。"""
        out = {}
        for sym in self.syms:
            r = self.r[sym]; g = self.g[sym]
            keys = rng.random(len(r))
            keys[0] = -1.0                       # 先頭（r=0）は動かさない
            order = np.lexsort((keys, g))        # 組順→組内はランダム。組は時間順に連続
            out[sym] = r[order]
        return out


def theory_sd(zbar, B):
    return float(math.sqrt((1.0 + zbar ** 2 / 2.0) / B))


def judge(table, b_list):
    sd = {B: table[B]["sd_z"] for B in b_list}
    ok = [B for B in b_list if np.isfinite(sd[B]) and sd[B] < 0.1]
    proposed = int(min(ok)) if ok else None
    flag500 = bool(500 in sd and np.isfinite(sd[500]) and sd[500] >= 0.2)
    return dict(proposed_default_B=proposed,
                proposed_note=("SD(z)<0.1 になる最小の B" if proposed else f"B={max(b_list)} でも SD(z)<0.1 にならない"),
                B500_sd_z=sd.get(500), B500_sd_ge_0p2=flag500,
                B500_note=("既存の B=500 の判定の z は ±0.2 の幅を見込む" if flag500 else "B=500 の SD(z) は 0.2 未満"),
                rule="SD(z)<0.1 の最小 B を既定値として提案。B=500 で SD(z)≥0.2 なら ±0.2 の幅を記録。理論値 √((1+z²/2)/B) と比べる",
                note="事前固定の規則で機械的に付けた判定。基盤の決まり（既定 B）への反映は実行者と本体が決める。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=max(B_LIST), help="帰無の最大回数（B_LIST のうちこれ以下を使う）")
    ap.add_argument("--seeds", type=int, default=N_SEEDS, help="seed の数")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    series = {}; missing = []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            n = len(dates); e = g.normal(0, 0.006, n); r = np.zeros(n)
            for i in range(1, n):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            keep = g.random(n) > 0.03
            series[sym] = (dates.values[keep], (base * np.exp(np.cumsum(r)))[keep])
        b_list = [5, 10]; n_seeds = min(args.seeds, 3)
    else:
        for sym in SYMS:
            d = load_daily(sym)
            if d is None or len(d) < 300:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        b_list = [B for B in B_LIST if B <= args.B] or [args.B]; n_seeds = args.seeds
    Bmax = max(b_list)
    pooled = Pooled(series)
    t_obs = pooled.t_stat(pooled.r)

    # seed ごとに Bmax 回を順に生成し、先頭 B 回で z・q975・累積時間
    per_seed = []
    for k in range(n_seeds):
        rng = np.random.default_rng(SEED + k)
        tn = np.empty(Bmax); times = {}
        ts = time.time()
        for b in range(Bmax):
            tn[b] = pooled.t_stat(pooled.permuted(rng))
            if (b + 1) in b_list:
                times[b + 1] = time.time() - ts
        row = dict(seed=SEED + k)
        for B in b_list:
            v = tn[:B]; sd = v.std(ddof=1)
            row[f"z_B{B}"] = float((t_obs - v.mean()) / sd) if sd > 0 else float("nan")
            row[f"q975_B{B}"] = float(np.percentile(v, 97.5))
            row[f"null_mean_B{B}"] = float(v.mean()); row[f"null_sd_B{B}"] = float(sd)
            row[f"time_B{B}"] = float(times[B])
        per_seed.append(row)
        print(f"  seed {k + 1}/{n_seeds} done ({time.time() - ts:.1f}s)  z@B{Bmax}={row[f'z_B{Bmax}']:+.3f}")
    ps = pd.DataFrame(per_seed)
    zbar = float(ps[f"z_B{Bmax}"].mean())
    table = {}
    for B in b_list:
        z = ps[f"z_B{B}"].values; q = ps[f"q975_B{B}"].values
        sd_z = float(z.std(ddof=1)) if len(z) > 1 else float("nan")
        th = theory_sd(zbar, B)
        table[B] = dict(B=B, n_seeds=int(len(z)), mean_z=float(z.mean()), sd_z=sd_z, min_z=float(z.min()), max_z=float(z.max()),
                        sd_q975=float(q.std(ddof=1)) if len(q) > 1 else float("nan"), mean_q975=float(q.mean()),
                        theory_sd_z=th, ratio_sd_to_theory=float(sd_z / th) if th > 0 and np.isfinite(sd_z) else float("nan"),
                        time_sec_mean=float(ps[f"time_B{B}"].mean()))
    verdict = judge(table, b_list)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_per_seed_{stamp}.csv"); ps.to_csv(csv_path, index=False)
    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(LOOKBACK=LOOKBACK, B_LIST=b_list, N_SEEDS=n_seeds, SEED=SEED, COST_RT=COST_RT, syms=list(series.keys()),
                      missing_syms=missing, n_missing=len(missing), data_dir=DATA_DIR,
                      stat="TSMOM20 全合算のドリフト除去後 t（組=銘柄×半年、組内並べ替え）", nested="seed ごとに Bmax 回生成し先頭 B 回を使う"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        t_obs=t_obs, zbar_Bmax=zbar, results={f"B{B}": v for B, v in table.items()}, judgement=verdict,
        files=dict(per_seed_csv=csv_path), multiple_comparisons="なし（記述の検証）",
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(series)} missing={missing} seeds={n_seeds} B_LIST={b_list} smoke={args.smoke} elapsed={elapsed:.1f}s  t_obs={t_obs:+.3f}")
    for B, v in table.items():
        print(f"  B={B:5d}  z̄={v['mean_z']:+.3f}  SD(z)={v['sd_z']:.3f}  理論={v['theory_sd_z']:.3f}  比={v['ratio_sd_to_theory']:.2f}  "
              f"SD(q975)={v['sd_q975']:.3f}  time={v['time_sec_mean']:.1f}s")
    print("  判定(機械):", verdict["proposed_default_B"], verdict["proposed_note"], "|", verdict["B500_note"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
