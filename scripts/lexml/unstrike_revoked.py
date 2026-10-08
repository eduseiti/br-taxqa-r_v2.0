#!/usr/bin/env python3
"""Un-strike dispositivos revoked by a given act, so the statutory parser keeps them.

Planalto prints revoked text with strike-through, and the statutory parser drops struck runs, which
takes the whole article with it (rebuild plan §3.1, cause 2a). The P&R IRPF 2024 covers calendar
year 2023, so a dispositivo revoked by an act that took effect later (Lei nº 14.754, de 12/12/2023,
effective 2024) is still the right legal basis and must be in the corpus, in its 2023 wording.

A paragraph whose text carries ``(Revogad… pel… <--revoked-by>…)`` has the strike removed from every
run (the note stays in the text). The following paragraphs that are struck in full and do not
start a new article (its incisos, alíneas, parágrafos, quoted amending text) are un-struck too.
Other struck text (superseded wordings, earlier revocations) is left alone.

Usage::

    python3 scripts/lexml/unstrike_revoked.py IN.docx OUT.docx --revoked-by 'Lei nº 14\\.754, de 2023'
"""
import argparse
import re
import shutil
import tempfile
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ART_RE = re.compile(r"^\s*Art\.?\s*\d")


def text_of(p) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t"))


def struck(r) -> bool:
    s = r.find(f"{W}rPr/{W}strike")
    return s is not None and s.get(W + "val", "true") not in ("0", "false")


def unstrike(p) -> int:
    n = 0
    for r in p.iter(W + "r"):
        for tag in ("strike", "dstrike"):
            s = r.find(f"{W}rPr/{W}{tag}")
            if s is not None:
                s.getparent().remove(s)
                n += 1
    return n


def fully_struck(p) -> bool:
    runs = [r for r in p.iter(W + "r") if "".join(t.text or "" for t in r.iter(W + "t")).strip()]
    return bool(runs) and all(struck(r) for r in runs)


def process(root, revoked_by: str) -> list[str]:
    note = re.compile(rf"\(Revogad[oa]s?\s+pel[oa]s?\s+{revoked_by}")
    changed = []
    following = False
    for p in root.iter(W + "p"):
        txt = text_of(p).strip()
        if not txt:
            continue
        if note.search(txt):
            if unstrike(p):
                changed.append(txt[:90])
            following = True
        elif following and fully_struck(p) and not ART_RE.match(txt):
            unstrike(p)
            changed.append("  " + txt[:88])
        else:
            following = False
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--revoked-by", required=True, help="regex of the revoking act, e.g. 'Lei nº 14\\.754, de 2023'")
    args = ap.parse_args()
    with zipfile.ZipFile(args.src) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
        changed = process(root, args.revoked_by)
        data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    zout.writestr(item, data if item.filename == "word/document.xml" else zin.read(item.filename))
    shutil.move(tmp.name, args.dst)
    print(f"{len(changed)} paragraphs un-struck")
    for c in changed:
        print("  " + c)


if __name__ == "__main__":
    main()
