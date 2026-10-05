# -*- coding: utf-8 -*-
"""
06_target_ensemble.py  (2026-10-03) 別のターゲットで学習したモデルを混ぜると BMC が上がるか

=== 事前に固定した計画（結果を見る前に書いた） ===
背景 : 05 で ender_20（主ターゲットと同じ種類で期間だけ短い）と混ぜたら BMC はむしろ悪化。
       公式チュートリアル（target_ensemble.ipynb）は teager2b_60・xerxes_60 を挙げ、
       「主ターゲットで学習したモデルより平均が高い」と書いている。種類の違うターゲットなら効くかを確かめる。
比べる3つ（これ以外は試さない。パラメータは基準と同じ・small 42本・4エラに1つ間引き）:
  E teager2b_60 で学習したモデル単体
  F xerxes_60 で学習したモデル単体
  G A（基準）・E・F の予測をエラごとの順位で等しく平均
採点 : 05 と同じ（validation・12エラ除外・numerai_corr・BMC は v53_lgbm_ender60）。
       参考として v53_lgbm_ender20 に対する BMC も出す（公式のエージェント手順の主指標。判定には使わない）。
判定 : 05 と同じ。主は BMC、3回比較なので |差÷SE| > 3.1 で採用、1〜3.1 保留、1未満は区別できない。
       CORR が A の半分を下回るものは採用しない。直近214エラは参考。
出力 : results/target_ensemble.csv、results/target_ensemble_per_era.csv、models/{teager2b60,xerxes60}_small.pkl
実行 : 1回約150秒まで。モデル学習1つ、または採点の途中までで止まるので、終わるまで繰り返し実行。
"""
import os, pickle, time
import numpy as np, pandas as pd, lightgbm as lgb
from numerai_tools.scoring import numerai_corr, correlation_contribution

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
pk = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
A_MODEL, FEATS = pk["model"], pk["features"]
t0 = time.time()
TG = {"E": "target_teager2b_60", "F": "target_xerxes_60"}
MODELS = {}
for k, t in TG.items():
    p = os.path.join(HERE, "models", t.replace("target_", "").replace("_", "") + "_small.pkl")
    if os.path.exists(p):
        MODELS[k] = pickle.load(open(p, "rb")); continue
    tr = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era", t] + FEATS)
    tr = tr[tr.era.isin(tr.era.unique()[::4])].dropna(subset=[t])
    m = lgb.LGBMRegressor(n_estimators=2000, learning_rate=0.01, max_depth=5, num_leaves=31,
                          colsample_bytree=0.1, verbose=-1)
    m.fit(tr[FEATS], tr[t]); pickle.dump(m, open(p, "wb"))
    print(f"{t} を学習・保存（{time.time()-t0:.0f}秒）。もう一度実行して続きへ。"); raise SystemExit(0)

last = int(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[-1])
emb = [str(last + i).zfill(4) for i in range(1, 13)]
va = pd.read_parquet(os.path.join(DATA, "validation.parquet"), columns=["era", "target"] + FEATS,
                     filters=[("data_type", "==", "validation"), ("era", "not in", emb)]).dropna(subset=["target"])
bm = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"), columns=["v53_lgbm_ender60", "v53_lgbm_ender20"])
va = va.join(bm, how="left").dropna(subset=["v53_lgbm_ender60", "v53_lgbm_ender20"])

ck = os.path.join(HERE, "results", "target_ensemble_per_era.partial.csv")
done = pd.read_csv(ck, dtype={"era": str}) if os.path.exists(ck) else pd.DataFrame()
todo = sorted(set(va.era) - set(done.era if len(done) else []))
print(f"検証 {va.era.nunique()}エラ・残り {len(todo)}", flush=True)
rows = []
for era in todo:
    if time.time() - t0 > 150: break
    g = va[va.era == era]
    a = pd.Series(A_MODEL.predict(g[FEATS]), index=g.index).rank(pct=True)
    e = pd.Series(MODELS["E"].predict(g[FEATS]), index=g.index).rank(pct=True)
    f = pd.Series(MODELS["F"].predict(g[FEATS]), index=g.index).rank(pct=True)
    gg = ((a + e + f) / 3).rank(pct=True)
    r = {"era": era}
    for k, v in {"A": a, "E": e, "F": f, "G": gg}.items():
        r[f"corr_{k}"] = numerai_corr(v.to_frame("p"), g["target"])["p"]
        r[f"bmc_{k}"] = correlation_contribution(v.to_frame("p"), g["v53_lgbm_ender60"], g["target"])["p"]
        r[f"bmc20_{k}"] = correlation_contribution(v.to_frame("p"), g["v53_lgbm_ender20"], g["target"])["p"]
    rows.append(r)
done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True); done.to_csv(ck, index=False)
if len(done) < va.era.nunique():
    print(f"途中保存: {len(done)}/{va.era.nunique()} エラ。もう一度実行すると続きから。"); raise SystemExit(0)
pe = done.sort_values("era").reset_index(drop=True)
pe.to_csv(os.path.join(HERE, "results", "target_ensemble_per_era.csv"), index=False)


def block_se(d, B=12):
    blk = d.groupby(np.arange(len(d)) // B).mean()
    return blk.std(ddof=1) / np.sqrt(len(blk))


out = []
for label, sub in [("全体", pe), ("直近214エラ（参考）", pe.tail(214))]:
    for k in "AEFG":
        row = dict(期間=label, 版=k, エラ数=len(sub), CORR平均=sub[f"corr_{k}"].mean(), BMC平均=sub[f"bmc_{k}"].mean(),
                   BMC20平均=sub[f"bmc20_{k}"].mean(), CORRシャープ=sub[f"corr_{k}"].mean() / sub[f"corr_{k}"].std())
        if k != "A":
            for m in ["corr", "bmc", "bmc20"]:
                d = (sub[f"{m}_{k}"] - sub[f"{m}_A"]).reset_index(drop=True)
                row[f"{m.upper()}差÷SE"] = d.mean() / block_se(d)
        out.append(row)
res = pd.DataFrame(out); res.to_csv(os.path.join(HERE, "results", "target_ensemble.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(res.round(5).to_string(index=False))
a_corr = res[(res.期間 == "全体") & (res.版 == "A")].CORR平均.iloc[0]
for k in "EFG":
    r = res[(res.期間 == "全体") & (res.版 == k)].iloc[0]; z = r["BMC差÷SE"]
    verdict = "採用" if (z > 3.1 and r["CORR平均"] >= a_corr / 2) else ("保留" if abs(z) >= 1 else "区別できない")
    print(f"判定 {k}: BMC差÷SE={z:+.2f} → {verdict}")
