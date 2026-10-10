# Q277 リスクオフ日（US500 下位 5%）の金・円・フラン・豪ドルのベータは前後半で安定か（安全資産の役割）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q277 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Ranaldo・Söderlind 2010（Review of Finance・安全資産通貨）、Baur・Lucey 2010（金）、RIETI DP 19-E-048、知見 Q241・Q236。

- スクリプト: `kensho_safe_haven_beta_q277.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: US500・XAUUSD・USDJPY・USDCHF・AUDUSD D1_fromH1（2011-09〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_safe_haven_beta_q277.py`（B=1000・小（B=1000・30 秒）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q277_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_safe_haven_beta_q277.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q277 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: US500 の日次リターンが拡大窓の下位 5% の日（リスクオフ日）に、XAUUSD・USDJPY・USDCHF・AUDUSD の同日リターンを US500 のリターンに回帰したベータ β_off は、前半 2012–2016 と後半 2017–2026 で符号が同じで差が 2se 未満（役割は安定）。
- 定義: リスクオフ日: t−1 までの拡大窓（最短 250 日）の 5% 分位以下。β_off を前後半で OLS（HC1 の se）。β_normal（それ以外の日）も記述。
- 測るもの: 4 銘柄の β_off（前後半）と差の z=(β_post−β_pre)/√(se²+se²)。Holm 4 本。
- 帰無: リスクオフ日ラベルを年内で並べ替え B=1000 → β_off の帰無分布（通常日との差）→ z（記述）。
- 多重比較: 差の検定 4 本を Holm で補正。並べ替え z は記述。
- 捨てた案: 約3: VIX 条件（無い）、H1 の同時相関、EURCHF（手元に無い）。
- 先行研究チェック: WebSearch 2026-10-10「safe haven gold yen Swiss franc beta to equity market crash days stability over time 2008-2024 empirical」: RIETI DP 19-E-048、Financial Innovation 2024、CEPR DP7249（Ranaldo・Söderlind）、EMU の安全資産論文。 4 銘柄 CFD の下位 5% 条件つきベータの前後半差を Holm・年内並べ替えで判定する形は未確認（条件の穴）。

## 判定（事前固定）

4 銘柄とも 前後半で β_off 同符号かつ Holm 後の差 |z|<2 → 支持（安定）。1 つ以上で符号が逆または Holm 後 |z|≥2 → 棄却（どの銘柄が変わったかを書く）。前後半のどちらかで β_off が 0 と区別できない銘柄がある → 未確定。

## 結果

未実行。
