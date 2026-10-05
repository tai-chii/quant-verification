# -*- coding: utf-8 -*-
"""
05_neutral_ensemble.py  (2026-10-03) 特徴量の中和とアンサンブルで BMC が上がるか

=== 事前に固定した計画（結果を見る前に書いた） ===
背景 : 基準（LightGBM・small 42本）の公式診断は CORR 0.0175・BMC −0.0011。NN の探索（20本）は基準と区別できなかった。
       公式のオンボーディングの次の段階は「中和とアンサンブル」。
比べる4つ（これ以外は試さない。パラメータも動かさない）:
  A 基準            : models/baseline_small.pkl の予測
  B 中和            : A をエラごとに small 42本の特徴量で 50% 中和（numerai_tools.scoring.neutralize, proportion=0.5）
  C アンサンブル    : A と、同じ設定で target_ender_20 を学習したモデルの予測を、エラごとの順位で 50/50 平均
  D アンサンブル＋中和: C を B と同じく 50% 中和
採点 : validation（data_type=validation、学習最後のエラの後12エラを除く）。エラごとに numerai_corr と
       BMC（correlation_contribution・公開ベンチマーク v53_lgbm_ender60）。
比較 : B・C・D それぞれの「A との差」を、エラごとに取り、12エラずつのまとまりで標準誤差を出す（自己相関 約0.47 のため）。
判定 : 主は BMC。比較は3回なので、採用の目安は |差÷標準誤差| > 2 + ln3 ≈ 3.1（改善判定の多重比較の目安）。
       1〜3.1 は保留、1 未満は「区別できない」。CORR が A の半分を下回るものは採用しない。
       直近214エラ（NN 探索の取っておく期間と同じ）の成績も参考に出す（判定には使わない）。
出力 : results/neutral_ensemble.csv（全体と直近）、results/neutral_ensemble_per_era.csv、models/ender20_small.pkl
"""
import os, json, pickle, time
import numpy as np, pandas as pd, lightgbm as lgb
from numerai_tools.scoring import numerai_corr, correlation_contribution, neutralize

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
pk = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
A_MODEL, FEATS = pk["model"], pk["features"]
t0 = time.time()

# --- target_ender_20 のモデル（A と同じ設定・同じ間引き） ---
mpath = os.path.join(HERE, "models", "ender20_small.pkl")
tr = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era", "target_ender_20"] + FEATS)
eras = tr.era.unique(); last = int(eras[-1])
if os.path.exists(mpath):
    C_MODEL = pickle.load(open(mpath, "rb"))
else:
    tr = tr[tr.era.isin(eras[::4])].dropna(subset=["target_ender_20"])
    C_MODEL = lgb.LGBMRegressor(n_estimators=2000, learning_rate=0.01, max_depth=5, num_leaves=31,
                                colsample_bytree=0.1, verbose=-1)
    C_MODEL.fit(tr[FEATS], tr["target_ender_20"]); pickle.dump(C_MODEL, open(mpath, "wb"))
del tr
print(f"ender20 モデル: {time.time()-t0:.0f}秒", flush=True)

# --- 検証データ ---
emb = [str(last + i).zfill(4) for i in range(1, 13)]
va = pd.read_parquet(os.path.join(DATA, "validation.parquet"), columns=["era", "target"] + FEATS,
                     filters=[("data_type", "==", "validation"), ("era", "not in", emb)]).dropna(subset=["target"])
bm = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"), columns=["v53_lgbm_ender60"])
va = va.join(bm, how="left")
va = va.dropna(subset=["v53_lgbm_ender60"])
print(f"検証: {va.era.nunique()}エラ・{len(va):,}行（ベンチマークのある行）", flush=True)

# 途中保存つき（1回の実行は約150秒まで。続きは再実行で）
ck = os.path.join(HERE, "results", "neutral_ensemble_per_era.partial.csv")
done = pd.read_csv(ck, dtype={"era": str}) if os.path.exists(ck) else pd.DataFrame()
todo = sorted(set(va.era) - set(done.era if len(done) else []))
print(f"残り {len(todo)} エラ", flush=True)
rows = []
for era in todo:
    if time.time() - t0 > 150: break
    g = va[va.era == era]
    a = pd.Series(A_MODEL.predict(g[FEATS]), index=g.index).rank(pct=True)
    c0 = pd.Series(C_MODEL.predict(g[FEATS]), index=g.index).rank(pct=True)
    c = ((a + c0) / 2).rank(pct=True)
    b = neutralize(a.to_frame("p"), g[FEATS].astype(float), proportion=0.5)["p"].rank(pct=True)
    d = neutralize(c.to_frame("p"), g[FEATS].astype(float), proportion=0.5)["p"].rank(pct=True)
    r = {"era": era}
    for k, v in {"A": a, "B": b, "C": c, "D": d}.items():
        r[f"corr_{k}"] = numerai_corr(v.to_frame("p"), g["target"])["p"]
        r[f"bmc_{k}"] = correlation_contribution(v.to_frame("p"), g["v53_lgbm_ender60"], g["target"])["p"]
    rows.append(r)
done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True); done.to_csv(ck, index=False)
if len(done) < va.era.nunique():
    print(f"途中保存: {len(done)}/{va.era.nunique()} エラ。もう一度実行すると続きから。"); raise SystemExit(0)
rows = done.to_dict("records")
pe = pd.DataFrame(rows).sort_values("era").reset_index(drop=True)
pe.to_csv(os.path.join(HERE, "results", "neutral_ensemble_per_era.csv"), index=False)


def block_se(d, B=12):
    blk = d.groupby(np.arange(len(d)) // B).mean()
    return blk.std(ddof=1) / np.sqrt(len(blk))


out = []
for label, sub in [("全体", pe), ("直近214エラ（参考）", pe.tail(214))]:
    for k in "ABCD":
        row = dict(期間=label, 版=k, エラ数=len(sub), CORR平均=sub[f"corr_{k}"].mean(), BMC平均=sub[f"bmc_{k}"].mean(),
                   CORRシャープ=sub[f"corr_{k}"].mean() / sub[f"corr_{k}"].std())
        if k != "A":
            for m in ["corr", "bmc"]:
                d = (sub[f"{m}_{k}"] - sub[f"{m}_A"]).reset_index(drop=True)
                se = block_se(d); row[f"{m.upper()}差"] = d.mean(); row[f"{m.upper()}差÷SE"] = d.mean() / se
        out.append(row)
res = pd.DataFrame(out); res.to_csv(os.path.join(HERE, "results", "neutral_ensemble.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(res.round(5).to_string(index=False))
for k in "BCD":
    r = res[(res.期間 == "全体") & (res.版 == k)].iloc[0]
    z = r["BMC差÷SE"]; ok_corr = r["CORR平均"] >= res[(res.期間 == "全体") & (res.版 == "A")].CORR平均.iloc[0] / 2
    verdict = "採用" if (z > 3.1 and ok_corr) else ("保留" if abs(z) >= 1 else "区別できない")
    print(f"判定 {k}: BMC差÷SE={z:+.2f} → {verdict}")
print(f"合計 {time.time()-t0:.0f}秒")
