"""Obsidian vault へレポートを書き出す（知識層＝正本）。"""
from __future__ import annotations
import datetime as dt, json, os, csv

JST = dt.timezone(dt.timedelta(hours=9))
DIR_JA = {"long": "買い", "short": "売り"}
TIER_JA = {"A": "A（強い・独立ソース複数）", "B": "B（中）", "C": "C（弱い・監視のみ）"}


def _vault(cfg) -> str:
    return os.path.expanduser(cfg["paths"]["vault_dir"])


def write_report(cfg, cycle_id: str, signals: list[dict], collect_status: list[dict],
                 stats: dict) -> str:
    base = _vault(cfg)
    rdir = os.path.join(base, cfg["paths"]["report_subdir"])
    os.makedirs(rdir, exist_ok=True)
    path = os.path.join(rdir, f"{cycle_id}.md")
    now = dt.datetime.now(JST)

    L = []
    L.append(f"# ファンダ提案 {cycle_id}")
    L.append("")
    L.append(f"生成: {now.isoformat(timespec='seconds')} / サイクルID: `{cycle_id}`")
    L.append("")
    L.append("> これは**仮説の提示**であって投資助言ではない。"
             "Tierは「情報の強さ」であって「勝てる確率」ではない。"
             "的中率が実測で出るまで、この順位は未検証である。")
    L.append("")
    L.append(f"記事 {stats.get('n_articles',0)}件 → 材料あり {stats.get('n_relevant',0)}件 "
             f"→ 生シグナル {stats.get('n_raw',0)}件 → 提案 {len(signals)}件 "
             f"｜ LLM: {stats.get('usage','-')}")
    L.append("")

    if not signals:
        L.append("## 提案なし")
        L.append("")
        L.append("しきい値を超える材料が出なかった。**これは正常な結果**で、"
                 "無理に提案を出すほうが検証を汚す。")
        L.append("")

    for tier in ("A", "B", "C"):
        rows = [s for s in signals if s["tier"] == tier][: cfg["report"]["max_signals_per_tier"]]
        if not rows:
            continue
        L.append(f"## Tier {TIER_JA[tier]}")
        L.append("")
        L.append("| 対象 | 方向 | 期間 | スコア | 独立ソース |")
        L.append("|---|---|---|---|---|")
        for s in rows:
            L.append(f'| {s["name"]}({s["symbol"]}) | **{DIR_JA[s["direction"]]}** | '
                     f'{s["horizon_days"]}営業日 | {s["score"]:.2f} | {s["n_independent"]} |')
        L.append("")
        for s in rows:
            L.append(f'### {s["name"]}({s["symbol"]}) — {DIR_JA[s["direction"]]} / {s["horizon_days"]}営業日')
            L.append("")
            L.append(f'- 仮説: {s["thesis"] or "（記載なし）"}')
            L.append(f'- スコア {s["score"]:.3f} ／ 支持記事 {s["n_sources"]}件（独立 {s["n_independent"]}件）')
            L.append(f'- 判定時刻: {s["decided_at"]} ← **この時刻より後の価格でしか検証しない**')
            L.append("- 根拠記事:")
            for e in json.loads(s["evidence"])[:6]:
                w = e.get("weight")
                wtxt = f', 重み {w:.2f}' if w is not None else ""
                L.append(f'    - [{e["source"]}/{e["tier"]}] [{e["title"]}]({e["url"]}) '
                         f'（{e["published_at"]}, conf {e["confidence"]:.2f}, '
                         f'織込 {e["priced_in"]:.2f}{wtxt}）')
            L.append("")

    L.append("## 収集ステータス")
    L.append("")
    L.append("| ソース | 結果 | 件数 | 備考 |")
    L.append("|---|---|---|---|")
    for s in collect_status:
        mark = "OK" if s["ok"] else ("スキップ" if s["ok"] is None else "失敗")
        L.append(f'| {s["id"]} | {mark} | {s["n"]} | {s["msg"]} |')
    L.append("")
    L.append("---")
    L.append("")
    L.append("関連: [[_設計メモ]] ／ [[検証ログ]] ／ 台帳 `シグナル台帳.csv`")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def append_ledger(cfg, signals: list[dict]) -> str:
    """シグナル台帳CSV（正本）。verifyがここに結果を書き戻す前提の追記専用ファイル。"""
    base = _vault(cfg)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "シグナル台帳.csv")
    cols = ["id", "cycle_id", "decided_at", "market", "symbol", "name", "direction",
            "horizon_days", "tier", "score", "n_independent", "thesis"]
    new = not os.path.exists(path)
    existing = set()
    if not new:
        with open(path, encoding="utf-8") as f:
            existing = {r["id"] for r in csv.DictReader(f)}
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for s in signals:
            if s["id"] in existing:
                continue
            w.writerow({c: s.get(c, "") for c in cols})
    return path
