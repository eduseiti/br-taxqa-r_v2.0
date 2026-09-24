"""Shared code for the segmentation pipeline (plan §2).

- LexML helpers (namespace, local names, XPath string()/normalize-space() equivalents);
- chunk-text rules mirrored from segmenta_estatutario.xsl: ``texto``, ``caminho``, ``tabela``,
  ``rotulo`` (parity-tested against the XSL output);
- ``calculaPos`` interval numbering in Python (``Positions``);
- document metadata for the ``[ METADADOS ]`` prefix (``metadata_for``);
- the pluggable tokenizer (``Tokenizer``);
- CSV reading/writing with the ``Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn`` schema.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

csv.field_size_limit(sys.maxsize)

REPO = Path(__file__).resolve().parents[2]
LEXML_DIR = REPO / "lexml"
ART_DIR = LEXML_DIR / "articulados"
NAO_DIR = LEXML_DIR / "nao_articulados"
SEG_DIR = REPO / "segmented"

NS = "http://www.lexml.gov.br/1.0"
NSMAP = {"l": NS}
CSV_COLS = ["Tipo", "Rotulo", "Num_Inicio", "Num_Final", "Texto", "urn"]

DISPOSITIVOS = ("Artigo", "Caput", "Paragrafo", "Inciso", "Alinea", "Item")
ORPHAN_TYPES = ("Caput", "Paragrafo", "Inciso", "Alinea", "Item")
AGRUPADORES = ("Parte", "Livro", "Titulo", "Subtitulo", "Capitulo", "Secao", "Subsecao")
# elements counted by calculaPos (13 types)
POS_TYPES = frozenset(DISPOSITIVOS + AGRUPADORES)
TEXT_TAGS = frozenset(("Rotulo", "TituloDispositivo", "NomeAgrupador", "p", "table"))
TIPO_OF = {"Parte": "PRT", "Livro": "LIV", "Titulo": "TIT", "Subtitulo": "SBT", "Capitulo": "CAP",
           "Secao": "SEC", "Subsecao": "SSC", "Artigo": "ART", "Caput": "CPT", "Paragrafo": "PAR",
           "Inciso": "INC", "Alinea": "ALI", "Item": "ITE"}
DEFAULT_TOKENIZER = "max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_EMENTA_MAX_TOKENS = 128
ANEXO_RE = re.compile(r"\.anexo(\d+)$", re.IGNORECASE)

_WS = re.compile(r"[\x20\t\n\r]+")


# --------------------------------------------------------------------------------------------
# XML helpers
# --------------------------------------------------------------------------------------------

def L(e) -> str | None:
    """Local name of an element (None for comments / PIs)."""
    tag = e.tag
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


def norm(s: str) -> str:
    """XPath normalize-space(): only XML whitespace (#x20 #x9 #xD #xA) is collapsed."""
    return _WS.sub(" ", s).strip("\x20\t\n\r")


def xstring(e) -> str:
    """XPath string(): concatenated text nodes of the subtree (comments excluded)."""
    return "".join(e.xpath(".//text()"))


def parse(path: Path | str):
    return etree.parse(str(path), etree.XMLParser(remove_blank_text=False, huge_tree=True))


def doc_urn(tree) -> str:
    r = tree.xpath("/l:LexML/l:Metadado[1]/l:Identificacao[1]/@URN", namespaces=NSMAP)
    return str(r[0]) if r else ""


def in_alteracao(e) -> bool:
    return any(L(a) == "Alteracao" for a in e.iterancestors())


def disp_ancestors(e) -> list:
    """Dispositivo ancestors of e, outermost first."""
    return [a for a in reversed(list(e.iterancestors())) if L(a) in DISPOSITIVOS]


def has_disp_ancestor(e) -> bool:
    return any(L(a) in DISPOSITIVOS for a in e.iterancestors())


def child_elems(e, *names):
    return [c for c in e if L(c) in names]


# --------------------------------------------------------------------------------------------
# Chunk text rules (Python mirror of segmenta_estatutario.xsl)
# --------------------------------------------------------------------------------------------

def tabela_rows(t) -> list[str]:
    return [" | ".join(norm(xstring(td)) for td in child_elems(tr, "td"))
            for tr in t.iter(f"{{{NS}}}tr")]


def tabela(t) -> str:
    """lx:tabela: 'Tabela: ' + rows (' ; ') of cells (' | ')."""
    return norm("Tabela: " + " ; ".join(tabela_rows(t)))


def texto_parts(n) -> list[str]:
    parts = []
    for x in n.iter():
        name = L(x)
        if name not in TEXT_TAGS:
            continue
        if any(L(a) == "table" for a in x.iterancestors()):
            continue
        parts.append(tabela(x) if name == "table" else norm(xstring(x)))
    return parts


def texto(n) -> str:
    """lx:texto: own Rotulo/TituloDispositivo/NomeAgrupador/p/table + all descendants, doc order."""
    return norm(" ".join(texto_parts(n)))


def own_parts(a) -> list[str]:
    """Rotulo, TituloDispositivo and own p of a dispositivo (its 'opening' in the ancestor path)."""
    return [norm(xstring(x)) for x in a if L(x) in ("Rotulo", "TituloDispositivo", "p")]


def in_article_paragraph(n) -> bool:
    return any(L(a) == "Paragrafo" and L(a.getparent()) == "Artigo"
               for a in [n, *n.iterancestors()])


def caminho_parts(n, include_self: bool = False) -> list[str]:
    """lx:caminho: path of the dispositivo ancestors of n (plus n itself if include_self)."""
    ancs = disp_ancestors(n)
    if include_self:
        ancs = ancs + [n]
    em_par = in_article_paragraph(n)
    parts: list[str] = []
    for a in ancs:
        parts += own_parts(a)
        if em_par and L(a) == "Artigo":
            for cpt in child_elems(a, "Caput"):
                parts += [norm(xstring(p)) for p in child_elems(cpt, "p")]
    return parts


def caminho(n) -> str:
    return norm(" ".join(caminho_parts(n)))


def prefixo(meta: str) -> str:
    meta = norm(meta)
    return f"[ {meta} ] " if meta else "[ ] "


def row_text(n, meta: str) -> str:
    """Texto column of an XSL row for element n."""
    return prefixo(meta) + norm(caminho(n) + " " + texto(n))


_CURTO = re.compile(r"^\s*([^\s–—\-).]+).*$")


def curto(r: str) -> str:
    r = norm(r)
    m = _CURTO.match(r)
    return m.group(1) if m else r


def _rotulo_of(e) -> str:
    r = child_elems(e, "Rotulo")
    return xstring(r[0]) if r else ""


def componente(d) -> str:
    name = L(d)
    if name == "Caput":
        return "caput"
    if name == "Inciso":
        return "Inciso " + curto(_rotulo_of(d))
    if name == "Alinea":
        return "Alínea " + curto(_rotulo_of(d))
    if name == "Item":
        return "Item " + curto(_rotulo_of(d))
    return norm(_rotulo_of(d))


def rotulo(n, sigla: str) -> str:
    """lx:rotulo: sigla + grouping path (groupings) or dispositivo path (dispositivos)."""
    chain = [*reversed(list(n.iterancestors())), n]
    if L(n) in AGRUPADORES:
        parts = [norm(_rotulo_of(g)) for g in chain if L(g) in AGRUPADORES]
    else:
        parts = [componente(d) for d in chain if L(d) in DISPOSITIVOS]
    return ", ".join([sigla] + [p for p in parts if p])


def citacao(n) -> str:
    """Citation-style path, e.g. 'Art. 8º, caput, II, b, 10' (provenance column)."""
    chain = [*reversed(list(n.iterancestors())), n]
    if L(n) in AGRUPADORES:
        return ", ".join(norm(_rotulo_of(g)) for g in chain if L(g) in AGRUPADORES)
    out = []
    for d in chain:
        name = L(d)
        if name not in DISPOSITIVOS:
            continue
        if name == "Caput":
            out.append("caput")
        elif name in ("Inciso", "Alinea", "Item"):
            c = curto(_rotulo_of(d))
            top = not has_disp_ancestor(d)
            out.append(f"{ {'Inciso': 'Inciso', 'Alinea': 'Alínea', 'Item': 'Item'}[name]} {c}" if top else c)
        else:
            out.append(norm(_rotulo_of(d)))
    return ", ".join(o for o in out if o)


def agrupadores(n) -> tuple[list[str], list[str]]:
    """(ids, 'ROTULO – NOME' labels) of the enclosing statutory groupings, outermost first."""
    ids, labels = [], []
    for g in reversed(list(n.iterancestors())):
        if L(g) in AGRUPADORES:
            ids.append(g.get("id", ""))
            nome = child_elems(g, "NomeAgrupador")
            lab = norm(_rotulo_of(g))
            if nome:
                lab = " – ".join(x for x in (lab, norm(xstring(nome[0]))) if x)
            labels.append(lab)
    return ids, labels


# --------------------------------------------------------------------------------------------
# XSL row selection (which elements get which Tipo) — mirrors the xsl:for-each order
# --------------------------------------------------------------------------------------------

def xsl_row_elements(tree) -> list[tuple[str, object]]:
    """[(Tipo, element)] in the exact order the amended XSL emits its rows."""
    root = tree.getroot()
    live = [e for e in root.iter() if L(e) is not None and not in_alteracao(e)]
    by = {}
    for e in live:
        by.setdefault(L(e), []).append(e)
    out = []
    for c in by.get("Caput", []):
        art = c.getparent()
        if L(art) == "Artigo" and any(L(x) == "Paragrafo" for x in art):
            out.append(("CPT", c))
    out += [("PAR", e) for e in by.get("Paragrafo", []) if has_disp_ancestor(e)]
    out += [("ART", e) for e in by.get("Artigo", [])]
    out += [("DSP", e) for e in live if L(e) in ORPHAN_TYPES and not has_disp_ancestor(e)]
    for g in AGRUPADORES:
        out += [(TIPO_OF[g], e) for e in by.get(g, [])]
    for t in ("Inciso", "Alinea", "Item"):
        out += [(TIPO_OF[t], e) for e in by.get(t, []) if has_disp_ancestor(e)]
    return out


def top_orphans(tree) -> list:
    return [e for e in tree.getroot().iter() if L(e) in ORPHAN_TYPES and not in_alteracao(e)
            and not has_disp_ancestor(e)]


# --------------------------------------------------------------------------------------------
# calculaPos in Python
# --------------------------------------------------------------------------------------------

class Positions:
    """calculaPos numbers for any element: start = 2*before - anc + 1, end = start + 2*desc + 1,
    where before/anc/desc count the 13 POS_TYPES elements outside Alteracao that start before /
    enclose / are enclosed by the element (before includes the ancestors)."""

    def __init__(self, tree):
        self._pos: dict = {}
        counter = 0
        stack: list = []  # (element, counted_before_at_entry, counted_ancestors)

        def counted(e) -> bool:
            return L(e) in POS_TYPES and not in_alteracao(e)

        def visit(e, anc):
            nonlocal counter
            before = counter
            is_c = counted(e)
            if is_c:
                counter += 1
            for c in e:
                if isinstance(c.tag, str):
                    visit(c, anc + (1 if is_c else 0))
            desc = counter - before - (1 if is_c else 0)
            start = 2 * before - anc + 1
            self._pos[e] = (start, start + 2 * desc + 1)

        sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
        visit(tree.getroot(), 0)

    def __getitem__(self, e) -> tuple[int, int]:
        return self._pos[e]


# --------------------------------------------------------------------------------------------
# Tokenizer (plan §5.4)
# --------------------------------------------------------------------------------------------

class Tokenizer:
    """``chars:N`` | ``tiktoken:<encoding>`` | ``hf:<model>`` | ``max:<spec>,<spec>,...``.

    ``count`` is cached per text. ``count_many`` batches uncached texts."""

    def __init__(self, spec: str = DEFAULT_TOKENIZER):
        self.spec = spec
        self._cache: dict[str, int] = {}
        if spec.startswith("max:"):
            self.children = [Tokenizer(s) for s in _split_specs(spec[4:])]
            self.kind = "max"
        elif spec.startswith("chars:"):
            self.kind, self.div = "chars", float(spec.split(":", 1)[1] or 4)
        elif spec.startswith("tiktoken:"):
            import tiktoken
            self.kind, self.enc = "tiktoken", tiktoken.get_encoding(spec.split(":", 1)[1])
        elif spec.startswith("hf:"):
            self.kind = "hf"
            self.tok = _load_hf(spec.split(":", 1)[1])
        else:
            raise ValueError(f"unknown tokenizer spec {spec!r}")

    def leaves(self) -> list["Tokenizer"]:
        return [lf for c in self.children for lf in c.leaves()] if self.kind == "max" else [self]

    def _raw_many(self, texts: list[str]) -> list[int]:
        if self.kind == "chars":
            return [int(-(-len(t) // self.div)) for t in texts]
        if self.kind == "tiktoken":
            return [len(x) for x in self.enc.encode_ordinary_batch(texts)]
        if self.kind == "hf":
            out = []
            for i in range(0, len(texts), 256):
                out += [len(x.ids) for x in self.tok.encode_batch(texts[i:i + 256], add_special_tokens=False)]
            return out
        per = [c.count_many(texts) for c in self.children]
        return [max(v) for v in zip(*per)]

    def count_many(self, texts: list[str]) -> list[int]:
        todo = list({t for t in texts if t not in self._cache})
        if todo:
            for t, n in zip(todo, self._raw_many(todo)):
                self._cache[t] = n
        return [self._cache[t] for t in texts]

    def count(self, text: str) -> int:
        n = self._cache.get(text)
        if n is None:
            n = self._raw_many([text])[0]
            self._cache[text] = n
        return n

    def clear_cache(self) -> None:
        self._cache.clear()
        if self.kind == "max":
            for c in self.children:
                c.clear_cache()


class _HFAdapter:
    """transformers tokenizer behind the tokenizers.Tokenizer.encode_batch interface."""

    def __init__(self, tok):
        self.tok = tok

    def encode_batch(self, texts, add_special_tokens=False):
        from types import SimpleNamespace
        ids = self.tok(list(texts), add_special_tokens=add_special_tokens)["input_ids"]
        return [SimpleNamespace(ids=x) for x in ids]


def _load_hf(name: str):
    """The model's tokenizer.json through the light `tokenizers` library (same counts as the
    transformers fast tokenizer, checked on 3,000 chunks; importing transformers takes ~12 s per
    process on this filesystem). Cached files first: parallel workers must not all hit the HF Hub.
    Falls back to transformers when the model has no tokenizer.json."""
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer as _Tk
    for local in (True, False):
        try:
            return _Tk.from_file(hf_hub_download(name, "tokenizer.json", local_files_only=local))
        except Exception:  # noqa: BLE001
            continue
    import logging
    logging.getLogger("transformers").setLevel(logging.ERROR)
    from transformers import AutoTokenizer
    return _HFAdapter(AutoTokenizer.from_pretrained(name))


def _split_specs(s: str) -> list[str]:
    """'tiktoken:cl100k_base,hf:Qwen/X' -> ['tiktoken:cl100k_base', 'hf:Qwen/X']."""
    out, cur = [], ""
    for piece in s.split(","):
        if re.match(r"^(chars|tiktoken|hf|max):", piece) or not cur:
            if cur:
                out.append(cur)
            cur = piece
        else:
            cur += "," + piece
    if cur:
        out.append(cur)
    return out


@functools.lru_cache(maxsize=4)
def get_tokenizer(spec: str = DEFAULT_TOKENIZER) -> Tokenizer:
    return Tokenizer(spec)


def truncate_tokens(text: str, max_tokens: int, tok: Tokenizer) -> tuple[str, bool]:
    """Cut text at a word boundary so that it has <= max_tokens (with ' …' appended)."""
    if tok.count(text) <= max_tokens:
        return text, False
    words = text.split(" ")
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tok.count(" ".join(words[:mid]) + " …") <= max_tokens:
            lo = mid
        else:
            hi = mid - 1
    return " ".join(words[:lo]) + " …", True


# --------------------------------------------------------------------------------------------
# Metadata (plan §2.3)
# --------------------------------------------------------------------------------------------

CAMARA_RE = re.compile(r"^\s*C[ÂA]MARA DOS DEPUTADOS\s+Centro de Documenta[çc][ãa]o e Informa[çc][ãa]o\s*",
                       re.IGNORECASE)
TITLE_LIKE_RE = re.compile(r"^(solu[çc][ãa]o|parecer|ato|portaria|instru[çc][ãa]o|nota|s[úu]mula|"
                           r"ac[óo]rd[ãa]o|decreto|lei|despacho|resolu[çc][ãa]o)\b", re.IGNORECASE)


def clean_meta(s: str) -> str:
    return norm(s.replace("[", "(").replace("]", ")"))


def _canon(s: str) -> str:
    return re.sub(r"[^\w]", "", s).lower()


# Planalto / Câmara page furniture found at the start of ementas (checked on all 224 main docs)
EMENTA_NOISE = [re.compile(p, re.IGNORECASE) for p in (
    r"^\d{1,2}\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})",                 # page number before the epígrafe
    r"^Texto compilado", r"^Texto original", r"^Texto para impress[ãa]o",
    r"^Vig[êe]ncia", r"^\(Altera[çc][õo]es de anexos\)", r"^Exposi[çc][ãa]o de motivos",
    r"^Mensagem de veto", r"^all_inclusive", r"^Regulamenta[çc][ãa]o(?=\s*[A-Z])",
    r"^Produ[çc][ãa]o de efeitos?", r"^Sem efic[áa]cia",
    r"^Convertid[ao] n[ao] Lei n[ºo°]\s*[\d.]+, de \d{4}",
    r"^Revogad[oa] pel[oa] .{0,80}?, de \d{4}",
    r"^\(Vide [^)]*\)", r"^Vide [^()]{0,80}?n[ºo°]\s*[\d./-]+(, de \d{4})?",
    r"^Publicad[oa](\(a\))? no DOU de [\d./]+(, se[çc][ãa]o \d+)?(, p[áa]gina \d+)?",
    r"^\(Republicad[oa][^)]*\)",
)]


def _strip_epigrafe(e: str, epigrafe: str) -> str:
    """Strip a repeated epígrafe at the start of the ementa (punctuation/case-insensitive)."""
    ce = _canon(epigrafe)
    if not ce or not _canon(e).startswith(ce):
        return e
    acc = 0
    for i, ch in enumerate(e):
        acc += len(_canon(ch))
        if acc >= len(ce):
            return e[i + 1:].lstrip(" .,;:–-")
    return e


def clean_ementa(ementa: str, epigrafe: str) -> str:
    e = CAMARA_RE.sub("", norm(ementa))
    changed = True
    while changed:
        before = e
        for rx in EMENTA_NOISE:
            e = rx.sub("", e).lstrip(" .,;:–-")
        e = _strip_epigrafe(e, epigrafe) if epigrafe else e
        e = CAMARA_RE.sub("", e)
        changed = e != before
    return norm(e)


@dataclass
class Meta:
    epigrafe: str
    ementa: str            # cleaned, full
    ementa_prefix: str     # possibly truncated
    truncated: bool
    anexo_label: str = ""
    ementa_id: str = ""    # id of the ementa Agrupamento (non-statutory), for its own TXT chunk
    source: str = ""       # how epígrafe/ementa were found (report)

    def text(self) -> str:
        parts = [self.epigrafe, self.ementa_prefix, self.anexo_label]
        return " | ".join(clean_meta(p) for p in parts if p and clean_meta(p))


def _first(tree, xp: str):
    r = tree.xpath(xp, namespaces=NSMAP)
    return r[0] if r else None


def statutory_main_meta(tree) -> tuple[str, str]:
    epi = _first(tree, "(//l:ParteInicial/l:Epigrafe | //l:Epigrafe)[1]")
    em = _first(tree, "(//l:ParteInicial/l:Ementa | //l:Ementa)[1]")
    epigrafe = norm(xstring(epi)) if epi is not None else ""
    ementa = clean_ementa(xstring(em), epigrafe) if em is not None else ""
    return epigrafe, ementa


def nonstat_meta(tree) -> tuple[str, str, str, str]:
    """(epígrafe, ementa, ementa Agrupamento id, source description) of a non-statutory doc."""
    def agr(nome):
        return tree.xpath(f"//l:Agrupamento[@nome='{nome}']", namespaces=NSMAP)

    def campos(*nomes):
        return [norm(xstring(c)) for c in tree.xpath("//l:campo", namespaces=NSMAP)
                if c.get("nome") in nomes and norm(xstring(c))]

    epis, ems = agr("epigrafe"), agr("ementa")
    ementa_campos = campos("EMENTA", "Ementa")
    assunto_campos = campos("ASSUNTO", "Assunto")
    src = []
    epigrafe = norm(" ".join(xstring(e) for e in epis))
    ementa, ementa_id = "", ""
    if epigrafe:
        src.append("epi=agrupamento")
    elif (len(ems) == 1 and len(norm(xstring(ems[0]))) < 200
          and TITLE_LIKE_RE.match(norm(xstring(ems[0])))):
        # the parser tagged the title as 'ementa' (e.g. solucao.consulta_2019-03-25_6007)
        epigrafe = norm(xstring(ems[0]))
        ems = []
        src.append("epi=ementa-agrupamento-title")
    if not epigrafe:
        for nome in ("preliminar", "tituloAnexo"):
            a = agr(nome)
            ps = a[0].xpath(".//l:p", namespaces=NSMAP) if a else []
            first = norm(xstring(ps[0])) if ps else ""
            if first and len(first) < 200:
                epigrafe = first
                src.append(f"epi={nome}-first-line")
                break
    if not epigrafe:
        h = _first(tree, "//l:PartePrincipal/l:AgrupamentoHierarquico[1]")
        head = norm(" ".join(xstring(x) for x in h if L(x) in ("Rotulo", "NomeAgrupador"))) if h is not None else ""
        if head and len(head) < 200:
            epigrafe = head
            src.append("epi=first-section-heading")
    if not epigrafe:
        epigrafe = doc_urn(tree)
        src.append("epi=urn")
    if ems:
        ementa = norm(" ".join(xstring(e) for e in ems))
        ementa_id = ems[0].get("id", "")
        src.append("ementa=agrupamento")
    elif ementa_campos:
        ementa = "; ".join(ementa_campos)
        src.append("ementa=campo-ementa")
    elif assunto_campos:
        ementa = "; ".join({_canon(a): a for a in reversed(assunto_campos)}[k]
                           for k in dict.fromkeys(_canon(a) for a in assunto_campos))
        src.append("ementa=campo-assunto")
    else:
        src.append("ementa=none")
    return epigrafe, clean_ementa(ementa, epigrafe), ementa_id, ",".join(src)


def annex_own_title(tree) -> str:
    root_doc = _first(tree, "/l:LexML/l:Anexo/*")
    if root_doc is None:
        return ""
    if L(root_doc) == "DocumentoArticulado":
        e = _first(root_doc, ".//l:Epigrafe")
        return norm(xstring(e)) if e is not None else ""
    t = _first(root_doc, ".//l:Agrupamento[@nome='tituloAnexo']")
    if t is not None:
        return norm(xstring(t))
    p = _first(root_doc, "l:PartePrincipal/l:p[1]")
    if p is not None and norm(xstring(p)).upper().startswith("ANEXO"):
        return norm(xstring(p))
    return ""


def annex_number(urn: str) -> str:
    m = re.search(r"!anexo(\d+)$", urn)
    return m.group(1) if m else ""


def is_annex_tree(tree) -> bool:
    return L(tree.getroot()[-1]) == "Anexo" or bool(tree.xpath("/l:LexML/l:Anexo", namespaces=NSMAP))


@functools.lru_cache(maxsize=None)
def urn_index() -> dict[str, Path]:
    """URN -> file for every main (non-annex) document in lexml/."""
    idx = {}
    for d in (ART_DIR, NAO_DIR):
        for p in sorted(d.glob("*.xml")):
            try:
                for _ev, el in etree.iterparse(str(p), events=("start",), huge_tree=True):
                    if L(el) == "Identificacao":
                        idx.setdefault(el.get("URN", ""), p)
                        break
            except etree.XMLSyntaxError:
                continue
    return idx


def resolve_parent(annex_path: Path, annex_urn: str) -> tuple[Path | None, str]:
    """Parent main document of an annex: family stem first, then the URN without '!anexoN'."""
    base = annex_path.name[:-4]
    stem = ANEXO_RE.sub("", base)
    cand = annex_path.parent / f"{stem}.xml"
    if stem != base and cand.is_file():
        return cand, "stem"
    purn = re.sub(r"!anexo\d+$", "", annex_urn)
    p = urn_index().get(purn)
    if p is not None and p != annex_path:
        return p, "urn"
    return None, "unresolved"


def metadata_for(xml_path: Path, tok: Tokenizer | None = None,
                 ementa_max_tokens: int = DEFAULT_EMENTA_MAX_TOKENS, tree=None) -> Meta:
    """METADADOS for any LexML file (statutory main, annex of any category, non-statutory)."""
    xml_path = Path(xml_path)
    tree = tree if tree is not None else parse(xml_path)
    urn = doc_urn(tree)
    tok = tok or get_tokenizer()
    anexo_label = ""
    target_tree = tree
    source = ""
    if is_annex_tree(tree):
        n = annex_number(urn)
        own = annex_own_title(tree)
        anexo_label = " – ".join(x for x in (f"Anexo {n}" if n else "Anexo", own) if x)
        parent, how = resolve_parent(xml_path, urn)
        source = f"parent={how}"
        target_tree = parse(parent) if parent is not None else None
    if target_tree is None:
        epigrafe, ementa, ementa_id = "", "", ""
    elif _first(target_tree, "//l:ProjetoNorma") is not None:
        epigrafe, ementa = statutory_main_meta(target_tree)
        ementa_id = ""
        source = ",".join(x for x in (source, "statutory") if x)
    else:
        epigrafe, ementa, ementa_id, src = nonstat_meta(target_tree)
        source = ",".join(x for x in (source, src) if x)
    if target_tree is not tree:
        ementa_id = ""  # the parent's ementa chunk belongs to the parent document
    ementa_prefix, truncated = truncate_tokens(ementa, ementa_max_tokens, tok) if ementa else ("", False)
    return Meta(epigrafe, ementa, ementa_prefix, truncated, anexo_label, ementa_id, source)


# --------------------------------------------------------------------------------------------
# CSV I/O and provenance sidecars
# --------------------------------------------------------------------------------------------

def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLS, quoting=csv.QUOTE_ALL, lineterminator="\n",
                       extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    path.write_text(buf.getvalue(), encoding="utf-8")


def prov_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".prov.jsonl")


def write_prov(csv_path: Path, records: list[dict], append: bool = False) -> None:
    p = prov_path(csv_path)
    if not records and not append:
        if p.exists():
            p.unlink()
        return
    with open(p, "a" if append else "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_prov(csv_path: Path) -> list[dict]:
    p = prov_path(csv_path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def body_of(texto: str) -> str:
    """Texto without the '[ METADADOS ] ' prefix (metadata never contains '[' or ']')."""
    i = texto.find(" ] ")
    return texto[i + 3:] if texto.startswith("[") and i >= 0 else texto


# --------------------------------------------------------------------------------------------
# Splitting helpers (plan §5.3 and §5b)
# --------------------------------------------------------------------------------------------

_SENT_RE = re.compile(r"(?<=[.;:!?])\s+")
_PARNUM_RE = re.compile(r"^\(?\d+(\.\d+)*[.)]?$")      # "12." / "3.1" / "(4)" on its own line
_ENDS_OK = (".", ";", ":")


def greedy_pack(n: int, fits) -> list[tuple[int, int]]:
    """Split range(n) into consecutive maximal groups [s, e) with fits(s, e) (assumed monotone in e).
    An item that does not fit alone becomes a group of its own (the caller flags it)."""
    out, s = [], 0
    while s < n:
        if not fits(s, s + 1):
            out.append((s, s + 1))
            s += 1
            continue
        ok, step = s + 1, 1
        while ok + step <= n and fits(s, ok + step):
            ok += step
            step *= 2
        lo, hi = ok, min(n, ok + step - 1)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fits(s, mid):
                lo = mid
            else:
                hi = mid - 1
        out.append((s, lo))
        s = lo
    return out


def join_text(head: str, pieces: list[str]) -> str:
    return norm(head + " " + " ".join(pieces))


def split_words(text: str, head: str, cap: int, tok: "Tokenizer") -> list[str]:
    words = text.split(" ")
    groups = greedy_pack(len(words), lambda s, e: tok.count(join_text(head, words[s:e])) <= cap)
    return [" ".join(words[s:e]) for s, e in groups]


def split_sentences(text: str, head: str, cap: int, tok: "Tokenizer") -> list[str]:
    """Sentences packed greedily; a sentence over the cap by itself is cut at word boundaries."""
    sents: list[str] = []
    for s in _SENT_RE.split(norm(text)):
        if s and tok.count(join_text(head, [s])) > cap:
            sents += split_words(s, head, cap, tok)
        elif s:
            sents.append(s)
    groups = greedy_pack(len(sents), lambda s, e: tok.count(join_text(head, sents[s:e])) <= cap)
    return [" ".join(sents[s:e]) for s, e in groups]


def good_boundary(lines: list[str], i: int) -> bool:
    """A cut before lines[i] is preferred when the previous line ends a sentence (not a bare
    paragraph number) or when lines[i] is a bare paragraph number."""
    prev, cur = lines[i - 1].rstrip(), lines[i].strip()
    if _PARNUM_RE.match(cur):
        return True
    return prev.endswith(_ENDS_OK) and not _PARNUM_RE.match(prev.strip())


def split_lines(lines: list[str], head: str, cap: int, tok: "Tokenizer") -> list[list[str]]:
    """Plan §5.3: greedy, cut at the last preferred line boundary, else at a line boundary; lines
    over the cap by themselves are first cut at sentence, then word boundaries."""
    fine: list[str] = []
    for ln in lines:
        if tok.count(join_text(head, [ln])) > cap:
            fine += split_sentences(ln, head, cap, tok)
        else:
            fine.append(ln)
    out, s, n = [], 0, len(fine)
    fits = lambda a, b: tok.count(join_text(head, fine[a:b])) <= cap  # noqa: E731
    while s < n:
        (_, e), = greedy_pack(n - s, lambda a, b: fits(s + a, s + b))[:1]
        e += s
        if e < n:
            for b in range(e, s, -1):
                if good_boundary(fine, b):
                    e = b
                    break
        out.append(fine[s:e])
        s = e
    return out


def table_header_count(t) -> int:
    """1 header row, or 2 when the first row is a single spanning title."""
    trs = list(t.iter(f"{{{NS}}}tr"))
    if len(trs) < 3:
        return min(1, len(trs))
    ncols = max(sum(int(td.get("colspan", "1") or 1) for td in child_elems(tr, "td")) for tr in trs)
    first = child_elems(trs[0], "td")
    if ncols > 1 and len(first) == 1:
        return 2
    return 1


def split_table_rows(rows: list[str], n_header: int, head: str, cap: int,
                     tok: "Tokenizer") -> list[tuple[list[str], bool]]:
    """Row groups [(rows_of_part, oversize)], header rows repeated in every part."""
    header, body = rows[:n_header], rows[n_header:]
    if not body:
        return [(rows, tok.count(join_text(head, ["Tabela: " + " ; ".join(rows)])) > cap)]

    def txt(a, b):
        return join_text(head, ["Tabela: " + " ; ".join(header + body[a:b])])

    groups = greedy_pack(len(body), lambda a, b: tok.count(txt(a, b)) <= cap)
    return [(header + body[a:b], tok.count(txt(a, b)) > cap) for a, b in groups]
