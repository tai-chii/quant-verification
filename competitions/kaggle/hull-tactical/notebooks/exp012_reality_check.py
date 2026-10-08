"""exp_012: 参加者側の選択に Reality Check／SPA／Step-SPA をかける（Q036）
=========================================================================
事前登録: vault/60_検証/kaggle/2026-06_hull-tactical/exp012_事前登録.md（2026-10-02 10:35、測定前に固定）

問い: 自分が試した多数の戦略の中で最良に見えたもの（exp_011: volTarget w=20 q=0.6, +0.0212）は、
      選んだ回数を補正しても「常に1.0」より良いと言えるか。補正すると、どれだけ大きな差が要るか（選択の値段）。

手続き（事前登録どおり）
  * 評価窓: train 末尾1,500日（exp_010・011 と同じ）。指標: 公式 hull_score。基準: 常に1.0
  * U1 = exp_011 の15通り、U2 = U1 + exp_010 のマッピング9通り
  * 定常ブートストラップ（平均ブロック長21日）、B=2000、種 20261002。感度: 平均ブロック長10・63
  * 素朴な p（最良1本）、RC（White 2000）、SPA（Hansen 2005）、Step-SPA（Hsu, Hsu & Kuan 2010, α=0.10）
  * 陽性対照: pos = clip(1 + 0.5 s_t)。s_t は確率 q で sign(翌日リターン)、確率 1−q でその逆
    （2026-10-02 10:50 変更。当初の「残りは無作為の符号」は q=0.50 でも正解率75%になる誤りだった。1回目のログは exp012_log_run1_旧対照.txt）
"""
import numpy as np, pandas as pd, pickle, json, sys
import hull_lib as H
from hull_metric import hull_score

SEED, B, ALPHA = 20261002, 2000, 0.10
OUT = {}

# ---------------- データと戦略 ----------------
df = H.data(); folds = H.make_folds(len(df))
s0, e0 = folds[0][0], folds[-1][1]
fr_all = df["forward_returns"].values
fr = fr_all[s0:e0]; rf = df["risk_free_rate"].values[s0:e0]; n = len(fr)
oof = pickle.load(open("oof_cache.pkl", "rb"))
rank = np.concatenate([o["rank"] for o in oof])
assert np.allclose(np.concatenate([o["fr"] for o in oof]), fr)

def vol_target_pos(window, target_q=0.5, lookback=1260, cap=2.0):   # exp_011 と同一
    v_full = (pd.Series(fr_all).shift(1).rolling(window).std()*np.sqrt(252))
    tgt = v_full.shift(1).rolling(lookback, min_periods=252).quantile(target_q).values[s0:e0]
    v = v_full.values[s0:e0]
    return np.clip(tgt / v, 0, cap)

U1 = {}
for w in [20, 60, 120, 250]:
    for q in [0.4, 0.5, 0.6]:
        U1[f"volTarget w={w} q={q}"] = vol_target_pos(w, q)
for w in [120, 250]:
    U1[f"volTarget w={w} 21日平滑"] = pd.Series(vol_target_pos(w, 0.5)).rolling(21, min_periods=1).mean().values
U1["volTarget w=120 × モデルtilt"] = np.clip(vol_target_pos(120, 0.5) * (1 + 0.25*(2*rank-1)), 0, 2)
U1 = {k: np.nan_to_num(v, nan=1.0) for k, v in U1.items()}

def linear(k, c=1.0): return np.clip(c + k*(2*rank-1), 0, 2)
def sign_map(k, c=1.0): return np.clip(c + k*np.sign(rank-0.5), 0, 2)
E10 = {"対照:常に1.1": np.full(n, 1.1), "対照:常に1.2": np.full(n, 1.2),
       "linear k=0.10": linear(0.10), "linear k=0.25": linear(0.25),
       "linear k=0.50": linear(0.50), "linear k=1.00": linear(1.00),
       "sign k=0.25": sign_map(0.25), "sign k=0.50": sign_map(0.50),
       "旧暫定:0 or 2": np.clip(1+np.sign(rank-0.5), 0, 2)}
base = np.full(n, 1.0)

# ---------------- 再現の関門 ----------------
r11 = json.load(open("exp011_results.json")); r10 = json.load(open("exp010_results.json"))["scores"]
gate = {}
for k, p in {**U1, **E10}.items():
    ref = r11.get(k, r10.get(k))
    s = hull_score(p, fr, rf); gate[k] = (s, ref, abs(s-ref) < 1e-6)
s_base = hull_score(base, fr, rf)
print(f"基準 常に1.0: {s_base:+.6f}（記録 {r11['対照:常に1.0']:+.6f}）")
print("再現の関門（|差|<1e-6）:")
for k, (s, ref, ok) in gate.items():
    print(f"  {'OK' if ok else 'NG'}  {k:<30} 再計算 {s:+.6f}  記録 {ref:+.6f}  差 {s-ref:+.2e}")
dropped = [k for k, v in gate.items() if not v[2]]
OUT["gate"] = {k: dict(recomputed=v[0], recorded=v[1], ok=v[2]) for k, v in gate.items()}
U1 = {k: v for k, v in U1.items() if k not in dropped}
E10 = {k: v for k, v in E10.items() if k not in dropped}
print(f"外した戦略: {dropped if dropped else 'なし'}")

# ---------------- ブートストラップの道具 ----------------
def stationary_idx(n, B, mean_block, rng):
    """Politis-Romano の定常ブートストラップ（円環）。返り値 (B, n)"""
    p = 1.0 / mean_block
    idx = np.empty((B, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, B)
    new = rng.random((B, n)) < p
    starts = rng.integers(0, n, (B, n))
    for t in range(1, n):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t-1] + 1) % n)
    return idx

def hs_mat(P, FR, RF):
    """hull_score を行ごとに（B, n）。hull_metric.hull_score と同じ式"""
    m = P.shape[1]
    strat = RF*(1-P) + P*FR
    sme = np.exp(np.log1p(strat - RF).sum(1)/m) - 1
    sstd = strat.std(1, ddof=1)
    sharpe = sme / sstd * np.sqrt(252)
    mme = np.exp(np.log1p(FR - RF).sum(1)/m) - 1
    mstd = FR.std(1, ddof=1)
    volpen = 1 + np.maximum(0, sstd/mstd - 1.2)
    gap = np.maximum(0, (mme - sme)*100*252)
    return np.minimum(sharpe / (volpen * (1 + gap**2/100)), 1e6)

# 数値の一致を確認（行列版 = 公式版）
_chk = hs_mat(U1[next(iter(U1))][None, :], fr[None, :], rf[None, :])[0]
assert abs(_chk - hull_score(U1[next(iter(U1))], fr, rf)) < 1e-9

def boot_diffs(strats, idx):
    FR, RF = fr[idx], rf[idx]
    sb = hs_mat(base[idx], FR, RF)
    return np.column_stack([hs_mat(p[idx], FR, RF) - sb for p in strats])   # (B, K)

def tests(d, D, alpha=ALPHA):
    """d: (K,) 元の差、D: (B, K) リサンプルの差"""
    rn = np.sqrt(n); K = len(d)
    best = int(np.argmax(d))
    p_naive = float(np.mean(rn*(D[:, best]-d[best]) >= rn*d[best]))
    V = rn*d.max(); Vs = (rn*(D - d)).max(1)
    p_rc = float(np.mean(Vs >= V))
    om = (rn*D).std(0, ddof=1)
    A = np.sqrt(2*np.log(np.log(n)))
    keep = rn*d/om > -A                                  # Hansen の一致性のある中心化
    Z = D - d*keep
    T = max((rn*d/om).max(), 0.0); Ts = np.maximum((rn*Z/om).max(1), 0.0)
    p_spa = float(np.mean(Ts >= T))
    # Step-SPA（Hsu, Hsu & Kuan 2010）: 棄却されたものを除いて臨界値を出し直す
    rejected = np.zeros(K, bool)
    while True:
        rem = ~rejected
        if rem.sum() == 0: break
        crit = np.quantile((rn*Z[:, rem]/om[rem]).max(1), 1-alpha)
        new = rem & (rn*d/om > crit)
        if not new.any(): break
        rejected |= new
    # 選択の楽観: 各リサンプルで最良を選び、その戦略の元データでの差
    kb = np.argmax(D, 1)
    optimism_est = float(np.mean(d[kb]))
    return dict(best=best, d_best=float(d[best]), p_naive=p_naive, p_rc=p_rc, p_spa=p_spa,
                stepspa_rejected=int(rejected.sum()), rejected_idx=np.where(rejected)[0].tolist(),
                selected_strategy_expected_diff=optimism_est,
                pct_selected_best=float(np.mean(kb == best)))

def paired_ci(d_k, D_k):
    lo, hi = np.percentile(D_k, [2.5, 97.5])
    return float(lo), float(hi), bool(lo > 0 or hi < 0)

rng = np.random.default_rng(SEED)
IDX = {21: stationary_idx(n, B, 21, rng), 10: stationary_idx(n, B, 10, rng), 63: stationary_idx(n, B, 63, rng)}

def run_universe(name, S, blocks=(21, 10, 63)):
    keys = list(S); strats = [S[k] for k in keys]
    d = np.array([hull_score(p, fr, rf) - s_base for p in strats])
    res = {}
    for bl in blocks:
        D = boot_diffs(strats, IDX[bl])
        t = tests(d, D)
        t["best_name"] = keys[t["best"]]; t["rejected_names"] = [keys[i] for i in t["rejected_idx"]]
        if bl == 21:
            naive_sig = {keys[i]: paired_ci(d[i], D[:, i]) for i in range(len(keys))}
            t["naive_ci_sig"] = [k for k, v in naive_sig.items() if v[2]]
            t["naive_ci"] = {k: v[:2] for k, v in naive_sig.items()}
            t["D21"] = D
        res[bl] = t
        print(f"\n[{name}] K={len(keys)} 平均ブロック長{bl}: 最良 {t['best_name']} 差 {t['d_best']:+.4f}"
              f" | 素朴p {t['p_naive']:.3f} | RC p {t['p_rc']:.3f} | SPA p {t['p_spa']:.3f}"
              f" | Step-SPA 棄却 {t['stepspa_rejected']}本 | 選んだ戦略の差の期待値 {t['selected_strategy_expected_diff']:+.4f}"
              f" | 最良が選ばれる割合 {t['pct_selected_best']:.0%}")
        if bl == 21: print(f"  素朴な95%CIで有意（exp_011 の判定）: {t['naive_ci_sig'] or 'なし'}")
    return keys, d, res

k1, d1, R1 = run_universe("U1", U1)
k2, d2, R2 = run_universe("U2", {**U1, **E10}, blocks=(21,))
OUT["U1"] = {"keys": k1, "d": d1.tolist(), **{str(b): {kk: vv for kk, vv in r.items() if kk != "D21"} for b, r in R1.items()}}
OUT["U2"] = {"keys": k2, "d": d2.tolist(), **{str(b): {kk: vv for kk, vv in r.items() if kk != "D21"} for b, r in R2.items()}}

# ---------------- 陽性対照（検出力） ----------------
print("\n=== 陽性対照: U1 に1本混ぜたときの検出力（α=0.10、各q 200回、平均ブロック長21）===")
D_U1 = R1[21]["D21"]; idx21 = IDX[21]; FR21, RF21 = fr[idx21], rf[idx21]
sb21 = hs_mat(base[idx21], FR21, RF21)
rn = np.sqrt(n); A = np.sqrt(2*np.log(np.log(n)))
QS = [0.500, 0.505, 0.510, 0.515, 0.520, 0.525, 0.530, 0.540]; R = 200   # 変更（2026-10-02 10:50）: 格子を細かく
crng = np.random.default_rng(SEED + 1)
power = {}
for q in QS:
    hit_step = hit_single = 0; dc_list = []
    for r in range(R):
        right = crng.random(n) < q            # 変更（2026-10-02 10:50）: 正解率 = q
        sg = np.sign(fr); sg[sg == 0] = 1.0
        s = np.where(right, sg, -sg)
        pc = np.clip(1 + 0.5*s, 0, 2)
        dc = hull_score(pc, fr, rf) - s_base; dc_list.append(dc)
        Dc = hs_mat(pc[idx21], FR21, RF21) - sb21
        # 1本だけの素朴な検定
        hit_single += np.mean(rn*(Dc - dc) >= rn*dc) <= ALPHA
        # U1 + 対照 の Step-SPA で対照が棄却されるか
        d = np.append(d1, dc); D = np.column_stack([D_U1, Dc])
        om = (rn*D).std(0, ddof=1); keep = rn*d/om > -A; Z = D - d*keep
        rej = np.zeros(len(d), bool)
        while True:
            rem = ~rej
            crit = np.quantile((rn*Z[:, rem]/om[rem]).max(1), 1-ALPHA)
            new = rem & (rn*d/om > crit)
            if not new.any(): break
            rej |= new
        hit_step += rej[-1]
    power[q] = dict(single=hit_single/R, stepspa=hit_step/R, mean_diff=float(np.mean(dc_list)))
    print(f"  q={q:.3f}  対照の平均の差 {np.mean(dc_list):+.4f}  検出力: 1本だけ {hit_single/R:.0%} / U1に混ぜて Step-SPA {hit_step/R:.0%}", flush=True)
OUT["power"] = {str(k): v for k, v in power.items()}

json.dump(OUT, open("exp012_results.json", "w"), indent=1, ensure_ascii=False, default=float)
print("\n保存: exp012_results.json")
