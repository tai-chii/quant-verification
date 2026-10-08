"""打牌方策。

BASELINE : 向聴数最小化 → 受け入れ枚数最大化 → 同点はランダム
MYRULE   : 向聴数最小化 → マイルール優先度 → 受け入れ枚数最大化

マイルールのソロ環境での扱い:
  R1 序盤は字牌優先。切り順 客風→白→發→中→場風→自風  … 実装（全巡適用）
  R2 役がつく字牌の対子のみ保持（客風は対子でも切る）    … 実装
  R3 鳴かない                                            … ソロは門前のみ。自動的に満たす
  R4 残り2枚が河に出た字牌対子は雀頭/安牌として保持      … 他家の河が存在しないため対象外
  R5 孤立牌は端から、繋がりにくい牌から                  … 実装
  R6 愚形聴牌は3巡黙聴で様子見                           … 実装（リーチ判断）
  R7 先制リーチにはベタオリ                              … 他家不在のため対象外
"""
from core import (min_shanten_discards, ukeire, is_isolated, HONOR,
                  TON, NAN, SHA, PEI, HAKU, HATSU, CHUN)

# 東場・子（自風=南）を既定とする
BAKAZE, JIKAZE = TON, NAN
YAKUHAI = {HAKU, HATSU, CHUN, BAKAZE, JIKAZE}
OTAKAZE = {TON, NAN, SHA, PEI} - {BAKAZE, JIKAZE}   # 客風 = 西・北

# R1: 客風 → 白 → 發 → 中 → 場風 → 自風
_R1_ORDER = {}
for _t in OTAKAZE:
    _R1_ORDER[_t] = 0
_R1_ORDER[HAKU] = 1
_R1_ORDER[HATSU] = 2
_R1_ORDER[CHUN] = 3
_R1_ORDER[BAKAZE] = 4
_R1_ORDER[JIKAZE] = 5

# R5: 孤立数牌は端から
_R5_ORDER = {0: 10, 8: 10, 1: 11, 7: 11, 2: 12, 6: 12, 3: 13, 5: 13, 4: 14}


def myrule_priority(h34, t):
    """切る優先度。小さいほど先に切る。h34 は14枚形。"""
    if t >= HONOR:
        c = h34[t]
        if t in OTAKAZE:
            # R2: 客風は対子でも切る
            return 0 if c == 1 else 0.5
        if c == 1:
            return _R1_ORDER[t]          # 孤立役牌 → R1順
        return 30                        # 役牌の対子・暗刻は保持
    if is_isolated(h34, t):
        return _R5_ORDER[t % 9]          # R5: 孤立数牌は端から
    return 20                            # 塔子・対子の一部 → 保持


def choose_baseline(h34, unseen, turn, rng):
    sh, cands = min_shanten_discards(h34)
    best, bu = [], -1
    for t in cands:
        h34[t] -= 1
        u, _ = ukeire(h34, unseen, sh)
        h34[t] += 1
        if u > bu:
            bu, best = u, [t]
        elif u == bu:
            best.append(t)
    return rng.choice(best), sh


def choose_myrule(h34, unseen, turn, rng):
    sh, cands = min_shanten_discards(h34)
    pr = min(myrule_priority(h34, t) for t in cands)
    cands = [t for t in cands if myrule_priority(h34, t) == pr]
    best, bu = [], -1
    for t in cands:
        h34[t] -= 1
        u, _ = ukeire(h34, unseen, sh)
        h34[t] += 1
        if u > bu:
            bu, best = u, [t]
        elif u == bu:
            best.append(t)
    return rng.choice(best), sh


# --- リーチ判断 ---------------------------------------------------------

def riichi_baseline(wait_kinds, turns_tenpai, turn):
    """即リーチ。"""
    return True


def riichi_myrule(wait_kinds, turns_tenpai, turn):
    """R6: 愚形（待ち種類1以下）は聴牌から3巡は黙聴。良形は即リーチ。"""
    if len(wait_kinds) >= 2:
        return True
    return turns_tenpai >= 3


def _priority_r5only(h34, t):
    """R5（孤立牌は端から）だけを使う。字牌は一律に孤立牌の先頭扱い。"""
    if t >= HONOR:
        return 9 if h34[t] == 1 else 30
    if is_isolated(h34, t):
        return _R5_ORDER[t % 9]
    return 20


def _make_chooser(prio):
    def f(h34, unseen, turn, rng):
        sh, cands = min_shanten_discards(h34)
        p = min(prio(h34, t) for t in cands)
        cands = [t for t in cands if prio(h34, t) == p]
        best, bu = [], -1
        for t in cands:
            h34[t] -= 1
            u, _ = ukeire(h34, unseen, sh)
            h34[t] += 1
            if u > bu:
                bu, best = u, [t]
            elif u == bu:
                best.append(t)
        return rng.choice(best), sh
    return f


choose_r5only = _make_chooser(_priority_r5only)

POLICIES = {
    "baseline": (choose_baseline, riichi_baseline),
    "myrule": (choose_myrule, riichi_myrule),
    # アブレーション用
    "myrule_soku": (choose_myrule, riichi_baseline),   # R6を外す（打牌はマイルール）
    "r5only": (choose_r5only, riichi_baseline),        # R5だけ（R1/R2を外す）
}
