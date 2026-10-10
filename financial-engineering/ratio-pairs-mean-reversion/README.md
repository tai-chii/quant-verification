# Q233 金銀比・Brent−WTI の z スコア逆張り（ペアトレード）は 2015 年以降コスト後に残るか

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q233 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: Gatev・Goetzmann・Rouwenhorst 2006（要旨）、`pair-trading/`（手元）、知見 Q042。

- スクリプト: `kensho_ratio_pairs_q233.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: D1_fromH1: (XAUUSD, XAGUSD) 2008〜、(UKOIL, WTI) 2011-09〜（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_ratio_pairs_q233.py`（B=300・30 秒。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q233_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_ratio_pairs_q233.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q233 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: 対数比の 60 日 z が ±2 で比の縮小に賭け |z|<0.5 で手仕舞い。組の純損益（両脚のコスト込み）の年単位 t・シャープ・切替回数・半減期。帰無は建玉列の循環シフト（≥252 日）
- 先行研究チェック: WebSearch 2026-10-10「gold silver ratio mean reversion pairs trading z-score backtest transaction costs Brent WTI spread」: ブログ・TradingView・QuantConnect のみ（根拠にしない）。前後半＋循環シフト帰無＋コスト込みは未確認（条件の穴）

## 判定（事前固定）

組ごとに前後半とも 純損益>0・t≥2・z≥2 → 残る。2 組とも残る → 支持、1 組 → 未確定、0 → 棄却

## 結果

未実行。
