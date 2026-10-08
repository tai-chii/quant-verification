# -*- coding: utf-8 -*-
"""
01_download.py  Numerai の最新データを取得する（キー不要）
使い方（Mac のターミナル）:
    pip install numerapi lightgbm pyarrow pandas
    python3 ~/ワークスペース/検証/verification-lab/competitions/numerai/01_download.py
- 最新のデータ版（vX.Y/）を自動で選び、features.json・train.parquet・validation.parquet・validation_benchmark_models.parquet（BMC の計算用）を data/ に保存する。
- 既にあるファイルは取り直さない。成功／失敗を最後に表示する。
"""
import os, re, sys
from numerapi import NumerAPI
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data"); os.makedirs(DATA, exist_ok=True)
napi = NumerAPI()
ds = napi.list_datasets()
vers = sorted({m.group(1) for d in ds for m in [re.match(r"^(v\d+\.\d+)/", d)] if m},
              key=lambda v: tuple(int(x) for x in v[1:].split(".")))
if not vers:
    print("データ版が見つからない。ネット接続を確認して再実行"); sys.exit(1)
V = vers[-1]; print("データ版:", V)
open(os.path.join(DATA, "VERSION"), "w").write(V)
res = {}
for f in ["features.json", "train.parquet", "validation.parquet", "validation_benchmark_models.parquet"]:
    src = f"{V}/{f}"; dst = os.path.join(DATA, f)
    if src not in ds:
        res[f] = "提供元になし"; continue
    if os.path.exists(dst):
        res[f] = "取得済み（飛ばした）"; continue
    try:
        napi.download_dataset(src, dst); res[f] = "成功"
    except Exception as e:
        res[f] = f"失敗: {e}"
for k, v in res.items(): print(f"  {k}: {v}")
print("完了。Claude に「numeraiのデータ取れた」と伝えてください。" if all(not v.startswith("失敗") for v in res.values()) else "失敗があります。時間をおいて再実行してください。")
