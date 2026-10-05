"""生シグナルを銘柄×期間で集約し、信頼度Tierを付ける。

スコアの考え方（意図的に単純・説明可能にしてある）:
  edge_i  = (confidence - 0.5) * 2 * (1 - priced_in)   # 織り込み済みの材料は価値を割り引く
  weight_i= tier_weight(情報源) * 2^(-経過時間/半減期)
  net     = Σ sign_i * edge_i * weight_i               # long:+ short:-
  score   = |net| , direction = sign(net)
独立ソース数は cluster_id（見出し類似で束ねた単位）で数える。同じ通信社記事の転載を2件と数えないため。
"""
from __future__ import annotations
import datetime as dt, json, math, os
from .db import sha1, now_iso, jdump
from . import reliability

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JST = dt.timezone(dt.timedelta(hours=9))


def _decay(published_at: str, now: dt.datetime, half_life_h: float) -> float:
    try:
        p = dt.datetime.fromisoformat(published_at)
        if p.tzinfo is None:
            p = p.replace(tzinfo=JST)
    except Exception:
        return 0.5
    age_h = max(0.0, (now - p).total_seconds() / 3600)
    return 0.5 ** (age_h / half_life_h)


def _yahoo_map(universe: dict) -> dict:
    m = {}
    for k in ("fx", "jp_index", "jp_stocks"):
        for u in universe.get(k, []):
            m[u["symbol"]] = (u["yahoo"], u["name"], k)
    return m


def compute(con, cfg, universe, cycle_id: str, weights: dict | None = None) -> list[dict]:
    now = dt.datetime.now(JST)
    hl = cfg["aggregate"]["recency_half_life_hours"]
    tw = cfg["tier_weights"]
    # 実績から測った重みがあれば tier の勘より優先する（run.py weights で生成）
    learned = reliability.load_weights(ROOT) if weights is None else weights
    ymap = _yahoo_map(universe)

    rows = con.execute("""
        SELECT r.*, a.title, a.url, a.source_id, a.source_name, a.tier, a.published_at, a.cluster_id
        FROM raw_signals r JOIN articles a ON a.id = r.article_id
        WHERE r.cycle_id = ?""", (cycle_id,)).fetchall()

    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["market"], r["symbol"], r["horizon_days"]), []).append(dict(r))

    decided_at = now_iso()
    out = []
    for (market, symbol, horizon), items in groups.items():
        net = 0.0
        ev = []
        for it in items:
            edge = (it["confidence"] - 0.5) * 2 * (1 - it["priced_in"])
            base = learned.get(it["source_id"], tw.get(it["tier"], 0.2))
            w = base * _decay(it["published_at"], now, hl)
            sign = 1 if it["direction"] == "long" else -1
            net += sign * edge * w
            ev.append({"title": it["title"], "url": it["url"], "source": it["source_name"],
                       "source_id": it["source_id"], "weight": round(base, 3),
                       "tier": it["tier"], "published_at": it["published_at"],
                       "direction": it["direction"], "confidence": it["confidence"],
                       "priced_in": it["priced_in"], "mechanism": it["mechanism"],
                       "cluster_id": it["cluster_id"]})
        if abs(net) < 1e-9:
            continue
        direction = "long" if net > 0 else "short"
        score = abs(net)
        agree = [e for e in ev if e["direction"] == direction]
        n_independent = len({e["cluster_id"] for e in agree})

        th = cfg["aggregate"]["tier_thresholds"]
        minsrc = cfg["aggregate"]["min_independent_sources"]
        tier = "-"
        for t in ("A", "B", "C"):
            if score >= th[t] and n_independent >= minsrc[t]:
                tier = t
                break

        yahoo, name, _kind = ymap.get(symbol, (symbol, symbol, "jp_stocks"))
        thesis = " / ".join(dict.fromkeys(e["mechanism"] for e in agree if e["mechanism"]))[:600]
        sid = sha1(f"{cycle_id}|{market}|{symbol}|{horizon}|{direction}")
        row = {"id": sid, "cycle_id": cycle_id, "decided_at": decided_at, "market": market,
               "symbol": symbol, "yahoo": yahoo, "name": name, "direction": direction,
               "horizon_days": horizon, "score": round(score, 4), "tier": tier,
               "n_sources": len(agree), "n_independent": n_independent,
               "thesis": thesis, "evidence": jdump(ev), "status": "open"}
        out.append(row)
    out.sort(key=lambda r: (r["tier"], -r["score"]))
    return out


def run(con, cfg, universe, cycle_id: str) -> list[dict]:
    """採択されたシグナル（tier A/B/C）だけをDBに保存して返す。"""
    rows = compute(con, cfg, universe, cycle_id)
    kept = [r for r in rows if r["tier"] != "-"]
    for row in kept:
        con.execute("""INSERT OR REPLACE INTO signals
            (id,cycle_id,decided_at,market,symbol,yahoo,name,direction,horizon_days,
             score,tier,n_sources,n_independent,thesis,evidence,status)
            VALUES (:id,:cycle_id,:decided_at,:market,:symbol,:yahoo,:name,:direction,
             :horizon_days,:score,:tier,:n_sources,:n_independent,:thesis,:evidence,:status)""", row)
    con.commit()
    return kept


def distribution(con, cfg, universe) -> str:
    """しきい値を「勘」でなく「分布」で決めるための集計。

    kaggle/CLAUDE.md の原則（判断を測定に置き換える）をここにも適用する。
    tier_thresholds は本来こうして決めるべきで、初期値は完全に暫定である。
    """
    import statistics as st
    cids = [r["id"] for r in con.execute("SELECT id FROM cycles ORDER BY id").fetchall()]
    learned = reliability.load_weights(ROOT)
    scores, nind = [], []
    for cid in cids:
        for r in compute(con, cfg, universe, cid, weights=learned):
            scores.append(r["score"])
            nind.append(r["n_independent"])
    L = ["# スコア分布（しきい値較正用）", ""]
    if len(scores) < 20:
        L.append(f"候補 n={len(scores)}。20未満では分布を語れない。サイクルを回してから再実行する。")
        return "\n".join(L)
    scores.sort()

    def q(p):
        return scores[min(len(scores) - 1, int(len(scores) * p))]

    L.append(f"候補グループ n={len(scores)}  中央値={st.median(scores):.3f}  最大={scores[-1]:.3f}")
    L.append("")
    L.append("| 分位 | スコア | 意味 |")
    L.append("|---|---|---|")
    for p, why in ((0.50, "半分がここ以上"), (0.70, "上位30%"), (0.90, "上位10%"), (0.97, "上位3%")):
        L.append(f"| {int(p*100)}% | {q(p):.3f} | {why} |")
    L.append("")
    L.append("提案しきい値（上位3% / 10% / 30% を A/B/C に当てる案）:")
    L.append("```yaml")
    L.append("tier_thresholds:")
    L.append(f"  A: {q(0.97):.2f}")
    L.append(f"  B: {q(0.90):.2f}")
    L.append(f"  C: {q(0.70):.2f}")
    L.append("```")
    L.append("")
    L.append("※ これは「どれだけ絞るか」の決定であって「当たるか」の決定ではない。")
    L.append("  当たるかどうかは verify/stats の超過リターンだけが答える。")
    return "\n".join(L)
