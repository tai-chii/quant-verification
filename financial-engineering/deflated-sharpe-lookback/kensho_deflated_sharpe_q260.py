#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q260: 参照日数60通りから選んだ最良は Deflated Sharpe Ratio で補正すると何銘柄で残るか（Bailey・López de Prado 2014）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q260 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Bailey・López de Prado 2014（J. Portfolio Management・DSR）、[[Korzan2026-2_1214試行のDSRは97.05パーセントWhite_RCはp0.027で多重性補正後も有意だが最終3年のCAPMアルファは有意でない]]、知見 Q171（PBO 0.88）・Q139・Q172
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "deflated Sharpe ratio Bailey Lopez de Prado applied to trend following lookback selection multiple testing"）:
  見つかったもの: SSRN 2460551（原論文）、Wikipedia、quantstrat の deflatedSharpe、CXO「Sharper Sharpe ratio」。
  未確認: DSR を順張りの参照日数選択に 15 銘柄・並べ替え帰無つきで当てた形は未確認（追試）。

【仮説（測る前に固定）】
H: 各銘柄で参照日数 L∈{5,…,300}（60 通り）から標本内（2008–2016）の最良シャープを選び、DSR（試行数 60・試行のシャープの分散・歪度・尖度・日数で補正）を当てると、DSR≥0.95 で残る銘柄は 15 銘柄中 2 以下（名目 5% 並み）。

【データ】
15銘柄 D1_fromH1。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
試行 N=60。E[max SR] = √V·((1−γ)Φ⁻¹(1−1/N)+γΦ⁻¹(1−1/(Ne)))（γ=0.5772）。PSR(SR*, SR̂) を DSR とする。標本外 2017– の最良 L のシャープも記述。

【測るもの】
DSR≥0.95 の銘柄数（all15）、DSR と標本外シャープの Spearman。

【帰無】
リターンを年内で並べ替えた帰無で同じ手順（選択＋DSR）を B=200 回 → DSR≥0.95 の銘柄数の帰無分布 → 観測が帰無の 95 点を超えるか。

【判定（事前固定・変更禁止）】
DSR≥0.95 の銘柄数 ≤2 かつ 帰無の 95 点以下 → 支持（補正後は名目並み）。≥5 かつ 帰無の 95 点超 → 棄却（補正後も残る）。それ以外 → 未確定。
多重比較: 判定は銘柄数 1 本（DSR 自体が 60 試行の補正）。Spearman は記述。

【捨てた案の数】
約3: 試行数を 60×15 にする（銘柄をまたぐ選択はしない）、PBO と同時に出す（Q171 で済み）、月次シャープ。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_deflated_sharpe_q260.py            （B=200・中（B=200×60 通り×15・3〜5 分））
      python3 kensho_deflated_sharpe_q260.py --smoke    （合成データで経路の確認。判定には使わない）
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
from statistics import NormalDist

QID = "Q260"
DEFAULT_B = 200
LOOKBACKS = list(range(5, 301, 5))  # 60 通り
N_TRIALS = len(LOOKBACKS)
IS_END = SPLIT_YEAR   # 標本内 2008–2016、標本外 2017–
DSR_CUT = 0.95
EULER = 0.5772156649
_ND = NormalDist()


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def pnl_matrix(close, cost, Ls):
    """各 L の TSMOM の日次純損益 [bp] を列に持つ行列（n × len(Ls)）。pnl_bp と同じ約定規則。"""
    c = np.asarray(close, float); n = len(c)
    P = np.zeros((n, len(Ls)))
    for j, L in enumerate(Ls):
        P[L:, j] = np.sign(c[L:] - c[:-L])
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1
    held = np.vstack([np.zeros((1, len(Ls))), P[:-1]])
    prev = np.vstack([np.zeros((1, len(Ls))), held[:-1]])
    cshift = np.r_[0.0, cost[:-1]]
    return held * ret[:, None] * 1e4 - np.abs(held - prev) * cshift[:, None]


def moments(M):
    """列ごとの 日次シャープ・歪度・尖度（非超過）・日数。"""
    n = M.shape[0]
    mu = M.mean(0); sd = M.std(0, ddof=1)
    sr = np.where(sd > 0, mu / np.where(sd > 0, sd, 1), np.nan)
    e = M - mu
    s2 = (e ** 2).mean(0)
    skew = np.where(s2 > 0, (e ** 3).mean(0) / np.where(s2 > 0, s2, 1) ** 1.5, np.nan)
    kurt = np.where(s2 > 0, (e ** 4).mean(0) / np.where(s2 > 0, s2, 1) ** 2, np.nan)
    return sr, skew, kurt, n


def expected_max_sr(V, N):
    if not np.isfinite(V) or V <= 0:
        return float("nan")
    return math.sqrt(V) * ((1 - EULER) * _ND.inv_cdf(1 - 1 / N) + EULER * _ND.inv_cdf(1 - 1 / (N * math.e)))


def psr(sr_hat, sr_star, T, skew, kurt):
    den = 1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2
    if not (np.isfinite(den) and den > 0 and T > 1 and np.isfinite(sr_hat) and np.isfinite(sr_star)):
        return float("nan")
    return phi((sr_hat - sr_star) * math.sqrt(T - 1) / math.sqrt(den))


def select_and_dsr(M_is):
    """標本内の損益行列 → 最良 L の添字・SR̂・DSR・E[max SR]・V。"""
    sr, skew, kurt, T = moments(M_is)
    if not np.isfinite(sr).any():
        return None
    j = int(np.nanargmax(sr))
    V = float(np.nanvar(sr, ddof=1))
    sr_star = expected_max_sr(V, N_TRIALS)
    d = psr(sr[j], sr_star, T, skew[j], kurt[j])
    return {"j": j, "sr_hat_daily": float(sr[j]), "skew": float(skew[j]), "kurt": float(kurt[j]), "T": int(T),
            "V": V, "sr_star": float(sr_star), "dsr": float(d), "psr0": psr(sr[j], 0.0, T, skew[j], kurt[j])}


def run(args, rng):
    syms, missing = syms_available(SYMS, "D1_fromH1", args.smoke)
    data = {}
    rows = []
    for s in syms:
        if args.smoke:
            df = _smoke_ohlc(s, rng, n=5000, freq="D", start="2008-01-01")
            df = df[df["high"] != df["low"]].reset_index(drop=True); df["year"] = df["time"].dt.year
        else:
            df = load_d1(s, args.smoke, rng)
        c = df["close"].values; yrs = df["year"].values
        is_m = yrs < IS_END
        if is_m.sum() < 400 or (~is_m).sum() < 60:
            missing.append(s); continue
        cost = cost_bp_oneway(s, c)
        M = pnl_matrix(c, cost, LOOKBACKS)
        # 標本内は最初の約定日（L 日後）を含む行列の行で評価。標本外は選んだ L のみ。
        sel = select_and_dsr(M[is_m])
        if sel is None:
            missing.append(s); continue
        oos = M[~is_m, sel["j"]]
        is_ann = sharpe_ann(M[is_m, sel["j"]])
        data[s] = {"c": c, "cost": cost, "yrs": yrs, "is_m": is_m}
        rows.append({"sym": s, "best_L": LOOKBACKS[sel["j"]], "sr_is_daily": sel["sr_hat_daily"], "sr_is_ann": is_ann,
                     "skew": sel["skew"], "kurt": sel["kurt"], "T_is": sel["T"], "var_trials": sel["V"],
                     "sr_star_daily": sel["sr_star"], "psr_vs_0": sel["psr0"], "dsr": sel["dsr"],
                     "sr_oos_ann": sharpe_ann(oos), "pnl_oos_bp": float(np.mean(oos)), "n_oos": int(len(oos))})
    tab = pd.DataFrame(rows)
    if tab.empty:
        return {"question": "参照日数 60 通りから選んだ最良は DSR で補正すると何銘柄で残るか", "missing": missing, "summary": {},
                "machine_verdict": "未確定: 計算できない", "settings": {}, "multiple_comparisons": ""}, None
    n_keep = int((tab["dsr"] >= DSR_CUT).sum())
    rho = spearman(tab["dsr"].values, tab["sr_oos_ann"].values)

    # 帰無: 標本内のリターンを年内で並べ替え → 価格を作り直し → 同じ手順（選択＋DSR）→ DSR≥0.95 の銘柄数
    null_counts = []
    for b in range(args.B):
        cnt = 0
        for s, d in data.items():
            c = d["c"][d["is_m"]]; y = d["yrs"][d["is_m"]]
            r = np.r_[0.0, c[1:] / c[:-1] - 1]
            r2 = perm_within(rng, r, y); r2[0] = 0.0
            c2 = c[0] * np.cumprod(1 + r2)
            cost2 = cost_bp_oneway(s, c2)
            sel = select_and_dsr(pnl_matrix(c2, cost2, LOOKBACKS))
            if sel is not None and np.isfinite(sel["dsr"]) and sel["dsr"] >= DSR_CUT:
                cnt += 1
        null_counts.append(cnt)
    null_counts = np.array(null_counts, float)
    q95 = float(np.quantile(null_counts, 0.95)) if len(null_counts) else float("nan")
    pct = float((null_counts < n_keep).mean()) if len(null_counts) else float("nan")
    summary = {"all15": {"n_syms": int(len(tab)), "n_dsr_ge_095": n_keep, "null_q95": f(q95), "null_mean": f(null_counts.mean()) if len(null_counts) else None,
                         "pct_null_below_obs": f(pct), "spearman_dsr_vs_oos_sharpe": f(rho),
                         "mean_dsr": f(tab["dsr"].mean()), "mean_sr_oos_ann_bestL": f(tab["sr_oos_ann"].mean()),
                         "n_psr_vs0_ge_095": int((tab["psr_vs_0"] >= DSR_CUT).sum()),
                         "syms_dsr_ge_095": tab[tab["dsr"] >= DSR_CUT]["sym"].tolist()}}
    if not np.isfinite(q95):
        verdict = "未確定: 計算できない"
    elif n_keep <= 2 and n_keep <= q95:
        verdict = "支持: DSR≥0.95 の銘柄数 ≤2 かつ 帰無の 95 点以下（補正後は名目並み）"
    elif n_keep >= 5 and n_keep > q95:
        verdict = "棄却: DSR≥0.95 の銘柄数 ≥5 かつ 帰無の 95 点超（補正後も残る）"
    else:
        verdict = "未確定"
    res = {"question": "参照日数 60 通りから選んだ最良は Deflated Sharpe Ratio で補正すると何銘柄で残るか",
           "settings": {"lookbacks": f"{LOOKBACKS[0]}..{LOOKBACKS[-1]} step 5", "n_trials": N_TRIALS, "in_sample": f"<{IS_END}", "out_of_sample": f">={IS_END}",
                        "dsr_cut": DSR_CUT, "sharpe_unit": "日次（非年率）・DSR は日次の SR̂ と日数 T で計算", "B": args.B,
                        "null": "標本内リターンを年内で並べ替え（perm_within・年）→ 価格再構成 → 選択＋DSR"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は銘柄数 1 本（DSR 自体が 60 試行の補正）。Spearman・標本外シャープは記述。"}
    return res, {"per_sym": tab, "null_counts": pd.DataFrame({"b": np.arange(len(null_counts)), "n_dsr_ge_095": null_counts})}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
