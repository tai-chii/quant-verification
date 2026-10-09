#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q175: 15銘柄を束ねた t は、日でクラスタさせると素朴な t から何割下がるか（GarciaArano 2026-3・検証基盤の決まりのため）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: GarciaArano2026-3_相関する4銘柄をまとめたt検定は日でクラスタさせると素朴なtから約60パーセント下がった。
  関連: 改善判定（_基盤/知識/検証方法論/改善判定）、Q146（並べ替えの z のぶれ）。
  → 「手元の15銘柄（FX8・トレンド7）で、銘柄×日をプールした素朴な t と、日でクラスタした t（日ごとの合計の系列の t）の比はいくつか。
     群によって違うか。改善判定に『束ねるときは日でクラスタ』を決まりとして足す根拠になるか」。

【仮説（測る前に固定）】
H1: 為替8通貨はドルを共通に持つので相関が高く、比（クラスタ t ÷ 素朴 t）は 0.7 以下まで下がる。トレンド7 は相関が低く 0.9 前後。
（GarciaArano の 4 銘柄で −60% ＝ 比 0.4。）

【データ】15銘柄 D1_fromH1。規則 = TSMOM の参照日数 L ∈ {5,…,300}（60 通り。比の分布を見るため）。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- 素朴 t: 群の銘柄×日の純損益をすべて並べて 1 標本の t（n = 銘柄数×日数）。
- クラスタ t: 日ごとに群の銘柄の純損益を平均した系列の t（n = 日数）。さらに Newey-West(5) 版も出す。
- 比 = クラスタ t ÷ 素朴 t（符号は同じなので比は正。|t| で計算）。L ごとに出し、L の中央値・範囲。
- 理論値: 比 ≈ 1/√(1 + (n−1)·ρ̄)（ρ̄ = 群の損益の平均ペア相関）と比べる。
- 帰無: 各銘柄の損益系列を独立に時間方向へ循環シフト（銘柄間の相関を壊す）して比を B=300 回 → 比の分布（1 付近のはず）。
- 群: all15・FX8・トレンド7。前後半。

【測るもの】比の中央値（L 60 通り）、理論値、帰無の比、ρ̄、群別・前後半。|t|≥2 の判定が素朴とクラスタで割れる L の数。

【判定（事前固定・変更禁止）】
FX8 の比の中央値 ≤ 0.7 →「束ねた t は素朴な t から3割以上下がる」＝改善判定に『束ねるときは日でクラスタ（または合算系列の t）』を決まりとして追記する根拠。
FX8・トレンド7 とも比 ≥ 0.9 →「クラスタの影響は小さい（決まりは不要・注記にとどめる）」。それ以外は未確定（群ごとに記述）。
判定が割れる L の数は記述。

【捨てた案の数】約3: ランダム効果モデル、銘柄でクラスタする案（時系列の依存が主なので日でクラスタ）、月でクラスタ（日次損益の自己相関は小さいので日と NW で足りる）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。手順は機械的。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・比の中央値・GarciaArano 2026 の該当箇所（4銘柄の t の表）を返す。

【実装】自己完結。実行: python3 kensho_cluster_t_shrinkage_q175.py（B=300、1分前後）／--B 30／--smoke
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


QID = "Q175"
DEFAULT_B = 300
LS = list(range(5, 301, 5))


def _ratio(P):
    """P: 日×銘柄の損益（NaN なし）。戻り: (素朴 t, クラスタ t, NW t, 比)。"""
    naive = tstat(P.ravel()); clus = tstat(P.mean(axis=1)); nw = nw_t(P.mean(axis=1))
    ratio = abs(clus) / abs(naive) if naive not in (0, None) and np.isfinite(naive) and naive != 0 else float("nan")
    return naive, clus, nw, ratio


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    data = {s: load_d1(s, args.smoke, rng) for s in syms}
    pnls = {}
    for s in syms:
        c = data[s]["close"].values; cb = cost_bp_oneway(s, c)
        pnls[s] = pd.DataFrame(np.column_stack([pnl_bp(tsmom_pos(c, L), c, cb) for L in LS]), index=data[s]["time"].values, columns=LS)
    out = {}
    for g, members in GROUPS.items():
        ms = [m for m in members if m in pnls]
        if len(ms) < 2:
            continue
        common = pd.concat([pnls[m] for m in ms], axis=1, keys=ms).dropna()
        yrs = common.index.year.values
        for pn, msk in (("all", np.ones(len(common), bool)), ("pre", yrs < SPLIT_YEAR), ("post", yrs >= SPLIT_YEAR)):
            sub = common[msk]
            if len(sub) < 300:
                continue
            ratios = []; split_flags = 0; rows = []
            for L in LS:
                P = np.column_stack([sub[(m, L)].values for m in ms])
                nv, cl, nw, ra = _ratio(P); ratios.append(ra); rows.append((L, nv, cl, nw, ra))
                if (abs(nv) >= 2) != (abs(cl) >= 2):
                    split_flags += 1
            # ρ̄ と理論値（L=20 の損益で）
            P20 = np.column_stack([sub[(m, 20)].values for m in ms]); C = np.corrcoef(P20.T); n = len(ms)
            rho = float((C.sum() - n) / (n * (n - 1))); theory = 1 / math.sqrt(1 + (n - 1) * rho) if 1 + (n - 1) * rho > 0 else float("nan")
            # 帰無: 各銘柄を独立に循環シフト（L=20）
            null = []
            T = len(P20)
            for _ in range(args.B):
                Q = np.column_stack([np.roll(P20[:, j], int(rng.integers(252, T - 252))) for j in range(n)])
                null.append(_ratio(Q)[3])
            out[f"{g}_{pn}"] = {"n_syms": n, "n_days": int(len(sub)), "ratio_median": f(np.nanmedian(ratios)), "ratio_min": f(np.nanmin(ratios)), "ratio_max": f(np.nanmax(ratios)),
                                "rho_bar_L20": f(rho), "theory_ratio_L20": f(theory), "ratio_L20": f(rows[LS.index(20)][4]),
                                "naive_t_L20": f(rows[LS.index(20)][1]), "cluster_t_L20": f(rows[LS.index(20)][2]), "nw_t_L20": f(rows[LS.index(20)][3]),
                                "null_ratio_mean": f(np.nanmean(null)), "null_ratio_2.5": f(np.nanpercentile(null, 2.5)), "null_ratio_97.5": f(np.nanpercentile(null, 97.5)),
                                "n_L_decision_split_at_2": split_flags}
            print(g, pn, out[f"{g}_{pn}"]["ratio_median"], "theory", out[f"{g}_{pn}"]["theory_ratio_L20"])
    fx = out.get("fx8_all", {}).get("ratio_median"); tr = out.get("trend7_all", {}).get("ratio_median")
    if fx is not None and fx <= 0.7:
        verdict = "支持: 束ねた t は素朴な t から3割以上下がる（改善判定に日クラスタの決まりを追記する根拠）"
    elif fx is not None and tr is not None and fx >= 0.9 and tr >= 0.9:
        verdict = "棄却: クラスタの影響は小さい"
    else:
        verdict = "未確定"
    res = {"question": "15銘柄を束ねた t は日でクラスタさせると素朴な t から何割下がるか", "settings": {"LS": LS, "B": args.B}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "multiple_comparisons": "判定は FX8_all と trend7_all の比の中央値。L 別・前後半は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
