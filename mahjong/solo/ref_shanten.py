"""検証用の独立実装（再帰的な面子分解）。ライブラリの向聴数と突き合わせる。"""

def _rec(h, i, melds, partials, pair):
    """i以降を走査。melds=面子数, partials=搭子/対子数(雀頭以外), pair=雀頭の有無"""
    while i < 34 and h[i] == 0:
        i += 1
    if i == 34:
        return (melds, partials, pair)
    best = None

    def upd(r):
        nonlocal best
        # 評価: 8 - 2*melds - (partials+pair) が小さいほど良い
        if best is None:
            best = r
        else:
            a = 8 - 2 * best[0] - (best[1] + (1 if best[2] else 0))
            b = 8 - 2 * r[0] - (r[1] + (1 if r[2] else 0))
            if b < a or (b == a and r[0] > best[0]):
                best = r

    # 刻子
    if h[i] >= 3 and melds + partials < 4:
        h[i] -= 3
        upd(_rec(h, i, melds + 1, partials, pair))
        h[i] += 3
    # 順子
    if i < 27 and i % 9 <= 6 and h[i] and h[i + 1] and h[i + 2] and melds + partials < 4:
        h[i] -= 1; h[i + 1] -= 1; h[i + 2] -= 1
        upd(_rec(h, i, melds + 1, partials, pair))
        h[i] += 1; h[i + 1] += 1; h[i + 2] += 1
    # 雀頭
    if h[i] >= 2 and not pair:
        h[i] -= 2
        upd(_rec(h, i, melds, partials, True))
        h[i] += 2
    # 対子（搭子扱い）
    if h[i] >= 2 and melds + partials < 4:
        h[i] -= 2
        upd(_rec(h, i, melds, partials + 1, pair))
        h[i] += 2
    # 両面/嵌張
    if i < 27 and melds + partials < 4:
        if i % 9 <= 7 and h[i] and h[i + 1]:
            h[i] -= 1; h[i + 1] -= 1
            upd(_rec(h, i, melds, partials + 1, pair))
            h[i] += 1; h[i + 1] += 1
        if i % 9 <= 6 and h[i] and h[i + 2]:
            h[i] -= 1; h[i + 2] -= 1
            upd(_rec(h, i, melds, partials + 1, pair))
            h[i] += 1; h[i + 2] += 1
    # 孤立牌として捨てる
    h[i] -= 1
    upd(_rec(h, i, melds, partials, pair))
    h[i] += 1
    return best


def regular(h34):
    m, p, pr = _rec(list(h34), 0, 0, 0, False)
    return 8 - 2 * m - (p + (1 if pr else 0))


def chiitoi(h34):
    pairs = sum(1 for c in h34 if c >= 2)
    kinds = sum(1 for c in h34 if c >= 1)
    return 6 - pairs + max(0, 7 - kinds)


def kokushi(h34):
    y = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    kinds = sum(1 for i in y if h34[i] >= 1)
    has_pair = any(h34[i] >= 2 for i in y)
    return 13 - kinds - (1 if has_pair else 0)


def ref_shanten(h34):
    return min(regular(h34), chiitoi(h34), kokushi(h34))
