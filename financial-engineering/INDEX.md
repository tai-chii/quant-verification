# financial-engineering 検証一覧

> このファイルは `python3 tools/gen_fe_index.py` で自動生成しています。手で編集しないでください。

全 34 件。判定の「—」は未実行または README に判定の記載がないもの。詳細は各ディレクトリの README を参照。

| ディレクトリ | 問い | 判定 |
| :--- | :--- | :--- |
| [bad-period-weighted-selection](./bad-period-weighted-selection) | Q141 悪い時期を重くする目的関数で選んだ順張りは、標本外の最大下落が小さいか（TradeGrad の CPRO の型） | 棄却（確定） |
| [breakeven-cost-vs-spread](./breakeven-cost-vs-spread) | Q140 順張りの損益分岐コストは実測スプレッドの何倍か（XAUUSD の Ask データで容量・コスト曲線） | TSMOM20・ドンチャン55/20 とも未確定 |
| [data-source-signal-agreement](./data-source-signal-agreement) | Q137 データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか | 「データ源は規則の定義の一部（Korzan と同じ）」→ 確定 |
| [direction-accuracy-vs-base-rate](./direction-accuracy-vs-base-rate) | Q147 翌日の方向の的中率は「常に上」「前日の符号」の基準率を超えるか（HSAT の基準の置き方） | 確定 |
| [dow-structure-direction-vs-time](./dow-structure-direction-vs-time) | Q104 ダウ型の構造確定の後の24時間: 向きの情報か、時刻と地合いか | 棄却（向きの情報なし） |
| [embargo-length-effect](./embargo-length-effect) | Q155 検証とテストの間のエンバーゴ日数で順張りの標本外成績はどれだけ変わるか | — |
| [execution-delay-effect](./execution-delay-effect) | Q156 約定を1〜2営業日遅らせると順張りの成績はどう変わるか（Korzan 2026 表5 では遅れで改善した） | — |
| [fundagent](./fundagent) | fundagent：ニュースから売買仮説を出し、その的中率を実測するシステム | — |
| [fx-roundnumber-bounce](./fx-roundnumber-bounce) | 為替のキリ番は「跳ね返る場所」ではなく「抜けやすい場所」 | 支持 |
| [fx-shortterm-meanreversion](./fx-shortterm-meanreversion) | 為替の超短期平均回帰は2015年以降の1時間足では消えたか | 消えた（支持） |
| [ic-vs-decision-loss](./ic-vs-decision-loss) | Q138 予測の当たりやすさ（IC）と決定の損失（コスト後の純損益）はどれだけ食い違うか | 未確定 |
| [instrument-selection-bias](./instrument-selection-bias) | Q150 15銘柄から成績の良い 8 銘柄を事後に選ぶと順張りの成績はどれだけ膨らむか（Korzan 2026 §6 の銘柄選択バイアス） | — |
| [kensho-anomaly-decay](./kensho-anomaly-decay) | 決算発表後のアノマリー減衰 | README の「主な検証」表を参照 |
| [long-short-decomposition](./long-short-decomposition) | Q152 順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか | — |
| [m15-autocorr-by-hour](./m15-autocorr-by-hour) | Q153 15分足の1次自己相関は時刻で符号が変わるか（USDJPY・EURUSD 2021〜・Holm 補正） | — |
| [ma-cross-eurusd](./ma-cross-eurusd) | MAクロス 全パターン検証（EURUSD 4時間足） | — |
| [ma200-timing-vs-exposure](./ma200-timing-vs-exposure) | 200日移動平均線ルールの下落防御は、タイミングの効果か市場露出が減るだけか（約100年・米株） | README の「主な検証」表を参照 |
| [oshime-d1-yahoo-close-recheck](./oshime-d1-yahoo-close-recheck) | Q158 押し目・逆張りの D1 系14本を Dukascopy 日足に差し替えて再確認（2026-10-09 Opus） | — |
| [pair-trading](./pair-trading) | ペアトレード（IEF/TLT, NVDA/AMD） | README の「主な検証」表を参照 |
| [permutation-null-stability](./permutation-null-stability) | Q146 並べ替え帰無の z は何回で安定するか（B と seed のぶれ。検証基盤の既定 B を決めるため） | — |
| [predictability-to-profit-conversion](./predictability-to-profit-conversion) | Q149 分散比で「予測できる」と出た組は、次の期間にコスト後で儲かるか（Alahmadi 2026 §3.4.1 の変換率） | — |
| [rebalance-frequency](./rebalance-frequency) | リバランス頻度とリスク尺度のどちらが成績差を支配するか（米国セクター ETF） | README の「主な検証」表を参照 |
| [report-scoring](./report-scoring) | 検証ログの採点基準の事後検証 | README の「主な検証」表を参照 |
| [seasonality](./seasonality) | 季節性（暖房株・気温相関など） | README の「主な検証」表を参照 |
| [selection-optimism-vs-J](./selection-optimism-vs-J) | Q139 候補数 J を増やすと選択の楽観はどれだけ増え、Alonso の下側限界はそれを覆うか | 単調性「支持」・限界「使える」 |
| [signal-direction-compression](./signal-direction-compression) | Q145 戦略の日次ポジションを平均の向きに圧縮したとき、向きが離れたペアは履歴の相関も低いか（Nunes 2026 を 12 戦略 × 15銘柄で） | — |
| [trend-persistence-vs-tf-pnl](./trend-persistence-vs-tf-pnl) | Q136 トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか | H1・H2 とも棄却 |
| [trend-pnl-half-life](./trend-pnl-half-life) | Q143 順張りの純損益の減衰は指数か、それとも最初から0か（Feng 2026 の半減期を FX8・トレンド7 で） | — |
| [tsmom12m-ma200-cash-rule](./tsmom12m-ma200-cash-rule) | Q151 12か月リターン>0 かつ 200日線上で保有・外れたら現金の規則は、循環シフトの帰無より下落が浅いか（Korzan の規則を15銘柄で） | — |
| [two-month-live-vs-random](./two-month-live-vs-random) | Q144 2か月の成績はランダム売買の分布のどこに入るか、順位は次の2か月で入れ替わるか（15銘柄・TSMOM20） | — |
| [usdjpy-london-open-vs-naive-momentum](./usdjpy-london-open-vs-naive-momentum) | USDJPY の日中順張りは、ロンドン開始30分の時刻条件つきシグナルでのみ効くか | README の「主な検証」表を参照 |
| [variance-ratio-setting-dependence](./variance-ratio-setting-dependence) | Q148 弱い形の効率性の検定（分散比）の結論は、設定（q・期間）でどれだけ動くか（Alahmadi・Basingab 2026 §3.5） | — |
| [vol-regime-trend-following](./vol-regime-trend-following) | Q142 高ボラ局面では順張りの的中率と純損益が下がるか（15銘柄・GARCH なしの実現ボラ） | — |
| [wrc-spa-disagreement](./wrc-spa-disagreement) | Q154 WRC・SPA(consistent)・SPA(conservative) の判定は同じルール群でどれだけ割れるか | — |
