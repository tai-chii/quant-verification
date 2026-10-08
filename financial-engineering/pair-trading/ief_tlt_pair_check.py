# -*- coding: utf-8 -*-
"""
IEF × TLT ペアトレード適性チェック(米国債ETF・年限ペア)
============================================================

【何を見るか】
IEF = 米国債7-10年ETF(中期)
TLT = 米国債20年超ETF(長期)
同じ「米国債」で共通の金融政策・金利に強く連動する一方、年限が違うので
金利変動への感応度(デュレーション)が異なる=別物性がある。
イールドカーブ取引の入口(2資産版)を、株と同じ枠組みで検証する。

【仮説】
同じ発行体(米国債)ゆえ株の同業ペアより共和分しやすいはず。
ただし利上げ/QT等の政策レジーム転換があった期間では、
スプレッドがドリフトして共和分が弱まる可能性もある。
→ 「国債の年限ペアは共和分するのか?」を数字で確認する。

【実行】
    pip install yfinance statsmodels pandas matplotlib
    cd /Users/goyataichi/ワークスペース/vault   # ← ここで実行するとpngもvaultに出る
    python ief_tlt_pair_check.py

【流れ(相関調査の5段)】
 1. データを揃える  2. リターン化  3. 相関係数
 4. ローリング相関  5. 共和分検定(ペアトレードの本体)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint, adfuller

A, B = "IEF", "TLT"
START, END = "2019-01-01", "2025-05-31"

# ---- 1. データを揃える ----------------------------------------------------
px = yf.download([A, B], start=START, end=END, auto_adjust=True, progress=False)["Close"]
px = px.dropna()
print(f"期間: {px.index[0].date()} 〜 {px.index[-1].date()}  営業日数: {len(px)}")

# ---- 2. リターン化(対数リターン) ----------------------------------------
ret = np.log(px / px.shift(1)).dropna()

# ---- 3. 相関係数(ピアソン, リターンベース) ------------------------------
corr = ret[A].corr(ret[B])
print(f"\n[3] リターン相関(全期間): {corr:.3f}")
print("    → 0.7〜0.8以上なら『連動』の入口はクリア")

# ---- 4. ローリング相関(安定性) ------------------------------------------
roll = ret[A].rolling(60).corr(ret[B])
print(f"[4] 60日ローリング相関  平均{roll.mean():.2f} / 最小{roll.min():.2f} / 最大{roll.max():.2f}")

# ---- 5. 共和分検定(ペアトレードの本体) ----------------------------------
X = sm.add_constant(px[B])
beta = sm.OLS(px[A], X).fit().params[B]
spread = px[A] - beta * px[B]

eg_stat, eg_p, _ = coint(px[A], px[B])
adf_stat, adf_p = adfuller(spread.dropna())[:2]

print(f"\n[5] ヘッジ比率 β = {beta:.3f}   スプレッド = {A} - β*{B}")
print(f"    Engle-Granger共和分 p値 = {eg_p:.3f}")
print(f"    スプレッドADF検定  p値 = {adf_p:.3f}")
print("    → p<0.05 なら『平均回帰する＝ペアトレード可能』、p>0.05 なら不成立")

verdict = "成立の可能性あり" if (eg_p < 0.05 and adf_p < 0.05) else "不成立(戻らない)"
print(f"\n=== 判定: {verdict} ===")
print("NVDA/AMD(相関高いのに共和分×)と結果を比べると、")
print("『別物性はあるが発行体が同じ』国債ペアの方が共和分しやすいかが分かる。")

# ---- 参考: Zスコア(実際に何回エントリー機会があったか) ------------------
z = (spread - spread.rolling(60).mean()) / spread.rolling(60).std()
signals = int((z.abs() > 2).sum())
print(f"\n[参考] スプレッドZスコアが±2を超えた日数: {signals}日(エントリー機会の目安)")

# ---- 可視化 ---------------------------------------------------------------
fig, ax = plt.subplots(3, 1, figsize=(11, 11))
(px / px.iloc[0]).plot(ax=ax[0]); ax[0].set_title("正規化価格(開始=1.0)"); ax[0].grid(alpha=.3)
spread.plot(ax=ax[1], color="purple")
ax[1].axhline(spread.mean(), color="gray", ls="--")
ax[1].set_title(f"スプレッド {A}-β*{B}(平均回帰なら水平線付近を行き来)"); ax[1].grid(alpha=.3)
roll.plot(ax=ax[2], color="teal"); ax[2].axhline(roll.mean(), color="gray", ls="--")
ax[2].set_title("60日ローリング相関(安定性)"); ax[2].grid(alpha=.3)
plt.tight_layout(); plt.savefig("ief_tlt_pair.png", dpi=110)
print("\n図を ief_tlt_pair.png に保存しました。")
