#!/usr/bin/env bash
# 上位Notebookを raw_solutions/ に収集する
#
# 使い方: ./pull_top_kernels.sh <competition-slug> [件数]
#
# ★ taichi 自身の Terminal.app で実行すること。
#   Claude のシェルからは kaggle.com に到達できない（egress遮断・2026-09-08実測）。
#
# 注意: これで取れるのは公開Notebookのみ。
# 1位解法は Discussion のテキストで公開されることが多く、APIでは取れない。
# そちらは手動で読み、kaggle/_playbook/解法メモ/ に蒸留すること。
# 生コードを溜めること自体には価値がない。

set -euo pipefail
SLUG="${1:?usage: pull_top_kernels.sh <competition-slug> [n]}"
N="${2:-15}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/${SLUG}/raw_solutions"
mkdir -p "$DIR"

echo "== 上位 ${N} 件を取得: ${SLUG}"
kaggle kernels list --competition "$SLUG" --sort-by voteCount --page-size "$N" -v \
  | tail -n +2 | cut -d, -f1 | while read -r REF; do
    [ -z "$REF" ] && continue
    echo "-- $REF"
    kaggle kernels pull "$REF" -p "$DIR/${REF//\//__}" -m || echo "   skip: $REF"
done

echo
echo "取得先: $DIR"
echo "次: 生コードを読ませるのではなく、kaggle/_playbook/解法メモ/_テンプレート.md で1枚に蒸留する"
