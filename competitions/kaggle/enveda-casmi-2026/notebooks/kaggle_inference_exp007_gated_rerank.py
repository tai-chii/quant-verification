"""Enveda CASMI 2026 -- Kaggle kernel inference script, exp_007.

Single change from exp_006 (current best, Public LB 0.135): GATE the analog re-rank by
the exact channel's confidence. If the best exact-channel cosine for a molecule is
>= GATE_EXACT_COS (0.7), the molecule keeps exp_004's order (exact cosine, COCONUT fills
empty slots by mass); only molecules below the gate get exp_006's evidence re-rank.
Why: on the public dummy test (train copies, so the exact copy IS the answer) exp_006
changed the Top-1 of 106/400 molecules, i.e. the evidence term (W_ANALOG=1.0) can
demote a near-perfect library hit. Real Tier-1 molecules (~10-15%) are exactly those
with a high exact cosine, so the gate should only remove downside there. Everything
else is identical to exp_006. Expected: LB >= 0.135 if Tier-1 hits were being lost,
= 0.135 if not.

--- exp_006 docstring follows ---

Single structural change from exp_004 (current best, Public LB 0.124):
**mass-shift analog propagation** (a simplified version of the top public
solution's "Channel 2"), used to RE-RANK the candidate pool.

What exp_004 does (unchanged here, "Channel 1" + fallback):
  * exact channel: train spectra whose precursor m/z is within +-15 ppm of the query
    are scored by matched-peak cosine (0.01 Da); best cosine per structure (inchikey14).
  * COCONUT fallback: when fewer than 25 train structures were found, the empty slots
    are filled with COCONUT 2.0 structures whose neutral mass matches (+-15 ppm),
    ordered by mass closeness.

What exp_006 adds ("Channel 2", analog evidence):
  1. For every query spectrum, also search train spectra whose precursor m/z differs
     from the query by a *known chemical modification* (+-CH2, +-O, +-H2O, +-hexose,
     ... see ANALOG_SHIFTS), same adduct only, same +-15 ppm window around the shifted
     mass. Each such spectrum is scored with a *modified* cosine: a query peak may match
     a train peak either at the same m/z or at m/z + shift (fragments carrying the
     modification move by the shift).
  2. The structures of the best analog spectra (cosine >= ANALOG_MIN_COS, top
     N_EVIDENCE distinct structures per molecule) become "evidence structures", each
     weighted by its analog cosine.
  3. The candidate pool is: all exact-channel train structures (top TRAIN_POOL by
     cosine) + all mass-matching COCONUT structures (top COCONUT_POOL by mass
     closeness). Every candidate gets
         score = exact_cosine (0 for COCONUT)
               + W_ANALOG * max_i( analog_cosine_i * Tanimoto(candidate, evidence_i) )
     with Morgan fingerprints (radius 2, 2048 bits). Ties: train before COCONUT, then
     mass closeness -- so a molecule with NO analog evidence ranks exactly as in
     exp_004 (exact cosine order, then COCONUT by mass). Top-25 by score is submitted.

Why: Tier-2 molecules (~half of the test set per Discussion) have a known structure but
no library spectrum. Their exact-channel candidates are accidental same-mass matches
with low cosine, and the correct COCONUT structure sits unranked at cosine 0. A library
spectrum of a *close relative* (e.g. the same scaffold +-one sugar) is often present,
and its structure is a strong hint about which same-mass candidate is right. exp_006
tests exactly that one idea: structural similarity to analog-spectrum structures.

NOT monotone w.r.t. exp_004: a COCONUT candidate with strong evidence can push a train
candidate out of the Top-25, and the exact-channel order can change. Judge on LB.

Diagnostics printed: per-molecule best exact cosine histogram, how many molecules had
analog evidence, how many Top-25 lists / Top-1 picks differ from the exp_004 order, and
how many COCONUT structures entered the Top-25. (Public test.parquet is a dummy made of
train copies, so on Kaggle's visible run most molecules have exact cosine >= 0.9 and the
analog channel changes little; the real effect is only measurable on the hidden rerun
test, i.e. the Public LB.)

Requires: numpy, pandas, pyarrow (Kaggle image) + rdkit installed offline from the attached wheel
Dataset taichiii/rdkit-wheel-cp313 (the Kaggle image has no rdkit; found 2026-10-10 on the first run).
Also attach taichiii/coconut-2-0-lite-inchikey14-smiles-exact-mass (same as exp_004). CPU only.
"""
import os
import sys
import glob
import subprocess
import time
import numpy as np
import pandas as pd

# The Kaggle image (Python 3.13) has no rdkit and scoring runs offline, so install it
# from the attached wheel Dataset taichiii/rdkit-wheel-cp313 (deps numpy/Pillow are in the image).
RDKIT_WHEEL_DIR = '/kaggle/input/datasets/taichiii/rdkit-wheel-cp313'
try:
    import rdkit  # noqa: F401
except ModuleNotFoundError:
    wheels = glob.glob(os.path.join(RDKIT_WHEEL_DIR, '*.whl')) or glob.glob('/kaggle/input/**/rdkit-*.whl', recursive=True)
    if not wheels:
        raise SystemExit('rdkit wheel not found under /kaggle/input -- attach Dataset taichiii/rdkit-wheel-cp313')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '-q', wheels[0]])
from rdkit import Chem, RDLogger
from rdkit.Chem import DataStructs, rdFingerprintGenerator

RDLogger.DisableLog('rdApp.*')

# ---- paths (same as exp_004/exp_005) ----
TRAIN_PATH = '/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
TEST_PATH = '/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/test.parquet'
COCONUT_LITE_PATH = '/kaggle/input/datasets/taichiii/coconut-2-0-lite-inchikey14-smiles-exact-mass/coconut_lite.csv'
OUT_PATH = 'submission.csv'

# ---- exp_001/exp_004 constants (unchanged) ----
PRECURSOR_PPM_TOL = 15.0
PEAK_MATCH_DA_TOL = 0.01
TOP_K = 25
MASS_PPM_TOL = PRECURSOR_PPM_TOL

# ---- exp_007's one new knob ----
GATE_EXACT_COS = 0.7    # best exact cosine >= this -> keep exp_004 order (no evidence re-rank)

# ---- exp_006 knobs (unchanged) ----
W_ANALOG = 1.0          # weight of the analog-evidence term relative to exact cosine (both in [0,1])
ANALOG_MIN_COS = 0.3    # analog spectra below this modified cosine are not evidence
N_EVIDENCE = 10         # max distinct evidence structures per molecule
TRAIN_POOL = 200        # exact-channel structures kept in the pool (by cosine)
COCONUT_POOL = 300      # COCONUT structures kept in the pool (by mass closeness)
MAX_SPECTRA_PER_WINDOW = 1500  # runtime guard for very dense mass windows (closest m/z kept)
FP_RADIUS, FP_BITS = 2, 2048

# Neutral monoisotopic mass shifts of common chemical modifications (Da). Applied with
# both signs. Same adduct is required, so the precursor m/z shift equals the neutral
# shift (singly charged adducts only; multiply-charged/dimer adducts never match).
ANALOG_SHIFTS = {
    'H2': 2.015650,        # (de)hydrogenation / double bond
    'CH2': 14.015650,      # methylene / methyl homologue
    'O': 15.994915,        # hydroxylation / oxidation
    'H2O': 18.010565,      # (de)hydration
    'C2H4': 28.031300,     # ethyl homologue
    'CH2O': 30.010565,     # methoxy
    'C2H2O': 42.010565,    # acetyl
    'CO2': 43.989830,      # (de)carboxylation
    'C5H8': 68.062600,     # isoprene unit
    'SO3': 79.956815,      # sulfation
    'HPO3': 79.966331,     # phosphorylation
    'C5H8O4': 132.042259,  # pentose
    'C6H10O4': 146.057909, # deoxyhexose (rhamnose)
    'C6H10O5': 162.052824, # hexose
    'C6H8O6': 176.032088,  # glucuronic acid
}

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


# ----------------------------------------------------------------------------- spectra
def _segment_max(ints_b, lo, hi):
    """For each i, max(ints_b[lo[i]:hi[i]]) assuming hi[i] > lo[i]. Vectorised."""
    best = ints_b[lo]
    width = int((hi - lo).max())
    for k in range(1, width):
        idx = lo + k
        ok = idx < hi
        best = np.where(ok, np.maximum(best, ints_b[np.minimum(idx, len(ints_b) - 1)]), best)
    return best


def _matched_numerator(mzs_a, ints_a, mzs_b_sorted, ints_b_sorted, tol):
    """Per query peak: max intensity of train peaks within +-tol (0 if none)."""
    lo = np.searchsorted(mzs_b_sorted, mzs_a - tol, side='left')
    hi = np.searchsorted(mzs_b_sorted, mzs_a + tol, side='right')
    out = np.zeros(len(mzs_a))
    m = hi > lo
    if m.any():
        out[m] = _segment_max(ints_b_sorted, lo[m], hi[m])
    return out


def matched_peak_cosine(mzs_a, ints_a, mzs_b, ints_b, tol=PEAK_MATCH_DA_TOL, shift=0.0):
    """GNPS-style matched-peak cosine. With shift != 0 this is a (simplified) modified
    cosine: each query peak may match a train peak at m/z or at m/z + shift, whichever
    is more intense. shift = 0 reproduces exp_001's cosine exactly (same arithmetic,
    vectorised)."""
    if len(mzs_a) == 0 or len(mzs_b) == 0:
        return 0.0
    order_b = np.argsort(mzs_b)
    mzs_b_sorted = mzs_b[order_b]
    ints_b_sorted = ints_b[order_b]
    matched = _matched_numerator(mzs_a, ints_a, mzs_b_sorted, ints_b_sorted, tol)
    if shift != 0.0:
        matched = np.maximum(matched, _matched_numerator(mzs_a + shift, ints_a, mzs_b_sorted, ints_b_sorted, tol))
    num = float(np.dot(ints_a, matched))
    denom = np.sqrt(np.sum(ints_a ** 2)) * np.sqrt(np.sum(ints_b ** 2))
    return float(num / denom) if denom > 0 else 0.0


class TrainIndex:
    """train spectra sorted by precursor m/z, held as plain numpy arrays (no iterrows)."""

    def __init__(self, train_df):
        order = np.argsort(train_df['precursor_mz'].values, kind='stable')
        self.mz = train_df['precursor_mz'].values[order]
        self.ik = train_df['inchikey14'].values[order]
        self.smiles = train_df['normalized_smiles'].values[order]
        self.adduct = train_df['adduct'].values[order]
        self.ms2_mz = train_df['ms2_mzs'].values[order]
        self.ms2_int = train_df['ms2_normalized_intensities'].values[order]

    def window(self, center_mz, ppm_tol=PRECURSOR_PPM_TOL, adduct=None):
        w = center_mz * ppm_tol * 1e-6
        lo = np.searchsorted(self.mz, center_mz - w, side='left')
        hi = np.searchsorted(self.mz, center_mz + w, side='right')
        idx = np.arange(lo, hi)
        if adduct is not None and len(idx):
            idx = idx[self.adduct[idx] == adduct]
        if len(idx) > MAX_SPECTRA_PER_WINDOW:
            closest = np.argsort(np.abs(self.mz[idx] - center_mz), kind='stable')[:MAX_SPECTRA_PER_WINDOW]
            idx = idx[closest]
        return idx


def exact_channel(spectra, tidx):
    """exp_001 ranking: best cosine per train structure over all spectra of the molecule."""
    best_score, best_smiles = {}, {}
    for precursor_mz, mzs, ints in spectra:
        for j in tidx.window(precursor_mz):
            sim = matched_peak_cosine(mzs, ints, np.asarray(tidx.ms2_mz[j], dtype=float),
                                       np.asarray(tidx.ms2_int[j], dtype=float))
            ik = tidx.ik[j]
            if sim > best_score.get(ik, -1.0):
                best_score[ik] = sim
                best_smiles[ik] = tidx.smiles[j]
    ranked = sorted(best_score.items(), key=lambda kv: kv[1], reverse=True)
    return [(ik, best_smiles[ik], s) for ik, s in ranked]


def analog_channel(spectra, tidx, adduct):
    """Evidence structures from mass-shifted analog spectra: [(ik, smiles, analog_cos, tag)]."""
    best, best_smiles, best_tag = {}, {}, {}
    for precursor_mz, mzs, ints in spectra:
        for name, delta in ANALOG_SHIFTS.items():
            for sign in (1.0, -1.0):
                shift = sign * delta   # train precursor = query precursor + shift
                for j in tidx.window(precursor_mz + shift, adduct=adduct):
                    sim = matched_peak_cosine(mzs, ints, np.asarray(tidx.ms2_mz[j], dtype=float),
                                               np.asarray(tidx.ms2_int[j], dtype=float), shift=shift)
                    if sim < ANALOG_MIN_COS:
                        continue
                    ik = tidx.ik[j]
                    if sim > best.get(ik, -1.0):
                        best[ik] = sim
                        best_smiles[ik] = tidx.smiles[j]
                        best_tag[ik] = ('+' if sign > 0 else '-') + name
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:N_EVIDENCE]
    return [(ik, best_smiles[ik], s, best_tag[ik]) for ik, s in ranked]


# ----------------------------------------------------------------------------- COCONUT
def build_coconut_index(path):
    df = pd.read_csv(path)
    return df.sort_values('exact_molecular_weight').reset_index(drop=True)


def coconut_candidates(cc_sorted, mass, ppm_tol=MASS_PPM_TOL):
    """[(ik, smiles, ppm_error)] sorted by mass closeness."""
    if mass is None:
        return []
    masses = cc_sorted['exact_molecular_weight'].values
    w = mass * ppm_tol * 1e-6
    lo = np.searchsorted(masses, mass - w, side='left')
    hi = np.searchsorted(masses, mass + w, side='right')
    if hi <= lo:
        return []
    sub = cc_sorted.iloc[lo:hi]
    ppm = (np.abs(sub['exact_molecular_weight'].values - mass) / mass) * 1e6
    order = np.argsort(ppm, kind='stable')
    return [(sub['inchikey14'].values[i], sub['canonical_smiles'].values[i], float(ppm[i])) for i in order]


# ----------------------------------------------------------------------------- fingerprints
_FPGEN = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_BITS)
_FP_CACHE = {}
_MISS = object()


def fingerprint(smiles):
    fp = _FP_CACHE.get(smiles, _MISS)
    if fp is not _MISS:
        return fp
    mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
    fp = _FPGEN.GetFingerprint(mol) if mol is not None else None
    _FP_CACHE[smiles] = fp
    return fp


def evidence_term(cand_smiles, evidence_fps, evidence_w):
    """max_i analog_cos_i * Tanimoto(candidate, evidence_i); 0 if no evidence / bad SMILES."""
    if not evidence_fps:
        return 0.0
    fp = fingerprint(cand_smiles)
    if fp is None:
        return 0.0
    sims = DataStructs.BulkTanimotoSimilarity(fp, evidence_fps)
    return float(max(w * s for w, s in zip(evidence_w, sims)))


# ----------------------------------------------------------------------------- ranking
def exp004_order(exact, coco):
    """exp_004's final list: exact-channel order, COCONUT (by mass) fills empty slots only."""
    ranked = [(ik, smi) for ik, smi, _ in exact[:TOP_K]]
    if len(ranked) < TOP_K:
        seen = {ik for ik, _ in ranked}
        for ik, smi, _ in coco:
            if ik not in seen:
                ranked.append((ik, smi))
                seen.add(ik)
            if len(ranked) >= TOP_K:
                break
    return ranked


def exp006_order(exact, coco, evidence):
    """Re-rank the pooled candidates by exact cosine + W_ANALOG * evidence term."""
    evidence_fps, evidence_w = [], []
    for _, smi, s, _ in evidence:
        fp = fingerprint(smi)
        if fp is not None:
            evidence_fps.append(fp)
            evidence_w.append(s)
    pool = {}
    for ik, smi, s in exact[:TRAIN_POOL]:
        pool[ik] = (smi, s, 1.0, 0.0, 'train')  # (smiles, exact_cos, train_prior, ppm, src)
    for ik, smi, ppm in coco[:COCONUT_POOL]:
        if ik not in pool:
            pool[ik] = (smi, 0.0, 0.0, ppm, 'coconut')
    scored = []
    for ik, (smi, ecos, prior, ppm, src) in pool.items():
        ev = evidence_term(smi, evidence_fps, evidence_w) if evidence_fps else 0.0
        score = ecos + W_ANALOG * ev
        # tie-breakers reproduce exp_004 when ev == 0: train first, then mass closeness
        key = (score, prior, -ppm)
        scored.append((key, ik, smi, src, ecos, ev))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:TOP_K]


def rank_molecule(spectra, adduct, tidx, cc_sorted):
    exact = exact_channel(spectra, tidx)
    mass = neutral_mass(float(np.mean([p for p, _, _ in spectra])), adduct)
    coco = coconut_candidates(cc_sorted, mass)
    evidence = analog_channel(spectra, tidx, adduct)
    base = exp004_order(exact, coco)
    best_exact = exact[0][2] if exact else 0.0
    if best_exact >= GATE_EXACT_COS:
        # exp_007: trusted library hit -> exp_004 order, re-expressed in exp006_order's tuple layout
        new = [((0.0, 0.0, 0.0), ik, smi, 'gated', 0.0, 0.0) for ik, smi in base]
        gated = True
    else:
        new = exp006_order(exact, coco, evidence)
        gated = False
    return exact, coco, evidence, base, new, gated


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    print('--- input file listing (sanity check for COCONUT_LITE_PATH) ---')
    for root, _, files in os.walk('/kaggle/input'):
        for f in files:
            print(os.path.join(root, f))
    if not os.path.exists(COCONUT_LITE_PATH):
        raise SystemExit(f'COCONUT_LITE_PATH={COCONUT_LITE_PATH} not found; fix the constant (see listing).')

    train_cols = ['inchikey14', 'normalized_smiles', 'precursor_mz', 'adduct', 'ms2_mzs', 'ms2_normalized_intensities']
    train_df = pd.read_parquet(TRAIN_PATH, columns=train_cols)
    tidx = TrainIndex(train_df)
    n_struct = train_df['inchikey14'].nunique()
    del train_df
    cc_sorted = build_coconut_index(COCONUT_LITE_PATH)
    print(f'train: {len(tidx.mz)} rows, {n_struct} structures; coconut: {len(cc_sorted)} structures; '
          f'load {time.time() - t0:.0f}s')

    test_cols = ['molecule_id', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities', 'adduct']
    test_df = pd.read_parquet(TEST_PATH, columns=test_cols)

    rows, top_scores = [], []
    n_evid = n_top1_changed = n_list_changed = n_coco_in_top25 = n_coco_top1 = n_gated = 0
    for i, (mid, g) in enumerate(test_df.groupby('molecule_id')):
        adduct = g['adduct'].iloc[0]
        spectra = [(float(r['precursor_mz']), np.asarray(r['ms2_mzs'], dtype=float),
                    np.asarray(r['ms2_normalized_intensities'], dtype=float)) for _, r in g.iterrows()]
        exact, coco, evidence, base, new, gated = rank_molecule(spectra, adduct, tidx, cc_sorted)
        top_scores.append(exact[0][2] if exact else 0.0)
        n_gated += gated
        n_evid += bool(evidence)
        new_iks = [ik for _, ik, _, _, _, _ in new]
        base_iks = [ik for ik, _ in base]
        n_top1_changed += (new_iks[:1] != base_iks[:1])
        n_list_changed += (new_iks != base_iks)
        n_coco_in_top25 += sum(1 for t in new if t[3] == 'coconut')
        n_coco_top1 += bool(new) and new[0][3] == 'coconut'
        guesses = [smi for _, _, smi, _, _, _ in new] or ['C']
        rows.append({'molecule_id': mid, 'smiles': ';'.join(guesses)})
        if i % 50 == 0:
            print(f'[{i}] {mid} adduct={adduct} spectra={len(spectra)} exact={len(exact)} coco={len(coco)} '
                  f'evidence={[(t, round(s, 2)) for _, _, s, t in evidence[:3]]} '
                  f'top1={new[0][3] if new else None} elapsed={time.time() - t0:.0f}s')

    ts = np.asarray(top_scores)
    print('best exact-cosine histogram (per molecule):',
          {f'<{b}': int((ts < b).sum()) for b in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.01)})
    n = len(rows)
    print(f'molecules with analog evidence: {n_evid}/{n}')
    print(f'gated (best exact cosine >= {GATE_EXACT_COS}, kept exp_004 order): {n_gated}/{n}')
    print(f'Top-1 changed vs exp_004 order: {n_top1_changed}/{n}; Top-25 list changed: {n_list_changed}/{n}')
    print(f'COCONUT structures in Top-25 (total slots): {n_coco_in_top25}; COCONUT at Top-1: {n_coco_top1}')
    pd.DataFrame(rows).to_csv(OUT_PATH, index=False)
    print(f'wrote {OUT_PATH} rows={n} total {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
