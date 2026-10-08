"""収集レイヤ: 公開フィード/APIから記事メタを取得してDBへ。

方針:
- 取得するのは「配信目的で公開されたフィード/API」のみ。
- 本文の全文取得・保存はしない（タイトル＋公式サマリのみ）。有料記事の複製を避けるため。
- 取れなかったソースは黙って飛ばし、レポートに「欠測」として残す。
"""
from __future__ import annotations
import datetime as dt, difflib, html, re, unicodedata
from typing import Any

import requests
import feedparser

from .db import sha1, now_iso

JST = dt.timezone(dt.timedelta(hours=9))

# ------------------------------------------------------------------ robots.txt

_ROBOTS: dict[str, object] = {}


def robots_ok(url: str, ua: str) -> bool:
    """robots.txt を確認する。取得できない/未設置なら許可とみなす（慣例どおり）。

    フィード配信は許可されているのが普通だが、二次情報ブログを足すときに
    「禁止されている先を踏まない」ための防護柵として全取得に通す。
    """
    from urllib.parse import urlsplit
    from urllib.robotparser import RobotFileParser
    sp = urlsplit(url)
    host = f"{sp.scheme}://{sp.netloc}"
    rp = _ROBOTS.get(host)
    if rp is None:
        rp = RobotFileParser()
        rp.set_url(host + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = "allow"           # 取得できない = 判断材料なし = 許可
        _ROBOTS[host] = rp
    if rp == "allow":
        return True
    try:
        return rp.can_fetch(ua, url)
    except Exception:
        return True


def _get(url: str, cfg: dict, params: dict | None = None):
    ua = cfg["collect"]["user_agent"]
    if not robots_ok(url, ua):
        raise PermissionError("robots.txt で禁止されているため取得しない")
    r = requests.get(url, params=params, headers={"User-Agent": ua},
                     timeout=cfg["collect"]["timeout_sec"])
    r.raise_for_status()
    return r


def _clean(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^\w぀-ヿ一-鿿]+", "", s)


def _to_jst(struct_time) -> str | None:
    if not struct_time:
        return None
    try:
        d = dt.datetime(*struct_time[:6], tzinfo=dt.timezone.utc)
        return d.astimezone(JST).isoformat(timespec="seconds")
    except Exception:
        return None


def fetch_rss(src: dict, cfg: dict) -> list[dict]:
    r = _get(src["url"], cfg)
    feed = feedparser.parse(r.content)
    out = []
    for e in feed.entries[: cfg["collect"]["max_per_source"]]:
        url = e.get("link") or ""
        if not url:
            continue
        pub = _to_jst(e.get("published_parsed") or e.get("updated_parsed"))
        out.append({
            "id": sha1(url),
            "source_id": src["id"], "source_name": src["name"], "tier": src["tier"],
            "title": _clean(e.get("title")),
            "summary": _clean(e.get("summary") or e.get("description"))[:600],
            "url": url,
            "published_at": pub or now_iso(),
            "fetched_at": now_iso(),
        })
    return out


def fetch_tdnet(src: dict, cfg: dict) -> list[dict]:
    """TDnet適時開示。yanoshin webapi（無料・キー不要）経由。"""
    ua = cfg["collect"]["user_agent"]
    hours = cfg["collect"]["lookback_hours"]
    limit = cfg["collect"]["max_per_source"]
    url = f'{src["url"].rstrip("/")}/recent.json' if not src["url"].endswith(".json") else src["url"]
    r = _get(url, cfg, params={"limit": limit})
    items = r.json().get("items", [])
    cutoff = dt.datetime.now(JST) - dt.timedelta(hours=hours)
    out = []
    for it in items:
        t = it.get("Tdnet") or {}
        pub_raw = t.get("pubdate")
        try:
            pub = dt.datetime.strptime(pub_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        except Exception:
            continue
        if pub < cutoff:
            continue
        doc = t.get("document_url") or ""
        code = (t.get("company_code") or "")[:4]
        out.append({
            "id": sha1(doc or f'{t.get("id")}'),
            "source_id": src["id"], "source_name": src["name"], "tier": src["tier"],
            "title": f'【適時開示】{t.get("company_name","")}({code}) {t.get("title","")}',
            "summary": f'開示種別の推定は本文タイトルから。市場: {t.get("markets_string","")}',
            "url": doc,
            "published_at": pub.isoformat(timespec="seconds"),
            "fetched_at": now_iso(),
        })
    return out


def fetch_html_list(src: dict, cfg: dict) -> list[dict]:
    """RSSを持たないブログ用。一覧ページから「見出し＋リンク＋日付」だけを取る。

    本文は取得・保存しない（見出しとリンクのみ。要旨は空になる）。
    セレクタはサイト構造に依存するので壊れやすい。壊れたら sources.yaml の
    selectors を直す。直せないソースは enabled: false にして切る。
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise SystemExit("beautifulsoup4 が未導入です: pip install -r requirements.txt")
    sel = src.get("selectors") or {}
    r = _get(src["url"], cfg)
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select(sel.get("item", "article"))[: cfg["collect"]["max_per_source"]]
    from urllib.parse import urljoin
    out = []
    for it in items:
        a = it.select_one(sel.get("link", "a[href]"))
        if not a or not a.get("href"):
            continue
        url = urljoin(src["url"], a["href"])
        t_el = it.select_one(sel["title"]) if sel.get("title") else a
        title = _clean(t_el.get_text() if t_el else "")
        if not title:
            continue
        pub = None
        if sel.get("date"):
            d_el = it.select_one(sel["date"])
            raw = (d_el.get("datetime") if d_el and d_el.has_attr("datetime")
                   else (_clean(d_el.get_text()) if d_el else ""))
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
                try:
                    d = dt.datetime.strptime(raw[:len(dt.datetime.now().strftime(fmt))], fmt)
                    pub = d.replace(tzinfo=d.tzinfo or JST).astimezone(JST).isoformat(timespec="seconds")
                    break
                except Exception:
                    continue
        out.append({
            "id": sha1(url),
            "source_id": src["id"], "source_name": src["name"], "tier": src["tier"],
            "title": title, "summary": "", "url": url,
            "published_at": pub or now_iso(), "fetched_at": now_iso(),
        })
    return out


FETCHERS = {"rss": fetch_rss, "tdnet_api": fetch_tdnet, "html_list": fetch_html_list}


def role_map(sources: dict) -> dict[str, str]:
    """source_id -> role ("news" | "opinion")。extract のプロンプト分岐に使う。"""
    return {s["id"]: s.get("role", "news") for s in sources.get("sources", [])}


def cluster(rows: list[dict], threshold: float = 0.72) -> None:
    """タイトル類似で束ねる。通信社の配信が複数媒体に載った場合を1件と数えるため。"""
    reps: list[tuple[str, str]] = []  # (norm_title, cluster_id)
    for r in rows:
        nt = _norm_title(r["title"])
        cid = None
        for rt, rid in reps:
            if difflib.SequenceMatcher(None, nt, rt).ratio() >= threshold:
                cid = rid
                break
        if cid is None:
            cid = r["id"]
            reps.append((nt, cid))
        r["cluster_id"] = cid


def run(con, cfg: dict, sources: dict, only: list[str] | None = None) -> dict[str, Any]:
    hours = cfg["collect"]["lookback_hours"]
    cutoff = dt.datetime.now(JST) - dt.timedelta(hours=hours)
    all_rows: list[dict] = []
    status: list[dict] = []
    for src in sources["sources"]:
        if src.get("enabled") is False:
            status.append({"id": src["id"], "ok": None, "n": 0, "msg": "無効化"})
            continue
        if only and src["id"] not in only:
            continue
        fn = FETCHERS.get(src["kind"])
        if fn is None:
            status.append({"id": src["id"], "ok": False, "n": 0, "msg": f'未対応kind={src["kind"]}'})
            continue
        try:
            rows = fn(src, cfg)
            kept = []
            for r in rows:
                try:
                    p = dt.datetime.fromisoformat(r["published_at"])
                except Exception:
                    continue
                if p.tzinfo is None:
                    p = p.replace(tzinfo=JST)
                if p >= cutoff:
                    kept.append(r)
            all_rows.extend(kept)
            status.append({"id": src["id"], "ok": True, "n": len(kept), "msg": ""})
        except Exception as e:
            status.append({"id": src["id"], "ok": False, "n": 0, "msg": f"{type(e).__name__}: {e}"[:160]})

    cluster(all_rows)
    seen = set()
    uniq = []
    for r in all_rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)

    for r in uniq:
        con.execute(
            """INSERT OR IGNORE INTO articles
               (id,source_id,source_name,tier,title,summary,url,published_at,fetched_at,cluster_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (r["id"], r["source_id"], r["source_name"], r["tier"], r["title"], r["summary"],
             r["url"], r["published_at"], r["fetched_at"], r.get("cluster_id")))
    con.commit()
    return {"fetched": len(uniq), "status": status}
