"""Measures the nature of the Enveda CASMI 2026 evaluation problem, since the hidden
test set's novelty-class labels (1=public library / 2=known-no-spectra / 3=de novo)
are not published.

Two measurements, both against train.parquet + test.parquet:

1. Mass saturation: for every test molecule, back out its neutral monoisotopic mass
   from precursor_mz and adduct, then find the closest-mass structure in the training
   library (275k unique structures). If this is near-100% within a few ppm, it means
   "finding a mass-matching candidate" is not a discriminating step -- the library
   already covers the whole observed mass range.

2. Isomer ambiguity: for every distinct molecular formula in train, count how many
   distinct structures (by InChIKey14) share it. A high median group size means that
   even knowing the exact formula leaves many candidate structures to choose between --
   this is the real difficulty, as opposed to mass-based retrieval.

Usage: python3 evaluation_period_analysis.py /path/to/train.parquet /path/to/test.parquet
"""
import sys
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

ADDUCT_MASS_SHIFT = {
    '[M+H]+': -1.007276,
    '[M-H]-': 1.007276,
    '[M+Na]+': -22.989770,
    '[M+NH4]+': -18.033823,
    '[M+K]+': -38.963158,
    '[M+Cl]-': 34.969402,
    '[M+CH2O2-H]-': -44.998203,
}
ADDUCT_PRIORITY = list(ADDUCT_MASS_SHIFT.keys())


def exact_mass(smiles: str) -> float:
    m = Chem.MolFromSmiles(smiles)
    return Descriptors.ExactMolWt(m) if m is not None else np.nan


def mass_saturation(train_path: str, test_path: str) -> pd.DataFrame:
    train = pd.read_parquet(train_path, columns=['normalized_smiles', 'inchikey14'])
    mol_train = train.drop_duplicates('inchikey14').copy()
    mol_train['exact_mass'] = mol_train['normalized_smiles'].apply(exact_mass)
    mol_train = mol_train.dropna(subset=['exact_mass'])
    train_sorted = np.sort(mol_train['exact_mass'].values)

    test = pd.read_parquet(test_path, columns=['molecule_id', 'adduct', 'precursor_mz'])

    def pick_row(g):
        for p in ADDUCT_PRIORITY:
            sub = g[g['adduct'] == p]
            if len(sub):
                return sub.iloc[0]
        return g.iloc[0]

    rows = []
    for mid, g in test.groupby('molecule_id'):
        r = pick_row(g)
        shift = ADDUCT_MASS_SHIFT.get(r['adduct'])
        if shift is None:
            continue
        rows.append((mid, r['precursor_mz'] + shift))
    test_mass = pd.DataFrame(rows, columns=['molecule_id', 'neutral_mass'])

    def min_ppm_diff(m):
        idx = np.searchsorted(train_sorted, m)
        candidates = [c for c in (train_sorted[idx] if idx < len(train_sorted) else None,
                                   train_sorted[idx - 1] if idx > 0 else None) if c is not None]
        return min(abs(c - m) / m * 1e6 for c in candidates)

    test_mass['min_ppm_to_train'] = test_mass['neutral_mass'].apply(min_ppm_diff)
    return test_mass


def isomer_ambiguity(train_path: str) -> pd.Series:
    train = pd.read_parquet(train_path, columns=['inchikey14', 'molecular_formula'])
    mol_train = train.drop_duplicates('inchikey14')
    return mol_train.groupby('molecular_formula').size()


def main():
    train_path, test_path = sys.argv[1], sys.argv[2]

    test_mass = mass_saturation(train_path, test_path)
    print(f'test molecules resolved to a neutral mass: {len(test_mass)}')
    for thresh in (5, 10, 20, 50):
        pct = (test_mass['min_ppm_to_train'] <= thresh).mean()
        print(f'  within {thresh:>3} ppm of some train structure: {pct:.1%}')

    sizes = isomer_ambiguity(train_path)
    print(f'\ndistinct formulas in train: {len(sizes)}')
    print(f'isomer-group size (distinct structures sharing a formula): {sizes.describe()}')
    for q in (0.5, 0.75, 0.9, 0.95, 0.99):
        print(f'  p{int(q*100)}: {sizes.quantile(q):.1f}')
    print(f'formulas with exactly 1 structure (unambiguous if formula known): {(sizes == 1).mean():.1%}')


if __name__ == '__main__':
    main()
