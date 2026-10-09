#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検証キュー Q148: 弱い形の効率性の検定（分散比）の結論は、設定（q・期間）でどれだけ動くか
（Alahmadi・Basingab 2026 §3.5・15銘柄 D1・暦年）
================================================================================

【出典】
- 事前登録: /tmp/claude-0/specs20.py の Q148（Fable 2026-10-09）＝アイデア候補.md の行。
- 論文ノート: Alahmadi・Basingab 2026 弱い形の市場効率性検定の体系的レビュー。
  検証するなら:「ある検定で非効率と出た結果は、設定を変えると消える頻度が高い」。§3.5 設定依存、§4.5 構造変化。
- Lo & MacKinlay (1988)（未読・分散比検定）。式はよく知られた形を自前で実装（下の【定義】）。

【仮説（測る前に固定）】
H: 分散比検定の結論（有意か・VR の符号）は、q と年の取り方で割れる頻度が、真の VR=1 の帰無で出る偽陽性の水準より
   はっきり高い（＝結論は設定依存）。

【データ】
検証/学問/金融工学/作業/FX/システムトレード/data_<SYM>_D1_fromH1.csv（UTC 日足）。15銘柄。期間＝暦年 2008〜2025 の 18 年
（2026 は 7 月までなので判定の表には入れない。MIN_DAYS=100 未満の年は捨てる）。無いファイルは除いて件数を JSON に書く。

【定義（1通りに固定）】
- 日次対数リターン r_t = ln(c_t / c_{t−1})。セル = 銘柄 × 暦年 × q、q ∈ {2, 5, 10, 20}。
- Lo–MacKinlay の分散比（重なりあり・不偏調整）: T 個のリターン、μ̂ = 平均。
    σ̂a² = Σ (r_t − μ̂)² / (T − 1)
    σ̂c²(q) = Σ_{t=q}^{T} (r_t + … + r_{t−q+1} − q μ̂)² / m,  m = q (T − q + 1)(1 − q/T)
    VR(q) = σ̂c²(q) / σ̂a²
- 不均一分散に頑健な z*（Lo–MacKinlay 1988 式）:
    δ(j) = [Σ_{t=j+1}^{T} (r_t − μ̂)² (r_{t−j} − μ̂)²] / [Σ (r_t − μ̂)²]²
    θ(q) = Σ_{j=1}^{q−1} [2 (q − j) / q]² δ(j),   z*(q) = (VR(q) − 1) / √θ(q)
- 有意 = |z*| ≥ 1.96。符号 = VR > 1（持続）か VR < 1（反転）か。
- (a) 設定で結論が割れる: 銘柄×年で、4 つの q のうち有意の数が 1〜3 の割合（0 と 4 は「割れない」）。
- (b) 符号が q 間で割れる: 銘柄×年で、VR−1 の符号が 4 つの q で一致しない割合。
- (c) 隣り合う年で結論が変わる: 同じ銘柄・同じ q で、連続する 2 年の結論（有意+／有意−／非有意）が異なる割合。
      あわせて「どれかの q で有意」の有無が隣り合う年で変わる割合（記述）。
- 帰無: 日次リターンを年内で並べ替え（真の VR=1・ドリフトとボラは同じ）、同じ (a)(b) を B=300 回。
  (a)(b) の帰無分布の平均・97.5% 点と、観測の z。
- 期間: 前半 = year < 2017、後半 = year ≥ 2017、全期間。群: 全15・FX8・トレンド7。判定は 全15×全期間。

【測るもの】
(a)(b)(c) の割合（群×期間）、帰無の (a)(b) の分布、セルごとの VR・z*・有意・符号の表（CSV）。

【判定（事前固定・変更禁止）】
- 全15×全期間で、(a) ≥ 2 × 帰無の (a) の平均 かつ (a) ≥ 0.30 なら「結論は設定依存」（Alahmadi の懸念を支持）。
- (a) が帰無と区別できなければ（z < 2）「設定依存は偽陽性の水準」。それ以外は未確定。
- (c) は記述（判定に使わない）。
- 多重比較: 検定のセルは 15 × 18 × 4 = 1080 だが、判定は割合 (a) の 1 本（帰無との比較）。

【捨てた案の数】
約5: 均一分散の z（頑健版だけに統一）、q を {2,4,8,16} にする案（登録どおり {2,5,10,20}）、重なりなしの分散比、
Chow–Denning の同時検定（設定依存そのものを測るので多重 q をまとめない）、半年のセル（年に統一）。

【知識の締め切り】
Claude の知識の締め切りはおよそ 2026-06。データは 2026-07 まで。検定の結論の「割れ方」は相場観からは作れない。

【委託の確かめ方】
設計は Fable（specs20.py）。コードは Claude（Fable 5.1、2026-10-09）。分散比と z* は自前実装（scipy 不要）。
実行と結果の解釈は Sonnet／Opus が後で行う。実行者は結論ではなく、結果 JSON のパス・(a)(b)(c) と帰無の値・原典の箇所を本体に返す。

【実装】自己完結・決定的（乱数は seed 固定の並べ替えだけ）。依存: python3 + numpy/pandas（matplotlib は任意）。
実行: python3 kensho_variance_ratio_setting_dependence_q148.py            （B=300、1〜2 分）
      python3 kensho_variance_ratio_setting_dependence_q148.py --B 30
      python3 kensho_variance_ratio_setting_dependence_q148.py --smoke    （合成データで経路の確認。結果は捨てる）
事前登録からの変更点: なし（2026 年は 7 月までで 100 日以上あるためセルとしては残るが、年のリストは 2008〜2025 に固定）。
"""
import argparse
import datetime as _dt
import json
import math
import os
import sys
import time
import unicodedata

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
           "XAGUSD": 0.04, "WTI": 0.06, "UKOIL": 0.06, "US500": 1.0, "USTECH": 3.0, "BTCUSD": 40.0}  # 参考（売買なし）

QS = [2, 5, 10, 20]
YEARS = list(range(2008, 2026))
MIN_DAYS = 100
ZCRIT = 1.96
SPLIT_YEAR = 2017
NULL_B = 300
SEED = 20261009


# ----------------------------------------------------------------------------- 基本の道具
def z_against_null(obs, null_vals):
    v = np.asarray(null_vals, float); v = v[np.isfinite(v)]
    if len(v) < 10 or not np.isfinite(obs):
        return float("nan"), float("nan")
    sd = v.std(ddof=1)
    z = (obs - v.mean()) / sd if sd > 0 else float("nan")
    pct = float((v < obs).mean())
    return float(z), pct


def lm_variance_ratio(R, q):
    """Lo–MacKinlay の分散比と不均一分散に頑健な z*。R: (B, T) の対数リターン行列（各行が 1 系列）。
    返り値: VR (B,), zstar (B,)。"""
    R = np.asarray(R, float)
    if R.ndim == 1:
        R = R[None, :]
    B, T = R.shape
    if T < 3 * q:
        return np.full(B, np.nan), np.full(B, np.nan)
    mu = R.mean(axis=1, keepdims=True)
    d = R - mu
    s2a = (d ** 2).sum(axis=1) / (T - 1)
    cs = np.cumsum(R, axis=1)
    cs = np.concatenate([np.zeros((B, 1)), cs], axis=1)
    rq = cs[:, q:] - cs[:, :-q]                       # 長さ T−q+1 の重なりあり q 日リターン
    m = q * (T - q + 1) * (1.0 - q / T)
    s2c = ((rq - q * mu) ** 2).sum(axis=1) / m
    vr = s2c / s2a
    d2 = d ** 2
    S = d2.sum(axis=1)
    theta = np.zeros(B)
    for j in range(1, q):
        delta = (d2[:, j:] * d2[:, :-j]).sum(axis=1) / (S ** 2)
        theta += (2.0 * (q - j) / q) ** 2 * delta
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (vr - 1.0) / np.sqrt(theta)
    return vr, z


# ----------------------------------------------------------------------------- データ
def load_daily(sym):
    f = os.path.join(DATA_DIR, f"data_{sym}_D1_fromH1.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f, parse_dates=["time"])
    d = d[(d.high > d.low) & (d.close > 0)].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return d


def synthetic_series(syms):
    """合成: AR(1) の対数リターン（φ を銘柄ごとに変える）。経路の確認だけが目的。"""
    g = np.random.default_rng(1)
    dates = pd.bdate_range("2008-02-01", "2026-07-14")
    out = {}
    for k, sym in enumerate(syms):
        phi = -0.1 + 0.3 * (k / (len(syms) - 1))
        e = g.normal(0, 0.006, len(dates)); r = np.zeros(len(dates))
        for i in range(1, len(dates)):
            r[i] = phi * r[i - 1] + e[i]
        base = {"USDJPY": 110, "EURJPY": 130, "GBPJPY": 150, "XAUUSD": 1500, "XAGUSD": 20, "WTI": 60, "UKOIL": 65,
                "US500": 3000, "USTECH": 10000, "BTCUSD": 20000}.get(sym, 1.2)
        out[sym] = (dates.values, base * np.exp(np.cumsum(r)))
    return out


# ----------------------------------------------------------------------------- セルの計算
def year_returns(t, c):
    """{year: r} 暦年ごとの日次対数リターン（MIN_DAYS 以上の年だけ）。"""
    r = np.zeros(len(c)); r[1:] = np.log(c[1:] / c[:-1])
    yr = pd.DatetimeIndex(t).year.values
    out = {}
    for y in YEARS:
        idx = np.flatnonzero(yr == y); idx = idx[idx >= 1]
        if len(idx) >= MIN_DAYS:
            out[y] = r[idx]
    return out


def cell_matrix(series, B, rng):
    """観測と帰無の、(銘柄, 年) ごとの VR・z* を q 別に出す。
    返り値: obs 表 (DataFrame)、null: dict key=(sym,year) → VR (B,4), Z (B,4)。"""
    rows = []; null = {}
    for sym, (t, c) in series.items():
        yrs = year_returns(t, c)
        for y, r in yrs.items():
            T = len(r)
            # 観測
            vr_o = []; z_o = []
            for q in QS:
                v, z = lm_variance_ratio(r, q); vr_o.append(float(v[0])); z_o.append(float(z[0]))
            rows.append(dict(sym=sym, year=y, n_days=T, **{f"VR{q}": vr_o[i] for i, q in enumerate(QS)},
                             **{f"z{q}": z_o[i] for i, q in enumerate(QS)}))
            # 帰無: 年内の並べ替え B 回（行列で一括）
            if B > 0:
                P = np.empty((B, T), dtype=np.int64)
                for b in range(B):
                    P[b] = rng.permutation(T)
                R = r[P]
                VRn = np.empty((B, len(QS))); Zn = np.empty((B, len(QS)))
                for i, q in enumerate(QS):
                    VRn[:, i], Zn[:, i] = lm_variance_ratio(R, q)
                null[(sym, y)] = (VRn, Zn)
    return pd.DataFrame(rows), null


def shares_from(VR, Z):
    """VR, Z: (n_cells, 4)。(a) 有意の数が 1〜3 の割合、(b) 符号が割れる割合、有意の数の分布。"""
    sig = np.abs(Z) >= ZCRIT
    nsig = sig.sum(axis=1)
    a = float(((nsig >= 1) & (nsig <= 3)).mean()) if len(nsig) else float("nan")
    pos = VR > 1.0
    b = float((pos.any(axis=1) & (~pos).any(axis=1)).mean()) if len(nsig) else float("nan")
    any_sig = float((nsig >= 1).mean()) if len(nsig) else float("nan")
    all_sig = float((nsig == 4).mean()) if len(nsig) else float("nan")
    dist = {int(k): int((nsig == k).sum()) for k in range(5)}
    return a, b, any_sig, all_sig, dist


def conclusion_code(VR, Z):
    """有意+ = 1、有意− = −1、非有意 = 0。"""
    sig = np.abs(Z) >= ZCRIT
    return np.where(sig, np.where(VR > 1.0, 1, -1), 0)


def transitions(obs):
    """(c) 同じ銘柄・同じ q で隣り合う年の結論が変わる割合（全セルで）。"""
    n_change = 0; n_pairs = 0; n_change_any = 0; n_pairs_any = 0
    for sym, g in obs.groupby("sym"):
        g = g.sort_values("year")
        yrs = g.year.values
        VR = g[[f"VR{q}" for q in QS]].values; Z = g[[f"z{q}" for q in QS]].values
        code = conclusion_code(VR, Z); any_sig = (np.abs(Z) >= ZCRIT).any(axis=1)
        for i in range(1, len(yrs)):
            if yrs[i] != yrs[i - 1] + 1:
                continue
            n_change += int((code[i] != code[i - 1]).sum()); n_pairs += len(QS)
            n_change_any += int(any_sig[i] != any_sig[i - 1]); n_pairs_any += 1
    return dict(c_share_conclusion_change=(n_change / n_pairs if n_pairs else float("nan")),
                c_share_anysig_change=(n_change_any / n_pairs_any if n_pairs_any else float("nan")),
                n_year_pairs=n_pairs_any)


def evaluate(obs, null, B):
    groups = {"全15": SYMS, "FX8": FX8, "トレンド7": TREND7}
    periods = {"前半": lambda y: y < SPLIT_YEAR, "後半": lambda y: y >= SPLIT_YEAR, "全期間": lambda y: True}
    res = {}
    for gname, syms in groups.items():
        for per, f in periods.items():
            g = obs[obs.sym.isin(syms) & obs.year.map(f)]
            keys = list(zip(g.sym, g.year))
            VR = g[[f"VR{q}" for q in QS]].values; Z = g[[f"z{q}" for q in QS]].values
            a, b, any_s, all_s, dist = shares_from(VR, Z)
            r = dict(n_cells=int(len(g)), a_share_split_1to3=a, b_share_sign_split=b, share_any_sig=any_s,
                     share_all4_sig=all_s, nsig_distribution=dist,
                     share_sig_by_q={f"q{q}": float((np.abs(Z[:, i]) >= ZCRIT).mean()) if len(g) else float("nan")
                                     for i, q in enumerate(QS)},
                     share_vr_gt1_by_q={f"q{q}": float((VR[:, i] > 1).mean()) if len(g) else float("nan")
                                        for i, q in enumerate(QS)})
            r.update(transitions(g))
            if B > 0 and keys:
                na = np.empty(B); nb = np.empty(B); nany = np.empty(B)
                VRs = np.stack([null[k][0] for k in keys], axis=1)   # B × n_cells × 4
                Zs = np.stack([null[k][1] for k in keys], axis=1)
                for bb in range(B):
                    na[bb], nb[bb], nany[bb], _, _ = shares_from(VRs[bb], Zs[bb])
                r["null_a_mean"] = float(na.mean()); r["null_a_sd"] = float(na.std(ddof=1)) if B > 1 else float("nan")
                r["null_a_p975"] = float(np.percentile(na, 97.5)); r["null_a_p95"] = float(np.percentile(na, 95))
                r["null_b_mean"] = float(nb.mean()); r["null_b_p975"] = float(np.percentile(nb, 97.5))
                r["null_anysig_mean"] = float(nany.mean())
                r["a_z"], r["a_pct"] = z_against_null(a, na)
                r["b_z"], r["b_pct"] = z_against_null(b, nb)
                r["a_ratio_to_null"] = float(a / r["null_a_mean"]) if r["null_a_mean"] > 0 else float("nan")
            res[f"{gname}|{per}"] = r
    return res


def judge(res):
    r = res["全15|全期間"]
    a = r["a_share_split_1to3"]; na = r.get("null_a_mean", float("nan")); z = r.get("a_z", float("nan"))
    dep = bool(np.isfinite(a) and np.isfinite(na) and a >= 2.0 * na and a >= 0.30)
    indist = bool(np.isfinite(z) and z < 2.0)
    verdict = ("結論は設定依存（Alahmadi の懸念を支持）" if dep else
               "設定依存は偽陽性の水準" if indist else "未確定")
    return dict(a_obs=a, a_null_mean=na, a_ratio=r.get("a_ratio_to_null"), a_z=z,
                cond_ratio_ge2_and_a_ge30pct=dep, cond_indistinguishable_z_lt2=indist,
                b_obs=r["b_share_sign_split"], b_null_mean=r.get("null_b_mean"), b_z=r.get("b_z"),
                c_obs=r["c_share_conclusion_change"], verdict=verdict,
                note="事前固定の規則で機械的に付けた判定（全15×全期間の (a)）。(c) と群別・期間別は記述。"
                     "解釈（確定／ノイズ／未確定）は実行者が記録する。")


def make_plot(res, path):
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
        keys = [k for k in res if k.endswith("|全期間") or k.endswith("|前半") or k.endswith("|後半")]
        fig, ax = plt.subplots(figsize=(10, 4.5))
        x = np.arange(len(keys))
        ax.bar(x - 0.2, [res[k]["a_share_split_1to3"] for k in keys], width=0.4, label="(a) 観測")
        ax.bar(x + 0.2, [res[k].get("null_a_mean", np.nan) for k in keys], width=0.4, label="(a) 帰無の平均")
        ax.axhline(0.30, lw=.6, c="gray", ls="--")
        ax.set_xticks(x); ax.set_xticklabels(keys, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("4つの q のうち有意が 1〜3 の割合"); ax.legend()
        fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
        return path
    except Exception as e:  # 図は任意
        return f"(図なし: {e})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=NULL_B, help="帰無の並べ替え回数")
    ap.add_argument("--smoke", action="store_true", help="合成データで経路確認（結果は results/smoke_ に保存）")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    missing = []
    if args.smoke:
        series = synthetic_series(SYMS); B = min(args.B, 10)
    else:
        series = {}
        for sym in SYMS:
            d = load_daily(sym)
            if d is None:
                missing.append(sym); continue
            series[sym] = (d.time.values, d.close.values.astype(float))
        B = args.B
    if not series:
        print("データがありません:", DATA_DIR); sys.exit(1)

    obs, null = cell_matrix(series, B, rng)
    res = evaluate(obs, null, B)
    verdict = judge(res)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "smoke_" if args.smoke else ""
    csv_path = os.path.join(OUT, f"{prefix}Q148_cells_{stamp}.csv"); obs.to_csv(csv_path, index=False)
    png_path = make_plot(res, os.path.join(OUT, f"{prefix}Q148_shares_{stamp}.png"))
    out = dict(
        queue_id="Q148", script=os.path.basename(__file__), run_at=stamp, smoke=bool(args.smoke),
        elapsed_sec=round(time.time() - t0, 1),
        settings=dict(QS=QS, YEARS=[YEARS[0], YEARS[-1]], MIN_DAYS=MIN_DAYS, ZCRIT=ZCRIT, SPLIT_YEAR=SPLIT_YEAR, NULL_B=B,
                      SEED=SEED, COST_RT=COST_RT, syms=list(series.keys()), missing_syms=missing, data_dir=DATA_DIR),
        data_span={s: dict(start=str(pd.Timestamp(series[s][0][0]).date()), end=str(pd.Timestamp(series[s][0][-1]).date()),
                           n=int(len(series[s][1]))) for s in series},
        n_syms=len(series), n_missing=len(missing), n_cells_sym_year=int(len(obs)), n_cells_sym_year_q=int(len(obs) * len(QS)),
        results=res, judgement=verdict,
        files=dict(cells_csv=csv_path, shares_png=png_path),
        multiple_comparisons=f"検定セル = {len(obs)} (銘柄×年) × {len(QS)} q = {len(obs)*len(QS)}。判定は割合 (a) の 1 本（帰無との比較）",
    )
    jpath = os.path.join(OUT, f"{prefix}Q148_result_{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else
                  (bool(o) if isinstance(o, np.bool_) else str(o)))

    print(f"[Q148] syms={len(series)} missing={missing} cells={len(obs)} B={B} smoke={args.smoke} elapsed={out['elapsed_sec']}s")
    for per in ("前半", "後半", "全期間"):
        for gname in ("全15", "FX8", "トレンド7"):
            r = res[f"{gname}|{per}"]
            print(f"  {per:3s} {gname:6s} n={r['n_cells']:3d}  (a)={r['a_share_split_1to3']:.3f} null={r.get('null_a_mean', float('nan')):.3f} "
                  f"z={r.get('a_z', float('nan')):+.2f}  (b)={r['b_share_sign_split']:.3f} null={r.get('null_b_mean', float('nan')):.3f}  "
                  f"(c)={r['c_share_conclusion_change']:.3f}  any_sig={r['share_any_sig']:.3f}")
    print("  判定(機械):", verdict["verdict"], f"| a={verdict['a_obs']:.3f} null={verdict['a_null_mean']:.3f} z={verdict['a_z']:+.2f}")
    print("  JSON:", jpath)


if __name__ == "__main__":
    main()
