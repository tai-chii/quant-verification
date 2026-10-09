"""Enveda CASMI 2026 -- Kaggle kernel inference script, exp_005.

Single change from exp_004 (current best, Public LB 0.124): exp_004's low-confidence
branch (best cosine < CONF_THRESHOLD) never actually added anything when train already
returned 25 candidates, because it only filled `TOP_K - len(ranked)` slots. So in
exp_004 the fallback fired only for molecules with <25 train candidates (24/400).
exp_005: when best cosine < CONF_THRESHOLD (raised 0.05 -> 0.3), keep only the top
KEEP_TRAIN_LOW_CONF (=10) train candidates and fill the remaining 15 slots with COCONUT
candidates (mass-closeness ranked). The <25-candidates branch is unchanged.
Unlike exp_004 this is NOT monotone: it can push a correct train candidate at rank 11-25
out of the list. Also prints a histogram of per-molecule best cosine for diagnostics
(note: public test.parquet is a dummy; the scored rerun test differs).

--- exp_004 docstring follows ---

Self-contained (no local-repo imports) so this can be pasted directly as the Kaggle
kernel's main script, the same way exp_001/exp_002/exp_003 were. Single structural
change from exp_001/exp_003 (current best, Public LB 0.122, PRECURSOR_PPM_TOL=15.0,
PEAK_MATCH_DA_TOL=0.01): when the train-library retrieval is NOT confident (best
matched-peak cosine < CONF_THRESHOLD, or fewer than TOP_K distinct structures found),
back off and fill the remaining Top-25 slots with COCONUT 2.0 candidates (external
natural-product DB, ~474k distinct skeletons, Zenodo 13897048) whose neutral
monoisotopic mass (precursor_mz corrected for the reported adduct) falls within the
same ppm window as the train precursor pre-filter. COCONUT candidates are ranked only
by mass closeness (no spectra available for them) and NEVER replace or reorder a
train-based candidate -- they only fill otherwise-empty/low-confidence slots.

Rationale (CLAUDE.md "確認済みの事実", Phase1 Discussion notes, measured 2026-10-09):
the 400 test molecules are believed to split into Tier1 (~10-15%, exact library
spectral match) / Tier2 (~45-55%, known structure but no library spectrum) / Tier3
(~30-40%, genuinely novel). train has 275,810 distinct structures; COCONUT has
473,936, with only 25,945 overlapping train's set -- so COCONUT is a mostly
*different*, larger pool, a plausible source of correct answers for Tier-2 molecules.

BEFORE running this on Kaggle:
  1. Upload data/external_coconut/coconut_lite.csv (columns: inchikey14,
     canonical_smiles, exact_molecular_weight; ~51MB, 473,936 rows) as a Kaggle
     Dataset and attach it to this kernel (competition blocks internet at scoring
     time, so it cannot be downloaded at runtime).
  2. Fix COCONUT_LITE_PATH below to wherever Kaggle mounts that dataset
     (printed by the "input file listing" block below on first run if the guessed
     path is wrong -- check the kernel's Data tab for the exact mount path).

Local validation note: this exact logic (not this literal file, but the same
functions) was smoke-tested in notebooks/spectral_retrieval_coconut_fallback.py on a
393k-row train subset (full 2.5M-row load OOMs the Mac-side dev sandbox's 3.8GB RAM):
baseline (train-only) local-CV MRR@25 = 0.0000 (as expected, exact-match CV is
structurally broken for this method -- see CLAUDE.md), coconut-fallback local-CV
MRR@25 = 0.0074 on a 60-molecule held-out sample. That is a code-correctness /
plausibility check only, not an LB estimate -- this kernel run is the first real
measurement.
"""
import os
import sys
import numpy as np
import pandas as pd

# ---- paths (edit COCONUT_LITE_PATH if the Dataset mounts somewhere else) ----
TRAIN_PATH = '/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
TEST_PATH = '/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/test.parquet'
COCONUT_LITE_PATH = '/kaggle/input/datasets/taichiii/coconut-2-0-lite-inchikey14-smiles-exact-mass/coconut_lite.csv'
OUT_PATH = 'submission.csv'

# ---- same constants as exp_001/exp_003 (current best, tied at LB 0.122) ----
PRECURSOR_PPM_TOL = 15.0
PEAK_MATCH_DA_TOL = 0.01
TOP_K = 25

# ---- exp_004's one new knob ----
CONF_THRESHOLD = 0.3    # exp_005: 0.05 -> 0.3; below this best-cosine, the train match is not trusted
KEEP_TRAIN_LOW_CONF = 10  # exp_005: on low confidence keep only this many train candidates
MASS_PPM_TOL = PRECURSOR_PPM_TOL  # same window, applied to the COCONUT mass lookup

# Monoisotopic adduct mass shifts (precursor_mz = neutral_mass + delta), singly
# charged, electron mass accounted for. Covers every adduct observed in test.parquet
# (measured 2026-10-09): [M+H]+, [M-H]-, [M+CH2O2-H]-, [M+Na]+, [M+NH4]+, [M+K]+, [M+Cl]-.
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


def matched_peak_cosine(mzs_a, ints_a, mzs_b, ints_b, tol=PEAK_MATCH_DA_TOL):
    """Cosine similarity using only mutually-matched peaks (GNPS-style). Identical to
    exp_001/exp_003's spectral_retrieval_inference.matched_peak_cosine."""
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
    order = np.argsort(train_df['precursor_mz'].values)
    return train_df.iloc[order].reset_index(drop=True)


def candidates_for_mz(train_sorted, mz, ppm_tol=PRECURSOR_PPM_TOL):
    window = mz * ppm_tol * 1e-6
    lo = np.searchsorted(train_sorted['precursor_mz'].values, mz - window, side='left')
    hi = np.searchsorted(train_sorted['precursor_mz'].values, mz + window, side='right')
    return train_sorted.iloc[lo:hi]


def rank_candidates_scored(test_spectra_rows, train_sorted):
    """Same ranking as exp_001, but also returns the best (top) cosine score."""
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


def build_coconut_index(coconut_lite_path):
    df = pd.read_csv(coconut_lite_path)  # already: inchikey14, canonical_smiles, exact_molecular_weight
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


TOP_SCORES = []


def rank_with_coconut_fallback(test_spectra_rows, train_sorted, cc_sorted, adduct):
    ranked, top_score = rank_candidates_scored(test_spectra_rows, train_sorted)
    TOP_SCORES.append(top_score)
    if len(ranked) >= TOP_K and top_score >= CONF_THRESHOLD:
        return ranked, 'train_only'
    if top_score < CONF_THRESHOLD:
        ranked = ranked[:KEEP_TRAIN_LOW_CONF]  # exp_005: make room for COCONUT
    precursor_mzs = [p for p, _, _ in test_spectra_rows]
    mass = neutral_mass(float(np.mean(precursor_mzs)), adduct)
    exclude_ik = {ik for ik, _ in ranked}
    fallback = coconut_candidates_for_mass(cc_sorted, mass, exclude_ik)
    need = TOP_K - len(ranked)
    return ranked + fallback[:need], ('coconut_fallback' if fallback else 'train_only_short')


def main():
    print('--- input file listing (sanity check for COCONUT_LITE_PATH) ---')
    for root, dirs, files in os.walk('/kaggle/input'):
        for f in files:
            print(os.path.join(root, f))
    if not os.path.exists(COCONUT_LITE_PATH):
        raise SystemExit(
            f'COCONUT_LITE_PATH={COCONUT_LITE_PATH} not found. '
            f'Check the listing above for the real mount path and fix the constant.'
        )

    train_cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
    train_df = pd.read_parquet(TRAIN_PATH, columns=train_cols)
    train_sorted = build_train_index(train_df)
    cc_sorted = build_coconut_index(COCONUT_LITE_PATH)
    print(f'train: {len(train_df)} rows, {train_df["inchikey14"].nunique()} structures')
    print(f'coconut: {len(cc_sorted)} structures')

    test_cols = ['molecule_id', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities', 'adduct']
    test_df = pd.read_parquet(TEST_PATH, columns=test_cols)

    rows = []
    fallback_used = 0
    for mid, g in test_df.groupby('molecule_id'):
        adduct = g['adduct'].iloc[0]
        spectra = [(row['precursor_mz'], np.asarray(row['ms2_mzs'], dtype=float),
                    np.asarray(row['ms2_normalized_intensities'], dtype=float))
                   for _, row in g.iterrows()]
        ranked, source = rank_with_coconut_fallback(spectra, train_sorted, cc_sorted, adduct)
        if source != 'train_only':
            fallback_used += 1
        guesses = [smi for _, smi in ranked]
        if not guesses:
            guesses = ['C']
        rows.append({'molecule_id': mid, 'smiles': ';'.join(guesses)})

    ts = np.asarray(TOP_SCORES)
    print('best-cosine histogram (per molecule):',
          {f'<{b}': int((ts < b).sum()) for b in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.01)})
    submission = pd.DataFrame(rows)
    submission.to_csv(OUT_PATH, index=False)
    print(f'wrote {OUT_PATH}  rows={len(submission)}  '
          f'molecules_using_coconut_fallback={fallback_used}/{len(submission)}')


if __name__ == '__main__':
    main()
