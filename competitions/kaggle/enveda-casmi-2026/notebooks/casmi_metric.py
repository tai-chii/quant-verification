"""Kaggle scoring for CASMI: Mean Reciprocal Rank @ max_rank (MRR@25 by default).

Submission is one row per molecule, `molecule_id,smiles`, where `smiles` holds up to `max_rank`
candidate structures joined by semicolons, best guess first:

    molecule_id,smiles
    m_0014ef,CCO;CC(=O)O;c1ccccc1

Each molecule scores 1/position of the first guess whose tautomer-canonical InChIKey14 matches
the answer, else 0. There is exactly one correct structure per molecule, so nothing accumulates
past the first hit -- this is reciprocal rank, not average precision, and it stays reciprocal
rank even if `canonical_ik14s_all` is later extended to accept several indistinguishable
isomers, because the loop breaks on the first match. `max_rank` is a metric parameter set on
the competition page.
Inlines RDKit canonicalization to run standalone on Kaggle.

Stereochemistry is stripped before the tautomer canonicalization -- see
`canonicalize_smiles_to_ik14` for why comparing InChIKey14 is not on its own enough to deliver
the "stereochemistry is free" guarantee the competition makes.
"""

import importlib
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd

# Solution key canonicalized with RDKit 2026.03.3. RDKit's TautomerEnumerator output has changed
# between releases, so this pin decides which submissions match; it is not a convenience.
# https://pypi.org/project/rdkit/2026.3.3/
EXPECTED_RDKIT_VERSION = '2026.03.3'
# PyPI spells the same release 2026.3.3 -- PEP 440 strips the leading zero -- while
# rdkit.__version__ reports it zero-padded. Both strings appear below on purpose.
RDKIT_REQUIREMENT = 'rdkit==2026.3.3'
# RDKit is not in docker-python, so the wheel ships as a competition input and is installed
# offline at scoring time. Wheel dataset: https://www.kaggle.com/datasets/<owner>/rdkit-2026-3-3-wheel
RDKIT_WHEEL_DIR = '/kaggle/input/datasets/metric/rdkit-2026-3-3-wheel'

# Bound by install_dependencies(); importing this module must not require RDKit, because the
# orchestrator imports it before anything has had a chance to install.
Chem = None
_tautomer_canonicalizer = None


class HostVisibleError(Exception):
    pass


def install_dependencies() -> None:
    """Make RDKit importable, installing it from the bundled wheel if the image lacks it.

    Idempotent and cheap on repeat calls. Called at the top of score() rather than at import time:
    validate_local_metrics and the orchestrator both import this module first, and an import-time
    install would run before the competition inputs are mounted.
    """
    global Chem, _tautomer_canonicalizer
    if Chem is not None:
        return

    try:
        import rdkit
    except ImportError:
        if not os.path.isdir(RDKIT_WHEEL_DIR):
            raise HostVisibleError(
                f'{RDKIT_WHEEL_DIR} does not exist, so {RDKIT_REQUIREMENT} cannot be installed. '
                f'Attach the wheel dataset to the metric notebook as an input.'
            )
        # pip rather than uv: pip always installs into the interpreter running it, whereas
        # `uv pip install` wants a virtualenv and exits 2 when there isn't one. --no-deps because
        # rdkit only needs numpy and Pillow, both already in the image; without it the resolver
        # goes looking for them and --no-index leaves it nowhere to look.
        command = [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--no-deps',
            '--no-index',
            f'--find-links={RDKIT_WHEEL_DIR}',
            RDKIT_REQUIREMENT,
        ]
        # Captured, not inherited: a bare check=True reports only the exit status, which says
        # nothing about whether the wheel was missing, unresolvable, or wrong for this Python.
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            available = sorted(os.listdir(RDKIT_WHEEL_DIR))
            raise HostVisibleError(
                f'{" ".join(command)} exited {result.returncode}. '
                f'Python {sys.version_info.major}.{sys.version_info.minor}; '
                f'{RDKIT_WHEEL_DIR} contains {available}. '
                f'stderr: {result.stderr[-1500:]} stdout: {result.stdout[-1500:]}'
            )
        importlib.invalidate_caches()
        try:
            import rdkit
        except ImportError as err:
            raise HostVisibleError(f'{RDKIT_REQUIREMENT} installed but still not importable: {err}')

    from rdkit import Chem as _Chem
    from rdkit import RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize

    RDLogger.DisableLog('rdApp.*')
    if rdkit.__version__ != EXPECTED_RDKIT_VERSION:
        warnings.warn(
            f'RDKit version mismatch: solution={EXPECTED_RDKIT_VERSION}, scoring={rdkit.__version__}. Canonicalization may differ.',
            UserWarning,
        )
    Chem = _Chem
    _tautomer_canonicalizer = rdMolStandardize.TautomerEnumerator()


def canonicalize_smiles_to_ik14(smiles: str) -> str:
    """Canonicalize SMILES to InChIKey14, or None if parsing fails.

    Stereochemistry is removed *before* the tautomer canonicalization, not left to fall out of
    the InChIKey14 truncation afterwards. Truncating to InChIKey14 discards the stereo block, so
    it looks like it should already make stereochemistry free -- but the canonicalization runs
    first, and `TautomerEnumerator` will not move a double bond whose position a neighbouring
    stereocentre constrains. The same skeleton drawn with and without that stereocentre can
    therefore land on two different canonical tautomers, and different tautomers are different
    connectivity, which is the part of the InChIKey14 that survives truncation. Stripping first
    makes the canonical form depend only on the skeleton, which is what the competition promises.

    Both the answer key and the submission go through this function, so the two sides can never
    be treated asymmetrically.
    """
    if not isinstance(smiles, str):
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        Chem.RemoveStereochemistry(mol)
        canonical_mol = _tautomer_canonicalizer.Canonicalize(mol)
        inchikey = Chem.MolToInchiKey(canonical_mol)
        return inchikey[:14]
    # RDKit's MolSanitizeException family subclasses ValueError; RuntimeError covers the C++
    # layer and TypeError covers Boost.Python argument errors. One participant's malformed
    # SMILES must never take the whole scoring run down, so a failure here is just a non-match.
    except (ValueError, RuntimeError, TypeError):
        return None


def heavy_atom_composition(smiles: str):
    """Heavy-atom element counts (excluding H, ignoring charge) as a hashable key, or None
    if parsing fails.

    Cheap (no tautomer enumeration) -- used to gate the expensive canonicalization. Anything
    that shares an InChIKey14 with an accepted structure has the same heavy-atom skeleton, so
    a heavy-atom-composition mismatch lets us skip canonicalization with no change to any
    score. We deliberately do NOT gate on full molecular formula: protomers / charge variants
    (e.g. a zwitterion C(=O)[O-]...[N+] vs its neutral-acid protomer C(=O)O...[N+]) share an
    InChIKey14 but differ in H count and charge, so a formula gate would wrongly reject them.
    """
    mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
    if mol is None:
        return None
    counts = {}
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        if sym != 'H':
            counts[sym] = counts.get(sym, 0) + 1
    return tuple(sorted(counts.items()))


class ParticipantVisibleError(Exception):
    pass


def score(
    solution: pd.DataFrame,
    submission: pd.DataFrame,
    row_id_column_name: str,
    max_rank: int = 25,
) -> float:
    """Score CASMI submissions using mean reciprocal rank.

    max_rank: how many ranked guesses each molecule may carry. Set on the competition page.

    Examples
    --------
    >>> import pandas as pd
    >>> solution = pd.DataFrame({
    ...     'molecule_id': ['m_1', 'm_2'],
    ...     'smiles': ['CCO', 'c1ccccc1'],
    ...     'Usage': ['Public', 'Public'],
    ... })

    Position in the semicolon-separated list is the rank: ethanol is guessed first and scores
    1.0, benzene is guessed second and scores 1/2, so the mean is 0.75.

    >>> submission = pd.DataFrame({
    ...     'molecule_id': ['m_1', 'm_2'],
    ...     'smiles': ['CCO;CC(=O)O', 'CC(=O)O;c1ccccc1'],
    ... })
    >>> score(solution, submission, 'molecule_id')
    0.75

    A molecule with no correct guess scores zero, and only the first correct guess counts, so
    repeating it gains nothing.

    >>> score(solution, pd.DataFrame({
    ...     'molecule_id': ['m_1', 'm_2'],
    ...     'smiles': ['CC(=O)O', 'c1ccccc1;c1ccccc1;c1ccccc1'],
    ... }), 'molecule_id')
    0.5

    Matching is on the tautomer-canonical InChIKey14, so stereochemistry is ignored: the
    submission below omits the stereocentre the answer specifies and still scores.

    >>> score(
    ...     pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['C[C@H](N)C(=O)O']}),
    ...     pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['CC(N)C(=O)O']}),
    ...     'molecule_id',
    ... )
    1.0

    Regression test for the stereo/tautomer interaction described in
    `canonicalize_smiles_to_ik14`. These two differ only in one stereocentre, but the
    stereocentre pins the enone double bond, so before stereochemistry was stripped up front
    they canonicalized to different tautomers -- UMCVTKGFWFSNGJ and PUSIBJUZNMNGHT -- and this
    scored 0.0 rather than 1.0.

    >>> score(
    ...     pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['C=C(C)C1CCC2CCC(=O)C=C2C1']}),
    ...     pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['C=C(C)[C@@H]1CCC2CCC(=O)C=C2C1']}),
    ...     'molecule_id',
    ... )
    1.0

    Malformed submissions raise ParticipantVisibleError.

    >>> try:
    ...     score(solution, pd.DataFrame({
    ...         'molecule_id': ['m_1', 'm_1'], 'smiles': ['CCO', 'CCO'],
    ...     }), 'molecule_id')
    ... except ParticipantVisibleError as err:
    ...     print(err)
    Each molecule_id must appear exactly once

    >>> try:
    ...     score(solution, pd.DataFrame({
    ...         'molecule_id': ['m_1'], 'smiles': [';'.join(['CCO'] * 3)],
    ...     }), 'molecule_id', max_rank=2)
    ... except ParticipantVisibleError as err:
    ...     print(err)
    At most 2 semicolon-separated guesses per molecule_id, got 3 for m_1

    An answer the canonicalizer cannot parse is a broken solution file, not a zero score.

    >>> try:
    ...     score(
    ...         pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['not a molecule']}),
    ...         pd.DataFrame({'molecule_id': ['m_1'], 'smiles': ['CCO']}),
    ...         'molecule_id',
    ...     )
    ... except HostVisibleError as err:
    ...     print(err)
    Solution SMILES for molecule_id m_1 could not be parsed: 'not a molecule'
    """
    install_dependencies()
    if not isinstance(max_rank, (int, np.integer)) or max_rank < 1:
        raise ValueError(f'max_rank must be a positive integer, got {max_rank!r}')
    required = ['molecule_id', 'smiles']
    if not all(c in submission.columns for c in required):
        raise ParticipantVisibleError(f'Missing columns: {required}')
    if len(submission) == 0:
        raise ParticipantVisibleError('Submission is empty')
    if submission[required].isna().any().any():
        raise ParticipantVisibleError('NaN in required columns')
    if 'smiles' not in solution.columns:
        raise ParticipantVisibleError('Solution missing smiles column')
    if submission['molecule_id'].duplicated().any():
        raise ParticipantVisibleError('Each molecule_id must appear exactly once')

    # One row per molecule; rank is position in the list, so there is no rank column to validate
    # and no way to claim two guesses share a rank. A semicolon cannot occur inside a valid SMILES
    # -- RDKit rejects "CCO;CC(=O)O" -- so splitting on it can never cut a legitimate guess in half.
    # Whitespace would not be safe here: RDKit reads "CCO ethanol" as ethanol with a name attached.
    guesses_by_molecule = {}
    for molecule_id, raw_guesses in zip(submission['molecule_id'], submission['smiles']):
        parsed = [candidate.strip() for candidate in str(raw_guesses).split(';')]
        parsed = [candidate for candidate in parsed if candidate]
        if not parsed:
            raise ParticipantVisibleError(f'No guesses for molecule_id {molecule_id}')
        if len(parsed) > max_rank:
            raise ParticipantVisibleError(f'At most {max_rank} semicolon-separated guesses per molecule_id, got {len(parsed)} for {molecule_id}')
        guesses_by_molecule[molecule_id] = parsed

    # Cheap heavy-atom-composition gate (computed up front; no tautomer enumeration).
    gate_keys = {s: heavy_atom_composition(s) for guesses in guesses_by_molecule.values() for s in guesses}

    scores = []
    unknown_ids = set(submission['molecule_id']) - set(solution['molecule_id'])
    if unknown_ids:
        print(f'Unknown molecule_ids: {sorted(unknown_ids)[:5]}{"..." if len(unknown_ids) > 5 else ""}')

    # Per molecule: the accepted InChIKey14 set and the heavy-atom compositions those accepted
    # structures can have (one composition in practice; built as a set to be safe). The keys are
    # derived from the answer SMILES through the same canonicalization a submission goes through,
    # rather than stored alongside them -- one source of truth, and the answer key cannot drift out
    # of step with the canonicalizer the way a precomputed column silently would.
    sol_dict = {}
    for _, row in solution.iterrows():
        molecule_id = row['molecule_id']
        accept_smiles = row['smiles'] if isinstance(row['smiles'], str) else ''
        candidates = [s for s in accept_smiles.split(',') if s]
        if not candidates:
            raise HostVisibleError(f'Solution has no answer SMILES for molecule_id {molecule_id}')
        accept_ik14s = {k for k in map(canonicalize_smiles_to_ik14, candidates) if k}
        accept_keys = {k for k in map(heavy_atom_composition, candidates) if k}
        # Skipping an unparseable answer would quietly drop the molecule from the mean, so a
        # corrupt key would read as a lower score rather than as a broken solution file.
        if not accept_ik14s or not accept_keys:
            raise HostVisibleError(f'Solution SMILES for molecule_id {molecule_id} could not be parsed: {accept_smiles!r}')
        sol_dict[molecule_id] = (accept_ik14s, accept_keys)

    # Memoize canonicalization so a repeated SMILES is only canonicalized once.
    canon_cache = {}

    def canon(smiles):
        if smiles not in canon_cache:
            canon_cache[smiles] = canonicalize_smiles_to_ik14(smiles)
        return canon_cache[smiles]

    for mol_id, (acceptable, accept_keys) in sol_dict.items():
        ap = 0.0
        for rank, guess in enumerate(guesses_by_molecule.get(mol_id, []), 1):
            # Gate: skip the costly tautomer canonicalization when heavy-atom composition
            # rules out a match. Not guarded on `accept_keys` being populated -- the solution
            # parsing above raises if it is empty, so a silently disabled gate cannot happen.
            if gate_keys[guess] not in accept_keys:
                continue
            if canon(guess) in acceptable:
                ap = 1.0 / rank
                break
        scores.append(ap)

    return float(np.mean(scores))
