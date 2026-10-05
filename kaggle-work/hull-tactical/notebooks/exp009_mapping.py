"""exp_009: 予測→配分マッピングを公式指標で決める（暫定判断ログ #3,#6 を潰す）
確定済みパイプライン(embargo=1, A/B/C/D ランク平均)のOOF予測を1度だけ作り、
その上でマッピングだけを差し替えて **公式指標** で比較する。
最重要の対照: 「モデルを使わない定数配分」。これに勝てなければ全部無意味。
"""
import numpy as np, pandas as pd, lightgbm as lgb, json, pickle, os
from scipy.stats import spearmanr
import hull_lib as H
from hull_metric import hull_score, diagnostics

CACHE = "oof_cache.pkl"
df = H.data(); feats = [c for c in df.columns if c not in H.TRAIN_ONLY + ["date_id"]]
folds = H.make_folds(len(df)); EMB = 1

if os.path.exists(CACHE):
    oof = pickle.load(open(CACHE, "rb"))
else:
    oof = []
    for va_s, va_e in folds:
        tr_end = va_s - EMB
        X_va = df.loc[va_s:va_e-1, feats]
        ranks = []
        for name, (mode, p) in H.CANDIDATES.items():
            idx = (df.index[(df.date_id >= p) & (df.index < tr_end)] if mode == "abs"
                   else df.index[(df.index >= max(0, tr_end-p)) & (df.index < tr_end)])
            Xtr, ytr = df.loc[idx, feats], df.loc[idx, H.EVAL_TARGET]
            pr = np.zeros(len(X_va))
            for sd in (42, 43, 44):
                pr += lgb.LGBMRegressor(random_state=sd, **H.DEFAULT_PARAMS).fit(Xtr, ytr).predict(X_va)
            ranks.append(pd.Series(pr/3).rank(pct=True).values)
        oof.append(dict(rank=np.mean(ranks, axis=0),
                        fr=df.loc[va_s:va_e-1, "forward_returns"].values,
                        rf=df.loc[va_s:va_e-1, "risk_free_rate"].values,
                        y=df.loc[va_s:va_e-1, H.EVAL_TARGET].values))
        print(f"fold done ({va_s})")
    pickle.dump(oof, open(CACHE, "wb"))

# --- マッピング候補 ---
def const(c):        return lambda r: np.full(len(r), c)
def linear(k, c=1.0):return lambda r: np.clip(c + k*(2*r-1), 0, 2)
def sign_map(k, c=1.0): return lambda r: np.clip(c + k*np.sign(r-0.5), 0, 2)
MAPS = {
 "対照:常に1.0(市場保有)": const(1.0),
 "対照:常に1.2":           const(1.2),
 "対照:常に0.8":           const(0.8),
 "旧暫定:sign 0 or 2":     lambda r: np.clip(1+np.sign(r-0.5), 0, 2),
 "linear k=0.25":          linear(0.25),
 "linear k=0.50":          linear(0.50),
 "linear k=1.00":          linear(1.00),
 "linear k=0.50 c=1.2":    linear(0.50, 1.2),
 "linear k=0.25 c=1.2":    linear(0.25, 1.2),
 "sign k=0.25":            sign_map(0.25),
 "sign k=0.50":            sign_map(0.50),
}
res = {}
for name, f in MAPS.items():
    sc = [hull_score(f(o["rank"]), o["fr"], o["rf"]) for o in oof]
    res[name] = sc
print(f"\n{'マッピング':<24}{'公式スコア':>12}{'std':>9}{'最悪fold':>11}{'正fold':>8}")
for k, v in sorted(res.items(), key=lambda kv: -np.mean(kv[1])):
    v = np.array(v)
    print(f"  {k:<22}{v.mean():>+12.4f}{v.std(ddof=1):>9.4f}{v.min():>+11.4f}{int((v>0).sum()):>6}/6")

base = "対照:常に1.0(市場保有)"
print(f"\n=== 対応あり比較（基準: {base}）===")
for k, v in sorted(res.items(), key=lambda kv: -np.mean(kv[1])):
    if k == base: continue
    d = np.array(v) - np.array(res[base]); se = d.std(ddof=1)/np.sqrt(len(d)); t = d.mean()/se
    verdict = "**有意**" if abs(t) > 2 else ("保留" if abs(t) > 1 else "差なし")
    print(f"  {k:<22}: {d.mean():+.4f}  se_d {se:.4f}  比 {t:+.2f}  {verdict}")

print("\n=== 内訳（fold平均）: どのペナルティで削られているか ===")
for k in ["対照:常に1.0(市場保有)", "旧暫定:sign 0 or 2", "linear k=0.50", "linear k=0.25 c=1.2"]:
    ds = [diagnostics(MAPS[k](o["rank"]), o["fr"], o["rf"]) for o in oof]
    m = {kk: np.mean([d[kk] for d in ds]) for kk in ds[0]}
    print(f"  {k:<22} 生Sharpe {m['sharpe_raw']:+.3f}  ボラ比 {m['vol_ratio']:.2f} "
          f"(罰{m['vol_penalty']:.2f})  リターン差 {m['return_gap']:.2f} (罰{m['return_penalty']:.2f})")
json.dump(res, open("exp009_results.json","w"), indent=1, default=float)
