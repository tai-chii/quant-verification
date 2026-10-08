"""LLM二段解析。
段1 triage : 安いモデルで「そもそも売買材料か」を選別（記事の8割をここで落とす）
段2 extract: 賢いモデルで「銘柄・方向・確度・織り込み度」を構造化抽出
"""
from __future__ import annotations
import json
from .db import sha1, now_iso, jdump

# ------------------------------------------------------------------ 段1

TRIAGE_SYSTEM = """あなたは金融ニュースの選別器です。日本株とドル円を含むFXのトレード材料になるかだけを判定します。

判定基準:
- relevant=true にするのは「特定の企業の業績・事業・資本政策」か「金利・為替・景気に効くマクロ/政策」に関する新規の事実がある記事だけ。
- 以下は relevant=false: 一般社会ニュース、人事の細目、既報のまとめ、コラム/オピニオン、相場後講釈（「日経平均は〇〇円高」など結果の記述）、広告・PR。
- novelty は「この情報がどれだけ新しいか」。既報の焼き直し=0.0、初出の事実=1.0。
- ただし【二次情報(相場観)】と付いた記事は例外で、書き手が特定の通貨ペア/銘柄の方向に言及していれば relevant=true にする（コラム/オピニオンだが、その書き手の的中率を測るために拾う）。
- 迷ったら relevant=false にする。取りこぼしより誤検出のほうが有害。

出力は必ず次のJSONのみ。説明文を書かない。
{"results":[{"i":<入力番号>,"relevant":true/false,"markets":["JP"|"FX"|"US"],"event_type":"決算|業績修正|受注・提携|M&A|資本政策|規制・訴訟|金融政策|マクロ指標|地政学|商品市況|その他","entities":["企業名や通貨名"],"novelty":0.0}]}"""


def triage(con, llm, cfg, cycle_id: str, roles: dict[str, str] | None = None) -> list[dict]:
    rows = con.execute("""
        SELECT a.* FROM articles a LEFT JOIN triage t ON t.article_id=a.id
        WHERE t.article_id IS NULL ORDER BY a.published_at DESC""").fetchall()
    rows = [dict(r) for r in rows]
    bs = cfg["llm"]["triage_batch_size"]
    model = cfg["llm"]["triage_model"]
    out = []
    for i in range(0, len(rows), bs):
        batch = rows[i:i + bs]
        roles = roles or {}
        lines = []
        for j, b in enumerate(batch):
            kind = "【二次情報(相場観)】" if roles.get(b["source_id"]) == "opinion" else ""
            lines.append(f'[{j}] ({b["source_name"]}/{b["tier"]}){kind} {b["title"]}\n    {b["summary"][:220]}')
        user = "次の記事を判定してください。\n\n" + "\n".join(lines)
        stub = {"results": [{"i": j, "relevant": j % 4 == 0, "markets": ["JP"],
                             "event_type": "その他", "entities": [], "novelty": 0.5}
                            for j in range(len(batch))]}
        res = llm.call_json(model, TRIAGE_SYSTEM, user, stub)
        by_i = {r.get("i"): r for r in res.get("results", [])}
        for j, b in enumerate(batch):
            r = by_i.get(j, {"relevant": False, "markets": [], "event_type": "その他",
                             "entities": [], "novelty": 0.0})
            con.execute("""INSERT OR REPLACE INTO triage
                (article_id,relevant,markets,event_type,entity_hint,novelty,model,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (b["id"], 1 if r.get("relevant") else 0, jdump(r.get("markets", [])),
                 r.get("event_type", "その他"), jdump(r.get("entities", [])),
                 float(r.get("novelty", 0.0) or 0.0), model, now_iso()))
            if r.get("relevant"):
                b["triage"] = r
                out.append(b)
        con.commit()
    return out


# ------------------------------------------------------------------ 段2

EXTRACT_SYSTEM = """あなたは慎重なファンダメンタルズ・アナリストです。与えられたニュースから、売買方向の仮説を構造化して出力します。

絶対に守る規則:
1. 記事に書かれていない事実を作らない。推論は mechanism に「なぜその方向か」を一文で書き、根拠が弱ければ confidence を下げる。
2. confidence は「その方向に動く主観確率」。0.5 は優位なしを意味する。ほとんどのニュースは 0.50〜0.65 に収まるはず。0.75 を超えるのは、決算の大幅サプライズや政策変更のような明確な材料だけ。
3. priced_in は「その情報が既に価格に織り込まれている度合い」(0=未反映, 1=完全反映)。公開ニュースの大半は高い。事前に観測されていた/報道済みの内容なら 0.7 以上を付ける。正直に高く見積もること。
4. 対象は与えられた監視ユニバースの銘柄・通貨ペアのみ。該当がなければそのニュースからはシグナルを出さない（無理に出さない）。
5. 相場の結果を述べただけの記事、観測気球、アナリスト個人の見通しからはシグナルを出さない。
6. horizon_days は材料の持続期間の見積り: 1(即日で消化), 5(数日), 20(四半期の業績観に効く)。

種別が【二次情報(相場観)】の記事の扱い:
- これは書き手個人の相場見通しであって事実の報道ではない。**書き手が明示した方向だけを抜き出す。**
  書かれていない方向をこちらで推論して補わない。方向が明示されていなければ、その記事からは何も出さない。
- 「〇〇を上抜けたら買い」のような条件付きの見解は、条件が満たされたか判定できないので出さない。
- confidence は「書き手がどれだけ強く断定しているか」ではなく、**あなたから見たその主張の確からしさ**。
  書き手の断定口調に引きずられない。根拠が示されていなければ 0.55 以下にする。
- priced_in は「その見解が既に市場のコンセンサスになっているか」と読み替える。
  誰もが言っている話なら高く、独自の視点なら低く。
- mechanism には書き手の論拠を一文で要約する（あなたの意見ではなく、書き手の論拠）。

出力は必ず次のJSONのみ。該当なしなら signals を空配列にする。
{"signals":[{"article_index":0,"market":"JP"|"FX"|"INDEX","symbol":"7203","direction":"long"|"short","horizon_days":5,"confidence":0.60,"priced_in":0.70,"mechanism":"一文"}]}"""


def _universe_block(universe: dict, cfg: dict) -> str:
    parts = ["【FX】"]
    parts += [f'  {u["symbol"]}={u["name"]}' for u in universe.get("fx", [])]
    parts.append("【指数】")
    parts += [f'  {u["symbol"]}={u["name"]}' for u in universe.get("jp_index", [])]
    parts.append("【日本株】")
    parts += [f'  {u["symbol"]}={u["name"]}({u.get("sector","")})' for u in universe.get("jp_stocks", [])]
    return "\n".join(parts)


def extract(con, llm, cfg, universe: dict, cycle_id: str, articles: list[dict],
            roles: dict[str, str] | None = None) -> list[dict]:
    if not articles:
        return []
    articles = articles[: cfg["llm"]["extract_max_articles"]]
    model = cfg["llm"]["extract_model"]
    lines = []
    roles = roles or {}
    for j, a in enumerate(articles):
        tg = a.get("triage", {})
        kind = "【二次情報(相場観)】" if roles.get(a["source_id"]) == "opinion" else "【報道・開示】"
        lines.append(
            f'[{j}] {a["published_at"]} ({a["source_name"]}/信頼度{a["tier"]}/種別{tg.get("event_type","")}) {kind}\n'
            f'    見出し: {a["title"]}\n    要旨: {a["summary"][:300]}')
    user = ("監視ユニバース:\n" + _universe_block(universe, cfg) +
            "\n\n---\nニュース一覧:\n" + "\n".join(lines) +
            "\n\n上の規則に従ってシグナルを抽出してください。")
    stub = {"signals": [{"article_index": 0, "market": "FX", "symbol": "USDJPY",
                         "direction": "long", "horizon_days": 5, "confidence": 0.58,
                         "priced_in": 0.6, "mechanism": "（dry-run のダミー）"}]}
    res = llm.call_json(model, EXTRACT_SYSTEM, user, stub)

    valid = set()
    for k in ("fx", "jp_index", "jp_stocks"):
        valid |= {u["symbol"] for u in universe.get(k, [])}

    out = []
    for s in res.get("signals", []):
        try:
            idx = int(s["article_index"])
            a = articles[idx]
        except Exception:
            continue
        sym = str(s.get("symbol", "")).strip()
        if sym not in valid and not cfg["aggregate"]["allow_off_universe"]:
            continue
        if s.get("direction") not in ("long", "short"):
            continue
        rid = sha1(f'{cycle_id}|{a["id"]}|{sym}|{s["direction"]}')
        row = {"id": rid, "cycle_id": cycle_id, "article_id": a["id"],
               "market": s.get("market", ""), "symbol": sym, "name": "",
               "direction": s["direction"],
               "horizon_days": int(s.get("horizon_days", 5) or 5),
               "confidence": float(s.get("confidence", 0.5) or 0.5),
               "mechanism": str(s.get("mechanism", ""))[:400],
               "priced_in": float(s.get("priced_in", 0.7) or 0.7),
               "created_at": now_iso()}
        con.execute("""INSERT OR REPLACE INTO raw_signals
            (id,cycle_id,article_id,market,symbol,name,direction,horizon_days,
             confidence,mechanism,priced_in,created_at)
            VALUES (:id,:cycle_id,:article_id,:market,:symbol,:name,:direction,
             :horizon_days,:confidence,:mechanism,:priced_in,:created_at)""", row)
        out.append(row)
    con.commit()
    return out
