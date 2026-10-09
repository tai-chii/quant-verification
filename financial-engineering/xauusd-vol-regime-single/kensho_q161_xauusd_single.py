#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q161: XAUUSD の日足順張りは直前20〜60日の実現ボラが高い日に翌日の損益が下がるか
================================================================================

【背景】
Q142（2026-10-09）でトレンド7 の TSMOM20・実現ボラ20日の組み合わせを試して半期の条件に届かず
棄却。事後の発見として、合算の pnl_diff の負は主に XAUUSD と（後半の）BTCUSD から来ていた。
Q159（2026-10-09）で 2規則×2窓＝4通りに広げたが、半期の |t|≥2・|z|≥2 の両方を事前基準に
したため「未確定」。XAUUSD 単銘柄で見ると、Q159 の per_symbol で 4通りすべて pnl_diff が負
（前後半も）だが |t|<2 で、群平均の判定からは漏れた（results/Q159_per_symbol_20261009_201840.csv）。

Q161 は、Q159 の中心銘柄＝XAUUSD 単銘柄で、ボラ窓を 20〜60 日の 3 本（20・40・60）に広げ、
さらに「ドリフト除去」（局面間で net 露出が違うことによる見かけ上の差を取り除く）後も
同じ向きが残るかを確かめる。前後半は補助、全期間 6通りが主の判定。

【仮説（測る前に固定）】
H: XAUUSD の日足順張り（TSMOM60・DON55/20）は、直前20〜60日の実現ボラが「高い」と機械的に
   ラベルづけされた日に、翌日の純損益（ドリフト除去後、bp/日）が「安定」の日より低い。
   6通り（2規則×3窓）の全期間について、過半数で pnl_adj_diff < 0 かつ |z| ≥ 2 なら確認。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_XAUUSD_D1_fromH1.csv（UTC 日足、2008-05〜2026-06、約4719本）

【規則（Q159 と同じ・1通りずつ固定）】
- RULE-TSMOM60: s_t = sign(c_t − c_{t−60})。翌日 t+1 のポジション。
- RULE-DON55/20: 終値が直前55日高値を上抜けで買い、直前20日安値を下抜けで手仕舞い（売りは対称）。
片道コスト段階1: XAUUSD は COST_RT=0.6 USD（Q142・Q152 と同じ）。片道は 0.3。

【ボラ局面】
日次対数リターン r_t、v_t(W) = r_{t−W+1..t} の標準偏差（ddof=1、W∈{20,40,60}）。
L_t = 高 if v_t > median(v_1..v_{t−1})（拡大窓の中央値、t を含まない、MIN_HIST=60）。
翌日 t+1 の損益に対応する局面は L_t（先読みなし）。GARCH は使わない（Q142・Q159 と同じ）。

【ドリフト除去（主の測定・2026-10-09 の FX 改善ログの教訓に合わせる）】
ドリフト（買い持ち分）= pos_prev[t] × μ_bp、μ_bp は銘柄の日次リターン平均（bp）を全期間で計算。
pnl_adj[t] = pnl[t] − pos_prev[t] × μ_bp。
注意: FX 改善ログ 2026-10-02(5) の失敗パターンでは「ドリフト除去は過大補正」との警告があったが、
Q161 では μ_bp を全期間平均で固定し、同じ μ_bp を 高・安定 両方に引く。局面間で mean(pos) が
違うことに由来する差を取り除くのが目的で、各局面内のドリフト差分は残す（並べ替え帰無も
同じ μ_bp を使うので対称）。

【帰無（Q159 と同じ・ラベル並べ替え）】
その銘柄の月ブロックごとに局面ラベルを並べ替え（損益・ポジションは固定）B=500 回、
z = (観測差 − 帰無平均) / 帰無 SD（符号は観測差の符号そのまま）。SEED 固定。
pnl_adj の帰無でも同じ pos_prev×μ_bp を同じ日に引く → 位置のドリフトはどの並べ替えでも等しい。

【測るもの】
銘柄×規則×窓×期間（前半 2008〜2016 ／ 後半 2017〜2026 ／ 全期間）ごと:
  pnl_high, pnl_stable, pnl_diff（bp/日）, pnl_adj_high, pnl_adj_stable, pnl_adj_diff,
  hit_high, hit_stable, hit_diff, pnl_diff_half_t, pnl_adj_diff_half_t（半年単位プール差）,
  pnl_diff_z, pnl_adj_diff_z（並べ替え帰無）.

【判定（事前固定・変更禁止）】
主の指標: 全期間の pnl_adj_diff と |z|（並べ替え帰無）。
6通り（2規則×3窓）について各通りを:
  通過（厳し）= 全期間 pnl_adj_diff < 0 かつ |z|≥2 かつ 前後半 pnl_adj_diff の符号が共に負。

さらに（補助の確認）:
  raw_通過 = 全期間 pnl_diff < 0 かつ |z|≥2 かつ 前後半 pnl_diff 両負。

総合判定:
  「確認（支持）」= 通過（厳し）が ≥ 5/6 かつ raw_通過 ≥ 4/6
  「部分支持」  = 通過（厳し）が 3〜4/6、かつ 全期間 pnl_adj_diff が負＆|z|≥1.5 が ≥ 4/6
  「棄却」      = 通過（厳し）が 0〜1/6、かつ 全期間 pnl_adj_diff が負＆|z|≥2 が < 2/6、
                かつ 全期間 raw でも負＆|z|≥2 が < 2/6
  それ以外       = 「未確定」

多重比較: 2規則 × 3窓 = 6通り（主）。全期間 raw/adj の 2 本と、前後半の 2 本 × 2 = 計 6 本/通り。
主判定は 全期間 adj 6本（補助に raw 6本と半期の符号）。

【捨てた案の数】
約4: ボラ窓を 5本以上（過剰）／FX8 を混ぜる（XAUUSD の確認目的から外れる）／
GARCH で局面を分ける（scipy 依存・Q142・Q159 と不整合）／3値（高・中・低）
の局面（判定が2値でない）.

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。後半（2017〜）には
知識の圏内の相場が多く、後知恵の懸念は残る。ただし XAUUSD 単銘柄の規則・窓・判定は
Q142 → Q159 → Q161 と事前登録を重ねており、Q161 で新しく選択の自由度が増えたのは
「窓を 20・40・60 の 3 本に広げる」部分のみ。

【委託の確かめ方】
設計・コード・実行・解釈はいずれも Opus（claude-opus-4-7）。Q159 の per_symbol と同じ 4通り
（TSMOM60|vol10・|vol60・DON55_20|vol10・|vol60）の数字と、Q161 の対応する 2通り（|vol40 は無い）
を本体の報告で比較して、整合を確かめる。

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

SYM = "XAUUSD"
COST_RT_XAU = 0.6  # Q142・Q152・Q159 と同じ

VOL_WINS = (20, 40, 60)  # 事前登録の 3 窓（20〜60）
MIN_HIST = 60
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261010
QID = "Q161"

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


# ----------------------------------------------------------------------------- 1規則×窓 の表（XAUUSD 単銘柄）
def build_table(t, c, rule, vol_win, mu_bp):
    n = len(c)
    r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
    vol = pd.Series(r).rolling(vol_win).std(ddof=1).values.copy()
    vol[:vol_win] = np.nan
    med = expanding_median_prev(vol)
    lab_t = np.where(np.isfinite(vol) & np.isfinite(med), (vol > med).astype(float), np.nan)
    regime = np.concatenate([[np.nan], lab_t[:-1]])  # 翌日 t+1 向け
    pos = RULES[rule](c)
    warmup = RULE_WARMUP[rule]
    pnl, pos_prev, ret = daily_net_pnl_bp(c, pos, COST_RT_XAU, warmup)
    pnl_adj = pnl - pos_prev * mu_bp  # ドリフト除去（固定 μ_bp）
    hit = np.where((pos_prev != 0) & (ret != 0), (pos_prev * ret > 0).astype(float), np.nan)
    valid = np.arange(n) > max(warmup, vol_win)
    hit[~valid] = np.nan
    ts = pd.Series(t)
    ym = ts.dt.year.values * 100 + ts.dt.month.values
    hy = ts.dt.year.values * 10 + np.where(ts.dt.month.values <= 6, 1, 2)
    df = pd.DataFrame(dict(date=t, year=ts.dt.year.values, month_id=ym, half_id=hy,
                           pnl=pnl, pnl_adj=pnl_adj, hit=hit, regime=regime, pos=pos_prev, valid=valid))
    df = df[df.valid & np.isfinite(df.regime)].reset_index(drop=True)
    return df


def permute_regime_by_month(df, rng):
    months = df.month_id.values
    uniq, start = np.unique(months, return_index=True)
    order = np.argsort(start)
    blocks = np.split(df.regime.values, start[order][1:])
    perm = rng.permutation(len(blocks))
    return np.concatenate([blocks[i] for i in perm])


def pooled_diff_core(x, reg):
    hi = reg == 1; lo = reg == 0
    return (float(x[hi].mean()) if hi.any() else float("nan"),
            float(x[lo].mean()) if lo.any() else float("nan"))


def pooled_diff(pnl, pnl_adj, hit, reg):
    out = dict(n_high=int((reg == 1).sum()), n_stable=int((reg == 0).sum()))
    out["pnl_high"], out["pnl_stable"] = pooled_diff_core(pnl, reg)
    out["pnl_diff"] = out["pnl_high"] - out["pnl_stable"]
    out["pnl_adj_high"], out["pnl_adj_stable"] = pooled_diff_core(pnl_adj, reg)
    out["pnl_adj_diff"] = out["pnl_adj_high"] - out["pnl_adj_stable"]
    hh = hit[reg == 1]; hl = hit[reg == 0]
    out["hit_high"] = float(np.nanmean(hh)) if np.isfinite(hh).any() else float("nan")
    out["hit_stable"] = float(np.nanmean(hl)) if np.isfinite(hl).any() else float("nan")
    out["hit_diff"] = out["hit_high"] - out["hit_stable"]
    return out


def stats_for(tab, period, reg_col="regime"):
    g = tab
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    reg = g[reg_col].values
    out = pooled_diff(g.pnl.values, g.pnl_adj.values, g.hit.values, reg)
    out["n_days"] = int(len(g))
    diffs = []; diffs_adj = []; hdiffs = []
    for _, gb in g.groupby("half_id"):
        rb = gb[reg_col].values
        if (rb == 1).sum() >= 3 and (rb == 0).sum() >= 3:
            d = pooled_diff(gb.pnl.values, gb.pnl_adj.values, gb.hit.values, rb)
            diffs.append(d["pnl_diff"]); diffs_adj.append(d["pnl_adj_diff"]); hdiffs.append(d["hit_diff"])
    m, tt, n = mean_t(diffs)
    out["pnl_diff_half_mean"] = m; out["pnl_diff_half_t"] = tt; out["pnl_diff_half_n"] = n
    m, tt, _ = mean_t(diffs_adj)
    out["pnl_adj_diff_half_mean"] = m; out["pnl_adj_diff_half_t"] = tt
    m, tt, _ = mean_t(hdiffs)
    out["hit_diff_half_mean"] = m; out["hit_diff_half_t"] = tt
    return out


def judge(res_by_combo):
    def fin(x): return x is not None and np.isfinite(x)
    passes = {}
    pass_adj = 0; pass_raw = 0
    allp_adj_neg_sig2 = 0; allp_adj_neg_sig15 = 0
    allp_raw_neg_sig2 = 0
    for combo, res in res_by_combo.items():
        r1 = res["前半"]; r2 = res["後半"]; rA = res["全期間"]
        both_neg_adj = fin(r1["pnl_adj_diff"]) and fin(r2["pnl_adj_diff"]) and r1["pnl_adj_diff"] < 0 and r2["pnl_adj_diff"] < 0
        both_neg_raw = fin(r1["pnl_diff"]) and fin(r2["pnl_diff"]) and r1["pnl_diff"] < 0 and r2["pnl_diff"] < 0
        allp_adj_neg = fin(rA["pnl_adj_diff"]) and rA["pnl_adj_diff"] < 0
        allp_raw_neg = fin(rA["pnl_diff"]) and rA["pnl_diff"] < 0
        allp_adj_z2 = fin(rA["pnl_adj_diff_z"]) and abs(rA["pnl_adj_diff_z"]) >= 2.0
        allp_adj_z15 = fin(rA["pnl_adj_diff_z"]) and abs(rA["pnl_adj_diff_z"]) >= 1.5
        allp_raw_z2 = fin(rA["pnl_diff_z"]) and abs(rA["pnl_diff_z"]) >= 2.0
        p_adj = bool(allp_adj_neg and allp_adj_z2 and both_neg_adj)
        p_raw = bool(allp_raw_neg and allp_raw_z2 and both_neg_raw)
        passes[combo] = dict(
            前半=dict(pnl_diff=r1["pnl_diff"], pnl_adj_diff=r1["pnl_adj_diff"],
                     t=r1["pnl_diff_half_t"], t_adj=r1["pnl_adj_diff_half_t"],
                     z=r1["pnl_diff_z"], z_adj=r1["pnl_adj_diff_z"]),
            後半=dict(pnl_diff=r2["pnl_diff"], pnl_adj_diff=r2["pnl_adj_diff"],
                     t=r2["pnl_diff_half_t"], t_adj=r2["pnl_adj_diff_half_t"],
                     z=r2["pnl_diff_z"], z_adj=r2["pnl_adj_diff_z"]),
            全期間=dict(pnl_diff=rA["pnl_diff"], pnl_adj_diff=rA["pnl_adj_diff"],
                      t=rA["pnl_diff_half_t"], t_adj=rA["pnl_adj_diff_half_t"],
                      z=rA["pnl_diff_z"], z_adj=rA["pnl_adj_diff_z"]),
            passed_adj=p_adj, passed_raw=p_raw,
        )
        if p_adj: pass_adj += 1
        if p_raw: pass_raw += 1
        if allp_adj_neg and allp_adj_z2: allp_adj_neg_sig2 += 1
        if allp_adj_neg and allp_adj_z15: allp_adj_neg_sig15 += 1
        if allp_raw_neg and allp_raw_z2: allp_raw_neg_sig2 += 1
    if pass_adj >= 5 and pass_raw >= 4:
        verdict = "確認（支持）"
    elif pass_adj in (3, 4) and allp_adj_neg_sig15 >= 4:
        verdict = "部分支持"
    elif pass_adj <= 1 and allp_adj_neg_sig2 < 2 and allp_raw_neg_sig2 < 2:
        verdict = "棄却"
    else:
        verdict = "未確定"
    return dict(by_combo=passes, n_pass_adj=int(pass_adj), n_pass_raw=int(pass_raw),
                allp_adj_neg_sig2=int(allp_adj_neg_sig2), allp_adj_neg_sig15=int(allp_adj_neg_sig15),
                allp_raw_neg_sig2=int(allp_raw_neg_sig2),
                rule=("6通り（2規則×3窓）について『全期間 pnl_adj_diff<0 かつ |z|≥2 かつ 前後半 pnl_adj_diff 両負』を"
                      "すべて満たせば主の通過。確認＝主の通過≥5/6 かつ raw の通過≥4/6"),
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

    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-05-01", "2026-06-30")
        n = len(dates); e = g.normal(0, 0.012, n)
        scale = np.exp(0.5 * np.sin(np.arange(n) / 120.0))
        e = e * scale
        r = np.zeros(n)
        for i in range(1, n):
            r[i] = 0.1 * r[i - 1] + e[i]
        t_arr = dates.values
        c_arr = 1500.0 * np.exp(np.cumsum(r))
        B = min(args.B, 10)
    else:
        d = load_daily(SYM)
        if d is None or len(d) < 300:
            raise RuntimeError(f"data not found or too short: {SYM}")
        t_arr = d.time.values
        c_arr = d.close.values.astype(float)
        B = args.B

    # 全期間の日次リターン平均（bp）— ドリフト除去に使う μ_bp（固定）
    ret_arr = np.zeros(len(c_arr)); ret_arr[1:] = c_arr[1:] / c_arr[:-1] - 1.0
    mu_bp = float(np.mean(ret_arr[1:]) * 1e4)

    combos = [(rule, w) for rule in RULES for w in VOL_WINS]
    periods = ["前半", "後半", "全期間"]
    res_by_combo = {}
    per_rows = []
    for rule, w in combos:
        combo_key = f"{rule}|vol{w}"
        tab = build_table(t_arr, c_arr, rule, w, mu_bp)
        res = {p: stats_for(tab, p) for p in periods}
        null_vals = {p: {"pnl_diff": [], "pnl_adj_diff": [], "hit_diff": []} for p in periods}
        for b in range(B):
            tab["regime_null"] = permute_regime_by_month(tab, rng)
            for p in periods:
                s = stats_for(tab, p, reg_col="regime_null")
                null_vals[p]["pnl_diff"].append(s["pnl_diff"])
                null_vals[p]["pnl_adj_diff"].append(s["pnl_adj_diff"])
                null_vals[p]["hit_diff"].append(s["hit_diff"])
        for p in periods:
            res[p]["pnl_diff_z"], res[p]["pnl_diff_pct"] = z_against_null(res[p]["pnl_diff"], null_vals[p]["pnl_diff"])
            res[p]["pnl_adj_diff_z"], res[p]["pnl_adj_diff_pct"] = z_against_null(res[p]["pnl_adj_diff"], null_vals[p]["pnl_adj_diff"])
            res[p]["hit_diff_z"], res[p]["hit_diff_pct"] = z_against_null(res[p]["hit_diff"], null_vals[p]["hit_diff"])
            res[p]["null_pnl_diff_mean"] = float(np.nanmean(null_vals[p]["pnl_diff"])) if B else float("nan")
            res[p]["null_pnl_diff_sd"] = float(np.nanstd(null_vals[p]["pnl_diff"], ddof=1)) if B > 1 else float("nan")
            res[p]["null_pnl_adj_diff_mean"] = float(np.nanmean(null_vals[p]["pnl_adj_diff"])) if B else float("nan")
            res[p]["null_pnl_adj_diff_sd"] = float(np.nanstd(null_vals[p]["pnl_adj_diff"], ddof=1)) if B > 1 else float("nan")
            per_rows.append(dict(combo=combo_key, period=p,
                                 n_days=res[p]["n_days"], n_high=res[p]["n_high"], n_stable=res[p]["n_stable"],
                                 pnl_high=res[p]["pnl_high"], pnl_stable=res[p]["pnl_stable"], pnl_diff=res[p]["pnl_diff"],
                                 pnl_adj_high=res[p]["pnl_adj_high"], pnl_adj_stable=res[p]["pnl_adj_stable"],
                                 pnl_adj_diff=res[p]["pnl_adj_diff"], pnl_diff_half_t=res[p]["pnl_diff_half_t"],
                                 pnl_adj_diff_half_t=res[p]["pnl_adj_diff_half_t"],
                                 pnl_diff_z=res[p]["pnl_diff_z"], pnl_adj_diff_z=res[p]["pnl_adj_diff_z"],
                                 hit_high=res[p]["hit_high"], hit_stable=res[p]["hit_stable"],
                                 hit_diff=res[p]["hit_diff"], hit_diff_z=res[p]["hit_diff_z"]))
        res_by_combo[combo_key] = res

    per = pd.DataFrame(per_rows)
    verdict = judge(res_by_combo)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_per_combo_{stamp}.csv")
    per.to_csv(csv_path, index=False)

    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(elapsed, 1),
        settings=dict(SYM=SYM, VOL_WINS=list(VOL_WINS), MIN_HIST=MIN_HIST, SPLIT_YEAR=SPLIT_YEAR,
                      NULL_B=B, SEED=SEED, COST_RT_XAU=COST_RT_XAU, TSMOM_LOOKBACK=TSMOM_LOOKBACK,
                      DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT, data_dir=DATA_DIR, mu_bp=mu_bp,
                      regime_def="20/40/60日の実現ボラ > 拡大窓の中央値（t を含まない・GARCH 不使用）",
                      drift_def="ドリフト除去: pnl_adj = pnl − pos_prev × μ_bp（μ_bp は全期間の日次リターン平均 bp・固定）",
                      null_def="局面ラベルを月ブロックで並べ替え（損益・ポジション・μ_bp 固定）"),
        data_span=dict(start=str(pd.Timestamp(t_arr[0]).date()),
                       end=str(pd.Timestamp(t_arr[-1]).date()), n=int(len(c_arr))),
        combos=[f"{r}|vol{w}" for r, w in combos],
        results=res_by_combo, judgement=verdict,
        files=dict(per_combo_csv=csv_path),
        multiple_comparisons="2規則 × 3窓 = 6通り。主判定は全期間 pnl_adj_diff 6本。raw の 6本と前後半の符号は補助",
        reference=dict(parent_queue="Q159", parent_overall_verdict="未確定",
                       xauusd_from_q159=dict(TSMOM60_vol10_all_pnl_diff=-3.16, TSMOM60_vol60_all_pnl_diff=-7.01,
                                             DON55_20_vol10_all_pnl_diff=-2.82, DON55_20_vol60_all_pnl_diff=-3.17)),
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] sym={SYM} B={B} smoke={args.smoke} μ_bp={mu_bp:+.3f}  elapsed={elapsed:.1f}s")
    for combo in [f"{r}|vol{w}" for r, w in combos]:
        print(f"  [{combo}]")
        for p in periods:
            r = res_by_combo[combo][p]
            print(f"    {p:3s} n={r['n_days']:5d} hi/lo={r['n_high']}/{r['n_stable']}  "
                  f"raw pnl 差={r['pnl_diff']:+6.2f}bp t={r['pnl_diff_half_t']:+.2f} z={r['pnl_diff_z']:+.2f}  "
                  f"adj 差={r['pnl_adj_diff']:+6.2f}bp t={r['pnl_adj_diff_half_t']:+.2f} z={r['pnl_adj_diff_z']:+.2f}  "
                  f"hit 差={r['hit_diff']:+.3f} z={r['hit_diff_z']:+.2f}")
    print(f"  通過(adj厳): {verdict['n_pass_adj']}/6   通過(raw): {verdict['n_pass_raw']}/6")
    print(f"  判定(機械): {verdict['verdict']}")
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
