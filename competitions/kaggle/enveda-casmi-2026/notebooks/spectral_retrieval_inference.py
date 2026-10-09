"""Phase 2 baseline for Enveda CASMI 2026: untuned spectral-library-search retrieval.

This is the standard, no-tuning cheminformatics default (the top public solution's own
"Channel 1: exact spectral matching"): for each query spectrum, find training spectra
within a tight precursor-mass window, score them by matched-peak cosine similarity, and
rank the underlying structures by their best-matching spectrum. No ML, no fitting -- the
point of Phase 2 is a pipeline that actually runs end to end, not a tuned model.

Per-molecule aggregation: a test molecule can have several spectra (different collision
energies / adducts). Each test spectrum independently retrieves candidate molecules; a
molecule's final score is its best (max) similarity across all of that test molecule's
spectra. Final ranking = top 25 distinct structures (deduped by inchikey14) by that score.

Usage (local CV):   python3 baseline_spectral_retrieval.py cv   <train.parquet>
Usage (real test):  python3 baseline_spectral_retrieval.py test <train.parquet> <test.parquet> <out.csv>
"""
import sys
import numpy as np
import pandas as pd

PRECURSOR_PPM_TOL = 15.0      # precursor pre-filter window
PEAK_MATCH_DA_TOL = 0.01       # fragment-peak matching tolerance
TOP_K = 25


def matched_peak_cosine(mzs_a, ints_a, mzs_b, ints_b, tol=PEAK_MATCH_DA_TOL):
    """Cosine similarity using only mutually-matched peaks (GNPS-style)."""
    if len(mzs_a) == 0 or len(mzs_b) == 0:
        return 0.0
    order_b = np.argsort(mzs_b)
    mzs_b_sorted = mzs_b[order_b]
    ints_b_sorted = ints_b[order_b]
    num = 0.0
    for mz, inten in zip(mzs_a, ints_a):
        lo = np.searchsorted(mzs_b_sorted, mz - tol, side='left')
        hi = np.searchsorted(mzs_b_sorted, mz + tol, side='right')
        if hi > lo:
            num += inten * ints_b_sorted[lo:hi].max()
    denom = np.sqrt(np.sum(ints_a ** 2)) * np.sqrt(np.sum(ints_b ** 2))
    return float(num / denom) if denom > 0 else 0.0


def build_train_index(train_df):
    """train_df must have: inchikey14, normalized_smiles, precursor_mz, ms2_mzs, ms2_normalized_intensities."""
    order = np.argsort(train_df['precursor_mz'].values)
    return train_df.iloc[order].reset_index(drop=True)


def candidates_for_mz(train_sorted, mz, ppm_tol=PRECURSOR_PPM_TOL):
    window = mz * ppm_tol * 1e-6
    lo = np.searchsorted(train_sorted['precursor_mz'].values, mz - window, side='left')
    hi = np.searchsorted(train_sorted['precursor_mz'].values, mz + window, side='right')
    return train_sorted.iloc[lo:hi]


def rank_candidates_for_molecule(test_spectra_rows, train_sorted):
    """test_spectra_rows: list of (precursor_mz, mzs, intensities) for one test molecule.
    Returns up to TOP_K (inchikey14, smiles) pairs ranked by best similarity."""
    best_score = {}
    best_smiles = {}
    for precursor_mz, mzs, ints in test_spectra_rows:
        cands = candidates_for_mz(train_sorted, precursor_mz)
        if len(cands) == 0:
            continue
        for _, row in cands.iterrows():
            sim = matched_peak_cosine(mzs, ints, np.asarray(row['ms2_mzs'], dtype=float),
                                       np.asarray(row['ms2_normalized_intensities'], dtype=float))
            ik = row['inchikey14']
            if sim > best_score.get(ik, -1.0):
                best_score[ik] = sim
                best_smiles[ik] = row['normalized_smiles']
    ranked = sorted(best_score.items(), key=lambda kv: kv[1], reverse=True)[:TOP_K]
    return [(ik, best_smiles[ik]) for ik, _ in ranked]


def run_cv(train_path, n_held=400, seed=0):
    sys.path.insert(0, '/'.join(__file__.split('/')[:-1]) or '.')
    from casmi_metric import score

    cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
    df = pd.read_parquet(train_path, columns=cols)

    rng = np.random.RandomState(seed)
    uniq = df['inchikey14'].unique()
    idx = rng.permutation(len(uniq))
    held_ids = set(uniq[idx[:n_held]])
    pool_ids = set(uniq[idx[n_held:]])

    held_df = df[df['inchikey14'].isin(held_ids)]
    pool_df = df[df['inchikey14'].isin(pool_ids)]
    train_sorted = build_train_index(pool_df)

    solution_rows = []
    submission_rows = []
    for ik, g in held_df.groupby('inchikey14'):
        true_smiles = g['normalized_smiles'].iloc[0]
        spectra = [(row['precursor_mz'], np.asarray(row['ms2_mzs'], dtype=float),
                    np.asarray(row['ms2_normalized_intensities'], dtype=float))
                   for _, row in g.iterrows()]
        ranked = rank_candidates_for_molecule(spectra, train_sorted)
        guesses = [smi for _, smi in ranked]
        if not guesses:
            guesses = ['C']  # harmless placeholder, never correct
        solution_rows.append({'molecule_id': ik, 'smiles': true_smiles})
        submission_rows.append({'molecule_id': ik, 'smiles': ';'.join(guesses)})

    solution = pd.DataFrame(solution_rows)
    submission = pd.DataFrame(submission_rows)
    s = score(solution, submission, 'molecule_id', max_rank=TOP_K)
    print(f'seed={seed}  n_held={len(solution)}  spectral-retrieval MRR@25 = {s:.4f}')
    return s


def run_real_test(train_path, test_path, out_path):
    train_cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
    train_df = pd.read_parquet(train_path, columns=train_cols)
    train_sorted = build_train_index(train_df)

    test_cols = ['molecule_id', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
    test_df = pd.read_parquet(test_path, columns=test_cols)

    rows = []
    for mid, g in test_df.groupby('molecule_id'):
        spectra = [(row['precursor_mz'], np.asarray(row['ms2_mzs'], dtype=float),
                    np.asarray(row['ms2_normalized_intensities'], dtype=float))
                   for _, row in g.iterrows()]
        ranked = rank_candidates_for_molecule(spectra, train_sorted)
        guesses = [smi for _, smi in ranked]
        if not guesses:
            guesses = ['C']
        rows.append({'molecule_id': mid, 'smiles': ';'.join(guesses)})

    submission = pd.DataFrame(rows)
    submission.to_csv(out_path, index=False)
    print(f'wrote {out_path}  rows={len(submission)}')


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'cv':
        run_cv(sys.argv[2])
    elif mode == 'test':
        run_real_test(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit('mode must be cv or test')
