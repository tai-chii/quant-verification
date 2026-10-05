"""
Hull Tactical 公式評価指標の移植
================================
出典: https://www.kaggle.com/code/metric/hull-competition-sharpe (Apache 2.0)
取得日: 2026-09-08

構造:
  strategy_returns = rf*(1-pos) + pos*forward_returns
  sharpe          = 幾何平均超過リターン / std(strategy_returns) * sqrt(252)
  vol_penalty     = 1 + max(0, 戦略ボラ/市場ボラ - 1.2)      ← 市場の120%まで無罰
  return_gap      = max(0, (市場平均超過 - 戦略平均超過) * 100 * 252)
  return_penalty  = 1 + return_gap^2 / 100                  ← 市場に負けると2乗で罰
  score           = sharpe / (vol_penalty * return_penalty)

読み取れる設計上の含意:
  * position は [0,2]。**市場に負けた瞬間に2乗のペナルティ**が効くので、
    配分の中心を1.0より下に置くのは極めて危険
  * ボラは市場の1.2倍まで無料。つまり「当たっている時だけ強く張る」余地がある
"""
import numpy as np

MIN_INVESTMENT, MAX_INVESTMENT = 0, 2
TRADING_DAYS = 252

def hull_score(position, forward_returns, risk_free_rate):
    pos = np.asarray(position, dtype=float)
    fr  = np.asarray(forward_returns, dtype=float)
    rf  = np.asarray(risk_free_rate, dtype=float)
    if pos.max() > MAX_INVESTMENT or pos.min() < MIN_INVESTMENT:
        raise ValueError(f"position out of [{MIN_INVESTMENT},{MAX_INVESTMENT}]: "
                         f"{pos.min():.3f}..{pos.max():.3f}")
    n = len(pos)
    strat = rf * (1 - pos) + pos * fr
    strat_excess = strat - rf
    strat_mean_excess = (1 + strat_excess).prod() ** (1 / n) - 1
    strat_std = strat.std(ddof=1)
    if strat_std == 0:
        raise ValueError("strategy std is zero")
    sharpe = strat_mean_excess / strat_std * np.sqrt(TRADING_DAYS)

    strat_vol = strat_std * np.sqrt(TRADING_DAYS) * 100
    mkt_excess = fr - rf
    mkt_mean_excess = (1 + mkt_excess).prod() ** (1 / n) - 1
    mkt_std = fr.std(ddof=1)
    mkt_vol = mkt_std * np.sqrt(TRADING_DAYS) * 100
    if mkt_vol == 0:
        raise ValueError("market std is zero")

    vol_penalty = 1 + max(0.0, strat_vol / mkt_vol - 1.2)
    return_gap = max(0.0, (mkt_mean_excess - strat_mean_excess) * 100 * TRADING_DAYS)
    return_penalty = 1 + (return_gap ** 2) / 100
    return min(float(sharpe / (vol_penalty * return_penalty)), 1e6)

def diagnostics(position, forward_returns, risk_free_rate):
    """スコアの内訳。どのペナルティで削られているかを見るため。"""
    pos = np.asarray(position, float); fr = np.asarray(forward_returns, float)
    rf = np.asarray(risk_free_rate, float); n = len(pos)
    strat = rf * (1 - pos) + pos * fr
    sme = (1 + (strat - rf)).prod() ** (1/n) - 1
    mme = (1 + (fr - rf)).prod() ** (1/n) - 1
    svol = strat.std(ddof=1) * np.sqrt(TRADING_DAYS) * 100
    mvol = fr.std(ddof=1) * np.sqrt(TRADING_DAYS) * 100
    gap = max(0.0, (mme - sme) * 100 * TRADING_DAYS)
    return dict(sharpe_raw=sme / strat.std(ddof=1) * np.sqrt(TRADING_DAYS),
                vol_ratio=svol / mvol, vol_penalty=1 + max(0.0, svol/mvol - 1.2),
                return_gap=gap, return_penalty=1 + gap**2/100,
                mean_pos=float(pos.mean()))
