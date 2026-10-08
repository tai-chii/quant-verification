# -*- coding: utf-8 -*-
"""
03_nn_search.py  ニューラルネット構造探索 (2026-10-03 固定)
主指標: 探索用期間（validation 前2/3）の BMC 平均が最大のモデルを選ぶ
副条件: CORR 平均 >= 0.0175/2 = 0.00875 の足切り
最後に取っておく期間（後1/3）で基準 LightGBM と比較する
"""
import os, json, pickle, datetime as dt, time
import numpy as np, pandas as pd
import torch, torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
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
os.makedirs(os.path.join(HERE, "models"), exist_ok=True)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)

MAX_TRIALS = 20
MAX_SEC = 2 * 3600
CORR_MIN = 0.0175 / 2
BENCHMARK_COL = "v53_lgbm_ender60"
BATCH_SMALL = 8192
BATCH_MEDIUM = 4096

# ============================================================
# 試行リスト（事前固定: 結果を見る前に決定）
# ============================================================
TRIALS_DEF = [
    # small, bn=True, dropout 変え
    {"id":  1, "layers": [128, 64],        "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  2, "layers": [256, 128],       "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  3, "layers": [256, 128, 64],   "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  4, "layers": [512, 256, 128],  "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  5, "layers": [128, 64],        "dropout": 0.0, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  6, "layers": [256, 128],       "dropout": 0.0, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  7, "layers": [256, 128, 64],   "dropout": 0.0, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  8, "layers": [128, 64],        "dropout": 0.3, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id":  9, "layers": [256, 128],       "dropout": 0.3, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id": 10, "layers": [256, 128, 64],   "dropout": 0.3, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    # small, bn=False
    {"id": 11, "layers": [128, 64],        "dropout": 0.2, "bn": False, "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id": 12, "layers": [256, 128],       "dropout": 0.2, "bn": False, "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id": 13, "layers": [256, 128, 64],   "dropout": 0.2, "bn": False, "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    # lr 変え
    {"id": 14, "layers": [256, 128],       "dropout": 0.2, "bn": True,  "lr": 5e-4, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    {"id": 15, "layers": [256, 128, 64],   "dropout": 0.2, "bn": True,  "lr": 5e-4, "wd": 0,    "target": "target",       "fs": "small",  "epochs": 50},
    # weight decay
    {"id": 16, "layers": [256, 128],       "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 1e-4, "target": "target",       "fs": "small",  "epochs": 50},
    {"id": 17, "layers": [256, 128, 64],   "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 1e-4, "target": "target",       "fs": "small",  "epochs": 50},
    # ender target
    {"id": 18, "layers": [256, 128, 64],   "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target_ender_60", "fs": "small", "epochs": 50},
    # medium feature set
    {"id": 19, "layers": [256, 128],       "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "medium", "epochs": 50},
    {"id": 20, "layers": [256, 128, 64],   "dropout": 0.2, "bn": True,  "lr": 1e-3, "wd": 0,    "target": "target",       "fs": "medium", "epochs": 50},
]

# ============================================================
# データ読み込み
# ============================================================
meta = json.load(open(os.path.join(DATA, "features.json")))
feats_small = meta["feature_sets"]["small"]
feats_medium = meta["feature_sets"]["medium"]

# embargo 計算
tr_meta = pd.read_parquet(os.path.join(DATA, "train.parquet"), columns=["era"])
last_train_era = int(tr_meta["era"].max())
sub_eras_tr = tr_meta["era"].unique()[::4]
emb = [str(last_train_era + i).zfill(4) for i in range(1, 13)]
del tr_meta

# small 学習データ
print("学習データ (small) 読み込み中...")
tr_small = pd.read_parquet(
    os.path.join(DATA, "train.parquet"),
    columns=["era", "target", "target_ender_60"] + feats_small,
)
tr_small = tr_small[tr_small["era"].isin(sub_eras_tr)].reset_index(drop=True)
print(f"  small: {tr_small['era'].nunique()}エラ・{len(tr_small):,}行")

# ベンチマーク予測
bench_df = pd.read_parquet(os.path.join(DATA, "validation_benchmark_models.parquet"))
assert BENCHMARK_COL in bench_df.columns

# validation 読み込み (small 特徴量)
print("検証データ (small) 読み込み中...")
va_small = pd.read_parquet(
    os.path.join(DATA, "validation.parquet"),
    columns=["era", "data_type", "target", "target_ender_60"] + feats_small,
    filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
)
va_small = va_small.dropna(subset=["target"]).reset_index(drop=True)
va_small = va_small.join(bench_df[[BENCHMARK_COL]], how="left")

# era 分割
eras_sorted = sorted(va_small["era"].unique())
n_eras = len(eras_sorted)
n_search = int(n_eras * 2 / 3)
eras_search = set(eras_sorted[:n_search])
eras_hold = set(eras_sorted[n_search:])
print(f"  validation: {n_eras}エラ（探索用: {len(eras_search)}, 取っておく: {len(eras_hold)}）")

va_search_small = va_small[va_small["era"].isin(eras_search)].copy()

# medium は後で遅延読み込み
tr_medium = None
va_search_medium = None

def load_medium_if_needed():
    global tr_medium, va_search_medium
    if tr_medium is not None:
        return
    print("medium データ読み込み中（時間かかります）...")
    tr_medium = pd.read_parquet(
        os.path.join(DATA, "train.parquet"),
        columns=["era", "target"] + feats_medium,
    )
    tr_medium = tr_medium[tr_medium["era"].isin(sub_eras_tr)].reset_index(drop=True)
    print(f"  medium train: {tr_medium['era'].nunique()}エラ・{len(tr_medium):,}行")

    va_m = pd.read_parquet(
        os.path.join(DATA, "validation.parquet"),
        columns=["era", "data_type", "target"] + feats_medium,
        filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
    )
    va_m = va_m.dropna(subset=["target"]).reset_index(drop=True)
    va_m = va_m.join(bench_df[[BENCHMARK_COL]], how="left")
    va_search_medium = va_m[va_m["era"].isin(eras_search)].copy()
    print(f"  medium va_search: {va_search_medium['era'].nunique()}エラ")

# ============================================================
# モデル定義
# ============================================================
class MLP(nn.Module):
    def __init__(self, in_dim, layers, dropout, bn):
        super().__init__()
        seq = []
        d = in_dim
        for h in layers:
            seq.append(nn.Linear(d, h))
            if bn:
                seq.append(nn.BatchNorm1d(h))
            seq.append(nn.ReLU())
            if dropout > 0:
                seq.append(nn.Dropout(dropout))
            d = h
        seq.append(nn.Linear(d, 1))
        self.net = nn.Sequential(*seq)

    def forward(self, x):
        return self.net(x).squeeze(-1)

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
# 探索ループ
# ============================================================
start_time = time.time()
trials_csv = os.path.join(HERE, "results", "nn_trials.csv")
records = []

for trial in TRIALS_DEF:
    elapsed = time.time() - start_time
    if elapsed > MAX_SEC:
        print(f"時間制限 ({MAX_SEC/3600:.1f}h) に達した。停止。")
        break

    tid = trial["id"]
    layers = trial["layers"]
    dropout = trial["dropout"]
    bn = trial["bn"]
    lr = trial["lr"]
    wd = trial["wd"]
    fs = trial["fs"]
    tgt_col = trial["target"]
    epochs = trial["epochs"]
    batch_size = BATCH_SMALL if fs == "small" else BATCH_MEDIUM

    # データ選択
    if fs == "small":
        tr_data = tr_small
        va_data = va_search_small
        feats = feats_small
    else:
        load_medium_if_needed()
        tr_data = tr_medium
        va_data = va_search_medium
        feats = feats_medium

    if tgt_col not in tr_data.columns:
        print(f"Trial {tid}: {tgt_col} が学習データにない。スキップ。")
        continue

    tr_t = tr_data.dropna(subset=[tgt_col])
    print(f"\n=== Trial {tid}/{MAX_TRIALS}: layers={layers}, drop={dropout}, bn={bn}, "
          f"lr={lr}, wd={wd}, target={tgt_col}, fs={fs} ===")
    t0 = time.time()

    X_tr = tr_t[feats].values.astype(np.float32)
    y_tr = tr_t[tgt_col].values.astype(np.float32)

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_tr)

    dataset = TensorDataset(
        torch.tensor(X_tr, dtype=torch.float32),
        torch.tensor(y_tr, dtype=torch.float32),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    torch.manual_seed(SEED)
    model = MLP(len(feats), layers, dropout, bn).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            criterion(model(xb), yb).backward()
            optimizer.step()

    # 探索用検証
    model.eval()
    X_va = scaler.transform(va_data[feats].values.astype(np.float32))
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
    elapsed_trial = time.time() - t0

    print(f"  CORR: {corr_mean:.4f}±{corr_std:.4f}  BMC: {bmc_mean:.5f}±{bmc_std:.5f}"
          f"  Sharpe: {sharpe:.2f}  時間: {elapsed_trial:.0f}s")

    rec = {
        "datetime": dt.datetime.now().isoformat(),
        "trial_id": tid,
        "layers": str(layers),
        "dropout": dropout,
        "batch_norm": bn,
        "lr": lr,
        "weight_decay": wd,
        "target": tgt_col,
        "feature_set": fs,
        "epochs": epochs,
        "search_eras": len(scores),
        "corr_mean": round(corr_mean, 6),
        "corr_std": round(corr_std, 6),
        "bmc_mean": round(bmc_mean, 6),
        "bmc_std": round(bmc_std, 6),
        "sharpe": round(sharpe, 4),
        "elapsed_sec": round(elapsed_trial, 1),
    }
    records.append(rec)
    pd.DataFrame(records).to_csv(trials_csv, index=False)

    # チェックポイント保存
    torch.save(
        {"model_state": model.state_dict(), "scaler": scaler,
         "feats": feats, "config": trial, "target_col": tgt_col},
        os.path.join(HERE, "models", f"nn_trial_{tid:02d}.pt"),
    )

print(f"\n=== 探索完了: {len(records)}本 ===")
total_elapsed = time.time() - start_time
print(f"合計時間: {total_elapsed/60:.1f}分")

# ============================================================
# ベストモデルの選択
# ============================================================
df_trials = pd.DataFrame(records)
df_trials.to_csv(trials_csv, index=False)

valid = df_trials[df_trials["corr_mean"] >= CORR_MIN].copy()
if len(valid) == 0:
    print(f"警告: CORR 足切り ({CORR_MIN:.4f}) を通過したモデルがない。全試行から選ぶ。")
    valid = df_trials

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
)
best_feats = ckpt["feats"]
best_scaler = ckpt["scaler"]
best_tgt_col = ckpt["target_col"]
best_cfg = ckpt["config"]

torch.manual_seed(SEED)
best_model = MLP(len(best_feats), best_cfg["layers"], best_cfg["dropout"], best_cfg["bn"])
best_model.load_state_dict(ckpt["model_state"])
best_model.eval()

# 取っておく期間の validation データ
if best_cfg["fs"] == "small":
    va_hold_base = va_small[va_small["era"].isin(eras_hold)].copy()
else:
    load_medium_if_needed()
    va_hold_base = va_search_medium  # ここは medium の hold
    va_m_full = pd.read_parquet(
        os.path.join(DATA, "validation.parquet"),
        columns=["era", "data_type", "target"] + feats_medium,
        filters=[("data_type", "==", "validation"), ("era", "not in", emb)],
    )
    va_m_full = va_m_full.dropna(subset=["target"]).reset_index(drop=True)
    va_m_full = va_m_full.join(bench_df[[BENCHMARK_COL]], how="left")
    va_hold_base = va_m_full[va_m_full["era"].isin(eras_hold)].copy()

# target_ender_60 で学習した場合も採点は target で行う
va_hold = va_hold_base.copy()

X_hold = best_scaler.transform(va_hold[best_feats].values.astype(np.float32))
with torch.no_grad():
    pred_nn = best_model(torch.tensor(X_hold, dtype=torch.float32)).numpy()
va_hold["pred_nn"] = pred_nn

# ベースライン LightGBM の予測
bl = pickle.load(open(os.path.join(HERE, "models", "baseline_small.pkl"), "rb"))
bl_model = bl["model"]
bl_feats = bl["features"]

if "pred_bl" not in va_hold.columns:
    if best_cfg["fs"] != "small":
        va_hold_small = va_small[va_small["era"].isin(eras_hold)].copy()
        va_hold_small["pred_bl"] = bl_model.predict(va_hold_small[bl_feats])
        va_hold = va_hold.join(va_hold_small[["pred_bl"]], how="left")
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

# ベストモデルを保存
best_model_path = os.path.join(HERE, "models", f"nn_best_trial{best_id:02d}.pt")
torch.save(ckpt, best_model_path)
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
