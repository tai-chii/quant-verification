#!/usr/bin/env python3
"""実験ログ.csv の指定 exp 行に Public LB を記入する（その行だけを文字列置換。他の行は一切触らない）。

使い方:
  python3 record_lb.py <コンペdir名> <exp_id> <score>            # 変更内容を表示するだけ（dry-run）
  python3 record_lb.py <コンペdir名> <exp_id> <score> --apply    # 実際に書き込む
例:
  python3 record_lb.py enveda-casmi-2026 exp_004 0.125 --apply
前提: 対象行の lb_public が空欄であること（すでに値があれば中止）。
"""
import re, sys
from pathlib import Path

BASELINE = 0.122  # 現状ベスト（exp_001/003）。比較表示用

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if len(args) != 3:
        sys.exit(__doc__)
    comp, exp, score = args
    float(score)
    path = Path(__file__).resolve().parents[1] / comp / "notebooks" / "実験ログ.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = [i for i, l in enumerate(lines) if l.startswith(exp + ",")]
    if len(idx) != 1:
        sys.exit(f"ERROR: {exp} の行が {len(idx)} 件ある（1件のはず）")
    i = idx[0]
    old = lines[i]
    # cv_mean と cv_std の直後の空の lb_public 欄（次がクォート始まりの notes）を探す
    pat = re.compile(r',,,("(?:Smoke|[^"]))')
    if not pat.search(old):
        sys.exit("ERROR: lb_public が空欄の行ではない（すでに記入済み？）。手動で確認して")
    new = pat.sub(lambda m: f',,{score},{m.group(1)}', old, count=1)
    delta = float(score) - BASELINE
    new = new.replace(
        "PENDING: not yet run on real Kaggle LB.",
        f"Kaggle run 2026-10-09 done; Public LB {score} (delta vs exp_001 {BASELINE}: {delta:+.3f}); COCONUT fallback used for 24/400 molecules.",
        1,
    )
    print(f"--- {path.name} ({exp}) ---")
    print(f"lb_public: (空欄) -> {score}   delta vs {BASELINE}: {delta:+.3f}")
    print("PENDING 表記も置換:", "PENDING: not yet run" not in new)
    if apply:
        lines[i] = new
        path.write_text("".join(lines), encoding="utf-8")
        print("書き込み完了")
    else:
        print("(dry-run。--apply を付けると書き込む)")

if __name__ == "__main__":
    main()
