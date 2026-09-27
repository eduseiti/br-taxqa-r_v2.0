"""Markdown tables from an evaluation directory (``metrics.csv`` and friends) → ``report.md``."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import Dataset
from .relevance import LEVELS
from .runs import read_json

HEADLINE_BUDGET = "4000"


def md_table(headers: list[str], rows: list[list]) -> str:
    def fmt(v) -> str:
        if isinstance(v, float):
            return "–" if pd.isna(v) else f"{v:.3f}"
        return str(v)
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(headers))) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


class _Metrics:
    def __init__(self, df: pd.DataFrame):
        df = df.copy()
        df["cutoff"] = df["cutoff"].astype(str)
        self.idx = {tuple(r[:-2]): (r[-2], r[-1]) for r in
                    df[["strategy", "level", "view", "cutoff", "gold", "slice", "metric", "value", "n_questions"]]
                    .itertuples(index=False, name=None)}
        self.strategies = list(dict.fromkeys(df["strategy"]))

    def get(self, s, level, view, cutoff, metric, gold="all", sl="all") -> float:
        return self.idx.get((s, level, view, str(cutoff), gold, sl, metric), (float("nan"), 0))[0]

    def n(self, s, level, view, cutoff, metric, gold="all", sl="all") -> int:
        return int(self.idx.get((s, level, view, str(cutoff), gold, sl, metric), (0, 0))[1])


def budget_tables(m: _Metrics, budgets: list[str], gold: str) -> str:
    out = []
    for level in LEVELS:
        metrics = ["recall", "hit", "full_recall"] + (["partial_recall"] if level == "provision" else [])
        if gold == "all":
            metrics.append("context_precision")   # a property of the context, the same for both gold sets
        rows = []
        for s in m.strategies:
            for met in metrics:
                oracle = m.get(s, level, "oracle", "-", met, gold) if met != "context_precision" else float("nan")
                rows.append([s, met] + [m.get(s, level, "budget", b, met, gold) for b in budgets] + [oracle])
        n = m.n(m.strategies[0], level, "budget", budgets[0], "recall", gold)
        out.append(f"**{level.capitalize()} level** ({n} questions)\n\n" +
                   md_table(["Strategy", "Metric"] + [f"{int(b) // 1000}k" for b in budgets] + ["Oracle"], rows))
    return "\n\n".join(out)


def unit_tables(m: _Metrics, ks: list[str], gold: str) -> str:
    out = []
    for level in ("document", "article"):
        rows = [[s] + [m.get(s, level, "unit", k, "recall", gold) for k in ks] +
                [m.get(s, level, "unit", "-", "mrr", gold), m.get(s, level, "unit", "-", "ndcg@10", gold),
                 m.get(s, level, "oracle", "-", "recall", gold)] for s in m.strategies]
        n = m.n(m.strategies[0], level, "unit", ks[0], "recall", gold)
        out.append(f"**{level.capitalize()} level** ({n} questions)\n\n" +
                   md_table(["Strategy"] + [f"R@{k}" for k in ks] + ["MRR", "nDCG@10", "Oracle R"], rows))
    return "\n\n".join(out)


def raw_table(m: _Metrics, ks: list[str]) -> str:
    rows = []
    for level in LEVELS:
        for s in m.strategies:
            rows.append([level, s] + [m.get(s, level, "raw", k, "recall") for k in ks])
    return md_table(["Level", "Strategy"] + [f"R@{k}" for k in ks], rows)


def budget_context_table(m: _Metrics, budgets: list[str]) -> str:
    rows = [[s] + [f"{m.get(s, 'document', 'budget', b, 'context_tokens'):.0f} / "
                   f"{m.get(s, 'document', 'budget', b, 'context_texts'):.1f}" for b in budgets]
            for s in m.strategies]
    return md_table(["Strategy"] + [f"{int(b) // 1000}k" for b in budgets], rows)


def slice_table(m: _Metrics, slices: list[str], budget: str) -> str:
    rows = []
    for level in LEVELS:
        for sl in slices:
            n = m.n(m.strategies[0], level, "budget", budget, "recall", "all", sl)
            if not n:
                continue
            rows.append([level, sl, n] + [m.get(s, level, "budget", budget, "recall", "all", sl) for s in m.strategies]
                        + [m.get(s, level, "oracle", "-", "recall", "all", sl) for s in m.strategies])
    return md_table(["Level", "Slice", "Questions"] + [f"{s} recall" for s in m.strategies] +
                    [f"{s} oracle" for s in m.strategies], rows)


def comparison_table(c: pd.DataFrame, budgets: list[str]) -> str:
    if c.empty:
        return "_No comparisons._"
    c = c.copy()
    c["cutoff"] = c["cutoff"].astype(str)
    sel = (((c["view"] == "budget") & c["metric"].isin(["recall", "context_precision"])) |
           ((c["view"] == "unit") & (((c["cutoff"] == "10") & (c["metric"] == "recall")) |
                                     c["metric"].isin(["mrr", "ndcg@10"]))))
    rows = []
    for r in c[sel].itertuples(index=False):
        rows.append([f"{r.b} − {r.a}", r.level, r.view, r.cutoff, r.metric, r.mean_a, r.mean_b,
                     f"{r.diff:+.3f} [{r.ci_low:+.3f}, {r.ci_high:+.3f}]", f"{r.p_permutation:.4f}", r.n_questions])
    return md_table(["Pair", "Level", "View", "Cutoff", "Metric", "Mean A", "Mean B", "Diff [95 % CI]",
                     "p (perm.)", "n"], rows)


def reach_table(r: pd.DataFrame) -> str:
    cols = [c for c in r.columns if c not in ("strategy", "level")]
    return md_table(["Strategy", "Level"] + cols, r[["strategy", "level"] + cols].values.tolist())


def write_report(eval_dir: Path, ds: Dataset | None = None) -> Path:
    eval_dir = Path(eval_dir)
    man = read_json(eval_dir / "manifest.json")
    p = man["params"]
    m = _Metrics(pd.read_csv(eval_dir / "metrics.csv", dtype={"cutoff": str}))
    comps = pd.read_csv(eval_dir / "comparisons.csv", dtype={"cutoff": str}) \
        if (eval_dir / "comparisons.csv").stat().st_size > 1 else pd.DataFrame()
    reach = pd.read_csv(eval_dir / "reachability.csv")
    budgets = [str(b) for b in p["budgets"]]
    headline = HEADLINE_BUDGET if HEADLINE_BUDGET in budgets else budgets[len(budgets) // 2]
    emb = man["retrieval"]["embedding"]
    git = man["script"]["git"]
    text = f"""# Retrieval evaluation — {emb['slug']} / {emb['instruction_name']} / {man['eval_id']}

Generated by `scripts/rag/rag.py evaluate` at {man['created_at']} (git {str(git['commit'])[:10]}{' dirty' if git['dirty'] else ''}).
Retrieval: {man['retrieval']['retriever']['name']}, top-{man['retrieval']['top_n']}. Matcher: annex rule
`{p['annex_rule']}`, binary gains. Context selection: dedup `{p['dedup']}`, overflow `{p['overflow']}`,
Qwen3 tokens. Chunks SHA-256 `{man['inputs']['chunks']['sha256'][:12]}…`, references SHA-256
`{man['inputs']['references']['sha256'][:12]}…`.

Metrics are means over the questions with at least one gold item at the level. **Oracle** is the
best value any ranking could reach with the strategy's chunks (gold that no chunk can hit caps it).
"Reachable gold" tables drop unreachable gold items (plan §2.1).

## 1. Gold and reachability

{md_table(["Level", "Questions with gold", "Gold items"],
          [[lv, man['gold']['questions_with_gold'][lv], man['gold']['gold_items'][lv]] for lv in LEVELS])}

References: {man['gold']['references']}, of which {man['gold']['references_not_in_corpus']} not in the corpus
(not counted as gold).

{reach_table(reach)}

## 2. Token-budget view (headline) — all resolved gold

{budget_tables(m, budgets, "all")}

Mean context size (Qwen3 tokens / texts) actually selected:

{budget_context_table(m, budgets)}

## 3. Token-budget view — reachable gold only

{budget_tables(m, budgets, "reachable")}

## 4. Unit projection (distinct documents / articles)

{unit_tables(m, [str(k) for k in p['unit_ks']], "all")}

Reachable gold only:

{unit_tables(m, [str(k) for k in p['unit_ks']], "reachable")}

## 5. Raw text rank (diagnostic) — recall, all gold

{raw_table(m, [str(k) for k in p['raw_ks']])}

## 6. Slices — recall at the {int(headline) // 1000}k budget, all gold

{slice_table(m, ["all", "explicit", "embedded", "statutory", "non_statutory", "annex_A", "whole_article",
                 "sub_article"], headline)}

`whole_article` / `sub_article` (provision level): the gold unit is a whole article, or a caput /
§ / inciso / alínea / item inside one. Unresolved units (no LexML id) are in neither.

Per-chapter numbers: `metrics_by_chapter.csv.gz`.

## 7. Paired comparisons (per-question differences, {p['n_resamples']} resamples, seed {p['seed']})

{comparison_table(comps, budgets)}

All metrics and cutoffs: `comparisons.csv`.
"""
    out = eval_dir / "report.md"
    out.write_text(text, encoding="utf-8")
    return out
