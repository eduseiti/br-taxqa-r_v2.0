#!/usr/bin/env python3
"""Build the data files of the results dashboard (docs/dashboard/index.html).

No LLM or API calls: it only reads result tables already on disk and writes JavaScript data files that the
static page loads with <script> tags (so the page also works from file://, where fetch() is blocked).

Inputs (all relative to the repo root):
- retrieval evaluations  runs/retrieval/<emb>/irpf/eval/either_containment_merge_skip/
- generator contexts      runs/contexts/<emb>/irpf/<context_id>/contexts.jsonl.gz
- answers                 runs/answers/<emb>/irpf/<prompt>/<llm>/<context_id>/answers.jsonl
- nugget scoring          nuggets/scoring/{tables,analysis,score,ctxsupport}/gold-v0-auto/gemini-3.8-flash/...
- gold nuggets            nuggets/gold/v0-auto/nuggets.jsonl
- dataset                 dataset/{questions,references}.jsonl, scripts/rag/data/pr_irpf_2024_chapters.csv
- chunk table             segmented/chunks_all.csv.gz (chunk → article, chunk counts per strategy)
- notes                   docs/*.md (embedded so the page can show them in place)

Outputs, under docs/dashboard/data/:
- core.js       summary tables (retrieval metrics and comparisons, nugget runs and comparisons, robustness);
- docs.js       the docs/*.md notes, for the in-page reader;
- questions.js  per question: text, gold answer, references, nuggets, judge labels of every run, retrieval
                ranks of every gold item (gitignored: per-question data, regenerated in about a minute);
- contexts.js   per question and context: the selected chunks (gitignored);
- answers/*.js  per run: the generated answers, loaded on demand (gitignored).

Run from the repo root:  .venv/bin/python scripts/report/build_dashboard_data.py
"""

from __future__ import annotations

import ast
import glob
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
from ragpipe import metrics as M  # noqa: E402
from ragpipe.strategies import member_mask  # noqa: E402

OUT = ROOT / "docs" / "dashboard" / "data"
EMBS = ["jua-4b-mixed", "gemini-emb-2"]
EVAL_ID = "either_containment_merge_skip"
STRATS = ["S1", "S2", "S3", "S2c", "S4"]
BUDGETS = [1000, 2000, 4000, 8000, 16000]
SET = "gold-v0-auto"
JUDGE = "gemini-3.8-flash"
TABLES = ROOT / "nuggets/scoring/tables" / SET / JUDGE / "all"
ANALYSIS = ROOT / "nuggets/scoring/analysis" / SET / JUDGE / "all"
LABEL_CODE = {"support": "S", "partial_support": "P", "not_support": "N", "contradicts": "C"}
CONTEXT_IDS = {  # contexts shown in the question explorer
    "jua-4b-mixed": ["S1_budget4000", "S2_budget4000", "S3_budget4000", "S2c_budget4000", "S4_budget4000",
                     "oracle_budget4000", "S1_budget2000", "S2_budget2000", "S1_budget8000", "S2_budget8000",
                     "oracle_budget16000"],
    "gemini-emb-2": ["S1_budget4000", "S2_budget4000"],
}


def jl(path: Path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def clean(v):
    """JSON-safe scalar (NaN/inf → None, numpy → python, floats rounded)."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(float(v), 5)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def records(df: pd.DataFrame) -> dict:
    """Column-oriented table: {"cols": [...], "rows": [[...], ...]} (compact)."""
    return {"cols": list(df.columns), "rows": [[clean(x) for x in r] for r in df.itertuples(index=False)]}


def write_js(path: Path, var: str, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"{var}={s};\n", encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.2f} MB")


def maybe_literal(x):
    return ast.literal_eval(x) if isinstance(x, str) else x


# ================================================================================================
# Retrieval
# ================================================================================================

def retrieval_tables() -> dict:
    out = {"metrics": [], "comparisons": [], "reachability": [], "manifest": {}}
    for emb in EMBS:
        d = ROOT / "runs/retrieval" / emb / "irpf/eval" / EVAL_ID
        m = pd.read_csv(d / "metrics.csv", dtype={"cutoff": str})
        m = m[m.slice.isin(["all", "statutory", "non_statutory", "explicit", "embedded", "annex_A",
                            "whole_article", "sub_article"])]
        m.insert(0, "embedding", emb)
        out["metrics"].append(m)
        c = pd.read_csv(d / "comparisons.csv", dtype={"cutoff": str})
        c.insert(0, "embedding", emb)
        out["comparisons"].append(c)
        r = pd.read_csv(d / "reachability.csv")
        r.insert(0, "embedding", emb)
        out["reachability"].append(r)
        man = json.loads((d / "manifest.json").read_text())
        out["manifest"][emb] = {"created_at": man["created_at"], "params": man["params"], "gold": man["gold"],
                                "retrieval": man["retrieval"], "commit": man["script"]["git"]["commit"]}
    metrics = pd.concat(out["metrics"], ignore_index=True)
    comps = pd.concat(out["comparisons"], ignore_index=True)
    comps["kind"] = "strategy"
    cross = cross_embedding_comparisons()
    return {"metrics": records(metrics), "comparisons": records(pd.concat([comps, cross], ignore_index=True)),
            "reachability": records(pd.concat(out["reachability"], ignore_index=True)),
            "manifest": out["manifest"]}


def cross_embedding_comparisons() -> pd.DataFrame:
    """Gemini − jua per strategy, paired over questions (rag.py compare works within one run only)."""
    pqs = {}
    for emb in EMBS:
        pq = pd.read_csv(ROOT / "runs/retrieval" / emb / "irpf/eval" / EVAL_ID / "per_question.csv.gz",
                         dtype={"question_number": str, "cutoff": str})
        pqs[emb] = pq[(pq.gold == "all") & (pq.slice == "all") & pq.view.isin(["budget", "unit", "raw"])]
    metrics = ["recall", "hit", "full_recall", "partial_recall", "mrr", "ndcg@10", "context_precision"]
    rows = []
    key = ["question_number", "strategy", "level", "view", "cutoff"]
    a = pqs["jua-4b-mixed"].set_index(key)[metrics]
    b = pqs["gemini-emb-2"].set_index(key)[metrics]
    j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
    for (s, lv, view, cut), g in j.groupby(level=["strategy", "level", "view", "cutoff"]):
        X, Y = g[[f"{m}_a" for m in metrics]].to_numpy(float), g[[f"{m}_b" for m in metrics]].to_numpy(float)
        ok = ~np.isnan(X) & ~np.isnan(Y)
        cols = [i for i in range(len(metrics)) if ok[:, i].any()]
        # one resampling for all metrics that share the same questions (the usual case), else per metric
        groups: dict[bytes, list[int]] = defaultdict(list)
        for i in cols:
            groups[ok[:, i].tobytes()].append(i)
        for _, idx in groups.items():
            rmask = ok[:, idx[0]]
            D = Y[rmask][:, idx] - X[rmask][:, idx]
            lo, hi = M.paired_bootstrap_ci(D, 10_000, 13)
            p = M.paired_permutation_p(D, 10_000, 13)
            for jj, i in enumerate(idx):
                d = D[:, jj]
                rows.append({"embedding": "gemini-emb-2 − jua-4b-mixed", "a": f"{s}@jua-4b-mixed",
                             "b": f"{s}@gemini-emb-2", "level": lv, "view": view, "cutoff": cut, "metric": metrics[i],
                             "mean_a": X[rmask, i].mean(), "mean_b": Y[rmask, i].mean(), "diff": d.mean(),
                             "ci_low": lo[jj], "ci_high": hi[jj], "p_permutation": p[jj], "n_questions": int(rmask.sum()),
                             "n_better": int((d > 1e-12).sum()), "n_worse": int((d < -1e-12).sum()),
                             "kind": "embedding"})
    return pd.DataFrame(rows)


# ================================================================================================
# Nuggets
# ================================================================================================

def nugget_tables() -> dict:
    def rd(p):
        return records(pd.read_csv(p))

    out = {"runs": rd(TABLES / "runs.csv"), "comparisons": rd(TABLES / "comparisons.csv"),
           "ctxsupport_runs": rd(TABLES / "ctxsupport_runs.csv")}
    for name in ["crossset_comparisons", "perturbation_s1_s2", "chapters_s1_s2", "judge_agreement_gemini-3.1-pro",
                 "judge_comparisons_gemini-3.1-pro", "slices_comparisons", "utilisation_runs", "linkage_runs",
                 "runs_by_pgd", "judge_confusion_gemini-3.1-pro"]:
        p = ANALYSIS / f"{name}.csv"
        if p.exists():
            df = pd.read_csv(p)
            if "runs_mean" in df.columns:
                df = df.drop(columns="runs_mean")
            out[name] = records(df)
    # other nugget sets (runs.csv of each)
    other = {}
    for s in ["gemini-3.1-pro.rep0", "qwen3.8-max.rep0"]:
        p = ROOT / "nuggets/scoring/tables" / s / JUDGE / "all/runs.csv"
        if p.exists():
            other[s] = records(pd.read_csv(p))
    out["other_sets_runs"] = other
    return out


def nugget_set_stats(nuggets: dict[str, list[dict]]) -> dict:
    allx = [n for v in nuggets.values() for n in v]
    per_q = [len(v) for v in nuggets.values()]
    cats = defaultdict(int)
    for n in allx:
        cats[n.get("category") or "?"] += 1
    return {"n_nuggets": len(allx), "n_vital": sum(n["importance"] == "vital" for n in allx),
            "n_questions": len(nuggets), "per_question_median": float(np.median(per_q)),
            "per_question_min": int(min(per_q)), "per_question_max": int(max(per_q)), "categories": dict(cats)}


# ================================================================================================
# Corpus / strategies
# ================================================================================================

def strategy_chunk_counts(chunks: pd.DataFrame, excluded_files: set[str]) -> list[dict]:
    import yaml
    sd = yaml.safe_load((ROOT / "scripts/rag/strategies.yaml").read_text())["strategies"]
    rows = []
    keep = ~chunks.arquivo.isin(excluded_files)
    for s, d in sd.items():
        tipos = set(d["tipos"])
        var = d.get("variantes", ["base"])
        sub = chunks[keep & member_mask(chunks, tipos, var)]
        by = sub.Tipo.value_counts().to_dict()
        rows.append({"strategy": s, "description": d["description"], "tipos": d["tipos"], "variantes": var,
                     "chunks": int(len(sub)), "by_tipo": {k: int(v) for k, v in by.items()},
                     "tokens_median": float(sub.n_tokens_qwen3.median()),
                     "tokens_mean": float(sub.n_tokens_qwen3.mean())})
    return rows


# ================================================================================================
# Per question
# ================================================================================================

def chapters_of(qids: list[str]) -> dict[str, str]:
    df = pd.read_csv(ROOT / "scripts/rag/data/pr_irpf_2024_chapters.csv", dtype=str)
    out = {}
    for q in qids:
        for r in df.itertuples():
            if r.first_question <= q <= r.last_question:
                out[q] = r.chapter
                break
    return out


def run_dirs() -> list[dict]:
    """Every scored run (score labels) with its answers folder."""
    out = []
    base = ROOT / "nuggets/scoring/score" / SET / JUDGE
    for lab in sorted(base.glob("*/irpf/*/*/*/labels.jsonl")):
        emb, _, prompt, llm, ctx = lab.parts[-6:-1]
        cid = ctx if emb == "jua-4b-mixed" else f"{ctx}@{emb}"
        out.append({"key": f"{llm}|{cid}", "llm": llm, "context_id": cid, "embedding": emb, "prompt": prompt,
                    "labels": lab, "answers": ROOT / "runs/answers" / emb / "irpf" / prompt / llm / ctx / "answers.jsonl"})
    return out


def ctx_dirs() -> list[dict]:
    out = []
    base = ROOT / "nuggets/scoring/ctxsupport" / SET / JUDGE
    for lab in sorted(base.glob("*/irpf/*/labels.jsonl")):
        emb, _, ctx = lab.parts[-4:-1]
        cid = ctx if emb == "jua-4b-mixed" else f"{ctx}@{emb}"
        out.append({"context_id": cid, "labels": lab})
    return out


def per_item_tables() -> dict:
    """question → level → {items: [...], stats: {emb|strategy: [[rank_full, rank_any, unit_pos, mask_full,
    mask_any, reachable], ...]}}"""
    out: dict = defaultdict(lambda: defaultdict(lambda: {"items": [], "idx": {}, "stats": {}}))
    for emb in EMBS:
        pi = pd.read_csv(ROOT / "runs/retrieval" / emb / "irpf/eval" / EVAL_ID / "per_item.csv.gz",
                         dtype={"question_number": str})
        for r in pi.itertuples(index=False):
            q, lv = r.question_number, r.level
            slot = out[q][lv]
            if r.item not in slot["idx"]:
                slot["idx"][r.item] = len(slot["items"])
                slot["items"].append({"key": r.item, "label": r.label, "statutory": bool(r.statutory),
                                      "sub_article": bool(r.sub_article), "origin": r.origin})
            i = slot["idx"][r.item]
            k = f"{emb}|{r.strategy}"
            st = slot["stats"].setdefault(k, [])
            while len(st) <= i:
                st.append(None)
            mf = sum(1 << j for j, b in enumerate(BUDGETS) if getattr(r, f"budget_full_{b}"))
            ma = sum(1 << j for j, b in enumerate(BUDGETS) if getattr(r, f"budget_any_{b}"))
            st[i] = [clean(r.rank_full), clean(r.rank_any), clean(r.unit_pos), mf, ma, int(bool(r.reachable)),
                     r.unreachable_reason if isinstance(r.unreachable_reason, str) else ""]
    for q in out:
        for lv in out[q]:
            out[q][lv].pop("idx")
    return out


def contexts_data(chunk_art: dict[str, tuple[str, str]], gold_art: dict[str, set], gold_doc: dict[str, set]) -> dict:
    """context key → question → [[n, rank, tipo, doc, label, tokens, hit]] (hit: A article / D document / ''), plus
    ``titles`` (document → title as written in the context header)."""
    out = {}
    meta = {}
    titles: dict[str, str] = {}
    for emb, cids in CONTEXT_IDS.items():
        for cid in cids:
            p = ROOT / "runs/contexts" / emb / "irpf" / cid / "contexts.jsonl.gz"
            if not p.exists():
                continue
            key = cid if emb == "jua-4b-mixed" else f"{cid}@{emb}"
            per_q = {}
            for ln in jl(p):
                q = ln["question_number"]
                items = maybe_literal(ln.get("items")) or []
                rows = []
                for it in items:
                    ids = [it["chunk_id"]] + list(it.get("alias_chunk_ids") or [])
                    hit = ""
                    for c in ids:
                        f, art = chunk_art.get(c, ("", ""))
                        if art and f"{it['document_id']}|{art}" in gold_art.get(q, ()):
                            hit = "A"
                            break
                    if not hit and it["document_id"] in gold_doc.get(q, ()):
                        hit = "D"
                    fonte = it.get("fonte") or ""
                    head, _, tail = fonte.rpartition(" — ")
                    if head and it.get("document_id") not in titles:
                        titles[it["document_id"]] = head
                    rows.append([it.get("n"), it.get("rank"), it.get("tipo"), it.get("document_id"),
                                 tail or it.get("citacao") or "", it.get("tokens_qwen3"), hit])
                per_q[q] = {"t": ln.get("context_tokens_qwen3"), "i": rows}
            out[key] = per_q
            meta[key] = {"embedding": emb, "context_id": cid, "path": str(p.relative_to(ROOT))}
    return {"meta": meta, "titles": titles, "data": out}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading dataset, nuggets, chunks …")
    questions = list(jl(ROOT / "dataset/questions.jsonl"))
    refs = list(jl(ROOT / "dataset/references.jsonl"))
    qids = [q["question_number"] for q in questions]
    chap = chapters_of(qids)
    nuggets: dict[str, list[dict]] = defaultdict(list)
    for n in jl(ROOT / "nuggets/gold/v0-auto/nuggets.jsonl"):
        nuggets[n["question_number"]].append(n)
    chunks = pd.read_csv(ROOT / "segmented/chunks_all.csv.gz",
                         usecols=["Tipo", "arquivo", "chunk_id", "artigo_id", "unidade_id", "parte", "variante",
                                  "n_tokens_qwen3"], dtype=str, keep_default_na=False)
    chunks["n_tokens_qwen3"] = pd.to_numeric(chunks.n_tokens_qwen3)
    chunk_art = dict(zip(chunks.chunk_id, zip(chunks.arquivo, chunks.artigo_id)))
    gold_art, gold_doc = defaultdict(set), defaultdict(set)
    for r in refs:
        if r["document_id"]:
            gold_doc[r["question_number"]].add(r["document_id"])
            for a in r["article_ids"]:
                gold_art[r["question_number"]].add(f"{r['document_id']}|{a}")

    print("core tables …")
    import yaml
    excl = yaml.safe_load((ROOT / "scripts/rag/corpus_exclusions.yaml").read_text())
    excl_docs = set((excl or {}).get("documents") or {})
    excl_files = {a for a in chunks.arquivo.unique() if a.split(".")[0] in excl_docs}
    runs = run_dirs()
    core = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "retrieval": retrieval_tables(),
        "nuggets": nugget_tables(),
        "nugget_set": nugget_set_stats(nuggets),
        "strategies": strategy_chunk_counts(chunks, excl_files),
        "excluded_documents": sorted(excl_docs),
        "runs_index": [{k: v for k, v in r.items() if k not in ("labels", "answers")} |
                       {"has_answers": r["answers"].exists()} for r in runs],
        "contexts_summary": {emb: records(pd.read_csv(ROOT / "runs/contexts" / emb / "irpf/summary.csv"))
                             for emb in EMBS if (ROOT / "runs/contexts" / emb / "irpf/summary.csv").exists()},
        "n_questions": len(qids),
    }
    write_js(OUT / "core.js", "window.DATA_CORE", core)

    print("docs …")
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "docs").glob("*.md"))}
    docs["scripts/nuggets/README.md"] = (ROOT / "scripts/nuggets/README.md").read_text(encoding="utf-8")
    docs["scripts/rag/README.md"] = (ROOT / "scripts/rag/README.md").read_text(encoding="utf-8")
    write_js(OUT / "docs.js", "window.DATA_DOCS", docs)

    print("per question …")
    items = per_item_tables()
    labels: dict[str, dict[str, str]] = defaultdict(dict)    # q → run key → label codes (nugget order)
    sources: dict[str, dict[str, str]] = defaultdict(dict)
    order = {q: [n["nugget_id"] for n in v] for q, v in nuggets.items()}

    def codes(x, q):
        lab = {y["nugget_id"]: LABEL_CODE[y["label"]] for y in x["labels"]}
        return "".join(lab.get(n, "-") for n in order[q])

    for r in runs:
        for x in jl(r["labels"]):
            q = x["question_number"]
            labels[q][r["key"]] = codes(x, q)
            if x["source"] != "judge":
                sources[q][r["key"]] = x["source"]
    ctx_labels: dict[str, dict[str, str]] = defaultdict(dict)
    for c in ctx_dirs():
        for x in jl(c["labels"]):
            ctx_labels[x["question_number"]][c["context_id"]] = codes(x, x["question_number"])
    refs_by_q = defaultdict(list)
    for r in refs:
        refs_by_q[r["question_number"]].append({
            "id": r["reference_id"], "origin": r["origin"], "title": r["cited_title"], "doc": r["document_id"],
            "citation": r["citation_text"], "articles": r["article_ids"],
            "provisions": [p["label"] for p in r["provisions"]]})
    qdata = {}
    for q in questions:
        n = q["question_number"]
        qdata[n] = {
            "summary": q["question_summary"], "text": q["question_text"], "answer": q["answer"],
            "chapter": chap.get(n, ""), "refs": refs_by_q.get(n, []),
            "nuggets": [[x["nugget_id"], x["text"], x["importance"], x.get("category") or ""] for x in nuggets.get(n, [])],
            "labels": labels.get(n, {}), "sources": sources.get(n, {}), "ctx_labels": ctx_labels.get(n, {}),
            "items": items.get(n, {}),
        }
    write_js(OUT / "questions.js", "window.DATA_Q", qdata)

    print("contexts …")
    write_js(OUT / "contexts.js", "window.DATA_CTX", contexts_data(chunk_art, gold_art, gold_doc))

    print("answers …")
    for r in runs:
        if not r["answers"].exists():
            continue
        a = {}
        for ln in jl(r["answers"]):
            a[ln["question_number"]] = [ln.get("status"), bool(ln.get("abstained")), ln.get("answer") or ""]
        fname = r["key"].replace("|", "__").replace("@", "_at_") + ".js"
        path = OUT / "answers" / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("(window.DATA_ANS=window.DATA_ANS||{})[" + json.dumps(r["key"]) + "]=" +
                        json.dumps(a, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("  answers/:", sum(p.stat().st_size for p in (OUT / "answers").glob("*.js")) / 1e6, "MB")


if __name__ == "__main__":
    main()
