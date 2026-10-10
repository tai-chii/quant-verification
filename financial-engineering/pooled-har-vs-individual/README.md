# Q274 15銘柄をプールしたパネル HAR は銘柄別 HAR より翌日の QLIKE を下げるか

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q274 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Bollerslev・Hood・Huss・Pedersen 2018（RFS・Risk Everywhere・パネル HAR）、Corsi 2009、知見 Q222（Parkinson HAR）・Q187。

- スクリプト: `kensho_pooled_har_q274.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1（2008〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_pooled_har_q274.py`（B=2000・小（B=2000・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q274_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_pooled_har_q274.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q274 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 対数 Parkinson 分散の HAR（1・5・22 日）を 15 銘柄でプール（係数共通・銘柄固定効果）して推定すると、銘柄別推定より翌日の QLIKE が低い（係数の推定誤差が減る）。
- 定義: 年ごとのウォークフォワード（前年までの拡大窓・最短 500 日で推定し翌年を予測）。A: 銘柄別 OLS。B: プール OLS（固定効果）。予測は exp(log 予測)（補正なし・両者同じ）。
- 測るもの: 年×銘柄の QLIKE 差 B−A（対応あり・年単位 t・all15/fx8/trend7）。前後半。
- 帰無: 差の符号を年×銘柄で無作為に反転（符号並べ替え）B=2000 → z。
- 多重比較: 判定は all15 の前後半 2 本。群別は記述。
- 捨てた案: 約3: 群別プール（fx8・trend7 で別々）、縮小推定（プールと個別の中間）、5 日先。
- 先行研究チェック: WebSearch 2026-10-10「pooled panel HAR model versus individual asset HAR realized volatility forecasting QLIKE cross-asset」: Bollerslev ほか 2018「Risk Everywhere」、arXiv 2406.08041「HARd to Beat」、METU「Forecasting volatility with HAR-RV: commodities, currencies, equities」。 Risk Everywhere は先物の高頻度 RV。手元 CFD 15 銘柄・Parkinson・年次ウォークフォワード・符号並べ替え帰無は未確認（追試＋移植）。

## 判定（事前固定）

all15 前後半とも QLIKE 差<0 かつ t≤−2 かつ z≤−2 → 支持。前後半とも t≥2 → 逆向きで確定（プールは害）。それ以外 → 棄却（差は見えない）。

## 結果

未実行。
