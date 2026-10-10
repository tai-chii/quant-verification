# Q267 金曜の最終1時間（NY 16時前）のリターンは週の向きと逆か（週末前の手仕舞い・FX8＋トレンド7 H1）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q267 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Krohn・Mueller・Whelan 2018（FX premia around the clock）、[[Dao2016-1_為替は週末の窓が大きいとその週のうちに逆向きに戻る]]、知見 Q051・Q248。

- スクリプト: `kensho_friday_last_hour_q267.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: FX8＋トレンド7 の H1_dukascopy（2008/2011〜2026-06）。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_friday_last_hour_q267.py`（B=2000・小（B=2000・1 分前後）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q267_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_friday_last_hour_q267.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q267 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 金曜 NY 時刻 15 時台（15:00→16:00・週の最終 1 時間）のリターン r_F は、その週（月曜 0 時 UTC〜金曜 15 時 NY）のリターン r_W と逆符号: E[sign(r_W)·r_F]<0。
- 定義: NY 時刻は America/New_York（夏時間込み）。r_F は金曜の NY 15 時台の足。r_W はその週の月曜最初の足の始値から金曜 15 時 NY の足の始値まで。y=sign(r_W)·r_F [bp]。対照: 金曜以外の 15 時台で同じ y。
- 測るもの: 年×銘柄の y の年単位 t（all15/fx8/trend7）、対照との差。前後半。
- 帰無: sign(r_W) を週で無作為に付け替え B=2000 → y の平均の帰無分布 → z。
- 多重比較: 判定は all15 の前後半 2 本。群別・対照は記述。
- 捨てた案: 約3: 最終 2 時間、ロンドン 16 時台（Krohn の fix と混ざる）、翌週月曜の続き（Q248 と混ざる）。
- 先行研究チェック: WebSearch 2026-10-10「Friday last hour before weekend reversal position squaring FX futures intraday return opposite to weekly return empirical」: Krohn・Mueller・Whelan 2018、Dao ほか 2016（週末の過剰反応）、Bank of Canada SWP 2021-48。 週の向きで条件づけた金曜最終 1 時間を 15 銘柄・前後半・符号付け替え帰無で測る形は未確認（条件の穴）。

## 判定（事前固定）

all15 前後半とも y<0 かつ t≤−2 かつ z≤−2 → 支持。全期間 z>−1 → 棄却。それ以外 → 未確定。

## 結果

未実行。
