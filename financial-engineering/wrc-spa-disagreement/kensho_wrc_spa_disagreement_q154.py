#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q154: WRC・SPA(consistent)・SPA(conservative) の判定は同じルール群でどれだけ割れるか
（RCtest 表1 の食い違いを 15銘柄 × TSMOM 180本で・自前実装）
================================================================================

【出典】
- 計画（事前登録）: /tmp/claude-0/specs20.py の Q154（Fable 2026-10-09）。アイデア候補.md の該当行。
- 論文ノート: Jedrzejewska・Drachal2026_RCtest（表1: WRC p=0.010・SPA consistent p<0.001・SPA conservative p=0.469。
  表2: 依存が強いと名目より多く棄却）、White2000_データスヌーピングの Reality Check、Hansen (2005, JBES「A Test for
  Superior Predictive Ability」、未読・定義は記憶による: 中心化 μ̂^l / μ̂^c / μ̂^u と閾値 √(2 log log n)）。
- 既存の知見: 先進国通貨の日足テクニカルは 2016 年以降も補正後に有意なルールが 0 本（Q019・Step-SPA）。
  → 「同じルール群・同じデータで、3 つの検定の 5% 判定がどれだけ割れるか。並べ替え帰無で各検定のサイズは名目か」。

【仮説（測る前に固定）】
H1: 銘柄×期間のセルのうち、3 つの検定の 5% 判定が一致しないセルが 30% 以上ある（検定の選び方で結論が変わる）。
H2: 真の差 0 の帰無（並べ替え・各ルールを中心化）で、名目 5% を 2 倍以上超える検定がある（依存で膨らむ）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足、列 time,open,high,low,close）。
15銘柄 = FX8 + トレンド7。2008-02〜2026-07。値動きのない足（high==low）は除く。無い銘柄は除いて件数を JSON に書く。

【定義（1通りに固定）】
- ルール群: TSMOM の参照日数 L ∈ {5,10,…,300}（60通り）× {買いのみ, 売りのみ, 両方} = 180 本。
  s_t = sign(c_t − c_{t−L})。買いのみ = max(s,0)、売りのみ = min(s,0)、両方 = s。翌日のポジション = 合図。
- 日次純損益 d_{k,t} [bp] = pos × (c_t/c_{t−1} − 1) × 1e4 − |Δpos| × 片道コスト[bp]（段階1の往復 COST_RT の半分）。
  基準 = 0（現金）なので損失関数の差 = d_{k,t} そのもの。
- セル = 銘柄 × 期間（前半 year<2017 / 後半 year≥2017）。各期間は t > LMAX=300 の日だけ（全ルールが定義される日）。
- ブートストラップ: 循環ブロック（ブロック長 BLOCK_LEN=5、ブロック数 nb=⌈n/5⌉、開始位置は一様乱数）、B=999 既定。
  ブロック和の表から d̄*_{b,k} = (1/(nb·5)) Σ_blocks S_k[start] を出す（最後のブロックを切り詰めない近似。n が 5 の倍数で
  ないとき高々 4 本の差）。同じ乱数の開始位置を 3 検定で共有する。
- WRC（White 2000・スチューデント化なし）: V = max_k √n d̄_k、V*_b = max_k √n (d̄*_{b,k} − d̄_k)、p = #{V*_b ≥ V}/B。
- SPA（Hansen 2005・スチューデント化）: ω̂_k = SD_b[√n (d̄*_{b,k} − d̄_k)]（ブートストラップの標準偏差）。
  T = max(0, max_k √n d̄_k/ω̂_k)。T*_b = max(0, max_k √n (d̄*_{b,k} − g(d̄_k))/ω̂_k)。p = #{T*_b ≥ T}/B。
  consistent: g_c(d̄_k) = d̄_k·1{√n d̄_k/ω̂_k > −√(2 log log n)}（はっきり悪いルールだけ中心化しない）。
  conservative（中心化なし・登録の呼び方）: g_u(d̄_k) = d̄_k（全ルールを 0 に中心化 ＝ μ̂^u、p が最大）。
  参考（判定に使わない）: lower g_l(d̄_k) = max(d̄_k, 0)（μ̂^l、p が最小）。
- 帰無（サイズ）: 各セルで日次対数リターンを期間内で並べ替えて価格を作り直し、180 本の d を出す。真の差 0（境界）に
  するため、各ルールの列から「並べ替え帰無のもとでの期待純損益 μ0_k」（MU0_PERMS=100 回の並べ替えの平均。コストと
  ドリフト×露出の分）を引く（標本平均で中心化すると観測統計量が 0 になり p=1 に固定されるので不可）。ルール間の依存は保つ。
  SIZE_REPS 回 × 30 セルで、各検定の 5% 棄却率。参考に中心化しない版（コストのため真の差 < 0 ＝ 境界の内側）も出す。
- 陽性対照（検出力）: 中心化した帰無の 1 本（L=20・両方）に +1bp/日 を足し、各検定の棄却率。

【測るもの】
(a) 観測セル（15×2）の 3 つの p と 5% 判定、判定が割れるセルの割合。
(b) 並べ替え帰無での各検定の棄却率（中心化あり＝サイズ、中心化なし＝参考）。
(c) 陽性対照での各検定の棄却率（検出力）。ついでに 3 検定の p の相関と、WRC−SPA(c) の p の差の分布。

【判定（事前固定・変更禁止）】
(a) ≥ 30% なら「検定の選び方で結論が変わる」＝基盤の決まりに「3つを併記」を追加する根拠。
(b) で名目 5% を 2 倍以上（≥10%）超える検定があれば「依存で膨らむ」（RCtest 表2と整合）を記録。(c) は記述。

【捨てた案の数】
約6: 定常ブートストラップ（Politis–Romano。登録は循環ブロック長 5）、ω̂ を Newey–West で出す案（Hansen の
ブートストラップ分散に統一）、Step-SPA（Q019 で済み・個々のルールの判定は問わない）、帰無を半年の組内の並べ替えに
する案（期間内一括。組内でも結論は変わらない見込み）、サイズの反復を B=999 のまま 100 回にする案（計算量のため 20 回
既定・`--size-reps` で調整）、ルール群に MA クロスを足す案（180 本に固定）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。Hansen 2005 の定義は記憶によるもの（未読）で、
閾値と中心化の 3 通りは原典と照合していない（RCtest パッケージの実装と差があり得る＝要確認）。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、下請け）。実行と解釈は後で Sonnet／Opus。
実行者は結論ではなく、JSON のパス・(a)(b)(c) の数値・原典の箇所（RCtest 表1・表2）を本体に返す。

【実装】自己完結・決定的。依存: python3 + numpy/pandas（matplotlib は任意、scipy 不要）。
実行: python3 kensho_wrc_spa_disagreement_q154.py                       （B=999、size-reps=20。目安 10〜20 分）
      python3 kensho_wrc_spa_disagreement_q154.py --B 199 --size-reps 5  （軽い試走）
      python3 kensho_wrc_spa_disagreement_q154.py --smoke                （合成データで経路の確認。結果は捨てる）
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import time
import unicodedata
import warnings

import numpy as np
import pandas as pd

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
TREND7 = ["XAUUSD", "XAGUSD", "WTI", "UKOIL", "US500", "USTECH", "BTCUSD"]
SYMS = FX8 + TREND7
COST_RT = {"EURUSD": .0002, "GBPUSD": .0002, "AUDUSD": .0002, "USDCHF": .0002, "USDCAD": .0002,
           "USDJPY": .02, "EURJPY": .02, "GBPJPY": .02, "XAUUSD": 0.6,
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}

LS = list(range(5, 301, 5))       # 60 通り
SIDES = ["long", "short", "both"]
LMAX = max(LS)
SPLIT_YEAR = 2017
BLOCK_LEN = 5
BOOT_B = 999
SIZE_REPS = 20
ALPHA = 0.05
POS_CONTROL_BP = 1.0
POS_CONTROL_RULE = ("both", 20)   # 陽性対照を足すルール
SEED = 20261009
CHUNK = 100
MU0_PERMS = 100      # 中心化に使う帰無の期待値を出す並べ替え回数


# ----------------------------------------------------------------------------- データ
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d.time.values, d.close.values.astype(float)


# ----------------------------------------------------------------------------- ルール群（ベクトル化）
def rule_names():
    return [f"{side}_L{L}" for side in SIDES for L in LS]


def rule_pnl_matrix(c, cost_rt):
    """n × 180 の日次純損益 [bp]。列の順 = SIDES × LS。"""
    n = len(c)
    S = np.zeros((n, len(LS)))
    for j, L in enumerate(LS):
        S[L:, j] = np.sign(c[L:] - c[:-L])
    sig = np.concatenate([np.maximum(S, 0), np.minimum(S, 0), S], axis=1)     # n × 180
    pos = np.vstack([np.zeros((1, sig.shape[1])), sig[:-1]])                   # 翌日に持つ
    ret = np.zeros(n); ret[1:] = c[1:] / c[:-1] - 1.0
    gross = pos * ret[:, None] * 1e4
    dpos = np.abs(np.diff(np.vstack([np.zeros((1, sig.shape[1])), pos]), axis=0))
    cost_bp = np.zeros(n); cost_bp[1:] = (cost_rt / 2.0) / c[:-1] * 1e4
    return gross - dpos * cost_bp[:, None]


# ----------------------------------------------------------------------------- ブートストラップと検定
def block_sums(D, l=BLOCK_LEN):
    """S[j] = Σ_{i<l} D[(j+i) mod n]（循環）。"""
    n = D.shape[0]
    cs = np.vstack([np.zeros((1, D.shape[1])), np.cumsum(np.vstack([D, D[:l - 1]]), axis=0)])
    return cs[l:l + n] - cs[:n]


def boot_means(D, starts, l=BLOCK_LEN):
    """starts: (B, nb) の開始位置 → d̄*: (B, K)。"""
    S = block_sums(D, l)
    nb = starts.shape[1]
    out = np.empty((starts.shape[0], D.shape[1]))
    for i in range(0, starts.shape[0], CHUNK):
        st = starts[i:i + CHUNK]
        out[i:i + CHUNK] = S[st].sum(axis=1) / (nb * l)
    return out


def tests_from_boot(dbar, Dstar, n):
    """dbar: (K,), Dstar: (B, K) 同じ系列のブートストラップ平均。3 つ（+参考 1 つ）の p を返す。"""
    sq = math.sqrt(n)
    dev = Dstar - dbar[None, :]                         # d̄* − d̄
    # WRC
    V = sq * dbar.max()
    Vstar = sq * dev.max(axis=1)
    p_wrc = float((Vstar >= V).mean())
    # SPA
    omega = np.sqrt(np.maximum((sq * dev).var(axis=0, ddof=1), 1e-300))
    tk = sq * dbar / omega
    T = max(0.0, float(tk.max()))
    thr = math.sqrt(2.0 * math.log(math.log(n)))
    g_c = np.where(tk > -thr, dbar, 0.0)                # consistent: はっきり悪いルールは中心化しない
    g_u = dbar                                          # conservative: 全部 0 に中心化
    g_l = np.maximum(dbar, 0.0)                         # lower（参考）
    out = {"p_wrc": p_wrc}
    for name, g in (("p_spa_consistent", g_c), ("p_spa_conservative", g_u), ("p_spa_lower", g_l)):
        Z = sq * (Dstar - g[None, :]) / omega[None, :]
        Tstar = np.maximum(0.0, Z.max(axis=1))
        out[name] = float((Tstar >= T).mean())
    out["stat_wrc"] = float(V); out["stat_spa"] = float(T)
    out["best_rule_idx"] = int(np.argmax(dbar)); out["best_dbar_bp"] = float(dbar.max())
    out["n_rules_positive"] = int((dbar > 0).sum())
    return out


def run_cell(D, rng, B):
    """観測セル: D (n × K) → 3 つの p。"""
    n = D.shape[0]; nb = int(math.ceil(n / BLOCK_LEN))
    starts = rng.integers(0, n, size=(B, nb))
    Dstar = boot_means(D, starts)
    return tests_from_boot(D.mean(axis=0), Dstar, n)


def permuted_pnl(c, cost_rt, period_idx, rng):
    """期間内で対数リターンを並べ替えて価格を作り直し、180 本の日次純損益（期間の行だけ）を返す。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    r2 = r.copy()
    idx = period_idx[period_idx >= 1]
    r2[idx] = r[rng.permutation(idx)]
    c2 = np.exp(np.log(c[0]) + np.cumsum(r2))
    return rule_pnl_matrix(c2, cost_rt)[period_idx]


def null_expected_mean(c, cost_rt, period_idx, rng, M=MU0_PERMS):
    """並べ替え帰無のもとでの各ルールの期待純損益 μ0_k（M 回の並べ替えの平均）。中心化に使う。"""
    acc = np.zeros(len(LS) * len(SIDES))
    for _ in range(M):
        acc += permuted_pnl(c, cost_rt, period_idx, rng).mean(axis=0)
    return acc / M


def run_null_cell(c, cost_rt, period_idx, rng, B, pos_idx, mu0):
    """並べ替え帰無 1 回: D → 中心化あり（D − μ0・真の差 0）／なし／陽性対照 の 3 変種の p（同じブートストラップ）。
    注意: 標本平均で中心化すると観測統計量が 0 になり p=1 に固定されるので、帰無の期待値 μ0 で中心化する。"""
    D = permuted_pnl(c, cost_rt, period_idx, rng)
    n = D.shape[0]; nb = int(math.ceil(n / BLOCK_LEN))
    starts = rng.integers(0, n, size=(B, nb))
    Dstar = boot_means(D, starts)
    dbar = D.mean(axis=0)
    out = {}
    out["raw"] = tests_from_boot(dbar, Dstar, n)                                       # 真の差 < 0（コスト）
    out["centered"] = tests_from_boot(dbar - mu0, Dstar - mu0[None, :], n)              # 真の差 0（境界）
    delta = -mu0.copy(); delta[pos_idx] += POS_CONTROL_BP
    out["positive_control"] = tests_from_boot(dbar + delta, Dstar + delta[None, :], n)  # 境界 + 1 本だけ +1bp
    return out


# ----------------------------------------------------------------------------- 本体
TESTS = ["p_wrc", "p_spa_consistent", "p_spa_conservative"]


def judge(a_share, size_rates):
    a_ok = np.isfinite(a_share) and a_share >= 0.30
    inflated = [k for k, v in size_rates.items() if np.isfinite(v) and v >= 2 * ALPHA]
    v1 = "検定の選び方で結論が変わる（3つを併記の根拠）" if a_ok else "判定が割れるセルは 30% 未満"
    v2 = f"依存で膨らむ検定あり（{', '.join(inflated)}）" if inflated else "名目 5% の 2 倍を超える検定なし"
    return dict(a_share_disagree=a_share, a_verdict=v1, size_rates_centered=size_rates, inflated_tests=inflated, b_verdict=v2,
                verdict=f"(a) {v1} / (b) {v2}",
                note="事前固定の規則で機械的に付けた判定。解釈（確定／ノイズ／未確定、(c) の検出力の読み）は実行者が記録する。")


def make_plot(cells, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"]:
            if os.path.exists(p):
                font_manager.fontManager.addfont(p)
                matplotlib.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name(); break
        matplotlib.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(10, 4.5))
        x = np.arange(len(cells)); w = 0.27
        for i, (k, col) in enumerate(zip(TESTS, ["tab:blue", "tab:orange", "tab:green"])):
            ax.bar(x + (i - 1) * w, cells[k], w, label=k, color=col)
        ax.axhline(ALPHA, c="k", lw=.6, ls="--")
        ax.set_xticks(x); ax.set_xticklabels([f"{s}\n{p}" for s, p in zip(cells.sym, cells.period)], fontsize=7, rotation=90)
        ax.set_ylabel("p"); ax.set_title("WRC / SPA(c) / SPA(u) の p（銘柄×期間）"); ax.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=BOOT_B, help="ブートストラップ回数（登録 999）")
    ap.add_argument("--size-reps", type=int, default=SIZE_REPS, help="セルごとの並べ替え帰無の反復数（サイズ・検出力）")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    series, missing = {}, []
    if args.smoke:
        g = np.random.default_rng(1)
        dates = pd.bdate_range("2008-02-01", "2026-07-14")
        for k, sym in enumerate(SYMS):
            phi = -0.1 + 0.3 * (k / (len(SYMS) - 1))
            e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
            for i in range(1, len(dates)):
                r[i] = phi * r[i - 1] + e[i]
            base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                    "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
            series[sym] = (dates.values, base * np.exp(np.cumsum(r)))
        B = min(args.B, 10); reps = min(args.size_reps, 2)
    else:
        for sym in SYMS:
            got = load_daily(sym)
            if got is None:
                missing.append(sym); continue
            series[sym] = got
        B = args.B; reps = args.size_reps
    names = rule_names()
    pos_idx = names.index(f"{POS_CONTROL_RULE[0]}_L{POS_CONTROL_RULE[1]}")

    # (a) 観測セル
    rows = []
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        D_all = rule_pnl_matrix(c, COST_RT[sym])
        for per, m in (("前半", years < SPLIT_YEAR), ("後半", years >= SPLIT_YEAR)):
            idx = np.flatnonzero(m & (np.arange(len(c)) > LMAX))
            if len(idx) < 250:
                continue
            r = run_cell(D_all[idx], rng, B)
            r["best_rule"] = names[r.pop("best_rule_idx")]
            rows.append(dict(sym=sym, period=per, n_days=int(len(idx)), **r))
    cells = pd.DataFrame(rows)
    for k in TESTS + ["p_spa_lower"]:
        cells["rej_" + k] = cells[k] < ALPHA
    rej = cells[["rej_" + k for k in TESTS]].values
    cells["disagree"] = rej.any(axis=1) & ~rej.all(axis=1)
    a_share = float(cells.disagree.mean()) if len(cells) else float("nan")
    t_obs = time.time() - t0

    # (b)(c) 並べ替え帰無
    nrows = []
    for sym, (t, c) in series.items():
        years = pd.DatetimeIndex(t).year.values
        for per, m in (("前半", years < SPLIT_YEAR), ("後半", years >= SPLIT_YEAR)):
            idx = np.flatnonzero(m & (np.arange(len(c)) > LMAX))
            if len(idx) < 250:
                continue
            mu0 = null_expected_mean(c, COST_RT[sym], idx, rng, M=(10 if args.smoke else MU0_PERMS))
            for rep in range(reps):
                o = run_null_cell(c, COST_RT[sym], idx, rng, B, pos_idx, mu0)
                row = dict(sym=sym, period=per, rep=rep)
                for var in ("raw", "centered", "positive_control"):
                    for k in TESTS + ["p_spa_lower"]:
                        row[f"{var}|{k}"] = o[var][k]
                nrows.append(row)
    nulls = pd.DataFrame(nrows)
    size_rates = {k: float((nulls[f"centered|{k}"] < ALPHA).mean()) if len(nulls) else float("nan") for k in TESTS}
    size_rates_raw = {k: float((nulls[f"raw|{k}"] < ALPHA).mean()) if len(nulls) else float("nan") for k in TESTS}
    power_rates = {k: float((nulls[f"positive_control|{k}"] < ALPHA).mean()) if len(nulls) else float("nan") for k in TESTS}
    extra = {var: float((nulls[f"{var}|p_spa_lower"] < ALPHA).mean()) if len(nulls) else float("nan") for var in ("raw", "centered", "positive_control")}
    n_null = int(len(nulls))
    null_disagree = float(((nulls[[f"centered|{k}" for k in TESTS]].values < ALPHA).any(axis=1) &
                           ~(nulls[[f"centered|{k}" for k in TESTS]].values < ALPHA).all(axis=1)).mean()) if n_null else float("nan")

    verdict = judge(a_share, size_rates)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q154_cells_{stamp}.csv"); cells.to_csv(csv_path, index=False)
    ncsv_path = os.path.join(OUT, f"{prefix}Q154_null_{stamp}.csv"); nulls.to_csv(ncsv_path, index=False)
    png_path = make_plot(cells, os.path.join(OUT, f"{prefix}Q154_pvalues_{stamp}.png")) if len(cells) else "(図なし)"
    pcorr = cells[TESTS].corr(method="spearman").round(3).to_dict() if len(cells) > 2 else {}
    out = dict(
        queue_id="Q154", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        settings=dict(LS=LS, SIDES=SIDES, n_rules=len(names), LMAX=LMAX, SPLIT_YEAR=SPLIT_YEAR, BLOCK_LEN=BLOCK_LEN, BOOT_B=B,
                      SIZE_REPS=reps, MU0_PERMS=MU0_PERMS, ALPHA=ALPHA, POS_CONTROL_BP=POS_CONTROL_BP, POS_CONTROL_RULE=list(POS_CONTROL_RULE),
                      SEED=SEED, COST_RT=COST_RT, syms=list(series), data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()), n=int(len(series[s][1])))
                   for s in series},
        missing=missing,
        a=dict(n_cells=int(len(cells)), share_disagree=a_share, n_disagree=int(cells.disagree.sum()) if len(cells) else 0,
               reject_rate_by_test={k: float(cells["rej_" + k].mean()) if len(cells) else float("nan") for k in TESTS + ["p_spa_lower"]},
               p_spearman_between_tests=pcorr,
               cells=cells[["sym", "period", "n_days"] + TESTS + ["p_spa_lower", "disagree", "best_rule", "best_dbar_bp", "n_rules_positive"]].to_dict(orient="records")),
        b=dict(n_null_datasets=n_null, size_rate_centered=size_rates, size_rate_raw_uncentered=size_rates_raw,
               spa_lower_reference=extra, null_disagree_share_centered=null_disagree),
        c=dict(power_rate_positive_control=power_rates, positive_control_bp=POS_CONTROL_BP, rule=names[pos_idx]),
        judgement=verdict,
        timing_sec=dict(observed_cells=round(t_obs, 1), total=round(time.time() - t0, 1)),
        files=dict(cells_csv=csv_path, null_csv=ncsv_path, png=png_path),
        multiple_comparisons=f"観測セル {len(cells)} × 3 検定 = {3 * len(cells)} 本の p（(a) は割れの割合を記述するだけで、個々の p を有意と数えない）。帰無 {n_null} データ × 3 変種 × 3 検定",
        deviations_from_prereg=["Hansen 2005 の中心化・閾値は記憶による自前実装（原典未読）。参考に SPA lower も出す（判定に使わない）",
                                "サイズ・検出力の反復は 1 セルあたり SIZE_REPS=20（計算量のため）。`--size-reps` で調整",
                                "循環ブロックの最後のブロックは切り詰めず nb×5 本で平均（近似）",
                                "各期間は全ルールが定義される t>300 の日だけ使う"],
    )
    jpath = os.path.join(OUT, f"{prefix}Q154_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else (int(o) if isinstance(o, np.integer) else (bool(o) if isinstance(o, np.bool_) else str(o))))

    print(f"[Q154] syms={len(series)}  rules={len(names)}  B={B}  size_reps={reps}  smoke={args.smoke}  missing={missing}")
    print(f"  (a) cells={len(cells)} disagree={a_share:.3f}  reject rate: " + " ".join(f"{k}={cells['rej_' + k].mean():.2f}" for k in TESTS))
    for _, r in cells.iterrows():
        print(f"      {r.sym:7s} {r.period} n={r.n_days:4d} WRC={r.p_wrc:.3f} SPAc={r.p_spa_consistent:.3f} SPAu={r.p_spa_conservative:.3f} "
              f"(l={r.p_spa_lower:.3f}) best={r.best_rule} {r.best_dbar_bp:+.2f}bp {'割れ' if r.disagree else ''}")
    print(f"  (b) size (centered): {size_rates}  raw: {size_rates_raw}  n_null={n_null}")
    print(f"  (c) power (+{POS_CONTROL_BP}bp on {names[pos_idx]}): {power_rates}")
    print("  判定(機械):", verdict["verdict"])
    print(f"  時間: 観測 {t_obs:.1f}s / 合計 {time.time() - t0:.1f}s")
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
