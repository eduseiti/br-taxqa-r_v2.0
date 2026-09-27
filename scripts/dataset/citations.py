"""Parse the legal citations of the IRPF Q&A document into nested LexML fragment ids.

The Q&A document cites provisions in running text, for example

    Lei nº 11.482, de 31 de maio de 2007, art. 1º, inciso X e parágrafo único
    Instrução Normativa RFB nº 2.178, de 5 de março de 2024, art. 12, § 1º, inciso II
    inciso II do § 1º do art. 162 do Regulamento do Imposto sobre a Renda – RIR/2018

The word order carries the nesting: the first line cites two sibling units (caput inciso X and
the parágrafo único), the second one path (inciso II *of* § 1º), the third the same kind of path
written in reverse ("X do Y do Z"). This module turns such text into LexML fragment ids
(``art1_cpt_inc10``, ``art1_par1u``, ``art12_par1_inc2``, ``art162_par1_inc2``), the id scheme of
the XML files in ``lexml/`` and of the ``unidade_id`` / ``cobre_ids`` columns of the chunks.

Two steps:

1. :func:`find_chains` finds every *chain* of provision tokens (``art.``, ``§``, ``inciso``,
   ``alínea``, ``item``, ``caput``, ``Anexo``… with their numbers, joined by ``,`` / ``e`` /
   ranges ``a``/``ao``/``até`` / genitive ``do``/``da``) in a text.
2. :func:`chain_units` turns one chain into the cited units. Reverse ("do/da") links are first
   rewritten into forward order; then a stack attaches each unit under the closest open unit of a
   higher level. A unit is cited when nothing is attached under it, or when a child follows it
   through ``e`` ("art. 26 e parágrafo único" cites the article *and* its paragraph).

Attributing chains to the cited acts (which act a chain belongs to) is done by the dataset builder,
which knows the acts of each question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ------------------------------------------------------------------------------------ levels

LEVEL = {"anx": -2, "grp": -1, "art": 0, "par": 1, "cpt": 1, "inc": 2, "ali": 3, "ite": 4}

# keyword -> kind. Order matters: longer alternatives first.
KEYWORDS = [
    ("art", r"\b(?:artigos?|arts?)\b\.?"),
    ("par", r"§§?|\bpar[áa]grafos?\b|\bpar\."),
    ("cpt", r"\bcaput\b"),
    ("inc", r"\bincisos?\b|\binc\."),
    ("ali", r"\bal[íi]neas?\b|\bletras?\b"),
    ("ite", r"\bitens\b|\bitem\b"),
    ("anx", r"\bAnexos?\b"),
    ("grp", r"\b(?:Cap[íi]tulos?|Subse[çc](?:ão|ões)|Se[çc](?:ão|ões)|T[íi]tulos?)\b"),
]
KW_RE = re.compile("|".join(f"(?P<{k}>{p})" for k, p in KEYWORDS), re.I)

ARABIC = r"(?P<num>\d{1,3}(?:\.\d{3})+|\d+)(?:\s*(?:[º°ª]|o(?![a-z])))?(?:\s*-\s*(?P<suf>[A-Z])\b)?"
ROMAN = r"(?P<rom>\b[IVXLCDM]+\b)"
UNICO = r"(?P<uni>\b[ÚúUu]nic[oa]\b)"
QUOTED_LETTER = r"[“\"'‘](?P<qlet>[a-z])[”\"'’]"
LETTER = r"(?P<let>\b[a-z]\b)"
DECIMAL = r"(?P<dec>\d+(?:\.\d{1,2})+(?![\d.]))"   # "1.8", "19.1" (a thousands dot has 3 digits)
VALUE_RE = re.compile(rf"{UNICO}|{QUOTED_LETTER}|{DECIMAL}|{ARABIC}|{ROMAN}|{LETTER}")

SEQ_RE = re.compile(r"\s+(?=§)|\s*;\s*e\s+(?=\d)|\s*,\s*e\s+|\s*,\s*|\s+e\s+|(?<=[”’\"'])\s*e\s+")
RANGE_RE = re.compile(r"\s+(?:a|ao|até)\s+")
GEN_RE = re.compile(r"\s*,?\s+(?:d[oa]s?|de\s+seu|de\s+sua)\s+")
SPACE_RE = re.compile(r"\s*")
DE_RE = re.compile(r"(?:de\s+)?")          # "incisos de I a IV"
GENITIVE_ACT_RE = re.compile(r"\s*,?\s+(?:d[oa]s?|ao|à)\s+(?!art|§|inciso|al[íi]nea|item|par[áa]grafo)", re.I)
HAS_ARTICLE_CHILD = re.compile(r"\s*,?\s*(?:caput\b|§|par[áa]grafo)", re.I)

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int | None:
    total, prev = 0, 0
    for c in reversed(s.upper()):
        v = ROMAN_VALUES.get(c)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


# ------------------------------------------------------------------------------------ data

@dataclass
class Ref:
    """One cited value of one kind, e.g. ('par', '1º'), with its link to the previous ref."""
    kind: str
    raw: str            # value as written ("1º", "12-A", "X", "c", "único", "" for caput)
    key: str | None     # id part ("1", "12-1", "10", "3", "1u"); None when not id-able
    link: str           # 'start', ',', 'e', 'range', or 'of' (the previous ref is a child of this one)

    @property
    def level(self) -> int:
        return LEVEL[self.kind]


@dataclass
class Chain:
    start: int
    end: int
    text: str
    refs: list[Ref]
    genitive_after: bool = False   # followed by "do/da <act>" ("art. 6º da Lei nº …")


@dataclass
class Unit:
    """One cited unit: its path from the outermost ref, the LexML fragment id and a label."""
    path: list[Ref] = field(default_factory=list)

    @property
    def annex(self) -> str | None:
        a = [r for r in self.path if r.kind == "anx"]
        return f"Anexo {a[-1].raw}".strip() if a else None

    @property
    def article_id(self) -> str | None:
        a = [r for r in self.path if r.kind == "art"]
        return f"art{a[0].key}" if a and a[0].key else None

    @property
    def fragment_id(self) -> str | None:
        """LexML id; None for units outside an article or with a value that has no id form."""
        if not self.article_id:
            return None
        parts, has_l1 = [], False
        for r in self.path:
            if r.kind == "anx":
                continue
            if r.kind == "grp":         # "art. V, Seção 18" (treaties): no LexML id form
                return None
            if r.key is None:
                return None
            if r.kind == "art":
                parts.append(f"art{r.key}")
                continue
            if r.level == 1:
                has_l1 = True
            elif not has_l1:        # inciso/alínea/item directly under the article: caput
                parts.append("cpt")
                has_l1 = True
            parts.append(r.kind if r.kind == "cpt" else f"{r.kind}{r.key}")
        return "_".join(parts)

    @property
    def label(self) -> str:
        return ", ".join(_label(r) for r in self.path)


def _label(r: Ref) -> str:
    return {
        "art": f"art. {r.raw}", "par": "parágrafo único" if r.key == "1u" else f"§ {r.raw}",
        "cpt": "caput", "inc": f"inciso {r.raw}", "ali": f"alínea {r.raw}", "ite": f"item {r.raw}",
        "anx": f"Anexo {r.raw}".strip(), "grp": r.raw,
    }[r.kind]


# ------------------------------------------------------------------------------------ values

def _key(kind: str, m: re.Match) -> str | None:
    """Id part of a value match for a kind ('1', '12-1', '10', '3', '1u'); None if impossible."""
    if m["dec"]:
        return None
    if m["uni"]:
        return "1u" if kind in ("art", "par") else None
    if m["num"]:
        if kind in ("inc", "ali"):
            return None
        n = str(int(m["num"].replace(".", "")))
        return n + (f"-{ord(m['suf']) - 64}" if m["suf"] else "")
    if m["rom"]:
        v = roman_to_int(m["rom"])
        return str(v) if v and kind in ("art", "inc", "anx", "grp") else None   # treaties: "art. V"
    letter = m["qlet"] or m["let"]
    if letter:
        return str(ord(letter) - 96) if kind == "ali" else None
    return None


def _bare_kind(m: re.Match, used: list[tuple[str, bool]], closed: set[str]) -> str | None:
    """Kind of a value written without keyword, from its form and the keywords used so far.

    Roman numeral -> inciso; letter -> alínea; arabic -> the last *plural* arabic keyword
    ("arts. 2º, inciso IV, 4º e 6º": 4 and 6 are articles), else the last arabic keyword.
    A list already closed by "e" ("§§ 1º e 4º, e 7º") takes no further bare values, so 7 goes
    back to the article list. Ordinals ("19ª Seção") are never bare values. (A number followed by
    "caput" or "§" is an article whatever this function says; see _scan_chain.)
    """
    if m["rom"]:
        return "inc"
    if m["qlet"] or m["let"]:
        return "ali"
    if "ª" in m.group():
        return None
    if m["num"] or m["uni"] or m["dec"]:
        arabic = [(k, pl) for k, pl in used if k in ("art", "par", "ite") and k not in closed]
        if not arabic:
            arabic = [(k, pl) for k, pl in used if k in ("art", "par", "ite")]
        plural = [k for k, pl in arabic if pl]
        if plural:
            return plural[-1]
        return arabic[-1][0] if arabic else None
    return None


# ------------------------------------------------------------------------------------ scanning

def _value_at(text: str, pos: int, kind: str | None, after_kw: bool):
    """Match a value at pos. Unquoted single letters count only right after an alínea keyword,
    or in alínea context when they are not the words 'a'/'e'."""
    m = VALUE_RE.match(text, pos)
    if not m:
        return None
    if m["let"] and not (kind == "ali" and (after_kw or m["let"] not in "ae")):
        return None
    return m


def _scan_chain(text: str, start: int) -> Chain | None:
    refs: list[Ref] = []
    used: list[tuple[str, bool]] = []
    closed: set[str] = set()        # kinds whose value list was ended by "e"
    pos, link, kind, last_end = start, "start", None, start
    while True:
        kw = KW_RE.match(text, pos)
        if kw:
            kind = kw.lastgroup
            closed.discard(kind)
            plural = kw.group().rstrip(".").lower().endswith(("s", "§§", "itens"))
            used.append((kind, plural))
            p = SPACE_RE.match(text, kw.end()).end()
            p = DE_RE.match(text, p).end()
            if kind == "cpt":
                refs.append(Ref("cpt", "", "", link))
                last_end = kw.end()
            elif kind == "par" and re.match(r"[úu]nico\b", text[p:], re.I):
                m = VALUE_RE.match(text, p)
                refs.append(Ref("par", "único", "1u", link))
                last_end = m.end()
            else:
                m = _value_at(text, p, kind, after_kw=True)
                if not m:
                    if kind == "anx":             # "Anexo" alone
                        refs.append(Ref("anx", "", None, link))
                        last_end = kw.end()
                    else:
                        break
                else:
                    raw = m.group().strip()
                    refs.append(Ref(kind, f"{kw.group()} {raw}" if kind == "grp" else raw, _key(kind, m), link))
                    last_end = m.end()
        else:
            if not refs:
                return None
            m = _value_at(text, pos, kind, after_kw=False)
            if not m:
                break
            k = _bare_kind(m, used, closed) if link != "range" else refs[-1].kind
            if (link != "range" and m["num"] and any(u == "art" for u, _ in used)
                    and HAS_ARTICLE_CHILD.match(text, m.end())):
                k = "art"
            if k is None:
                break
            kind = k
            refs.append(Ref(k, m.group().strip(), _key(k, m), link))
            last_end = m.end()
            if link == "e":
                closed.add(k)
        # connector
        for ctype, cre in (("range", RANGE_RE), ("of", GEN_RE), ("seq", SEQ_RE)):
            c = cre.match(text, last_end)
            if not c:
                continue
            nxt = c.end()
            if ctype == "of" and not KW_RE.match(text, nxt):
                continue
            if ctype == "range" and not VALUE_RE.match(text, nxt):
                continue
            if ctype == "seq" and not (KW_RE.match(text, nxt) or _value_at(text, nxt, kind, False)):
                continue
            link = {"range": "range", "of": "of", "seq": "e" if "e" in c.group().split() else ","}[ctype]
            pos = nxt
            break
        else:
            break
    if not refs:
        return None
    return Chain(start, last_end, text[start:last_end], refs, bool(GENITIVE_ACT_RE.match(text, last_end)))


def find_chains(text: str) -> list[Chain]:
    """All provision chains of a text, in order."""
    chains, pos = [], 0
    while True:
        kw = KW_RE.search(text, pos)
        if not kw:
            return chains
        ch = _scan_chain(text, kw.start())
        if ch:
            chains.append(ch)
            pos = max(ch.end, kw.end())
        else:
            pos = kw.end()


# ------------------------------------------------------------------------------------ units

def _expand_ranges(refs: list[Ref]) -> list[Ref]:
    out: list[Ref] = []
    for r in refs:
        if r.link == "range" and out and out[-1].kind == r.kind and out[-1].key and r.key:
            a, b = out[-1].key, r.key
            if a.isdigit() and b.isdigit() and 0 < int(b) - int(a) <= 300:
                for i in range(int(a) + 1, int(b) + 1):
                    raw = r.raw if i == int(b) else _raw_of(r.kind, i)
                    out.append(Ref(r.kind, raw, str(i), ","))
                continue
        out.append(Ref(r.kind, r.raw, r.key, "," if r.link == "range" else r.link))
    return out


def _raw_of(kind: str, i: int) -> str:
    if kind == "inc":
        vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"),
                (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
        s = ""
        for v, sym in vals:
            while i >= v:
                s, i = s + sym, i - v
        return s
    if kind == "ali":
        return chr(96 + i)
    return f"{i}º" if kind in ("art", "par") and i < 10 else str(i)


def _forward(refs: list[Ref]) -> list[Ref]:
    """Rewrite reverse links ("inciso II do § 1º do art. 12") into forward order.

    Repeatedly take the rightmost 'of' link: its target (the ref carrying the link) moves in front
    of the run of refs before it that are deeper than the target (its children), and the links are
    shifted so the children follow the target as a path.
    """
    refs = [Ref(r.kind, r.raw, r.key, r.link) for r in refs]
    while True:
        idx = [i for i, r in enumerate(refs) if r.link == "of"]
        if not idx:
            return refs
        t = idx[-1]
        target = refs[t]
        s = t - 1
        while s - 1 >= 0 and refs[s - 1].level > target.level and refs[s].link != "start":
            s -= 1
        children = refs[s:t]
        target.link, children[0].link = children[0].link, ","
        refs = refs[:s] + [target] + children + refs[t + 1:]


def chain_units(chain: Chain | list[Ref]) -> list[Unit]:
    """The units cited by a chain, each with its full path (see module docstring)."""
    refs = _forward(_expand_ranges(chain.refs if isinstance(chain, Chain) else chain))
    stack: list[dict] = []          # open units: {"ref", "has_children", "emitted"}
    out: list[Unit] = []

    def path(n: int) -> Unit:
        return Unit([node["ref"] for node in stack[:n]])

    for r in refs:
        popped = False
        while stack and stack[-1]["ref"].level >= r.level:
            if not stack[-1]["has_children"] and not stack[-1]["emitted"]:
                out.append(path(len(stack)))
            stack.pop()
            popped = True
        if stack:
            parent = stack[-1]
            # "art. 26 e parágrafo único": a child joined by "e" right after its parent cites both
            if r.link == "e" and not popped and not parent["has_children"] and not parent["emitted"]:
                out.append(path(len(stack)))
                parent["emitted"] = True
            parent["has_children"] = True
        stack.append({"ref": r, "has_children": False, "emitted": False})
    while stack:
        if not stack[-1]["has_children"] and not stack[-1]["emitted"]:
            out.append(path(len(stack)))
        stack.pop()
    seen, uniq = set(), []          # first appearance, no duplicates
    for u in out:
        k = u.fragment_id or u.label
        if k not in seen:
            seen.add(k)
            uniq.append(u)
    return uniq


def parse(text: str) -> list[Unit]:
    """All units cited in a text (all chains). Used for overrides and tests."""
    return [u for ch in find_chains(text) for u in chain_units(ch)]


# ------------------------------------------------------------------------------------ acts

NUMBER_IN_TITLE = re.compile(r"n[º°o]\.?\s*(\d[\d.]*(?:-\d+)?)", re.I)
ANY_NUMBER = re.compile(r"\bn[º°o]s?\.?\s*\d", re.I)
APPROVED_BY = re.compile(r"(?:aprovad[oa]|promulgad[oa])\s+pel[oa]\s+(?:[\w-]+\s+){0,2}$", re.I)
AMENDED_BY = re.compile(r"(?:alterad[oa]|redação\s+dada)\s+pel[oa]\s+(?:[\w-]+\s+){0,2}$", re.I)
RIR = re.compile(r"Regulamento do Imposto sobre a Renda|RIR/2018", re.I)


def _number_pattern(num: str) -> re.Pattern:
    """'2.158-35' -> regex for 'nº 2.158-35' / 'nº 2158-35' (thousands dots optional)."""
    digits, _, suffix = num.partition("-")
    body = r"\.?".join(re.escape(c) for c in digits.replace(".", ""))
    tail = r"\s*-\s*" + re.escape(suffix) if suffix else ""
    return re.compile(rf"\bn[º°o]\.?\s*{body}{tail}(?![\d-])", re.I)


def _approved_by(text: str, pos: int) -> bool:
    return bool(APPROVED_BY.search(text[max(0, pos - 40):pos]))


def act_positions(text: str, title: str) -> list[int]:
    """Where the act of a v1.1 reference title is mentioned in a text (start offsets).

    RIR/2018 titles ("Regulamento … aprovado pelo Decreto nº 9.580") are found by the regulation's
    name; other numbered acts by their number ("nº 9.250"), skipping "aprovado pelo Decreto nº …";
    unnumbered acts (Constituição, Código Civil, conventions) by the head of the title.
    """
    if RIR.search(title):
        pos = [m.start() for m in RIR.finditer(text)]
        return [p for i, p in enumerate(pos) if i == 0 or p - pos[i - 1] > 60]   # "Regulamento … - RIR/2018" once
    m = NUMBER_IN_TITLE.search(title)
    if m:
        return [x.start() for x in _number_pattern(m[1]).finditer(text) if not _approved_by(text, x.start())]
    head = re.split(r"\s*[,(–]|\s+-\s+", title.strip())[0]
    words = head.split()
    for n in (len(words), 3, 2, 1):
        if n > len(words) or (n == 1 and len(words[0]) < 6):
            continue
        pat = re.compile(re.escape(" ".join(words[:n])), re.I)
        found = [x.start() for x in pat.finditer(text)]
        if found:
            return found
    return []


@dataclass
class Attribution:
    chains: list[Chain] = field(default_factory=list)
    anchored: bool = False          # the act was found in the text
    pieces: list[str] = field(default_factory=list)   # source text pieces holding the act/chains


def attribute(titles: list[str], texts: list[str], continuation: bool) -> tuple[list[Attribution], list[tuple[str, Chain]]]:
    """Assign the provision chains of ``texts`` to the acts ``titles`` (v1.1 order).

    ``texts`` are the raw citation strings of one question and origin. With ``continuation``
    (the explicit reference block) they are one running text split into ';' pieces, and a piece
    without an act ("…; e art. 6º, §§ 1º e 2º") continues the previous act. Without it (embedded
    citations) each string stands alone.

    A chain followed by "do/da <act>" belongs to the next act mention; any other chain to the
    closest act mention before it (or after it, when there is none before). Mentions of numbered
    acts that no title claims are kept as anonymous anchors, so their chains are not attributed to
    a neighbour; they are returned as ``orphans`` (text, chain).
    """
    groups = [" ; ".join(texts)] if continuation else list(texts)
    result = [Attribution() for _ in titles]
    orphans: list[tuple[str, Chain]] = []
    cursor = (0, 0)
    claimed: dict[tuple[int, int], int] = {}
    positions = [[(g, p) for g, t in enumerate(groups) for p in act_positions(t, title)] for title in titles]
    for i, pos in enumerate(positions):          # in order, each title takes its next free mention
        free = [p for p in pos if p not in claimed]
        pick = next((p for p in free if p >= cursor), None) or (free[0] if free else None) or (pos[0] if pos else None)
        if pick is None:
            continue
        result[i].anchored = True
        claimed.setdefault(pick, i)
        cursor = pick
    owner: dict[tuple[int, int], int | None] = dict(claimed)
    for i, pos in enumerate(positions):          # further mentions of the same act
        for p in pos:
            if p not in owner:
                same = [q for q, j in claimed.items() if j == i]
                if same:
                    owner[p] = i
    for g, t in enumerate(groups):               # mentions of acts that no title claims
        for m in ANY_NUMBER.finditer(t):
            if _approved_by(t, m.start()) or AMENDED_BY.search(t[max(0, m.start() - 40):m.start()]):
                continue
            if not any(gg == g and abs(p - m.start()) < 40 for gg, p in owner):
                owner[(g, m.start())] = None
    for i, title in enumerate(titles):             # e.g. "Decreto nº 9.580" only as "aprovado pelo …"
        m = NUMBER_IN_TITLE.search(title)
        if result[i].anchored or not m:
            continue
        for g, t in enumerate(groups):
            for x in _number_pattern(m[1]).finditer(t):
                _add_piece(result[i], t, _pieces(t) if continuation else [(0, len(t))], x.start())
    for g, t in enumerate(groups):
        anchors = sorted((p, o) for (gg, p), o in owner.items() if gg == g)
        pieces = _pieces(t) if continuation else [(0, len(t))]
        for (p, o) in anchors:
            if o is not None:
                _add_piece(result[o], t, pieces, p)
        for ch in find_chains(t):
            target = None
            if ch.genitive_after:
                nxt = [a for a in anchors if ch.end <= a[0] <= ch.end + 150]
                target = nxt[0] if nxt else None
            if target is None:
                before = [a for a in anchors if a[0] <= ch.start]
                after = [a for a in anchors if a[0] >= ch.end]
                target = before[-1] if before else (after[0] if after else None)
            if target is None or target[1] is None:
                orphans.append((t, ch))
                continue
            result[target[1]].chains.append(ch)
            _add_piece(result[target[1]], t, pieces, ch.start)
    return result, orphans


def _pieces(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in re.finditer(r";", text):
        out.append((start, m.start()))
        start = m.end()
    out.append((start, len(text)))
    return out


def _add_piece(att: Attribution, text: str, pieces: list[tuple[int, int]], pos: int) -> None:
    for a, b in pieces:
        if a <= pos <= b:
            s = re.sub(r"\s+", " ", text[a:b]).strip()
            s = re.sub(r"^e\s+", "", s)
            if s and s not in att.pieces:
                att.pieces.append(s)
            return
