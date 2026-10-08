# verification-lab

検証のポートフォリオ。金融工学の検証（トレード手法・シグナルの有効性を、ランダム化検定・前半/後半の順位相関・アウトオブサンプル確認などの再現性チェック付きで検証する一連のプロジェクト）と、分野を問わないデータサイエンスのコンペ参加実績（Kaggle・Numerai 等）をまとめています。

リポジトリは `financial-engineering/`（為替・株などマーケット系の検証）・`mahjong/`（麻雀の戦術検証）・`competitions/`（コンペ参加実績）・`tools/`（補助ツール）の4本柱で構成しています。

## 1. 検証（再現性チェック付きバックテスト）

マーケット系の検証は 2026-10-09 に `financial-engineering/` 配下へ統合しました（下表の mahjong 以外はすべてその配下です）。

| ディレクトリ | 対象 | 手法概要 |
| :--- | :--- | :--- |
| [fx-shortterm-meanreversion](./financial-engineering/fx-shortterm-meanreversion) | 為替の超短期平均回帰（1996年前後の報告の追試） | 主要8通貨の H1・週次ラグ1自己相関を 2008–2026 を3期間に分けて測定。2015年以降は消えたことを確認（棄却も知見として記録） |
| [fx-roundnumber-bounce](./financial-engineering/fx-roundnumber-bounce) | 為替のキリ番は跳ね返るか・損切りは狩られやすいか | 主要8通貨＋金銀の H1/M15 で、キリ番と対照価格の反転率・継続率・損切りの到達率/狩られ率を比較。キリ番は跳ね返りにくく、むしろ抜けやすいことを独立データで確認 |
| [ma-cross-eurusd](./financial-engineering/ma-cross-eurusd) | EURUSD H4 の移動平均クロス | SMA/EMA 2本・3本の全周期組合せ（約508万通り）を総当たり検証。循環シフトによるランダム化検定とデータスヌーピング補正、前半/後半の再現性チェックを実施 |
| [kensho-anomaly-decay](./financial-engineering/kensho-anomaly-decay) | 決算発表後のアノマリー減衰 | 公表効果（PEAD 等）がどの程度のスピードで薄れるかをブートストラップで検証 |
| [seasonality](./financial-engineering/seasonality) | 季節性（暖房株・気温相関など） | 気温と関連銘柄の相関、暖房株の季節パターン・空売り検証、決算前後の分解分析 |
| [pair-trading](./financial-engineering/pair-trading) | ペアトレード（IEF/TLT, NVDA/AMD） | 共和分・スプレッドの検証スクリプト |
| [rebalance-frequency](./financial-engineering/rebalance-frequency) | リバランス頻度とリスク尺度のどちらが成績差を支配するか（米国セクター ETF） | Shah et al.(2026) の「頻度間の差がリスク尺度間の差より大きい」という結果が、推定窓の長さを頻度に連動させない設計でも残るかを検証。残る（支持。ただし信頼区間は0を含み、点推定どまり） |
| [dow-structure-direction-vs-time](./financial-engineering/dow-structure-direction-vs-time) | ダウ型（山谷）の構造確定後24時間は、方向の情報か時刻・地合いの情報か（為替8通貨） | USDJPY でのブログの数値は再現したが、上昇後/下降後の差の多くは同じ時刻帯の平均リターンで説明され、方向そのものの情報は棄却 |
| [ma200-timing-vs-exposure](./financial-engineering/ma200-timing-vs-exposure) | 200日移動平均線ルールの下落防御は、タイミングの効果か市場露出が減るだけか（約100年・米株） | Q097: 循環シフト検定で、防御効果はタイミングによるものを支持。Q098: 下落速度別の200日線/ボラティリティターゲティングの優劣は符号検定で過半数支持だが、全局面では成立せず |
| [usdjpy-london-open-vs-naive-momentum](./financial-engineering/usdjpy-london-open-vs-naive-momentum) | USDJPY の日中順張りは、ロンドン開始30分の時刻条件つきシグナルでのみ効くか | Seeck(2026) のロンドン開始30分シグナルを 2025-01〜2026-07 の独立データで再検証。コスト後の優位性なし（棄却） |
| [report-scoring](./financial-engineering/report-scoring) | 検証ログの採点基準の事後検証 | 採点基準（先読みなし・帰無比較・多重比較考慮など）が「結論が後で覆るかどうか」をどれだけ予測するかを、ブラインド採点と AUC で検証するメタ分析 |
| [mahjong](./mahjong) | 雀魂の戦術検証 | mjai+libriichi による対人バックテストと、門前牌効率のみを測るソロシミュレータの2系統で、マイルールをアブレーション検証 |

各検証の詳細な手法・結果は、それぞれのディレクトリの README・計画書を参照してください。

## 2. fundagent — ニュース駆動のシグナル生成＋自動検証

[fundagent/](./financial-engineering/fundagent)（`financial-engineering/` 配下）— ファンダメンタルズのニュースを LLM で構造化して売買仮説を提案し、**後からその提案の成績を自動で検証する**プロトタイプ。主役は提案ではなく検証そのものです。詳細は [fundagent/README.md](./financial-engineering/fundagent/README.md) を参照してください。

## 3. competitions — データサイエンスコンペ参加実績

[competitions/](./competitions) — Kaggle（Hull Tactical Market Prediction）・Numerai トーナメントでのモデル学習・アンサンブル・提出パイプライン。詳細は [competitions/README.md](./competitions/README.md) を参照してください。

## 4. tools — 補助ツール

[tools/](./tools) — 検証キューの管理スクリプトなど、検証パイプラインを回すための補助ツール。

## このリポジトリについて

**方針**: コードと、それを理解するのに必要な最小限の情報（README・手法の説明・軽量な結果要約）のみを置く。検証を再現すればいつでも再生成できる生データ・中間生成物・運用ログは含めない。

- 全組合せの生データ（npz/parquet 等）、取引明細の生ダンプ、per-era 等の大容量な途中経過 CSV、ブートストラップの生サンプル、収集・学習・提出の運用ログ、学習データ・モデル重み・キャッシュはリポジトリに含めていません。各検証・プロジェクトの要約（`summary.json`・集計済み CSV 等）のみを残しています。
- 実際の売買記録（損益を含む個人的な取引履歴）は対象外としています。
- 今後、USDJPY や他の時間足・手法の検証を追加予定です。
