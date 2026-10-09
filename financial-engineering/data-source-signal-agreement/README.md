# Q137 データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか

事前登録: `/tmp/claude-0/specs20.py` の Q137（Fable 2026-10-09）＝ `検証/学問/金融工学/知識/文献/アイデア候補.md` の行。出典は Korzan (2026) §5.1（Nasdaq の価格で合図を作り直すと一致 49.51%・不合格）と FX改善ログ 2026-07-14（XAUUSD の yahoo 差は先物ベーシス）。

- スクリプト: `kensho_data_source_signal_agreement_q137.py`（自己完結・決定的・乱数なし。冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: `検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv` と `data_<SYM>_D1_yahoo.csv`（EURUSD GBPUSD AUDUSD USDJPY EURJPY GBPJPY XAUUSD のうち両方あるもの。無い銘柄は除いて `missing` に件数を書く）。共通の日付だけ使う
- 実行: `python3 kensho_data_source_signal_agreement_q137.py`（数秒。帰無なし。`--B` は互換のためだけで未使用）
- 試走: 経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q137_result_<日時>.json`（設定・銘柄ごとの一致率・年差の t・終値差の分布・機械判定）、`results/Q137_table_<日時>.csv`（銘柄×合図の表）、棒グラフ PNG（matplotlib があれば）

## 状態（2026-10-09）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_data_source_signal_agreement_q137.py` を Mac で実行（パスは NFC/NFD 両対応）。本番の見込み時間: 数秒〜10 秒（smoke 3 秒）。
3. JSON の `judgement` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く。特に:
   - 判定は XAUUSD を除く銘柄で付ける。XAUUSD は `results['XAUUSD']` で別枠に記述（終値差の平均 bp が先物ベーシスの大きさ）。
   - `self_lag1_agree_rate`（同じソースで 1 日ずらした自己一致率）と並べ、ソースの違いが「1 日の遅れ」よりどれだけ小さい／大きいかを書く。
   - 前半/後半の一致率・t（`agree_rate_前半` など）は記述。多重比較: 銘柄 ≤6 × 合図 2 の t。
   - Yahoo の日付規約（NY 終値を当日日付で持つか）は共通日付の厳密一致で扱っている。一致率が低く出たら、終値差の分布（`close_diff_bp`）で「日付のずれ」か「値の差」かを切り分けて記述する。
4. 記録先: 知見ノート、主張カード（Korzan2026 の `自分の検証`）、アイデア候補の状態、FX改善ログ、検証キュー Q137 を完了へ。

## 方法（要点）

- 合図 2 本固定: (i) SMA200 の上下、(ii) TSMOM20（20 日リターンの符号）。共通日付の系列で各ソースから作る。
- 一致率 = 両方の合図が定義される日のうち同じ値の日の割合。参考に 1 日ずらした自己一致率。
- 純損益 = 翌日のポジション × 翌日リターン（bp）− ポジション変化 × 片道コスト（段階1の保守値 `COST_RT` の半分）。差 Δ = Dukascopy − Yahoo を年ごとに平均し、年を単位に t。
- 終値差 = (Yahoo/Dukascopy − 1) × 1e4 bp の分布（平均・中央値・SD・5/95%・|差|の平均）。
- 帰無は不要（記述の問い）。

## 判定（事前固定）

- XAUUSD を除く全銘柄・両合図で 一致率 ≥ 99% かつ 年差の |t| < 2 →「データ源は結論を変えない」。
- 1 銘柄でも一致率 < 95%（どちらかの合図）→「データ源は規則の定義の一部」（Korzan と同じ）。
- 間 → 未確定。XAUUSD は別枠で記述。

## 結果（2026-10-09 Opus 実行・判定）

- 本番: `検証/verification-lab/financial-engineering/data-source-signal-agreement/results/Q137_result_20261009_075431.json`（`Q137_table_20261009_075431.csv`・`Q137_bars_20261009_075431.png`）。XAUUSD は `data_XAUUSD_D1_yahoo.csv` が無く除外（6銘柄で判定）。
- **機械判定: 「データ源は規則の定義の一部（Korzan と同じ）」→ 確定。** TSMOM20 の一致率 94.00〜95.37%（4銘柄が <95%）、SMA200 は 97.55〜98.56%。純損益の年差は 12 本とも |t|≤1.26。
- 補足診断（事後・判定外）: `q137_yahoo_close_diagnosis.py` → `検証/verification-lab/financial-engineering/data-source-signal-agreement/results/Q137_diag_20261009_075657.json`。Yahoo 為替日足は |終値−始値| 中央値 0.3〜0.9bp（高安幅 54〜73bp）＝終値は実は日の始めの値。Dukascopy の UTC 終値と 10bp 以内で合うのは約 2/3 の日、残り約 1/3 は1日ずれた時刻に近い。時刻が合う日の差は中央値 約2bp。
- 知見: [[_基盤/知識/知見/Yahooの為替日足の終値は実は日の始めの値で日付も約3分の1ずれ、順張りの合図は5〜6パーセントの日でDukascopyと食い違う|知見（Q137）]]
