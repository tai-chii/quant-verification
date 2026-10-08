#!/usr/bin/env python3
"""雀魂_戦績.csv を読み、累積値から区間（前回スナップショットからの差分）を逆算する。

使い方:  python3 code/senseki.py            # 標準出力に表示
        python3 code/senseki.py --inject   # 雀魂_戦績台帳.md の AUTO ブロックを差し替え
出力  :  形式ごとの累積表と区間表（markdown）。標準誤差つき。
注意  :  雀魂が表示するのは全部「累積値」。区間の値は差分から逆算した推定で、
         1試合あたりの局数が一定という近似が入っている。
"""
import csv, math, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
# 対戦データ・台帳は非公開（Obsidian vault側）に置く想定。環境変数 MAHJONG_DATA_DIR で
# そのフォルダ（雀魂_戦績.csv・雀魂_戦績台帳.md がある場所）を指す。未設定時はこのスクリプトの
# 一つ上の階層を見る（コードとデータを同じ場所に置いて使うケース向けのフォールバック）。
DATA_DIR = os.environ.get("MAHJONG_DATA_DIR", os.path.join(HERE, ".."))
CSV = os.path.join(DATA_DIR, "雀魂_戦績.csv")
MD  = os.path.join(DATA_DIR, "雀魂_戦績台帳.md")
BEGIN, END = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"

# 1試合あたりの平均局数（連荘・南入込みの概算）。区間の局単位指標の標準誤差にだけ使う。
KYOKU = {"東風": 5.5, "半荘": 9.5}
# 順位の標準偏差（4着順がほぼ均等なときの値）
SD_RANK = 1.12
# 比較基準：雀魂牌譜屋の玉の間平均（2022-05-18時点・四人打ち・東風/半荘混在）
TAMA = {"和了率": 21.44, "放銃率": 14.09, "立直率": 18.69, "副露率": 32.26, "平均和了": 6559}

RANK = ["1位率", "2位率", "3位率", "4位率"]
RATE = ["和了率", "放銃率", "立直率", "副露率"]          # 局単位・単純差分でよい
WEIGHTED = ["平均和了", "和了巡数", "ツモ率"]            # 和了数で重みづけが要る


def load():
    with open(CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["対戦数"].strip()]
    for r in rows:
        for k, v in list(r.items()):
            if k in ("記録日", "形式", "段位", "備考"):
                continue
            r[k] = float(v) if v.strip() else None
    return rows


def days_between(d1, d2):
    try:
        y1, m1, dd1 = [int(x) for x in d1.replace("/", "-").split("-")]
        y2, m2, dd2 = [int(x) for x in d2.replace("/", "-").split("-")]
        return (date(y2, m2, dd2) - date(y1, m1, dd1)).days
    except Exception:
        return None


def window(a, b):
    """スナップショット a → b の区間を逆算する。"""
    na, nb = a["対戦数"], b["対戦数"]
    n = nb - na
    o = {"対戦数": n, "日数": days_between(a["記録日"], b["記録日"])}
    for k in RANK + ["飛び率"] + RATE:
        o[k] = (b[k] / 100 * nb - a[k] / 100 * na) / n * 100
    o["平均順位"] = (b["平均順位"] * nb - a["平均順位"] * na) / n
    ag_a = a["和了率"] / 100 * na          # 和了数 ÷ 1試合あたり局数（比なので約分される）
    ag_b = b["和了率"] / 100 * nb
    dag = ag_b - ag_a
    for k in WEIGHTED:
        sc = 100 if k == "ツモ率" else 1
        o[k] = (b[k] / sc * ag_b - a[k] / sc * ag_a) / dag * sc
    return o


def se_rank(games):
    return SD_RANK / math.sqrt(games)


def se_rate(p, games, fmt):
    n = games * KYOKU[fmt]
    p = p / 100
    return math.sqrt(max(p * (1 - p), 1e-9) / n) * 100


def fmt_row(label, d, fmt, se=True):
    cells = [label, f"{d['平均順位']:.3f}"]
    if se:
        cells[-1] += f" ±{se_rank(d['対戦数']):.3f}"
    for k in RANK + ["飛び率"]:
        cells.append(f"{d[k]:.2f}%")
    for k in ["和了率", "放銃率"]:
        s = f"{d[k]:.2f}%"
        if se:
            s += f" ±{se_rate(d[k], d['対戦数'], fmt):.2f}"
        cells.append(s)
    cells += [f"{d['立直率']:.2f}%", f"{d['副露率']:.2f}%",
              f"{d['平均和了']:.0f}", f"{d['和了巡数']:.2f}", f"{d['ツモ率']:.2f}%"]
    days = d.get("日数")
    cells.append("—" if not days else f"{d['対戦数'] / days:.1f}戦/日（{days:.0f}日）")
    return "| " + " | ".join(cells) + " |"


HEAD = ("| 区間 | 平均順位 | 1位 | 2位 | 3位 | 4位 | 飛び | 和了率 | 放銃率 | 立直率 | 副露率 | 平均和了 | 和了巡数 | ツモ率 | ペース |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def report():
    out, orig = [], sys.stdout
    class Cap:
        def write(self, t): out.append(t)
        def flush(self): pass
    sys.stdout = Cap()
    try:
        main()
    finally:
        sys.stdout = orig
    return "".join(out).strip()


def inject():
    body = report()
    with open(MD, encoding="utf-8") as f:
        s = f.read()
    if BEGIN not in s or END not in s:
        print(f"AUTOブロックが見つからない: {MD}", file=sys.stderr)
        return 1
    head, rest = s.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    with open(MD, "w", encoding="utf-8") as f:
        f.write(f"{head}{BEGIN}\n\n{body}\n\n{END}{tail}")
    print(f"更新: {os.path.basename(MD)}")
    return 0


def main():
    rows = load()
    for fmt in ("東風", "半荘"):
        snaps = sorted([r for r in rows if r["形式"] == fmt], key=lambda r: r["対戦数"])
        if not snaps:
            continue
        print(f"\n## {fmt}戦（1試合あたり{KYOKU[fmt]}局と仮定）\n")
        print("### 累積値\n")
        print(HEAD)
        for s in snaps:
            print(fmt_row(f"〜{s['対戦数']:.0f}戦", s, fmt))
        if len(snaps) > 1:
            print("\n### 区間（差分から逆算）\n")
            print(HEAD)
            print(fmt_row(f"1〜{snaps[0]['対戦数']:.0f}戦", snaps[0], fmt))
            for a, b in zip(snaps, snaps[1:]):
                w = window(a, b)
                print(fmt_row(f"{a['対戦数']:.0f}〜{b['対戦数']:.0f}戦", w, fmt))
        last = snaps[-1]
        print(f"\n### 玉の間平均との差（累積{last['対戦数']:.0f}戦）\n")
        print("| 指標 | 自分 | 玉の間平均 | 差 |")
        print("|---|---|---|---|")
        for k, v in TAMA.items():
            d = last[k] - v
            unit = "" if k == "平均和了" else "%"
            f2 = ".0f" if k == "平均和了" else ".2f"
            print(f"| {k} | {last[k]:{f2}}{unit} | {v}{unit} | {d:+{f2}}{unit} |")


if __name__ == "__main__":
    sys.exit(inject() if "--inject" in sys.argv else main())
