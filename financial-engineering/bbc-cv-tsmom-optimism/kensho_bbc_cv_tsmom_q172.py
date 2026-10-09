#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q172: BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018）
================================================================================

【出典】
- Tsamardinos ほか 2018（BBC-CV）: 期間外予測の行列を行方向にブートストラップし、最良選択を繰り返して
  選ばれなかった行で成績を測ることで、追加の学習なく「選んだ最良の楽観」をほぼ取り除ける（§4・§6.1）。
  著者は「行の独立性が前提。時系列ではブロック化が要る」と限界に明記（結論 §7・p27–28）。
- 論文ノート: [[Tsamardinosほか2018_交差検証で選んだ最良の楽観をブートストラップで補正する]]
- 隣接の既存検証: Q139（選択の楽観 vs J）、Q036（Kaggle・RC/SPA）、Alonso 2026 下側限界

【仮説（測る前に固定・事前登録）】
H1（削減）: BBC-CV の残留偏り |mean(BBC - OOS)| は、素朴な選択の楽観 |mean(Naive - OOS)| の
    30% 以下まで小さくなる（ブロック長 BLOCK=20 固定、J=60）。
H2（較正）: 年を単位にした残留偏りの t 統計量 |t_year(BBC - OOS)| < 2（0 と区別できない）。

対立: 時系列の自己相関で、独立行の BBC（行ばらばらのブートストラップ）では楽観が残る。
    ブロック化しても、相互作用（候補間の相関）やドリフトで残る可能性がある。

【データ】
15銘柄 `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足、2008〜2026-07）。無いファイルは除く。

【定義（1通りに固定）】
- 候補: TSMOM の参照日数 L ∈ {5, 10, 15, …, 300}（60 通り）。s_t = sign(c_t − c_{t−L})、翌日ポジ。
  日次純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（COST_RT/2 を bp 換算）。L+1 日未満は nan。
- 年 t（暦年）: 定義された日が MIN_DAYS=100 未満の年は使わない。
- Naive: 年 t の候補ごとの平均を取り、最大を与える L を L*。Naive_t(L*) = mean_days_in_t(PnL(L*))。
- OOS: 翌年 t+1 の同じ L* の平均。OOS_t = mean_days_in_{t+1}(PnL(L*))。
- BBC-CV: 年 t の n 日からブロック長 BLOCK=20 のムービングブロック・ブートストラップで in-bag を n 日選ぶ。
  重複した行番号から選ばれなかった元の日の集合 = out-of-bag。
  in-bag で候補ごとの平均を取り、最大の L を L*_b。out-of-bag の L*_b の平均 = BBC_b。
  BBC_t = mean_b(BBC_b)（B=NBOOT 回。out-of-bag が MIN_OOB=20 未満の試行は捨てる）。
- 楽観 Opt_t = Naive_t − OOS_t。残留 Res_t = BBC_t − OOS_t。
- 集計: (銘柄, 年 t) をプールして、全15／FX8／トレンド7、前半 t<2017／後半 t≥2017／全期間で平均・t。

【測るもの】
- mean(Opt)、mean(Res)、ratio = |mean(Res)| / |mean(Opt)|
- 年単位 t: t_year(Opt)、t_year(Res)
- 条件付き数値: 「Naive が正の勝ちセル」だけに絞った同じ量（オンライン運用で意味のある部分集合）

【帰無】
翌年 t+1 のリターンだけを並べ替え（各暦年の中で日次対数リターンを並べ替えて価格を作り直す）。
楽観 Opt が「選択の楽観だけで生じる」分と比較。B_NULL=200。
（BBC の残留は内部で既にブートストラップしているため、BBC の帰無は作らない。目的は BBC の性能評価。）

【判定（事前固定・変更禁止）】
前半・後半のそれぞれで:
- 前提: 年単位の t_year(Opt) ≥ 2（楽観がそもそも年ごとに安定して正）。満たさなければ H1 判定不能。
- H1 支持: ratio ≤ 0.3（BBC が楽観の 70% 以上を削る）。
- H1 棄却: ratio ≥ 0.7（BBC が楽観の 30% も削れない）。
- H1 未確定: 0.3 < ratio < 0.7。
- H2 支持: |t_year(Res)| < 2。棄却: |t_year(Res)| ≥ 2。
- 全体判定（verdict）: 前半と後半で H1 と H2 の判定が一致したらその判定、割れたら「未確定」。
- z_vs_null はコンテキスト用。帰無は「翌年ランダム」で OOS をゼロ中心にずらすため、Opt の存在検定には使わない。

多重比較: 期間 3 × 群 3 の集計の中で、判定に使うのは「全15」の前半・後半だけ。他は副次。

【捨てた案の数】
約 6:
  (a) J を 1〜60 で変える（J 依存は Q139 で既に測った。本検証は J=60 固定で BBC の性能に集中）、
  (b) ブロック長 BLOCK を可変（BLOCK=5/20/60 でのロバスト性は副次指標として吐くが判定には使わない）、
  (c) 円滑化ブートストラップや定常ブートストラップ（ムービングブロックで統一、Politis & Romano は未参照）、
  (d) OOS を「翌年」ではなく「期間末まで保持」する（Q139 と揃えるため翌年のみ）、
  (e) 残留をコスト前で評価（既にコスト後で統一）、
  (f) BBC を「全日の予測行列から」行う（Tsamardinos の原形は CV の OOS 予測の行列。本検証は年 t 内で
      ブートストラップするので、より保守的。原形 BBC-CV の実装には年を跨ぐ CV が要るため）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証の量（BBC の残留偏りが
素朴な楽観の何割かという比）は、特定の年の相場観では作れない。

【委託の確かめ方】
設計はこのファイル。コードは Claude Opus 4.7（この下請け）。実行者は、結論ではなく、
結果 JSON のパス・主要な数値（期間ごとの Opt / Res / ratio / t / z_vs_null）・原典（Tsamardinos §4・§6.1・§7）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定のブートストラップと並べ替え）。
依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_bbc_cv_tsmom_q172.py            （NBOOT=500, B_NULL=200、15 分前後）
      python3 kensho_bbc_cv_tsmom_q172.py --B 50 --B-null 30   （軽い試走）
      python3 kensho_bbc_cv_tsmom_q172.py --smoke   （合成データで経路の確認。結果は results/smoke_*）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import time
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
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LS = list(range(5, 305, 5))                 # 60 候補
J_FIXED = 60                                 # 全候補を使う（Q139 で J 依存は既に測った）
ALPHA = 0.05
MIN_DAYS = 100
MIN_OOB = 20
BLOCK = 20
SPLIT_YEAR = 2017
NBOOT_DEFAULT = 500
NULL_B_DEFAULT = 200
SEED = 20261009
RATIO_HI, RATIO_LO = 0.7, 0.3
T_YEAR_TH = 2.0
Z_NULL_TH = 2.0


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
    return float(z), float((v < obs).mean())


def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


# ----------------------------------------------------------------------------- ルール（60 候補をまとめて）
def pnl_matrix(c, cost_rt):
    """全候補 L の日次純損益 [bp]（n × 60）。未定義の日は nan。"""
    n = len(c)
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    M = np.full((n, len(LS)), np.nan)
    for j, L in enumerate(LS):
        s = np.full(n, np.nan); s[L:] = np.sign(c[L:] - c[:-L])
        pos_prev = np.concatenate([[np.nan], s[:-1]])
        pp = np.where(np.isfinite(pos_prev), pos_prev, 0.0)
        dpos = np.abs(np.diff(np.concatenate([[0.0], pp])))
        pnl = pp * ret * 1e4 - dpos * cost_bp
        pnl[:L + 1] = np.nan
        M[:, j] = pnl
    return M


def shuffled_prices_by_year(c, years, rng):
    """各暦年の中で日次対数リターンを並べ替え、価格を作り直す。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    r2 = r.copy()
    for y in np.unique(years):
        idx = np.flatnonzero(years == y); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    return np.exp(np.log(c[0]) + np.cumsum(r2))


# ----------------------------------------------------------------------------- BBC-CV の中身
def bbc_estimate(sub, nboot, block, rng):
    """
    sub: その年の日次純損益 (n × 60)、nan を含んで良い。
    返り値: BBC 推定（out-of-bag で評価した最良の平均の、ブートストラップ平均）、使えた試行数。
    """
    n = sub.shape[0]
    if n < max(MIN_DAYS, 2 * block):
        return float("nan"), 0
    nb = (n + block - 1) // block
    bbc_vals = []
    for _ in range(nboot):
        starts = rng.integers(0, n - block + 1, size=nb)
        idx_in = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        in_bag_mask = np.zeros(n, dtype=bool)
        in_bag_mask[np.unique(idx_in)] = True
        oob = ~in_bag_mask
        if oob.sum() < MIN_OOB:
            continue
        # in-bag で候補ごとの平均（nan を除く）→ 最良 L*_b
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            # in-bag の実際の重複を反映するには、idx_in（重複あり）で平均をとる
            in_sub = sub[idx_in]           # (n, 60) すべての行（重複含む）
            cnt = np.isfinite(in_sub).sum(axis=0)
            if (cnt < MIN_DAYS).all():
                continue
            mean_in = np.where(cnt >= MIN_DAYS,
                                np.nansum(in_sub, axis=0) / np.maximum(cnt, 1),
                                np.nan)
            if np.isfinite(mean_in).sum() == 0:
                continue
            k = int(np.nanargmax(mean_in))
            # out-of-bag の L*_b の平均
            oob_vals = sub[oob, k]
            oob_vals = oob_vals[np.isfinite(oob_vals)]
            if len(oob_vals) < MIN_OOB:
                continue
            bbc_vals.append(float(oob_vals.mean()))
    if not bbc_vals:
        return float("nan"), 0
    return float(np.mean(bbc_vals)), len(bbc_vals)


def naive_oos(sub, sub_next):
    """Naive（年内最良）と OOS（翌年の同じ L の平均）、L*、σ、n_days。"""
    n = sub.shape[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cnt = np.isfinite(sub).sum(axis=0)
        ok = cnt >= MIN_DAYS
        if not ok.any():
            return float("nan"), float("nan"), -1, float("nan"), 0
        mean_in = np.where(ok, np.nanmean(sub, axis=0), np.nan)
        if np.isfinite(mean_in).sum() == 0:
            return float("nan"), float("nan"), -1, float("nan"), 0
        k = int(np.nanargmax(mean_in))
        naive = float(mean_in[k])
        sigma = float(np.nanstd(sub[:, k], ddof=1)) if np.isfinite(sub[:, k]).sum() >= 2 else float("nan")
        n_days = int(np.isfinite(sub[:, k]).sum())
    oos_vals = sub_next[:, k]
    oos_vals = oos_vals[np.isfinite(oos_vals)]
    oos = float(oos_vals.mean()) if len(oos_vals) >= MIN_DAYS else float("nan")
    return naive, oos, k, sigma, n_days


# ----------------------------------------------------------------------------- セル生成
def build_rows(sym, M, years, nboot, block, rng, M_next_override=None, skip_bbc=False):
    """
    (銘柄, 年 t) ごとに Naive, OOS, BBC を計算。M_next_override は帰無で翌年の予測行列を差し替えるため。
    skip_bbc=True なら BBC を計算しない（帰無で opt だけ欲しいときに使う）。
    """
    ys = np.unique(years)
    rows = []
    for i in range(len(ys) - 1):
        if ys[i + 1] != ys[i] + 1:
            continue
        t = ys[i]
        mask_t = years == t
        mask_next = years == ys[i + 1]
        sub = M[mask_t]
        sub_next = (M if M_next_override is None else M_next_override)[mask_next]
        if sub.shape[0] < MIN_DAYS or sub_next.shape[0] < MIN_DAYS:
            continue
        naive, oos, k, sigma, n_days = naive_oos(sub, sub_next)
        if not np.isfinite(naive) or not np.isfinite(oos):
            continue
        if skip_bbc:
            rows.append(dict(sym=sym, year=int(t), L_star=LS[k] if k >= 0 else -1,
                             n_days=n_days, sigma=sigma,
                             naive=naive, oos=oos, bbc=float("nan"),
                             opt=naive - oos, res=float("nan"), nb_ok=0))
            continue
        bbc, nb_ok = bbc_estimate(sub, nboot, block, rng)
        if not np.isfinite(bbc):
            continue
        rows.append(dict(sym=sym, year=int(t), L_star=LS[k] if k >= 0 else -1,
                         n_days=n_days, sigma=sigma,
                         naive=naive, oos=oos, bbc=bbc,
                         opt=naive - oos, res=bbc - oos, nb_ok=nb_ok))
    return rows


# ----------------------------------------------------------------------------- 集計・判定
def summarize(tab, syms, period, metric_cols=("opt", "res")):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    out = dict(n_cells=int(len(g)), n_syms=int(g.sym.nunique()))
    for col in metric_cols:
        per_year = g.groupby("year")[col].mean()
        m, tt, ny = mean_t(per_year.values)
        out[col] = dict(mean=float(g[col].mean()) if len(g) else float("nan"),
                        year_mean=m, year_t=tt, n_years=ny,
                        median=float(g[col].median()) if len(g) else float("nan"))
    opt_m = out["opt"]["mean"]; res_m = out["res"]["mean"]
    out["ratio_abs"] = (abs(res_m) / abs(opt_m)) if (len(g) and np.isfinite(opt_m) and np.isfinite(res_m) and abs(opt_m) > 1e-12) else float("nan")
    # 条件付き: Naive が正の勝ちセルに絞った同じ量
    gw = g[g.naive > 0]
    if len(gw):
        out["win_subset"] = dict(n_cells=int(len(gw)),
                                 opt_mean=float(gw.opt.mean()),
                                 res_mean=float(gw.res.mean()),
                                 ratio_abs=(abs(gw.res.mean()) / abs(gw.opt.mean())) if abs(gw.opt.mean()) > 1e-12 else float("nan"))
    else:
        out["win_subset"] = dict(n_cells=0, opt_mean=float("nan"), res_mean=float("nan"), ratio_abs=float("nan"))
    return out


def evaluate(obs, nulls):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    res = {}
    for gname, syms in groups.items():
        for per in ("前半", "後半", "全期間"):
            o = summarize(obs, syms, per)
            null_opt_means = []
            for nt in nulls:
                s = summarize(nt, syms, per)
                null_opt_means.append(s["opt"]["mean"])
            o["null_opt_mean"] = float(np.nanmean(null_opt_means)) if null_opt_means else float("nan")
            o["null_opt_p95"] = float(np.nanpercentile(null_opt_means, 95)) if null_opt_means else float("nan")
            o["z_opt_vs_null"], o["pct_opt_vs_null"] = z_against_null(o["opt"]["mean"], null_opt_means)
            res[f"{gname}|{per}"] = o
    return res


def _tag(s):
    """判定文字列のうち、前後半の一致判定に使う部分（数値部を除いた）タグを取り出す。"""
    for key in ("支持", "棄却", "未確定", "判定不能"):
        if s.startswith(key):
            return key
    return s


def judge(res):
    out = {}
    for per in ("前半", "後半"):
        r = res[f"全15|{per}"]
        ratio = r["ratio_abs"]
        t_year_opt = r["opt"]["year_t"]
        t_year_res = r["res"]["year_t"]
        # H1 判定（前提: t_year(Opt) >= 2 で楽観が年ごとに安定して正）
        if not np.isfinite(t_year_opt) or t_year_opt < T_YEAR_TH:
            h1 = f"判定不能（楽観が年ごとに安定しない t_y={t_year_opt:.2f}）"
        elif not np.isfinite(ratio):
            h1 = "判定不能（ratio=nan）"
        elif ratio <= RATIO_LO:
            h1 = f"支持（BBC は楽観を 70% 以上削る ratio={ratio:.2f}）"
        elif ratio >= RATIO_HI:
            h1 = f"棄却（BBC は楽観を 30% も削れない ratio={ratio:.2f}）"
        else:
            h1 = f"未確定（30%<削減<70% ratio={ratio:.2f}）"
        # H2 判定
        if not np.isfinite(t_year_res):
            h2 = "判定不能"
        elif abs(t_year_res) < T_YEAR_TH:
            h2 = f"支持（残留は 0 と区別できない |t|={abs(t_year_res):.2f}）"
        else:
            h2 = f"棄却（残留に偏りあり |t|={abs(t_year_res):.2f}）"
        out[per] = dict(ratio_abs=ratio, t_year_opt=t_year_opt, t_year_res=t_year_res, h1=h1, h2=h2)
    h1_v = out["前半"]["h1"] if _tag(out["前半"]["h1"]) == _tag(out["後半"]["h1"]) else "未確定（前後半で割れた）"
    h2_v = out["前半"]["h2"] if _tag(out["前半"]["h2"]) == _tag(out["後半"]["h2"]) else "未確定（前後半で割れた）"
    # 一致した場合、具体的な値はまとめ直す
    if h1_v != "未確定（前後半で割れた）":
        tag = _tag(h1_v)
        h1_v = f"{tag}（前半 ratio={out['前半']['ratio_abs']:.2f}, 後半 ratio={out['後半']['ratio_abs']:.2f}）"
    if h2_v != "未確定（前後半で割れた）":
        tag = _tag(h2_v)
        h2_v = f"{tag}（前半 |t|={abs(out['前半']['t_year_res']):.2f}, 後半 |t|={abs(out['後半']['t_year_res']):.2f}）"
    return dict(by_period=out, verdict_h1=h1_v, verdict_h2=h2_v,
                thresholds=dict(ratio_lo=RATIO_LO, ratio_hi=RATIO_HI,
                                t_year=T_YEAR_TH, z_null=Z_NULL_TH),
                note="事前固定の規則で機械的に付けた判定（全15）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


# ----------------------------------------------------------------------------- 本流
def run(nboot, nnull, block, smoke):
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    data_span = {}
    missing = []
    obs_rows = []
    null_rows_list = [[] for _ in range(nnull)]
    syms_used = []
    for sym in SYMS:
        try:
            if smoke:
                # 合成データ: AR(1) ドリフト小、年ごと 260 日 × 10 年
                yrs = np.repeat(np.arange(2010, 2020), 260)
                rng2 = np.random.default_rng(hash(sym) & 0xffff_ffff)
                r = rng2.normal(0, 0.01, size=len(yrs))
                for i in range(1, len(r)):
                    r[i] += 0.05 * r[i - 1]
                c = np.exp(np.cumsum(r))
                times = pd.date_range("2010-01-01", periods=len(c), freq="B")
                d = pd.DataFrame(dict(time=times, high=c * 1.001, low=c * 0.999, close=c))
            else:
                d = load_daily(sym)
            syms_used.append(sym)
            data_span[sym] = dict(start=str(d.time.iloc[0].date()), end=str(d.time.iloc[-1].date()), n=int(len(d)))
            c = d.close.values.astype(float)
            years = pd.to_datetime(d.time).dt.year.values if not smoke else yrs
            M = pnl_matrix(c, COST_RT[sym])
            rng_s = np.random.default_rng(SEED + hash(sym) & 0xffff_ffff)
            obs_rows.extend(build_rows(sym, M, years, nboot, block, rng_s))
            # 帰無: 翌年の価格を並べ替えて作る（M_next_override のため全日の shuffle 版を作って同じ pnl_matrix を回す）
            for b in range(nnull):
                rng_b = np.random.default_rng(SEED + 1000 + b + hash(sym) % 10_000)
                c_sh = shuffled_prices_by_year(c, years, rng_b)
                M_sh = pnl_matrix(c_sh, COST_RT[sym])
                null_rows_list[b].extend(build_rows(sym, M, years, nboot, block, rng_b,
                                                    M_next_override=M_sh, skip_bbc=True))
        except FileNotFoundError:
            missing.append(sym)
            continue
    obs = pd.DataFrame(obs_rows)
    nulls = [pd.DataFrame(r) for r in null_rows_list]
    res = evaluate(obs, nulls)
    jd = judge(res)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if smoke else ""
    cells_path = os.path.join(OUT, f"{prefix}Q172_cells_{ts}.csv")
    result_path = os.path.join(OUT, f"{prefix}Q172_result_{ts}.json")
    obs.to_csv(cells_path, index=False)
    out = dict(queue_id="Q172", script=os.path.basename(__file__),
               run_at=ts, smoke=bool(smoke),
               settings=dict(LS=LS, J_FIXED=J_FIXED, BLOCK=block, NBOOT=nboot, NULL_B=nnull,
                             MIN_DAYS=MIN_DAYS, MIN_OOB=MIN_OOB, ALPHA=ALPHA, SPLIT_YEAR=SPLIT_YEAR,
                             COST_RT=COST_RT, SEED=SEED),
               data_span=data_span, missing=missing, n_symbols_used=len(syms_used),
               n_cells=int(len(obs)),
               results={k: {kk: vv for kk, vv in v.items()} for k, v in res.items()},
               judgement=jd,
               files=dict(cells=os.path.relpath(cells_path, HERE)),
               multiple_comparisons=dict(groups=3, periods=3, hypotheses=2,
                                         judged="全15 の 前半・後半 の H1・H2 のみ。他は副次。"))
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=lambda o: float(o) if hasattr(o, "item") else str(o))
    print(f"[Q172] n_cells={len(obs)}  cells={cells_path}  result={result_path}")
    for per in ("前半", "後半", "全期間"):
        r = res[f"全15|{per}"]
        print(f"  全15|{per}: n={r['n_cells']}  Opt={r['opt']['mean']:+.3f} (t_y={r['opt']['year_t']:+.2f}, z_null={r['z_opt_vs_null']:+.2f})  Res={r['res']['mean']:+.3f} (t_y={r['res']['year_t']:+.2f})  ratio={r['ratio_abs']}")
    print(f"  verdict H1={jd['verdict_h1']}")
    print(f"  verdict H2={jd['verdict_h2']}")
    return out


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--B", type=int, default=NBOOT_DEFAULT, help="BBC のブートストラップ回数")
    p.add_argument("--B-null", dest="bnull", type=int, default=NULL_B_DEFAULT, help="並べ替え帰無の回数")
    p.add_argument("--block", type=int, default=BLOCK, help="ムービングブロック長")
    p.add_argument("--smoke", action="store_true", help="合成データで経路の確認のみ")
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    t0 = time.time()
    run(a.B, a.bnull, a.block, a.smoke)
    print(f"[Q172] elapsed={time.time()-t0:.1f}s")
