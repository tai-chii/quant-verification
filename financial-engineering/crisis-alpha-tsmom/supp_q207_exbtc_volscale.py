#!/usr/bin/env python3
"""Q207 の補足（記述のみ・判定には使わない。2026-10-10 Opus /lab）。
本体の判定（L=252・等加重・値幅調整なし）は変えない。本体の 2019-05 に L252 −1891bp / L60 +3424bp の外れ月があり、
等加重（値幅調整なし）で BTCUSD が月次損益を支配している疑いがあるため、(1) 危機月の銘柄別寄与、(2) BTC 抜き 14 銘柄、
(3) 銘柄ごとに日次損益を過去 60 日の標準偏差で割った値幅調整版（Hurst 2017 は値幅目標つき）を記述する。危機月の定義・帰無は本体と同じ。"""
import importlib.util, os, json, numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__))
sp=importlib.util.spec_from_file_location("m",os.path.join(HERE,"kensho_crisis_alpha_q207.py")); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
rng=np.random.default_rng(m.SEED); B=1000
daily={}
for s in m.SYMS:
    df=m.load_d1(s); c=df["close"].values; cb=m.cost_bp_oneway(s,c)
    x=pd.Series(m.pnl_bp(m.tsmom_pos(c,252),c,cb),index=df["time"].values); x.iloc[:253]=np.nan; daily[s]=x
P=pd.concat(daily,axis=1)
us=m.load_d1("US500").set_index("time")["close"]; mu=us.resample("ME").last().pct_change().dropna(); mu=mu[mu.index>="2011-10-01"]
P=P[P.index>=mu.index.min()-pd.offsets.MonthBegin(1)]
vol=P.rolling(60,min_periods=40).std().shift(1)
variants={"base15":P,"exBTC14":P.drop(columns="BTCUSD"),"volscaled15":(P/vol)*100,"volscaled_exBTC14":(P/vol*100).drop(columns="BTCUSD")}
out={}
for k,Q in variants.items():
    mo=Q.mean(axis=1,skipna=True).resample("ME").sum(min_count=5)
    d=pd.DataFrame({"p":mo,"us":mu}).dropna(); thr=d.us.quantile(.1); cr=(d.us<=thr).values; x=d.p.values
    obs=x[cr].mean()-x[~cr].mean(); null=[ (lambda c: x[c].mean()-x[~c].mean())(rng.permutation(cr)) for _ in range(B)]
    z,_=m.z_of(obs,null)
    out[k]={"n_months":len(d),"n_crisis":int(cr.sum()),"crisis_mean":m.f(x[cr].mean()),"crisis_t":m.f(m.tstat(x[cr])),"rest_mean":m.f(x[~cr].mean()),"diff_z":m.f(z),
            "unit":"bp" if "vol" not in k else "銘柄ごとの日次損益/過去60日σ×100 の等加重平均の月次合計"}
# 危機月の銘柄別寄与（等加重平均への寄与 = 銘柄の月次合計/銘柄数）
mo_s=P.resample("ME").sum(min_count=5); d=mo_s.join(mu.rename("us")).dropna(subset=["us"]); thr=d.us.quantile(.1); cm=d[d.us<=thr].drop(columns="us")
out["crisis_contrib_bp_per_sym_mean"]={s:m.f(v,1) for s,v in cm.mean().sort_values().items()}
out["2019-05_by_sym_bp"]={s:m.f(v,1) for s,v in mo_s.loc["2019-05"].iloc[0].sort_values().items()}
p=os.path.join(HERE,"results","Q207_supp_exbtc_volscale_20261010.json"); json.dump(out,open(p,"w"),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
