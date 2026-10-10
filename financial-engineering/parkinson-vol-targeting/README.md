# Q232 Parkinson レンジボラでのボラ・ターゲティングは終値 σ60 版よりシャープが高いか（Q222 × Q205 の連鎖）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q232 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: 知見 Q222（Parkinson 入力 HAR は QLIKE を下げる）、知見 Q205（σ60 逆数・CAP=4 でシャープ +0.09）、Parkinson 1980、Harvey ほか 2018。

- スクリプト: `kensho_parkinson_vol_targeting_q232.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15 銘柄 D1_fromH1（高値・安値）（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_parkinson_vol_targeting_q232.py`（B=300・1 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q232_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_parkinson_vol_targeting_q232.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q232 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: w=min(4, σ_target/σ̂)（σ_target=10%/√252）の σ̂ を終値 60 日 std（CC）と Parkinson 60 日（PK）で作り、TSMOM60 の年×銘柄シャープの対応ありの差 PK−CC（年単位 t）。帰無は日次 PK 分散の年内並べ替え
- 先行研究チェック: WebSearch 2026-10-10「volatility targeting range-based Parkinson estimator trend following Sharpe improvement」: レンジ推定量の性質の論文のみ。ボラ・ターゲティングの入力を替えて対応ありで比べた研究は未確認（連鎖）

## 判定（事前固定）

all15 前後半とも 差>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定。他は棄却

## 結果

未実行。
