"""No-model baseline for Enveda CASMI 2026, measured by in-train cross-validation.

The real test set's ground-truth SMILES are not public, so this script substitutes a
held-out split of train.parquet (400 molecules, matching the real test set's molecule
count) to stand in for the hidden test set, and scores two non-learned heuristics with
the official MRR@25 metric (casmi_metric.py, ported from the competition's own metric
notebook).

Baseline A - global top-25 by spectral frequency: submit the same 25 most-frequent
structures (by spectra count in the training pool) for every molecule, regardless of
its properties. This is the "zero effort" floor.

Baseline B - molecular-formula match + frequency fallback: within each molecule's own
formula bucket, rank candidate structures in the training pool by frequency; fill out
to 25 candidates with the global top-25 if the formula bucket has fewer than 25 options
(or the formula was never seen in the pool at all).

Caveat: this in-train CV likely overstates the real score, because real test includes
"novelty class 3" molecules (de novo structures absent from every public library), which
this CV split cannot simulate -- every held-out molecule here comes from the same library
pool the baseline is built from.

Usage: python3 baseline_no_model.py /path/to/train.parquet /path/to/casmi_metric.py
"""
import sys
import numpy as np
import pandas as pd


def build_molecule_level(train_parquet_path: str) -> pd.DataFrame:
    cols = ['normalized_smiles', 'inchikey14', 'molecular_formula']
    df = pd.read_parquet(train_parquet_path, columns=cols)
    return (
        df.groupby('inchikey14')
        .agg(
            normalized_smiles=('normalized_smiles', 'first'),
            molecular_formula=('molecular_formula', 'first'),
            n_spectra=('inchikey14', 'size'),
        )
        .reset_index()
    )


def run_one_seed(mol: pd.DataFrame, seed: int, n_held: int, score_fn):
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(mol))
    held = mol.iloc[idx[:n_held]].reset_index(drop=True)
    pool = mol.iloc[idx[n_held:]].reset_index(drop=True)

    top25 = pool.sort_values('n_spectra', ascending=False).head(25)['normalized_smiles'].tolist()
    top25_str = ';'.join(top25)

    solution = pd.DataFrame({'molecule_id': held['inchikey14'], 'smiles': held['normalized_smiles']})

    submission_a = pd.DataFrame({'molecule_id': held['inchikey14'], 'smiles': [top25_str] * len(held)})
    score_a = score_fn(solution, submission_a, 'molecule_id', max_rank=25)

    formula_rank = (
        pool.sort_values('n_spectra', ascending=False)
        .groupby('molecular_formula')['normalized_smiles']
        .apply(list)
    )

    def guesses_for(formula):
        out = list(formula_rank.get(formula, [])[:25])
        for s in top25:
            if len(out) >= 25:
                break
            if s not in out:
                out.append(s)
        return ';'.join(out[:25])

    submission_b = pd.DataFrame(
        {'molecule_id': held['inchikey14'], 'smiles': [guesses_for(f) for f in held['molecular_formula']]}
    )
    score_b = score_fn(solution, submission_b, 'molecule_id', max_rank=25)
    return score_a, score_b


def main():
    train_path, metric_module_path = sys.argv[1], sys.argv[2]
    sys.path.insert(0, metric_module_path if not metric_module_path.endswith('.py') else '/'.join(metric_module_path.split('/')[:-1]))
    from casmi_metric import score

    mol = build_molecule_level(train_path)
    print(f'unique training molecules: {len(mol)}')

    results_a, results_b = [], []
    for seed in range(5):
        sa, sb = run_one_seed(mol, seed, n_held=400, score_fn=score)
        results_a.append(sa)
        results_b.append(sb)
        print(f'seed={seed}  BaselineA={sa:.4f}  BaselineB={sb:.4f}')

    print(f'\nBaseline A (global top-25, fixed):      mean={np.mean(results_a):.4f}  std={np.std(results_a):.4f}')
    print(f'Baseline B (formula-match + fallback):   mean={np.mean(results_b):.4f}  std={np.std(results_b):.4f}')


if __name__ == '__main__':
    main()
