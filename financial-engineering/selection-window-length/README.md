# Q244 参照日数の選択窓の長さ（1・2・3・5・8 年）で、順張りの標本外純損益は変わるか（15 銘柄）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q244 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: 知見 Q177（選び直す頻度）・Q188（台地選択）・Q139（候補数 J）・Q141・Q155、Pesaran・Timmermann 2007（未読）。

- スクリプト: `kensho_selection_window_length_q244.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15 銘柄 D1_fromH1（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_selection_window_length_q244.py`（B=300・1 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q244_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_selection_window_length_q244.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q244 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: L∈{5..300} から直前 W 年の平均純損益で最良を選び翌年の純損益を標本外に。W=8 が取れるセルだけを全 W で共通に使う。W の 5 点と群平均の Spearman、W=8−W=1 の年単位 t。参照にランダム L（B=300）。区切りはテスト年 2021
- 先行研究チェック: WebSearch 2026-10-10「lookback window length parameter selection out-of-sample trend following estimation window 1 year vs 10 years」: Inoue・Jin・Rossi（UPF）、arXiv 2609.29887、Quantpedia。窓の長さだけを 5 水準で対応あり＋ランダム L 帰無は未確認（条件の穴）

## 判定（事前固定）

all15 前後半とも Spearman≥0.9 かつ t≥2 → 支持（長いほど良い）。≤−0.9 かつ t≤−2 → 逆向きで確定。他は棄却（窓では変わらない）

## 結果

未実行。
