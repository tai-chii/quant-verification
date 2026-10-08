"""exp_008: embargo=1 の上昇はリークか、実運用可能なエッジか
=============================================================
禁止事項5（スコアが跳ねたらまずリークを疑う）に基づく検証。

2つの仮説が同じ観測を説明してしまう:
  H1 リーク  : 直近データが検証期間の情報を含んでいる
  H2 実エッジ: 直近データが現在のレジームを教えている（本番でも使える）

識別方法: embargo を負まで振ってカーブを見る。
  embargo<=0 は学習に検証行そのものを混ぜる = 確実なリーク（陽性対照）
  * カーブが連続的に上昇 → embargo=1 はリーク勾配の上。採用不可
  * embargo<=0 で崖ができ、1〜5が平坦 → 1 は崖の安全側。採用可
"""
import hull_lib as H, json
res = {}
for e in [-5, 0, 1, 2, 3]:
    r = H.run(embargo=e, label=f"emb{e}")
    res[f"embargo={e:>3}"] = r
    print(f"  embargo={e:>3}  IC {r['mean']:+.4f} ± {r['std']:.4f}")
prev = json.load(open("exp007_results.json"))
res["embargo=  5"] = prev["embargo=5(基準)"]
res["embargo= 21"] = prev["embargo=21"]

print("\n=== embargo カーブ ===")
for k in sorted(res, key=lambda k: int(k.split("=")[1])):
    r = res[k]
    print(f"  {k}  IC {r['mean']:+.4f}  std {r['std']:.4f}  最悪 {r['worst']:+.4f}  正 {r['n_pos']}/6")
json.dump(res, open("exp008_results.json","w"), indent=1, default=float)
