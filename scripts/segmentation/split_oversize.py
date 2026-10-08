#!/usr/bin/env python3
"""Oversize article splitting (plan §5b).

Replaces, in place, every ART/DSP row of a statutory CSV whose Texto is above the cap by parts built
along the structure:

1. the split items of an article are its direct children (Caput, each Paragrafo, …); of a DSP, its
   direct child dispositivos (and tables / Pena / Alteracao, which also hold text);
2. consecutive items are packed greedily while prefix + HEAD + items <= cap, where HEAD is the
   ancestor path of the part's first item (article label [+ caput sentence for paragraphs, X3b]
   [+ the opening of every unit that was descended into]);
3. an item over the cap by itself is replaced by its own items (incisos -> alíneas -> itens);
4. a leaf over the cap by itself is split within itself: tables by row groups with the header
   repeated, text at sentence then word boundaries; every piece keeps HEAD + the leaf's label.

Part columns: Rotulo + ", parte k/n"; urn + "_p<k>"; Num_Inicio/Num_Final = span of the dispositivos
in the part (pieces share their leaf's interval). Provenance goes to <csv>.prov.jsonl:
{urn, parte, n_partes, cobre_ids, parcial_ids}.

The input CSV must be the XSL output as written (row i <-> common.xsl_row_elements()[i]).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from common import (DEFAULT_MAX_TOKENS, DEFAULT_TOKENIZER, DISPOSITIVOS, POS_TYPES, L, Positions,
                    Tokenizer, caminho_parts, doc_urn, get_tokenizer, in_article_paragraph,
                    join_text, norm, own_parts, parse, split_sentences, split_table_rows,
                    table_header_count, tabela, tabela_rows, texto, truncate_tokens, write_prov,
                    write_rows, read_rows, xsl_row_elements)

HEAD_TAGS = ("Rotulo", "TituloDispositivo", "p")


@dataclass
class Item:
    head: list[str]               # ancestor path printed when the item starts a part
    body: str                     # text of the item
    element: object               # dispositivo / table / … (for pieces: the leaf)
    whole: bool                   # True: element wholly in this item; False: a piece of it
    oversize: bool = False        # cannot be cut further and still over the cap
    ancestors: list = field(default_factory=list)   # descended units between root and element


def items_of(e) -> list:
    """Direct children of e that carry text other than e's own head (Rotulo/Titulo/p)."""
    out = []
    for c in e:
        name = L(c)
        if name is None or name in HEAD_TAGS:
            continue
        if (tabela(c) if name == "table" else texto(c)):
            out.append(c)
    return out


def body_of_element(c) -> str:
    return tabela(c) if L(c) == "table" else texto(c)


class ArticleSplitter:
    def __init__(self, root, prefix: str, cap: int, tok: Tokenizer):
        self.root, self.prefix, self.cap, self.tok = root, prefix, cap, tok
        self.leaf_split = False
        self.head_truncated = False

    def big_head(self, head: list[str]) -> bool:
        h = norm(" ".join(head))
        return bool(h) and self.tok.count(self.prefix + h) > self.cap // 2

    def head_text(self, head: list[str], truncate: bool = True) -> str:
        """HEAD as printed. A repeated context that alone takes more than half of the cap (e.g. the
        ~1,900-token caput of CLT art. 670 repeated before each of its paragraphs) is truncated to
        a quarter of the cap once its full text has been shown in an earlier part (deviation D3)."""
        h = norm(" ".join(head))
        if truncate and self.big_head(head):
            h = truncate_tokens(h, self.cap // 4, self.tok)[0]
        return h

    def fits(self, head: list[str], bodies: list[str], truncate: bool = True) -> bool:
        return self.tok.count(join_text(self.prefix + self.head_text(head, truncate), bodies)) <= self.cap

    def expand(self, e, ancestors: list) -> list[Item]:
        out: list[Item] = []
        children = items_of(e)
        if not children:  # e is a leaf (only possible for the root: other leaves are handled below)
            return self.leaf_pieces(e, ancestors)
        for c in children:
            head = caminho_parts(c, caput="frase")  # caput plan Q2: HEAD keeps the caput
            body = body_of_element(c)
            if self.fits(head, [body]):
                out.append(Item(head, body, c, True, ancestors=ancestors))
            elif L(c) == "table":
                out += self.table_pieces(c, head, ancestors)
            elif L(c) in DISPOSITIVOS and items_of(c):
                out += self.expand(c, ancestors + [c])
            else:
                out += self.leaf_pieces(c, ancestors)
        return out

    def leaf_pieces(self, c, ancestors) -> list[Item]:
        """Text leaf over the cap: pieces at sentence (then word) boundaries; every piece keeps
        HEAD + the leaf's label."""
        self.leaf_split = True
        head = caminho_parts(c, caput="frase")  # caput plan Q2: HEAD keeps the caput
        if L(c) in DISPOSITIVOS:
            label = [norm(x.xpath("string()")) for x in c if L(x) in ("Rotulo", "TituloDispositivo")]
            text = norm(" ".join(norm(x.xpath("string()")) for x in c if L(x) == "p"))
        else:  # Alteracao / Pena / DispositivoGenerico: whole text, no own label
            label, text = [], texto(c)
        pieces = split_sentences(text, norm(self.prefix + self.head_text(head + label)), self.cap, self.tok)
        out = []
        for i, piece in enumerate(pieces):
            h = head + label if i else head
            body = norm(" ".join(label + [piece])) if i == 0 else piece
            over = not self.fits(h, [body])
            out.append(Item(h, body, c, False, over, ancestors))
        return out

    def table_pieces(self, t, head, ancestors) -> list[Item]:
        self.leaf_split = True
        rows = tabela_rows(t)
        groups = split_table_rows(rows, table_header_count(t), norm(self.prefix + self.head_text(head)),
                                  self.cap, self.tok)
        return [Item(head, norm("Tabela: " + " ; ".join(g)), t, False, over, ancestors)
                for g, over in groups]

    def parts(self) -> list[list[Item]]:
        items = self.expand(self.root, [])
        groups: list[list[Item]] = []
        self._head_of: dict = {}
        shown = ""                      # text of the parts built so far
        s, n = 0, len(items)
        while s < n:
            head = items[s].head
            trunc = False
            if self.big_head(head):
                if not all(h in shown for h in head if h):
                    # first appearance of a large context: its full text goes into part(s) of its own
                    owner = next((a for a in [items[s].element, *items[s].element.iterancestors()]
                                  if L(a) in DISPOSITIVOS and a is not items[s].element), self.root)
                    full = norm(" ".join(head))
                    for piece in split_sentences(full, self.prefix, self.cap, self.tok):
                        g = [Item([], piece, owner, False, not self.fits([], [piece]), items[s].ancestors)]
                        self._head_of[id(g)] = ""
                        groups.append(g)
                        shown += " " + piece
                trunc = True
                self.head_truncated = True
            e = s + 1
            while e < n and self.fits(head, [it.body for it in items[s:e + 1]], trunc):
                e += 1
            g = items[s:e]
            self._head_of[id(g)] = self.head_text(head, trunc)
            groups.append(g)
            shown += " " + self.part_text(g)
            s = e
        return groups

    def part_text(self, group: list[Item]) -> str:
        return join_text(self.prefix + self._head_of[id(group)], [it.body for it in group])


def nearest_counted(e, pos: Positions):
    for a in [e, *e.iterancestors()]:
        if L(a) in POS_TYPES:
            return a
    return None


def part_provenance(root, group: list[Item], pos: Positions) -> dict:
    cobre, parcial = [], [root.get("id", "")]
    spans = []
    for it in group:
        el = it.element
        if it.whole:
            if el.get("id"):
                cobre.append(el.get("id"))
        else:
            parcial.append(el.get("id", ""))
        parcial += [a.get("id", "") for a in it.ancestors]
        ref = el if (it.whole and L(el) in POS_TYPES) else nearest_counted(el, pos)
        if ref is not None:
            spans.append(pos[ref])
    first = group[0].element
    if in_article_paragraph(first) and L(root) == "Artigo":
        # caput sentence repeated in HEAD (X3b)
        parcial += [c.get("id", "") for c in root if L(c) == "Caput"]
    parcial = [x for x in dict.fromkeys(parcial) if x and x not in cobre]
    return {"cobre_ids": cobre, "parcial_ids": parcial,
            "span": (min(s for s, _ in spans), max(e for _, e in spans)) if spans else pos[root]}


def split_csv(csv_path: Path, xml_path: Path, meta_text: str, tok: Tokenizer,
              cap: int = DEFAULT_MAX_TOKENS, tree=None) -> dict:
    """Split the over-cap ART/DSP rows of csv_path in place; writes the provenance sidecar."""
    from common import prefixo
    rows = read_rows(csv_path)
    tree = tree if tree is not None else parse(xml_path)
    els = xsl_row_elements(tree)
    if len(els) != len(rows):
        raise RuntimeError(f"{csv_path.name}: {len(rows)} rows but {len(els)} XSL elements")
    prefix = prefixo(meta_text)
    base_rows = [(i, r) for i, r in enumerate(rows) if r["Tipo"] in ("ART", "DSP")]
    counts = tok.count_many([r["Texto"] for _, r in base_rows])
    pos = None
    out_rows: list[dict] = []
    prov: list[dict] = []
    report: list[dict] = []
    over = {i: n for (i, _), n in zip(base_rows, counts) if n > cap}
    urn = doc_urn(tree)
    for i, r in enumerate(rows):
        tipo, el = els[i]
        if r["urn"] != f"{urn}!{el.get('id', '')}" or r["Tipo"] != tipo:
            raise RuntimeError(f"{csv_path.name}: row {i} ({r['Tipo']} {r['urn']}) does not match "
                               f"XSL element {tipo} {el.get('id')}")
        if i not in over:
            out_rows.append(r)
            continue
        pos = pos or Positions(tree)
        sp = ArticleSplitter(el, prefix, cap, tok)
        groups = sp.parts()
        n = len(groups)
        uncut = []
        for k, g in enumerate(groups, 1):
            text = sp.part_text(g)
            pv = part_provenance(el, g, pos)
            purn = f"{r['urn']}_p{k}"
            ntok = tok.count(text)
            if ntok > cap:
                uncut.append({"parte": k, "tokens": ntok})
            out_rows.append({"Tipo": r["Tipo"], "Rotulo": f"{r['Rotulo']}, parte {k}/{n}",
                             "Num_Inicio": pv["span"][0], "Num_Final": pv["span"][1],
                             "Texto": text, "urn": purn})
            prov.append({"urn": purn, "parte": k, "n_partes": n, "unidade_id": el.get("id", ""),
                         "nivel": r["Tipo"], "cobre_ids": pv["cobre_ids"],
                         "parcial_ids": pv["parcial_ids"], "oversize": ntok > cap,
                         "intervalo_unidade": list(pos[el])})
        report.append({"urn": r["urn"], "rotulo": r["Rotulo"], "tokens": over[i], "partes": n,
                       "leaf_split": sp.leaf_split, "head_truncated": sp.head_truncated,
                       "uncuttable": uncut})
    write_rows(csv_path, out_rows)
    write_prov(csv_path, prov)
    return {"split": report, "rows_in": len(rows), "rows_out": len(out_rows)}


def main(argv=None) -> int:
    from common import metadata_for
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("csv", type=Path)
    p.add_argument("xml", type=Path)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    args = p.parse_args(argv)
    tok = get_tokenizer(args.tokenizer)
    res = split_csv(args.csv, args.xml, metadata_for(args.xml, tok).text(), tok, args.max_tokens)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
