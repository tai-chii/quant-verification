#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q206: 曜日効果は 15 銘柄の日足で 2017 年以降も残るか（曜日ラベル並べ替え・Holm）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第3弾（Fable 2026-10-10）。アイデア候補.md の該当行。
- 元の主張: Cross (1973)・French (1980) "Stock returns and the weekend effect" JFE 8 — 月曜の平均リターンが負（表 1）。為替では
  Yamori & Kurihara (2004) Applied Financial Economics Letters 1 — 1980 年代の曜日効果は 1990 年代に消えた。関連知見: Q181（月替わり効果は 2017 年
  以降有意でない）、Q153（15 分足の時刻の自己相関は多重比較で残らない）。
  → 本案は「公表後の消え方」の系列として、曜日ラベルの並べ替え帰無と Holm 補正で 15 銘柄×前後半を一括で測る。

【仮説（測る前に固定）】
H1: 15 銘柄の束で、ある曜日（月〜金のどれか）の平均リターンが他の曜日と Holm 補正後 p<0.05 で異なり、前後半で同じ符号。
H0: どの曜日も帰無（曜日ラベルを年内で並べ替え）と区別できない。

【データ】15 銘柄 D1_fromH1（2008-02〜2026-07）。曜日は UTC 日付。前半 <2017／後半 ≥2017。

【定義（1 通りに固定）】
- 統計量: 曜日 d の平均リターン（bp）− 他 4 曜日の平均リターン、銘柄×年のセルで計算 → 年ごとに銘柄平均 → 年平均。群別（all15・fx8・trend7）。
- 帰無: 曜日ラベルを銘柄×年の中で並べ替え B 回 → 両側 p（|帰無| ≥ |観測| の割合）→ 群×期間ごとに 5 曜日で Holm。
- 売買可能性（記述）: 「負の曜日を売り・正の曜日を買い」を前半で決めて後半に当てる純損益（往復コスト 1 回/日）。

【測るもの】5 曜日 × 3 群 × 前後半の差と Holm 補正後 p、前半で決めた規則の後半の純損益 t。

【判定（事前固定・変更禁止）】
all15 で、前後半とも Holm 補正後 p<0.05 で同じ符号の曜日が 1 つ以上ある → H1 支持（曜日効果が残る）。
どちらかの期間で Holm 補正後に有意な曜日が 0 → 棄却。群別は記述。

【捨てた案の数】約 3: 祝日前後（米祝日の暦が要る）、曜日×時間帯（H1 への拡張）、ボラの曜日差（別問題）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・Holm 後に有意な曜日の数（前後半）・French 1980 表 1 の月曜の値を返す。

【実装】自己完結。実行: python3 kensho_day_of_week_q206.py（B=500、1 分以内）／--B 50／--smoke
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

QID = "Q206"
DEFAULT_B = 500
DOWS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def dow_stats(cells, dow_col="dow"):
    """銘柄×年×曜日の平均 → 年ごとに銘柄平均 → 群×期間ごとに (曜日 − 他曜日) の年平均。"""
    m = cells.groupby(["sym", "year", dow_col])["ret_bp"].mean().unstack(dow_col)
    m = m.reindex(columns=range(5))
    out = {}
    for g, members in GROUPS.items():
        mg = m[m.index.get_level_values(0).isin(members)]
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            yrs = mg.index.get_level_values(1)
            d = mg[(yrs >= y0) & (yrs < y1)]
            if d.empty:
                continue
            yr = d.groupby(level=1).mean()  # 年 × 曜日
            diffs = []
            for k in range(5):
                others = yr.drop(columns=k).mean(axis=1)
                diffs.append(float((yr[k] - others).mean()))
            out[f"{g}_{pn}"] = diffs
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    frames = []
    for s in syms:
        df = load_d1(s, args.smoke, rng)
        d = pd.DataFrame({"sym": s, "year": df["year"].values, "dow": df["time"].dt.dayofweek.values, "ret_bp": df["ret"].values * 1e4}).dropna()
        frames.append(d[d["dow"] <= 4])
    cells = pd.concat(frames, ignore_index=True)
    obs = dow_stats(cells)
    null = {k: [] for k in obs}
    key = cells["sym"].astype(str).values + cells["year"].astype(str).values
    for b in range(args.B):
        cells["dow_p"] = perm_within(rng, cells["dow"].values.astype(float), key).astype(int)
        st = dow_stats(cells, "dow_p")
        for k in obs:
            if k in st:
                null[k].append(st[k])
        if b % 100 == 0:
            print("null", b)
    summary = {}
    for k, diffs in obs.items():
        nl = np.array(null[k]); p = [(float((np.abs(nl[:, i]) >= abs(diffs[i])).mean()) if len(nl) else float("nan")) for i in range(5)]
        ph = holm(p) if len(nl) else [None] * 5
        summary[k] = {DOWS[i]: {"diff_bp": f(diffs[i]), "p": f(p[i]), "p_holm": f(ph[i]), "z": f(z_of(diffs[i], nl[:, i])[0] if len(nl) else float("nan"))} for i in range(5)}
    # 記述: 前半で決めた規則を後半に当てる
    pre = summary.get("all15_pre", {})
    rule = {i: np.sign(pre[DOWS[i]]["diff_bp"] or 0) for i in range(5)}
    post = cells[cells["year"] >= SPLIT_YEAR].copy()
    post["pos"] = post["dow"].map(rule)
    # 毎日往復（曜日ごとの符号が切り替わる日にコスト）: 近似として 1 日 1 往復を仮定
    costs = {s: COST_RT[s] / np.nanmean(load_d1(s, args.smoke, rng)["close"].values) * 1e4 for s in syms}
    post["net"] = post["pos"] * post["ret_bp"] - post["sym"].map(costs)
    yr = post.groupby("year")["net"].mean()
    rule_post = {"rule_signs": {DOWS[i]: int(rule[i]) for i in range(5)}, "post_net_bp_per_day": f(yr.mean()), "post_t": f(tstat(yr.values)), "n_years": int(len(yr))}
    sig_pre = {d for d, v in summary.get("all15_pre", {}).items() if (v["p_holm"] or 1) < 0.05}
    sig_post = {d for d, v in summary.get("all15_post", {}).items() if (v["p_holm"] or 1) < 0.05}
    same = [d for d in sig_pre & sig_post if np.sign(summary["all15_pre"][d]["diff_bp"] or 0) == np.sign(summary["all15_post"][d]["diff_bp"] or 0)]
    if same:
        verdict = f"支持: 前後半とも Holm 後に有意で同符号の曜日あり {same}"
    else:
        verdict = f"棄却: Holm 後に前後半で同符号・有意な曜日なし（前半 {sorted(sig_pre)}・後半 {sorted(sig_post)}）"
    res = {"question": "曜日効果は 15 銘柄の日足で 2017 年以降も残るか", "settings": {"B": args.B}, "missing": missing, "summary": summary,
           "rule_from_pre_applied_to_post": rule_post, "machine_verdict": verdict,
           "multiple_comparisons": "群×期間ごとに 5 曜日で Holm。判定は all15 の前後半のみ。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
