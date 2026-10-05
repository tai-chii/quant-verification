# -*- coding: utf-8 -*-
"""
05_nn_final_eval.py  取っておく期間での最終評価（メモリ節約版: 20エラごとに処理）
"""
import os, json, pickle, datetime as dt
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BENCHMARK_COL = "v53_lgbm_ender60"
CORR_MIN = 0.0175 / 2
ERA_CHUNK = 20

# LightGBM を torch より先に読み込む（Mac MPS との共有ライブラリ競合を回避）
_bl = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
bl_model = _bl["model"]
bl_feats = _bl["features"]

import torch

class MLP(torch.nn.Module):
    def __init__(self, in_dim, layers, dropout, bn):
        super().__init__()
        seq = []
        d = in_dim
        for h in layers:
            seq.append(torch.nn.Linear(d, h))
            if bn:
                seq.append(torch.nn.BatchNorm1d(h))
            seq.append(torch.nn.ReLU())
            if dropout > 0:
                seq.append(torch.nn.Dropout(dropout))
            d = h
        seq.append(torch.nn.Linear(d, 1))
        self.net = torch.nn.Sequential(*seq)
    def forward(self, x):
        return self.net(x).squeeze(-1)

# ベストモデルを選択
trials_csv = os.path.join(HERE, "results", "nn_trials.csv")
df = pd.read_csv(trials_csv)
valid = df[df["corr_mean"] >= CORR_MIN].dropna(subset=["bmc_mean"])
if len(valid) == 0:
    valid = df.dropna(subset=["bmc_mean"])
best_row = valid.loc[valid["bmc_mean"].idxmax()]
best_id = int(best_row["trial_id"])
print(f"選んだモデル: Trial {best_id}")
print(f"  layers={best_row['layers']}, dropout={best_row['dropout']}, bn={best_row['batch_norm']}")
print(f"  探索用 CORR={best_row['corr_mean']:.4f}, BMC={best_row['bmc_mean']:.5f}")

# チェックポイント
ckpt = torch.load(
    os.path.join(HERE, "models", f"nn_trial_{best_id:02d}.pt"),
    map_location="cpu", weights_only=False,
)
best_feats = ckpt["feats"]
best_scaler = ckpt["scaler"]
best_cfg = ckpt["config"]
best_tgt_col = ckpt["target_col"]

# state dict の net indices を事前抽出
state = ckpt["model_state"]
net_indices = sorted(set(int(k.split(".")[1]) for k in state.keys() if k.startswith("net.")))
max_idx = max(net_indices)
use_bn = best_cfg["bn"]

def numpy_mlp_batch(X_batch):
    x = X_batch.astype("float32")
    for idx in net_indices:
        prefix = f"net.{idx}"
        is_last = (idx == max_idx)
        if f"{prefix}.running_mean" in state:
            gamma = state[f"{prefix}.weight"].numpy().astype("float32")
            beta  = state[f"{prefix}.bias"].numpy().astype("float32")
            mean  = state[f"{prefix}.running_mean"].numpy().astype("float32")
            var   = state[f"{prefix}.running_var"].numpy().astype("float32")
            x = (x - mean) / np.sqrt(var + 1e-5) * gamma + beta
            if not is_last:
                np.maximum(x, 0, out=x)
        elif f"{prefix}.weight" in state:
            W = state[f"{prefix}.weight"].numpy().astype("float32")
            b = state[f"{prefix}.bias"].numpy().astype("float32")
            if W.ndim == 2:
                x = x @ W.T + b
                if not is_last and not use_bn:
                    np.maximum(x, 0, out=x)
    return x.squeeze(-1)

# ベースライン LightGBM
bl = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
bl_model = bl["model"]
bl_feats = bl["features"]

# 相関計算（ランクベース・scipy なし）
def rank_normalize(v):
    n = len(v)
    r = np.argsort(np.argsort(v)).astype("float64")
    # タイ処理
    vals, inv, cnts = np.unique(v, return_inverse=True, return_counts=True)
    cum = np.concatenate([[0], np.cumsum(cnts)])
    avg = np.array([(cum[i] + cum[i+1] - 1) / 2.0 for i in range(len(vals))])
    r = avg[inv]
    # [0, 1] → z-score 近似（線形近似: (r + 0.5) / n → ppf）
    p = (r + 0.5) / n
    p = np.clip(p, 1e-6, 1 - 1e-6)
    # probit 近似 (Beasley-Springer-Moro)
    a = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
    b = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
    c = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
         0.0276438810333863, 0.0038405729373609, 0.0003951896511349,
         0.0000321767881768, 0.0000002888167364, 0.0000003960315187]
    r_in = p - 0.5
    out = np.where(
        np.abs(r_in) < 0.42,
        r_in * np.polyval(a[::-1], r_in**2) / np.polyval(b[::-1], r_in**2),
        np.sign(r_in) * np.polyval(c[::-1], np.where(r_in > 0, np.log(-np.log(1 - p)), np.log(-np.log(p))))
    )
    return out

def corr_contribution_manual(pred, bench, target):
    p_g = rank_normalize(pred)
    m_g = rank_normalize(bench)
    t = np.asarray(target, dtype="float64")
    mm = np.dot(m_g, m_g)
    if mm < 1e-10:
        return np.nan
    proj = np.dot(p_g, m_g) / mm
    orth = p_g - proj * m_g
    return float(np.dot(orth, t) / len(t))

def numerai_corr_manual(pred, target):
    p_g = rank_normalize(pred)
    t = np.asarray(target, dtype="float64")
    std_p = p_g.std()
    std_t = t.std()
    if std_p < 1e-10 or std_t < 1e-10:
        return np.nan
    p_n = (p_g - p_g.mean()) / std_p
    t_n = (t - t.mean()) / std_t
    return float(np.dot(p_n, t_n) / len(t_n))

# embargo 計算
tr_meta = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"])
last_train_era = int(tr_meta["era"].max())
emb = [str(last_train_era + i).zfill(4) for i in range(1, 13)]
del tr_meta

# 取っておく期間のエラを特定
va_meta = pd.read_parquet(
    os.path.join(DATA, "validation.parquet"),
    columns=["era", "data_type"],
    filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
)
eras_sorted = sorted(va_meta["era"].unique())
n_search = int(len(eras_sorted) * 2 / 3)
eras_hold = sorted(eras_sorted[n_search:])
del va_meta
print(f"取っておく期間: {len(eras_hold)}エラ ({eras_hold[0]} - {eras_hold[-1]})")

# ベンチマーク予測読み込み
bench_df = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"))

# ===== エラチャンクごとに処理 =====
corr_nn_all, bmc_nn_all, corr_bl_all, bmc_bl_all, era_list = [], [], [], [], []

for chunk_start in range(0, len(eras_hold), ERA_CHUNK):
    chunk_eras = eras_hold[chunk_start:chunk_start + ERA_CHUNK]

    # このチャンクのデータだけ読む
    chunk = pd.read_parquet(
        os.path.join(DATA, "validation.parquet"),
        columns=["era", "data_type", "target"] + list(dict.fromkeys(best_feats + bl_feats)),
        filters=[
            ("data_type", "==", "validation"),
            ("era", "in", chunk_eras),
        ],
    )
    chunk = chunk.dropna(subset=["target"])
    chunk = chunk.join(bench_df[[BENCHMARK_COL]], how="left")

    # NN 予測
    X = best_scaler.transform(chunk[best_feats].values.astype("float32"))
    chunk["pred_nn"] = numpy_mlp_batch(X)

    # LightGBM 予測
    chunk["pred_bl"] = bl_model.predict(chunk[bl_feats].values)

    # エラごとに採点
    for era, g in chunk.groupby("era"):
        if g[BENCHMARK_COL].isna().all():
            continue
        p_nn = g["pred_nn"].values
        p_bl = g["pred_bl"].values
        bench = g[BENCHMARK_COL].values
        tgt = g["target"].values

        corr_nn_all.append(numerai_corr_manual(p_nn, tgt))
        bmc_nn_all.append(corr_contribution_manual(p_nn, bench, tgt))
        corr_bl_all.append(numerai_corr_manual(p_bl, tgt))
        bmc_bl_all.append(corr_contribution_manual(p_bl, bench, tgt))
        era_list.append(era)

    print(f"  チャンク {chunk_start//ERA_CHUNK + 1}/{(len(eras_hold) + ERA_CHUNK - 1)//ERA_CHUNK} 完了 (era {chunk_eras[0]}-{chunk_eras[-1]})")
    del chunk

hold_nn = pd.DataFrame({"corr": corr_nn_all, "bmc": bmc_nn_all}, index=era_list)
hold_bl = pd.DataFrame({"corr": corr_bl_all, "bmc": bmc_bl_all}, index=era_list)

diff_bmc = hold_nn["bmc"] - hold_bl["bmc"]
diff_corr = hold_nn["corr"] - hold_bl["corr"]

def block_se(series, block_size=12):
    vals = series.dropna().values
    n_blocks = len(vals) // block_size
    if n_blocks < 2:
        return float(np.std(vals, ddof=1) / np.sqrt(max(len(vals), 1)))
    blocks = [vals[i * block_size:(i+1) * block_size].mean() for i in range(n_blocks)]
    return float(np.std(blocks, ddof=1) / np.sqrt(n_blocks))

print(f"\n=== 取っておく期間の結果 ({len(hold_nn)}エラ) ===")
print(f"  NN  CORR: {hold_nn['corr'].mean():.4f}  BMC: {hold_nn['bmc'].mean():.5f}")
print(f"  BL  CORR: {hold_bl['corr'].mean():.4f}  BMC: {hold_bl['bmc'].mean():.5f}")
print(f"  差  CORR: {diff_corr.mean():.4f}±{block_se(diff_corr):.4f}"
      f"  BMC: {diff_bmc.mean():.5f}±{block_se(diff_bmc):.5f}")

ratio_bmc = (hold_nn["bmc"].mean() / hold_bl["bmc"].mean()
             if abs(hold_bl["bmc"].mean()) > 1e-8 else float("nan"))
ratio_corr = (hold_nn["corr"].mean() / hold_bl["corr"].mean()
              if abs(hold_bl["corr"].mean()) > 1e-8 else float("nan"))

if np.isnan(ratio_bmc) or ratio_bmc < 1:
    verdict = "基準と区別できない"
elif ratio_bmc < 2:
    verdict = "保留"
else:
    verdict = "改善"
print(f"  BMC比: {ratio_bmc:.3f}  CORR比: {ratio_corr:.3f}  → 判定: {verdict}")

# ベストモデル保存
import shutil
best_model_path = os.path.join(HERE, "models", f"nn_best_trial{best_id:02d}.pt")
shutil.copy(os.path.join(HERE, "models", f"nn_trial_{best_id:02d}.pt"), best_model_path)

# summary.csv に追記
summary_row = {
    "date": dt.date.today().isoformat(),
    "model": f"nn_trial_{best_id:02d}",
    "metric": "numerai_corr_approx・BMC_approx・エンバーゴ12",
    "eras": len(hold_nn),
    "mean": round(float(hold_nn["corr"].mean()), 6),
    "std": round(float(hold_nn["corr"].std()), 6),
    "bmc_mean": round(float(hold_nn["bmc"].mean()), 6),
    "bmc_std": round(float(hold_nn["bmc"].std()), 6),
    "bmc_vs_baseline_diff": round(float(diff_bmc.mean()), 6),
    "bmc_vs_baseline_se": round(block_se(diff_bmc), 6),
    "bmc_ratio": round(ratio_bmc, 4) if not np.isnan(ratio_bmc) else "nan",
    "corr_vs_baseline_diff": round(float(diff_corr.mean()), 6),
    "corr_vs_baseline_se": round(block_se(diff_corr), 6),
    "corr_ratio": round(ratio_corr, 4),
    "verdict": verdict,
    "n_trials": len(df),
    "best_config": str(best_row["layers"]),
    "best_target": best_tgt_col,
    "best_fs": best_cfg["fs"],
}
f = os.path.join(HERE, "results", "summary.csv")
pd.DataFrame([summary_row]).to_csv(f, mode="a", header=False, index=False)
print(f"summary.csv に追記完了。")
print("\n完了。")
