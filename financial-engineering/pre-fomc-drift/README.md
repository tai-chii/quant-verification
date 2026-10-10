# Q243 FOMC 前日ドリフトは US500 H1 で 2015 年以降も残るか（Lucca・Moench 2015／Kurov ほか 2021 の追試）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q243 の行（Fable 2026-10-10・20案一括生成 第4弾）。出典: Lucca・Moench 2015（JF 70）、Kurov・Wolfe・Gilbert 2021（FRL 40・「消えた」）、知見 Q219・Q056。

- スクリプト: `kensho_pre_fomc_drift_q243.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: US500 H1（2011-09〜2026-06）。FOMC 定例会合の発表日 2012〜2026 はスクリプトに Fable の知識から記載（**実行者は federalreserve.gov と照合し、違えば `--fomc_csv` で差し替える**）（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_pre_fomc_drift_q243.py`（B=2000・30 秒。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q243_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_pre_fomc_drift_q243.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q243 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 測るもの: 米東部 14:00 で終わる足の終値の前日比（発表前 24 時間）[bp] を FOMC 日と他の日で比べる。帰無は他の日から同数を無作為抽出。発表後 1 時間は記述。前半 2012–2016／後半 2017–
- 先行研究チェック: WebSearch 2026-10-10「pre-FOMC announcement drift disappeared after 2015 Lucca Moench update」: Kurov ほか 2021、Applied Economics 2025 の再検討。CFD H1・2017 区切り・ランダム日の帰無は未確認（追試・公表後）

## 判定（事前固定）

後半 差>0 かつ z≥2 → 残っている（Kurov を棄却）。後半 z<2 → 消えた（前半で再現したかを併記）

## 結果

未実行。
