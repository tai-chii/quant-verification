#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q269: EIA 原油在庫発表（水曜 10:30 ET）直後 1 時間の向きは次の 2〜4 時間に続くか（WTI・UKOIL H1）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q269 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Xu 2023（Energy Journal 44-5・EIA 発表の反応）、Adelaide の博士論文（在庫発表と原油）、知見 Q219（NFP 直後は続かない・Andersen 2003）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "EIA weekly petroleum status report announcement crude oil intraday price reaction continuation hours after release"）:
  見つかったもの: Xu 2023（IAEE Energy Journal 44-5）、Adelaide の博士論文、Journal of Energy Markets。
  未確認: 発表直後の向きが数時間続くかを H1・2 銘柄・前後半・符号付け替え帰無で判定する形は未確認（追試＋移植）。

【仮説（測る前に固定）】
H: 水曜 NY 10 時台（10:00→11:00・発表 10:30 を含む足）の WTI の向きは、続く 11〜14 時（3 時間）に反転も継続もしない（Q219 と同じ型）: E[sign(r_0)·r_{1..3}]=0。

【データ】
WTI・UKOIL H1_dukascopy（2011-09〜2026-06）。発表日は「水曜」規則（祝日週の木曜へのずれは知識から記載・実行者が EIA の原典と照合。`--eia_csv` で日付表を差し替え可）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
NY 時刻 America/New_York。r_0 = 10 時台、r_1..3 = 11〜13 時台の和。y = sign(r_0)·r_1..3 [bp]。対照: 他の曜日の同じ時刻。|r_0| の対照比（反応の大きさ）は記述。

【測るもの】
y の平均と年単位 t（2 銘柄・前後半 2012–2016／2017–）、対照との差。

【帰無】
sign(r_0) を日で無作為に付け替え B=2000 → z。

【判定（事前固定・変更禁止）】
2 銘柄とも全期間 |z|<2 → 支持（続かない）。両方 前後半とも同符号で z≥2（継続）または z≤−2（反転）→ 棄却（向きを書く）。それ以外 → 未確定。
多重比較: 判定は 2 銘柄の全期間（2 本）。前後半・対照は記述。

【捨てた案の数】
約3: 15 分足（原油には無い）、API（火曜夜）との組み合わせ、在庫のサプライズ値（手元に無い）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_eia_release_q269.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_eia_release_q269.py --smoke    （合成データで経路の確認。判定には使わない）
"""
import argparse
import datetime as _dt
import itertools
import json
import math
import os
import sys
import unicodedata
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
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
FX6 = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD"]  # ドル建て先進国（Q019・Q054 と同じ）
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
CRYPTO = ["BTCUSD", "ETHUSD", "XRPUSD", "LTCUSD", "ADAUSD", "BCHUSD", "XLMUSD", "EOSUSD", "LNKUSD", "DOTUSD", "SOLUSD"]
# 往復コスト（価格単位・段階1の保守値。Q136〜Q190 と同じ表）
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
CRYPTO_COST_RT_REL = 30e-4  # 暗号資産: 往復 30bp の仮置き（Q152 と同じ）
SPLIT_YEAR = 2017
SEED = 20261010
GROUPS = {"all15": SYMS, "fx8": FX8, "trend7": TREND7}


# ----------------------------------------------------------------------------- データ
def _read(path):
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return df


def load_d1(sym, smoke=False, rng=None):
    """UTC 日足（D1_fromH1）。値動きのない足（high==low）は除く。列: time, open, high, low, close, ret, year"""
    if smoke:
        df = _smoke_ohlc(sym, rng, n=2600, freq="D", start="2015-01-01")
    else:
        df = _read(os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv"))
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    df["year"] = df["time"].dt.year
    return df


def load_csv(name, smoke=False, rng=None, freq="h", n=20000, start="2015-01-01"):
    """任意の data_<name>.csv（H1/H4/M15/yahoo/ask）。"""
    if smoke:
        return _smoke_ohlc(name, rng, n=n, freq=freq, start=start)
    return _read(os.path.join(DATA_DIR, f"data_{name}.csv"))


def load_h1(sym, smoke=False, rng=None, n=60000, start="2015-01-01"):
    """UTC 1時間足（H1_dukascopy）。値動きのない足は除く。列: time, open, high, low, close, volume, ret, year, hour, dow"""
    df = load_csv(f"{sym}_H1_dukascopy", smoke, rng, freq="h", n=n, start=start)
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["ret"] = df["close"].pct_change()
    df["year"] = df["time"].dt.year
    df["hour"] = df["time"].dt.hour
    df["dow"] = df["time"].dt.dayofweek
    return df


def h1_to_d1(h1, cutoff_hour=0):
    """H1 を「cutoff_hour（UTC）始まり」の日足に束ねる。日付ラベルは区間の開始日。"""
    t = h1["time"] - pd.Timedelta(hours=cutoff_hour)
    key = t.dt.floor("D")
    g = h1.groupby(key)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                      "volume": g["volume"].sum() if "volume" in h1 else g["close"].size(), "nbars": g["close"].size()})
    d.index.name = "time"; d = d.reset_index()
    d = d[(d["high"] != d["low"]) & (d["nbars"] >= 6)].reset_index(drop=True)
    d["ret"] = d["close"].pct_change(); d["year"] = d["time"].dt.year
    return d


def _smoke_ohlc(sym, rng, n, freq, start):
    """合成データ（GBM）。判定には使わない。"""
    rng = rng or np.random.default_rng(SEED)
    t = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(0.0001, 0.006, n)
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    v = np.abs(rng.lognormal(8, 0.5, n))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v})


def exists_sym(sym, kind="D1_fromH1"):
    return os.path.exists(os.path.join(DATA_DIR, f"data_{sym}_{kind}.csv"))


def cost_bp_oneway(sym, close, rel=None):
    """片道コスト [bp]（価格に対する比）。rel を渡せば相対コスト（往復）を使う。"""
    if rel is not None:
        return np.full(len(close), rel / 2 * 1e4)
    return COST_RT[sym] / 2 / np.asarray(close, float) * 1e4


# ----------------------------------------------------------------------------- 合図と損益
def tsmom_pos(close, L):
    c = np.asarray(close, float)
    s = np.zeros(len(c))
    s[L:] = np.sign(c[L:] - c[:-L])
    return s


def sma_pos(close, n):
    c = pd.Series(np.asarray(close, float))
    m = c.rolling(n).mean().values
    s = np.sign(c.values - m)
    s[np.isnan(m)] = 0.0
    return s


def atr(high, low, close, n=20):
    h = np.asarray(high, float); l = np.asarray(low, float); c = np.asarray(close, float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    return pd.Series(tr).rolling(n).mean().values


def rsi(close, n):
    c = pd.Series(np.asarray(close, float))
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).values


def pnl_bp(pos, close, cost_oneway_bp):
    """pos[t] は t の終値で決めて t+1 のリターンに効く。pnl[t+1] = pos[t]*ret[t+1]*1e4 − |pos[t]−pos[t−1]|*片道[bp]。先頭は 0。"""
    c = np.asarray(close, float); pos = np.asarray(pos, float)
    ret = np.zeros(len(c)); ret[1:] = c[1:] / c[:-1] - 1
    held = np.r_[0.0, pos[:-1]]
    prev = np.r_[0.0, held[:-1]]
    cost = np.abs(held - prev) * np.r_[0.0, cost_oneway_bp[:-1]]
    return held * ret * 1e4 - cost


# ----------------------------------------------------------------------------- 統計
def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def nw_t(x, lag=5):
    """Newey-West（Bartlett）の t。"""
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")
    e = x - x.mean()
    s = (e ** 2).sum()
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * (e[k:] * e[:-k]).sum()
    se = math.sqrt(max(s, 1e-300)) / n
    return float(x.mean() / se) if se > 0 else float("nan")


def spearman(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    if len(x) < 3:
        return float("nan")
    rx = np.array(pd.Series(x).rank().values, float); ry = np.array(pd.Series(y).rank().values, float)
    rx -= rx.mean(); ry -= ry.mean()
    d = math.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def max_drawdown(pnl):
    cum = np.cumsum(np.asarray(pnl, float)); peak = np.maximum.accumulate(cum)
    return float((cum - peak).min()) if len(cum) else float("nan")


def sharpe_ann(pnl, per_year=252):
    x = np.asarray(pnl, float); x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(per_year)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def qlike(s2_pred, r2):
    """QLIKE 損失（小さいほど良い）。r2: 実現分散、s2_pred: 予測分散。"""
    s2 = np.asarray(s2_pred, float); r2 = np.asarray(r2, float)
    m = np.isfinite(s2) & np.isfinite(r2) & (s2 > 0) & (r2 > 0)
    return float(np.mean(r2[m] / s2[m] - np.log(r2[m] / s2[m]) - 1)) if m.sum() > 2 else float("nan")


def z_of(obs, null):
    null = np.asarray(null, float); null = null[np.isfinite(null)]
    if len(null) < 3 or null.std(ddof=1) == 0 or not np.isfinite(obs):
        return float("nan"), float("nan")
    return float((obs - null.mean()) / null.std(ddof=1)), float((null < obs).mean())


def perm_within(rng, x, groups):
    """groups（例: 年）の中で x を並べ替える。"""
    x = np.asarray(x, float).copy(); g = np.asarray(groups)
    for v in np.unique(g):
        idx = np.where(g == v)[0]
        x[idx] = x[rng.permutation(idx)]
    return x


def block_perm(rng, x, block):
    """block 本ごとの塊を並べ替える（塊の中の順序は保つ）。"""
    x = np.asarray(x, float); n = len(x); nb = int(math.ceil(n / block))
    order = rng.permutation(nb)
    out = np.concatenate([x[b * block:(b + 1) * block] for b in order])
    return out[:n]


def circ_shift(rng, x, min_shift=1):
    """循環シフト（合図とリターンの対応を壊し、合図の自己相関は保つ）。"""
    x = np.asarray(x, float); n = len(x)
    k = int(rng.integers(min_shift, max(min_shift + 1, n - min_shift)))
    return np.roll(x, k)


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p); order = np.argsort(p); adj = np.empty(m)
    run = 0.0
    for i, k in enumerate(order):
        run = max(run, (m - i) * p[k]); adj[k] = min(1.0, run)
    return adj


def by_year_stats(df, col, year_col="year", y0=0, y1=9999):
    """年を単位にした平均と t（銘柄は年の中で平均してから）。df: year, sym, col。"""
    d = df[(df[year_col] >= y0) & (df[year_col] < y1)]
    if d.empty:
        return {"n_years": 0, "mean": float("nan"), "t": float("nan")}
    if "sym" in d.columns:
        yr = d.groupby([year_col, "sym"])[col].mean().groupby(level=0).mean()
    else:
        yr = d.groupby(year_col)[col].mean()
    yr = yr.dropna()
    return {"n_years": int(len(yr)), "mean": float(yr.mean()) if len(yr) else float("nan"), "t": tstat(yr.values)}


# ----------------------------------------------------------------------------- 入出力
def parse_args(default_B=300, extra=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=default_B, help="帰無の回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路の確認（判定に使わない）")
    ap.add_argument("--seed", type=int, default=SEED)
    if extra:
        extra(ap)
    return ap.parse_args()


def write_result(qid, res, smoke, extra_csv=None):
    os.makedirs(OUT, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = f"smoke_{qid}" if smoke else qid
    path = os.path.join(OUT, f"{pre}_result_{ts}.json")
    res = {"qid": qid, "smoke": smoke, "generated": ts, **res}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=_json_default)
    print("wrote", os.path.relpath(path, HERE))
    if extra_csv is not None:
        for name, df in extra_csv.items():
            cp = os.path.join(OUT, f"{pre}_{name}_{ts}.csv"); df.to_csv(cp, index=False); print("wrote", os.path.relpath(cp, HERE))
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, _dt.datetime, _dt.date)):
        return str(o)
    return str(o)


def f(x, nd=4):
    try:
        return None if x is None or not np.isfinite(x) else round(float(x), nd)
    except Exception:
        return None


def syms_available(syms, kind="D1_fromH1", smoke=False):
    if smoke:
        return list(syms), []
    ok = [s for s in syms if exists_sym(s, kind)]
    return ok, [s for s in syms if s not in ok]
# ============================================================================= 共通の土台ここまで
# ============================================================================= 共通の土台ここまで

QID = "Q269"
DEFAULT_B = 2000
START = "2012-01-01"
SYMS2 = ["WTI", "UKOIL"]
TZ = "America/New_York"
H0, H_FOLLOW = 10, [11, 12, 13]  # NY 時刻: 発表 10:30 を含む 10 時台、続く 11〜13 時台
# EIA 週間石油在庫統計の既定の発表日: 毎週水曜 10:30 ET。
# 祝日（月曜が祝日の週など）は木曜 11:00 ET にずれることがある → 知識から記載・実行者が EIA の原典（Release Schedule）と照合。
# `--eia_csv`（列 `date`・YYYY-MM-DD・NY 日付）を渡すと水曜規則を置き換える。


def _extra(ap):
    ap.add_argument("--eia_csv", type=str, default=None, help="発表日の表（列 date・YYYY-MM-DD・NY 日付）。水曜規則を置き換える")


def daily_cells(sym, args, rng):
    """NY 日付ごとに r0（10 時台）と r123（11〜13 時台の和）[bp] を作る。"""
    df = load_h1(sym, args.smoke, rng, n=130000, start="2011-09-01")
    df = df[df["time"] >= pd.Timestamp(START)].reset_index(drop=True)
    t = pd.DatetimeIndex(df["time"]).tz_localize("UTC").tz_convert(TZ)
    d = pd.DataFrame({"ret_bp": df["ret"].values * 1e4, "nydate": t.tz_localize(None).normalize(), "nyhour": t.hour})
    d = d.dropna(subset=["ret_bp"])
    r0 = d[d["nyhour"] == H0].groupby("nydate")["ret_bp"].sum()
    fol = d[d["nyhour"].isin(H_FOLLOW)].groupby("nydate")["ret_bp"].agg(["sum", "size"])
    fol = fol[fol["size"] == len(H_FOLLOW)]["sum"]
    cells = pd.DataFrame({"r0": r0}).join(fol.rename("r123"), how="inner").reset_index()
    cells = cells[cells["r0"] != 0].reset_index(drop=True)
    cells["year"] = cells["nydate"].dt.year
    cells["dow"] = cells["nydate"].dt.dayofweek
    cells["y"] = np.sign(cells["r0"]) * cells["r123"]
    cells["sym"] = sym
    return cells


def eia_mask(cells, args):
    if args.eia_csv:
        tab = pd.read_csv(args.eia_csv)
        dates = pd.to_datetime(tab["date"]).dt.normalize()
        return cells["nydate"].isin(set(dates)).values, "eia_csv"
    return (cells["dow"] == 2).values, "every_wednesday"


def year_mean_matrix(years):
    """年ごとの平均を取る行列 M（n_years × n）。M @ x = 年平均ベクトル。"""
    yu = np.unique(years)
    M = (years[None, :] == yu[:, None]).astype(float)
    return M / M.sum(1, keepdims=True)


def run(args, rng):
    syms, missing = syms_available(SYMS2, "H1_dukascopy", args.smoke)
    summary = {}; rows = []
    for sym in syms:
        cells = daily_cells(sym, args, rng)
        m, rule = eia_mask(cells, args)
        ev = cells[m].copy(); ct = cells[~m].copy()
        rows.append(ev)
        summary[sym] = {"n_event_days": int(len(ev)), "n_control_days": int(len(ct)), "event_rule": rule}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            e = ev[(ev["year"] >= y0) & (ev["year"] < y1)]; c = ct[(ct["year"] >= y0) & (ct["year"] < y1)]
            st = by_year_stats(e, "y", y0=y0, y1=y1); stc = by_year_stats(c, "y", y0=y0, y1=y1)
            z = pct = float("nan")
            if len(e) >= 5:
                M = year_mean_matrix(e["year"].values)
                r123 = e["r123"].values
                S = rng.choice([-1.0, 1.0], size=(args.B, len(e)))
                null = ((S * r123[None, :]) @ M.T).mean(1)
                z, pct = z_of(st["mean"], null)
            summary[sym][pn] = {"n_event": int(len(e)), "n_years": st["n_years"], "y_mean_bp": f(st["mean"]), "y_t": f(st["t"]),
                                "y_z": f(z), "y_pct": f(pct),
                                "ctrl_y_mean_bp": f(stc["mean"]), "ctrl_y_t": f(stc["t"]),
                                "diff_vs_ctrl_bp": f(st["mean"] - stc["mean"]) if np.isfinite(st["mean"]) and np.isfinite(stc["mean"]) else None,
                                "abs_r0_event_bp": f(e["r0"].abs().mean()) if len(e) else None,
                                "abs_r0_ctrl_bp": f(c["r0"].abs().mean()) if len(c) else None,
                                "abs_r0_ratio": f(e["r0"].abs().mean() / c["r0"].abs().mean()) if len(e) and len(c) and c["r0"].abs().mean() > 0 else None}
    # 判定
    g = lambda s, p, k: summary.get(s, {}).get(p, {}).get(k)
    if len(syms) < 2:
        verdict = "未確定: 銘柄が揃わない（missing=%s）" % missing
    elif any(g(s, "all", "y_z") is None for s in syms):
        verdict = "未確定: 計算できない（z が nan）"
    elif all(abs(g(s, "all", "y_z")) < 2 for s in syms):
        verdict = "支持: 2 銘柄とも全期間 |z|<2（発表直後の向きは続かない）"
    else:
        direction = {}
        for s in syms:
            zp, zq = g(s, "pre", "y_z"), g(s, "post", "y_z")
            if zp is not None and zq is not None and zp >= 2 and zq >= 2:
                direction[s] = "継続"
            elif zp is not None and zq is not None and zp <= -2 and zq <= -2:
                direction[s] = "反転"
        if len(direction) == len(syms):
            verdict = "棄却: 2 銘柄とも前後半とも |z|≥2（" + "・".join(f"{s}={d}" for s, d in direction.items()) + "）"
        else:
            verdict = "未確定: 全期間 |z|≥2 の銘柄があるが前後半で揃わない"
    res = {"question": "EIA 原油在庫発表（水曜 10:30 ET）直後 1 時間の向きは次の 3 時間（11〜13 時台）に続くか",
           "settings": {"syms": SYMS2, "start": START, "tz": TZ, "hour0_ny": H0, "follow_hours_ny": H_FOLLOW, "split_year": SPLIT_YEAR,
                        "event_rule": "every Wednesday (NY date) unless --eia_csv; 祝日週の木曜へのずれは知識から記載・実行者が原典と照合",
                        "eia_csv": args.eia_csv, "B": args.B, "null": "sign(r0) を日で無作為に付け替え"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は 2 銘柄の全期間（2 本）。前後半・対照・|r0| の比は記述。"}
    ev_all = pd.concat(rows, ignore_index=True) if rows else None
    return res, ({"event_days": ev_all[["sym", "nydate", "year", "r0", "r123", "y"]]} if ev_all is not None else None)


def main():
    args = parse_args(default_B=DEFAULT_B, extra=_extra)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
