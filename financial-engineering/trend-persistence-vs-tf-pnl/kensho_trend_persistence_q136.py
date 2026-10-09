#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q136: トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか
（Takahashi・Mizuta・Yagi 2026 の「今後の課題③」を実データで・15銘柄 D1）
================================================================================

【出典】
- 計画（事前登録）: 検証/学問/金融工学/知識/文献/アイデア候補.md 2026-10-09 の1件目
  「トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか」。
- 論文ノート: 検証/学問/金融工学/知識/文献/論文ノート/
  Takahashi・Mizuta・Yagi2026_順張り投資家が増えると市場のトレンドと順張りの収益はどう変わるか.md
  （人工知能学会 SIG-FIN-037、PDF/Takahashi_Mizuta_Yagi_2026_SIG-FIN-037_trendfollow_ABS.pdf）
  人工市場で、市場のテクニカル成分（過去の値動きが同じ向きの注文を呼ぶ度合い）が強いと順張りが儲かり、
  弱いと損失が縮むだけ。§6 の今後の課題③: 「現実の市場のデータで、観察された収益性とトレンド特性の関係が
  現れるかの検証」＝本スクリプトの問い。
- 既存の知見（この問いの背景）:
  * 為替の日足テクニカルは 2016 年以降も補正後に有意なルールが 0 本（Q019・Q054）
  * ドンチャン 55/20 の多レジーム: FX8 は OOS で有意にマイナス、トレンド群はドリフトのシャッフルと区別できず、
    BTC だけ残る（FX改善ログ 2026-10-02(4)・(5)、2026-10-03）
  → 「順張りが効く銘柄・時期と効かない銘柄・時期の差を、トレンドの持続時間という1つの量で説明できるか」が本検証。

【仮説（測る前に固定）】
H1（説明）: 銘柄×半年の組で、トレンドの持続時間 D が長いほど、同じ組の順張りの純損益 P が大きい。
H2（予測）: 前の半年の D が長いほど、次の半年の P が大きい。前の半年の D で順張りの可否を決めると、無条件より純損益が良い。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（補修済み Dukascopy H1 から作った UTC 日足。
kensho_donchian_regime.py が生成。列: time,open,high,low,close）。15銘柄 = FX8 + トレンド群7。2008-02〜2026-07。
値動きのない足（high==low）は除く。欠損・重複の点検は作成時に済み（FX改善ログ 2026-10-02）。

【定義（1通りに固定）】
- 日次対数リターン r_t = ln(c_t / c_{t-1})。
- 組 = 銘柄 × 暦の半年（1〜6月 / 7〜12月、UTC 日付）。日数が MIN_DAYS=100 未満の組は捨てる（端の半年）。
- 持続時間 D = 組の中で、r_t の符号（0 は除く）が同じ値で連続する「連」の長さの平均（日）。
  独立で対称なら E[D]=2。これが Takahashi ほかの「トレンドの持続時間」に対応させた観測量（主）。
- 副（判定に使わない）: 分散比 VR10 = Var(10日リターン) / (10 × Var(1日リターン))。>1 で持続。
- 順張り P（主）: 時系列モメンタム1本。s_t = sign(c_t − c_{t−20})。翌日 t+1 のポジション = s_t。
  日次の粗損益 = pos_t × (c_{t+1}/c_t − 1) × 1e4 [bp]。コスト = ポジションが変わった日に |Δpos| × 片道コスト。
  片道コスト = 段階1の保守値（kensho_donchian_regime.py の往復 COST の半分）を価格で割って bp にする。
  組の P = 組の中の日次純損益の平均 [bp/日]。
- 副（判定に使わない）: ドンチャン簡略版。終値が直前55日の高値を上回れば翌日から買い、直前20日の安値を下回れば手仕舞い
  （売りは対称）。損切りなし（元の 55/20/2 の ATR 損切りは省く＝簡略化を明記）。同じコスト。
- 帰無（Takahashi ほかの「テクニカル成分ゼロ」に当たる）: 各組の中で r_t を並べ替える（自己相関0・ドリフトとボラは同じ）。
  全銘柄で並べ替えた系列から価格を作り直し、同じ手順で D・P を出す。B=NULL_B 回、seed 固定。
  注意: 並べ替えは銘柄ごとに独立なので、横断面の共通の動きも壊れる。横断面の依存は下の FM 型の t で別に扱う。

【測るもの】
H1: (a) 全組をプールした Spearman ρ(D, P)。帰無 B 回の ρ の分布から z = (ρ_obs − mean) / sd と片側パーセンタイル。
    (b) 半年ごとの横断面 Spearman（銘柄数 ≥ MIN_CS=8 の半年だけ）の平均と t（Fama–MacBeth 型。半年を単位）。
H2: (c) 同じ銘柄の連続する組 (D_{b−1}, P_b) をプールした Spearman と帰無の z。
    (d) 条件つき順張り: 組 b で、D_{b−1} > その銘柄のそれまでの D の中央値（拡大窓・b を含まない・先読みなし）なら順張り、
        そうでなければ休む。条件つき − 無条件 の純損益（bp/日）の差を、半年ごとに銘柄平均 → 半年単位の t（FM 型）。
期間: 前半 = 2008〜2016 の組、後半 = 2017〜2026 の組。それぞれで (a)〜(d) を出す。群: 全15・FX8・トレンド7 で記述。

【判定（事前固定・変更禁止）】
H1 支持 = 前半・後半とも (a) の ρ>0 かつ z≥2（帰無の上位2.5%より外）。どちらかで z<2 → H1 棄却。
H2 支持 = 前半・後半とも (c) の z≥2 かつ (d) の差>0 で t≥2。どれか欠ければ H2 棄却。
H1 支持・H2 棄却 = 「説明にはなるが予測には使えない」（成果として記録）。
H1 が全15では支持でも FX8 だけで z<2 なら、「FX は D そのものが帰無と重なる（持続時間が短い）」のか
「D は長いのに P が出ない」のかを、FX8 の D の分布（帰無の D との差）で分けて記述する。
副次（VR10・ドンチャン簡略版）は多重比較の数に入れ（主2本＋副2本＝4通り×2期間）、判定には使わない。

【捨てた案の数】
約7（設計で検討して捨てた案の概数）: ZigZag の山谷の間隔を D にする案（ZigZag は先読みで既に痛い目・符号の連で代用）、
VR10 を主にする案（副へ）、ドンチャン 55/20/2 を主の P にする案（半年に数回しか取引がなく組の P が粗い→副へ・簡略版）、
月ブロック（組が短く D が粗い）、暗号資産 12 銘柄の追加（期間が短く前半がない→今回は BTC のみ）、
GARCH の局面分け（アイデア候補の2件目へ）、組内の位置（前半・後半）で D を分ける案。判定に使うのは主の定義1本。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。各銘柄の大まかな値動き（2020 年の急変動、2022 年の
ドル高、2024〜25 年の金・BTC の上昇）を知っている可能性があり、後知恵を完全には排除できない。
ただし本検証は「D と P の関係」という横断面・時系列の両方にまたがる量で、特定の年の相場観だけでは作れない。
仮説の元（Takahashi ほか 2026-08）は締め切り後の公表。

【委託の確かめ方】
設計とコードは Fable（2026-10-09、taichi の指示）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（(a)〜(d) と z・t）・原典の箇所（論文ノートの §6 ③、
アイデア候補の行）を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（scipy・matplotlib は任意）。
実行: python3 kensho_trend_persistence_q136.py            （B=500、数分）
      python3 kensho_trend_persistence_q136.py --B 50     （軽い試走）
      python3 kensho_trend_persistence_q136.py --smoke    （合成データで経路の確認。結果は捨てる）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import unicodedata

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


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")

FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
# 段階1の保守的な往復コスト（価格単位）。kensho_donchian_regime.py と同じ値。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20          # 時系列モメンタムの参照日数
DON_ENTRY, DON_EXIT = 55, 20
VR_Q = 10
MIN_DAYS = 100         # 組として数える最小日数
MIN_CS = 8             # 横断面 Spearman に要る最小銘柄数
SPLIT_YEAR = 2017      # 前半 = year < 2017、後半 = year >= 2017
NULL_B = 500
SEED = 20261009


# ----------------------------------------------------------------------------- 基本の道具
def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    rx = pd.Series(x).rank().values; ry = pd.Series(y).rank().values
    rx = rx - rx.mean(); ry = ry - ry.mean()
    d = math.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def run_length_mean(r):
    """符号（0 を除く）の連の平均の長さ。"""
    s = np.sign(r); s = s[s != 0]
    if len(s) < 2:
        return float("nan")
    changes = np.flatnonzero(np.diff(s) != 0)
    n_runs = len(changes) + 1
    return float(len(s) / n_runs)


def variance_ratio(r, q=VR_Q):
    r = np.asarray(r, float)
    if len(r) < 3 * q:
        return float("nan")
    v1 = r.var(ddof=1)
    rq = pd.Series(r).rolling(q).sum().dropna().values
    vq = rq.var(ddof=1)
    return float(vq / (q * v1)) if v1 > 0 else float("nan")


# ----------------------------------------------------------------------------- データ
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def half_year_id(ts):
    return ts.dt.year * 10 + np.where(ts.dt.month <= 6, 1, 2)


# ----------------------------------------------------------------------------- ルール
def tsmom_positions(c):
    """s_t = sign(c_t − c_{t−20})。翌日のポジションに使う（呼び出し側で shift）。"""
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def donchian_positions(c):
    """終値が直前55日高値を上抜けで買い、直前20日安値を下抜けで手仕舞い（売りは対称）。損切りなし。"""
    n = len(c); pos = np.zeros(n)
    cs = pd.Series(c)
    hiE = cs.rolling(DON_ENTRY).max().shift(1).values; loE = cs.rolling(DON_ENTRY).min().shift(1).values
    hiX = cs.rolling(DON_EXIT).max().shift(1).values; loX = cs.rolling(DON_EXIT).min().shift(1).values
    p = 0
    for i in range(n):
        if p == 1 and np.isfinite(loX[i]) and c[i] < loX[i]:
            p = 0
        elif p == -1 and np.isfinite(hiX[i]) and c[i] > hiX[i]:
            p = 0
        if p == 0:
            if np.isfinite(hiE[i]) and c[i] > hiE[i]:
                p = 1
            elif np.isfinite(loE[i]) and c[i] < loE[i]:
                p = -1
        pos[i] = p
    return pos


def daily_net_pnl_bp(c, signal, cost_rt):
    """signal_t を翌日 t+1 に持つ。bp 単位の日次純損益（長さ n、先頭は 0）。"""
    n = len(c); pnl = np.zeros(n)
    pos_prev = np.concatenate([[0.0], signal[:-1]])          # t 日のポジション = s_{t−1}
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))  # t 日の朝（= t−1 の引け）に変えた量
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:LOOKBACK + 1] = 0.0
    return pnl


# ----------------------------------------------------------------------------- 組ごとの量
def block_table(sym, t, c, cost_rt):
    """1銘柄の価格列から、半年の組ごとの D・VR10・P(tsmom)・P(donchian)・日数を出す。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    p_ts = daily_net_pnl_bp(c, tsmom_positions(c), cost_rt)
    p_dc = daily_net_pnl_bp(c, donchian_positions(c), cost_rt)
    hid = half_year_id(pd.Series(t))
    rows = []
    for b in np.unique(hid):
        m = (hid == b).values if hasattr(hid, "values") else (hid == b)
        idx = np.flatnonzero(m)
        if len(idx) < MIN_DAYS:
            continue
        idx_r = idx[idx >= 1]                   # リターンが定義される日
        idx_p = idx[idx > LOOKBACK]             # ポジションが定義される日
        rows.append(dict(sym=sym, block=int(b), year=int(b // 10), half=int(b % 10), days=int(len(idx)),
                         D=run_length_mean(r[idx_r]), VR10=variance_ratio(r[idx_r]),
                         P_tsmom=float(p_ts[idx_p].mean()) if len(idx_p) else float("nan"),
                         P_donchian=float(p_dc[idx_p].mean()) if len(idx_p) else float("nan"),
                         drift_bp=float(r[idx_r].mean() * 1e4), vol_bp=float(r[idx_r].std(ddof=1) * 1e4)))
    return rows


def shuffled_prices(t, c, rng):
    """各半年の組の中で日次対数リターンを並べ替え、価格を作り直す（組の最初の終値から）。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    hid = half_year_id(pd.Series(t)).values
    r2 = r.copy()
    for b in np.unique(hid):
        idx = np.flatnonzero(hid == b); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    lc = np.log(c[0]) + np.cumsum(r2)
    return np.exp(lc)


# ----------------------------------------------------------------------------- 統計
def stats_for(tab, group_syms, period, dcol="D", pcol="P_tsmom"):
    """(a) プール Spearman、(b) 半年ごとの横断面 Spearman の平均と t、(c) 予測の Spearman、(d) 条件つき−無条件。"""
    g = tab[tab.sym.isin(group_syms)].copy()
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    g = g.sort_values(["sym", "block"])
    out = {"n_blocks": int(len(g))}
    out["a_rho_pool"] = spearman(g[dcol], g[pcol])
    # (b) 横断面
    cs = []
    for b, gb in g.groupby("block"):
        if len(gb) >= MIN_CS:
            cs.append(spearman(gb[dcol], gb[pcol]))
    m, tt, n = mean_t(cs)
    out.update(b_cs_mean=m, b_cs_t=tt, b_cs_n=n)
    # (c)(d) 予測版: 同じ銘柄の連続する組
    g["D_prev"] = g.groupby("sym")[dcol].shift(1)
    g["block_prev"] = g.groupby("sym")["block"].shift(1)
    # 連続する半年だけ（間が飛んでいる組は使わない）: 前の組が上半期なら +1、下半期なら +9 が次の組
    bp = g["block_prev"].fillna(-1).astype(int).values; b = g["block"].values
    g["consec"] = (bp > 0) & (((bp % 10 == 1) & (b == bp + 1)) | ((bp % 10 == 2) & (b == bp + 9)))
    h = g[g.consec & np.isfinite(g.D_prev)].copy()
    out["c_rho_pred"] = spearman(h.D_prev, h[pcol]); out["c_n"] = int(len(h))
    # 拡大窓の中央値（b を含まない・先読みなし）: 銘柄ごとに、その組より前の全組の D の中央値
    med = []
    for sym, gs in g.groupby("sym"):
        ds = gs[dcol].values
        med.extend([np.median(ds[:i]) if i >= 2 else np.nan for i in range(len(ds))])
    g["D_med_prev"] = med
    h = g[g.consec & np.isfinite(g.D_prev) & np.isfinite(g.D_med_prev)].copy()
    h["trade"] = (h.D_prev > h.D_med_prev).astype(float)
    h["P_cond"] = h.trade * h[pcol]
    h["diff"] = h.P_cond - h[pcol]
    per = h.groupby("block")[["diff", "P_cond", pcol]].mean()
    m, tt, n = mean_t(per["diff"].values)
    out.update(d_diff_mean=m, d_diff_t=tt, d_n_halfyears=n,
               d_P_cond_mean=float(per["P_cond"].mean()) if len(per) else float("nan"),
               d_P_uncond_mean=float(per[pcol].mean()) if len(per) else float("nan"),
               d_trade_share=float(h.trade.mean()) if len(h) else float("nan"))
    return out


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


# ----------------------------------------------------------------------------- 本体
def build_tables(series, B, rng):
    """series: {sym: (t, c)}。観測の表と、帰無 B 回の表のリストを返す。"""
    obs = []
    for sym, (t, c) in series.items():
        obs.extend(block_table(sym, t, c, COST_RT[sym]))
    obs = pd.DataFrame(obs)
    nulls = []
    for b in range(B):
        rows = []
        for sym, (t, c) in series.items():
            c2 = shuffled_prices(t, c, rng)
            rows.extend(block_table(sym, t, c2, COST_RT[sym]))
        nulls.append(pd.DataFrame(rows))
    return obs, nulls


def evaluate(obs, nulls):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    periods = ["前半", "後半", "全期間"]
    specs = {"主": ("D", "P_tsmom"), "副_VR10": ("VR10", "P_tsmom"), "副_donchian": ("D", "P_donchian")}
    res = {}
    for sname, (dcol, pcol) in specs.items():
        for gname, syms in groups.items():
            for per in periods:
                key = f"{sname}|{gname}|{per}"
                o = stats_for(obs, syms, per, dcol, pcol)
                ns = [stats_for(nt, syms, per, dcol, pcol) for nt in nulls]   # 帰無は1回だけ計算
                na = [s["a_rho_pool"] for s in ns]
                nc = [s["c_rho_pred"] for s in ns]
                nd = [s["d_diff_mean"] for s in ns]
                o["a_z"], o["a_pct"] = z_against_null(o["a_rho_pool"], na)
                o["c_z"], o["c_pct"] = z_against_null(o["c_rho_pred"], nc)
                o["d_z"], o["d_pct"] = z_against_null(o["d_diff_mean"], nd)
                o["null_a_mean"] = float(np.nanmean(na)) if len(na) else float("nan")
                o["null_a_sd"] = float(np.nanstd(na, ddof=1)) if len(na) > 1 else float("nan")
                res[key] = o
    # D の分布（FX8 が帰無と重なるか）: 観測 D の平均 − 帰無 D の平均、銘柄群ごと
    ddist = {}
    for gname, syms in groups.items():
        od = obs[obs.sym.isin(syms)]["D"].values
        nd = np.concatenate([nt[nt.sym.isin(syms)]["D"].values for nt in nulls]) if nulls else np.array([])
        ddist[gname] = dict(D_obs_mean=float(np.nanmean(od)), D_obs_sd=float(np.nanstd(od, ddof=1)),
                            D_null_mean=float(np.nanmean(nd)) if len(nd) else float("nan"),
                            share_obs_above_null_mean=float((od > np.nanmean(nd)).mean()) if len(nd) else float("nan"))
    return res, ddist


def judge(res):
    def ok(v, th):
        return np.isfinite(v) and v >= th
    h1 = {}
    for per in ("前半", "後半"):
        r = res[f"主|全15|{per}"]
        h1[per] = bool(np.isfinite(r["a_rho_pool"]) and r["a_rho_pool"] > 0 and ok(r["a_z"], 2.0))
    h1_sup = h1["前半"] and h1["後半"]
    h2 = {}
    for per in ("前半", "後半"):
        r = res[f"主|全15|{per}"]
        h2[per] = bool(ok(r["c_z"], 2.0) and np.isfinite(r["d_diff_mean"]) and r["d_diff_mean"] > 0 and ok(r["d_diff_t"], 2.0))
    h2_sup = h2["前半"] and h2["後半"]
    fx_h1 = {per: bool(ok(res[f"主|FX8|{per}"]["a_z"], 2.0)) for per in ("前半", "後半")}
    verdict = ("H1 支持・H2 支持" if (h1_sup and h2_sup) else
               "H1 支持・H2 棄却（説明にはなるが予測には使えない）" if h1_sup else
               "H1 棄却")
    return dict(H1_by_period=h1, H1=("支持" if h1_sup else "棄却"), H2_by_period=h2, H2=("支持" if h2_sup else "棄却"),
                FX8_H1_z_ge2_by_period=fx_h1, verdict=verdict,
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定、FX8 の切り分け）は実行者が記録する。")


def make_plot(obs, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"]:
            if os.path.exists(p):
                font_manager.fontManager.addfont(p)
                matplotlib.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name(); break
        matplotlib.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
        for a, (gname, syms, col) in zip(ax, [("FX8", FX8, "tab:blue"), ("トレンド7", TREND7, "tab:orange")]):
            g = obs[obs.sym.isin(syms)]
            a.scatter(g.D, g.P_tsmom, s=12, alpha=.6, c=col)
            a.axhline(0, lw=.6, c="k"); a.axvline(2.0, lw=.6, c="gray", ls="--")
            a.set_xlabel("持続時間 D（同符号の連の平均・日）"); a.set_ylabel("順張りの純損益 P（bp/日）")
            a.set_title(f"{gname}: 銘柄×半年 n={len(g)}  Spearman={spearman(g.D, g.P_tsmom):+.3f}")
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:  # 図は任意
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    series = {}
    if args.smoke:
        # 合成: AR(1) の対数リターン（φ を銘柄ごとに変える）。経路の確認だけが目的。
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
            for i in range(1, len(dates)):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 20)
    else:
        for sym in SYMS:
            d = load_daily(sym)
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B

    obs, nulls = build_tables(series, B, rng)
    res, ddist = evaluate(obs, nulls)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q136_blocks_{stamp}.csv"); obs.to_csv(csv_path, index=False)
    png_path = make_plot(obs, os.path.join(OUT, f"{prefix}Q136_scatter_{stamp}.png"))
    out = dict(
        queue_id="Q136", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT, VR_Q=VR_Q, MIN_DAYS=MIN_DAYS,
                      MIN_CS=MIN_CS, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT,
                      syms=SYMS, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_blocks_total=int(len(obs)),
        results=res, D_distribution=ddist, judgement=verdict,
        files=dict(blocks_csv=csv_path, scatter_png=png_path),
        multiple_comparisons="主(D×tsmom)＋副(VR10×tsmom, D×donchian)＝3仕様 × 前半/後半＝6（判定は主×2のみ）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q136_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    # 画面の要約
    print(f"[Q136] blocks={len(obs)}  B={B}  smoke={args.smoke}")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"主|{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_blocks']:3d}  (a) rho={r['a_rho_pool']:+.3f} z={r['a_z']:+.2f}  "
                  f"(b) cs_mean={r['b_cs_mean']:+.3f} t={r['b_cs_t']:+.2f}  (c) rho_pred={r['c_rho_pred']:+.3f} z={r['c_z']:+.2f}  "
                  f"(d) diff={r['d_diff_mean']:+.2f}bp t={r['d_diff_t']:+.2f} trade={r['d_trade_share']:.2f}")
    print("  D分布:", {k: (round(v['D_obs_mean'], 3), round(v['D_null_mean'], 3)) for k, v in ddist.items()})
    print("  判定(機械):", verdict["verdict"], "| H1", verdict["H1_by_period"], "| H2", verdict["H2_by_period"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
