"""exp_004 for Enveda CASMI 2026: COCONUT 2.0 fallback candidates.

Single structural change from exp_001 (the untuned spectral-library-search baseline,
PRECURSOR_PPM_TOL=15.0, PEAK_MATCH_DA_TOL=0.01 -- current best, tied with exp_003):

    When the train-library retrieval is NOT confident (best matched-peak cosine
    similarity across all candidates is below CONF_THRESHOLD, or fewer than TOP_K
    distinct structures were found), back off and fill the remaining Top-25 slots
    with structures from COCONUT 2.0 (an external natural-product database, ~474k
    distinct skeletons, Zenodo record 13897048) whose neutral monoisotopic mass
    (precursor_mz corrected for the reported adduct) falls within the same ppm
    window used for the train precursor pre-filter.

Rationale (see CLAUDE.md "確認済みの事実" and the Phase1 Discussion notes): the test
set's 400 molecules are believed to split into three tiers -- (1) ~10-15% with an
exact library spectral match, (2) ~45-55% with a known structure but no matching
library spectrum, (3) ~30-40% genuinely novel structures. The train library here has
only 275,810 distinct structures; COCONUT has 473,936, with only 25,945 overlapping
train's set (measured 2026-10-09). So COCONUT is a mostly *different*, much larger
pool of known natural-product structures -- a plausible source of correct answers
for Tier-2 molecules that train's spectral matching cannot score confidently.

COCONUT does not carry MS2 spectra, so its candidates cannot be cosine-ranked against
the query spectrum. They are ranked only by closeness of neutral mass (ties are
expected and are not broken further -- isomer ambiguity is the known main difficulty
in this competition; see CLAUDE.md "評価期間の性質の測定"). This fallback NEVER
reorders or removes a train-based candidate -- it only fills otherwise-empty or
low-confidence Top-25 slots.

This is the single change under test. Everything else (train index, matched-peak
cosine, PRECURSOR_PPM_TOL, PEAK_MATCH_DA_TOL, TOP_K) is identical to
spectral_retrieval_inference.py's exp_001/exp_003 settings.

Usage (local CV, limited validity -- see note at bottom of file):
    python3 spectral_retrieval_coconut_fallback.py cv   <train.parquet> <coconut.csv>
Usage (real test):
    python3 spectral_retrieval_coconut_fallback.py test <train.parquet> <test.parquet> <coconut.csv> <out.csv>
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spectral_retrieval_inference import (
    PRECURSOR_PPM_TOL, PEAK_MATCH_DA_TOL, TOP_K,
    matched_peak_cosine, build_train_index, candidates_for_mz,
)

CONF_THRESHOLD = 0.05  # below this best-cosine, the train match is not trusted
MASS_PPM_TOL = PRECURSOR_PPM_TOL  # same window as the train precursor pre-filter

# Monoisotopic adduct mass shifts (precursor_mz = neutral_mass + delta), singly charged,
# electron mass accounted for. Covers every adduct observed in test.parquet (measured
# 2026-10-09: [M+H]+, [M-H]-, [M+CH2O2-H]-, [M+Na]+, [M+NH4]+, [M+K]+, [M+Cl]-).
ADDUCT_DELTA = {
    '[M+H]+': 1.007276,
    '[M-H]-': -1.007276,
    '[M+Na]+': 22.989221,
    '[M+NH4]+': 18.033825,
    '[M+K]+': 38.963158,
    '[M+Cl]-': 34.969402,
    '[M+CH2O2-H]-': 44.998203,
}


def neutral_mass(precursor_mz, adduct):
    delta = ADDUCT_DELTA.get(adduct)
    if delta is None:
        return None
    return precursor_mz - delta


def build_coconut_index(coconut_csv_path):
    """Load COCONUT, collapse to one row per inchikey14 (skeleton), sort by mass."""
    df = pd.read_csv(
        coconut_csv_path,
        usecols=['canonical_smiles', 'standard_inchi_key', 'exact_molecular_weight'],
        low_memory=False,
    )
    df['inchikey14'] = df['standard_inchi_key'].str.slice(0, 14)
    df = df.drop_duplicates('inchikey14').reset_index(drop=True)
    df = df.sort_values('exact_molecular_weight').reset_index(drop=True)
    return df


def coconut_candidates_for_mass(cc_sorted, mass, exclude_ik, ppm_tol=MASS_PPM_TOL):
    if mass is None:
        return []
    masses = cc_sorted['exact_molecular_weight'].values
    window = mass * ppm_tol * 1e-6
    lo = np.searchsorted(masses, mass - window, side='left')
    hi = np.searchsorted(masses, mass + window, side='right')
    if hi <= lo:
        return []
    sub = cc_sorted.iloc[lo:hi]
    sub = sub[~sub['inchikey14'].isin(exclude_ik)]
    if len(sub) == 0:
        return []
    absdiff = (sub['exact_molecular_weight'] - mass).abs()
    order = absdiff.values.argsort()
    sub_sorted = sub.iloc[order]
    return list(zip(sub_sorted['inchikey14'], sub_sorted['canonical_smiles']))


def rank_candidates_for_molecule_scored(test_spectra_rows, train_sorted):
    """Same ranking as spectral_retrieval_inference.rank_candidates_for_molecule,
    but also returns the best (top) cosine score so the caller can judge confidence."""
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
    top_score = ranked[0][1] if ranked else 0.0
    return [(ik, best_smiles[ik]) for ik, _ in ranked], top_score


def rank_with_coconut_fallback(test_spectra_rows, train_sorted, cc_sorted, adduct):
    ranked, top_score = rank_candidates_for_molecule_scored(test_spectra_rows, train_sorted)
    if len(ranked) >= TOP_K and top_score >= CONF_THRESHOLD:
        return ranked  # confident train match already fills all slots -- no fallback needed
    # representative precursor_mz for mass back-calculation: mean across this molecule's spectra
    precursor_mzs = [p for p, _, _ in test_spectra_rows]
    mass = neutral_mass(float(np.mean(precursor_mzs)), adduct)
    exclude_ik = {ik for ik, _ in ranked}
    fallback = coconut_candidates_for_mass(cc_sorted, mass, exclude_ik)
    need = TOP_K - len(ranked)
    return ranked + fallback[:need]


def run_cv(train_path, coconut_path, n_held=400, seed=0):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from casmi_metric import score

    cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'ms2_mzs',
            'ms2_normalized_intensities', 'adduct']
    df = pd.read_parquet(train_path, columns=cols)

    rng = np.random.RandomState(seed)
    uniq = df['inchikey14'].unique()
    idx = rng.permutation(len(uniq))
    held_ids = set(uniq[idx[:n_held]])
    pool_ids = set(uniq[idx[n_held:]])

    held_df = df[df['inchikey14'].isin(held_ids)]
    pool_df = df[df['inchikey14'].isin(pool_ids)]
    train_sorted = build_train_index(pool_df)
    cc_sorted = build_coconut_index(coconut_path)

    solution_rows = []
    submission_rows = []
    for ik, g in held_df.groupby('inchikey14'):
        true_smiles = g['normalized_smiles'].iloc[0]
        adduct = g['adduct'].iloc[0]
        spectra = [(row['precursor_mz'], np.asarray(row['ms2_mzs'], dtype=float),
                    np.asarray(row['ms2_normalized_intensities'], dtype=float))
                   for _, row in g.iterrows()]
        ranked = rank_with_coconut_fallback(spectra, train_sorted, cc_sorted, adduct)
        guesses = [smi for _, smi in ranked]
        if not guesses:
            guesses = ['C']
        solution_rows.append({'molecule_id': ik, 'smiles': true_smiles})
        submission_rows.append({'molecule_id': ik, 'smiles': ';'.join(guesses)})

    solution = pd.DataFrame(solution_rows)
    submission = pd.DataFrame(submission_rows)
    s = score(solution, submission, 'molecule_id', max_rank=TOP_K)
    print(f'seed={seed}  n_held={len(solution)}  coconut-fallback MRR@25 = {s:.4f}')
    return s


def run_real_test(train_path, test_path, coconut_path, out_path):
    train_cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'ms2_mzs',
                  'ms2_normalized_intensities']
    train_df = pd.read_parquet(train_path, columns=train_cols)
    train_sorted = build_train_index(train_df)
    cc_sorted = build_coconut_index(coconut_path)

    test_cols = ['molecule_id', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities', 'adduct']
    test_df = pd.read_parquet(test_path, columns=test_cols)

    rows = []
    for mid, g in test_df.groupby('molecule_id'):
        adduct = g['adduct'].iloc[0]
        spectra = [(row['precursor_mz'], np.asarray(row['ms2_mzs'], dtype=float),
                    np.asarray(row['ms2_normalized_intensities'], dtype=float))
                   for _, row in g.iterrows()]
        ranked = rank_with_coconut_fallback(spectra, train_sorted, cc_sorted, adduct)
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
        run_cv(sys.argv[2], sys.argv[3])
    elif mode == 'test':
        run_real_test(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        raise SystemExit('mode must be cv or test')
