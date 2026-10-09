#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q142: 高ボラ局面では順張りの的中率と純損益が下がるか
（Loubaris・Koraich 2026 の問いを 15銘柄 D1・GARCH なしの実現ボラで）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q142（Fable 2026-10-09）。
  検証/学問/金融工学/知識/文献/アイデア候補.md の同日の行。
- 論文ノート: Loubaris・Koraich2026_GARCHで分けたボラ局面ごとのトレンド指標の的中率
  （500日・1銘柄で非有意）、Takahashi・Mizuta・Yagi2026（順張り投資家とトレンド）、
  知見 Q042（為替の押し目の逆張りは荒れた相場に限っても 4時間足では戻らない）。
- 既存の知見: FX8 の順張り（TSMOM・ドンチャン）はコスト後に無条件で負け（Q019・Q054・FX改善ログ 2026-10-02）。
  → 本検証は「負けの大きさ（トレンド群では勝ちの大きさ）が局面で変わるか」を測る。

【仮説（測る前に固定）】
H: 高ボラ局面では、TSMOM20 の翌日の的中率と純損益（bp/日）が安定局面より低い。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 日次対数リターン r_t = ln(c_t / c_{t−1})。
- 実現ボラ v_t = r_{t−19..t} の標準偏差（20日・ddof=1）。
- 局面ラベル L_t = 「高」 if v_t > median(v_1..v_{t−1})（その銘柄の拡大窓の中央値・t を含まない）else 「安定」。
  拡大窓に MIN_HIST=60 個未満しか無い間はラベルなし（除外）。GARCH は使わない（論文との違い）。
- 翌日 t+1 の損益に対応する局面は L_t（t の引けで分かる情報だけ。先読みなし）。
- TSMOM20: s_t = sign(c_t − c_{t−20})。翌日 t+1 のポジション = s_t。
  日次純損益 [bp] = pos × (c_{t+1}/c_t − 1) × 1e4 − |Δpos| × 片道コスト（段階1の保守値 COST_RT/2 を価格で割って bp）。
- 的中 = pos × ret > 0 の日（pos=0 または ret=0 の日は除く）。的中率 = 的中日 / 判定可能日。
- 期間: 前半 = 2008〜2016、後半 = 2017〜2026（UTC 日付の年）。群: 全15・FX8・トレンド7。

【測るもの】
局面別（高／安定）の 的中率 と 純損益（bp/日）。差 = 高 − 安定。
- 銘柄ごと（記述）と、合算（群の全日をプール: 高の日の平均 − 安定の日の平均）。
- 合算の差の t: 半年を単位（各半年で群内の日をプールして差を出し、半年の系列の平均／SE）。
- 帰無: 各銘柄の局面ラベルを「月ブロック」ごとに並べ替える（月ごとのラベルの塊を順序だけ入れ替え、損益系列は固定）
  B=500 回、seed 固定。合算の差の帰無分布から z = (差_obs − mean) / sd。

【判定（事前固定・変更禁止）】
「局面で変わる」 = 全15合算の純損益の差（高 − 安定）が 前半・後半で同符号 かつ 両期間で |t|≥2 かつ 両期間で |z|≥2。
どちらかの期間で逆符号、または |t|<2（または |z|<2）→ 棄却（論文と同じ非有意）。
FX8 は無条件で負けなので、支持でも「負けの大きさが局面で変わる」としか言えない（実行者が記述）。
的中率の差は記述（判定に使わない）。多重比較: 指標2（的中率・純損益）× 群3 × 期間2 = 12（判定は純損益×全15×2期間のみ）。

【捨てた案の数】
約5: GARCH(1,1) の条件付き分散で局面を分ける案（論文に合わせるが scipy 無しで安定して推定しにくい→実現ボラ）、
ボラ3分位（高／中／低）の案（判定が2値でなくなる→2値）、固定閾値（年率 10%）の案（銘柄間で不公平→拡大窓の中央値）、
ドンチャン簡略版も入れる案（Q142 は1本固定→外す）、月クラスタの t を主にする案（半年単位と二択→半年を主、月は参考として出す）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。2008・2020・2022 の高ボラ期の相場を知っている可能性があり、
後知恵を完全には排除できない。ただし局面ラベルは拡大窓の中央値で機械的に付け、規則は1本固定。

【委託の確かめ方】
設計は Fable（specs20.py）、コードは Claude（Fable 5.1 下請け、2026-10-09）、実行と解釈は Sonnet／Opus が後で行う。
実行者は結果 JSON のパス・主要な数値（合算の差・t・z・前後半の符号）・原典の箇所を本体に返し、本体が照合してから記録する。

【実装】自己完結・決定的（乱数は seed 固定のラベル並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_vol_regime_trend_following_q142.py            （B=500）
      python3 kensho_vol_regime_trend_following_q142.py --B 50     （軽い試走）
      python3 kensho_vol_regime_trend_following_q142.py --smoke    （合成データで経路の確認。結果は捨てる）
事前登録からの変更点: なし（t の単位は「半年」を主に採用し、月クラスタの t は参考として併記）。
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
# 段階1の保守的な往復コスト（価格単位）。片道はこの半分。
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LOOKBACK = 20          # TSMOM の参照日数
VOL_WIN = 20           # 実現ボラの窓
MIN_HIST = 60          # 拡大窓の中央値に要る最小個数
SPLIT_YEAR = 2017
NULL_B = 500
SEED = 20261009
QID = "Q142"


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
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def tsmom_positions(c):
    n = len(c); s = np.zeros(n)
    s[LOOKBACK:] = np.sign(c[LOOKBACK:] - c[:-LOOKBACK])
    return s


def daily_net_pnl_bp(c, signal, cost_rt):
    """signal_t を翌日 t+1 に持つ。bp 単位の日次純損益（長さ n、先頭は 0）。"""
    n = len(c)
    pos_prev = np.concatenate([[0.0], signal[:-1]])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos_prev * ret * 1e4
    dpos = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    pnl = gross - dpos * cost_bp
    pnl[:LOOKBACK + 1] = 0.0
    return pnl, pos_prev, ret


def expanding_median_prev(v):
    """各 i について median(v[:i])（i を含まない）。MIN_HIST 未満は nan。O(n log n) の近似ではなく素直に O(n²) だが n≈4800 で軽い。"""
    n = len(v); out = np.full(n, np.nan)
    # 有限値だけで拡大窓中央値（pandas の expanding().median() を 1 つずらす）
    s = pd.Series(v)
    em = s.expanding(min_periods=MIN_HIST).median().shift(1).values
    out[:] = em
    return out


# ----------------------------------------------------------------------------- 1銘柄の表
def symbol_table(sym, t, c, cost_rt):
    """日ごとの表: date, year, month_id, half_id, pnl, hit(1/0/nan), regime(1=高,0=安定,nan)。"""
    n = len(c)
    r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
    vol = pd.Series(r).rolling(VOL_WIN).std(ddof=1).values.copy()
    vol[:VOL_WIN] = np.nan                      # r[0]=0 の分を含む窓は捨てる
    med = expanding_median_prev(vol)
    lab_t = np.where(np.isfinite(vol) & np.isfinite(med), (vol > med).astype(float), np.nan)
    regime = np.concatenate([[np.nan], lab_t[:-1]])   # 日 t+1 の損益には L_t
    pnl, pos, ret = daily_net_pnl_bp(c, tsmom_positions(c), cost_rt)
    hit = np.where((pos != 0) & (ret != 0), (pos * ret > 0).astype(float), np.nan)
    valid = np.arange(n) > LOOKBACK
    hit[~valid] = np.nan
    ts = pd.Series(t)
    ym = ts.dt.year.values * 100 + ts.dt.month.values
    hy = ts.dt.year.values * 10 + np.where(ts.dt.month.values <= 6, 1, 2)
    df = pd.DataFrame(dict(sym=sym, date=t, year=ts.dt.year.values, month_id=ym, half_id=hy,
                           pnl=pnl, hit=hit, regime=regime, valid=valid))
    df = df[df.valid & np.isfinite(df.regime)].reset_index(drop=True)
    return df


def permute_regime_by_month(df, rng):
    """月ブロックごとのラベルの塊を順序だけ並べ替え（損益は固定）。"""
    months = df.month_id.values
    uniq, start = np.unique(months, return_index=True)
    order = np.argsort(start)
    blocks = np.split(df.regime.values, start[order][1:])
    perm = rng.permutation(len(blocks))
    return np.concatenate([blocks[i] for i in perm])


# ----------------------------------------------------------------------------- 統計
def pooled_diff(pnl, hit, reg):
    hi = reg == 1; lo = reg == 0
    out = dict(n_high=int(hi.sum()), n_stable=int(lo.sum()))
    out["pnl_high"] = float(pnl[hi].mean()) if hi.any() else float("nan")
    out["pnl_stable"] = float(pnl[lo].mean()) if lo.any() else float("nan")
    out["pnl_diff"] = out["pnl_high"] - out["pnl_stable"]
    hh = hit[hi]; hl = hit[lo]
    out["hit_high"] = float(np.nanmean(hh)) if np.isfinite(hh).any() else float("nan")
    out["hit_stable"] = float(np.nanmean(hl)) if np.isfinite(hl).any() else float("nan")
    out["hit_diff"] = out["hit_high"] - out["hit_stable"]
    return out


def stats_for(tab, syms, period, reg_col="regime"):
    g = tab[tab.sym.isin(syms)]
    if period == "前半":
        g = g[g.year < SPLIT_YEAR]
    elif period == "後半":
        g = g[g.year >= SPLIT_YEAR]
    pnl = g.pnl.values; hit = g.hit.values; reg = g[reg_col].values
    out = pooled_diff(pnl, hit, reg)
    out["n_days"] = int(len(g))
    # 半年を単位の t（各半年でプールした差）
    for unit, col in (("half", "half_id"), ("month", "month_id")):
        diffs = []; hdiffs = []
        for _, gb in g.groupby(col):
            rb = gb[reg_col].values
            if (rb == 1).sum() >= 3 and (rb == 0).sum() >= 3:
                d = pooled_diff(gb.pnl.values, gb.hit.values, rb)
                diffs.append(d["pnl_diff"]); hdiffs.append(d["hit_diff"])
        m, tt, n = mean_t(diffs)
        out[f"pnl_diff_{unit}_mean"] = m; out[f"pnl_diff_{unit}_t"] = tt; out[f"pnl_diff_{unit}_n"] = n
        m, tt, n = mean_t(hdiffs)
        out[f"hit_diff_{unit}_mean"] = m; out[f"hit_diff_{unit}_t"] = tt
    return out


def judge(res):
    def fin(v):
        return v is not None and np.isfinite(v)
    per = {}
    for p in ("前半", "後半"):
        r = res[f"全15|{p}"]
        per[p] = dict(pnl_diff=r["pnl_diff"], t=r["pnl_diff_half_t"], z=r["pnl_diff_z"],
                      abs_t_ge2=bool(fin(r["pnl_diff_half_t"]) and abs(r["pnl_diff_half_t"]) >= 2.0),
                      abs_z_ge2=bool(fin(r["pnl_diff_z"]) and abs(r["pnl_diff_z"]) >= 2.0))
    same_sign = (fin(per["前半"]["pnl_diff"]) and fin(per["後半"]["pnl_diff"])
                 and np.sign(per["前半"]["pnl_diff"]) == np.sign(per["後半"]["pnl_diff"]) and per["前半"]["pnl_diff"] != 0)
    support = bool(same_sign and all(per[p]["abs_t_ge2"] and per[p]["abs_z_ge2"] for p in per))
    verdict = "局面で変わる（支持）" if support else "棄却（前後半で逆符号または |t|<2／|z|<2。論文と同じ非有意）"
    return dict(by_period=per, same_sign=bool(same_sign), verdict=verdict,
                rule="全15合算の純損益の差（高−安定）が前後半で同符号 かつ 両期間で |t|≥2（半年単位）かつ |z|≥2（月ブロック並べ替え B 回）",
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定、FX8 は『負けの大きさが局面で変わる』としか言えない点）は実行者が記録する。")


def make_plot(per_sym, path):
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
        fig, ax = plt.subplots(figsize=(10, 4.5))
        x = np.arange(len(per_sym)); w = 0.38
        ax.bar(x - w / 2, per_sym.pnl_high, w, label="高ボラ", color="tab:red", alpha=.7)
        ax.bar(x + w / 2, per_sym.pnl_stable, w, label="安定", color="tab:blue", alpha=.7)
        ax.set_xticks(x); ax.set_xticklabels(per_sym.sym, rotation=60); ax.axhline(0, lw=.6, c="k")
        ax.set_ylabel("TSMOM20 の純損益（bp/日）"); ax.set_title("局面別の純損益（全期間）"); ax.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


# ----------------------------------------------------------------------------- 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無のラベル並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
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
            n = len(dates); e = g.normal(0, 0.006, n)
            # ボラの局面を作る（GARCH 風の緩い変動）
            scale = np.exp(0.4 * np.sin(np.arange(n) / 120.0 + k))
            e = e * scale
            r = np.zeros(n)
            for i in range(1, n):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 10)
    else:
        for sym in SYMS:
            d = load_daily(sym)
            if d is None or len(d) < 300:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    syms_used = list(series.keys())
    fx_used = [s for s in FX8 if s in series]; tr_used = [s for s in TREND7 if s in series]

    tabs = {sym: symbol_table(sym, t, c, COST_RT[sym]) for sym, (t, c) in series.items()}
    tab = pd.concat(tabs.values(), ignore_index=True)

    groups = {"全15": syms_used, "FX8": fx_used, "トレンド7": tr_used}
    periods = ["前半", "後半", "全期間"]
    res = {f"{gname}|{per}": stats_for(tab, syms, per) for gname, syms in groups.items() for per in periods}

    # 帰無: 月ブロックのラベル並べ替え（銘柄ごと独立）。損益は固定。
    null_vals = {k: {"pnl_diff": [], "hit_diff": [], "pnl_diff_half_t": []} for k in res}
    for b in range(B):
        tab["regime_null"] = np.concatenate([permute_regime_by_month(tabs[s], rng) for s in syms_used])
        for gname, syms in groups.items():
            for per in periods:
                k = f"{gname}|{per}"
                s = stats_for(tab, syms, per, reg_col="regime_null")
                for key in null_vals[k]:
                    null_vals[k][key].append(s[key])
    for k in res:
        res[k]["pnl_diff_z"], res[k]["pnl_diff_pct"] = z_against_null(res[k]["pnl_diff"], null_vals[k]["pnl_diff"])
        res[k]["hit_diff_z"], res[k]["hit_diff_pct"] = z_against_null(res[k]["hit_diff"], null_vals[k]["hit_diff"])
        res[k]["null_pnl_diff_mean"] = float(np.nanmean(null_vals[k]["pnl_diff"])) if B else float("nan")
        res[k]["null_pnl_diff_sd"] = float(np.nanstd(null_vals[k]["pnl_diff"], ddof=1)) if B > 1 else float("nan")
        res[k]["null_t_sd"] = float(np.nanstd(null_vals[k]["pnl_diff_half_t"], ddof=1)) if B > 1 else float("nan")

    # 銘柄ごと（記述）
    rows = []
    for sym in syms_used:
        for per in periods:
            s = stats_for(tab, [sym], per)
            rows.append(dict(sym=sym, period=per, n_days=s["n_days"], n_high=s["n_high"], n_stable=s["n_stable"],
                             pnl_high=s["pnl_high"], pnl_stable=s["pnl_stable"], pnl_diff=s["pnl_diff"],
                             pnl_diff_half_t=s["pnl_diff_half_t"], hit_high=s["hit_high"], hit_stable=s["hit_stable"],
                             hit_diff=s["hit_diff"], hit_diff_half_t=s["hit_diff_half_t"]))
    per_sym = pd.DataFrame(rows)
    verdict = judge(res)
    elapsed = time.time() - t0

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}{QID}_per_symbol_{stamp}.csv"); per_sym.to_csv(csv_path, index=False)
    png_path = make_plot(per_sym[per_sym.period == "全期間"].reset_index(drop=True), os.path.join(OUT, f"{prefix}{QID}_bars_{stamp}.png"))
    out = dict(
        queue_id=QID, script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke), elapsed_sec=round(elapsed, 1),
        settings=dict(LOOKBACK=LOOKBACK, VOL_WIN=VOL_WIN, MIN_HIST=MIN_HIST, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B, SEED=SEED,
                      COST_RT=COST_RT, syms=syms_used, missing_syms=missing, n_missing=len(missing), data_dir=DATA_DIR,
                      regime_def="20日実現ボラ > その銘柄の拡大窓の中央値（t を含まない・GARCH 不使用）",
                      null_def="局面ラベルを月ブロックで並べ替え（損益固定）"),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        results=res, judgement=verdict,
        files=dict(per_symbol_csv=csv_path, bars_png=png_path),
        multiple_comparisons="指標2（的中率・純損益）× 群3 × 期間2 = 12（判定は純損益×全15×前後半のみ）",
    )
    jpath = os.path.join(OUT, f"{prefix}{QID}_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o))

    print(f"[{QID}] syms={len(syms_used)} missing={missing} B={B} smoke={args.smoke} elapsed={elapsed:.1f}s")
    for per in periods:
        for gname in groups:
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_days']:6d} high/stable={r['n_high']}/{r['n_stable']}  "
                  f"pnl 高={r['pnl_high']:+.2f} 安定={r['pnl_stable']:+.2f} 差={r['pnl_diff']:+.2f}bp "
                  f"t(半年)={r['pnl_diff_half_t']:+.2f} t(月)={r['pnl_diff_month_t']:+.2f} z={r['pnl_diff_z']:+.2f}  "
                  f"hit 高={r['hit_high']:.3f} 安定={r['hit_stable']:.3f} 差={r['hit_diff']:+.3f} z={r['hit_diff_z']:+.2f}")
    print("  判定(機械):", verdict["verdict"], "|", {p: (round(v['pnl_diff'], 2), round(v['t'], 2), round(v['z'], 2)) for p, v in verdict["by_period"].items()})
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
