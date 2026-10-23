"""Phase 5: scoring of RAG answers against the gold nuggets (plan v2 §5.1–§5.3).

Inputs are the answer runs of ``scripts/rag/rag.py run`` (``runs/answers/<run_id>/answers.jsonl`` + ``run.json``)
and the context sets of ``rag.py context`` (``runs/contexts/<…>/<context_id>/contexts.jsonl.gz``). The judge calls
live in ``nuggets.py score`` / ``ctxsupport``; this module holds what needs no LLM: which items need a call, the
per-question scores (V_strict, V, A_strict, A, W, contradiction rate) and the paired comparisons.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "rag"))

from ragpipe.data import load_chapters  # noqa: E402
from ragpipe.metrics import paired_bootstrap_ci, paired_permutation_p  # noqa: E402

CHAPTERS = REPO / "scripts" / "rag" / "data" / "pr_irpf_2024_chapters.csv"
CREDIT = {"support": 1.0, "partial_support": 0.5, "not_support": 0.0, "contradicts": 0.0}
LABELS = tuple(CREDIT)


def jl(path: Path) -> list[dict]:
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f.read().split("\n") if x.strip()]


def run_key(run_dir: Path) -> str:
    """``runs/answers/<embedding>/<instruction>/<prompt>/<llm>/<context_id>`` → the ``run_id`` of run.json."""
    return json.loads((Path(run_dir) / "run.json").read_text())["run_id"]


def answer_items(run_dir: Path, qids: set[str]) -> list[dict]:
    """Answer lines of ``qids``. Skipped lines (empty oracle) are dropped; an abstention or an error needs no
    judge call: every nugget is ``not_support`` (``source`` says why)."""
    out = []
    for ln in jl(Path(run_dir) / "answers.jsonl"):
        if ln["question_number"] not in qids or ln["status"] == "skipped":
            continue
        src = "error" if ln["status"] == "error" else "abstained" if ln.get("abstained") else "judge"
        out.append({"question_number": ln["question_number"], "text": ln.get("answer") or "", "source": src,
                    "context_id": ln["context_id"]})
    return out


def context_items(ctx_dir: Path, qids: set[str]) -> list[dict]:
    """Context lines of ``qids``; an empty context (empty oracle) is dropped."""
    out = []
    for ln in jl(Path(ctx_dir) / "contexts.jsonl.gz"):
        if ln["question_number"] in qids and ln.get("context", "").strip():
            out.append({"question_number": ln["question_number"], "text": ln["context"], "source": "judge",
                        "context_id": ln["context_id"]})
    return out


def question_scores(labels: list[str], importance: list[str]) -> dict:
    """Plan v1 §4.3: s(support)=1, s(partial)=0.5, s(not / contradicts)=0."""
    s = np.array([CREDIT[x] for x in labels])
    strict = np.array([x == "support" for x in labels], dtype=float)
    vital = np.array([i == "vital" for i in importance])
    w = np.where(vital, 1.0, 0.5)
    nv = int(vital.sum())
    return {"n_nuggets": len(labels), "n_vital": nv,
            "V_strict": strict[vital].mean() if nv else np.nan, "V": s[vital].mean() if nv else np.nan,
            "A_strict": strict.mean(), "A": s.mean(), "W": float((w * s).sum() / w.sum()),
            "contradicts": float(np.mean([x == "contradicts" for x in labels])),
            "any_contradicts": float(any(x == "contradicts" for x in labels)),
            **{f"n_{k}": sum(x == k for x in labels) for k in LABELS}}


METRICS = ("V_strict", "V", "A_strict", "A", "W", "contradicts", "any_contradicts")


def per_question(labels_path: Path, nuggets: dict[str, list[dict]], meta: dict) -> pd.DataFrame:
    """One row per question of a ``labels.jsonl`` (score or ctxsupport) with ``meta`` columns."""
    rows = []
    for x in jl(labels_path):
        qn = nuggets[x["question_number"]]
        imp = [n["importance"] for n in qn]
        rows.append({**meta, "question_number": x["question_number"], "source": x["source"],
                     **question_scores([y["label"] for y in x["labels"]], imp)})
    return pd.DataFrame(rows)


def chapter_cluster_ci(diff: np.ndarray, chapters: np.ndarray, n_resamples: int = 10_000, seed: int = 13,
                       alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean difference with P&R chapters resampled as clusters (plan v2 §5.3)."""
    labs, inv = np.unique(chapters, return_inverse=True)
    sums = np.bincount(inv, weights=diff, minlength=len(labs))
    cnt = np.bincount(inv, minlength=len(labs)).astype(float)
    rng = np.random.default_rng(seed)
    k = rng.multinomial(len(labs), np.full(len(labs), 1.0 / len(labs)), size=n_resamples).astype(float)
    means = (k @ sums) / (k @ cnt)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def compare(pq: pd.DataFrame, a: str, b: str, by: list[str], n_resamples: int = 10_000,
            seed: int = 13) -> pd.DataFrame:
    """Paired b − a per group of ``by`` (e.g. generator) over the questions both runs scored."""
    chapters = load_chapters(CHAPTERS, sorted(pq.question_number.unique()))
    out = []
    for key, g in pq.groupby(by):
        ga, gb = g[g.context_id == a].set_index("question_number"), g[g.context_id == b].set_index("question_number")
        common = ga.index.intersection(gb.index)
        if not len(common):
            continue
        ch = np.array([chapters[q] for q in common])
        for m in METRICS:
            d = (gb.loc[common, m] - ga.loc[common, m]).to_numpy(dtype=float)
            ok = ~np.isnan(d)
            d, c = d[ok], ch[ok]
            lo, hi = paired_bootstrap_ci(d, n_resamples, seed)
            clo, chi = chapter_cluster_ci(d, c, n_resamples, seed)
            out.append({**dict(zip(by, key if isinstance(key, tuple) else (key,))), "a": a, "b": b, "metric": m,
                        "n": int(ok.sum()), "mean_a": float(ga.loc[common, m][ok].mean()),
                        "mean_b": float(gb.loc[common, m][ok].mean()), "diff": float(d.mean()),
                        "ci_lo": lo, "ci_hi": hi, "p_perm": paired_permutation_p(d, n_resamples, seed),
                        "cluster_ci_lo": clo, "cluster_ci_hi": chi})
    return pd.DataFrame(out)


# Default pairs (plan v2 §5.3): the main S2 − S1, the S3 / caput variants, and the bounds.
PAIRS = [("S1_budget4000", "S2_budget4000"), ("S2_budget4000", "S3_budget4000"),
         ("S2_budget4000", "S2c_budget4000"), ("S3_budget4000", "S4_budget4000"),
         ("closed_book", "S1_budget4000"), ("closed_book", "S2_budget4000"),
         ("S1_budget4000", "oracle_budget4000"), ("S2_budget4000", "oracle_budget4000"),
         ("S1_budget2000", "S2_budget2000"), ("S1_budget8000", "S2_budget8000"),
         ("S2_budget4000", "S2_budget4000_context_v1"), ("S2_budget4000", "wrong-S2_budget4000")]
