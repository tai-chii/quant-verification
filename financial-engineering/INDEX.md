# financial-engineering 検証一覧

> このファイルは `python3 tools/gen_fe_index.py` で自動生成しています。手で編集しないでください。

全 59 件。判定の「—」は未実行または README に判定の記載がないもの。詳細は各ディレクトリの README を参照。

| ディレクトリ | 問い | 判定 |
| :--- | :--- | :--- |
| [bad-period-weighted-selection](./bad-period-weighted-selection) | Q141 悪い時期を重くする目的関数で選んだ順張りは、標本外の最大下落が小さいか（TradeGrad の CPRO の型） | 棄却（確定） |
| [bbc-cv-optimism](./bbc-cv-optimism) | Q172 BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | —（未実行） |
| [bbc-cv-tsmom-optimism](./bbc-cv-tsmom-optimism) | Q172 BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | 確定 |
| [bid-ask-signal-fragility](./bid-ask-signal-fragility) | Q185 合図は bid か ask かで何割変わるか（XAUUSD 実測＋15銘柄の半スプレッドの擬似ずらし） | —（未実行） |
| [breakeven-cost-vs-spread](./breakeven-cost-vs-spread) | Q140 順張りの損益分岐コストは実測スプレッドの何倍か（XAUUSD の Ask データで容量・コスト曲線） | TSMOM20・ドンチャン55/20 とも未確定 |
| [cluster-t-shrinkage](./cluster-t-shrinkage) | Q175 15銘柄を束ねた t は日でクラスタさせると素朴な t から何割下がるか（GarciaArano 2026-3） | 支持（確定） |
| [cpro-exact-selection](./cpro-exact-selection) | Q168 CPRO 本式（Yang 2026 TradeGrad の正格な実装）で順張りの参照日数を選んでも、翌年の最大下落は A と区別がつかない | 棄却（確定） |
| [crypto-h1-reversal-vol](./crypto-h1-reversal-vol) | Q183 暗号資産の1時間足の逆張りの見返りは直前のボラで予測できるか（Farag 2024-1・11通貨） | —（未実行） |
| [data-source-signal-agreement](./data-source-signal-agreement) | Q137 データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか | 「データ源は規則の定義の一部（Korzan と同じ）」→ 確定 |
| [direction-accuracy-vs-base-rate](./direction-accuracy-vs-base-rate) | Q147 翌日の方向の的中率は「常に上」「前日の符号」の基準率を超えるか（HSAT の基準の置き方） | 確定 |
| [dow-structure-direction-vs-time](./dow-structure-direction-vs-time) | Q104 ダウ型の構造確定の後の24時間: 向きの情報か、時刻と地合いか | 棄却（向きの情報なし） |
| [embargo-length-effect](./embargo-length-effect) | Q155 検証とテストの間のエンバーゴ日数で順張りの標本外成績はどれだけ変わるか | e=0 に楽観の方向はあるが、事前登録の第一指標が有意に届かなかった |
| [execution-delay-effect](./execution-delay-effect) | Q156 約定を1〜2営業日遅らせると順張りの成績はどう変わるか（Korzan 2026 表5 では遅れで改善した） | 遅れで改善するのは Korzan のユニバース（二周期の株式ローテーション）に固有の性質。FX／商品／指数／BTC の… |
| [fundagent](./fundagent) | fundagent：ニュースから売買仮説を出し、その的中率を実測するシステム | — |
| [fx-roundnumber-bounce](./fx-roundnumber-bounce) | 為替のキリ番は「跳ね返る場所」ではなく「抜けやすい場所」 | 支持 |
| [fx-shortterm-meanreversion](./fx-shortterm-meanreversion) | 為替の超短期平均回帰は2015年以降の1時間足では消えたか | 消えた（支持） |
| [gotobi-cross-jpy](./gotobi-cross-jpy) | Q179 五十日の仲値前の円安はクロス円でも出て2021年以降に消えたか（Bessho 2023） | —（未実行） |
| [ic-vs-decision-loss](./ic-vs-decision-loss) | Q138 予測の当たりやすさ（IC）と決定の損失（コスト後の純損益）はどれだけ食い違うか | 未確定 |
| [indicator-confirmation](./indicator-confirmation) | Q182 複数の順張り指標が一致したときだけ売買すると的中率と純損益は上がるか（Loubaris 2026-2） | —（未実行） |
| [instrument-selection-bias](./instrument-selection-bias) | Q150 15銘柄から成績の良い 8 銘柄を事後に選ぶと順張りの成績はどれだけ膨らむか（Korzan 2026 §6 の銘柄選択バイアス） | 支持（確定）。選んだ銘柄は後半でむしろ劣る（反転）。膨らみが帰無の95%点をわずかに超えるのはその反転の裏返し（帰無は… |
| [intraday-momentum-first-last](./intraday-momentum-first-last) | Q176 最初の1時間→最後の1時間の日中モメンタムは為替・株価指数・金で公表後に残るか（GarciaArano 2026） | 最初の1時間 → 最後の1時間 の日中モメンタムは、FX8・金・US株価指数2 の H1 で公表後にコスト前・コスト後… |
| [kensho-anomaly-decay](./kensho-anomaly-decay) | 決算発表後のアノマリー減衰 | README の「主な検証」表を参照 |
| [long-short-decomposition](./long-short-decomposition) | Q152 順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか | 未確定（売り側に利益なしは確定。買い側の順張りは機械判定では支持だが、BTC・後半・ドンチャンに依存） |
| [m15-autocorr-by-hour](./m15-autocorr-by-hour) | Q153 15分足の1次自己相関は時刻で符号が変わるか（USDJPY・EURUSD 2021〜・Holm 補正） | 確定（棄却） |
| [ma-cross-eurusd](./ma-cross-eurusd) | MAクロス 全パターン検証（EURUSD 4時間足） | — |
| [ma200-timing-vs-exposure](./ma200-timing-vs-exposure) | 200日移動平均線ルールの下落防御は、タイミングの効果か市場露出が減るだけか（約100年・米株） | README の「主な検証」表を参照 |
| [ml-core-eurusd-h1](./ml-core-eurusd-h1) | Q191 ML 自動売買の「核」（Model 0）は EURUSD の1時間足からコスト後に 0 と区別できる信号を取り出せるか | 棄却（段階1: 粗利でも t<2・コスト以前に信号なし） |
| [null-model-choice](./null-model-choice) | Q178 帰無モデルの選び方（並べ替え・AR(1)・GARCH型）で移動平均ルールの判定は変わるか（Brock 1992） | —（未実行） |
| [oshime-d1-yahoo-close-recheck](./oshime-d1-yahoo-close-recheck) | Q158 押し目・逆張りの D1 系14本を Dukascopy 日足に差し替えて再確認（2026-10-09 Opus） | — |
| [overnight-intraday-reversal-fx](./overnight-intraday-reversal-fx) | Q173 為替の夜間→日中の逆張りは2015年以降の主要8通貨でコスト後に残るか（DellaCorte 2015） | 棄却 |
| [pair-trading](./pair-trading) | ペアトレード（IEF/TLT, NVDA/AMD） | README の「主な検証」表を参照 |
| [parameter-plateau-selection](./parameter-plateau-selection) | Q188 周辺パラメータの平均で選ぶ（台地選択）と最良1点で選ぶより標本外が良いか（ブログZenn2026e-2） | —（未実行） |
| [pbo-cscv-tsmom](./pbo-cscv-tsmom) | Q171 順張りの参照日数 60 通りの CSCV で測った過剰適合の確率 PBO は約 0.88（Bailey 2017） | 支持（過剰適合） |
| [pbo-tsmom-grid](./pbo-tsmom-grid) | Q171 順張りの参照日数60通りの CSCV で過剰適合の確率 PBO はいくつか（Bailey 2017） | —（未実行） |
| [permutation-null-stability](./permutation-null-stability) | Q146 並べ替え帰無の z は何回で安定するか（B と seed のぶれ。検証基盤の既定 B を決めるため） | — |
| [post-fix-conditional-sell](./post-fix-conditional-sell) | Q190 仲値後のドル円の売りは仲値前に上がった五十日だけ効くか（Bessho 2023-2・2008〜2026） | —（未実行） |
| [predictability-to-profit-conversion](./predictability-to-profit-conversion) | Q149 分散比で「予測できる」と出た組は、次の期間にコスト後で儲かるか（Alahmadi 2026 §3.4.1 の変換率） | 前後半とも (b) の t<2 で事前の規則どおり「変換されない」。点推定も前後半とも負で、予測できる組は予測できない… |
| [random-vs-chrono-split](./random-vs-chrono-split) | Q189 ランダム分割の交差検証は時系列分割より順張り選択の楽観をどれだけ膨らませるか（Roelofs 2019-2） | —（未実行） |
| [rebalance-frequency](./rebalance-frequency) | リバランス頻度とリスク尺度のどちらが成績差を支配するか（米国セクター ETF） | README の「主な検証」表を参照 |
| [report-scoring](./report-scoring) | 検証ログの採点基準の事後検証 | README の「主な検証」表を参照 |
| [reselection-frequency](./reselection-frequency) | Q177 順張りの参照日数を選び直す頻度（月・四半期・半年・年）で標本外成績は変わるか（Zarrabi 2017） | —（未実行） |
| [rsi-rules-fx](./rsi-rules-fx) | Q180 RSI の族は先進国通貨の日足で2016年以降も補正後に残るか（Coakley 2016-2） | —（未実行） |
| [seasonality](./seasonality) | 季節性（暖房株・気温相関など） | README の「主な検証」表を参照 |
| [selection-optimism-vs-J](./selection-optimism-vs-J) | Q139 候補数 J を増やすと選択の楽観はどれだけ増え、Alonso の下側限界はそれを覆うか | 単調性「支持」・限界「使える」 |
| [signal-direction-compression](./signal-direction-compression) | Q145 戦略の日次ポジションを平均の向きに圧縮したとき、向きが離れたペアは履歴の相関も低いか（Nunes 2026 を 12 戦略 × 15銘柄で） | — |
| [trend-persistence-vs-tf-pnl](./trend-persistence-vs-tf-pnl) | Q136 トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか | H1・H2 とも棄却 |
| [trend-pnl-half-life](./trend-pnl-half-life) | Q143 順張りの純損益の減衰は指数か、それとも最初から0か（Feng 2026 の半減期を FX8・トレンド7 で） | — |
| [tsmom12m-ma200-cash-rule](./tsmom12m-ma200-cash-rule) | Q151 12か月リターン>0 かつ 200日線上で保有・外れたら現金の規則は、循環シフトの帰無より下落が浅いか（Korzan の規則を15銘柄で） | 確定 |
| [turn-of-month-shift](./turn-of-month-shift) | Q181 月替わり効果の窓は2017年以降に前倒しされたか（QuanterLab 2026・US500/USTECH/SPX） | —（未実行） |
| [two-month-live-vs-random](./two-month-live-vs-random) | Q144 2か月の成績はランダム売買の分布のどこに入るか、順位は次の2か月で入れ替わるか（15銘柄・TSMOM20） | — |
| [usdjpy-london-open-vs-naive-momentum](./usdjpy-london-open-vs-naive-momentum) | USDJPY の日中順張りは、ロンドン開始30分の時刻条件つきシグナルでのみ効くか | README の「主な検証」表を参照 |
| [variance-ratio-setting-dependence](./variance-ratio-setting-dependence) | Q148 弱い形の効率性の検定（分散比）の結論は、設定（q・期間）でどれだけ動くか（Alahmadi・Basingab 2026 §3.5） | 1年の日足では分散比検定そのものがほとんど棄却しない（名目 5% 以下）。「1つの q で非効率と出ても他の q では… |
| [vol-change-reversal](./vol-change-reversal) | Q174 ボラの変化は1日逆張りの翌日リターンを予測するか（DellaCorte 2015-3・15銘柄） | 棄却 |
| [vol-forecast-loss-vs-model](./vol-forecast-loss-vs-model) | Q187 為替のボラ予測で損失関数の差はモデルの差の何倍に見えるか（Tokajuk 2026-1 の為替移植） | —（未実行） |
| [vol-regime-trend-following](./vol-regime-trend-following) | Q142 高ボラ局面では順張りの的中率と純損益が下がるか（15銘柄・GARCH なしの実現ボラ） | 未確定（事後発見の向きは4通り一致、大きさは半期では届かず・全期間は2/4 で ／z／≥2・主に XAUUSD と v… |
| [weekly-vs-daily-tsmom](./weekly-vs-daily-tsmom) | Q186 週足の順張りは日足より強いか（Neely 2003-3・15銘柄・2008〜2026） | —（未実行） |
| [window-pnl-vs-vol](./window-pnl-vs-vol) | Q184 2か月窓の順張り成績はその窓の実現ボラとドリフトで説明できるか（Rashid 2026-1・Q144 の続き） | —（未実行） |
| [wrc-spa-disagreement](./wrc-spa-disagreement) | Q154 WRC・SPA(consistent)・SPA(conservative) の判定は同じルール群でどれだけ割れるか | 確定（棄却） |
| [xauusd-vol-regime-single](./xauusd-vol-regime-single) | Q161 XAUUSD 単銘柄・直前20〜60日の実現ボラが高い日に翌日の順張り損益が下がるか（ドリフト除去・前後半） | 未確定（6/6 で向き一致・／z／≥2 達成は 3/6 で窓40・60日に偏る・ドリフト除去は結論を変えない） |
