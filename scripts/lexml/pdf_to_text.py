#!/usr/bin/env python3
"""Born-digital Solução de Consulta PDF → cleaned plain text for ``lexml_nonstat parse``.

Plan: ``docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md`` §1.3 (R1).

``pdftotext -raw`` loses the paragraph structure (one line per PDF line) and keeps the page
furniture, so the non-statutory parser reads the whole document as one ``<p>``. This script reads
``pdftotext -bbox-layout`` instead, which gives each line's position, and rebuilds the text the way
the existing SC ``.docx`` sources look:

1. **Furniture is dropped by position**: the page header band (``Cosit``/``Fls. N``, the faux-bold
   running header, ``PROCESSO …``/``SOLUÇÃO DE CONSULTA N – COSIT``, the broken
   "Erro: Origem da referência não encontrada" field) and the footer band (page number,
   "Cópia autenticada administrativamente").
2. **The first-page header box** (``Processo``, ``Interessado``, ``CNPJ/CPF``, ``Data``…) is
   replaced by the title line the ``.docx`` sources start with:
   ``Solução de Consulta Cosit nº N, de D de <mês> de AAAA``.
3. **Paragraphs** are rebuilt from vertical gaps: words on the same baseline are one line (so a
   paragraph number such as ``2.`` joins its text), and a gap wider than the document's line
   spacing starts a new paragraph. A paragraph cut by a page break is rejoined when its last line
   has no closing punctuation or the next page starts in lower case.
4. **Ementa zone** (``Assunto:`` up to the first section heading): the ``Assunto`` line, the
   upper-case headings and the ementa texts become separate paragraphs, as in the ``.docx``.
5. **Indentation** of body paragraphs whose lines all start right of the text margin (quoted
   legislation) is written as leading spaces (``txt_reader``: 180 twips per space), so the parser's
   quotation guard sees the same evidence it gets from a ``.docx``.

Output: one paragraph per line, paragraphs separated by a blank line (``txt_reader`` joins lines of
one block and splits blocks on blank lines).

Usage::

    python3 scripts/lexml/pdf_to_text.py original/nao_articulados/sc_cosit_*.pdf \\
        -o lexml/nao_articulados/_text/
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

H = "{http://www.w3.org/1999/xhtml}"

#: Header band (top y, in points): lines above HEADER_Y are page furniture; between HEADER_Y and
#: HEADER_MAX only lines that look like furniture are (body text starts at y≈81 on some pages,
#: while SC 354/2014 prints "Fls. N" at y≈75).
HEADER_Y = 72.0
HEADER_MAX = 90.0
FURNITURE_RE = re.compile(r"^(Cosit|Fls\. ?\d+|\d{1,3}|Erro: Origem da|referência não|encontrada|"
                          r"S ?o ?l ?u ?ç ?ã ?o de Consulta n\.º \d+.*)$")
#: Footer band: page number and the "Cópia autenticada" stamp.
FOOTER_Y = 785.0

SECTION_RE = re.compile(
    r"^(relat[óo]rio|fundamentos?|fundamenta[çc][ãa]o|conclus[ãa]o|an[áa]lise|"
    r"ordem de intima[çc][ãa]o|despacho de aprova[çc][ãa]o.*)$", re.I)
NUMBERED_RE = re.compile(r"^\d+(\.\d+)*\.\s")
ENUM_RE = re.compile(r"^(Art\.\s|§\s|Par[áa]grafo único|[IVXLC]+\s*[-–−]\s|[a-z]\)\s|\d+\)\s)")
END_RE = re.compile(r"[.:;?!][”\"’')\]]*$")
MONTHS = "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro"


@dataclass
class Line:
    page: int
    y: float
    x: float
    x_max: float
    text: str


@dataclass
class Para:
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        out = ""
        for ln in self.lines:
            t = ln.text
            if not out:
                out = t
            elif re.search(r"[A-Za-zÀ-ú]-$", out):
                out += t  # compound word wrapped at its hyphen ("ano-" + "calendário")
            else:
                out += " " + t
        return out

    @property
    def x(self) -> float:
        return min(ln.x for ln in self.lines)


def read_lines(pdf: Path) -> list[Line]:
    xml = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], check=True,
                         capture_output=True, text=True).stdout
    root = ET.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", xml))
    lines: list[Line] = []
    for pi, page in enumerate(root.iter(H + "page")):
        raw = []
        for ln in page.iter(H + "line"):
            # Words closer than 0.5 pt are one word split by a font change (small caps:
            # "A" + "SSUNTO"), so they are joined without a space.
            text, last = "", None
            for w in ln.iter(H + "word"):
                x0 = float(w.get("xMin"))
                sep = "" if last is None or x0 - last < 0.5 else " "
                text += sep + (w.text or "")
                last = float(w.get("xMax"))
            raw.append((float(ln.get("yMin")), float(ln.get("xMin")), float(ln.get("xMax")), text))
        # Words of one baseline can come out as several pdftotext lines/blocks (justified text,
        # paragraph numbers): merge lines whose yMin differs by < 3 pt, in x order.
        raw.sort(key=lambda r: (round(r[0]), r[1]))
        merged: list[list] = []
        for y, x, xm, t in raw:
            if merged and abs(merged[-1][0] - y) < 3:
                merged[-1][3].append((x, xm, t))
            else:
                merged.append([y, None, None, [(x, xm, t)]])
        for y, _, _, parts in merged:
            parts.sort()
            lines.append(Line(pi, y, parts[0][0], parts[-1][1], " ".join(p[2] for p in parts)))
    return lines


def title_from_header(header: list[Line], stem: str) -> str:
    number = re.match(r"sc_cosit_(\d+)_", stem).group(1)
    date = None
    for ln in header:
        m = re.search(rf"(\d{{1,2}}º? de ({MONTHS.replace(' ', '|')}) de \d{{4}})", ln.text, re.I)
        if m:
            date = m.group(1)
    if date is None:
        sys.exit(f"{stem}: no date in the first-page header")
    return f"Solução de Consulta Cosit nº {number}, de {date}"


def split_ementa(p: Para) -> list[Para]:
    """Assunto line / upper-case heading runs / ementa text, as separate paragraphs."""
    out: list[Para] = []
    cur: Para | None = None
    kind = None
    for i, ln in enumerate(p.lines):
        t = ln.text
        letters = re.sub(r"[^A-Za-zÀ-ú]", "", t)
        upper = bool(letters) and letters == letters.upper()
        if re.match(r"^(assunto|ementa)\s*:", t, re.I):
            k = "assunto"
        elif kind == "assunto" and (cur.text.endswith("-") or len(t) <= 6):
            k = "assunto"  # "IMPOSTO SOBRE A RENDA DE PESSOA FÍSICA -" / "IRPF"
        else:
            k = "caps" if upper else "text"
        # Change of kind only at a line end with closing punctuation, so a wrapped last word
        # in upper case ("… administrado pela" / "RFB.") stays in its paragraph.
        if cur is not None and k != "assunto" and kind != "assunto" and not END_RE.search(cur.lines[-1].text):
            k = kind
        if cur is None or k != kind:
            cur = Para()
            out.append(cur)
            kind = k
        cur.lines.append(ln)
    return out


def build(pdf: Path) -> str:
    stem = pdf.stem
    lines = read_lines(pdf)
    lines = [ln for ln in lines if HEADER_Y <= ln.y < FOOTER_Y
             and not (ln.y < HEADER_MAX and FURNITURE_RE.match(ln.text))]
    lines = [ln for ln in lines if not re.fullmatch(r"\d{1,3}", ln.text)]  # stray page counters

    # First-page header box → title.
    start = next(i for i, ln in enumerate(lines) if re.match(r"^(assunto|ementa)\s*:", ln.text, re.I))
    title = title_from_header(lines[:start], stem)
    body = lines[start:]

    # Typical line spacing: the lower half of consecutive same-page gaps.
    gaps = sorted(b.y - a.y for a, b in zip(body, body[1:]) if a.page == b.page and b.y > a.y)
    spacing = statistics.median(gaps[: max(1, len(gaps) // 2)])
    limit = spacing * 1.3

    paras: list[Para] = []
    for ln in body:
        if not paras:
            paras.append(Para([ln]))
            continue
        prev = paras[-1].lines[-1]
        if ln.page != prev.page:
            cont = not END_RE.search(prev.text) or ln.text[:1].islower()
            heading_like = SECTION_RE.match(ln.text) or NUMBERED_RE.match(ln.text)
            new = not cont or bool(heading_like)
        else:
            new = ln.y - prev.y > limit
        new = new or bool(SECTION_RE.match(ln.text)) or bool(SECTION_RE.match(prev.text))
        if new:
            paras.append(Para([ln]))
        else:
            paras[-1].lines.append(ln)

    # Ementa zone: up to the first section heading or numbered paragraph.
    end = next((i for i, p in enumerate(paras)
                if SECTION_RE.match(p.text) or NUMBERED_RE.match(p.text)), len(paras))
    ementa = [q for p in paras[:end] for q in split_ementa(p)]
    rest = paras[end:]

    # Text margin of the body: where the numbered paragraphs start ("2. A consulente…"); quoted
    # legislation can outnumber body lines, so the mode of all lines is not reliable.
    xs = [round(p.lines[0].x) for p in rest if NUMBERED_RE.match(p.lines[0].text)]
    margin = statistics.mode(xs) if xs else min((round(p.x) for p in rest), default=0)

    out = [title]
    for p in ementa:
        out.append(norm(p.text))
    for p in rest:
        text = norm(p.text)
        indent = p.x - margin
        spaces = int(round(indent * 20 / 180)) if indent > 20 else 0
        out.append(" " * spaces + text)
    return "\n\n".join(out) + "\n"


def norm(t: str) -> str:
    t = re.sub(r"^(\d+(\.\d+)*) \.", r"\1.", t)  # "7 ." → "7."
    t = re.sub(r"^ASSUNTO\s*:", "Assunto:", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdfs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        dest = args.out / f"{pdf.stem}.txt"
        dest.write_text(build(pdf), encoding="utf-8")
        print(f"{pdf.name} → {dest}")


if __name__ == "__main__":
    main()
