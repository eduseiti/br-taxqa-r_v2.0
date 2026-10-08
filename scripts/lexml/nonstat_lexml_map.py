#!/usr/bin/env python3
"""Regenerate ``scripts/dataset/nonstat_lexml_map.tsv`` from the non-statutory parse output.

``lexml/nao_articulados/*.xml`` are named after their URN, so the source stem is not in the name.
Since the rebuild (plan §3.2) every source is parsed with a **declared** URN
(``scripts/lexml/nonstat_metadata.tsv``, ``lexml_nonstat parse --metadata``), so the map is exact:
the main XML whose ``Identificacao/@URN`` equals the stem's declared URN. The script fails unless
every stem maps to exactly one XML and every main XML to exactly one stem.

Usage::

    python3 scripts/lexml/nonstat_lexml_map.py
"""
import csv
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "scripts" / "lexml" / "nonstat_metadata.tsv"
OUT = ROOT / "scripts" / "dataset" / "nonstat_lexml_map.tsv"
NAO = ROOT / "lexml" / "nao_articulados"
L = "{http://www.lexml.gov.br/1.0}"


def main() -> int:
    rows = csv.DictReader((ln for ln in open(META, encoding="utf-8") if not ln.startswith("#")), delimiter="\t")
    declared = {r["stem"]: r["urn"] for r in rows}
    by_urn: dict[str, list[str]] = {}
    for f in sorted(NAO.glob("*.xml")):
        if "!anexo" in f.name:
            continue
        urn = etree.parse(str(f)).find(f".//{L}Identificacao").get("URN")
        by_urn.setdefault(urn, []).append(f.name)
    errors = []
    out = []
    for stem, urn in sorted(declared.items()):
        files = by_urn.get(urn, [])
        if len(files) != 1:
            errors.append(f"{stem}: {len(files)} XML files with URN {urn}")
            continue
        out.append((stem, files[0], "declared-urn"))
    orphans = sorted(f for u, fs in by_urn.items() if u not in set(declared.values()) for f in fs)
    errors += [f"XML with no declared source: {f}" for f in orphans]
    if errors:
        sys.exit("\n".join(errors))
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["stem", "lexml_file", "match"])
        w.writerows(out)
    print(f"{len(out)} stems -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
