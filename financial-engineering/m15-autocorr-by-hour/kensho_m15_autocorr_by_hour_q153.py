#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q153: 15分足の1次自己相関は時刻で符号が変わるか（USDJPY・EURUSD 2021〜・Holm 補正）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q153（Fable 2026-10-09）。アイデア候補.md の該当行。
- 論文ノート: Neely・Weller2003_為替の日中足テクニカル（30分足に負の1次自己相関）、
  Krohn・Mueller・Whelan2024_為替のフィキシングと一日の中のリターン、Seeck2026_FXの日中モメンタムと円の増幅。
- 既存の知見: USDJPY のロンドン開始30分シグナルは 2025 年以降コスト後に優位性が消える（Q108）、
  為替の超短期の平均回帰は 2015 年以降の1時間足では消えた。
  → 「1時間足で消えた自己相関が、15分足では時刻を限れば残っているか。残っても 1pip のコストに耐えるか」が本検証。

【仮説（測る前に固定）】
H1: UTC の時刻 h によって 15分リターンの1次自己相関 ρ₁(h) の符号が変わり、Holm 補正後にも有意な時刻が
    2021–23 と 2024–26 の両期間で同じ符号で残る。
H2: その時刻で符号どおりに売買（1本保有）すると、片道 1pip のコスト後も純損益が正。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_USDJPY_M15_dukascopy.csv・data_EURUSD_M15_dukascopy.csv
（UTC、足の開始時刻、列 time,open,high,low,close,volume、BID、2021-01〜2026-07）。
無いファイルは除いて件数を JSON に書く。15分足は値動きのない足（high==low）も残す（「直前の足」を実際の直前の
15分にするため。日足の扱いと違う点を明記）。重複時刻は除く。

【定義（1通りに固定）】
- 15分対数リターン r_t = ln(c_t / c_{t−1})。ペア (r_t, r_{t−1}) は、t−1 の足の開始時刻が t のちょうど 15 分前のときだけ使う
  （週末・欠損をまたぐペアは捨てる）。
- 時刻 h = 足 t の開始時刻の UTC の時（0〜23）。ρ₁(h) = ペアのうち h に始まる足での corr(r_t, r_{t−1})。
- t 値: z_t = (r_t − 平均)(r_{t−1} − 平均)/(σ_x σ_y) の平均 ρ に対し、Newey–West（Bartlett、ラグ NW_LAGS=4 ＝ 1時間）
  の標準誤差で t = ρ / se。
- 期間: 前期 2021–2023、後期 2024–2026（UTC 日付の年）。
- Holm 補正: 2通貨 × 24時 × 2期間 = 96 本を 1 つの族として、p = 2(1 − Φ(|t|)) を Holm で補正（α=0.05）。
- 売買: 有意な時刻の集合 H と符号 s_h = sign(ρ₁(h)) について、h に始まる足 t のポジション = s_h × sign(r_{t−1})、
  1本保有（粗利 = pos × (c_t/c_{t−1} − 1) × 1e4 bp）。コスト = |Δpos| × 片道 1pip（pip = USDJPY 0.01、EURUSD 0.0001、
  直前の終値で bp に換算）。集合 H は (i) 各期間の中で有意な時刻（標本内）と (ii) 両期間で同符号に残った時刻
  （両期間に当てはめる）。判定は (ii)。
- 帰無: 足の順序を UTC 日の中で並べ替え（日内の自己相関を壊し、日ごとのリターンの集合と時刻ラベルは保つ）、
  同じ 96 本の t と Holm を B 回 → 「有意な時刻の数」と「max |t|」の分布（族全体の偽陽性の水準）。

【測るもの】
通貨×期間×時刻の ρ₁(h)・NW t・Holm 後の p・有意フラグ。両期間で同符号に残った時刻の数。
その時刻での売買の粗利・1pip 後の純損益（bp/足、合計、年あたり）。帰無での有意数の分布。

【判定（事前固定・変更禁止）】
Holm 補正後に有意な時刻が両期間で同じ符号で残れば「時刻依存の自己相関あり」。残っても片道 1pip 後に（どちらかの期間で）
負なら「売買には使えない」。有意な時刻が 0 なら棄却（H1 の結果と整合）。通貨ごとに付け、総合は 2 通貨を並記。

【捨てた案の数】
約5: 30分足に集計し直す案（Neely–Weller と揃うが 15分の登録に従う）、ρ を回帰の傾きにする案（相関で統一）、
値動きのない足を除く案（直前の足がずれるので残す）、曜日別の分解（族が 5 倍になる）、帰無を「日をまたいで並べ替え」
にする案（日内に限って時刻ラベルの構造を保つ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。ロンドン・NY の開始時刻の値動きが大きいこと、
フィキシング（16:00 ロンドン）周辺の既知の型は知っている。Holm で 96 本をまとめて補正するので、特定の時刻を
後知恵で選ぶ余地はない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、下請け）。実行と解釈は後で Sonnet／Opus。
実行者は結論ではなく、JSON のパス・有意な時刻（通貨・期間・符号）・売買の純損益・原典の箇所を本体に返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas（matplotlib は任意、scipy 不要）。
実行: python3 kensho_m15_autocorr_by_hour_q153.py            （B=300）
      python3 kensho_m15_autocorr_by_hour_q153.py --B 30     （軽い試走）
      python3 kensho_m15_autocorr_by_hour_q153.py --smoke    （合成データで経路の確認。結果は捨てる）
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

SYMS = ["USDJPY", "EURUSD"]
PIP = {"USDJPY": 0.01, "EURUSD": 0.0001}
COST_ONEWAY_PIPS = 1.0
PERIODS = {"2021-23": (2021, 2023), "2024-26": (2024, 2026)}
NW_LAGS = 4
ALPHA = 0.05
NULL_B = 300
SEED = 20261009
MIN_PAIRS = 200


# ----------------------------------------------------------------------------- 基本の道具
def norm_sf2(t):
    """両側 p = 2(1−Φ(|t|))。"""
    return float(math.erfc(abs(t) / math.sqrt(2.0)))


def holm(pvals, alpha=ALPHA):
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(np.where(np.isfinite(p), p, np.inf))
    adj = np.full(n, np.nan)
    running = 0.0
    for rank, i in enumerate(order):
        if not np.isfinite(p[i]):
            continue
        v = min(1.0, (n - rank) * p[i])
        running = max(running, v)
        adj[i] = running
    return adj, np.isfinite(adj) & (adj < alpha)


def nw_mean_t(z, lags=NW_LAGS):
    """z の平均と、Bartlett 加重の Newey–West 標準誤差による t。"""
    z = np.asarray(z, float); n = len(z)
    if n < 10:
        return float("nan"), float("nan"), n
    m = z.mean(); d = z - m
    lrv = (d * d).mean()
    for k in range(1, min(lags, n - 1) + 1):
        w = 1.0 - k / (lags + 1.0)
        lrv += 2.0 * w * (d[k:] * d[:-k]).mean()
    if lrv <= 0:
        return float(m), float("nan"), n
    return float(m), float(m / math.sqrt(lrv / n)), n


def rho_by_hour(r, prev_ok, hour, mask):
    """各 h の ρ₁(h)・NW t・n。r: リターン、prev_ok: 直前の足が 15 分前、hour: 足の時、mask: 期間。"""
    rho = np.full(24, np.nan); tv = np.full(24, np.nan); nn = np.zeros(24, int)
    x_all = r; y_all = np.concatenate([[0.0], r[:-1]])
    base = prev_ok & mask
    for h in range(24):
        m = base & (hour == h)
        n = int(m.sum()); nn[h] = n
        if n < MIN_PAIRS:
            continue
        x = x_all[m]; y = y_all[m]
        sx = x.std(); sy = y.std()
        if sx <= 0 or sy <= 0:
            continue
        z = (x - x.mean()) * (y - y.mean()) / (sx * sy)
        rho[h], tv[h], _ = nw_mean_t(z)
    return rho, tv, nn


# ----------------------------------------------------------------------------- データ
def load_m15(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_M15_dukascopy.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[d.close > 0].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d.time.values, d.close.values.astype(float)


def prepare(t, c):
    t = pd.DatetimeIndex(t)
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    prev_ok = np.zeros(len(c), bool)
    prev_ok[1:] = (t[1:] - t[:-1]) == pd.Timedelta(minutes=15)
    hour = t.hour.values; year = t.year.values
    day_id = (t.year * 10000 + t.month * 100 + t.day).values
    return dict(t=t, c=c, r=r, prev_ok=prev_ok, hour=hour, year=year, day_id=day_id)


def period_mask(D, per):
    y0, y1 = PERIODS[per]
    return (D["year"] >= y0) & (D["year"] <= y1)


def shuffle_within_day(r, day_id, rng):
    """UTC 日の中でリターンを並べ替える（時刻ラベルは動かさない）。"""
    key = rng.random(len(r))
    order = np.lexsort((key, day_id))          # 日ごとにランダム順
    # 日ごとの並びの先頭位置は元と同じ（day_id は既に時間順でソート済みの前提）
    r2 = np.empty_like(r); r2[:] = r[order]
    return r2


# ----------------------------------------------------------------------------- 売買
def trade_pnl(D, hours_sign, mask, pip):
    """hours_sign: {h: ±1}。h に始まる足で pos = s_h × sign(r_{t−1})、1本保有。片道 1pip コスト。"""
    n = len(D["c"]); pos = np.zeros(n)
    y_prev = np.concatenate([[0.0], D["r"][:-1]])
    for h, s in hours_sign.items():
        m = mask & D["prev_ok"] & (D["hour"] == h)
        pos[m] = s * np.sign(y_prev[m])
    ret = np.zeros(n); ret[1:] = D["c"][1:] / D["c"][:-1] - 1.0
    gross = pos * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos])))
    cost_bp = np.zeros(n); cost_bp[1:] = COST_ONEWAY_PIPS * pip / D["c"][:-1] * 1e4
    cost = dpos * cost_bp
    net = gross - cost
    traded = (pos != 0) & mask
    n_bars = int(traded.sum())
    days = max(1, len(np.unique(D["day_id"][mask])))
    return dict(n_hours=len(hours_sign), n_trade_bars=n_bars,
                gross_bp_per_bar=float(gross[traded].mean()) if n_bars else float("nan"),
                net_bp_per_bar=float((gross[mask] - cost[mask]).sum() / n_bars) if n_bars else float("nan"),
                gross_total_bp=float(gross[mask].sum()), net_total_bp=float(net[mask].sum()),
                net_bp_per_year=float(net[mask].sum() / days * 252.0), n_days=days)


# ----------------------------------------------------------------------------- 本体
def run_family(data, r_override=None):
    """2通貨×2期間×24時の ρ・t を出し、96 本を Holm で補正。r_override: {sym: r} で帰無用に差し替え。"""
    rows = []
    for sym, D in data.items():
        r = D["r"] if r_override is None else r_override[sym]
        for per in PERIODS:
            rho, tv, nn = rho_by_hour(r, D["prev_ok"], D["hour"], period_mask(D, per))
            for h in range(24):
                rows.append(dict(sym=sym, period=per, hour=h, n=int(nn[h]), rho=float(rho[h]), t=float(tv[h]),
                                 p=norm_sf2(tv[h]) if np.isfinite(tv[h]) else float("nan")))
    tab = pd.DataFrame(rows)
    adj, sig = holm(tab.p.values)
    tab["p_holm"] = adj; tab["sig_holm"] = sig
    return tab


def both_period_hours(tab, sym):
    """両期間で Holm 後に有意かつ同符号の時刻 → {h: sign}。"""
    g = tab[tab.sym == sym]
    pers = list(PERIODS)
    a = g[g.period == pers[0]].set_index("hour"); b = g[g.period == pers[1]].set_index("hour")
    out = {}
    for h in range(24):
        if h in a.index and h in b.index and a.sig_holm[h] and b.sig_holm[h] and np.sign(a.rho[h]) == np.sign(b.rho[h]) and a.rho[h] != 0:
            out[h] = int(np.sign(a.rho[h]))
    return out


def judge(res_by_sym):
    out = {}
    for sym, r in res_by_sym.items():
        n_both = r["n_hours_both_periods_same_sign"]
        if n_both == 0:
            v = "棄却（Holm 後に両期間で同符号に残る時刻が 0）"
        else:
            nets = [r["trade_both_set"][per]["net_total_bp"] for per in PERIODS]
            if all(np.isfinite(x) and x > 0 for x in nets):
                v = "時刻依存の自己相関あり（1pip 後も両期間で正）"
            else:
                v = "時刻依存の自己相関あり・売買には使えない（1pip 後に負の期間あり）"
        out[sym] = dict(n_hours_both=n_both, hours_both=r["hours_both_periods"], verdict=v)
    return dict(by_symbol=out, verdict=" / ".join(f"{s}: {o['verdict']}" for s, o in out.items()),
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定、H1 の結果との整合）は実行者が記録する。")


def make_plot(tab, path):
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
        syms = list(tab.sym.unique())
        fig, ax = plt.subplots(1, len(syms), figsize=(5.5 * len(syms), 4), squeeze=False)
        for a, sym in zip(ax[0], syms):
            for per, col in zip(PERIODS, ["tab:blue", "tab:orange"]):
                g = tab[(tab.sym == sym) & (tab.period == per)].sort_values("hour")
                a.plot(g.hour, g.rho, "-o", ms=3, c=col, label=per)
                s = g[g.sig_holm]
                a.scatter(s.hour, s.rho, s=60, facecolors="none", edgecolors=col)
            a.axhline(0, lw=.6, c="k"); a.set_xlabel("UTC 時"); a.set_ylabel("rho1(h)")
            a.set_title(f"{sym}: 15分足の1次自己相関（○= Holm 後に有意）"); a.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def synth_m15(rng, base, sigma):
    """合成: 時刻で φ が変わる AR(1)（h=0,8 は +0.15、h=16 は −0.15、他は 0）。平日のみ 96 本/日。"""
    days = pd.bdate_range("2021-01-04", "2026-07-10")
    t = pd.DatetimeIndex(np.concatenate([(pd.Timestamp(d) + pd.to_timedelta(np.arange(96) * 15, unit="m")).values for d in days]))
    n = len(t); hour = t.hour.values
    phi = np.where(np.isin(hour, [0, 8]), 0.15, np.where(hour == 16, -0.15, 0.0))
    e = rng.normal(0, sigma, n); r = np.zeros(n)
    for i in range(1, n):
        r[i] = phi[i] * r[i - 1] + e[i]
    return t.values, base * np.exp(np.cumsum(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    data, missing = {}, []
    if args.smoke:
        g = np.random.default_rng(1)
        for sym, base in [("USDJPY", 110.0), ("EURUSD", 1.1)]:
            t, c = synth_m15(g, base, 0.0004)
            data[sym] = prepare(t, c)
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            got = load_m15(sym)
            if got is None:
                missing.append(sym); continue
            data[sym] = prepare(*got)
        B = args.B
    if not data:
        print("[Q153] データがありません:", missing); sys.exit(1)

    # 観測
    tab = run_family(data)
    res_by_sym = {}
    for sym, D in data.items():
        both = both_period_hours(tab, sym)
        insample = {}
        trade_in, trade_both = {}, {}
        for per in PERIODS:
            g = tab[(tab.sym == sym) & (tab.period == per) & tab.sig_holm]
            hs = {int(h): int(np.sign(rh)) for h, rh in zip(g.hour, g.rho) if rh != 0}
            insample[per] = hs
            trade_in[per] = trade_pnl(D, hs, period_mask(D, per), PIP[sym])
            trade_both[per] = trade_pnl(D, both, period_mask(D, per), PIP[sym])
        res_by_sym[sym] = dict(
            n_sig_holm_by_period={per: int(len(insample[per])) for per in PERIODS},
            sig_hours_by_period={per: insample[per] for per in PERIODS},
            n_hours_both_periods_same_sign=len(both), hours_both_periods=both,
            trade_insample_set=trade_in, trade_both_set=trade_both,
        )

    # 帰無: 日内の並べ替え → 同じ 96 本の族で Holm
    null_nsig = []; null_maxabs_t = []; null_nboth = []
    for b in range(B):
        r_over = {sym: shuffle_within_day(D["r"], D["day_id"], rng) for sym, D in data.items()}
        nt = run_family(data, r_over)
        null_nsig.append(int(nt.sig_holm.sum()))
        null_maxabs_t.append(float(np.nanmax(np.abs(nt.t.values))))
        null_nboth.append(int(sum(len(both_period_hours(nt, s)) for s in data)))
    null_summary = dict(B=B, n_sig_holm_mean=float(np.mean(null_nsig)) if B else float("nan"),
                        share_draws_with_any_sig=float(np.mean(np.array(null_nsig) > 0)) if B else float("nan"),
                        share_draws_with_any_both_period=float(np.mean(np.array(null_nboth) > 0)) if B else float("nan"),
                        maxabs_t_p95=float(np.percentile(null_maxabs_t, 95)) if B else float("nan"),
                        maxabs_t_p975=float(np.percentile(null_maxabs_t, 97.5)) if B else float("nan"))
    obs_maxabs_t = float(np.nanmax(np.abs(tab.t.values)))
    null_summary["obs_maxabs_t"] = obs_maxabs_t
    null_summary["obs_maxabs_t_pct_in_null"] = float((np.array(null_maxabs_t) < obs_maxabs_t).mean()) if B else float("nan")

    verdict = judge(res_by_sym)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q153_hours_{stamp}.csv"); tab.to_csv(csv_path, index=False)
    png_path = make_plot(tab, os.path.join(OUT, f"{prefix}Q153_rho_by_hour_{stamp}.png"))
    out = dict(
        queue_id="Q153", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(SYMS=list(data.keys()), PIP=PIP, COST_ONEWAY_PIPS=COST_ONEWAY_PIPS, PERIODS=PERIODS, NW_LAGS=NW_LAGS,
                      ALPHA=ALPHA, MIN_PAIRS=MIN_PAIRS, NULL_B=B, SEED=SEED, data_dir=DATA_DIR),
        data_span={s: dict(start=str(D["t"][0]), end=str(D["t"][-1]), n=int(len(D["c"])), n_pairs=int(D["prev_ok"].sum()))
                   for s, D in data.items()},
        missing=missing,
        results=res_by_sym, null=null_summary, judgement=verdict,
        files=dict(hours_csv=csv_path, png=png_path),
        multiple_comparisons="2通貨 × 24時 × 2期間 = 96 本を 1 つの族として Holm（α=0.05）。売買の集合は (i) 標本内・(ii) 両期間共通の 2 通り（判定は (ii)）",
        deviations_from_prereg=["15分足は値動きのない足（high==low）を除かない（直前の足を実際の直前の15分にするため）",
                                "Newey–West のラグは 4（=1時間）に固定（登録に数値なし）"],
    )
    jpath = os.path.join(OUT, f"{prefix}Q153_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else (int(o) if isinstance(o, np.integer) else str(o)))

    print(f"[Q153] syms={list(data)}  B={B}  smoke={args.smoke}  missing={missing}")
    for sym, r in res_by_sym.items():
        print(f"  {sym}: Holm後の有意時刻 {r['n_sig_holm_by_period']}  両期間同符号={r['hours_both_periods']}")
        for per in PERIODS:
            ti = r["trade_insample_set"][per]; tb = r["trade_both_set"][per]
            print(f"    {per}: 標本内集合 n_h={ti['n_hours']} net={ti['net_total_bp']:+.0f}bp ({ti['net_bp_per_bar']:+.2f}/本) | "
                  f"両期間集合 n_h={tb['n_hours']} net={tb['net_total_bp']:+.0f}bp ({tb['net_bp_per_bar']:+.2f}/本, {tb['net_bp_per_year']:+.0f}/年)")
    print(f"  帰無: 有意数の平均={null_summary['n_sig_holm_mean']:.2f} 1本以上の割合={null_summary['share_draws_with_any_sig']:.3f} "
          f"max|t| 97.5%={null_summary['maxabs_t_p975']:.2f} (観測 max|t|={obs_maxabs_t:.2f})")
    print("  判定(機械):", verdict["verdict"])
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
