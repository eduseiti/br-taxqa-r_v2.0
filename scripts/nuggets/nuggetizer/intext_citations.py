"""In-text legal citations of the generated answers (A2; plan ``docs/20261122_134404_*``).

The generators write their legal basis in the answer text ("conforme o art. 8º, inciso II, da Lei nº 9.250,
de 1995"). This module extracts those citations claim by claim, resolves each cited act to a corpus document,
and scores them against the gold references, with validity checks and, for RAG answers, the comparison with
the sources each claim links to and with the context.

Pipeline:

1. **Acts** (:func:`find_acts`): numbered acts by regex (type + issuer + "nº" + number + date or year:
   ``Lei nº 9.250, de 1995``, ``Lei 7.713/88``, ``IN RFB nº 2.178/2024``, ``Solução de Consulta Cosit nº 12``…),
   named acts by an alias table (RIR/2018, CTN, Código Civil, Constituição…) and anaphors ("da mesma Lei",
   "do referido Decreto", "desta Instrução Normativa") that point back to the previous act of the same type.
   Each numbered act is resolved to a ``document_id`` of ``dataset/documents.jsonl`` by (type family, number,
   year); a well-formed act that is not in the corpus is kept as ``not_in_corpus``.
   Deviation from the plan: ``lexml-linker`` is not the resolver, because its spans merge the provision chain
   with the act and it misses the Receita Federal acts; it is run as a cross-check of the federal acts
   (:func:`linker_crosscheck`).
2. **Chains** (``scripts/dataset/citations.py``): ``find_chains`` / ``chain_units`` turn the provision text into
   nested LexML ids. A chain is attributed to an act as in ``citations.attribute``: one followed by "do/da <act>"
   to that act; otherwise to the closest act before it in the claim, else the closest after it; else to the last
   act of the previous claims of the same answer (``carried``). Chains with no article and no annex
   ("item 5", "Seção II") are kept only when they bind directly to an act ("item 3 da IN …").
3. **Scoring** (:func:`score_answer`): the cited units against the question's gold items
   (``ragpipe.relevance.gold_items``) at the document, article and provision levels (rules in
   :func:`unit_matches`).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "dataset"))
sys.path.insert(0, str(REPO / "scripts" / "rag"))
import citations as C  # noqa: E402

REFERENCE_DATE = "2024-05-03"      # date of the P&R IRPF 2024 v1.0
REVOKED = {   # document_id or (family, number) → note; acts revoked before the reference date
    "decreto_3000_19990326": "RIR/1999 (revoked by Decreto 9.580/2018)",
    ("decreto", "3000"): "RIR/1999 (revoked by Decreto 9.580/2018)",
    ("decreto", "1041"): "RIR/1994 (revoked)",
    ("decreto", "85450"): "RIR/1980 (revoked)",
    ("decreto", "76186"): "RIR/1975 (revoked)",
}

# ------------------------------------------------------------------ documents: (family, number, year) index

#: document_id prefix → type family
FAMILY_OF_PREFIX = [
    ("lei_comp_", "lei.complementar"), ("decreto_lei_", "decreto.lei"), ("decreto_legislativo_", "decreto.legislativo"),
    ("lei_", "lei"), ("decreto_", "decreto"), ("mp_", "mp"), ("in_", "in"),
    ("adi_", "ad"), ("adn_", "ad"), ("ade_", "ad"), ("ad_", "ad"),
    ("sci_", "sci"), ("sc_", "sc"), ("sd_", "sd"), ("pn_", "pn"),
    ("par_", "parecer"), ("parecer_", "parecer"), ("port_", "portaria"), ("resol_", "resolucao"),
    ("nota_", "nota"), ("sumula_", "sumula"), ("constitui", "constituicao"), ("circ_", "circular"),
]


def family_of_doc(doc_id: str) -> str | None:
    for p, f in FAMILY_OF_PREFIX:
        if doc_id.startswith(p):
            return f
    return None


def norm_number(s: str) -> str:
    """'9.250' → '9250'; '2.158-35' → '2158-35'; '0012' → '12'."""
    s = s.replace(".", "").replace(" ", "")
    base, _, suf = s.partition("-")
    base = base.lstrip("0") or "0"
    return f"{base}-{suf.lstrip('0') or '0'}" if suf else base


def norm_year(y: str | None) -> int | None:
    if not y:
        return None
    y = y.replace(".", "")
    if len(y) == 2:
        n = int(y)
        return 1900 + n if n >= 30 else 2000 + n
    n = int(y)
    return n if 1850 <= n <= 2100 else None


@dataclass
class DocIndex:
    """Corpus documents by (family, number) for act resolution, plus aliases and unit ids."""

    docs: dict[str, dict]
    by_key: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, docs: list[dict]) -> "DocIndex":
        ix = cls({d["document_id"]: d for d in docs})
        for d in docs:
            fam = family_of_doc(d["document_id"])
            urn = d.get("urn") or ""
            if not fam or ";" not in urn:
                continue
            num = norm_number(urn.rsplit(";", 1)[1])
            ix.by_key.setdefault((fam, num), []).append(d["document_id"])
        return ix

    def year_of(self, doc_id: str) -> int | None:
        urn = self.docs[doc_id].get("urn") or ""
        m = re.search(r":(\d{4})(?:-\d\d-\d\d)?;", urn)
        return int(m[1]) if m else None

    def date_of(self, doc_id: str) -> str | None:
        urn = self.docs[doc_id].get("urn") or ""
        m = re.search(r":(\d{4}(?:-\d\d-\d\d)?);", urn)
        return m[1] if m else None

    def resolve(self, fam: str, number: str, year: int | None, subtype: str | None = None) -> tuple[list[str], str]:
        """Candidate documents and a status: ``corpus`` (one), ``ambiguous`` (several), ``not_in_corpus``."""
        num = norm_number(number)
        cands = list(self.by_key.get((fam, num), []))
        if not cands and "-" not in num:     # "MP nº 2.158" for 2.158-35 (the reissue number left out)
            cands = [d for (f, n), ds in self.by_key.items() if f == fam and n.split("-")[0] == num for d in ds]
        if year is not None:
            cands = [d for d in cands if self.year_of(d) == year]
        if len(cands) > 1 and subtype:
            sub = [d for d in cands if d.startswith(subtype)]
            cands = sub or cands
        if not cands:
            return [], "not_in_corpus"
        return cands, ("corpus" if len(cands) == 1 else "ambiguous")


# ------------------------------------------------------------------ act mentions

MONTHS = r"janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
NUM = r"(?P<num>\d{1,3}(?:\.\d{3})+(?:-\d{1,3})?|\d{1,6}(?:-\d{1,3})?)"
DATE = (rf"(?:\s*,?\s*de\s+(?:(?P<day>\d{{1,2}})[º°o]?\s+de\s+(?P<month>{MONTHS})\s+de\s+)?(?P<year>\d{{4}}|\d\.\d{{3}})"
        rf"|\s*/\s*(?P<syear>\d{{4}}|\d{{2}})(?!\d))?")
NO = r"(?:\s*n[º°o.]?\s*[º°.]?\s*|\s+n[úu]mero\s+|\s+)"

#: (family, subtype-prefix for disambiguation, regex of the type words incl. the issuer)
TYPES = [
    ("lei.complementar", None, r"Lei\s+Complementar|LC"),
    ("decreto.lei", None, r"Decreto[\s-]+Lei|DL"),
    ("decreto.legislativo", None, r"Decreto\s+Legislativo"),
    ("lei", None, r"Lei(?:\s+Federal|\s+Ordin[áa]ria)?"),
    ("decreto", None, r"Decreto(?:\s+Federal)?"),
    ("mp", None, r"Medida\s+Provis[óo]ria|MP"),
    ("in", None, r"(?:Instru[çc][ãa]o\s+Normativa|IN)(?:\s+Conjunta)?(?:\s+(?:da\s+)?(?:RFB|SRF|SRFB|Secretaria\s+da\s+Receita\s+Federal(?:\s+do\s+Brasil)?|Receita\s+Federal(?:\s+do\s+Brasil)?)|\s+(?:RFB|SRF)/\w+)?"),
    ("ad", "adi_", r"(?:Ato\s+Declarat[óo]rio\s+Interpretativo|ADI)(?:\s+(?:RFB|SRF|Cosit|SRFB))?"),
    ("ad", "adn_", r"(?:Ato\s+Declarat[óo]rio\s+Normativo|ADN)(?:\s+(?:CST|Cosit|SRF))?"),
    ("ad", "ade_", r"(?:Ato\s+Declarat[óo]rio\s+Executivo|ADE)(?:\s+(?:RFB|SRF|Codac|Cosar|Cofis|Corat))?"),
    ("ad", "ad_", r"Ato\s+Declarat[óo]rio(?:\s+(?:PGFN|SRF|RFB|Cosar|Cosit|do\s+Procurador-Geral\s+da\s+Fazenda\s+Nacional))?"),
    ("sci", None, r"Solu[çc][ãa]o\s+de\s+Consulta\s+Interna(?:\s+(?:Cosit|SRF))?|SCI(?:\s+Cosit)?"),
    ("sd", None, r"Solu[çc][ãa]o\s+de\s+Diverg[êe]ncia(?:\s+Cosit)?"),
    ("sc", None, r"Solu[çc][ãa]o\s+de\s+Consulta(?:\s+(?:Cosit|Disit|SRRF\d*/?\w*|RFB))?|SC(?:\s+Cosit)"),
    ("pn", None, r"Parecer\s+Normativo(?:\s+(?:CST|Cosit|SRF|RFB))?|PN(?:\s+(?:CST|Cosit))?"),
    ("parecer", None, r"Parecer(?:\s+(?:PGFN(?:/\w+)*|Cosit|SEI|AGU))?"),
    ("portaria", None, r"Portaria(?:\s+(?:MF|ME|RFB|Conjunta|Interministerial|\w+/\w+))?"),
    ("resolucao", None, r"Resolu[çc][ãa]o(?:\s+(?:CMN|CGSN|TSE|CGPC|do\s+\w+))?"),
    ("nota", None, r"Nota(?:\s+(?:PGFN(?:/\w+)*|SEI|T[ée]cnica))?"),
    ("sumula", None, r"S[úu]mula(?:\s+(?:Vinculante|CARF|STJ|STF|do\s+(?:CARF|STJ|STF)))?"),
    ("emenda.constitucional", None, r"Emenda\s+Constitucional|EC"),
]
_TYPES_RE = "|".join(f"(?P<t{i}>{p})" for i, (_, _, p) in enumerate(TYPES))
ACT_RE = re.compile(rf"\b(?:{_TYPES_RE}){NO}{NUM}(?![\d])(?:{DATE})", re.I)
# all-caps abbreviations must be upper case in the text ("IN", "MP", "LC", "DL", "SC", "PN", "EC", "ADI"…)
_ABBREV = {"IN", "MP", "LC", "DL", "SC", "PN", "EC", "ADI", "ADN", "ADE", "SCI"}

#: aliases: regex → document_id (or None when the act is outside the corpus) and a family
ALIASES = [
    (r"RIR\s*/\s*(?:2018|18)\b|Regulamento\s+do\s+Imposto\s+(?:sobre\s+a|de)\s+Renda(?:\s+e\s+Proventos\s+de\s+Qualquer\s+Natureza)?\s*(?:\(\s*)?(?:[-–—,]\s*)?(?:RIR\s*)?(?:/\s*)?(?:,?\s*de\s+)?2018",
     "decreto_9580_20181122", "decreto"),
    (r"RIR\s*/\s*(?:1999|99)\b|Regulamento\s+do\s+Imposto\s+(?:sobre\s+a|de)\s+Renda\s*(?:\(\s*)?(?:[-–—,]\s*)?(?:RIR\s*)?(?:/\s*)?(?:,?\s*de\s+)?1999",
     "decreto_3000_19990326", "decreto"),
    (r"RIR\s*/\s*(?:1994|94)\b", "@decreto:1041:1994", "decreto"),
    (r"RIR\s*/\s*(?:1980|80)\b", "@decreto:85450:1980", "decreto"),
    (r"RIR\s*/\s*(?:1975|75)\b", "@decreto:76186:1975", "decreto"),
    # the regulation without a year: the one in force (RIR/2018); flagged as resolver "alias_default"
    (r"\bRIR\b(?!\s*/)|Regulamento\s+do\s+Imposto\s+(?:sobre\s+a|de)\s+Renda", "decreto_9580_20181122*", "decreto"),
    (r"C[óo]digo\s+Tribut[áa]rio\s+Nacional|\bCTN\b", "lei_5172_19661025", "lei"),
    (r"C[óo]digo\s+Civil|\bCC\b(?=\s*[,)]|\s+art)", "lei_10406_20020110", "lei"),
    (r"Constitui[çc][ãa]o(?:\s+Federal|\s+da\s+Rep[úu]blica(?:\s+Federativa\s+do\s+Brasil)?|\s+de\s+1988)(?:\s+de\s+1988)?|\bCF(?:/88|/1988)?\b",
     "constituição_1988_19881005", "constituicao"),
    (r"Estatuto\s+da\s+Pessoa\s+Idosa|Estatuto\s+do\s+Idoso", "@lei:10741:2003", "lei"),
    (r"Estatuto\s+da\s+Crian[çc]a\s+e\s+do\s+Adolescente|\bECA\b", "@lei:8069:1990", "lei"),
    (r"Consolida[çc][ãa]o\s+das\s+Leis\s+do\s+Trabalho|\bCLT\b", "@decreto.lei:5452:1943", "decreto.lei"),
    (r"C[óo]digo\s+de\s+Processo\s+Civil|\bCPC\b", "@lei:13105:2015", "lei"),
]
ALIAS_RE = [(re.compile(p, re.I), d, f) for p, d, f in ALIASES]
_CAPS_ALIAS = re.compile(r"(?:RIR|CTN|CC|CF|ECA|CLT|CPC)\b", re.I)

#: anaphors: "da mesma Lei", "dessa Instrução Normativa", "do referido Decreto", "do citado diploma"
_ANA_TYPES = {"lei.complementar": r"Lei\s+Complementar", "decreto.lei": r"Decreto[\s-]+Lei", "lei": r"Lei",
              "decreto": r"Decreto|Regulamento", "mp": r"Medida\s+Provis[óo]ria", "in": r"Instru[çc][ãa]o\s+Normativa|IN",
              "sc": r"Solu[çc][ãa]o\s+de\s+Consulta", "pn": r"Parecer\s+Normativo", "*": r"diploma|norma|ato|lei|c[óo]digo"}
ANAPHOR_RE = re.compile(
    r"\b(?:d[oa]s?\s+(?:mesm[oa]|referid[oa]|citad[oa]|aludid[oa]|mencionad[oa])|dess[ae]|dest[ae]|nest[ae]|ness[ae]|"
    r"pel[oa]\s+(?:mesm[oa]|referid[oa]|citad[oa]))\s+(?:" + "|".join(f"(?P<a_{k.replace('.', '_').replace('*', 'any')}>{p})"
                                                                     for k, p in _ANA_TYPES.items()) + r")\b", re.I)
#: a bare type word with no number ("da Lei", "do Decreto"): weak anaphor to the previous act of that type
BARE_RE = re.compile(r"\b(?:d[oa]|na|no|pel[oa])\s+(?P<w>Lei|Decreto|Instru[çc][ãa]o\s+Normativa|Medida\s+Provis[óo]ria)"
                     r"(?!\s*(?:[-\s]Lei\b|Complementar|Legislativo|n[º°o.]|\d|[A-Z]{2,}|Federal\s+n|Normativa\s+n))")
_FAMILY_OF_WORD = {"lei": "lei", "decreto": "decreto", "instrução normativa": "in", "instrucao normativa": "in",
                   "medida provisória": "mp", "medida provisoria": "mp"}


#: "com a redação dada pela Lei nº …", "incluído pela …": the act amended the cited one; not a citation itself
AMENDING_RE = re.compile(r"(?:reda[çc][ãa]o\s+dada|alterad[oa]s?|inclu[íi]d[oa]s?|acrescentad[oa]s?|acrescid[oa]s?|"
                         r"introduzid[oa]s?|revogad[oa]s?|modificad[oa]s?)\s+(?:\w+\s+){0,2}?pel[oa]s?\s+$", re.I)


@dataclass
class Act:
    start: int
    end: int
    text: str
    kind: str                      # numbered | alias | anaphor | bare
    family: str | None = None
    number: str | None = None
    year: int | None = None
    date: str | None = None        # YYYY-MM-DD when the day is written
    doc_id: str | None = None
    status: str = ""               # corpus | ambiguous | not_in_corpus | unresolved
    resolver: str = ""             # regex | alias | alias_default | anaphor | bare
    candidates: list[str] = field(default_factory=list)
    issuer: str = ""
    amending: bool = False         # "redação dada pela Lei nº …": skipped as a citation

    @property
    def act_key(self) -> str:
        """Identity of the act for reporting (document_id when resolved, else family:number:year)."""
        if self.doc_id:
            return self.doc_id
        return f"{self.family}:{norm_number(self.number) if self.number else '?'}:{self.year or '?'}"


_MONTH_N = {m: i + 1 for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                             "setembro", "outubro", "novembro", "dezembro"])}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def find_acts(text: str, ix: DocIndex) -> list[Act]:
    """Act mentions of a text, resolved, in order; anaphors left unresolved (see :func:`resolve_anaphors`)."""
    acts: list[Act] = []
    taken: list[tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return not any(s < b and a < e for a, b in taken)

    for m in ACT_RE.finditer(text):
        gi = next(i for i in range(len(TYPES)) if m[f"t{i}"])
        word = m[f"t{gi}"]
        head = word.split()[0].split("/")[0]
        if head.upper() in _ABBREV and head != head.upper():
            continue
        fam, sub, _ = TYPES[gi]
        if fam == "lei" and re.match(r"\d{1,2}$", m["num"]) and not (m["year"] or m["syear"]):
            continue                 # "Lei 13" without a year: likely not an act (low numbers are rare in IRPF)
        year = norm_year(m["year"] or m["syear"])
        date = None
        if m["day"] and m["month"] and year:
            mo = _MONTH_N.get(_fold(m["month"]).replace("marco", "março"), _MONTH_N.get(m["month"].lower()))
            if mo:
                date = f"{year:04d}-{mo:02d}-{int(m['day']):02d}"
        if fam == "pn" and "cst" in word.lower():
            sub = "pn_cst"
        elif fam == "pn" and "cosit" in word.lower():
            sub = "pn_cosit"
        elif fam == "in" and re.search(r"\bSRF\b|Secretaria da Receita Federal(?! do Brasil)", word):
            sub = "in_srf"
        elif fam == "in" and re.search(r"\bRFB\b|SRFB|do Brasil", word):
            sub = "in_rfb"
        cands, status = ix.resolve(fam, m["num"], year, sub)
        act = Act(m.start(), m.end(), m.group(), "numbered", fam, m["num"], year, date,
                  cands[0] if status == "corpus" else None, status, "regex", cands, issuer=word)
        act.amending = bool(AMENDING_RE.search(text[max(0, m.start() - 45):m.start()]))
        acts.append(act)
        taken.append((m.start(), m.end()))
    for rx, target, fam in ALIAS_RE:
        for m in rx.finditer(text):
            if not free(m.start(), m.end()):
                continue
            if _CAPS_ALIAS.match(m.group()) and not m.group()[:2].isupper():   # "cc", "eca" in running text
                continue
            resolver = "alias"
            if target.endswith("*"):
                target, resolver = target[:-1], "alias_default"
                # "Regulamento … (Decreto nº 3.000, de 1999)" / "aprovado pelo Decreto nº 9.580": the numbered act decides
                near = [a for a in acts if a.kind == "numbered" and 0 <= a.start - m.end() <= 60]
                if near:            # the mention belongs to the numbered act: one act from the regulation's name on
                    near[0].start = m.start()
                    taken.append((m.start(), m.end()))
                    continue
            if target.startswith("@"):
                f, num, y = target[1:].split(":")
                act = Act(m.start(), m.end(), m.group(), "alias", f, num, int(y), None, None, "not_in_corpus", resolver)
            else:
                act = Act(m.start(), m.end(), m.group(), "alias", fam, ix.docs[target].get("number"),
                          ix.year_of(target), ix.date_of(target), target, "corpus", resolver, [target])
            acts.append(act)
            taken.append((m.start(), m.end()))
    for m in ANAPHOR_RE.finditer(text):
        if not free(m.start(), m.end()):
            continue
        g = next(k for k, v in m.groupdict().items() if v)
        fam = {"a_any": None}.get(g, g[2:].replace("_", "."))
        acts.append(Act(m.start(), m.end(), m.group(), "anaphor", fam, resolver="anaphor", status="unresolved"))
        taken.append((m.start(), m.end()))
    for m in BARE_RE.finditer(text):
        s = m.start("w")
        if not free(s, m.end()):
            continue
        fam = _FAMILY_OF_WORD.get(_fold(m["w"]).replace("ç", "c"), _FAMILY_OF_WORD.get(m["w"].lower()))
        fam = fam or {"instrucao normativa": "in", "medida provisoria": "mp"}.get(_fold(m["w"]))
        acts.append(Act(s, m.end(), m["w"], "bare", fam, resolver="bare", status="unresolved"))
        taken.append((s, m.end()))
    acts.sort(key=lambda a: a.start)
    return acts


def resolve_anaphors(acts: list[Act], previous: list[Act]) -> None:
    """Point anaphors and bare type words to the previous resolved-or-numbered act of the same family
    (any family for "do mesmo diploma"), looking in this text first, then in ``previous`` (earlier claims)."""
    for i, a in enumerate(acts):
        if a.kind not in ("anaphor", "bare"):
            continue
        pool = [b for b in acts[:i] if b.kind in ("numbered", "alias") or b.status in ("corpus", "not_in_corpus", "ambiguous")]
        pool = previous + pool
        for b in reversed(pool):
            if b.kind in ("anaphor", "bare") and not b.family:
                continue
            if a.family is None or b.family == a.family or (a.family == "decreto" and b.doc_id == "decreto_9580_20181122"):
                a.family, a.number, a.year, a.date = b.family, b.number, b.year, b.date
                a.doc_id, a.status, a.candidates = b.doc_id, b.status, list(b.candidates)
                break


# ------------------------------------------------------------------ chains → acts

@dataclass
class Citation:
    """One cited unit (or one act cited without a provision) of one claim."""

    claim: int
    act: Act | None
    unit: C.Unit | None
    chain_text: str = ""
    binding: str = ""        # genitive | before | after | carried | act_only | none

    @property
    def article_id(self) -> str | None:
        return self.unit.article_id if self.unit else None

    fragment_override: str | None = None    # set by the scorer ("§ 1º" → parágrafo único, see canonical_fragment)

    @property
    def fragment_id(self) -> str | None:
        return self.fragment_override or (self.unit.fragment_id if self.unit else None)

    @property
    def annex(self) -> str | None:
        return self.unit.annex if self.unit else None


_GEN_LOOKAHEAD = re.compile(r"(?:\s+e\s+(?:seguintes|ss\.?))?\s*,?\s*(?:d[oa]s?|ao|à|n[oa]s?|pel[oa])\s+", re.I)


def _keep_chain(ch: C.Chain) -> bool:
    return any(r.kind == "art" or (r.kind == "anx" and r.key) for r in ch.refs)


def extract_claims(claims: list[str], ix: DocIndex) -> tuple[list[Citation], list[list[Act]]]:
    """Citations of the claims of one answer (claim order matters: carried acts and anaphors)."""
    out: list[Citation] = []
    all_acts: list[list[Act]] = []
    previous: list[Act] = []
    for ci, text in enumerate(claims):
        acts = find_acts(text, ix)
        resolve_anaphors(acts, previous)
        anchors = [a for a in acts if a.status in ("corpus", "ambiguous", "not_in_corpus") and not a.amending]
        used: set[int] = set()
        for ch in C.find_chains(text):
            gen = None
            g = _GEN_LOOKAHEAD.match(text, ch.end)
            if g:
                gen = next((a for a in acts if ch.end <= a.start <= g.end() + 25 and not a.amending), None)
            if not _keep_chain(ch) and gen is None:
                continue
            if gen is not None:
                act, binding = gen, "genitive"
            else:
                before = [a for a in anchors if a.end <= ch.start]
                after = [a for a in anchors if a.start >= ch.end]
                if before:
                    act, binding = before[-1], "before"
                elif after:
                    act, binding = after[0], "after"
                elif previous:
                    resolved_prev = [a for a in previous if a.status in ("corpus", "ambiguous", "not_in_corpus")]
                    act, binding = (resolved_prev[-1], "carried") if resolved_prev else (None, "none")
                else:
                    act, binding = None, "none"
            if act is not None:
                used.add(id(act))
            for u in C.chain_units(ch):
                out.append(Citation(ci, act, u, ch.text, binding))
        for a in anchors:          # acts cited without any provision: document-level citation
            done = {c.act.act_key for c in out if c.claim == ci and c.act}
            if id(a) not in used and a.kind in ("numbered", "alias") and a.act_key not in done:
                out.append(Citation(ci, a, None, "", "act_only"))
                used.add(id(a))
        previous = previous + [a for a in acts if a.status in ("corpus", "ambiguous", "not_in_corpus") and not a.amending]
        all_acts.append(acts)
    return out, all_acts


# ------------------------------------------------------------------ matching against gold

def _is_prefix(anc: str, desc: str) -> bool:
    return desc == anc or desc.startswith(anc + "_")


def unit_matches(cit: Citation, item, level: str, files_of_cit: set[str] | None) -> str | None:
    """``full`` / ``partial`` / ``None``: does a cited unit match a gold item at ``level``?

    - document: same document;
    - article: same article; the annex rule ``either`` (the citation names no file, so any file of the document
      counts) unless the citation names an annex and the gold item names other files;
    - provision: full when the cited fragment equals the gold fragment or is its ancestor (a coarser citation that
      contains the gold unit, the G5 analogue), partial when it is a descendant of it.
    """
    doc = cit.act.doc_id if cit.act else None
    if not doc or doc != item.document_id:
        return None
    if level == "document":
        return "full"
    art = cit.article_id
    if not art:
        return None
    if level == "article":
        if art != item.article_id:
            return None
        if files_of_cit and item.files and not (files_of_cit & item.files):
            return None
        return "full"
    frag, gfrag = cit.fragment_id, item.fragment_id
    if not frag or not gfrag:
        return None
    if files_of_cit and item.lexml_file and item.lexml_file not in files_of_cit:
        return None
    if _is_prefix(frag, gfrag):
        return "full"
    if _is_prefix(gfrag, frag):
        return "partial"
    return None


# ------------------------------------------------------------------ linker cross-check

def linker_urns(texts: list[str]) -> list[set[str]]:
    """``lexml-linker`` URNs (act part only) of each text; one process for all texts (one line each)."""
    inp = "\n".join(t.replace("\n", " ") for t in texts) + "\n"
    res = subprocess.run(["linkertool", "-x"], input=inp.encode(), capture_output=True, env={**os.environ, "LANG": "C.UTF-8"},
                         check=False)
    lines = res.stdout.decode("utf-8", "replace").split("\n")
    out = []
    for i in range(len(texts)):
        ln = lines[i] if i < len(lines) else ""
        out.append({u.split("!")[0] for u in re.findall(r'xlink:href="([^"]+)"', ln)})
    return out


def urn_key(urn: str) -> tuple[str, str, int | None] | None:
    """``urn:lex:br:federal:lei:2005;11196`` → ('lei', '11196', 2005)."""
    m = re.match(r"urn:lex:br:federal:([\w.]+):(\d{4})?[\d-]*;([\d-]+)", urn)
    if not m:
        return None
    fam = {"medida.provisoria": "mp"}.get(m[1], m[1])
    return fam, norm_number(m[3]), int(m[2]) if m[2] else None


# ------------------------------------------------------------------ scoring of one answer

class InTextScorer:
    """Gold, corpus unit ids and (for RAG answers) the chunk matcher, loaded once."""

    def __init__(self):
        from ragpipe.data import Paths, load_dataset
        from ragpipe.relevance import gold_items

        paths = Paths()
        ds = load_dataset(paths.dataset)
        self.ix = DocIndex.load(ds.documents.to_dict("records"))
        self.gold = gold_items(ds)
        self.file_to_doc = ds.file_to_document()
        self.main_file = {d: Path(f).name for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"]) if f}
        self.annex_files: dict[str, list[str]] = {
            d: [Path(f).name for f in fs] for d, fs in zip(ds.documents["document_id"], ds.documents["lexml_annex_files"])}
        ut = pd.read_csv(paths.unit_tokens, usecols=["arquivo", "unidade_id"], dtype=str)
        self.units_of_doc: dict[str, set[str]] = {}
        self.articles_of_doc: dict[str, set[str]] = {}
        for f, u in zip(ut.arquivo, ut.unidade_id):
            d = self.file_to_doc.get(f)
            if d is None:
                continue
            self.units_of_doc.setdefault(d, set()).add(u)
            if u.startswith("art") and "_" not in u:
                self.articles_of_doc.setdefault(d, set()).add(u)
        self.units_of_file: dict[tuple[str, str], bool] = {(f, u): True for f, u in zip(ut.arquivo, ut.unidade_id)}
        self._ps = None

    # -- corpus checks ---------------------------------------------------------------------------

    def files_of_citation(self, c: Citation) -> set[str] | None:
        """The file a citation names: an annex when the chain says "Anexo N" (by number); else ``None`` (either)."""
        if not c.act or not c.act.doc_id or not c.annex:
            return None
        m = re.search(r"(\d+|[IVXLC]+)\s*$", c.annex)
        if not m:
            return None
        n = m[1] if m[1].isdigit() else str(C.roman_to_int(m[1]))
        f = [x for x in self.annex_files.get(c.act.doc_id, []) if re.search(rf"\.anexo{n}\.xml$", x)]
        return set(f) or None

    def exists(self, c: Citation) -> tuple[object, object]:
        """(article exists, unit exists) in the cited document's LexML; ``None`` when it cannot be checked
        (no resolved document, no article, or a document without articles)."""
        d = c.act.doc_id if c.act else None
        if not d or not c.article_id or d not in self.articles_of_doc:
            return None, None
        art = c.article_id in self.articles_of_doc[d]
        if not c.fragment_id or c.fragment_id == c.article_id:
            return art, art
        units = self.units_of_doc[d]
        frag = c.fragment_id
        ok = frag in units or (frag.endswith("_cpt") and frag[:-4] in units)
        return art, ok

    def later(self, a: Act | None) -> object:
        """The act is dated after the reference date (``None`` when its date is unknown or ambiguous)."""
        if a is None or a.status == "unresolved":
            return None
        date = a.date or (self.ix.date_of(a.doc_id) if a.doc_id else None)
        if date and len(date) == 10:
            return date > REFERENCE_DATE
        y = a.year or (self.ix.year_of(a.doc_id) if a.doc_id else None)
        if y is None:
            return None
        if y > int(REFERENCE_DATE[:4]):
            return True
        if y < int(REFERENCE_DATE[:4]):
            return False
        return None

    @staticmethod
    def revoked(a: Act | None) -> bool:
        if a is None:
            return False
        if a.doc_id and a.doc_id in REVOKED:
            return True
        return bool(a.family and a.number and (a.family, norm_number(a.number)) in REVOKED)

    def canonical_fragment(self, doc: str | None, frag: str | None) -> tuple[str | None, bool]:
        """The cited fragment as a LexML id of the document: "§ 1º" of an article that has only a parágrafo único
        (``par1`` → ``par1u``) and the reverse. Returns (fragment, rewritten)."""
        units = self.units_of_doc.get(doc or "")
        if not frag or not units or frag in units:
            return frag, False
        for a, b in (("_par1u", "_par1"), ("_par1", "_par1u")):
            parts = frag.split("_")
            for i, p in enumerate(parts):
                if "_" + p == a:
                    alt = "_".join(parts[:i] + [b[1:]] + parts[i + 1:])
                    if alt in units:
                        return alt, True
        return frag, False

    # -- context mapping (§3.6) ------------------------------------------------------------------

    @property
    def ps(self):
        if self._ps is None:
            from nuggetizer.analysis import ProvisionScorer
            self._ps = ProvisionScorer()
        return self._ps

    def context_class(self, c: Citation, q: str, ctx_items: list[dict], src_n: set[int]) -> dict:
        """Per level (document, article, provision): ``in_sources`` / ``in_context_not_sources`` /
        ``outside_context``, or ``None`` when the citation has no unit at that level."""
        from ragpipe.relevance import GoldItem
        out = {}
        d = c.act.doc_id if c.act else None
        m = self.ps.inp.matcher
        rows_of = {it["n"]: {self.ps.row[x] for x in [it["chunk_id"], *it["alias_chunk_ids"]]} for it in ctx_items}
        for level in ("document", "article", "provision"):
            if level == "document":
                if c.act is None or c.act.status == "unresolved":
                    out[level] = None
                    continue
                if not d:
                    out[level] = "outside_context"
                    continue
                hit = {it["n"] for it in ctx_items if it["document_id"] == d}
            else:
                if not c.article_id or (level == "provision" and not c.fragment_id):
                    out[level] = None
                    continue
                if not d:
                    out[level] = "outside_context"
                    continue
                files = self.files_of_citation(c)
                if level == "article":
                    gi = GoldItem(q, "article", (d, c.article_id), d, "", article_id=c.article_id, files=files)
                else:
                    f = next(iter(files)) if files else self.main_file.get(d)
                    gi = GoldItem(q, "provision", (d, c.fragment_id, f), d, "", article_id=c.article_id,
                                  fragment_id=c.fragment_id, lexml_file=f)
                mt = m.match(gi)
                rows = set(mt.full.tolist()) | set(mt.partial.tolist())
                hit = {n for n, rs in rows_of.items() if rs & rows}
            out[level] = "in_sources" if hit & src_n else ("in_context_not_sources" if hit else "outside_context")
        return out

    # -- one answer ------------------------------------------------------------------------------

    def answer(self, ln: dict, ctx_line: dict | None) -> tuple[list[dict], list[dict]]:
        """Citation rows and per-level answer rows of one answer line."""
        q = ln["question_number"]
        answered = ln["status"] == "ok" and not ln.get("abstained")
        claims = ln.get("claims") or [] if answered else []
        cits, _ = extract_claims([c.get("texto") or "" for c in claims], self.ix)
        gold = self.gold.get(q)
        crow = []
        for c in cits:
            a = c.act
            rewritten = False
            if c.unit is not None and a is not None:
                frag, rewritten = self.canonical_fragment(a.doc_id, c.unit.fragment_id)
                if rewritten:
                    c.fragment_override = frag
            files = self.files_of_citation(c)
            m = {}
            for level in ("document", "article", "provision"):
                best = None
                for it in (gold or {}).get(level, []):
                    r = unit_matches(c, it, level, files)
                    if r == "full" or (r and best is None):
                        best = r
                    if best == "full":
                        break
                m[level] = best
            art_ok, unit_ok = self.exists(c)
            row = {"question_number": q, "claim": c.claim, "binding": c.binding, "chain": c.chain_text,
                   "act_text": a.text if a else "", "act_kind": a.kind if a else "", "resolver": a.resolver if a else "",
                   "act_status": a.status if a else "no_act", "act_key": a.act_key if a and a.status != "unresolved" else "",
                   "document_id": a.doc_id if a else None, "act_year": a.year if a else None,
                   "unit": c.unit.label if c.unit else "", "article_id": c.article_id, "fragment_id": c.fragment_id,
                   "par_unico_rewrite": rewritten, "annex": c.annex, "files": ";".join(sorted(files)) if files else "", "has_gold": gold is not None,
                   "match_document": m["document"], "match_article": m["article"], "match_provision": m["provision"],
                   "article_exists": art_ok, "unit_exists": unit_ok, "later": self.later(a), "revoked": self.revoked(a)}
            if ctx_line is not None and ctx_line.get("items"):
                src = {f.get("documento") for f in (claims[c.claim].get("fundamentos") or []) if isinstance(f, dict)}
                cc = self.context_class(c, q, ctx_line["items"], src)
                row.update({f"ctx_{k}": v for k, v in cc.items()})
            crow.append(row)
        arows = []
        attributed = [r for r in crow if r["act_key"]]
        for level, (key_cols, need) in {"document": (("act_key",), None), "article": (("act_key", "article_id"), "article_id"),
                                        "provision": (("act_key", "fragment_id"), "fragment_id")}.items():
            units: dict[tuple, dict] = {}
            for r in attributed:
                if need and not r[need]:
                    continue
                k = tuple(r[c] for c in key_cols)
                u = units.setdefault(k, {"match": None, "in_corpus": r["act_status"] in ("corpus", "ambiguous")})
                if r[f"match_{level}"] == "full" or (r[f"match_{level}"] and u["match"] is None):
                    u["match"] = r[f"match_{level}"]
            gl = (gold or {}).get(level, [])
            full = partial = 0
            for it in gl:
                best = None
                for r in attributed:
                    rr = unit_matches(_RowCit(r), it, level, set(r["files"].split(";")) if r["files"] else None)
                    if rr == "full":
                        best = "full"
                        break
                    best = best or rr
                full += best == "full"
                partial += best == "partial"
            n_u = len(units)
            n_ok = sum(1 for u in units.values() if u["match"] == "full")
            n_any = sum(1 for u in units.values() if u["match"])
            in_c = [u for u in units.values() if u["in_corpus"]]
            arows.append({"question_number": q, "answered": answered, "level": level, "n_gold": len(gl),
                          "has_gold": gold is not None, "n_cited": n_u, "n_cited_in_corpus": len(in_c),
                          "n_unattributed": sum(1 for r in crow if not r["act_key"] and (r["article_id"] or level == "document")),
                          "cited_recall": full / len(gl) if gl else np.nan,
                          "cited_recall_any": (full + partial) / len(gl) if gl else np.nan,
                          "cited_any": float(full > 0) if gl else np.nan,
                          "cited_precision": n_ok / n_u if n_u and gl else np.nan,
                          "cited_precision_any": n_any / n_u if n_u and gl else np.nan,
                          "cited_precision_in_corpus": (sum(1 for u in in_c if u["match"] == "full") / len(in_c)
                                                        if in_c and gl else np.nan)})
        return crow, arows


class _RowCit:
    """A citation row seen as a :class:`Citation` for :func:`unit_matches` (recall pass)."""

    def __init__(self, r: dict):
        self.act = type("A", (), {"doc_id": r["document_id"]})()
        self.article_id, self.fragment_id = r["article_id"], r["fragment_id"]




# ------------------------------------------------------------------ runs

def answer_runs(answers_root: Path) -> list[tuple[str, Path]]:
    """(run_id, run dir) of every generated run under ``runs/answers/<embedding>/<instruction>/<prompt>/<llm>/<ctx>``."""
    out = []
    for f in sorted(answers_root.glob("*/*/*/*/*/answers.jsonl")):
        rd = f.parent
        out.append((str(rd.relative_to(answers_root)), rd))
    return out


def score_runs(runs: list[tuple[str, Path]], sc: InTextScorer, qids: set[str] | None = None,
               context_key=lambda r: r.split("/")[-1], log=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Citation rows and answer rows of all runs (no API calls)."""
    import json
    cit, ans, ctx_cache = [], [], {}
    for run_id, rd in runs:
        run = json.loads((rd / "run.json").read_text())
        cpath = (run.get("context") or {}).get("path")
        ctx = None
        if cpath:
            cfile = REPO / Path(cpath).parent / "contexts.jsonl.gz"
            if cfile not in ctx_cache:
                import gzip
                ctx_cache[cfile] = {x["question_number"]: x for x in map(json.loads, gzip.open(cfile, "rt"))}
            ctx = ctx_cache[cfile]
        cid = context_key(run_id)
        if cid == "closed_book":
            ctx = None
        meta = {"run_id": run_id, "llm": run["llm"]["name"], "context_id": cid, "rag": ctx is not None}
        n = 0
        for x in (REPO / rd / "answers.jsonl").read_text().split("\n"):
            if not x.strip():
                continue
            ln = json.loads(x)
            if (qids and ln["question_number"] not in qids) or ln["status"] == "skipped":
                continue
            c, a = sc.answer(ln, ctx.get(ln["question_number"]) if ctx else None)
            cit += [{**meta, **r} for r in c]
            ans += [{**meta, **r} for r in a]
            n += 1
        log(f"  {run_id}: {n} answers")
    return pd.DataFrame(cit), pd.DataFrame(ans)


def run_summary(cit: pd.DataFrame, ans: pd.DataFrame) -> pd.DataFrame:
    """Per run × level: citation rate, cited recall / precision / @any, resolver coverage, validity, context class."""
    rows = []
    keys = ["run_id", "llm", "context_id", "rag"]
    for k, g in ans.groupby(keys):
        c = cit[(cit.run_id == k[0])] if len(cit) else cit
        answered = g[g.answered & (g.level == "document")]
        n_ans = len(answered)
        for level, h in g[g.answered].groupby("level"):
            hg = h[h.has_gold]
            citing = hg[hg.n_cited > 0]
            r = {**dict(zip(keys, k)), "level": level, "n_answers": n_ans,
                 "citation_rate": float((h.n_cited > 0).mean()) if len(h) else np.nan,
                 "n_cited_mean": h.n_cited.mean(),
                 "n_gold_answers": len(hg),
                 "recall_all": hg.cited_recall.mean(), "recall_any_all": hg.cited_recall_any.mean(),
                 "cited_any_all": hg.cited_any.mean(),
                 "n_citing": len(citing), "recall_citing": citing.cited_recall.mean(),
                 "precision_citing": citing.cited_precision.mean(),
                 "precision_any_citing": citing.cited_precision_any.mean(),
                 "precision_in_corpus_citing": citing.cited_precision_in_corpus.mean()}
            rows.append(r)
        if not len(c):
            continue
        # citation-level shares (all questions), on top of the document-level row
        acts = c[c.act_status != "no_act"]
        art = c[c.article_id.notna()]
        chk = art[art.article_exists.notna()]
        r = rows[-3] if rows and rows[-3]["level"] == "document" else None
        extra = {"n_citations": len(c),
                 "attributed": float((c.act_key != "").mean()),
                 "resolved_corpus": float(c.act_status.isin(["corpus"]).mean()),
                 "not_in_corpus": float((acts.act_status == "not_in_corpus").mean()) if len(acts) else np.nan,
                 "unattributed": float((c.act_key == "").mean()),
                 "article_missing": float((chk.article_exists == False).mean()) if len(chk) else np.nan,  # noqa: E712
                 "unit_missing": float((chk.unit_exists == False).mean()) if len(chk) else np.nan,  # noqa: E712
                 "later": float((c.later == True).sum() / max(1, c.later.notna().sum())),  # noqa: E712
                 "later_n": int((c.later == True).sum()),  # noqa: E712
                 "revoked": float(c.revoked.mean()),
                 "answers_with_later": float(c[c.later == True].groupby("question_number").size().size / max(1, n_ans)),  # noqa: E712
                 }
        for lv in ("document", "article", "provision"):
            col = f"ctx_{lv}"
            if col in c and c[col].notna().any():
                v = c[col].dropna()
                for cls in ("in_sources", "in_context_not_sources", "outside_context"):
                    extra[f"{lv}_{cls}"] = float((v == cls).mean())
        for rr in rows:
            if rr["run_id"] == k[0] and rr["level"] == "document":
                rr.update(extra)
    return pd.DataFrame(rows)


def quality_link(ans: pd.DataFrame, pq: pd.DataFrame) -> pd.DataFrame:
    """§3.7: V_strict of answers by what they cite at the article level (questions with gold, answered)."""
    a = ans[(ans.level == "article") & ans.has_gold & ans.answered][["run_id", "question_number", "n_cited",
                                                                       "cited_any", "cited_recall"]]
    m = a.merge(pq[["run_id", "llm", "context_id", "question_number", "V_strict"]], on=["run_id", "question_number"])
    rows = []
    for (llm, cid), g in m.groupby(["llm", "context_id"]):
        grp = {"no_citation": g.n_cited == 0, "only_wrong": (g.n_cited > 0) & (g.cited_any == 0),
               "right": g.cited_any == 1}
        r = {"llm": llm, "context_id": cid, "n": len(g)}
        for k, b in grp.items():
            r[f"n_{k}"], r[f"V_strict_{k}"] = int(b.sum()), g.V_strict[b].mean()
        c = g[g.n_cited > 0]
        r["spearman_recall_V_strict_citing"] = (c.cited_recall.corr(c.V_strict, method="spearman")
                                                 if len(c) > 2 else np.nan)
        rows.append(r)
    return pd.DataFrame(rows)


def linker_crosscheck(texts: list[str], ix: DocIndex, n_examples: int = 30) -> tuple[dict, list[dict]]:
    """Federal acts found by ``lexml-linker`` vs the regex/alias detector, per claim (act family + number)."""
    fed = {"lei", "decreto", "decreto.lei", "mp", "lei.complementar", "constituicao"}
    texts = [t for t in texts if t.strip()]
    counts = {"both": 0, "linker_only": 0, "regex_only": 0, "regex_only_alias": 0}
    ex = []
    for t, urns in zip(texts, linker_urns(texts)):
        lk = {k[:2] for k in map(urn_key, urns) if k and k[0] in fed}
        acts = [a for a in find_acts(t, ix) if a.family in fed and a.number and a.kind in ("numbered", "alias")]
        rg = {(a.family, norm_number(a.number)) for a in acts}
        alias = {(a.family, norm_number(a.number)) for a in acts if a.kind == "alias"}
        for k in lk | rg:
            tag = "both" if k in lk and k in rg else ("linker_only" if k in lk else
                                                       ("regex_only_alias" if k in alias else "regex_only"))
            counts[tag] += 1
            if tag in ("linker_only", "regex_only") and len(ex) < n_examples:
                ex.append({"tag": tag, "act": ":".join(k), "text": t[:300]})
    return counts, ex
