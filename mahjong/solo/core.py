"""ソロ牌効率シミュレータ - 中核部分

完全ソロモデル: 他家は存在しない。配牌13枚 + 残り山から自分だけが順にツモる。
和了はツモのみ（ロンは構造上あり得ない）。
"""
import random
from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules

_SH = Shanten()
_HC = HandCalculator()

# 牌種インデックス: 0-8=萬子1-9, 9-17=筒子1-9, 18-26=索子1-9,
#                   27=東 28=南 29=西 30=北 31=白 32=發 33=中
MAN, PIN, SOU, HONOR = 0, 9, 18, 27
TON, NAN, SHA, PEI, HAKU, HATSU, CHUN = 27, 28, 29, 30, 31, 32, 33

_shanten_cache = {}


def shanten(h34):
    """向聴数（-1=和了形）。メモ化つき。"""
    k = bytes(h34)
    v = _shanten_cache.get(k)
    if v is None:
        v = _SH.calculate_shanten(list(h34))
        _shanten_cache[k] = v
    return v


def candidate_tiles(h34):
    """受け入れ判定の対象にする牌種。手牌から±2以内の数牌と、全字牌。"""
    cand = set()
    for i in range(34):
        if h34[i] == 0:
            continue
        if i >= HONOR:
            cand.add(i)
        else:
            suit, num = divmod(i, 9)
            base = suit * 9
            for d in (-2, -1, 0, 1, 2):
                n = num + d
                if 0 <= n <= 8:
                    cand.add(base + n)
    # 字牌は対子→刻子の受けがあるので手牌にあるものだけで十分
    return cand


def ukeire(h34, unseen, cur_sh=None):
    """(受け入れ枚数, 受け入れ牌種のリスト)。h34は13枚形であること。"""
    if cur_sh is None:
        cur_sh = shanten(h34)
    total, kinds = 0, []
    for t in candidate_tiles(h34):
        if unseen[t] <= 0 or h34[t] >= 4:
            continue
        h34[t] += 1
        s = shanten(h34)
        h34[t] -= 1
        if s < cur_sh:
            total += unseen[t]
            kinds.append(t)
    return total, kinds


def waits(h34, unseen):
    """聴牌時の待ち。(残り枚数, 待ち牌種リスト)。h34は13枚形。"""
    total, kinds = 0, []
    for t in range(34):
        if h34[t] >= 4:
            continue
        h34[t] += 1
        s = shanten(h34)
        h34[t] -= 1
        if s == -1:
            kinds.append(t)
            total += max(0, unseen[t])
    return total, kinds


def min_shanten_discards(h34):
    """14枚形から、切ると向聴数が最小になる牌のリストと、その向聴数。"""
    best = 99
    res = []
    for t in range(34):
        if h34[t] == 0:
            continue
        h34[t] -= 1
        s = shanten(h34)
        h34[t] += 1
        if s < best:
            best, res = s, [t]
        elif s == best:
            res.append(t)
    return best, res


def is_isolated(h34, t):
    """孤立牌か。字牌は1枚のみ、数牌は±2以内に他の牌がない。"""
    if t >= HONOR:
        return h34[t] == 1
    suit, num = divmod(t, 9)
    base = suit * 9
    for d in (-2, -1, 1, 2):
        n = num + d
        if 0 <= n <= 8 and h34[base + n] > 0:
            return False
    return h34[t] == 1


def score_hand(h34_14, win_tile, dora_indicators, is_riichi, is_tsumo,
               is_ippatsu=False, is_haitei=False, turn=None):
    """和了形の点数を返す。役なしなら None。"""
    tiles136 = TilesConverter.to_136_array(h34_14)
    # win_tile の136表現をhandから1つ選ぶ
    wt = None
    for x in tiles136:
        if x // 4 == win_tile:
            wt = x
            break
    if wt is None:
        return None
    cfg = HandConfig(
        is_tsumo=is_tsumo, is_riichi=is_riichi, is_ippatsu=is_ippatsu,
        is_haitei=is_haitei and is_tsumo,
        options=OptionalRules(has_aka_dora=False, has_open_tanyao=True),
    )
    try:
        r = _HC.estimate_hand_value(
            tiles136, wt,
            dora_indicators=dora_indicators,
            config=cfg)
    except Exception:
        return None
    if r.error or r.cost is None:
        return None
    return r
