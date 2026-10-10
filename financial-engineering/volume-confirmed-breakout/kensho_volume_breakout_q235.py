#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q235: ティック出来高の急増つきドンチャン・ブレイクアウトは、継続率と純損益を上げるか（15 銘柄・H1 出来高から日足）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q235 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- 知見 Q216（出来高の多い日のリターンは翌日に続かず符号は反転・棄却）、知見 Q220（アジアレンジのブレイクアウトは続かない）、
  [[Park2007-1_近代研究95本のうち56本がテクニカルの収益性を支持]]（出来高つきルールを含む）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "volume confirmation breakout Donchian channel does volume improve breakout success empirical study"）:
  教材・TradingView・StockSharp の例ばかりで、ラベル並べ替えの帰無と前後半で「出来高の確認の有無」の差を測った研究は未確認。条件の穴。
  注意: Dukascopy の volume はティック数（FX・CFD）で約定数量ではない。

【仮説（測る前に固定）】
H: ドンチャン（55 日高値/安値の抜けで入り、20 日の逆側で出る）のブレイク日の出来高が直前 20 日の中央値の 1.5 倍以上
   （「確認あり」）の取引は、確認なしの取引より、10 日後の継続率と 1 取引あたり純損益が高い。

【データ】15 銘柄の H1（Dukascopy・volume 列）→ UTC 日足（h1_to_d1。volume は 1 日の合計）。volume の合計が 0 の日が全体の 1% を超える
銘柄は除いて missing に書く（指数の初期など）。

【定義（1通りに固定）】
- 入り: 終値 > 直前 55 日の高値 → 買い、終値 < 直前 55 日の安値 → 売り（t の終値で決め t+1 から保有）。出: 終値が直前 20 日の安値（買い）／高値（売り）を割る。
- 確認: ブレイク日の volume ≥ 1.5 × median(volume の直前 20 日)。
- 取引の純損益 [bp] = 保有中の pos × 日次リターン × 1e4 の合計 − 往復コスト（段階1）。継続 = 10 日後の終値がブレイク方向に進んでいる（1/0）。
- 差 = 確認あり − 確認なし（1 取引あたり純損益、継続率）。取引を年で束ねて年単位の t。

【測るもの】群 all15・fx8・trend7 × 前半（<2017）／後半（≥2017）／全期間: 取引数、純損益・継続率の差と t・z、無条件の純損益。

【帰無】ブレイク日の「確認あり」のラベルを年内で並べ替え（割合は保つ）B=300 → 差の帰無分布 → z。

【判定（事前固定・変更禁止）】
- all15 で前半・後半とも 純損益の差 > 0 かつ z ≥ 2 → 支持。
- all15 で前半・後半とも 差 ≤ 0 → 棄却（確認は役に立たない。Q216 と同じ向き）。
- それ以外 → 未確定。
多重比較: 判定は all15 前後半の純損益の差の z 2 本。継続率・群別は記述。

【捨てた案の数】約4: 20/10 日の短いドンチャン、倍率 2.0、出来高の順位（分位）で刻む案、ブレイク後 3 日の出来高を使う案（先読み）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・差と z（前後半）・取引数を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_volume_breakout_q235.py            （B=300・2 分前後。H1 の読み込みが主）
      python3 kensho_volume_breakout_q235.py --smoke
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

QID = "Q235"
DEFAULT_B = 300
N_IN, N_OUT = 55, 20
VOL_MULT = 1.5
HORIZON = 10


def donchian_trades(d):
    """d: 日足 DataFrame。取引の一覧（entry_idx, exit_idx, side）。"""
    c = d["close"].values; h = d["high"].values; l = d["low"].values; n = len(c)
    hi55 = pd.Series(h).shift(1).rolling(N_IN).max().values; lo55 = pd.Series(l).shift(1).rolling(N_IN).min().values
    hi20 = pd.Series(h).shift(1).rolling(N_OUT).max().values; lo20 = pd.Series(l).shift(1).rolling(N_OUT).min().values
    trades = []; p = 0; e = None
    for t in range(n):
        if p == 0:
            if np.isfinite(hi55[t]) and c[t] > hi55[t]:
                p, e = 1, t
            elif np.isfinite(lo55[t]) and c[t] < lo55[t]:
                p, e = -1, t
        else:
            if (p == 1 and np.isfinite(lo20[t]) and c[t] < lo20[t]) or (p == -1 and np.isfinite(hi20[t]) and c[t] > hi20[t]):
                trades.append((e, t, p)); p = 0; e = None
    if p != 0:
        trades.append((e, n - 1, p))
    return trades


def trade_table(d, sym):
    c = d["close"].values; v = d["volume"].values; yr = d["year"].values; cb = cost_bp_oneway(sym, c)
    vmed = pd.Series(v).shift(1).rolling(20).median().values
    rows = []
    for e, x, side in donchian_trades(d):
        if x <= e or not np.isfinite(vmed[e]) or vmed[e] <= 0:
            continue
        gross = side * (c[x] / c[e] - 1) * 1e4
        net = gross - 2 * cb[e]
        cont = int(side * (c[min(e + HORIZON, len(c) - 1)] - c[e]) > 0) if e + HORIZON < len(c) else np.nan
        rows.append({"sym": sym, "year": int(yr[e]), "side": side, "net_bp": float(net), "cont": cont, "confirmed": int(v[e] >= VOL_MULT * vmed[e]), "hold": int(x - e)})
    return pd.DataFrame(rows)


def diff_stats(tr, col="net_bp"):
    out = {}
    for g, members in GROUPS.items():
        tg = tr[tr["sym"].isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = tg[(tg["year"] >= y0) & (tg["year"] < y1)]
            if d.empty or d["confirmed"].nunique() < 2:
                continue
            a = d[d["confirmed"] == 1]; b = d[d["confirmed"] == 0]
            ya = a.groupby("year")[col].mean(); yb = b.groupby("year")[col].mean(); dd = (ya - yb).dropna()
            out[f"{g}_{pn}"] = {"n_trades": int(len(d)), "n_confirmed": int(len(a)), "mean_confirmed": f(a[col].mean()), "mean_unconfirmed": f(b[col].mean()),
                                "diff": f(a[col].mean() - b[col].mean()), "diff_year_t": f(tstat(dd.values)), "net_all_bp": f(d["net_bp"].mean()),
                                "cont_confirmed": f(a["cont"].mean()), "cont_unconfirmed": f(b["cont"].mean())}
    return out


def run(args, rng):
    tabs = []; missing = []
    for s in SYMS:
        if not args.smoke and not exists_sym(s, "H1_dukascopy"):
            missing.append(s); continue
        h1 = load_h1(s, args.smoke, rng, n=140000, start="2008-01-01")
        if args.smoke:  # 合成データの出来高は分散が小さすぎるので、日ごとの変動を足す（判定には使わない）
            h1["volume"] = h1["volume"].values * np.exp(rng.normal(0, 1.0, len(h1)))
        d = h1_to_d1(h1)
        if (d["volume"] <= 0).mean() > 0.01:
            missing.append(f"{s}(volume_zero>1%)"); continue
        d = d[d["volume"] > 0].reset_index(drop=True); d["year"] = d["time"].dt.year
        tabs.append(trade_table(d, s))
    tr = pd.concat(tabs, ignore_index=True)
    obs = diff_stats(tr)
    null = {k: [] for k in obs}
    for b in range(args.B):
        t2 = tr.copy(); t2["confirmed"] = perm_within(rng, t2["confirmed"].values.astype(float), t2["sym"].astype(str).values + "_" + t2["year"].astype(str).values).astype(int)
        st = diff_stats(t2)
        for k in obs:
            if k in st:
                null[k].append(st[k]["diff"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        z, _ = z_of(v["diff"] if v["diff"] is not None else np.nan, null[k]); summary[k] = {**v, "diff_z": f(z)}
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, q: (p.get(q) if p.get(q) is not None else float("nan"))
    if all(g(p, "diff") > 0 and g(p, "diff_z") >= 2 for p in (pre, post)):
        verdict = "支持: 出来高の確認は純損益を上げる"
    elif all(g(p, "diff") <= 0 for p in (pre, post)):
        verdict = "棄却: 確認ありの純損益は確認なし以下"
    else:
        verdict = "未確定"
    conf_share = f(tr["confirmed"].mean())
    if conf_share is None or conf_share < 0.05 or conf_share > 0.95:
        verdict = f"未確定: 確認ありの割合 {conf_share} が偏りすぎ（倍率 1.5 の定義を見直す。判定規則は変えない）"
    res = {"question": "出来高の急増つきドンチャン・ブレイクアウトは継続率と純損益を上げるか", "settings": {"n_in": N_IN, "n_out": N_OUT, "vol_mult": VOL_MULT, "horizon": HORIZON, "B": args.B},
           "confirmed_share": conf_share, "missing": missing, "summary": summary, "machine_verdict": verdict, "multiple_comparisons": "判定は all15 前後半の純損益の差の z 2 本。"}
    return res, {"trades": tr}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
