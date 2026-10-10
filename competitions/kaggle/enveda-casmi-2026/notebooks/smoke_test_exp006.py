"""Smoke test for exp_006 (code-correctness + plausibility only, NOT an LB estimate).

Same design as exp_004's smoke test: read a few row groups of train.parquet (the full
2.5M-row file OOMs the 3.8GB dev sandbox), hold out N molecules (by inchikey14) as fake
"test", use the rest as the library, score with the official casmi_metric. Because the
held-out structure is removed from the library by construction, train-only ranking is
always 0; only COCONUT can hit, so this measures whether the analog channel helps place
the right COCONUT structure higher than mass-closeness does.

Also checks that exp_006's vectorised cosine reproduces exp_005's scalar cosine exactly.

Usage: python3 smoke_test_exp006.py <train.parquet> <coconut_lite.csv> <notebooks_dir> [row_groups=3] [n_hold=60] [seed=0]
"""
import sys
import time
import importlib.util
import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    train_path, coconut_path, nb_dir = sys.argv[1:4]
    n_rg = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    n_hold = int(sys.argv[5]) if len(sys.argv) > 5 else 60
    seed = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    e6 = load('e6', f'{nb_dir}/kaggle_inference_exp006_analog_propagation.py')
    e5 = load('e5', f'{nb_dir}/kaggle_inference_exp005_coconut_lowconf.py')
    metric = load('metric', f'{nb_dir}/casmi_metric.py')

    t0 = time.time()
    pf = pq.ParquetFile(train_path)
    cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'adduct', 'ms2_mzs',
            'ms2_normalized_intensities', 'instrument_type']
    rng = np.random.default_rng(seed)
    rgs = rng.choice(pf.metadata.num_row_groups, size=n_rg, replace=False)
    df = pd.concat([pf.read_row_group(int(i), columns=cols).to_pandas() for i in rgs], ignore_index=True)
    print(f'loaded row groups {sorted(rgs.tolist())}: {len(df)} rows, {df.inchikey14.nunique()} structures, '
          f'{time.time() - t0:.0f}s')

    # --- cosine equivalence check (exact channel must be byte-for-byte exp_001 logic) ---
    sub = df.sample(400, random_state=seed)
    a = sub.iloc[:200]; b = sub.iloc[200:]
    maxdiff = 0.0
    for (_, ra), (_, rb) in zip(a.iterrows(), b.iterrows()):
        x = (np.asarray(ra.ms2_mzs, float), np.asarray(ra.ms2_normalized_intensities, float))
        y = (np.asarray(rb.ms2_mzs, float), np.asarray(rb.ms2_normalized_intensities, float))
        old = e5.matched_peak_cosine(x[0], x[1], y[0], y[1])
        new = e6.matched_peak_cosine(x[0], x[1], y[0], y[1])
        maxdiff = max(maxdiff, abs(old - new))
        old_self = e5.matched_peak_cosine(x[0], x[1], x[0], x[1])
        new_self = e6.matched_peak_cosine(x[0], x[1], x[0], x[1])
        maxdiff = max(maxdiff, abs(old_self - new_self))
    print(f'cosine equivalence exp_005 vs exp_006 (200 random pairs + self): max |diff| = {maxdiff:.3e}')
    assert maxdiff < 1e-9

    # --- hold out molecules (timsTOF, singly-charged adducts) ---
    ok = df.adduct.isin(list(e6.ADDUCT_DELTA))
    if df.instrument_type.eq('timsTOF').sum() >= 20 * n_hold:  # prefer timsTOF (= test instrument) when available
        ok &= df.instrument_type.eq('timsTOF')
    iks = df.loc[ok, 'inchikey14'].unique()
    hold = set(rng.choice(iks, size=n_hold, replace=False))
    lib = df[~df.inchikey14.isin(hold)].reset_index(drop=True)
    test = df[df.inchikey14.isin(hold) & ok].reset_index(drop=True)
    tidx = e6.TrainIndex(lib[['inchikey14', 'normalized_smiles', 'precursor_mz', 'adduct',
                              'ms2_mzs', 'ms2_normalized_intensities']])
    cc = e6.build_coconut_index(coconut_path)
    in_coco = len(hold & set(cc.inchikey14))
    print(f'library {len(lib)} rows; held-out {n_hold} molecules ({len(test)} spectra); '
          f'{in_coco} of them exist in COCONUT (the only ones that can be hit)')

    sol_rows, base_rows, new_rows = [], [], []
    n_ev = n_changed = n_coco_top1 = 0
    t1 = time.time()
    for ik, g in test.groupby('inchikey14'):
        adduct = g.adduct.iloc[0]
        g = g[g.adduct == adduct]
        spectra = [(float(r.precursor_mz), np.asarray(r.ms2_mzs, float),
                    np.asarray(r.ms2_normalized_intensities, float)) for _, r in g.iterrows()]
        exact, coco, evidence, base, new = e6.rank_molecule(spectra, adduct, tidx, cc)
        n_ev += bool(evidence)
        n_changed += [x[1] for x in new] != [x[0] for x in base]
        n_coco_top1 += bool(new) and new[0][3] == 'coconut'
        sol_rows.append({'molecule_id': ik, 'smiles': g.normalized_smiles.iloc[0]})
        base_rows.append({'molecule_id': ik, 'smiles': ';'.join(s for _, s in base) or 'C'})
        new_rows.append({'molecule_id': ik, 'smiles': ';'.join(t[2] for t in new) or 'C'})
    print(f'ranking {len(sol_rows)} molecules took {time.time() - t1:.0f}s '
          f'({(time.time() - t1) / len(sol_rows):.1f}s/molecule on this subset)')
    print(f'molecules with analog evidence: {n_ev}/{len(sol_rows)}; Top-25 changed vs exp_004: {n_changed}; '
          f'COCONUT at Top-1: {n_coco_top1}')
    sol = pd.DataFrame(sol_rows)
    s_base = metric.score(sol.copy(), pd.DataFrame(base_rows), 'molecule_id')
    s_new = metric.score(sol.copy(), pd.DataFrame(new_rows), 'molecule_id')
    print(f'MRR@25 exp_004-order = {s_base:.4f}   exp_006-order = {s_new:.4f}   (held-out {n_hold}, seed {seed})')


if __name__ == '__main__':
    main()
