# Q255 ドル因子を除いた残差の順張りは生の順張りより強いか（FX6・Blitz 2011 の残差モメンタムの移植）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q255 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Blitz・Huij・Martens 2011（J. Empirical Finance・残差モメンタム）、知見 Q208（ドル因子の順張りは個別より強くない）、Verdelhan 2018。

- スクリプト: `kensho_residual_momentum_q255.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: FX6（EURUSD・GBPUSD・AUDUSD・USDJPY・USDCHF・USDCAD）D1_fromH1（2008〜2026-06）。ドルが分母の組は符号を反転して「ドルのリターン」にそろえる。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_residual_momentum_q255.py`（B=500・小（B=500・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q255_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_residual_momentum_q255.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q255 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 各通貨の日次リターンから 6 通貨等加重のドル因子への回帰残差（拡大窓・250 日以上）を作り、残差の 60 日累積の符号で売買する残差順張りは、生の TSMOM60 より年×通貨の純損益 [bp/日] が高い。
- 定義: ドル因子 F_t: 6 組の「ドル高が正」のリターンの等加重。β は t 日までの拡大窓（最短 250 日）の OLS。残差 e=r−βF。合図: sign(Σ_{60} e)。建玉は元の通貨の向きに戻す。pnl_bp。
- 測るもの: 年×通貨の純損益差（残差−生）[bp/日]（年単位 t）、合図の一致率、両者のシャープ。前後半 2008–2016／2017–。
- 帰無: 合図とリターンの対応を循環シフト（両規則に同じシフト）B=500 → 差の帰無分布 → z。
- 多重比較: 判定は差の前後半 2 本。合図の一致率・シャープは記述。
- 捨てた案: 約3: 第 2 因子（キャリー・ドル以外）を足す（手元に無い）、12-1 か月の株式型（Q215 で反転が出た型）、クロス円を含める（ドル成分が無い）。
- 先行研究チェック: WebSearch 2026-10-10「residual momentum currencies dollar factor removed idiosyncratic momentum FX Blitz Huij Martens」: Blitz・Huij・Martens 2011（EUR repub）、Quantpedia 136、Alpha Architect「Is currency momentum factor momentum」、AEA 2023「Dissecting currency momentum」。 株式の残差モメンタムは確立。FX6 の日次・ドル因子 1 本・2008–2026 前後半・循環シフト帰無での移植は未確認（移植）。

## 判定（事前固定）

前後半とも 差>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定（残差は害）。それ以外 → 棄却（差は見えない）。

## 結果

未実行。
