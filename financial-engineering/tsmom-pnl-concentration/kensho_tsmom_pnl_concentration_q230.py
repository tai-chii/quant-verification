#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q230: 順張りの純損益は上位 1% の日に集中しているか — 最大の k 日を除くと年単位の t が 2 を切るか（15 銘柄 D1）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q230 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- [[Feng2026-2_標本外でアルファが弱まる原因は偽の発見と裁定と構造変化]]（アルファの頑健性の点検）、知見 Q143（順張りの年次純損益は 2008 年の突出が
  支配）、知見 Q144（2 か月の成績は運と区別できない）。Hurst・Ooi・Pedersen 2017（順張りの利益は少数の大きなトレンドから出る、と一般に言われる）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "trend following profits concentrated few days removing best days time series momentum"）:
  「最良の日を除く」議論は買い持ちの文脈（市場タイミングの反論）で多数。順張りの日次純損益についてランダムな合図の帰無と比べて集中度を
  測る形は未確認。条件の穴。

【仮説（測る前に固定）】
H: 15 銘柄の日足順張り（TSMOM60）の純損益は少数の日に集中しており、各銘柄の最良 1% の日を除くと、年を単位にした t が 2 を切る。
   かつ、その集中度（上位 1% の日の粗利の合計 ÷ 粗利の正の部分の合計）は、循環シフトで合図とリターンの対応を壊した帰無より高い。

【データ】15 銘柄の UTC 日足（`data_<SYM>_D1_fromH1.csv`、2008〜2026-06）。無い銘柄は除いて missing に書く。

【定義（1通りに固定）】
- 合図 s_t = sign(c_t − c_{t−60})、翌日のポジション。日次純損益 [bp] = pos × 翌日リターン × 1e4 − |Δpos| × 片道コスト（段階1）。
- 「最良 k% の日」= 銘柄ごとに純損益の上位 k% の日（k ∈ {1, 2, 5}）。除いた系列で年×銘柄の平均 → 年の平均 → 年単位の t（by_year_stats）。
- 両側トリム（上位 k% と下位 k% の両方を除く）も出す（記述）。
- 集中度 C1 = 上位 1% の日の純損益の合計 ÷ 正の日の純損益の合計（銘柄ごと → 群の平均）。

【測るもの】群 all15・fx8・trend7、期間 前半（<2017）／後半（≥2017）／全期間: t_full、t_trim(k)、C1、帰無の C1 の分布に対する z。

【帰無】循環シフト（合図の列を 252 日以上ずらす）B=300 → 帰無の C1 と t_full・t_trim(1%) の分布。

【判定（事前固定・変更禁止）】
- all15 で前半・後半とも t_full ≥ 2 かつ t_trim(1%) < 2 → 支持（上位 1% の日に依存）。
- all15 で前半・後半とも t_trim(1%) ≥ 2 → 棄却（集中していない）。
- all15 で t_full < 2 の期間がある → 未確定（もともと有意でないので集中を問えない。C1 の z は記述）。
多重比較: 判定は all15 の前後半 × (t_full, t_trim1) の 4 本。k=2・5、両側トリム、群別、C1 の z は記述。

【捨てた案の数】約4: 上位 k 日を絶対日数で指定（期間の長さが違うので % に）、シャープで測る案（t に統一）、月単位で除く案、
TSMOM20 を並べる案（1 本固定）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。規則は固定。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・t_full/t_trim・C1 と z を返す。

【実装】自己完結・決定的（乱数は循環シフトのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_tsmom_pnl_concentration_q230.py            （B=300・1 分前後）
      python3 kensho_tsmom_pnl_concentration_q230.py --smoke
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

QID = "Q230"
DEFAULT_B = 300
L_MOM = 60
KS = [1, 2, 5]


def trim_mask(pnl, k_pct, both=False):
    """上位 k% （both なら下位 k% も）の日を除くマスク（True=残す）。"""
    x = np.asarray(pnl, float); n = len(x); keep = np.ones(n, bool)
    m = max(1, int(round(n * k_pct / 100.0)))
    order = np.argsort(x)
    keep[order[-m:]] = False
    if both:
        keep[order[:m]] = False
    return keep


def concentration(pnl, k_pct=1):
    x = np.asarray(pnl, float); pos = x[x > 0]
    if len(pos) == 0:
        return float("nan")
    m = max(1, int(round(len(x) * k_pct / 100.0)))
    top = np.sort(x)[-m:]
    return float(top.sum() / pos.sum())


def stats_from(frames):
    """frames: {sym: DataFrame(year, pnl)} → 群×期間の t_full と t_trim(k)。"""
    out = {}
    for g, members in GROUPS.items():
        rows = []
        for s in members:
            if s in frames:
                rows.append(frames[s].assign(sym=s))
        if not rows:
            continue
        df = pd.concat(rows, ignore_index=True)
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = df[(df["year"] >= y0) & (df["year"] < y1)]
            if d.empty:
                continue
            r = {"n_years": by_year_stats(d, "pnl")["n_years"], "pnl_bp": f(by_year_stats(d, "pnl")["mean"]), "t_full": f(by_year_stats(d, "pnl")["t"])}
            for k in KS:
                parts = []; parts2 = []
                for s, dd in d.groupby("sym"):
                    keep = trim_mask(dd["pnl"].values, k); parts.append(dd[keep])
                    keep2 = trim_mask(dd["pnl"].values, k, both=True); parts2.append(dd[keep2])
                r[f"t_trim{k}"] = f(by_year_stats(pd.concat(parts), "pnl")["t"])
                r[f"pnl_trim{k}_bp"] = f(by_year_stats(pd.concat(parts), "pnl")["mean"])
                r[f"t_trim{k}_both"] = f(by_year_stats(pd.concat(parts2), "pnl")["t"])
            r["C1"] = f(np.nanmean([concentration(dd["pnl"].values, 1) for _, dd in d.groupby("sym")]))
            out[f"{g}_{pn}"] = r
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    store = {}; frames = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yr = df["year"].values
        sig = tsmom_pos(c, L_MOM); store[s] = (yr, sig, c, cb)
        frames[s] = pd.DataFrame({"year": yr, "pnl": pnl_bp(sig, c, cb)})
    obs = stats_from(frames)
    null = {k: {"C1": [], "t_full": [], "t_trim1": []} for k in obs}
    for b in range(args.B):
        fr = {}
        for s, (yr, sig, c, cb) in store.items():
            fr[s] = pd.DataFrame({"year": yr, "pnl": pnl_bp(circ_shift(rng, sig, 252), c, cb)})
        st = stats_from(fr)
        for k in obs:
            if k in st:
                for q in ("C1", "t_full", "t_trim1"):
                    null[k][q].append(st[k][q] if st[k][q] is not None else np.nan)
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        r = dict(v)
        for q in ("C1", "t_full", "t_trim1"):
            z, pct = z_of(v[q] if v[q] is not None else np.nan, null[k][q]); r[f"{q}_z"] = f(z); r[f"{q}_null_mean"] = f(np.nanmean(null[k][q])) if null[k][q] else None
        summary[k] = r
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, q: (p.get(q) if p.get(q) is not None else float("nan"))
    if any(not (g(p, "t_full") >= 2) for p in (pre, post)):
        verdict = "未確定: all15 の t_full が 2 未満の期間があり集中を問えない"
    elif all(g(p, "t_trim1") < 2 for p in (pre, post)):
        verdict = "支持: 上位 1% の日を除くと t<2（集中している）"
    elif all(g(p, "t_trim1") >= 2 for p in (pre, post)):
        verdict = "棄却: 上位 1% を除いても t≥2（集中していない）"
    else:
        verdict = "未確定: 前後半で割れる"
    res = {"question": "順張りの純損益は上位 1% の日に集中しているか", "settings": {"L": L_MOM, "k_pct": KS, "B": args.B, "min_shift": 252},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 前後半 × (t_full, t_trim1) の 4 本。k=2・5、両側トリム、群別、C1 の z は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
