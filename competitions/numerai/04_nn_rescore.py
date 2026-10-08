# -*- coding: utf-8 -*-
"""
04_nn_rescore.py  保存済みモデルの再採点 + 最終評価
03_nn_search.py の reset_index バグ（ベンチマーク結合が全NaN）を修正して再採点する
"""
import os, json, pickle, datetime as dt
import numpy as np, pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from numerai_tools.scoring import numerai_corr, correlation_contribution

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
DEVICE = torch.device(
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
print(f"デバイス: {DEVICE}")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BENCHMARK_COL = "v53_lgbm_ender60"
CORR_MIN = 0.0175 / 2

# ============================================================
# MLP 定義（03_nn_search.py と同じ）
# ============================================================
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

# ============================================================
# データ読み込み（index を保持する: reset_index しない）
# ============================================================
meta = json.load(open(os.path.join(DATA, "features.json")))
feats_small = meta["feature_sets"]["small"]
feats_medium = meta["feature_sets"]["medium"]

tr_meta = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"])
last_train_era = int(tr_meta["era"].max())
emb = [str(last_train_era + i).zfill(4) for i in range(1, 13)]
del tr_meta

bench_df = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"))
assert BENCHMARK_COL in bench_df.columns

# validation small（インデックスを保持）
print("validation (small) 読み込み中...")
va_small = pd.read_parquet(
    os.path.join(DATA, "validation.parquet"),
    columns=["era", "data_type", "target"] + feats_small,
    filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
)
va_small = va_small.dropna(subset=["target"])  # reset_index しない
va_small = va_small.join(bench_df[[BENCHMARK_COL]], how="left")
print(f"  {va_small['era'].nunique()}エラ・{len(va_small):,}行")
print(f"  ベンチマーク非NaN: {va_small[BENCHMARK_COL].notna().sum():,}/{len(va_small):,}")

# era 分割（探索用 前2/3 / 取っておく 後1/3）
eras_sorted = sorted(va_small["era"].unique())
n_eras = len(eras_sorted)
n_search = int(n_eras * 2 / 3)
eras_search = set(eras_sorted[:n_search])
eras_hold = set(eras_sorted[n_search:])
print(f"探索用: {len(eras_search)}エラ, 取っておく: {len(eras_hold)}エラ")

va_search_small = va_small[va_small["era"].isin(eras_search)].copy()

# medium（必要なら）
va_search_medium = None
va_hold_medium = None

def load_medium():
    global va_search_medium, va_hold_medium
    if va_search_medium is not None:
        return
    print("validation (medium) 読み込み中...")
    va_m = pd.read_parquet(
        os.path.join(DATA, "validation.parquet"),
        columns=["era", "data_type", "target"] + feats_medium,
        filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
    )
    va_m = va_m.dropna(subset=["target"])
    va_m = va_m.join(bench_df[[BENCHMARK_COL]], how="left")
    va_search_medium = va_m[va_m["era"].isin(eras_search)].copy()
    va_hold_medium = va_m[va_m["era"].isin(eras_hold)].copy()
    print(f"  medium 探索用: {va_search_medium['era'].nunique()}エラ")

# ============================================================
# 採点関数
# ============================================================
def score_per_era(va_df, pred_col):
    corr_vals, bmc_vals, era_list = [], [], []
    for era, g in va_df.groupby("era"):
        if g[BENCHMARK_COL].isna().all():
            continue
        preds_df = g[[pred_col]]
        bench_s = g[BENCHMARK_COL]
        tgt_s = g["target"]
        c = float(numerai_corr(preds_df, tgt_s).iloc[0])
        try:
            b = float(correlation_contribution(preds_df, bench_s, tgt_s).iloc[0])
        except Exception:
            b = np.nan
        corr_vals.append(c)
        bmc_vals.append(b)
        era_list.append(era)
    return pd.DataFrame({"corr": corr_vals, "bmc": bmc_vals}, index=era_list)

def block_se(series, block_size=12):
    vals = series.dropna().values
    n_blocks = len(vals) // block_size
    if n_blocks < 2:
        return float(np.std(vals, ddof=1) / np.sqrt(max(len(vals), 1)))
    blocks = [vals[i * block_size:(i + 1) * block_size].mean() for i in range(n_blocks)]
    return float(np.std(blocks, ddof=1) / np.sqrt(n_blocks))

# ============================================================
# 保存済みモデルを再採点
# ============================================================
trials_csv = os.path.join(HERE, "results", "nn_trials.csv")
df_orig = pd.read_csv(trials_csv)
records = df_orig.to_dict("records")

print(f"\n保存済みモデル数: {len(records)}")

for i, rec in enumerate(records):
    tid = int(rec["trial_id"])
    pt_path = os.path.join(HERE, "models", f"nn_trial_{tid:02d}.pt")
    if not os.path.exists(pt_path):
        print(f"Trial {tid}: チェックポイントなし。スキップ。")
        continue

    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    feats = ckpt["feats"]
    scaler = ckpt["scaler"]
    tgt_col = ckpt["target_col"]

    # 対応する検証データを選択
    if cfg["fs"] == "small":
        va_data = va_search_small
    else:
        load_medium()
        va_data = va_search_medium

    model = MLP(len(feats), cfg["layers"], cfg["dropout"], cfg["bn"])
    model.load_state_dict(ckpt["model_state"])
    model.to(DEVICE)
    model.eval()

    X_va = scaler.transform(va_data[feats].values.astype("float32"))
    with torch.no_grad():
        preds = model(torch.tensor(X_va, dtype=torch.float32).to(DEVICE)).cpu().numpy()

    va_cp = va_data.copy()
    va_cp["pred"] = preds
    scores = score_per_era(va_cp, "pred")

    corr_mean = float(scores["corr"].mean())
    corr_std = float(scores["corr"].std())
    bmc_mean = float(scores["bmc"].mean())
    bmc_std = float(scores["bmc"].std())
    sharpe = corr_mean / corr_std if corr_std > 0 else float("nan")

    records[i]["search_eras"] = len(scores)
    records[i]["corr_mean"] = round(corr_mean, 6)
    records[i]["corr_std"] = round(corr_std, 6)
    records[i]["bmc_mean"] = round(bmc_mean, 6)
    records[i]["bmc_std"] = round(bmc_std, 6)
    records[i]["sharpe"] = round(sharpe, 4)

    print(f"Trial {tid:2d}: CORR={corr_mean:.4f}±{corr_std:.4f}  BMC={bmc_mean:.5f}±{bmc_std:.5f}  Sharpe={sharpe:.2f}")

df_rescored = pd.DataFrame(records)
df_rescored.to_csv(trials_csv, index=False)
print(f"\nnn_trials.csv 更新完了。")

# ============================================================
# ベストモデルの選択
# ============================================================
valid = df_rescored[df_rescored["corr_mean"] >= CORR_MIN].copy()
if len(valid) == 0:
    print(f"警告: CORR 足切り ({CORR_MIN:.4f}) を通過したモデルがない。全試行から選ぶ。")
    valid = df_rescored.dropna(subset=["bmc_mean"])

best_row = valid.loc[valid["bmc_mean"].idxmax()]
best_id = int(best_row["trial_id"])
print(f"\n選んだモデル: Trial {best_id}")
print(f"  layers={best_row['layers']}, dropout={best_row['dropout']}, bn={best_row['batch_norm']}")
print(f"  探索用 CORR={best_row['corr_mean']:.4f}, BMC={best_row['bmc_mean']:.5f}")

# ============================================================
# 取っておく期間の最終評価（1回だけ）
# ============================================================
print(f"\n=== 取っておく期間の評価 ({len(eras_hold)}エラ) ===")

ckpt = torch.load(
    os.path.join(HERE, "models", f"nn_trial_{best_id:02d}.pt"),
    map_location="cpu",
    weights_only=False,
)
best_feats = ckpt["feats"]
best_scaler = ckpt["scaler"]
best_tgt_col = ckpt["target_col"]
best_cfg = ckpt["config"]

# 取っておく期間のデータ
if best_cfg["fs"] == "small":
    va_hold = va_small[va_small["era"].isin(eras_hold)].copy()
else:
    load_medium()
    va_hold = va_hold_medium.copy()

torch.manual_seed(SEED)
best_model = MLP(len(best_feats), best_cfg["layers"], best_cfg["dropout"], best_cfg["bn"])
best_model.load_state_dict(ckpt["model_state"])
best_model.cpu()
best_model.eval()

X_hold = best_scaler.transform(va_hold[best_feats].values.astype("float32"))
with torch.no_grad():
    pred_nn = best_model(torch.tensor(X_hold, dtype=torch.float32)).numpy()
va_hold["pred_nn"] = pred_nn

# ベースライン LightGBM
bl = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
bl_model = bl["model"]
bl_feats = bl["features"]

if best_cfg["fs"] != "small":
    # small の hold-out データを別途用意して LightGBM を予測
    va_hold_s = va_small[va_small["era"].isin(eras_hold)].copy()
    va_hold_s["pred_bl"] = bl_model.predict(va_hold_s[bl_feats])
    va_hold = va_hold.join(va_hold_s[["pred_bl"]], how="left")
else:
    va_hold["pred_bl"] = bl_model.predict(va_hold[bl_feats])

hold_nn = score_per_era(va_hold, "pred_nn")
va_hold_bl = va_hold.rename(columns={"pred_bl": "pred"})
hold_bl = score_per_era(va_hold_bl, "pred")

diff_bmc = hold_nn["bmc"] - hold_bl["bmc"]
diff_corr = hold_nn["corr"] - hold_bl["corr"]

print(f"  NN  CORR: {hold_nn['corr'].mean():.4f}  BMC: {hold_nn['bmc'].mean():.5f}")
print(f"  BL  CORR: {hold_bl['corr'].mean():.4f}  BMC: {hold_bl['bmc'].mean():.5f}")
print(f"  差  CORR: {diff_corr.mean():.4f}±{block_se(diff_corr):.4f}"
      f"  BMC: {diff_bmc.mean():.5f}±{block_se(diff_bmc):.5f}")

ratio_bmc = (hold_nn["bmc"].mean() / hold_bl["bmc"].mean()
             if hold_bl["bmc"].mean() != 0 else float("nan"))
ratio_corr = (hold_nn["corr"].mean() / hold_bl["corr"].mean()
              if hold_bl["corr"].mean() != 0 else float("nan"))

if ratio_bmc < 1:
    verdict = "基準と区別できない"
elif ratio_bmc < 2:
    verdict = "保留"
else:
    verdict = "改善"
print(f"  BMC比: {ratio_bmc:.3f}  CORR比: {ratio_corr:.3f}  → 判定: {verdict}")

# ベストモデル保存
best_model_path = os.path.join(HERE, "models", f"nn_best_trial{best_id:02d}.pt")
import shutil
shutil.copy(os.path.join(HERE, "models", f"nn_trial_{best_id:02d}.pt"), best_model_path)
print(f"ベストモデル保存: {best_model_path}")

# summary.csv に追記
summary_row = {
    "date": dt.date.today().isoformat(),
    "model": f"nn_trial_{best_id:02d}",
    "metric": "numerai_corr・BMC・エンバーゴ12",
    "eras": len(hold_nn),
    "mean": round(float(hold_nn["corr"].mean()), 6),
    "std": round(float(hold_nn["corr"].std()), 6),
    "bmc_mean": round(float(hold_nn["bmc"].mean()), 6),
    "bmc_std": round(float(hold_nn["bmc"].std()), 6),
    "bmc_vs_baseline_diff": round(float(diff_bmc.mean()), 6),
    "bmc_vs_baseline_se": round(block_se(diff_bmc), 6),
    "bmc_ratio": round(ratio_bmc, 4),
    "corr_vs_baseline_diff": round(float(diff_corr.mean()), 6),
    "corr_vs_baseline_se": round(block_se(diff_corr), 6),
    "corr_ratio": round(ratio_corr, 4),
    "verdict": verdict,
    "n_trials": len(records),
    "best_config": str(best_row["layers"]),
    "best_target": best_tgt_col,
    "best_fs": best_cfg["fs"],
}
f = os.path.join(HERE, "results", "summary.csv")
pd.DataFrame([summary_row]).to_csv(f, mode="a", header=False, index=False)
print(f"summary.csv に追記完了。")
print("\n完了。")
