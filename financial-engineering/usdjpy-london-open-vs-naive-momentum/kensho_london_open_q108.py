# -*- coding: utf-8 -*-
"""
検証キュー Q108: USDJPYの日中順張りの効きはロンドン開始30分の時刻条件の中だけにあるのか（矛盾の解消）
================================================================================

【出典】
- 計画: 検証/学問/金融工学/知識/文献/アイデア候補.md 2026-10-08 の行
  「USDJPYの日中順張りの効きはロンドン開始30分の時刻条件の中だけにあるのか（矛盾の解消）」（測る前の事前登録）。
- Seeck (2026) SSRN WP 7008318（検証/学問/金融工学/知識/文献/PDF/Seeck_2026_SSRN_Intraday_momentum_spot_FX_JPY_amplification.pdf）
  p4 3.2: "r1 = log(P_t1/P_t0), Signal = sign(r1) ... r_trade = sign(r1) × log(P_t2/P_t1), where P_t0 denotes the
  London Open price, P_t1 the price 30 minutes after London Open, and P_t2 the price at the selected intraday exit
  within the London-New York session."  p4 3.4: 出口時刻は IS(2012–2018) で選択（値は本文に無い）。
  p5 表1: USDJPY OOS β=0.000748 (t=5.21)、IS β=−0.000312 (t=−2.14, 逆向き)。p5 表2: USDJPY 往復1.47pips で OOS Sortino +0.748。
  p3 3.1: Dukascopy M5 bid、CET(Europe/Berlin)、出来高が直近20日中央値の10%未満の日を除外。
  ※ p6 5.3 では USDJPY β_IS=−0.000002, β_OOS=+0.000286 (t=2.57) と表1と食い違う（論文ノートの「限界」に既記）。
- 主張カード: Seeck2026-1（ロンドン開始30分の日中モメンタムは円の組で約3.8倍強く期間外でも有意）、
  Seeck2026-2（日中モメンタムはコスト後にUSDJPYだけが残った）、
  HiroAlgo2026-2（ARIMAはAR1・ナイーブ順張りと比べても優位性がなく3手法とも全条件で負ける。
  ナイーブ＝前バー上昇後に買い・下落後に売り、1バー保有。USDJPY 15分/1時間/4時間足 2023-07〜2026-08）。

【仮説（測る前に固定・アイデア候補.mdより）】
毎バーのナイーブ順張りはコスト込みで負ける（HiroAlgo2026-2）が、ロンドン開始30分の符号に1日1回だけ乗る
時刻条件つきシグナルは USDJPY でコスト後も正（Seeck2026-1/2）。同じ手元データ・同じ期間・同じコストで2本を並べる。

【データの制約への対応（測る前に決めた。アイデア候補の期間からの変更点）】
- 手元の data_USDJPY_M15_dukascopy.csv は 2021-01-04〜2026-07-14（BID・UTC・足の開始時刻、fetch_m15_dukascopy.py の docstring）。
  計画の「2019–2024 再現・2025-01〜2026-09 新規」は取れない。次のように置き換える:
  * 再現期間 = 2021-01-04〜2024-12-31。Seeck の期間外(2019–2024)の後ろ4年と重なり、データ源も同じ Dukascopy bid なので
    「独立の検証ではなく、Seeck の期間外の一部を M15 で再計算したもの」と位置づける（判定には使わず、向きの確認に使う）。
  * 新規期間（判定に使う） = 2025-01-01〜2026-07-14（データの末尾）。Seeck の標本（〜2024-12）と重ならない独立の期間。
    計画の終わり（2026-09）はデータが無いので末尾までに短縮。約18.5か月・約380営業日。
  * 2019–2020 は手元に無いため測らない（再現期間は計画より2年短い）。
- 頻度: Seeck は M5、手元は M15。ロンドン開始30分＝M15の2本でちょうど作れるので近似の誤差は出口の位置だけ。
- コスト: CSV は BID のみ（スプレッド列なし）→ 検証/学問/金融工学/CLAUDE.md「コストの扱い: 2段階」に従う。
  * 段階1: 往復 0 pips（粗利）と 往復 2 pips（片道1pip、保守的）の2本。
  * 段階2: 新規期間の主仕様で粗利の平均が 4 pips（保守的コストの2倍）を超えたときだけ、往復 0.5 / 1.0 pips の感度を出す。
  * 参考（判定に使わない）: Seeck の USDJPY 往復 1.47 pips での成績と Sortino（Seeck 表2 との比較用）。

【ルール（1通りに固定＝主仕様）】
A. ロンドン開始シグナル（1日1回）
  - ロンドン開始 = ロンドン現地 07:00（= CET 08:00、UTC 07:00 冬／06:00 夏。親タスクの指定と、Seeck が CET で時刻を揃えている点から）。
  - P0 = ロンドン開始の M15 足の始値、P1 = その次の足（開始+15分）の終値（= 開始+30分）、signal = sign(P1−P0)。
  - 出口 P2 = ロンドン現地 16:00 の価格（15:45 開始の足の終値）。Seeck の出口は「London-New York session 内」で IS で選ばれ値が不明。
    ロンドン市場の終わり（ロンドンとNYの重なりの終わり・WM/R 16:00 フィックス）を、IS を見ずに構造から1つ選んだ。
  - 取引の粗利（pips） = signal × (P2 − P1) / 0.01。signal=0 の日は取引なし。往復コストを1取引に1回引く。
  - 日の選別: ロンドン現地の平日。Seeck に合わせ、その日（ロンドン現地日付）の出来高合計が直前20営業日の中央値の10%未満の日を除く。
    P0・P1・P2 のどれかの足が無い日は除く（件数を出す）。
B. ナイーブ順張り（毎バー、HiroAlgo2026-2 の定義）
  - 各 M15 足 t について、前の足の終値変化 sign(C[t−1]−C[t−2]) の向きに C[t−1] で入り C[t] で出る（1バー保有）。
    3本が15分間隔で連続している足だけ使う（週末・欠けをまたがない）。符号0は取引なし。1取引ごとに往復コスト。
  - HiroAlgo の売買規則は「予測変化が直近96バーの中央スプレッドを超えたら入る」だが、手元にスプレッドが無いので
    毎バー入る素朴な版にする（ルール解釈の違いとして明記）。
  - t 値は日（UTC日付）ごとの損益の合計の系列で Newey-West 5ラグ（同じ日の取引の相関を束ねる）。

【棄却条件（事前固定・変更禁止。アイデア候補.mdの文言を期間だけ置き換え）】
新規期間（2025-01-01〜2026-07-14）の主仕様Aで、
  (i) 粗利の平均の t 値（Newey-West 5ラグ, Seeck に合わせる）が 2 未満、または
  (ii) 往復 2 pips（段階1の保守的コスト）を引いた後の平均が 0 以下
なら「時刻条件つきシグナルにも優位性なし」で棄却 → 判定「ノイズ」。
棄却されず、かつ再現期間（2021–2024）でも粗利の平均が正で t≥2 なら → 判定「確定（新規期間でも残る）」。
棄却されないが再現期間で t<2 または逆向きなら → 判定「未確定」。
再現期間の粗利の平均が Seeck と逆向き（負）なら、判定の前にルール解釈の違い（下の「解釈の違い」）を結果に書く。
ナイーブ順張りBは比較の対照で、同じ (i)(ii) を当てはめた結果を並べて出す（判定の対象は A）。
感度（開始時刻・出口の別の値）・時刻の偽薬・ナイーブの別定義は**記述のみ**で、判定に使わない。

【感度・記述（判定に使わない。多重比較の数に入れる）】
- 開始時刻: ロンドン現地 07:00（主）/ 08:00。出口: ロンドン 16:00（主）/ NY 12:00 / NY 17:00（NYの引け＝「その日の残り」）。計 2×3=6 通り。
  比較を6回すると |t|>2+log(6)≈3.8 程度でないと偶然と区別しにくい（改善判定「多重比較」の目安）。
- 時刻の偽薬: ロンドン現地 00:00〜23:00 の各正時を「開始」にして、同じ 30分の符号 → 8.5時間保有（主仕様と同じ長さ）の粗利。
  24通りの記述。ロンドン開始が他の時刻と比べて特別かを見る（|t|>2+log(24)≈5.2 が目安）。
- ナイーブ: 実体の向き sign(C[t−1]−O[t−1]) 版、ロンドン現地の時刻ごとの粗利。
- 地合い: 同じ保有区間をいつも買った場合の平均（ドリフト）と、OLS r = α + β·signal の β（Seeck の係数と同じ形, NW5）。

【解釈の違い（Seeck と比べて、測る前から分かっている点）】
M15 と M5／ロンドン開始の時刻（Seeck は CET で揃えたとだけ書き、開始の時刻を明記していない）／出口時刻（Seeck は IS で選択・値非公開）／
出来高フィルタの日付の切り方／2019–2020 が無い／Seeck の表1と5.3節で USDJPY の β が食い違う。

【捨てた案の数】
約8（このサブエージェントが設計で検討して捨てた案の概数）:
開始時刻の候補 2（ロンドン 08:00 を主にする案→感度へ）、出口の候補 4（ロンドン 12:00・NY 12:00・NY 17:00・翌日同時刻。
NY 12:00/17:00 は感度へ、ロンドン 12:00 と翌日同時刻は不採用）、ナイーブの定義 1（実体の向き→記述へ）、
期間の切り方 1（2021–2023／2024–2026 の二分割案）。判定に使うのは主仕様1本だけ。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。新規期間 2025-01〜2026-07-14 のうち 2026-06 以前（約17か月）は締め切りより前で、
ドル円の大まかな動き（2025年の円高局面など）を知っている可能性があり、後知恵を完全には排除できない。
締め切り以降の未知データは 2026-06〜2026-07-14 の約6週間（約30営業日）だけで、単独では判定に足りない（記述のみで別に出す）。
仮説そのもの（Seeck 2026-06 の論文）も締め切り直前の公表。

【委託の確かめ方】
この実行は Opus のサブエージェントが行った。結論ではなく、スクリプトのパス・数値・原典の箇所（Seeck p3–p6 の原文、
アイデア候補.md の該当行、HiroAlgo2026-2 の「結果」節）を本体（親セッション）に返し、本体が原典箇所と数値を照合してから記録する。

【実装】自己完結・決定的（乱数なし、同じCSVで同じ結果）。依存: python3 + pandas/numpy。
"""
import json, math, os, sys, datetime, unicodedata
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # ワークスペース


def _p(*parts):
    """macOS 共有の NFD 名に対応（NFC で無ければ NFD で探す）。"""
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


CSV = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード", "data_USDJPY_M15_dukascopy.csv")
OUT = os.path.join(HERE, "results")
PIP = 0.01
NW_L = 5
PERIODS = {
    "再現2021-2024": ("2021-01-01", "2025-01-01"),
    "新規2025-2026.07": ("2025-01-01", "2026-07-15"),
}
DESCR_PERIODS = {
    "全期間2021-2026.07": ("2021-01-01", "2026-07-15"),
    "締切後2026-06-01〜": ("2026-06-01", "2026-07-15"),
}
OPENS = {"LDN07": ("Europe/London", 7, 0), "LDN08": ("Europe/London", 8, 0)}
EXITS = {"LDN16": ("Europe/London", 16, 0), "NY12": ("America/New_York", 12, 0), "NY17": ("America/New_York", 17, 0)}
PRIMARY = ("LDN07", "LDN16")
COST_STAGE1 = [0.0, 2.0]
COST_STAGE2 = [0.5, 1.0]
COST_REF_SEECK = 1.47


# ---------------- 統計 ----------------
def nw_var_mean(x, L=NW_L):
    x = np.asarray(x, float); n = len(x)
    if n < 3:
        return float("nan")
    u = x - x.mean()
    v = (u @ u) / n
    for l in range(1, min(L, n - 1) + 1):
        v += 2 * (1 - l / (L + 1)) * (u[l:] @ u[:-l]) / n
    return v / n


def stats(x, L=NW_L):
    x = np.asarray(x, float); n = len(x)
    if n < 3:
        return dict(n=int(n))
    m = float(x.mean()); sd = float(x.std(ddof=1))
    se_iid = sd / math.sqrt(n); se_nw = math.sqrt(max(nw_var_mean(x, L), 1e-300))
    return dict(n=int(n), mean=m, sd=sd, t_iid=m / se_iid, t_nw=m / se_nw, win=float((x > 0).mean()))


def ols_hac(y, s, L=NW_L):
    y = np.asarray(y, float); X = np.column_stack([np.ones(len(y)), np.asarray(s, float)])
    XtX = np.linalg.inv(X.T @ X); b = XtX @ X.T @ y
    u = X * (y - X @ b)[:, None]; n = len(y)
    S = u.T @ u
    for l in range(1, L + 1):
        G = u[l:].T @ u[:-l]; S += (1 - l / (L + 1)) * (G + G.T)
    V = XtX @ S @ XtX
    return dict(alpha=float(b[0]), beta=float(b[1]), t_beta=float(b[1] / math.sqrt(V[1, 1])))


def sortino(x):
    x = np.asarray(x, float)
    dd = math.sqrt(np.mean(np.minimum(x, 0) ** 2))
    return float(x.mean() / dd * math.sqrt(252)) if dd > 0 else float("nan")


# ---------------- データ ----------------
def load():
    d = pd.read_csv(CSV)
    d["time"] = pd.to_datetime(d["time"])
    audit = dict(rows=int(len(d)), first=str(d["time"].min()), last=str(d["time"].max()),
                 dup_time=int(d["time"].duplicated().sum()),
                 non_monotonic=int((d["time"].diff().dt.total_seconds() <= 0).sum()),
                 nan_cells=int(d[["open", "high", "low", "close", "volume"]].isna().sum().sum()),
                 nonpositive_price=int((d[["open", "high", "low", "close"]] <= 0).sum().sum()),
                 ohlc_logic_bad=int(((d["high"] < d[["open", "close"]].max(axis=1)) |
                                     (d["low"] > d[["open", "close"]].min(axis=1))).sum()),
                 zero_volume_bars=int((d["volume"] <= 0).sum()),
                 max_abs_bar_move_pips=float(((d["close"] - d["open"]).abs() / PIP).max()))
    d = d.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d = d[d["volume"] > 0].reset_index(drop=True)
    return d, audit


def local_to_utc(dates, tz, hh, mm):
    """ロンドン現地の日付 dates（naive, 00:00）に tz の現地時刻 hh:mm を付けて UTC(naive) にする。"""
    t = (dates + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(tz, nonexistent="shift_forward", ambiguous=False)
    return t.tz_convert("UTC").tz_localize(None)


def daily_volume_filter(d):
    """ロンドン現地日付ごとの出来高合計。直前20営業日の中央値の10%未満の日を False。"""
    ld = d["time"].dt.tz_localize("UTC").dt.tz_convert("Europe/London").dt.tz_localize(None).dt.normalize()
    v = d.groupby(ld)["volume"].sum()
    v = v[v.index.dayofweek < 5]
    med = v.shift(1).rolling(20, min_periods=5).median()
    ok = (v >= 0.1 * med) | med.isna()
    return ok


# ---------------- A: ロンドン開始シグナル ----------------
def london_signal(d, ok_day, open_key, exit_key, anchor=None):
    O = d.set_index("time")["open"]; C = d.set_index("time")["close"]
    days = ok_day.index[ok_day.values]
    days_all = ok_day.index
    if anchor is None:
        tz, hh, mm = OPENS[open_key]
        t0 = local_to_utc(days, tz, hh, mm)
        etz, eh, em = EXITS[exit_key]
        t2bar = local_to_utc(days, etz, eh, em) - pd.Timedelta(minutes=15)
    else:  # 偽薬: ロンドン現地 anchor 時の30分 → 8.5時間保有
        t0 = local_to_utc(days, "Europe/London", anchor, 0)
        t2bar = t0 + pd.Timedelta(minutes=30) + pd.Timedelta(hours=8, minutes=30) - pd.Timedelta(minutes=15)
    t1bar = t0 + pd.Timedelta(minutes=15)
    p0 = O.reindex(t0).values; p1 = C.reindex(t1bar).values; p2 = C.reindex(t2bar).values
    df = pd.DataFrame(dict(day=days, t0=t0, p0=p0, p1=p1, p2=p2))
    n_missing = int(df[["p0", "p1", "p2"]].isna().any(axis=1).sum())
    df = df.dropna().copy()
    df["sig"] = np.sign(df["p1"] - df["p0"])
    df["fwd_pips"] = (df["p2"] - df["p1"]) / PIP
    df["fwd_log"] = np.log(df["p2"] / df["p1"])
    df = df[df["sig"] != 0].copy()
    df["gross"] = df["sig"] * df["fwd_pips"]
    meta = dict(days_total=int(len(days_all)), days_vol_filtered_out=int((~ok_day).sum()),
                days_missing_bar=n_missing)
    return df, meta


def summarize_A(df, start, end, costs):
    s = df[(df["day"] >= start) & (df["day"] < end)]
    if len(s) < 3:
        return dict(n=int(len(s)))
    out = dict(n_trades=int(len(s)), long_share=float((s["sig"] > 0).mean()))
    for c in costs:
        out[f"cost{c:g}"] = stats(s["gross"].values - c)
    out["drift_always_long_pips"] = stats(s["fwd_pips"].values)
    out["ols_log"] = ols_hac(s["fwd_log"].values, s["sig"].values)
    out["ols_pips"] = ols_hac(s["fwd_pips"].values, s["sig"].values)
    out["sortino_cost1.47_ref"] = sortino(s["gross"].values - COST_REF_SEECK)
    out["sortino_cost0"] = sortino(s["gross"].values)
    return out


# ---------------- B: ナイーブ順張り ----------------
def naive(d, body=False):
    t = d["time"]; c = d["close"].values; o = d["open"].values
    gap1 = (t.diff().dt.total_seconds() == 900).values
    ok = gap1 & np.roll(gap1, 1)
    ok[:2] = False
    prev = np.r_[np.nan, np.nan, (c[1:-1] - o[1:-1]) if body else (c[1:-1] - c[:-2])]
    sig = np.sign(prev)
    r = np.r_[np.nan, (c[1:] - c[:-1]) / PIP]
    m = ok & (sig != 0) & ~np.isnan(sig)
    out = pd.DataFrame(dict(time=t[m].values, sig=sig[m], gross=sig[m] * r[m]))
    out["udate"] = out["time"].dt.normalize()
    out["lhour"] = out["time"].dt.tz_localize("UTC").dt.tz_convert("Europe/London").dt.hour
    return out


def summarize_B(nv, start, end, costs):
    s = nv[(nv["time"] >= start) & (nv["time"] < end)]
    g = s.groupby("udate")["gross"].agg(["sum", "count"])
    out = dict(n_trades=int(len(s)), n_days=int(len(g)), trades_per_day=float(g["count"].mean()))
    for c in costs:
        daily = g["sum"].values - c * g["count"].values
        st = stats(daily)
        out[f"cost{c:g}"] = dict(mean_per_trade_pips=float(daily.sum() / g["count"].sum()),
                                  daily_sum_mean_pips=st["mean"], t_nw_daily=st["t_nw"], t_iid_daily=st["t_iid"],
                                  win_per_trade=float(((s["gross"].values - c) > 0).mean()))
    return out


def verdict_rule(new, rep, costkey_cons="cost2"):
    t_new = new["cost0"]["t_nw"]; net_new = new[costkey_cons]["mean"]
    rejected = (t_new < 2) or (net_new <= 0)
    rep_ok = (rep["cost0"]["mean"] > 0) and (rep["cost0"]["t_nw"] >= 2)
    if rejected:
        v = "ノイズ（棄却: 時刻条件つきシグナルにも優位性なし）"
    elif rep_ok:
        v = "確定（新規期間でも残る）"
    else:
        v = "未確定"
    return dict(t_new_gross_nw=t_new, net2_new_mean=net_new, cond_i_t_lt2=bool(t_new < 2),
                cond_ii_net2_le0=bool(net_new <= 0), rejected=bool(rejected),
                replication_gross_pos_t_ge2=bool(rep_ok),
                replication_opposite_to_seeck=bool(rep["cost0"]["mean"] < 0), verdict=v)


def main():
    d, audit = load()
    ok_day = daily_volume_filter(d)
    res = dict(task="Q108", csv=CSV, audit=audit, periods=PERIODS, descr_periods=DESCR_PERIODS,
               primary=dict(open=PRIMARY[0], exit=PRIMARY[1]), nw_lags=NW_L)

    # A 主仕様 + 感度
    A = {}
    for ok_ in OPENS:
        for ek in EXITS:
            df, meta = london_signal(d, ok_day, ok_, ek)
            key = f"{ok_}->{ek}"
            A[key] = dict(meta=meta)
            for pn, (a, b) in {**PERIODS, **DESCR_PERIODS}.items():
                A[key][pn] = summarize_A(df, a, b, COST_STAGE1)
            if (ok_, ek) == PRIMARY:
                prim_df = df
    res["A_london_open"] = A
    P = A[f"{PRIMARY[0]}->{PRIMARY[1]}"]
    newk, repk = "新規2025-2026.07", "再現2021-2024"

    # 段階2（主仕様の新規期間で粗利平均 > 4 pips のときだけ）
    g_new = P[newk]["cost0"]["mean"]
    res["stage2_triggered"] = bool(g_new > 4.0)
    if g_new > 4.0:
        res["stage2"] = {pn: summarize_A(prim_df, a, b, COST_STAGE2) for pn, (a, b) in PERIODS.items()}

    # 参考: Seeck のコスト 1.47
    res["ref_seeck_cost1.47"] = {pn: stats(prim_df[(prim_df.day >= a) & (prim_df.day < b)]["gross"].values - COST_REF_SEECK)
                                 for pn, (a, b) in PERIODS.items()}

    # 判定（主仕様のみ）
    res["verdict_A"] = verdict_rule(P[newk], P[repk])

    # 偽薬: 開始時刻を 0〜23時（ロンドン現地）に動かす。8.5時間保有。
    plac = {}
    for h in range(24):
        df, meta = london_signal(d, ok_day, None, None, anchor=h)
        plac[h] = {pn: (lambda s: dict(n=int(len(s)), mean=float(s.mean()) if len(s) else None,
                                        t_nw=stats(s.values).get("t_nw")))(df[(df.day >= a) & (df.day < b)]["gross"])
                   for pn, (a, b) in {**PERIODS, "全期間2021-2026.07": DESCR_PERIODS["全期間2021-2026.07"]}.items()}
    res["placebo_anchor_hour_8h30"] = plac

    # B ナイーブ
    nv = naive(d); nvb = naive(d, body=True)
    B = {pn: summarize_B(nv, a, b, COST_STAGE1) for pn, (a, b) in {**PERIODS, **DESCR_PERIODS}.items()}
    Bb = {pn: summarize_B(nvb, a, b, COST_STAGE1) for pn, (a, b) in PERIODS.items()}
    res["B_naive_close2close"] = B
    res["B_naive_body_descr"] = Bb
    # B に同じ (i)(ii) を当てはめる（対照）
    bn = B[newk]
    res["verdict_B_same_rule"] = dict(t_new_gross_nw=bn["cost0"]["t_nw_daily"],
                                      net2_new_per_trade=bn["cost2"]["mean_per_trade_pips"],
                                      rejected=bool(bn["cost0"]["t_nw_daily"] < 2 or bn["cost2"]["mean_per_trade_pips"] <= 0))
    # ナイーブのロンドン時刻別（全期間、粗利/取引）
    hh = nv.groupby("lhour")["gross"].agg(["mean", "count"])
    res["B_naive_by_london_hour_all"] = {int(k): dict(mean_pips=float(v["mean"]), n=int(v["count"])) for k, v in hh.iterrows()}

    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fp = os.path.join(OUT, f"Q108_result_{stamp}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    # 日ごとの取引（主仕様）も保存
    prim_df.to_csv(os.path.join(OUT, f"Q108_primary_trades_{stamp}.csv"), index=False)

    # ---- 表示 ----
    print("audit:", audit)
    print("primary meta:", P["meta"])
    for pn in list(PERIODS) + list(DESCR_PERIODS):
        x = P[pn]
        if "cost0" not in x:
            print(pn, x); continue
        print(f"[A {PRIMARY}] {pn}: n={x['n_trades']} long={x['long_share']:.2f} gross={x['cost0']['mean']:+.2f}p "
              f"t_nw={x['cost0']['t_nw']:+.2f} t_iid={x['cost0']['t_iid']:+.2f} net2={x['cost2']['mean']:+.2f}p "
              f"(t_nw {x['cost2']['t_nw']:+.2f}) win={x['cost0']['win']:.3f} beta_log={x['ols_log']['beta']:+.6f} "
              f"(t {x['ols_log']['t_beta']:+.2f}) drift={x['drift_always_long_pips']['mean']:+.2f}p sortino1.47={x['sortino_cost1.47_ref']:+.3f}")
    for k, v in A.items():
        print("  sens", k, {pn: (round(v[pn]['cost0']['mean'], 2), round(v[pn]['cost0']['t_nw'], 2), round(v[pn]['cost2']['mean'], 2))
                           for pn in PERIODS})
    print("stage2_triggered:", res["stage2_triggered"])
    print("ref seeck 1.47:", {k: (round(v['mean'], 2), round(v['t_nw'], 2)) for k, v in res["ref_seeck_cost1.47"].items()})
    print("VERDICT A:", res["verdict_A"])
    for pn in list(PERIODS) + list(DESCR_PERIODS):
        x = B[pn]
        print(f"[B naive] {pn}: n={x['n_trades']} gross/trade={x['cost0']['mean_per_trade_pips']:+.4f}p "
              f"t_nw(daily)={x['cost0']['t_nw_daily']:+.2f} net2/trade={x['cost2']['mean_per_trade_pips']:+.4f}p "
              f"(t {x['cost2']['t_nw_daily']:+.2f}) win_gross={x['cost0']['win_per_trade']:.3f}")
    for pn in PERIODS:
        x = Bb[pn]
        print(f"[B body] {pn}: gross/trade={x['cost0']['mean_per_trade_pips']:+.4f}p t={x['cost0']['t_nw_daily']:+.2f}")
    print("VERDICT B (same rule):", res["verdict_B_same_rule"])
    print("placebo (all period) hour: mean pips / t_nw")
    for h in range(24):
        v = plac[h]["全期間2021-2026.07"]
        print(f"  {h:02d}: n={v['n']} {v['mean']:+.2f} t={v['t_nw']:+.2f} | rep {plac[h][repk]['mean']:+.2f} ({plac[h][repk]['t_nw']:+.2f}) "
              f"new {plac[h][newk]['mean']:+.2f} ({plac[h][newk]['t_nw']:+.2f})")
    print("naive by london hour:", {k: round(v['mean_pips'], 3) for k, v in res["B_naive_by_london_hour_all"].items()})
    print("saved:", fp)


if __name__ == "__main__":
    main()


# 【事後の点検（2026-10-08 実行後に追記。事前登録・判定は変えていない）】
# - データの穴: M15 CSV は平日の15分足の約17%が欠けている（1時間単位の塊で 5,767 時間分・23,059 本）。
#   欠けた時間の 96.7% は H1 CSV（data_USDJPY_H1_dukascopy.csv）には存在する → 取得の失敗（失敗パターン集 2026-09-30 と同じ型）。
#   欠けはロンドン時刻ごとに 81.7〜84.8% の在庫率でほぼ一様、年では 2023 年が最も多い（在庫 77.3%）。
#   そのため主仕様は 1,427 営業日のうち 382 日が「足が無い」で落ち、再現 731 取引・新規 289 取引になった。
#   欠けが時刻・値動きと無関係なら平均は偏らず検出力だけが下がる。M15 の穴埋め（再取得）をすれば n は約1.2倍になる。
# - 検出力: 新規期間の粗利の標準誤差は NW で 3.27 pips（95%区間 −6.55〜+6.26）。Seeck 表1 の β=0.000748 は
#   約 9.7 pips（130円換算）で検出できる大きさ、5.3節の β=0.000286（約 3.7 pips）は検出できない大きさ。
# - 実行結果: results/Q108_result_20261008_063704.json、主仕様の日ごとの取引 results/Q108_primary_trades_20261008_063704.csv
