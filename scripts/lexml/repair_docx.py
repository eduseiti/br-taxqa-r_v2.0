#!/usr/bin/env python3
"""Apply hand-checked repairs to statutory source ``.docx`` files (corpus fix B, 2026-11-22).

Each repair names its document and finds its paragraphs by text, never by position, so a repair
that no longer applies fails loudly instead of editing the wrong place. The edited file replaces
the input (the fetched file stays in git history). Repairs, and why (see
``docs/<date>_fix_b_corpus_revision_results.md``):

* ``lei_12715_20120917``: the fetched page holds arts. 69–78 twice. The first copy ends in a garbled
  art. 78, § 2º, II (the start of III spliced with art. 68's quoted text), followed by stray copies
  of the quoted "Art. 2º" of art. 68. It is deleted; the second, clean copy stays. The two copies
  of arts. 69–78, § 2º, I are checked to be equal first, apart from the "(NR)" markers and dot
  leaders that only the second copy has right.
* ``decreto_lei_5844_19430923``: Seção IV of Capítulo I of Título V ("Da exploração de películas
  cinematográficas estrangeiras") numbers its article "Art. 93." between arts. 97 and 99. It is
  art. 98 (art. 100 cites "arts. 97 e 98"); art. 93 is in Seção IV of the previous chapter.

Usage::

    python3 scripts/lexml/repair_docx.py original/articulados/lei_12715_20120917.docx
    python3 scripts/lexml/repair_docx.py --all            # every document listed below
    python3 scripts/lexml/repair_docx.py --all --check    # exit 1 if any repair still applies
"""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = Path(__file__).resolve().parents[2]


def text_of(p) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t"))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def body_paragraphs(body):
    return [p for p in body if p.tag == W + "p"]


def find(paras, pattern, start=0):
    rx = re.compile(pattern)
    for i in range(start, len(paras)):
        if rx.search(text_of(paras[i])):
            return i
    return None


def repair_lei_12715(body) -> bool:
    paras = body_paragraphs(body)
    first = find(paras, r"^\s*Art\. 69\. Os arts\. 1º e 3º da Medida Provisória nº 2\.199-14")
    second = find(paras, r"^\s*Art\. 69\. Os arts\. 1º e 3º da Medida Provisória nº 2\.199-14", (first or 0) + 1)
    if first is None or second is None:
        return False                                  # already repaired
    # the copies agree from art. 69 through art. 78, § 2º, I
    end1 = find(paras, r"^\s*I - da nova redação dada ao § 15", first)
    end2 = find(paras, r"^\s*I - da nova redação dada ao § 15", second)
    # the first copy lacks the "(NR)" markers and has different dot leaders; nothing else differs
    loose = lambda p: re.sub(r"\(NR\)|\.{3,}|\s+", "", text_of(p))
    a = [loose(p) for p in paras[first:end1 + 1]]
    b = [loose(p) for p in paras[second:end2 + 1]]
    if a != b:
        raise SystemExit("lei_12715: the two copies of arts. 69-78 differ; repair not applied")
    for p in paras[first:second]:
        body.remove(p)
    print(f"  lei_12715: deleted paragraphs {first}..{second - 1} (garbled first copy of arts. 69-78)")
    return True


def replace_in_runs(p, old: str, new: str) -> None:
    ts = list(p.iter(W + "t"))
    for t in ts:
        if t.text and old in t.text:
            t.text = t.text.replace(old, new, 1)
            return
    raise SystemExit(f"'{old}' is split across runs in: {text_of(p)[:80]}")


def repair_dl_5844(body) -> bool:
    paras = body_paragraphs(body)
    i = find(paras, r"^\s*Art\. 93\. Considera.se rendimento tributável da exploração, no país, de películas")
    if i is None:
        return False
    prev = norm(text_of(paras[i - 1]))
    if prev != "Da exploração de películas cinematográficas estrangeiras":
        raise SystemExit(f"decreto_lei_5844: unexpected heading before the article: {prev!r}")
    replace_in_runs(paras[i], "93", "98")
    print("  decreto_lei_5844: 'Art. 93. Considera-se rendimento tributável…' -> 'Art. 98.'")
    return True


REPAIRS = {
    "lei_12715_20120917": repair_lei_12715,
    "decreto_lei_5844_19430923": repair_dl_5844,
}


def apply(path: Path, check: bool) -> bool:
    stem = path.stem
    if stem not in REPAIRS:
        raise SystemExit(f"no repair for {stem}")
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    tree = etree.fromstring(xml)
    body = tree.find(W + "body")
    changed = REPAIRS[stem](body)
    if not changed:
        print(f"  {stem}: already repaired")
        return False
    if check:
        return True
    tmp = Path(tempfile.mkstemp(suffix=".docx")[1])
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(item, data)
    shutil.move(tmp, path)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", nargs="*", type=Path)
    ap.add_argument("--all", action="store_true", help="repair every listed document in original/articulados")
    ap.add_argument("--check", action="store_true", help="only report; exit 1 if a repair still applies")
    a = ap.parse_args()
    paths = list(a.docx) + ([ROOT / "original/articulados" / f"{s}.docx" for s in REPAIRS] if a.all else [])
    pending = [p for p in paths if apply(p, a.check)]
    if a.check and pending:
        sys.exit(1)


if __name__ == "__main__":
    main()
