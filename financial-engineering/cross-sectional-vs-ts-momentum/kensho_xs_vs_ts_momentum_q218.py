#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q218: 横断モメンタム（15 銘柄の上位 5 買い・下位 5 売り）は時系列モメンタムとコスト後にどれだけ違うか（Moskowitz ほか 2012 の型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum" JFE 104(2) — TSMOM は横断モメンタム（XSMOM）と別物で、TSMOM が XSMOM を説明する
  （表 5）。Goyal & Jegadeesh (2018) RFS 31(5) "Cross-Sectional and Time-Series Tests of Return Predictability: What Is the Difference?" — 差の大部分は
  TSMOM が持つ「市場全体のネット・ロング」（タイミング）で、それを揃えると差は小さい（表 2・3）。関連知見: Q150（銘柄選択バイアス）、Q152（売り側の分解）。
  → 本案は 15 銘柄で TS と XS を同じ参照（12 か月）・同じ保有（21 日）・同じボラ調整で作り、差と「ネット・ロング」の寄与を測る。

【仮説（測る前に固定）】
H1（Goyal・Jegadeesh の型）: XS − TS の純損益（bp/日・単位露出あたり）の差は、TS から「ネット・ロング分」（全銘柄等加重の買い持ち × TS の平均建玉）
    を引いた TS' と XS の差より大きい（差の大部分がタイミング）。
主判定は単純: 前後半とも XS − TS の年単位 t ≥ 2 → 「XS が強い」、≤ −2 → 「TS が強い」、それ以外は「差なし（ノイズ）」。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 合図の元: 直前 252 日リターン ÷ σ60（年率）（ボラ調整）。判定は 21 日ごと（全銘柄同じ日）。
- TS: 各銘柄 pos = sign(合図) ÷ 15。XS: 合図の順位で上位 5 を +1/10・下位 5 を −1/10・中央 5 を 0（単位露出 1）。
- 損益: 各銘柄の pnl_bp（段階 1 のコスト）に建玉を掛けて合計 [bp/日・単位露出]。
- TS' = TS − (TS の平均建玉 Σpos_i) × 等加重買い持ちの日次リターン（ネット・ロング分を除く）。
- 帰無: 合図を銘柄内で循環シフト（最小 42 日）B 回 → XS・TS それぞれの z（記述）。

【測るもの】TS・XS・TS' の bp/日と年単位 t、XS − TS と XS − TS' の差の t（前後半）、TS の平均ネット・ロング。

【判定（事前固定・変更禁止）】
前後半とも XS − TS の t ≥ 2 → XS が強い。前後半とも t ≤ −2 → TS が強い。それ以外は「差なし」で確定（ノイズ）。
H1（タイミングの寄与）は |XS − TS'| の t が |XS − TS| の t より小さいかを記述（判定本数に数えない）。

【捨てた案の数】約 4: 1 か月参照（Q215 で別途）、ボラ調整なし（商品と為替の建玉の大きさが揃わない）、上位 3・下位 3、毎日のリバランス。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・XS − TS の t（前後半）・Goyal 2018 表 2 の値を返す。

【実装】自己完結。実行: python3 kensho_xs_vs_ts_momentum_q218.py（B=300、1 分前後）／--B 30／--smoke
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

QID = "Q218"
DEFAULT_B = 300
LB, H, VOL_N, TOP = 252, 21, 60, 5


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    data = {s: load_d1(s, args.smoke, rng).set_index("time") for s in syms}
    idx = sorted(set().union(*[set(d.index) for d in data.values()]))
    idx = pd.DatetimeIndex(idx)
    close = pd.DataFrame({s: data[s]["close"].reindex(idx).ffill() for s in syms})
    ret = close.pct_change().fillna(0.0)
    sig = (close / close.shift(LB) - 1) / (ret.rolling(VOL_N).std() * math.sqrt(252))
    sig = sig.where(np.isfinite(sig))
    years = idx.year.values
    cb = {s: cost_bp_oneway(s, close[s].values) for s in syms}
    valid = pd.DataFrame({s: data[s]["close"].reindex(idx).notna() for s in syms})  # その銘柄にデータがある日

    def positions(sig):
        """21 日ごとに TS・XS の建玉行列を作る。"""
        n_t, k_s = len(idx), len(syms)
        TS = np.zeros((n_t, k_s)); XS = np.zeros((n_t, k_s))
        last_ts = np.zeros(k_s); last_xs = np.zeros(k_s)
        S = sig.values; V = valid.values
        for t in range(n_t):
            if t >= LB + VOL_N and (t - LB - VOL_N) % H == 0:
                s = np.where(V[t], S[t], np.nan); ok = np.isfinite(s); n = int(ok.sum())
                last_ts = np.where(ok, np.sign(s), 0.0) / max(n, 1)
                last_xs = np.zeros(k_s)
                if n >= 2 * TOP + 1:
                    k = min(TOP, n // 3)
                    top = np.argsort(np.where(ok, s, -np.inf))[-k:]; bot = np.argsort(np.where(ok, s, np.inf))[:k]
                    last_xs[top] = 1.0 / (2 * k); last_xs[bot] = -1.0 / (2 * k)
            TS[t] = last_ts; XS[t] = last_xs
        return pd.DataFrame(TS, index=idx, columns=syms), pd.DataFrame(XS, index=idx, columns=syms)

    def pnl_port(pos):
        tot = np.zeros(len(idx))
        for j, s in enumerate(syms):
            tot += np.nan_to_num(pnl_bp(pos[s].values, close[s].values, np.nan_to_num(cb[s])))  # データ開始前の NaN は 0（建玉も 0）
        return tot

    ts, xs = positions(sig)
    p_ts, p_xs = pnl_port(ts), pnl_port(xs)
    net_long = ts.sum(axis=1).values  # TS の平均建玉（ネット・ロング）
    ew = (ret.where(valid).mean(axis=1).fillna(0.0).values) * 1e4
    p_ts_prime = p_ts - np.r_[0.0, net_long[:-1]] * ew
    start = LB + VOL_N + 1
    def yearly(x, y0, y1):
        ser = pd.Series(x[start:]).groupby(years[start:]).mean(); return ser[(ser.index >= y0) & (ser.index < y1)]
    obs = {}
    for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        a, b, c = yearly(p_ts, y0, y1), yearly(p_xs, y0, y1), yearly(p_ts_prime, y0, y1)
        if a.empty:
            continue
        obs[pn] = {"n_years": int(len(a)), "TS_bp": float(a.mean()), "TS_t": tstat(a.values), "XS_bp": float(b.mean()), "XS_t": tstat(b.values), "TSprime_bp": float(c.mean()),
                   "XS_minus_TS_bp": float((b - a).mean()), "XS_minus_TS_t": tstat((b - a).values), "XS_minus_TSprime_bp": float((b - c).mean()), "XS_minus_TSprime_t": tstat((b - c).values),
                   "mean_net_long": float(np.mean(net_long[start:][(years[start:] >= y0) & (years[start:] < y1)]))}
    null = {pn: {"TS": [], "XS": []} for pn in obs}
    for bidx in range(args.B):
        sp = sig.copy()
        for s in syms:
            sp[s] = circ_shift(rng, sig[s].values, 42)
        tsp, xsp = positions(sp); a_, b_ = pnl_port(tsp), pnl_port(xsp)
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            if pn in obs:
                null[pn]["TS"].append(float(yearly(a_, y0, y1).mean())); null[pn]["XS"].append(float(yearly(b_, y0, y1).mean()))
        if bidx % 50 == 0:
            print("null", bidx)
    summary = {}
    for pn, v in obs.items():
        zt, _ = z_of(v["TS_bp"], null[pn]["TS"]); zx, _ = z_of(v["XS_bp"], null[pn]["XS"])
        summary[pn] = {**{k: (f(x) if isinstance(x, float) else x) for k, x in v.items()}, "TS_z": f(zt), "XS_z": f(zx)}
    pre, post = summary.get("pre", {}), summary.get("post", {})
    g = lambda p, k: (p.get(k) or 0)
    if g(pre, "XS_minus_TS_t") >= 2 and g(post, "XS_minus_TS_t") >= 2:
        verdict = "確定: 横断モメンタムが時系列より強い"
    elif g(pre, "XS_minus_TS_t") <= -2 and g(post, "XS_minus_TS_t") <= -2:
        verdict = "確定: 時系列モメンタムが横断より強い"
    else:
        verdict = "ノイズ: 前後半で揃った差はない"
    timing_note = "タイミングの寄与: |XS−TS'| の t が |XS−TS| の t より " + ("小さい（差の一部はネット・ロング）" if abs(g(summary.get("all", {}), "XS_minus_TSprime_t")) < abs(g(summary.get("all", {}), "XS_minus_TS_t")) else "小さくない")
    res = {"question": "横断モメンタムは時系列モメンタムとコスト後にどれだけ違うか", "settings": {"LB": LB, "H": H, "VOL_N": VOL_N, "TOP": TOP, "B": args.B}, "missing": missing,
           "summary": summary, "timing_note": timing_note, "machine_verdict": verdict, "multiple_comparisons": "判定は前後半の XS−TS の t の 2 本（両側）。z・TS'・ネット・ロングは記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
