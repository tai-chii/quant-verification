# -*- coding: utf-8 -*-
"""
numerai_yoru.py  夜間キューから毎晩実行（2026-10-04）。Mac のターミナルは Numerai に届くので、昼間の Claude が取れないものを取る。
1. メタモデルの予測（vX.Y/meta_model.parquet）を data/ に取り直す（1日以上古ければ）。MMC を自分で計算するため。
2. 今のデータ版を確かめ、新しい版が出ていたら知らせる（学習し直しは手動で判断）。
3. 本番の成績（ラウンドごとの CORR・MMC）を取れるか試す。API キーが環境変数（NUMERAI_PUBLIC_ID・NUMERAI_SECRET_KEY）にあれば使う。なければ飛ばす。
結果は results/yoru_status.txt に追記する。
"""
import os, re, time, datetime as dt
from numerapi import NumerAPI
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data"); RES = os.path.join(HERE, "results")
log = []
def say(s): print(s, flush=True); log.append(s)
napi = NumerAPI(os.environ.get("NUMERAI_PUBLIC_ID"), os.environ.get("NUMERAI_SECRET_KEY"))
ds = napi.list_datasets()
vers = sorted({m.group(1) for d in ds for m in [re.match(r"^(v\d+\.\d+)/", d)] if m}, key=lambda v: tuple(int(x) for x in v[1:].split(".")))
V = vers[-1]; vf = os.path.join(DATA, "VERSION"); cur = open(vf).read().strip() if os.path.exists(vf) else "なし"
say(f"データ版: 最新 {V}・手元 {cur}" + ("" if V == cur else "  ← 新しい版が出ている（学習し直すかは Claude と相談）"))
mm = [d for d in ds if d.startswith(f"{cur}/") and "meta_model" in d] or [d for d in ds if d.startswith(f"{V}/") and "meta_model" in d]
say(f"メタモデルのファイル: {mm}")
for src in mm:
    dst = os.path.join(DATA, os.path.basename(src))
    if os.path.exists(dst) and time.time() - os.path.getmtime(dst) < 86400:
        say(f"  {src}: 1日以内に取得済み（飛ばした）"); continue
    try:
        napi.download_dataset(src, dst + ".tmp"); os.replace(dst + ".tmp", dst); say(f"  {src}: 取得 {os.path.getsize(dst)/1e6:.1f}MB")
    except Exception as e:
        say(f"  {src}: 失敗 {e}")
try:
    import pandas as pd
    m = pd.read_parquet(os.path.join(DATA, "meta_model.parquet"))
    say(f"  メタモデル: {len(m):,}行・列 {list(m.columns)[:5]}・エラ {m['era'].min() if 'era' in m else '?'}〜{m['era'].max() if 'era' in m else '?'}")
except Exception as e:
    say(f"  メタモデルの中身の確認: {e}")
if os.environ.get("NUMERAI_PUBLIC_ID"):
    try:
        import pandas as pd
        models = napi.get_models(tournament=8); say(f"モデル: {sorted(models)}")
        rows = []
        for name, mid in models.items():
            for r in napi.round_model_performances_v2(mid)[:20]:
                row = dict(model=name, round=r.get("roundNumber"))
                row.update({k: v for k, v in r.items() if k != "roundNumber" and not isinstance(v, (list, dict))})
                for s in (r.get("submissionScores") or []): row[str(s.get("displayName"))] = s.get("value")
                rows.append(row)
        pd.DataFrame(rows).to_csv(os.path.join(RES, "live_scores.csv"), index=False); say(f"本番の成績: {len(rows)}行を results/live_scores.csv に保存")
    except Exception as e:
        say(f"本番の成績: 取得できず（{e}）")
else:
    say("本番の成績: API キーが環境変数にないので飛ばした（数字が出始めるのは10月9日ごろ）")
open(os.path.join(RES, "yoru_status.txt"), "a", encoding="utf-8").write(f"\n== {dt.datetime.now():%Y-%m-%d %H:%M}\n" + "\n".join(log) + "\n")
say("完了")
