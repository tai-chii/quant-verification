#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q160（Q152 の次段階・事前登録し直し）
================================================================================
BTC を除いたトレンド6と商品4銘柄だけの群で、ドンチャン55/20 の買い側ドリフト除去後が
日時共通の並べ替え帰無で z≥2 か。

【出典】
- 計画（事前登録・2026-10-09）: Q160（この docstring）。元の Q152 の README 末尾の
  「次に確かめるなら: BTC を除いたトレンド7と、商品4銘柄だけの群で同じ分解（事前登録し直し）」。
- Q152（主ドンチャン簡略版 55/20・B=500）: トレンド7 の買い側 +1.79 bp/足・z 3.1、
  日時共通並べ替えで z 2.5。ただし +1.79 のうち BTC（D1）が +7.81 で約6割、
  BTC 除外6銘柄の平均は +0.78（事後の切り口）。株価指数は負（US500 -1.51・USTECH -0.55）、
  商品は正（XAU +1.27・XAG +1.22・WTI +1.48・UKOIL +2.79）。
- 既存の決まり: Q152 の帰無は銘柄ごとに独立に並べ替えて同時点相関を壊すため、群平均の
  帰無 sd を小さく見積もる疑いが Q152 の感度確認で示された（z 3.1→2.5、3.0→2.2）。
  Q160 は最初から 日時共通の並べ替え 1 本に固定して事前登録する。

【仮説（測る前に固定）】
H1: BTC を除いたトレンド6（XAU/XAG/WTI/UKOIL/US500/USTECH）で、ドンチャン55/20 の
    買い側ドリフト除去後 [bp/足] は 0 より大きい（日時共通並べ替え帰無で z≥2）。
H2: 商品4（XAU/XAG/WTI/UKOIL）でも 買い側ドリフト除去後 z≥2。
H3: 両群で売り側ドリフト除去後 |z|<2（Q152 の売り側頑健性の再確認）。

【判定（事前固定・変更禁止）】
- 群ごとに:
  - 買い側ドリフト除去後 z ≥ 2 かつ 売り側 |z| < 2 → 支持
  - 買い側 z < 2 → 否定（BTC・後半依存だった）
  - その他（売り側 |z|≥2 など）→ 当てはまらない
- 総合:
  - 両群で支持 → **確定**「BTC 除外でも、商品のみでも、順張りの買い側は上昇相場の分でなく追加の利益」
  - 片方のみ支持 → **群で割れる（未確定）**
  - 両群で否定 → **ノイズ**（Q152 の買い側利益は BTC/後半に大きく依存）
  - その他の組合せ → **未確定**

【データ】
- 検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv の 6 銘柄
  （XAUUSD/XAGUSD/WTI/UKOIL/US500/USTECH）。2008-02〜2026-07。
- Q152 と同じ load_csv・half_year_id・daily_net_pnl_bp を使う（コピーで自己完結）。

【定義（1通りに固定・Q152 と同じ）】
- 規則: ドンチャン簡略版 55/20（終値が直前55日高値を上抜けで翌足から買い、
  直前20日安値を下抜けで手仕舞い、売りは対称、損切りなし）。
- 日次純損益 [bp] = pos_{t-1} × ret_t × 1e4 − |Δpos| × 片道コスト。片道 = COST_RT/2。
- 側の分解: 買い側 = pos=+1 の足の pnl、売り側 = pos=−1 の足の pnl。全足の平均を使う。
- ドリフト除去: 同期間の平均リターン r̄[bp] × 露出を引く
  （買い側: pnl − r̄, 売り側: pnl + r̄, pos=0 の足は 0）。
- 群平均 = 銘柄ごとの全足平均の等ウェイト平均。
- 期間: 全期間（判定）、前半 (<2017)・後半 (≥2017)（記述）。

【帰無（日時共通の並べ替え）】
各半年の組の中で日時ごとに 1 つの乱数キーを引き、全銘柄が同じキーで並べ替える
（同時点相関を保つ）。B=500、seed=20261009。z = (観測 − 帰無の平均)/帰無の標準偏差。

【捨てた案の数】約4】
- 日足を H1 に戻す（Q152 と揃えるため D1 のまま）、
- ドンチャン以外の規則の併記（規則は 1 本・Q152 と同じ）、
- 期間を 3 分割（前半・後半は記述・事前固定の判定は全期間のみ）、
- ドリフト除去を年ごとにする（評価期間ごと 1 本・Q152 と同じ）。

【多重比較】
2 群 × 2 側 × 1 期間 = 4 本。判定に使う主要なのは 2 群 × 買い側 = 2 本
（売り側 2 本は H3 の確認用）。|z|≥2 の 2 本同時当選は独立下で約 0.000625。
商品4 ⊂ トレンド6（6 銘柄中 4 銘柄が商品）なので独立ではない。報告に書く。

【知識の締め切り】
Claude の知識はおよそ 2026-06 まで。金・原油・米株が 2020 年以降に上げたことは知って
おり、「商品の買い側が勝つ」方向の後知恵は排除できない。問いは「ドリフトを引いた残り」
で、相場観だけでは答えは出ない。Q152 の事後に見えた切り口を事前登録に昇格させるので、
データ・コードは同じ・切り口（群分け）だけが事前登録になる点を明記する。

【委託の確かめ方】
設計・実行・解釈とも Opus（検証キュー Q160・担当列 opus）。コードはこの docstring の
計画と Q152 スクリプトの関数を忠実に写した自己完結版。実行者は結論ではなく、JSON の
パス・群×側のドリフト除去後の平均と z・Q152 との差を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas。
実行: python3 kensho_q160.py            （B=500）
      python3 kensho_q160.py --B 50     （軽い試走）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import unicodedata
import warnings

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

TREND6 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH"]
COMMODITIES4 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL"]
COST_RT = {"XAUUSD": 0.6, "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0}
LOOKBACK = 20
DON_ENTRY, DON_EXIT = 55, 20
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261009


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
        return float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct, float(v.mean()), float(sd), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def load_csv(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def half_year_id(ts):
    ts = pd.Series(ts)
    return (ts.dt.year * 10 + np.where(ts.dt.month <= 6, 1, 2)).values


def donchian_positions(c):
    n = len(c); pos = np.zeros(n)
    cs = pd.Series(c)
    hiE = cs.rolling(DON_ENTRY).max().shift(1).values; loE = cs.rolling(DON_ENTRY).min().shift(1).values
    hiX = cs.rolling(DON_EXIT).max().shift(1).values; loX = cs.rolling(DON_EXIT).min().shift(1).values
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


def daily_net_pnl_bp(c, signal, cost_rt):
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:LOOKBACK + 1] = 0.0
    return pnl, pos_prev, ret


PERIODS = ["全期間", "前半", "後半"]
KEYS = ["long_raw", "short_raw", "long_adj", "short_adj"]


def side_series(c, t, cost_rt):
    pnl, pos, ret = daily_net_pnl_bp(c, donchian_positions(c), cost_rt)
    years = pd.Series(t).dt.year.values
    months = (pd.Series(t).dt.year * 100 + pd.Series(t).dt.month).values
    valid = np.arange(len(c)) > max(LOOKBACK, DON_ENTRY)
    out = {}
    for per in PERIODS:
        m = valid.copy()
        if per == "前半":
            m &= years < SPLIT_YEAR
        elif per == "後半":
            m &= years >= SPLIT_YEAR
        if m.sum() < 50:
            continue
        rbar = ret[m].mean() * 1e4
        isL = (pos == 1) & m; isS = (pos == -1) & m
        s = {"long_raw": np.where(isL, pnl, 0.0), "short_raw": np.where(isS, pnl, 0.0),
             "long_adj": np.where(isL, pnl - rbar, 0.0), "short_adj": np.where(isS, pnl + rbar, 0.0)}
        d = {}
        for k, v in s.items():
            d[k] = dict(mean=float(v[m].mean()), monthly=pd.Series(v[m]).groupby(months[m]).mean(),
                        mean_active=float(v[isL if k.startswith("long") else isS].mean()) if (isL if k.startswith("long") else isS).sum() else float("nan"))
        d["n"] = int(m.sum()); d["expo_long"] = float(isL.sum() / m.sum()); d["expo_short"] = float(isS.sum() / m.sum())
        d["drift_bp"] = float(rbar)
        out[per] = d
    return out


def group_stats(per_sym, syms, per):
    res = {}
    syms = [s for s in syms if s in per_sym and per in per_sym[s]]
    res["n_syms"] = len(syms); res["syms"] = syms
    for k in KEYS:
        if not syms:
            res[k] = dict(mean=float("nan"), t=float("nan"), n_months=0, mean_active=float("nan"))
            continue
        means = [per_sym[s][per][k]["mean"] for s in syms]
        mon = pd.concat([per_sym[s][per][k]["monthly"].rename(s) for s in syms], axis=1).mean(axis=1)
        m, tt, n = mean_t(mon.values)
        res[k] = dict(mean=float(np.mean(means)), t=tt, n_months=n,
                      mean_active=float(np.nanmean([per_sym[s][per][k]["mean_active"] for s in syms])))
    if syms:
        res["expo_long"] = float(np.mean([per_sym[s][per]["expo_long"] for s in syms]))
        res["expo_short"] = float(np.mean([per_sym[s][per]["expo_short"] for s in syms]))
        res["drift_bp"] = float(np.mean([per_sym[s][per]["drift_bp"] for s in syms]))
    return res


def shuffle_common(series, rng, all_t):
    """日時ごとに 1 つの乱数キー、各半年の組の中で各銘柄が同じキー順で並べ替える。"""
    key = pd.Series(rng.random(len(all_t)), index=pd.DatetimeIndex(all_t))
    out = {}
    for s, (t, c) in series.items():
        r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
        hid = half_year_id(t); kk = key.reindex(pd.DatetimeIndex(t)).values
        r2 = r.copy()
        for h in np.unique(hid):
            idx = np.flatnonzero(hid == h); idx = idx[idx >= 1]
            if len(idx) > 1:
                r2[idx] = r[idx[np.argsort(kk[idx], kind="stable")]]
        out[s] = (t, np.exp(np.log(c[0]) + np.cumsum(r2)))
    return out


def judge_group(res_group, g_name):
    r = res_group
    if r["n_syms"] == 0:
        return dict(group=g_name, verdict="データなし")
    zl = r["long_adj"]["z"]; zs = r["short_adj"]["z"]
    long_pos = np.isfinite(zl) and zl >= 2.0
    short_null = np.isfinite(zs) and abs(zs) < 2.0
    if long_pos and short_null:
        v = "支持"
    elif np.isfinite(zl) and zl < 2.0:
        v = "否定（買い側 z<2・BTC/後半依存だった）"
    else:
        v = "当てはまらない（売り側 |z|≥2 など）"
    return dict(group=g_name, long_adj_z=zl, short_adj_z=zs, verdict=v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B)
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    series, costs = {}, {}
    missing = {}
    for sym in TREND6:
        f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
        if not os.path.exists(f):
            missing.setdefault("D1_missing", []).append(sym); continue
        d = load_csv(f)
        series[sym] = (d.time.values, d.close.values.astype(float))
        costs[sym] = COST_RT[sym]
    groups = {"トレンド6": [s for s in TREND6 if s in series],
              "商品4": [s for s in COMMODITIES4 if s in series]}

    per_sym = {s: side_series(c, t, costs[s]) for s, (t, c) in series.items()}
    res = {}
    rows = []
    for gname, syms in groups.items():
        for per in PERIODS:
            res[f"{gname}|{per}"] = group_stats(per_sym, syms, per)
    for s in series:
        for per, d in per_sym[s].items():
            rows.append(dict(sym=s, period=per, n=d["n"], expo_long=d["expo_long"], expo_short=d["expo_short"], drift_bp=d["drift_bp"],
                             **{k: d[k]["mean"] for k in KEYS}, **{k + "_active": d[k]["mean_active"] for k in KEYS}))
    tab = pd.DataFrame(rows)

    # 日時共通並べ替え帰無
    all_t = np.unique(np.concatenate([series[s][0] for s in series]))
    null = {key: {k: [] for k in KEYS} for key in res}
    for b in range(args.B):
        sh = shuffle_common(series, rng, all_t)
        ps = {s: side_series(c, t, costs[s]) for s, (t, c) in sh.items()}
        for gname, syms in groups.items():
            for per in PERIODS:
                gs = group_stats(ps, syms, per)
                for k in KEYS:
                    null[f"{gname}|{per}"][k].append(gs[k]["mean"])
    for key in res:
        for k in KEYS:
            z, pct, nm, ns, p025, p975 = z_against_null(res[key][k]["mean"], null[key][k])
            res[key][k]["z"] = z; res[key][k]["pct"] = pct
            res[key][k]["null_mean"] = nm; res[key][k]["null_sd"] = ns
            res[key][k]["null_p025"] = p025; res[key][k]["null_p975"] = p975

    g_verdicts = {g: judge_group(res[f"{g}|全期間"], g) for g in groups}
    verdicts = [g_verdicts[g].get("verdict", "データなし") for g in groups]
    sup = [v == "支持" for v in verdicts]
    neg = [v.startswith("否定") for v in verdicts]
    if all(sup):
        overall = "確定"
        overall_text = "確定: BTC 除外でも、商品のみでも、順張りの買い側は上昇相場の分でなく追加の利益"
    elif all(neg):
        overall = "ノイズ"
        overall_text = "ノイズ: Q152 の買い側利益は BTC/後半に大きく依存していた"
    elif any(sup) and any(neg):
        overall = "群で割れる（未確定）"
        overall_text = "群で割れる（未確定）"
    else:
        overall = "未確定"
        overall_text = "未確定（支持・否定のどちらも揃わない）"

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(OUT, f"Q160_by_symbol_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    out = dict(
        queue_id="Q160", script=os.path.basename(__file__), run_at=stamp,
        settings=dict(LOOKBACK=LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT,
                      SPLIT_YEAR=SPLIT_YEAR, NULL_B=args.B, SEED=SEED, COST_RT=COST_RT,
                      syms=list(series.keys()), data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0])), end=str(pd.Timestamp(series[s][0][-1])), n=int(len(series[s][1])))
                   for s in series},
        groups={g: list(syms) for g, syms in groups.items()},
        missing=missing,
        results=res,
        by_group_verdict=g_verdicts,
        overall=overall, overall_text=overall_text,
        multiple_comparisons="2 群 × 2 側 × 1 期間 = 4 本（判定は主 2 本の買い側 + H3 の確認 2 本の売り側）。商品4 ⊂ トレンド6（6 中 4 が商品）で独立でない。",
        notes_vs_q152=["規則・データ・コスト・ドリフト除去・期間分割は Q152 と完全同一。群分けだけ変更。",
                       "帰無は Q152 の感度確認（日時共通並べ替え）を本体に昇格。seed=20261009 で Q152 感度と同じ。",
                       "Q152 の BTC 除外トレンド6 の事後の平均は +0.78 bp/足（README）。それが日時共通並べ替え帰無で z≥2 か を事前登録で問う。"],
        files=dict(by_symbol_csv=csv_path),
    )
    jpath = os.path.join(OUT, f"Q160_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q160] syms={len(series)} B={args.B} missing={missing}")
    for per in PERIODS:
        for gname in groups:
            r = res[f"{gname}|{per}"]
            if r["n_syms"] == 0:
                print(f"  {per:3s} {gname:7s} (銘柄なし)"); continue
            print(f"  {per:3s} {gname:7s} n={r['n_syms']} expoL={r['expo_long']:.2f} expoS={r['expo_short']:.2f} drift={r['drift_bp']:+.2f}bp | " +
                  " ".join(f"{k}={r[k]['mean']:+.2f}(t{r[k]['t']:+.1f},z{r[k]['z']:+.1f})" for k in KEYS))
    for g, v in g_verdicts.items():
        print(f"  判定（事前固定）{g}:", v.get("verdict"))
    print("  総合判定:", overall_text)
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
