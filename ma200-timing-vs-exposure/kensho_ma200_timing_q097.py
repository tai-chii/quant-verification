# -*- coding: utf-8 -*-
"""
検証キュー Q097: 200日線の下落の軽さはタイミングか露出の低さか（矛盾の解消・株・Ken French日次＋SPY）
================================================================================

【出典】
- 高橋2016・Sullivan1999: 移動平均の売買の合図に収益の予測力はない（運を除くと予測力なし）。
- ブログ QuanterLab2026 b-2（SPY全期間）: 200日線は最大下落を -56.5% → -25.7% に半減させる。
- 計画: 接続ログ 2026-10-08「矛盾（Q096）」の行・アイデア候補.md 2026-10-08 の1行目
  （測る前の事前登録。以下は変更せずそのまま転記）。

【仮説（測る前に固定）】
問い: 200日線が最大下落を軽くするのは**合図のタイミング**が効いているのか、それとも
**市場にいる平均時間（露出）が単に下がっただけ**か。

- データ:
  1. Ken French の市場ポートフォリオ日次（Mkt-RF, SMB, HML, RF）1926-07〜2025-12、
     配当込み・リスクフリー金利つき。市場リターン = Mkt-RF + RF。
  2. SPY 2000〜2025（価格のみ、ブログの数値 -25.7%/-56.5% の再現用）。
- シグナル/ルール: 200日移動平均（終値で判定：終値が200日MAより上なら翌日の終値でロング、
  下なら翌日の終値でキャッシュ、に約定）。片道コスト0.02%（感度分析で0.1%も）。
- 測る指標: 最大ドローダウン、日次リターンの下位5% CVaR。
- 比較対象（2つ）:
  ① 同じ平均露出の固定配分（現金比率 = 1 − 200日線ルールの平均露出。つまり
     「タイミングなしで同じだけ市場にいる」ベンチマーク）
  ② 合図の列を252日以上ずらした循環シフト（circular shift。露出の合計と切り替え回数を
     保ったまま、価格との対応だけを壊す。B=2000回のシフト幅をランダムに取る。
     シフト幅は252日以上、かつ系列長未満でランダムに選ぶ）
- 期間分割: 前半（1927〜1975）・後半（1976〜2025）で別々に計算。

【測る前に固定する棄却条件】
- 200日線の実際の最大ドローダウンが、循環シフトB=2000の最大ドローダウン分布の
  **下位5%パーセンタイルより浅い**（両半期とも）→「タイミングによる防御」= **支持**
- 両半期とも循環シフト分布の**下位10%パーセンタイルに入らない**→「露出が減っただけ」= **棄却**
- それ以外 → **未確定**
- 付帯条件: SPYでブログの-25.7%（全期間）が再現しなければ、データの違いを先に書いてから進める。

（実装上の読み方 ※事前ルールの変更ではなく、文言の機械化）:
「下位5%パーセンタイル」は最大ドローダウンの“深さ” |MDD| の分布で読む。すなわち
  支持 = 両半期とも  |MDD_実際| < 循環シフト |MDD| の5%点（＝シフトの95%より浅い）
  棄却 = 両半期とも  |MDD_実際| >= 循環シフト |MDD| の10%点（＝浅い側10%に入らない）
文字どおり「符号付きMDD（負の値）の5%点より浅い」と読むと、シフトの95%より“深い”だけで
支持になってしまい判定として意味を持たないため。念のため、文字どおりの読み方での判定と
百分位順位（シフトのうち実際以下の深さだったものの割合）も結果JSONに併記する。

【捨てた案の数】
この案自体は接続ログのとおり「通過」判定済みで、代替案の比較は接続ログの時点で完了している
（循環シフト法を無作為シグナル法として採用、のみ。他の代替は検討していない）。

【LLMの知識の締め切りとの関係】
この仮説はClaude（知識の締め切りおよそ2026-06）が2026-10-08にブログ記事（QuanterLab2026b-1,
b-2）と高橋2016・Sullivan1999を読んだ上で新たに立てたもの。検証対象のデータ（1926-2025年）
自体は締め切り以前の期間を含むが、問いの立て方自体は締め切り後の情報に基づく。

【委託の確かめ方】
Opusサブエージェントがこの検証を行い（スクリプト作成・実行・JSON保存）、Sonnet本体が
計算結果のJSON・スクリプトの該当箇所を直接確認する（サブエージェントの結論の言葉だけでは
確認済みとしない）。

【実装の細部（測る前に決めたもの）】
- 価格系列: Ken French は市場リターン（Mkt-RF+RF, %）を累積した配当込み指数。SPY は
  Adj Close（配当調整済み）と Close（純粋な価格）の両方で計算し、主は Close。
- 先読みなし: 日 t の終値で sig_t = [P_t > MA200_t] を決め、日 t+1 の終値で約定。
  よって日 s のリターンに対する保有 pos_s = sig_{s-2}。キャッシュ中はKen Frenchでは RF を
  受け取る（SPYはキャッシュ0%）。
- コスト: pos が変わった日のリターンから 片道コスト × |Δpos| を引く（0.02%, 感度0.1%）。
- 固定配分: 毎日ウェイト w（= 当該半期の200日線ルールの平均露出）に戻す。戻すときの売買量
  （ドリフト分）にも同じ片道コストを課す。
- 循環シフト: 半期ごとに、その半期内の pos 列を np.roll(pos, k)。k は [252, N) の一様整数
  （N = 半期の日数）。コストはシフト後の pos の変化に同様に課す。seed = 20261008。
  参考（判定には使わない）: k を [252, N-252] に限った版（後ろ向き252日未満のずれを除く）。
- 200日MAは1926-07-01からの全系列で計算し（ウォームアップに前の期間を使う、これは先読み
  ではない）、前半は pos が定義される最初の日から始める（開始日はJSONに記録）。
- 欠損の扱い: 欠損・重複があれば件数を表示し、黙って埋めない（失敗パターン集 2026-09-30）。

【この環境について】
データはネットワークから取得せず、既に保存済みのファイルを読む。
    python3 kensho_ma200_timing_q097.py [--ff /tmp/q097/F-F_Research_Data_Factors_daily.csv]
        [--spy /tmp/q097/spy_yf.csv] [--B 2000] [--out results]
依存: numpy, pandas のみ（scipy不要）。

【実行時間の見積もり】
1半期 約12,500日 × B=2000 × コスト2通り ≒ 5,000万要素の累積積。numpyで数十秒〜1分程度。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

MA_WINDOW = 200
COSTS = [0.0002, 0.001]          # 片道 0.02%（主）, 0.1%（感度）
MIN_SHIFT = 252
B_DEFAULT = 2000
RANDOM_SEED = 20261008
HALVES = {"first_1927_1975": ("1927-01-01", "1975-12-31"),
          "second_1976_2025": ("1976-01-01", "2025-12-31")}
FF_START, FF_END = "1926-07-01", "2025-12-31"
SPY_START, SPY_END = "2000-01-03", "2025-12-30"
BLOG_MA200_MDD = -0.257
BLOG_BH_MDD = -0.565


# ---------------------------------------------------------------- データ
def load_ff(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    hdr = next(i for i, l in enumerate(lines) if l.replace(" ", "").startswith(",Mkt-RF"))
    rows, end_line = [], None
    for i in range(hdr + 1, len(lines)):
        l = lines[i].strip()
        if not l or not l[:8].isdigit():
            end_line = i
            break
        rows.append(l.split(","))
    df = pd.DataFrame(rows, columns=["date", "Mkt-RF", "SMB", "HML", "RF"])
    raw_n = len(df)
    df["date"] = pd.to_datetime(df["date"].str.strip(), format="%Y%m%d", errors="coerce")
    for c in ["Mkt-RF", "SMB", "HML", "RF"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    chk = {
        "header_line_no": hdr + 1,
        "header_line": lines[hdr],
        "daily_section_end_line_no": (end_line + 1) if end_line is not None else None,
        "rows_in_daily_section": raw_n,
        "first_rows_raw": lines[hdr + 1:hdr + 4],
        "last_rows_raw": lines[hdr + raw_n - 2:hdr + raw_n + 1],
        "unparseable_dates": int(df["date"].isna().sum()),
        "nan_values": {c: int(df[c].isna().sum()) for c in ["Mkt-RF", "SMB", "HML", "RF"]},
        "missing_value_codes_-99.99": int((df[["Mkt-RF", "SMB", "HML", "RF"]] <= -99.99).sum().sum()),
        "duplicate_dates": int(df["date"].duplicated().sum()),
        "non_monotonic_dates": int((df["date"].diff().dt.days <= 0).sum()),
        "file_date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
    }
    in_rng = (df["date"] >= FF_START) & (df["date"] <= FF_END)
    chk["rows_outside_1926-07-01_2025-12-31_excluded"] = int((~in_rng).sum())
    df = df[in_rng].set_index("date")
    gaps = df.index.to_series().diff().dt.days
    big = gaps[gaps > 5]
    chk["gaps_over_5_calendar_days"] = [(str(d.date()), int(g)) for d, g in big.items()]
    chk["rows_used"] = len(df)
    chk["used_range"] = [str(df.index.min().date()), str(df.index.max().date())]
    if chk["unparseable_dates"] or sum(chk["nan_values"].values()) or chk["duplicate_dates"]:
        raise SystemExit(f"データに欠損/重複あり。黙って埋めずに停止: {chk}")
    return df, chk


def load_spy(path):
    s = pd.read_csv(path, header=[0, 1], index_col=0)
    s.index = pd.to_datetime(s.index, errors="coerce")
    chk = {"columns": [list(c) for c in s.columns], "rows_raw": len(s),
           "unparseable_dates": int(s.index.isna().sum())}
    s = s[s.index.notna()]
    out = pd.DataFrame({"adj_close": pd.to_numeric(s[("Adj Close", "SPY")], errors="coerce"),
                        "close": pd.to_numeric(s[("Close", "SPY")], errors="coerce")})
    chk["nan_values"] = {c: int(out[c].isna().sum()) for c in out}
    chk["nonpositive_prices"] = int((out <= 0).sum().sum())
    chk["duplicate_dates"] = int(out.index.duplicated().sum())
    chk["non_monotonic_dates"] = int((out.index.to_series().diff().dt.days <= 0).sum())
    in_rng = (out.index >= SPY_START) & (out.index <= SPY_END)
    chk["rows_outside_range_excluded"] = int((~in_rng).sum())
    out = out[in_rng]
    gaps = out.index.to_series().diff().dt.days
    chk["gaps_over_5_calendar_days"] = [(str(d.date()), int(g)) for d, g in gaps[gaps > 5].items()]
    chk["rows_used"] = len(out)
    chk["used_range"] = [str(out.index.min().date()), str(out.index.max().date())]
    chk["first_rows"] = out.head(2).reset_index().astype(str).values.tolist()
    chk["last_rows"] = out.tail(2).reset_index().astype(str).values.tolist()
    if sum(chk["nan_values"].values()) or chk["duplicate_dates"] or chk["nonpositive_prices"]:
        raise SystemExit(f"SPYに欠損/重複あり。黙って埋めずに停止: {chk}")
    return out, chk


# ---------------------------------------------------------------- 指標
def max_dd(r):
    """r: 日次リターン(小数)。2次元 (B, T) も可。最大ドローダウン（負の値）。"""
    w = np.cumprod(1.0 + r, axis=-1)
    peak = np.maximum.accumulate(np.maximum(w, 1.0), axis=-1)  # 初期資産1をピークに含める
    return (w / peak - 1.0).min(axis=-1)


def cvar5(r):
    r = np.sort(np.atleast_2d(r), axis=-1)
    k = int(np.ceil(0.05 * r.shape[-1]))
    v = r[..., :k].mean(axis=-1)
    return v if v.size > 1 else float(v[0])


def ann(r):
    return float(np.prod(1 + r) ** (252.0 / len(r)) - 1)


def strat_returns(pos, rm, rf, cost):
    """pos: 0/1（2次元可）。キャッシュ中は rf。pos が変わった日に cost×|Δpos| を引く。"""
    dpos = np.abs(np.diff(pos, axis=-1, prepend=pos[..., :1]))
    return pos * rm + (1 - pos) * rf - cost * dpos


def fixed_alloc_returns(w, rm, rf, cost):
    """毎日ウェイト w に戻す。戻すときのドリフト分の売買量にコストを課す。"""
    gross = w * rm + (1 - w) * rf
    w_drift = w * (1 + rm) / (1 + gross)
    turnover = np.abs(w_drift - w)              # 前日分の戻し（当日終値で実施）
    turnover = np.concatenate([[0.0], turnover[:-1]])
    return gross - cost * turnover


def ma_positions(price):
    """sig_t = [P_t > MA200_t]（t の終値で判定）→ t+1 の終値で約定 → pos_s = sig_{s-2}。"""
    ma = price.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    sig = (price > ma).astype(float).where(ma.notna())
    return sig.shift(2)


# ---------------------------------------------------------------- 本体
def evaluate_half(name, rm, rf, pos, B, rng, dates):
    N = len(pos)
    out = {"start": str(dates[0].date()), "end": str(dates[-1].date()), "n_days": int(N),
           "mean_exposure": float(pos.mean()),
           "n_switches": int(np.abs(np.diff(pos)).sum())}
    w = pos.mean()
    ks = rng.integers(MIN_SHIFT, N, size=B)               # 事前登録: [252, N)
    ks_alt = rng.integers(MIN_SHIFT, N - MIN_SHIFT + 1, size=B)  # 参考: [252, N-252]
    idx = (np.arange(N)[None, :] - ks[:, None]) % N        # np.roll(pos, k) と同じ
    idx_alt = (np.arange(N)[None, :] - ks_alt[:, None]) % N
    out["shift_k_summary"] = {"min": int(ks.min()), "max": int(ks.max()),
                              "n_k_gt_N_minus_252": int((ks > N - MIN_SHIFT).sum())}
    out["buy_and_hold"] = {"max_dd": float(max_dd(rm)), "cvar5": cvar5(rm), "ann_ret": ann(rm)}
    out["by_cost"] = {}
    for c in COSTS:
        r_s = strat_returns(pos, rm, rf, c)
        r_f = fixed_alloc_returns(w, rm, rf, c)
        res = {"ma200": {"max_dd": float(max_dd(r_s)), "cvar5": cvar5(r_s), "ann_ret": ann(r_s)},
               "fixed_alloc_same_exposure": {"weight": float(w), "max_dd": float(max_dd(r_f)),
                                             "cvar5": cvar5(r_f), "ann_ret": ann(r_f)}}
        for label, ix in [("circular_shift", idx), ("circular_shift_alt_k_le_N_minus_252", idx_alt)]:
            mdds, cvs = [], []
            for j in range(0, B, 250):                    # メモリ節約のため分割
                P = pos[ix[j:j + 250]]
                R = strat_returns(P, rm[None, :], rf[None, :], c)
                mdds.append(max_dd(R)); cvs.append(np.atleast_1d(cvar5(R)))
            mdds = np.concatenate(mdds); cvs = np.concatenate(cvs)
            depth = -mdds
            act_depth = -res["ma200"]["max_dd"]
            d = {"B": int(B),
                 "mdd_signed_percentiles": {f"p{q}": float(np.percentile(mdds, q)) for q in (1, 5, 10, 25, 50, 75, 90, 95, 99)},
                 "depth_p5": float(np.percentile(depth, 5)),     # 浅い側5%の境界
                 "depth_p10": float(np.percentile(depth, 10)),   # 浅い側10%の境界
                 "frac_shifts_shallower_or_equal_than_actual": float((depth <= act_depth).mean()),
                 "cvar5_percentiles": {f"p{q}": float(np.percentile(cvs, q)) for q in (5, 10, 50, 90, 95)},
                 "frac_shifts_cvar5_better_or_equal_than_actual": float((cvs >= res["ma200"]["cvar5"]).mean()),
                 "mean_switches_shifted": float(np.abs(np.diff(pos[ix[:200]], axis=1)).sum(axis=1).mean())}
            d["support_cond_depth_lt_p5"] = bool(act_depth < d["depth_p5"])
            d["in_shallow10_depth_lt_p10"] = bool(act_depth < d["depth_p10"])
            # 文字どおりの読み（符号付きMDDの5%/10%点）: 参考
            d["literal_signed_shallower_than_p5"] = bool(res["ma200"]["max_dd"] > d["mdd_signed_percentiles"]["p5"])
            d["literal_signed_shallower_than_p10"] = bool(res["ma200"]["max_dd"] > d["mdd_signed_percentiles"]["p10"])
            res[label] = d
        out["by_cost"][str(c)] = res
    return out


def judge(halves, cost_key, label="circular_shift"):
    sup = [h["by_cost"][cost_key][label]["support_cond_depth_lt_p5"] for h in halves.values()]
    in10 = [h["by_cost"][cost_key][label]["in_shallow10_depth_lt_p10"] for h in halves.values()]
    if all(sup):
        return "支持（タイミングによる防御）"
    if not any(in10):
        return "棄却（露出が減っただけ）"
    return "未確定"


def spy_block(spy):
    out = {"note": "価格のみの再現（SPYはキャッシュ0%、配当はAdj Close版でのみ反映）。"
                   "ブログの配当・金利・約定タイミングの扱いは不明なので差が出うる。"}
    for col in ["close", "adj_close"]:
        px = spy[col]
        r = px.pct_change().to_numpy()
        res = {"buy_and_hold_full_mdd": float(max_dd(r[1:]))}
        for lag_name, lag in [("next_day_close_exec_registered", 2), ("same_day_close_exec_reference", 1)]:
            ma = px.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
            sig = (px > ma).astype(float).where(ma.notna())
            pos = sig.shift(lag).to_numpy()
            ok = ~np.isnan(pos)
            rr, pp = r[ok], pos[ok]
            z = np.zeros_like(rr)
            sub = {"eval_start": str(px.index[ok][0].date()), "mean_exposure": float(pp.mean())}
            for c in [0.0] + COSTS:
                rs = strat_returns(pp, rr, z, c)
                sub[f"cost_{c}"] = {"max_dd": float(max_dd(rs)), "cvar5": cvar5(rs), "ann_ret": ann(rs)}
            sub["buy_and_hold_same_window_mdd"] = float(max_dd(rr))
            res[lag_name] = sub
        out[col] = res
    main = out["close"]["next_day_close_exec_registered"]["cost_0.0002"]["max_dd"]
    out["blog_ma200_mdd"] = BLOG_MA200_MDD
    out["blog_bh_mdd"] = BLOG_BH_MDD
    out["reproduced_within_2pt"] = bool(abs(main - BLOG_MA200_MDD) <= 0.02)
    return out


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--ff", default="/tmp/q097/F-F_Research_Data_Factors_daily.csv")
    ap.add_argument("--spy", default="/tmp/q097/spy_yf.csv")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--out", default=os.path.join(here, "results"))
    a = ap.parse_args()
    t0 = datetime.now()
    rng = np.random.default_rng(RANDOM_SEED)

    ff, ff_chk = load_ff(a.ff)
    spy, spy_chk = load_spy(a.spy)
    rm = (ff["Mkt-RF"] + ff["RF"]) / 100.0
    rf = ff["RF"] / 100.0
    price = (1 + rm).cumprod()
    pos = ma_positions(price)

    halves = {}
    for name, (s, e) in HALVES.items():
        m = (ff.index >= s) & (ff.index <= e) & pos.notna().to_numpy()
        halves[name] = evaluate_half(name, rm[m].to_numpy(), rf[m].to_numpy(),
                                     pos[m].to_numpy(), a.B, rng, ff.index[m])
    # 参考: 全期間（判定には使わない）
    m = pos.notna().to_numpy()
    full = {}
    for c in COSTS:
        rs = strat_returns(pos[m].to_numpy(), rm[m].to_numpy(), rf[m].to_numpy(), c)
        rfx = fixed_alloc_returns(pos[m].mean(), rm[m].to_numpy(), rf[m].to_numpy(), c)
        full[str(c)] = {"ma200_mdd": float(max_dd(rs)), "fixed_mdd": float(max_dd(rfx)),
                        "ma200_cvar5": cvar5(rs), "fixed_cvar5": cvar5(rfx)}
    full["bh_mdd"] = float(max_dd(rm[m].to_numpy()))
    full["mean_exposure"] = float(pos[m].mean())

    result = {
        "queue_id": "Q097", "run_at": t0.isoformat(timespec="seconds"),
        "seed": RANDOM_SEED, "B": a.B, "min_shift": MIN_SHIFT, "costs_one_way": COSTS,
        "data_check": {"ken_french": ff_chk, "spy": spy_chk},
        "spy_reproduction": spy_block(spy),
        "halves": halves,
        "full_period_reference_not_for_judgment": full,
        "judgment_main_cost_0.0002": judge(halves, "0.0002"),
        "judgment_sensitivity_cost_0.001": judge(halves, "0.001"),
        "judgment_reference_alt_k_cost_0.0002": judge(halves, "0.0002", "circular_shift_alt_k_le_N_minus_252"),
        "judgment_reading_note": "支持=両半期で |MDD実際| < シフト|MDD|の5%点、棄却=両半期で |MDD実際| >= 10%点。"
                                 "文字どおり（符号付き）の読みは literal_* フラグを参照。",
    }
    result["elapsed_sec"] = (datetime.now() - t0).total_seconds()
    os.makedirs(a.out, exist_ok=True)
    fn = os.path.join(a.out, f"Q097_result_{t0.strftime('%Y%m%d_%H%M%S')}_B{a.B}.json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(fn)
    print(json.dumps({k: result[k] for k in result if k.startswith("judgment")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
