# -*- coding: utf-8 -*-
"""
03_submit.py  今のラウンドの live データを取得し、予測して提出する
使い方: python3 ~/ワークスペース/検証/verification-lab/competitions/numerai/03_submit.py <モデル名> [small|medium]
準備（1回だけ）:
  1. numer.ai でモデルを作る（Models → 新規。名前は半角英数）
  2. Account → API Keys で「Upload submissions」「View user info」にチェックしたキーを作る
  3. キーをこのフォルダの外に置く（vault に入れない・チャットに貼らない）:
       mkdir -p ~/.numerai && nano ~/.numerai/keys
     中身は2行:  public_id=XXXX  と  secret_key=YYYY
       chmod 600 ~/.numerai/keys
"""
import os, sys, pickle
import pandas as pd
from numerapi import NumerAPI
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
if len(sys.argv) < 2:
    print("使い方: python3 03_submit.py <モデル名> [small|medium]"); sys.exit(1)
NAME = sys.argv[1]; FS = (sys.argv[2] if len(sys.argv) > 2 else "small").lower()
kv = dict(l.strip().split("=", 1) for l in open(os.path.expanduser("~/.numerai/keys")) if "=" in l)
napi = NumerAPI(kv["public_id"], kv["secret_key"])
models = napi.get_models()
if NAME not in models:
    print(f"モデル「{NAME}」が見つからない。numer.ai にあるモデル: {list(models)}"); sys.exit(1)
pk = pickle.load(open(os.path.join(HERE, "models", f"baseline_{FS}.pkl"), "rb"))
V = pk["version"]; rnd = napi.get_current_round()
live_path = os.path.join(DATA, f"live_{rnd}.parquet")
if not os.path.exists(live_path):
    napi.download_dataset(f"{V}/live.parquet", live_path)
live = pd.read_parquet(live_path, columns=pk["features"])
pred = pd.Series(pk["model"].predict(live[pk["features"]]), index=live.index).rank(pct=True).rename("prediction")
os.makedirs(os.path.join(HERE, "submissions"), exist_ok=True)
out = os.path.join(HERE, "submissions", f"{NAME}_round{rnd}.csv"); pred.to_frame().to_csv(out)
sid = napi.upload_predictions(out, model_id=models[NAME])
log = os.path.join(HERE, "results", "submissions_log.csv")
pd.DataFrame([dict(round=rnd, model=NAME, feature_set=FS, rows=len(pred), submission_id=sid,
                   submitted_at=pd.Timestamp.now(tz="Asia/Tokyo").isoformat())]).to_csv(log, mode="a", header=not os.path.exists(log), index=False)
print(f"提出しました: ラウンド {rnd}・{len(pred):,}行・submission_id={sid}")
