# Q270 株価指数・金の夜間→日中の逆張りはコスト後に残るか（DellaCorte 2015 の指数・金への移植・H1）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q270 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: [[DellaCorte2015-1_夜間リターンで作る逆張りは米国株で従来の短期リバーサルの約5倍の収益だった]]、[[DellaCorte2015-2_従来の短期リバーサルが効かない通貨先物でも夜間から日中への逆張りは有意だった]]、知見 Q173（FX は残らない）・Q209（夜間プレミアム）。

- スクリプト: `kensho_overnight_reversal_idx_q270.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: US500・USTECH・XAUUSD H1_dukascopy（2011-09〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_overnight_reversal_idx_q270.py`（B=2000・小（B=2000・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q270_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_overnight_reversal_idx_q270.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q270 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: US500・USTECH・XAUUSD の H1 で、夜間（NY 16 時→翌 9 時 30 分の足まで）のリターンの逆符号で日中（NY 9 時台→16 時）を売買すると、コスト後の純損益 [bp/日] は正。
- 定義: NY 時刻。夜間 r_N: 前日 16 時の足の終値 → 当日 9 時台の足の始値。日中 r_D: 9 時台の始値 → 16 時台の足の始値。pos=−sign(r_N)。純損益 = pos·r_D·1e4 − 往復コスト [bp]。
- 測るもの: 年×銘柄の純損益の年単位 t（3 銘柄束・個別）、粗利の t。前後半 2012–2016／2017–。
- 帰無: sign(r_N) を日で無作為に付け替え B=2000 → z。
- 多重比較: 判定は束の前後半 2 本。個別は記述。
- 捨てた案: 約3: FX（Q173 で済み）、夜間の分散で条件づけ（DellaCorte-3・Q174 で済み）、日次の D1 だけで作る（始値が夜間を含む）。
- 先行研究チェック: WebSearch 2026-10-10「overnight return reversal intraday stock index futures gold overnight-to-intraday reversal strategy empirical」: CXO「Overnight/Intraday Return Reversal Trading」、QuantReturns「Overnight Mean-Reversion」（ブログ）、arXiv 2507.04481（夜間ニュース）。 指数 CFD・金の H1 で 2012–2026 前後半・コスト込み・符号付け替え帰無の判定は未確認（移植）。

## 判定（事前固定）

3 銘柄束で前後半とも 純損益>0 かつ t≥2 かつ z≥2 → 支持。全期間 粗利の z<2 → 棄却（信号がない）。それ以外 → 未確定（粗利は有るがコストで消える等を書く）。

## 結果

未実行。
