"""Gold items from ``references.jsonl`` and the gold ↔ chunk matcher (plan §4.1, §4.2).

Shared with the legal-provision score of generated answers (nugget plan §4.5), so both use one
definition of "the right provision".

Levels and gold keys:

- ``document``  — ``document_id``;
- ``article``   — ``(document_id, article_id)`` from the reference's ``article_ids``;
- ``provision`` — ``(document_id, fragment_id, lexml_file)`` from ``provisions[]`` (nested LexML id,
  e.g. ``art1_cpt_inc10``). Units without ``fragment_id`` or ``lexml_file`` are kept as unreachable.

Matching rules (plan §4.2):

- G1 chunk → document through its file (``arquivo``), main or annex, not the URN;
- G2 chunk → article through ``(arquivo, artigo_id)``: any chunk of the article counts (inciso,
  paragraph, article part). A grouping chunk hits an article whose interval it contains;
- G3 annex rule: ``either`` (article N of the main file or of any annex of D) or ``main_first``
  (the annex only when the main file lacks article N);
- G4 matches that exist only through ``id_ambiguo = 1`` chunks are flagged;
- G5 provision: **full** hit when a ``cobre_ids`` id equals the fragment or is its ancestor, or a
  grouping chunk contains the unit; **partial** when the fragment is an ancestor of a ``cobre_ids``
  id or appears in ``parcial_ids``. Refinement (deviation from the plan, recorded in the Phase 1
  note): a unit held by the parts of a **split article** (``n_partes > 1``) is also fully hit once
  *all* those parts are retrieved (``Match.parts``) — otherwise an article cited as a whole could
  never be fully hit in S1/S2 when it is long enough to be split.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .data import Dataset

LEVELS = ("document", "article", "provision")
ANNEX_RULES = ("either", "main_first")


@dataclass
class GoldItem:
    """One gold unit of one question at one level."""

    question_number: str
    level: str
    key: tuple
    document_id: str
    label: str
    origins: set[str] = field(default_factory=set)
    article_id: str | None = None
    fragment_id: str | None = None
    lexml_file: str | None = None        # basename

    @property
    def key_str(self) -> str:
        return "|".join("" if k is None else str(k) for k in self.key)

    @property
    def origin(self) -> str:
        """``explicit`` when any citing reference is explicit, else ``embedded``."""
        return "explicit" if "explicit" in self.origins else "embedded"


def gold_items(ds: Dataset) -> dict[str, dict[str, list[GoldItem]]]:
    """``question_number`` → level → gold items (resolved references only, one item per key)."""
    acc: dict[tuple[str, str, tuple], GoldItem] = {}

    def add(q: str, level: str, key: tuple, origin: str, **kw) -> None:
        it = acc.get((q, level, key))
        if it is None:
            it = acc[(q, level, key)] = GoldItem(q, level, key, **kw)
        it.origins.add(origin)

    for r in ds.references:
        doc = r["document_id"]
        if not doc:
            continue
        q, o = r["question_number"], r["origin"]
        add(q, "document", (doc,), o, document_id=doc, label=r["cited_title"] or doc)
        for art in r["article_ids"]:
            add(q, "article", (doc, art), o, document_id=doc, label=f"{doc} {art}", article_id=art)
        for p in r["provisions"]:
            f = Path(p["lexml_file"]).name if p["lexml_file"] else None
            frag = p["fragment_id"]
            key = (doc, frag, f) if frag else (doc, None, p["label"])
            add(q, "provision", key, o, document_id=doc, label=f"{doc} {p['label']}", article_id=p["article_id"],
                fragment_id=frag, lexml_file=f)
    out: dict[str, dict[str, list[GoldItem]]] = defaultdict(lambda: {lv: [] for lv in LEVELS})
    for (q, level, _), it in sorted(acc.items(), key=lambda kv: (kv[0][0], LEVELS.index(kv[0][1]),
                                                                 kv[1].key_str)):
        out[q][level].append(it)
    return dict(out)


@dataclass
class Match:
    """Chunk-table rows matching a gold item (all strategies; filter by strategy afterwards)."""

    full: np.ndarray
    partial: np.ndarray
    units: list[tuple[str, str]]        # (arquivo, artigo_id) or (document_id,) retrieval units
    main_and_annex: bool = False        # article exists in the main file and in an annex (G3)
    #: split-article parts that together hold the unit, one array per file (provision level only):
    #: the unit is fully hit when every part of one file is retrieved
    parts: list[np.ndarray] = field(default_factory=list)


def _is_prefix(anc: str, desc: str) -> bool:
    """``anc`` is ``desc`` or one of its ancestors (LexML ids nest with ``_``)."""
    return desc == anc or desc.startswith(anc + "_")


class Matcher:
    """Finds the chunks that hit a gold item, strategy-independently.

    ``chunks`` is the chunk table (row index = chunk row), ``file_to_doc`` maps ``arquivo`` to
    ``document_id`` and ``main_file`` maps ``document_id`` to its main LexML file basename.
    """

    def __init__(self, chunks: pd.DataFrame, file_to_doc: dict[str, str], main_file: dict[str, str],
                 grouping_tipos: frozenset[str], annex_rule: str = "either"):
        if annex_rule not in ANNEX_RULES:
            raise ValueError(f"annex_rule must be one of {ANNEX_RULES}")
        self.annex_rule = annex_rule
        self.file_to_doc = file_to_doc
        self.main_file = main_file
        self.arquivo = chunks["arquivo"].to_numpy()
        self.artigo = chunks["artigo_id"].to_numpy()
        self.start = chunks["Num_Inicio"].to_numpy()
        self.end = chunks["Num_Final"].to_numpy()
        self.ambiguous = chunks["id_ambiguo"].to_numpy() == 1
        self.split = chunks["n_partes"].to_numpy() > 1
        self.categoria = dict(zip(chunks["arquivo"], chunks["categoria"]))
        self.cobre = [c.split(";") if c else [] for c in chunks["cobre_ids"]]
        self.parcial = [c.split(";") if c else [] for c in chunks["parcial_ids"]]
        is_group = chunks["Tipo"].isin(grouping_tipos).to_numpy()
        self.is_group = is_group

        self.doc_of_row = np.array([file_to_doc.get(a) for a in self.arquivo], dtype=object)
        rows_by_doc: dict[str, list[int]] = defaultdict(list)
        for i, d in enumerate(self.doc_of_row):
            if d is not None:
                rows_by_doc[d].append(i)
        self.rows_by_doc = {d: np.array(v, dtype=np.int64) for d, v in rows_by_doc.items()}

        by_art: dict[tuple[str, str], list[int]] = defaultdict(list)
        for i in np.flatnonzero(~is_group & (self.artigo != "")):
            by_art[(self.arquivo[i], self.artigo[i])].append(int(i))
        self.rows_by_article = {k: np.array(v, dtype=np.int64) for k, v in by_art.items()}
        self.article_interval = {k: (int(self.start[v].min()), int(self.end[v].max()))
                                 for k, v in self.rows_by_article.items()}
        self.files_of_doc: dict[str, set[str]] = defaultdict(set)
        for a in set(self.arquivo):
            if a in file_to_doc:
                self.files_of_doc[file_to_doc[a]].add(a)
        self.articles_of_file: dict[str, set[str]] = defaultdict(set)
        for (f, art) in self.rows_by_article:
            self.articles_of_file[f].add(art)
        unit = chunks["unidade_id"].to_numpy()
        uiv: dict[tuple[str, str], tuple[int, int]] = {}
        for i in range(len(unit)):
            k = (self.arquivo[i], unit[i])
            s, e = int(self.start[i]), int(self.end[i])
            if k in uiv:
                s0, e0 = uiv[k]
                uiv[k] = (min(s, s0), max(e, e0))
            else:
                uiv[k] = (s, e)
        self.unit_interval = uiv
        groups: dict[str, list[int]] = defaultdict(list)
        for i in np.flatnonzero(is_group):
            groups[self.arquivo[i]].append(int(i))
        self.groups_by_file = {f: np.array(v, dtype=np.int64) for f, v in groups.items()}
        self._cache: dict[tuple, Match] = {}

    # -- file selection (G3) ---------------------------------------------------------------------

    def article_files(self, doc: str, art: str) -> tuple[list[str], bool]:
        """Files of ``doc`` whose article ``art`` counts, and whether main and an annex both have it."""
        main = self.main_file.get(doc)
        have = sorted(f for f in self.files_of_doc.get(doc, ()) if art in self.articles_of_file.get(f, ()))
        in_main = main in have
        both = in_main and len(have) > 1
        if self.annex_rule == "main_first" and in_main:
            return [main], both
        return have, both

    def is_annex_a(self, files: list[str]) -> bool:
        return any(self.categoria.get(f) == "A" for f in files)

    # -- matching --------------------------------------------------------------------------------

    def _groups_containing(self, f: str, interval: tuple[int, int]) -> np.ndarray:
        g = self.groups_by_file.get(f)
        if g is None:
            return np.empty(0, dtype=np.int64)
        s, e = interval
        return g[(self.start[g] <= s) & (self.end[g] >= e)]

    def match(self, item: GoldItem) -> Match:
        k = (item.level, item.key)
        if k not in self._cache:
            self._cache[k] = getattr(self, f"_match_{item.level}")(item)
        return self._cache[k]

    def _match_document(self, item: GoldItem) -> Match:
        rows = self.rows_by_doc.get(item.document_id, np.empty(0, dtype=np.int64))
        return Match(full=rows, partial=np.empty(0, dtype=np.int64), units=[(item.document_id,)])

    def _match_article(self, item: GoldItem) -> Match:
        files, both = self.article_files(item.document_id, item.article_id)
        parts = []
        for f in files:
            parts.append(self.rows_by_article[(f, item.article_id)])
            parts.append(self._groups_containing(f, self.article_interval[(f, item.article_id)]))
        rows = np.unique(np.concatenate(parts)) if parts else np.empty(0, dtype=np.int64)
        return Match(full=rows, partial=np.empty(0, dtype=np.int64),
                     units=[(f, item.article_id) for f in files], main_and_annex=both)

    def _match_provision(self, item: GoldItem) -> Match:
        empty = np.empty(0, dtype=np.int64)
        frag, art = item.fragment_id, item.article_id
        if not frag or not item.lexml_file:
            return Match(full=empty, partial=empty, units=[])
        if self.annex_rule == "either":
            files, both = self.article_files(item.document_id, art)
            files = sorted(set(files) | {item.lexml_file})
        else:
            files, both = [item.lexml_file], False
        full, partial, parts = [], [], []
        for f in files:
            split_parts = []
            for i in self.rows_by_article.get((f, art), empty):
                if any(_is_prefix(c, frag) for c in self.cobre[i]):
                    full.append(i)
                elif any(_is_prefix(frag, c) for c in self.cobre[i]) or frag in self.parcial[i]:
                    partial.append(i)
                    if self.split[i]:
                        split_parts.append(i)
            if split_parts:
                parts.append(np.array(split_parts, dtype=np.int64))
            interval = self.unit_interval.get((f, frag)) or self.article_interval.get((f, art))
            if interval:
                full.extend(self._groups_containing(f, interval).tolist())
        return Match(full=np.unique(np.array(full, dtype=np.int64)),
                     partial=np.setdiff1d(np.array(partial, dtype=np.int64), full),
                     units=[(f, art) for f in files], main_and_annex=both, parts=parts)

    def only_ambiguous(self, rows: np.ndarray) -> bool:
        """True when ``rows`` is non-empty and every row has ``id_ambiguo = 1`` (G4)."""
        return len(rows) > 0 and bool(self.ambiguous[rows].all())

    # -- retrieval units (unit-projection view) --------------------------------------------------

    def units_of_rows(self, rows: np.ndarray, level: str) -> list[tuple]:
        """Distinct retrieval units of some chunks, in document order.

        Documents for ``document``; ``(arquivo, artigo_id)`` for ``article`` (a grouping chunk
        stands for every article it contains).
        """
        out: dict[tuple, int] = {}
        for i in rows:
            if level == "document":
                d = self.doc_of_row[i]
                out.setdefault((d,) if d is not None else ("?" + self.arquivo[i],), 0)
            elif self.is_group[i]:
                f = self.arquivo[i]
                arts = [(self.article_interval[(f, a)][0], a) for a in self.articles_of_file.get(f, ())
                        if self.start[i] <= self.article_interval[(f, a)][0]
                        and self.article_interval[(f, a)][1] <= self.end[i]]
                for s, a in sorted(arts):
                    out.setdefault((f, a), s)
            elif self.artigo[i]:
                out.setdefault((self.arquivo[i], self.artigo[i]), int(self.start[i]))
        return list(out)
