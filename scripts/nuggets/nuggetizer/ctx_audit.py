"""Audit of the context-support result (phase 5 note §10): why do the cited provisions support only about half of
the vital nuggets?

- known-answer tests of the context judge (``assign_ctx_v1``): the phase 4 tests with the test text as the context,
  and needle tests (the nugget's source sentence of the P&R answer appended to its oracle context);
- corpus search: the nuggets the oracle does not support, judged against the texts of the whole corpus that a
  lexical search (TF-IDF on the nugget text) ranks first, outside the cited articles;
- classification of each unsupported nugget into a cause, by a second model with all the evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .scoring import REPO, jl

RETRIEVAL = REPO / "runs" / "retrieval" / "jua-4b-mixed" / "irpf"
CAUSES = ("judge_error", "other_provision", "corpus_gap", "pgd_practical", "interpretation", "not_in_legislation",
          "nugget_problem")


def needle_tests(ctx: dict[str, dict], labels: list[dict], nugs: dict[str, list[dict]]) -> list[dict]:
    """One test per vital nugget the oracle context does not support: the context plus one more block holding the
    nugget's source sentence of the P&R answer. Expected: the target becomes ``support`` (or partial)."""
    tests = []
    by_id = {n["nugget_id"]: n for ns in nugs.values() for n in ns}
    for x in labels:
        q = x["question_number"]
        ln = ctx[q]
        for y in x["labels"]:
            n = by_id[y["nugget_id"]]
            if n["importance"] != "vital" or y["label"] != "not_support" or not n.get("source_span"):
                continue
            k = ln["n_texts"] + 1
            block = f"[Documento {k}] Texto complementar\n{n['source_span'].strip()}"
            tests.append({"test_id": f"{n['nugget_id']}_L", "question_number": q, "type": "L",
                          "targets": [n["nugget_id"]], "excluded": [],
                          "answer": ln["context"].rstrip() + "\n\n" + block})
    return tests


class CorpusSearch:
    """TF-IDF over the S1 texts (articles, orphan dispositivos, tables, non-statutory blocks) of the corpus, revoked
    documents excluded as in the RAG runs; renders hits as context blocks of the RAG template."""

    def __init__(self, template: str = "context_v2"):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from ragpipe.context import Template
        from ragpipe.contexts import PROMPTS, describe
        from ragpipe.data import Paths, load_chunks, load_dataset
        from ragpipe.exclusions import Exclusions
        from ragpipe.relevance import Matcher
        from ragpipe.strategies import member_mask
        rman = json.loads((RETRIEVAL / "manifest.json").read_text())
        paths = Paths()
        ch = load_chunks(paths.chunks, with_text=True)
        ds = load_dataset(paths.dataset)
        main_file = {d: Path(f).name for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"]) if f}
        s1 = rman["strategies"]["strategies"]["S1"]
        mask = member_mask(ch, frozenset(s1["tipos"]), s1.get("variantes", ["base"])) & \
            ~Exclusions.from_manifest(rman).row_mask(ch, ds.file_to_document())
        rows = np.flatnonzero(mask)
        _, first = np.unique(ch["texto_sha256"].to_numpy()[rows], return_index=True)
        self.rows = rows[np.sort(first)]
        self.ch = ch
        titles = {d: t for d, t in zip(ds.documents["document_id"], ds.documents["title"]) if isinstance(t, str) and t.strip()}
        self.inp = SimpleNamespace(chunks=ch, title=titles, matcher=Matcher(
            ch, ds.file_to_document(), main_file, frozenset(rman["strategies"]["grouping_tipos"]), "either"))
        self.tmpl, self.describe = Template.load(PROMPTS, template), describe
        self.vec = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2), min_df=2,
                                   sublinear_tf=True, max_df=0.5)
        self.X = self.vec.fit_transform(ch["Texto"].to_numpy()[self.rows])
        self.unit = list(zip(ch["arquivo"].to_numpy()[self.rows], ch["artigo_id"].to_numpy()[self.rows]))

    def row_of(self, chunk_id: str) -> int:
        if not hasattr(self, "_row"):
            self._row = dict(zip(self.ch["chunk_id"], range(len(self.ch))))
        return self._row[chunk_id]

    def article_of_chunk(self, chunk_id: str) -> tuple[str, str]:
        r = self.row_of(chunk_id)
        return self.ch.at[r, "arquivo"], self.ch.at[r, "artigo_id"]

    def search(self, texts: list[str], skip_units: set, per_query: int = 4, budget: int = 6000) -> list[int]:
        """Chunk rows: the best ``per_query`` texts of each query (round robin), outside ``skip_units`` (the cited
        articles already in the oracle), until ``budget`` tokens."""
        sims = (self.X @ self.vec.transform(texts).T).toarray()
        order = [np.argsort(-sims[:, j]) for j in range(len(texts))]
        picked, tok = [], 0
        for rank in range(200):
            for j in range(len(texts)):
                if sum(1 for p in picked if p[1] == j) >= per_query:
                    continue
                i = order[j][rank]
                r = int(self.rows[i])
                if sims[i, j] <= 0 or self.unit[i] in skip_units or r in [p[0] for p in picked]:
                    continue
                t = int(self.ch.at[r, "n_tokens_qwen3"])
                if tok + t > budget:
                    continue
                picked.append((r, j))
                tok += t
            if all(sum(1 for p in picked if p[1] == j) >= per_query for j in range(len(texts))):
                break
        return [p[0] for p in picked]

    def render(self, rows: list[int]) -> tuple[str, list[dict]]:
        from ragpipe.contexts import Item
        seen: set[str] = set()
        desc, blocks = [], []
        for n, r in enumerate(rows, 1):
            d, b = self.describe(self.inp, n, Item(rows=np.array([r]), rank=None, score=None, text_id=str(r)),
                                 self.tmpl, seen)
            desc.append(d)
            blocks.append(b)
        return self.tmpl.render(blocks), desc


def cited_docs(justification: str) -> list[int]:
    return sorted({int(x) for x in re.findall(r"[Dd]ocumentos?\s+(\d+)", justification)})


def references(question_number: str) -> list[str]:
    """The P&R references of a question, as the dataset gives them (document, articles, provisions)."""
    out = []
    for r in REFS.get(question_number, []):
        prov = ", ".join(p["label"] for p in r["provisions"]) if r["provisions"] else ""
        out.append(f"{r['cited_title'] or r['document_id']}" + (f" — {prov}" if prov else
                                                                f" — {', '.join(r['article_ids'])}" if r["article_ids"] else ""))
    return out


REFS: dict[str, list[dict]] = {}
for _r in jl(REPO / "dataset" / "references.jsonl"):
    REFS.setdefault(_r["question_number"], []).append(_r)
