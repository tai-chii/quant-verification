"""完全ソロ牌効率シミュレーション本体。"""
import random, math, json, sys
from core import shanten, waits, score_hand
from policy import POLICIES

MAX_TURN = 18


def play_one(seed, choose, riichi_fn, eval_turns=(12, 18)):
    rng = random.Random(seed)
    wall = [i for i in range(136)]
    rng.shuffle(wall)

    h34 = [0] * 34
    for x in wall[:13]:
        h34[x // 4] += 1
    dora_ind = wall[13]
    ura_ind = wall[14]
    draws = wall[15:15 + MAX_TURN]

    unseen = [4] * 34
    for i in range(34):
        unseen[i] -= h34[i]
    unseen[dora_ind // 4] -= 1

    rec = {
        "sh": [None] * (MAX_TURN + 1),      # 各巡目終了時の向聴数（和了後は-1）
        "riichi_turn": None,
        "agari_turn": None,
        "agari_score": None,
        "agari_han": None,
        "snap": {},                          # 指定巡目のスナップショット
    }
    rec["sh"][0] = shanten(h34)

    is_riichi = False
    turns_tenpai = 0
    riichi_turn = None

    for turn in range(1, MAX_TURN + 1):
        drawn = draws[turn - 1] // 4
        h34[drawn] += 1
        unseen[drawn] -= 1

        if shanten(h34) == -1:
            ind = [dora_ind] + ([ura_ind] if is_riichi else [])
            ippatsu = is_riichi and riichi_turn is not None and turn == riichi_turn + 1
            r = score_hand(h34, drawn, ind, is_riichi, True,
                           is_ippatsu=ippatsu, is_haitei=(turn == MAX_TURN))
            if r is not None:
                rec["agari_turn"] = turn
                rec["agari_score"] = r.cost["main"] + 2 * r.cost["additional"]
                rec["agari_han"] = r.han
                for t2 in range(turn, MAX_TURN + 1):
                    rec["sh"][t2] = -1
                break
        # 打牌
        if is_riichi:
            d = drawn                      # リーチ後はツモ切り
        else:
            d, _ = choose(h34, unseen, turn, rng)
        h34[d] -= 1
        sh_now = shanten(h34)
        rec["sh"][turn] = sh_now

        # リーチ判断
        if not is_riichi and sh_now == 0:
            turns_tenpai += 1
            _, wk = waits(h34, unseen)
            if turn <= MAX_TURN - 1 and riichi_fn(wk, turns_tenpai, turn):
                is_riichi = True
                riichi_turn = turn
                rec["riichi_turn"] = turn
        elif sh_now != 0:
            turns_tenpai = 0

        if turn in eval_turns and sh_now == 0:
            wn, wk = waits(h34, unseen)
            ind = [dora_ind] + ([ura_ind] if is_riichi else [])
            ron_pts, tsumo_pts, wsum = 0.0, 0.0, 0
            for w in wk:
                n = unseen[w]
                if n <= 0:
                    continue
                h34[w] += 1
                rr = score_hand(h34, w, ind, is_riichi, False)
                rt = score_hand(h34, w, ind, is_riichi, True)
                h34[w] -= 1
                ron_pts += n * (rr.cost["main"] if rr else 0)
                tsumo_pts += n * ((rt.cost["main"] + 2 * rt.cost["additional"]) if rt else 0)
                wsum += n
            rec["snap"][turn] = {
                "waits": wn,
                "kinds": len(wk),
                "riichi": is_riichi,
                "ron": ron_pts / wsum if wsum else 0.0,
                "tsumo": tsumo_pts / wsum if wsum else 0.0,
            }
    return rec


def _one(args):
    policy, seed = args
    choose, rfn = POLICIES[policy]
    r = play_one(seed, choose, rfn)
    sh = r["sh"]
    for t in range(MAX_TURN + 1):
        if sh[t] is None:
            sh[t] = sh[t - 1]
    return {
        "seed": seed,
        "sh": sh,
        "agari_turn": r["agari_turn"],
        "agari_score": r["agari_score"],
        "agari_han": r["agari_han"],
        "riichi_turn": r["riichi_turn"],
        "snap": r["snap"],
    }


def run(policy, n, seed0=0, procs=2):
    from multiprocessing import Pool
    args = [(policy, seed0 + i) for i in range(n)]
    if procs <= 1:
        return [_one(a) for a in args]
    with Pool(procs) as p:
        return p.map(_one, args, chunksize=50)


if __name__ == "__main__":
    pol = sys.argv[1]
    n = int(sys.argv[2])
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    out = run(pol, n, seed0)
    with open(f"raw_{pol}.json", "w") as f:
        json.dump(out, f)
    print(pol, "done", n, file=sys.stderr)
