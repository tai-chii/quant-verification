#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q187: 為替のボラ予測で、損失関数の差はモデルの差の何倍に見えるか（Tokajuk・Chudziak 2026-1 の為替移植）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Tokajuk2026-1_ボラ予測の成績は損失関数を変えたときの差がモデルを変えたときの差の約3倍に見える、
  Tokajuk2026-2_損失関数の差の大半は予測の水準で検証期間の定数倍でそろえると77パーセント減りモデルの差が上回る。
  知見 Q076（為替で前年の定数倍は平均の偏りを消すが年ごとのずれは小さくならない）。
  → Q076 は「水準合わせの効果」だけ。本案は Tokajuk の主張の前半「損失関数の差 ÷ モデルの差」の比そのものを為替で測る。

【仮説（測る前に固定）】
H1（Tokajuk の移植）: 為替の日次ボラ予測でも、学習に使う損失関数を変えたときの期間外の成績の幅は、モデルを変えたときの幅の 2 倍以上に見え、
水準合わせ（前年の定数倍）でその幅が半分以下に減る。
H0: 比が 1 未満（為替では損失関数の差は小さい）。

【データ】FX8 D1_fromH1（2008〜2026-06）。目的変数 y_{t+1} = r_{t+1}²（日次の二乗リターン。実現分散の代理・明記）。

【定義（1通りに固定）】
- モデル 3 族: (M1) EWMA(λ)、λ ∈ {0.80,0.85,0.90,0.92,0.94,0.96,0.97,0.98,0.99}；(M2) 移動窓の分散 n ∈ {5,10,20,40,60,120}；
  (M3) HAR 型（切片なし）ŷ = β1·v1 + β2·v5 + β3·v22（v_k = 直前 k 日の r² の平均）、β ∈ {0,0.1,…,1.2}³ の格子。
- 学習損失 3 つ: MSE、QLIKE（y/ŷ − log(y/ŷ) − 1）、MAE。各族のハイパーパラメータ（λ・n・β）を学習期間でその損失が最小になるように選ぶ。
- 評価: 拡大窓・年ごとに再学習（最初の学習 3 年）。期間外（翌年）の MSE・QLIKE・MAE を出し、評価損失ごとにモデル×学習損失の 3×3 の表。
- 幅: 評価損失 e ごとに、D_loss(e) = 各モデルについての（学習損失間の最大−最小）の平均、D_model(e) = 各学習損失についての（モデル間の最大−最小）の平均。
  比 R(e) = D_loss / D_model。3 つの評価損失の平均の比 R̄。
- 水準合わせ: 前年の c = mean(y/ŷ)（Tokajuk 式 1）を掛けてから同じ表を作り、R̄_c と、幅の減り方 1 − D_loss_c/D_loss。
- 集計: 通貨ごとに R̄ を出し、8 通貨の平均と t。前後半（テスト年で分ける）。帰無は置かない（比の記述。Tokajuk も記述）。

【測るもの】R̄、R̄_c、D_loss の減り方、通貨別、前後半。

【判定（事前固定・変更禁止）】
8 通貨の平均で R̄ ≥ 2 かつ 水準合わせで D_loss が 50% 以上減る →「Tokajuk の構図は為替でも再現」＝H1 支持。
R̄ < 1 →「為替では損失関数の差は小さい」＝H0。その間は未確定。前後半で R̄ の向きが割れれば未確定。

【捨てた案の数】約4: GARCH の最尤（scipy なし）、実現分散（日中足から作る案。H1 から作れるが別案に回す）、
HAR の切片（格子が増える）、学習損失に Huber を足す案。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・R̄ と減り方・Tokajuk 2026 の該当表（損失関数間・モデル間の幅）を返す。

【実装】自己完結。実行: python3 kensho_vol_forecast_loss_vs_model_q187.py（数分）／--smoke
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


QID = "Q187"
DEFAULT_B = 0
LAMS = [0.80, 0.85, 0.90, 0.92, 0.94, 0.96, 0.97, 0.98, 0.99]
NS = [5, 10, 20, 40, 60, 120]
BGRID = np.arange(0, 1.21, 0.1)
BMAT = np.array([[b1, b2, b3] for b1 in BGRID for b2 in BGRID for b3 in BGRID])
BMAT = BMAT[BMAT.sum(axis=1) > 0]  # 全部 0 の予測（ŷ=0）は除く
LOSSES = ["MSE", "QLIKE", "MAE"]
TRAIN_YEARS = 3


def _loss(y, yhat, kind):
    yhat = np.maximum(yhat, 1e-12)
    if kind == "MSE":
        return float(np.mean((y - yhat) ** 2))
    if kind == "MAE":
        return float(np.mean(np.abs(y - yhat)))
    q = y / yhat
    return float(np.mean(q - np.log(np.maximum(q, 1e-12)) - 1))


def _ewma_fc(r2, lam):
    """ŷ_{t+1} = λ ŷ_t + (1−λ) r²_t（先頭は 60 日平均）。"""
    v = np.empty(len(r2)); v[0] = r2[:60].mean()
    for t in range(1, len(r2)):
        v[t] = lam * v[t - 1] + (1 - lam) * r2[t - 1]
    return v


def _forecasts(r2):
    s = pd.Series(r2)
    fc = {("EWMA", lam): _ewma_fc(r2, lam) for lam in LAMS}
    fc.update({("ROLL", n): s.rolling(n).mean().shift(1).values for n in NS})
    V = np.column_stack([s.rolling(k).mean().shift(1).values for k in (1, 5, 22)])
    return fc, V


def run(args, rng):
    syms, missing = syms_available(FX8, smoke=args.smoke)
    per = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); r = df["ret"].fillna(0).values; yrs = df["year"].values
        r2 = (r * 1e2) ** 2  # 単位: (%)²。目的変数 y_t = r2_t を t−1 までの情報で予測する
        fc, V = _forecasts(r2)
        years = sorted(np.unique(yrs)); rows = []
        for i, Y in enumerate(years):
            if i < TRAIN_YEARS:
                continue
            tr = (yrs < Y) & (yrs >= years[0]); te = yrs == Y; prev = yrs == years[i - 1]
            tr &= np.isfinite(V).all(axis=1); te_ok = te & np.isfinite(V).all(axis=1)
            if te_ok.sum() < 100:
                continue
            ytr, yte, yprev = r2[tr], r2[te_ok], r2[prev]
            for L in LOSSES:
                # 各族で学習損失 L を最小にするハイパーパラメータ
                best = {}
                for fam, keys in (("EWMA", LAMS), ("ROLL", NS)):
                    k = min(keys, key=lambda kk: _loss(ytr, fc[(fam, kk)][tr], L)); best[fam] = fc[(fam, k)]
                YH = np.maximum(V[tr] @ BMAT.T, 1e-12)  # T×2197
                if L == "MSE":
                    ls = ((ytr[:, None] - YH) ** 2).mean(axis=0)
                elif L == "MAE":
                    ls = np.abs(ytr[:, None] - YH).mean(axis=0)
                else:
                    q = ytr[:, None] / YH; ls = (q - np.log(q) - 1).mean(axis=0)
                best["HAR"] = V @ BMAT[int(np.argmin(ls))]
                for fam, yh in best.items():
                    c = float(np.mean(yprev / np.maximum(yh[prev], 1e-12)))  # 前年の水準合わせ
                    for E in LOSSES:
                        rows.append({"year": int(Y), "train_loss": L, "model": fam, "eval_loss": E, "loss": _loss(yte, yh[te_ok], E), "loss_c": _loss(yte, c * yh[te_ok], E)})
        d = pd.DataFrame(rows)

        def ratios(d, col):
            out = {}
            for E in LOSSES:
                sub = d[d["eval_loss"] == E].groupby(["model", "train_loss"])[col].mean().unstack("train_loss")
                D_loss = float((sub.max(axis=1) - sub.min(axis=1)).mean()); D_model = float((sub.max(axis=0) - sub.min(axis=0)).mean())
                out[E] = {"D_loss": D_loss, "D_model": D_model, "ratio": D_loss / D_model if D_model > 0 else float("nan")}
            return out
        per[s] = {}
        for pn, (y0, y1) in (("all", (0, 9999)), ("pre", (0, SPLIT_YEAR)), ("post", (SPLIT_YEAR, 9999))):
            dd = d[(d["year"] >= y0) & (d["year"] < y1)]
            if dd.empty:
                continue
            ra, rc = ratios(dd, "loss"), ratios(dd, "loss_c")
            per[s][pn] = {"ratio_mean": f(np.nanmean([v["ratio"] for v in ra.values()])), "ratio_mean_aligned": f(np.nanmean([v["ratio"] for v in rc.values()])),
                          "D_loss_reduction": f(1 - np.mean([rc[E]["D_loss"] for E in LOSSES]) / max(np.mean([ra[E]["D_loss"] for E in LOSSES]), 1e-12)),
                          "by_eval": {E: {k: f(v) for k, v in ra[E].items()} for E in LOSSES}, "n_test_years": int(dd["year"].nunique())}
        print(s, per[s].get("all"))
    summ = {}
    for pn in ("all", "pre", "post"):
        vals = [per[s][pn]["ratio_mean"] for s in syms if pn in per[s] and per[s][pn]["ratio_mean"] is not None]
        reds = [per[s][pn]["D_loss_reduction"] for s in syms if pn in per[s] and per[s][pn]["D_loss_reduction"] is not None]
        if vals:
            summ[pn] = {"ratio_mean": f(np.mean(vals)), "ratio_t": f(tstat(vals)), "reduction_mean": f(np.mean(reds)), "n_syms": len(vals)}
    a = summ.get("all", {}); rm, red = a.get("ratio_mean"), a.get("reduction_mean")
    split_ok = all(((summ.get(p, {}).get("ratio_mean") or 0) >= 1) == ((rm or 0) >= 1) for p in ("pre", "post") if p in summ)
    if rm is not None and rm >= 2 and red is not None and red >= 0.5 and split_ok:
        verdict = "支持: Tokajuk の構図は為替でも再現"
    elif rm is not None and rm < 1 and split_ok:
        verdict = "H0: 為替では損失関数の差は小さい"
    else:
        verdict = "未確定"
    res = {"question": "為替のボラ予測で損失関数の差はモデルの差の何倍に見えるか", "settings": {"LAMS": LAMS, "NS": NS, "BGRID_step": 0.1, "LOSSES": LOSSES, "TRAIN_YEARS": TRAIN_YEARS}, "missing": missing,
           "per_symbol": per, "summary": summ, "machine_verdict": verdict, "note": "目的変数は日次の二乗リターン（実現分散の代理）。HAR は切片なしの格子。帰無なし（比の記述）。",
           "multiple_comparisons": "判定は 8 通貨平均の R̄ と減り方の 2 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
