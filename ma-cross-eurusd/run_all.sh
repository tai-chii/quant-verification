#!/bin/bash
# Mac 用: 全パターン計算（Windows と分担）→ 集計 → レポート
# 使い方:  ./run_all.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
WS="$(cd "$HERE/../../.." && pwd)"                      # ~/ワークスペース
cd "$WS"
DATA="vault/40_市場/FX/システムトレード/data_EURUSD_H4_dukascopy.csv"
OUT="作業層/市場/ma_cross_eurusd/results"
caffeinate -i python3 "$HERE/bt.py" --data "$DATA" --out "$OUT" --step 2 --max-period 500 --start-frac 0.0 "$@"
D="$OUT/step2_p5-500_SMA-EMA"
if [ -f "$D/null_max.npz" ]; then
  python3 "$HERE/analyze.py" "$D" && open "$D/report.html"
else
  echo "Windows 側の分がまだ同期されていません。少し待ってから ./run_all.sh をもう一度（済みの分は飛ばします）"
fi
