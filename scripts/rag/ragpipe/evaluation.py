"""Stage RE: score stored rankings against the gold references — the legal-provision test
(plan §4).

For every question, strategy and level (document / article / provision), each gold item gets its
first hit position in three views (plan §4.3):

- ``budget`` (headline): the texts selected by :func:`ragpipe.context.select` under a Qwen3-token
  budget, with containment de-duplication — the context the generator would see;
- ``unit``: the ranking projected to distinct documents / articles (a grouping chunk stands for the
  articles it contains); document and article levels only;
- ``raw``: texts as retrieved (diagnostic);

plus ``oracle``: whether any chunk of the strategy can hit the item at all (the ceiling).

Outputs, under ``<retrieval run>/eval/<eval_id>/``::

    manifest.json            gold hash, matcher rules, cutoffs, retrieval run pointer
    metrics.csv              strategy, level, view, cutoff, gold, slice, metric, value, n_questions
    metrics_by_chapter.csv.gz same, sliced by the P&R chapter (gold = all)
    comparisons.csv          paired differences between strategies (bootstrap CI, permutation p)
    reachability.csv         gold items per strategy × level: reachable, unreachable by reason, G3/G4 counts
    per_question.csv.gz      one row per question × strategy × level × view × cutoff × gold
    per_item.csv.gz          one row per gold item × strategy (positions and budget hits)
    report.md                generated tables
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as M
from .context import Cutoff, select
from .data import InputError, Paths, load_chapters, load_chunks, load_dataset
from .relevance import LEVELS, GoldItem, Matcher, gold_items
from .retrieval import load_rankings
from .strategies import member_mask
from .runs import (base_manifest, prepare_run_dir, read_json, rel, sha256_file, sha256_json, write_csv,
                   write_json)

log = logging.getLogger("ragpipe")

INF = math.inf
ITEM_SLICES = ("all", "explicit", "embedded", "statutory", "non_statutory", "annex_A", "whole_article",
               "sub_article")
GOLD_SETS = ("all", "reachable")
QUALITY_METRICS = ("recall", "hit", "full_recall", "partial_recall")
#: Unit positions beyond this count as "not retrieved" (bounds work for grouping chunks in S3).
MAX_UNIT_POSITION = 1000


@dataclass
class EvalConfig:
    annex_rule: str = "either"
    budgets: tuple[int, ...] = (1000, 2000, 4000, 8000, 16000)
    unit_ks: tuple[int, ...] = (1, 3, 5, 10, 20, 50, 100)
    raw_ks: tuple[int, ...] = (1, 5, 10, 20, 50, 100, 1000)
    dedup: str = "containment"
    overflow: str = "skip"
    strategies: list[str] | None = None
    comparisons: tuple[tuple[str, str], ...] = (("S1", "S2"), ("S2", "S3"))
    n_resamples: int = 10_000
    seed: int = 13
    eval_id: str | None = None
    force: bool = False

    @property
    def resolved_eval_id(self) -> str:
        return self.eval_id or f"{self.annex_rule}_{self.dedup}_{self.overflow}"

    def params(self) -> dict:
        return {"annex_rule": self.annex_rule, "budgets": list(self.budgets), "unit_ks": list(self.unit_ks),
                "raw_ks": list(self.raw_ks), "dedup": self.dedup, "overflow": self.overflow,
                "token_counter": "qwen3", "gain": "binary", "max_unit_position": MAX_UNIT_POSITION,
                "comparisons": [list(c) for c in self.comparisons], "n_resamples": self.n_resamples,
                "seed": self.seed}


# ================================================================================================
# Ranked texts of one strategy
# ================================================================================================

@dataclass
class RankedTexts:
    """The texts that occur in a strategy's rankings, with their chunks, tokens and intervals."""

    text_ids: list[str]
    members: list[np.ndarray]                        # chunk rows, representative first
    tokens: np.ndarray                               # Qwen3 tokens of the text
    intervals: list[list[tuple[int, int, int]]]      # (file index, start, end) per member
    local_of_row: np.ndarray                         # chunk row → local text index (-1: not ranked)
    per_question: dict[str, np.ndarray]              # question → local indices, best first
    units: dict[str, dict[int, list[tuple]]] = field(default_factory=lambda: {"document": {}, "article": {}})


def ranked_texts(rankings: pd.DataFrame, chunks: pd.DataFrame, file_index: dict[str, int]) -> RankedTexts:
    row_of = dict(zip(chunks["chunk_id"], range(len(chunks))))
    uniq = rankings.drop_duplicates("text_id")[["text_id", "chunk_id", "alias_chunk_ids"]]
    text_ids = uniq["text_id"].tolist()
    local = {t: i for i, t in enumerate(text_ids)}
    arquivo, start, end = chunks["arquivo"].to_numpy(), chunks["Num_Inicio"].to_numpy(), chunks["Num_Final"].to_numpy()
    ntok = chunks["n_tokens_qwen3"].to_numpy()
    members, intervals = [], []
    local_of_row = np.full(len(chunks), -1, dtype=np.int64)
    for i, (rep, al) in enumerate(zip(uniq["chunk_id"], uniq["alias_chunk_ids"])):
        ids = [rep] + (al.split(";") if al else [])
        try:
            rows = np.array([row_of[c] for c in ids], dtype=np.int64)
        except KeyError as e:
            raise InputError(f"ranked chunk {e} is not in the chunk file; rerun `rag.py retrieve`") from None
        members.append(rows)
        intervals.append([(file_index[arquivo[r]], int(start[r]), int(end[r])) for r in rows])
        local_of_row[rows] = i
    tokens = np.array([int(ntok[m[0]]) for m in members], dtype=np.int64)
    loc = rankings["text_id"].map(local).to_numpy()
    per_question = {q: loc[idx] for q, idx in rankings.groupby("question_number", sort=False).indices.items()}
    return RankedTexts(text_ids, members, tokens, intervals, local_of_row, per_question)


def unit_positions(rt: RankedTexts, ranked: np.ndarray, level: str, matcher: Matcher) -> dict[tuple, int]:
    """Distinct retrieval units of a ranking in order of first appearance → 1-based position."""
    cache = rt.units[level]
    pos: dict[tuple, int] = {}
    for t in ranked:
        units = cache.get(t)
        if units is None:
            units = cache[t] = matcher.units_of_rows(rt.members[t], level)
        for u in units:
            if u not in pos:
                pos[u] = len(pos) + 1
        if len(pos) >= MAX_UNIT_POSITION:
            break
    return pos


# ================================================================================================
# Per strategy: item positions and context statistics
# ================================================================================================

def evaluate_strategy(name: str, in_strategy: np.ndarray, rt: RankedTexts, gold: dict[str, dict[str, list[GoldItem]]],
                      matcher: Matcher, statutory: dict[str, bool],
                      cfg: EvalConfig) -> tuple[list[dict], list[dict]]:
    """Rows of the per-item table and of the context table for one strategy (``in_strategy``: the
    chunk-table rows it indexes, :func:`.strategies.member_mask`)."""
    cutoffs = [Cutoff("budget", b) for b in cfg.budgets]
    item_rows, ctx_rows = [], []
    empty = np.empty(0, dtype=np.int64)
    for q in sorted(gold):
        ranked = rt.per_question.get(q, empty)
        selections = {c.value: select(ranked, rt.tokens, rt.intervals, c, cfg.dedup, cfg.overflow) for c in cutoffs}
        for level in LEVELS:
            items = gold[q][level]
            if not items:
                continue
            upos = unit_positions(rt, ranked, level, matcher) if level != "provision" else {}
            relevant_any = np.zeros(len(ranked), dtype=bool)
            rank_of: dict[int, int] | None = None
            for it in items:
                m = matcher.match(it)
                full_rows = m.full[in_strategy[m.full]]
                part_rows = m.partial[in_strategy[m.partial]]
                full_t = np.unique(rt.local_of_row[full_rows])
                any_t = np.unique(rt.local_of_row[np.concatenate([full_rows, part_rows])])
                hit_full = np.isin(ranked, full_t[full_t >= 0])
                hit_any = np.isin(ranked, any_t[any_t >= 0])
                relevant_any |= hit_any
                # split-article coverage: all parts of one file retrieved (relevance G5 refinement)
                cover_sets = [rt.local_of_row[p] for p in m.parts if in_strategy[p].all()]
                rank_cover = INF
                if cover_sets:
                    if rank_of is None:
                        rank_of = {int(t): i + 1 for i, t in enumerate(ranked)}
                    rank_cover = min(max(rank_of.get(int(t), INF) for t in cs) for cs in cover_sets)
                files = [u[0] for u in m.units]
                row = {
                    "question_number": q, "strategy": name, "level": level, "item": it.key_str,
                    "label": it.label, "origin": it.origin, "statutory": statutory.get(it.document_id, True),
                    "annex_A": matcher.is_annex_a(files) if level != "document"
                    else matcher.is_annex_a(sorted(matcher.files_of_doc.get(it.document_id, ()))),
                    "main_and_annex": m.main_and_annex,
                    "sub_article": level == "provision" and bool(it.fragment_id) and it.fragment_id != it.article_id,
                    "reachable": len(full_rows) > 0 or bool(cover_sets),
                    "reachable_partial": len(full_rows) + len(part_rows) > 0,
                    "reachable_by_parts_only": not len(full_rows) and bool(cover_sets),
                    "only_ambiguous": matcher.only_ambiguous(full_rows),
                    "unreachable_reason": "" if len(full_rows) or cover_sets else unreachable_reason(it, m, matcher),
                    "rank_full": min(_first(hit_full), rank_cover), "rank_any": _first(hit_any),
                    "unit_pos": min((upos.get(u, INF) for u in m.units), default=INF) if level != "provision" else INF,
                }
                for b, sel in selections.items():
                    covered = bool(sel) and (bool(hit_full[sel].any()) or any(
                        np.isin(cs, ranked[sel]).all() for cs in cover_sets))
                    row[f"budget_full_{b}"] = covered
                    row[f"budget_any_{b}"] = bool(hit_any[sel].any()) if sel else False
                item_rows.append(row)
            for b, sel in selections.items():
                toks = rt.tokens[ranked[sel]] if sel else empty
                total = int(toks.sum())
                gold_toks = int(toks[relevant_any[sel]].sum()) if sel else 0
                ctx_rows.append({"question_number": q, "strategy": name, "level": level, "view": "budget",
                                 "cutoff": str(b), "context_tokens": total, "context_texts": len(sel),
                                 "context_precision": gold_toks / total if total else math.nan})
    return item_rows, ctx_rows


def _first(mask: np.ndarray) -> float:
    idx = np.flatnonzero(mask)
    return float(idx[0] + 1) if len(idx) else INF


def unreachable_reason(it: GoldItem, m, matcher: Matcher) -> str:
    if it.level == "provision" and not (it.fragment_id and it.lexml_file):
        return "no_lexml_id"
    if it.document_id not in matcher.rows_by_doc:
        return "document_without_chunks"
    if it.level == "article" and not m.units:
        return "article_not_in_lexml"
    if it.level == "provision" and len(m.full) == 0:
        return "partial_only" if len(m.partial) else "unit_not_in_chunks"
    return "not_in_strategy"


# ================================================================================================
# Aggregation
# ================================================================================================

def view_hits(items: pd.DataFrame, cfg: EvalConfig) -> pd.DataFrame:
    """Long table: one row per item × (view, cutoff) with ``hit_full`` / ``hit_any``."""
    parts = []
    keep = ["question_number", "strategy", "level", "origin", "statutory", "annex_A", "sub_article", "reachable"]

    def add(view: str, cutoff: str, full: pd.Series, anyh: pd.Series, mask: pd.Series | None = None) -> None:
        df = items.loc[:, keep].copy()
        df["view"], df["cutoff"], df["hit_full"], df["hit_any"] = view, cutoff, full.to_numpy(), anyh.to_numpy()
        parts.append(df if mask is None else df[mask.to_numpy()])

    add("oracle", "-", items["reachable"], items["reachable_partial"])
    for b in cfg.budgets:
        add("budget", str(b), items[f"budget_full_{b}"], items[f"budget_any_{b}"])
    for k in cfg.raw_ks:
        add("raw", str(k), items["rank_full"] <= k, items["rank_any"] <= k)
    unit = items["level"] != "provision"
    for k in cfg.unit_ks:
        add("unit", str(k), items["unit_pos"] <= k, items["unit_pos"] <= k, unit)
    return pd.concat(parts, ignore_index=True)


def slice_mask(df: pd.DataFrame, s: str) -> pd.Series:
    return {"all": pd.Series(True, index=df.index), "explicit": df["origin"] == "explicit",
            "embedded": df["origin"] == "embedded", "statutory": df["statutory"],
            "non_statutory": ~df["statutory"], "annex_A": df["annex_A"],
            # provision level only: gold unit is a whole article vs a caput / § / inciso / alínea / item
            "whole_article": (df["level"] == "provision") & ~df["sub_article"],
            "sub_article": df["sub_article"]}[s]


def per_question_table(items: pd.DataFrame, ctx: pd.DataFrame, cfg: EvalConfig,
                       slices: tuple[str, ...] = ITEM_SLICES) -> pd.DataFrame:
    """Wide per-question metrics for every view/cutoff, gold set and item slice."""
    long = view_hits(items, cfg)
    keys = ["question_number", "strategy", "level", "view", "cutoff"]
    out = []
    for gold in GOLD_SETS:
        base = long if gold == "all" else long[long["reachable"]]
        ibase = items if gold == "all" else items[items["reachable"]]
        for s in slices:
            sub = base[slice_mask(base, s)]
            g = sub.groupby(keys, sort=False).agg(n_gold=("hit_full", "size"), n_hit=("hit_full", "sum"),
                                                  n_hit_any=("hit_any", "sum")).reset_index()
            g["recall"] = g["n_hit"] / g["n_gold"]
            g["hit"] = (g["n_hit"] > 0).astype(float)
            g["full_recall"] = (g["n_hit"] == g["n_gold"]).astype(float)
            g["partial_recall"] = np.where(g["level"] == "provision", g["n_hit_any"] / g["n_gold"], np.nan)
            # MRR and nDCG@10 on the unit projection
            isub = ibase[slice_mask(ibase, s) & (ibase["level"] != "provision")]
            if len(isub):
                u = isub.assign(rr=1.0 / isub["unit_pos"],
                                gain=np.where(isub["unit_pos"] <= 10, 1.0 / np.log2(isub["unit_pos"] + 1), 0.0))
                r = u.groupby(["question_number", "strategy", "level"], sort=False).agg(
                    n_gold=("rr", "size"), mrr=("rr", "max"), dcg=("gain", "sum")).reset_index()
                ideal = {n: sum(1 / math.log2(i + 1) for i in range(1, min(n, 10) + 1)) for n in r["n_gold"].unique()}
                r["ndcg@10"] = r["dcg"] / r["n_gold"].map(ideal)
                r["view"], r["cutoff"] = "unit", "-"
                g = pd.concat([g, r.drop(columns="dcg")], ignore_index=True)
            g["gold"], g["slice"] = gold, s
            out.append(g)
    pq = pd.concat(out, ignore_index=True)
    ctx = ctx.assign(gold="all", slice="all")
    pq = pq.merge(ctx, on=keys + ["gold", "slice"], how="left")
    cols = keys + ["gold", "slice", "n_gold", "n_hit", "recall", "hit", "full_recall", "partial_recall", "mrr",
                   "ndcg@10", "context_precision", "context_tokens", "context_texts"]
    return pq[cols]


METRIC_COLS = ["recall", "hit", "full_recall", "partial_recall", "mrr", "ndcg@10", "context_precision",
               "context_tokens", "context_texts"]


def aggregate(pq: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Mean over questions → long format ``… metric, value, n_questions`` (NaN metrics dropped)."""
    long = pq.melt(id_vars=by + ["question_number"], value_vars=METRIC_COLS, var_name="metric").dropna(
        subset=["value"])
    agg = long.groupby(by + ["metric"], sort=False)["value"].agg(["mean", "size"]).reset_index()
    return agg.rename(columns={"mean": "value", "size": "n_questions"})


def order_rows(df: pd.DataFrame, strategies: list[str]) -> pd.DataFrame:
    """Deterministic, readable row order."""
    view_order = {"budget": 0, "unit": 1, "raw": 2, "oracle": 3}
    df = df.copy()
    sk = {s: i for i, s in enumerate(strategies)}
    df["_s"] = df["strategy"].map(sk)
    df["_l"] = df["level"].map({lv: i for i, lv in enumerate(LEVELS)})
    df["_v"] = df["view"].map(view_order)
    df["_c"] = pd.to_numeric(df["cutoff"], errors="coerce").fillna(1e12)
    extra = [c for c in ("gold", "slice", "metric") if c in df.columns]
    df = df.sort_values(["_s", "_l", "_v", "_c", *extra, *([] if "question_number" not in df else ["question_number"])],
                        kind="stable")
    return df.drop(columns=["_s", "_l", "_v", "_c"]).reset_index(drop=True)


def compare(pq: pd.DataFrame, a: str, b: str, n_resamples: int, seed: int,
            views: tuple[str, ...] = ("budget", "unit", "raw")) -> pd.DataFrame:
    """Paired per-question differences ``b − a`` over the questions both strategies were scored on."""
    base = pq[(pq["gold"] == "all") & (pq["slice"] == "all") & pq["view"].isin(views)]
    metrics = ["recall", "hit", "full_recall", "partial_recall", "mrr", "ndcg@10", "context_precision"]
    rows = []
    for level in LEVELS:
        sub = base[base["level"] == level]
        long = sub.melt(id_vars=["question_number", "strategy", "view", "cutoff"], value_vars=metrics,
                        var_name="metric").dropna(subset=["value"])
        wide = long.pivot_table(index="question_number", columns=["strategy", "view", "cutoff", "metric"],
                                values="value", aggfunc="first")
        if a not in wide.columns.get_level_values(0) or b not in wide.columns.get_level_values(0):
            continue
        A, B = wide[a], wide[b]
        common = A.columns.intersection(B.columns)
        A, B = A[common], B[common]
        ok = A.notna().all(axis=1) & B.notna().all(axis=1)
        A, B = A[ok], B[ok]
        if not len(A):
            continue
        D = (B - A).to_numpy()
        lo, hi = M.paired_bootstrap_ci(D, n_resamples, seed)
        p = M.paired_permutation_p(D, n_resamples, seed)
        for j, (view, cutoff, metric) in enumerate(common):
            rows.append({"a": a, "b": b, "level": level, "view": view, "cutoff": cutoff, "metric": metric,
                         "mean_a": A.iloc[:, j].mean(), "mean_b": B.iloc[:, j].mean(), "diff": D[:, j].mean(),
                         "ci_low": lo[j], "ci_high": hi[j], "p_permutation": p[j], "n_questions": len(D)})
    out = pd.DataFrame(rows)
    if len(out):
        out["strategy"] = a
        out = order_rows(out, [a]).drop(columns="strategy")
    return out


def reachability(items: pd.DataFrame, strategies: list[str]) -> pd.DataFrame:
    rows = []
    for (s, lv), g in items.groupby(["strategy", "level"], sort=False):
        row = {"strategy": s, "level": lv, "questions": g["question_number"].nunique(), "gold_items": len(g),
               "reachable": int(g["reachable"].sum()),
               "reachable_by_split_parts_only": int(g["reachable_by_parts_only"].sum()),
               "reachable_partial_only": int((~g["reachable"] & g["reachable_partial"]).sum()),
               "unreachable": int((~g["reachable"]).sum()),
               "questions_with_reachable_gold": g.loc[g["reachable"], "question_number"].nunique(),
               "only_ambiguous_matches": int(g["only_ambiguous"].sum()),
               "main_and_annex_both_have_it": int(g["main_and_annex"].sum()),
               "annex_A_items": int(g["annex_A"].sum())}
        for reason, n in g.loc[~g["reachable"], "unreachable_reason"].value_counts().sort_index().items():
            row[f"unreachable:{reason}"] = int(n)
        rows.append(row)
    df = pd.DataFrame(rows).fillna(0)
    for c in df.columns:
        if c.startswith("unreachable:"):
            df[c] = df[c].astype(int)
    df["view"], df["cutoff"] = "oracle", "-"
    return order_rows(df, strategies).drop(columns=["view", "cutoff"])


# ================================================================================================
# Driver
# ================================================================================================

def run_evaluation(retrieval_dir: Path, cfg: EvalConfig, paths: Paths = Paths()) -> Path:
    """Run stage RE on a retrieval run and return the evaluation directory."""
    t0 = time.time()
    retrieval_dir = Path(retrieval_dir)
    if not (retrieval_dir / "manifest.json").exists():
        raise InputError(f"{rel(retrieval_dir)} is not a retrieval run (no manifest.json); run `rag.py retrieve`")
    rman = read_json(retrieval_dir / "manifest.json")
    chunks_sha = sha256_file(paths.chunks)
    if chunks_sha != rman["inputs"]["chunks"]["sha256"]:
        raise InputError(f"the rankings in {rel(retrieval_dir)} were made from another chunk file "
                         f"({rman['inputs']['chunks']['sha256'][:12]}… ≠ {chunks_sha[:12]}…); rerun `rag.py retrieve`")
    for s, out in rman["outputs"].items():
        if sha256_file(retrieval_dir / out["path"]) != out["sha256"]:
            raise InputError(f"{rel(retrieval_dir / out['path'])} changed after retrieval; rerun `rag.py retrieve`")
    sdefs = rman["strategies"]["strategies"]
    names = cfg.strategies or [s for s in rman["params"]["strategies"]]
    unknown = [n for n in names if n not in rman["outputs"]]
    if unknown:
        raise InputError(f"no rankings for {unknown} in {rel(retrieval_dir)} (have {', '.join(rman['outputs'])})")
    grouping = frozenset(rman["strategies"]["grouping_tipos"])

    chunks = load_chunks(paths.chunks)
    ds = load_dataset(paths.dataset)
    chapters = load_chapters(paths.chapters, ds.question_ids)
    file_to_doc = ds.file_to_document()
    main_file = {d: Path(f).name for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"]) if f}
    statutory = dict(zip(ds.documents["document_id"], ds.documents["statutory"].astype(bool)))
    matcher = Matcher(chunks, file_to_doc, main_file, grouping, cfg.annex_rule)
    gold = gold_items(ds)
    file_index = {f: i for i, f in enumerate(sorted(set(chunks["arquivo"])))}
    t_load = time.time()

    params = {**cfg.params(), "strategies": names}
    inputs = {"retrieval_manifest": {"path": rel(retrieval_dir / "manifest.json"), "config_hash": rman["config_hash"]},
              "chunks": {"path": rel(paths.chunks), "sha256": chunks_sha},
              **{Path(p).stem: {"path": p, "sha256": h} for p, h in ds.sha256.items()},
              "chapters": {"path": rel(paths.chapters), "sha256": sha256_file(paths.chapters)}}
    config_hash = sha256_json({"params": params, "inputs": inputs})
    out_dir = retrieval_dir / "eval" / cfg.resolved_eval_id
    prepare_run_dir(out_dir, config_hash, cfg.force)

    item_rows, ctx_rows = [], []
    for name in names:
        ts = time.time()
        rt = ranked_texts(load_rankings(retrieval_dir, name), chunks, file_index)
        in_strategy = member_mask(chunks, frozenset(sdefs[name]["tipos"]), sdefs[name].get("variantes", ["base"]))
        i_rows, c_rows = evaluate_strategy(name, in_strategy, rt, gold, matcher, statutory, cfg)
        item_rows += i_rows
        ctx_rows += c_rows
        log.info("%s: %d gold items scored in %.1fs", name, len(i_rows), time.time() - ts)
    items = pd.DataFrame(item_rows)
    ctx = pd.DataFrame(ctx_rows)
    t_score = time.time()

    pq = order_rows(per_question_table(items, ctx, cfg), names)
    group = ["strategy", "level", "view", "cutoff", "gold", "slice"]
    metrics_df = order_rows(aggregate(pq, group), names)
    chap = pq[(pq["gold"] == "all") & (pq["slice"] == "all")].assign(
        slice=lambda d: "chapter:" + d["question_number"].map(chapters))
    by_chapter = order_rows(aggregate(chap, group), names)
    comps = [compare(pq, a, b, cfg.n_resamples, cfg.seed) for a, b in cfg.comparisons if a in names and b in names]
    comparisons = pd.concat(comps, ignore_index=True) if comps else pd.DataFrame()
    reach = reachability(items, names)
    t_agg = time.time()

    items_out = order_rows(items.assign(view="oracle", cutoff="-"), names).drop(columns=["view", "cutoff"])
    write_csv(items_out.replace({INF: np.nan}), out_dir / "per_item.csv.gz")
    write_csv(pq, out_dir / "per_question.csv.gz")
    write_csv(metrics_df, out_dir / "metrics.csv")
    write_csv(by_chapter, out_dir / "metrics_by_chapter.csv.gz")
    write_csv(comparisons, out_dir / "comparisons.csv")
    write_csv(reach, out_dir / "reachability.csv")

    manifest = base_manifest("retrieval_evaluation")
    manifest.update({
        "config_hash": config_hash, "eval_id": cfg.resolved_eval_id, "params": params, "inputs": inputs,
        "retrieval": {"embedding": rman["embedding"], "retriever": rman["retriever"], "top_n": rman["params"]["top_n"]},
        "gold": {"questions_with_gold": {lv: sum(1 for q in gold if gold[q][lv]) for lv in LEVELS},
                 "gold_items": {lv: sum(len(gold[q][lv]) for q in gold) for lv in LEVELS},
                 "references": len(ds.references),
                 "references_not_in_corpus": sum(1 for r in ds.references if not r["document_id"])},
        "outputs": {f: {"sha256": sha256_file(out_dir / f)} for f in
                    ["metrics.csv", "metrics_by_chapter.csv.gz", "comparisons.csv", "reachability.csv",
                     "per_question.csv.gz", "per_item.csv.gz"]},
        "timings_s": {"load": round(t_load - t0, 2), "score": round(t_score - t_load, 2),
                      "aggregate": round(t_agg - t_score, 2), "total": round(time.time() - t0, 2)},
    })
    write_json(out_dir / "manifest.json", manifest)
    from .report import write_report   # local import: report depends on this module's outputs only
    write_report(out_dir, ds)
    return out_dir
