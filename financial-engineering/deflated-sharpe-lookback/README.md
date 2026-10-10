# Q260 参照日数60通りから選んだ最良は Deflated Sharpe Ratio で補正すると何銘柄で残るか（Bailey・López de Prado 2014）

事前登録: `検証/学問/金融工学/知識/文献/アイデア候補.md` の Q260 の行（Fable 2026-10-10・30案一括生成 第5弾）。出典: Bailey・López de Prado 2014（J. Portfolio Management・DSR）、[[Korzan2026-2_1214試行のDSRは97.05パーセントWhite_RCはp0.027で多重性補正後も有意だが最終3年のCAPMアルファは有意でない]]、知見 Q171（PBO 0.88）・Q139・Q172。

- スクリプト: `kensho_deflated_sharpe_q260.py`（自己完結・冒頭に仮説・定義・判定・捨てた案の数・知識の締め切り・委託の確かめ方を記載）
- データ: 15銘柄 D1_fromH1。（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の `missing` に）
- 実行: `python3 kensho_deflated_sharpe_q260.py`（B=200・中（B=200×60 通り×15・3〜5 分）。pandas/numpy のみ）
- 試走: `--B 10`。経路の確認だけなら `--smoke`（合成データ・結果は `results/smoke_*`。**判定には使わない**）
- 結果: `results/Q260_result_<日時>.json`（設定・集計・機械判定 `machine_verdict`）

## 状態（2026-10-10）

**設計（Fable）とコード（Claude Fable 5.1）まで。実行と結果の解釈は未。** コードはクラウド側で `--smoke --B 5` の経路確認だけ済み（合成データ・判定には使わない）。
Sonnet／Opus が実行するときの手順:

1. 標準手順H の 3「出口で検証するときの決まり」どおり、スクリプト冒頭の仮説・判定を読んでから走らせる（変更しない）。
2. `python3 kensho_deflated_sharpe_q260.py` を Mac で実行。
3. JSON の `machine_verdict` は事前固定の規則で機械的に付けたもの。**確定／ノイズ／未確定** の解釈は実行者が書く（下の「結果」の節に `判定: **…**` の形で）。
4. 記録先: 知見ノート（＋知見一覧.jsonl）、出典の主張カードの `自分の検証`、アイデア候補の状態、FX 改善ログ（FX のとき）、検証キュー Q260 を完了へ、`gen_fe_index.py` で一覧を更新。

## 方法（要点）

- 仮説: H: 各銘柄で参照日数 L∈{5,…,300}（60 通り）から標本内（2008–2016）の最良シャープを選び、DSR（試行数 60・試行のシャープの分散・歪度・尖度・日数で補正）を当てると、DSR≥0.95 で残る銘柄は 15 銘柄中 2 以下（名目 5% 並み）。
- 定義: 試行 N=60。E[max SR] = √V·((1−γ)Φ⁻¹(1−1/N)+γΦ⁻¹(1−1/(Ne)))（γ=0.5772）。PSR(SR*, SR̂) を DSR とする。標本外 2017– の最良 L のシャープも記述。
- 測るもの: DSR≥0.95 の銘柄数（all15）、DSR と標本外シャープの Spearman。
- 帰無: リターンを年内で並べ替えた帰無で同じ手順（選択＋DSR）を B=200 回 → DSR≥0.95 の銘柄数の帰無分布 → 観測が帰無の 95 点を超えるか。
- 多重比較: 判定は銘柄数 1 本（DSR 自体が 60 試行の補正）。Spearman は記述。
- 捨てた案: 約3: 試行数を 60×15 にする（銘柄をまたぐ選択はしない）、PBO と同時に出す（Q171 で済み）、月次シャープ。
- 先行研究チェック: WebSearch 2026-10-10「deflated Sharpe ratio Bailey Lopez de Prado applied to trend following lookback selection multiple testing」: SSRN 2460551（原論文）、Wikipedia、quantstrat の deflatedSharpe、CXO「Sharper Sharpe ratio」。 DSR を順張りの参照日数選択に 15 銘柄・並べ替え帰無つきで当てた形は未確認（追試）。

## 判定（事前固定）

DSR≥0.95 の銘柄数 ≤2 かつ 帰無の 95 点以下 → 支持（補正後は名目並み）。≥5 かつ 帰無の 95 点超 → 棄却（補正後も残る）。それ以外 → 未確定。

## 結果

未実行。
