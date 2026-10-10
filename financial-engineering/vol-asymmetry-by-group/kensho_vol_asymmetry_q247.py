#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q247: ボラの非対称性の向きは群で違うか（株価指数は負・金は正・FX は無し。HAR に符号項・15 銘柄）
================================================================================

【出典】
- 計画（事前登録）: アイデア候補.md の Q247 の行（Fable 2026-10-10・20案一括生成 第4弾）。
- Black (1976) レバレッジ効果、Nelson (1991) EGARCH、Corsi (2009) HAR、Baur (2012) "Asymmetric volatility in the gold market"
  （金は正のリターンの後にボラが上がる「逆の非対称」）。Griffith の再検討 "The asymmetric volatility in the gold market revisited"。本文未読・要旨。
- 知見 Q222（Parkinson 入力の HAR）、知見 Q187（為替のボラ予測は損失関数よりモデルの差）。
- 先行研究チェック（WebSearch 2026-10-10・検索語 "bid-ask spread changes predict next hour realized volatility HAR model gold" の結果に Griffith の金の非対称の
  再検討を確認。追加検索なし）: 株式・金は個別に多数。15 銘柄を同じ HAR＋符号項・年内並べ替え帰無・前後半で並べて群の違いを事前固定で判定する形は未確認。
  追試＋条件の穴（FX・BTC・原油を同じ土俵に）。

【仮説（測る前に固定）】
H: 翌日の対数 Parkinson 分散を HAR（1・5・22 日）で説明したうえで、当日のリターンが負のダミー 1[r_t<0] の係数 γ は、
   株価指数（US500・USTECH）で正（負の日の後にボラ上昇）、金（XAUUSD）で負（逆の非対称）、FX8 では 0 と区別できない。

【データ】15 銘柄の UTC 日足（D1_fromH1、高値・安値あり、2008〜2026-06）。

【定義（1通りに固定）】
- v_t = ln(H_t/L_t)² / (4 ln 2)、y_{t+1} = ln v_{t+1}。説明変数: ln v_t、直前 5 日平均、直前 22 日平均、D_t = 1[r_t < 0]。OLS。
- γ の推定と Newey-West（5 ラグ）の t。期間: 前半（<2017）／後半（≥2017）／全期間で別々に推定。

【測るもの】銘柄ごとの γ・t・z。群の要約: 指数 2・金 1・FX8・その他（XAG・WTI・UKOIL・BTC は記述）。

【帰無】D_t を年内で並べ替え（符号の割合は保つ・ボラとの対応を壊す）B=500 → γ の帰無分布 → z。

【判定（事前固定・変更禁止）】前半・後半の両方で:
- US500・USTECH の γ > 0 かつ z ≥ 2（2 銘柄とも）、かつ XAUUSD の γ < 0 かつ z ≤ −2、かつ FX8 の 6 銘柄以上で |z| < 2 → 支持。
- XAUUSD の γ > 0 かつ z ≥ 2（指数と同じ向き）→ 「金の逆の非対称」を棄却（他は記述）。
- それ以外 → 未確定（どの部分が通らなかったかを書く）。
多重比較: 15 銘柄 × 2 期間 = 30 本（判定に使うのは 11 銘柄 × 2 期間）。

【捨てた案の数】約4: EGARCH（HAR に統一）、符号ではなく r_t の水準（符号項に統一）、H1 版、2 日後まで。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。データは 2026-06 まで。

【委託の確かめ方】設計・コードは Fable（2026-10-10）。実行と解釈は Sonnet／Opus が後で行い、JSON のパス・銘柄別の γ と z（前後半）を返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas。
実行: python3 kensho_vol_asymmetry_q247.py            （B=500・1 分前後）
      python3 kensho_vol_asymmetry_q247.py --smoke
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

QID = "Q247"
DEFAULT_B = 500
INDICES = ["US500", "USTECH"]
GOLD = "XAUUSD"


def design(df):
    v = np.log(df["high"].values / df["low"].values) ** 2 / (4 * math.log(2)); lv = np.log(v + 1e-12)
    s = pd.Series(lv); X = pd.DataFrame({"lv1": s, "lv5": s.rolling(5).mean(), "lv22": s.rolling(22).mean(), "D": (df["ret"].values < 0).astype(float)})
    X["y"] = s.shift(-1); X["year"] = df["year"].values
    return X.dropna().reset_index(drop=True)


def gamma_of(X, Dcol="D"):
    A = np.c_[np.ones(len(X)), X[["lv1", "lv5", "lv22"]].values, X[Dcol].values]; y = X["y"].values
    beta, *_ = np.linalg.lstsq(A, y, rcond=None); resid = y - A @ beta
    # Newey-West の t（係数 γ）
    n = len(y); XtX_inv = np.linalg.pinv(A.T @ A); u = A * resid[:, None]; lag = 5
    S = u.T @ u
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1); G = u[k:].T @ u[:-k]; S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    g = float(beta[-1]); se = float(np.sqrt(max(V[-1, -1], 1e-300)))
    return g, g / se


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    per = {}
    for s in syms:
        X = design(load_d1(s, args.smoke, rng)); per[s] = {}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            d = X[(X["year"] >= y0) & (X["year"] < y1)]
            if len(d) < 300:
                continue
            g, t = gamma_of(d); null = []
            for b in range(args.B):
                d2 = d.copy(); d2["D"] = perm_within(rng, d2["D"].values, d2["year"].values); null.append(gamma_of(d2)[0])
            z, _ = z_of(g, null)
            per[s][pn] = {"n": int(len(d)), "gamma": f(g), "t_nw": f(t), "z": f(z)}
        print("done", s)
    def ok(s, pn, cond):
        v = per.get(s, {}).get(pn)
        return v is not None and v["z"] is not None and cond(v["gamma"], v["z"])
    checks = {}
    for pn in ("pre", "post"):
        idx_ok = all(ok(s, pn, lambda g, z: g > 0 and z >= 2) for s in INDICES)
        gold_ok = ok(GOLD, pn, lambda g, z: g < 0 and z <= -2)
        fx_null = sum(1 for s in FX8 if ok(s, pn, lambda g, z: abs(z) < 2))
        gold_same_as_idx = ok(GOLD, pn, lambda g, z: g > 0 and z >= 2)
        checks[pn] = {"indices_positive": idx_ok, "gold_negative": gold_ok, "fx_null_count": fx_null, "gold_positive_like_indices": gold_same_as_idx}
    if all(checks[pn]["indices_positive"] and checks[pn]["gold_negative"] and checks[pn]["fx_null_count"] >= 6 for pn in ("pre", "post")):
        verdict = "支持: 指数は負の非対称・金は逆・FX は無し"
    elif all(checks[pn]["gold_positive_like_indices"] for pn in ("pre", "post")):
        verdict = "金の逆の非対称を棄却: 金も指数と同じ向き"
    else:
        verdict = "未確定: " + "; ".join(f"{pn}: 指数 {c['indices_positive']}・金 {c['gold_negative']}・FX 無し {c['fx_null_count']}/8" for pn, c in checks.items())
    res = {"question": "ボラの非対称性の向きは群で違うか", "settings": {"B": args.B}, "missing": missing, "per_sym": per, "checks": checks, "machine_verdict": verdict,
           "multiple_comparisons": "15 銘柄 × 2 期間 = 30 本（判定は 11 銘柄 × 2 期間）。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
