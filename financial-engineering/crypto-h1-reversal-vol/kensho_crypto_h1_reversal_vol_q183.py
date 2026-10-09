#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q183: 暗号資産の1時間足の逆張りの見返りは、直前のボラで予測できるか（Farag ほか 2024-1・11通貨）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Farag2024-1_暗号資産の5分足の流動性供給の見返りはボラや暴落リスクで期間外でも予測できた（5分足・高頻度）。
  関連: DellaCorte2015-3（ボラの変化がリバーサルを予測）、FX 改善ログ 2026-10-03（暗号資産の順張りは買い側だけ）。
  → 手元の H1（5分足はない。違いを明記）で、「前の1時間の符号の逆を1時間持つ」の見返りが、直前24時間の実現ボラで予測できるか。

【仮説（測る前に固定）】
H1: 直前24時間の実現ボラが高いほど、1時間逆張りの粗利は大きい（Farag の「ボラで予測できる」と同じ向き）。
H0: 関係は 0 と区別できない。コスト（往復 30bp の仮置き）後に残るかは別に記述。

【データ】暗号資産 H1（Dukascopy）: BTC・ETH・XRP・LTC・ADA・BCH・XLM・EOS・LNK・DOT・SOL のうち存在するもの。2017/2019〜2026-06。
前半 ≤2021／後半 ≥2022。

【定義（1通りに固定）】
- 逆張りの粗利 R_{t+1} = −sign(r_t) × r_{t+1} × 1e4 [bp]（1 時間保有・毎時間往復）。
- ボラ V_t = 直前 24 本の 1 時間リターンの標準偏差（対数）。
- (a) 通貨×月のセルで Spearman(V_t, R_{t+1}) → 月ごとに通貨平均 → 月単位の平均と t（NW 3）。
- (b) 各通貨・各月で V が上位 1/5 の時間だけ逆張り: 粗利 [bp/本] と、往復 5bp・30bp のコスト後。残りの時間との差（月単位 t）。
- 帰無: V_t を通貨×月の中で並べ替え B=300 → (a)(b) の z。

【測るもの】(a) の平均・t・z、(b) の差・t・z、上位 1/5 のコスト後の水準、前後半。

【判定（事前固定・変更禁止）】
前後半とも (a) の Spearman の平均 > 0 かつ z ≥ 2、かつ (b) の差 > 0 で t ≥ 2 →「ボラは逆張りの見返りを予測する（H1 の H1 版）」＝支持。
どちらかで (a) の z < 2 → 棄却。それ以外は未確定。コスト後（30bp）に上位 1/5 が正かは記述（Farag の 5 分足とは頻度が違うので「売買に使える」とは言わない）。

【捨てた案の数】約4: 暴落リスク（歪度）の予測変数（ボラだけに絞る）、5 分足（手元にない）、H4（1 時間の見返りの定義が崩れる）、BTC だけの版。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・(a)(b) の t と z・Farag 2024 の該当表を返す。

【実装】自己完結。実行: python3 kensho_crypto_h1_reversal_vol_q183.py（B=300、数分）／--B 30／--smoke
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
# 往復コスト（価格単位・段階1の保守値。Q136〜Q156 と同じ表）
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}
CRYPTO_COST_RT_REL = 30e-4  # 暗号資産: 往復 30bp の仮置き（Q152 と同じ）
SPLIT_YEAR = 2017
SEED = 20261009
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


def _smoke_ohlc(sym, rng, n, freq, start):
    """合成データ（GBM）。判定には使わない。"""
    rng = rng or np.random.default_rng(SEED)
    t = pd.date_range(start, periods=n, freq=freq)
    r = rng.normal(0.0001, 0.006, n)
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})


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


def donchian_pos(high, low, close, n_in=55, n_out=20):
    """ドンチャン簡略版（両方向）: n_in 本高値更新で買い・安値更新で売り、n_out 本の逆側で手仕舞い。終値で判定。"""
    h = pd.Series(np.asarray(high, float)); l = pd.Series(np.asarray(low, float)); c = np.asarray(close, float)
    hi_in = h.rolling(n_in).max().shift(1).values; lo_in = l.rolling(n_in).min().shift(1).values
    hi_out = h.rolling(n_out).max().shift(1).values; lo_out = l.rolling(n_out).min().shift(1).values
    pos = np.zeros(len(c)); p = 0.0
    for t in range(len(c)):
        if np.isnan(hi_in[t]) or np.isnan(hi_out[t]):
            pos[t] = 0.0; continue
        if p == 1 and c[t] < lo_out[t]:
            p = 0.0
        elif p == -1 and c[t] > hi_out[t]:
            p = 0.0
        if p == 0:
            if c[t] > hi_in[t]:
                p = 1.0
            elif c[t] < lo_in[t]:
                p = -1.0
        pos[t] = p
    return pos


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
    x = np.asarray(pnl, float)
    return float(x.mean() / x.std(ddof=1) * math.sqrt(per_year)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


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


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p); order = np.argsort(p); adj = np.empty(m)
    run = 0.0
    for i, k in enumerate(order):
        run = max(run, (m - i) * p[k]); adj[k] = min(1.0, run)
    return adj


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


QID = "Q183"
DEFAULT_B = 300
VOL_WIN = 24
SPLIT_Y = 2022
COSTS_RT_BP = [5.0, 30.0]


def run(args, rng):
    syms, missing = syms_available(CRYPTO, kind="H1_dukascopy", smoke=args.smoke)
    frames = []
    for s in syms:
        df = load_csv(f"{s}_H1_dukascopy", args.smoke, rng, freq="h", n=50000, start="2019-01-01")
        df = df[df["high"] != df["low"]].reset_index(drop=True)
        c = df["close"].values; r = np.r_[np.nan, c[1:] / c[:-1] - 1]
        V = np.log(pd.Series(r).rolling(VOL_WIN).std().values)
        R = np.r_[-np.sign(np.nan_to_num(r[:-1])) * r[1:] * 1e4, np.nan]  # R[t] = −sign(r_t) r_{t+1}
        d = pd.DataFrame({"sym": s, "ym": df["time"].dt.year.values * 100 + df["time"].dt.month.values, "year": df["time"].dt.year.values, "V": V, "R": R}).dropna()
        frames.append(d)
    cells = pd.concat(frames, ignore_index=True)
    groups_idx = {k: v.index.values for k, v in cells.groupby(["ym", "sym"])}
    Rv = cells["R"].values

    def stats(Vv):
        cs = {}
        for (ym, s), idx in groups_idx.items():
            v = Vv[idx]; R_ = Rv[idx]
            if len(idx) < 100:
                continue
            q = np.nanquantile(v, 0.8); top = v >= q
            cs[(ym, s)] = (spearman(v, R_), R_[top].mean(), R_[~top].mean())
        out = {}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_Y)), ("post", (SPLIT_Y, 9999))):
            by = {}
            for (ym, s), st in cs.items():
                if y0 <= ym // 100 < y1:
                    by.setdefault(ym, []).append(st)
            if len(by) < 6:
                continue
            arr = np.array([np.nanmean(np.array(v, float), axis=0) for v in by.values()])
            out[pn] = {"n_months": int(len(arr)), "rho_mean": float(np.nanmean(arr[:, 0])), "rho_t": nw_t(arr[:, 0], 3), "top_gross": float(np.nanmean(arr[:, 1])),
                       "top_minus_rest": float(np.nanmean(arr[:, 1] - arr[:, 2])), "top_minus_rest_t": nw_t(arr[:, 1] - arr[:, 2], 3)}
        return out
    obs = stats(cells["V"].values)
    null = {k: {"rho": [], "diff": []} for k in obs}
    key = cells["sym"].astype(str).values + cells["ym"].astype(str).values
    for b in range(args.B):
        st = stats(perm_within(rng, cells["V"].values, key))
        for k in obs:
            if k in st:
                null[k]["rho"].append(st[k]["rho_mean"]); null[k]["diff"].append(st[k]["top_minus_rest"])
        if b % 50 == 0:
            print("null", b)
    summary = {}
    for k, v in obs.items():
        summary[k] = {**{kk: f(vv) for kk, vv in v.items()}, "n_months": v["n_months"], "rho_z": f(z_of(v["rho_mean"], null[k]["rho"])[0]), "diff_z": f(z_of(v["top_minus_rest"], null[k]["diff"])[0]),
                      "top_net_after_cost": {str(cst): f(v["top_gross"] - cst) for cst in COSTS_RT_BP}}
    pre, post = summary.get("pre", {}), summary.get("post", {})
    ok = lambda p: (p.get("rho_mean") or 0) > 0 and (p.get("rho_z") or 0) >= 2 and (p.get("top_minus_rest") or 0) > 0 and (p.get("top_minus_rest_t") or 0) >= 2
    if ok(pre) and ok(post):
        verdict = "支持: ボラは逆張りの見返りを予測する"
    elif (pre.get("rho_z") or 0) < 2 or (post.get("rho_z") or 0) < 2:
        verdict = "棄却: 前後半のどちらかで z<2"
    else:
        verdict = "未確定"
    res = {"question": "暗号資産の1時間足の逆張りの見返りは直前のボラで予測できるか", "settings": {"VOL_WIN": VOL_WIN, "split": SPLIT_Y, "costs_rt_bp": COSTS_RT_BP, "B": args.B}, "missing": missing,
           "n_syms": len(syms), "summary": summary, "machine_verdict": verdict, "note": "H1（Farag は 5 分足）。コストは仮置き。", "multiple_comparisons": "判定は前後半の (a) z と (b) t の 4 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
