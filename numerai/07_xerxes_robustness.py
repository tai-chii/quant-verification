# -*- coding: utf-8 -*-
"""
07_xerxes_robustness.py  (2026-10-04) xerxes_60 の優位は「学習データの選び方」の偶然ではないか

=== 事前に固定した計画（結果を見る前に書いた） ===
背景 : 06 で xerxes_60 単体（F）が基準（ender_60）より BMC 差÷SE +3.5 で採用になった。
       ただし両モデルとも「4エラに1つ」（先頭から）で間引いて学習しているので、間引きの位置が違えば
       結果が変わる可能性がある（学習のばらつき）。06 の SE は検証エラのばらつきしか見ていない。
やること: 間引きの開始位置を 1・2・3 にずらして、ender_60 と xerxes_60 を各3本ずつ学習し直す（設定は 06 と同じ）。
         開始位置ごとに「xerxes − ender」の BMC 差を検証640エラで測る。
判定 : 3つすべてで BMC 差÷SE > +1 なら「再現した」→ taichi_te の採用を維持。
       1つでも差がマイナスなら「再現しない」→ 06 の採用は学習のばらつきだった可能性が高いと記録。
       それ以外は「弱く再現」。
       参考: 4本（0〜3）の予測を平均したモデル同士の差も出す（判定には使わない）。
出力 : results/xerxes_robustness.csv・_per_era.csv、models/{ender60,xerxes60}_o{1,2,3}_small.pkl
実行 : 1回150秒まで。繰り返し実行で続きから。
"""
import os, pickle, time
import numpy as np, pandas as pd, lightgbm as lgb
from numerai_tools.scoring import numerai_corr, correlation_contribution

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data"); MD = os.path.join(HERE, "models")
t0 = time.time()
base = pickle.load(open(os.path.join(MD, "baseline_small.pkl"), "rb")); FEATS = base["features"]
M = {("ender", 0): base["model"], ("xerxes", 0): pickle.load(open(os.path.join(MD, "xerxes60_small.pkl"), "rb"))}
TG = {"ender": "target_ender_60", "xerxes": "target_xerxes_60"}
tr = None
for o in (1, 2, 3):
    for k, t in TG.items():
        p = os.path.join(MD, f"{k}60_o{o}_small.pkl")
        if os.path.exists(p):
            M[(k, o)] = pickle.load(open(p, "rb")); continue
        if time.time() - t0 > 120:
            print("学習の途中で止めた。もう一度実行。"); raise SystemExit(0)
        if tr is None:
            tr = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"] + list(TG.values()) + FEATS)
        eras = tr.era.unique(); sub = tr[tr.era.isin(eras[o::4])].dropna(subset=[t])
        m = lgb.LGBMRegressor(n_estimators=2000, learning_rate=0.01, max_depth=5, num_leaves=31,
                              colsample_bytree=0.1, verbose=-1)
        m.fit(sub[FEATS], sub[t]); pickle.dump(m, open(p, "wb")); M[(k, o)] = m
        print(f"学習 {k} o{o}（{time.time()-t0:.0f}秒）", flush=True)
if tr is not None:
    print("学習完了。もう一度実行して採点へ。"); raise SystemExit(0)

last = int(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[-1])
emb = [str(last + i).zfill(4) for i in range(1, 13)]
va = pd.read_parquet(os.path.join(DATA, "validation.parquet"), columns=["era", "target"] + FEATS,
                     filters=[("data_type", "==", "validation"), ("era", "not in", emb)]).dropna(subset=["target"])
bm = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"), columns=["v53_lgbm_ender60"])
va = va.join(bm, how="left").dropna(subset=["v53_lgbm_ender60"])
ck = os.path.join(HERE, "results", "xerxes_robustness_per_era.partial.csv")
done = pd.read_csv(ck, dtype={"era": str}) if os.path.exists(ck) else pd.DataFrame()
todo = sorted(set(va.era) - set(done.era if len(done) else []))
print(f"検証 {va.era.nunique()}エラ・残り {len(todo)}", flush=True)
rows = []
for era in todo:
    if time.time() - t0 > 150: break
    g = va[va.era == era]; X = g[FEATS]
    P = {key: pd.Series(m.predict(X), index=g.index).rank(pct=True) for key, m in M.items()}
    for k in TG:
        P[(k, "avg")] = (sum(P[(k, o)] for o in range(4)) / 4).rank(pct=True)
    r = {"era": era}
    for (k, o), v in P.items():
        r[f"corr_{k}_{o}"] = numerai_corr(v.to_frame("p"), g["target"])["p"]
        r[f"bmc_{k}_{o}"] = correlation_contribution(v.to_frame("p"), g["v53_lgbm_ender60"], g["target"])["p"]
    rows.append(r)
done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True); done.to_csv(ck, index=False)
if len(done) < va.era.nunique():
    print(f"途中保存: {len(done)}/{va.era.nunique()} エラ。"); raise SystemExit(0)
pe = done.sort_values("era").reset_index(drop=True)
pe.to_csv(os.path.join(HERE, "results", "xerxes_robustness_per_era.csv"), index=False)


def block_se(d, B=12):
    blk = d.groupby(np.arange(len(d)) // B).mean()
    return blk.std(ddof=1) / np.sqrt(len(blk))


out = []
for label, sub in [("全体", pe), ("直近214（参考）", pe.tail(214))]:
    for o in [0, 1, 2, 3, "avg"]:
        d = (sub[f"bmc_xerxes_{o}"] - sub[f"bmc_ender_{o}"]).reset_index(drop=True)
        dc = (sub[f"corr_xerxes_{o}"] - sub[f"corr_ender_{o}"]).reset_index(drop=True)
        out.append(dict(期間=label, 間引き開始=o, ender_CORR=sub[f"corr_ender_{o}"].mean(), xerxes_CORR=sub[f"corr_xerxes_{o}"].mean(),
                        ender_BMC=sub[f"bmc_ender_{o}"].mean(), xerxes_BMC=sub[f"bmc_xerxes_{o}"].mean(),
                        **{"BMC差": d.mean(), "BMC差÷SE": d.mean() / block_se(d), "CORR差÷SE": dc.mean() / block_se(dc)}))
res = pd.DataFrame(out); res.to_csv(os.path.join(HERE, "results", "xerxes_robustness.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(res.round(5).to_string(index=False))
z = res[(res.期間 == "全体") & (res.間引き開始.isin([1, 2, 3]))]["BMC差÷SE"].astype(float)
v = "再現した" if (z > 1).all() else ("再現しない" if (res[(res.期間 == "全体") & (res.間引き開始.isin([1, 2, 3]))].BMC差 < 0).any() else "弱く再現")
print(f"判定: 開始1〜3の BMC差÷SE = {', '.join(f'{x:+.2f}' for x in z)} → {v}")
