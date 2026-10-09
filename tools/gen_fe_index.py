#!/usr/bin/env python3
"""financial-engineering/ 配下の検証一覧（INDEX.md）を各ディレクトリの README から自動生成する。

使い方: python3 tools/gen_fe_index.py
- 問い: README の最初の見出し（# ...）。README が無い場合は financial-engineering/README.md の
  「主な検証」表の「対象」列を使う。
- 判定: README 中の「**解釈: …**」を優先し、無ければ「結論: **…**」「判定: **…**」「**結論: …**」「## 判定: …」の最初の一致。
  見つからなければ「—」（未実行・未記載）。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "financial-engineering"
OUT = FE / "INDEX.md"
MAXLEN = 60

VERDICT_PATTERNS = [  # 上ほど優先（機械判定より人の解釈を優先する）
    re.compile(r"\*\*解釈[:：]\s*(.+?)\*\*"),
    re.compile(r"\*\*(?:機械)?(?:結論|判定)[:：]\s*(.+?)\*\*"),
    re.compile(r"(?:結論|判定)[:：]\s*\*\*(.+?)\*\*"),
    re.compile(r"^##\s*(?:結論|判定)[:：]\s*(.+)$"),
]


def curated_targets():
    """主な検証の表から {dir: 対象} を取る（README が無いディレクトリの補完用）。"""
    p = FE / "README.md"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\[([^\]]+)\]\([^)]*\)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def short(s):
    s = re.sub(r"\s+", " ", s.strip()).strip("。 ")
    return s if len(s) <= MAXLEN else s[: MAXLEN - 1] + "…"


def parse(d, fallback):
    readme = d / "README.md"
    if not readme.exists():
        if d.name in fallback:
            return fallback[d.name], "README の「主な検証」表を参照"
        return "（README なし）", "—"
    lines = readme.read_text(encoding="utf-8").splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), d.name)
    title = re.sub(r"\s*—\s*", "：", title)
    verdict = "—"
    for pat in VERDICT_PATTERNS:
        m = next((pat.search(l) for l in lines if pat.search(l)), None)
        if m:
            verdict = short(m.group(1))
            break
    return title.replace("|", "／"), verdict.replace("|", "／")


def main():
    fallback = curated_targets()
    dirs = sorted(p for p in FE.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    rows = []
    for d in dirs:
        q, v = parse(d, fallback)
        rows.append(f"| [{d.name}](./{d.name}) | {q} | {v} |")
    text = (
        "# financial-engineering 検証一覧\n\n"
        "> このファイルは `python3 tools/gen_fe_index.py` で自動生成しています。手で編集しないでください。\n\n"
        f"全 {len(rows)} 件。判定の「—」は未実行または README に判定の記載がないもの。"
        "詳細は各ディレクトリの README を参照。\n\n"
        "| ディレクトリ | 問い | 判定 |\n| :--- | :--- | :--- |\n" + "\n".join(rows) + "\n"
    )
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
