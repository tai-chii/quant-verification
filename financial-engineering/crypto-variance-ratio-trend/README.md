# Q264 暗号資産11通貨の H1 の分散比は 2022 年以降に 1 へ近づいたか（適応的市場仮説の移植）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q264 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Lo・MacKinlay 1988（分散比）、[[Alahmadi・Basingab2026-3_設定の選び方が弱形効率性検定の結論に実質的に効く]]、知見 Q148・Q149、Tehran／ASE の AMH 論文（要旨）。

- スクリプト: `kensho_crypto_vr_trend_q264.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 暗号資産 11 通貨 H1_dukascopy（2017/2018〜2026-09）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_crypto_vr_trend_q264.py`（B=2000・小（B=2000・30 秒）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q264_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_crypto_vr_trend_q264.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q264 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 各通貨・暦年の H1 対数リターンの分散比 VR(q=24)（1 日）の |VR−1| は 2022 以降の年で 2018–2021 より小さい（効率化）。
- 定義: VR(q)=Var(q 時間リターン)/(q·Var(1 時間リターン))（重なり窓・Lo-MacKinlay の不均一分散に頑健な z は記述）。年×通貨の |VR−1|。
- 測るもの: D = mean|VR−1|(2022–) − mean|VR−1|(〜2021)（通貨を束ねて年単位 t）。q=6・168 は副次。
- 帰無: 年ラベルを通貨内で並べ替え（前後を壊す）B=2000 → D の帰無分布 → z。
- 多重比較: 判定は q=24 の D 1 本。q=6・168 は記述。
- 捨てた案: 約3: Hurst 指数（Q169 系で済み）、rolling 窓（暦年で固定）、符号つき VR の平均（|VR−1| に統一）。
- 先行研究チェック: WebSearch 2026-10-10「cryptocurrency market efficiency variance ratio test over time improving efficiency 2022 2023 hourly altcoins」: Tehran IJMS「Adaptive Market Hypothesis: Evidence From the Cryptocurrency Market」、RFB 2024「Evolving Efficiency of Cryptocurrency Market」、Springer 章。 多くは日次・BTC/ETH 中心。11 通貨 H1・暦年・2022 分割・年ラベル並べ替え帰無は未確認（移植＋条件の穴）。

## 判定（事前固定）

D<0 かつ t≤−2 かつ z≤−2 → 支持（1 に近づいた）。D>0 かつ z≥2 → 逆向きで確定（遠ざかった）。それ以外 → 棄却（変化は見えない）。

## 結果

未実行。
