"""Figures for docs/20261108_224913_results_overview_segmentation_and_embedding.md (no LLM calls).

Run from the repo root:  .venv/bin/python scripts/report/make_results_overview_figures.py
Inputs: the retrieval evaluations, the nugget scoring tables, the frozen nugget set and the chunk table.
Numbers that exist only in the notes (perturbation shares, the cause audit of 57 questions) are copied
from docs/20261023_210727_rag_phase5_scoring_and_analysis.md §7.2 and §10.3.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path("docs/figures/20261108_224913_results_overview")
OUT.mkdir(parents=True, exist_ok=True)

# Palette (dataviz reference instance, light mode): S1 orange, S2 blue, as in the slide deck.
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

TABLES = Path("nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all")
GEM = "@gemini-emb-2"
GENS = [("gpt-5.6-terra", "GPT-5.6 Terra"), ("sabia-4", "Sabiá-4"), ("gpt-5.6-luna", "GPT-5.6 Luna"),
        ("sabiazinho-4", "Sabiazinho-4")]


def save(fig, name):
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


# ------------------------------------------------------------------------------------------------
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.set_axis_off(); ax.set_xlim(0, 11); ax.set_ylim(0, 2.6)
    boxes = [
        (0.1, "Legal corpus", "453 laws, decrees, INs,\nrulings → LexML XML"),
        (2.3, "Segmentation", "S1 articles  vs\nS2 + paragraphs/incisos"),
        (4.5, "Embedding +\nretrieval", "jua-4b-mixed  vs\ngemini-embedding-2"),
        (6.7, "Context (4k tokens)\n+ generator LLM", "4 generators answer\n715 IRPF questions"),
        (8.9, "Nugget scoring", "LLM judge checks each\nkey fact of the gold answer"),
    ]
    for x, title, sub in boxes:
        ax.add_patch(FancyBboxPatch((x, 0.35), 1.95, 1.9, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="#f1f0ec", ec=LIGHT, lw=1))
        ax.text(x + 0.975, 1.78, title, ha="center", va="center", fontsize=10, fontweight="bold")
        ax.text(x + 0.975, 0.85, sub, ha="center", va="center", fontsize=8.5, color=INK2)
    for x in (2.07, 4.27, 6.47, 8.67):
        ax.annotate("", xy=(x + 0.21, 1.3), xytext=(x, 1.3),
                    arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2))
    ax.text(3.3, 0.08, "compared here", ha="center", fontsize=8.5, color=S2C, fontweight="bold")
    ax.text(5.5, 0.08, "compared here", ha="center", fontsize=8.5, color=S2C, fontweight="bold")
    ax.text(5.5, 2.48, "Retrieval stage: are the cited legal provisions found?", ha="center", fontsize=9,
            color=INK2, style="italic")
    ax.text(9.9, 2.48, "Answer stage: is the answer right?", ha="center", fontsize=9, color=INK2,
            style="italic")
    save(fig, "fig1_pipeline.png")


# ------------------------------------------------------------------------------------------------
def fig_segmentation_example():
    d = pd.read_csv("segmented/chunks_all.csv.gz", usecols=["Tipo", "Rotulo", "arquivo", "n_tokens",
                                                             "variante", "artigo_id"])
    x = d[d.arquivo.str.startswith("lei_9250_19951226") & (d.artigo_id == "art35") & (d.variante == "base")]
    art = int(x[x.Tipo == "ART"].n_tokens.iloc[0])
    subs = x[x.Tipo != "ART"].copy()
    order = {"CPT": 0, "INC": 1, "PAR": 2}
    subs["o"] = subs.Tipo.map(order)
    subs = subs.sort_values(["o"], kind="stable")
    labels = [r.split("Art. 35., ")[-1].replace("caput, Inciso ", "inciso ") for r in subs.Rotulo]
    fig, ax = plt.subplots(figsize=(10.5, 3.3))
    ax.barh([1.6], [art], color=S1C, height=0.55)
    ax.text(art + 15, 1.6, f"S1: the whole article = 1 chunk, {art} tokens", va="center", fontsize=9)
    left = 0
    for (lab, tok, t) in zip(labels, subs.n_tokens, subs.Tipo):
        ax.barh([0.6], [tok - 4], left=left, color=S2C if t != "CPT" else "#7aa9e6", height=0.55)
        if tok > 80:
            ax.text(left + tok / 2, 0.6, lab.replace("inciso ", "").replace("§ ", "§"), ha="center",
                    va="center", fontsize=7, color="white")
        left += tok
    ax.text(left + 15, 0.6, f"S2 adds {len(subs)} smaller chunks\n(caput, 7 incisos, 5 §§; median "
            f"{int(subs.n_tokens.median())} tokens)", va="center", fontsize=9)
    ax.set_yticks([1.6, 0.6], ["S1", "S2\n(also keeps\nthe article)"])
    ax.set_xlabel("tokens (each chunk also carries the law's title and ementa as a prefix)")
    ax.set_xlim(0, 3400); ax.set_ylim(0.1, 2.1); ax.grid(axis="y", visible=False)
    ax.set_title("Example: Lei 9.250/1995, art. 35 (who counts as a dependant)", loc="left")
    save(fig, "fig2_segmentation_example.png")


def fig_chunk_lengths():
    d = pd.read_csv("segmented/chunks_all.csv.gz", usecols=["Tipo", "n_tokens", "variante", "arquivo"])
    d = d[(d.variante == "base") & ~d.arquivo.str.startswith("decreto_3000_19990326")]
    s1 = d[d.Tipo.isin(["ART", "DSP", "TXT", "TAB"])].n_tokens.clip(upper=1600)
    s2 = d[d.Tipo.isin(["CPT", "PAR", "INC", "ALI", "ITE"])].n_tokens.clip(upper=1600)
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    bins = np.arange(0, 1625, 25)
    ax.hist(s2, bins=bins, color=S2C, alpha=0.85, label=f"S2 sub-article units ({len(s2):,})")
    ax.hist(s1, bins=bins, histtype="step", color=S1C, lw=2, label=f"S1 basic units ({len(s1):,})")
    ax.axvline(1024, color=INK2, lw=1.2, ls="--")
    ax.text(1034, ax.get_ylim()[1] * 0.9, "cap: 1,024 tokens\nlonger articles are split\n"
            "(3.8 % of articles)", fontsize=8.5, color=INK2, va="top")
    ax.set_xlabel("chunk length, tokens (values above 1,600 drawn at 1,600)")
    ax.set_ylabel("chunks")
    ax.legend(loc="upper right", bbox_to_anchor=(1, 0.62))
    ax.set_title("Chunk lengths: S2's added units are short; S1 units fill up to the cap", loc="left")
    print("median S1", s1.median(), "S2 sub", s2.median())
    save(fig, "fig3_chunk_lengths.png")


# ------------------------------------------------------------------------------------------------
def retrieval_metrics(emb):
    m = pd.read_csv(f"runs/retrieval/{emb}/irpf/eval/either_containment_merge_skip/metrics.csv")
    return m[(m.level == "article") & (m.gold == "all") & (m.slice == "all")]


def fig_retrieval():
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1.5, 1]})
    cuts = [1000, 2000, 4000, 8000, 16000]
    for emb, name, ls, mk in [("jua-4b-mixed", "jua", "--", "o"), ("gemini-emb-2", "Gemini", "-", "s")]:
        m = retrieval_metrics(emb)
        for s, c in (("S1", S1C), ("S2", S2C)):
            r = m[(m.strategy == s) & (m.view == "budget") & (m.metric == "recall")].copy()
            r["cutoff"] = r.cutoff.astype(int)
            r = r.set_index("cutoff").loc[cuts]
            a.plot(range(5), r.value, ls=ls, marker=mk, color=c, lw=2, ms=6, mec=SURF, mew=1.5)
            dy = {("S2", "jua"): 0.012, ("S2", "Gemini"): -0.012}.get((s, name), 0)
            a.text(4.12, r.value.iloc[-1] + dy, f"{s} {name}", va="center", fontsize=8.5, color=INK)
    a.set_xticks(range(5), ["1k", "2k", "4k", "8k", "16k"]); a.set_xlim(-0.2, 4.9)
    a.axvline(2, color=LIGHT, lw=6, zorder=0)
    a.text(2, 0.21, "budget used\nfor answers", ha="center", fontsize=8, color=INK2)
    a.set_xlabel("context budget (tokens given to the generator)")
    a.set_ylabel("share of cited articles in the context")
    a.set_title("(a) What fits in the context: S2 ≫ S1; Gemini ≈ jua", loc="left")
    a.legend([Line2D([], [], color=INK2, ls="--", marker="o"), Line2D([], [], color=INK2, ls="-", marker="s")],
             ["jua-4b-mixed", "gemini-embedding-2"], loc="upper left")
    # (b) MRR, unit view
    vals = {}
    for emb in ("jua-4b-mixed", "gemini-emb-2"):
        m = retrieval_metrics(emb)
        for s in ("S1", "S2"):
            vals[(emb, s)] = m[(m.strategy == s) & (m.view == "unit") & (m.metric == "mrr")].value.iloc[0]
    x = np.arange(2)
    for i, (emb, lab, alpha) in enumerate([("jua-4b-mixed", "jua", 0.45), ("gemini-emb-2", "Gemini", 1.0)]):
        for j, (s, c) in enumerate((("S1", S1C), ("S2", S2C))):
            v = vals[(emb, s)]
            b.bar(j + (i - 0.5) * 0.38, v, width=0.36, color=c, alpha=alpha)
            b.text(j + (i - 0.5) * 0.38, v + 0.01, f"{v:.2f}\n{lab}", ha="center", fontsize=8)
    b.set_xticks(x, ["S1", "S2"]); b.set_ylim(0, 0.78); b.grid(axis="x", visible=False)
    b.set_ylabel("MRR of the first cited article")
    b.set_title("(b) Ranking quality: Gemini ≫ jua", loc="left")
    save(fig, "fig4_retrieval.png")


# ------------------------------------------------------------------------------------------------
def fig_answers():
    runs = pd.read_csv(TABLES / "runs.csv")
    runs = runs[runs.n >= 700]
    conds = [("closed_book", "closed book (no context)", GRAY, "o"),
             ("S1_budget4000", "S1, jua", S1C, "o"), ("S2_budget4000", "S2, jua", S2C, "o"),
             ("S1_budget4000" + GEM, "S1, Gemini", S1C, "s"), ("S2_budget4000" + GEM, "S2, Gemini", S2C, "s")]
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    for gi, (g, gname) in enumerate(GENS):
        y = len(GENS) - 1 - gi
        r = runs[runs.llm == g].set_index("context_id")
        pts = [(c, r.V_strict.get(c)) for c, *_ in conds]
        vs = [v for _, v in pts if v is not None and not np.isnan(v)]
        ax.plot([min(vs), max(vs)], [y, y], color=LIGHT, lw=2, zorder=1)
        for (c, lab, col, mk) in conds:
            v = r.V_strict.get(c)
            if v is None or np.isnan(v):
                continue
            filled = c.endswith(GEM) or c == "closed_book"
            ax.scatter(v, y, s=70, marker=mk, color=col if filled else SURF, edgecolor=col, lw=2, zorder=3)
    ax.set_yticks(range(len(GENS)), [g for _, g in reversed(GENS)])
    handles = [Line2D([], [], marker=mk, ls="", ms=8, mfc=(col if (c.endswith(GEM) or c == "closed_book")
                                                           else SURF), mec=col, mew=2)
               for c, _, col, mk in conds]
    ax.legend(handles, [lab for _, lab, *_ in conds], loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=5,
              fontsize=8.5)
    ax.set_xlabel("V_strict: share of the gold answer's vital facts the answer fully states")
    ax.set_xlim(0.16, 0.37); ax.set_ylim(-0.5, 3.5)
    ax.set_title("Answer quality at a 4k-token context (715 questions)", loc="left")
    ax.text(0.37, -0.42, "Gemini was run for Sabiá-4 and Luna only", ha="right", fontsize=8, color=INK2)
    save(fig, "fig5_answers.png")


def fig_forest():
    comp = pd.read_csv(TABLES / "comparisons.csv")
    comp = comp[comp.metric == "V_strict"]
    rows = []
    for g, gname in GENS:
        rows.append(("S2 vs S1 (jua)", gname, g, "S1_budget4000", "S2_budget4000", S2C))
    for g, gname in GENS[1:3]:
        rows.append(("S2 vs S1 (Gemini)", gname, g, "S1_budget4000" + GEM, "S2_budget4000" + GEM, S2C))
    for g, gname in GENS[1:3]:
        for s in ("S1", "S2"):
            rows.append(("Gemini vs jua (same strategy)", f"{gname}, {s}", g, f"{s}_budget4000",
                         f"{s}_budget4000" + GEM, AQUA))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ys, labs = [], []
    y = 0
    prev = None
    for grp, gname, g, a, b, col in rows:
        if grp != prev:
            if prev is not None:
                y -= 0.6
            ax.text(-0.042, y + 0.05, grp, fontsize=9.5, fontweight="bold", va="bottom")
            y -= 0.55
            prev = grp
        r = comp[(comp.llm == g) & (comp.a == a) & (comp.b == b)].iloc[0]
        sig = r.p_perm < 0.05 and r.cluster_ci_lo > 0
        ax.plot([r.ci_lo, r.ci_hi], [y, y], color=col, lw=2.2, alpha=1 if sig else 0.5)
        ax.scatter(r["diff"], y, s=60, color=col if sig else SURF, edgecolor=col, lw=2, zorder=3)
        ax.text(0.071, y, f"{r['diff']:+.3f}   p = {r.p_perm:.3f}".replace("p = 0.000", "p < .001")
                .replace("= 0.", "= ."), va="center", fontsize=8.5, color=INK if sig else INK2)
        ys.append(y); labs.append(gname)
        y -= 1
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(ys, labs)
    ax.set_xlim(-0.045, 0.07); ax.set_ylim(y + 0.3, 0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("paired difference in V_strict, with 95 % bootstrap CI (filled = significant)")
    ax.set_title("Effect sizes: segmentation and embedding (714 paired questions)", loc="left")
    ax.text(0.071, 0.25, "diff        p (perm.)", fontsize=8.5, color=INK2)
    save(fig, "fig6_effects.png")


def fig_context_vs_answer():
    """Context support (judge on the context) for jua / Gemini, S1 / S2, and the oracle."""
    cs = pd.read_csv(TABLES / "ctxsupport_runs.csv").set_index("context_id")
    items = [("S1_budget4000", "S1, jua", S1C, 0.45), ("S2_budget4000", "S2, jua", S2C, 0.45),
             ("S1_budget4000" + GEM, "S1, Gemini", S1C, 1), ("S2_budget4000" + GEM, "S2, Gemini", S2C, 1),
             ("oracle_budget4000", "oracle: cited\narticles only*", GRAY, 1)]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for i, (cid, lab, col, al) in enumerate(items):
        v = cs.loc[cid, "V_strict"]
        ax.bar(i, v, color=col, alpha=al, width=0.62)
        ax.text(i, v + 0.008, f"{v:.3f}", ha="center", fontsize=9)
    ax.set_xticks(range(len(items)), [lab for _, lab, *_ in items], fontsize=9)
    ax.set_ylim(0, 0.56); ax.grid(axis="x", visible=False)
    ax.set_ylabel("vital facts fully stated\nby the context")
    ax.set_title("What the 4k context holds of the gold answer (judge applied to the context)", loc="left")
    ax.text(4.35, 0.535, "*596 questions with cited legislation", ha="right", fontsize=7.5, color=INK2)
    save(fig, "fig7_context_support.png")


# ------------------------------------------------------------------------------------------------
def fig_perturbation():
    dmg = [0, 10, 15, 20, 30, 40, 50]
    luna = [1.00, 0.95, 0.89, 0.78, 0.60, 0.48, 0.32]
    sabia = [1.00, 0.97, 0.93, 0.86, 0.79, 0.68, 0.60]
    fig, ax = plt.subplots(figsize=(7.5, 3.3))
    ax.axvspan(15, 20, color="#ecebe7", zorder=0)
    ax.text(17.5, 0.12, "robustness bar\nset in the plan", ha="center", fontsize=8, color=INK2)
    for ys, lab, col, mk in ((sabia, "Sabiá-4", VIOLET, "s"), (luna, "GPT-5.6 Luna", AQUA, "o")):
        ax.plot(dmg, ys, color=col, lw=2, marker=mk, ms=6, mec=SURF, mew=1.5)
        ax.text(51, ys[-1], lab, va="center", fontsize=9)
    ax.axhline(0.5, color=INK2, lw=0.8, ls=":")
    ax.set_xlim(-1, 60); ax.set_ylim(0, 1.05)
    ax.set_xlabel("share of gold nuggets deleted at random (%)")
    ax.set_ylabel("replicates where S2 > S1\nstays significant")
    ax.set_title("S2 > S1 survives damage to the nugget set (1,000 replicates)", loc="left")
    save(fig, "fig8_perturbation.png")


def fig_nuggets():
    N = [json.loads(line) for line in open("nuggets/gold/v0-auto/nuggets.jsonl")]
    cat = Counter((n["category"], n["importance"]) for n in N)
    names = {"regra": "rule", "condicao": "condition", "resposta_direta": "direct answer (Sim/Não…)",
             "procedimento_pgd": "filing-program step", "valor_prazo": "value / deadline",
             "definicao": "definition"}
    order = sorted(names, key=lambda k: -(cat[(k, "vital")] + cat[(k, "okay")]))
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 3.6), gridspec_kw={"width_ratios": [1, 1], "wspace": 0.85})
    y = np.arange(len(order))[::-1]
    v = [cat[(k, "vital")] for k in order]; o = [cat[(k, "okay")] for k in order]
    a.barh(y, v, color=S2C, height=0.6, label="vital")
    a.barh(y, o, left=np.array(v) + 15, color="#a9c7ee", height=0.6, label="okay")
    a.set_yticks(y, [names[k] for k in order]); a.grid(axis="y", visible=False)
    a.legend(loc="center right"); a.set_xlabel("nuggets")
    a.set_title(f"(a) {len(N):,} gold nuggets, {sum(v):,} vital", loc="left")
    # (b) where the vital facts are, audit of 57 questions (phase 5 note §10.3)
    parts = [("fully stated by the cited provisions", 50.5, S2C),
             ("partly stated by them", 20.8, "#a9c7ee"),
             ("cited, but cut from our oracle context", 5.7, GRAY),
             ("stated in other, uncited legislation", 7.1, YELLOW),
             ("the tax authority's interpretation", 9.4, RED),
             ("filing-program instructions", 3.8, RED),
             ("administrative position, no legal text", 2.4, RED)]
    yy = np.arange(len(parts))[::-1]
    for y_, (lab, val, col) in zip(yy, parts):
        b.barh(y_, val, color=col, height=0.62)
        b.text(val + 1, y_, f"{val:.1f} %", va="center", fontsize=8.5)
    b.set_yticks(yy, [p[0] for p in parts], fontsize=8.5); b.grid(axis="y", visible=False)
    b.set_xlim(0, 60)
    b.axhspan(-0.45, 2.45, color="#fbe3e2", zorder=0)
    b.text(59, 1, "not in any legal\ntext of the corpus:\n15.6 %", ha="right", va="center", fontsize=8.5,
           color=INK)
    b.set_xlabel("share of vital nuggets (%), 57 audited questions")
    b.set_title("(b) Are the gold facts in the cited law?", loc="left")
    save(fig, "fig9_nuggets.png")


if __name__ == "__main__":
    fig_pipeline(); fig_segmentation_example(); fig_chunk_lengths(); fig_retrieval(); fig_answers()
    fig_forest(); fig_context_vs_answer(); fig_perturbation(); fig_nuggets()
