# 事後の点検（判定に使わない）: 並べ替え帰無の q 別の有意率と、ボラの塊を残す符号反転の帰無での (a)。
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kensho_variance_ratio_setting_dependence_q148 as K
rng = np.random.default_rng(7); B = 300
perm_sig = np.zeros(4); flip_sig = np.zeros(4); n = 0
perm_a = []; flip_a = []; flip_any = []
cells_perm = []; cells_flip = []
for sym in K.SYMS if hasattr(K, 'SYMS') else []:
    d = K.load_daily(sym)
    if d is None: continue
    yrs = K.year_returns(d.time.values, d.close.values)
    for y, r in yrs.items():
        T = len(r); n += 1
        P = np.array([rng.permutation(T) for _ in range(B)]); Rp = r[P]
        S = rng.choice([-1.0, 1.0], size=(B, T)); Rf = (r - r.mean()) * S + r.mean()
        Zp = np.column_stack([K.lm_variance_ratio(Rp, q)[1] for q in K.QS])
        Zf = np.column_stack([K.lm_variance_ratio(Rf, q)[1] for q in K.QS])
        cells_perm.append(np.abs(Zp) >= 1.96); cells_flip.append(np.abs(Zf) >= 1.96)
cp = np.stack(cells_perm, 1); cf = np.stack(cells_flip, 1)   # (B, cells, 4)
def a_share(c):
    k = c.sum(2); return ((k >= 1) & (k <= 3)).mean(1), (k >= 1).mean(1)
ap, anp = a_share(cp); af, anf = a_share(cf)
out = dict(n_cells=n, B=B,
  perm_sig_by_q=dict(zip(map(str, K.QS), cp.mean((0, 1)).round(4).tolist())),
  flip_sig_by_q=dict(zip(map(str, K.QS), cf.mean((0, 1)).round(4).tolist())),
  perm_a_mean=float(ap.mean()), perm_a_sd=float(ap.std()), perm_any_mean=float(anp.mean()),
  flip_a_mean=float(af.mean()), flip_a_sd=float(af.std()), flip_any_mean=float(anf.mean()),
  obs_a=0.08536585365853659, z_obs_vs_flip=float((0.08536585365853659 - af.mean()) / af.std()))
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'posthoc_q148_null_by_q_and_signflip.json'), 'w'), ensure_ascii=False, indent=1)
