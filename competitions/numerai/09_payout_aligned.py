# -*- coding: utf-8 -*-
"""
09_payout_aligned.py  (2026-10-04) 報酬の式に合わせた指標で medium 対 small を比べ直す

=== 事前に固定した計画（合成指標の結果を見る前に書いた） ===
背景 : 08 で主の指標を BMC にしたが、公式の報酬は「3 × CORR60 + 15 × MMC60」（ラウンド1343〜、
       docs.numer.ai/numerai-tournament/staking で 2026-10-04 に確認）。判定の軸がずれていた。
確認 : v5.3 の validation では target と target_ender_60 が完全に一致（差の平均 0.0・相関 1.0）。
       よって 08 の CORR は報酬と同じターゲットで測れていた。
MMC  : メタモデルの予測ファイルは、Mac・クラウドともに Numerai の API に届かず取得できなかった。
       事前の取り決めどおり、v53_lgbm_ender60 に対する BMC で代わりに測る（MMC そのものではない）。
比べる : F（xerxes_60・small 42本＝今の taichi_te）と I（xerxes_60・medium 780本）だけ。
データ : results/feature_sets_per_era.csv（08 の出力。ターゲット・ベンチマーク・エラが同じなので学習し直さない）。
指標 : エラごとの payout = 3×CORR + 15×BMC。差（I−F）を12エラのまとまりで標準誤差を出す。
判定 : 比較は1回。差÷SE > 2 で採用候補、1〜2 で保留、1 未満で「区別できない」。
注意 : 同じ検証期間を見るのは2回目（CORR と BMC は個別に見ている）。採用候補でも本番は差し替えず、
       別スロットで live 成績を確かめてから決める。
       あわせて medium の推論が実行制限（4GB・10分）に収まるかを測る（判定には使わない）。
出力 : results/payout_aligned.csv
"""
import os, glob, time, resource
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
pe = pd.read_csv(os.path.join(HERE, "results", "feature_sets_per_era.csv"), dtype={"era": str}).sort_values("era").reset_index(drop=True)
for k in "FI":
    pe[f"pay_{k}"] = 3 * pe[f"corr_{k}"] + 15 * pe[f"bmc_{k}"]


def block_se(d, B=12):
    blk = d.groupby(np.arange(len(d)) // B).mean()
    return blk.std(ddof=1) / np.sqrt(len(blk))


out = []
for label, sub in [("全体", pe), ("直近214（参考）", pe.tail(214).reset_index(drop=True))]:
    row = {"期間": label, "エラ数": len(sub)}
    for k in "FI":
        p = sub[f"pay_{k}"]
        row[f"payout平均_{k}"] = p.mean(); row[f"payoutシャープ_{k}"] = p.mean() / p.std()
        row[f"プラスのエラ割合_{k}"] = (p > 0).mean()
    d = sub["pay_I"] - sub["pay_F"]
    row["差の平均"] = d.mean(); row["差÷SE"] = d.mean() / block_se(d)
    row["CORR寄与の差"] = 3 * (sub.corr_I - sub.corr_F).mean(); row["BMC寄与の差"] = 15 * (sub.bmc_I - sub.bmc_F).mean()
    out.append(row)
res = pd.DataFrame(out); res.to_csv(os.path.join(HERE, "results", "payout_aligned.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(res.round(5).T.to_string())
z = res.iloc[0]["差÷SE"]
print(f"判定（I medium 対 F small, payout=3CORR+15BMC）: 差÷SE={z:+.2f} → " +
      ("採用候補（live 確認へ）" if z > 2 else "保留" if abs(z) >= 1 else "区別できない"))
