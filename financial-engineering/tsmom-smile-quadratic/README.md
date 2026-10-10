# Q257 順張り束の月次損益は US500 月次リターンの 2 次関数（スマイル）か（Fung・Hsieh 2001／Moskowitz 2012 の型）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q257 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Fung・Hsieh 2001（RFS・トレンドフォロワーの lookback straddle）、Moskowitz・Ooi・Pedersen 2012 図（TSMOM smile）、知見 Q207・Q224（危機アルファは再現しない）。

- スクリプト: `kensho_tsmom_smile_q257.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1 → 月次。US500 D1_fromH1 → 月次リターン（2011-09〜）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_tsmom_smile_q257.py`（B=2000・小（B=2000・30 秒）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q257_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_tsmom_smile_q257.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q257 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 15 銘柄等加重の TSMOM60 束の月次純損益 y を US500 の月次リターン x に y=a+bx+cx² で回帰すると c>0（スマイル）。
- 定義: 束の月次純損益: 各銘柄 pnl_bp を σ60 で規模調整（Q205 型）し等加重した日次の月内和。x: ln(US500 月末/前月末)。OLS（Newey-West 3 か月）。
- 測るもの: c の NW t、c の符号、|x|>5% の月の平均 y と |x|≤5% の月の平均 y の差。前半 2011–2016／後半 2017–／全期間。
- 帰無: 月次 y を月ブロックで並べ替え（x との対応を壊す）B=2000 → c の帰無分布 → z。
- 多重比較: 判定は全期間 c の 1 本（前後半の符号は条件）。裾の月の差は記述。
- 捨てた案: 約3: 参照日数 1/3/12 か月の合成（Q224 で済み）、週次の回帰（点が少ない）、US500 以外の x（ドル・金）。
- 先行研究チェック: WebSearch 2026-10-10「time series momentum smile quadratic equity market return option-like payoff Moskowitz Fung Hsieh lookback straddle」: arXiv 2607.19497「The Science and Practice of Trend-Following Systems」、Columbia（djk 2019）、UCD WP19-06。 原典は先物の長期。手元 CFD 15 銘柄・2011–2026・月ブロック帰無で c の有意性を事前固定で測る形は未確認（追試＋条件の穴）。

## 判定（事前固定）

全期間 c>0 かつ NW t≥2 かつ z≥2、かつ前後半とも c>0 → 支持（スマイル）。全期間 z<1 → 棄却。それ以外 → 未確定。

## 結果

未実行。
