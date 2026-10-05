"""精度検証。ここが本体。

先読み防止の設計:
- エントリーは signals.decided_at の「日付より後」の最初の取引日の【始値】。
  判定した瞬間の価格では約定できないため、翌営業日寄りを使う。
- 決済は そこから horizon_days 本後の取引日の【終値】。
- 往復コストを必ず差し引く（config.verify.cost_pct）。
- ベンチマーク（TOPIX連動ETF）の同期間リターンを引いた「超過リターン」も出す。
  市場全体のドリフトを自分のエッジと誤認しないため。
- 方向を無視して常に買った場合（always-long）も同時に計算する。
  「方向判定に意味があったか」の最小の帰無仮説。
"""
from __future__ import annotations
import datetime as dt, math, statistics as st
from .db import now_iso

JST = dt.timezone(dt.timedelta(hours=9))


def _cost(cfg, market: str, symbol: str) -> float:
    c = cfg["verify"]["cost_pct"]
    if market == "FX":
        return c["fx"]
    if market == "INDEX":
        return c["jp_index"]
    return c["jp_stock"]


def _load_prices(symbols: list[str], start: dt.date, end: dt.date):
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        raise SystemExit("yfinance/pandas が未導入です: pip install -r requirements.txt")
    data = {}
    for s in symbols:
        try:
            df = yf.download(s, start=start.isoformat(), end=(end + dt.timedelta(days=3)).isoformat(),
                             progress=False, auto_adjust=False)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            data[s] = df
        except Exception as e:  # noqa: BLE001
            print(f"  価格取得失敗 {s}: {e}")
    return data


def _entry_exit(df, decided_date: dt.date, horizon: int):
    import pandas as pd
    idx = df.index
    after = idx[idx > pd.Timestamp(decided_date)]
    if len(after) == 0:
        return None
    e_ts = after[0]
    pos = idx.get_loc(e_ts)
    x_pos = pos + horizon
    if x_pos >= len(idx):
        return None
    x_ts = idx[x_pos]
    try:
        return (e_ts, float(df.loc[e_ts, "Open"]), x_ts, float(df.loc[x_ts, "Close"]))
    except Exception:
        return None


def _yahoo_map(universe: dict) -> dict:
    m = {}
    for k in ("fx", "jp_index", "jp_stocks"):
        for u in universe.get(k, []):
            m[u["symbol"]] = u["yahoo"]
    return m


def _pending_rows(con, universe) -> tuple[list[dict], list[dict]]:
    """まだ評価していない 集約シグナル と 生シグナル を返す。"""
    ym = _yahoo_map(universe)
    sig = [dict(r) for r in con.execute("""
        SELECT s.id, s.decided_at, s.market, s.symbol, s.yahoo, s.direction, s.horizon_days
        FROM signals s LEFT JOIN evals e
          ON e.signal_id = s.id AND e.horizon_days = s.horizon_days
        WHERE e.signal_id IS NULL ORDER BY s.decided_at""").fetchall()]
    raw = []
    for r in con.execute("""
        SELECT r.id, r.created_at AS decided_at, r.market, r.symbol, r.direction, r.horizon_days
        FROM raw_signals r LEFT JOIN raw_evals e
          ON e.raw_signal_id = r.id AND e.horizon_days = r.horizon_days
        WHERE e.raw_signal_id IS NULL ORDER BY r.created_at""").fetchall():
        d = dict(r)
        d["yahoo"] = ym.get(d["symbol"])
        if d["yahoo"]:
            raw.append(d)
    return sig, raw


def run(con, cfg, universe) -> dict:
    """集約シグナルと、情報源ごとの実績測定に使う生シグナルの両方を評価する。"""
    sig, raw = _pending_rows(con, universe)
    if not sig and not raw:
        return {"evaluated": 0, "raw_evaluated": 0, "pending": 0}

    syms = sorted({r["yahoo"] for r in sig + raw if r["yahoo"]} | {cfg["verify"]["baseline_symbol"]})
    dates = [dt.datetime.fromisoformat(r["decided_at"]).date() for r in sig + raw]
    prices = _load_prices(syms, min(dates) - dt.timedelta(days=10), dt.date.today())
    bench_df = prices.get(cfg["verify"]["baseline_symbol"])

    def evaluate(rows, table, id_col):
        n_ok = n_pend = 0
        for r in rows:
            df = prices.get(r["yahoo"])
            if df is None:
                n_pend += 1
                continue
            d = dt.datetime.fromisoformat(r["decided_at"]).date()
            ee = _entry_exit(df, d, r["horizon_days"])
            if ee is None:
                n_pend += 1   # まだ期間が満了していない
                continue
            e_ts, e_px, x_ts, x_px = ee
            sign = 1 if r["direction"] == "long" else -1
            gross = sign * (x_px - e_px) / e_px * 100
            net = gross - _cost(cfg, r["market"], r["symbol"])
            bench = 0.0
            if r["market"] != "FX" and bench_df is not None:
                bee = _entry_exit(bench_df, d, r["horizon_days"])
                if bee:
                    bench = (bee[3] - bee[1]) / bee[1] * 100
            excess = net - sign * bench
            con.execute(f"""INSERT OR REPLACE INTO {table}
                ({id_col},horizon_days,entry_time,entry_price,exit_time,exit_price,
                 ret_gross,ret_net,bench_ret,ret_excess,hit,evaluated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["id"], r["horizon_days"], str(e_ts.date()), e_px, str(x_ts.date()), x_px,
                 round(gross, 4), round(net, 4), round(bench, 4), round(excess, 4),
                 1 if net > 0 else 0, now_iso()))
            n_ok += 1
        return n_ok, n_pend

    a_ok, a_pend = evaluate(sig, "evals", "signal_id")
    b_ok, b_pend = evaluate(raw, "raw_evals", "raw_signal_id")
    con.commit()
    return {"evaluated": a_ok, "raw_evaluated": b_ok, "pending": a_pend + b_pend}


def _summ(vals: list[float]) -> dict:
    n = len(vals)
    if n == 0:
        return {"n": 0}
    m = st.fmean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = m / se if se and not math.isnan(se) and se > 0 else float("nan")
    return {"n": n, "mean": m, "sd": sd, "se": se, "t": t}


def stats(con, cfg) -> str:
    rows = con.execute("""
        SELECT s.tier, s.market, s.horizon_days, s.direction, s.decided_at,
               e.ret_net, e.ret_excess, e.hit, e.entry_price, e.exit_price
        FROM evals e JOIN signals s ON s.id = e.signal_id
        ORDER BY s.decided_at""").fetchall()
    rows = [dict(r) for r in rows]
    L = ["# 検証サマリ", "", f"集計時刻: {now_iso()}", "",
         "> n が小さいうちは全部ノイズ。判定は `平均 > 2*標準誤差` を最低ラインにする。",
         "> 「常に買い」列より明確に上でなければ、方向判定に意味はなかったということ。",
         "> **多重比較に注意**: Tier別・市場別・期間別を同時に見ているので、"
         "どこか1セルが t>2 になるのは偶然でも普通に起きる。"
         "判定は『全体』と、事前に1つだけ決めたセルで行う。後から良いセルを探して有意と言わない。", ""]
    if not rows:
        L.append("まだ評価済みシグナルがない。時間を置いて `python run.py verify` を再実行。")
        return "\n".join(L)

    def block(title, subset):
        s_net = _summ([r["ret_net"] for r in subset])
        s_exc = _summ([r["ret_excess"] for r in subset])
        # 方向を無視して常に買った場合
        al = [r["ret_net"] if r["direction"] == "long" else -r["ret_net"] for r in subset]
        s_al = _summ(al)
        hit = sum(r["hit"] for r in subset) / len(subset) * 100
        L.append(f"### {title}")
        L.append("")
        L.append("| 指標 | n | 平均(%) | 標準偏差 | 標準誤差 | t | 判定 |")
        L.append("|---|---|---|---|---|---|---|")
        for nm, s in (("純リターン", s_net), ("超過リターン", s_exc), ("常に買い(帰無)", s_al)):
            if s["n"] == 0:
                continue
            verdict = "有意っぽい" if (s["t"] == s["t"] and abs(s["t"]) >= 2) else "ノイズと区別不能"
            L.append(f'| {nm} | {s["n"]} | {s["mean"]:+.3f} | {s["sd"]:.3f} | '
                     f'{s["se"]:.3f} | {s["t"]:+.2f} | {verdict} |')
        L.append("")
        L.append(f"勝率 {hit:.1f}%（ただし勝率とエッジは別物。ロットはエッジで決める）")
        L.append("")

    block("全体", rows)
    for tier in ("A", "B", "C"):
        sub = [r for r in rows if r["tier"] == tier]
        if len(sub) >= 5:
            block(f"Tier {tier}", sub)
        elif sub:
            L.append(f"### Tier {tier}\n\nn={len(sub)} は少なすぎる。集計しない。\n")
    for mkt in ("JP", "FX", "INDEX"):
        sub = [r for r in rows if r["market"] == mkt]
        if len(sub) >= 5:
            block(f"市場 {mkt}", sub)
    for h in cfg["verify"]["horizons_days"]:
        sub = [r for r in rows if r["horizon_days"] == h]
        if len(sub) >= 5:
            block(f"保有 {h}営業日", sub)

    # アウトオブサンプル: 時系列で前半/後半に割る。前半で見えた効果が後半で消えたら蜃気楼。
    L.append("## アウトオブサンプル（前半 / 後半）")
    L.append("")
    if len(rows) < 40:
        L.append(f"n={len(rows)}。40未満で前後に割っても何も言えない。溜まってから見る。")
    else:
        half = len(rows) // 2
        first, second = rows[:half], rows[half:]
        L.append("| 期間 | n | 純リターン平均 | 超過リターン平均 | 勝率 |")
        L.append("|---|---|---|---|---|")
        for nm, sub in (("前半(IS)", first), ("後半(OOS)", second)):
            a = _summ([r["ret_net"] for r in sub])
            b = _summ([r["ret_excess"] for r in sub])
            hr = sum(r["hit"] for r in sub) / len(sub) * 100
            L.append(f'| {nm} | {a["n"]} | {a["mean"]:+.3f} | {b["mean"]:+.3f} | {hr:.1f}% |')
        L.append("")
        L.append("後半で符号が反転、または平均が半分以下になったら、前半の結果は採用しない。")
    L.append("")
    return "\n".join(L)
