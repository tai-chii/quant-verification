#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Q152 感度確認（実行者 Opus 2026-10-09 追加。本体の判定規則・観測値は変えない）
目的: 本体の帰無は銘柄ごとに独立に並べ替えるため、銘柄間の相関（金・銀、米株2指数、暗号資産どうし）を壊し、
      群平均の帰無の標準偏差を小さく見積もる＝z が膨らむ疑い。
方法: 同じ半年の組の中で「日時ごとに1つの乱数キー」を引き、各銘柄は自分の日時のキー順にリターンを並べ替える。
      同じ日時を持つ銘柄どうしは同じ置換を受けるので、同時点の相関が保たれる（ドリフト・ボラも本体と同じく保つ）。
      主（ドンチャン簡略版 55/20）・全期間・ドリフト除去後の買い側／売り側だけ、B=300、seed=20261009。
判定の読み方: 本体の事前固定規則（売り |z|<2 かつ 買い z≥2）をこの z にも当てはめて併記する（参考）。
"""
import json, os, sys, datetime as dt
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import kensho_long_short_decomposition_q152 as M

B = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rng = np.random.default_rng(20261009)
series, costs = {}, {}
for s in M.SYMS:
    d = M.load_csv(os.path.join(M.DATA_DIR, f"data_{s}_D1_fromH1.csv")); series[s] = (d.time.values, d.close.values.astype(float)); costs[s] = (M.COST_RT[s], None)
crypto = []
for s in M.CRYPTO_CANDIDATES:
    f = os.path.join(M.DATA_DIR, f"data_{s}_H4_dukascopy.csv")
    if not os.path.exists(f): continue
    d = M.load_csv(f)
    if len(d) == 0 or pd.Timestamp(d.time.iloc[0]).year > M.CRYPTO_MAX_START_YEAR: continue
    series["H4_" + s] = (d.time.values, d.close.values.astype(float)); costs["H4_" + s] = (0.0, M.CRYPTO_COST_RT_BP); crypto.append(s)
groups = {"FX8": M.FX8, "トレンド7": M.TREND7, "暗号資産": ["H4_" + s for s in crypto]}
PER = "全期間"; KEYS = ["long_adj", "short_adj"]

def obs_of(ser):
    ps = {s: M.side_series(c, t, *costs[s], rule="donchian") for s, (t, c) in ser.items()}
    return {g: M.group_stats(ps, syms, PER) for g, syms in groups.items()}

obs = obs_of(series)
all_t = np.unique(np.concatenate([series[s][0] for s in series]))
null = {g: {k: [] for k in KEYS} for g in groups}
for b in range(B):
    key = pd.Series(rng.random(len(all_t)), index=pd.DatetimeIndex(all_t))
    sh = {}
    for s, (t, c) in series.items():
        r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1]); hid = M.half_year_id(t); kk = key.reindex(pd.DatetimeIndex(t)).values
        r2 = r.copy()
        for h in np.unique(hid):
            idx = np.flatnonzero(hid == h); idx = idx[idx >= 1]
            if len(idx) > 1: r2[idx] = r[idx[np.argsort(kk[idx], kind="stable")]]
        sh[s] = (t, np.exp(np.log(c[0]) + np.cumsum(r2)))
    o = obs_of(sh)
    for g in groups:
        for k in KEYS: null[g][k].append(o[g][k]["mean"])
out = {"B": B, "seed": 20261009, "rule": "donchian", "period": PER, "crypto_used": crypto, "groups": {}}
for g in groups:
    out["groups"][g] = {}
    for k in KEYS:
        z, pct = M.z_against_null(obs[g][k]["mean"], null[g][k]); v = np.asarray(null[g][k])
        out["groups"][g][k] = dict(mean=obs[g][k]["mean"], t=obs[g][k]["t"], z_common=z, pct=pct, null_mean=float(v.mean()), null_sd=float(v.std(ddof=1)),
                                   null_p025=float(np.percentile(v, 2.5)), null_p975=float(np.percentile(v, 97.5)))
    gl, gs = out["groups"][g]["long_adj"]["z_common"], out["groups"][g]["short_adj"]["z_common"]
    out["groups"][g]["rule_applied"] = ("利益は買い側のドリフトではなく買い側の順張り" if (abs(gs) < 2 and gl >= 2) else
                                        "利益は上昇相場の分（買い側もドリフト除去後に z<2）" if gl < 2 else "規則に当てはまらない")
    print(g, json.dumps(out["groups"][g], ensure_ascii=False))
p = os.path.join(HERE, "results", f"Q152_sensitivity_common_perm_{dt.datetime.now():%Y%m%d_%H%M%S}.json")
json.dump(out, open(p, "w"), ensure_ascii=False, indent=1); print("JSON:", p)
