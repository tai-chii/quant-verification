# Q237 終値位置 CLV が極端な日の翌日は、続くか反転するか（15 銘柄・Holm）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q237 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: 知見 Q030（大きな実体の H1 の続きは見えない）・Q216・Q215、TTR の CLV（Chaikin A/D の部品）。

- スクリプト: `kensho_close_location_q237.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15 銘柄 D1_fromH1（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_close_location_q237.py`（B=500・1 分前後。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q237_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_close_location_q237.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q237 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: CLV=(C−L)/(H−L) が ≥0.9／≤0.1 の日の翌日リターンを引けの向きで符号づけした cont [bp]。all15 前後半の年単位 t と z（翌日リターンの（銘柄, 年）内並べ替え）。銘柄別 z と Holm（15 本）・対照（極端でない日の sign(C−O)）・コスト後は記述
- 先行研究チェック: WebSearch 2026-10-10「close location value (close-low)/(high-low) next day return predictability daily bars」: CXO Advisory（SPY のみ・ブログ）と指標の説明のみ。15 銘柄・Holm・前後半は未確認（条件の穴）

## 判定（事前固定）

all15 前後半とも cont>0 かつ z≥2 → 支持（継続）。前後半とも cont<0 かつ z≤−2 → 反転で確定。他は棄却

## 結果

未実行。
