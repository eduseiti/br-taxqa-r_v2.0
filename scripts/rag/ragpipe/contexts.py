"""Stage C: build the generator contexts of a retrieval run (plan §6).

A **context set** is one way of building the context of every question, named by a spec:

- ``<strategy>@<cutoff>`` (e.g. ``S2@budget=4000``): the strategy's ranking cut by
  :func:`ragpipe.context.select`, the selection of the evaluation's budget view;
- ``closed_book``: no context (plan §6.3);
- ``oracle@<cutoff>``: the gold articles of the question (relevance rules G1–G3 and the annex rule)
  as whole-article units of the oracle strategy (S1); a gold document without a matchable gold
  article adds its chunks. Ordered by their rank in that strategy's ranking (unranked ones after, in file order),
  then cut like a retrieval context. Questions without resolved gold get an empty context;
- ``wrong:<strategy>@<cutoff>``: the retrieval context of another question (the *donor*: another
  P&R chapter, no shared gold document, none of the question's gold documents in the donor context;
  seeded), the control for answers drawn from the model's own
  knowledge (``docs/20261021_194457_*`` §4.2).

Every context records which gold items it holds (same rules as the evaluation), so answer scores
can be linked to retrieval per question (phase 5). For retrieval sets the coverage is checked
against ``per_item.csv.gz`` of a matching evaluation.

Outputs, under ``runs/contexts/<embedding>/<instruction>/``::

    <context_id>/manifest.json       parameters, input hashes, counts, gold coverage, consistency check
    <context_id>/contexts.jsonl.gz   one line per question: items, gold coverage, rendered context
    summary.csv                      one row per context set
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .context import Cutoff, Template, select, source_label
from .data import InputError, Paths, load_chapters, load_chunks, load_dataset
from .evaluation import RankedTexts, ranked_texts
from .relevance import LEVELS, Matcher, gold_items
from .retrieval import load_rankings
from .runs import (base_manifest, prepare_run_dir, read_json, rel, sha256_file, sha256_json, write_csv,
                   write_json, write_jsonl_gz)
from .strategies import member_mask

log = logging.getLogger("ragpipe")

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
ORDERS = ("score", "document")
#: The context sets of the RAG pilot (first-evaluation note §2.3), the default of ``rag.py context``.
DEFAULT_SETS = ("S1@budget=4000", "S2@budget=4000", "S3@budget=4000", "S2c@budget=4000", "S4@budget=4000",
                "S1@budget=2000", "S2@budget=2000", "S1@budget=8000", "S2@budget=8000", "closed_book",
                "oracle@budget=4000", "wrong:S2@budget=4000")
SPEC_RE = re.compile(r"(?:(?P<wrong>wrong):)?(?P<base>[A-Za-z0-9_]+)(?:@(?P<cutoff>[a-z]+=\d+))?")
TOKENIZER = "Qwen/Qwen3-Embedding-4B"   # the n_tokens_qwen3 tokenizer of the segmentation


@dataclass(frozen=True)
class SetSpec:
    """One context set: ``kind`` is ``retrieval``, ``closed_book``, ``oracle`` or ``wrong``."""

    kind: str
    strategy: str | None = None
    cutoff: Cutoff | None = None

    @classmethod
    def parse(cls, spec: str) -> "SetSpec":
        m = SPEC_RE.fullmatch(spec.strip())
        if not m:
            raise ValueError(f"bad context set {spec!r}: use S2@budget=4000, closed_book, oracle@budget=4000 "
                             "or wrong:S2@budget=4000")
        base, cut = m.group("base"), m.group("cutoff")
        cutoff = Cutoff.parse(cut) if cut else None
        if base == "closed_book":
            if cutoff or m.group("wrong"):
                raise ValueError(f"bad context set {spec!r}: closed_book takes no cutoff")
            return cls("closed_book")
        if cutoff is None:
            raise ValueError(f"bad context set {spec!r}: a cutoff is required (@budget=<tokens> or @k=<n>)")
        if base == "oracle":
            if m.group("wrong"):
                raise ValueError(f"bad context set {spec!r}: wrong: takes a strategy")
            return cls("oracle", None, cutoff)
        return cls("wrong" if m.group("wrong") else "retrieval", base, cutoff)

    def base_id(self) -> str:
        cut = f"{self.cutoff.kind}{self.cutoff.value}" if self.cutoff else ""
        return {"closed_book": "closed_book", "oracle": f"oracle_{cut}", "retrieval": f"{self.strategy}_{cut}",
                "wrong": f"wrong-{self.strategy}_{cut}"}[self.kind]


@dataclass
class ContextConfig:
    sets: tuple[str, ...] = DEFAULT_SETS
    dedup: str = "containment_merge"
    overflow: str = "skip"
    order: str = "score"
    template: str = "context_v1"
    annex_rule: str = "either"
    oracle_strategy: str = "S1"
    seed: int = 13
    count_tokens: bool = True
    eval_id: str | None = None          # evaluation for the consistency check (default: a matching one)
    force: bool = False

    def suffix(self) -> str:
        """Context-id suffix naming the non-default options, so variants never share a directory."""
        d = ContextConfig()
        parts = [f"{k}-{getattr(self, k)}" for k in ("dedup", "overflow", "order", "annex_rule", "oracle_strategy")
                 if getattr(self, k) != getattr(d, k)]
        if self.template != d.template:
            parts.append(self.template)
        return "".join(f"_{p}" for p in parts)

    def params(self) -> dict:
        return {"dedup": self.dedup, "overflow": self.overflow, "order": self.order, "template": self.template,
                "annex_rule": self.annex_rule, "oracle_strategy": self.oracle_strategy, "seed": self.seed,
                "token_counter": "qwen3"}


# ================================================================================================
# Inputs shared by all sets
# ================================================================================================

@dataclass
class Inputs:
    chunks: pd.DataFrame
    question_ids: list[str]
    questions: dict[str, str]
    chapters: dict[str, str]
    matcher: Matcher
    gold: dict
    title: dict[str, str]
    file_index: dict[str, int]
    strategies: dict
    retrieval_dir: Path
    ranked: dict[str, tuple[RankedTexts, dict[str, np.ndarray]]] = field(default_factory=dict)

    def ranking(self, name: str) -> tuple[RankedTexts, dict[str, np.ndarray]]:
        """Ranked texts of a strategy and the scores per question (aligned with ``per_question``)."""
        if name not in self.ranked:
            if name not in self.strategies:
                raise InputError(f"no rankings for {name} in {rel(self.retrieval_dir)} "
                                 f"(have {', '.join(self.strategies)})")
            df = load_rankings(self.retrieval_dir, name)
            rt = ranked_texts(df, self.chunks, self.file_index)
            score = df["score"].to_numpy()
            scores = {q: score[idx] for q, idx in df.groupby("question_number", sort=False).indices.items()}
            self.ranked[name] = (rt, scores)
        return self.ranked[name]

    def member_mask(self, name: str) -> np.ndarray:
        s = self.strategies[name]
        return member_mask(self.chunks, frozenset(s["tipos"]), s.get("variantes", ["base"]))


@dataclass
class Item:
    """One selected text: its chunk rows (representative first), rank and score (None when unranked)."""

    rows: np.ndarray
    rank: int | None
    score: float | None
    text_id: str


# ================================================================================================
# Selection per kind
# ================================================================================================

def retrieval_items(inp: Inputs, spec: SetSpec, cfg: ContextConfig) -> dict[str, list[Item]]:
    rt, scores = inp.ranking(spec.strategy)
    empty = np.empty(0, dtype=np.int64)
    out = {}
    for q in inp.question_ids:
        ranked = rt.per_question.get(q, empty)
        sel = select(ranked, rt.tokens, rt.intervals, spec.cutoff, cfg.dedup, cfg.overflow)
        out[q] = [Item(rt.members[ranked[i]], i + 1, float(scores[q][i]), rt.text_ids[ranked[i]]) for i in sel]
    return out


def oracle_items(inp: Inputs, spec: SetSpec, cfg: ContextConfig) -> dict[str, list[Item]]:
    name = cfg.oracle_strategy
    rt, scores = inp.ranking(name)
    in_s = inp.member_mask(name)
    ch = inp.chunks
    sha, tok = ch["texto_sha256"].to_numpy(), ch["n_tokens_qwen3"].to_numpy()
    arquivo, start, end = ch["arquivo"].to_numpy(), ch["Num_Inicio"].to_numpy(), ch["Num_Final"].to_numpy()
    out = {}
    for q in inp.question_ids:
        g = inp.gold.get(q)
        if not g:
            out[q] = []
            continue
        rows, with_article = [], set()
        for it in g["article"]:
            r = inp.matcher.match(it).full
            r = r[in_s[r]]
            if len(r):
                rows.append(r)
                with_article.add(it.document_id)
        # a gold document none of whose gold articles is matchable (e.g. a treaty's "art. IX") adds its chunks
        rows += [inp.matcher.rows_by_doc.get(it.document_id, np.empty(0, dtype=np.int64))
                 for it in g["document"] if it.document_id not in with_article]
        cand = np.unique(np.concatenate(rows)) if rows else np.empty(0, dtype=np.int64)
        cand = cand[in_s[cand]]
        ranked = rt.per_question.get(q, np.empty(0, dtype=np.int64))
        pos = {int(t): i for i, t in enumerate(ranked)}
        texts: dict[str, list[int]] = {}
        for r in cand:                                   # group rows by text, file order
            texts.setdefault(sha[r], []).append(int(r))
        entries = []
        for tid, rs in texts.items():
            t = int(rt.local_of_row[rs[0]])
            i = pos.get(t) if t >= 0 else None
            members = rt.members[t] if i is not None else np.array(rs, dtype=np.int64)
            key = (0, i, 0, 0) if i is not None else (1, 0, inp.file_index[arquivo[rs[0]]], int(start[rs[0]]))
            entries.append((key, Item(members, i + 1 if i is not None else None,
                                      float(scores[q][i]) if i is not None else None, tid)))
        entries.sort(key=lambda e: e[0])
        items = [e[1] for e in entries]
        toks = np.array([int(tok[it.rows[0]]) for it in items], dtype=np.int64)
        ivs = [[(inp.file_index[arquivo[r]], int(start[r]), int(end[r])) for r in it.rows] for it in items]
        sel = select(np.arange(len(items)), toks, ivs, spec.cutoff, cfg.dedup, cfg.overflow)
        out[q] = [items[i] for i in sel]
    return out


def donors(inp: Inputs, base: dict[str, list[Item]], seed: int) -> tuple[dict[str, str], int]:
    """Question → donor question for the wrong-context control: another P&R chapter, no shared gold
    document, and a donor context holding no chunk of the question's gold documents. A seeded
    permutation, so a donor is reused only when no unused one is eligible. Returns the donors and the
    number of questions for which the context condition had to be dropped (no eligible donor)."""
    rng = np.random.default_rng(seed)
    gdocs = {q: {it.document_id for it in inp.gold.get(q, {}).get("document", [])} for q in inp.question_ids}
    cdocs = {q: {inp.matcher.doc_of_row[r] for it in base[q] for r in it.rows} for q in inp.question_ids}
    ch = inp.chapters
    free = set(inp.question_ids)
    out, relaxed = {}, 0

    def eligible(q: str, pool, strict: bool) -> list[str]:
        return [d for d in pool if d != q and ch.get(d) != ch.get(q) and not (gdocs[d] & gdocs[q])
                and (not strict or not (cdocs[d] & gdocs[q]))]

    for q in inp.question_ids:
        ok = eligible(q, sorted(free), True) or eligible(q, inp.question_ids, True)
        if not ok:
            relaxed += 1
            ok = eligible(q, inp.question_ids, False)
        d = ok[int(rng.integers(len(ok)))]
        out[q] = d
        free.discard(d)
    return out, relaxed


# ================================================================================================
# Coverage, rendering, writing
# ================================================================================================

def coverage(inp: Inputs, q: str, items: list[Item]) -> dict:
    """Gold items of ``q`` held by the context, per level (``full``: the evaluation's full hit)."""
    rows = np.concatenate([it.rows for it in items]) if items else np.empty(0, dtype=np.int64)
    out = {}
    for level in LEVELS:
        gl = inp.gold.get(q, {}).get(level, [])
        full, anyh = [], []
        for it in gl:
            m = inp.matcher.match(it)
            f = bool(np.isin(m.full, rows).any()) or any(np.isin(p, rows).all() for p in m.parts)
            a = f or bool(np.isin(m.partial, rows).any())
            if f:
                full.append(it.key_str)
            if a:
                anyh.append(it.key_str)
        out[level] = {"n": len(gl), "full": full, "any": anyh}
    return out


def order_items(inp: Inputs, items: list[Item], order: str) -> list[Item]:
    if order == "score":
        return items
    ch = inp.chunks
    return sorted(items, key=lambda it: (inp.file_index[ch.at[int(it.rows[0]), "arquivo"]],
                                         int(ch.at[int(it.rows[0]), "Num_Inicio"])))


PREFIX_RE = re.compile(r"^\[\s*([^\]]*?)\s*\]")


def epigrafe(texto: str) -> str | None:
    """First field of the ``[ Epígrafe | Ementa ]`` prefix of a chunk text (title fallback); the
    second when the first is a URN (a document parsed without a title, e.g. the DIAT service page)."""
    m = PREFIX_RE.match(texto or "")
    if not m:
        return None
    fields = [f.strip() for f in m.group(1).split("|") if f.strip()]
    if fields and fields[0].startswith("urn:") and len(fields) > 1:
        return fields[1]
    return fields[0] if fields else None


def describe(inp: Inputs, n: int, it: Item) -> dict:
    r = int(it.rows[0])
    c = inp.chunks
    doc = inp.matcher.doc_of_row[r]
    title = inp.title.get(doc) or epigrafe(c.at[r, "Texto"]) or c.at[r, "Rotulo"].split(",")[0]
    fonte = source_label(title, c.at[r, "doc_urn"], bool(c.at[r, "anexo_urn"]), c.at[r, "citacao"],
                         int(c.at[r, "parte"]), int(c.at[r, "n_partes"]))
    return {"n": n, "text_id": it.text_id, "chunk_id": c.at[r, "chunk_id"],
            "alias_chunk_ids": [c.at[int(x), "chunk_id"] for x in it.rows[1:]], "rank": it.rank,
            "score": None if it.score is None else round(it.score, 6), "document_id": doc,
            "arquivo": c.at[r, "arquivo"], "tipo": c.at[r, "Tipo"], "citacao": c.at[r, "citacao"],
            "tokens_qwen3": int(c.at[r, "n_tokens_qwen3"]), "fonte": fonte}


class TokenCounter:
    """Qwen3 token counts of rendered contexts (the segmentation's tokenizer), when it is installed."""

    def __init__(self, enabled: bool):
        self.tok = None
        if not enabled:
            return
        try:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
        except Exception as e:   # optional dependency: the counts are left empty
            log.warning("rendered-context token counts skipped (%s: %s)", type(e).__name__, e)

    def count(self, texts: list[str]) -> list[int | None]:
        if self.tok is None:
            return [None] * len(texts)
        return [len(ids) for ids in self.tok(texts, add_special_tokens=False)["input_ids"]]


def build_set(inp: Inputs, spec: SetSpec, cfg: ContextConfig, tmpl: Template, counter: TokenCounter,
              cache: dict) -> tuple[list[dict], dict]:
    """Lines of ``contexts.jsonl.gz`` and the extra manifest fields of one set."""
    extra: dict = {}
    donor: dict[str, str] = {}
    if spec.kind == "closed_book":
        sel = {q: [] for q in inp.question_ids}
    elif spec.kind == "oracle":
        sel = oracle_items(inp, spec, cfg)
    else:
        key = (spec.strategy, str(spec.cutoff))
        if key not in cache:
            cache[key] = retrieval_items(inp, SetSpec("retrieval", spec.strategy, spec.cutoff), cfg)
        base = cache[key]
        if spec.kind == "wrong":
            donor, relaxed = donors(inp, base, cfg.seed)
            sel = {q: base[donor[q]] for q in inp.question_ids}
            extra["donor_rule"] = ("another P&R chapter, no shared gold document, no chunk of the question's gold "
                                   "documents in the donor context; seeded permutation")
            extra["donor_context_rule_relaxed"] = relaxed
            extra["donor_reused"] = len(donor) - len(set(donor.values()))
        else:
            sel = base
    lines = []
    for q in inp.question_ids:
        items = order_items(inp, sel[q], cfg.order)
        desc = [describe(inp, n, it) for n, it in enumerate(items, 1)]
        text = tmpl.render([(d["fonte"], inp.chunks.at[int(it.rows[0]), "Texto"]) for d, it in zip(desc, items)])
        line = {"context_id": None, "question_number": q, "kind": spec.kind,
                **({"donor_question": donor[q]} if donor else {}),
                "n_texts": len(items), "context_tokens_qwen3": int(sum(d["tokens_qwen3"] for d in desc)),
                "rendered_tokens_qwen3": None, "rendered_chars": len(text), "items": desc,
                "gold": coverage(inp, q, sel[q]), "context": text}
        lines.append(line)
    for line, n in zip(lines, counter.count([ln["context"] for ln in lines])):
        line["rendered_tokens_qwen3"] = n
    return lines, extra


def set_summary(lines: list[dict]) -> dict:
    """Counts and gold coverage of a set (means over questions with gold at the level)."""
    df = pd.DataFrame([{"n_texts": ln["n_texts"], "tokens": ln["context_tokens_qwen3"],
                        "rendered": ln["rendered_tokens_qwen3"], "chars": ln["rendered_chars"]} for ln in lines])
    out = {"questions": len(lines), "empty_contexts": int((df["n_texts"] == 0).sum()),
           "mean_texts": round(float(df["n_texts"].mean()), 3),
           "mean_context_tokens_qwen3": round(float(df["tokens"].mean()), 1),
           "mean_rendered_tokens_qwen3": round(float(df["rendered"].mean()), 1) if df["rendered"].notna().all()
           else None,
           "mean_rendered_chars": round(float(df["chars"].mean()), 1)}
    for level in LEVELS:
        cov = [ln["gold"][level] for ln in lines if ln["gold"][level]["n"]]
        out[f"{level}_questions"] = len(cov)
        out[f"{level}_recall"] = round(float(np.mean([len(c["full"]) / c["n"] for c in cov])), 6) if cov else None
        out[f"{level}_hit"] = round(float(np.mean([bool(c["full"]) for c in cov])), 6) if cov else None
    return out


def find_eval(retrieval_dir: Path, cfg: ContextConfig, chunks_sha: str) -> Path | None:
    """An evaluation of the run with the same annex rule, de-duplication, overflow and chunk file."""
    root = retrieval_dir / "eval"
    cands = [root / cfg.eval_id] if cfg.eval_id else sorted(root.glob("*/"))
    best = None
    for d in cands:
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        m = read_json(mf)
        p = m["params"]
        if (p["annex_rule"], p["dedup"], p["overflow"]) != (cfg.annex_rule, cfg.dedup, cfg.overflow) \
                or m["inputs"]["chunks"]["sha256"] != chunks_sha or not (d / "per_item.csv.gz").exists():
            if cfg.eval_id:
                raise InputError(f"{rel(d)} does not match the context options or the chunk file")
            continue
        if best is None or m["created_at"] > best[0]:
            best = (m["created_at"], d)
    return best[1] if best else None


def consistency(eval_dir: Path | None, per_item: dict, spec: SetSpec, lines: list[dict]) -> dict | None:
    """Compare the context's full gold hits with the evaluation's ``budget_full_<B>`` per item."""
    if spec.kind != "retrieval" or spec.cutoff.kind != "budget" or eval_dir is None:
        return None
    col = f"budget_full_{spec.cutoff.value}"
    if eval_dir not in per_item:
        per_item[eval_dir] = pd.read_csv(eval_dir / "per_item.csv.gz", dtype={"question_number": str},
                                         keep_default_na=False)
    pi = per_item[eval_dir]
    if col not in pi.columns:
        return {"eval": rel(eval_dir), "skipped": f"budget {spec.cutoff.value} not evaluated"}
    pi = pi[pi["strategy"] == spec.strategy]
    ours = {(ln["question_number"], lv, k) for ln in lines for lv in LEVELS for k in ln["gold"][lv]["full"]}
    theirs = pi[pi[col].astype(str) == "True"]
    theirs = set(zip(theirs["question_number"], theirs["level"], theirs["item"]))
    mism = sorted(ours ^ theirs)
    return {"eval": rel(eval_dir), "items": int(len(pi)), "full_hits": len(ours), "mismatches": len(mism),
            "examples": [list(x) for x in mism[:10]]}


# ================================================================================================
# Driver
# ================================================================================================

def run_contexts(retrieval_dir: Path, cfg: ContextConfig, paths: Paths = Paths()) -> Path:
    """Build every context set of ``cfg.sets`` and return the output root."""
    t0 = time.time()
    retrieval_dir = Path(retrieval_dir)
    if not (retrieval_dir / "manifest.json").exists():
        raise InputError(f"{rel(retrieval_dir)} is not a retrieval run (no manifest.json); run `rag.py retrieve`")
    if cfg.order not in ORDERS:
        raise ValueError(f"order must be one of {ORDERS}")
    specs = [SetSpec.parse(s) for s in cfg.sets]
    rman = read_json(retrieval_dir / "manifest.json")
    chunks_sha = sha256_file(paths.chunks)
    if chunks_sha != rman["inputs"]["chunks"]["sha256"]:
        raise InputError(f"the rankings in {rel(retrieval_dir)} were made from another chunk file; "
                         "rerun `rag.py retrieve`")
    for s, out in rman["outputs"].items():
        if sha256_file(retrieval_dir / out["path"]) != out["sha256"]:
            raise InputError(f"{rel(retrieval_dir / out['path'])} changed after retrieval; rerun `rag.py retrieve`")
    tmpl = Template.load(PROMPTS, cfg.template)
    chunks = load_chunks(paths.chunks, with_text=True)
    ds = load_dataset(paths.dataset)
    main_file = {d: Path(f).name for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"]) if f}
    grouping = frozenset(rman["strategies"]["grouping_tipos"])
    titles = ({d: t for d, t in zip(ds.documents["document_id"], ds.documents["title"]) if isinstance(t, str) and t.strip()}
              if "title" in ds.documents else {})
    inp = Inputs(chunks=chunks, question_ids=ds.question_ids,
                 questions=dict(zip(ds.questions["question_number"], ds.questions["question_text"])),
                 chapters=load_chapters(paths.chapters, ds.question_ids),
                 matcher=Matcher(chunks, ds.file_to_document(), main_file, grouping, cfg.annex_rule),
                 gold=gold_items(ds), title=titles,
                 file_index={f: i for i, f in enumerate(sorted(set(chunks["arquivo"])))},
                 strategies={n: rman["strategies"]["strategies"][n] for n in rman["outputs"]},
                 retrieval_dir=retrieval_dir)
    unknown = [s.strategy for s in specs if s.strategy and s.strategy not in inp.strategies]
    if cfg.oracle_strategy not in inp.strategies:
        unknown.append(cfg.oracle_strategy)
    if unknown:
        raise InputError(f"no rankings for {sorted(set(unknown))} in {rel(retrieval_dir)} "
                         f"(have {', '.join(inp.strategies)})")
    eval_dir = find_eval(retrieval_dir, cfg, chunks_sha)
    if eval_dir is None:
        log.warning("no matching evaluation in %s: the consistency check is skipped", rel(retrieval_dir / "eval"))
    counter = TokenCounter(cfg.count_tokens)
    root = paths.runs / "contexts" / rman["params"]["embedding"] / rman["params"]["instruction"]
    inputs = {"retrieval_manifest": {"path": rel(retrieval_dir / "manifest.json"), "config_hash": rman["config_hash"]},
              "chunks": {"path": rel(paths.chunks), "sha256": chunks_sha},
              **{Path(p).stem: {"path": p, "sha256": h} for p, h in ds.sha256.items()},
              "chapters": {"path": rel(paths.chapters), "sha256": sha256_file(paths.chapters)},
              "template": {"path": rel(PROMPTS / f"{cfg.template}.pt.md"), "sha256": tmpl.sha256}}
    log.info("inputs loaded in %.1fs", time.time() - t0)

    cache: dict = {}
    per_item: dict = {}
    summary = []
    for spec in specs:
        ts = time.time()
        cid = spec.base_id() + cfg.suffix()
        params = {**cfg.params(), "set": spec.kind, "strategy": spec.strategy,
                  "cutoff": str(spec.cutoff) if spec.cutoff else None}
        config_hash = sha256_json({"params": params, "inputs": inputs})
        out = root / cid
        prepare_run_dir(out, config_hash, cfg.force)
        lines, extra = build_set(inp, spec, cfg, tmpl, counter, cache)
        for ln in lines:
            ln["context_id"] = cid
        write_jsonl_gz(lines, out / "contexts.jsonl.gz")
        stats = set_summary(lines)
        check = consistency(eval_dir, per_item, spec, lines)
        if check and check.get("mismatches"):
            log.error("%s: %d gold hits differ from %s (e.g. %s)", cid, check["mismatches"], check["eval"],
                      check["examples"][:3])
        man = base_manifest("contexts")
        man.update({"config_hash": config_hash, "context_id": cid, "params": params, "inputs": inputs, **extra,
                    "counts": stats, "consistency_with_evaluation": check,
                    "outputs": {"contexts.jsonl.gz": {"sha256": sha256_file(out / "contexts.jsonl.gz")}},
                    "timings_s": {"total": round(time.time() - ts, 2)}})
        write_json(out / "manifest.json", man)
        summary.append({"context_id": cid, **params, **stats,
                        "consistency_mismatches": None if not check else check.get("mismatches")})
        log.info("%s: %d questions, %.0f tokens on average, written in %.1fs", cid, stats["questions"],
                 stats["mean_context_tokens_qwen3"], time.time() - ts)
    write_summary(root, pd.DataFrame(summary))
    return root


def write_summary(root: Path, new: pd.DataFrame) -> None:
    """``summary.csv``: one row per context set, rows of earlier runs kept unless rebuilt now."""
    path = root / "summary.csv"
    if path.exists():
        old = pd.read_csv(path, keep_default_na=False)
        new = pd.concat([old[~old["context_id"].isin(new["context_id"])], new], ignore_index=True)
    write_csv(new.sort_values("context_id", kind="stable"), path)


def load_contexts(context_dir: Path) -> list[dict]:
    path = Path(context_dir) / "contexts.jsonl.gz"
    if not path.exists():
        raise InputError(f"{rel(path)} not found; run `rag.py context` first")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]
