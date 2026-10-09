#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q177: 順張りの参照日数を選び直す頻度（月・四半期・半年・年）で標本外成績は変わるか（Zarrabi ほか 2017）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Zarrabi2017-1_FXテクニカルは期間全体では多くが有意でも毎月選び直すと儲かり方が続かなかった。
  関連知見: Q139（候補 J から選ぶ楽観）、Q155（エンバーゴ）、Q156（約定の遅れ）。
  → 「選び直す頻度 f を 21・63・126・252 営業日にすると、選んだ L の標本外純損益は f について単調に変わるか。頻繁に選び直すほど悪いか（Zarrabi）、それとも良いか」。

【仮説（測る前に固定）】
H1（Zarrabi）: 選び直す頻度が高い（f が小さい）ほど、標本外の純損益は低い（選択のノイズと切替コストが増える）。
H0: f によらず同じ（|t|<2・単調でない）。

【データ】15銘柄 D1_fromH1。候補 = TSMOM の参照日数 L ∈ {5,…,300}（60）。日次純損益（片道コスト段階1。L を切り替えた日の
ポジション変化にもコストがかかる＝切替コストを含む）。

【定義（1通りに固定）】
- 選択窓 = 直前 756 営業日（固定長）。選び直しの時点 = 営業日 756 から f 営業日ごと。各時点で窓内の平均純損益が最大の L を選び、次の選び直しまでその L のポジションを持つ。
- 標本外純損益 = つなげたポジション列から計算した日次純損益 [bp]（切替日の |Δpos| にコスト）。
- 集計: 銘柄×暦年の平均純損益 → 年ごとに銘柄平均 → 年を単位に平均と t。f=252 との対応ありの差（年単位 t）。単調性 = f 4 点と平均の Spearman。
- 群: all15・FX8・トレンド7。前後半。切替回数（L が変わった回数）も記録。
- 帰無: 各選び直し時点で L をランダムに選ぶ（B=300）→ 年単位の純損益の分布 → 各 f の z。

【測るもの】f ごとの純損益（年単位の平均・t）、f=252 との差の t、Spearman(f, 純損益)、切替回数、z。

【判定（事前固定・変更禁止）】
all15・全期間で、Spearman(f, 純損益) ≥ 0.8（f が長いほど良い）かつ f=21 − f=252 の差の t ≤ −2 →「頻繁な選び直しは損（Zarrabi と整合）」＝H1 支持。
|Spearman| < 0.8 かつ |t| < 2 →「頻度は結論を変えない」＝H0。Spearman ≤ −0.8 かつ t ≥ 2 →「頻繁な選び直しが良い（想定外）」。それ以外は未確定。

【捨てた案の数】約4: 拡大窓、選択の目的関数にシャープ、選び直しと同時に窓長も f に連動させる案（Q088 の交絡を避ける）、f=5（切替コストで決まりきる）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。手順は機械的。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・f ごとの純損益と差の t・Zarrabi 2017 の該当表（毎月の選び直しの結果）を返す。

【実装】自己完結。実行: python3 kensho_reselection_frequency_q177.py（B=300、数分）／--B 30／--smoke
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


QID = "Q177"
DEFAULT_B = 300
LS = list(range(5, 301, 5))
SEL_DAYS = 756
FREQS = [21, 63, 126, 252]


def _walk(M, POS, c, cb, freq, rng=None):
    """M: 日×L の純損益、POS: 日×L のポジション。選び直し時点ごとに L を選びポジションをつなげる。"""
    T = len(c); pos = np.zeros(T); chosen = []; t = SEL_DAYS
    while t < T:
        if rng is None:
            k = int(np.argmax(M[t - SEL_DAYS:t].mean(axis=0)))
        else:
            k = int(rng.integers(0, len(LS)))
        chosen.append(k); pos[t:t + freq] = POS[t:t + freq, k]; t += freq
    pnl = pnl_bp(pos, c, cb); pnl[:SEL_DAYS + 1] = np.nan
    switches = int(sum(1 for i in range(1, len(chosen)) if chosen[i] != chosen[i - 1]))
    return pnl, switches


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    per_year = []  # (sym, year, f, pnl_mean)
    switches = {}
    null_year = []  # (sym, year, f, b, pnl_mean)
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c); yrs = df["year"].values
        POS = np.column_stack([tsmom_pos(c, L) for L in LS]); M = np.column_stack([pnl_bp(POS[:, j], c, cb) for j in range(len(LS))])
        for fq in FREQS:
            pnl, sw = _walk(M, POS, c, cb, fq); switches[(s, fq)] = sw
            d = pd.DataFrame({"year": yrs, "pnl": pnl}).dropna().groupby("year")["pnl"].agg(["mean", "count"])
            for y, r in d[d["count"] >= 100].iterrows():
                per_year.append((s, int(y), fq, r["mean"]))
            for b in range(args.B):
                pn, _ = _walk(M, POS, c, cb, fq, rng)
                dn = pd.DataFrame({"year": yrs, "pnl": pn}).dropna().groupby("year")["pnl"].mean()
                for y, v in dn.items():
                    null_year.append((s, int(y), fq, b, v))
        print(s, {fq: switches[(s, fq)] for fq in FREQS})
    obs = pd.DataFrame(per_year, columns=["sym", "year", "f", "pnl"]); nul = pd.DataFrame(null_year, columns=["sym", "year", "f", "b", "pnl"])
    out = {}
    for g, members in GROUPS.items():
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            sub = obs[obs["sym"].isin(members) & (obs["year"] >= y0) & (obs["year"] < y1)]
            if sub.empty:
                continue
            by = sub.groupby(["year", "f"])["pnl"].mean().unstack("f").dropna()
            if len(by) < 3:
                continue
            means = {int(fq): f(by[fq].mean()) for fq in FREQS}; ts = {int(fq): f(tstat(by[fq].values)) for fq in FREQS}
            diff = by[21].values - by[252].values
            rho = spearman(FREQS, [by[fq].mean() for fq in FREQS])
            nsub = nul[nul["sym"].isin(members) & (nul["year"] >= y0) & (nul["year"] < y1)]
            nb = nsub.groupby(["b", "year", "f"])["pnl"].mean().groupby(["b", "f"]).mean().unstack("f")
            zs = {int(fq): f(z_of(by[fq].mean(), nb[fq].values)[0]) for fq in FREQS if fq in nb}
            out[f"{g}_{pn}"] = {"n_years": int(len(by)), "pnl_mean_by_f": means, "pnl_t_by_f": ts, "diff_21_minus_252": f(diff.mean()), "diff_t": f(tstat(diff)),
                                "spearman_f_pnl": f(rho), "null_z_by_f": zs,
                                "switches_mean_by_f": {int(fq): f(np.mean([switches[(m, fq)] for m in members if (m, fq) in switches]), 1) for fq in FREQS}}
    a = out.get("all15_all", {})
    rho, dt = a.get("spearman_f_pnl"), a.get("diff_t")
    if rho is not None and rho >= 0.8 and dt is not None and dt <= -2:
        verdict = "支持: 頻繁な選び直しは損（Zarrabi と整合）"
    elif rho is not None and abs(rho) < 0.8 and dt is not None and abs(dt) < 2:
        verdict = "H0: 頻度は結論を変えない"
    elif rho is not None and rho <= -0.8 and dt is not None and dt >= 2:
        verdict = "想定外: 頻繁な選び直しが良い"
    else:
        verdict = "未確定"
    res = {"question": "順張りの参照日数を選び直す頻度で標本外成績は変わるか", "settings": {"LS": LS, "SEL_DAYS": SEL_DAYS, "FREQS": FREQS, "B": args.B}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "multiple_comparisons": "判定は all15_all の Spearman と差の t の 2 本。群別・前後半は記述。"}
    return res, {"cells": obs}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
