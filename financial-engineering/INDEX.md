# financial-engineering 検証一覧

> このファイルは `python3 tools/gen_fe_index.py` で自動生成しています。手で編集しないでください。

全 99 件。判定の「—」は未実行または README に判定の記載がないもの。詳細は各ディレクトリの README を参照。

| ディレクトリ | 問い | 判定 |
| :--- | :--- | :--- |
| [52week-high-vs-momentum](./52week-high-vs-momentum) | Q214 52 週高値への近さは 15 銘柄の翌月リターンを 12 か月モメンタムより予測するか（George・Hwang 2004 の型） | 棄却側の確定 |
| [adx-filter-tsmom](./adx-filter-tsmom) | Q246 ADX(14) > 25 の局面に限ると、順張りの純損益は上がるか（15 銘柄・月ブロック並べ替え帰無） | … |
| [asian-range-breakout](./asian-range-breakout) | Q220 アジア時間（0〜7 UTC）のレンジを欧州時間に抜けたら終値まで続くか（FX8 H1・ブレイクアウト） | 棄却 |
| [atr-stop-loss-tsmom](./atr-stop-loss-tsmom) | Q204 ATR 倍の損切りは 15 銘柄の日足順張りの純損益と最大下落を改善するか（Kaminski・Lo 2014 の型） | 未確定（純損益の改善なし）／最大下落は確実に改善（記述） |
| [bad-period-weighted-selection](./bad-period-weighted-selection) | Q141 悪い時期を重くする目的関数で選んだ順張りは、標本外の最大下落が小さいか（TradeGrad の CPRO の型） | 棄却（確定） |
| [bbc-cv-optimism](./bbc-cv-optimism) | Q172 BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | —（未実行） |
| [bbc-cv-tsmom-optimism](./bbc-cv-tsmom-optimism) | Q172 BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | 確定 |
| [bid-ask-signal-fragility](./bid-ask-signal-fragility) | Q185 合図は bid か ask かで何割変わるか（XAUUSD 実測＋15銘柄の半スプレッドの擬似ずらし） | 未確定（機械判定）／解釈: 規則の型による |
| [breakeven-cost-vs-spread](./breakeven-cost-vs-spread) | Q140 順張りの損益分岐コストは実測スプレッドの何倍か（XAUUSD の Ask データで容量・コスト曲線） | TSMOM20・ドンチャン55/20 とも未確定 |
| [close-location-next-day](./close-location-next-day) | Q237 終値位置 CLV が極端な日の翌日は、続くか反転するか（15 銘柄・Holm） | … |
| [cluster-t-shrinkage](./cluster-t-shrinkage) | Q175 15銘柄を束ねた t は日でクラスタさせると素朴な t から何割下がるか（GarciaArano 2026-3） | 支持（確定） |
| [commodity-currency-leadlag](./commodity-currency-leadlag) | Q241 原油→USDCAD・金→AUDUSD の日次リード・ラグは、両方向のどちらが強いか（Chen・Rogoff・Rossi 2010 の逆向き） | … |
| [cpro-exact-selection](./cpro-exact-selection) | Q168 CPRO 本式（Yang 2026 TradeGrad の正格な実装）で順張りの参照日数を選んでも、翌年の最大下落は A と区別がつかない | 棄却（確定） |
| [crisis-alpha-tsmom](./crisis-alpha-tsmom) | Q207・Q224 危機アルファ：US500 の下落局面で順張りは正の損益か（Hurst・Ooi・Pedersen 2017 の型） | 原典型 TSMOM（1/3/12か月合成・σ60値幅目標）は US500 の下落局面で合計 +189 bp・6 局面中… |
| [cross-market-leadlag-h1](./cross-market-leadlag-h1) | Q236 4 組（XAU→XAG・WTI→UKOIL・BTC→ETH・US500→USTECH）の H1 リード・ラグは、両方向のどちらが強いか | … |
| [cross-sectional-vs-ts-momentum](./cross-sectional-vs-ts-momentum) | Q218 横断モメンタム（15 銘柄の上位 5 買い・下位 5 売り）は時系列モメンタムとコスト後にどれだけ違うか（Moskowitz ほか 2012 の型） | ノイズ（前後半で揃った差はない） |
| [crypto-h1-reversal-vol](./crypto-h1-reversal-vol) | Q183 暗号資産の1時間足の逆張りの見返りは直前のボラで予測できるか（Farag 2024-1・11通貨） | ボラは1時間逆張りの粗利を予測する（Farag 2024-1 の H1 版）。ただし後半で係数が3〜4倍小さくなり、保… |
| [crypto-hour-of-day](./crypto-hour-of-day) | Q242 暗号資産 11 通貨の UTC 時刻効果は、Holm 補正後に前後半で同符号で残るか | … |
| [crypto-weekend-effect](./crypto-weekend-effect) | Q212 暗号資産の週末（土日）はリターン・ボラ・順張りの損益が平日と違うか（11 通貨 H1） | H1a 弱い確定（効果はほぼ消滅）／H1b 棄却 |
| [daily-cutoff-hour-dependence](./daily-cutoff-hour-dependence) | Q211 日足の区切り時刻（0・8・13・17・21 UTC）で順張りの純損益はどれだけ変わるか（帰無: 区切りをランダムに選ぶ） | 棄却 |
| [data-source-signal-agreement](./data-source-signal-agreement) | Q137 データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか | 「データ源は規則の定義の一部（Korzan と同じ）」→ 確定 |
| [day-of-week-15](./day-of-week-15) | Q206 曜日効果は 15 銘柄の日足で 2017 年以降も残るか（曜日ラベル並べ替え・Holm） | 棄却（Q206・2026-10-10・15銘柄 D1 2008-02〜2026-07・B=500・SPLIT_YEAR… |
| [direction-accuracy-vs-base-rate](./direction-accuracy-vs-base-rate) | Q147 翌日の方向の的中率は「常に上」「前日の符号」の基準率を超えるか（HSAT の基準の置き方） | 確定 |
| [dollar-factor-momentum](./dollar-factor-momentum) | Q208 ドル因子（6 通貨の対ドル等加重）の順張りは個別ペアの順張りの平均より強いか（Verdelhan 2018 の型） | 棄却 |
| [dow-structure-direction-vs-time](./dow-structure-direction-vs-time) | Q104 ダウ型の構造確定の後の24時間: 向きの情報か、時刻と地合いか | 棄却（向きの情報なし） |
| [embargo-length-effect](./embargo-length-effect) | Q155 検証とテストの間のエンバーゴ日数で順張りの標本外成績はどれだけ変わるか | e=0 に楽観の方向はあるが、事前登録の第一指標が有意に届かなかった |
| [equity-curve-trading](./equity-curve-trading) | Q210 エクイティカーブ・トレーディング（戦略の直近損益で規模を変える）は 15 銘柄の順張りの標本外成績を上げるか | 棄却 |
| [execution-delay-effect](./execution-delay-effect) | Q156 約定を1〜2営業日遅らせると順張りの成績はどう変わるか（Korzan 2026 表5 では遅れで改善した） | 遅れで改善するのは Korzan のユニバース（二周期の株式ローテーション）に固有の性質。FX／商品／指数／BTC の… |
| [execution-hour-spread](./execution-hour-spread) | Q245 XAUUSD 順張りの約定時刻を、実測スプレッドの狭い時間に移すと純損益は上がるか | … |
| [fundagent](./fundagent) | fundagent：ニュースから売買仮説を出し、その的中率を実測するシステム | — |
| [fx-roundnumber-bounce](./fx-roundnumber-bounce) | 為替のキリ番は「跳ね返る場所」ではなく「抜けやすい場所」 | 支持 |
| [fx-shortterm-meanreversion](./fx-shortterm-meanreversion) | 為替の超短期平均回帰は2015年以降の1時間足では消えたか | 消えた（支持） |
| [gotobi-cross-jpy](./gotobi-cross-jpy) | Q179 五十日の仲値前の円安はクロス円でも出て2021年以降に消えたか（Bessho 2023） | 対立を支持: ドル固有 |
| [halloween-effect](./halloween-effect) | Q238 「5 月に売れ」（ハロウィン効果）は 2008〜2026 の指数・商品 6 銘柄で残るか（6 か月ブロックの循環シフト帰無） | … |
| [ic-vs-decision-loss](./ic-vs-decision-loss) | Q138 予測の当たりやすさ（IC）と決定の損失（コスト後の純損益）はどれだけ食い違うか | 未確定 |
| [indicator-confirmation](./indicator-confirmation) | Q182 複数の順張り指標が一致したときだけ売買すると的中率と純損益は上がるか（Loubaris 2026-2） | 棄却（Loubaris と同じ非有意） |
| [instrument-selection-bias](./instrument-selection-bias) | Q150 15銘柄から成績の良い 8 銘柄を事後に選ぶと順張りの成績はどれだけ膨らむか（Korzan 2026 §6 の銘柄選択バイアス） | 支持（確定）。選んだ銘柄は後半でむしろ劣る（反転）。膨らみが帰無の95%点をわずかに超えるのはその反転の裏返し（帰無は… |
| [intraday-momentum-first-last](./intraday-momentum-first-last) | Q176 最初の1時間→最後の1時間の日中モメンタムは為替・株価指数・金で公表後に残るか（GarciaArano 2026） | 最初の1時間 → 最後の1時間 の日中モメンタムは、FX8・金・US株価指数2 の H1 で公表後にコスト前・コスト後… |
| [kensho-anomaly-decay](./kensho-anomaly-decay) | 決算発表後のアノマリー減衰 | README の「主な検証」表を参照 |
| [long-short-decomposition](./long-short-decomposition) | Q152 順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか | 未確定（売り側に利益なしは確定。買い側の順張りは機械判定では支持だが、BTC・後半・ドンチャンに依存） |
| [lookback-ensemble-tsmom](./lookback-ensemble-tsmom) | Q223 参照日数の集合（20・60・120・250 の合図平均）は最良単一の参照日数より標本外で良いか（Baltas・Kosowski の型） | ノイズ: 合図平均と最良単一の差は前後半で揃わず事前固定の t≥2 または t≤−2 のどちらも通らない |
| [m15-autocorr-by-hour](./m15-autocorr-by-hour) | Q153 15分足の1次自己相関は時刻で符号が変わるか（USDJPY・EURUSD 2021〜・Holm 補正） | 確定（棄却） |
| [ma-cross-eurusd](./ma-cross-eurusd) | MAクロス 全パターン検証（EURUSD 4時間足） | — |
| [ma200-timing-vs-exposure](./ma200-timing-vs-exposure) | 200日移動平均線ルールの下落防御は、タイミングの効果か市場露出が減るだけか（約100年・米株） | README の「主な検証」表を参照 |
| [ml-core-eurusd-h1](./ml-core-eurusd-h1) | Q191 ML 自動売買の「核」（Model 0）は EURUSD の1時間足からコスト後に 0 と区別できる信号を取り出せるか | 棄却（段階1: 粗利でも t<2・コスト以前に信号なし） |
| [month-end-fix-dollar](./month-end-fix-dollar) | Q229 月末のロンドン16時フィキシング前のドルの向きは、その月の US500 リターンと逆か（Melvin・Prins 2015 の型） | … |
| [nfp-m15-followthrough](./nfp-m15-followthrough) | Q219 米雇用統計（NFP）の直後 15 分の向きは次の 1〜4 時間に続くか反転するか（EURUSD・USDJPY M15・2021 年以降） | 棄却: 継続とも反転とも区別できない |
| [nr7-breakout-continuation](./nr7-breakout-continuation) | Q217 NR7（直前 7 日で最小レンジ）の翌日は最初の 2 時間の向きに続くか（FX8＋金・H1 から日足） | 棄却 |
| [null-model-choice](./null-model-choice) | Q178 帰無モデルの選び方（並べ替え・AR(1)・GARCH型）で移動平均ルールの判定は変わるか（Brock 1992） | 確定（H1 支持: 帰無の選び方で判定はほぼ割れない） |
| [one-month-reversal](./one-month-reversal) | Q215 1 か月の短期反転（直前 21 日の逆）は 15 銘柄の日足でコスト後に残るか（Jegadeesh 1990 の型・12-1 モメンタムと対比） | 棄却（粗利でも負・事前固定 z≥2 を通らず） |
| [oshime-d1-yahoo-close-recheck](./oshime-d1-yahoo-close-recheck) | Q158 押し目・逆張りの D1 系14本を Dukascopy 日足に差し替えて再確認（2026-10-09 Opus） | — |
| [overnight-intraday-reversal-fx](./overnight-intraday-reversal-fx) | Q173 為替の夜間→日中の逆張りは2015年以降の主要8通貨でコスト後に残るか（DellaCorte 2015） | 棄却 |
| [overnight-premium-indices](./overnight-premium-indices) | Q209 株価指数・金の夜間（現物取引時間外）リターンは日中より高いか（夜間プレミアム・H1・2017 年以降） | 棄却。夜間が日中より稼ぐように見える差は「夜間が 18 時間・日中が 6 時間」という長さの差で説明でき、14〜20 … |
| [pair-trading](./pair-trading) | ペアトレード（IEF/TLT, NVDA/AMD） | README の「主な検証」表を参照 |
| [parameter-plateau-selection](./parameter-plateau-selection) | Q188 周辺パラメータの平均で選ぶ（台地選択）と最良1点で選ぶより標本外が良いか（ブログZenn2026e-2） | H0: 選び方では変わらない |
| [parkinson-vol-forecast](./parkinson-vol-forecast) | Q222 Parkinson のレンジボラは終値ボラより翌日の実現ボラをよく予測するか（15 銘柄・QLIKE・HAR 型） | 支持: Parkinson のレンジは終値より翌日の実現ボラをよく予測する |
| [parkinson-vol-targeting](./parkinson-vol-targeting) | Q232 Parkinson レンジボラでのボラ・ターゲティングは終値 σ60 版よりシャープが高いか（Q222 × Q205 の連鎖） | … |
| [pbo-cscv-tsmom](./pbo-cscv-tsmom) | Q171 順張りの参照日数 60 通りの CSCV で測った過剰適合の確率 PBO は約 0.88（Bailey 2017） | 支持（過剰適合） |
| [pbo-tsmom-grid](./pbo-tsmom-grid) | Q171 順張りの参照日数60通りの CSCV で過剰適合の確率 PBO はいくつか（Bailey 2017） | —（未実行） |
| [permutation-null-stability](./permutation-null-stability) | Q146 並べ替え帰無の z は何回で安定するか（B と seed のぶれ。検証基盤の既定 B を決めるため） | — |
| [post-fix-conditional-sell](./post-fix-conditional-sell) | Q190 仲値後のドル円の売りは仲値前に上がった五十日だけ効くか（Bessho 2023-2・2008〜2026） | 棄却 |
| [pre-fomc-drift](./pre-fomc-drift) | Q243 FOMC 前日ドリフトは US500 H1 で 2015 年以降も残るか（Lucca・Moench 2015／Kurov ほか 2021 の追試） | … |
| [pre-holiday-effect](./pre-holiday-effect) | Q239 休日前効果は SPX・NDX（2008〜2026）で残るか（祝日は欠損営業日から復元・Lakonishok・Smidt 1988 の型） | … |
| [predictability-to-profit-conversion](./predictability-to-profit-conversion) | Q149 分散比で「予測できる」と出た組は、次の期間にコスト後で儲かるか（Alahmadi 2026 §3.4.1 の変換率） | 前後半とも (b) の t<2 で事前の規則どおり「変換されない」。点推定も前後半とも負で、予測できる組は予測できない… |
| [random-vs-chrono-split](./random-vs-chrono-split) | Q189 ランダム分割の交差検証は時系列分割より順張り選択の楽観をどれだけ膨らませるか（Roelofs 2019-2） | 符号は仮説と逆（ランダム分割の方が時系列分割より楽観が小さい）だが、有意ではない |
| [ratio-pairs-mean-reversion](./ratio-pairs-mean-reversion) | Q233 金銀比・Brent−WTI の z スコア逆張り（ペアトレード）は 2015 年以降コスト後に残るか | … |
| [realized-skew-next-month](./realized-skew-next-month) | Q231 H1 から作る月次の実現歪度は翌月リターンを負に予測するか（Amaya ほか 2015 の型・15 銘柄） | … |
| [rebalance-frequency](./rebalance-frequency) | リバランス頻度とリスク尺度のどちらが成績差を支配するか（米国セクター ETF） | README の「主な検証」表を参照 |
| [report-scoring](./report-scoring) | 検証ログの採点基準の事後検証 | README の「主な検証」表を参照 |
| [reselection-frequency](./reselection-frequency) | Q177 順張りの参照日数を選び直す頻度（月・四半期・半年・年）で標本外成績は変わるか（Zarrabi 2017） | ノイズ |
| [rsi-rules-fx](./rsi-rules-fx) | Q180 RSI の族は先進国通貨の日足で2016年以降も補正後に残るか（Coakley 2016-2） | 棄却（確定） |
| [seasonality](./seasonality) | 季節性（暖房株・気温相関など） | README の「主な検証」表を参照 |
| [selection-optimism-vs-J](./selection-optimism-vs-J) | Q139 候補数 J を増やすと選択の楽観はどれだけ増え、Alonso の下側限界はそれを覆うか | 単調性「支持」・限界「使える」 |
| [selection-window-length](./selection-window-length) | Q244 参照日数の選択窓の長さ（1・2・3・5・8 年）で、順張りの標本外純損益は変わるか（15 銘柄） | … |
| [signal-confirmation-filter](./signal-confirmation-filter) | Q221 合図の確認フィルタ（k 日連続同符号で入る）は 15 銘柄の順張りのホイップソーを減らし純損益を上げるか | 未確定 |
| [signal-direction-compression](./signal-direction-compression) | Q145 戦略の日次ポジションを平均の向きに圧縮したとき、向きが離れたペアは履歴の相関も低いか（Nunes 2026 を 12 戦略 × 15銘柄で） | — |
| [spread-change-vol-forecast](./spread-change-vol-forecast) | Q234 XAUUSD の実測スプレッドの変化は、HAR に足すと翌時間の実現ボラの QLIKE を下げるか | … |
| [streak-reversal](./streak-reversal) | Q240 k 日連続同符号（k=3・5）の翌日は反転するか（15 銘柄・年内並べ替え帰無） | … |
| [trend-persistence-vs-tf-pnl](./trend-persistence-vs-tf-pnl) | Q136 トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか | H1・H2 とも棄却 |
| [trend-pnl-half-life](./trend-pnl-half-life) | Q143 順張りの純損益の減衰は指数か、それとも最初から0か（Feng 2026 の半減期を FX8・トレンド7 で） | — |
| [tsmom-pnl-concentration](./tsmom-pnl-concentration) | Q230 順張りの純損益は上位 1% の日に集中しているか: 最大の k 日を除くと年単位の t が 2 を切るか（15 銘柄 D1） | … |
| [tsmom12m-ma200-cash-rule](./tsmom12m-ma200-cash-rule) | Q151 12か月リターン>0 かつ 200日線上で保有・外れたら現金の規則は、循環シフトの帰無より下落が浅いか（Korzan の規則を15銘柄で） | 確定 |
| [turn-of-month-shift](./turn-of-month-shift) | Q181 月替わり効果の窓は2017年以降に前倒しされたか（QuanterLab 2026・US500/USTECH/SPX） | 棄却: 古典窓と前倒し窓の差は見えない |
| [two-month-live-vs-random](./two-month-live-vs-random) | Q144 2か月の成績はランダム売買の分布のどこに入るか、順位は次の2か月で入れ替わるか（15銘柄・TSMOM20） | — |
| [usdjpy-london-open-vs-naive-momentum](./usdjpy-london-open-vs-naive-momentum) | USDJPY の日中順張りは、ロンドン開始30分の時刻条件つきシグナルでのみ効くか | README の「主な検証」表を参照 |
| [ustech-btc-leadlag](./ustech-btc-leadlag) | Q213 USTECH の直前 1 時間のリターンは BTC の次の 1 時間を予測するか（リード・ラグ・2020 年以降・H1） | 棄却 |
| [variance-ratio-setting-dependence](./variance-ratio-setting-dependence) | Q148 弱い形の効率性の検定（分散比）の結論は、設定（q・期間）でどれだけ動くか（Alahmadi・Basingab 2026 §3.5） | 1年の日足では分散比検定そのものがほとんど棄却しない（名目 5% 以下）。「1つの q で非効率と出ても他の q では… |
| [vol-asymmetry-by-group](./vol-asymmetry-by-group) | Q247 ボラの非対称性の向きは群で違うか（株価指数は負・金は正・FX は無し。HAR に符号項・15 銘柄） | … |
| [vol-change-reversal](./vol-change-reversal) | Q174 ボラの変化は1日逆張りの翌日リターンを予測するか（DellaCorte 2015-3・15銘柄） | 棄却 |
| [vol-forecast-loss-vs-model](./vol-forecast-loss-vs-model) | Q187 為替のボラ予測で損失関数の差はモデルの差の何倍に見えるか（Tokajuk 2026-1 の為替移植） | 棄却（H0 支持: 為替では損失関数の差はモデルの差より小さい・Tokajuk の構図は為替で再現しない） |
| [vol-regime-trend-following](./vol-regime-trend-following) | Q142 高ボラ局面では順張りの的中率と純損益が下がるか（15銘柄・GARCH なしの実現ボラ） | 未確定（事後発見の向きは4通り一致、大きさは半期では届かず・全期間は2/4 で ／z／≥2・主に XAUUSD と v… |
| [vol-targeting-tsmom](./vol-targeting-tsmom) | Q205 ボラ・ターゲティング（σ60 で規模調整）は 15 銘柄の日足順張りの年ごとのシャープを上げるか（Harvey ほか 2018 の追試） | 支持（確定・事前登録どおり） |
| [volume-confirmed-breakout](./volume-confirmed-breakout) | Q235 ティック出来高の急増つきドンチャン・ブレイクアウトは、継続率と純損益を上げるか（15 銘柄・H1 出来高から日足） | … |
| [volume-return-interaction](./volume-return-interaction) | Q216 出来高（ティック数）が多い日のリターンは翌日に続きやすく、少ない日は反転しやすいか（Campbell・Grossman・Wang 1993 の型・15 銘柄） | 棄却（CGW の型の反転は FX+コモディティ+指数の日足では前後半揃って再現しない） |
| [weekend-gap-fill-trend7](./weekend-gap-fill-trend7) | Q248 トレンド群（金・銀・原油 2・株価指数 2）の週末の窓は週内に埋まるか（Dao 2016 の FX 以外への条件の穴） | … |
| [weekly-vs-daily-tsmom](./weekly-vs-daily-tsmom) | Q186 週足の順張りは日足より強いか（Neely 2003-3・15銘柄・2008〜2026） | 棄却（前後半のどちらかで ／t／<2） |
| [window-pnl-vs-vol](./window-pnl-vs-vol) | Q184 2か月窓の順張り成績はその窓の実現ボラとドリフトで説明できるか（Rashid 2026-1・Q144 の続き） | Rashid の「ボラに左右される」は向きが違う |
| [wrc-spa-disagreement](./wrc-spa-disagreement) | Q154 WRC・SPA(consistent)・SPA(conservative) の判定は同じルール群でどれだけ割れるか | 確定（棄却） |
| [xauusd-vol-regime-single](./xauusd-vol-regime-single) | Q161 XAUUSD 単銘柄・直前20〜60日の実現ボラが高い日に翌日の順張り損益が下がるか（ドリフト除去・前後半） | 未確定（6/6 で向き一致・／z／≥2 達成は 3/6 で窓40・60日に偏る・ドリフト除去は結論を変えない） |
