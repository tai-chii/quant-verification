#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q176: 最初の1時間→最後の1時間の日中モメンタムは、為替・株価指数・金で公表後に残るか（GarciaArano 2026・DeadSignalsLab 2026）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: GarciaArano2026-1_4銘柄共通パネルで日中モメンタムはコスト後に平均マイナス2.30bpパーデイで負けた、
  GarciaArano2026-2_IWMの日中モメンタムは公表前のグロス1.40bpから公表後は0.08bpまで減衰した、Seeck2026-1/2（ロンドン開始30分）、
  知見 Q108（USDJPY のロンドン開始30分シグナルは 2025 年以降コスト後に消える）。
  → Q108 は「開始30分→その日の残り」の USDJPY 1 本。本案は Gao ほか (2018) 型の「最初の1時間→最後の1時間」を為替8・金・株価指数2 の H1 で、
     公表（2018）前後に分けて測る。

【仮説（測る前に固定）】
H1: 最初の1時間の符号で最後の1時間を持つ日中モメンタムは、公表後（2018〜）にはコスト後に 0 と区別できない（GarciaArano の減衰と整合）。
対立: 株価指数（US500・USTECH）では公表後も粗利が正で残る。

【データ】H1（Dukascopy、UTC）: FX8・XAUUSD（2008〜）、US500・USTECH（2011〜）。

【定義（1通りに固定・夏時間は考えない）】
- 為替・金: 最初の1時間 = 07:00 の足（ロンドン寄付）、最後の1時間 = 20:00 の足（NY 引け前）。
- 株価指数: 最初の1時間 = 14:00 の足（NY 現物の寄付 13:30/14:30 UTC を含む近似）、最後の1時間 = 20:00 の足。
  感度（記述）: 最初を 13:00、最後を 19:00 にした版。
- r_first = その足の close/open − 1、r_last = 同じ。戦略: 最後の1時間に sign(r_first) を持つ（往復 1 回／日。段階1のコスト）。
- 統計: 銘柄ごとの平均 [bp/日]（粗利・コスト後）と NW(5) の t。群（FX8・指数2・金）の合算（日ごとの平均）。
  期間: 公表前 2008–2017／公表後 2018–2026-06（Gao, Han, Li & Zhou 2018 の公開年で区切る。固定）。
- 帰無: r_first を年内で並べ替え（最初と最後の繋がりを壊す）て合算の平均を B=500 回 → z。

【測るもの】銘柄別・群別の粗利とコスト後の平均・t・z、公表前後。

【判定（事前固定・変更禁止）】
公表後に、群の合算（粗利）の t < 2 または z < 2 が FX8・金・指数2 のすべて →「公表後は残らない」＝H1 支持。
指数2 の合算（粗利）が公表後に t ≥ 2 かつ z ≥ 2 で、コスト後も正 →「株価指数では残る」＝H1 の対立を支持。
それ以外は未確定。公表前の数値は再現の確認（記述）。

【捨てた案の数】約5: 30 分足（手元に無い）、夏時間で窓を動かす案、最初の30分（H1 では作れない）、
最後の1時間ではなくその日の残り（Q108 と重なる）、閾値つき（|r_first| 上位のみ）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・群別の t と z・GarciaArano 2026 の公表前後の表の箇所を返す。

【実装】自己完結。実行: python3 kensho_intraday_momentum_first_last_q176.py（B=500、1分前後）／--B 50／--smoke
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


QID = "Q176"
DEFAULT_B = 500
PUB_YEAR = 2018
WINDOWS = {"fx": (7, 20), "gold": (7, 20), "index": (14, 20)}
ALT_WINDOWS = {"index": (13, 19)}
GROUPS_Q = {"fx8": FX8, "gold": ["XAUUSD"], "index2": ["US500", "USTECH"]}


def _daily(df, h_first, h_last):
    d = df.copy(); d["date"] = d["time"].dt.date; d["hour"] = d["time"].dt.hour
    first = d[d["hour"] == h_first].set_index("date"); last = d[d["hour"] == h_last].set_index("date")
    x = pd.DataFrame({"r_first": first["close"] / first["open"] - 1, "p_last": last["open"], "r_last": last["close"] / last["open"] - 1}).dropna()
    x["year"] = pd.to_datetime(pd.Series(x.index)).dt.year.values
    return x.reset_index()


def _pnl(x, sym):
    pos = np.sign(x["r_first"].values); gross = pos * x["r_last"].values * 1e4
    net = gross - np.abs(pos) * COST_RT[sym] / x["p_last"].values * 1e4
    return gross, net


def run(args, rng):
    cands = FX8 + ["XAUUSD", "US500", "USTECH"]
    syms, missing = syms_available(cands, kind="H1_dukascopy", smoke=args.smoke)
    per = {}; daily = {}
    for s in syms:
        kind = "fx" if s in FX8 else ("gold" if s == "XAUUSD" else "index")
        df = load_csv(f"{s}_H1_dukascopy", args.smoke, rng, freq="h", n=80000, start="2009-01-01")
        x = _daily(df, *WINDOWS[kind]); g, n = _pnl(x, s); x["gross"], x["net"] = g, n; daily[s] = x
        per[s] = {}
        for pn, msk in (("pre", x["year"] < PUB_YEAR), ("post", x["year"] >= PUB_YEAR)):
            sub = x[msk]
            per[s][pn] = {"n": int(len(sub)), "gross_mean": f(sub["gross"].mean()), "gross_t": f(nw_t(sub["gross"].values)), "net_mean": f(sub["net"].mean()), "net_t": f(nw_t(sub["net"].values))}
        if kind in ALT_WINDOWS:
            xa = _daily(df, *ALT_WINDOWS[kind]); ga, na = _pnl(xa, s)
            per[s]["alt_window_post"] = {"gross_mean": f(ga[xa["year"] >= PUB_YEAR].mean()), "gross_t": f(nw_t(ga[xa["year"] >= PUB_YEAR]))}
        print(s, per[s])
    pooled = {}
    for g, members in GROUPS_Q.items():
        ms = [m for m in members if m in daily]
        if not ms:
            continue
        for pn, (y0, y1) in (("pre", (0, PUB_YEAR)), ("post", (PUB_YEAR, 9999))):
            frames = [daily[m][(daily[m]["year"] >= y0) & (daily[m]["year"] < y1)].set_index("date")[["gross", "net"]].add_suffix("_" + m) for m in ms]
            if not frames or any(len(fr) == 0 for fr in frames):
                continue
            cm = pd.concat(frames, axis=1)
            G = cm[[c for c in cm.columns if c.startswith("gross")]].mean(axis=1).dropna(); N = cm[[c for c in cm.columns if c.startswith("net")]].mean(axis=1).dropna()
            null = []
            for _ in range(args.B):
                vals = []
                for m in ms:
                    x = daily[m][(daily[m]["year"] >= y0) & (daily[m]["year"] < y1)]
                    rf = perm_within(rng, x["r_first"].values, x["year"].values)
                    vals.append((np.sign(rf) * x["r_last"].values * 1e4).mean())
                null.append(np.mean(vals))
            z, pct = z_of(G.mean(), null)
            pooled[f"{g}_{pn}"] = {"n_syms": len(ms), "n_days": int(len(G)), "gross_mean": f(G.mean()), "gross_t": f(nw_t(G.values)), "net_mean": f(N.mean()), "net_t": f(nw_t(N.values)), "null_z": f(z), "null_pct": f(pct)}
            print(g, pn, pooled[f"{g}_{pn}"])
    post = {g: pooled.get(f"{g}_post", {}) for g in GROUPS_Q}
    gone = all(((p.get("gross_t") or 0) < 2 or (p.get("null_z") or 0) < 2) for p in post.values() if p)
    idx = post.get("index2", {})
    if idx and (idx.get("gross_t") or 0) >= 2 and (idx.get("null_z") or 0) >= 2 and (idx.get("net_mean") or 0) > 0:
        verdict = "対立を支持: 株価指数では公表後も残る"
    elif gone:
        verdict = "支持: 公表後は残らない"
    else:
        verdict = "未確定"
    res = {"question": "最初の1時間→最後の1時間の日中モメンタムは為替・株価指数・金で公表後に残るか", "settings": {"windows_utc": WINDOWS, "alt_windows": ALT_WINDOWS, "pub_year": PUB_YEAR, "B": args.B},
           "missing": missing, "per_symbol": per, "pooled": pooled, "machine_verdict": verdict, "note": "夏時間は固定（近似）。指数の寄付の窓は 14:00 の足で近似し、13:00/19:00 を感度として併記。",
           "multiple_comparisons": "判定は公表後の群 3 本の粗利 t と z。銘柄別・公表前・感度は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
