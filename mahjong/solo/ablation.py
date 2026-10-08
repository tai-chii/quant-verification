import json, math, statistics as st
from analyze import load, mean_se, paired

KEYS = [
    ("12巡目 聴牌率(%)", lambda r: 100.0 if r["sh"][12] <= 0 else 0.0, 1),
    ("18巡目 聴牌率(%)", lambda r: 100.0 if r["sh"][18] <= 0 else 0.0, 1),
    ("12巡目 平均向聴", lambda r: float(r["sh"][12]), 3),
    ("18巡目 平均向聴", lambda r: float(r["sh"][18]), 3),
    ("ツモ和了率(%)", lambda r: 100.0 if r["agari_turn"] else 0.0, 2),
    ("リーチ率(%)", lambda r: 100.0 if r["riichi_turn"] else 0.0, 1),
    ("全局平均和了打点", lambda r: float(r["agari_score"] or 0), 0),
]


def table(pairs):
    L = ["| 比較 | " + " | ".join(k[0] for k in KEYS) + " |",
         "|---" * (len(KEYS) + 1) + "|"]
    for label, a, b in pairs:
        cells = []
        for name, f, d in KEYS:
            ma, sa, mb, sb, md, sd = paired(a, b, f)
            star = "**" if sd > 0 and abs(md) > 2 * sd else ""
            cells.append(f"{md:+.{d}f}±{sd:.{d}f}{star}")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(L)


def absolute(named):
    L = ["| 方策 | " + " | ".join(k[0] for k in KEYS) + " |",
         "|---" * (len(KEYS) + 1) + "|"]
    for label, D in named:
        seeds = sorted(D)
        cells = []
        for name, f, d in KEYS:
            m, e = mean_se([f(D[s]) for s in seeds])
            cells.append(f"{m:.{d}f}±{e:.{d}f}")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(L)


if __name__ == "__main__":
    P = {k: load(k) for k in ["baseline", "r5only", "myrule_soku", "myrule"]}
    print("## 絶対値\n")
    print(absolute([
        ("B: 受け入れ最大化・ランダムタイブレーク・即リーチ", P["baseline"]),
        ("B+R5: 孤立牌は端から・即リーチ", P["r5only"]),
        ("B+R5+R1R2: 打牌はマイルール・即リーチ", P["myrule_soku"]),
        ("マイルール一式（+R6 愚形3巡黙聴）", P["myrule"]),
    ]))
    print("\n## 差分（同一牌山ペア比較）\n")
    print(table([
        ("R5を足す（B → B+R5）", P["baseline"], P["r5only"]),
        ("R1/R2を足す（B+R5 → 打牌マイルール）", P["r5only"], P["myrule_soku"]),
        ("R6を足す（即リーチ → 愚形3巡黙聴）", P["myrule_soku"], P["myrule"]),
        ("合計（B → マイルール一式）", P["baseline"], P["myrule"]),
    ]))
