# Q241 原油→USDCAD・金→AUDUSD の日次リード・ラグは、両方向のどちらが強いか（Chen・Rogoff・Rossi 2010 の逆向き）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q241 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: Chen・Rogoff・Rossi 2010（QJE 125・NBER w13901 要旨）、Bork ほか 2023（再検討）、知見 Q208・Q213。

- スクリプト: `kensho_commodity_currency_leadlag_q241.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: D1_fromH1: (WTI, USDCAD) 2011-09〜、(XAUUSD, AUDUSD) 2008〜（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_commodity_currency_leadlag_q241.py`（B=1000・1 分。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q241_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_commodity_currency_leadlag_q241.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q241 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: 符号をそろえた為替（CAD 高・AUD 高を正）と商品の日次リターンで、為替→商品と商品→為替の年ごとの Spearman IC → 年平均・t。帰無は商品側の循環シフト（≥30 日）。同時相関と 1 日持つ純損益は記述
- 先行研究チェック: WebSearch 2026-10-10「commodity currencies predict commodity prices daily oil CAD gold AUD lead lag Chen Rogoff Rossi」: 原論文（四半期）と Bork ほか 2023。日次 Dukascopy・循環シフト・前後半・両方向は未確認（条件の穴）

## 判定（事前固定）

組ごと: 為替→商品 IC>0 かつ前後半 z≥2 かつ逆 z<2 → 為替が商品を予測（逆なら商品が為替を予測）。2 組同じ向き → 確定、割れ → 未確定、2 組とも無し → 棄却

## 結果

未実行。
