"""exp_011: ボラティリティ・ターゲティング（4位解法の核）を測る
================================================================
出典: [4th Place] Technical Model, No Learning: Short Term Reversal (YannFb, 2026-07-04)
  「予測精度の限界的改善より、ポートフォリオ構築の方が寄与が大きい」
  「vol targeting overlay が、alpha へのどんな改良よりスコアに効いた」
  Buy&Hold: Sharpe 0.33 / ボラ19.2% → 彼らの解: Sharpe 0.66 / ボラ14.3%
  = **予測を良くしたのではなく、ボラを下げて Sharpe を上げた**

仮説: 予測を一切使わず、ボラティリティ・ターゲティングだけで
      「常に1.0」(+0.6664) を超えられるのではないか。

先読み厳禁: 時刻 t の決定に使えるのは forward_returns[..t-2] まで
  （forward_returns[t-1] は t-1→t のリターンで、t の時点で観測済み）
"""
import numpy as np, pandas as pd, pickle, json
import hull_lib as H
from hull_metric import hull_score, diagnostics

df = H.data(); folds = H.make_folds(len(df))
eval_s, eval_e = folds[0][0], folds[-1][1]
fr_all = df["forward_returns"].values
oof = pickle.load(open("oof_cache.pkl","rb"))
rank = np.concatenate([o["rank"] for o in oof])
fr = fr_all[eval_s:eval_e]; rf = df["risk_free_rate"].values[eval_s:eval_e]
print(f"評価期間: 行{eval_s}-{eval_e} ({len(fr)}日)")

def realized_vol(window):
    """時刻tの決定時点で観測可能な過去windowの実現ボラ（年率）"""
    s = pd.Series(fr_all).shift(1).rolling(window).std() * np.sqrt(252)
    return s.values[eval_s:eval_e]

def vol_target_pos(window, target_q=0.5, lookback=1260, cap=2.0):
    """target = 過去lookback日の実現ボラの分位点（拡張窓・先読みなし）"""
    v_full = (pd.Series(fr_all).shift(1).rolling(window).std()*np.sqrt(252))
    tgt = v_full.shift(1).rolling(lookback, min_periods=252).quantile(target_q).values[eval_s:eval_e]
    v = v_full.values[eval_s:eval_e]
    return np.clip(tgt / v, 0, cap)

base = np.full(len(fr), 1.0)
print(f"\n基準 常に1.0: {hull_score(base, fr, rf):+.4f}")
print(f"\n{'戦略':<34}{'公式スコア':>11}{'生Sharpe':>10}{'ボラ比':>8}{'平均配分':>9}")
res = {"対照:常に1.0": base}
for w in [20, 60, 120, 250]:
    for q in [0.4, 0.5, 0.6]:
        res[f"volTarget w={w} q={q}"] = vol_target_pos(w, q)
# 4位解法の指摘「長めの窓・頻繁に更新しない」を反映した版
for w in [120, 250]:
    p = vol_target_pos(w, 0.5)
    p = pd.Series(p).rolling(21, min_periods=1).mean().values   # 21日ごとの平滑化
    res[f"volTarget w={w} 21日平滑"] = p
# モデルのtiltと組み合わせ
vt = vol_target_pos(120, 0.5)
res["volTarget w=120 × モデルtilt"] = np.clip(vt * (1 + 0.25*(2*rank-1)), 0, 2)

scores = {}
for k, pos in res.items():
    pos = np.nan_to_num(pos, nan=1.0)
    s = hull_score(pos, fr, rf); scores[k] = s
    d = diagnostics(pos, fr, rf)
    print(f"  {k:<32}{s:>+11.4f}{d['sharpe_raw']:>+10.3f}{d['vol_ratio']:>8.2f}{d['mean_pos']:>9.2f}")

# ブロック・ブートストラップ
BLOCK, NB, n = 21, 2000, len(fr)
rng = np.random.default_rng(0); nblk = n // BLOCK
idxs = [np.concatenate([np.arange(s, s+BLOCK) for s in rng.integers(0, n-BLOCK, nblk)]) for _ in range(NB)]
print(f"\n=== 対 常に1.0: 21日ブロック・ペアード・ブートストラップ ===")
for k in sorted(scores, key=lambda k: -scores[k]):
    if k == "対照:常に1.0": continue
    pos = np.nan_to_num(res[k], nan=1.0)
    d = np.array([hull_score(pos[i], fr[i], rf[i]) - hull_score(base[i], fr[i], rf[i]) for i in idxs])
    lo, hi = np.percentile(d, [2.5, 97.5])
    v = "**有意**" if lo > 0 or hi < 0 else "差なし"
    print(f"  {k:<32} 差 {scores[k]-scores['対照:常に1.0']:+.4f}  CI[{lo:+.4f},{hi:+.4f}]  P(勝ち)={(d>0).mean():.0%}  {v}")
json.dump(scores, open("exp011_results.json","w"), indent=1, default=float)
