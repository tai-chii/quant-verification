# -*- coding: utf-8 -*-
"""
NVDA × AMD ペアトレード適性チェック
=====================================

【仮説】
NVDAとAMDは同じGPU/半導体セクターで相関は高いはず。
だが2022年以降のAI需要でNVDAだけが構造的に突出したため、
スプレッド(価格差)は「戻る」のではなく一方向に開き続け、
共和分検定に落ちる(=ペアトレードは成立しない)はずだ。

→ 「相関が高い ≠ ペアトレード可能」「合否を決めるのは共和分」を
   自分の手で数字で確認するための実験。

【この環境について】
Claudeのサンドボックスは市場データ提供元へネットワークが通らないため、
データ取得はローカル(このスクリプトを自分のPCで実行)で行う。
    pip install yfinance statsmodels pandas matplotlib
    python nvda_amd_pair_check.py

【流れ(相関調査の5段:前回説明の実装)】
 1. データを揃える(同じ期間・調整済み終値)
 2. リターン化(価格ではなく対数リターンで相関を測る=スプリアス回避)
 3. 相関係数(ピアソン)
 4. ローリング相関(相関が時間で安定しているか)
 5. 共和分検定(スプレッドが平均回帰するか＝ペアトレードの本体)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint, adfuller

A, B = "NVDA", "AMD"
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
print("    → 0.7〜0.8以上なら『連動』の入口はクリア(=候補になる)")

# ---- 4. ローリング相関(安定性) ------------------------------------------
roll = ret[A].rolling(60).corr(ret[B])
print(f"[4] 60日ローリング相関  平均{roll.mean():.2f} / 最小{roll.min():.2f} / 最大{roll.max():.2f}")

# ---- 5. 共和分検定(ペアトレードの本体) ----------------------------------
# ヘッジ比率βをOLSで推定し、スプレッド = A - β*B を作る
X = sm.add_constant(px[B])
beta = sm.OLS(px[A], X).fit().params[B]
spread = px[A] - beta * px[B]

# (a) Engle-Granger共和分検定
eg_stat, eg_p, _ = coint(px[A], px[B])
# (b) スプレッド自体のADF検定(平均回帰するか)
adf_stat, adf_p = adfuller(spread.dropna())[:2]

print(f"\n[5] ヘッジ比率 β = {beta:.3f}   スプレッド = {A} - β*{B}")
print(f"    Engle-Granger共和分 p値 = {eg_p:.3f}")
print(f"    スプレッドADF検定  p値 = {adf_p:.3f}")
print("    → p<0.05 なら『平均回帰する＝ペアトレード可能』、p>0.05 なら不成立")

verdict = "成立の可能性あり" if (eg_p < 0.05 and adf_p < 0.05) else "不成立(戻らない)"
print(f"\n=== 判定: {verdict} ===")
print("相関が高くても共和分に落ちれば、それが仮説どおりの結論。")

# ---- 可視化 ---------------------------------------------------------------
fig, ax = plt.subplots(3, 1, figsize=(11, 11))
(px / px.iloc[0]).plot(ax=ax[0]); ax[0].set_title("正規化価格(開始=1.0)"); ax[0].grid(alpha=.3)
spread.plot(ax=ax[1], color="purple")
ax[1].axhline(spread.mean(), color="gray", ls="--")
ax[1].set_title(f"スプレッド {A}-β*{B}(平均回帰しないなら一方向に伸びる)"); ax[1].grid(alpha=.3)
roll.plot(ax=ax[2], color="teal"); ax[2].axhline(roll.mean(), color="gray", ls="--")
ax[2].set_title("60日ローリング相関(安定性)"); ax[2].grid(alpha=.3)
plt.tight_layout(); plt.savefig("nvda_amd_pair.png", dpi=110)
print("\n図を nvda_amd_pair.png に保存しました。")
