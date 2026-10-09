#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q178: 帰無モデルの選び方（並べ替え・AR(1) ブートストラップ・GARCH 型）で移動平均ルールの判定は変わるか（Brock ほか 1992）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Brock1992-2_買いと売りの差はランダムウォークやGARCHでは説明できない、Brock1992-1（買い中 年12%・売り中 −7%）、
  Brock1992-3（補正はしていない）。関連: 失敗パターン集（帰無の選び方）、Q146（並べ替え帰無の z のぶれ）、Q154（WRC と SPA の判定の割れ）。
  → 「手元の15銘柄で Brock 型の移動平均ルールの『買い−売り』の差を、3 つの帰無（並べ替え・AR(1) 残差ブートストラップ・GARCH 型＝EWMA で標準化した残差の再構成）で検定すると、5% の判定はどれだけ割れるか」。

【仮説（測る前に固定）】
H1: 判定は帰無の選び方であまり割れない（割れるセルは 1 割以下。Q154 の WRC/SPA と同程度）。
対立: 3 割以上で割れる → 基盤の決まりに「帰無を 2 つ併記」を足す根拠。

【データ】15銘柄 D1_fromH1（2008-02〜2026-07）。

【定義（1通りに固定）】
- ルール（Brock 1992 の VMA、帯なし・固定）: (1,50)・(1,150)・(1,200)。買い = 終値 > 長期 SMA、売り = 以下。
- 統計量 = 買いの日の翌日平均リターン − 売りの日の翌日平均リターン [bp]（Brock の buy−sell）。コストは掛けない（帰無の比較が目的）。
- 帰無 (P): 日次リターンを年内で並べ替え。帰無 (A): AR(1) を当て（切片・係数）、残差を i.i.d. に再抽出して系列を再構成。
  帰無 (G): EWMA(λ=0.94) の分散で標準化した残差を i.i.d. に再抽出し、同じ EWMA の再帰で分散を作り直して系列を再構成（GARCH(1,1) の近似。明記）。
  各帰無で B=500 回、両側 p（|統計量| が観測以上の割合）。
- セル = 銘柄 × ルール × 期間（全・前半・後半）= 15×3×3 = 135。判定 = p < 0.05。
- 割れる = 3 つの帰無の判定が一致しないセル。サイズの確認: 統計量の符号を乱した系列（P で作った系列に P・A・G を当てる）で 5% 棄却率（記述）。

【測るもの】割れるセルの割合、帰無ごとの棄却数、帰無間の p の相関、p の差の分布。

【判定（事前固定・変更禁止）】
割れるセルの割合 ≥ 30% →「帰無の選び方で結論が変わる」（基盤の決まりに併記を足す根拠）。
≤ 10% →「変わらない（Q154 と整合）」＝H1 支持。その間は未確定（どのルール・群で割れるかを記述）。

【捨てた案の数】約4: GARCH(1,1) の最尤推定（scipy なし・EWMA で代替）、Brock の帯（1%）、ホールド 10 日の版、ブロックブートストラップ（並べ替えと近いので省く）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。手順は機械的。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・割れる割合・Brock 1992 の表（買い−売りとブートストラップの p）を返す。

【実装】自己完結。実行: python3 kensho_null_model_choice_q178.py（B=500、数分）／--B 50／--smoke
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


QID = "Q178"
DEFAULT_B = 500
RULES = [50, 150, 200]
LAMBDA = 0.94


def _stat(r, c, n):
    s = sma_pos(c, n); held = np.r_[0.0, s[:-1]]; rr = r * 1e4
    buy = rr[(held > 0) & np.isfinite(rr)]; sell = rr[(held < 0) & np.isfinite(rr)]
    return float(buy.mean() - sell.mean()) if len(buy) > 10 and len(sell) > 10 else float("nan")


def _recon(r0, c0, r_new):
    """リターン列 r_new から価格列を作る（先頭の価格は c0）。"""
    return c0 * np.cumprod(1 + np.r_[0.0, r_new[1:]])


def _ar1_boot_batch(rng, r, B):
    """AR(1) 残差ブートストラップを B 本まとめて（t のループ 1 回・B はベクトル）。戻り: B×T"""
    x, y = r[:-1], r[1:]; X = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta; T = len(r)
    eb = rng.choice(e, (B, T), replace=True); out = np.empty((B, T)); out[:, 0] = r[0]
    for t in range(1, T):
        out[:, t] = beta[0] + beta[1] * out[:, t - 1] + eb[:, t]
    return out


def _ewma_var(r):
    v = np.empty(len(r)); v[0] = r[:60].var()
    for t in range(1, len(r)):
        v[t] = LAMBDA * v[t - 1] + (1 - LAMBDA) * r[t - 1] ** 2
    return v


def _garch_boot_batch(rng, r, B):
    """EWMA 標準化残差の再抽出 → 同じ再帰で分散を作り直す（GARCH(1,1) の近似）。B×T"""
    v = _ewma_var(r); z = r / np.sqrt(v); mu = r.mean(); T = len(r)
    zb = rng.choice(z - z.mean(), (B, T), replace=True); out = np.empty((B, T)); vv = np.full(B, v[0]); out[:, 0] = r[0]
    for t in range(1, T):
        vv = LAMBDA * vv + (1 - LAMBDA) * (out[:, t - 1] - mu) ** 2
        out[:, t] = mu + np.sqrt(vv) * zb[:, t]
    return out


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    cells = []
    for s in syms:
        df = load_d1(s, args.smoke, rng); yrs = df["year"].values
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            msk = (yrs >= y0) & (yrs < y1)
            if msk.sum() < 500:
                continue
            c = df["close"].values[msk]; r = np.r_[0.0, c[1:] / c[:-1] - 1]
            obs = {n: _stat(r, c, n) for n in RULES}
            nulls = {k: {n: [] for n in RULES} for k in "PAG"}
            RA = _ar1_boot_batch(rng, r, args.B); RG = _garch_boot_batch(rng, r, args.B)
            for b in range(args.B):
                rP = perm_within(rng, r, yrs[msk])
                for k, rn in (("P", rP), ("A", RA[b]), ("G", RG[b])):
                    cn = _recon(r, c[0], rn)
                    for n in RULES:
                        nulls[k][n].append(_stat(rn, cn, n))
            for n in RULES:
                ps = {k: float((np.abs(np.array(nulls[k][n])) >= abs(obs[n])).mean()) if np.isfinite(obs[n]) else float("nan") for k in "PAG"}
                dec = {k: (ps[k] < 0.05) for k in "PAG"}
                cells.append({"sym": s, "period": pn, "rule": n, "stat_bp": obs[n], "p_P": ps["P"], "p_A": ps["A"], "p_G": ps["G"], "split": len(set(dec.values())) > 1})
        print(s, "done")
    cdf = pd.DataFrame(cells)
    out = {"n_cells": int(len(cdf)), "split_fraction": f(cdf["split"].mean()), "reject_counts": {k: int((cdf[f"p_{k}"] < 0.05).sum()) for k in "PAG"},
           "p_corr": {"P_A": f(cdf["p_P"].corr(cdf["p_A"])), "P_G": f(cdf["p_P"].corr(cdf["p_G"])), "A_G": f(cdf["p_A"].corr(cdf["p_G"]))},
           "split_by_rule": {int(n): f(cdf[cdf["rule"] == n]["split"].mean()) for n in RULES},
           "split_by_group": {g: f(cdf[cdf["sym"].isin(m)]["split"].mean()) for g, m in GROUPS.items()},
           "split_by_period": {pn: f(cdf[cdf["period"] == pn]["split"].mean()) for pn in ("all", "pre", "post")}}
    sf = out["split_fraction"] or 0
    verdict = "対立: 帰無の選び方で結論が変わる" if sf >= 0.30 else ("支持: 変わらない（Q154 と整合）" if sf <= 0.10 else "未確定")
    res = {"question": "帰無モデルの選び方で移動平均ルールの判定は変わるか", "settings": {"RULES": RULES, "LAMBDA": LAMBDA, "B": args.B}, "missing": missing,
           "summary": out, "machine_verdict": verdict, "note": "G は GARCH(1,1) の EWMA 近似（最尤推定なし）。", "multiple_comparisons": "判定は割れる割合 1 本。"}
    return res, {"cells": cdf}


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
