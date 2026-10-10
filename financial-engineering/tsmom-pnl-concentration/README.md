# Q230 順張りの純損益は上位 1% の日に集中しているか: 最大の k 日を除くと年単位の t が 2 を切るか（15 銘柄 D1）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q230 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: [[Feng2026-2_標本外でアルファが弱まる原因は偽の発見と裁定と構造変化]]、知見 Q143・Q144、Hurst・Ooi・Pedersen 2017。

- スクリプト: `kensho_tsmom_pnl_concentration_q230.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15 銘柄 D1_fromH1（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_tsmom_pnl_concentration_q230.py`（B=300・1 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q230_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_tsmom_pnl_concentration_q230.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q230 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: TSMOM60 の日次純損益から銘柄ごとに上位 k%（1・2・5）の日を除いた年単位の t（t_trim）と、集中度 C1（上位 1% の日の純損益÷正の日の合計）。帰無は循環シフト
- 先行研究チェック: WebSearch 2026-10-10「trend following profits concentrated few days removing best days time series momentum」: 買い持ちの「最良の日を除く」議論ばかり。順張りの日次純損益で帰無と比べる形は未確認（条件の穴）

## 判定（事前固定）

all15 前後半とも t_full≥2 かつ t_trim1<2 → 支持（集中）。前後半とも t_trim1≥2 → 棄却。t_full<2 の期間あり → 未確定

## 結果

未実行。
