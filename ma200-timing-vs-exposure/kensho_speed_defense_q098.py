# -*- coding: utf-8 -*-
"""
検証キュー Q098: 下落の速さで200日線とボラティリティターゲティングの勝ち負けが分かれるか・
併用は常に浅いか（約100年・株・Ken French日次＋SPY）
================================================================================

【出典】
- ブログ QuanterLab2026 b-1: 2000-2025年SPYの大型下落6回で「長期の弱気相場では200日線、
  急落ではボラティリティ・ターゲティングが有効」。b-3: 「併用が6回中5回で単独より浅い」。
  （標本6回のみ・著者の区分。Web保存の要約のみで原文の逐語引用はほぼなく、正確な日付・
  数値は確認不能。ブログは比較対象としてのみ言及し、論文の出口で根拠には使わない）
- 先行研究（構図の向きは既出）: Harvey et al. 2019 (JPM)・AQR 2022 "Should Your Portfolio
  Protection Work Fast or Slow?"。トレンドは長い下落に強く、速い道具は急落に強いという構図
  自体は既に示されている。本検証の新規性は「ボラティリティ・ターゲティングを急落側の道具と
  して検定」「併用の検定」「標本数を増やしたこと」のみで小さい。H2の方が情報量が多い。
- 計画: アイデア候補.md 2026-10-08 の2行目／接続ログ 2026-10-08「条件の穴（Q096）」の行
  （測る前の事前登録。以下は変更せずそのまま転記）。

【仮説・計画（測る前に固定）】
- データ: Ken French の市場ポートフォリオ日次（1926-07〜2025-12、配当込み・リスクフリー金利
  つき。市場リターン(%) = Mkt-RF + RF）。SPY日次2000-2025（局面検出の妥当性確認用）。
- 下落局面の定義: 買い持ち（市場ポートフォリオ、配当込み）の価格が、直前の最高値（それまで
  の累積リターンのランニングマックス）から15%以上下落した区間を1局面とする（感度分析で20%も）。
  局面の開始＝直前の最高値の日、終了＝その後に新高値を更新した日（またはデータ終了日）。
  局面内の最安値の日を「底」とする。
- 速さの定義: 局面の開始から底までの営業日数が63日以下＝「急落」、それ以外＝「長期」。
- ルール（各1通りだけ・事前固定）:
  - 200日線: 終値判定・翌日終値約定（Q097と同じ: sig_t = [P_t > MA200_t]、pos_s = sig_{s-2}）、
    片道コスト0.02%（感度0.1%）。
  - ボラティリティ・ターゲティング: 21日実現ボラ（直近21営業日の日次リターンの標本標準偏差
    ×sqrt(252)）で、レバレッジ = min(1.0, 0.15/実現ボラ年率) を毎日計算、上限1倍（残りは
    キャッシュ）。日 t のレバレッジは t-1 までのリターンで計算した実現ボラを使う（先読み厳禁）。
    売買コストは片道0.02%（毎日の目標レバレッジの変化分に課す。感度0.1%）。
  - 併用: 200日線の0/1シグナル × ボラ・ターゲティングのレバレッジ。
- 測る指標: 各局面内の各ルールの最大下落（局面内最大ドローダウン）。
- H1（2×2のFisherの正確検定）: 速さ（急落/長期）×「局面内最大下落で浅かったのは
  200日線かVTか（同値は除外して別途記録）」。p<0.10 かつ方向が「急落→VT優位、
  長期→200日線優位」なら支持。方向が逆、または p>=0.10 なら棄却。
- H2（符号検定）: 併用の局面内最大下落が単独2ルールの浅い方より浅い局面の割合を符号検定。
  過半数に届かなければ「併用が常に有利」を棄却。
- 未確定の条件: 急落・長期のどちらかの群が4局面未満なら未確定（H1は計算しても未確定と明記）。
- 先行して: SPY 2000-2025（Close主、Adj Close参考）で同じ局面検出を走らせ、件数・期間・
  下落幅・分類を出す（ブログの「6回」との厳密な再現ではなく、検出ロジックの妥当性確認）。

（実装上の決め事 ※事前ルールの変更ではなく、文言の機械化。測る前に決めた）
- 局面内MDDの窓: 「開始（最高値の日の終値）〜局面終了日」で統一（主）。開始〜底の窓は参考
  として併記するのみ（判定に使わない）。各ルールの資産は開始日の終値で1に正規化し、開始日
  翌日〜終了日のリターンで計算。買い持ちの局面内MDD＝局面の下落幅になることを検算する。
- 新高値の更新: 直前の最高値を厳密に上回った（>）日。
- 営業日数: 開始日と底の日の間の行数差（データの日次行=営業日）。
- キャッシュ部分: Ken French は RF を受け取る（Q097と同じ）。SPY はキャッシュ0%。
- コスト: 各ルールのポジション（0〜1）の日々の変化 |Δpos| × 片道コストを当日リターンから
  引く（200日線は0/1、VTはレバレッジ、併用は積の変化）。VTのドリフト分の戻しは計上しない
  （計画どおり「目標レバレッジの変化分」に課す）。
- 約定の時点: 計画の文言どおり、200日線は翌日終値約定（pos_s=sig_{s-2}）、VTは t-1 までの
  リターンでレバレッジを決め日 t のリターンに適用（= t-1 終値で約定）。両者の約定遅れは
  異なる（VT の方が1日速い）。これは計画の記述そのままで、変更しない。
- 3ルールが全て定義される日（200日MAとVTが両方定義）から評価。局面の窓（開始翌日〜終了）が
  評価期間に完全に入らない局面は除外し、件数を記録する。
- 同値: |MDD_200日線 − MDD_VT| < 1e-12 を同値として H1 の表から除外し別途記録。
  H2 も同様に同値は除外（件数記録）。
- Fisher: 両側p（主）で判定。予測方向の片側pも併記。scipy非依存で超幾何分布から計算。
- 符号検定: 片側（併用勝ちが多い向き） P(X>=k), X~Bin(n,0.5)。判定は事前登録どおり
  「勝ち割合が過半数（>0.5）に届かない→棄却」。届いた場合は p<0.10 かどうかと、
  「常に（全局面）」かどうかを併記。
- 主の判定は 閾値15%・コスト0.02%。感度: 15%/0.1%、20%/0.02%、20%/0.1%。

【捨てた案の数】
接続ログの時点で「通過（条件の穴として）」の判定が済んでおり、代替案の検討はそこで完了している
（他の速さの閾値・他のボラ目標の検討は行っていない。63営業日・年率15%は事前固定）。

【LLMの知識の締め切りとの関係】
この仮説はClaude（知識の締め切りおよそ2026-06）が2026-10-08にQuanterLabのブログと
Harvey et al. 2019・AQR 2022を踏まえて立てたもの。データ自体（1926-2025年）は締め切り以前の
期間を含むが、問いの立て方自体は締め切り後の情報に基づく。

【委託の確かめ方】
Opusサブエージェントがこの検証を行い（スクリプト作成・実行・JSON保存）、Sonnet本体が
計算結果JSON・スクリプトの該当箇所を直接確認する（結論の言葉だけでは確認済みとしない）。

【この環境について】
データはネットワークから取得せず、既に保存済みのファイルを読む。
    python3 kensho_speed_defense_q098.py [--ff /tmp/q097/F-F_Research_Data_Factors_daily.csv]
        [--spy /tmp/q097/spy_yf.csv] [--out results]
依存: numpy, pandas のみ（scipy不要）。欠損・重複は黙って埋めず停止（失敗パターン集）。

【実行時間の見積もり】
約26,000日 × 3ルール × 4条件。数秒。
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd

from kensho_ma200_timing_q097 import load_ff, load_spy, ma_positions  # Q097と同じ読み込み・200日線

VOL_WIN = 21
VOL_TARGET = 0.15
FAST_DAYS = 63
THRESHOLDS = [0.15, 0.20]          # 主 15%、感度 20%
COSTS = [0.0002, 0.001]            # 主 0.02%、感度 0.1%
MIN_GROUP = 4
ALPHA_H1 = 0.10
TIE_EPS = 1e-12
BLOG_N_EPISODES = 6                # 比較対象としてのみ（根拠には使わない）


# ---------------------------------------------------------------- ルール
def vt_leverage(r: pd.Series) -> pd.Series:
    """日 t のレバレッジ = min(1, 0.15 / (std(r_{t-21..t-1}, ddof=1)*sqrt(252)))。先読みなし。"""
    vol = r.rolling(VOL_WIN, min_periods=VOL_WIN).std(ddof=1).shift(1) * math.sqrt(252)
    return np.minimum(1.0, VOL_TARGET / vol).where(vol.notna())


def rule_returns(pos, rm, rf, cost):
    """pos: 0〜1。キャッシュ部分は rf。|Δpos|×片道コストを当日に引く（初日はΔ=0）。"""
    dpos = np.abs(np.diff(pos, prepend=pos[:1]))
    return pos * rm + (1 - pos) * rf - cost * dpos


def mdd(r):
    if len(r) == 0:
        return 0.0
    w = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.maximum(w, 1.0))   # 開始日の資産1をピークに含める
    return float((w / peak - 1.0).min())


# ---------------------------------------------------------------- 局面検出
def detect_episodes(wealth: np.ndarray, thr: float):
    """開始=直前の最高値の日、終了=その最高値を厳密に上回った日（なければ最終日・ongoing）。
    その間の最安値が開始値から thr 以上下落していれば1局面。インデックスで返す。"""
    eps = []
    pk = 0
    n = len(wealth)
    for i in range(1, n + 1):
        if i == n or wealth[i] > wealth[pk]:
            if i - pk > 1:
                seg = wealth[pk + 1:i]
                j = int(np.argmin(seg)) + pk + 1
                depth = wealth[j] / wealth[pk] - 1.0
                if depth <= -thr:
                    eps.append({"i_start": pk, "i_trough": j,
                                "i_end": (i if i < n else n - 1),
                                "ongoing_at_data_end": i == n, "depth": float(depth)})
            pk = i
    return eps


def describe(eps, dates):
    out = []
    for e in eps:
        d = dict(e)
        d["start"] = str(dates[e["i_start"]].date())
        d["trough"] = str(dates[e["i_trough"]].date())
        d["end"] = str(dates[e["i_end"]].date())
        d["days_peak_to_trough"] = int(e["i_trough"] - e["i_start"])
        d["days_peak_to_end"] = int(e["i_end"] - e["i_start"])
        d["speed"] = "急落" if d["days_peak_to_trough"] <= FAST_DAYS else "長期"
        out.append(d)
    return out


# ---------------------------------------------------------------- 検定
def fisher_exact(a, b, c, d):
    """[[a,b],[c,d]]。両側p（P(x)<=P(obs)の和）と片側p（P(X>=a), P(X<=a)）。"""
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2
    den = math.comb(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    P = {x: math.comb(r1, x) * math.comb(r2, c1 - x) / den for x in range(lo, hi + 1)}
    p_obs = P[a]
    two = sum(p for p in P.values() if p <= p_obs * (1 + 1e-7))
    return {"p_two_sided": min(1.0, two),
            "p_greater_a": min(1.0, sum(P[x] for x in P if x >= a)),
            "p_less_a": min(1.0, sum(P[x] for x in P if x <= a)),
            "odds_ratio_sample": (a * d / (b * c)) if b * c > 0 else (float("inf") if a * d > 0 else float("nan"))}


def sign_test(k, n):
    if n == 0:
        return float("nan")
    return float(sum(math.comb(n, x) for x in range(k, n + 1)) / 2 ** n)


# ---------------------------------------------------------------- 本体
def evaluate(eps_desc, rm, rf, positions, valid, cost):
    """各局面で3ルール＋買い持ちの局面内MDD（主: 開始〜終了、参考: 開始〜底）。"""
    rets = {k: rule_returns(np.nan_to_num(p), rm, rf, cost) for k, p in positions.items()}
    rows, excluded = [], []
    for e in eps_desc:
        s, t, en = e["i_start"], e["i_trough"], e["i_end"]
        if not valid[s + 1:en + 1].all():
            excluded.append({"start": e["start"], "reason": "局面の窓が3ルールの評価期間外（ウォームアップ前）"})
            continue
        row = {k: e[k] for k in ["start", "trough", "end", "ongoing_at_data_end", "depth",
                                 "days_peak_to_trough", "days_peak_to_end", "speed"]}
        row["mdd_start_to_end"] = {"buy_and_hold": mdd(rm[s + 1:en + 1])}
        row["mdd_start_to_trough_reference"] = {"buy_and_hold": mdd(rm[s + 1:t + 1])}
        for k, r in rets.items():
            row["mdd_start_to_end"][k] = mdd(r[s + 1:en + 1])
            row["mdd_start_to_trough_reference"][k] = mdd(r[s + 1:t + 1])
        for k, p in positions.items():
            row.setdefault("mean_exposure_in_episode", {})[k] = float(np.nanmean(p[s + 1:en + 1]))
        m = row["mdd_start_to_end"]
        diff = m["ma200"] - m["vol_target"]          # 正なら200日線の方が浅い
        row["h1_shallower"] = "tie" if abs(diff) < TIE_EPS else ("ma200" if diff > 0 else "vol_target")
        best_single = max(m["ma200"], m["vol_target"])
        d2 = m["combined"] - best_single
        row["h2_combined_vs_best_single"] = "tie" if abs(d2) < TIE_EPS else ("combined_shallower" if d2 > 0 else "combined_not_shallower")
        rows.append(row)
    return rows, excluded


def judge(rows):
    fast = [r for r in rows if r["speed"] == "急落"]
    long_ = [r for r in rows if r["speed"] == "長期"]
    tab = {"急落": {"ma200": 0, "vol_target": 0, "tie": 0}, "長期": {"ma200": 0, "vol_target": 0, "tie": 0}}
    for r in rows:
        tab[r["speed"]][r["h1_shallower"]] += 1
    a, b = tab["急落"]["vol_target"], tab["急落"]["ma200"]
    c, d = tab["長期"]["vol_target"], tab["長期"]["ma200"]
    h1 = {"table_rows_speed_cols_shallower_rule": tab,
          "fisher_layout": "[[急落&VT浅い a, 急落&200日線浅い b],[長期&VT浅い c, 長期&200日線浅い d]]",
          "a_b_c_d": [a, b, c, d],
          "n_fast_episodes": len(fast), "n_long_episodes": len(long_)}
    if a + b + c + d > 0:
        fe = fisher_exact(a, b, c, d)
        h1.update(fe)
        fr_f = a / (a + b) if a + b else float("nan")
        fr_l = c / (c + d) if c + d else float("nan")
        h1["frac_vt_shallower_fast"] = fr_f
        h1["frac_vt_shallower_long"] = fr_l
        pred_dir = (a + b > 0 and c + d > 0 and fr_f > fr_l)
        h1["direction_matches_prediction"] = bool(pred_dir)
        h1["p_one_sided_predicted_direction"] = fe["p_greater_a"]
    undetermined = len(fast) < MIN_GROUP or len(long_) < MIN_GROUP
    if undetermined:
        h1["judgment"] = f"未確定（急落{len(fast)}・長期{len(long_)}局面。どちらかが{MIN_GROUP}未満）"
    elif h1.get("p_two_sided", 1.0) < ALPHA_H1 and h1.get("direction_matches_prediction"):
        h1["judgment"] = "支持"
    else:
        h1["judgment"] = "棄却"
    wins = sum(r["h2_combined_vs_best_single"] == "combined_shallower" for r in rows)
    ties = sum(r["h2_combined_vs_best_single"] == "tie" for r in rows)
    n = len(rows) - ties
    frac = wins / n if n else float("nan")
    h2 = {"combined_shallower_than_best_single": wins, "n_non_tie": n, "ties": ties,
          "frac": frac, "p_sign_test_one_sided": sign_test(wins, n),
          "always_all_episodes": bool(n > 0 and wins == n),
          "by_speed": {sp: {"wins": sum(r["h2_combined_vs_best_single"] == "combined_shallower" for r in rows if r["speed"] == sp),
                            "n": sum(r["h2_combined_vs_best_single"] != "tie" for r in rows if r["speed"] == sp)}
                       for sp in ["急落", "長期"]},
          "combined_shallower_than_ma200": sum(r["mdd_start_to_end"]["combined"] > r["mdd_start_to_end"]["ma200"] + TIE_EPS for r in rows),
          "combined_shallower_than_vol_target": sum(r["mdd_start_to_end"]["combined"] > r["mdd_start_to_end"]["vol_target"] + TIE_EPS for r in rows),
          "n_episodes": len(rows)}
    if n == 0:
        h2["judgment"] = "未確定（局面なし）"
    elif not frac > 0.5:
        h2["judgment"] = "棄却（併用が単独の良い方より浅い局面が過半数に届かない）"
    else:
        h2["judgment"] = ("過半数に届いた（「常に有利」の棄却なし）" +
                          ("・符号検定 p<0.10" if h2["p_sign_test_one_sided"] < 0.10 else "・符号検定 p>=0.10") +
                          ("・全局面で勝ち" if h2["always_all_episodes"] else "・ただし全局面ではない"))
    return h1, h2


def run_market(rm, rf, dates, price, label):
    lev = vt_leverage(pd.Series(rm, index=dates)).to_numpy()
    ma = ma_positions(pd.Series(price, index=dates)).to_numpy()
    positions = {"ma200": ma, "vol_target": lev, "combined": ma * lev}
    valid = ~np.isnan(ma) & ~np.isnan(lev)
    out = {"eval_start_first_valid_day": str(dates[np.argmax(valid)].date()),
           "vt_leverage_summary": {"mean": float(np.nanmean(lev)), "frac_days_lev_eq_1": float(np.nanmean(lev[valid] >= 1.0 - 1e-15)),
                                   "min": float(np.nanmin(lev))},
           "ma200_mean_exposure": float(np.nanmean(ma[valid])),
           "combined_mean_exposure": float(np.nanmean((ma * lev)[valid])),
           "by_threshold": {}}
    for thr in THRESHOLDS:
        eps = describe(detect_episodes(price, thr), dates)
        blk = {"n_episodes_detected": len(eps),
               "n_fast": sum(e["speed"] == "急落" for e in eps),
               "n_long": sum(e["speed"] == "長期" for e in eps),
               "by_cost": {}}
        for c in COSTS:
            rows, excl = evaluate(eps, rm, rf, positions, valid, c)
            h1, h2 = judge(rows)
            chk = max(abs(r["mdd_start_to_end"]["buy_and_hold"] - r["depth"]) for r in rows) if rows else None
            blk["by_cost"][str(c)] = {"n_episodes_evaluated": len(rows), "excluded": excl,
                                      "check_max_abs_diff_bh_mdd_vs_depth": chk,
                                      "H1": h1, "H2": h2, "episodes": rows}
        out["by_threshold"][str(thr)] = blk
    return out


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--ff", default="/tmp/q097/F-F_Research_Data_Factors_daily.csv")
    ap.add_argument("--spy", default="/tmp/q097/spy_yf.csv")
    ap.add_argument("--out", default=os.path.join(here, "results"))
    a = ap.parse_args()
    t0 = datetime.now()

    ff, ff_chk = load_ff(a.ff)
    spy, spy_chk = load_spy(a.spy)
    rm = ((ff["Mkt-RF"] + ff["RF"]) / 100.0).to_numpy()
    rf = (ff["RF"] / 100.0).to_numpy()
    price = np.cumprod(1 + rm)              # 初日のリターン込みの累積（初日終値=1+r_0）
    kf = run_market(rm, rf, ff.index, price, "ken_french")

    spy_out = {"note": "局面検出ロジックの妥当性確認（ブログの6回の厳密な再現ではない。ブログは"
                       "原文の逐語引用がなく正確な日付・分類基準が確認できないため数値再現は不可能）。"
                       "SPYはキャッシュ0%、主は Close（配当なし）、Adj Close は参考。",
               "blog_n_episodes_for_comparison_only": BLOG_N_EPISODES}
    for col in ["close", "adj_close"]:
        px = spy[col].to_numpy()
        r = np.concatenate([[0.0], px[1:] / px[:-1] - 1.0])   # 初日リターンは0（価格の基準日）
        spy_out[col] = run_market(r, np.zeros_like(r), spy.index, px / px[0], "spy_" + col)

    main_key = kf["by_threshold"]["0.15"]["by_cost"]["0.0002"]
    result = {
        "queue_id": "Q098", "run_at": t0.isoformat(timespec="seconds"),
        "params": {"vol_win": VOL_WIN, "vol_target": VOL_TARGET, "fast_days_max": FAST_DAYS,
                   "thresholds": THRESHOLDS, "costs_one_way": COSTS, "min_group": MIN_GROUP,
                   "alpha_h1": ALPHA_H1, "episode_mdd_window_main": "開始（最高値の日）〜局面終了日",
                   "ma_exec": "pos_s = sig_{s-2}（翌日終値約定）",
                   "vt_exec": "lev_t = min(1, 0.15/vol_{t-21..t-1})"},
        "data_check": {"ken_french": ff_chk, "spy": spy_chk},
        "ken_french": kf,
        "spy_episode_detection_check": spy_out,
        "judgment_main_thr0.15_cost0.0002": {"H1": main_key["H1"]["judgment"], "H2": main_key["H2"]["judgment"]},
        "judgment_sensitivity": {f"thr{t}_cost{c}": {"H1": kf["by_threshold"][str(t)]["by_cost"][str(c)]["H1"]["judgment"],
                                                     "H2": kf["by_threshold"][str(t)]["by_cost"][str(c)]["H2"]["judgment"]}
                                 for t in THRESHOLDS for c in COSTS},
        "novelty_note": "構図（トレンドは長い下落・速い道具は急落に強い）はHarvey et al. 2019・AQR 2022と同じ向きで既出。"
                        "H1が支持されても新規性は小さい（VTを急落側の道具として検定・併用の検定・標本数の拡大のみ）。"
                        "ブログの数値は比較対象としてのみ言及し根拠には使わない。",
    }
    result["elapsed_sec"] = (datetime.now() - t0).total_seconds()
    os.makedirs(a.out, exist_ok=True)
    fn = os.path.join(a.out, f"Q098_result_{t0.strftime('%Y%m%d_%H%M%S')}.json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(fn)
    print(json.dumps({k: result[k] for k in result if k.startswith("judgment")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
