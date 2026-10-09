#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q140: 順張りの損益分岐コストは実測スプレッドの何倍か（XAUUSD の Ask データで容量・コスト曲線）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q140（Fable 2026-10-09）＝ アイデア候補.md の行。
- 論文ノート: Feng・Cardozo・Xia2026_定量株式運用50年のサーベイ_アルファ減衰と実装の壁（転用案3: コストを基本・2倍・3倍に
  して純成績が正のままか。p20 の 4 シナリオ）。
- 知見（Q081）: XAUUSD の時間帯別スプレッドを LLM に推定させると順位は合うが水準を約 1.4 倍に見積もる。
- Korzan2026_二周期の株式ローテーション戦略_凍結した規則の評価 表5。

【仮説（測る前に固定）】
H: XAUUSD の順張り（TSMOM20・ドンチャン簡略版）は、実測スプレッドの 2 倍のコストでも純益が残る（損益分岐倍率 m* ≥ 2）。
対立: 実測コストで消える（m* < 1）。

【データ】
- XAUUSD: `data_XAUUSD_H1_dukascopy.csv`（bid、列 time,open,high,low,close,volume、UTC、足の開始時刻）と
  `data_XAUUSD_H1_dukascopy_ask.csv`（ask、同じ列構成）。同じ time で結合し、スプレッド = ask.close − bid.close。
  UTC 日足は bid の H1 から作る（open=最初の open、high=max、low=min、close=最後の close。足が MIN_BARS_DAY=6 本未満の日と
  high==low の日は除く）。
- 比較用: 15銘柄 `data_<SYM>_D1_fromH1.csv`（片道コスト＝段階1の保守値 COST_RT/2）。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 規則 (1) TSMOM20: s_t = sign(c_t − c_{t−20})、翌日のポジション。
  規則 (2) ドンチャン簡略版 55/20: 終値が直前 55 日高値を上抜けで買い、直前 20 日安値を下抜けで手仕舞い（売りは対称）、損切りなし。
- 日次: 粗損益 g_t = pos_{t−1} × (c_t/c_{t−1} − 1) × 1e4 [bp]、回転コスト k_t = |Δpos| × 片道コスト [bp]。
  純損益(m) = mean(g_t) − m × mean(k_t)。m ∈ {0, 0.5, 1, 1.5, 2, 3, 5}。
- 損益分岐 m* = mean(g) / mean(k)（純損益が m について線形なので線形補間＝厳密解。mean(k)=0 なら nan）。
- XAUUSD の片道コスト = 実測スプレッドの中央値。「約定時刻の時間帯」= 日足の最後の H1 足の開始時刻（UTC 時）の最頻値 h*。
  片道コスト = 時 h* のスプレッドの中央値（全期間）。価格単位 → bp は 各日の c_{t−1} で換算。
  （事前登録どおりスプレッド全幅を片道とみなす＝保守的。半スプレッドではない点を明記。）
- 「m* × 実測」を bp に直す = m* × mean(片道コスト bp)。
- 時間帯別スプレッドの中央値（0〜23 時）の表も出す（Q081 との照合用）。

【測るもの】
XAUUSD（実測コスト）と 15銘柄（段階1コスト）× 規則 2 で、m ごとの純損益の曲線、m*、帰無の m* の分布に対する
パーセンタイルと z。前半（<2017）/ 後半（≥2017）は記述。

【帰無】
粗利が 0 の帰無: 日次対数リターンを暦年の中で並べ替えた価格列で同じ規則を走らせ、m* を出す。B=300。
（m* は mean(g)/mean(k)。帰無では mean(g) がドリフト×露出の分だけ残るので 0 のまわりに散る。）

【判定（事前固定・変更禁止）】
XAUUSD・実測コスト・全期間・規則ごとに:
- m* ≥ 2 かつ m* が帰無の上位 5% より外（帰無のパーセンタイル ≥ 0.95）→「実用の余地あり」。
- m* < 1 →「実測コストで消える」。
- それ以外 → 未確定。
15銘柄の m* の表は記述（判定に使わない）。多重比較: 規則 2（判定）。

【捨てた案の数】
約5: 片道コストを半スプレッドにする案（登録は全幅。半幅は m を 0.5 で読めば同じ）、時間帯ごとのコストを日ごとに変える案
（日足の約定は 1 時間帯に集中するので 1 つの中央値に）、約定を翌日の寄り（日足の最初の H1）にする案（既存の型は終値→翌日）、
ATR 損切り付きドンチャンにする案（Q136 と同じ簡略版で統一）、スリッページを別に加える案（段階1はスプレッドだけ）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。金の 2024〜25 年の上昇を知っている可能性があるが、
規則・コストは固定で相場観は使わない。帰無はドリフトを保つ並べ替えなので上昇相場の分は帰無側にも入る。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude Fable 5.1（この下請け）。実行と結果の解釈は Sonnet／Opus が後で行う。
実行者は、結論ではなく、結果 JSON のパス・主要な数値（XAUUSD の m*・帰無のパーセンタイル・時間帯別スプレッド）・原典
（Feng p20・Q081）を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_breakeven_cost_vs_spread_q140.py            （B=300、数分）
      python3 kensho_breakeven_cost_vs_spread_q140.py --B 30     （軽い試走）
      python3 kensho_breakeven_cost_vs_spread_q140.py --smoke    （合成データで経路の確認。結果は results/smoke_*）
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

LOOKBACK = 20
DON_ENTRY, DON_EXIT = 55, 20
MULTS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
MIN_BARS_DAY = 6
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009
M_HI, M_LO, PCT_TH = 2.0, 1.0, 0.95
WARM = DON_ENTRY + 1


# ----------------------------------------------------------------------------- 基本の道具
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


def load_h1(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d["time"] = pd.to_datetime(d["time"]).dt.tz_localize(None)
    d = d[d.close > 0].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def h1_to_daily(h1):
    """UTC 日足（bid）。最後の足の開始時刻の時も持つ。"""
    h1 = h1.copy(); h1["date"] = h1.time.dt.normalize(); h1["hour"] = h1.time.dt.hour
    g = h1.groupby("date")
    d = pd.DataFrame(dict(open=g.open.first(), high=g.high.max(), low=g.low.min(), close=g.close.last(),
                          n_bars=g.size(), last_hour=g.hour.last())).reset_index().rename(columns={"date": "time"})
    d = d[(d.n_bars >= MIN_BARS_DAY) & (d.high > d.low) & (d.close > 0)].reset_index(drop=True)
    return d


# ----------------------------------------------------------------------------- ルール
def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def donchian_positions(c):
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


RULES = {"TSMOM20": tsmom_positions, "Donchian55_20": donchian_positions}


def gross_and_turnover_bp(c, signal, cost_oneway):
    """signal_t を翌日に持つ。粗損益 g_t [bp] と 回転コスト k_t [bp]（片道コスト 1 倍）。先頭 WARM+1 日は 0。
    cost_oneway: スカラー（価格単位）。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    g = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = cost_oneway / c[:-1] * 1e4
    k = dpos * cost_bp
    g[:WARM + 1] = 0.0; k[:WARM + 1] = 0.0
    return g, k


def curve(g, k, idx):
    """m ごとの純損益と m*。idx = 使う日の添字。"""
    mg = float(g[idx].mean()) if len(idx) else float("nan")
    mk = float(k[idx].mean()) if len(idx) else float("nan")
    m_star = mg / mk if (np.isfinite(mk) and mk > 0) else float("nan")
    return dict(gross_bp=mg, turnover_cost_bp=mk, net_by_m={str(m): mg - m * mk for m in MULTS}, m_star=m_star, n_days=int(len(idx)))


def shuffled_prices_by_year(c, years, rng):
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    r2 = r.copy()
    for y in np.unique(years):
        idx = np.flatnonzero(years == y); idx = idx[idx >= 1]
        if len(idx) > 1:
            r2[idx] = r[rng.permutation(idx)]
    return np.exp(np.log(c[0]) + np.cumsum(r2))


# ----------------------------------------------------------------------------- 1系列の評価（観測＋帰無）
def evaluate_series(name, t, c, cost_oneway, B, rng, with_null=True):
    years = pd.DatetimeIndex(t).year.values
    valid = np.arange(len(c)) > WARM
    periods = {"全期間": valid, "前半": valid & (years < SPLIT_YEAR), "後半": valid & (years >= SPLIT_YEAR)}
    out = {}
    for rname, fn in RULES.items():
        g, k = gross_and_turnover_bp(c, fn(c), cost_oneway)
        rec = {per: curve(g, k, np.flatnonzero(m)) for per, m in periods.items()}
        rec["cost_oneway_bp_mean"] = float(np.mean(cost_oneway / c[valid] * 1e4))
        rec["m_star_times_cost_bp"] = rec["全期間"]["m_star"] * rec["cost_oneway_bp_mean"] if np.isfinite(rec["全期間"]["m_star"]) else float("nan")
        out[rname] = rec
    if with_null and B > 0:
        nulls = {rname: {per: [] for per in periods} for rname in RULES}
        for b in range(B):
            c2 = shuffled_prices_by_year(c, years, rng)
            for rname, fn in RULES.items():
                g, k = gross_and_turnover_bp(c2, fn(c2), cost_oneway)
                for per, m in periods.items():
                    nulls[rname][per].append(curve(g, k, np.flatnonzero(m))["m_star"])
        for rname in RULES:
            for per in periods:
                nv = np.asarray(nulls[rname][per], float)
                z, pct = z_against_null(out[rname][per]["m_star"], nv)
                out[rname][per].update(null_m_star_mean=float(np.nanmean(nv)) if len(nv) else float("nan"),
                                       null_m_star_p95=float(np.nanpercentile(nv, 95)) if len(nv) else float("nan"),
                                       null_z=z, null_pct=pct)
    return out


def judge(xau):
    out = {}
    for rname in RULES:
        r = xau[rname]["全期間"]
        m = r["m_star"]; pct = r.get("null_pct", float("nan"))
        if not np.isfinite(m):
            v = "判定不能（回転なし）"
        elif m >= M_HI and np.isfinite(pct) and pct >= PCT_TH:
            v = "実用の余地あり"
        elif m < M_LO:
            v = "実測コストで消える"
        else:
            v = "未確定"
        out[rname] = dict(m_star=m, null_pct=pct, verdict=v)
    return dict(by_rule=out, thresholds=dict(m_hi=M_HI, m_lo=M_LO, null_pct=PCT_TH),
                note="事前固定の規則で機械的に付けた判定（XAUUSD・実測コスト・全期間・規則ごと）。15銘柄の表は記述。解釈は実行者が記録する。")


def make_plot(xau, table15, path):
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
        for rname in RULES:
            r = xau[rname]["全期間"]
            ax[0].plot(MULTS, [r["net_by_m"][str(m)] for m in MULTS], "o-", label=f"{rname} (m*={r['m_star']:.2f})")
        ax[0].axhline(0, c="k", lw=.6); ax[0].set_xlabel("コスト倍率 m（× 実測スプレッド）"); ax[0].set_ylabel("純損益 bp/日")
        ax[0].set_title("XAUUSD 実測コストの曲線"); ax[0].legend()
        syms = list(table15.keys()); x = np.arange(len(syms))
        for k, rname in enumerate(RULES):
            ax[1].bar(x + (k - .5) * .4, [table15[s][rname]["全期間"]["m_star"] for s in syms], width=.4, label=rname)
        ax[1].axhline(1, c="gray", ls=":", lw=.7); ax[1].axhline(2, c="gray", ls="--", lw=.7); ax[1].axhline(0, c="k", lw=.6)
        ax[1].set_xticks(x); ax[1].set_xticklabels(syms, rotation=60); ax[1].set_title("15銘柄の m*（段階1コスト）"); ax[1].legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 合成データ
def synth_daily(sym, k, g, n_days=None):
    dates = pd.bdate_range("2008-02-01", "2026-07-14")
    phi = -0.1 + 0.3 * (k / 14)
    e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
    for i in range(1, len(dates)):
        r[i] = phi * r[i - 1] + e[i]
    base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
            "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
    return dates.values, base * np.exp(np.cumsum(r))


def synth_h1_bid_ask(g):
    """合成 H1: 2020-01〜2022-12 の平日 24 本。スプレッドは時間帯で変える（アジア広め）。"""
    days = pd.bdate_range("2020-01-01", "2022-12-31")
    times = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in days for h in range(24)])
    n = len(times)
    r = 0.15 * np.concatenate([[0], g.normal(0, 0.0015, n - 1)]) + np.concatenate([[0], 0.85 * g.normal(0, 0.0015, n - 1)])
    c = 1800 * np.exp(np.cumsum(r))
    hour = times.hour.values
    spread = np.where((hour >= 0) & (hour < 7), 0.45, 0.25) + g.exponential(0.05, n)
    bid = pd.DataFrame(dict(time=times, open=c, high=c * 1.001, low=c * 0.999, close=c, volume=1.0))
    ask = bid.copy(); ask["close"] = bid.close + spread; ask["open"] = bid.open + spread
    ask["high"] = bid.high + spread; ask["low"] = bid.low + spread
    return bid, ask


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    warnings.simplefilter("ignore", RuntimeWarning)   # 空の期間の nan 警告を抑える
    rng = np.random.default_rng(SEED)
    missing = {}

    # --- XAUUSD H1 bid/ask
    if args.smoke:
        bid, ask = synth_h1_bid_ask(np.random.default_rng(2))
        B = min(args.B, 10)
    else:
        fb = os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy.csv"); fa = os.path.join(DATA_DIR, "data_XAUUSD_H1_dukascopy_ask.csv")
        bid = load_h1(fb) if os.path.exists(fb) else None
        ask = load_h1(fa) if os.path.exists(fa) else None
        if bid is None or ask is None:
            missing["XAUUSD_H1"] = dict(bid=bid is not None, ask=ask is not None)
        B = args.B
    xau, spread_info = None, {}
    if bid is not None and ask is not None:
        j = pd.merge(bid[["time", "close"]], ask[["time", "close"]], on="time", suffixes=("_bid", "_ask"))
        j["spread"] = j.close_ask - j.close_bid
        j = j[np.isfinite(j.spread) & (j.spread >= 0)]
        j["hour"] = j.time.dt.hour
        hour_med = j.groupby("hour")["spread"].median()
        daily = h1_to_daily(bid)
        h_star = int(daily.last_hour.mode().iloc[0])
        cost_oneway = float(hour_med.get(h_star, j.spread.median()))
        spread_info = dict(n_h1_joined=int(len(j)), start=str(j.time.iloc[0]), end=str(j.time.iloc[-1]),
                           hour_median={int(h): float(v) for h, v in hour_med.items()},
                           overall_median=float(j.spread.median()), overall_mean=float(j.spread.mean()),
                           execution_hour=h_star, execution_hour_share=float((daily.last_hour == h_star).mean()),
                           cost_oneway_price=cost_oneway, cost_oneway_bp_at_median_price=float(cost_oneway / daily.close.median() * 1e4),
                           note="片道コスト＝約定時間帯 h* のスプレッド中央値（全幅・保守的）。半幅なら m を 0.5 倍で読む。")
        t = daily.time.values; c = daily.close.values.astype(float)
        xau = evaluate_series("XAUUSD_measured", t, c, cost_oneway, B, rng, with_null=True)
        xau["data_span"] = dict(start=str(pd.Timestamp(t[0]).date()), end=str(pd.Timestamp(t[-1]).date()), n=int(len(c)))
        # 参考: 段階1コスト（0.3）でも同じ日足で
        xau_stage1 = evaluate_series("XAUUSD_stage1", t, c, COST_RT["XAUUSD"] / 2.0, 0, rng, with_null=False)
        xau["stage1_reference"] = {r: xau_stage1[r]["全期間"] for r in RULES}

    # --- 15銘柄（段階1コスト）
    table15, spans = {}, {}
    for k, sym in enumerate(SYMS):
        if args.smoke:
            t, c = synth_daily(sym, k, np.random.default_rng(10 + k))
        else:
            f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
            if not os.path.exists(f):
                missing[sym] = "ファイルなし"; continue
            try:
                d = load_daily(sym)
            except Exception as e:
                missing[sym] = str(e); continue
            t, c = d.time.values, d.close.values.astype(float)
        table15[sym] = evaluate_series(sym, t, c, COST_RT[sym] / 2.0, B, rng, with_null=True)
        spans[sym] = dict(start=str(pd.Timestamp(t[0]).date()), end=str(pd.Timestamp(t[-1]).date()), n=int(len(c)))

    verdict = judge(xau) if xau is not None else dict(verdict="判定不能（XAUUSD の H1 bid/ask が無い）", note="")

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    rows = []
    for s in table15:
        for r in RULES:
            for per in ("全期間", "前半", "後半"):
                x = table15[s][r][per]
                rows.append(dict(sym=s, rule=r, period=per, gross_bp=x["gross_bp"], turnover_cost_bp=x["turnover_cost_bp"], m_star=x["m_star"],
                                 null_pct=x.get("null_pct"), null_p95=x.get("null_m_star_p95"), n_days=x["n_days"]))
    if xau is not None:
        for r in RULES:
            for per in ("全期間", "前半", "後半"):
                x = xau[r][per]
                rows.append(dict(sym="XAUUSD_measured", rule=r, period=per, gross_bp=x["gross_bp"], turnover_cost_bp=x["turnover_cost_bp"], m_star=x["m_star"],
                                 null_pct=x.get("null_pct"), null_p95=x.get("null_m_star_p95"), n_days=x["n_days"]))
    csv_path = os.path.join(OUT, f"{prefix}Q140_table_{stamp}.csv"); pd.DataFrame(rows).to_csv(csv_path, index=False)
    png_path = make_plot(xau, table15, os.path.join(OUT, f"{prefix}Q140_curve_{stamp}.png")) if (xau is not None and table15) else "(図なし)"
    out = dict(
        queue_id="Q140", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LOOKBACK=LOOKBACK, DON_ENTRY=DON_ENTRY, DON_EXIT=DON_EXIT, MULTS=MULTS, MIN_BARS_DAY=MIN_BARS_DAY,
                      SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED, COST_RT=COST_RT, syms=SYMS, data_dir=DATA_DIR,
                      null="暦年の中で日次対数リターンを並べ替えた価格列で m* を出す（粗利 0 の帰無）"),
        data_span=spans, missing=missing, n_symbols_used=len(table15),
        xauusd_spread=spread_info, xauusd_measured=xau, table15=table15, judgement=verdict,
        files=dict(table_csv=csv_path, curve_png=png_path),
        multiple_comparisons="判定は XAUUSD × 規則 2 ＝ 2。15銘柄 × 規則 2 × 期間 3 の m* は記述",
    )
    jpath = os.path.join(OUT, f"{prefix}Q140_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))

    print(f"[Q140] symbols15={len(table15)}  B={B}  smoke={args.smoke}  missing={missing}")
    if spread_info:
        print(f"  XAUUSD spread: overall median={spread_info['overall_median']:.3f}  exec hour={spread_info['execution_hour']} "
              f"(share {spread_info['execution_hour_share']:.2f})  cost_oneway={spread_info['cost_oneway_price']:.3f} "
              f"(≈{spread_info['cost_oneway_bp_at_median_price']:.2f} bp)")
        print("  hour medians:", {h: round(v, 3) for h, v in spread_info["hour_median"].items()})
    if xau is not None:
        for r in RULES:
            x = xau[r]["全期間"]
            print(f"  XAUUSD {r:14s} gross={x['gross_bp']:+.2f} cost@1={x['turnover_cost_bp']:.2f}  m*={x['m_star']:+.2f} "
                  f"(null p95={x['null_m_star_p95']:+.2f}, pct={x['null_pct']:.2f}, z={x['null_z']:+.2f})  m*×実測={xau[r]['m_star_times_cost_bp']:+.2f}bp  "
                  f"前半 m*={xau[r]['前半']['m_star']:+.2f} 後半 m*={xau[r]['後半']['m_star']:+.2f}")
    print("  15銘柄 m*(全期間):")
    for s in table15:
        print(f"    {s:7s} " + "  ".join(f"{r}={table15[s][r]['全期間']['m_star']:+.2f} (pct {table15[s][r]['全期間'].get('null_pct', float('nan')):.2f})" for r in RULES))
    print("  判定(機械):", {r: v["verdict"] for r, v in verdict.get("by_rule", {}).items()} or verdict.get("verdict"))
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
