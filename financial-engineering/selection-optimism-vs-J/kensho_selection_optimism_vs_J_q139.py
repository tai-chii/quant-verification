#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q139: 候補数 J を増やすと選択の楽観はどれだけ増え、Alonso の下側限界はそれを覆うか
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q139（Fable 2026-10-09）＝ アイデア候補.md の行。
- 論文ノート: Alonso2026_意思決定理論とAI_回帰誤差とルーティング後悔（§5.5・§11 定理 11.1: 候補を先に固定すれば
  下側限界 √(log(J/α)/(2n)) が出せる。時系列の依存は扱えない p28）。
- Tsamardinos ほか 2018（交差検証で選んだ最良の楽観をブートストラップで補正する）、知見（Q036）。

【仮説（測る前に固定）】
H1: 候補数 J が大きいほど、選択年の最良の純損益と翌年の同じ候補の純損益の差（楽観）は大きい（J について単調）。
H2: Alonso の下側限界の幅 √(log(J/α)/(2n)) × 日次 SD は、実際の楽観を覆う（限界 ≥ 実差の 90%）。
    対立: 時系列の依存で限界が狭すぎる（70% 未満）＝ Alonso p28 の注意の実証。

【データ】
15銘柄 `data_<SYM>_D1_fromH1.csv`（Dukascopy、UTC 日足。値動きのない足は除く）。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 候補 = TSMOM の参照日数 L ∈ {5, 10, 15, …, 300}（60 通り）。s_t = sign(c_t − c_{t−L})、翌日のポジション。
  日次純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（COST_RT/2 を bp 換算）。L 日未満の日は未定義（nan）。
- J ∈ {1, 2, 4, 8, 16, 32, 60}: 候補の先頭から J 個（L=5…5J）を使う（固定・順序は L の昇順）。
- 年 t（暦年）の候補ごとの純損益 = その年の定義された日の平均 [bp/日]。定義された日が MIN_DAYS=100 未満の年は使わない。
- 選択: 年 t で J 個の候補のうち純損益が最大の L* を選ぶ。楽観 O_J(s,t) = P_t(L*) − P_{t+1}(L*)。
  （翌年 t+1 も MIN_DAYS 以上で定義されている (銘柄, 年) だけ。）
- Alonso の限界の幅 W_J(s,t) = √(log(J/α)/(2n)) × σ、α=0.05、n = 年 t の日数、σ = 年 t の L* の日次純損益の標準偏差 [bp]。
  比 = 限界が実差を覆う割合 = mean(W_J) / mean(O_J)（期間・J ごと。mean(O_J) ≤ 0 なら inf＝覆う）。
- 集計: 銘柄×年でプールした平均と、年を単位にした t（年ごとに銘柄平均 → 年数で t）。

【測るもの】
期間: 前半（選択年 t < 2017）／後半（t ≥ 2017）／全期間。
各 J: 楽観の平均・年単位の t・限界の平均・比。J の 7 点と楽観の平均の Spearman（単調性）。
帰無に対する z: 楽観の平均（J ごと）。

【帰無】
翌年のリターンを並べ替え（各暦年の中で日次対数リターンを並べ替えた価格列を作り、翌年 t+1 の純損益をそこから出す。
選択は実データの年 t のまま）。楽観が選択だけで生じる分。B=300。

【判定（事前固定・変更禁止）】
前半・後半のそれぞれで:
- Spearman(J, 楽観の平均) ≥ 0.8（7 点）→「選択の楽観は J で増える」＝支持。< 0.8 → 棄却。
- 比（J ≥ 2 の 6 点の中央値）≥ 0.9 →「限界は使える」。< 0.7 →「時系列では限界が狭すぎる」（Alonso p28）。間は未確定。
前半と後半で割れたら未確定。
多重比較: J 7 点 × 期間 2 の t（判定は単調性と比の 2 本 × 2 期間）。

【捨てた案の数】
約5: 候補をランダムに J 個選ぶ案（固定の先頭 J 個が登録）、σ を全候補の平均 SD にする案（選んだ候補の SD が定理の n·σ に
近い）、比を J ごとに全部 0.9 以上と要求する案（1 点の揺れで割れる → 中央値）、楽観を翌年の最良との差にする案
（それは別の量）、ブートストラップで楽観を補正する案（Tsamardinos は別の検証へ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。本検証の量（選択年と翌年の差の J 依存）は特定の年の
相場観だけでは作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude Fable 5.1（この下請け）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（J ごとの楽観・Spearman・比・z）・原典（Alonso §11 定理 11.1・p28）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_selection_optimism_vs_J_q139.py            （B=300、数分）
      python3 kensho_selection_optimism_vs_J_q139.py --B 30     （軽い試走）
      python3 kensho_selection_optimism_vs_J_q139.py --smoke    （合成データで経路の確認。結果は results/smoke_*）
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
# 段階1の保守的な往復コスト（価格単位）。kensho_donchian_regime.py と同じ値。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LS = list(range(5, 305, 5))                 # 60 候補
JS = [1, 2, 4, 8, 16, 32, 60]
ALPHA = 0.05
MIN_DAYS = 100
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009
MONO_TH, COVER_HI, COVER_LO = 0.8, 0.9, 0.7


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
        pos_prev = np.concatenate([[np.nan], s[:-1]])         # t 日のポジション = s_{t−1}
        pp = np.where(np.isfinite(pos_prev), pos_prev, 0.0)
        dpos = np.abs(np.diff(np.concatenate([[0.0], pp])))
        pnl = pp * ret * 1e4 - dpos * cost_bp
        pnl[:L + 1] = np.nan
        M[:, j] = pnl
    return M


def yearly_table(M, years):
    """年ごとの候補の純損益平均 (years × 60)、日次 SD (years × 60)、日数。MIN_DAYS 未満の年は nan。"""
    ys = np.unique(years)
    P = np.full((len(ys), len(LS)), np.nan); S = np.full((len(ys), len(LS)), np.nan); N = np.zeros(len(ys), int)
    for i, y in enumerate(ys):
        m = years == y
        sub = M[m]
        cnt = np.isfinite(sub).sum(axis=0)
        ok = cnt >= MIN_DAYS
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mu = np.nanmean(np.where(ok, sub, np.nan), axis=0) if ok.any() else np.full(len(LS), np.nan)
            sd = np.nanstd(np.where(ok, sub, np.nan), axis=0, ddof=1) if ok.any() else np.full(len(LS), np.nan)
        P[i] = np.where(ok, mu, np.nan); S[i] = np.where(ok, sd, np.nan); N[i] = int(m.sum())
    return ys, P, S, N


def shuffled_prices_by_year(c, years, rng):
    """各暦年の中で日次対数リターンを並べ替え、価格を作り直す。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    r2 = r.copy()
    for y in np.unique(years):
        idx = np.flatnonzero(years == y); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    return np.exp(np.log(c[0]) + np.cumsum(r2))


# ----------------------------------------------------------------------------- 楽観の表
def optimism_rows(sym, ys, P, S, N, P_next=None):
    """(銘柄, 選択年 t, J) ごとの楽観と限界。P_next を渡せば翌年はそちら（帰無）。"""
    Pn = P if P_next is None else P_next
    rows = []
    for i in range(len(ys) - 1):
        if ys[i + 1] != ys[i] + 1:
            continue
        for J in JS:
            p_sel = P[i, :J]
            if not np.isfinite(p_sel).all() or not np.isfinite(Pn[i + 1, :J]).all():
                continue
            k = int(np.argmax(p_sel))
            n = int(np.isfinite(P[i, k]) and N[i])
            sigma = S[i, k]
            W = math.sqrt(math.log(J / ALPHA) / (2.0 * n)) * sigma if n > 0 and np.isfinite(sigma) else float("nan")
            rows.append(dict(sym=sym, year=int(ys[i]), J=J, L_star=LS[k], P_sel=float(P[i, k]), P_next=float(Pn[i + 1, k]),
                             optimism=float(P[i, k] - Pn[i + 1, k]), bound=float(W), sigma=float(sigma), n_days=n))
    return rows


def summarize(tab, syms, period):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    out = {}
    for J in JS:
        h = g[g.J == J]
        per_year = h.groupby("year")["optimism"].mean()
        m, tt, ny = mean_t(per_year.values)
        mean_opt = float(h.optimism.mean()) if len(h) else float("nan")
        mean_bd = float(h.bound.mean()) if len(h) else float("nan")
        cover = (float("inf") if mean_opt <= 0 else mean_bd / mean_opt) if (len(h) and np.isfinite(mean_opt) and np.isfinite(mean_bd)) else float("nan")
        out[J] = dict(n_cells=int(len(h)), optimism_mean=mean_opt, optimism_year_mean=m, optimism_year_t=tt, n_years=ny,
                      bound_mean=mean_bd, cover_ratio=cover,
                      share_bound_covers=float((h.bound >= h.optimism).mean()) if len(h) else float("nan"),
                      P_sel_mean=float(h.P_sel.mean()) if len(h) else float("nan"),
                      P_next_mean=float(h.P_next.mean()) if len(h) else float("nan"))
    opt = [out[J]["optimism_mean"] for J in JS]
    out["spearman_J_optimism"] = spearman(JS, opt)
    cov = [out[J]["cover_ratio"] for J in JS if J >= 2]
    cov = [min(c, 1e9) for c in cov if np.isfinite(c) or c == float("inf")]
    out["cover_ratio_median_Jge2"] = float(np.median(cov)) if cov else float("nan")
    return out


def evaluate(obs, nulls):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    res = {}
    for gname, syms in groups.items():
        for per in ("前半", "後半", "全期間"):
            o = summarize(obs, syms, per)
            ns = [summarize(nt, syms, per) for nt in nulls]
            for J in JS:
                nv = [s[J]["optimism_mean"] for s in ns]
                o[J]["null_optimism_mean"] = float(np.nanmean(nv)) if nv else float("nan")
                o[J]["null_optimism_p95"] = float(np.nanpercentile(nv, 95)) if nv else float("nan")
                o[J]["z_vs_null"], o[J]["pct_vs_null"] = z_against_null(o[J]["optimism_mean"], nv)
            nsp = [s["spearman_J_optimism"] for s in ns]
            o["null_spearman_mean"] = float(np.nanmean(nsp)) if nsp else float("nan")
            res[f"{gname}|{per}"] = {str(k): v for k, v in o.items()}
    return res


def judge(res):
    out = {}
    for per in ("前半", "後半"):
        r = res[f"全15|{per}"]
        sp = r["spearman_J_optimism"]; cov = r["cover_ratio_median_Jge2"]
        mono = "支持（楽観は J で増える）" if (np.isfinite(sp) and sp >= MONO_TH) else "棄却（単調でない）"
        if not np.isfinite(cov):
            bound = "判定不能"
        elif cov >= COVER_HI:
            bound = "限界は使える"
        elif cov < COVER_LO:
            bound = "時系列では限界が狭すぎる（Alonso p28）"
        else:
            bound = "未確定"
        out[per] = dict(spearman=sp, monotone=mono, cover_ratio_median=cov, bound=bound)
    mono_v = out["前半"]["monotone"] if out["前半"]["monotone"] == out["後半"]["monotone"] else "未確定（前後半で割れた）"
    bound_v = out["前半"]["bound"] if out["前半"]["bound"] == out["後半"]["bound"] else "未確定（前後半で割れた）"
    return dict(by_period=out, verdict_monotone=mono_v, verdict_bound=bound_v,
                thresholds=dict(spearman=MONO_TH, cover_hi=COVER_HI, cover_lo=COVER_LO),
                note="事前固定の規則で機械的に付けた判定（全15）。解釈（確定／ノイズ／未確定）は実行者が記録する。")


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
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.3))
        for a, per in zip(ax, ("前半", "後半")):
            r = res[f"全15|{per}"]
            a.plot(JS, [r[str(J)]["optimism_mean"] for J in JS], "o-", label="楽観（選択年−翌年）")
            a.plot(JS, [r[str(J)]["bound_mean"] for J in JS], "s--", label="Alonso の限界の幅")
            a.plot(JS, [r[str(J)]["null_optimism_mean"] for J in JS], "x:", c="gray", label="帰無の楽観")
            a.set_xscale("log"); a.set_xlabel("J（候補数）"); a.set_ylabel("bp/日"); a.axhline(0, lw=.6, c="k")
            a.set_title(f"{per}: Spearman(J,楽観)={r['spearman_J_optimism']:+.2f} 比={r['cover_ratio_median_Jge2']:.2f}"); a.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    series, missing = {}, {}
    if args.smoke:
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
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
            if not os.path.exists(f):
                missing[sym] = "ファイルなし"; continue
            try:
                d = load_daily(sym)
            except Exception as e:
                missing[sym] = str(e); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B

    obs_rows, info = [], {}
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        ys, P, S, N = yearly_table(pnl_matrix(c, COST_RT[sym]), years)
        info[sym] = (years, ys, P, S, N)
        obs_rows.extend(optimism_rows(sym, ys, P, S, N))
    obs = pd.DataFrame(obs_rows)
    nulls = []
    for b in range(B):
        rows = []
        for sym, (t, c) in series.items():
            years, ys, P, S, N = info[sym]
            c2 = shuffled_prices_by_year(c, years, rng)
            _, P2, _, _ = yearly_table(pnl_matrix(c2, COST_RT[sym]), years)
            rows.extend(optimism_rows(sym, ys, P, S, N, P_next=P2))
        nulls.append(pd.DataFrame(rows))
    res = evaluate(obs, nulls)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q139_cells_{stamp}.csv"); obs.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q139_curve_{stamp}.png"))
    out = dict(
        queue_id="Q139", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, JS=JS, ALPHA=ALPHA, MIN_DAYS=MIN_DAYS, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      null="各暦年の中で日次対数リターンを並べ替えた価格列から翌年の純損益を出す（選択は実データの年 t）"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        missing=missing, n_symbols_used=len(series), n_cells=int(len(obs)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, curve_png=png_path),
        multiple_comparisons="J 7 点 × 期間 2 の年単位 t ＝ 14（判定は 単調性 Spearman と 比の中央値 の 2 本 × 2 期間）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q139_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[Q139] cells={len(obs)}  B={B}  smoke={args.smoke}  missing={list(missing)}")
    for per in ("前半", "後半", "全期間"):
        r = res[f"全15|{per}"]
        print(f"  {per:3s} 全15  Spearman(J,楽観)={r['spearman_J_optimism']:+.2f}  比(中央値,J≥2)={r['cover_ratio_median_Jge2']:.2f}  null Spearman={r['null_spearman_mean']:+.2f}")
        for J in JS:
            x = r[str(J)]
            print(f"      J={J:2d} n={x['n_cells']:3d} 楽観={x['optimism_mean']:+.2f}bp (t_year={x['optimism_year_t']:+.2f}) 限界={x['bound_mean']:.2f} 比={x['cover_ratio']:.2f} "
                  f"covers={x['share_bound_covers']:.2f}  null 楽観={x['null_optimism_mean']:+.2f} z={x['z_vs_null']:+.2f}")
    print("  判定(機械): 単調性:", verdict["verdict_monotone"], "| 限界:", verdict["verdict_bound"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
