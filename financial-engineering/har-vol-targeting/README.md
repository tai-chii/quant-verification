# Q259 HAR 予測の分散でのボラ・ターゲティングは σ60 版よりシャープが高いか（Q222×Q205 の連鎖）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q259 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Corsi 2009（HAR）、Harvey ほか 2018（ボラ・ターゲティング）、知見 Q205（σ60 でシャープ +0.09）・Q222（Parkinson HAR）・Q232。

- スクリプト: `kensho_har_vol_targeting_q259.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1（2008〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_har_vol_targeting_q259.py`（B=300・小（B=300・1〜2 分）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q259_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_har_vol_targeting_q259.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q259 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 規模 = 目標σ／予測σ の予測σに、HAR（1・5・22 日の対数 Parkinson 分散・拡大窓で年ごとに再推定）の 1 日先予測を使うと、σ60（終値の 60 日標準偏差）より年×銘柄のシャープが高い。
- 定義: A: σ60 版（Q205 と同じ）。B: HAR 版（係数は前年までの拡大窓 OLS・最短 500 日・予測は exp(log 予測)）。目標σ=年率 10%。順張りは TSMOM60。pnl_bp を規模倍。
- 測るもの: 年×銘柄のシャープ差 B−A（対応あり・年単位 t）、純損益差、規模の変動係数。前後半・群別。
- 帰無: HAR 予測を年内で循環シフト（予測の分布を保ち時点との対応を壊す）B=300 → シャープ差の帰無分布 → z。
- 多重比較: 判定は all15 のシャープ差の前後半 2 本。純損益・群別は記述。
- 捨てた案: 約3: 5 日先予測で規模を週次更新、GARCH 版（HAR に統一）、目標σを年ごとに合わせ込む（Q030 と混ざる）。
- 先行研究チェック: WebSearch 2026-10-10「volatility targeting using HAR-RV forecast versus trailing realized volatility Sharpe improvement」: Alpha Architect「Volatility targeting improves risk-adjusted returns」、Macrosynergy「The point of volatility targeting」、arXiv 2604.02743（オプション情報の RV 予測）。 HAR 予測を規模に使ったときの差を 15 銘柄・前後半・循環シフト帰無で測る形は未確認（連鎖）。

## 判定（事前固定）

all15 前後半とも シャープ差>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定。それ以外 → 棄却（差は見えない）。

## 結果

未実行。
