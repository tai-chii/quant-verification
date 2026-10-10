#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q204: ATR 倍の損切りは 15 銘柄の日足順張りの純損益と最大下落を改善するか（Kaminski・Lo 2014 の型）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Kaminski & Lo (2014) "When Do Stop-Loss Rules Stop Losses?" J. Financial Markets 18 — 損切りはリターンに正の自己相関（モメンタム）が
  あるときだけ期待値を上げる（§2 命題）。関連知見: Q156（約定の遅れは順張りを下げる）、Q097（順張りの下落の軽さはタイミング）。
  → 本案は「順張りの合図の反転」とは別の出口（トレーリング損切り）を足すと純損益・最大下落がどう動くかを測る。

【仮説（測る前に固定）】
H1: 直近高値（含み益の最大）から k×ATR20 逆行したら手仕舞い、合図が反転するまで再参入しない規則は、合図の反転だけの基準より
    年ごとの純損益（bp/日）を上げる。副次: 最大下落（年ごと）を浅くする。
H0: 差は 0 と区別できない。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 基準: TSMOM L=60（close_t − close_{t−60} の符号。t の終値で決めて t+1 に効く）。毎日判定・保有。
- 損切り: 保有中、建玉の方向での最良終値から k×ATR20（建玉時点の ATR で固定）逆行した終値で手仕舞い（翌日から 0）。
  再参入は合図の符号が反転した日。k=3 を判定用、k=2 は記述。
- 損益: 共通の pnl_bp（往復コスト表・段階 1）。銘柄×年のセルで平均 bp/日と最大下落 → 年ごとに銘柄平均 → 年を単位に対応ありの差と t。
- 帰無: 損切りの発火日を年内で並べ替え（発火した日数を保ちつつ位置をずらす）て「同じ日数だけ休む」規則の損益を B 回 → 観測の差の z。

【測るもの】k=3 の差（純損益・最大下落）の年単位 t と z、前後半・群別、発火率（年あたりの損切り回数）、k=2 の同じ数値。

【判定（事前固定・変更禁止）】
all15 で前後半とも「損切り − 基準」の純損益の年単位 t ≥ 2 かつ z ≥ 2 → H1 支持（損切りは純損益を上げる）。
前後半とも t ≤ −2 → 「損切りは純損益を下げる」で確定（逆向きの確定）。それ以外は未確定（最大下落は記述・判定に使わない）。

【捨てた案の数】約 4: 建玉からの固定幅（ATR でなく pips）、時間損切り（n 日で手仕舞い）、利食い（ターゲット）、損切り後の即時再参入。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・k=3 の差の t と z（前後半）・発火率を返す。

【実装】自己完結。実行: python3 kensho_atr_stop_loss_q204.py（B=300、2 分前後）／--B 30／--smoke
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

QID = "Q204"
DEFAULT_B = 300
L_MOM, ATR_N = 60, 20
KS = [3.0, 2.0]


def stop_rule(sig, close, atr_v, k):
    """sig: 合図（t の終値で決定）。損切り発火で 0、合図反転で復帰。返り値: pos（実際の建玉）と発火フラグ。"""
    n = len(close); pos = np.zeros(n); fired = np.zeros(n, bool)
    p = 0.0; best = np.nan; a0 = np.nan; blocked_dir = 0.0
    for t in range(n):
        s = sig[t]
        if s == 0 or np.isnan(atr_v[t]):
            p = 0.0; blocked_dir = 0.0; pos[t] = 0.0; continue
        if blocked_dir != 0 and s != blocked_dir:
            blocked_dir = 0.0  # 合図が反転 → 再参入を許す
        if p != 0 and s != p:
            p = 0.0  # 合図の反転で手仕舞い
        if p == 0 and blocked_dir == 0:
            p = s; best = close[t]; a0 = atr_v[t]
        elif p != 0:
            best = max(best, close[t]) if p > 0 else min(best, close[t])
            if (best - close[t]) * p >= k * a0:
                fired[t] = True; blocked_dir = p; p = 0.0
        pos[t] = p
    return pos, fired


def apply_pause(sig, pause, close):
    """pause[t]=True の日は（基準の建玉を）翌日から外す簡易規則（帰無用）。"""
    pos = sig.copy(); pos[pause] = 0.0
    return pos


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    rows = []; per_sym = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values
        cb = cost_bp_oneway(s, c); sig = tsmom_pos(c, L_MOM); a = atr(df["high"].values, df["low"].values, c, ATR_N)
        base = pnl_bp(sig, c, cb)
        rec = {"year": df["year"].values, "base": base}
        for k in KS:
            pos, fired = stop_rule(sig, c, a, k)
            rec[f"stop{k:g}"] = pnl_bp(pos, c, cb); rec[f"fired{k:g}"] = fired.astype(float)
        per_sym[s] = (df, sig, cb, c, rec)
        d = pd.DataFrame(rec); d["sym"] = s; rows.append(d)
    cells = pd.concat(rows, ignore_index=True)

    def summarize(cells, cols, with_mdd=True):
        out = {}
        sy_all = cells.groupby(["year", "sym"]).agg({c: "mean" for c in cols})
        if with_mdd:
            mdd = cells.groupby(["year", "sym"]).agg({c: (lambda x: max_drawdown(x.values)) for c in cols})
            mdd.columns = [f"mdd_{c}" for c in cols]
            sy_all = pd.concat([sy_all, mdd], axis=1)
        sy_all = sy_all.reset_index()
        for g, members in GROUPS.items():
            cg = sy_all[sy_all["sym"].isin(members)]
            for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
                d = cg[(cg["year"] >= y0) & (cg["year"] < y1)]
                if d.empty:
                    continue
                yr = d.drop(columns="sym").groupby("year").mean()
                r = {"n_years": int(len(yr))}
                for c in cols:
                    r[f"{c}_bp"] = float(yr[c].mean())
                    if with_mdd:
                        r[f"mdd_{c}"] = float(yr[f"mdd_{c}"].mean())
                    if c != "base":
                        diff = yr[c] - yr["base"]; r[f"diff_{c}_bp"] = float(diff.mean()); r[f"diff_{c}_t"] = tstat(diff.values)
                        if with_mdd:
                            dm = yr[f"mdd_{c}"] - yr["mdd_base"]; r[f"mdd_diff_{c}"] = float(dm.mean()); r[f"mdd_diff_{c}_t"] = tstat(dm.values)
                out[f"{g}_{pn}"] = r
        return out
    cols = ["base"] + [f"stop{k:g}" for k in KS]
    obs = summarize(cells, cols)
    fire_rate = {f"k{k:g}": float(cells.groupby(["sym", "year"])[f"fired{k:g}"].sum().mean()) for k in KS}

    # 帰無: 発火日を年内で並べ替えた「同じ日数だけ休む」規則
    null = {key: [] for key in obs}
    for b in range(args.B):
        rows_b = []
        for s, (df, sig, cb, c, rec) in per_sym.items():
            fired = rec["fired3"].astype(bool)
            pf = perm_within(rng, fired.astype(float), rec["year"]).astype(bool)
            # 休む期間: 発火日から合図が反転するまで（観測と同じ長さの構造を近似: 発火日から次の合図反転まで 0）
            pause = np.zeros(len(sig), bool); on = False; d0 = 0.0
            for t in range(len(sig)):
                if pf[t] and sig[t] != 0:
                    on = True; d0 = sig[t]
                if on and (sig[t] != d0):
                    on = False
                pause[t] = on
            rows_b.append(pd.DataFrame({"year": rec["year"], "sym": s, "base": rec["base"], "stop3": pnl_bp(apply_pause(sig, pause, c), c, cb)}))
        st = summarize(pd.concat(rows_b, ignore_index=True), ["base", "stop3"], with_mdd=False)
        for key in obs:
            if key in st:
                null[key].append(st[key]["diff_stop3_bp"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for key, v in obs.items():
        z, _ = z_of(v["diff_stop3_bp"], null[key])
        summary[key] = {kk: (f(vv) if isinstance(vv, float) else vv) for kk, vv in v.items()}; summary[key]["diff_stop3_z"] = f(z)
    pre, post = summary.get("all15_pre", {}), summary.get("all15_post", {})
    g = lambda p, k: (p.get(k) or 0)
    if g(pre, "diff_stop3_t") >= 2 and g(pre, "diff_stop3_z") >= 2 and g(post, "diff_stop3_t") >= 2 and g(post, "diff_stop3_z") >= 2:
        verdict = "支持: ATR 損切りは順張りの純損益を上げる"
    elif g(pre, "diff_stop3_t") <= -2 and g(post, "diff_stop3_t") <= -2:
        verdict = "逆向きで確定: ATR 損切りは順張りの純損益を下げる"
    else:
        verdict = "未確定"
    res = {"question": "ATR 倍の損切りは日足順張りの純損益と最大下落を改善するか", "settings": {"L": L_MOM, "ATR_N": ATR_N, "k": KS, "B": args.B}, "missing": missing,
           "fire_per_sym_year": fire_rate, "summary": summary, "machine_verdict": verdict,
           "multiple_comparisons": "判定は all15 前後半の k=3 の差の t と z の 4 本。k=2・群別・最大下落は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
