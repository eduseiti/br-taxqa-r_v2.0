#!/usr/bin/env python3
"""Build the data of the corpus & question explorer (docs/explorer/index.html).

The explorer reuses the question-trace data (docs/dashboard/data/trace/, scripts/report/build_trace_data.py) for the
heavy parts: chunk texts per document, rankings, contexts, answers and judge labels. This script adds what the
trace does not have. No LLM or API calls; it reads local files only.

Outputs, under docs/explorer/data/:
- index.js     documents (type, files, chunk counts per strategy, the questions that cite them with the reference
               origin: explicit or embedded), questions (references by origin, per-question summary scores);
- q/<qid>.js   per question: the chunks of every strategy that match each gold item (document, article, provision;
               full and partial hits, the evaluation's own matcher), the per-question retrieval metrics of the 10
               strategy × embedding runs, the per-question nugget scores of every scored generation run.

Run from the repo root:  .venv/bin/python scripts/report/build_explorer_data.py [--questions 001,350]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "scripts" / "report"))
from ragpipe.data import load_chunks, load_dataset  # noqa: E402
from ragpipe.exclusions import Exclusions  # noqa: E402
from ragpipe.relevance import LEVELS, Matcher, gold_items  # noqa: E402
from ragpipe.strategies import member_mask  # noqa: E402
from build_dashboard_data import EVAL_ID, JUDGE, SET, chapters_of  # noqa: E402
from build_trace_data import EMBS, dumps, git_commit, num, write_js  # noqa: E402

OUT = ROOT / "docs" / "explorer" / "data"
TRACE_INDEX = ROOT / "docs" / "dashboard" / "data" / "trace" / "index.js"
BUDGETS = [1000, 2000, 4000, 8000, 16000]
UNIT_K = ["1", "3", "5", "10", "20", "50", "100"]
GEN_COLS = ["V_strict", "V", "W", "A_strict", "A", "n_support", "n_partial_support", "n_not_support", "n_contradicts"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", help="comma-separated question numbers (default: all)")
    a = ap.parse_args()
    t0 = time.time()
    if not TRACE_INDEX.exists():
        sys.exit(f"{TRACE_INDEX.relative_to(ROOT)} missing: build or download the trace data first")
    tix = json.loads(TRACE_INDEX.read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";"))
    trace_runs = {r["key"] for r in tix["runs"]}

    print("loading dataset, chunks …", flush=True)
    ds = load_dataset(ROOT / "dataset")
    chunks = load_chunks(ROOT / "segmented/chunks_all.csv.gz", with_text=False)
    file_to_doc = ds.file_to_document()
    docs_meta = {r["document_id"]: r for r in ds.documents.to_dict("records")}
    main_file = {d: Path(m["lexml_file"]).name for d, m in docs_meta.items() if m.get("lexml_file")}
    questions = ds.questions.to_dict("records")
    qids_all = [q["question_number"] for q in questions]
    qids = a.questions.split(",") if a.questions else qids_all
    chap = chapters_of(qids_all)
    gold = gold_items(ds)
    doc_of_row = np.array([file_to_doc.get(f) for f in chunks.arquivo], dtype=object)

    rman = json.loads((ROOT / "runs/retrieval/jua-4b-mixed/irpf/manifest.json").read_text())
    eman = json.loads((ROOT / f"runs/retrieval/jua-4b-mixed/irpf/eval/{EVAL_ID}/manifest.json").read_text())
    P = eman["params"]
    sdefs = rman["strategies"]["strategies"]
    strat_names = list(rman["params"]["strategies"])
    grouping = frozenset(rman["strategies"]["grouping_tipos"])
    excluded = Exclusions.from_manifest(rman)
    excl_rows = excluded.row_mask(chunks, file_to_doc)
    masks = {s: member_mask(chunks, frozenset(sdefs[s]["tipos"]), sdefs[s].get("variantes", ["base"])) for s in strat_names}
    matcher = Matcher(chunks, file_to_doc, main_file, grouping, P["annex_rule"])
    checks: dict = {"strategy_chunks": {s: int((m & ~excl_rows).sum()) for s, m in masks.items()}}
    if checks["strategy_chunks"] != tix["checks"]["strategy_chunks"]:
        sys.exit(f"strategy chunk counts differ from the trace data: {checks['strategy_chunks']} vs "
                 f"{tix['checks']['strategy_chunks']} — rebuild the trace data first")

    # ---------------------------------------------------------------- documents
    print("documents …", flush=True)
    refs_by_doc = defaultdict(list)
    refs_by_q = defaultdict(list)
    for r in ds.references:
        refs_by_q[r["question_number"]].append(r)
        if r["document_id"]:
            refs_by_doc[r["document_id"]].append(r)
    counts = defaultdict(lambda: {s: 0 for s in strat_names})
    tok_tot = defaultdict(lambda: {s: 0 for s in strat_names})
    n_art = Counter()
    files_of = defaultdict(set)
    for s, m in masks.items():
        rows = np.flatnonzero(m)
        for d, t in zip(doc_of_row[rows], chunks.n_tokens_qwen3.to_numpy()[rows]):
            if d:
                counts[d][s] += 1
                tok_tot[d][s] += int(t)
    for d, f, art in zip(doc_of_row, chunks.arquivo, chunks.artigo_id):
        if d:
            files_of[d].add(f)
    for d, arts in pd.Series(chunks.artigo_id.to_numpy()[masks["S1"]], index=doc_of_row[masks["S1"]]).groupby(level=0):
        n_art[d] = int(arts[arts != ""].nunique())
    doc_file = {d: tix["documents"][d][2] for d in docs_meta if d in tix["documents"]}
    docs_out = {}
    for d, m in sorted(docs_meta.items()):
        rr = refs_by_doc.get(d, [])
        docs_out[d] = {
            "title": m.get("title"), "statutory": bool(m.get("statutory")), "date": m.get("date"), "number": m.get("number"),
            "urn": m.get("urn"), "excluded": d in excluded, "file": doc_file.get(d), "n_files": len(files_of.get(d, ())),
            "n_articles": n_art.get(d, 0), "chunks": counts[d] if d in counts else {s: 0 for s in strat_names},
            "tokens": tok_tot[d] if d in tok_tot else {s: 0 for s in strat_names},
            # [question, reference id, origin, article ids, provision labels]
            "refs": [[r["question_number"], r["reference_id"], r["origin"], r["article_ids"],
                      [p["label"] for p in r["provisions"]]] for r in sorted(rr, key=lambda r: r["reference_id"])],
        }

    # ---------------------------------------------------------------- retrieval metrics per question
    print("retrieval metrics …", flush=True)
    ret = defaultdict(dict)        # q → run key → level → metrics
    for emb in EMBS:
        pq = pd.read_csv(ROOT / "runs/retrieval" / emb / "irpf/eval" / EVAL_ID / "per_question.csv.gz",
                         dtype={"question_number": str, "cutoff": str}, low_memory=False)
        pq = pq[(pq.gold == "all") & (pq.slice == "all")].rename(columns={"ndcg@10": "ndcg10"})
        pq["question_number"] = pq.question_number.str.zfill(3)
        for (q, s, lv), g in pq.groupby(["question_number", "strategy", "level"], sort=False):
            byv = {(r.view, r.cutoff): r for r in g.itertuples(index=False)}
            b = [byv.get(("budget", str(x))) for x in BUDGETS]
            u = [byv.get(("unit", k)) for k in UNIT_K]
            tot = byv.get(("unit", "-"))
            orc = byv.get(("oracle", "-"))
            ret[q].setdefault(f"{emb}|{s}", {})[lv] = {
                "n": num(g.n_gold.iat[0]),
                "b": [num(x.recall) if x is not None else None for x in b],
                "bf": [num(x.full_recall) if x is not None else None for x in b],
                "cp": [num(x.context_precision) if x is not None else None for x in b],
                "u": [num(x.recall) if x is not None else None for x in u],
                "mrr": num(tot.mrr) if tot is not None else None,
                "ndcg": num(tot.ndcg10) if tot is not None else None,
                "oracle": num(orc.recall) if orc is not None else None,
            }
    # ---------------------------------------------------------------- generation scores per question
    print("generation scores …", flush=True)
    gq = pd.read_csv(ROOT / "nuggets/scoring/tables" / SET / JUDGE / "all/per_question.csv.gz",
                     dtype={"question_number": str})
    gq["question_number"] = gq.question_number.str.zfill(3)
    gq["key"] = gq.llm + "|" + gq.context_id
    gq = gq[gq.key.isin(trace_runs)]
    gen = defaultdict(dict)
    for r in gq.itertuples(index=False):
        gen[r.question_number][r.key] = [r.source] + [num(getattr(r, c)) for c in GEN_COLS]
    checks["generation_runs"] = int(gq.key.nunique())

    # ---------------------------------------------------------------- per question
    print("questions …", flush=True)
    total = 0
    qset = set(qids)
    q_out = {}
    seg_stats = Counter()
    row_meta = {}

    def meta(i: int) -> list:
        if i not in row_meta:
            row_meta[i] = [doc_of_row[i], chunks.Tipo.iat[i], chunks.citacao.iat[i] or chunks.Rotulo.iat[i],
                           chunks.artigo_id.iat[i], int(chunks.n_tokens_qwen3.iat[i]), chunks.variante.iat[i],
                           int(chunks.parte.iat[i]), int(chunks.n_partes.iat[i]), chunks.arquivo.iat[i]]
        return row_meta[i]

    for q in questions:
        qn = q["question_number"]
        refs = refs_by_q.get(qn, [])
        rq = ret.get(qn, {})
        gg = gen.get(qn, {})
        vs = [v[1] for v in gg.values() if v[0] != "error" and v[1] is not None]
        art = rq.get("jua-4b-mixed|S2", {}).get("article", {})
        q_out[qn] = [q["question_summary"], chap.get(qn, ""), sum(r["origin"] == "explicit" for r in refs),
                     sum(r["origin"] == "embedded" for r in refs), len({r["document_id"] for r in refs if r["document_id"]}),
                     round(sum(vs) / len(vs), 4) if vs else None, art.get("b", [None] * 5)[2]]
        if qn not in qset:
            continue
        gq_ = gold.get(qn, {lv: [] for lv in LEVELS})
        segs = {}
        ch = {}
        for lv in LEVELS:
            lst = []
            for it in gq_[lv]:
                m = matcher.match(it)
                per = {}
                for s in strat_names:
                    inn = masks[s] & ~excl_rows
                    full = [int(i) for i in m.full if inn[i]]
                    part = [int(i) for i in m.partial if inn[i]]
                    if lv == "document":      # every chunk of the document: counts only, the corpus view lists them
                        per[s] = [len(full), 0, [], []]
                        continue
                    for i in full + part:
                        ch[chunks.chunk_id.iat[i]] = meta(i)
                    per[s] = [len(full), len(part), [chunks.chunk_id.iat[i] for i in full],
                              [chunks.chunk_id.iat[i] for i in part]]
                    seg_stats[f"{lv}:{'hit' if full or part else 'none'}"] += 1
                lst.append({"key": it.key_str, "label": it.label, "doc": it.document_id, "art": it.article_id,
                            "frag": it.fragment_id, "origin": it.origin, "seg": per,
                            "split_parts": len(m.parts) if lv == "provision" and m.parts else 0})
            segs[lv] = lst
        obj = {"n": qn, "segs": segs, "chunks": ch, "ret": rq, "gen": gg}
        total += write_js(OUT / "q" / f"{qn}.js", f"(window.EXP_Q=window.EXP_Q||{{}})[{dumps(qn)}]={dumps(obj)};\n")
    checks["gold_segments"] = dict(seg_stats)
    print(f"  q/: {total / 1e6:.1f} MB; gold segments: {dict(seg_stats)}", flush=True)

    index = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "commit": git_commit(),
        "trace_generated": tix["generated"], "trace_commit": tix["commit"],
        "strategies": strat_names, "budgets": BUDGETS, "unit_k": [int(k) for k in UNIT_K], "gen_cols": GEN_COLS,
        "documents": docs_out, "questions": q_out, "built_questions": sorted(qset),
        "eval_id": EVAL_ID, "judge": JUDGE, "nugget_set": SET, "checks": checks,
        "build_seconds": round(time.time() - t0, 1),
    }
    n = write_js(OUT / "index.js", f"window.EXP_INDEX={dumps(index)};\n")
    print(f"index.js {n / 1e6:.2f} MB; done in {time.time() - t0:.0f}s; checks: {json.dumps(checks)}")


if __name__ == "__main__":
    main()
