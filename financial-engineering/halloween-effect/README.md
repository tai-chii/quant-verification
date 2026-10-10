# Q238 「5 月に売れ」（ハロウィン効果）は 2008〜2026 の指数・商品 6 銘柄で残るか（6 か月ブロックの循環シフト帰無）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q238 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: Bouman・Jacobsen 2002（AER）、Jacobsen・Zhang「The Halloween Indicator, Everywhere and All the Time」（SSRN・要旨）、知見 Q206・Q181。

- スクリプト: `kensho_halloween_q238.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: SPX・NDX・XAUUSD・XAGUSD・WTI（long_yahoo 2008〜2026-07）＋ US500 D1_fromH1。BTC は記述（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_halloween_q238.py`（B=2000・30 秒。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q238_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_halloween_q238.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q238 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: 冬（11〜4 月）− 夏（5〜10 月）の 6 か月リターンの差 D を季節年ごとに対にし、6 銘柄の群平均の年単位 t。帰無は日次リターンの循環シフト（≥126 日）。季節 18 対で検出力は低い
- 先行研究チェック: WebSearch 2026-10-10「Halloween effect sell in May S&P 500 still exists after 2000 Zhang Jacobsen 2021 out-of-sample」: Jacobsen・Zhang は残ると主張、CXO は 3 世紀の整理。2008〜2026・循環シフト帰無・指数と商品を同じ設計は未確認（追試・公表後）

## 判定（事前固定）

群平均 D>0 かつ前後半とも z≥2 → 支持。全期間 z<2 → 棄却。他は未確定

## 結果

未実行。
