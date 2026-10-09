#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q152: 順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか
（15銘柄 D1 + 暗号資産 H4・Rashid 2026 の買い／売りの分解。主=ドンチャン簡略版、副=TSMOM20）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q152（Fable 2026-10-09）。
  アイデア候補.md の行「順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか」。
- 論文ノート: Rashid・Hongほか2026_FinAnalyst_LLM専門家とルール信号の売買エージェント
  （利益がすべて空売りから出た、という分解を報告の標準項目に）。
- 既存の知見: FX改善ログ 2026-10-03（暗号資産の順張りは買い側だけ +0.48R は事後の切り口）、
  為替の4時間足 MA クロスの知見（利益は売り側＝ユーロ安の分）。
  → 「買い側／売り側に分けたとき、ドリフト（上昇相場の分）を引いても残るのはどちらか」を測る。

【仮説（測る前に固定）】
H1: トレンド群・暗号資産で、順張り（主: ドンチャン簡略版 55/20）の売り側の純損益はドリフト除去後に 0 と区別できない。
H2: 買い側の純損益はドリフト除去後も 0 より大きい（＝利益は買い側の「順張り」であって、上昇相場の分ではない）。

【データ】
- 15銘柄: 検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
  FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。
- 暗号資産: data_<SYM>_H4_dukascopy.csv（UTC、列 time,open,high,low,close,volume）。
  候補 BTC ETH XRP LTC ADA BCH XLM EOS LNK DOT SOL のうち、最初の足が 2019 年以前のものだけ使う。
  ファイルが無い／開始が 2020 年以降の銘柄は除き、件数を JSON に書く。

【定義（1通りに固定）】
- 規則（主・Fable 承認 2026-10-09 で入れ替え）: ドンチャン簡略版 55/20。終値が直前55日高値を上抜けで翌足から買い、
  直前20日安値割れで手仕舞い（売りは対称）、損切りなし。休む期間があるので買い側と売り側が別の量になる。
- 規則（副・登録の主だったもの）: TSMOM20。s_t = sign(c_t − c_{t−20})。翌足 t+1 のポジション = s_t（日足は 20 日、
  H4 は 20 本 ≈ 3.3 日）。恒等式の確認用（identity_check）。同じコスト・同じ分解。
- 日次純損益 [bp] = pos_t × (c_t/c_{t−1} − 1) × 1e4 − |Δpos_t| × 片道コスト[bp]。片道コスト＝段階1の往復 COST_RT の半分。
  暗号資産（BTC 以外）は COST_RT の登録が無いので、往復 30bp（片道 15bp）の相対コストを置く（変更点として明記）。
- 側の分解: 買い側 P_L,t = 純損益_t × 1{pos_t=+1}、売り側 P_S,t = 純損益_t × 1{pos_t=−1}。
  側ごとの平均 [bp/足] は「全足の平均」（＝その側の寄与）。参考に「その側を持った足だけの平均」も出す。
- ドリフト除去: 同じ期間（評価期間ごと・銘柄ごと）の平均リターン r̄ [bp] × 露出を引く。
  買い側: P_L,t − r̄ × 1{pos_t=+1}、売り側: P_S,t + r̄ × 1{pos_t=−1}（＝売りは −r̄ の露出）。
- 群: FX8 / トレンド7 / 暗号資産。群の平均 = 銘柄ごとの平均の等ウェイト平均。
  t = 月クラスタ（月ごとに銘柄平均した系列の平均/標準誤差、月を単位）。
- 帰無: 各銘柄の半年の組の中でリターンを並べ替え（自己相関0・ドリフトとボラは同じ）、同じ量を B 回。
  z = (観測 − 帰無の平均) / 帰無の標準偏差。

【測るもの】
規則×群×側×{生, ドリフト除去}×期間{全期間, 前半(<2017), 後半(≥2017)} の 平均 bp/足、月クラスタ t、帰無の z。
判定に使うのは 主（ドンチャン簡略版）の 全期間 のドリフト除去後（トレンド7・暗号資産 × 買い/売り = 4 本）。残りは記述。

【事前登録からの変更点（恒等式のため主を入れ替えた。Fable 承認 2026-10-09）】
登録の主 TSMOM20 は常に ±1 を持つので、買い側の生の損益 − 売り側の生の損益 = Σ_全足 r_t（期間の総リターン・コストを除く）が
恒等的に成り立つ。したがって「露出 × 平均リターン」を引いたドリフト除去後の買い側と売り側は（コストと s_t=0 の足を
除いて）**同じ値**になり、帰無（並べ替えは Σ r_t を保つ）に対する z も同じになる。事前登録の判定
「売り側 |z|<2 かつ 買い側 z≥2」は TSMOM20 では論理的に起こり得ない（出るのは「買い側も z<2 → 上昇相場の分」か
「両側 z≥2 → 規則に当てはまらない」だけ）。この事実は JSON の `identity_check`（両側の差）で確かめられるようにした。
そこで主を、休む期間があるドンチャン簡略版 55/20 に入れ替え（Fable 承認 2026-10-09）、登録の判定規則をそのまま主に付ける
（`judgement`）。TSMOM20 は副に下げ、恒等式の確認用に同じ分解と判定を参考で残す（`judgement_sub_tsmom`・`identity_check`）。
測るもの・帰無・判定の規則そのものは変えていない。

【判定（事前固定・変更禁止）】
トレンド群・暗号資産で、売り側のドリフト除去後の純損益が 0 と区別できず（|z|<2）かつ 買い側がドリフト除去後も z≥2
なら「利益は買い側のドリフトではなく買い側の順張り」。買い側もドリフト除去後に z<2 なら「利益は上昇相場の分」
（既存の疑いを確定）。FX8 は記述のみ。群ごとに判定を付け、総合はトレンド7 と暗号資産の両方で同じ結論のときだけ付ける。

【捨てた案の数】
約6: 側ごとの「持った足だけの平均」を主にする案（恒等式のため同符号・露出比で縮尺が変わるだけ→参考値に）、 暗号資産を日足に集計し直す案（H4 のまま規則を足単位で適用＝登録どおり）、ドリフト除去を年ごとにする案
（期間ごと1本に統一）、側ごとの「持った足だけの平均」を主にする案（寄与の平均を主・持った足だけは参考）、
ブロック・ブートストラップの区間（並べ替え帰無の z に統一）、ドンチャンの併記（規則1本に固定）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。金・株価指数・BTC が 2020 年以降に大きく上げた
ことは知っており、「買い側が勝つ」方向の後知恵は排除できない。ただし問いは「ドリフトを引いた残り」なので、
相場観だけでは答えを作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、下請け）。実行と解釈は後で Sonnet／Opus。
実行者は結論ではなく、JSON のパス・群×側のドリフト除去後の平均と z・原典（Rashid 2026 の分解、FX改善ログ 2026-10-03）を
本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_long_short_decomposition_q152.py            （B=500）
      python3 kensho_long_short_decomposition_q152.py --B 50     （軽い試走）
      python3 kensho_long_short_decomposition_q152.py --smoke    （合成データで経路の確認。結果は捨てる）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import unicodedata
import warnings

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
CRYPTO_CANDIDATES = ["BTCUSD", "ETHUSD", "XRPUSD", "LTCUSD", "ADAUSD", "BCHUSD", "XLMUSD", "EOSUSD", "LNKUSD", "DOTUSD", "SOLUSD"]
CRYPTO_MAX_START_YEAR = 2019   # 最初の足がこの年以前の銘柄だけ使う
# 段階1の保守的な往復コスト（価格単位）。kensho_donchian_regime.py と同じ値。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
CRYPTO_COST_RT_BP = 30.0       # 暗号資産 H4 の往復コスト（bp、相対）。片道はこの半分。【事前登録からの補足】

LOOKBACK = 20          # 時系列モメンタムの参照本数（日足=20日、H4=20本）
SPLIT_YEAR = 2017      # 前半 = year < 2017、後半 = year >= 2017
NULL_B = 500
SEED = 20261009


# ----------------------------------------------------------------------------- 基本の道具
def mean_t(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    n = len(v)
    if n < 2:
        return float("nan"), float("nan"), n
    m = v.mean(); s = v.std(ddof=1)
    return float(m), float(m / (s / math.sqrt(n))) if s > 0 else float("nan"), n


def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


# ----------------------------------------------------------------------------- データ
def load_csv(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def half_year_id(ts):
    ts = pd.Series(ts)
    return (ts.dt.year * 10 + np.where(ts.dt.month <= 6, 1, 2)).values


# ----------------------------------------------------------------------------- ルール
def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


DON_ENTRY, DON_EXIT = 55, 20


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


RULES = {"donchian": donchian_positions, "tsmom": tsmom_positions}   # 主=ドンチャン、副=TSMOM20


def daily_net_pnl_bp(c, signal, cost_rt, cost_rt_bp=None):
    """signal_t を翌足 t+1 に持つ。bp 単位の純損益（長さ n、先頭は 0）と、持ったポジション pos_t を返す。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n)
    if cost_rt_bp is None:
        cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    else:
        cost_bp[1:] = cost_rt_bp / 2.0
    pnl = gross - dpos * cost_bp
    pnl[:LOOKBACK + 1] = 0.0
    return pnl, pos_prev, ret


def shuffled_prices(t, c, rng):
    """各半年の組の中で対数リターンを並べ替え、価格を作り直す。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    hid = half_year_id(t)
    r2 = r.copy()
    for b in np.unique(hid):
        idx = np.flatnonzero(hid == b); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    return np.exp(np.log(c[0]) + np.cumsum(r2))


# ----------------------------------------------------------------------------- 側ごとの量
PERIODS = ["全期間", "前半", "後半"]
KEYS = ["long_raw", "short_raw", "long_adj", "short_adj"]


def side_series(c, t, cost_rt, cost_rt_bp=None, rule="tsmom"):
    """1銘柄: 期間ごとに {key: (平均, 月ごとの平均の Series)} と露出・持った足だけの平均を返す。"""
    pnl, pos, ret = daily_net_pnl_bp(c, RULES[rule](c), cost_rt, cost_rt_bp)
    years = pd.Series(t).dt.year.values
    months = (pd.Series(t).dt.year * 100 + pd.Series(t).dt.month).values
    valid = np.arange(len(c)) > max(LOOKBACK, DON_ENTRY if rule == "donchian" else 0)
    out = {}
    for per in PERIODS:
        m = valid.copy()
        if per == "前半":
            m &= years < SPLIT_YEAR
        elif per == "後半":
            m &= years >= SPLIT_YEAR
        if m.sum() < 50:
            continue
        rbar = ret[m].mean() * 1e4                     # 同じ期間の平均リターン [bp]
        isL = (pos == 1) & m; isS = (pos == -1) & m
        s = {"long_raw": np.where(isL, pnl, 0.0), "short_raw": np.where(isS, pnl, 0.0),
             "long_adj": np.where(isL, pnl - rbar, 0.0), "short_adj": np.where(isS, pnl + rbar, 0.0)}
        d = {}
        for k, v in s.items():
            d[k] = dict(mean=float(v[m].mean()), monthly=pd.Series(v[m]).groupby(months[m]).mean(),
                        mean_active=float(v[isL if k.startswith("long") else isS].mean()) if (isL if k.startswith("long") else isS).sum() else float("nan"))
        d["n"] = int(m.sum()); d["expo_long"] = float(isL.sum() / m.sum()); d["expo_short"] = float(isS.sum() / m.sum())
        d["drift_bp"] = float(rbar)
        out[per] = d
    return out


def group_stats(per_sym, syms, per):
    """群: 銘柄平均の等ウェイト平均と、月ごとに銘柄平均した系列の t。"""
    res = {}
    syms = [s for s in syms if s in per_sym and per in per_sym[s]]
    res["n_syms"] = len(syms)
    for k in KEYS:
        if not syms:
            res[k] = dict(mean=float("nan"), t=float("nan"), n_months=0, mean_active=float("nan"))
            continue
        means = [per_sym[s][per][k]["mean"] for s in syms]
        mon = pd.concat([per_sym[s][per][k]["monthly"].rename(s) for s in syms], axis=1).mean(axis=1)
        m, tt, n = mean_t(mon.values)
        res[k] = dict(mean=float(np.mean(means)), t=tt, n_months=n,
                      mean_active=float(np.nanmean([per_sym[s][per][k]["mean_active"] for s in syms])))
    if syms:
        res["expo_long"] = float(np.mean([per_sym[s][per]["expo_long"] for s in syms]))
        res["expo_short"] = float(np.mean([per_sym[s][per]["expo_short"] for s in syms]))
        res["drift_bp"] = float(np.mean([per_sym[s][per]["drift_bp"] for s in syms]))
    return res


def judge(res, rule="tsmom", groups_for_judge=("トレンド7", "暗号資産")):
    out = {}
    verdicts = []
    for g in groups_for_judge:
        r = res.get(f"{rule}|{g}|全期間")
        if r is None or r["n_syms"] == 0:
            out[g] = "データなし"; verdicts.append("データなし"); continue
        zl = r["long_adj"]["z"]; zs = r["short_adj"]["z"]
        short_null = np.isfinite(zs) and abs(zs) < 2.0
        long_pos = np.isfinite(zl) and zl >= 2.0
        if short_null and long_pos:
            v = "利益は買い側のドリフトではなく買い側の順張り"
        elif np.isfinite(zl) and zl < 2.0:
            v = "利益は上昇相場の分（買い側もドリフト除去後に z<2）"
        else:
            v = "規則に当てはまらない（売り側も z≥2 など）"
        out[g] = dict(long_adj_z=zl, short_adj_z=zs, verdict=v); verdicts.append(v)
    overall = verdicts[0] if len(set(verdicts)) == 1 else "群で割れる（" + " / ".join(f"{g}: {v}" for g, v in zip(groups_for_judge, verdicts)) + "）"
    return dict(rule=rule, by_group=out, verdict=overall,
                note="事前固定の規則で機械的に付けた判定（全期間・ドリフト除去後の z）。解釈（確定／ノイズ／未確定）と FX8 の記述は実行者が記録する。"
                     + ("副 TSMOM20 は恒等式により買い側と売り側のドリフト除去後が同じ値になる（docstring の変更点・identity_check 参照）。参考判定。" if rule == "tsmom" else "主（ドンチャン簡略版 55/20・Fable 承認 2026-10-09 で入れ替え）の判定。"))


def make_plot(res, path):
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
        groups = ["FX8", "トレンド7", "暗号資産"]
        fig, ax = plt.subplots(figsize=(9, 4))
        x = np.arange(len(groups)); w = 0.2
        for i, k in enumerate(KEYS):
            vals = [res[f"donchian|{g}|全期間"][k]["mean"] for g in groups]
            ax.bar(x + (i - 1.5) * w, vals, w, label=k)
        ax.axhline(0, lw=.6, c="k"); ax.set_xticks(x); ax.set_xticklabels(groups); ax.set_ylabel("bp/足（全足の平均）")
        ax.set_title("ドンチャン簡略版 55/20 の純損益の買い／売り分解（全期間）"); ax.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def synth_series(rng, dates, phi, base, sigma, drift=0.0):
    e = rng.normal(0, sigma, len(dates)); r = np.zeros(len(dates))
    for i in range(1, len(dates)):
        r[i] = phi * r[i - 1] + e[i] + drift
    return dates.values, base * np.exp(np.cumsum(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    series, costs, missing = {}, {}, {}
    crypto_used = []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = synth_series(g, dates, phi, base, 0.006, drift=0.0002 if sym in TREND7 else 0.0)
            costs[sym] = (COST_RT[sym], None)
        h4 = pd.date_range("2017-06-01", "2026-07-14", freq="4h")
        for k, sym in enumerate(["BTCUSD", "ETHUSD", "XRPUSD", "LTCUSD"]):
            series["H4_" + sym] = synth_series(g, h4, 0.05 + 0.05 * k, 100.0, 0.01, drift=0.0001)
            costs["H4_" + sym] = (0.0, CRYPTO_COST_RT_BP); crypto_used.append(sym)
        missing = {"crypto_skipped": ["ADAUSD(例: 開始2020以降)"]}
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
            if not os.path.exists(f):
                missing.setdefault("D1_missing", []).append(sym); continue
            d = load_csv(f); series[sym] = (d.time.values, d.close.values.astype(float)); costs[sym] = (COST_RT[sym], None)
        for sym in CRYPTO_CANDIDATES:
            f = os.path.join(DATA_DIR, f"data_{sym}_H4_dukascopy.csv")
            if not os.path.exists(f):
                missing.setdefault("crypto_missing", []).append(sym); continue
            d = load_csv(f)
            if len(d) == 0 or pd.Timestamp(d.time.iloc[0]).year > CRYPTO_MAX_START_YEAR:
                missing.setdefault("crypto_skipped_start_after_2019", []).append(f"{sym}:{str(d.time.iloc[0])[:10] if len(d) else 'empty'}"); continue
            series["H4_" + sym] = (d.time.values, d.close.values.astype(float)); costs["H4_" + sym] = (0.0, CRYPTO_COST_RT_BP)
            crypto_used.append(sym)
        B = args.B
    groups = {"FX8": [s for s in FX8 if s in series], "トレンド7": [s for s in TREND7 if s in series],
              "暗号資産": ["H4_" + s for s in crypto_used]}

    # 観測
    res = {}; rows = []
    for rule in RULES:
        per_sym = {s: side_series(c, t, *costs[s], rule=rule) for s, (t, c) in series.items()}
        for gname, syms in groups.items():
            for per in PERIODS:
                res[f"{rule}|{gname}|{per}"] = group_stats(per_sym, syms, per)
        for s in series:
            for per, d in per_sym[s].items():
                rows.append(dict(rule=rule, sym=s, period=per, n=d["n"], expo_long=d["expo_long"], expo_short=d["expo_short"], drift_bp=d["drift_bp"],
                                 **{k: d[k]["mean"] for k in KEYS}, **{k + "_active": d[k]["mean_active"] for k in KEYS}))
    tab = pd.DataFrame(rows)

    # 帰無（1回の並べ替えで両規則を評価）
    null = {key: {k: [] for k in KEYS} for key in res}
    for b in range(B):
        shuffled = {s: shuffled_prices(t, c, rng) for s, (t, c) in series.items()}
        for rule in RULES:
            ps = {s: side_series(shuffled[s], series[s][0], *costs[s], rule=rule) for s in series}
            for gname, syms in groups.items():
                for per in PERIODS:
                    gs = group_stats(ps, syms, per)
                    for k in KEYS:
                        null[f"{rule}|{gname}|{per}"][k].append(gs[k]["mean"])
    for key in res:
        for k in KEYS:
            res[key][k]["z"], res[key][k]["pct"] = z_against_null(res[key][k]["mean"], null[key][k])
            v = np.asarray(null[key][k], float)
            res[key][k]["null_mean"] = float(np.nanmean(v)) if len(v) else float("nan")
            res[key][k]["null_sd"] = float(np.nanstd(v, ddof=1)) if len(v) > 1 else float("nan")

    verdict = judge(res, "donchian")
    verdict_sub = judge(res, "tsmom")
    identity_check = {key: dict(long_adj_minus_short_adj=float(res[key]["long_adj"]["mean"] - res[key]["short_adj"]["mean"]),
                                z_long_minus_z_short=float(res[key]["long_adj"]["z"] - res[key]["short_adj"]["z"]))
                      for key in res}
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q152_by_symbol_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q152_sides_{stamp}.png"))
    out = dict(
        queue_id="Q152", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT,
                      CRYPTO_COST_RT_BP=CRYPTO_COST_RT_BP, CRYPTO_MAX_START_YEAR=CRYPTO_MAX_START_YEAR,
                      syms=list(series.keys()), crypto_used=crypto_used, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0])), end=str(pd.Timestamp(series[s][0][-1])), n=int(len(series[s][1])))
                   for s in series},
        missing=missing,
        results=res, judgement=verdict, judgement_sub_tsmom=verdict_sub, identity_check=identity_check,
        files=dict(by_symbol_csv=csv_path, png=png_path),
        multiple_comparisons="2規則 × 3群 × 2側 × 2（生/ドリフト除去）× 3期間 = 72 本。判定は主ドンチャン簡略版の 2群（トレンド7・暗号資産）× 2側 のドリフト除去後・全期間 = 4 本（副 TSMOM20 の 4 本は参考）",
        deviations_from_prereg=["暗号資産（BTC 以外）の往復コストは登録が無いので相対 30bp を置いた（CRYPTO_COST_RT_BP）",
                                "暗号資産 H4 の TSMOM20 は 20 本（≈3.3日）。日足の 20 日と日数が違う点は明記のみ",
                                "ドリフト除去の『同じ期間』は評価期間（全期間／前半／後半）ごとに 1 本",
                                "恒等式のため主を入れ替えた（Fable 承認 2026-10-09）: 主=ドンチャン簡略版 55/20（休む期間あり）、副=TSMOM20（恒等式の確認用、identity_check）。判定の規則は登録どおり"],
    )
    jpath = os.path.join(OUT, f"{prefix}Q152_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q152] syms={len(series)} (crypto={crypto_used})  B={B}  smoke={args.smoke}  missing={missing}")
    for rule in RULES:
      for per in PERIODS:
        for gname in groups:
            r = res[f"{rule}|{gname}|{per}"]
            if r["n_syms"] == 0:
                print(f"  {rule:8s} {per:3s} {gname:5s} (銘柄なし)"); continue
            print(f"  {rule:8s} {per:3s} {gname:5s} n_sym={r['n_syms']:2d} expoL={r['expo_long']:.2f} expoS={r['expo_short']:.2f} drift={r['drift_bp']:+.2f}bp | " +
                  " ".join(f"{k}={r[k]['mean']:+.2f}(t{r[k]['t']:+.1f},z{r[k]['z']:+.1f})" for k in KEYS))
    print("  判定(機械・主 ドンチャン簡略版):", verdict["verdict"])
    print("  参考(副 TSMOM20):", verdict_sub["verdict"])
    print("  恒等式の確認(副 TSMOM20・全期間 long_adj−short_adj):", {g: round(identity_check[f"tsmom|{g}|全期間"]["long_adj_minus_short_adj"], 4) for g in groups})
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
