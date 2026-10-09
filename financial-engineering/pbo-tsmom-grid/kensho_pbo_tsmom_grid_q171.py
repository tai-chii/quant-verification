#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q171: 順張りの参照日数60通りの CSCV で、過剰適合の確率 PBO はいくつか（Bailey ほか 2017）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。`検証/学問/金融工学/知識/文献/アイデア候補.md` の該当行。
- 主張カード: Bailey2017-1_期間内の最良が期間外で中央値より下になる割合でバックテストの過剰適合の確率を測れる、
  Bailey2017-2_PBOは試したものすべてを入れないと過小評価になり探索の目的関数に使うのは誤用。
  既存知見: Q139（候補 J で楽観が増える）、Q150（事後の銘柄選択は後半で残らない）、Q036（多数から選んだ最良は補正後に基準と区別できない）。
  → 「手元の順張りの候補集合（参照日数 60 通り）は、Bailey の CSCV で測ると PBO がいくつか。『選んだ L が標本外で中央値以下』は半分より多いか」。

【仮説（測る前に固定）】
H1: 順張りの参照日数の候補集合は実質的に1つの戦略（L 間の相関が高い）なので、PBO は 0.5 付近に出る（選択に情報がない）。
H0 の対立: PBO が 0.2 以下なら「選択は標本外でも中央値より上を当てる」。

【データ】
15銘柄 D1_fromH1（2008-02〜2026-07）。候補 = TSMOM の参照日数 L ∈ {5,10,…,300}（60）。日次純損益（片道コスト段階1）。

【定義（1通りに固定）】
- CSCV（Bailey 2017 §5）: 損益行列 M（T 日 × 60 候補）を S=16 の等しい塊に分け、8 塊を期間内（IS）・残り 8 塊を期間外（OOS）とする
  全 C(16,8)=12,870 通りで、IS のシャープ最大の候補 k* を選び、OOS でのその候補の順位 ω（相対順位 = 順位/(N+1)）を出す。
  λ = log(ω/(1−ω))。PBO = λ<0 の割合（＝選んだ候補が OOS で中央値以下の割合）。
- 銘柄ごとに PBO を出す。合算（all15 の等ウェイト損益＝15銘柄の日次純損益の平均を候補ごとに）でも出す。
- 前半（<2017）／後半（≥2017）でも別々に（塊数は S=8・C(8,4)=70 に減る）。
- 帰無: 日次リターンを年の中で並べ替えて（候補間の相関構造は保たれ、時間の情報が消える）同じ PBO を B 回（既定 B=50。CSCV が重いので小さい）。
  帰無でも PBO ≈ 0.5 になるはず。その 2.5〜97.5 点を記録。
- 副次: OOS の成績の劣化（IS の最良のシャープ − 同じ候補の OOS シャープ）の平均（Bailey の performance degradation）。

【測るもの】
銘柄別・合算・群別（FX8・トレンド7）の PBO、λ の分布、帰無の PBO の区間、劣化の平均。

【判定（事前固定・変更禁止）】
合算（all15）の PBO ≥ 0.5 かつ 群の過半の銘柄で PBO ≥ 0.5 →「過剰適合の確率は高い（選んだ L は標本外で半分以上が中央値以下）」＝H1 支持。
合算の PBO ≤ 0.2 かつ 過半の銘柄で ≤ 0.3 →「選択は標本外でも当たる」＝H1 棄却。それ以外は未確定。
帰無の区間に合算の PBO が入っていれば「選択の情報は帰無と区別できない」を併記。

【捨てた案の数】
約4: 塊数 S を 8 にする案（組合せが少なすぎる）、OOS の指標を純損益にする案（Bailey はシャープ）、拡大窓の前方検証（Bailey の型から外れる）、
候補に ドンチャンや MA も混ぜる案（族が混ざると順位の解釈が難しい）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。CSCV は機械的な手順で、相場観の後知恵は入らない。

【委託の確かめ方】設計・コードは Fable（2026-10-09）。実行と解釈は後で Opus。実行者は結論ではなく JSON のパス・PBO の数値・
帰無の区間・Bailey 2017 §5（CSCV の手順）の該当箇所を返す。

【実装】自己完結。依存: numpy/pandas。
実行: python3 kensho_pbo_tsmom_grid_q171.py          （B=50、数分）
      python3 kensho_pbo_tsmom_grid_q171.py --B 5
      python3 kensho_pbo_tsmom_grid_q171.py --smoke
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


QID = "Q171"
DEFAULT_B = 50
LS = list(range(5, 301, 5))
S_FULL, S_HALF = 16, 8


def _pnl_matrix(df, sym):
    cb = cost_bp_oneway(sym, df["close"].values)
    return np.column_stack([pnl_bp(tsmom_pos(df["close"].values, L), df["close"].values, cb) for L in LS])


def cscv(M, S):
    """M: T×N の日次損益。戻り: PBO, λ の配列, 劣化の平均。"""
    T, N = M.shape
    T2 = (T // S) * S
    blocks = M[:T2].reshape(S, T2 // S, N)
    lam = []; degr = []
    for comb in itertools.combinations(range(S), S // 2):
        mask = np.zeros(S, bool); mask[list(comb)] = True
        IS = blocks[mask].reshape(-1, N); OOS = blocks[~mask].reshape(-1, N)
        sd_is = IS.std(axis=0, ddof=1); sd_oos = OOS.std(axis=0, ddof=1)
        sh_is = np.where(sd_is > 0, IS.mean(axis=0) / np.where(sd_is > 0, sd_is, 1), -np.inf)
        sh_oos = np.where(sd_oos > 0, OOS.mean(axis=0) / np.where(sd_oos > 0, sd_oos, 1), 0.0)
        k = int(np.argmax(sh_is))
        rank = (sh_oos < sh_oos[k]).sum() + 1  # 1..N（高いほど良い）
        w = rank / (N + 1)
        lam.append(math.log(w / (1 - w)))
        degr.append(sh_is[k] - sh_oos[k])
    lam = np.array(lam)
    return float((lam < 0).mean()), lam, float(np.mean(degr))


def run(args, rng):
    syms, missing = syms_available(SYMS, smoke=args.smoke)
    data = {s: load_d1(s, args.smoke, rng) for s in syms}
    per = {}; mats = {}
    for s in syms:
        M = _pnl_matrix(data[s], s); mats[s] = (data[s]["year"].values, M)
        T0 = LS[-1]
        pbo, lam, dg = cscv(M[T0:], S_FULL)
        yrs = data[s]["year"].values[T0:]
        halves = {}
        for name, msk in (("pre", yrs < SPLIT_YEAR), ("post", yrs >= SPLIT_YEAR)):
            if msk.sum() > 400:
                p2, l2, d2 = cscv(M[T0:][msk], S_HALF); halves[name] = {"pbo": f(p2), "degradation": f(d2), "n_days": int(msk.sum())}
        per[s] = {"pbo": f(pbo), "lambda_mean": f(lam.mean()), "degradation_sharpe_daily": f(dg), "n_days": int(len(M) - T0), **halves}
        print(s, "PBO", round(pbo, 3))
    # 合算（共通の日付で等ウェイト）
    frames = {s: pd.DataFrame(mats[s][1], index=data[s]["time"].values) for s in syms}
    pooled = {}
    for g, members in GROUPS.items():
        ms = [m for m in members if m in frames]
        if not ms:
            continue
        common = pd.concat([frames[m] for m in ms], axis=1, keys=ms).dropna()
        M = np.mean([common[m].values for m in ms], axis=0)
        pbo, lam, dg = cscv(M, S_FULL)
        yrs = common.index.year.values
        halves = {}
        for name, msk in (("pre", yrs < SPLIT_YEAR), ("post", yrs >= SPLIT_YEAR)):
            if msk.sum() > 400:
                p2, _, d2 = cscv(M[msk], S_HALF); halves[name] = {"pbo": f(p2), "degradation": f(d2)}
        # 帰無
        null = []
        for b in range(args.B):
            # 候補ごとに同じ並べ替えを使う（候補間の相関構造を保つ）
            idx = np.arange(len(M)).astype(int)
            for v in np.unique(yrs):
                ii = np.where(yrs == v)[0]; idx[ii] = ii[rng.permutation(len(ii))]
            null.append(cscv(M[idx], S_FULL)[0])
        null = np.array(null)
        pooled[g] = {"pbo": f(pbo), "lambda_mean": f(lam.mean()), "degradation_sharpe_daily": f(dg), "n_days": int(len(M)), "n_syms": len(ms),
                     "null_pbo_mean": f(null.mean()), "null_pbo_2.5": f(np.percentile(null, 2.5)), "null_pbo_97.5": f(np.percentile(null, 97.5)), **halves}
        print(g, "PBO", round(pbo, 3), "null", round(null.mean(), 3))
    # 判定
    a = pooled.get("all15", {}).get("pbo")
    maj_hi = sum(1 for s in syms if (per[s]["pbo"] or 0) >= 0.5) > len(syms) / 2
    maj_lo = sum(1 for s in syms if (per[s]["pbo"] or 1) <= 0.3) > len(syms) / 2
    if a is not None and a >= 0.5 and maj_hi:
        verdict = "支持: 過剰適合の確率は高い（選んだ L は標本外で半分以上が中央値以下）"
    elif a is not None and a <= 0.2 and maj_lo:
        verdict = "棄却: 選択は標本外でも当たる"
    else:
        verdict = "未確定"
    in_null = a is not None and pooled["all15"]["null_pbo_2.5"] <= a <= pooled["all15"]["null_pbo_97.5"]
    res = {"question": "順張りの参照日数60通りの CSCV で過剰適合の確率 PBO はいくつか", "settings": {"LS": LS, "S": S_FULL, "S_half": S_HALF, "B": args.B},
           "missing": missing, "per_symbol": per, "pooled": pooled, "machine_verdict": verdict, "pbo_inside_null_interval": bool(in_null),
           "multiple_comparisons": "判定は all15 の PBO 1本＋銘柄別の過半。群別・前後半は記述。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
