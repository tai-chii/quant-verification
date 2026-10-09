#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q137 の補足診断（事後・判定には使わない。2026-10-09 Opus）。
本番（kensho_data_source_signal_agreement_q137.py）の機械判定「データ源は規則の定義の一部」の原因を切り分ける:
不一致は「値の差」か「Yahoo の終値の時刻・日付ラベル」か。
- Yahoo 為替日足の |終値−始値| と 高安幅 の中央値
- Yahoo 終値(t) を Dukascopy H1 の始値（Yahoo の日付 00:00 UTC + off 時間, off=-24..72）と比べ、日ごとに最も近い off
- off=+24h（＝Dukascopy の UTC 日足終値と同じ時刻）で |差|>10bp の日の割合（曜日別・年別）
決定的・乱数なし。出力: results/Q137_diag_<日時>.json
"""
import os, json, datetime as dt, unicodedata
import numpy as np, pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); WS=os.path.abspath(os.path.join(HERE,"..","..","..",".."))
def _p(*a):
    x=os.path.join(WS,*a)
    return x if os.path.exists(x) else os.path.join(WS,*[unicodedata.normalize("NFD",s) for s in a])
D=_p("検証","学問","金融工学","作業","FX","システムトレード")
SYMS=["EURUSD","GBPUSD","AUDUSD","USDJPY","EURJPY","GBPJPY"]; OFFS=list(range(-24,73))
out={}
for s in SYMS:
    y=pd.read_csv(os.path.join(D,f"data_{s}_D1_yahoo.csv"),parse_dates=["time"]).set_index("time")
    h=pd.read_csv(os.path.join(D,f"data_{s}_H1_dukascopy.csv"),parse_dates=["time"]).set_index("time")
    A=np.vstack([np.abs(y.close.values/h.open.reindex(y.index+pd.Timedelta(hours=o)).values-1)*1e4 for o in OFFS])
    ok=np.isfinite(A[OFFS.index(24)]); A=np.where(np.isfinite(A),A,np.inf)
    best=np.array(OFFS)[A.argmin(0)][ok]; d24=A[OFFS.index(24)][ok]; d0=A[OFFS.index(0)][ok]
    idx=y.index[ok]; bad=d24>10
    out[s]=dict(n=int(ok.sum()),
        yahoo_med_abs_close_minus_open_bp=float(((y.close/y.open-1).abs()*1e4).median()),
        yahoo_med_high_low_bp=float(((y.high/y.low-1)*1e4).median()),
        med_abs_diff_bp_at_off24=float(np.median(d24)), med_abs_diff_bp_at_off0=float(np.median(d0)),
        share_best_off24=float((best==24).mean()), share_best_off0=float((best==0).mean()),
        share_abs_diff_gt10bp_at_off24=float(bad.mean()),
        share_bad_by_dow={int(k):float(v) for k,v in pd.Series(bad,index=idx).groupby(idx.dayofweek).mean().items()},
        share_bad_by_year={int(k):float(v) for k,v in pd.Series(bad,index=idx).groupby(idx.year).mean().items()},
        yahoo_dow_counts={int(k):int(v) for k,v in y.index.dayofweek.value_counts().sort_index().items()})
    o=out[s]; print(f"{s}: |C-O|med={o['yahoo_med_abs_close_minus_open_bp']:.2f}bp H-L med={o['yahoo_med_high_low_bp']:.1f}bp  best=+24h {o['share_best_off24']:.2f} / 0h {o['share_best_off0']:.2f}  |d|>10bp@+24h {o['share_abs_diff_gt10bp_at_off24']:.3f}")
p=os.path.join(HERE,"results",f"Q137_diag_{dt.datetime.now():%Y%m%d_%H%M%S}.json")
json.dump(dict(note="事後の補足診断。判定には使わない",results=out),open(p,"w"),ensure_ascii=False,indent=1); print(p)
