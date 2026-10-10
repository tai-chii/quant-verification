# Q272 月曜（週末跨ぎ）のリターン分散は他の曜日の何倍か（取引時間 vs 暦時間・French・Roll 1986・15銘柄）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q272 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: French・Roll 1986（JFE・取引時間仮説）、知見 Q206（曜日効果）・Q212（暗号資産の週末）・Q209（夜間）、Purdue「Day of the Week Effects in Financial Futures」。

- スクリプト: `kensho_weekend_variance_q272.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1（2008〜2026-06）。暗号資産は 24/7 なので対照として BTC は別に書く。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_weekend_variance_q272.py`（B=1000・小（B=1000・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q272_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_weekend_variance_q272.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q272 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 15 銘柄の UTC 日足で、月曜（金曜終値→月曜終値・暦 3 日分）のリターン分散は火〜金の分散の 3 倍ではなく 1.0〜1.3 倍（取引時間仮説）。比 R = Var(月) / Var(火〜金)。
- 定義: R を年×銘柄で推定（年内の分散比）。群別・全期間の中央値。
- 測るもの: R の年×銘柄の対数の平均と年単位 t（log R=0 に対し、log 3 に対し）、群別。前後半。
- 帰無: 曜日ラベルを年内で並べ替え B=1000 → log R の帰無分布（=0 付近）→ z。
- 多重比較: 判定は all15 の 1 本（2 つの帰無値）。群別・BTC は記述。
- 捨てた案: 約3: 祝日跨ぎ（Q239 と混ざる）、H1 の週末跨ぎ足（Q248）、絶対リターン。
- 先行研究チェック: WebSearch 2026-10-10「French Roll 1986 trading time calendar time weekend variance Monday return variance ratio FX gold futures recent evidence」: French・Roll 1986 原論文、Boston Fed WP98-6、Purdue（McConnell）の金融先物の曜日効果、ASU「volatility during trading and nontrading hours」。 CFD 15 銘柄の 2008–2026 で前後半・曜日並べ替え帰無で比を事前固定の判定にかける形は未確認（条件の穴）。

## 判定（事前固定）

all15 で log R の年単位平均が log 1.3 未満かつ log 3 に対し t≤−2 → 支持（取引時間仮説）。log R≥log 2 かつ z≥2 → 棄却（暦時間に近い）。それ以外 → 未確定。

## 結果

未実行。
