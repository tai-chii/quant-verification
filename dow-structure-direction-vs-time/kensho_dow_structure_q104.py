# -*- coding: utf-8 -*-
"""
検証キュー Q104: ダウ型の構造確定の後の24時間の上がり方は向きの情報か、時刻と地合いか（矛盾の解消）
================================================================================

【出典】
- ブログ hiro_algo (Zenn 2026) https://zenn.dev/hiro_algo/articles/fx-dow-theory-test
  USDJPY 1時間足 2023-01〜2026-08: 上昇構造確定 517件 → 24h後 平均 +12.19pips（普通に買うより +9.18）、
  下降構造確定 516件 → 売りの向きに調整して −9.06pips（＝価格は +9.06pips 上がった）。
- 計画: vault/45_金融工学/文献/アイデア候補.md 2026-10-08 の3件目の行（測る前の事前登録。下に要点を転記）。
  出典はブログなので、結果は論文の出口の根拠には使わない。

【仮説（測る前に固定・アイデア候補.mdより）】
「上昇構造の後は続く・下降構造の後は逆に上がる」を、
  D = 上昇構造後 − 下降構造後（価格の向き。向きの情報）
  M = 両者の平均 − 同じUTC時刻・同じ年に始まる全24時間リターンの平均（向きに依らない部分）
に分ける。
- データ: Dukascopy H1 8通貨（USDJPY・EURJPY・GBPJPY・EURUSD・GBPUSD・AUDUSD・USDCAD・USDCHF）2015-01〜2026-06。
  ※ EURJPY のCSVは 2026-03-31 までしかないため、EURJPY の後半は 2021-01〜2026-03 で3か月短い。
- ルール（1通りだけ）: 左右2本の山谷・右2本の完成で確定・高値と安値の両方の切り上げ／切り下げで構造確定・片方だけは保留。
- 事象＝構造の転換の確定、起点＝次足の始値、結果＝24時間後までの対数リターン(bp)。
- 先に USDJPY 2023-01〜2026-06 でブログの向き（上昇後＋・下降後も価格は上）を再現。
- 8通貨×前半2015–2020／後半2021–2026 の16組。24時間の重なりは Newey-West 24ラグ。Holm補正。
- コストは測らない（合図の中身の分解で、売買ルールではない）。検証の鉄則の「コスト込み」は本設計では対象外。

【棄却条件（事前固定・変更禁止）】
USDJPY で D の区間が0を含み、かつ時刻をそろえた M が両期間で |t|<2 なら「向きの情報なし」＝カードの読みを棄却。
D>0 が補正後に USDJPY の両期間で有意かつ8通貨中5以上で同符号なら「向きの情報あり」＝カードの読みを支持。
それ以外は未確定。USDJPY 2023–2026 でブログの向きが再現しなければ、ルールの解釈の違いを書いてから進める。

【捨てた案の数】
0（親タスクから事前登録済みの計画をそのまま実施。設計上の案の取捨選択はこのサブエージェント実行では発生していない）。

【知識の締め切り】
Claude の知識の締め切りはおよそ2026-06。検証期間は2015-01〜2026-06で締め切り直前まで含むため、
締め切り以降の未知データでの検証ではない（後知恵バイアスを完全には排除できない）。

【委託の確かめ方】
本タスクはサブエージェント（Opus）が実行。結論だけでなく、変更/作成したファイルパス・主要な数値・
アイデア候補.md該当行の原文該当箇所を本体（親エージェント）に返し、親が照合する。

【実装の細部（測る前に決めた機械化。事前ルールの変更ではない）】
1. 前処理: Dukascopy CSV は週末・休場時間を volume=0 のフラット足で埋めているので、volume==0 の足を除く
   （ブログのMT5データと同じく「取引のある足だけ」の列にする）。「24時間後」＝この列で24本先。
2. 山: h[i] が左右2本（i-2,i-1,i+1,i+2）の高値より厳密に高い。谷: l[i] が左右2本の安値より厳密に低い。
   山谷は i+2 の足が完成した時点で初めて判明（先読みなし）。
3. 構造: 判明済みの直近2つの山 (H_prev,H_last) と直近2つの谷 (L_prev,L_last) で、
   H_last>H_prev かつ L_last>L_prev → 上昇構造、H_last<H_prev かつ L_last<L_prev → 下降構造、
   それ以外（片方だけ）→ 前の構造を保留。
   構造の判定は i+2 の足（山谷の確定足）の完成時点で行い、構造が変わった足を「確定足」とする。
4. 事象＝上昇→下降、下降→上昇の転換（最初の構造の発生は除く）。起点＝確定足の次の足の始値 O[k+1]、
   結果＝ r = 1e4*ln(O[k+1+24]/O[k+1]) (bp)。期間の割当は起点の時刻で行う。
5. 基準（時刻をそろえる）: 同じ通貨の全ての足 j について r_all[j]=1e4*ln(O[j+24]/O[j]) を作り、
   (UTC年, UTC時) ごとの平均を基準 b とする。事象ごとの超過 e = r − b(年,時)。
   M = (mean(e|上昇) + mean(e|下降))/2。D = mean(r|上昇) − mean(r|下降)（価格の向き）。
6. 推定: r = a + D*up の OLS（up=1/0）、e = c0 + c1*up で M = c0 + c1/2。分散は Newey-West
   （事象を足の番号の上に置き、番号の差 d≤24 の組に Bartlett 重み 1−d/25 を掛ける HAC）。
   感度として UTC 日付でのクラスタ頑健SEも併記。p値は正規近似（両側）。
7. Holm: D の16組（8通貨×2期間）の両側p値に Holm（族ごと有意水準5%）。M の16組にも参考で併記。
8. 判定の機械化:
   - 「USDJPYでDの区間が0を含み」＝USDJPY 前半・後半の両方で D の95%区間（NW, 補正なし）が0を含む。
   - 「Mが両期間で|t|<2」＝USDJPY 前半・後半の M の NW t 値がともに |t|<2。
   - 「D>0が補正後にUSDJPYの両期間で有意」＝USDJPY 前半・後半とも D>0 かつ Holm 補正後 p<0.05。
   - 「8通貨中5以上で同符号」＝ D>0 の通貨数。主の数え方は「前半・後半の両方で D>0 の通貨数」、
     参考に「全期間(2015–2026)をまとめた D>0 の通貨数」も出す。両者が5の境をまたいだら未確定側に倒す。
   決定的（乱数なし、同じCSVで同じ結果）。
"""
import json, math, os, sys, datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # ワークスペース
DATA_DIR = os.path.join(WS, "vault", "40_市場", "FX", "システムトレード")
PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF"]
PERIODS = {"前半2015-2020": ("2015-01-01", "2021-01-01"), "後半2021-2026": ("2021-01-01", "2026-07-01")}
H = 24
NW_L = 24
PIP = {"JPY": 0.01}


def load(pair):
    p = os.path.join(DATA_DIR, f"data_{pair}_H1_dukascopy.csv")
    d = pd.read_csv(p, parse_dates=["time"])
    d = d[d["volume"] > 0].reset_index(drop=True)
    return d


def find_events(d):
    h = d["high"].values; l = d["low"].values; n = len(d)
    # 山谷（i で発生、i+2 の完成で判明）
    sh = np.zeros(n, bool); sl = np.zeros(n, bool)
    for i in range(2, n - 2):
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            sh[i] = True
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            sl[i] = True
    highs = []; lows = []; state = 0
    ev = []  # (k=確定足, dir)
    for k in range(4, n):
        i = k - 2  # この足 k の完成で i の山谷が判明
        changed = False
        if sh[i]:
            highs.append(h[i]); changed = True
        if sl[i]:
            lows.append(l[i]); changed = True
        if not changed or len(highs) < 2 or len(lows) < 2:
            continue
        up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
        dn = highs[-1] < highs[-2] and lows[-1] < lows[-2]
        new = 1 if up else (-1 if dn else state)
        if new != state:
            if state != 0:
                ev.append((k, new))
            state = new
    return ev


def build(pair):
    d = load(pair)
    o = d["open"].values; n = len(d)
    r_all = np.full(n, np.nan)
    r_all[:n-H] = 1e4 * np.log(o[H:] / o[:n-H])
    d["r"] = r_all
    d["yr"] = d["time"].dt.year; d["hr"] = d["time"].dt.hour
    base = d.groupby(["yr", "hr"])["r"].mean()
    ev = find_events(d)
    rows = []
    for k, dr in ev:
        j = k + 1
        if j + H >= n:
            continue
        t = d["time"].iat[j]
        r = r_all[j]
        b = base.loc[(t.year, t.hour)]
        rows.append(dict(idx=j, time=t, up=int(dr == 1), r=r, e=r - b, b=b,
                         r_price=(o[j+H] - o[j])))
    return d, pd.DataFrame(rows)


def hac_ols(y, X, idx, L=NW_L, clusters=None):
    y = np.asarray(y, float); X = np.asarray(X, float); idx = np.asarray(idx)
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = X * (y - X @ beta)[:, None]
    if clusters is not None:
        S = np.zeros((X.shape[1],) * 2)
        for g in pd.unique(clusters):
            s = u[clusters == g].sum(0); S += np.outer(s, s)
    else:
        S = u.T @ u
        order = np.argsort(idx); u2 = u[order]; ix = idx[order]
        m = len(ix)
        for a in range(m):
            b = a + 1
            while b < m and ix[b] - ix[a] <= L:
                w = 1 - (ix[b] - ix[a]) / (L + 1)
                S += w * (np.outer(u2[a], u2[b]) + np.outer(u2[b], u2[a]))
                b += 1
    V = XtX_inv @ S @ XtX_inv
    return beta, V


def ptwo(t):
    return math.erfc(abs(t) / math.sqrt(2))


def contrast(beta, V, c):
    c = np.asarray(c, float); est = float(c @ beta); se = float(math.sqrt(c @ V @ c))
    t = est / se
    return dict(est=est, se=se, t=t, p=ptwo(t), ci95=[est - 1.96 * se, est + 1.96 * se])


def analyze(ev, start, end):
    s = ev[(ev["time"] >= start) & (ev["time"] < end)]
    X = np.column_stack([np.ones(len(s)), s["up"].values])
    out = dict(n_up=int(s["up"].sum()), n_down=int((1 - s["up"]).sum()),
               mean_r_up=float(s.loc[s.up == 1, "r"].mean()), mean_r_down=float(s.loc[s.up == 0, "r"].mean()),
               mean_e_up=float(s.loc[s.up == 1, "e"].mean()), mean_e_down=float(s.loc[s.up == 0, "e"].mean()))
    cl = s["time"].dt.strftime("%Y-%m-%d").values
    for name, cl_ in (("NW24", None), ("day_cluster", cl)):
        bR, VR = hac_ols(s["r"].values, X, s["idx"].values, clusters=cl_)
        bE, VE = hac_ols(s["e"].values, X, s["idx"].values, clusters=cl_)
        out[name] = dict(D=contrast(bR, VR, [0, 1]), M=contrast(bE, VE, [1, 0.5]),
                         D_excess=contrast(bE, VE, [0, 1]))
    return out


def holm(ps):
    m = len(ps); order = np.argsort(ps); adj = np.empty(m); run = 0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i])); adj[i] = run
    return adj


def main():
    res = dict(meta=dict(queue="Q104", script=os.path.basename(__file__),
                         run_at=datetime.datetime.now().isoformat(timespec="seconds"),
                         horizon_bars=H, nw_lags=NW_L, units="bp (1e4*log return)",
                         note_EURJPY="EURJPY CSV ends 2026-03-31; 後半 is 2021-01..2026-03 only"),
               pairs={})
    events_all = {}
    for p in PAIRS:
        d, ev = build(p)
        events_all[p] = (d, ev)
        res["pairs"][p] = dict(data_end=str(d["time"].iat[-1]), n_events_total=len(ev))
        for pn, (a, b) in PERIODS.items():
            res["pairs"][p][pn] = analyze(ev, pd.Timestamp(a), pd.Timestamp(b))
        res["pairs"][p]["全期間2015-2026"] = analyze(ev, pd.Timestamp("2015-01-01"), pd.Timestamp("2026-07-01"))
        print(p, "done", len(ev), file=sys.stderr)

    # --- USDJPY 再現（2023-01〜2026-06）
    d, ev = events_all["USDJPY"]
    a, b = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-07-01")
    s = ev[(ev.time >= a) & (ev.time < b)]
    allr = d[(d.time >= a) & (d.time < b)]["r"].dropna()
    allp = (d["open"].shift(-H) - d["open"])[(d.time >= a) & (d.time < b)].dropna()
    up = s[s.up == 1]; dn = s[s.up == 0]
    rep = dict(period="2023-01..2026-06", n_up=len(up), n_down=len(dn),
               up_mean_pips=float(up.r_price.mean() / 0.01), down_mean_pips_price=float(dn.r_price.mean() / 0.01),
               all_bars_mean_pips=float(allp.mean() / 0.01),
               up_minus_all_pips=float(up.r_price.mean() / 0.01 - allp.mean() / 0.01),
               down_sellside_minus_allsell_pips=float(-dn.r_price.mean() / 0.01 + allp.mean() / 0.01),
               up_mean_bp=float(up.r.mean()), down_mean_bp=float(dn.r.mean()), all_bars_mean_bp=float(allr.mean()),
               blog=dict(n_up=517, n_down=516, up_mean_pips=12.19, up_vs_buy=9.18,
                         down_sellside_pips=-9.06, down_vs_sell=-6.06, period="2023-01..2026-08"),
               detail=analyze(ev, a, b))
    rep["reproduced"] = bool(rep["up_minus_all_pips"] > 0 and rep["down_mean_pips_price"] > 0)
    res["usdjpy_replication"] = rep

    # --- Holm
    keys = [(p, pn) for p in PAIRS for pn in PERIODS]
    for which in ("D", "M"):
        ps = np.array([res["pairs"][p][pn]["NW24"][which]["p"] for p, pn in keys])
        adj = holm(ps)
        for (p, pn), q in zip(keys, adj):
            res["pairs"][p][pn]["NW24"][which]["p_holm16"] = float(q)

    # --- 判定
    U = res["pairs"]["USDJPY"]; P1, P2 = list(PERIODS)
    d_ci_has0 = all(U[pn]["NW24"]["D"]["ci95"][0] <= 0 <= U[pn]["NW24"]["D"]["ci95"][1] for pn in PERIODS)
    m_small = all(abs(U[pn]["NW24"]["M"]["t"]) < 2 for pn in PERIODS)
    d_sig_pos = all(U[pn]["NW24"]["D"]["est"] > 0 and U[pn]["NW24"]["D"]["p_holm16"] < 0.05 for pn in PERIODS)
    n_pos_both = sum(all(res["pairs"][p][pn]["NW24"]["D"]["est"] > 0 for pn in PERIODS) for p in PAIRS)
    n_pos_full = sum(res["pairs"][p]["全期間2015-2026"]["NW24"]["D"]["est"] > 0 for p in PAIRS)
    n_neg_both = sum(all(res["pairs"][p][pn]["NW24"]["D"]["est"] < 0 for pn in PERIODS) for p in PAIRS)
    reject = d_ci_has0 and m_small
    support = d_sig_pos and n_pos_both >= 5 and n_pos_full >= 5
    verdict = "棄却（向きの情報なし）" if reject else ("支持（向きの情報あり）" if support else "未確定")
    res["judgement"] = dict(usdjpy_D_ci_contains0_both=d_ci_has0, usdjpy_M_abs_t_lt2_both=m_small,
                            usdjpy_D_pos_sig_holm_both=d_sig_pos, n_pairs_D_pos_both_periods=n_pos_both,
                            n_pairs_D_pos_full_period=n_pos_full, n_pairs_D_neg_both_periods=n_neg_both,
                            verdict=verdict)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(HERE, "results", f"Q104_result_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    # 要約の表示
    print("USDJPY再現:", json.dumps({k: v for k, v in rep.items() if k != "detail"}, ensure_ascii=False, default=str))
    print(f"{'pair':7s} {'period':14s} {'nU':>5s} {'nD':>5s} {'rU':>7s} {'rD':>7s} {'D':>7s} {'tD':>6s} {'pHolm':>6s} {'M':>7s} {'tM':>6s} | {'tD_day':>6s} {'tM_day':>6s}")
    for p in PAIRS:
        for pn in list(PERIODS) + ["全期間2015-2026"]:
            x = res["pairs"][p][pn]; nw = x["NW24"]; dc = x["day_cluster"]
            print(f"{p:7s} {pn:14s} {x['n_up']:5d} {x['n_down']:5d} {x['mean_r_up']:7.2f} {x['mean_r_down']:7.2f} "
                  f"{nw['D']['est']:7.2f} {nw['D']['t']:6.2f} {nw['D'].get('p_holm16', float('nan')):6.3f} "
                  f"{nw['M']['est']:7.2f} {nw['M']['t']:6.2f} | {dc['D']['t']:6.2f} {dc['M']['t']:6.2f}")
    print("判定:", json.dumps(res["judgement"], ensure_ascii=False))
    print("saved", out)


if __name__ == "__main__":
    main()
