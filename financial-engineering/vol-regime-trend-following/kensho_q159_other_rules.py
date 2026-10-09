#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q159: トレンド7 の「高ボラ日に順張りが弱い」事後発見を別の規則・別の窓で確認
================================================================================

【背景】
Q142（2026-10-09）で、トレンド7（商品4銘柄・株価指数2銘柄・BTCUSD）に TSMOM20・実現ボラ20日の
組み合わせで試したところ、合算の純損益の差（高−安定）は 全期間 −5.94bp/日（t=−3.29・z=−2.40）
で、的中率の差 z=−4.16 と大きく出た（results/Q142_result_20261009_174900.json）。
ただし半期で見ると前半 −3.85（t=−1.74・z=−1.08）・後半 −7.28（t=−2.95・z=−2.20）で前半は
事前判定条件に届かず、群と条件を1つに固定したので事後の記述扱いになった（Q142 判定: 棄却）。
Q159 は、この事後発見を 2規則（ドンチャン55/20・TSMOM60）× 2窓（10日・60日）＝ 4通りで独立に
確かめ、群・銘柄の切り分けではなく「規則と窓を変えても同じ向きに出るか」を測る。

【仮説（測る前に固定）】
H: トレンド7（最大7銘柄・BTCUSD は 2017 以降しか無く後半のみ）では、高ボラ局面（翌日ラベルは L_t）での
   順張りの純損益と的中率が、安定局面より低い。4通り（規則×窓）のうち過半数で下に出れば確認。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）
TREND7 = XAUUSD, XAGUSD, WTI, UKOIL, US500, USTECH, BTCUSD。無いファイルは除いて JSON に記録。

【規則（1通りに固定・コスト段階1 の片道 COST_RT/2 を bp で引く）】
- RULE-TSMOM60: s_t = sign(c_t − c_{t−60})。翌日 t+1 のポジション。LOOKBACK=60。
- RULE-DON55/20: 終値が直前55日高値を上抜けで買い、直前20日安値を下抜けで手仕舞い（売りは対称）。
  Q152 と同じ `donchian_positions` を再利用。LOOKBACK=55。損切りなし。

【ボラ局面（1通りに固定）】
日次対数リターン r_t、v_t(W) = r_{t−W+1..t} の標準偏差（ddof=1、W∈{10,60}）。
L_t = 「高」 if v_t > median(v_1..v_{t−1})（その銘柄の拡大窓の中央値・t を含まない・MIN_HIST=60）。
翌日 t+1 の損益に対応する局面は L_t。GARCH は使わない（Q142 と同じ）。

【測るもの】
銘柄×期間ごとの表 と、トレンド7 合算の 的中率 と 純損益（bp/日）。差 = 高 − 安定。
- 合算の差の t: 半年を単位。
- 帰無: 各銘柄の局面ラベルを月ブロックごとに並べ替え（損益固定・規則固定）B=500 回、SEED 固定。
- 期間: 前半 2008〜2016 ／ 後半 2017〜2026。合算（全期間）も参考に出す。

【判定（事前固定・変更禁止）】
各通り（2規則×2窓＝4）について:
  C1: 前後半で pnl_diff が同符号（0 除く）。
  C2: |pnl_diff_half_t| ≥ 2 が 前後半の両方で満たされる。
  C3: |pnl_diff_z| ≥ 2 が 前後半の両方で満たされる。
C1〜C3 すべて満たす通りを「通過」。
- 「確認（支持）」= 通過 ≥ 3 / 4
- 「部分支持」= 通過 1〜2 / 4、かつ 全期間 合算で 4通りのうち過半数で負＆|z|≥2
- 「棄却」= 通過 0 / 4、かつ 全期間 合算で負＆|z|≥2 が 2通り未満
- それ以外は「未確定」

的中率の差は記述。多重比較: 4通り × 2期間（判定）＝ 8。全期間は参考として併記。

【捨てた案の数】
約5: TSMOM12（短すぎて TSMOM20 と重複）／ドンチャン20/5（短期・コストに敵わない）／
GARCH で局面を分ける（scipy 依存で再現性が低い）／3値（高・中・低）の局面（判定が2値でない）／
FX8・全15 も混ぜる（Q159 の目的は TREND7 単体の事後発見の確認）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで（BTCUSD は 2017-05 から）。
後半には知識の圏内の相場が多く、後知恵の懸念は残る。ただし規則と窓は 4通りに固定し、
局面ラベルは拡大窓の中央値で機械的に付ける。

【委託の確かめ方】
設計・コード・実行・解釈はいずれも Opus（claude-opus-4-7）。結果 JSON の主要な数値（通過数・
各通りの pnl_diff・t・z）を本体の報告に書き、Q142 の数値と比べて記録する。

【実装】自己完結・決定的（乱数は SEED 固定のラベル並べ替えだけ）。依存: python3 + numpy/pandas。
事前登録からの変更点: なし。
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

TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
# 段階1の保守的な往復コスト（価格単位）。片道はこの半分。Q142・Q152 と同じ値。
COST_RT = {"XAUUSD": 0.6, "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06,
           "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

VOL_WINS = (10, 60)        # 事前登録の 2 窓
MIN_HIST = 60
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261010
QID = "Q159"

# 規則
TSMOM_LOOKBACK = 60
DON_ENTRY, DON_EXIT = 55, 20


# ----------------------------------------------------------------------------- 道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    return float(z), float((v < obs).mean())


def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def tsmom_positions(c, lb=TSMOM_LOOKBACK):
    n = len(c); s = np.zeros(n)
    s[lb:] = np.sign(c[lb:] - c[:-lb])
    return s


def donchian_positions(c):
    """Q152 と同じ: 終値が直前55日高値を上抜けで買い、直前20日安値を下抜けで手仕舞い（売りは対称）。損切りなし。"""
    n = len(c); pos = np.zeros(n)
    cs = pd.Series(c)
    hiE = cs.rolling(DON_ENTRY).max().shift(1).values
    loE = cs.rolling(DON_ENTRY).min().shift(1).values
    hiX = cs.rolling(DON_EXIT).max().shift(1).values
    loX = cs.rolling(DON_EXIT).min().shift(1).values
    p = 0
    for i in range(n):
        if p == 1 and np.isfinite(loX[i]) and c[i] < loX[i]:
            p = 0
        elif p == -1 and np.isfinite(hiX[i]) and c[i] > hiX[i]:
            p = 0
        if p == 0:
            if np.isfinite(hiE[i]) and c[i] > hiE[i]:
                p = 1
            elif np.isfinite(loE[i]) and c[i] < loE[i]:
                p = -1
        pos[i] = p
    return pos


RULES = {"TSMOM60": tsmom_positions, "DON55_20": donchian_positions}
RULE_WARMUP = {"TSMOM60": TSMOM_LOOKBACK, "DON55_20": DON_ENTRY}


def daily_net_pnl_bp(c, signal, cost_rt, warmup):
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:warmup + 1] = 0.0
    return pnl, pos_prev, ret


def expanding_median_prev(v):
    s = pd.Series(v)
    return s.expanding(min_periods=MIN_HIST).median().shift(1).values


# ----------------------------------------------------------------------------- 1銘柄×規則×窓 の表
def symbol_table(sym, t, c, rule, vol_win):
    n = len(c)
    r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
    vol = pd.Series(r).rolling(vol_win).std(ddof=1).values.copy()
    vol[:vol_win] = np.nan
    med = expanding_median_prev(vol)
    lab_t = np.where(np.isfinite(vol) & np.isfinite(med), (vol > med).astype(float), np.nan)
    regime = np.concatenate([[np.nan], lab_t[:-1]])
    pos = RULES[rule](c)
    warmup = RULE_WARMUP[rule]
    pnl, pos_prev, ret = daily_net_pnl_bp(c, pos, COST_RT[sym], warmup)
    hit = np.where((pos_prev != 0) & (ret != 0), (pos_prev * ret > 0).astype(float), np.nan)
    valid = np.arange(n) > max(warmup, vol_win)
    hit[~valid] = np.nan
    ts = pd.Series(t)
    ym = ts.dt.year.values * 100 + ts.dt.month.values
    hy = ts.dt.year.values * 10 + np.where(ts.dt.month.values <= 6, 1, 2)
    df = pd.DataFrame(dict(sym=sym, date=t, year=ts.dt.year.values, month_id=ym, half_id=hy,
                           pnl=pnl, hit=hit, regime=regime, pos=pos_prev, valid=valid))
    df = df[df.valid & np.isfinite(df.regime)].reset_index(drop=True)
    return df


def permute_regime_by_month(df, rng):
    months = df.month_id.values
    uniq, start = np.unique(months, return_index=True)
    order = np.argsort(start)
    blocks = np.split(df.regime.values, start[order][1:])
    perm = rng.permutation(len(blocks))
    return np.concatenate([blocks[i] for i in perm])


def pooled_diff(pnl, hit, reg):
    hi = reg == 1; lo = reg == 0
    out = dict(n_high=int(hi.sum()), n_stable=int(lo.sum()))
    out["pnl_high"] = float(pnl[hi].mean()) if hi.any() else float("nan")
    out["pnl_stable"] = float(pnl[lo].mean()) if lo.any() else float("nan")
    out["pnl_diff"] = out["pnl_high"] - out["pnl_stable"]
    hh = hit[hi]; hl = hit[lo]
    out["hit_high"] = float(np.nanmean(hh)) if np.isfinite(hh).any() else float("nan")
    out["hit_stable"] = float(np.nanmean(hl)) if np.isfinite(hl).any() else float("nan")
    out["hit_diff"] = out["hit_high"] - out["hit_stable"]
    return out


def stats_for(tab, syms, period, reg_col="regime"):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    pnl = g.pnl.values; hit = g.hit.values; reg = g[reg_col].values
    out = pooled_diff(pnl, hit, reg)
    out["n_days"] = int(len(g))
    out["n_syms"] = int(g.sym.nunique())
    diffs = []; hdiffs = []
    for _, gb in g.groupby("half_id"):
        rb = gb[reg_col].values
        if (rb == 1).sum() >= 3 and (rb == 0).sum() >= 3:
            d = pooled_diff(gb.pnl.values, gb.hit.values, rb)
            diffs.append(d["pnl_diff"]); hdiffs.append(d["hit_diff"])
    m, tt, n = mean_t(diffs)
    out["pnl_diff_half_mean"] = m; out["pnl_diff_half_t"] = tt; out["pnl_diff_half_n"] = n
    m, tt, _ = mean_t(hdiffs)
    out["hit_diff_half_mean"] = m; out["hit_diff_half_t"] = tt
    return out


def judge(res_by_combo):
    """4通り（規則×窓）の 前後半通過を数える。"""
    def fin(x): return x is not None and np.isfinite(x)
    passes = {}
    halfperiod_hits = {"前半": 0, "後半": 0}
    allperiod_neg_signif = 0
    for combo, res in res_by_combo.items():
        r1 = res["前半"]; r2 = res["後半"]
        rA = res["全期間"]
        same_sign = (fin(r1["pnl_diff"]) and fin(r2["pnl_diff"]) and
                     np.sign(r1["pnl_diff"]) == np.sign(r2["pnl_diff"]) and r1["pnl_diff"] != 0)
        c1_sign_neg = same_sign and r1["pnl_diff"] < 0
        c2_t = fin(r1["pnl_diff_half_t"]) and fin(r2["pnl_diff_half_t"]) and \
            abs(r1["pnl_diff_half_t"]) >= 2.0 and abs(r2["pnl_diff_half_t"]) >= 2.0
        c3_z = fin(r1["pnl_diff_z"]) and fin(r2["pnl_diff_z"]) and \
            abs(r1["pnl_diff_z"]) >= 2.0 and abs(r2["pnl_diff_z"]) >= 2.0
        passed = bool(same_sign and r1["pnl_diff"] < 0 and r2["pnl_diff"] < 0 and c2_t and c3_z)
        passes[combo] = dict(
            前半=dict(pnl_diff=r1["pnl_diff"], t=r1["pnl_diff_half_t"], z=r1["pnl_diff_z"]),
            後半=dict(pnl_diff=r2["pnl_diff"], t=r2["pnl_diff_half_t"], z=r2["pnl_diff_z"]),
            全期間=dict(pnl_diff=rA["pnl_diff"], t=rA["pnl_diff_half_t"], z=rA["pnl_diff_z"]),
            same_sign_neg=bool(c1_sign_neg), both_abs_t_ge2=bool(c2_t), both_abs_z_ge2=bool(c3_z),
            passed=passed,
        )
        if fin(r1["pnl_diff_z"]) and r1["pnl_diff"] < 0 and abs(r1["pnl_diff_z"]) >= 2.0:
            halfperiod_hits["前半"] += 1
        if fin(r2["pnl_diff_z"]) and r2["pnl_diff"] < 0 and abs(r2["pnl_diff_z"]) >= 2.0:
            halfperiod_hits["後半"] += 1
        if fin(rA["pnl_diff_z"]) and rA["pnl_diff"] < 0 and abs(rA["pnl_diff_z"]) >= 2.0:
            allperiod_neg_signif += 1
    n_pass = sum(1 for v in passes.values() if v["passed"])
    if n_pass >= 3:
        verdict = "確認（支持）"
    elif n_pass >= 1 and allperiod_neg_signif >= 3:
        verdict = "部分支持"
    elif n_pass == 0 and allperiod_neg_signif < 2:
        verdict = "棄却"
    else:
        verdict = "未確定"
    return dict(by_combo=passes, n_pass_strict=int(n_pass),
                n_halfperiod_neg_signif=halfperiod_hits,
                n_allperiod_neg_signif=int(allperiod_neg_signif),
                rule="4通り（2規則×2窓）について『前後半とも符号が負・|t|≥2・|z|≥2』をすべて満たせば通過。通過数で判定",
                verdict=verdict)


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    series = {}; missing = []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(TREND7):
            phi = 0.0 + 0.3 * (k / (len(TREND7) - 1))
            n = len(dates); e = g.normal(0, 0.006, n)
            scale = np.exp(0.5 * np.sin(np.arange(n) / 120.0 + k))
            e = e * scale
            r = np.zeros(n)
            for i in range(1, n):
                r[i] = phi * r[i - 1] + e[i]
            base = {"XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65, "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.0)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 10)
    else:
        for sym in TREND7:
            d = load_daily(sym)
            if d is None or len(d) < 300:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    syms_used = list(series.keys())

    combos = [(rule, w) for rule in RULES for w in VOL_WINS]
    periods = ["前半", "後半", "全期間"]
    res_by_combo = {}
    per_sym_rows = []
    for rule, w in combos:
        combo_key = f"{rule}|vol{w}"
        tabs = {sym: symbol_table(sym, t, c, rule, w) for sym, (t, c) in series.items()}
        tab = pd.concat(tabs.values(), ignore_index=True)
        res = {p: stats_for(tab, syms_used, p) for p in periods}
        null_vals = {p: {"pnl_diff": [], "hit_diff": [], "pnl_diff_half_t": []} for p in periods}
        for b in range(B):
            tab["regime_null"] = np.concatenate([permute_regime_by_month(tabs[s], rng) for s in syms_used])
            for p in periods:
                s = stats_for(tab, syms_used, p, reg_col="regime_null")
                for key in null_vals[p]:
                    null_vals[p][key].append(s[key])
        for p in periods:
            res[p]["pnl_diff_z"], res[p]["pnl_diff_pct"] = z_against_null(res[p]["pnl_diff"], null_vals[p]["pnl_diff"])
            res[p]["hit_diff_z"], res[p]["hit_diff_pct"] = z_against_null(res[p]["hit_diff"], null_vals[p]["hit_diff"])
            res[p]["null_pnl_diff_mean"] = float(np.nanmean(null_vals[p]["pnl_diff"])) if B else float("nan")
            res[p]["null_pnl_diff_sd"] = float(np.nanstd(null_vals[p]["pnl_diff"], ddof=1)) if B > 1 else float("nan")
        res_by_combo[combo_key] = res
        for sym in syms_used:
            for p in periods:
                s = stats_for(tab, [sym], p)
                per_sym_rows.append(dict(combo=combo_key, sym=sym, period=p,
                                         n_days=s["n_days"], n_high=s["n_high"], n_stable=s["n_stable"],
                                         pnl_high=s["pnl_high"], pnl_stable=s["pnl_stable"], pnl_diff=s["pnl_diff"],
                                         pnl_diff_half_t=s["pnl_diff_half_t"],
                                         hit_high=s["hit_high"], hit_stable=s["hit_stable"],
                                         hit_diff=s["hit_diff"], hit_diff_half_t=s["hit_diff_half_t"]))
    per_sym = pd.DataFrame(per_sym_rows)
    verdict = judge(res_by_combo)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_per_symbol_{stamp}.csv")
    per_sym.to_csv(csv_path, index=False)

    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(VOL_WINS=list(VOL_WINS), MIN_HIST=MIN_HIST, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, TSMOM_LOOKBACK=TSMOM_LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT,
                      syms=syms_used, missing_syms=missing, n_missing=len(missing), data_dir=DATA_DIR,
                      regime_def="各窓の実現ボラ > その銘柄の拡大窓の中央値（t を含まない・GARCH 不使用）",
                      null_def="局面ラベルを月ブロックで並べ替え（損益・ポジション固定）"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()),
                           end=str(pd.Timestamp(series[s][0][-1]).date()), n=int(len(series[s][1]))) for s in series},
        combos=[f"{r}|vol{w}" for r, w in combos],
        results=res_by_combo, judgement=verdict,
        files=dict(per_symbol_csv=csv_path),
        multiple_comparisons="2規則 × 2窓 = 4通り。前後半2期間で判定 → 8本の判定。全期間（4本）は参考",
        reference=dict(parent_queue="Q142", parent_post_hoc_trend7_all_pnl_diff_bp=-5.94,
                       parent_post_hoc_trend7_all_t_half=-3.29, parent_post_hoc_trend7_all_z=-2.40),
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(syms_used)} missing={missing} B={B} smoke={args.smoke} elapsed={elapsed:.1f}s")
    for combo in [f"{r}|vol{w}" for r, w in combos]:
        print(f"  [{combo}]")
        for p in periods:
            r = res_by_combo[combo][p]
            print(f"    {p:3s} n={r['n_days']:6d} hi/lo={r['n_high']}/{r['n_stable']}  "
                  f"pnl 高={r['pnl_high']:+.2f} 安定={r['pnl_stable']:+.2f} 差={r['pnl_diff']:+.2f}bp  "
                  f"t(半年)={r['pnl_diff_half_t']:+.2f} z={r['pnl_diff_z']:+.2f}  "
                  f"hit 差={r['hit_diff']:+.3f} z={r['hit_diff_z']:+.2f}")
    print(f"  通過: {verdict['n_pass_strict']}/4   全期間負＆|z|≥2: {verdict['n_allperiod_neg_signif']}/4")
    print(f"  判定(機械): {verdict['verdict']}")
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
