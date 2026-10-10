# Q278 前後半の分割年を 2014〜2020 で動かすと「前後半とも同符号 t≥2」の判定は何割割れるか（基盤・簡単な規則群）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q278 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Hansen・Timmermann 2012（EUI・分割点の選択）、Rossi・Inoue 2012、知見 Q146（B の安定）・Q175（クラスタ t）・Q154（WRC/SPA の割れ）。

- スクリプト: `kensho_split_year_q278.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1（2008〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_split_year_q278.py`（B=300・中（B=300×75 セル×7 分割・2〜3 分）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q278_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_split_year_q278.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q278 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 15 銘柄 × 規則 5 本（TSMOM20・60・120・SMA200・RSI14 逆張り）= 75 セルで、「前後半とも同符号かつ両方 t≥2」の判定が分割年 2014〜2020 の 7 通りのうち一致しない（判定が割れる）セルの割合は、年内並べ替えの帰無で出る割合と同程度（基盤の決まりの妥当性）。
- 定義: セルごとに純損益の年×銘柄 t を分割年ごとに計算。判定: 支持（両方 t≥2 同符号）／棄却／他。割れ = 7 通りの判定が全部同じでない。
- 測るもの: 割れる割合 F（観測）、帰無の F 分布、支持になる分割年の数の分布。
- 帰無: リターンを年内で並べ替え B=300 → 同じ手順で F → 帰無分布 → z。
- 多重比較: 判定は F の 1 本。75 セルは判定の材料で個別には検定しない。
- 捨てた案: 約3: 分割を 3 期に増やす、t の閾値 1.5（2 に固定）、WRC を各分割で（重い）。
- 先行研究チェック: WebSearch 2026-10-10「sample split point sensitivity in-sample out-of-sample split date choice anomaly robustness backtest multiple splits」: Hansen・Timmermann「Choice of Sample Split in Out-of-Sample Forecast Evaluation」（EUI 2012）、Rossi・Inoue、Coventry／Tilburg「Out-of-sample equity premium predictability and sample split–invariant inference」。 予測評価の分割点理論は確立。自前の『前後半とも t≥2』判定を 7 分割で割れ率として帰無と比べる形は未確認（基盤）。

## 判定（事前固定）

観測 F が帰無の 95 点以下 → 支持（分割依存は偽陽性の水準を超えない）。95 点超 → 棄却（分割年に依存する。どの規則かを書く）。帰無の F が 0 近くで比較不能 → 未確定。

## 結果

未実行。
