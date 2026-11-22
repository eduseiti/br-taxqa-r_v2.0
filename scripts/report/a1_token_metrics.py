#!/usr/bin/env python3
"""A1 analyses (plan ``docs/20261122_164407_*`` §3.5): token-weighted retrieval metrics against answer quality.

No API calls. Inputs: the ``v3_either_containment_merge_skip`` evaluations (``rag.py evaluate --token-metrics``)
of jua-4b-mixed and gemini-emb-2, and the phase 5 nugget scores (answers and context support, judge
gemini-3.8-flash, primary set ``gold-v0-auto``, all questions).

1. ``noise_signal.csv``: token precision, noise and scaffold shares, token recall vs the binary metrics, per
   embedding × strategy × budget × level (``metrics.csv``, gold = all, slice = all).
2. ``spearman_levels.csv``: per answer run (generator × context set), the Spearman correlation over questions
   between a per-question retrieval metric of that context and (a) the answer's V_strict, (b) the context's
   own nugget support (ctx V_strict), (c) the answer's utilisation (share of the context-supported nuggets
   the answer supports). Plus the partial correlation of token precision given token recall.
   ``spearman_gains.csv``: the granularity note §4 design: per question, S2 − S1 retrieval gain against the
   S2 − S1 V_strict gain, per generator and question group.
3. ``coverage_by_group.csv``: the granularity note §3 retrieval premise with ``item_coverage`` (graded) next to
   the full hit, by question group (whole_only / sub_only / mixed).

Usage::

    .venv/bin/python scripts/report/a1_token_metrics.py      # → nuggets/scoring/analysis/…/all/token_metrics/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "nuggets"))

EVAL_ID = "v3_either_containment_merge_skip"
EMBS = {"jua-4b-mixed": "", "gemini-emb-2": "@gemini-emb-2"}
SCORE = REPO / "nuggets" / "scoring"
SET, JUDGE = "gold-v0-auto", "gemini-3.8-flash"
OUT = SCORE / "analysis" / SET / JUDGE / "all" / "token_metrics"
METRICS = ["recall", "partial_recall", "token_recall", "item_coverage", "context_precision", "token_precision",
           "noise_share", "scaffold_share"]
CID_RE = re.compile(r"^(S1|S2|S2c|S3|S4)_budget(\d+)(@gemini-emb-2)?$")


def eval_dir(emb: str) -> Path:
    return REPO / "runs" / "retrieval" / emb / "irpf" / "eval" / EVAL_ID


def per_question() -> pd.DataFrame:
    """Per question × context set (``context_id`` as in the nugget tables) × level, budget view, all gold."""
    out = []
    for emb, suf in EMBS.items():
        pq = pd.read_csv(eval_dir(emb) / "per_question.csv.gz", dtype={"question_number": str, "cutoff": str})
        pq = pq[(pq.view == "budget") & (pq.gold == "all") & (pq["slice"] == "all")
                & pq.level.isin(["article", "provision"])]
        pq = pq.assign(context_id=pq.strategy + "_budget" + pq.cutoff + suf, embedding=emb)
        out.append(pq)
    df = pd.concat(out, ignore_index=True)
    df["question_number"] = df.question_number.astype(int)
    return df


def question_groups() -> pd.Series:
    """whole_only / sub_only / mixed / none, from the statutory provision items (granularity note §3)."""
    d = pd.read_csv(eval_dir("jua-4b-mixed") / "per_item.csv.gz", dtype={"question_number": str}, low_memory=False)
    s1 = d[d.strategy == "S1"]
    prov = s1[(s1.level == "provision") & s1.statutory]
    g = prov.groupby("question_number").sub_article.agg(["size", "sum"])
    cls = pd.Series("none", index=sorted(set(s1.question_number)))
    cls[g.index] = np.where(g["sum"] == 0, "whole_only", np.where(g["sum"] == g["size"], "sub_only", "mixed"))
    cls.index = cls.index.astype(int)
    return cls


def spearman(x: pd.Series, y: pd.Series) -> float:
    ok = x.notna() & y.notna()
    if ok.sum() < 10 or x[ok].nunique() < 2 or y[ok].nunique() < 2:
        return np.nan
    return float(x[ok].rank().corr(y[ok].rank()))


def partial_spearman(x: pd.Series, y: pd.Series, z: pd.Series) -> float:
    """Spearman correlation of x and y controlling for z (Pearson partial correlation of the ranks)."""
    ok = x.notna() & y.notna() & z.notna()
    if ok.sum() < 10:
        return np.nan
    rx, ry, rz = x[ok].rank(), y[ok].rank(), z[ok].rank()
    rxy, rxz, ryz = rx.corr(ry), rx.corr(rz), ry.corr(rz)
    den = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return float((rxy - rxz * ryz) / den) if den > 0 else np.nan


def utilisation_per_question() -> pd.DataFrame:
    """Per answer run and question: share of the context-supported nuggets the answer supports."""
    from nuggetizer import analysis as an
    lab = an.nugget_labels(SCORE / "score" / SET / JUDGE)
    cl = an.nugget_labels(SCORE / "ctxsupport" / SET / JUDGE)
    m = lab[["llm", "context_id", "question_number", "nugget_id", "label"]].merge(
        cl[["context_id", "nugget_id", "label"]].rename(columns={"label": "ctx_label"}), on=["context_id", "nugget_id"])
    m = m[m.ctx_label == "support"]
    u = (m.assign(s=(m.label == "support").astype(float))
         .groupby(["llm", "context_id", "question_number"]).s.agg(["mean", "size"]).reset_index()
         .rename(columns={"mean": "utilisation", "size": "n_ctx_support"}))
    u["question_number"] = u.question_number.astype(int)
    return u


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)

    # 1. noise and signal ------------------------------------------------------------------------------------
    rows = []
    for emb in EMBS:
        m = pd.read_csv(eval_dir(emb) / "metrics.csv", dtype={"cutoff": str})
        m = m[(m.view == "budget") & (m.gold == "all") & (m["slice"] == "all") & m.level.isin(["article", "provision"])]
        w = m.pivot_table(index=["level", "cutoff", "strategy"], columns="metric", values="value").reset_index()
        rows.append(w.assign(embedding=emb))
    ns = pd.concat(rows, ignore_index=True)
    ns["cutoff"] = ns.cutoff.astype(int)
    cols = ["embedding", "level", "cutoff", "strategy", "recall", "hit", "partial_recall", "token_recall",
            "item_coverage", "context_precision", "token_precision", "noise_share", "scaffold_share", "context_tokens",
            "context_texts"]
    ns = ns[cols].sort_values(["embedding", "level", "cutoff", "strategy"],
                              key=lambda s: s.map({"S1": 0, "S2": 1, "S2c": 2, "S3": 3, "S4": 4}) if s.name == "strategy" else s)
    ns.to_csv(OUT / "noise_signal.csv", index=False, float_format="%.4f")
    print(ns[ns.cutoff == 4000].to_string(index=False, float_format="%.3f"))

    # 2. per-question correlations ----------------------------------------------------------------------------
    pq = per_question()
    ans = pd.read_csv(SCORE / "tables" / SET / JUDGE / "all" / "per_question.csv.gz")
    ans = ans[ans.context_id.str.match(CID_RE)]
    ctx = pd.read_csv(SCORE / "tables" / SET / JUDGE / "all" / "ctxsupport_per_question.csv.gz")
    ctx = ctx[ctx.context_id.str.match(CID_RE)][["context_id", "question_number", "V_strict"]].rename(
        columns={"V_strict": "ctx_V_strict"})
    util = utilisation_per_question()
    cls = question_groups()

    lv = []
    for level in ("provision", "article"):
        p = pq[pq.level == level]
        a = ans.merge(p, on=["context_id", "question_number"], how="inner")
        a = a.merge(ctx, on=["context_id", "question_number"], how="left").merge(
            util, on=["llm", "context_id", "question_number"], how="left")
        a = a[a.token_recall.notna()]           # questions with gold at this level (and a unit)
        for (llm, cid), g in a.groupby(["llm", "context_id"]):
            r = {"level": level, "llm": llm, "context_id": cid, "n": len(g)}
            for met in METRICS:
                r[f"V_strict~{met}"] = spearman(g.V_strict, g[met])
                r[f"ctx_V_strict~{met}"] = spearman(g.ctx_V_strict, g[met])
                r[f"utilisation~{met}"] = spearman(g.utilisation, g[met])
            r["V_strict~token_precision|token_recall"] = partial_spearman(g.V_strict, g.token_precision, g.token_recall)
            r["V_strict~noise_share|token_recall"] = partial_spearman(g.V_strict, g.noise_share, g.token_recall)
            r["utilisation~token_precision|token_recall"] = partial_spearman(g.utilisation, g.token_precision,
                                                                              g.token_recall)
            r["utilisation~noise_share|token_recall"] = partial_spearman(g.utilisation, g.noise_share, g.token_recall)
            lv.append(r)
    lv = pd.DataFrame(lv)
    lv.to_csv(OUT / "spearman_levels.csv", index=False, float_format="%.4f")
    show = ["V_strict~recall", "V_strict~partial_recall", "V_strict~token_recall", "V_strict~item_coverage",
            "V_strict~context_precision", "V_strict~token_precision", "V_strict~noise_share",
            "V_strict~token_precision|token_recall"]
    print("\n== Spearman with V_strict, mean over runs (provision level)")
    print(lv[lv.level == "provision"].groupby("llm")[show].mean().round(3).to_string())
    print(lv.groupby("level")[show].mean().round(3).to_string())
    print("\n== with ctx V_strict and utilisation")
    print(lv.groupby("level")[[c for c in lv.columns if c.startswith(("ctx_V", "utilisation~"))]].mean().round(3).T.to_string())

    # gains (granularity note §4 design), S2 − S1 at 4000
    gains = []
    for emb, suf in EMBS.items():
        a_id, b_id = "S1_budget4000" + suf, "S2_budget4000" + suf
        w = {}
        for level in ("article", "provision"):
            p = pq[(pq.level == level) & pq.context_id.isin([a_id, b_id])]
            x = p.pivot_table(index="question_number", columns="context_id", values=METRICS)
            for met in METRICS:
                if (met, b_id) in x and (met, a_id) in x:
                    w[f"{level}:{met}"] = x[(met, b_id)] - x[(met, a_id)]
        w = pd.DataFrame(w)
        for llm, h in ans[ans.context_id.isin([a_id, b_id])].groupby("llm"):
            v = h.pivot_table(index="question_number", columns="context_id", values="V_strict").dropna()
            if a_id not in v or b_id not in v:
                continue
            dv = (v[b_id] - v[a_id]).rename("dV")
            j = w.join(dv, how="inner").join(cls.rename("cls"), how="left")
            j = j[j.cls != "none"]
            for grp, h2 in [("all", j)] + list(j.groupby("cls")):
                r = {"embedding": emb, "llm": llm, "group": grp, "n": len(h2)}
                for c in w.columns:
                    r[c] = spearman(h2[c], h2.dV)
                gains.append(r)
    gains = pd.DataFrame(gains)
    gains.to_csv(OUT / "spearman_gains.csv", index=False, float_format="%.4f")
    gshow = ["article:recall", "provision:recall", "provision:partial_recall", "provision:token_recall",
             "provision:item_coverage", "provision:token_precision", "provision:context_precision"]
    print("\n== S2 − S1 retrieval gain vs V_strict gain (Spearman), jua, mean over generators")
    gj = gains[gains.embedding == "jua-4b-mixed"]
    print(gj.groupby("group")[["n"] + gshow].mean().round(3).to_string())
    print(gains[gains.embedding == "gemini-emb-2"].groupby("group")[["n"] + gshow].mean().round(3).to_string())

    # 3. whole vs sub-article with coverage -------------------------------------------------------------------
    cov = []
    for emb in EMBS:
        d = pd.read_csv(eval_dir(emb) / "per_item.csv.gz", dtype={"question_number": str}, low_memory=False)
        d = d[(d.level == "provision") & d.statutory]
        d["question_number"] = d.question_number.astype(int)
        for b in (2000, 4000, 8000):
            q = d.groupby(["question_number", "strategy"]).agg(full=(f"budget_full_{b}", "mean"),
                                                                any=(f"budget_any_{b}", "mean"),
                                                                coverage=(f"budget_cov_{b}", "mean")).reset_index()
            q = q.merge(cls.rename("group"), left_on="question_number", right_index=True)
            t = q.groupby(["group", "strategy"])[["full", "any", "coverage"]].mean().reset_index()
            cov.append(t.assign(embedding=emb, budget=b))
    cov = pd.concat(cov, ignore_index=True)
    cov.to_csv(OUT / "coverage_by_group.csv", index=False, float_format="%.4f")
    c4 = cov[(cov.budget == 4000) & cov.strategy.isin(["S1", "S2", "S3"]) & (cov.group != "none")]
    print("\n== provision items, budget 4000: full hit / any hit / token coverage per question group")
    print(c4.pivot_table(index=["embedding", "group"], columns="strategy", values=["full", "any", "coverage"])
          .round(3).to_string())
    print("\noutputs in", OUT.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
