#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q180: RSI の族は、先進国通貨の日足で2016年以降も補正後に残るか（Coakley ほか 2016-2・Q054 ボリンジャーの続き）
================================================================================

【出典】
- 計画（事前登録）: 20案一括生成 第2弾（Fable 2026-10-09）。アイデア候補.md の該当行。
- 主張カード: Coakley2016-2_ボリンジャーとRSIのルールはFX22通貨で補正後も両期間に残った、Coakley2016-1（従来のルールは 2006–2015 にほぼ 0 本）。
  知見: 先進国通貨の日足テクニカルは2016年以降も補正後に有意なルールが0本（Q019: 移動平均・チャネル等、Q054: ボリンジャー）。
  → Coakley が「残った」と報告した 2 族のうち、RSI は未検証（条件の穴）。

【仮説（測る前に固定）】
H1: RSI の族も 2016 年以降の先進国 6 通貨で補正後に有意なルールは 0 本（Q019・Q054 と同じ）。
対立: 6 通貨中 2 以上で補正後に有意 →「RSI は公表後も残る」。

【データ】FX6（EURUSD・GBPUSD・AUDUSD・USDJPY・USDCHF・USDCAD）D1_fromH1。2016-01〜2026-06。参考期間 2008–2015（Coakley の標本と重なる。再現の確認）。

【定義（1通りに固定）】
- RSI(n) n ∈ {2, 7, 14, 21}。閾値（売られすぎ, 買われすぎ）∈ {(20,80), (30,70)}。保有 h ∈ {1, 5, 10} 日。向き: 逆張り（RSI<下で買い・RSI>上で売り）と順張り（逆）。
  計 4×2×3×2 = 48 本。合図の日の翌日から h 日保有（重なる合図は延長しない・1 本の単純な状態機械）。
- 日次純損益 [bp]: 片道コスト 1bp（Q019・Q054 と同じ。段階1 の表ではなく論文の設定）。
- 検定（White 2000 の Reality Check を並べ替えで）: 各通貨で、48 本の平均純損益の最大 max_k √T·mean(d_k) を、
  日次リターンを年内で並べ替えて作った系列で同じ 48 本を走らせた最大値の分布（B=500）と比べる → p（RC の p）。
  Step-SPA は Q019 のコードに依存するので使わない（違いを明記）。
- 有意 = p < 0.10（Q019 の α と同じ）。参考期間でも同じ手順。

【測るもの】通貨ごとの最良ルール・その純損益・RC の p、有意な通貨の数（2016–／参考 2008–2015）。

【判定（事前固定・変更禁止）】
2016 年以降で RC の p < 0.10 の通貨が 1 以下 →「RSI の族も残らない」＝H1 支持。2 以上 →「RSI は公表後も残る」＝対立を支持。
参考期間（2008–2015）で 2 以上なら Coakley の再現、0〜1 なら「手元のデータ・手順では元の結果も再現しない」と記述。

【捨てた案の数】約4: 閾値の格子を広げる（48 本に固定）、Step-SPA（依存を避ける）、片道コストを段階1の表にする（論文と揃える）、FX8（Q019 と同じ FX6）。

【知識の締め切り】Claude の知識の締め切りはおよそ 2026-06。

【委託の確かめ方】設計・コードは Fable。実行と解釈は後で Opus。実行者は JSON のパス・通貨別の p・Coakley 2016 の表（RSI 族の補正後の結果）を返す。

【実装】自己完結。実行: python3 kensho_rsi_rules_fx_q180.py（B=500、数分）／--B 50／--smoke
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


QID = "Q180"
DEFAULT_B = 500
NS = [2, 7, 14, 21]; THR = [(20, 80), (30, 70)]; HOLDS = [1, 5, 10]; DIRS = ["contra", "trend"]
COST_ONEWAY_BP = 1.0
PERIODS = {"2016-2026": (2016, 9999), "ref_2008-2015": (2008, 2016)}


def _rule_pos(r, lo, hi, h, direction):
    """合図の日から h 日保有。新しい合図があれば上書き（ベクトル化のための定義・明記）。"""
    sig = np.where(r < lo, 1.0, np.where(r > hi, -1.0, np.nan))
    if direction == "trend":
        sig = -sig
    return pd.Series(sig).ffill(limit=h - 1).fillna(0.0).values if h > 1 else np.nan_to_num(sig)


def _all_rules(close):
    cb = np.full(len(close), COST_ONEWAY_BP)
    out = []; names = []
    for n in NS:
        r = rsi(close, n)
        for lo, hi in THR:
            for h in HOLDS:
                for d in DIRS:
                    out.append(pnl_bp(_rule_pos(r, lo, hi, h, d), close, cb)); names.append(f"RSI{n}_{lo}-{hi}_h{h}_{d}")
    return np.column_stack(out), names


def run(args, rng):
    syms, missing = syms_available(FX6, smoke=args.smoke)
    out = {}
    for s in syms:
        df = load_d1(s, args.smoke, rng); yrs = df["year"].values; out[s] = {}
        for pn, (y0, y1) in PERIODS.items():
            msk = (yrs >= y0) & (yrs < y1)
            if msk.sum() < 500:
                continue
            c = df["close"].values[msk]; r = np.r_[0.0, c[1:] / c[:-1] - 1]; T = len(c)
            M, names = _all_rules(c); means = M.mean(axis=0); k = int(np.argmax(means)); stat = math.sqrt(T) * means[k]
            null = []
            for b in range(args.B):
                rp = perm_within(rng, r, yrs[msk]); cp = c[0] * np.cumprod(1 + np.r_[0.0, rp[1:]])
                Mn, _ = _all_rules(cp); null.append(math.sqrt(T) * Mn.mean(axis=0).max())
            p = float((np.array(null) >= stat).mean())
            out[s][pn] = {"n_days": int(T), "best_rule": names[k], "best_mean_bp": f(means[k]), "best_t": f(tstat(M[:, k])), "stat": f(stat), "rc_p": f(p), "n_rules_t_ge_2": int((np.abs([tstat(M[:, j]) for j in range(M.shape[1])]) >= 2).sum())}
            print(s, pn, out[s][pn]["best_rule"], out[s][pn]["rc_p"])
    n_sig = sum(1 for s in syms if (out[s].get("2016-2026", {}).get("rc_p") or 1) < 0.10)
    n_ref = sum(1 for s in syms if (out[s].get("ref_2008-2015", {}).get("rc_p") or 1) < 0.10)
    verdict = "支持: RSI の族も残らない" if n_sig <= 1 else "対立を支持: RSI は公表後も残る"
    res = {"question": "RSI の族は先進国通貨の日足で2016年以降も補正後に残るか", "settings": {"NS": NS, "THR": THR, "HOLDS": HOLDS, "cost_oneway_bp": COST_ONEWAY_BP, "n_rules": 48, "B": args.B, "alpha": 0.10},
           "missing": missing, "per_symbol": out, "n_significant_2016": n_sig, "n_significant_ref": n_ref, "machine_verdict": verdict,
           "note": "Reality Check を年内並べ替えで実装（Step-SPA ではない）。", "multiple_comparisons": "48 本×6 通貨を RC で補正。判定は有意な通貨の数 1 本。"}
    return res, None


def main():
    args = parse_args(default_B=DEFAULT_B)
    rng = np.random.default_rng(args.seed)
    res, csvs = run(args, rng)
    write_result(QID, res, args.smoke, csvs)
    print("machine_verdict:", res.get("machine_verdict"))


if __name__ == "__main__":
    main()
