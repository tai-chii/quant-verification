# -*- coding: utf-8 -*-
"""
08_feature_sets.py  (2026-10-04) 特徴量を small（42本）から広げると、xerxes_60 モデルの BMC は上がるか

=== 事前に固定した計画（結果を見る前に書いた） ===
背景 : 今の一番は xerxes_60・small 42本（taichi_te。公式診断 CORR 0.0179・BMC +0.0004）。
       公式の例は「medium か all の方が良い。RAM が要る」と書き、オンボーディングは faith（372本）を使う。
比べる2つ（パラメータ・ターゲット・間引き（4エラに1つ、先頭から）は taichi_te と同じ。特徴量だけ変える）:
  H faith 372本
  I medium 780本
基準 : F = xerxes_60・small（models/xerxes60_small.pkl）
採点 : 06 と同じ（validation・12エラ除外・numerai_corr・BMC は v53_lgbm_ender60）。
判定 : 主は BMC。比較2回なので |差÷SE| > 2 + ln2 ≈ 2.7 で採用、1〜2.7 保留、1未満は区別できない。
       CORR が F の半分を下回るものは採用しない。直近214エラは参考。
       採用でも、Numerai の実行制限（1 CPU・4GB・10分）に収まるかを別に確かめてから本番候補にする。
注意 : この PC の制限（1回180秒・メモリ4GB）のため、学習は 250本ずつ続きから足していく。
       faith は init_model で続きを学習、medium は「前までの予測を init_score にして次の250本」を足し合わせる方式。
       途中で乱数の流れが切れるので、一度に学習した場合と木が完全には同じにならない（性能の差は小さいはず）。
出力 : results/feature_sets.csv・_per_era.csv、models/xerxes60_{faith,medium}.txt
"""
import os, json, pickle, time, sys
import numpy as np, pandas as pd, lightgbm as lgb
from numerai_tools.scoring import numerai_corr, correlation_contribution

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data"); MD = os.path.join(HERE, "models")
CACHE = os.path.expanduser("~/numerai_cache"); os.makedirs(CACHE, exist_ok=True)
t0 = time.time(); LIMIT = 140
fs = json.load(open(os.path.join(DATA, "features.json")))["feature_sets"]
SETS = {"H": ("faith", fs["faith"]), "I": ("medium", fs["medium"])}
SMALL = pickle.load(open(os.path.join(MD, "baseline_small.pkl"), "rb"))["features"]
T = "target_xerxes_60"; N_TREES = 2000
PARAMS = dict(objective="regression", learning_rate=0.01, max_depth=5, num_leaves=31, feature_fraction=0.1,
              verbose=-1, num_threads=4)

# --- 学習 ---
import glob


def seg_files(name):
    one = os.path.join(MD, f"xerxes60_{name}.txt")
    return [one] if os.path.exists(one) else sorted(glob.glob(os.path.join(MD, f"xerxes60_{name}_seg*.txt")))


def n_trees(name):
    return sum(lgb.Booster(model_file=f).num_trees() for f in seg_files(name))


for k, (name, feats) in SETS.items():
    if n_trees(name) >= N_TREES:
        continue
    cp = os.path.join(CACHE, f"train_{name}.npz")
    if not os.path.exists(cp):
        import pyarrow.parquet as pq  # 行のまとまり×100列ずつ読み、使うエラの行だけ詰める（メモリ節約）
        pf = pq.ParquetFile(os.path.join(DATA, "train.parquet"))
        keep = set(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[::4])
        masks = []
        for g in range(pf.num_row_groups):
            t = pf.read_row_group(g, columns=["era", T]).to_pandas()
            masks.append((t.era.isin(keep) & t[T].notna()).values)
        n = sum(m.sum() for m in masks); X = np.empty((n, len(feats)), dtype=np.uint8); y = np.empty(n, dtype=np.float32)
        pos = 0
        for g, m in enumerate(masks):
            k_ = m.sum(); y[pos:pos + k_] = pf.read_row_group(g, columns=[T]).column(0).to_numpy(zero_copy_only=False)[m]
            for j in range(0, len(feats), 100):
                tb = pf.read_row_group(g, columns=feats[j:j + 100])
                for c in range(tb.num_columns):
                    X[pos:pos + k_, j + c] = tb.column(c).to_numpy(zero_copy_only=False)[m]
                del tb
            pos += k_
        np.savez(cp, X=X, y=y)
        print(f"{name}: 学習データを用意（{n:,}行）。もう一度実行。"); sys.exit(0)
    # メモリ節約のため、LightGBM 用のバイナリ（一度だけ作る）＋「250本ずつの部品」を足し合わせる方式で学習する。
    # 前の部品までの予測値（生の値）を init_score として渡し、続きの250本を学習する＝一度に学習するのと同じ考え方。
    xp = os.path.join(CACHE, f"train_{name}_X.npy"); yp = xp.replace("_X", "_y")
    if not os.path.exists(xp):
        z = np.load(cp); np.save(xp, z["X"]); np.save(yp, z["y"]); del z
    bp = os.path.join(CACHE, f"train_{name}.bin")
    Xm = np.load(xp, mmap_mode="r"); ym = np.load(yp)
    if not os.path.exists(bp):
        class Seq(lgb.Sequence):
            def __init__(self, a): self.a = a; self.batch_size = 20000
            def __getitem__(self, i): return self.a[i].astype(np.float64)
            def __len__(self): return len(self.a)
        lgb.Dataset(Seq(Xm), ym, params={"verbose": -1}).construct().save_binary(bp)
        print(f"{name}: LightGBM 用データを保存。もう一度実行。"); sys.exit(0)

    def raw_pred(fn):
        b = lgb.Booster(model_file=fn); out = np.empty(len(Xm))
        for i in range(0, len(Xm), 50000):
            out[i:i + 50000] = b.predict(Xm[i:i + 50000].astype(np.float32), raw_score=True)
        return out
    sp = os.path.join(CACHE, f"score_{name}.npz")
    segs = seg_files(name)
    if os.path.exists(sp) and int(np.load(sp)["n"]) == len(segs):
        score = np.load(sp)["s"]
    else:
        score = sum(raw_pred(f) for f in segs) if segs else None
        if score is not None: np.savez(sp, s=score, n=len(segs))
    while n_trees(name) < N_TREES and time.time() - t0 < LIMIT - 30:
        ds = lgb.Dataset(bp, init_score=score, params={"verbose": -1})
        bst = lgb.train(PARAMS, ds, num_boost_round=250)
        fn = os.path.join(MD, f"xerxes60_{name}_seg{len(segs):02d}.txt"); bst.save_model(fn); segs = seg_files(name)
        add = raw_pred(fn); score = add if score is None else score + add
        np.savez(sp, s=score, n=len(segs))
        print(f"{name}: {n_trees(name)}/{N_TREES} 本（{time.time()-t0:.0f}秒）", flush=True)
    print("もう一度実行して続きへ。"); sys.exit(0)

# --- 採点（エラのまとまりごとに読み込む） ---
F_MODEL = pickle.load(open(os.path.join(MD, "xerxes60_small.pkl"), "rb"))
BST = {k: [lgb.Booster(model_file=f) for f in seg_files(n)] for k, (n, _) in SETS.items()}
import pyarrow.parquet as pq
last = int(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[-1])
emb = {str(last + i).zfill(4) for i in range(1, 13)}
VP = pq.ParquetFile(os.path.join(DATA, "validation.parquet"))
idx_cache = os.path.join(CACHE, "val_index.parquet")  # 行のまとまりごとの era・data_type・target・id（小さいので一度だけ作る）
if not os.path.exists(idx_cache):
    parts = []
    for g in range(VP.num_row_groups):
        t = VP.read_row_group(g, columns=["id", "era", "data_type", "target"]).to_pandas()
        t["rg"] = g; t["row"] = np.arange(len(t)); parts.append(t)
    pd.concat(parts).to_parquet(idx_cache)
IDX = pd.read_parquet(idx_cache)
bm = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"), columns=["v53_lgbm_ender60"])
IDX = IDX[(IDX.data_type == "validation") & ~IDX.era.isin(emb) & IDX.target.notna()]
IDX = IDX[IDX.index.isin(bm.index)]
eras_all = sorted(IDX.era.unique())
ck = os.path.join(HERE, "results", "feature_sets_per_era.partial.csv")
done = pd.read_csv(ck, dtype={"era": str}) if (os.path.exists(ck) and os.path.getsize(ck) > 5) else pd.DataFrame()
todo = [e for e in eras_all if e not in set(done.era if len(done) else [])]
allf = sorted(set(SMALL) | set(fs["faith"]) | set(fs["medium"])); col = {f: i for i, f in enumerate(allf)}
print(f"検証 {len(eras_all)}エラ・残り {len(todo)}", flush=True)
rows = []
while todo and time.time() - t0 < 30:
    chunk = todo[:30]                                   # 60エラずつ。エラが「行のまとまり」をまたいでも読めるようにする
    sel = IDX[IDX.era.isin(chunk)]
    X = np.empty((len(sel), len(allf)), dtype=np.uint8)
    for g0 in sel.rg.unique():
        m = (sel.rg == g0).values; rws = sel.row.values[m]
        for j in range(0, len(allf), 100):
            tb = VP.read_row_group(g0, columns=allf[j:j + 100])
            for c in range(tb.num_columns):
                X[m, j + c] = tb.column(c).to_numpy(zero_copy_only=False)[rws]
            del tb
    ix = lambda fl: [col[f] for f in fl]
    pF = F_MODEL.predict(pd.DataFrame(X[:, ix(SMALL)], columns=SMALL))
    pk = {k: sum(b.predict(X[:, ix(feats)], raw_score=True) for b in BST[k]) for k, (n, feats) in SETS.items()}
    sel = sel.assign(F=pF, **pk).join(bm, how="left")
    for era, g in sel.groupby("era"):
        r = {"era": era}
        for k in ["F", "H", "I"]:
            v = g[k].rank(pct=True).to_frame("p")
            r[f"corr_{k}"] = numerai_corr(v, g["target"])["p"]
            r[f"bmc_{k}"] = correlation_contribution(v, g["v53_lgbm_ender60"], g["target"])["p"]
        rows.append(r)
    todo = [e for e in todo if e not in chunk]
    print(f"  {len(rows)} エラ採点（{time.time()-t0:.0f}秒）", flush=True)
done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True); done.to_csv(ck, index=False)
if len(done) < len(eras_all):
    print(f"途中保存: {len(done)}/{len(eras_all)} エラ。"); sys.exit(0)
pe = done.sort_values("era").reset_index(drop=True)
pe.to_csv(os.path.join(HERE, "results", "feature_sets_per_era.csv"), index=False)


def block_se(d, B=12):
    blk = d.groupby(np.arange(len(d)) // B).mean()
    return blk.std(ddof=1) / np.sqrt(len(blk))


out = []
for label, sub in [("全体", pe), ("直近214（参考）", pe.tail(214))]:
    for k in "FHI":
        row = {"期間": label, "版": k, "CORR平均": sub[f"corr_{k}"].mean(), "BMC平均": sub[f"bmc_{k}"].mean(),
               "CORRシャープ": sub[f"corr_{k}"].mean() / sub[f"corr_{k}"].std()}
        if k != "F":
            for m in ["corr", "bmc"]:
                d = (sub[f"{m}_{k}"] - sub[f"{m}_F"]).reset_index(drop=True)
                row[f"{m.upper()}差÷SE"] = d.mean() / block_se(d)
        out.append(row)
res = pd.DataFrame(out); res.to_csv(os.path.join(HERE, "results", "feature_sets.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(res.round(5).to_string(index=False))
f_corr = res[(res.期間 == "全体") & (res.版 == "F")].CORR平均.iloc[0]
for k in "HI":
    r = res[(res.期間 == "全体") & (res.版 == k)].iloc[0]; z = r["BMC差÷SE"]
    v = "採用" if (z > 2.7 and r["CORR平均"] >= f_corr / 2) else ("保留" if abs(z) >= 1 else "区別できない")
    print(f"判定 {k}（{SETS[k][0]}）: BMC差÷SE={z:+.2f} → {v}")
