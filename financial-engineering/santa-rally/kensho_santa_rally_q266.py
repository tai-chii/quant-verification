#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q266: 年末年始効果（12月最終5営業日＋1月最初2営業日）は SPX・NDX（2008〜2026）で残るか（年内ブロック並べ替え）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q266 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- Hirsch（Stock Trader's Almanac・Santa Claus Rally）、知見 Q239（休日前効果）・Q238（ハロウィン）、Wright Research・Benzinga（ブログ）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "Santa Claus rally last five trading days December first two January S&P 500 Nasdaq empirical post-2008 significance"）:
  見つかったもの: Stock Trader's Almanac、Nasdaq.com・Benzinga・Wright Research（ブログ・記事）。
  未確認: 根拠にしない（記事のみ）。2008–2026・前後半・年内ブロック並べ替え帰無での判定は未確認（条件の穴）。

【仮説（測る前に固定）】
H: SPX・NDX の暦年ごとの「12 月最終 5 営業日＋1 月最初 2 営業日」の 7 日間の累積リターンは、同じ年の他の 7 営業日ブロックの平均より高い（D>0）。

【データ】
SPX・NDX D1_long_yahoo（2008〜2026）、US500・USTECH D1_fromH1（2011-09〜）は追試。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
窓: 12 月の最後の 5 営業日と翌年 1 月の最初の 2 営業日。年 y の D_y = 窓の累積 [bp] − その年（7 月〜翌 6 月）の 7 日ブロックの平均累積。

【測るもの】
D の年単位 t（2 指数それぞれ・束）、正の年の割合。前半 2008–2016／後半 2017–。

【帰無】
各年の窓の位置をその年の中でランダムに選ぶ（年内ブロック並べ替え）B=2000 → D の帰無分布 → z。

【判定（事前固定・変更禁止）】
SPX・NDX とも 全期間 D>0 かつ z≥2 かつ 前後半とも D>0 → 支持。全期間 z<1 → 棄却。それ以外 → 未確定（n=18 年で検出力が低いことを書く）。
多重比較: 判定は 2 指数の全期間（2 本）。US500/USTECH CFD の追試は記述。

【捨てた案の数】
約3: 1 月効果（小型株は手元に無い）、12 月全体（ハロウィンと重なる）、窓 10 日。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_santa_rally_q266.py            （B=2000・小（B=2000・30 秒））
      python3 kensho_santa_rally_q266.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q266"
DEFAULT_B = 2000
MAIN = {"SPX": "SPX_D1_long_yahoo", "NDX": "NDX_D1_long_yahoo"}
TRIAL = {"US500": "US500_D1_fromH1", "USTECH": "USTECH_D1_fromH1"}
N_DEC, N_JAN, WIN = 5, 2, 7
Y_MIN = 2008


def load_daily(name, smoke, rng):
    if smoke:
        df = _smoke_ohlc(name, rng, n=5000, freq="B", start="2008-01-01")
    else:
        df = _read(os.path.join(DATA_DIR, f"data_{name}.csv"))
    df = df[df["high"] != df["low"]].reset_index(drop=True)
    df["lr"] = np.log(df["close"]).diff() * 1e4            # 対数リターン [bp]
    df["year"] = df["time"].dt.year; df["month"] = df["time"].dt.month
    return df.dropna(subset=["lr"]).reset_index(drop=True)


def santa_cells(df, rng, B):
    """年 y ごとに 窓（12 月最後 5 営業日＋翌 1 月最初 2 営業日）の累積 − その年（7 月〜翌 6 月）の 7 日ブロックの平均累積。
    帰無: 窓の位置をその年の中で無作為に選ぶ（B 回）。返り値: cells DataFrame, null 行列（年 × B）。"""
    lr = df["lr"].values; yr = df["year"].values; mo = df["month"].values
    rows = []; nulls = []
    for y in range(max(Y_MIN, int(yr.min())), int(yr.max()) + 1):
        dec = np.where((yr == y) & (mo == 12))[0]
        jan = np.where((yr == y + 1) & (mo == 1))[0]
        if len(dec) < N_DEC or len(jan) < N_JAN:
            continue
        w_idx = np.r_[dec[-N_DEC:], jan[:N_JAN]]
        if not (np.diff(w_idx) == 1).all():
            continue
        span = np.where(((yr == y) & (mo >= 7)) | ((yr == y + 1) & (mo <= 6)))[0]
        if len(span) < 10 * WIN:
            continue
        x = lr[span]
        nb = len(x) // WIN
        blocks = x[:nb * WIN].reshape(nb, WIN).sum(1)
        win = lr[w_idx].sum()
        base = blocks.mean()
        rows.append({"year": y, "win_bp": win, "block_mean_bp": base, "D_bp": win - base, "n_blocks": nb, "n_days_span": len(span),
                     "win_start": str(df["time"].iloc[w_idx[0]].date()), "win_end": str(df["time"].iloc[w_idx[-1]].date())})
        # 帰無: 窓の開始位置を span 内で無作為に（7 日が収まる位置）
        starts = rng.integers(0, len(x) - WIN + 1, size=B)
        cs = np.r_[0.0, np.cumsum(x)]
        nulls.append(cs[starts + WIN] - cs[starts] - base)
    cells = pd.DataFrame(rows)
    return cells, (np.array(nulls) if nulls else np.zeros((0, B)))


def summarize(cells, nullm, years_sel=None):
    out = {}
    for p, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
        m = (cells["year"].values >= y0) & (cells["year"].values < y1)
        if m.sum() == 0:
            out[p] = {"n_years": 0, "D_bp": None, "t": None, "z": None, "pct": None, "share_pos": None}
            continue
        d = cells["D_bp"].values[m]
        z, pct = z_of(d.mean(), nullm[m].mean(0)) if nullm.shape[0] else (float("nan"), float("nan"))
        out[p] = {"n_years": int(m.sum()), "D_bp": f(d.mean()), "t": f(tstat(d)), "z": f(z), "pct": f(pct), "share_pos": f((d > 0).mean())}
        if "win_bp" in cells.columns:
            out[p]["win_mean_bp"] = f(cells["win_bp"].values[m].mean()); out[p]["block_mean_bp"] = f(cells["block_mean_bp"].values[m].mean())
    return out


def run(args, rng):
    missing = []; summary = {}; csvs = {}; cells_all = {}; null_all = {}
    for label, name in {**MAIN, **TRIAL}.items():
        if not args.smoke and not os.path.exists(os.path.join(DATA_DIR, f"data_{name}.csv")):
            missing.append(name); continue
        df = load_daily(name, args.smoke, rng)
        cells, nullm = santa_cells(df, rng, args.B)
        if cells.empty:
            missing.append(name); continue
        cells_all[label] = cells; null_all[label] = nullm
        summary[label] = summarize(cells, nullm)
        csvs[f"cells_{label}"] = cells
    # 束（SPX・NDX の年ごとの平均）
    if all(k in cells_all for k in MAIN):
        a = cells_all["SPX"].set_index("year")["D_bp"]; b = cells_all["NDX"].set_index("year")["D_bp"]
        common = a.index.intersection(b.index)
        bund = pd.DataFrame({"year": common, "D_bp": (a[common].values + b[common].values) / 2})
        na = pd.DataFrame(null_all["SPX"], index=cells_all["SPX"]["year"]).loc[common].values
        nb = pd.DataFrame(null_all["NDX"], index=cells_all["NDX"]["year"]).loc[common].values
        summary["bundle_SPX_NDX"] = summarize(bund, (na + nb) / 2)
    g = lambda k, p, c: summary.get(k, {}).get(p, {}).get(c)
    need = [g(k, p, c) for k in MAIN for p in ("all", "pre", "post") for c in ("D_bp",)] + [g(k, "all", "z") for k in MAIN]
    if any(v is None for v in need):
        verdict = "未確定: 計算できない"
    elif all(g(k, "all", "D_bp") > 0 and g(k, "all", "z") >= 2 and g(k, "pre", "D_bp") > 0 and g(k, "post", "D_bp") > 0 for k in MAIN):
        verdict = "支持: SPX・NDX とも 全期間 D>0 かつ z≥2 かつ 前後半とも D>0"
    elif all(g(k, "all", "z") < 1 for k in MAIN):
        verdict = "棄却: 全期間 z<1（SPX・NDX とも）"
    else:
        verdict = "未確定（n≈18 年で検出力が低い）"
    res = {"question": "SPX・NDX の『12 月最終 5 営業日＋1 月最初 2 営業日』の累積リターンは同じ年の他の 7 日ブロックの平均より高いか",
           "settings": {"main": MAIN, "trial": TRIAL, "window": f"12 月最後 {N_DEC} 営業日 + 翌 1 月最初 {N_JAN} 営業日", "year_span": "7 月〜翌 6 月",
                        "blocks": "span を先頭から 7 営業日ずつ非重複に区切った累積の平均", "ret": "対数リターン [bp]", "split_year": SPLIT_YEAR,
                        "year_label": "12 月の年", "B": args.B, "null": "窓の開始位置を span 内で無作為に選ぶ（年内ブロック並べ替え）",
                        "verdict_reject_rule": "棄却は SPX・NDX の両方で全期間 z<1 のとき"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は 2 指数の全期間（2 本）。US500/USTECH CFD の追試・束は記述。"}
    return res, csvs or None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
