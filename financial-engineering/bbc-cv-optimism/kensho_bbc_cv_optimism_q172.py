#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q172: BBC-CV のブートストラップ補正は、時系列の順張り選択の楽観を取り除くか（Tsamardinos ほか 2018）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Tsamardinos2018-1_交差検証で選んだ最良の成績は楽観的で標本が小さく設定が多いほど大きい、
  Tsamardinos2018-2_期間外の予測をブートストラップして選ぶ手順ごと再現すると追加の学習なしで楽観をほぼ取り除ける。
  既存知見: Q139（楽観は J で増え約 +8bp/日で頭打ち）、Q036（BBC-CV の楽観補正と Step-SPA の結論が同じ）。
  → 「BBC（bootstrap bias correction）を順張りの参照日数の選択に当てると、補正後の見積もりは翌年の実際の成績にどれだけ近づくか」。

【仮説（測る前に固定）】
H1: BBC の補正後の見積もりは、素朴な見積もり（選択期間での最良の成績）より翌年の実績に近い（楽観の過半を取り除く）。
対立: 時系列の依存（Tsamardinos は i.i.d. 前提）のため、補正後も翌年の実績より有意に高いまま。

【データ】15銘柄 D1_fromH1。候補 = TSMOM の参照日数 L ∈ {5,…,300}（60）。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- 選択期間 = テスト年 Y の直前 756 営業日（3年）。テスト = 暦年 Y（営業日 100 以上）。
- 候補に学習パラメータはないので、BBC の「プールした期間外予測」は選択期間の日次損益そのもの（Tsamardinos の手順の退化形。明記）。
- 素朴 = 選択期間で平均純損益が最大の L の、選択期間の平均 [bp/日]。
- BBC = 選択期間の日を 21 日ブロックで B 回ブートストラップ。各回、標本内（ブートストラップ標本）で最良の L を選び、
  標本外（選ばれなかった日 = out-of-bag）でのその L の平均を取り、B 回の平均。
- 実績 = 素朴で選んだ L のテスト年の平均純損益 [bp/日]。
- 楽観 = 素朴 − 実績、残り = BBC − 実績。（銘柄, 年）ごとに出し、年ごとに銘柄平均 → 年を単位に平均と t。
- 帰無: 翌年のリターンを年内で並べ替え（選択と翌年の関係を壊す）て「残り」の分布を B_null=200 回 → 残りの z（記述）。
- 前半／後半でも出す。

【測るもの】楽観の平均と t、残りの平均と t、残り÷楽観（取り除けた割合 = 1 − 残り/楽観）、群別、前後半。

【判定（事前固定・変更禁止）】
全15・全期間で、楽観 > 0 かつ t ≥ 2（楽観が存在）を前提に、
残りの |t| < 2 かつ 取り除けた割合 ≥ 0.5 →「BBC は時系列でも楽観の過半を取り除く」＝H1 支持。
残りの t ≥ 2 かつ 取り除けた割合 < 0.5 →「時系列では取り除けない」＝H1 棄却。それ以外（楽観自体が t<2 を含む）は未確定。

【捨てた案の数】約4: K 分割交差検証を作る案（候補に学習がないので不要）、i.i.d. ブートストラップ（時系列なので 21 日ブロック）、
BBC の内側にさらに選択の目的関数（シャープ）を使う案、拡大窓。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。手順は機械的。

【委託の確かめ方】設計・コードは Fable（2026-10-09）。実行と解釈は後で Opus。実行者は JSON のパス・楽観と残りの t・
Tsamardinos 2018 の BBC の手順（§2.3）の該当箇所を返す。

【実装】自己完結。実行: python3 kensho_bbc_cv_optimism_q172.py（B=200、数分）／--B 20／--smoke
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


QID = "Q172"
DEFAULT_B = 200
LS = list(range(5, 301, 5))
SEL_DAYS = 756
TEST_MIN = 100
BLOCK = 21
B_NULL = 200


def _bbc(M, rng, B, block):
    """M: 選択期間の日次損益（T×N）。戻り: BBC の見積もり [bp/日]。"""
    T, N = M.shape; nb = int(math.ceil(T / block)); ests = []
    for b in range(B):
        starts = rng.integers(0, nb, nb)
        idx = np.concatenate([np.arange(s * block, min((s + 1) * block, T)) for s in starts])
        inbag = np.zeros(T, bool); inbag[idx] = True
        oob = ~inbag
        if oob.sum() < 20:
            continue
        k = int(np.argmax(M[idx].mean(axis=0)))
        ests.append(M[oob, k].mean())
    return float(np.mean(ests)) if ests else float("nan")


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    rows = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); c = df["close"].values; cb = cost_bp_oneway(s, c)
        M = np.column_stack([pnl_bp(tsmom_pos(c, L), c, cb) for L in LS])
        yrs = df["year"].values
        for Y in np.unique(yrs):
            te = np.where(yrs == Y)[0]
            if len(te) < TEST_MIN:
                continue
            t0 = te[0]
            if t0 - SEL_DAYS < LS[-1]:
                continue
            sel = np.arange(t0 - SEL_DAYS, t0)
            Ms = M[sel]; Mt = M[te]
            k = int(np.argmax(Ms.mean(axis=0)))
            naive = Ms[:, k].mean(); real = Mt[:, k].mean(); bbc = _bbc(Ms, rng, args.B, BLOCK)
            # 帰無: テスト年のリターンの並べ替え → 実績の分布（残りの z 用）。候補ごとに同じ並べ替え。
            nulls = []
            r = np.zeros(len(te)); r[1:] = c[te][1:] / c[te][:-1] - 1
            for b in range(min(B_NULL, args.B)):
                pr = rng.permutation(len(te))
                cp = c[te][0] * np.cumprod(1 + np.r_[0.0, r[pr][1:]])
                full = np.r_[c[:t0], cp]
                nulls.append(pnl_bp(tsmom_pos(full, LS[k]), full, cost_bp_oneway(s, full))[t0:].mean())
            rows.append({"sym": s, "year": int(Y), "L": LS[k], "naive": naive, "bbc": bbc, "real": real,
                         "real_null_mean": float(np.mean(nulls)) if nulls else float("nan")})
        print(s, "cells", sum(1 for r_ in rows if r_["sym"] == s))
    cells = pd.DataFrame(rows)
    cells["optimism"] = cells["naive"] - cells["real"]; cells["residual"] = cells["bbc"] - cells["real"]
    cells["residual_null"] = cells["bbc"] - cells["real_null_mean"]
    out = {}
    for g, members in GROUPS.items():
        for per, msk in (("all", np.ones(len(cells), bool)), ("pre", cells["year"] < SPLIT_YEAR), ("post", cells["year"] >= SPLIT_YEAR)):
            sub = cells[msk & cells["sym"].isin(members)]
            if sub.empty:
                continue
            by = sub.groupby("year")[["optimism", "residual", "residual_null"]].mean()
            opt, resid = by["optimism"].values, by["residual"].values
            removed = 1 - resid.mean() / opt.mean() if opt.mean() != 0 else float("nan")
            out[f"{g}_{per}"] = {"n_cells": int(len(sub)), "n_years": int(len(by)), "optimism_mean": f(opt.mean()), "optimism_t": f(tstat(opt)),
                                 "residual_mean": f(resid.mean()), "residual_t": f(tstat(resid)), "removed_fraction": f(removed),
                                 "residual_vs_null_mean": f(by["residual_null"].mean()), "residual_vs_null_t": f(tstat(by["residual_null"].values))}
    a = out.get("all15_all", {})
    if a.get("optimism_t") is not None and a["optimism_mean"] > 0 and a["optimism_t"] >= 2:
        if abs(a["residual_t"]) < 2 and a["removed_fraction"] >= 0.5:
            verdict = "支持: BBC は時系列でも楽観の過半を取り除く"
        elif a["residual_t"] >= 2 and a["removed_fraction"] < 0.5:
            verdict = "棄却: 時系列では取り除けない"
        else:
            verdict = "未確定"
    else:
        verdict = "未確定（楽観自体が t<2）"
    res = {"question": "BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか", "settings": {"LS": LS, "SEL_DAYS": SEL_DAYS, "BLOCK": BLOCK, "B": args.B},
           "missing": missing, "summary": out, "machine_verdict": verdict, "note": "候補に学習パラメータがないため BBC のプール予測は選択期間の損益そのもの（退化形）",
           "multiple_comparisons": "判定は all15_all の残りの t と取り除けた割合の2本。群別・前後半は記述。"}
    return res, {"cells": cells}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
