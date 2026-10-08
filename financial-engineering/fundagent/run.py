#!/usr/bin/env python3
"""fundagent CLI

  python run.py cycle            # 収集→選別→抽出→集約→レポート（通常はこれだけ）
  python run.py cycle --dry-run  # APIキー無しで配線だけ確認
  python run.py verify           # 期間が満了したシグナルの結果を price で確定
  python run.py weights          # 情報源ごとの実績から重みを測り直す
  python run.py stats            # 的中率・EV・有意性の集計を vault に出力
  python run.py calibrate        # スコア分布からしきい値を決め直す（勘で決めない）
  python run.py models           # 使えるモデルIDの一覧（config.yaml に書き写す用）
  python run.py collect          # 収集だけ
"""
from __future__ import annotations
import argparse, datetime as dt, os, sys, yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fundagent import db, collect, analyze, aggregate, report, verify, reliability  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
JST = dt.timezone(dt.timedelta(hours=9))


def load(name):
    with open(os.path.join(ROOT, "config", name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def cycle_id() -> str:
    return dt.datetime.now(JST).strftime("%Y%m%d-%H%M")


def cmd_models(args):
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY が未設定")
    for m in anthropic.Anthropic(api_key=key).models.list(limit=50).data:
        print(f"{m.id:40s} {getattr(m, 'display_name', '')}")


def cmd_collect(args):
    cfg, src = load("config.yaml"), load("sources.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    res = collect.run(con, cfg, src)
    print(f'取得 {res["fetched"]}件')
    for s in res["status"]:
        mark = "OK  " if s["ok"] else ("skip" if s["ok"] is None else "NG  ")
        print(f'  {mark} {s["id"]:12s} n={s["n"]:3d} {s["msg"]}')
    return res


def cmd_cycle(args):
    from fundagent.llm import LLM
    cfg, src, uni = load("config.yaml"), load("sources.yaml"), load("universe.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    cid = cycle_id()
    con.execute("INSERT OR REPLACE INTO cycles(id,started_at) VALUES (?,?)", (cid, db.now_iso()))

    print("[1/4] 収集")
    cres = collect.run(con, cfg, src)
    for s in cres["status"]:
        mark = "OK  " if s["ok"] else ("skip" if s["ok"] is None else "NG  ")
        print(f'  {mark} {s["id"]:12s} n={s["n"]:3d} {s["msg"]}')

    roles = collect.role_map(src)
    llm = LLM(cfg, dry_run=args.dry_run)
    print("[2/4] 選別(triage)")
    rel = analyze.triage(con, llm, cfg, cid, roles)
    print(f"  材料あり {len(rel)}件")

    print("[3/4] 抽出(extract)")
    raw = analyze.extract(con, llm, cfg, uni, cid, rel, roles)
    print(f"  生シグナル {len(raw)}件")

    print("[4/4] 集約→レポート")
    sigs = aggregate.run(con, cfg, uni, cid)
    stats = {"n_articles": cres["fetched"], "n_relevant": len(rel),
             "n_raw": len(raw), "usage": llm.usage_note()}
    path = report.write_report(cfg, cid, sigs, cres["status"], stats)
    ledger = report.append_ledger(cfg, sigs)
    con.execute("""UPDATE cycles SET finished_at=?,n_articles=?,n_relevant=?,n_signals=?,cost_note=?
                   WHERE id=?""",
                (db.now_iso(), cres["fetched"], len(rel), len(sigs), llm.usage_note(), cid))
    con.commit()
    print(f"  提案 {len(sigs)}件")
    print(f"  レポート: {path}")
    print(f"  台帳:     {ledger}")
    print(f"  {llm.usage_note()}")


def cmd_verify(args):
    cfg, uni = load("config.yaml"), load("universe.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    res = verify.run(con, cfg, uni)
    print(f'集約シグナル確定 {res["evaluated"]}件 / '
          f'情報源別の単独シグナル確定 {res["raw_evaluated"]}件 / '
          f'未満了・取得不可 {res["pending"]}件')


def cmd_weights(args):
    cfg = load("config.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    scores, meta = reliability.compute(con, cfg)
    reliability.persist(con, scores)
    text = reliability.report(scores, meta, cfg)
    wpath = reliability.save_weights(cfg, scores, meta, ROOT)
    out = os.path.join(os.path.expanduser(cfg["paths"]["vault_dir"]), "情報源スコア.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n重みファイル: {wpath}")
    print(f"レポート:     {out}")


def cmd_stats(args):
    cfg = load("config.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    text = verify.stats(con, cfg)
    out = os.path.join(os.path.expanduser(cfg["paths"]["vault_dir"]), "検証ログ.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n保存: {out}")


def cmd_calibrate(args):
    cfg, uni = load("config.yaml"), load("universe.yaml")
    con = db.connect(os.path.join(ROOT, cfg["paths"]["db"]))
    text = aggregate.distribution(con, cfg, uni)
    out = os.path.join(os.path.expanduser(cfg["paths"]["vault_dir"]), "しきい値較正.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n保存: {out}")


def main():
    ap = argparse.ArgumentParser(description="fundagent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("collect", cmd_collect), ("cycle", cmd_cycle),
                     ("verify", cmd_verify), ("stats", cmd_stats), ("models", cmd_models),
                     ("calibrate", cmd_calibrate), ("weights", cmd_weights)):
        p = sub.add_parser(name)
        p.add_argument("--dry-run", action="store_true", help="LLMを呼ばずスタブで動かす")
        p.set_defaults(func=fn)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
