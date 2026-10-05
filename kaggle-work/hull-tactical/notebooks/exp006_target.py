"""exp_006: 学習の目的変数はどちらが良いか（EDA.md 暫定判断ログ #2 を潰す）
評価は常に market_forward_excess_returns で固定し、学習ターゲットだけ差し替える。"""
import hull_lib as H, json
res = {}
for t in ["market_forward_excess_returns", "forward_returns"]:
    res[t] = H.run(train_target=t, label=t)
    print(f"done {t}: IC {res[t]['mean']:+.4f}")
H.report(res, "market_forward_excess_returns")
json.dump(res, open("exp006_results.json","w"), indent=1, default=float)
