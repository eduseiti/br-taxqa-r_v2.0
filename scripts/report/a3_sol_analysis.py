#!/usr/bin/env python3
"""A3 analyses (plan ``docs/20261122_164407_*`` §5.3): GPT-6.2 Sol against GPT-5.6 Terra in Terra's 4 conditions.

No API calls. Inputs: the phase 5 nugget labels (primary set ``gold-v0-auto``, judge gemini-3.8-flash, all
questions), the context-support labels (utilisation / leakage), and the A2 in-text citation tables
(``nuggets.py intext``; rerun it after the Sol runs exist).

Outputs in ``nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/sol/``:

- ``means.csv``: per generator × condition: V_strict, A_strict, V, contradiction rates, abstention, length;
- ``sol_vs_terra.csv``: paired Sol − Terra per condition (bootstrap CI, permutation p, chapter-cluster CI);
- ``within.csv``: paired condition differences per generator (closed book → S1 / S2 / oracle, S1 → S2);
- ``did.csv``: difference in differences (Sol − Terra) × (b − a), paired by question (H1: closed book → S2;
  H5: S1 → S2; also closed book → S1 / oracle);
- ``utilisation.csv``: utilisation and leakage of both generators (H3, nugget level);
- ``intext.csv``: A2 in-text citation figures of both generators (H3 citation level, H4).

Usage::

    .venv/bin/python scripts/report/a3_sol_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "scripts" / "nuggets"), str(REPO / "scripts")]

from nuggetizer import analysis as an  # noqa: E402
from nuggetizer import scoring  # noqa: E402
from ragpipe.metrics import paired_bootstrap_ci, paired_permutation_p  # noqa: E402

SCORE = REPO / "nuggets" / "scoring"
SET, JUDGE = "gold-v0-auto", "gemini-3.8-flash"
OUT = SCORE / "analysis" / SET / JUDGE / "all" / "sol"
LLMS = ["gpt-5.6-terra", "gpt-6.2-sol"]
CONDS = ["closed_book", "S1_budget4000", "S2_budget4000", "oracle_budget4000"]
METRICS = ["V_strict", "A_strict", "V", "any_contradicts", "contradicts"]
N_RES = 10_000


def nuggets() -> dict:
    d: dict[str, list[dict]] = {}
    for n in scoring.jl(REPO / "nuggets" / "gold" / "v0-auto" / "nuggets.jsonl"):
        d.setdefault(n["question_number"], []).append(n)
    return d


def per_question(nt: pd.DataFrame) -> pd.DataFrame:
    lab = an.nugget_labels(SCORE / "score" / SET / JUDGE)
    lab = lab[lab.llm.isin(LLMS) & lab.context_id.isin(CONDS)]
    return an.per_question_long(lab, nt, ["run_id", "llm", "context_id"]), lab


def answers_meta() -> pd.DataFrame:
    rows = []
    for llm in LLMS:
        for c in CONDS:
            p = "answer_closed_v1" if c == "closed_book" else "answer_v1"
            for x in scoring.jl(REPO / "runs/answers/jua-4b-mixed/irpf" / p / llm / c / "answers.jsonl"):
                if x["status"] == "skipped":
                    continue
                rows.append({"llm": llm, "context_id": c, "question_number": x["question_number"],
                             "abstained": bool(x.get("abstained")), "answer_chars": len(x.get("answer") or ""),
                             "n_claims": len(x.get("claims") or [])})
    return pd.DataFrame(rows)


def did(pq: pd.DataFrame, a: str, b: str) -> list[dict]:
    """(Sol − Terra) × (b − a) per question; positive = Sol gains more from a → b than Terra."""
    w = pq.pivot_table(index="question_number", columns=["llm", "context_id"], values=METRICS)
    out = []
    for m in METRICS:
        try:
            d = ((w[(m, "gpt-6.2-sol", b)] - w[(m, "gpt-6.2-sol", a)])
                 - (w[(m, "gpt-5.6-terra", b)] - w[(m, "gpt-5.6-terra", a)])).dropna().to_numpy(float)
        except KeyError:
            continue
        lo, hi = paired_bootstrap_ci(d, N_RES, 13)
        sol = (w[(m, "gpt-6.2-sol", b)] - w[(m, "gpt-6.2-sol", a)]).dropna()
        ter = (w[(m, "gpt-5.6-terra", b)] - w[(m, "gpt-5.6-terra", a)]).dropna()
        out.append({"a": a, "b": b, "metric": m, "n": len(d), "terra_diff": ter.mean(), "sol_diff": sol.mean(),
                    "did": d.mean(), "ci_lo": lo, "ci_hi": hi, "p_perm": paired_permutation_p(d, N_RES, 13)})
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    nt = an.nugget_table(nuggets())
    pq, lab = per_question(nt)
    meta = answers_meta()
    m = pq.merge(meta, on=["llm", "context_id", "question_number"], how="left")
    means = m.groupby(["llm", "context_id"]).agg(
        n=("V_strict", "size"), V_strict=("V_strict", "mean"), A_strict=("A_strict", "mean"), V=("V", "mean"),
        any_contradicts=("any_contradicts", "mean"), contradicts=("contradicts", "mean"),
        abstained=("abstained", "mean"), answer_chars=("answer_chars", "mean"), n_claims=("n_claims", "mean")
    ).reset_index()
    means.to_csv(OUT / "means.csv", index=False, float_format="%.4f")

    x = pq.rename(columns={"context_id": "cond"}).assign(context_id=lambda d: d.llm)
    vs = scoring.compare(x, "gpt-5.6-terra", "gpt-6.2-sol", ["cond"], N_RES)
    vs.to_csv(OUT / "sol_vs_terra.csv", index=False, float_format="%.4f")

    pairs = [("closed_book", "S2_budget4000"), ("closed_book", "S1_budget4000"), ("closed_book", "oracle_budget4000"),
             ("S1_budget4000", "S2_budget4000"), ("S2_budget4000", "oracle_budget4000")]
    within = pd.concat([scoring.compare(pq, a, b, ["llm"], N_RES) for a, b in pairs], ignore_index=True)
    within.to_csv(OUT / "within.csv", index=False, float_format="%.4f")

    d = pd.DataFrame([r for a, b in pairs for r in did(pq, a, b)])
    d.to_csv(OUT / "did.csv", index=False, float_format="%.4f")

    cl = an.nugget_labels(SCORE / "ctxsupport" / SET / JUDGE)
    cl = cl[cl.contexts.str.startswith("runs/contexts/jua-4b-mixed/irpf/")]
    ut = an.utilisation(lab[lab.context_id != "closed_book"], cl, nt)
    ut.to_csv(OUT / "utilisation.csv", index=False, float_format="%.4f")

    it = SCORE / "analysis" / SET / JUDGE / "all" / "intext" / "intext_citations_runs.csv"
    if it.exists():
        t = pd.read_csv(it)
        t = t[t.llm.isin(LLMS) & t.context_id.isin(CONDS)]
        t.to_csv(OUT / "intext.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 250)
    show = lambda df: print(df.to_string(index=False, float_format="%.3f"), "\n")  # noqa: E731
    print("== means"); show(means)
    print("== Sol − Terra, paired, per condition"); show(vs[vs.metric.isin(["V_strict", "A_strict", "any_contradicts"])][
        ["cond", "metric", "n", "mean_a", "mean_b", "diff", "ci_lo", "ci_hi", "p_perm", "cluster_ci_lo", "cluster_ci_hi"]])
    print("== within generator"); show(within[within.metric.isin(["V_strict", "any_contradicts"])][
        ["llm", "a", "b", "metric", "n", "mean_a", "mean_b", "diff", "ci_lo", "ci_hi", "p_perm"]])
    print("== difference in differences (Sol − Terra) × (b − a)"); show(d[d.metric.isin(["V_strict", "A_strict",
                                                                                            "any_contradicts"])])
    print("== utilisation (vital nuggets)"); show(ut[ut.nuggets == "vital"])
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
