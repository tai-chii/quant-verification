"""同一シードA/Bバックテスト実行スクリプト。

座席バイアスを消すため、各シードで検証ボットの座席を0〜3に回して4回対戦させる。
"""
import sys, os, json, tempfile, argparse, statistics
from multiprocessing import Pool
from loguru import logger
logger.remove()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mjai.engine import DockerMjaiLogEngine
from mjai.mlibriichi.arena import Match
from bots import (BaselineBot, TaichiBot, TaichiNoFold, TaichiCallOK,
                  CautiousBot, TaichiInstantRiichi,
                  TaichiYakuhaiPon, TaichiPonInstant, BaselineFixed)

BOTS = {"baseline": BaselineBot, "taichi": TaichiBot,
        "taichi_nofold": TaichiNoFold, "taichi_callok": TaichiCallOK,
        "cautious": CautiousBot, "taichi_instant": TaichiInstantRiichi,
        "taichi_pon": TaichiYakuhaiPon,
        "taichi_pon_instant": TaichiPonInstant,
        "baseline_fixed": BaselineFixed}


class Engine(DockerMjaiLogEngine):
    def __init__(self, name, cls, pid):
        super().__init__(name, player=cls(pid))
        self.final = None

    def end_game(self, gi, scores):
        self.final = list(scores)
        super().end_game(gi, scores)


def rank_of(scores, seat):
    s = list(scores)
    adj = [(-v - (3 - i) * 0.1) for i, v in enumerate(s)]
    order = sorted(range(4), key=lambda i: adj[i])
    return order.index(seat) + 1


def one(args):
    seed, seat, test_name, field = args
    classes = [BOTS[field]] * 4
    classes[seat] = BOTS[test_name]
    ags = [Engine(str(i), classes[i], i) for i in range(4)]
    import gzip
    stats = {"kyoku": 0, "agari": 0, "houjuu": 0, "riichi": 0,
             "kyoku_oya": 0, "kyoku_ko": 0, "agari_oya": 0, "agari_ko": 0,
             "delta_oya": 0, "delta_ko": 0, "pon": 0}
    is_oya = False
    try:
        with tempfile.TemporaryDirectory() as d:
            Match(log_dir=d).py_match(*ags, seed_start=(seed, 2026))
            for fn in os.listdir(d):
                with gzip.open(os.path.join(d, fn), "rt") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        ev = json.loads(line)
                        t = ev.get("type")
                        if t == "start_kyoku":
                            stats["kyoku"] += 1
                            is_oya = (ev.get("oya") == seat)
                            stats["kyoku_oya" if is_oya else "kyoku_ko"] += 1
                        elif t == "pon" and ev.get("actor") == seat:
                            stats["pon"] += 1
                        elif t == "hora":
                            if ev.get("actor") == seat:
                                stats["agari"] += 1
                                stats["agari_oya" if is_oya
                                      else "agari_ko"] += 1
                            elif ev.get("target") == seat:
                                stats["houjuu"] += 1
                        if t in ("hora", "ryukyoku") and ev.get("deltas"):
                            stats["delta_oya" if is_oya else "delta_ko"] += \
                                ev["deltas"][seat]
                        elif t == "reach" and ev.get("actor") == seat:
                            stats["riichi"] += 1
    except BaseException:
        return None
    sc = ags[0].final
    if not sc:
        return None
    return {"seed": seed, "seat": seat, "field": field, "score": sc[seat],
            "rank": rank_of(sc, seat), **stats}


def summarize(rows, label):
    sc = [r["score"] for r in rows]
    rk = [r["rank"] for r in rows]
    n = len(rows)
    dist = [rk.count(i) / n for i in (1, 2, 3, 4)]
    mean = statistics.mean(sc)
    sd = statistics.stdev(sc) if n > 1 else 0.0
    se = sd / (n ** 0.5) if n > 1 else 0.0
    ky = sum(r.get("kyoku", 0) for r in rows) or 1
    return {"label": label, "n": n, "mean_score": round(mean, 1),
            "se": round(se, 1),
            "mean_rank": round(statistics.mean(rk), 4),
            "rank_dist": [round(x, 4) for x in dist],
            "agari_rate": round(sum(r.get("agari", 0) for r in rows) / ky, 4),
            "houjuu_rate": round(sum(r.get("houjuu", 0) for r in rows) / ky, 4),
            "riichi_rate": round(sum(r.get("riichi", 0) for r in rows) / ky, 4),
            "pon_rate": round(sum(r.get("pon", 0) for r in rows) / ky, 4),
            "kyoku": ky,
            "oya": _sub(rows, "oya"), "ko": _sub(rows, "ko")}


def _sub(rows, tag):
    k = sum(r.get(f"kyoku_{tag}", 0) for r in rows) or 1
    return {"kyoku": k,
            "agari_rate": round(sum(r.get(f"agari_{tag}", 0)
                                    for r in rows) / k, 4),
            "pts_per_kyoku": round(sum(r.get(f"delta_{tag}", 0)
                                       for r in rows) / k, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=50, help="シード数")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--out", default="result.json")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--arms", default="baseline,taichi")
    ap.add_argument("--field", default="baseline")
    a = ap.parse_args()

    jobs = []
    arms = a.arms.split(",")
    for s in range(a.offset, a.offset + a.games):
        for seat in range(4):
            for name in arms:
                jobs.append((s, seat, name, a.field))

    with Pool(a.procs) as p:
        res = p.map(one, jobs, chunksize=4)

    rows = {k: [] for k in arms}
    for job, r in zip(jobs, res):
        if r:
            rows[job[2]].append(r)

    out = {k: summarize(v, k) for k, v in rows.items() if v}
    # 基準は理論期待値25000点(4人打ちの平均)。z検定はこれに対して行う。
    for k, v in list(out.items()):
        v["vs_25000"] = round(v["mean_score"] - 25000, 1)
        v["z_vs_25000"] = round((v["mean_score"] - 25000) / v["se"], 3) \
            if v["se"] else 0.0
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
