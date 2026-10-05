"""exp_007: embargo は何日必要か（EDA.md 暫定判断ログ #1 を潰す）
解釈の指針:
  * embargoを短くしてICが上がる → 直近データのリーク疑い（採用してはいけない）
  * embargoを変えてもICが動かない → リークなし。短くして学習データを増やしてよい
"""
import hull_lib as H, json
base = json.load(open("exp006_results.json"))["market_forward_excess_returns"]
res = {"embargo=5(基準)": base}
for e in [1, 21]:
    res[f"embargo={e}"] = H.run(embargo=e, label=f"embargo={e}")
    print(f"done embargo={e}: IC {res[f'embargo={e}']['mean']:+.4f}")
H.report(res, "embargo=5(基準)")
json.dump(res, open("exp007_results.json","w"), indent=1, default=float)
