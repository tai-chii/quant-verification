import sys, time
sys.path.insert(0, '/tmp/claude-0')
import numpy as np
import pyarrow.parquet as pq
import pyarrow.compute as pc
import pandas as pd
from casmi_metric import score

TRAIN_PATH = "/tmp/claude-0/enveda-casmi-data/train.parquet"
PRECURSOR_PPM_TOL = 15.0
PEAK_MATCH_DA_TOL = 0.01
TOP_K = 25
N_HELD = 400
SEED = 0


def mem():
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


t0 = time.time()
light = pq.read_table(
    TRAIN_PATH, columns=['inchikey14', 'precursor_mz'],
    filters=[('instrument_type', '==', 'timsTOF')],
)
print(f'light (timsTOF-only) loaded: {light.num_rows} rows in {time.time()-t0:.1f}s, mem={mem():.0f}MB')

ik_col = light.column('inchikey14').combine_chunks()
mz_all = light.column('precursor_mz').to_numpy(zero_copy_only=False)
n_total = light.num_rows

uniq_table = pc.unique(ik_col)
n_uniq = len(uniq_table)
print(f'unique molecules (timsTOF): {n_uniq}, mem={mem():.0f}MB')

rng = np.random.RandomState(SEED)
perm = rng.permutation(n_uniq)
held_ids_arr = uniq_table.take(perm[:N_HELD])

is_held_arrow = pc.is_in(ik_col, value_set=held_ids_arr)
is_held = is_held_arrow.to_numpy(zero_copy_only=False)
print(f'is_held computed, n_held_rows={is_held.sum()}, mem={mem():.0f}MB')

ik_all = ik_col.to_numpy(zero_copy_only=False)  # object array of python strings, needed for grouping later

pool_orig_idx = np.where(~is_held)[0]
held_orig_idx = np.where(is_held)[0]
print(f'pool rows: {len(pool_orig_idx)}  held rows: {len(held_orig_idx)}  mem={mem():.0f}MB')

pool_mz = mz_all[pool_orig_idx]
order = np.argsort(pool_mz)
pool_orig_idx_sorted = pool_orig_idx[order]
pool_mz_sorted = pool_mz[order]
pool_ik_sorted = ik_all[pool_orig_idx_sorted]
del pool_mz, order
print(f'pool sorted, mem={mem():.0f}MB')

held_mz = mz_all[held_orig_idx]
query_lo = np.empty(len(held_orig_idx), dtype=np.int64)
query_hi = np.empty(len(held_orig_idx), dtype=np.int64)
needed_pool_orig = set()
for i, mzv in enumerate(held_mz):
    w = mzv * PRECURSOR_PPM_TOL * 1e-6
    lo = np.searchsorted(pool_mz_sorted, mzv - w, side='left')
    hi = np.searchsorted(pool_mz_sorted, mzv + w, side='right')
    query_lo[i], query_hi[i] = lo, hi
    if hi > lo:
        needed_pool_orig.update(pool_orig_idx_sorted[lo:hi].tolist())

print(f'needed pool rows (candidates): {len(needed_pool_orig)} of {len(pool_orig_idx)}, mem={mem():.0f}MB')
needed_all = needed_pool_orig | set(held_orig_idx.tolist())
print(f'total rows needing heavy cols: {len(needed_all)}, mem={mem():.0f}MB')

del light, ik_col, is_held_arrow, uniq_table  # free what we can

# NOTE: 'needed_all' indexes are positions within the TIMSTOF-FILTERED table, not the
# raw file's row order. We must re-derive raw file row numbers by re-scanning with the
# same filter and tracking a running timsTOF-relative counter.
t1 = time.time()
heavy = {}
timstof_pos = 0
pf = pq.ParquetFile(TRAIN_PATH)
for batch in pf.iter_batches(
        columns=['instrument_type', 'normalized_smiles', 'ms2_mzs', 'ms2_normalized_intensities'],
        batch_size=20_000):
    instr = batch.column('instrument_type').to_numpy(zero_copy_only=False)
    tims_mask = instr == 'timsTOF'
    n_tims_in_batch = int(tims_mask.sum())
    if n_tims_in_batch == 0:
        continue
    local_tims_positions = np.where(tims_mask)[0]
    # positions (in the global timsTOF-relative index) covered by this batch:
    batch_global_positions = np.arange(timstof_pos, timstof_pos + n_tims_in_batch)
    hits_mask = np.fromiter((p in needed_all for p in batch_global_positions), dtype=bool, count=n_tims_in_batch)
    if hits_mask.any():
        smi_col = batch.column('normalized_smiles')
        mzs_col = batch.column('ms2_mzs')
        ints_col = batch.column('ms2_normalized_intensities')
        hit_local = local_tims_positions[hits_mask]
        hit_global = batch_global_positions[hits_mask]
        for li, g in zip(hit_local, hit_global):
            mzs = np.asarray(mzs_col[int(li)].as_py(), dtype=float)
            ints = np.asarray(ints_col[int(li)].as_py(), dtype=float)
            o = np.argsort(mzs)
            heavy[int(g)] = (smi_col[int(li)].as_py(), mzs[o], ints[o])
    timstof_pos += n_tims_in_batch
print(f'fetched heavy cols for {len(heavy)}/{len(needed_all)} rows in {time.time()-t1:.1f}s, mem={mem():.0f}MB')


def matched_peak_cosine(mzs_a, ints_a, mzs_b_sorted, ints_b_sorted, tol=PEAK_MATCH_DA_TOL):
    if len(mzs_a) == 0 or len(mzs_b_sorted) == 0:
        return 0.0
    num = 0.0
    for mzv, inten in zip(mzs_a, ints_a):
        lo = np.searchsorted(mzs_b_sorted, mzv - tol, side='left')
        hi = np.searchsorted(mzs_b_sorted, mzv + tol, side='right')
        if hi > lo:
            num += inten * ints_b_sorted[lo:hi].max()
    denom = np.sqrt(np.sum(ints_a ** 2)) * np.sqrt(np.sum(ints_b_sorted ** 2))
    return float(num / denom) if denom > 0 else 0.0


t2 = time.time()
held_ik = ik_all[held_orig_idx]
mol_to_held_positions = {}
for pos, ikv in enumerate(held_ik):
    mol_to_held_positions.setdefault(ikv, []).append(pos)

solution_rows, submission_rows = [], []
n_scored_pairs = 0
n_mol_done = 0
n_mol_total = len(mol_to_held_positions)
for ikv, positions in mol_to_held_positions.items():
    n_mol_done += 1
    if n_mol_done % 10 == 0:
        print(f'  progress: {n_mol_done}/{n_mol_total} molecules, {n_scored_pairs} pairs scored, '
              f'elapsed={time.time()-t2:.1f}s', flush=True)
    true_smiles = None
    best_score, best_smiles = {}, {}
    for pos in positions:
        orig = int(held_orig_idx[pos])
        if orig not in heavy:
            continue
        smi_a, mzs_a, ints_a = heavy[orig]
        true_smiles = smi_a
        lo, hi = int(query_lo[pos]), int(query_hi[pos])
        for cpos in range(lo, hi):
            corig = int(pool_orig_idx_sorted[cpos])
            if corig not in heavy:
                continue
            smi_b, mzs_b, ints_b = heavy[corig]
            sim = matched_peak_cosine(mzs_a, ints_a, mzs_b, ints_b)
            n_scored_pairs += 1
            cik = pool_ik_sorted[cpos]
            if sim > best_score.get(cik, -1.0):
                best_score[cik] = sim
                best_smiles[cik] = smi_b
    if true_smiles is None:
        continue
    ranked = sorted(best_score.items(), key=lambda kv: kv[1], reverse=True)[:TOP_K]
    guesses = [best_smiles[k] for k, _ in ranked] or ['C']
    solution_rows.append({'molecule_id': ikv, 'smiles': true_smiles})
    submission_rows.append({'molecule_id': ikv, 'smiles': ';'.join(guesses)})

print(f'scored {n_scored_pairs} spectrum pairs for {len(solution_rows)} molecules in {time.time()-t2:.1f}s')

sol_df = pd.DataFrame(solution_rows)
sub_df = pd.DataFrame(submission_rows)
s = score(sol_df, sub_df, 'molecule_id', max_rank=TOP_K)
print(f'\nspectral-retrieval local-CV MRR@25 (seed={SEED}, n_held={len(sol_df)}) = {s:.4f}')
