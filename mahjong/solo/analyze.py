import json, math, statistics as st
from collections import defaultdict

MAX_TURN = 18


def load(p):
    with open(f"raw_{p}.json") as f:
        d = json.load(f)
    return {r["seed"]: r for r in d}


def mean_se(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    return m, st.pstdev(xs) * math.sqrt(n / (n - 1)) / math.sqrt(n)


def paired(a, b, f):
    """f(rec)->float。b - a の対応差。"""
    seeds = sorted(set(a) & set(b))
    da = [f(a[s]) for s in seeds]
    db = [f(b[s]) for s in seeds]
    d = [y - x for x, y in zip(da, db)]
    ma, sa = mean_se(da)
    mb, sb = mean_se(db)
    md, sd = mean_se(d)
    return ma, sa, mb, sb, md, sd


def fmt(m, s, d=1):
    return f"{m:.{d}f}±{s:.{d}f}"


def report(A, B, nameA="baseline", nameB="myrule"):
    L = []
    seeds = sorted(set(A) & set(B))
    n = len(seeds)
    L.append(f"局数: {n}（同一牌山でのペア比較）\n")

    L.append("## 巡目別 聴牌率（%）\n")
    L.append("| 巡目 | " + nameA + " | " + nameB + " | 差 |")
    L.append("|---|---|---|---|")
    for t in list(range(1, 19)):
        f = lambda r, t=t: 100.0 if r["sh"][t] <= 0 else 0.0
        ma, sa, mb, sb, md, sd = paired(A, B, f)
        star = " **" if abs(md) > 2 * sd and sd > 0 else ""
        L.append(f"| {t} | {fmt(ma,sa)} | {fmt(mb,sb)} | {md:+.1f}±{sd:.1f}{star} |")

    L.append("\n## 巡目別 平均向聴数（和了は-1で計上）\n")
    L.append("| 巡目 | " + nameA + " | " + nameB + " | 差 |")
    L.append("|---|---|---|---|")
    for t in [0, 3, 6, 9, 12, 15, 18]:
        f = lambda r, t=t: float(r["sh"][t])
        ma, sa, mb, sb, md, sd = paired(A, B, f)
        L.append(f"| {t} | {ma:.3f}±{sa:.3f} | {mb:.3f}±{sb:.3f} | {md:+.3f}±{sd:.3f} |")

    L.append("\n## 和了・リーチ（ソロなのでツモ和了のみ）\n")
    rows = [
        ("12巡目までのツモ和了率(%)", lambda r: 100.0 if r["agari_turn"] and r["agari_turn"] <= 12 else 0.0, 2),
        ("18巡目までのツモ和了率(%)", lambda r: 100.0 if r["agari_turn"] else 0.0, 2),
        ("リーチ率(%)", lambda r: 100.0 if r["riichi_turn"] else 0.0, 1),
        ("平均和了打点(全局平均)", lambda r: float(r["agari_score"] or 0), 0),
    ]
    L.append("| 指標 | " + nameA + " | " + nameB + " | 差 |")
    L.append("|---|---|---|---|")
    for name, f, d in rows:
        ma, sa, mb, sb, md, sd = paired(A, B, f)
        star = " **" if abs(md) > 2 * sd and sd > 0 else ""
        L.append(f"| {name} | {fmt(ma,sa,d)} | {fmt(mb,sb,d)} | {md:+.{d}f}±{sd:.{d}f}{star} |")

    # 条件付き平均
    L.append("\n| 指標 | " + nameA + " | " + nameB + " |")
    L.append("|---|---|---|")
    for name, key in [("平均和了巡目", "agari_turn"), ("和了時の平均翻数", "agari_han"),
                      ("和了時の平均打点", "agari_score")]:
        va = [A[s][key] for s in seeds if A[s]["agari_turn"]]
        vb = [B[s][key] for s in seeds if B[s]["agari_turn"]]
        ma, sa = mean_se(va)
        mb, sb = mean_se(vb)
        L.append(f"| {name} | {fmt(ma,sa,2)} | {fmt(mb,sb,2)} |")
    va = [A[s]["riichi_turn"] for s in seeds if A[s]["riichi_turn"]]
    vb = [B[s]["riichi_turn"] for s in seeds if B[s]["riichi_turn"]]
    ma, sa = mean_se(va); mb, sb = mean_se(vb)
    L.append(f"| 平均リーチ巡目 | {fmt(ma,sa,2)} | {fmt(mb,sb,2)} |")

    for T in (12, 18):
        L.append(f"\n## {T}巡目時点で聴牌している手の中身\n")
        L.append("| 指標 | " + nameA + " | " + nameB + " |")
        L.append("|---|---|---|")
        for name, k, d in [("該当局数", None, 0), ("平均待ち枚数", "waits", 2),
                           ("平均待ち種類", "kinds", 2), ("リーチ済率(%)", "riichi", 1),
                           ("期待打点(ロン)", "ron", 0), ("期待打点(ツモ)", "tsumo", 0)]:
            vals = []
            for D in (A, B):
                xs = [D[s]["snap"][str(T)] for s in seeds if str(T) in D[s]["snap"]]
                if k is None:
                    vals.append(f"{len(xs)}")
                elif k == "riichi":
                    m, e = mean_se([100.0 if x["riichi"] else 0.0 for x in xs])
                    vals.append(fmt(m, e, 1))
                else:
                    m, e = mean_se([float(x[k]) for x in xs])
                    vals.append(fmt(m, e, d))
            L.append(f"| {name} | {vals[0]} | {vals[1]} |")
    return "\n".join(L)


def turn12_question(D, name):
    """『12巡目までにリーチできなかった手』はその後どうなるか。"""
    L = [f"\n### {name}\n"]
    seeds = sorted(D)
    grp = defaultdict(list)
    for s in seeds:
        r = D[s]
        if r["agari_turn"] and r["agari_turn"] <= 12:
            continue
        if r["riichi_turn"] and r["riichi_turn"] <= 12:
            continue
        sh12 = r["sh"][12]
        grp[min(sh12, 3)].append(r)
    tot = sum(len(v) for v in grp.values())
    L.append(f"12巡目終了時点で未リーチ・未和了: {tot}局 / {len(seeds)}局 = {tot/len(seeds)*100:.1f}%\n")
    L.append("| 12巡目の向聴 | 該当局 | 構成比 | →18巡目までに聴牌到達 | →ツモ和了 |")
    L.append("|---|---|---|---|---|")
    for k in sorted(grp):
        v = grp[k]
        tenpai = sum(1 for r in v if any(r["sh"][t] <= 0 for t in range(13, 19)))
        agari = sum(1 for r in v if r["agari_turn"])
        lbl = {0: "聴牌(未リーチ)", 1: "1向聴", 2: "2向聴", 3: "3向聴以上"}[k]
        L.append(f"| {lbl} | {len(v)} | {len(v)/tot*100:.1f}% | "
                 f"{tenpai/len(v)*100:.1f}% | {agari/len(v)*100:.1f}% |")
    return "\n".join(L)


if __name__ == "__main__":
    A = load("baseline"); B = load("myrule")
    out = report(A, B)
    out += "\n\n## 『12巡目までにリーチできなければ』の実態\n"
    out += turn12_question(A, "baseline（受け入れ最大化・即リーチ）")
    out += "\n" + turn12_question(B, "myrule（R1/R2/R5/R6）")
    print(out)
