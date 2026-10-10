# Q248 トレンド群（金・銀・原油 2・株価指数 2）の週末の窓は週内に埋まるか（Dao 2016 の FX 以外への条件の穴）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q248 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: [[Dao2016-1_為替は週末の窓が大きいとその週のうちに逆向きに戻る]]、[[Dao2016-2_週末の窓の逆張りは期間外の2007年から2014年にコストと金利を引いても残る]]、知見 Q051・Q209・Q212。

- スクリプト: `kensho_weekend_gap_fill_q248.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: XAUUSD・XAGUSD・WTI・UKOIL・US500・USTECH の H1（BTC は週末も動くので除く）（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_weekend_gap_fill_q248.py`（B=2000・1 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q248_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_weekend_gap_fill_q248.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q248 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: g=ln(月曜始値/金曜終値)、rev=−sign(g)×（月曜始値→金曜終値）[bp]。|g| が拡大窓の中央値より大きい週の rev（年単位 t）と埋まった割合。帰無は g の符号の無作為付け替え。コスト後・銘柄別は記述
- 先行研究チェック: WebSearch 2026-10-10「weekend gap fill probability stock index futures gold oil Monday open gap reversal empirical」: Harbourfront Quant・MQL5・TradingView（ブログ）と UJ の論文。Dao の定義で商品・指数 CFD を 2 期間・符号並べ替え帰無は未確認（移植）

## 判定（事前固定）

群で前後半とも |g| 大の rev>0 かつ z≥2 → 支持。全期間 z<2 → 棄却。他は未確定

## 結果

未実行。
