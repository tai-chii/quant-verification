#!/usr/bin/env python3
"""
EURUSD H4  MAクロス 全パターン検証（ロング/ショート両方）

ルール
  2本MA : 短>長 (GC) でロング、短<長 (DC) でショート（ドテン、常に建玉あり）
  3本MA : 短>中>長 が成立したらロング → 短<中 (DC) で決済
          短<中<長 が成立したらショート → 短>中 (GC) で決済（揃っていない間はノーポジ）
  シグナルは足の終値で判定し、その終値で約定（FXは次足始値≒当足終値）
  コストは往復 --cost-pips（片道でその半分）

検定
  ・前半/後半（IS/OOS）でそれぞれ成績を計算 → 再現性
  ・ランダム化検定: 収益系列を循環シフトして「同じ売買パターンを相場とずらした」
    場合のシャープを K 通り計算（FFTで全シフトを一括計算）
      - 組合せごとの p値
      - 全組合せ中の最大シャープの帰無分布（データスヌーピング補正）

使い方
  python3 bt.py --data data/eurusd_h4.csv --budget-hours 3     # 予算に合わせて刻みを自動決定
  python3 bt.py --data ... --step 5 --max-period 300            # 刻みを手動指定
  途中で止めても同じコマンドで再実行すれば続きから再開します。
"""
import argparse, os, sys, time, json, itertools, glob, re, tempfile
import numpy as np
import pandas as pd
from multiprocessing import Pool

PIP = 1e-4
BPY = 6 * 5 * 52            # H4の年間本数（年率換算用）
COLS = ["ma", "n_ma", "S", "M", "L",
        "trades", "ev", "winrate", "pf", "hold_bars", "total_pips", "sharpe", "maxdd", "exposure",
        "n_long", "ev_long", "n_short", "ev_short",
        "trades_IS", "ev_IS", "sharpe_IS", "trades_OOS", "ev_OOS", "sharpe_OOS",
        "p_shift", "sharpe_dm", "sharpe_dm_IS", "sharpe_dm_OOS"]
MA_KINDS = ["SMA", "EMA"]

# ---------------------------------------------------------------- データ
def load_prices(path):
    df = pd.read_csv(path)
    low = {c.lower().strip(): c for c in df.columns}
    tkey = next(k for k in ["timestamp", "time", "datetime", "date", "gmt time", "local time"] if k in low)
    t = df[low[tkey]]
    if pd.api.types.is_numeric_dtype(t):
        idx = pd.to_datetime(t, unit="ms" if t.iloc[0] > 1e11 else "s", utc=True)
    else:
        idx = pd.to_datetime(t, utc=True, dayfirst=("." in str(t.iloc[0])[:6]))
    s = pd.Series(df[low["close"]].astype(float).values, index=idx).sort_index()
    s = s[~s.index.duplicated()].dropna()
    s = s[s > 0]
    step = s.index.to_series().diff().median()
    if step < pd.Timedelta("4h"):                     # M1/H1 などが来たら H4 に変換
        s = s.resample("4h").last().dropna()
    if "volume" in low:                               # 出来高0の足（週末の埋め足）を除外
        v = pd.Series(df[low["volume"]].values, index=idx)
        v = v[~v.index.duplicated()].reindex(s.index)
        if v.notna().all() and (v > 0).mean() > 0.5:
            s = s[v.values > 0]
    return s

def ma_matrix(px, periods, kind):
    T = len(px); M = np.full((len(periods), T), np.nan)
    if kind == "SMA":
        cs = np.concatenate([[0.0], np.cumsum(px)])
        for i, p in enumerate(periods):
            M[i, p - 1:] = (cs[p:] - cs[:-p]) / p
    else:
        ser = pd.Series(px)
        for i, p in enumerate(periods):
            e = ser.ewm(span=p, adjust=False).mean().to_numpy(copy=True)
            e[:3 * p] = np.nan                         # 立ち上がりの不安定区間は使わない
            M[i] = e
    return M

# ---------------------------------------------------------------- ポジション
def pos_2ma(S, L):
    valid = ~np.isnan(L)
    pos = np.where(S > L, 1, np.where(S < L, -1, 0)).astype(np.int8)
    pos[~valid] = 0
    return pos

def _side(run, cond, ar):
    prev = np.zeros_like(run); prev[:, 1:] = run[:, :-1]
    last_start = np.maximum.accumulate(np.where(run & ~prev, ar, -1), axis=1)
    last_ent = np.maximum.accumulate(np.where(run & cond, ar, -1), axis=1)
    return run & (last_ent >= last_start)

def pos_3ma(S, M, L):
    valid = ~np.isnan(L)
    ar = np.arange(S.shape[1])[None, :]
    up = (S > M) & valid
    dn = (S < M) & valid
    lp = _side(up, M > L, ar)      # 短>中 の連続区間内で 中>長 が一度でも揃った以降
    sp = _side(dn, M < L, ar)
    return lp.astype(np.int8) - sp.astype(np.int8)

# ---------------------------------------------------------------- 評価
G = {}

def init_worker(cfg):
    G.update(cfg)
    px = G["px"]
    G["MA"] = {k: ma_matrix(px, G["periods"], k) for k in G["kinds"]}
    r = np.zeros(len(px)); r[1:] = (px[1:] - px[:-1]) / PIP     # pips
    G["r"] = r
    T = len(r)
    G["Rf"] = np.fft.rfft(r); G["R2f"] = np.fft.rfft(r * r)

def eval_chunk(job):
    chunk_id, kind, nma, combos = job
    outp = os.path.join(G["outdir"], "chunks", f"{chunk_id:06d}.npz")
    if os.path.exists(outp):
        return chunk_id
    MA = G["MA"][kind]; r = G["r"]; T = len(r)
    half = G["cost"] / 2; split = G["split"]; shifts = G["shifts"]
    c = np.array(combos)
    if nma == 2:
        pos = pos_2ma(MA[c[:, 0]], MA[c[:, 1]])
    else:
        pos = pos_3ma(MA[c[:, 0]], MA[c[:, 1]], MA[c[:, 2]])
    h = np.zeros(pos.shape, np.float64); h[:, 1:] = pos[:, :-1]     # 足tで保有している建玉
    dh = np.abs(np.diff(h, axis=1, prepend=0))
    cost = dh * half
    gross = h * r[None, :]
    pnl = gross - cost
    n = len(c)
    res = np.full((n, len(COLS)), np.nan, np.float32)
    res[:, 0] = MA_KINDS.index(kind); res[:, 1] = nma
    res[:, 2] = G["periods"][c[:, 0]]
    res[:, 3] = G["periods"][c[:, 1]] if nma == 3 else 0
    res[:, 4] = G["periods"][c[:, -1]]

    def sh(x):
        m = x.mean(1); s = x.std(1)
        return np.where(s > 0, m / np.where(s > 0, s, 1) * np.sqrt(BPY), 0)

    sharpe = sh(pnl)
    eq = np.cumsum(pnl, 1)
    res[:, 10] = eq[:, -1]; res[:, 11] = sharpe
    res[:, 12] = (eq - np.maximum.accumulate(eq, 1)).min(1)
    res[:, 13] = (h != 0).mean(1)
    res[:, 20] = sh(pnl[:, :split]); res[:, 23] = sh(pnl[:, split:])
    # ドリフト除去版: 各期間の平均騰落を引いた収益で評価（「相場がずっと下げていたから売りが勝った」を除く）
    rdm = r.copy(); rdm[:split] -= r[:split].mean(); rdm[split:] -= r[split:].mean()
    pdm = h * rdm[None, :] - cost
    res[:, 25] = sh(h * (r - r.mean())[None, :] - cost)
    res[:, 26] = sh(pdm[:, :split]); res[:, 27] = sh(pdm[:, split:])

    # トレード単位
    cg = np.concatenate([np.zeros((n, 1)), np.cumsum(gross, 1)], 1)
    for i in range(n):
        hi = h[i]
        chg = np.flatnonzero(np.diff(hi, prepend=0, append=0))
        a, b = chg[:-1], chg[1:]
        side = hi[a]; keep = side != 0
        a, b, side = a[keep], b[keep], side[keep]
        if len(a) == 0:
            continue
        tp = cg[i, b] - cg[i, a] - G["cost"]
        w = tp[tp > 0].sum(); l = -tp[tp < 0].sum()
        res[i, 5] = len(tp); res[i, 6] = tp.mean(); res[i, 7] = (tp > 0).mean()
        res[i, 8] = w / l if l > 0 else np.inf; res[i, 9] = (b - a).mean()
        L_ = side > 0; S_ = ~L_
        res[i, 14] = L_.sum(); res[i, 15] = tp[L_].mean() if L_.any() else np.nan
        res[i, 16] = S_.sum(); res[i, 17] = tp[S_].mean() if S_.any() else np.nan
        isI = a < split
        res[i, 18] = isI.sum(); res[i, 19] = tp[isI].mean() if isI.any() else np.nan
        res[i, 21] = (~isI).sum(); res[i, 22] = tp[~isI].mean() if (~isI).any() else np.nan

    # ランダム化検定（循環シフト, FFTで全シフト一括）
    # pnl_k[t] = h[t]*r[t-k] - cost[t]
    Hf = np.fft.rfft(h, axis=1); Af = np.fft.rfft(np.abs(h), axis=1); Cf = np.fft.rfft(h * cost, axis=1)
    S1 = np.fft.irfft(Hf * np.conj(G["Rf"])[None, :], n=T, axis=1)[:, shifts] - cost.sum(1)[:, None]
    S2 = (np.fft.irfft(Af * np.conj(G["R2f"])[None, :], n=T, axis=1)[:, shifts]
          - 2 * np.fft.irfft(Cf * np.conj(G["Rf"])[None, :], n=T, axis=1)[:, shifts]
          + (cost ** 2).sum(1)[:, None])
    mu = S1 / T; var = np.maximum(S2 / T - mu ** 2, 1e-18)
    null_sh = mu / np.sqrt(var) * np.sqrt(BPY)                        # (n, K)
    res[:, 24] = ((null_sh >= sharpe[:, None]).sum(1) + 1) / (len(shifts) + 1)
    tmp = outp + ".tmp"                              # 書き終わってから名前を変える（同期中の半端なファイル対策）
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, res=res, null_max=null_sh.max(0).astype(np.float32),
                        null_mean=null_sh.mean(0).astype(np.float32), n=n,
                        family=f"{kind}_{nma}")
    os.replace(tmp, outp)
    return chunk_id

# ---------------------------------------------------------------- ジョブ
def build_jobs(periods, kinds, chunk):
    jobs = []; cid = 0
    idx = range(len(periods))
    for kind in kinds:
        for nma in (2, 3):
            combos = list(itertools.combinations(idx, nma))
            for s in range(0, len(combos), chunk):
                jobs.append((cid, kind, nma, combos[s:s + chunk])); cid += 1
    return jobs

def n_combos(np_):
    return np_ * (np_ - 1) // 2 + np_ * (np_ - 1) * (np_ - 2) // 6

def make_cfg(s, args, periods, outdir):
    px = s.values.astype(float)
    T = len(px)
    split = int(np.searchsorted(s.index.values, np.datetime64(pd.Timestamp(args.split).tz_localize(None)))) \
        if args.split else T // 2
    rng = np.random.default_rng(args.seed)
    gap = 6 * 5 * 13                                   # 最低でも約3か月ずらす
    shifts = np.sort(rng.choice(np.arange(gap, T - gap), size=args.n_shifts, replace=False))
    return dict(px=px, periods=np.array(periods), kinds=args.kinds, cost=args.cost_pips,
                split=split, shifts=shifts, outdir=outdir)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--split", default=None, help="前半/後半の境目 (省略時は期間の中点)")
    ap.add_argument("--min-period", type=int, default=5)
    ap.add_argument("--max-period", type=int, default=300)
    ap.add_argument("--step", type=int, default=None, help="MA期間の刻み。省略時は --budget-hours から自動決定")
    ap.add_argument("--budget-hours", type=float, default=3.0)
    ap.add_argument("--kinds", nargs="+", default=["SMA", "EMA"], choices=MA_KINDS)
    ap.add_argument("--cost-pips", type=float, default=0.8, help="往復コスト(pips)")
    ap.add_argument("--n-shifts", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start-frac", type=float, default=0.0,
                    help="複数PCで分担するとき、ジョブ一覧のどこから始めるか(0〜1)。他PCが済ませた分は飛ばす")
    ap.add_argument("--no-merge", action="store_true", help="最後の集計をしない（Windows側用）")
    ap.add_argument("--merge-only", action="store_true", help="計算せず、そろったチャンクを集計だけする")
    args = ap.parse_args()

    s = load_prices(args.data)
    s = s[s.index >= pd.Timestamp(args.start, tz="UTC")]
    if args.end:
        s = s[s.index < pd.Timestamp(args.end, tz="UTC")]
    s.index = s.index.tz_convert(None)
    print(f"データ: {s.index[0]} 〜 {s.index[-1]}  {len(s):,}本  (H4)", flush=True)

    # ---- 途中で止まった前回の実行があれば、その刻みで再開
    if args.step is None:
        prev = sorted(glob.glob(os.path.join(args.out, f"step*_p{args.min_period}-{args.max_period}_{'-'.join(args.kinds)}")))
        prev = [p for p in prev if not os.path.exists(os.path.join(p, "null_max.npz"))]
        if prev:
            args.step = int(os.path.basename(prev[-1]).split("_")[0][4:])
            print(f"前回の途中結果を検出 → 刻み {args.step} で再開", flush=True)
    # ---- 刻みの自動決定（ベンチマーク）
    if args.step is None:
        print(f"ベンチマーク中（{args.workers}並列）...", flush=True)
        periods = list(range(args.min_period, args.max_period + 1, 5))
        bdir = os.path.join(tempfile.gettempdir(), "_bt_bench")
        cfg = make_cfg(s, args, periods, bdir); os.makedirs(os.path.join(bdir, "chunks"), exist_ok=True)
        for f in glob.glob(os.path.join(bdir, "chunks", "*")): os.remove(f)
        jobs = build_jobs(periods, args.kinds, args.chunk)
        bj = [j for j in jobs if j[2] == 3][: args.workers * 2]
        t0 = time.time()
        with Pool(args.workers, init_worker, (cfg,)) as p:
            p.map(eval_chunk, bj)
        el = time.time() - t0
        per_combo = el / sum(len(j[3]) for j in bj) * args.workers   # 1コアあたり秒/組
        budget = args.budget_hours * 3600 * 0.85
        step = 5
        for st in [1, 2, 3, 4, 5, 10]:
            npd = len(range(args.min_period, args.max_period + 1, st))
            est = n_combos(npd) * len(args.kinds) * per_combo / args.workers
            if est <= budget:
                step = st; break
        args.step = step
        print(f"  1組あたり {per_combo*1000:.1f} ms/コア → 刻み {step} を採用", flush=True)

    periods = list(range(args.min_period, args.max_period + 1, args.step))
    tag = f"step{args.step}_p{args.min_period}-{args.max_period}_{'-'.join(args.kinds)}"
    outdir = os.path.join(args.out, tag)
    os.makedirs(os.path.join(outdir, "chunks"), exist_ok=True)
    cfg = make_cfg(s, args, periods, outdir)
    meta = dict(start=str(s.index[0]), end=str(s.index[-1]), bars=len(s), split_bar=cfg["split"],
                split_date=str(s.index[cfg["split"]]), periods=periods, kinds=args.kinds,
                cost_pips=args.cost_pips, n_shifts=args.n_shifts, bpy=BPY,
                bh_pips=float((s.values[-1] - s.values[0]) / PIP))
    if not os.path.exists(os.path.join(outdir, "meta.json")):
        json.dump(meta, open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    jobs = build_jobs(periods, args.kinds, args.chunk)
    total = sum(len(j[3]) for j in jobs)
    chunk_files = lambda: [f for f in glob.glob(os.path.join(outdir, "chunks", "*.npz"))
                           if re.fullmatch(r"\d{6}\.npz", os.path.basename(f))]
    done0 = len(chunk_files())
    print(f"組合せ: {total:,} 通り（MA期間 {len(periods)} 種 × {args.kinds} × 2本/3本）  "
          f"チャンク {len(jobs)}（済 {done0}）", flush=True)
    t0 = time.time(); done = 0
    off = int(len(jobs) * args.start_frac) % max(len(jobs), 1)
    order = jobs[off:] + jobs[:off]
    todo = [] if args.merge_only else \
        [j for j in order if not os.path.exists(os.path.join(outdir, "chunks", f"{j[0]:06d}.npz"))]
    todo_n = sum(len(j[3]) for j in todo)
    with (Pool(args.workers, init_worker, (cfg,)) if todo else _Null()) as p:
        sizes = {j[0]: len(j[3]) for j in todo}
        for cid in p.imap_unordered(eval_chunk, todo):
            done += sizes[cid]
            el = time.time() - t0
            eta = el / done * (todo_n - done)
            print(f"\r  {done:,}/{todo_n:,}  経過 {el/60:5.1f}分  残り約 {eta/60:5.1f}分   ", end="", flush=True)
    files = sorted(chunk_files())
    if len(files) < len(jobs):
        print(f"\nこのPCの担当分は終了。全体 {len(files)}/{len(jobs)} チャンク（残りは他PCが計算中か未同期）。"
              f"\nそろったら Mac で: python3 bt.py --data ... --step {args.step} --merge-only")
        return
    if args.no_merge:
        print("\n全チャンクそろいました（集計は Mac 側で行います）"); return
    print("\n集計中...", flush=True)

    # ---- 結合
    res = []; fam = {}
    for f in files:
        z = np.load(f)
        res.append(z["res"]); k = str(z["family"])
        if k not in fam:
            fam[k] = z["null_max"].copy()
        else:
            fam[k] = np.maximum(fam[k], z["null_max"])
    df = pd.DataFrame(np.concatenate(res), columns=COLS)
    df["ma"] = df["ma"].map(dict(enumerate(MA_KINDS)))
    df = df.astype({"n_ma": int, "S": int, "M": int, "L": int})
    df.to_parquet(os.path.join(outdir, "results.parquet")) if _has_parquet() else \
        df.to_csv(os.path.join(outdir, "results.csv.gz"), index=False)
    np.savez(os.path.join(outdir, "null_max.npz"), **fam)
    print(f"完了: {outdir}  （次: python3 analyze.py {outdir}）")

class _Null:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def imap_unordered(self, f, it): return iter(())

def _has_parquet():
    try:
        import pyarrow  # noqa
        return True
    except Exception:
        return False

if __name__ == "__main__":
    main()
