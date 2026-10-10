#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q264: 暗号資産11通貨の H1 の分散比は 2022 年以降に 1 へ近づいたか（適応的市場仮説の移植）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q264 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Lo・MacKinlay 1988（分散比）、[[Alahmadi・Basingab2026-3_設定の選び方が弱形効率性検定の結論に実質的に効く]]、知見 Q148・Q149、Tehran／ASE の AMH 論文（要旨）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "cryptocurrency market efficiency variance ratio test over time improving efficiency 2022 2023 hourly altcoins"）:
  見つかったもの: Tehran IJMS「Adaptive Market Hypothesis: Evidence From the Cryptocurrency Market」、RFB 2024「Evolving Efficiency of Cryptocurrency Market」、Springer 章。
  未確認: 多くは日次・BTC/ETH 中心。11 通貨 H1・暦年・2022 分割・年ラベル並べ替え帰無は未確認（移植＋条件の穴）。

【仮説（測る前に固定）】
H: 各通貨・暦年の H1 対数リターンの分散比 VR(q=24)（1 日）の |VR−1| は 2022 以降の年で 2018–2021 より小さい（効率化）。

【データ】
暗号資産 11 通貨 H1_dukascopy（2017/2018〜2026-09）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
VR(q)=Var(q 時間リターン)/(q·Var(1 時間リターン))（重なり窓・Lo-MacKinlay の不均一分散に頑健な z は記述）。年×通貨の |VR−1|。

【測るもの】
D = mean|VR−1|(2022–) − mean|VR−1|(〜2021)（通貨を束ねて年単位 t）。q=6・168 は副次。

【帰無】
年ラベルを通貨内で並べ替え（前後を壊す）B=2000 → D の帰無分布 → z。

【判定（事前固定・変更禁止）】
D<0 かつ t≤−2 かつ z≤−2 → 支持（1 に近づいた）。D>0 かつ z≥2 → 逆向きで確定（遠ざかった）。それ以外 → 棄却（変化は見えない）。
多重比較: 判定は q=24 の D 1 本。q=6・168 は記述。

【捨てた案の数】
約3: Hurst 指数（Q169 系で済み）、rolling 窓（暦年で固定）、符号つき VR の平均（|VR−1| に統一）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_crypto_vr_trend_q264.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_crypto_vr_trend_q264.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q264"
DEFAULT_B = 2000
Q_MAIN = 24
Q_SUB = (6, 168)
SPLIT_CRYPTO = 2022
KIND = "H1_dukascopy"
MIN_HOURS = 2000


def variance_ratio(r, q):
    """Lo-MacKinlay の分散比（重なり窓）と不均一分散に頑健な z。r: 1 時間対数リターン。"""
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    n = len(r)
    if n < 5 * q:
        return float("nan"), float("nan")
    mu = r.mean()
    s1 = ((r - mu) ** 2).sum() / (n - 1)
    rq = np.convolve(r, np.ones(q), mode="valid")          # 重なり q 時間リターン
    m = (n - q + 1) * (1 - q / n)                            # Lo-MacKinlay の自由度補正
    sq = ((rq - q * mu) ** 2).sum() / m
    vr = sq / (q * s1) if s1 > 0 else float("nan")
    e2 = (r - mu) ** 2; den = e2.sum() ** 2
    theta = 0.0
    for k in range(1, q):
        dk = (e2[k:] * e2[:-k]).sum() / den
        theta += (2 * (q - k) / q) ** 2 * dk
    z = (vr - 1) / math.sqrt(theta) if theta > 0 else float("nan")
    return float(vr), float(z)


def run(args, rng):
    syms, missing = syms_available(CRYPTO, KIND, args.smoke)
    rows = []
    for s in syms:
        h1 = load_h1(s, args.smoke, rng, n=60000, start="2018-01-01")
        lr = np.log(h1["close"].values); r = np.diff(lr); yrs = h1["year"].values[1:]
        for yr in np.unique(yrs):
            m = yrs == yr
            if m.sum() < MIN_HOURS:
                continue
            rec = {"sym": s, "year": int(yr), "n_hours": int(m.sum())}
            for q in (Q_MAIN,) + Q_SUB:
                vr, z = variance_ratio(r[m], q)
                rec[f"vr_{q}"] = vr; rec[f"z_lm_{q}"] = z; rec[f"absdev_{q}"] = abs(vr - 1) if np.isfinite(vr) else np.nan
            rows.append(rec)
    cells = pd.DataFrame(rows)
    if cells.empty:
        return {"question": "暗号資産 H1 の分散比は 2022 以降 1 に近づいたか", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない", "settings": {}, "multiple_comparisons": ""}, None

    def D_stat(df, col, years):
        """年ごとに通貨を平均 → 後半の平均 − 前半の平均、Welch t。"""
        yr = df.assign(year=years).groupby(["year", "sym"])[col].mean().groupby(level=0).mean().dropna()
        a = yr[yr.index >= SPLIT_CRYPTO].values; b = yr[yr.index < SPLIT_CRYPTO].values
        if len(a) < 2 or len(b) < 2:
            return float("nan"), float("nan"), len(a), len(b)
        d = a.mean() - b.mean()
        se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        return float(d), float(d / se) if se > 0 else float("nan"), len(a), len(b)

    summary = {}
    null = []
    for q in (Q_MAIN,) + Q_SUB:
        col = f"absdev_{q}"
        D, t, na, nb = D_stat(cells, col, cells["year"].values)
        summary[f"q{q}"] = {"D": f(D), "t_welch": f(t), "n_years_post": na, "n_years_pre": nb,
                            "mean_absdev_pre": f(cells[cells["year"] < SPLIT_CRYPTO][col].mean()),
                            "mean_absdev_post": f(cells[cells["year"] >= SPLIT_CRYPTO][col].mean()),
                            "mean_vr_pre": f(cells[cells["year"] < SPLIT_CRYPTO][f"vr_{q}"].mean()),
                            "mean_vr_post": f(cells[cells["year"] >= SPLIT_CRYPTO][f"vr_{q}"].mean()),
                            "share_abs_z_lm_gt2": f((cells[f"z_lm_{q}"].abs() > 2).mean())}
        if q == Q_MAIN:
            # 帰無: 年ラベルを通貨内で並べ替え（前後を壊す）
            sym_codes = cells["sym"].values
            for b in range(args.B):
                yperm = perm_within(rng, cells["year"].values.astype(float), sym_codes).astype(int)
                null.append(D_stat(cells, col, yperm)[0])
            z, pct = z_of(D, null)
            summary[f"q{q}"]["z"] = f(z); summary[f"q{q}"]["pct"] = f(pct)
    m = summary[f"q{Q_MAIN}"]
    D, t, z = m["D"], m["t_welch"], m["z"]
    if D is None or t is None or z is None:
        verdict = "未確定: 計算できない"
    elif D < 0 and t <= -2 and z <= -2:
        verdict = "支持: D<0 かつ t≤−2 かつ z≤−2（1 に近づいた）"
    elif D > 0 and z >= 2:
        verdict = "逆向きで確定: D>0 かつ z≥2（遠ざかった）"
    else:
        verdict = "棄却: 変化は見えない"
    res = {"question": "暗号資産 11 通貨の H1 分散比 VR(24) の |VR−1| は 2022 以降の年で小さいか（効率化）",
           "settings": {"syms": CRYPTO, "kind": KIND, "q_main": Q_MAIN, "q_sub": Q_SUB, "split_year": SPLIT_CRYPTO, "min_hours_per_year": MIN_HOURS,
                        "B": args.B, "null": "年ラベルを通貨内で並べ替え（perm_within・sym）", "t": "年平均（通貨を束ねる）の前後 2 群 Welch t",
                        "note": "値動きのない足（high==low）は load_h1 で除かれるので、1 時間リターンは連続する残存足の差"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は q=24 の D 1 本。q=6・168 と Lo-MacKinlay の z は記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
