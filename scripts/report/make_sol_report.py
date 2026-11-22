"""Figures and tables for docs/20261122_231441_results_with_sol_granularity_citations_and_answer_quality.md.

No LLM calls. Run from the repo root with an interpreter that has matplotlib (the .venv has none):
    python3 scripts/report/make_sol_report.py
Inputs: the retrieval evaluation v3 (both embeddings), the nugget scoring tables (primary set, judge Gemini
3.8 Flash), the A1 token-metric analyses and the A2 in-text citation tables, all already including GPT-6.2 Sol.
Outputs: PNG figures in docs/figures/20261122_231441_sol_report/ and CSV tables in
nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/sol_report/. The script also prints every table.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

FIG = Path("docs/figures/20261122_231441_sol_report")
TAB = Path("nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/sol_report")
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

ANALYSIS = Path("nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all")
TABLES = Path("nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all")
EVAL = "runs/retrieval/{emb}/irpf/eval/v3_either_containment_merge_skip"
GEM = "@gemini-emb-2"

# Palette as in make_results_overview_figures.py (S1 orange, S2 blue).
S1C, S2C = "#eb6834", "#2a78d6"
AQUA, VIOLET, GREEN, YELLOW, RED = "#1baf7a", "#6250d6", "#008300", "#eda100", "#e34948"
GRAY, LIGHT, INK, INK2 = "#9b9a94", "#d9d8d3", "#0b0b0b", "#52514e"
SURF = "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.edgecolor": LIGHT, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#ecebe7",
    "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False, "text.color": INK,
})

GENS = [("gpt-6.2-sol", "GPT-6.2 Sol"), ("gpt-5.6-terra", "GPT-5.6 Terra"), ("sabia-4", "Sabiá-4"),
        ("gpt-5.6-luna", "GPT-5.6 Luna"), ("sabiazinho-4", "Sabiazinho-4")]
NAME = dict(GENS)
RNG_SEED, B = 0, 10_000


def save(fig, name):
    fig.savefig(FIG / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / name)


def show(df, name, floatfmt=3):
    df.to_csv(TAB / f"{name}.csv", index=False)
    print(f"\n### {name}\n")
    print(df.to_markdown(index=False, floatfmt=f".{floatfmt}f"))


def paired(d: np.ndarray, rng):
    """Mean, percentile bootstrap CI and sign-flip permutation p of paired differences."""
    d = d[~np.isnan(d)]
    bs = rng.choice(d, (B, len(d))).mean(1)
    flips = rng.choice([-1.0, 1.0], (B, len(d)))
    perm = np.abs((flips * d).mean(1))
    p = (1 + (perm >= abs(d.mean()) - 1e-12).sum()) / (B + 1)
    return d.mean(), *np.percentile(bs, [2.5, 97.5]), p, len(d)


# ------------------------------------------------------------------------------------------------
# Part 1: granularity and token-weighted metrics
# ------------------------------------------------------------------------------------------------
def granularity_classes():
    d = pd.read_csv(f"{EVAL.format(emb='jua-4b-mixed')}/per_item.csv.gz")
    s1 = d[d.strategy == "S1"]
    prov = s1[(s1.level == "provision") & s1.statutory]
    g = prov.groupby("question_number").sub_article.agg(["size", "sum"])
    cls = pd.Series("none", index=sorted(set(s1.question_number)))
    cls[g.index] = np.where(g["sum"] == 0, "whole_only", np.where(g["sum"] == g["size"], "sub_only", "mixed"))
    return cls


def retrieval_tables():
    ns = pd.read_csv(ANALYSIS / "token_metrics/noise_signal.csv")
    x = ns[(ns.cutoff == 4000) & ns.strategy.isin(["S1", "S2", "S3"])]
    rows = []
    for (emb, lvl, st), r in x.groupby(["embedding", "level", "strategy"]):
        r = r.iloc[0]
        rows.append({"embedding": emb, "level": lvl, "strategy": st, "binary recall": r.recall,
                     "token recall": r.token_recall, "item coverage": r.item_coverage,
                     "context precision": r.context_precision, "token precision": r.token_precision,
                     "noise share": r.noise_share, "scaffold share": r.scaffold_share})
    show(pd.DataFrame(rows), "t1_retrieval_4k")
    cg = pd.read_csv(ANALYSIS / "token_metrics/coverage_by_group.csv")
    cg = cg[(cg.budget == 4000) & cg.strategy.isin(["S1", "S2"]) & (cg.group != "none")]
    w = cg.pivot_table(index=["embedding", "group"], columns="strategy", values=["full", "coverage"])
    w.columns = [f"{s} {m}" for m, s in w.columns]
    w = w.reset_index()[["embedding", "group", "S1 full", "S2 full", "S1 coverage", "S2 coverage"]]
    w["S2−S1 full"] = w["S2 full"] - w["S1 full"]
    w["S2−S1 coverage"] = w["S2 coverage"] - w["S1 coverage"]
    show(w, "t2_retrieval_by_granularity_4k")


def answers_by_granularity():
    cls = granularity_classes()
    pq = pd.read_csv(TABLES / "per_question.csv.gz")
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for emb, sfx in (("jua", ""), ("Gemini", GEM)):
        a, b = "S1_budget4000" + sfx, "S2_budget4000" + sfx
        for llm, _ in GENS:
            x = pq[(pq.llm == llm) & pq.context_id.isin([a, b])]
            w = x.pivot_table(index="question_number", columns="context_id", values="V_strict").dropna()
            if a not in w or b not in w:
                continue
            w["diff"] = w[b] - w[a]
            w["cls"] = cls.reindex(w.index).fillna("no gold")
            for grp in ("all", "whole_only", "sub_only", "mixed"):
                y = w if grp == "all" else w[w.cls == grp]
                m, lo, hi, p, n = paired(y["diff"].to_numpy(), rng)
                rows.append({"embedding": emb, "llm": llm, "group": grp, "n": n, "S2−S1": m, "ci_lo": lo,
                             "ci_hi": hi, "p": p})
    df = pd.DataFrame(rows)
    show(df, "t3_answers_s2_minus_s1_by_granularity")

    fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharey=True)
    combos = [(e, g) for g, _ in GENS for e in ("jua", "Gemini")
              if ((df.embedding == e) & (df.llm == g)).any()]
    for ax, grp, title in zip(axes, ("all", "whole_only", "sub_only", "mixed"),
                              ("All questions (714)", "Only whole articles (186)", "Only sub-article units (130)",
                               "Mixed (235)")):
        for i, (e, g) in enumerate(combos):
            r = df[(df.embedding == e) & (df.llm == g) & (df.group == grp)].iloc[0]
            y = len(combos) - 1 - i
            col = VIOLET if g == "gpt-6.2-sol" else (S2C if e == "jua" else AQUA)
            sig = r.ci_lo > 0 or r.ci_hi < 0
            ax.plot([r.ci_lo, r.ci_hi], [y, y], color=col, lw=2, alpha=0.9)
            ax.scatter(r["S2−S1"], y, s=42, color=col if sig else SURF, edgecolor=col, lw=1.8, zorder=3)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_xlim(-0.11, 0.17)
        ax.set_xlabel("V_strict, S2 − S1")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(combos)),
                       [f"{NAME[g]}, {e}" for e, g in reversed(combos)], fontsize=8.5)
    fig.suptitle("Answer gain of S2 over S1, by citation granularity (4k context, 95% bootstrap CI; "
                 "filled = CI excludes 0)", x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    save(fig, "fig1_s2_s1_by_granularity.png")


def token_metric_tracking():
    sl = pd.read_csv(ANALYSIS / "token_metrics/spearman_levels.csv")
    sl = sl[(sl.level == "provision") & sl.context_id.isin(["S1_budget4000", "S2_budget4000"])]
    cols = {"V_strict~recall": "full-hit recall", "V_strict~partial_recall": "any-hit recall",
            "V_strict~token_recall": "token recall", "V_strict~item_coverage": "item coverage",
            "V_strict~context_precision": "context precision", "V_strict~token_precision": "token precision",
            "V_strict~noise_share": "noise share"}
    t = sl.groupby("llm")[list(cols)].mean().rename(columns=cols).reindex([g for g, _ in GENS]).reset_index()
    show(t, "t4_spearman_levels_provision_jua4k")
    sg = pd.read_csv(ANALYSIS / "token_metrics/spearman_gains.csv")
    sg = sg[(sg.embedding == "jua-4b-mixed")]
    cols = {"article:recall": "article recall", "provision:recall": "prov. full hit",
            "provision:partial_recall": "prov. any hit", "provision:token_recall": "token recall",
            "provision:item_coverage": "item coverage", "provision:token_precision": "token precision"}
    t = sg[["llm", "group", "n", *cols]].rename(columns=cols)
    t["llm"] = pd.Categorical(t.llm, [g for g, _ in GENS])
    t["group"] = pd.Categorical(t.group, ["all", "whole_only", "sub_only", "mixed"])
    show(t.sort_values(["group", "llm"]), "t5_spearman_gains_jua4k")


# ------------------------------------------------------------------------------------------------
# Part 2: in-text citations from memory vs the retrieval pipeline
# ------------------------------------------------------------------------------------------------
def citations_vs_retrieval():
    ir = pd.read_csv(ANALYSIS / "intext/intext_citations_runs.csv")
    rows = []
    for emb, sfx in (("jua-4b-mixed", ""), ("gemini-emb-2", GEM)):
        m = pd.read_csv(f"{EVAL.format(emb=emb)}/metrics.csv")
        m = m[(m.view == "budget") & (m.cutoff.astype(str) == "4000") & (m.gold == "all") & (m.slice == "all")]
        for st in ("S1", "S2"):
            for lvl in ("document", "article", "provision"):
                r = m[(m.strategy == st) & (m.level == lvl)].set_index("metric").value
                rows.append({"source": f"retrieval context {st} 4k ({emb.split('-')[0]})", "level": lvl,
                             "recall": r["recall"], "cited@any / hit": r["hit"], "precision": np.nan,
                             "citing": np.nan})
    for cond, lab in (("closed_book", "closed book, in-text"), ("S2_budget4000", "S2 4k jua, in-text"),
                      ("oracle_budget4000", "oracle 4k, in-text")):
        for g, gn in GENS:
            for lvl in ("document", "article", "provision"):
                r = ir[(ir.llm == g) & (ir.context_id == cond) & (ir.level == lvl)]
                if r.empty:
                    continue
                r = r.iloc[0]
                rows.append({"source": f"{gn}: {lab}", "level": lvl, "recall": r.recall_all,
                             "cited@any / hit": r.cited_any_all, "precision": r.precision_citing,
                             "citing": r.citation_rate})
    t = pd.DataFrame(rows)
    show(t, "t6_citations_vs_retrieval")

    # Figure: article level, recall and cited@any.
    art = t[t.level == "article"].set_index("source")
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.6, 1]})
    x = np.arange(len(GENS))
    for j, (lab, col, alpha) in enumerate((("closed book, in-text", GRAY, 1.0),
                                           ("S2 4k jua, in-text", S2C, 1.0))):
        v = [art.loc[f"{gn}: {lab}", "recall"] for _, gn in GENS]
        h = [art.loc[f"{gn}: {lab}", "cited@any / hit"] for _, gn in GENS]
        a.bar(x + (j - 0.5) * 0.38, h, width=0.36, color=col, alpha=0.35)
        a.bar(x + (j - 0.5) * 0.38, v, width=0.36, color=col, alpha=alpha)
        for xi, vi, hi in zip(x, v, h):
            a.text(xi + (j - 0.5) * 0.38, hi + 0.01, f"{hi:.2f}", ha="center", fontsize=7.5, color=INK2)
            a.text(xi + (j - 0.5) * 0.38, vi / 2, f"{vi:.2f}", ha="center", fontsize=7.5,
                   color="white" if j else INK)
    for st, col, ls in (("S1", S1C, "--"), ("S2", S2C, "-")):
        r = art.loc[f"retrieval context {st} 4k (jua)"]
        a.axhline(r["recall"], color=col, ls=ls, lw=1.6)
        a.text(len(GENS) - 0.45, r["recall"], f"{st} context\nrecall {r['recall']:.2f}", fontsize=7.5,
               va="center", color=col)
    a.set_xticks(x, [gn.replace("GPT-", "") for _, gn in GENS], fontsize=9)
    a.set_xlim(-0.6, len(GENS) + 0.2)
    a.set_ylim(0, 0.98)
    a.grid(axis="x", visible=False)
    a.set_ylabel("share of the gold articles (per question)")
    a.set_title("(a) Gold articles cited in the answer text vs held by the context", loc="left")
    a.legend([plt.Rectangle((0, 0), 1, 1, color=GRAY), plt.Rectangle((0, 0), 1, 1, color=S2C),
              plt.Rectangle((0, 0), 1, 1, color=INK2, alpha=0.35)],
             ["closed book (memory)", "RAG, S2 4k", "light bar: answer cites ≥ 1 gold article"],
             loc="upper right", fontsize=8, ncol=1)
    # (b) precision among citing answers vs citation rate
    for _, gn in GENS:
        for lab, col, mk in (("closed book, in-text", GRAY, "o"), ("S2 4k jua, in-text", S2C, "s"),
                             ("oracle 4k, in-text", GREEN, "D")):
            r = art.loc[f"{gn}: {lab}"]
            b.scatter(r.citing, r.precision, color=col, marker=mk, s=46, edgecolor=SURF, zorder=3)
        r0, r1 = art.loc[f"{gn}: closed book, in-text"], art.loc[f"{gn}: S2 4k jua, in-text"]
        b.annotate("", (r1.citing, r1.precision), (r0.citing, r0.precision),
                   arrowprops=dict(arrowstyle="->", color=LIGHT, lw=1.2))
        b.text(r0.citing + 0.012, r0.precision - 0.012, gn.replace("GPT-", "").replace("5.6 ", "")
               .replace("6.2 ", ""), fontsize=7.5, color=INK2, va="top")
    b.set_xlim(0, 1.05)
    b.set_ylim(0, 1)
    b.set_xlabel("answers citing an article")
    b.set_ylabel("precision of cited articles (citing answers)")
    b.set_title("(b) How often and how accurately they cite", loc="left")
    b.legend([Line2D([], [], marker=m, ls="", color=c) for c, m in ((GRAY, "o"), (S2C, "s"), (GREEN, "D"))],
             ["closed book", "S2 4k", "oracle 4k"], loc="lower left", fontsize=8)
    fig.tight_layout()
    save(fig, "fig2_citations_vs_retrieval.png")


def complementarity():
    """Gold article items: held by the S2 4k context (jua), cited by the closed-book answer, both, neither."""
    p = pd.read_csv(f"{EVAL.format(emb='jua-4b-mixed')}/per_item.csv.gz")
    c = pd.read_csv(ANALYSIS / "intext/intext_citations.csv.gz")
    c = c[(c.context_id == "closed_book") & (c.match_article == "full")]
    rows = []
    for st in ("S1", "S2"):
        g = p[(p.strategy == st) & (p.level == "article")][["question_number", "item", "budget_full_4000"]].copy()
        n_q = g.question_number.nunique()
        for llm, gn in GENS:
            x = c[c.llm == llm]
            cited = set(zip(x.question_number, x.document_id + "|" + x.article_id))
            g["mem"] = [k in cited for k in zip(g.question_number, g.item)]
            ret, mem = g.budget_full_4000.astype(bool), g.mem
            q = g.assign(r=ret, m=mem).groupby("question_number")[["r", "m"]].any()
            rows.append({"retrieval": f"{st} 4k jua", "llm": llm, "gold articles": len(g),
                         "both": (ret & mem).mean(), "context only": (ret & ~mem).mean(),
                         "memory only": (~ret & mem).mean(), "neither": (~ret & ~mem).mean(),
                         "union": (ret | mem).mean(),
                         "memory share of context misses": (mem & ~ret).sum() / (~ret).sum(),
                         "questions: context misses all, memory hits": (~q.r & q.m).sum() / n_q,
                         "questions": n_q})
    t = pd.DataFrame(rows)
    show(t, "t7_memory_vs_context_complementarity")

    fig, ax = plt.subplots(figsize=(9.5, 3.4))
    t2 = t[t.retrieval == "S2 4k jua"].set_index("llm")
    parts = [("both", "in the context and cited from memory", VIOLET), ("context only", "only in the context", S2C),
             ("memory only", "only cited from memory", YELLOW), ("neither", "neither", LIGHT)]
    for i, (g, gn) in enumerate(GENS):
        y, left = len(GENS) - 1 - i, 0
        for k, _, col in parts:
            v = t2.loc[g, k]
            ax.barh(y, v, left=left, color=col, height=0.62)
            if v > 0.035:
                ax.text(left + v / 2, y, f"{v:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if col in (VIOLET, S2C) else INK)
            left += v
    ax.set_yticks(range(len(GENS)), [gn for _, gn in reversed(GENS)])
    ax.set_xlim(0, 1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("share of the 1,958 gold articles (553 questions cite an article; pooled over items)")
    ax.set_title("Gold articles: S2 4k context (jua) vs the closed-book answer's citations", loc="left")
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for *_, c in parts], [lab for _, lab, _ in parts],
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, fontsize=8.5)
    save(fig, "fig3_memory_vs_context.png")


def citation_validity():
    ir = pd.read_csv(ANALYSIS / "intext/intext_citations_runs.csv")
    x = ir[(ir.context_id == "closed_book") & (ir.level == "document")].set_index("llm")
    cit = pd.read_csv(ANALYSIS / "intext/intext_citations.csv.gz")
    rev = cit[cit.context_id == "closed_book"].groupby("llm").revoked.sum()
    t = pd.DataFrame([{"llm": g, "citations": int(x.loc[g, "n_citations"]),
                       "act outside corpus": x.loc[g, "not_in_corpus"],
                       "article missing": x.loc[g, "article_missing"], "unit missing": x.loc[g, "unit_missing"],
                       "revoked (citations)": int(rev.get(g, 0)), "act ≥ 2025": int(x.loc[g, "later_n"])}
                      for g, _ in GENS])
    show(t, "t8_closed_book_citation_validity")
    q = pd.read_csv(ANALYSIS / "intext/intext_vs_quality.csv")
    q = q[q.context_id.isin(["closed_book", "S2_budget4000"])]
    q["llm"] = pd.Categorical(q.llm, [g for g, _ in GENS])
    show(q.sort_values(["context_id", "llm"]), "t9_citation_vs_quality")
    ctx = ir[ir.context_id.isin(["S1_budget4000", "S2_budget4000", "oracle_budget4000"])
             & (ir.level == "document")][["llm", "context_id", "article_in_sources",
                                         "article_in_context_not_sources", "article_outside_context"]]
    ctx["llm"] = pd.Categorical(ctx.llm, [g for g, _ in GENS])
    show(ctx.sort_values(["llm", "context_id"]), "t10_rag_citations_vs_context")


# ------------------------------------------------------------------------------------------------
# Part 3: answer quality at a 4k-token context, closed book vs retrieval
# ------------------------------------------------------------------------------------------------
CONDS = [("closed_book", "closed book (no context)", GRAY, "o", True),
         ("S1_budget4000", "S1, jua", S1C, "o", False), ("S2_budget4000", "S2, jua", S2C, "o", False),
         ("S1_budget4000" + GEM, "S1, Gemini", S1C, "s", True), ("S2_budget4000" + GEM, "S2, Gemini", S2C, "s", True),
         ("oracle_budget4000", "oracle (cited articles; 596 q.)", GREEN, "D", True)]


def answer_quality():
    runs = pd.read_csv(TABLES / "runs.csv")
    runs = runs[runs.n >= 590]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 4.0), gridspec_kw={"width_ratios": [1.45, 1]}, sharey=True)
    for gi, (g, _) in enumerate(GENS):
        y = len(GENS) - 1 - gi
        r = runs[runs.llm == g].set_index("context_id")
        for axis, col_name in ((ax, "V_strict"), (bx, "any_contradicts")):
            vs = [r[col_name].get(c) for c, *_ in CONDS if c in r.index]
            axis.plot([min(vs), max(vs)], [y, y], color=LIGHT, lw=2, zorder=1)
            for c, _, col, mk, filled in CONDS:
                if c not in r.index:
                    continue
                axis.scatter(r.loc[c, col_name], y, s=70, marker=mk, color=col if filled else SURF, edgecolor=col,
                             lw=2, zorder=3)
    ax.set_yticks(range(len(GENS)), [gn for _, gn in reversed(GENS)])
    ax.set_xlabel("V_strict: share of the gold answer's vital facts the answer fully states")
    ax.set_title("(a) Answer quality at a 4k-token context (715 questions)", loc="left")
    bx.set_xlabel("share of answers contradicting ≥ 1 gold fact")
    bx.set_title("(b) Contradictions", loc="left")
    ax.set_ylim(-0.5, len(GENS) - 0.5)
    handles = [Line2D([], [], marker=mk, ls="", ms=8, mfc=col if filled else SURF, mec=col, mew=2)
               for _, _, col, mk, filled in CONDS]
    fig.legend(handles, [lab for _, lab, *_ in CONDS], loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=6,
               fontsize=8.5)
    ax.text(0.995, 0.01, "Gemini embedding: Sabiá-4 and Luna only", transform=ax.transAxes, ha="right",
            fontsize=8, color=INK2)
    fig.tight_layout()
    save(fig, "fig4_answers_4k.png")

    t = runs[runs.context_id.isin([c for c, *_ in CONDS]) & runs.llm.isin(NAME)][
        ["llm", "context_id", "n", "V_strict", "V", "any_contradicts", "abstained"]].copy()
    t["llm"] = pd.Categorical(t.llm, [g for g, _ in GENS])
    t["context_id"] = pd.Categorical(t.context_id, [c for c, *_ in CONDS])
    show(t.sort_values(["llm", "context_id"]), "t11_answers_4k")

    # Paired differences against closed book (same questions).
    pq = pd.read_csv(TABLES / "per_question.csv.gz")
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for g, _ in GENS:
        x = pq[pq.llm == g]
        for c, lab, *_ in CONDS[1:]:
            for metric in ("V_strict", "any_contradicts"):
                w = x[x.context_id.isin(["closed_book", c])].pivot_table(
                    index="question_number", columns="context_id", values=metric).dropna()
                if c not in w:
                    continue
                m, lo, hi, p, n = paired((w[c] - w["closed_book"]).to_numpy(), rng)
                rows.append({"llm": g, "context": c, "metric": metric, "n": n, "diff vs closed book": m,
                             "ci_lo": lo, "ci_hi": hi, "p": p})
    show(pd.DataFrame(rows), "t12_answers_vs_closed_book")


if __name__ == "__main__":
    retrieval_tables()
    answers_by_granularity()
    token_metric_tracking()
    citations_vs_retrieval()
    complementarity()
    citation_validity()
    answer_quality()
