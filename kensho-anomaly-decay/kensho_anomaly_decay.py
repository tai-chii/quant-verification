#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kensho_anomaly_decay.py (2026-10-05) 為替の日中・曜日のアノマリーは公表後にどれだけ減ったか（検証キュー Q063）

=== 事前に固定した計画（3つの比を計算する前に書いた。各アノマリーの期間別の値は Q051・Q056・五十日の追試で既知） ===
出どころ: アイデア候補 2026-10-05「為替の日中・曜日のアノマリーは公表後にどれだけ減ったか」。比べる相手は
          株の人気8因子（Arnott ほか 2019 の引用: 年5.8%→2.4%＝比 約0.41）と、月次の通貨戦略（Bartram ほか 2018、未読・アイデア候補の記載で比 約0.3）。
データ  : Dukascopy H1（vault/40_市場/FX/システムトレード/data_*_H1_dukascopy.csv を読むだけ。書き換えない）。
効果の定義（各追試のスクリプトと同じ。1つの数にする）:
  A 五十日  : USDJPY、日本の営業日の火〜金、JST 3:00→10:00 の対数リターン（bp）の「五十日の平均 − 対照の平均」（kensho_gotobi.py と同じ日の定義）
  B フィキシング: ドル建て6通貨の等しい重みの外貨ポートフォリオで、日ごとの「post-T − pre-T」（東京のV字の往復の大きさ、bp）の平均（kensho_fix_vshape.py と同じ窓）
  C 週末    : 主要6通貨、週末の窓の上位・下位5%（直前260週・移動）の逆張り、月曜始値→金曜終値のコスト前リターン（bp）の平均（kensho_weekend_overreaction.py と同じ）
              ※ 比を出すためコスト前を使う（コストは定数で、引くと比の意味が変わるため）
公表日（最初の公開版。翌月から公表後）:
  A arXiv 2301.13204v1 = 2023-01-29 → 公表後 2023-02-01〜2026-06-30
  B AEA 2020 年次大会の予稿（2020-01、aeaweb.org の preliminary program に掲載）→ 公表後 2020-02-01〜2026-06-30（それより前の版があった可能性は確認できていない）
  C 掲載誌 2016-12（Q051 と同じ。それより前の作業論文の版は確認できていない）→ 公表後 2017-01-01〜2026-06-30
公表前（元の論文の標本と自分のデータが重なる期間）:
  A 2018-01-01〜2020-12-31（論文の標本）  B 2008-01-01〜2019-12-31（論文 1999〜2019 のうちデータがある分）
  C 2013-01-01〜2014-05-31（論文 2002〜2014-05 のうち、直前260週の閾値が計算できる分。短いことは承知の上）
比      : 公表後の効果 ÷ 公表前の効果。95%区間は週ブロックのブートストラップ（公表前・後を別々に、暦週を単位に復元抽出、B=2000、乱数の種 20261005、パーセンタイル）。
          3つの平均の比は、同じ回のブートストラップの3つの比の平均で区間を出す。
          公表前の点推定が0以下のアノマリーは比を定義できないとして平均から除く（＝区間の幅>1と同じ扱い）。
判定（アイデア候補の棄却条件をそのまま使う）:
  ① 3つとも比の95%区間の幅が1を超える（または定義できない）→「判定不能」で止める。
  ② そうでなければ、3つの平均の比の95%区間で: 0.3 を含む →「日中・曜日でも月次と同じ程度に減る」、
     上限 < 0.3 →「月次より大きく減る」、下限 > 0.3 →「月次より減りが小さい」。株の 0.41 との関係も同じ形で書く（副）。
  個別の比は参考（判定に使わない）。多重比較: 主の判定は1本（平均の比）。個別3本は参考扱い。
決定的（乱数は種を固定）。先読みなし。
出力    : output/kensho_anomaly_decay.csv（期間別の効果と比）、_boot.csv（ブートストラップの比）
"""
import os, sys, math, importlib.util, datetime as dt
import numpy as np, pandas as pd, jpholiday

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "output")
SYS = os.environ["FX_SYS_DIR"]   # vault/40_市場/FX/システムトレード（NFD の名前のため実行時に渡す）
B = 2000; SEED = 20261005

def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SYS, name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.BASE = SYS; return m

# ---- A 五十日（kensho_gotobi.py の日の定義をそのまま写す） ----
def gotobi_days():
    d = pd.read_csv(os.path.join(SYS, "data_USDJPY_H1_dukascopy.csv"), parse_dates=["time"]); d = d[d.volume > 0].set_index("time")
    op = d.open
    def biz(x): return x.weekday() < 5 and not jpholiday.is_holiday(x) and not ((x.month == 12 and x.day == 31) or (x.month == 1 and x.day <= 3))
    days = pd.date_range("2008-02-02", "2026-06-30", freq="D").date
    goto = set()
    for x in days:
        if x.day % 5 == 0:
            y = x
            while not biz(y): y -= dt.timedelta(days=1)
            goto.add(y)
    rows = []
    for x in days:
        if not biz(x) or x.weekday() == 0: continue
        ts = pd.Timestamp(x); a = ts - pd.Timedelta(hours=6); b = ts + pd.Timedelta(hours=1)
        if a not in op.index or b not in op.index: continue
        rows.append(dict(date=ts, g=x in goto, v=math.log(op[b] / op[a]) * 1e4))
    return pd.DataFrame(rows)

def fixing_days():
    m = load("kensho_fix_vshape")
    D = {p: m.daily_windows(p) for p in m.PAIRS}
    port = (sum(D[p] for p in m.PAIRS) / len(m.PAIRS)).dropna()
    return pd.DataFrame(dict(date=port.index, v=(port["post-T"] - port["pre-T"]).values))

def weekend_trades():
    m = load("kensho_weekend_overreaction")
    T = pd.concat([m.signals(m.weeks(p), "rolling") for p in m.PAIRS], ignore_index=True)
    return pd.DataFrame(dict(date=T.t0.values, v=T.gross.values * 1e4))

def week_table(df, a, b, two=False):
    s = df[(df.date >= a) & (df.date < b)].copy(); s["wk"] = pd.to_datetime(s.date).dt.to_period("W").astype(str)
    if two:
        g = s.groupby("wk").apply(lambda x: pd.Series(dict(s1=x.v[x.g].sum(), n1=x.g.sum(), s0=x.v[~x.g].sum(), n0=(~x.g).sum())))
    else:
        g = s.groupby("wk").v.agg(s1="sum", n1="count")
    return g.astype(float).values, len(s)

def effect(W, two):
    if two: return W[:, 0].sum() / W[:, 1].sum() - W[:, 2].sum() / W[:, 3].sum()
    return W[:, 0].sum() / W[:, 1].sum()

def boot(W, two, rng):
    k = len(W); idx = rng.integers(0, k, size=(B, k)); S = W[idx].sum(axis=1)
    return S[:, 0] / S[:, 1] - S[:, 2] / S[:, 3] if two else S[:, 0] / S[:, 1]

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    A = ("A 五十日", gotobi_days(), True, ("2018-01-01", "2021-01-01"), ("2023-02-01", "2026-07-01"))
    Bx = ("B フィキシング", fixing_days(), False, ("2008-01-01", "2020-01-01"), ("2020-02-01", "2026-07-01"))
    C = ("C 週末", weekend_trades(), False, ("2013-01-01", "2014-06-01"), ("2017-01-01", "2026-07-01"))
    rng = np.random.default_rng(SEED); rows = []; boots = {}
    for name, df, two, pre, post in [A, Bx, C]:
        Wp, npre = week_table(df, *pre, two=two); Wq, npost = week_table(df, *post, two=two)
        ep, eq = effect(Wp, two), effect(Wq, two)
        bp, bq = boot(Wp, two, rng), boot(Wq, two, rng)
        ok = ep > 0
        r = bq / bp if ok else np.full(B, np.nan); boots[name] = r
        lo, hi = (np.nanpercentile(r, [2.5, 97.5]) if ok else (np.nan, np.nan))
        rows.append(dict(アノマリー=name, 公表前=f"{pre[0]}〜{pre[1]}", 公表後=f"{post[0]}〜{post[1]}", n前=npre, n後=npost, 週前=len(Wp), 週後=len(Wq),
                         効果前bp=round(ep, 3), 効果前_95=f"{np.percentile(bp,2.5):.2f}〜{np.percentile(bp,97.5):.2f}",
                         効果後bp=round(eq, 3), 効果後_95=f"{np.percentile(bq,2.5):.2f}〜{np.percentile(bq,97.5):.2f}",
                         比=round(eq / ep, 3) if ok else np.nan, 比_下=round(lo, 2), 比_上=round(hi, 2), 区間幅=round(hi - lo, 2) if ok else np.nan))
    Rt = pd.DataFrame(rows)
    valid = [k for k in boots if not np.isnan(boots[k]).all()]
    M = np.mean([boots[k] for k in valid], axis=0) if valid else None
    pt = np.mean([Rt.set_index("アノマリー").loc[k, "比"] for k in valid])
    mlo, mhi = np.percentile(M, [2.5, 97.5])
    Rt.loc[len(Rt)] = dict(アノマリー=f"平均（{len(valid)}本）", 比=round(pt, 3), 比_下=round(mlo, 2), 比_上=round(mhi, 2), 区間幅=round(mhi - mlo, 2))
    Rt.to_csv(os.path.join(OUT, "kensho_anomaly_decay.csv"), index=False)
    pd.DataFrame(boots).assign(平均=M).to_csv(os.path.join(OUT, "kensho_anomaly_decay_boot.csv"), index=False)
    print(Rt.to_string(index=False))
    wide = all((not np.isfinite(w)) or w > 1 for w in Rt["区間幅"].iloc[:3])
    if wide: verdict = "判定不能（3つとも区間の幅>1）"
    elif mlo <= 0.3 <= mhi: verdict = "日中・曜日でも月次と同じ程度に減る（平均の比の区間が0.3を含む）"
    elif mhi < 0.3: verdict = "月次より大きく減る"
    else: verdict = "月次より減りが小さい"
    sub = "株の0.41を含む" if mlo <= 0.41 <= mhi else ("株より大きく減る" if mhi < 0.41 else "株より減りが小さい")
    print(f"\n判定: {verdict} / 副: {sub}  平均の比 {pt:.3f}（95% {mlo:.2f}〜{mhi:.2f}）")
