#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q145: 戦略の日次ポジションを平均の向きに圧縮したとき、向きが離れたペアは履歴の相関も低いか
（Nunes 2026「Cities of Signals」§8 を手元の 12 戦略 × 15銘柄で）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q145（Fable 2026-10-09）。
  検証/学問/金融工学/知識/文献/アイデア候補.md の同日の行。
- 論文ノート: Nunes2026_Cities of Signals_信号を平均の向きに圧縮したとき新規性は保たれるか
  （§8: 向きが 60 度以上離れたペアで履歴の相関 ≤0.5 の割合 94.3%、選別前 85.0%。選別の効果は選別前との差で測る。
  評価期間で割合は 42〜64% 動く）、主張カード Nunes2026-1〜4。

【仮説（測る前に固定）】
H: 戦略の時間平均ポジション（15次元の「向き」）が 60° 以上離れたペアは、全ペアの基準率より高い割合で
   日次損益の相関が 0.5 以下になる（向きの選別は履歴の違いを保証しないが、基準率より改善する）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄 = FX8 + トレンド7。2008-02〜2026-07。
値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 戦略群 12 本（固定）:
  TSMOM L ∈ {5,10,20,40,60,120,250}（s_t = sign(c_t − c_{t−L})、翌日に持つ）、
  ドンチャン簡略版 {20/10, 55/20, 100/50}（終値が直前 E 日高値の上抜けで買い・直前 X 日安値の下抜けで手仕舞い。売りは対称。損切りなし）、
  MA乖離の逆張り {z>1, z>2}（z_t = (c_t − SMA20_t)/SD20_t、SD は終値の 20 日標準偏差。z>k で売り（−1）、z<−k で買い（+1）、間は 0）。
- 各戦略の各日のポジション = 15銘柄のベクトル（データの無い日は 0）。
  日次純損益 [bp] = 銘柄ごとに pos × (c_{t+1}/c_t − 1) × 1e4 − |Δpos| × 片道コスト（段階1 COST_RT/2 を価格で割って bp）、
  戦略の日次損益系列 = その日にデータのある銘柄の純損益の平均（等ウェイト）。
  全戦略に共通のウォームアップ WARM=250 日（各銘柄の最初の 250 日は 0 ポジション・評価から除く）。
- (a) 全履歴の相関 = 戦略ペアの日次損益系列の Pearson 相関（評価期間内）。
- (b) 平均の向き = 各戦略の時間平均ポジションベクトル（銘柄ごとに、その銘柄のデータのある評価日で平均）。
  ペアの角度 = arccos(cos 類似度)。どちらかのノルムが 0 なら角度は NaN（ペアから除く）。
- 選別後 = 角度 ≥ 60° のペア。割合 = 選別後のペアのうち (a) ≤ 0.5 の割合。選別前 = 全ペア（66 組）での同じ割合。差 = 選別後 − 選別前。
- 帰無（登録）: 各戦略の日次損益系列を時間方向に独立な一様ランダムの循環シフト（向きは保ち、履歴の相関を壊す）。B=300、seed 固定。
  帰無の差の分布から z = (差_obs − mean)/sd、パーセンタイル。
  ただし循環シフト後の相関は全ペアで ≈0（≤0.5）になるため、選別前・後の割合がともに 1 で差の分布が退化（sd=0・z 未定義）しうる。
  そのとき（`null_shift_degenerate`）は代替の帰無「向きのベクトルの戦略ラベルを並べ替え（相関行列と向きの集合は固定。
  角度と相関の対応だけ壊す＝同じ数のペアを無作為に選別したときの差の分布）」の z を判定に使う（`null_used` に記録）。
  両方の z を JSON に出す。
- 評価期間: 全期間（判定）、前半（2017 年より前）、後半（2017 年以降）（割合の幅を記述）。

【測るもの】
期間ごとに: 選別前の割合・選別後の割合・差・選別後のペア数・帰無の z・帰無の 2.5/97.5 点。
前半/後半/全期間での割合の幅（最大 − 最小、選別後と選別前それぞれ）。

【判定（事前固定・変更禁止）】
全期間で、差（選別後 − 選別前）が 帰無の上位 2.5% より外（z ≥ 2）かつ 差 ≥ 5 ポイント（0.05）→
「向きの選別は履歴の違いを保証しないが、基準率より改善する」（Nunes と同じ）。
差の帰無の区間（2.5〜97.5 点）が観測の差を含む（z<2 相当）、または差 ≤ 0 → 「向きだけでは何も言えない」。
それ以外（z≥2 だが差<5 ポイント）は未確定。
期間（前半/後半/全期間）で選別後の割合が 20 ポイント以上動けば「評価期間依存」を記述（判定に使わない）。
多重比較: 期間3（判定は全期間のみ）。

【捨てた案の数】
約5: 角度の閾値を 45°/90° でも出す案（Nunes の 60° に固定）、相関を日次ポジションの相関にする案（Nunes は損益の相関→損益）、
戦略をもっと増やす案（60 通りの L など。ペアが TSMOM 同士だらけになる→12 本）、ノルムで重みづけした cos を使う案（角度だけ）、
帰無を銘柄方向の並べ替えにする案（向きが変わる→循環シフト）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証は戦略間の構造（向きと相関）の問いで、
特定の年の相場観では作れない。Nunes 2026 の数値（94.3%・85.0%）は締め切り後の公表。

【委託の確かめ方】
設計は Fable（specs20.py）、コードは Claude（Fable 5.1 下請け、2026-10-09）、実行と解釈は Sonnet／Opus が後で行う。
実行者は結果 JSON のパス・主要な数値（選別前後の割合・差・z・期間の幅）・原典の箇所（Nunes §8）を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定の循環シフトだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_signal_direction_compression_q145.py            （B=300）
      python3 kensho_signal_direction_compression_q145.py --B 30
      python3 kensho_signal_direction_compression_q145.py --smoke
事前登録からの変更点: 登録の帰無（循環シフト）は差の分布が退化（全ペアの相関 ≈0 → 割合が 1 で sd=0）しうるため、
その場合は「向きのラベル並べ替え」の帰無で z を出して判定に使う（上の【定義】参照。両方を JSON に残す）。
共通ウォームアップ 250 日、MA乖離の SD の定義（終値の 20 日 SD）は実装上の固定値。
"""
import argparse
import datetime as _dt
import json
import math
import os
import time
import unicodedata

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))


def _p(*parts):
    a = os.path.join(WS, *parts)
    if os.path.exists(a):
        return a
    return os.path.join(WS, *[unicodedata.normalize("NFD", x) for x in parts])


DATA_DIR = _p("検証", "学問", "金融工学", "作業", "FX", "システムトレード")
OUT = os.path.join(HERE, "results")

FX8 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

TSMOM_L = [5, 10, 20, 40, 60, 120, 250]
DONCH = [(20, 10), (55, 20), (100, 50)]
MAZ_K = [1.0, 2.0]
MA_WIN = 20
WARM = 250
ANGLE_DEG = 60.0
CORR_TH = 0.5
DIFF_TH = 0.05
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009
QID = "Q145"

STRATS = [f"TSMOM{L}" for L in TSMOM_L] + [f"DONCH{e}_{x}" for e, x in DONCH] + [f"MAZ{k:g}" for k in MAZ_K]


# ----------------------------------------------------------------------------- 道具
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def tsmom_positions(c, L):
    n = len(c); s = np.zeros(n)
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def donchian_positions(c, E, X):
    n = len(c); pos = np.zeros(n)
    cs = pd.Series(c)
    hiE = cs.rolling(E).max().shift(1).values; loE = cs.rolling(E).min().shift(1).values
    hiX = cs.rolling(X).max().shift(1).values; loX = cs.rolling(X).min().shift(1).values
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


def maz_positions(c, k):
    cs = pd.Series(c)
    ma = cs.rolling(MA_WIN).mean().values; sd = cs.rolling(MA_WIN).std(ddof=1).values
    z = np.where(np.isfinite(sd) & (sd > 0), (c - ma) / np.where(sd > 0, sd, 1.0), 0.0)
    pos = np.zeros(len(c))
    pos[z > k] = -1.0; pos[z < -k] = 1.0
    return pos


def strategy_signal(c, name):
    if name.startswith("TSMOM"):
        return tsmom_positions(c, int(name[5:]))
    if name.startswith("DONCH"):
        e, x = name[5:].split("_"); return donchian_positions(c, int(e), int(x))
    return maz_positions(c, float(name[3:]))


def daily_net_pnl_bp(c, signal, cost_rt, warm=WARM):
    n = len(c)
    sig = signal.copy(); sig[:warm] = 0.0
    pos_prev = np.concatenate([[0.0], sig[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = pos_prev * ret * 1e4 - dpos * cost_bp
    pnl[:warm + 1] = 0.0
    return pnl, pos_prev


# ----------------------------------------------------------------------------- 行列
def build_matrices(series):
    """master 日付 × 銘柄 の pos・pnl を戦略ごとに。欠損は NaN。返り値: master, years, {strat: (pos[T,S], pnl[T,S])}, valid[T,S]"""
    master = np.unique(np.concatenate([np.asarray(t, "datetime64[ns]") for t, _ in series.values()]))
    T = len(master); S = len(series)
    valid = np.zeros((T, S), bool)
    mats = {name: (np.full((T, S), np.nan), np.full((T, S), np.nan)) for name in STRATS}
    for j, (sym, (t, c)) in enumerate(series.items()):
        tt = np.asarray(t, "datetime64[ns]")
        ix = np.searchsorted(master, tt)
        ok = np.arange(len(c)) > WARM
        valid[ix[ok], j] = True
        for name in STRATS:
            pnl, pos = daily_net_pnl_bp(c, strategy_signal(c, name), COST_RT[sym])
            mats[name][0][ix[ok], j] = pos[ok]; mats[name][1][ix[ok], j] = pnl[ok]
    years = pd.DatetimeIndex(master).year.values
    return master, years, mats, valid


def period_mask(years, per):
    if per == "前半":
        return years < SPLIT_YEAR
    if per == "後半":
        return years >= SPLIT_YEAR
    return np.ones(len(years), bool)


def pnl_series(mats, mask):
    """戦略ごとの日次損益系列（評価期間内・その日にデータのある銘柄の平均）。行: 日、列: 戦略。"""
    cols = []
    for name in STRATS:
        p = mats[name][1][mask]
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                cols.append(np.nanmean(p, axis=1))
    P = np.column_stack(cols)
    keep = np.isfinite(P).all(axis=1)
    return P[keep]


def direction_vectors(mats, mask):
    return np.column_stack([np.nanmean(mats[name][0][mask], axis=0) for name in STRATS])  # (S, K)


def pair_angles(D):
    K = D.shape[1]; ang = np.full((K, K), np.nan)
    nrm = np.linalg.norm(D, axis=0)
    for i in range(K):
        for j in range(K):
            if nrm[i] > 0 and nrm[j] > 0:
                cs = float(np.dot(D[:, i], D[:, j]) / (nrm[i] * nrm[j]))
                ang[i, j] = math.degrees(math.acos(max(-1.0, min(1.0, cs))))
    return ang


def shares(C, ang):
    K = C.shape[0]; iu = np.triu_indices(K, 1)
    c = C[iu]; a = ang[iu]
    ok = np.isfinite(c) & np.isfinite(a)
    base = float((c[ok] <= CORR_TH).mean()) if ok.any() else float("nan")
    sel = ok & (a >= ANGLE_DEG)
    after = float((c[sel] <= CORR_TH).mean()) if sel.any() else float("nan")
    return dict(share_before=base, share_after=after, diff=after - base, n_pairs=int(ok.sum()), n_selected=int(sel.sum()))


def corr_matrix(P):
    return np.corrcoef(P, rowvar=False)


def null_diffs(P, ang, B, rng):
    T, K = P.shape; out = []
    for _ in range(B):
        sh = rng.integers(1, T, K)
        Q = np.column_stack([np.roll(P[:, k], sh[k]) for k in range(K)])
        out.append(shares(corr_matrix(Q), ang)["diff"])
    return np.asarray(out)


def null_diffs_label(C, D, B, rng):
    """代替の帰無: 向きのベクトルの戦略ラベルを並べ替え（相関行列は固定・向きの集合も固定。角度と相関の対応だけ壊す）。"""
    K = D.shape[1]; out = []
    for _ in range(B):
        Dp = D[:, rng.permutation(K)]
        out.append(shares(C, pair_angles(Dp))["diff"])
    return np.asarray(out)


def judge(res):
    r = res["全期間"]
    d = r["diff"]; z = r["z_used"]
    fin = lambda v: v is not None and np.isfinite(v)
    if fin(d) and fin(z) and z >= 2.0 and d >= DIFF_TH:
        v = "向きの選別は履歴の違いを保証しないが、基準率より改善する（Nunes と同じ）"
    elif (not fin(d)) or d <= 0 or (fin(r["null_lo_used"]) and r["null_lo_used"] <= d <= r["null_hi_used"]):
        v = "向きだけでは何も言えない（差が帰無の区間内または ≤0）"
    else:
        v = "未確定（z≥2 だが差<5 ポイント）"
    aft = [res[p]["share_after"] for p in res]; bef = [res[p]["share_before"] for p in res]
    rng_after = float(np.nanmax(aft) - np.nanmin(aft)); rng_before = float(np.nanmax(bef) - np.nanmin(bef))
    return dict(diff=d, z=z, null_used=r["null_used"], z_shift=r["z"], z_label=r["z_label"], verdict=v, range_after_across_periods=rng_after, range_before_across_periods=rng_before,
                period_dependent=bool(np.isfinite(rng_after) and rng_after >= 0.20),
                rule="全期間で z≥2 かつ 差≥0.05 → 改善。差が帰無の 2.5〜97.5 点内または ≤0 → 何も言えない。他は未確定。期間で 20 ポイント以上動けば評価期間依存（記述）",
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定）は実行者が記録する。")


def make_plot(C, ang, path):
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
        iu = np.triu_indices(C.shape[0], 1)
        fig, ax = plt.subplots(figsize=(6, 4.5))
        ax.scatter(ang[iu], C[iu], s=18, alpha=.7)
        ax.axvline(ANGLE_DEG, c="r", lw=.8, ls="--"); ax.axhline(CORR_TH, c="r", lw=.8, ls="--")
        ax.set_xlabel("平均の向きの角度（度）"); ax.set_ylabel("日次損益の相関"); ax.set_title("戦略ペア 66 組（全期間）")
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の循環シフト回数")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    series = {}; missing = []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            n = len(dates); e = g.normal(0, 0.006, n); r = np.zeros(n)
            for i in range(1, n):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            keep = g.random(n) > 0.03
            series[sym] = (dates.values[keep], (base * np.exp(np.cumsum(r)))[keep])
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            d = load_daily(sym)
            if d is None or len(d) < 300:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    syms_used = list(series.keys())

    master, years, mats, valid = build_matrices(series)
    res = {}; C_all = ang_all = None; pair_rows = []
    for per in ("全期間", "前半", "後半"):
        mask = period_mask(years, per)
        P = pnl_series(mats, mask)
        D = direction_vectors(mats, mask)
        ang = pair_angles(D); C = corr_matrix(P)
        s = shares(C, ang)
        nd = null_diffs(P, ang, B, rng)
        nd = nd[np.isfinite(nd)]
        if len(nd) >= 10:
            sd = nd.std(ddof=1)
            s["z"] = float((s["diff"] - nd.mean()) / sd) if sd > 0 else float("nan")
            s["null_mean"] = float(nd.mean()); s["null_lo"] = float(np.percentile(nd, 2.5)); s["null_hi"] = float(np.percentile(nd, 97.5))
            s["pct"] = float((nd < s["diff"]).mean())
        else:
            s.update(z=float("nan"), null_mean=float("nan"), null_lo=float("nan"), null_hi=float("nan"), pct=float("nan"))
        # 代替の帰無（ラベル並べ替え）。登録の循環シフトは相関を全て ~0 にするので差の分布が退化（sd=0）しうる
        nl = null_diffs_label(C, D, B, rng); nl = nl[np.isfinite(nl)]
        if len(nl) >= 10:
            sdl = nl.std(ddof=1)
            s["z_label"] = float((s["diff"] - nl.mean()) / sdl) if sdl > 0 else float("nan")
            s["null_label_mean"] = float(nl.mean()); s["null_label_lo"] = float(np.percentile(nl, 2.5)); s["null_label_hi"] = float(np.percentile(nl, 97.5))
            s["pct_label"] = float((nl < s["diff"]).mean())
        else:
            s.update(z_label=float("nan"), null_label_mean=float("nan"), null_label_lo=float("nan"), null_label_hi=float("nan"), pct_label=float("nan"))
        shift_degenerate = (not np.isfinite(s["z"])) or (len(nd) >= 10 and nd.std(ddof=1) == 0)
        s["null_shift_degenerate"] = bool(shift_degenerate)
        if shift_degenerate:
            s["z_used"] = s["z_label"]; s["null_used"] = "label_permutation"
            s["null_lo_used"], s["null_hi_used"] = s["null_label_lo"], s["null_label_hi"]
        else:
            s["z_used"] = s["z"]; s["null_used"] = "circular_shift"
            s["null_lo_used"], s["null_hi_used"] = s["null_lo"], s["null_hi"]
        s["n_days"] = int(P.shape[0])
        s["mean_pnl_bp_by_strategy"] = {name: float(P[:, k].mean()) for k, name in enumerate(STRATS)}
        s["direction_norm_by_strategy"] = {name: float(np.linalg.norm(D[:, k])) for k, name in enumerate(STRATS)}
        res[per] = s
        iu = np.triu_indices(len(STRATS), 1)
        for i, j in zip(*iu):
            pair_rows.append(dict(period=per, s1=STRATS[i], s2=STRATS[j], angle_deg=ang[i, j], corr=C[i, j],
                                  selected=bool(np.isfinite(ang[i, j]) and ang[i, j] >= ANGLE_DEG)))
        if per == "全期間":
            C_all, ang_all = C, ang
    verdict = judge(res)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_pairs_{stamp}.csv"); pd.DataFrame(pair_rows).to_csv(csv_path, index=False)
    png_path = make_plot(C_all, ang_all, os.path.join(OUT, f"{prefix}{QID}_scatter_{stamp}.png"))
    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(strategies=STRATS, WARM=WARM, MA_WIN=MA_WIN, ANGLE_DEG=ANGLE_DEG, CORR_TH=CORR_TH, DIFF_TH=DIFF_TH,
                      SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=syms_used, missing_syms=missing,
                      n_missing=len(missing), data_dir=DATA_DIR, null_def="各戦略の日次損益系列を独立な一様ランダム量で循環シフト"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        results=res, judgement=verdict,
        files=dict(pairs_csv=csv_path, scatter_png=png_path),
        multiple_comparisons="期間3（全期間・前半・後半。判定は全期間のみ）",
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(syms_used)} missing={missing} B={B} smoke={args.smoke} elapsed={elapsed:.1f}s")
    for per, s in res.items():
        print(f"  {per:3s} days={s['n_days']:5d} pairs={s['n_pairs']} selected(≥{ANGLE_DEG:g}°)={s['n_selected']}  "
              f"割合 前={s['share_before']:.3f} 後={s['share_after']:.3f} 差={s['diff']:+.3f}  "
              f"z(循環シフト)={s['z']:+.2f} 帰無[{s['null_lo']:+.3f},{s['null_hi']:+.3f}]  "
              f"z(ラベル並べ替え)={s['z_label']:+.2f} 帰無[{s['null_label_lo']:+.3f},{s['null_label_hi']:+.3f}]  使用={s['null_used']}")
    print("  判定(機械):", verdict["verdict"], "| 期間の幅(後)=", round(verdict["range_after_across_periods"], 3),
          "| 期間依存", verdict["period_dependent"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
