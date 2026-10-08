#!/usr/bin/env python3
"""Audit: do the statutory LexML files hold every article of their source ``.docx``?

Plan: ``docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md`` §3.1 (item 2 of the dataset
note's §7). A cited article that has no ``<Artigo id="artN">`` gets no chunk, so no retriever can
find it. The cases found so far were found only because a question cites them; this audit looks at
every article of every statutory document.

For each ``original/articulados/<stem>.docx``:

- **docx labels**: paragraphs that start an article (``Art. 8º``, ``Art. 4º-A``, ``Art 41.``),
  outside quoted text (a paragraph opening with a quote mark, or inside a quoted block that runs
  until a paragraph ending with a closing quote / ``(NR)``), mapped to parser ids
  (``art8``, ``art4-1``);
- **XML ids**: top-level ``Artigo`` ids of ``lexml/articulados/<stem>.xml`` and its
  ``<stem>.anexoN.xml`` files (an ``Artigo`` inside an ``Alteracao`` is quoted text, not
  top-level);
- **missing** = docx labels without a top-level id, split into **nested** (an ``Alteracao`` holds an
  ``Artigo`` whose id ends in that label, the unclosed-quote symptom of cause 2c) and **absent**;
- **cited missing**: article ids cited by ``dataset/references.jsonl`` and not among the XML ids,
  whatever the docx says. The gate: every cited missing id must be listed in
  ``scripts/lexml/unmatchable_articles.tsv`` with a reason, or the audit exits 1.

Usage::

    python3 scripts/lexml/audit_article_coverage.py [--lexml lexml/articulados] [--out report.md]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
L = "{http://www.lexml.gov.br/1.0}"

ART_RE = re.compile(r"^\s*Art(?:igo)?\.?\s*(\d+(?:\.\d{3})*)\s*(?:[ºo°˚]|\.)?\s*(?:[-–‑]\s*([A-Z])\b)?")
OPEN_Q = "“\"'‘«"
CLOSE_RE = re.compile(r"(”|\"|’|»|\(NR\)|\(AC\))\s*[.;,)]*\s*$")


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(W + "p"):
        out.append("".join(t.text or "" for t in p.iter(W + "t")).strip())
    return [t for t in out if t]


def docx_article_ids(path: Path) -> list[str]:
    ids: list[str] = []
    quoted = False
    for text in docx_paragraphs(path):
        starts_quoted = text[:1] in OPEN_Q
        if starts_quoted and not CLOSE_RE.search(text):
            quoted = True
            continue
        if quoted:
            if CLOSE_RE.search(text):
                quoted = False
            continue
        if starts_quoted:
            continue
        m = ART_RE.match(text)
        if m:
            n = m.group(1).replace(".", "")
            ids.append(f"art{int(n)}" + (f"-{ord(m.group(2)) - 64}" if m.group(2) else ""))
    return ids


def xml_article_ids(lexml_dir: Path, stem: str) -> tuple[list[str], set[str], list[str]]:
    """Top-level ids (all files), ids nested in an Alteracao, ids duplicated within one file."""
    top: list[str] = []
    nested: set[str] = set()
    dups: list[str] = []
    files = [lexml_dir / f"{stem}.xml"] + sorted(lexml_dir.glob(f"{stem}.anexo*.xml"))
    for f in files:
        if not f.exists():
            continue
        tree = etree.parse(str(f))
        here: list[str] = []
        for a in tree.iter(L + "Artigo"):
            aid = a.get("id") or ""
            if any(anc.tag == L + "Alteracao" for anc in a.iterancestors()):
                m = re.search(r"(art\d+(?:-\d+)?)$", aid)
                if m:
                    nested.add(m.group(1))
            else:
                here.append(re.sub(r"^.*?(art\d+(?:-\d+)?)$", r"\1", aid))
        top += here
        suffix = "" if f.name == f"{stem}.xml" else f" ({f.name.split('.')[-2]})"
        dups += [a + suffix for a in sorted({a for a in here if here.count(a) > 1})]
    return top, nested, dups


def cited_articles(refs: Path) -> dict[str, set[str]]:
    cited: dict[str, set[str]] = defaultdict(set)
    if not refs.exists():
        return cited
    for line in refs.open(encoding="utf-8"):
        r = json.loads(line)
        for aid in r.get("article_ids") or []:
            cited[r["document_id"]].add(aid)
    return cited


def load_unmatchable(path: Path) -> dict[tuple[str, str], str]:
    out = {}
    if path.exists():
        for line in path.open(encoding="utf-8"):
            if line.startswith(("#", "document_id\t")) or not line.strip():
                continue
            doc, aid, reason = line.rstrip("\n").split("\t")[:3]
            out[(doc, aid)] = reason
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--original", type=Path, default=ROOT / "original/articulados")
    ap.add_argument("--lexml", type=Path, default=ROOT / "lexml/articulados")
    ap.add_argument("--references", type=Path, default=ROOT / "dataset/references.jsonl")
    ap.add_argument("--unmatchable", type=Path, default=ROOT / "scripts/lexml/unmatchable_articles.tsv")
    ap.add_argument("--out", type=Path, default=None, help="write the Markdown report here")
    args = ap.parse_args()

    cited = cited_articles(args.references)
    unmatchable = load_unmatchable(args.unmatchable)
    rows = []
    gate: list[tuple[str, str]] = []
    for docx in sorted(args.original.glob("*.docx")):
        stem = docx.stem
        labels = docx_article_ids(docx)
        top, nested, dup_xml = xml_article_ids(args.lexml, stem)
        top_set = set(top)
        missing = [a for a in dict.fromkeys(labels) if a not in top_set]
        dup_labels = sorted({a for a in labels if labels.count(a) > 1})
        cited_missing = sorted(a for a in cited.get(stem, ()) if a not in top_set)
        for a in cited_missing:
            if (stem, a) not in unmatchable:
                gate.append((stem, a))
        rows.append({
            "stem": stem, "cited": stem in cited, "docx": len(set(labels)), "xml": len(top_set),
            "nested": [a for a in missing if a in nested],
            "absent": [a for a in missing if a not in nested],
            "dup_labels": dup_labels, "dup_xml": dup_xml, "cited_missing": cited_missing,
        })

    def short(xs: list[str], n: int = 12) -> str:
        return ", ".join(xs[:n]) + (f", … (+{len(xs) - n})" if len(xs) > n else "")

    problems = [r for r in rows if r["nested"] or r["absent"] or r["dup_xml"] or r["cited_missing"]]
    problems.sort(key=lambda r: (not r["cited_missing"], not r["cited"], r["stem"]))
    md = ["# Article coverage audit", "",
          f"{len(rows)} statutory documents; {len(problems)} with a difference between the `.docx` "
          f"article labels and the top-level `Artigo` ids. Cited missing ids not in "
          f"`unmatchable_articles.tsv`: **{len(gate)}**.", "",
          "| Document | cited | docx | xml | cited missing | nested in Alteracao | absent from XML | duplicate XML ids |",
          "|---|---|---|---|---|---|---|---|"]
    for r in problems:
        cm = ", ".join(f"{a}{'' if (r['stem'], a) not in unmatchable else ' (unmatchable)'}"
                       for a in r["cited_missing"])
        md.append(f"| `{r['stem']}` | {'yes' if r['cited'] else ''} | {r['docx']} | {r['xml']} | {cm} | "
                  f"{short(r['nested'])} | {short(r['absent'])} | {short(r['dup_xml'])} |")
    text = "\n".join(md) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    if gate:
        print("GATE FAILED: cited articles missing from the XML and not listed as unmatchable:",
              file=sys.stderr)
        for stem, a in gate:
            print(f"  {stem}\t{a}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
