"""SQLite スキーマと薄いアクセス層。正本はこのDB。"""
import sqlite3, os, json, hashlib, datetime as dt

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id            TEXT PRIMARY KEY,   -- sha1(url)
  source_id     TEXT NOT NULL,
  source_name   TEXT,
  tier          TEXT,               -- S/A/B/C
  title         TEXT,
  summary       TEXT,
  url           TEXT,
  published_at  TEXT,               -- ISO8601 (JST)
  fetched_at    TEXT,
  cluster_id    TEXT,               -- 同一ニュースの束（転載の重複カウント防止）
  UNIQUE(url)
);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published_at);

CREATE TABLE IF NOT EXISTS triage (
  article_id   TEXT PRIMARY KEY,
  relevant     INTEGER,             -- 0/1
  markets      TEXT,                -- JSON配列 ["JP","FX"]
  event_type   TEXT,                -- 決算/金融政策/ガイダンス修正/M&A/規制/マクロ指標/その他
  entity_hint  TEXT,                -- JSON配列（銘柄名や通貨の手がかり）
  novelty      REAL,                -- 0-1 既出情報の焼き直しか
  model        TEXT,
  created_at   TEXT,
  FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS cycles (
  id           TEXT PRIMARY KEY,    -- YYYYMMDD-HHMM
  started_at   TEXT,
  finished_at  TEXT,
  n_articles   INTEGER,
  n_relevant   INTEGER,
  n_signals    INTEGER,
  cost_note    TEXT
);

-- LLMが個々の記事から出した生シグナル（集約前）
CREATE TABLE IF NOT EXISTS raw_signals (
  id            TEXT PRIMARY KEY,
  cycle_id      TEXT,
  article_id    TEXT,
  market        TEXT,               -- JP / FX / INDEX
  symbol        TEXT,
  name          TEXT,
  direction     TEXT,               -- long / short
  horizon_days  INTEGER,
  confidence    REAL,               -- 0-1 LLMの自己申告
  mechanism     TEXT,               -- なぜその方向か（因果の一文）
  priced_in     REAL,               -- 0-1 既に織り込まれている度合い（LLM自己申告）
  created_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_cycle ON raw_signals(cycle_id);

-- 集約後の提案シグナル（これが台帳の本体）
CREATE TABLE IF NOT EXISTS signals (
  id             TEXT PRIMARY KEY,
  cycle_id       TEXT,
  decided_at     TEXT NOT NULL,     -- ★このより後の価格でしか評価しない（先読み防止）
  market         TEXT,
  symbol         TEXT,
  yahoo          TEXT,
  name           TEXT,
  direction      TEXT,
  horizon_days   INTEGER,
  score          REAL,              -- 集約スコア
  tier           TEXT,              -- A/B/C
  n_sources      INTEGER,
  n_independent  INTEGER,
  thesis         TEXT,
  evidence       TEXT,              -- JSON: [{title,url,source,published_at}]
  status         TEXT DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_signals_decided ON signals(decided_at);

-- 情報源ごとの実績を測るため、個々の生シグナル（＝1ソースの単独主張）も評価する。
-- 集約後のsignalsは複数ソースが混ざるので、ソース別の成績を汚さずに測れない。
CREATE TABLE IF NOT EXISTS raw_evals (
  raw_signal_id TEXT,
  horizon_days  INTEGER,
  entry_time    TEXT,
  entry_price   REAL,
  exit_time     TEXT,
  exit_price    REAL,
  ret_gross     REAL,
  ret_net       REAL,
  bench_ret     REAL,
  ret_excess    REAL,
  hit           INTEGER,
  evaluated_at  TEXT,
  PRIMARY KEY(raw_signal_id, horizon_days)
);

-- reliability.py が書き出す情報源スコア（履歴を残す）
CREATE TABLE IF NOT EXISTS source_scores (
  computed_at   TEXT,
  source_id     TEXT,
  n             INTEGER,
  hit_rate      REAL,
  mean_excess   REAL,
  sd_excess     REAL,
  t_stat        REAL,
  shrunk_excess REAL,
  prior_weight  REAL,
  weight        REAL,
  PRIMARY KEY(computed_at, source_id)
);

CREATE TABLE IF NOT EXISTS evals (
  signal_id     TEXT,
  horizon_days  INTEGER,
  entry_time    TEXT,
  entry_price   REAL,
  exit_time     TEXT,
  exit_price    REAL,
  ret_gross     REAL,               -- 方向込みの素リターン(%)
  ret_net       REAL,               -- コスト差引後(%)
  bench_ret     REAL,               -- 同期間のベンチマーク(%)
  ret_excess    REAL,               -- ret_net - (方向符号 * bench_ret)
  hit           INTEGER,            -- ret_net > 0
  evaluated_at  TEXT,
  PRIMARY KEY(signal_id, horizon_days)
);
"""


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert_articles(con, rows) -> int:
    n = 0
    for r in rows:
        try:
            con.execute(
                """INSERT OR IGNORE INTO articles
                   (id,source_id,source_name,tier,title,summary,url,published_at,fetched_at,cluster_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (r["id"], r["source_id"], r["source_name"], r["tier"], r["title"],
                 r["summary"], r["url"], r["published_at"], r["fetched_at"], r.get("cluster_id")),
            )
            n += con.total_changes and 0 or 0
        except sqlite3.Error:
            pass
    con.commit()
    cur = con.execute("SELECT COUNT(*) c FROM articles")
    return cur.fetchone()["c"]


def jdump(o) -> str:
    return json.dumps(o, ensure_ascii=False)
