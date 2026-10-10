# Q256 クロス・シグナル（金→銀・WTI→UKOIL・US500→USTECH・BTC→ETH）の日足順張りは自身の合図より良いか

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q256 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: 知見 Q236（4 組の H1 リード・ラグ）、Quantpedia「Cross-Asset Price-Based Regimes for Gold」（要旨）、Moskowitz 2012。

- スクリプト: `kensho_cross_signal_q256.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: XAUUSD・XAGUSD・WTI・UKOIL・US500・USTECH D1_fromH1、BTCUSD D1_fromH1、ETHUSD は H1 → h1_to_d1（2017〜2026）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_cross_signal_q256.py`（B=500・小（B=500・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q256_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_cross_signal_q256.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q256 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 従（銀・UKOIL・USTECH・ETH）を主（金・WTI・US500・BTC）の TSMOM60 の合図で売買するクロス順張りは、従自身の合図の順張りと純損益 [bp/日] が変わらない（主はリードしない）。差 D=クロス−自身。
- 定義: 主の合図は主の終値（同じ UTC 日）で作り、従の翌日のリターンに当てる。自身の合図は従の TSMOM60。pnl_bp（ETH のコストは CRYPTO_COST_RT_REL）。
- 測るもの: 4 組それぞれ年単位の D [bp/日] と t、4 組を束ねた年単位 t。合図の一致率。前後半（BTC→ETH は 2021 で分ける）。
- 帰無: 主の合図を従のリターンに対し循環シフト B=500 → D の帰無分布 → z（組ごと・Holm 4 本）。
- 多重比較: 判定は 4 組 × 前後半 = 8 本（Holm は組の 4 本）。束ねた t・一致率は記述。
- 捨てた案: 約3: 逆向き（従→主）も同時に測る（Q236 が H1 で済み）、両方の合図の AND、参照日数 20。
- 先行研究チェック: WebSearch 2026-10-10「cross-asset signal gold momentum signal applied to silver lead-lag trading rule daily empirical」: Quantpedia「Cross-Asset Price-Based Regimes for Gold」、DeFi Trading Substack の商品リード・ラグ（ブログ）。 4 組の日足・主の合図を従に当てる形で 2 期間・循環シフト帰無・Holm は未確認（連鎖）。

## 判定（事前固定）

4 組のうち Holm 後に前後半とも D>0 かつ z≥2 の組が 1 つ以上 → 支持（その組を書く）。4 組とも全期間 |z|<2 → 棄却（主はリードしない）。それ以外 → 未確定。

## 結果

未実行。
