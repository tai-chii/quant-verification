#!/bin/bash
# 10 を終わるまで繰り返す（各回は時間制限なし）
cd "$(dirname "$0")"
for i in $(seq 1 40); do
  LIMIT=100000 python3 10_medium_ender_neutral.py >> results/run10_log.txt 2>&1
  if grep -q "^判定 K" results/run10_log.txt; then echo "完了" >> results/run10_log.txt; break; fi
done
