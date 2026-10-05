# -*- coding: utf-8 -*-
"""
02_train_validate.py  ベースラインのモデルを学習し、検証期間で採点する
使い方: python3 ~/ワークスペース/作業層/検証/numerai/02_train_validate.py [small|medium]

=== 事前に固定した設定（2026-10-03・結果を見る前） ===
- モデル: Numerai 公式の例と同じ LightGBM（n_estimators=2000, learning_rate=0.01, max_depth=5, num_leaves=31, colsample_bytree=0.1）
- 特徴量: 既定は small（メモリ節約）。medium は引数で。学習は train の4エラに1つ（公式の例と同じ間引き）
- 採点: validation の目的変数がある各エラで、予測の順位と target の相関（per-era Spearman）
=== 2026-10-03 補正（公式ノートブック hello_numerai に合わせた。結果の比較のためではなく、漏れと採点式の違いを直すため） ===
- 目的変数は60営業日（約12エラ）先を見るので、学習の最後のエラの直後12エラを検証から除く（エンバーゴ）。補正前は除いていなかった＝わずかな漏れ
- validation.parquet は data_type=="validation" の行だけを使う
- 採点は公式の numerai_corr（numerai-tools）。Spearman も参考に残す
  報告するもの: 平均・標準偏差・シャープ（平均/標準偏差）・プラスのエラの割合・最大の下落（累積和）
- これは比較の基準を作る回。設定を変えた版はこの数値と「同じエラの差」で比べる（改善判定）
出力: models/baseline_<特徴量>.pkl、results/baseline_<特徴量>_per_era.csv、results/summary.csv（1行追記）
"""
import os, sys, json, pickle, datetime as dt
import numpy as np, pandas as pd
import lightgbm as lgb
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
FS = (sys.argv[1] if len(sys.argv) > 1 else "small").lower()
os.makedirs(os.path.join(HERE, "models"), exist_ok=True); os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
meta = json.load(open(os.path.join(DATA, "features.json")))
feats = meta["feature_sets"][FS]; print(f"特徴量 {FS}: {len(feats)}本")
cols = ["era", "target"] + feats
tr = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=cols)
eras = tr.era.unique(); tr = tr[tr.era.isin(eras[::4])]
print(f"学習: {tr.era.nunique()}エラ・{len(tr):,}行")
model = lgb.LGBMRegressor(n_estimators=2000, learning_rate=0.01, max_depth=5, num_leaves=2**5 - 1,
                          colsample_bytree=0.1, verbose=-1)
model.fit(tr[feats], tr["target"]); del tr
pickle.dump({"model": model, "features": feats, "feature_set": FS, "version": open(os.path.join(DATA, "VERSION")).read()},
            open(os.path.join(HERE, "models", f"baseline_{FS}.pkl"), "wb"))
from numerai_tools.scoring import numerai_corr
last = int(eras[-1]); emb = [str(last + i).zfill(4) for i in range(1, 13)]
va = pd.read_parquet(os.path.join(DATA, "validation.parquet"), columns=cols,
                     filters=[("data_type", "==", "validation"), ("era", "not in", emb)])
va = va.dropna(subset=["target"])
va["pred"] = model.predict(va[feats])
pe = va.groupby("era")[["pred", "target"]].apply(lambda g: numerai_corr(g[["pred"]], g["target"])["pred"]).rename("corr")
sp = va.groupby("era")[["pred", "target"]].apply(lambda g: g["pred"].rank(pct=True).corr(g["target"], method="spearman"))
pe.to_csv(os.path.join(HERE, "results", f"baseline_{FS}_per_era.csv"))
cum = pe.cumsum(); mdd = (cum - cum.cummax()).min()
row = dict(date=dt.date.today().isoformat(), model=f"baseline_{FS}", metric="numerai_corr・エンバーゴ12", eras=len(pe), mean=pe.mean(), std=pe.std(), spearman_mean=sp.mean(),
           sharpe=pe.mean() / pe.std(), positive=(pe > 0).mean(), max_drawdown=mdd)
print("\n検証期間:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
f = os.path.join(HERE, "results", "summary.csv")
pd.DataFrame([row]).to_csv(f, mode="a", header=not os.path.exists(f), index=False)
print("完了。Claude に「numeraiの学習おわった」と伝えてください。")
