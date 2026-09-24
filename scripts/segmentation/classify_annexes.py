#!/usr/bin/env python3
"""Annex router (plan §4): the only place that decides which segmenter handles an annex.

Rule (elements inside Alteracao are ignored):
    any Artigo                              -> A (XSL)
    elif any Item|Alinea|Inciso|Paragrafo|Caput -> B (XSL; top-level dispositivos -> DSP)
    else                                    -> C (Python, full document)
    A/B with direct p/table children of Articulacao / PartePrincipal / (annex) Preambulo
                                            -> also Python, loose-content mode

The root element (DocumentoArticulado / DocumentoGenerico) is recorded but not used.
``loose_elements`` is also used for main statutory documents (deviation D1 of the execution log).

Output: segmented/annex_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from common import (ANEXO_RE, ART_DIR, DEFAULT_EMENTA_MAX_TOKENS, DEFAULT_TOKENIZER, SEG_DIR, L,
                    NSMAP, doc_urn, get_tokenizer, in_alteracao, metadata_for, parse, resolve_parent)

EXPECTED = {"A": 12, "B": 50, "C": 181}
LOOSE_CONTAINERS = ("Articulacao", "PartePrincipal")


@dataclass
class AnnexDecision:
    arquivo: str
    familia: str
    pai: str
    raiz: str
    categoria: str
    n_artigos: int
    n_dispositivos_topo: int
    n_soltos: int
    segmentadores: str
    metadados: str
    pai_resolucao: str = ""


def loose_elements(tree, include_preambulo: bool) -> list:
    """Direct p/table children of Articulacao/PartePrincipal (+ Preambulo of annexes)."""
    out = []
    for e in tree.getroot().iter():
        name = L(e)
        if name in LOOSE_CONTAINERS or (include_preambulo and name == "Preambulo"):
            if in_alteracao(e):
                continue
            out += [c for c in e if L(c) in ("p", "table")]
    return out


def classify_tree(tree) -> tuple[str, int, int]:
    """(categoria, n_artigos, n_dispositivos_topo)."""
    n_art, n_top, n_disp = 0, 0, 0
    for e in tree.getroot().iter():
        name = L(e)
        if name not in ("Artigo", "Caput", "Paragrafo", "Inciso", "Alinea", "Item") or in_alteracao(e):
            continue
        if name == "Artigo":
            n_art += 1
        else:
            n_disp += 1
            if not any(L(a) in ("Artigo", "Caput", "Paragrafo", "Inciso", "Alinea", "Item")
                       for a in e.iterancestors()):
                n_top += 1
    cat = "A" if n_art else ("B" if n_disp else "C")
    return cat, n_art, n_top


def classify(path: Path, tok=None, ementa_max_tokens: int = DEFAULT_EMENTA_MAX_TOKENS) -> AnnexDecision:
    tree = parse(path)
    cat, n_art, n_top = classify_tree(tree)
    loose = loose_elements(tree, include_preambulo=True) if cat in ("A", "B") else []
    segs = {"A": "xsl", "B": "xsl", "C": "python"}[cat]
    if loose:
        segs += "+python-loose"
    urn = doc_urn(tree)
    parent, how = resolve_parent(path, urn)
    meta = metadata_for(path, tok, ementa_max_tokens, tree=tree)
    root = tree.xpath("/l:LexML/l:Anexo/*", namespaces=NSMAP)
    return AnnexDecision(
        arquivo=path.name, familia=ANEXO_RE.sub("", path.name[:-4]),
        pai=parent.name if parent else "", raiz=L(root[0]) if root else "",
        categoria=cat, n_artigos=n_art, n_dispositivos_topo=n_top, n_soltos=len(loose),
        segmentadores=segs, metadados=meta.text(), pai_resolucao=how)


def classify_all(art_dir: Path = ART_DIR, tok=None, only=None,
                 ementa_max_tokens: int = DEFAULT_EMENTA_MAX_TOKENS) -> list[AnnexDecision]:
    paths = sorted(p for p in art_dir.glob("*.xml") if ANEXO_RE.search(p.name[:-4]))
    if only:
        paths = [p for p in paths if only(p)]
    return [classify(p, tok, ementa_max_tokens) for p in paths]


def write_manifest(decisions: list[AnnexDecision], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[f.name for f in fields(AnnexDecision)],
                           quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writeheader()
        for d in decisions:
            w.writerow(asdict(d))


def check_counts(decisions: list[AnnexDecision], allow_change: bool) -> dict:
    counts = {k: sum(d.categoria == k for d in decisions) for k in "ABC"}
    if counts != EXPECTED and not allow_change:
        raise SystemExit(f"annex category counts changed: {counts} != {EXPECTED} "
                         "(re-parse? use --allow-count-change)")
    return counts


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", type=Path, default=SEG_DIR / "annex_manifest.csv")
    p.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    p.add_argument("--ementa-max-tokens", type=int, default=DEFAULT_EMENTA_MAX_TOKENS)
    p.add_argument("--allow-count-change", action="store_true")
    args = p.parse_args(argv)
    decisions = classify_all(tok=get_tokenizer(args.tokenizer), ementa_max_tokens=args.ementa_max_tokens)
    counts = check_counts(decisions, args.allow_count_change)
    write_manifest(decisions, args.out)
    unresolved = [d.arquivo for d in decisions if not d.pai]
    loose = {k: sum(1 for d in decisions if d.categoria == k and d.n_soltos) for k in "AB"}
    print(f"categories {counts}; A/B with loose content {loose}; unresolved parents {unresolved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
