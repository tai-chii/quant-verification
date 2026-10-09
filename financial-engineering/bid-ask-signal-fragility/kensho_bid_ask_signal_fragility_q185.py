#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q185: 合図は bid か ask かで何割変わるか（XAUUSD の実測 bid/ask ＋ 15銘柄の半スプレッドの擬似ずらし・ブログZenn2026d-2）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: ブログZenn2026d-2_実弾とバックテストのエントリー日が一致しなかった、Park2007-5_ビッド・アスクと非同期取引の影響は未解決。
  知見 Q137（Yahoo と Dukascopy で順張りの合図は 5〜6% の日で食い違う）。
  → データ源の違い（Q137）の次は、同じデータ源の中の bid／ask／mid の違い。合図の定義に価格の種類が入っているかを測る。

【仮説（測る前に固定）】
H1: スプレッドが価格に比べて小さい（XAUUSD で数 bp）ので、合図の不一致率は 1% 未満で、Q137 のデータ源の差（5〜6%）より一桁小さい。
対立: 不一致率が 5% 以上（データ源の差と同程度）→ 合図の定義に bid/ask の指定を入れる必要がある。

【データ】XAUUSD: `data_XAUUSD_D1_dukascopy.csv`（bid）と `data_XAUUSD_D1_dukascopy_ask.csv`（ask）、H1 も同様（2008〜）。
15銘柄 D1_fromH1（bid）: 半スプレッド（段階1の COST_RT/2）を加えた擬似 ask を作る。

【定義（1通りに固定）】
- 合図 3 本（固定）: SMA200 の上下、TSMOM20 の符号、ドンチャン簡略版 55/20 の状態。
- 系列: bid・ask・mid（=(bid+ask)/2）。不一致率 = 同じ日に合図の符号が違う日の割合（bid vs ask、bid vs mid）。
- 純損益の差: 各系列で同じ規則を走らせた日次純損益（片道コスト段階1）の差の平均 [bp/日] と年単位の t。
- 参考（Q137 と同じ）: 1 日ずらした自分自身との不一致率。
- 擬似ずらし（15銘柄）: ask' = bid + COST_RT/2。不一致率と純損益の差。
- 帰無: 不要（記述の問い）。多重比較: 不一致率は規則 3 × 系列の組 2。

【測るもの】XAUUSD の D1・H1 の不一致率（規則別）、純損益の差と t、15銘柄の擬似ずらしの不一致率。

【判定（事前固定・変更禁止）】
XAUUSD D1 で 3 規則すべて bid vs ask の不一致率 < 1% かつ純損益の年差 |t| < 2 →「合図は bid/ask に頑健」＝H1 支持。
いずれかの規則で不一致率 ≥ 5% →「合図の定義に価格の種類が入る（対立）」。その間は未確定。H1 の不一致率と擬似ずらしは記述。

【捨てた案の数】約3: H1 で判定する案（D1 に固定・H1 は記述）、規則を 10 本に増やす案、mid ではなく last（約定値）を使う案（データなし）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・不一致率・ブログの該当箇所を返す。

【実装】自己完結。実行: python3 kensho_bid_ask_signal_fragility_q185.py（帰無なし・数十秒）／--smoke
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


QID = "Q185"
DEFAULT_B = 0


def _signals(df):
    c, h, l = df["close"].values, df["high"].values, df["low"].values
    return {"SMA200": sma_pos(c, 200), "TSMOM20": tsmom_pos(c, 20), "DONCH55_20": donchian_pos(h, l, c, 55, 20)}


def _compare(dfa, dfb, sym, label_a, label_b):
    m = pd.merge(dfa, dfb, on="time", suffixes=("_a", "_b"))
    A = _signals(m.rename(columns={"close_a": "close", "high_a": "high", "low_a": "low"})); B_ = _signals(m.rename(columns={"close_b": "close", "high_b": "high", "low_b": "low"}))
    out = {}
    yrs = m["time"].dt.year.values
    for k in A:
        valid = (A[k] != 0) | (B_[k] != 0)
        dis = float((A[k][valid] != B_[k][valid]).mean()) if valid.sum() else np.nan
        pa = pnl_bp(A[k], m["close_a"].values, cost_bp_oneway(sym, m["close_a"].values)); pb = pnl_bp(B_[k], m["close_b"].values, cost_bp_oneway(sym, m["close_b"].values))
        by = pd.DataFrame({"year": yrs, "d": pa - pb}).groupby("year")["d"].mean()
        # 1 日ずらした自分自身
        sh = np.r_[0.0, A[k][:-1]]; dis_shift = float((A[k][valid] != sh[valid]).mean()) if valid.sum() else np.nan
        out[k] = {"disagree_rate": f(dis), "disagree_rate_1day_shift_self": f(dis_shift), "pnl_diff_mean_bp": f((pa - pb).mean()), "pnl_diff_t_year": f(tstat(by.values)), "n": int(len(m))}
    out["_pair"] = f"{label_a} vs {label_b}"
    return out


def run(args, rng):
    res = {"xauusd": {}, "pseudo_15": {}}; missing = []
    # XAUUSD の実測
    for tf, (fb, fa) in {"D1": ("XAUUSD_D1_dukascopy", "XAUUSD_D1_dukascopy_ask"), "H1": ("XAUUSD_H1_dukascopy", "XAUUSD_H1_dukascopy_ask")}.items():
        if not args.smoke and not (os.path.exists(os.path.join(DATA_DIR, f"data_{fb}.csv")) and os.path.exists(os.path.join(DATA_DIR, f"data_{fa}.csv"))):
            missing.append(tf); continue
        bid = load_csv(fb, args.smoke, rng, freq="D" if tf == "D1" else "h", n=4000 if tf == "D1" else 40000)
        ask = load_csv(fa, args.smoke, rng, freq="D" if tf == "D1" else "h", n=4000 if tf == "D1" else 40000)
        if args.smoke:
            ask = bid.copy(); ask[["open", "high", "low", "close"]] += 0.3
        bid = bid[bid["high"] != bid["low"]]; ask = ask[ask["high"] != ask["low"]]
        mid = pd.merge(bid, ask, on="time", suffixes=("_b", "_a"))
        mid = pd.DataFrame({"time": mid["time"], "open": (mid["open_b"] + mid["open_a"]) / 2, "high": (mid["high_b"] + mid["high_a"]) / 2, "low": (mid["low_b"] + mid["low_a"]) / 2, "close": (mid["close_b"] + mid["close_a"]) / 2})
        spread_bp = float(((ask.set_index("time")["close"] - bid.set_index("time")["close"]) / bid.set_index("time")["close"] * 1e4).dropna().median())
        res["xauusd"][tf] = {"spread_median_bp": f(spread_bp), "bid_vs_ask": _compare(bid, ask, "XAUUSD", "bid", "ask"), "bid_vs_mid": _compare(bid, mid, "XAUUSD", "bid", "mid")}
        print("XAUUSD", tf, {k: v["disagree_rate"] for k, v in res["xauusd"][tf]["bid_vs_ask"].items() if k != "_pair"})
    # 擬似ずらし（15銘柄）
    syms, miss2 = syms_available(SYMS, smoke=args.smoke); missing += miss2
    for s in syms:
        bid = load_d1(s, args.smoke, rng); ask = bid.copy()
        for col in ("open", "high", "low", "close"):
            ask[col] = ask[col] + COST_RT[s] / 2
        res["pseudo_15"][s] = {k: v["disagree_rate"] for k, v in _compare(bid, ask, s, "bid", "bid+half_spread").items() if k != "_pair"}
    d1 = res["xauusd"].get("D1", {}).get("bid_vs_ask", {})
    rates = [v["disagree_rate"] for k, v in d1.items() if k != "_pair" and v["disagree_rate"] is not None]
    ts = [abs(v["pnl_diff_t_year"] or 0) for k, v in d1.items() if k != "_pair"]
    if rates and max(rates) < 0.01 and max(ts) < 2:
        verdict = "支持: 合図は bid/ask に頑健"
    elif rates and max(rates) >= 0.05:
        verdict = "対立: 合図の定義に価格の種類が入る"
    else:
        verdict = "未確定"
    out = {"question": "合図は bid か ask かで何割変わるか", "settings": {"rules": ["SMA200", "TSMOM20", "DONCH55_20"]}, "missing": missing, **res, "machine_verdict": verdict,
           "multiple_comparisons": "判定は XAUUSD D1 の bid vs ask 3 規則の不一致率と t。H1・擬似ずらしは記述。"}
    return out, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
