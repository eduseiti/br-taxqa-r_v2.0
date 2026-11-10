#!/usr/bin/env python3
"""Build the data of the dashboard's question-trace tab (docs/dashboard/index.html, tab 9).

Plan: docs/20261110_155548_question_trace_dashboard_feasibility_and_plan.md. No LLM or API calls: it reads the
local result files and writes JavaScript files that the static page loads on demand with <script> tags.

Outputs, under docs/dashboard/data/trace/ (gitignored, per-question data):
- index.js        question list, runs, contexts, prompt templates, documents, build checks;
- q/<qid>.js      one question through every stage: gold answer and nuggets (with the three nugget → document
                  signals), gold items, the rankings of the 10 strategy × embedding runs (top 100 + every row that
                  hits a gold article or provision) with gold and in-context marks, the generator contexts (items
                  and rendered text), the answers (claims, checks, prompt check) with the judge's labels;
- doc/<n>.js      one document: every chunk of every strategy, with its text and a strategy bitmask.

Checks run at build time (written to index.js and printed): first gold hits and budget hits recomputed with the
evaluation's own matcher equal per_item.csv.gz; the recomputed context selections equal the stored contexts;
every rebuilt prompt equals the request in the LLM cache (when the cache file is on this computer); label counts
per run equal runs.csv; strategy chunk counts.

Run from the repo root:  .venv/bin/python scripts/report/build_trace_data.py [--questions 001,028]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "scripts" / "report"))
from ragpipe.context import Cutoff, is_contained, select  # noqa: E402
from ragpipe.data import load_chunks, load_dataset  # noqa: E402
from ragpipe.evaluation import ranked_texts  # noqa: E402
from ragpipe.exclusions import Exclusions  # noqa: E402
from ragpipe.relevance import LEVELS, Matcher, gold_items  # noqa: E402
from ragpipe.retrieval import load_rankings  # noqa: E402
from ragpipe.strategies import member_mask  # noqa: E402
from build_dashboard_data import EVAL_ID, JUDGE, SET, chapters_of, jl  # noqa: E402

OUT = ROOT / "docs" / "dashboard" / "data" / "trace"
EMBS = ["jua-4b-mixed", "gemini-emb-2"]
TOP_K = 100
LABEL_CODE = {"support": "S", "partial_support": "P", "not_support": "N", "contradicts": "C"}
OTHER_FAMILIES = ["gemini-3.1-pro.rep0", "qwen3.8-max.rep0"]
ALIGNED = "gpt-6.1-sol.rep0"
MATCH_REL = {"same", "a_broader", "b_broader", "overlap"}
USER_MARK = "\n<<<USER>>>\n"


def ckey(emb: str, cid: str) -> str:
    return cid if emb == "jua-4b-mixed" else f"{cid}@{emb}"


def write_js(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def num(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return int(f) if f.is_integer() else round(f, 6)
    return v


# ================================================================================================
# Nugget → document signals (plan §3.1)
# ================================================================================================

STOP = set("""a o e é de da do das dos em no na nos nas um uma uns umas para por pelo pela pelos pelas com sem que se
ao aos à às ou como mais menos sua seu suas seus sobre entre até desde quando qual quais cujo cuja este esta esse essa
isso isto aquele aquela ser são foi for sido ter tem têm há não nº art arts lei inciso alínea parágrafo caput""".split())


def norm_tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2 and t not in STOP]


class BM25:
    """Okapi BM25 (k1 1.2, b 0.75) over the S1 texts of the whole corpus, so the idf is stable."""

    def __init__(self, docs: list[list[str]]):
        self.N = len(docs)
        self.avg = sum(map(len, docs)) / max(1, self.N)
        df = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def score(self, q: list[str], d: list[str], k1=1.2, b=0.75) -> float:
        tf = Counter(d)
        L = len(d)
        s = 0.0
        for t in set(q):
            f = tf.get(t)
            if f:
                s += self.idf.get(t, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * L / self.avg))
        return s


DOC_TYPES = [  # (regex on the citation, prefixes of document_id)
    (r"lei\s+complementar", ["lei_comp_", "lcp_"]),
    (r"decreto-lei", ["decreto_lei_", "del_"]),
    (r"decreto", ["decreto_"]),
    (r"instru[cç][aã]o\s+normativa(?:\s+conjunta)?|\bIN\b", ["in_"]),
    (r"medida\s+provis[oó]ria|\bMP\b", ["mp_"]),
    (r"ato\s+declarat[oó]rio\s+interpretativo|\bADI\b", ["adi_"]),
    (r"ato\s+declarat[oó]rio|\bADE?\b", ["ade_", "ad_", "adi_"]),
    (r"parecer", ["parecer", "pn_"]),
    (r"portaria", ["portaria_"]),
    (r"resolu[cç][aã]o", ["resolucao_"]),
    (r"constitui[cç][aã]o", ["constitui"]),
    (r"\blei\b", ["lei_"]),
]
ART_RX = re.compile(r"\barts?\.\s*(\d+[ºo°]?(?:-[A-Z])?(?:\s*(?:,|e|a)\s*\d+[ºo°]?(?:-[A-Z])?)*)")


def _art_id(tok: str) -> str:
    m = re.fullmatch(r"(\d+)[ºo°]?(?:-([A-Z]))?", tok.strip())
    if not m:
        return ""
    return f"art{m.group(1)}" + (f"-{ord(m.group(2)) - 64}" if m.group(2) else "")


def parse_legal_basis(s: str) -> tuple[list[str], str | None, str | None, str | None]:
    """(article ids, document type regex, document number) from a citation such as
    'arts. 10 a 13 da Lei nº 14.754, de 2023' or 'Lei nº 9.250, de 1995, art. 8º, inciso II'. 'art. 12-A' → art12-1
    (the LexML id)."""
    t = " ".join(s.split())
    arts: list[str] = []
    for m in ART_RX.finditer(t):
        body = m.group(1)
        for x, y in re.findall(r"(\d+)[ºo°]?\s*a\s*(\d+)", body):
            if 0 <= int(y) - int(x) <= 60:
                arts += [f"art{i}" for i in range(int(x), int(y) + 1)]
        body = re.sub(r"(\d+)[ºo°]?\s*a\s*(\d+)", "", body)
        arts += [a for a in (_art_id(x) for x in re.split(r"\s*(?:,|\be\b)\s*", body)) if a]
    rest = ART_RX.sub(" ", t)
    rest = re.sub(r"§+\s*\d+[ºo°]?|inciso\s+[IVXLC]+|al[ií]nea\s+\S+|item\s+\d+", " ", rest)
    dtype, number, year = None, None, None
    for rx, _ in DOC_TYPES:
        dm = re.search("(?:" + rx + r")[^\d]{0,60}?(?P<num>\d[\d.]*(?:-\d+)?)", rest, re.I)
        if dm:
            dtype, number = rx, dm.group("num").replace(".", "").strip()
            ym = re.match(r"\s*(?:,\s*)?(?:de\s+(?:\d+º?\s+de\s+\w+\s+de\s+)?(\d{4})|/(\d{2,4}))", rest[dm.end():])
            if ym:
                y = ym.group(1) or ym.group(2)
                year = y if len(y) == 4 else ("20" + y if int(y) < 50 else "19" + y)
            break
    if number is None and re.search(r"constitui[cç][aã]o", rest, re.I):
        dtype, number = r"constitui[cç][aã]o", "1988"
    if number is None:
        dm = re.search(r"n[ºo°]\s*(?P<num>\d[\d.]*(?:-\d+)?)", rest)
        number = dm.group("num").replace(".", "") if dm else None
    seen = set()
    arts = [a for a in arts if not (a in seen or seen.add(a))]
    return arts, dtype, number, year


def resolve_legal_basis(s: str, refs_docs: list[str], docs_meta: dict, articles_of_doc: dict) -> dict:
    arts, dtype, number, year = parse_legal_basis(s)
    out = {"s": s, "arts": arts, "doc": None, "in_refs": False, "status": "unresolved"}
    if not number:
        out["status"] = "no document number"
        return out
    prefixes = next((p for rx, p in DOC_TYPES if rx == dtype), [])

    def ok(d):
        meta = docs_meta[d]
        n = str(meta.get("number") or "").replace(".", "")
        if year and str(meta.get("date") or "")[:4] not in ("", year):
            return False
        return n == number and (not prefixes or any(d.startswith(p) for p in prefixes))
    cands = [d for d in refs_docs if ok(d)]
    in_refs = bool(cands)
    if not cands and prefixes:      # outside the question's references only when the type is known
        cands = [d for d in docs_meta if ok(d)]
    if not cands:
        out["status"] = "document not in corpus"
        return out
    d = cands[0]
    out.update(doc=d, in_refs=in_refs)
    have = articles_of_doc.get(d, set())
    out["arts_found"] = [a for a in arts if a in have]
    out["status"] = "resolved" if (not arts or out["arts_found"]) else "article not found"
    return out


# ================================================================================================
# main
# ================================================================================================

def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", help="comma-separated question numbers (default: all)")
    ap.add_argument("--no-docs", action="store_true", help="skip the document files")
    a = ap.parse_args()
    t0 = time.time()
    checks: dict = {}

    print("loading dataset, chunks …", flush=True)
    ds = load_dataset(ROOT / "dataset")
    chunks = load_chunks(ROOT / "segmented/chunks_all.csv.gz", with_text=True)
    extra = pd.read_csv(ROOT / "segmented/chunks_all.csv.gz", dtype=str, keep_default_na=False,
                        usecols=["chunk_id", "nivel", "agrupadores_rotulos"])
    chunks = chunks.merge(extra, on="chunk_id", how="left")
    row_of = {c: i for i, c in enumerate(chunks.chunk_id)}
    file_to_doc = ds.file_to_document()
    docs_meta = {r["document_id"]: r for r in ds.documents.to_dict("records")}
    main_file = {d: Path(m["lexml_file"]).name for d, m in docs_meta.items() if m.get("lexml_file")}
    questions = ds.questions.to_dict("records")
    qids_all = [q["question_number"] for q in questions]
    qids = a.questions.split(",") if a.questions else qids_all
    chap = chapters_of(qids_all)
    gold = gold_items(ds)
    refs_by_q = defaultdict(list)
    for r in ds.references:
        refs_by_q[r["question_number"]].append(r)
    doc_of_row = np.array([file_to_doc.get(f) for f in chunks.arquivo], dtype=object)
    articles_of_doc: dict[str, set] = defaultdict(set)
    for d, art in zip(doc_of_row, chunks.artigo_id):
        if d and art:
            articles_of_doc[d].add(art)

    # strategies, exclusions, matcher (as the evaluation)
    rman = json.loads((ROOT / "runs/retrieval/jua-4b-mixed/irpf/manifest.json").read_text())
    eman = json.loads((ROOT / f"runs/retrieval/jua-4b-mixed/irpf/eval/{EVAL_ID}/manifest.json").read_text())
    P = eman["params"]
    sdefs = rman["strategies"]["strategies"]
    strat_names = list(rman["params"]["strategies"])
    grouping = frozenset(rman["strategies"]["grouping_tipos"])
    excluded = Exclusions.from_manifest(rman)
    excl_rows = excluded.row_mask(chunks, file_to_doc)
    masks = {s: member_mask(chunks, frozenset(sdefs[s]["tipos"]), sdefs[s].get("variantes", ["base"])) for s in strat_names}
    checks["strategy_chunks"] = {s: int((m & ~excl_rows).sum()) for s, m in masks.items()}
    print("  strategy chunks:", checks["strategy_chunks"], flush=True)
    matcher = Matcher(chunks, file_to_doc, main_file, grouping, P["annex_rule"])
    file_index = {f: i for i, f in enumerate(sorted(set(chunks.arquivo)))}
    budgets = P["budgets"]

    # ---------------------------------------------------------------- nuggets
    print("nuggets …", flush=True)
    nuggets = defaultdict(list)
    for n in jl(ROOT / "nuggets/gold/v0-auto/nuggets.jsonl"):
        nuggets[n["question_number"]].append(n)
    rep0 = {n["nugget_id"]: n for n in jl(ROOT / f"nuggets/full/create/{ALIGNED}/nuggets.jsonl")}
    other_nugs = {f: {n["nugget_id"]: n for n in jl(ROOT / f"nuggets/full/create/{f}/nuggets.jsonl")} for f in OTHER_FAMILIES}
    align = {f: {r["a"]: r for r in jl(ROOT / f"nuggets/full/align/{ALIGNED}__{f}/alignment.jsonl")} for f in OTHER_FAMILIES}

    # BM25 over S1 texts (idf over the whole S1 index, excluded documents included)
    s1_rows = np.flatnonzero(masks["S1"])
    toks_of_row = {int(i): norm_tokens(chunks.Texto.iat[i]) for i in s1_rows}
    bm = BM25(list(toks_of_row.values()))
    s1_rows_by_doc = defaultdict(list)
    for i in s1_rows:
        if doc_of_row[i]:
            s1_rows_by_doc[doc_of_row[i]].append(int(i))

    # ---------------------------------------------------------------- runs, contexts, labels
    def run_list():
        out = []
        base = ROOT / "nuggets/scoring/score" / SET / JUDGE
        for lab in sorted(base.glob("*/irpf/*/*/*/labels.jsonl")):
            emb, _, prompt, llm, ctx = lab.parts[-6:-1]
            ans = ROOT / "runs/answers" / emb / "irpf" / prompt / llm / ctx / "answers.jsonl"
            if not ans.exists():
                continue
            n = sum(1 for _ in open(ans, encoding="utf-8"))
            if n <= 30:      # pilot-only runs (decision D2)
                continue
            out.append({"key": f"{llm}|{ckey(emb, ctx)}", "llm": llm, "context_id": ckey(emb, ctx), "embedding": emb,
                        "prompt": prompt, "labels": lab, "answers": ans, "ctx": ctx})
        return out
    runs = run_list()
    print(f"  {len(runs)} runs", flush=True)
    templates = {}
    for r in runs:
        rj = json.loads((r["answers"].parent / "run.json").read_text())
        pth = ROOT / rj["prompt"]["path"]
        txt = pth.read_text(encoding="utf-8")
        assert txt.count(USER_MARK) == 1, pth
        sysp, usr = txt.split(USER_MARK)
        sha = hashlib.sha256(pth.read_bytes()).hexdigest()
        templates[rj["prompt"]["name"]] = {"system": sysp.strip(), "user": usr.strip(), "path": rj["prompt"]["path"],
                                          "sha256": sha, "sha256_run": rj["prompt"].get("sha256")}
        r["template"] = rj["prompt"]["name"]
    checks["templates_unchanged"] = {k: v["sha256"] == v["sha256_run"] for k, v in templates.items()}

    contexts = []
    for emb in EMBS:
        for p in sorted((ROOT / "runs/contexts" / emb / "irpf").glob("*/contexts.jsonl.gz")):
            cid = p.parent.name
            m = re.fullmatch(r"(S1|S2|S3|S2c|S4)_budget(\d+)", cid)
            contexts.append({"key": ckey(emb, cid), "embedding": emb, "context_id": cid, "path": p,
                             "strategy": m.group(1) if m else None, "budget": int(m.group(2)) if m else None})
    ctx_data: dict[str, dict] = {}
    for c in contexts:
        ctx_data[c["key"]] = {ln["question_number"]: ln for ln in jl(c["path"])}
    ctxsup: dict[str, dict] = defaultdict(dict)       # q → ctx key → labels
    for lab in sorted((ROOT / "nuggets/scoring/ctxsupport" / SET / JUDGE).glob("*/irpf/*/labels.jsonl")):
        emb, _, ctx = lab.parts[-4:-1]
        for x in jl(lab):
            ctxsup[x["question_number"]][ckey(emb, ctx)] = {y["nugget_id"]: y for y in x["labels"]}
    print(f"  {len(contexts)} contexts", flush=True)

    # values and citations per answer (analysis tables)
    an = ROOT / "nuggets/scoring/analysis" / SET / JUDGE / "all"
    vals = pd.read_csv(an / "values_per_nugget.csv.gz", dtype={"question_number": str}, keep_default_na=False)
    vals_by = {(r.run_id, r.nugget_id): [r.kinds, r.value_hit, r.conflict, r.temporal_substitution]
               for r in vals.itertuples(index=False)}
    cits = pd.read_csv(an / "citations_per_answer.csv.gz", dtype={"question_number": str})
    cits_by = defaultdict(list)
    for r in cits.itertuples(index=False):
        cits_by[(r.run_id, r.question_number)].append([r.level, num(r.n_gold), num(r.n_cited), num(r.cited_recall),
                                                       num(r.cited_precision), num(r.context_recall)])
    runs_csv = pd.read_csv(ROOT / "nuggets/scoring/tables" / SET / JUDGE / "all/runs.csv")

    # ---------------------------------------------------------------- retrieval runs
    print("rankings …", flush=True)
    rets = {}
    per_item_check = Counter()
    sel_check = Counter()
    for emb in EMBS:
        rdir = ROOT / "runs/retrieval" / emb / "irpf"
        pi = pd.read_csv(rdir / "eval" / EVAL_ID / "per_item.csv.gz", dtype={"question_number": str})
        pi_idx = {(r.question_number, r.strategy, r.level, r.item): r for r in pi.itertuples(index=False)}
        for s in strat_names:
            ts = time.time()
            rk = load_rankings(rdir, s)
            rt = ranked_texts(rk, chunks, file_index)
            in_s = masks[s] & ~excl_rows
            score_of = dict(zip(zip(rk.question_number, rk["rank"]), rk.score))
            out = {}
            for q in qids:
                ranked = rt.per_question.get(q, np.empty(0, dtype=np.int64))
                pos_of = {int(t): i for i, t in enumerate(ranked)}
                sels = {b: select(ranked, rt.tokens, rt.intervals, Cutoff("budget", b), P["dedup"], P["overflow"])
                        for b in budgets}
                hits = {}       # level → list per item of (full positions set, any positions set)
                gq = gold.get(q, {lv: [] for lv in LEVELS})
                for lv in LEVELS:
                    lst = []
                    for it in gq[lv]:
                        m = matcher.match(it)
                        fr = m.full[in_s[m.full]]
                        pr = m.partial[in_s[m.partial]]
                        ft = {int(x) for x in rt.local_of_row[fr] if x >= 0}
                        at = ft | {int(x) for x in rt.local_of_row[pr] if x >= 0}
                        fpos = sorted(pos_of[t] for t in ft if t in pos_of)
                        apos = sorted(pos_of[t] for t in at if t in pos_of)
                        cover = [rt.local_of_row[p] for p in m.parts if in_s[p].all()]
                        rank_cover = math.inf
                        for cs in cover:
                            rank_cover = min(rank_cover, max((pos_of.get(int(t), math.inf) + 1) for t in cs))
                        rf = min(fpos[0] + 1 if fpos else math.inf, rank_cover)
                        ra = apos[0] + 1 if apos else math.inf
                        # check against the evaluation
                        ref = pi_idx.get((q, s, lv, it.key_str))
                        if ref is not None:
                            ef = ref.rank_full if not pd.isna(ref.rank_full) else math.inf
                            ea = ref.rank_any if not pd.isna(ref.rank_any) else math.inf
                            per_item_check["rank_ok" if (ef == rf and ea == ra) else "rank_diff"] += 1
                            for b in budgets:
                                sel = sels[b]
                                anyb = bool(set(sel) & set(apos))
                                per_item_check["budget_ok" if anyb == bool(getattr(ref, f"budget_any_{b}")) else "budget_diff"] += 1
                        else:
                            per_item_check["item_missing"] += 1
                        lst.append((set(fpos), set(apos), None if rf == math.inf else int(rf),
                                    None if ra == math.inf else int(ra)))
                    hits[lv] = lst
                # rows to show
                show = set(range(min(TOP_K, len(ranked))))
                for lv in ("article", "provision"):
                    for fp, ap, _, _ in hits[lv]:
                        show |= ap
                # in-context marks per budget: n (1-based position in context), -n (inside item n), 0
                ctx_pos = {b: {p: j + 1 for j, p in enumerate(sel)} for b, sel in sels.items()}
                sel_spans = {b: _span([iv for sp in sel for iv in rt.intervals[int(ranked[sp])]]) for b, sel in sels.items()}
                rows = []
                for p in sorted(show):
                    t = int(ranked[p])
                    rep_row = rt.members[t][0]
                    marks = []
                    for b in budgets:
                        n = ctx_pos[b].get(p)
                        if n:
                            marks.append(n)
                            continue
                        sel = sels[b]
                        inside = 0
                        if not is_contained(rt.intervals[t], sel_spans[b]):
                            marks.append(0)
                            continue
                        for j, sp in enumerate(sel):
                            if is_contained(rt.intervals[t], _span(rt.intervals[int(ranked[sp])])):
                                inside = -(j + 1)
                                break
                        marks.append(inside)
                    rows.append([p + 1, chunks.chunk_id.iat[rep_row], num(score_of.get((q, p + 1))),
                                 len(rt.members[t]) - 1, int(rt.tokens[t]),
                                 [i for i, h in enumerate(hits["document"]) if p in h[1]],
                                 [i for i, h in enumerate(hits["article"]) if p in h[1]],
                                 [i for i, h in enumerate(hits["provision"]) if p in h[0]],
                                 [i for i, h in enumerate(hits["provision"]) if p in h[1] and p not in h[0]],
                                 marks])
                firsts = {lv: [[h[2], h[3]] for h in hits[lv]] for lv in LEVELS}
                ctx_tokens = {b: int(sum(rt.tokens[ranked[sel]])) if sel else 0 for b, sel in sels.items()}
                out[q] = {"rows": rows, "firsts": firsts, "n": int(len(ranked)), "ctx_tokens": ctx_tokens,
                          "ctx_n": {b: len(sel) for b, sel in sels.items()}}
                # selection vs stored context
                for b in budgets:
                    stored = ctx_data.get(ckey(emb, f"{s}_budget{b}"), {}).get(q)
                    if stored is None:
                        continue
                    mine = [int(ranked[i]) for i in sels[b]]
                    theirs = [rt.local_of_row[row_of[it["chunk_id"]]] for it in stored["items"]]
                    sel_check["ok" if mine == [int(x) for x in theirs] else "diff"] += 1
            rets[f"{emb}|{s}"] = out
            print(f"  {emb} {s}: {time.time() - ts:.1f}s", flush=True)
    checks["per_item"] = dict(per_item_check)
    checks["context_selection"] = dict(sel_check)
    print("  per_item check:", dict(per_item_check), " selection vs stored contexts:", dict(sel_check), flush=True)

    # ---------------------------------------------------------------- answers + prompt check
    print("answers …", flush=True)
    answers: dict[str, dict] = {}
    labels: dict[str, dict] = {}
    prompt_check = Counter()
    label_count_check = Counter()
    qset = set(qids)
    qtext = {q["question_number"]: q["question_text"] for q in questions}
    cache_dir = ROOT / "runs/answers/cache"
    for r in runs:
        tmpl = templates[r["template"]]
        rows = {}
        for ln in jl(r["answers"]):
            q = ln["question_number"]
            if q not in qset:
                continue
            ctxline = ctx_data.get(r["context_id"], {}).get(q) if r["ctx"] != "closed_book" else None
            ver = 0          # 1 verified, 0 not verifiable, -1 differs
            if ln.get("status") in ("ok", "error") and ln.get("cache_key"):
                cp = cache_dir / f"{ln['cache_key']}.json"
                if cp.exists() and (ctxline is not None or r["ctx"] == "closed_book"):
                    req = json.loads(cp.read_text(encoding="utf-8"))["request"]
                    user = tmpl["user"].replace("{context}", ctxline["context"] if ctxline else "").replace("{question}", qtext[q])
                    ver = 1 if (req["system"].strip() == tmpl["system"] and req["user"].strip() == user.strip()) else -1
            prompt_check[{1: "verified", 0: "not_verifiable", -1: "differs"}[ver] +
                         ("" if ln.get("status") == "ok" else f"_{ln.get('status')}")] += 1
            claims = ln.get("claims") or []
            rows[q] = {"st": ln.get("status"), "ab": bool(ln.get("abstained")),
                       "cl": [[c["texto"], [[f.get("documento"), f.get("trecho"), f.get("status")] for f in c.get("fundamentos") or []]]
                              for c in claims],
                       "tx": "" if claims else (ln.get("answer") or ""),
                       "ck": ln.get("checks") or {}, "cited": ln.get("cited_chunk_ids") or [],
                       "pv": ver, "ck_key": (ln.get("cache_key") or "")[:12]}
        answers[r["key"]] = rows
        lab = {}
        for x in jl(r["labels"]):
            lab[x["question_number"]] = x
        labels[r["key"]] = lab
        n_csv = runs_csv[(runs_csv.llm == r["llm"]) & (runs_csv.context_id == r["context_id"])]
        if len(n_csv) and not a.questions:
            label_count_check["ok" if int(n_csv.n.iloc[0]) == len(lab) else f"diff:{r['key']}"] += 1
    checks["prompt"] = dict(prompt_check)
    checks["label_counts"] = dict(label_count_check)
    print("  prompt check:", dict(prompt_check), " label counts:", dict(label_count_check), flush=True)

    # ---------------------------------------------------------------- documents
    doc_ids = sorted(docs_meta)
    doc_file = {d: f"d{i:03d}" for i, d in enumerate(doc_ids)}
    strat_bit = {s: 1 << i for i, s in enumerate(strat_names)}
    bits = np.zeros(len(chunks), dtype=np.int64)
    for s, m in masks.items():
        bits |= np.where(m, strat_bit[s], 0)
    if not a.no_docs:
        print("documents …", flush=True)
        total = 0
        order = chunks.assign(xdoc=doc_of_row, xbits=bits)
        order = order[order.xdoc.notna()].sort_values(["xdoc", "arquivo", "Num_Inicio", "Num_Final"],
                                                      ascending=[True, True, True, False])
        for d, g in order.groupby("xdoc", sort=False):
            meta = docs_meta[d]
            files = []
            for f, gf in g.groupby("arquivo", sort=False):
                files.append({"arquivo": f, "categoria": gf.categoria.iat[0], "annex": f != main_file.get(d)})
            rows = [[r.chunk_id, r.arquivo, r.Tipo, r.citacao or r.Rotulo, r.artigo_id, r.nivel, int(r.Num_Inicio),
                     int(r.Num_Final), int(r.n_tokens_qwen3), r.variante, int(r.parte), int(r.n_partes),
                     int(r.xbits), r.agrupadores_rotulos, r.Texto]
                    for r in g.itertuples(index=False)]
            obj = {"id": d, "title": meta.get("title"), "urn": meta.get("urn"), "statutory": bool(meta.get("statutory")),
                   "excluded": d in excluded, "original": meta.get("original_file"), "lexml": meta.get("lexml_file"),
                   "files": files, "chunks": rows}
            total += write_js(OUT / "doc" / f"{doc_file[d]}.js",
                              f"(window.TRACE_DOC=window.TRACE_DOC||{{}})[{dumps(d)}]={dumps(obj)};\n")
        print(f"  doc/: {total / 1e6:.1f} MB", flush=True)

    # ---------------------------------------------------------------- per question
    print("questions …", flush=True)
    total = 0
    lb_stats = Counter()
    index_q = {}
    for q in questions:
        qn = q["question_number"]
        refs = refs_by_q.get(qn, [])
        ref_docs = sorted({r["document_id"] for r in refs if r["document_id"]})
        gq = gold.get(qn, {lv: [] for lv in LEVELS})
        gold_art_keys = {(it.document_id, it.article_id) for it in gq["article"]}
        nl = nuggets.get(qn, [])
        index_q[qn] = [q["question_summary"], q["question_text"], chap.get(qn, ""), len(refs), len(nl),
                       sum(n["importance"] == "vital" for n in nl)]
        if qn not in qset:
            continue
        # BM25 candidates: S1 texts of the gold articles; whole S1 texts of gold documents cited without articles
        cand = []
        for d in ref_docs:
            arts = {a_ for (dd, a_) in gold_art_keys if dd == d}
            for i in s1_rows_by_doc.get(d, []):
                art = chunks.artigo_id.iat[i]
                if arts and art not in arts:
                    continue
                cand.append(i)
        cand = cand[:4000]
        nug_out = []
        for n in nl:
            lbs = [resolve_legal_basis(s, ref_docs, docs_meta, articles_of_doc) for s in n.get("legal_basis") or []]
            for x in lbs:
                lb_stats[x["status"] + (" (in refs)" if x.get("in_refs") else "")] += 1
            qt = norm_tokens(n["text"])
            sc = sorted(((bm.score(qt, toks_of_row[i]), i) for i in cand), reverse=True)[:3]
            bm_top = [[chunks.chunk_id.iat[i], doc_of_row[i], chunks.artigo_id.iat[i], round(s_, 2),
                       (doc_of_row[i], chunks.artigo_id.iat[i]) in gold_art_keys] for s_, i in sc if s_ > 0]
            other = {}
            src = n.get("source_nugget_id") or n["nugget_id"]
            if n.get("stability") is not None and src in rep0:
                for f in OTHER_FAMILIES:
                    al = align[f].get(src)
                    if al:
                        other[f] = [al["relation"], [other_nugs[f].get(b, {}).get("importance") for b in al.get("b") or []]]
            nug_out.append({"id": n["nugget_id"], "text": n["text"], "imp": n["importance"], "cat": n.get("category"),
                            "span": n.get("source_span"), "span_match": n.get("span_match"), "lb": lbs, "bm25": bm_top,
                            "stab": n.get("stability"), "other": other,
                            "audit": {k: v.get("failed") for k, v in (n.get("audit") or {}).items()},
                            "values": [v.get("raw") for v in n.get("values") or []], "flags": n.get("flags") or {}})
        nids = [n["nugget_id"] for n in nl]
        ret = {k: v[qn] for k, v in rets.items() if qn in v}
        used_chunks = set()
        for v in ret.values():
            used_chunks.update(r_[1] for r_ in v["rows"])
        ctxs = {}
        for c in contexts:
            ln = ctx_data[c["key"]].get(qn)
            if not ln:
                continue
            items = []
            for it in ln["items"]:
                used_chunks.add(it["chunk_id"])
                items.append([it.get("n"), it.get("rank"), it["chunk_id"], it.get("alias_chunk_ids") or [],
                              it.get("tokens_qwen3"), it.get("tipo"), it.get("document_id"), it.get("fonte")])
            ctxs[c["key"]] = {"kind": ln.get("kind"), "items": items, "tokens": ln.get("context_tokens_qwen3"),
                              "rendered_tokens": ln.get("rendered_tokens_qwen3"), "gold": ln.get("gold"),
                              "text": ln.get("context") or ""}
        for v in answers.values():
            x = v.get(qn)
            if x:
                used_chunks.update(x["cited"])
        for n in nug_out:
            used_chunks.update(b[0] for b in n["bm25"])
        ch = {}
        for cid in used_chunks:
            i = row_of.get(cid)
            if i is None:
                continue
            ch[cid] = [doc_of_row[i], chunks.arquivo.iat[i], chunks.Tipo.iat[i], chunks.citacao.iat[i] or chunks.Rotulo.iat[i],
                       chunks.artigo_id.iat[i], int(chunks.n_tokens_qwen3.iat[i]), chunks.variante.iat[i]]
        ans = {}
        for r in runs:
            x = answers[r["key"]].get(qn)
            lab = labels[r["key"]].get(qn)
            if not x and not lab:
                continue
            lm = {y["nugget_id"]: y for y in (lab or {}).get("labels", [])}
            run_id = f"{r['embedding']}/irpf/{r['prompt']}/{r['llm']}/{r['ctx']}"
            ans[r["key"]] = {**(x or {}), "src": (lab or {}).get("source"),
                             "lab": [[LABEL_CODE.get(lm[i]["label"], "-"), lm[i].get("justification", "")] if i in lm else ["-", ""]
                                     for i in nids],
                             "val": [[num(v_) if not isinstance(v_, str) else v_ for v_ in vals_by.get((run_id, i), [])] for i in nids],
                             "cit": cits_by.get((run_id, qn), [])}
        cs = {}
        for k, m in ctxsup.get(qn, {}).items():
            cs[k] = [[LABEL_CODE.get(m[i]["label"], "-"), m[i].get("justification", "")] if i in m else ["-", ""] for i in nids]
        gold_out = {lv: [{"key": it.key_str, "label": it.label, "doc": it.document_id, "art": it.article_id,
                          "frag": it.fragment_id, "origin": it.origin} for it in gq[lv]] for lv in LEVELS}
        obj = {
            "q": {"n": qn, "summary": q["question_summary"], "text": q["question_text"], "answer": q["answer"],
                  "chapter": chap.get(qn, "")},
            "refs": [{"id": r["reference_id"], "origin": r["origin"], "title": r["cited_title"], "doc": r["document_id"],
                      "citation": r["citation_text"], "articles": r["article_ids"],
                      "provisions": [p["label"] for p in r["provisions"]]} for r in refs],
            "gold": gold_out, "nuggets": nug_out, "chunks": ch, "ret": ret, "ctx": ctxs, "ans": ans, "ctxsup": cs,
        }
        total += write_js(OUT / "q" / f"{qn}.js", f"(window.TRACE_Q=window.TRACE_Q||{{}})[{dumps(qn)}]={dumps(obj)};\n")
    checks["legal_basis"] = dict(lb_stats)
    print(f"  q/: {total / 1e6:.1f} MB; legal_basis: {dict(lb_stats)}", flush=True)

    # ---------------------------------------------------------------- index
    index = {
        "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "commit": git_commit(),
        "top_k": TOP_K, "budgets": budgets, "strategies": strat_names,
        "strategy_desc": {s: sdefs[s].get("description", "") for s in strat_names}, "strategy_bit": strat_bit,
        "eval_params": {k: P[k] for k in ("annex_rule", "dedup", "overflow")},
        "excluded_documents": sorted(excluded.documents),
        "questions": index_q, "built_questions": sorted(qset),
        "runs": [{k: r[k] for k in ("key", "llm", "context_id", "embedding", "prompt", "template")} for r in runs],
        "contexts": [{k: c[k] for k in ("key", "embedding", "context_id", "strategy", "budget")} for c in contexts],
        "retrieval_runs": list(rets),
        "templates": templates,
        "documents": {d: [m.get("title"), bool(m.get("statutory")), doc_file[d], d in excluded] for d, m in docs_meta.items()},
        "checks": checks, "build_seconds": round(time.time() - t0, 1),
    }
    write_js(OUT / "index.js", f"window.TRACE_INDEX={dumps(index)};\n")
    print(f"done in {time.time() - t0:.0f}s; checks: {json.dumps(checks, ensure_ascii=False)}")


def _span(ivs):
    sp: dict[int, list[tuple[int, int]]] = {}
    for f, s, e in ivs:
        sp.setdefault(f, []).append((s, e))
    return sp


if __name__ == "__main__":
    main()
