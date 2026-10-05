"""exp_010: 評価をコンペの実態に合わせる（fold平均 → 単一連続期間 + ブロックブートストラップ）
=========================================================================================
exp_009 の問題: 6foldに割ってスコアを平均したが、**コンペは1本の連続期間を1回採点する**。
6分割は (a) 実態と違い (b) fold std が ~1.0 と巨大で検出力がない。

修正: OOF 1,500日を1本の期間として公式指標で採点し、
      不確実性は 21日ブロックのブートストラップ（対応あり）で出す。
"""
import numpy as np, pickle, json
from hull_metric import hull_score, diagnostics

oof = pickle.load(open("oof_cache.pkl","rb"))
rank = np.concatenate([o["rank"] for o in oof])
fr   = np.concatenate([o["fr"]   for o in oof])
rf   = np.concatenate([o["rf"]   for o in oof])
n = len(rank); print(f"OOF連続期間: {n}日")

def const(c):  return lambda r: np.full(len(r), c)
def linear(k, c=1.0): return lambda r: np.clip(c + k*(2*r-1), 0, 2)
def sign_map(k, c=1.0): return lambda r: np.clip(c + k*np.sign(r-0.5), 0, 2)
MAPS = {"対照:常に1.0": const(1.0), "対照:常に1.1": const(1.1), "対照:常に1.2": const(1.2),
        "linear k=0.10": linear(0.10), "linear k=0.25": linear(0.25),
        "linear k=0.50": linear(0.50), "linear k=1.00": linear(1.00),
        "sign k=0.25": sign_map(0.25), "sign k=0.50": sign_map(0.50),
        "旧暫定:0 or 2": lambda r: np.clip(1+np.sign(r-0.5),0,2)}

print(f"\n{'マッピング':<18}{'公式スコア':>12}   内訳")
scores = {}
for k, f in MAPS.items():
    pos = f(rank); s = hull_score(pos, fr, rf); scores[k] = s
    d = diagnostics(pos, fr, rf)
    print(f"  {k:<16}{s:>+12.4f}   生Sharpe {d['sharpe_raw']:+.3f}  ボラ比 {d['vol_ratio']:.2f}"
          f"  罰(vol×ret) {d['vol_penalty']*d['return_penalty']:.3f}  平均配分 {d['mean_pos']:.2f}")

# --- 21日ブロック・ペアードブートストラップ ---
BLOCK, NB = 21, 2000
rng = np.random.default_rng(0)
nblk = n // BLOCK
base = "対照:常に1.0"
print(f"\n=== 対 {base}: 21日ブロック・ペアードブートストラップ (n={NB}) ===")
idx_all = []
for _ in range(NB):
    starts = rng.integers(0, n - BLOCK, size=nblk)
    idx_all.append(np.concatenate([np.arange(s, s+BLOCK) for s in starts]))
bpos = MAPS[base](rank)
for k, f in sorted(MAPS.items(), key=lambda kv: -scores[kv[0]]):
    if k == base: continue
    pos = f(rank); diffs = np.empty(NB)
    for i, idx in enumerate(idx_all):
        diffs[i] = hull_score(pos[idx], fr[idx], rf[idx]) - hull_score(bpos[idx], fr[idx], rf[idx])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    p_better = float((diffs > 0).mean())
    v = "**有意**" if lo > 0 or hi < 0 else "差なし"
    print(f"  {k:<16} 差 {scores[k]-scores[base]:+.4f}  95%CI [{lo:+.4f}, {hi:+.4f}]"
          f"  P(勝ち)={p_better:.0%}  {v}")
json.dump({"scores": scores}, open("exp010_results.json","w"), indent=1, default=float)
