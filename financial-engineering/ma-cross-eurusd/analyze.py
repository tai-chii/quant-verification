#!/usr/bin/env python3
"""
bt.py の結果を集計してレポート(report.html)と要約(summary.json)を出力
  python3 analyze.py results/step2_p5-300_SMA-EMA
"""
import sys, os, json, io, base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

for f in ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP", "IPAexGothic", "Yu Gothic"]:
    from matplotlib import font_manager
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f; break
plt.rcParams["axes.unicode_minus"] = False

d = sys.argv[1]
meta = json.load(open(os.path.join(d, "meta.json")))
p = os.path.join(d, "results.parquet")
df = pd.read_parquet(p) if os.path.exists(p) else pd.read_csv(os.path.join(d, "results.csv.gz"))
nulls = dict(np.load(os.path.join(d, "null_max.npz")))
df["family"] = df["ma"] + "_" + df["n_ma"].astype(str) + "本"
df = df[df["trades"] >= 30].copy()            # トレード数が少なすぎる組合せは除外
df["L_over_S"] = df["L"] / df["S"]
df["L_minus_S"] = df["L"] - df["S"]
is3 = df["n_ma"] == 3
df["spacing"] = "—"
df.loc[is3, "spacing"] = "その他"
df.loc[is3 & ((df["M"] - df["S"]) == (df["L"] - df["M"])), "spacing"] = "等差(短中=中長)"
ratio_eq = is3 & (np.abs(np.log((df["M"] / df["S"]) / (df["L"] / df["M"]))) < 0.1)
df.loc[ratio_eq & (df["spacing"] == "その他"), "spacing"] = "等比(倍率ほぼ一定)"

figs = []
def fig_to_b64(fig, title, note=""):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=110, bbox_inches="tight"); plt.close(fig)
    figs.append((title, base64.b64encode(b.getvalue()).decode(), note))

summary = dict(meta={k: v for k, v in meta.items() if k != "periods"},
               n_periods=len(meta["periods"]), period_step=meta["periods"][1] - meta["periods"][0])

# ---------------- 1. 2本 vs 3本（ファミリー別）
fam_rows = []
for fam, g in df.groupby("family"):
    key = fam.replace("本", "").replace("_", "_")
    nk = f"{g['ma'].iloc[0]}_{g['n_ma'].iloc[0]}"
    best = g["sharpe"].max()
    nm = nulls.get(nk)
    rc = float((np.sum(nm >= best) + 1) / (len(nm) + 1)) if nm is not None else np.nan
    fam_rows.append(dict(
        family=fam, combos=len(g),
        median_sharpe=g["sharpe"].median(), best_sharpe=best,
        median_ev_pips=g["ev"].median(), pct_ev_positive=(g["ev"] > 0).mean() * 100,
        pct_p05=(g["p_shift"] < 0.05).mean() * 100,
        reality_check_p=rc,
        median_trades=g["trades"].median(), median_hold_bars=g["hold_bars"].median(),
        is_oos_spearman=g[["sharpe_IS", "sharpe_OOS"]].corr("spearman").iloc[0, 1],
        is_oos_spearman_dm=g[["sharpe_dm_IS", "sharpe_dm_OOS"]].corr("spearman").iloc[0, 1],
        median_sharpe_dm=g["sharpe_dm"].median(),
        median_ev_long=g["ev_long"].median(), median_ev_short=g["ev_short"].median(),
    ))
fam_df = pd.DataFrame(fam_rows).set_index("family")
summary["families"] = fam_df.round(4).reset_index().to_dict("records")

fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for fam, g in df.groupby("family"):
    ax[0].hist(g["sharpe"], bins=80, alpha=.45, density=True, label=fam)
    ax[1].hist(g["ev"].clip(-30, 30), bins=80, alpha=.45, density=True, label=fam)
ax[0].set_title("年率シャープの分布"); ax[1].set_title("1トレード期待値(pips)の分布")
for a in ax: a.axvline(0, c="k", lw=.8); a.legend(fontsize=8)
fig_to_b64(fig, "2本 vs 3本：成績の分布")

fig, axs = plt.subplots(1, len(fam_df), figsize=(4 * len(fam_df), 3.2), squeeze=False)
for a, fam in zip(axs[0], fam_df.index):
    g = df[df.family == fam]; nk = f"{g['ma'].iloc[0]}_{g['n_ma'].iloc[0]}"
    a.hist(nulls[nk], bins=40, color="#999"); a.axvline(g["sharpe"].max(), c="r")
    a.set_title(f"{fam}\n最良 {g['sharpe'].max():.2f} / p={fam_df.loc[fam,'reality_check_p']:.3f}", fontsize=9)
fig_to_b64(fig, "ランダム化検定：全組合せ中の最良シャープ vs 偶然の最良（灰）",
           "収益系列を循環シフトして売買タイミングと相場をずらしたときの『最良の組合せのシャープ』の分布。赤線が実際の最良。p値が小さいほど、最良組合せは偶然では説明しにくい。")

# ---------------- 2. 2本MAのヒートマップ
for kind in df["ma"].unique():
    g = df[(df.ma == kind) & (df.n_ma == 2)]
    if g.empty: continue
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    for a, col, title, cmap in [(ax[0], "ev", "期待値 pips/トレード", "RdBu"),
                                (ax[1], "sharpe", "年率シャープ", "RdBu"),
                                (ax[2], "p_shift", "ランダム化 p値", "viridis_r")]:
        pv = g.pivot_table(index="S", columns="L", values=col)
        v = np.nanmax(np.abs(pv.values)) if col != "p_shift" else None
        im = a.imshow(pv.values, origin="lower", aspect="auto", cmap=cmap,
                      vmin=(-v if v else 0), vmax=(v if v else 1),
                      extent=[pv.columns.min(), pv.columns.max(), pv.index.min(), pv.index.max()])
        a.set_xlabel("長期MA"); a.set_ylabel("短期MA"); a.set_title(f"{kind} 2本：{title}")
        plt.colorbar(im, ax=a)
    fig_to_b64(fig, f"{kind} 2本MA：期間の組合せマップ")

# ---------------- 3. 3本MA：短期×長期（中期で平均）と間隔の型
for kind in df["ma"].unique():
    g = df[(df.ma == kind) & (df.n_ma == 3)]
    if g.empty: continue
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    pv = g.pivot_table(index="S", columns="L", values="sharpe", aggfunc="mean")
    v = np.nanmax(np.abs(pv.values))
    im = ax[0].imshow(pv.values, origin="lower", aspect="auto", cmap="RdBu", vmin=-v, vmax=v,
                      extent=[pv.columns.min(), pv.columns.max(), pv.index.min(), pv.index.max()])
    ax[0].set_xlabel("長期MA"); ax[0].set_ylabel("短期MA"); ax[0].set_title(f"{kind} 3本：シャープ（中期で平均）")
    plt.colorbar(im, ax=ax[0])
    sp = g.groupby("spacing")[["sharpe", "ev"]].median()
    ax[1].bar(sp.index, sp["sharpe"]); ax[1].set_title("間隔の型別 シャープ中央値"); ax[1].axhline(0, c="k", lw=.8)
    fig_to_b64(fig, f"{kind} 3本MA：期間と間隔の型")

# ---------------- 4. パラメータと成績の相関
feat = ["S", "L", "L_over_S", "L_minus_S", "trades", "hold_bars", "exposure"]
corr_rows = []
for fam, g in df.groupby("family"):
    fs = feat + (["M"] if g["n_ma"].iloc[0] == 3 else [])
    c = g[fs + ["ev", "sharpe"]].corr("spearman")
    for f_ in fs:
        corr_rows.append(dict(family=fam, feature=f_, rho_ev=c.loc[f_, "ev"], rho_sharpe=c.loc[f_, "sharpe"]))
corr_df = pd.DataFrame(corr_rows)
summary["param_correlation"] = corr_df.round(3).to_dict("records")
spacing = df[is3].groupby(["family", "spacing"])[["sharpe", "ev"]].agg(["median", "count"]).round(3)
summary["spacing"] = {f"{a}|{b}": v for (a, b), v in spacing["sharpe"]["median"].items()}

# ---------------- 5. ロング vs ショート
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
smp = df.sample(min(len(df), 30000), random_state=0)
for fam, g in smp.groupby("family"):
    ax[0].scatter(g["ev_long"], g["ev_short"], s=2, alpha=.3, label=fam)
ax[0].axhline(0, c="k", lw=.8); ax[0].axvline(0, c="k", lw=.8)
ax[0].set_xlabel("ロングの期待値 pips"); ax[0].set_ylabel("ショートの期待値 pips"); ax[0].legend(markerscale=5, fontsize=8)
ax[0].set_title("ロング/ショート別 期待値")
fam_df[["median_ev_long", "median_ev_short"]].plot.bar(ax=ax[1]); ax[1].axhline(0, c="k", lw=.8)
ax[1].set_title("ロング/ショート 期待値中央値")
fig_to_b64(fig, "ロングとショートの非対称性", f"期間中の単純保有: {meta['bh_pips']:.0f} pips（ユーロドルが下がった期間ならショートが有利になりやすい点に注意）")

# ---------------- 6. 前半/後半の再現性
fig, axs = plt.subplots(1, len(fam_df), figsize=(4 * len(fam_df), 3.6), squeeze=False)
rep_rows = []
for a, fam in zip(axs[0], fam_df.index):
    g = df[df.family == fam]; gs = g.sample(min(len(g), 15000), random_state=0)
    a.scatter(gs["sharpe_IS"], gs["sharpe_OOS"], s=2, alpha=.3)
    a.axhline(0, c="k", lw=.6); a.axvline(0, c="k", lw=.6)
    rho = fam_df.loc[fam, "is_oos_spearman"]
    a.set_title(f"{fam}  順位相関 ρ={rho:.2f}", fontsize=9); a.set_xlabel("前半シャープ"); a.set_ylabel("後半シャープ")
    top = g["sharpe_IS"] >= g["sharpe_IS"].quantile(.9)
    rep_rows.append(dict(family=fam, oos_sharpe_top10pct_IS=g.loc[top, "sharpe_OOS"].median(),
                         oos_sharpe_rest=g.loc[~top, "sharpe_OOS"].median(),
                         pct_same_sign=(np.sign(g["sharpe_IS"]) == np.sign(g["sharpe_OOS"])).mean() * 100,
                         rho_dm=g[["sharpe_dm_IS", "sharpe_dm_OOS"]].corr("spearman").iloc[0, 1],
                         oos_dm_top10pct_IS=g.loc[g["sharpe_dm_IS"] >= g["sharpe_dm_IS"].quantile(.9), "sharpe_dm_OOS"].median()))
fig_to_b64(fig, f"前半/後半の再現性（境目 {meta['split_date'][:10]}）",
           "前半で良かった組合せが後半でも良ければ点が右上がりに並ぶ。ρ≈0なら前半の成績は後半の予測に役立たない。")
rep_df = pd.DataFrame(rep_rows).set_index("family")
summary["reproducibility"] = rep_df.round(4).reset_index().to_dict("records")

# ---------------- 6.5 walk-forward（期間をN分割し、どの区間でも崩れていないか）
wf_cols = sorted([c for c in df.columns if c.startswith("sharpe_wf")])
has_wf = len(wf_cols) >= 2
if has_wf:
    wf = df[wf_cols].values
    df["wf_min"] = wf.min(axis=1)
    df["wf_all_positive"] = (wf > 0).all(axis=1)

    wf_rows = []
    for fam, g in df.groupby("family"):
        # 隣り合う区間どうしの順位相関の平均（時期によらず「良い設定は良いまま」かを見る）
        # ※ pandas の DataFrame.corr を使う（Series.corr(method="spearman") は scipy 依存だが、
        #    こちらは依存せずランクで計算できるため、他の箇所と同じ経路に揃える）
        cm = g[wf_cols].corr(method="spearman").values
        rhos = [cm[i, i + 1] for i in range(len(wf_cols) - 1)]
        wf_rows.append(dict(
            family=fam,
            wf_pct_all_positive=g["wf_all_positive"].mean() * 100,
            wf_min_sharpe_median=g["wf_min"].median(),
            wf_min_sharpe_best=g["wf_min"].max(),
            wf_adjacent_fold_spearman=float(np.nanmean(rhos)),
        ))
    wf_df = pd.DataFrame(wf_rows).set_index("family")
    summary["walk_forward"] = dict(
        n_folds=len(wf_cols),
        by_family=wf_df.round(4).reset_index().to_dict("records"),
    )

    fig, axs = plt.subplots(1, len(fam_df), figsize=(4 * len(fam_df), 3.6), squeeze=False)
    for a, fam in zip(axs[0], fam_df.index):
        g = df[df.family == fam]
        a.boxplot([g[c] for c in wf_cols], showfliers=False)
        a.set_xticks(range(1, len(wf_cols) + 1))
        a.set_xticklabels([str(i + 1) for i in range(len(wf_cols))])
        a.axhline(0, c="k", lw=.8)
        a.set_title(f"{fam}\n全区間プラス {wf_df.loc[fam,'wf_pct_all_positive']:.1f}%", fontsize=9)
        a.set_xlabel("区間（古い→新しい）"); a.set_ylabel("シャープ")
    fig_to_b64(fig, f"walk-forward：期間を{len(wf_cols)}分割した区間別シャープ",
               "各箱はその区間だけのシャープの分布。IS/OOSの2分割より厳しく、"
               "特定の区間だけで勝っている組合せ（外れ値頼み）を見分けられる。"
               "wf_pct_all_positiveは全区間でプラスだった組合せの割合。")

    # 全区間プラス（IS/OOSが両方プラスより厳しい条件）の上位
    wf_robust = df[df["wf_all_positive"]].sort_values("wf_min", ascending=False).head(30)
    wf_robust_cols = ["family", "S", "M", "L", "trades", "ev", "sharpe"] + wf_cols + ["wf_min"]
    summary["wf_robust30"] = wf_robust[wf_robust_cols].round(3).to_dict("records")
else:
    wf_df = None
    summary["walk_forward"] = None

# ---------------- 7. 上位組合せ
cols = ["family", "S", "M", "L", "trades", "ev", "winrate", "pf", "sharpe", "maxdd", "ev_long", "ev_short",
        "sharpe_IS", "sharpe_OOS", "p_shift"]
top = df.sort_values("sharpe", ascending=False).head(30)[cols]
summary["top30"] = top.round(3).to_dict("records")
robust = df[(df.sharpe_IS > 0) & (df.sharpe_OOS > 0)].copy()
robust["min_half"] = robust[["sharpe_IS", "sharpe_OOS"]].min(axis=1)
rob = robust.sort_values("min_half", ascending=False).head(30)[cols]
summary["robust30"] = rob.round(3).to_dict("records")

json.dump(summary, open(os.path.join(d, "summary.json"), "w"), ensure_ascii=False, indent=1, default=float)

# ---------------- HTML
def tbl(x, fmt="{:.3f}"):
    return x.to_html(float_format=lambda v: fmt.format(v), border=0, classes="t")
html = [f"""<!doctype html><html lang="ja"><meta charset="utf-8"><title>MAクロス検証 EURUSD H4</title>
<style>body{{font-family:-apple-system,'Hiragino Sans',sans-serif;max-width:1150px;margin:24px auto;padding:0 16px;color:#222}}
h1{{font-size:22px}}h2{{font-size:17px;border-bottom:1px solid #ddd;padding-bottom:4px;margin-top:36px}}
.t{{border-collapse:collapse;font-size:12px}}.t td,.t th{{padding:3px 8px;border-bottom:1px solid #eee;text-align:right}}
img{{max-width:100%}}.note{{color:#666;font-size:13px}}</style>
<h1>MAクロス 全パターン検証 — EURUSD 4時間足</h1>
<p class="note">期間 {meta['start'][:10]} 〜 {meta['end'][:10]}（{meta['bars']:,}本）／MA期間 {meta['periods'][0]}〜{meta['periods'][-1]}、{summary['period_step']}刻み／
{', '.join(meta['kinds'])}／往復コスト {meta['cost_pips']} pips／ランダム化 {meta['n_shifts']} 回／トレード30回未満の組合せは除外</p>
<h2>2本 vs 3本（まとめ）</h2>{tbl(fam_df)}
<p class="note">reality_check_p：全組合せ中の最良シャープが「偶然の最良」を上回る確率の裏返し（小さいほど本物の可能性）。pct_p05：個別p値&lt;0.05の割合（偶然なら約5%）。</p>
<h2>前半/後半の再現性</h2>{tbl(rep_df)}
<p class="note">rho_dm / *_dm：各期間の平均騰落（トレンドの偏り）を差し引いた「タイミングだけ」の成績。ユーロドルが一方向に動いた期間では、売り（買い）に偏った組合せが前半・後半とも勝ってしまうため、こちらで再現性を見るのが本命。</p>
{"<h2>walk-forward（" + str(len(wf_cols)) + "分割）</h2>" + tbl(wf_df) + "<p class='note'>IS/OOSの2分割より厳しい再現性チェック。wf_min_sharpe_median：組合せごとの「一番悪かった区間」のシャープの中央値（高いほど、どの時期でも崩れていない）。wf_adjacent_fold_spearman：隣り合う区間どうしの順位相関（高いほど「良い設定」が時期を超えて安定）。</p>" if has_wf else ""}
<h2>パラメータと成績の順位相関（Spearman）</h2>{tbl(corr_df.pivot(index='feature', columns='family', values='rho_sharpe'))}
<p class="note">値はシャープとの順位相関。期待値との相関は summary.json の param_correlation を参照。</p>
<h2>3本MA：間隔の型別</h2>{tbl(spacing)}
"""]
for t, b, n in figs:
    html.append(f"<h2>{t}</h2><img src='data:image/png;base64,{b}'>" + (f"<p class='note'>{n}</p>" if n else ""))
html.append(f"<h2>シャープ上位30</h2>{tbl(top.set_index('family'))}")
html.append(f"<h2>前半・後半ともにプラスで、悪い方の半分が最も良い30組（頑健さ順）</h2>{tbl(rob.set_index('family'))}")
if has_wf:
    html.append(f"<h2>walk-forward: 全区間プラスで、最悪区間が最も良い30組（最も厳しい頑健さ順）</h2>"
                f"{tbl(wf_robust.set_index('family'))}")
open(os.path.join(d, "report.html"), "w").write("\n".join(html))
print("出力:", os.path.join(d, "report.html"), "/ summary.json")
