# Q236 4 組（XAU→XAG・WTI→UKOIL・BTC→ETH・US500→USTECH）の H1 リード・ラグは、両方向のどちらが強いか

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q236 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: 知見 Q213（USTECH→BTC は予測しない）、Lo・MacKinlay 1990、Sifat ほか 2019（RIBAF 50・BTC–ETH の時間足・要旨）。

- スクリプト: `kensho_cross_market_leadlag_q236.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 各組の H1（共通時刻）。区切り: 2017（BTC–ETH は 2022）（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_cross_market_leadlag_q236.py`（B=500・2 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q236_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_cross_market_leadlag_q236.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q236 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: 順方向 IC=Spearman(r_lead,t, r_lag,t+1) と逆方向を年ごとに → 年平均・t。帰無は lag 側の循環シフト（≥48 本）。同時相関・lead の符号で lag を 1 時間持つ純損益は記述
- 先行研究チェック: WebSearch 2026-10-10「lead-lag gold silver hourly returns Brent WTI bitcoin ethereum lead lag cross-correlation」: BTC–ETH 2019、為替のリード・ラグ arXiv 1906.10388、暗号資産の価格発見 arXiv 2506.08718。4 組を同じ設計で両方向・前後半は未確認（移植＋条件の穴）

## 判定（事前固定）

組ごと: 順方向 IC>0 かつ前後半 z≥2 かつ逆方向 z<2 → lead→lag。4 組中 3 以上 → 支持、2 → 未確定、1 以下 → 棄却

## 結果

未実行。
