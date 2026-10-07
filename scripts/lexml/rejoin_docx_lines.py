#!/usr/bin/env python3
"""Rejoin hard-wrapped lines of a statutory .docx into one paragraph per dispositivo.

Some fetched documents (e.g. ``resol_tse_22250_20060629``, copied from a PDF) have a paragraph break
after every printed line. The statutory parser then reads wrapped citations that start a line
("9.504/97, art. 24, ..." or "22.") as dispositivos and the articulação falls apart.

A line starts a new paragraph when:

- it is a grouping heading (TÍTULO / CAPÍTULO / Seção / Subseção + roman numeral), or the title line
  that follows one, or the line after that title;
- or it begins with a structural marker (``Art. N``, ``§ N``, ``Parágrafo único``, ``I -``, ``a)``,
  ``ANEXO``, or one of ``--start`` regexes) **and** the previous line ends with ``.``, ``:`` or ``;``.
  Without the second condition a citation wrapped as "(Lei nº 9.504/97, art. 28," / "§ 2º)." would
  start a spurious paragraph.

Every other line is appended to the previous paragraph (its runs are moved, so formatting is kept),
joined by a space, or without one when the previous line ends with a hyphen and the next starts in
lowercase. Empty paragraphs are removed. Tables are left untouched.

Usage:
    python3 scripts/lexml/rejoin_docx_lines.py IN.docx OUT.docx \\
        --start '^RESOLUÇÃO' --start '^Relator' --start '^Ementa' --start '^O Tribunal Superior Eleitoral' \\
        --start '^Sala de Sessões' --start '^Brasília,'
"""
import argparse
import copy
import re

import docx
from docx.oxml.ns import qn

MARKER = (r"Art\.\s*\d|§\s*\d|Parágrafo único|[IVXLC]+\s*[-–]\s|[a-z]\)\s|"
          r"(TÍTULO|CAPÍTULO|Seção|Subseção)\s|ANEXO")
HEAD = re.compile(r"^(TÍTULO|CAPÍTULO|Seção|Subseção)\s+[IVXLC]+$")


def rejoin(doc, extra_start=()):
    start = re.compile("^(?:" + "|".join([MARKER, *[s.lstrip("^") for s in extra_start]]) + ")")
    body = doc.element.body
    paras = [p for p in doc.paragraphs if p._p.getparent() is body]
    kept, prev_text, prev_head, prev_title = None, "", False, False
    n_in = n_out = 0
    for p in paras:
        text = p.text.strip()
        if not text:
            body.remove(p._p)
            continue
        n_in += 1
        new = (kept is None or prev_head or prev_title or HEAD.match(text)
               or (start.match(text) and prev_text.rstrip().endswith((".", ":", ";"))))
        if new:
            kept, n_out = p, n_out + 1
            prev_title = prev_head
        else:
            hyphen = prev_text.endswith("-") and text[:1].islower()
            _append(kept, p, joiner="" if hyphen else " ", drop_hyphen=hyphen)
            body.remove(p._p)
            prev_title = False
        prev_text, prev_head = text, bool(HEAD.match(text))
    return n_in, n_out


def _append(dst, src, joiner, drop_hyphen):
    """Move the runs of paragraph ``src`` to the end of ``dst``."""
    runs = dst._p.findall(qn("w:r"))
    if drop_hyphen:
        for r in reversed(runs):
            ts = r.findall(qn("w:t"))
            if ts and ts[-1].text:
                ts[-1].text = ts[-1].text.rstrip()[:-1]
                break
    else:
        for r in reversed(runs):
            ts = r.findall(qn("w:t"))
            if ts and ts[-1].text is not None:
                ts[-1].text = ts[-1].text.rstrip() + joiner
                ts[-1].set(qn("xml:space"), "preserve")
                break
    first = True
    for child in list(src._p):
        if child.tag == qn("w:pPr"):
            continue
        if first and child.tag == qn("w:r"):
            ts = child.findall(qn("w:t"))
            if ts and ts[0].text:
                ts[0].text = ts[0].text.lstrip()
            first = False
        dst._p.append(copy.deepcopy(child))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--start", action="append", default=[],
                    help="extra regex for lines that start a paragraph (front and closing matter)")
    args = ap.parse_args()
    doc = docx.Document(args.src)
    n_in, n_out = rejoin(doc, args.start)
    doc.save(args.dst)
    print(f"{args.src}: {n_in} lines -> {n_out} paragraphs")


if __name__ == "__main__":
    main()
