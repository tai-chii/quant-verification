# -*- coding: utf-8 -*-
"""
11_selection_optimism.py  (2026-10-04) 検証期間で比べた11版（A〜K）から最良を選ぶ楽観を見積もる（点検・判定には使わない）
出どころ: Tsamardinos ほか (2018) BBC-CV、Bailey ほか (2017) PBO。研究の案としては不通過（PBO が既にある・Kaggle の Q036 と同じ形）。
指標   : エラごとの payout = 3×CORR + 15×BMC（v53_lgbm_ender60）。640エラ（0587〜1226）、12エラずつ53のまとまり。
BBC    : まとまりを復元抽出（2000回）→ 抽出した側で平均が最大の版を選ぶ → 抽出されなかったまとまりでその版の平均を測る。平均したものが「選んだ最良の補正後の成績」。
PBO    : 53まとまりを10群に分け、5群ずつを期間内・残り5群を期間外にする全252通りで、期間内の最良が期間外で中央値より下になる割合。
"""
import os, itertools, numpy as np, pandas as pd
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
src = {"neutral_ensemble_per_era.csv": "ABCD", "target_ensemble_per_era.csv": "EFG", "feature_sets_per_era.csv": "HI", "medium_ender_neutral_per_era.csv": "JK"}
P = None
for f, ks in src.items():
    d = pd.read_csv(os.path.join(R, f), dtype={"era": str}).set_index("era").sort_index()
    part = pd.DataFrame({k: 3 * d[f"corr_{k}"] + 15 * d[f"bmc_{k}"] for k in ks})
    P = part if P is None else P.join(part, how="inner")
P = P[sorted(P.columns)]; assert len(P) == 640 and P.shape[1] == 11
blk = np.arange(len(P)) // 12; B = blk.max() + 1; M = P.groupby(blk).mean().values   # 53×11（まとまりごとの平均）
naive = P.mean(); best = naive.idxmax()
rng = np.random.default_rng(20261004); sel_oob, gain_oob = [], []
cols = list(P.columns); iF = cols.index("F")
for _ in range(2000):
    s = rng.integers(0, B, B); oob = np.setdiff1d(np.arange(B), s)
    if len(oob) == 0: continue
    j = int(np.argmax(M[s].mean(0))); sel_oob.append(M[oob, j].mean()); gain_oob.append(M[oob, j].mean() - M[oob, iF].mean())
groups = np.array_split(np.arange(B), 10); ranks = []
for ins in itertools.combinations(range(10), 5):
    ib = np.concatenate([groups[g] for g in ins]); ob = np.concatenate([groups[g] for g in range(10) if g not in ins])
    j = int(np.argmax(M[ib].mean(0))); oos = M[ob].mean(0)
    ranks.append((oos < oos[j]).sum() / (len(cols) - 1))          # 期間外での相対順位（1＝最良）
ranks = np.array(ranks)
print("素朴な平均（全640エラ）:", naive.round(4).to_dict())
print(f"素朴な最良: {best} {naive[best]:.4f}（F {naive['F']:.4f}、差 {naive[best]-naive['F']:+.4f}）")
print(f"BBC 補正後の『選んだ最良』: {np.mean(sel_oob):.4f}（95%: {np.percentile(sel_oob,2.5):.4f}〜{np.percentile(sel_oob,97.5):.4f}）")
print(f"BBC 補正後の『選んだ最良 − F』: {np.mean(gain_oob):+.4f}（95%: {np.percentile(gain_oob,2.5):+.4f}〜{np.percentile(gain_oob,97.5):+.4f}、0以下の割合 {np.mean(np.array(gain_oob)<=0):.0%}）")
print(f"PBO（期間内の最良が期間外で中央値より下）: {np.mean(ranks < 0.5):.1%}、期間外での相対順位の中央値 {np.median(ranks):.2f}")
sel_counts = pd.Series([cols[int(np.argmax(M[np.random.default_rng(i).integers(0,B,B)].mean(0)))] for i in range(500)]).value_counts(normalize=True).round(2)
print("ブートストラップで選ばれた版の割合:", sel_counts.to_dict())
