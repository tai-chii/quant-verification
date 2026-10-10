# 記述のみ（判定に使わない）: ドル因子の日次 R²（各ペアの対ドル・リターンを DF に回帰）と L=60 の年ごとの A・B・差
import sys, os, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kensho_dollar_factor_momentum_q208 as k
syms = k.FX6; data = {s: k.load_d1(s).set_index("time") for s in syms}
idx = None
for s in syms: idx = data[s].index if idx is None else idx.intersection(data[s].index)
close = pd.DataFrame({s: data[s].loc[idx, "close"] for s in syms}); ret = close.pct_change()
u = pd.DataFrame({s: ret[s] * k.USD_SIGN[s] for s in syms}).dropna(); DF = u.mean(axis=1)
r2 = {s: float(np.corrcoef(u[s], DF)[0, 1] ** 2) for s in syms}
I = np.exp(np.log1p(pd.DataFrame({s: ret[s]*k.USD_SIGN[s] for s in syms}).mean(axis=1).fillna(0)).cumsum()).values
cb = {s: k.cost_bp_oneway(s, close[s].values) for s in syms}
sig = k.tsmom_pos(I, 60)
A = np.mean([k.pnl_bp(sig * k.USD_SIGN[s], close[s].values, cb[s]) for s in syms], axis=0)
B = np.mean([k.pnl_bp(k.tsmom_pos(close[s].values, 60), close[s].values, cb[s]) for s in syms], axis=0)
A[:61] = np.nan; B[:61] = np.nan
y = pd.DataFrame({"A": A, "B": B}, index=idx).groupby(idx.year).mean(); y["diff"] = y.A - y.B
out = {"r2_daily_on_DF": {s: round(v, 3) for s, v in r2.items()}, "r2_mean": round(float(np.mean(list(r2.values()))), 3),
       "yearly_L60_bp": {int(i): {c: round(float(y.loc[i, c]), 2) for c in y.columns} for i in y.index},
       "sharpe_ann_L60": {"A": k.sharpe_ann(A[61:]), "B": k.sharpe_ann(B[61:])}, "maxdd_bp_L60": {"A": k.max_drawdown(A[61:]), "B": k.max_drawdown(B[61:])}}
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Q208_supp_r2_yearly.json"); json.dump(out, open(p, "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False))
