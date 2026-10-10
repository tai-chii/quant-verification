#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q219: 米雇用統計（NFP）の直後 15 分の向きは次の 1〜4 時間に続くか反転するか（EURUSD・USDJPY M15・2021 年以降）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Andersen, Bollerslev, Diebold, Vega (2003) "Micro Effects of Macro Announcements" AER 93(1) — 為替は指標発表後数分で反応を終え、
  その後の継続は小さい（表 3・図 2）。Evans & Lyons (2008) JME はニュース後の注文フローを通じた遅い反映を報告。
  関連知見: Q153（15 分足の時刻の自己相関は多重比較で残らない）、Q057（ロンドン開始 30 分の合図は 2025 年以降消えた）。
  → 本案は発表時刻が暦で決まる NFP だけを対象に、直後 15 分の向きが +1h・+4h に続くか反転するかを、同じ時刻の他の金曜（対照）と比べる。

【仮説（測る前に固定）】
H1: NFP 発表足（12:30 または 13:30 UTC 始まりの 15 分足）の向き d に対し、発表足の終値から +1h（+4h）のリターン × d は正（継続）で、
    2 通貨をまとめた事象単位の t ≥ 2、かつ対照（NFP でない金曜の同じ時刻）との差の帰無 z ≥ 2。
H1'（反転）: t ≤ −2 かつ z ≤ −2。H0: どちらでもない。

【データ】EURUSD・USDJPY M15_dukascopy（2021-01〜2026-07、約 66 回の NFP）。期間が短いので前後半は記述（2021〜2023／2024〜）。

【定義（1 通りに固定）】
- NFP 日: 各月の第 1 金曜（例外の月は含めたまま。備考に「暦の例外は未補正」）。発表時刻: 米国夏時間（3 月第 2 日曜〜11 月第 1 日曜）は 12:30 UTC、それ以外 13:30 UTC。
- d = sign(発表足の終値 − 始値)。継続リターン = (close_{+1h} − close_発表足) ÷ close_発表足 × 1e4 × d − 往復コスト（EURUSD 2bp・USDJPY 2pips 相当）。+4h も同じ。
- 対照: NFP でない全ての金曜の同じ時刻の足に同じ規則。
- 統計量: 事象（通貨×NFP 日）ごとの純損益 → 平均と t（NW ラグ 1）。差 = NFP 平均 − 対照平均。帰無: NFP ラベルを金曜の中で並べ替え B 回 → z。

【測るもの】+1h・+4h の継続純損益と t（事象単位）、対照との差と z、発表足の絶対リターンの対照比（反応の大きさ）、通貨別・前後半。

【判定（事前固定・変更禁止）】
+1h と +4h の両方で 継続の t ≥ 2 かつ 差の z ≥ 2 → 「継続」で確定。両方で t ≤ −2 かつ z ≤ −2 → 「反転」で確定。それ以外は棄却（区別できない）。n≈130 事象と小さいことを備考に。

【捨てた案の数】約 4: 他の指標（CPI・FOMC は暦が不規則）、発表前のポジション（方向の予測は別問題）、M1 足（データなし）、閾値つき（反応が大きい時だけ）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・+1h/+4h の t と z・Andersen 2003 表 3 の該当値を返す。

【実装】自己完結。実行: python3 kensho_nfp_followthrough_q219.py（B=1000、1 分以内）／--B 100／--smoke
"""

# ============================================================================= 共通の土台（各スクリプトに同じものを埋め込む・自己完結）
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

QID = "Q219"
DEFAULT_B = 1000
PAIRS = ["EURUSD", "USDJPY"]
HORIZONS = {"1h": 4, "4h": 16}
SPLIT_N = 2024


def us_dst(d):
    """米国夏時間か（3 月第 2 日曜〜11 月第 1 日曜）。"""
    y = d.year
    mar = pd.Timestamp(y, 3, 1); start = mar + pd.Timedelta(days=(6 - mar.dayofweek) % 7 + 7)
    nov = pd.Timestamp(y, 11, 1); end = nov + pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return start <= d < end


def first_fridays(dates):
    out = set()
    for (y, m) in sorted({(d.year, d.month) for d in dates}):
        d0 = pd.Timestamp(y, m, 1); ff = d0 + pd.Timedelta(days=(4 - d0.dayofweek) % 7); out.add(ff)
    return out


def events(m15, sym):
    df = m15.copy(); df["date"] = df["time"].dt.floor("D")
    fri = df[df["time"].dt.dayofweek == 4]
    dates = sorted(fri["date"].unique()); nfp = first_fridays([pd.Timestamp(d) for d in dates])
    byt = df.set_index("time")
    cost_rt = COST_RT[sym]
    rows = []
    for d in dates:
        d = pd.Timestamp(d); rel = d + pd.Timedelta(hours=12 if us_dst(d) else 13, minutes=30)
        if rel not in byt.index:
            continue
        bar = byt.loc[rel]; dsign = np.sign(bar["close"] - bar["open"])
        if dsign == 0:
            continue
        pos = byt.index.get_loc(rel); r = {"sym": sym, "date": d, "nfp": int(d in nfp), "year": d.year, "abs_bar_bp": float(abs(bar["close"] / bar["open"] - 1) * 1e4)}
        ok = True
        for name, k in HORIZONS.items():
            j = pos + k
            if j >= len(byt) or (byt.index[j] - rel) > pd.Timedelta(minutes=15 * k + 30):
                ok = False; break
            r[name] = float((byt["close"].iloc[j] / bar["close"] - 1) * 1e4 * dsign - cost_rt / bar["close"] * 1e4)
        if ok:
            rows.append(r)
    return pd.DataFrame(rows)


def stats(ev, lab="nfp"):
    out = {}
    for name in HORIZONS:
        a = ev.loc[ev[lab] == 1, name].values; c = ev.loc[ev[lab] == 0, name].values
        out[name] = {"n_nfp": int(len(a)), "nfp_mean_bp": float(a.mean()) if len(a) else float("nan"), "nfp_t": nw_t(a, 1), "control_mean_bp": float(c.mean()) if len(c) else float("nan"),
                     "diff_bp": float(a.mean() - c.mean()) if len(a) and len(c) else float("nan")}
    return out


def run(args, rng):
    syms, missing = syms_available(PAIRS, kind="M15_dukascopy", smoke=args.smoke)
    ev = pd.concat([events(load_csv(f"{s}_M15_dukascopy", args.smoke, rng, freq="15min", n=120000, start="2021-01-04"), s) for s in syms], ignore_index=True)
    obs = stats(ev)
    null = {name: [] for name in HORIZONS}
    for b in range(args.B):
        ev["nfp_p"] = perm_within(rng, ev["nfp"].values.astype(float), ev["sym"].values).astype(int); st = stats(ev, "nfp_p")
        for name in HORIZONS:
            null[name].append(st[name]["diff_bp"])
    summary = {}
    for name, v in obs.items():
        z, _ = z_of(v["diff_bp"], null[name]); summary[name] = {**{k: (f(x) if isinstance(x, float) else x) for k, x in v.items()}, "diff_z": f(z)}
    reaction = {"nfp_abs_bar_bp": f(ev.loc[ev["nfp"] == 1, "abs_bar_bp"].mean()), "control_abs_bar_bp": f(ev.loc[ev["nfp"] == 0, "abs_bar_bp"].mean())}
    by = {}
    for s in syms:
        by[s] = {k: {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in stats(ev[ev["sym"] == s]).items()}
    for pn, m in (("pre", ev["year"] < SPLIT_N), ("post", ev["year"] >= SPLIT_N)):
        by[pn] = {k: {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in stats(ev[m]).items()}
    g = lambda p, k: (p.get(k) or 0)
    cont = all(g(summary[h], "nfp_t") >= 2 and g(summary[h], "diff_z") >= 2 for h in HORIZONS)
    rev = all(g(summary[h], "nfp_t") <= -2 and g(summary[h], "diff_z") <= -2 for h in HORIZONS)
    verdict = "確定: NFP 直後の向きは継続する" if cont else ("確定: NFP 直後の向きは反転する" if rev else "棄却: 継続とも反転とも区別できない")
    res = {"question": "NFP 直後 15 分の向きは次の 1〜4 時間に続くか反転するか", "settings": {"horizons_bars": HORIZONS, "split": SPLIT_N, "B": args.B}, "missing": missing,
           "n_events": int((ev["nfp"] == 1).sum()), "summary": summary, "reaction_size": reaction, "by_pair_and_period": by, "machine_verdict": verdict,
           "notes": "第 1 金曜の暦の例外（祝日ずれ）は未補正。n は小さい。", "multiple_comparisons": "判定は +1h・+4h の t と z の 4 本。通貨別・前後半は記述。"}
    return res, {"events": ev}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
