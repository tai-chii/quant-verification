#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q239: 休日前効果は SPX・NDX（2008〜2026）で残るか（祝日は欠損営業日から復元・Lakonishok・Smidt 1988 の型）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q239 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Lakonishok & Smidt (1988) "Are Seasonal Anomalies Real? A Ninety-Year Perspective" RFS 1（休日前の日のリターンは平日の 2〜5 倍）、
  Ariel (1990)。Kim & Park (1994)。本文未読・要旨のみ。知見 Q206（曜日効果は残らない）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "pre-holiday effect S&P 500 Lakonishok Smidt still present recent decades"）:
  Welch ほか（cfr.ivo-welch.info ko2021pre）など近年の再検討があり「弱まった」とする報告が多い。手元の 2008〜2026 で、祝日を
  価格データの欠損営業日から復元し、年内のラベル並べ替えで検定する形は未確認。追試（公表後 35 年超）。

【仮説（測る前に固定）】
H: 休日（取引所の休場日）の前の取引日のリターンは、それ以外の日より高い（差 > 0）。

【データ】`data_SPX_D1_long_yahoo.csv`・`data_NDX_D1_long_yahoo.csv`（2008-01〜2026-07）。

【定義（1通りに固定）】
- 休場日: 連続する取引日 t と t' の間に平日（月〜金）が 1 日以上欠けていて、かつ暦の差が 4 日以内（1 日の祝日＝データの穴と区別するため）。
  差が 5 日以上の穴は「データの欠損」として数え、判定から除く（件数を書く）。
- 休日前の日 = t（その日の終値リターン r_t = ln(c_t/c_{t−1})）。休日後の日 = t'（記述）。
- 差 = 休日前の日の平均 − それ以外の日の平均 [bp]。

【測るもの】銘柄ごと、前半（<2017）／後半（≥2017）／全期間: 休日前の件数、平均、差、z。休日後の差も記述。

【帰無】休日前のラベルを年内で並べ替え B=2000 → 差の帰無分布 → z。

【判定（事前固定・変更禁止）】
- SPX で前半・後半とも 差 > 0 かつ z ≥ 2 → 支持（残っている）。NDX は確認（同じ向きかを書く）。
- SPX の全期間の z < 2 → 棄却（残っていない）。
- それ以外 → 未確定。
多重比較: 判定は SPX の前後半 2 本。NDX・休日後は記述。

【捨てた案の数】約4: 祝日の暦を外部から持ち込む案（ネット遮断・欠損から復元で足りる）、週末前（金曜）も含める案（曜日効果と混ざる）、
休日前 2 日、US500（CFD は休場日も動く）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・差と z（前後半）・休日の件数を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_pre_holiday_q239.py            （B=2000・10 秒）
      python3 kensho_pre_holiday_q239.py --smoke
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

QID = "Q239"
DEFAULT_B = 2000
FILES = {"SPX": "SPX_D1_long_yahoo", "NDX": "NDX_D1_long_yahoo"}
MAX_GAP_DAYS = 4


def label_holidays(time):
    """time: DatetimeIndex（取引日）→ pre_holiday, post_holiday, data_hole（bool 配列）。"""
    t = pd.DatetimeIndex(time); n = len(t)
    pre = np.zeros(n, bool); post = np.zeros(n, bool); hole = np.zeros(n, bool); n_hol = 0
    for i in range(n - 1):
        gap = (t[i + 1] - t[i]).days
        if gap <= 1:
            continue
        missing_weekdays = int(np.busday_count((t[i] + pd.Timedelta(days=1)).date(), t[i + 1].date()))
        if missing_weekdays == 0:
            continue  # 週末だけ
        if gap <= MAX_GAP_DAYS:
            pre[i] = True; post[i + 1] = True; n_hol += 1
        else:
            hole[i] = True
    return pre, post, hole, n_hol


def diff_stats(df):
    out = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        d = df[(df["year"] >= y0) & (df["year"] < y1) & (~df["hole"])]
        a = d[d["pre_hol"]]; b = d[~d["pre_hol"]]
        if len(a) < 5:
            continue
        out[pn] = {"n_pre_holiday": int(len(a)), "mean_pre_bp": f(a["r"].mean()), "mean_other_bp": f(b["r"].mean()), "diff_bp": f(a["r"].mean() - b["r"].mean()),
                   "post_holiday_diff_bp": f(d[d["post_hol"]]["r"].mean() - d[~d["post_hol"]]["r"].mean())}
    return out


def run(args, rng):
    summary = {}; missing = []
    for s, name in FILES.items():
        if not args.smoke and not os.path.exists(os.path.join(DATA_DIR, f"data_{name}.csv")):
            missing.append(s); continue
        if args.smoke:
            df = _smoke_ohlc(s, rng, n=4600, freq="B", start="2008-01-01")
            keep = np.ones(len(df), bool); keep[rng.choice(len(df), 160, replace=False)] = False; df = df[keep].reset_index(drop=True)  # 祝日の穴を合成
        else:
            df = _read(os.path.join(DATA_DIR, f"data_{name}.csv"))
        df = df[df["close"] > 0].reset_index(drop=True)
        r = np.log(df["close"]).diff().values * 1e4
        pre, post, hole, n_hol = label_holidays(df["time"])
        d = pd.DataFrame({"year": df["time"].dt.year.values, "r": r, "pre_hol": pre, "post_hol": post, "hole": hole}).dropna(subset=["r"])
        obs = diff_stats(d); null = {pn: [] for pn in obs}
        for b in range(args.B):
            d2 = d.copy(); d2["pre_hol"] = perm_within(rng, d2["pre_hol"].values.astype(float), d2["year"].values).astype(bool)
            st = diff_stats(d2)
            for pn in obs:
                if pn in st:
                    null[pn].append(st[pn]["diff_bp"])
        for pn in obs:
            z, _ = z_of(obs[pn]["diff_bp"], null[pn]); obs[pn]["diff_z"] = f(z)
        summary[s] = {"n_holidays": n_hol, "n_data_holes": int(hole.sum()), "periods": obs}
    sp = summary.get("SPX", {}).get("periods", {})
    g = lambda pn, k: (sp.get(pn, {}).get(k) if sp.get(pn, {}).get(k) is not None else float("nan"))
    if all(g(pn, "diff_bp") > 0 and g(pn, "diff_z") >= 2 for pn in ("pre", "post")):
        verdict = "支持: 休日前効果は残っている（SPX）"
    elif g("all", "diff_z") < 2:
        verdict = "棄却: SPX 全期間の z < 2"
    else:
        verdict = "未確定"
    res = {"question": "休日前効果は SPX・NDX（2008〜2026）で残るか", "settings": {"files": FILES, "max_gap_days": MAX_GAP_DAYS, "B": args.B}, "missing": missing,
           "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は SPX 前後半の z 2 本。NDX・休日後は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
