#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q250: ヒステリシス帯（±θσ の不感帯）は順張りの合図反転を減らし純損益を上げるか（15銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q250 の行（Fable 2026-10-10・30案一括生成 第5弾）。
- 知見 Q221（k 日連続同符号の確認フィルタは取引回数を増やした）、Q136、Q204（ATR 損切り）、制御工学のヒステリシス（デッドバンド）
- 先行研究チェック（WebSearch 2026-10-10・standard・検索語 "trend following hysteresis band dead zone signal threshold reduce turnover whipsaw empirical"）:
  見つかったもの: TradingView／LuxAlgo のデッドバンド指標（ブログ・スクリプト）のみ。
  未確認: 根拠にしない。15 銘柄・コスト後・凍結日並べ替え帰無で測る形は未確認（条件の穴）。

【仮説（測る前に固定）】
H: 合図 m=ln(C_t/C_{t−60}) が ±θ·σ60·√60（θ=0.25）の帯の中にあるときは前日の建玉を維持する（帯を抜けたときだけ反転）と、生の sign(m) より取引回数が減り、純損益 [bp/日] が上がる。

【データ】
15銘柄 D1_fromH1（2008〜2026-06）。
（`検証/学問/金融工学/作業/FX/システムトレード/data_*.csv`。無い銘柄は除いて JSON の missing に書く。ネットは使わない）

【定義（1通りに固定）】
A: 生の TSMOM60（sign）。B: ヒステリシス θ=0.25（主セル）。θ=0.5 と 1.0 は副次（記述）。最初の建玉は sign。pnl_bp で翌日約定・片道コスト。

【測るもの】
年×銘柄の純損益差 B−A [bp/日]（年単位 t・all15/fx8/trend7）、取引回数の比、最大下落の差。前後半。

【帰無】
θ のヒステリシスを「ランダムな日に同じ回数だけ建玉を凍結する」帰無（凍結日の暦月ブロックを年内で並べ替え）B=300 → 差の帰無分布 → z。

【判定（事前固定・変更禁止）】
all15 前後半とも B−A>0 かつ t≥2 かつ z≥2 → 支持。前後半とも t≤−2 → 逆向きで確定（帯は害）。それ以外 → 棄却（差は見えない）。
多重比較: 判定は all15 の主セル θ=0.25 の前後半 2 本。θ=0.5・1.0 と群別は記述。

【捨てた案の数】
約3: θ を年ごとに選ぶ（選択の楽観が入る）、ATR 単位の帯（σ60 に統一）、帯の中で建玉を半分にする案。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-06（暗号資産は 2026-09）まで。規則は固定で相場観は使わない。
外部の暦（発表日など）を手で書いた箇所は「知識から記載・実行者が原典と照合」。

【委託の確かめ方】
設計は Fable（2026-10-10）、コードは Claude（Fable 5.1 の委託）。実行と解釈は Sonnet／Opus が後で行い、結論でなく JSON のパス・主要な統計量（t・z・前後半）・原典の箇所を返す。
machine_verdict は上の判定規則を機械的に当てたもので、確定／ノイズ／未確定の解釈は実行者が書く。

【実装】自己完結・決定的（乱数は帰無の並べ替えのみ seed 固定）。依存: python3 + numpy/pandas。
実行: python3 kensho_hysteresis_band_q250.py            （B=300・小（B=300・1〜2 分））
      python3 kensho_hysteresis_band_q250.py --smoke    （合成データで経路の確認。判定には使わない）
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

QID = "Q250"
DEFAULT_B = 300
L = 60
THETA_MAIN = 0.25
THETAS = (0.25, 0.5, 1.0)
PERIODS = (("all", 0, 9999), ("pre", 0, SPLIT_YEAR), ("post", SPLIT_YEAR, 9999))


def _hyst_pos(m, band):
    """帯の外では sign(m)、帯の中では前日の建玉を維持。最初の建玉は sign(m)。"""
    n = len(m)
    valid = np.isfinite(m) & np.isfinite(band)
    p = np.full(n, np.nan)
    out = valid & (np.abs(m) > band)
    p[out] = np.sign(m[out])
    i0 = np.where(valid)[0]
    if len(i0):
        i0 = i0[0]
        if not np.isfinite(p[i0]):
            p[i0] = np.sign(m[i0])
    p = pd.Series(p).ffill().to_numpy(copy=True)
    p[~np.isfinite(p)] = 0.0
    return p


def _pos_from_freeze(sign_m, freeze, valid):
    """凍結日は前日の建玉を維持、それ以外は sign(m)。"""
    p = np.where(valid & ~freeze, sign_m, np.nan)
    i0 = np.where(valid)[0]
    if len(i0) and not np.isfinite(p[i0[0]]):
        p[i0[0]] = sign_m[i0[0]]
    p = pd.Series(p).ffill().to_numpy(copy=True)
    p[~np.isfinite(p)] = 0.0
    return p


def _perm_month_blocks_within_year(rng, x, year, month):
    """暦月ブロックを年内で並べ替える（ブロック内の順序は保つ）。"""
    out = x.copy()
    ym = year * 100 + month
    for y in np.unique(year):
        idx = np.where(year == y)[0]
        blocks = [idx[ym[idx] == v] for v in np.unique(ym[idx])]
        order = rng.permutation(len(blocks))
        src = np.concatenate([blocks[o] for o in order])
        # 並べ替えたブロックを同じ位置に順に流し込む（長さの差は切り詰め／はみ出し分は末尾まで）
        vals = x[src]
        out[idx] = vals[:len(idx)] if len(vals) >= len(idx) else np.r_[vals, x[idx][len(vals):]]
    return out


def _year_cell_stats(year, sym_id, vals, nsym, y0, y1):
    """日次の値 → 年×銘柄平均 → 年内で銘柄平均 → 年平均。"""
    m = (year >= y0) & (year < y1) & np.isfinite(vals)
    if not m.any():
        return float("nan")
    key = year[m] * nsym + sym_id[m]
    s = np.bincount(key, weights=vals[m]); c = np.bincount(key)
    ok = c > 0
    cy = np.arange(len(c))[ok] // nsym; cv = s[ok] / c[ok]
    s2 = np.bincount(cy, weights=cv); c2 = np.bincount(cy); ok2 = c2 > 0
    return float((s2[ok2] / c2[ok2]).mean())


def run(args, rng):
    ok, missing = syms_available(SYMS, smoke=args.smoke)
    per = {}
    for s in ok:
        df = load_d1(s, args.smoke, rng)
        c = df["close"].values.astype(float)
        lr = np.r_[np.nan, np.diff(np.log(c))]
        sig60 = pd.Series(lr).rolling(L).std(ddof=1).values
        m = np.full(len(c), np.nan); m[L:] = np.log(c[L:] / c[:-L])
        valid = np.isfinite(m) & np.isfinite(sig60)
        cost = cost_bp_oneway(s, c)
        posA = tsmom_pos(c, L); pnlA = pnl_bp(posA, c, cost)
        d = {"year": df["year"].values, "month": df["time"].dt.month.values, "close": c, "cost": cost, "m": m,
             "sign_m": np.where(valid, np.sign(m), 0.0), "valid": valid, "posA": posA, "pnlA": pnlA, "pnlB": {}, "posB": {}}
        for th in THETAS:
            band = th * sig60 * math.sqrt(L)
            pB = _hyst_pos(m, band)
            d["posB"][th] = pB; d["pnlB"][th] = pnl_bp(pB, c, cost)
        per[s] = d
    syms = list(per); nsym = len(syms)
    # 年×銘柄のセル
    cells = []
    for i, s in enumerate(syms):
        d = per[s]
        fr = pd.DataFrame({"year": d["year"], "pnlA": d["pnlA"], "posA": d["posA"]})
        for th in THETAS:
            fr[f"pnlB_{th}"] = d["pnlB"][th]; fr[f"posB_{th}"] = d["posB"][th]
        for y, g in fr.groupby("year"):
            row = {"year": int(y), "sym": s, "n": int(len(g)), "pnlA": g["pnlA"].mean(), "tradesA": int((np.abs(np.diff(g["posA"].values)) > 0).sum()),
                   "mddA": max_drawdown(g["pnlA"].values)}
            for th in THETAS:
                row[f"diff_{th}"] = g[f"pnlB_{th}"].mean() - g["pnlA"].mean()
                row[f"tradesB_{th}"] = int((np.abs(np.diff(g[f"posB_{th}"].values)) > 0).sum())
                row[f"mdd_diff_{th}"] = max_drawdown(g[f"pnlB_{th}"].values) - row["mddA"]
            cells.append(row)
    celldf = pd.DataFrame(cells)
    # 帰無（主セル θ=0.25）: 凍結日の暦月ブロックを年内で並べ替え
    year_all = np.concatenate([per[s]["year"] for s in syms]); sym_all = np.concatenate([np.full(len(per[s]["year"]), i) for i, s in enumerate(syms)])
    obs = {pn: _year_cell_stats(year_all, sym_all, np.concatenate([per[s]["pnlB"][THETA_MAIN] - per[s]["pnlA"] for s in syms]), nsym, y0, y1) for pn, y0, y1 in PERIODS}
    null = {pn: [] for pn, _, _ in PERIODS}
    for b in range(args.B):
        diffs = []
        for s in syms:
            d = per[s]
            freeze = (d["posB"][THETA_MAIN] != d["sign_m"]) & d["valid"]  # θ 帯の中で前日を維持した日
            freeze = np.where(d["valid"], freeze, False)
            fz = _perm_month_blocks_within_year(rng, freeze.astype(float), d["year"], d["month"]) > 0.5
            pN = _pos_from_freeze(d["sign_m"], fz, d["valid"])
            diffs.append(pnl_bp(pN, d["close"], d["cost"]) - d["pnlA"])
        diffs = np.concatenate(diffs)
        for pn, y0, y1 in PERIODS:
            null[pn].append(_year_cell_stats(year_all, sym_all, diffs, nsym, y0, y1))
    summary = {}
    for th in THETAS:
        summary[f"theta_{th}"] = {}
        for g, gs in GROUPS.items():
            gd = celldf[celldf["sym"].isin(gs)]
            summary[f"theta_{th}"][g] = {}
            for pn, y0, y1 in PERIODS:
                st = by_year_stats(gd, f"diff_{th}", y0=y0, y1=y1)
                sub = gd[(gd["year"] >= y0) & (gd["year"] < y1)]
                ent = {"n_years": st["n_years"], "B_minus_A_bp": f(st["mean"]), "t": f(st["t"]),
                       "trade_ratio_B_over_A": f(sub[f"tradesB_{th}"].sum() / max(sub["tradesA"].sum(), 1)),
                       "mdd_diff_bp_mean": f(sub[f"mdd_diff_{th}"].mean())}
                if th == THETA_MAIN and g == "all15":
                    z, pct = z_of(obs[pn], null[pn]); ent.update({"z": f(z), "pct": f(pct)})
                summary[f"theta_{th}"][g][pn] = ent
    a = summary[f"theta_{THETA_MAIN}"]["all15"]
    if any(a[pn][k] is None for pn in ("pre", "post") for k in ("t", "z", "B_minus_A_bp")):
        verdict = "未確定: 計算できない"
    elif all(a[pn]["B_minus_A_bp"] > 0 and a[pn]["t"] >= 2 and a[pn]["z"] >= 2 for pn in ("pre", "post")):
        verdict = "支持: ヒステリシス帯（θ=0.25）は純損益を上げる（前後半とも B−A>0・t≥2・z≥2）"
    elif all(a[pn]["t"] <= -2 for pn in ("pre", "post")):
        verdict = "逆向きで確定: 帯は害（前後半とも t≤−2）"
    else:
        verdict = "棄却: 差は見えない"
    res = {"question": "ヒステリシス帯（±θσ60√60 の不感帯・θ=0.25）は TSMOM60 の合図反転を減らし純損益を上げるか",
           "settings": {"L": L, "theta_main": THETA_MAIN, "thetas": list(THETAS), "split_year": SPLIT_YEAR, "B": args.B,
                        "null": "凍結日（帯の中で前日を維持した日）の暦月ブロックを年内で並べ替え、同じ凍結日数で建玉を再構成",
                        "stat_for_z": "日次差 B−A を年×銘柄平均→年内銘柄平均→年平均"},
           "missing": missing, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 の主セル θ=0.25 の前後半 2 本。θ=0.5・1.0 と群別は記述。"}
    return res, {"cells": celldf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
