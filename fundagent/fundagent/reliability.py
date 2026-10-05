"""情報源の信頼度を「実績」から測り、重みに変換する。

目的:
  config.yaml の tier_weights（S=1.0, A=0.7 …）は完全に勘で置いた値だった。
  ここを実測に置き換える。これが二次情報ブログを足せる前提条件でもある
  ——素性のわからない発信者でも、実績が溜まれば重みは自動で決まる。

測り方:
  集約後の signals は複数ソースが混ざるので、ソース別の成績を測れない。
  そこで raw_signals（＝1記事＝1ソースの単独主張）を個別に評価した raw_evals を使う。
  「そのソースの言うとおりに毎回入っていたら、超過リターンはいくつだったか」を直接測る。

縮約（ここが要）:
  n=5 で平均+2%の発信者に重み2.0を与えたら、ただの運を増幅する装置になる。
  かといって tier（こちらの先入観）を掛け続けると、実績を出した無名ブログが
  永久に格上げされない。そこで経験ベイズの形で「先入観から実績へ」乗り換える:

      λ      = n / (n + k)                    # k = 事前分布の強さ（既定30）
      w_ev   = 1 + mean_excess / sd_pool      # 実績だけから決まる重み。tier を見ない
      weight = clip( (1-λ) * prior_weight + λ * w_ev , floor, cap )

  n=0  → λ=0 → 重みは tier の事前値そのまま（コールドスタートが滑らか）
  n≫k  → λ→1 → tier は消え、実績だけが重みを決める

  この形にしてあるので、tier C の個人ブログでも実績を積めば tier S を追い越せる。
  逆に tier S でも成績が悪ければ下がる。**tier は初期値であって、結論ではない。**

  sd_pool は全ソース通算の超過リターン（1シグナルあたり）の標準偏差。
  「1標準偏差ぶん平均が良いソースは重み +1.0」というスケール。
"""
from __future__ import annotations
import math, os, statistics as st
from .db import now_iso


def _rows(con):
    return [dict(r) for r in con.execute("""
        SELECT a.source_id, a.source_name, a.tier,
               e.ret_excess, e.ret_net, e.hit, r.horizon_days
        FROM raw_evals e
        JOIN raw_signals r ON r.id = e.raw_signal_id
        JOIN articles a    ON a.id = r.article_id""").fetchall()]


def compute(con, cfg) -> tuple[list[dict], dict]:
    rows = _rows(con)
    k = cfg.get("reliability", {}).get("prior_strength", 30)
    floor = cfg.get("reliability", {}).get("weight_floor", 0.05)
    cap = cfg.get("reliability", {}).get("weight_cap", 2.0)
    tw = cfg["tier_weights"]

    all_exc = [r["ret_excess"] for r in rows]
    sd_pool = st.stdev(all_exc) if len(all_exc) > 2 else 1.0
    if sd_pool <= 0:
        sd_pool = 1.0

    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["source_id"], []).append(r)

    out = []
    for sid, rs in sorted(by.items()):
        n = len(rs)
        exc = [r["ret_excess"] for r in rs]
        m = st.fmean(exc)
        sd = st.stdev(exc) if n > 1 else 0.0
        se = sd / math.sqrt(n) if n > 1 and sd > 0 else float("nan")
        t = m / se if se == se and se > 0 else float("nan")
        lam = n / (n + k)
        shrunk = m * lam
        prior = tw.get(rs[0]["tier"], 0.2)
        w_ev = 1.0 + m / sd_pool
        w = min(cap, max(floor, (1 - lam) * prior + lam * w_ev))
        out.append({"source_id": sid, "source_name": rs[0]["source_name"], "tier": rs[0]["tier"],
                    "n": n, "hit_rate": sum(r["hit"] for r in rs) / n * 100,
                    "mean_excess": m, "sd_excess": sd, "t_stat": t,
                    "shrunk_excess": shrunk, "prior_weight": prior, "weight": w})
    out.sort(key=lambda r: -r["weight"])
    meta = {"sd_pool": sd_pool, "k": k, "n_total": len(rows)}
    return out, meta


def save_weights(cfg, scores: list[dict], meta: dict, root: str) -> str:
    """aggregate が読む自動生成ファイル。手編集しない。"""
    path = os.path.join(root, "config", "source_weights.yaml")
    L = ["# 自動生成ファイル。手で編集しない（`python run.py weights` が上書きする）。",
         "# aggregate はこのファイルがあれば tier_weights より優先して使う。",
         f"computed_at: '{now_iso()}'",
         f"n_total: {meta['n_total']}",
         f"prior_strength: {meta['k']}",
         "weights:"]
    for s in scores:
        L.append(f'  {s["source_id"]}: {s["weight"]:.4f}   # n={s["n"]} 縮約後超過={s["shrunk_excess"]:+.3f}%')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def load_weights(root: str) -> dict:
    path = os.path.join(root, "config", "source_weights.yaml")
    if not os.path.exists(path):
        return {}
    import yaml
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    return d.get("weights") or {}


def report(scores: list[dict], meta: dict, cfg) -> str:
    L = ["# 情報源スコア（実績にもとづく重み）", "", f"集計: {now_iso()}",
         f"評価済み単独シグナル n={meta['n_total']} ／ 縮約の強さ k={meta['k']} "
         f"／ 超過リターンの母標準偏差 {meta['sd_pool']:.2f}%", ""]
    if meta["n_total"] < 50:
        L += ["> **まだ重みを動かす段階ではない。** n が k(=事前分布の強さ) を大きく超えるまで、",
              "> 縮約が効いて重みはほぼ tier の初期値のまま動かない。それが正しい挙動である。", ""]
    L += ["> **多重比較に注意。** 情報源が10個あれば、実力ゼロでも1個は t>2 になる。",
          "> 「一番成績の良いソース」を後から選んで有意と言わない。", ""]
    if not scores:
        L.append("評価済みの単独シグナルがまだない。`run.py verify` を回してから再実行する。")
        return "\n".join(L)

    L += ["| 情報源 | tier | n | 勝率 | 平均超過(%) | t | 縮約後 | 事前重み | 採用重み |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in scores:
        t = f'{s["t_stat"]:+.2f}' if s["t_stat"] == s["t_stat"] else "-"
        L.append(f'| {s["source_name"]} | {s["tier"]} | {s["n"]} | {s["hit_rate"]:.0f}% | '
                 f'{s["mean_excess"]:+.3f} | {t} | {s["shrunk_excess"]:+.3f} | '
                 f'{s["prior_weight"]:.2f} | **{s["weight"]:.2f}** |')
    L.append("")

    contrarian = [s for s in scores if s["n"] >= 50 and s["t_stat"] == s["t_stat"] and s["t_stat"] <= -2]
    if contrarian:
        L += ["## 逆張り候補（自動適用はしない）", "",
              "継続的にマイナスの超過リターンを出しているソース。逆に張れば勝てる可能性はあるが、",
              "**符号の自動反転はしない**。偶然の連敗と本物の逆相関は n が十分でも見分けにくく、",
              "反転を自動化すると壊れ方が読めなくなる。手動で仮説として検証すること。", ""]
        for s in contrarian:
            L.append(f'- {s["source_name"]}: n={s["n"]}, 平均超過 {s["mean_excess"]:+.3f}%, t={s["t_stat"]:+.2f}')
        L.append("")

    dead = [s for s in scores if s["weight"] <= 0.1]
    if dead:
        L += ["## 実質的に無視されているソース", "",
              "重みが下限に張り付いている。`sources.yaml` で `enabled: false` にして、"
              "収集コストと LLM コストを減らすことを検討する。", ""]
        for s in dead:
            L.append(f'- {s["source_name"]} (n={s["n"]}, 重み {s["weight"]:.2f})')
        L.append("")

    L += ["---", "",
          "重みの定義:  ",
          "`λ = n / (n + k)`  ",
          "`w_ev = 1 + 平均超過リターン / sd_pool`  （実績だけから決まる。tier を見ない）  ",
          "`weight = clip((1-λ) * 事前重み + λ * w_ev, floor, cap)`  ",
          "",
          "n=0 なら tier の初期値そのまま。n が k を大きく超えると tier は消え、実績だけが残る。  ",
          "**tier は初期値であって結論ではない。** 実績を積んだ個人ブログは tier S を追い越せるし、",
          "成績の悪い一次情報は下がる。"]
    return "\n".join(L)


def persist(con, scores: list[dict]) -> None:
    ts = now_iso()
    for s in scores:
        con.execute("""INSERT OR REPLACE INTO source_scores
            (computed_at,source_id,n,hit_rate,mean_excess,sd_excess,t_stat,
             shrunk_excess,prior_weight,weight)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ts, s["source_id"], s["n"], s["hit_rate"], s["mean_excess"], s["sd_excess"],
             None if s["t_stat"] != s["t_stat"] else s["t_stat"],
             s["shrunk_excess"], s["prior_weight"], s["weight"]))
    con.commit()
