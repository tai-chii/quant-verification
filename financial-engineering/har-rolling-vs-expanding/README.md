# Q276 HAR の係数を 2 年の rolling で推定し直すと拡大窓より QLIKE は下がるか（15銘柄）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q276 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Zhang・Wang ほか 2024（J. Forecasting・rolling か expanding か両方か）、arXiv 2406.08041「HARd to Beat」（rolling 窓の影響）、知見 Q222・Q274。

- スクリプト: `kensho_har_rolling_q276.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1（2008〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_har_rolling_q276.py`（B=2000・中（毎日再推定×15 銘柄・3〜5 分）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q276_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_har_rolling_q276.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q276 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: HAR（対数 Parkinson 分散・1・5・22 日）の係数を直近 500 日の rolling で推定すると、拡大窓（最短 500 日）より翌日の QLIKE が低い（係数の時変に追従）。
- 定義: 毎日再推定（両者）。A: 拡大窓。B: rolling 500 日。C: 両者の平均（副次・Zhang 2024 の型）。
- 測るもの: 年×銘柄の QLIKE 差 B−A（対応あり・年単位 t・all15）、C−A。前後半。
- 帰無: 差の符号を年×銘柄で無作為に反転 B=2000 → z。
- 多重比較: 判定は all15 の B−A の前後半 2 本。C は記述。
- 捨てた案: 約3: rolling 250 日（500 に固定）、年ごとの再推定（毎日に統一）、Parkinson 以外。
- 先行研究チェック: WebSearch 2026-10-10「HAR model rolling window versus expanding window estimation forecast accuracy parameter instability realized volatility」: J. Forecasting 2024「Out-of-sample volatility prediction: Rolling window, expanding window, or both?」、SFI N°24-70「HARd to Beat」、arXiv 1910.08202。 CFD 15 銘柄・Parkinson・毎日再推定・前後半・符号並べ替え帰無での判定は未確認（追試）。

## 判定（事前固定）

all15 前後半とも B−A<0 かつ t≤−2 かつ z≤−2 → 支持（rolling が良い）。前後半とも t≥2 → 逆向きで確定（拡大窓が良い）。それ以外 → 棄却（差は見えない）。

## 結果

未実行。
