#!/usr/bin/env bash
# <コンペ>/kernels/<名前>/ にある kernel-metadata.json を Kaggle に push する。
# コードの正本は notebooks/ に置き、kernels/<名前>/SOURCE にその相対パスを1行で書く。
# 使い方: push_kernels.sh [--dry-run]   (Kaggle CLI と認証が必要。--dry-run は検査のみ)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
dry=0; [ "${1:-}" = "--dry-run" ] && dry=1
found=0
for d in "$root"/*/kernels/*/; do
  [ -f "$d/kernel-metadata.json" ] || continue
  [ -f "$d/SKIP" ] && { echo "skip: $d"; continue; }  # 実行済みカーネルは再pushしない
  found=1
  src="$d/$(tr -d '\r\n' < "$d/SOURCE")"
  [ -f "$src" ] || { echo "ERROR: SOURCE が見つからない: $src" >&2; exit 1; }
  code_file="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['code_file'])" "$d/kernel-metadata.json")"
  [ "$code_file" = "$(basename "$src")" ] || { echo "ERROR: code_file($code_file) と SOURCE のファイル名が違う: $d" >&2; exit 1; }
  echo "==> $d  ($code_file)"
  [ "$dry" = 1 ] && continue
  tmp="$(mktemp -d)"
  cp "$d/kernel-metadata.json" "$tmp/"; cp "$src" "$tmp/"
  kaggle kernels push -p "$tmp"
  rm -rf "$tmp"
done
[ "$found" = 1 ] || echo "kernels/ が見つからない"
