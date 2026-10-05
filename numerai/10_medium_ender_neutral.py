# -*- coding: utf-8 -*-
"""
10_medium_ender_neutral.py  (2026-10-04) medium で報酬の目的変数を直接学習した版（J）と、medium の中和版（K）は、今の本番（F）より報酬の式で良いか

=== 事前に固定した計画（結果を見る前に書いた） ===
背景 : 公式の報酬は 3×CORR60 + 15×MMC60（docs の Staking、2026-10-04 確認）。v5.3 では target＝target_ender_60。
       09 で I（xerxes_60・medium）は F（xerxes_60・small＝本番 TAICHI_TE）に対し 3CORR+15BMC の差÷SE +1.76（保留）→ live の別枠（TAICHI_MD）へ。
       「ender_60・small」は基準 A そのもの（04 の baseline_small）。まだ測っていないのは次の2つだけ。
比べる : J = medium 780本 × target（＝ender_60）。学習の設定は I と同じ（2000本・学習率0.01・深さ5・葉31・特徴量の割合0.1・4エラに1つ間引き・250本ずつ足し合わせ）。
         K = I の予測を、エラごとに small 42本の特徴量で 50% 中和（05 の B・taichi_fn と同じ計算、numerai_tools.scoring.neutralize）。
         これ以外は試さない。パラメータも動かさない。
採点 : 08・09 と同じ（validation・学習最後のエラの後12エラを除く・numerai_corr・BMC は v53_lgbm_ender60）。
       エラごとの payout = 3×CORR + 15×BMC（MMC の代わりに BMC。メタモデルの予測は取得できないため）。
比較 : J−F、K−F（主）。12エラのまとまりで標準誤差。参考に J−I、K−I も出す。
判定 : 比較は2回なので、差÷SE > 2 + ln2 ≈ 2.7 で採用候補、1〜2.7 保留、1 未満は区別できない。
注意 : 同じ検証期間を見るのは3回目。採用候補になっても本番は差し替えず、別枠で live に出し、出す前に live の判定基準を固定する。
出力 : results/medium_ender_neutral.csv・_per_era.csv、models/ender60_medium_seg*.txt
実行 : 1回約150秒まで。学習の部品、または採点の途中までで止まるので、終わるまで繰り返す。キャッシュは cache/（VM のディスクが一杯のため）。
"""
import os, json, pickle, time, sys, glob
import numpy as np, pandas as pd, lightgbm as lgb
from numerai_tools.scoring import numerai_corr, correlation_contribution, neutralize
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data"); MD = os.path.join(HERE, "models")
CACHE = os.path.join(HERE, "cache"); os.makedirs(CACHE, exist_ok=True)
t0 = time.time(); LIMIT = float(os.environ.get("LIMIT", 150))
MED = json.load(open(os.path.join(DATA, "features.json")))["feature_sets"]["medium"]
SMALL = pickle.load(open(os.path.join(MD, "baseline_small.pkl"), "rb"))["features"]
T = "target"; N_TREES = 2000; NAME = "ender60_medium"
PARAMS = dict(objective="regression", learning_rate=0.01, max_depth=5, num_leaves=31, feature_fraction=0.1, verbose=-1, num_threads=4)
segs_of = lambda pre: sorted(glob.glob(os.path.join(MD, f"{pre}_seg*.txt")))
ntrees = lambda pre: sum(lgb.Booster(model_file=f).num_trees() for f in segs_of(pre))

# --- J の学習 ---
if ntrees(NAME) < N_TREES:
    xp = os.path.join(CACHE, "train_medium_X.npy"); yp = os.path.join(CACHE, "train_medium_target_y.npy")
    if not (os.path.exists(xp) and os.path.exists(yp)):
        import pyarrow.parquet as pq   # 途中で止めても続きから再開できる（行のまとまりごとに進み具合を保存）
        pf = pq.ParquetFile(os.path.join(DATA, "train.parquet")); stp = os.path.join(CACHE, "prep_state.json"); tmp = xp + ".tmp.npy"
        if not os.path.exists(stp):
            keep = set(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[::4])
            cnt = []
            for g in range(pf.num_row_groups):
                t = pf.read_row_group(g, columns=["era", T]).to_pandas(); cnt.append(int((t.era.isin(keep) & t[T].notna()).sum()))
            n = sum(cnt); np.lib.format.open_memmap(tmp, mode="w+", dtype=np.uint8, shape=(n, len(MED))).flush()
            np.save(yp + ".tmp.npy", np.zeros(n, np.float32))
            json.dump(dict(keep=sorted(keep), cnt=cnt, next=0), open(stp, "w")); print(f"準備: {n:,}行の枠を作成。もう一度実行。"); sys.exit(0)
        st = json.load(open(stp)); keep = set(st["keep"]); cnt = st["cnt"]
        X = np.load(tmp, mmap_mode="r+"); y = np.load(yp + ".tmp.npy")
        g = st["next"]; jj = st.get("col", 0)
        while g < pf.num_row_groups and time.time() - t0 < LIMIT - 40:
            pos = sum(cnt[:g]); k_ = cnt[g]
            t = pf.read_row_group(g, columns=["era", T]).to_pandas(); m = (t.era.isin(keep) & t[T].notna()).values
            if jj == 0: y[pos:pos + k_] = t[T].values[m]
            while jj < len(MED) and time.time() - t0 < LIMIT - 40:
                tb = pf.read_row_group(g, columns=MED[jj:jj + 50])
                for c in range(tb.num_columns): X[pos:pos + k_, jj + c] = tb.column(c).to_numpy(zero_copy_only=False)[m]
                del tb; jj += 50
            if jj >= len(MED): g += 1; jj = 0
        X.flush(); del X; np.save(yp + ".tmp.npy", y); st["next"] = g; st["col"] = jj; json.dump(st, open(stp, "w"))
        if g < pf.num_row_groups: print(f"準備: まとまり {g}/{pf.num_row_groups}・列 {jj}/{len(MED)}。もう一度実行。"); sys.exit(0)
        os.replace(tmp, xp); os.replace(yp + ".tmp.npy", yp); print("学習データを用意。もう一度実行。"); sys.exit(0)
    bp = os.path.join(CACHE, "train_medium_target.bin")
    Xm = np.load(xp, mmap_mode="r"); ym = np.load(yp)
    if not os.path.exists(bp):
        class Seq(lgb.Sequence):
            def __init__(self, a): self.a = a; self.batch_size = 20000
            def __getitem__(self, i): return self.a[i].astype(np.float64)
            def __len__(self): return len(self.a)
        lgb.Dataset(Seq(Xm), ym, params={"verbose": -1}).construct().save_binary(bp)
        print("LightGBM 用データを保存。もう一度実行。"); sys.exit(0)
    def raw_pred(fn):
        b = lgb.Booster(model_file=fn); out = np.empty(len(Xm))
        for i in range(0, len(Xm), 50000): out[i:i + 50000] = b.predict(Xm[i:i + 50000].astype(np.float32), raw_score=True)
        return out
    sp = os.path.join(CACHE, f"score_{NAME}.npz"); segs = segs_of(NAME)
    score = np.load(sp)["s"] if (os.path.exists(sp) and int(np.load(sp)["n"]) == len(segs)) else (sum(raw_pred(f) for f in segs) if segs else None)
    while ntrees(NAME) < N_TREES and time.time() - t0 < LIMIT - 40:
        bst = lgb.train(PARAMS, lgb.Dataset(bp, init_score=score, params={"verbose": -1}), num_boost_round=250)
        fn = os.path.join(MD, f"{NAME}_seg{len(segs):02d}.txt"); bst.save_model(fn); segs = segs_of(NAME)
        add = raw_pred(fn); score = add if score is None else score + add; np.savez(sp, s=score, n=len(segs))
        print(f"J: {ntrees(NAME)}/{N_TREES} 本（{time.time()-t0:.0f}秒）", flush=True)
    print("もう一度実行して続きへ。"); sys.exit(0)

# --- 採点 ---
import pyarrow.parquet as pq
F_MODEL = pickle.load(open(os.path.join(MD, "xerxes60_small.pkl"), "rb"))
BI = [lgb.Booster(model_file=f) for f in segs_of("xerxes60_medium")]; BJ = [lgb.Booster(model_file=f) for f in segs_of(NAME)]
last = int(pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"]).era.unique()[-1]); emb = {str(last + i).zfill(4) for i in range(1, 13)}
VP = pq.ParquetFile(os.path.join(DATA, "validation.parquet")); ic = os.path.join(CACHE, "val_index.parquet")
if not os.path.exists(ic):
    parts = []
    for g in range(VP.num_row_groups):
        t = VP.read_row_group(g, columns=["id", "era", "data_type", "target"]).to_pandas(); t["rg"] = g; t["row"] = np.arange(len(t)); parts.append(t)
    pd.concat(parts).to_parquet(ic); print("検証の索引を作成。もう一度実行。"); sys.exit(0)
IDX = pd.read_parquet(ic); bm = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"), columns=["v53_lgbm_ender60"])
IDX = IDX[(IDX.data_type == "validation") & ~IDX.era.isin(emb) & IDX.target.notna()]; IDX = IDX[IDX.index.isin(bm.index)]
eras_all = sorted(IDX.era.unique()); ck = os.path.join(HERE, "results", "medium_ender_neutral_per_era.partial.csv")
done = pd.read_csv(ck, dtype={"era": str}) if (os.path.exists(ck) and os.path.getsize(ck) > 5) else pd.DataFrame()
todo = [e for e in eras_all if e not in set(done.era if len(done) else [])]
allf = sorted(set(SMALL) | set(MED)); col = {f: i for i, f in enumerate(allf)}; ix = lambda fl: [col[f] for f in fl]
rows = []
while todo and time.time() - t0 < LIMIT - 60:
    chunk = todo[:30]; sel = IDX[IDX.era.isin(chunk)]; X = np.empty((len(sel), len(allf)), dtype=np.uint8)
    for g0 in sel.rg.unique():
        m = (sel.rg == g0).values; rws = sel.row.values[m]
        for j in range(0, len(allf), 100):
            tb = VP.read_row_group(g0, columns=allf[j:j + 100])
            for c in range(tb.num_columns): X[m, j + c] = tb.column(c).to_numpy(zero_copy_only=False)[rws]
            del tb
    XS = X[:, ix(SMALL)]; XM = X[:, ix(MED)]
    sel = sel.assign(F=F_MODEL.predict(pd.DataFrame(XS, columns=SMALL)), I=sum(b.predict(XM, raw_score=True) for b in BI),
                     J=sum(b.predict(XM, raw_score=True) for b in BJ)).join(bm, how="left")
    sel[SMALL] = XS.astype(float)
    for era, g in sel.groupby("era"):
        g = g.copy(); g["K"] = neutralize(g[["I"]].rank(pct=True), g[SMALL], proportion=0.5)["I"]
        r = {"era": era}
        for k in "FIJK":
            v = g[k].rank(pct=True).to_frame("p")
            r[f"corr_{k}"] = numerai_corr(v, g["target"])["p"]; r[f"bmc_{k}"] = correlation_contribution(v, g["v53_lgbm_ender60"], g["target"])["p"]
        rows.append(r)
    todo = [e for e in todo if e not in chunk]; print(f"  {len(rows)} エラ採点（{time.time()-t0:.0f}秒）", flush=True)
done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True); done.to_csv(ck, index=False)
if len(done) < len(eras_all): print(f"途中保存: {len(done)}/{len(eras_all)} エラ。"); sys.exit(0)
pe = done.sort_values("era").reset_index(drop=True)
for k in "FIJK": pe[f"pay_{k}"] = 3 * pe[f"corr_{k}"] + 15 * pe[f"bmc_{k}"]
pe.to_csv(os.path.join(HERE, "results", "medium_ender_neutral_per_era.csv"), index=False)
se = lambda d: d.groupby(np.arange(len(d)) // 12).mean().std(ddof=1) / np.sqrt(len(d) // 12 + (len(d) % 12 > 0))
out = []
for lab, sub in [("全体", pe), ("直近214（参考）", pe.tail(214).reset_index(drop=True))]:
    for k in "FIJK":
        row = dict(期間=lab, 版=k, CORR=sub[f"corr_{k}"].mean(), BMC=sub[f"bmc_{k}"].mean(), payout=sub[f"pay_{k}"].mean(), payoutシャープ=sub[f"pay_{k}"].mean() / sub[f"pay_{k}"].std())
        for base in ["F", "I"]:
            if k in "JK":
                d = (sub[f"pay_{k}"] - sub[f"pay_{base}"]).reset_index(drop=True); row[f"差÷SE_vs{base}"] = d.mean() / se(d)
        out.append(row)
R = pd.DataFrame(out); R.to_csv(os.path.join(HERE, "results", "medium_ender_neutral.csv"), index=False)
pd.set_option("display.width", 250); print(R.round(4).to_string(index=False))
for k in "JK":
    z = R[(R.期間 == "全体") & (R.版 == k)]["差÷SE_vsF"].iloc[0]
    print(f"判定 {k} 対 F: 差÷SE={z:+.2f} → " + ("採用候補（別枠で live へ）" if z > 2.7 else "保留" if abs(z) >= 1 else "区別できない"))
