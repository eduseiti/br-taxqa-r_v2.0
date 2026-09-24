#!/usr/bin/env python3
"""Non-statutory segmenter (plan §5, lxml).

Modes:
  document  a whole nao_articulados file or a category-C annex -> its own CSV;
  loose     only the direct p/table children of Articulacao / PartePrincipal (and, for annexes,
            Preambulo) of a statutory file, appended to its XSL CSV with numbering from --offset.

Units (§5.2): Agrupamento[texto|nota|preambulo|formulaPromulgacao|tituloAnexo|…] -> TXT;
tables -> TAB (the short p right before becomes the caption); runs of loose p -> TXT with a
synthetic id; AgrupamentoHierarquico and statutory groupings without articles -> heading lines.
epigrafe/ementa -> prefix (ementa also a TXT when truncated there); assinatura / localDataFecho /
preliminar -> dropped (Q4), except those with >= --keep-dropped-min-chars characters (deviation D2).

Every row gets a provenance record in <csv>.prov.jsonl (plan §2.7, §5b).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from common import (AGRUPADORES, DEFAULT_EMENTA_MAX_TOKENS, DEFAULT_MAX_TOKENS, DEFAULT_TOKENIZER,
                    DISPOSITIVOS, L, NSMAP, Meta, Tokenizer, child_elems, doc_urn, get_tokenizer,
                    join_text, metadata_for, norm, parse, prefixo, read_prov, read_rows,
                    split_lines, split_sentences, split_table_rows, table_header_count,
                    tabela_rows, write_prov, write_rows, xstring)

KEEP = {"texto", "nota", "preambulo", "formulaPromulgacao", "tituloAnexo"}
DROP = {"assinatura", "localDataFecho", "preliminar"}
PREFIX_ONLY = {"epigrafe"}
SKIP = {"Bloco", "Rotulo", "NomeAgrupador", "Anexos", "ReferenciaAnexo", "Epigrafe", "Ementa",
        "TituloDispositivo", "Omissis", "Alteracao", "ParteInicial", "ParteFinal"}
DEFAULT_KEEP_DROPPED_MIN_CHARS = 300


@dataclass
class Unit:
    kind: str                     # TXT | TAB
    uid: str
    label: str                    # Rotulo without sigla
    heading: str
    agr_ids: list[str]
    agr_labels: list[str]
    lines: list[str] = field(default_factory=list)
    table: object = None
    caption: str = ""
    synthetic: bool = False
    note: str = ""


@dataclass
class Result:
    rows: list[dict]
    prov: list[dict]
    stats: dict


def li_lines(ul) -> list[str]:
    out = []
    for li in child_elems(ul, "li"):
        own = _li_own(li)
        if own:
            out.append(own)
        for sub in li.iter(f"{{{NSMAP['l']}}}ul", f"{{{NSMAP['l']}}}ol"):
            if sub.getparent() is li:
                out += li_lines(sub)
    return out


def _li_own(li) -> str:
    parts = [li.text or ""]
    for c in li:
        if L(c) not in ("ul", "ol"):
            parts.append(xstring(c))
        parts.append(c.tail or "")
    return norm("".join(parts))


def lines_of(e) -> list[str]:
    if L(e) in ("ul", "ol"):
        return li_lines(e)
    s = norm(xstring(e))
    return [s] if s else []


def is_caption(p) -> bool:
    s = norm(xstring(p))
    return bool(s) and len(s) < 200 and not s.endswith(".")


def heading_of(e) -> str:
    rot = child_elems(e, "Rotulo")
    nome = child_elems(e, "NomeAgrupador")
    parts = [norm(xstring(x[0])) for x in (rot, nome) if x]
    return " – ".join(p for p in parts if p)


class Segmenter:
    def __init__(self, xml_path: Path, tok: Tokenizer, cap: int, ementa_max_tokens: int,
                 keep_dropped_min_chars: int, meta: Meta | None = None, tree=None):
        self.path = Path(xml_path)
        self.tree = tree if tree is not None else parse(self.path)
        self.tok, self.cap = tok, cap
        self.meta = meta or metadata_for(self.path, tok, ementa_max_tokens, tree=self.tree)
        self.prefix = prefixo(self.meta.text())
        self.sigla = self.path.name[:-4]
        self.urn = doc_urn(self.tree)
        self.keep_min = keep_dropped_min_chars
        self.units: list[Unit] = []
        # the element already used as the annex title in the prefix (plan §2.3) is prefix-only
        self.title_el = self._annex_title_element()
        self.n_tables = 0
        self.stats = {"dropped": [], "kept_long_dropped": [], "unknown": [], "oversize": [],
                      "split_units": 0, "ementa_chunk": False, "meta_source": self.meta.source,
                      "meta_truncated": self.meta.truncated}

    def _annex_title_element(self):
        if not self.meta.anexo_label:
            return None
        r = self.tree.xpath("/l:LexML/l:Anexo/l:DocumentoGenerico/l:PartePrincipal/l:Agrupamento[@nome='tituloAnexo']"
                            " | /l:LexML/l:Anexo/l:DocumentoGenerico/l:PartePrincipal/l:p[1]", namespaces=NSMAP)
        for e in r:
            if L(e) == "Agrupamento" or norm(xstring(e)).upper().startswith("ANEXO"):
                return e if norm(xstring(e)) and norm(xstring(e)) in self.meta.anexo_label else None
        return None

    # ---------------- unit collection ----------------
    def add_run(self, run: list, container, headings):
        if not run:
            return
        lines = [ln for e in run for ln in lines_of(e)]
        if not lines:
            return
        ps = [c for c in container if L(c) == "p"]
        pidx = [ps.index(e) + 1 for e in run if L(e) == "p"]
        base = container.get("id") or L(container).lower()
        uid = f"{base}_p{pidx[0]}-p{pidx[-1]}" if pidx else f"{base}_lista"
        ids, labels = [h[0] for h in headings], [h[1] for h in headings]
        self.units.append(Unit("TXT", uid, ", ".join(labels) or "texto", " > ".join(labels),
                               ids, labels, lines=lines, synthetic=True))

    def add_table(self, t, caption: str, headings):
        self.n_tables += 1
        ids, labels = [h[0] for h in headings], [h[1] for h in headings]
        lab = ", ".join(labels + [f"Tabela {self.n_tables}"])
        self.units.append(Unit("TAB", t.get("id", f"tab{self.n_tables}"), lab, " > ".join(labels),
                               ids, labels, table=t, caption=caption))

    def walk(self, container, headings, loose: bool = False):
        run: list = []
        for child in container:
            name = L(child)
            if name is None:
                continue
            if child is self.title_el:
                self.stats["annex_title_prefix_only"] = norm(xstring(child))
                continue
            if name in ("p", "ul", "ol"):
                run.append(child)
                continue
            if name == "table":
                caption = ""
                if run and L(run[-1]) == "p" and is_caption(run[-1]):
                    caption = norm(xstring(run.pop()))
                self.add_run(run, container, headings)
                run = []
                self.add_table(child, caption, headings)
                continue
            self.add_run(run, container, headings)
            run = []
            if loose:
                continue  # statutory content is covered by the XSL
            if name == "Agrupamento":
                self.agrupamento(child, headings)
            elif name == "AgrupamentoHierarquico" or name in AGRUPADORES:
                h = heading_of(child)
                n_before = len(self.units)
                self.walk(child, headings + [(child.get("id", ""), h)])
                if len(self.units) == n_before and h:
                    # heading-only grouping (e.g. decreto_lei_58_19371210.anexo1 "LIVRO AUXILIAR N. 8")
                    ids, labels = [x[0] for x in headings], [x[1] for x in headings]
                    self.units.append(Unit("TXT", child.get("id", ""), ", ".join(labels + [h]),
                                           " > ".join(labels), ids, labels, lines=[h]))
            elif name in SKIP or name in DISPOSITIVOS or name == "Artigo":
                continue
            else:
                self.stats["unknown"].append(name)
                self.walk(child, headings)
        self.add_run(run, container, headings)

    def agrupamento(self, a, headings):
        nome = a.get("nome", "")
        text = norm(xstring(a))
        if nome in PREFIX_ONLY:
            return
        if nome == "ementa":
            if self.meta.truncated and a.get("id") == self.meta.ementa_id:
                self.stats["ementa_chunk"] = True
                self._agr_unit(a, headings, "ementa")
            return
        if nome in DROP:
            if self.keep_min and len(text) >= self.keep_min:
                self.stats["kept_long_dropped"].append({"id": a.get("id"), "nome": nome, "chars": len(text)})
                self._agr_unit(a, headings, nome, note=f"kept:{nome}")
            else:
                self.stats["dropped"].append({"id": a.get("id"), "nome": nome, "chars": len(text)})
            return
        if nome not in KEEP:
            self.stats["unknown"].append(f"Agrupamento[{nome}]")
        self._agr_unit(a, headings, nome)

    def _agr_unit(self, a, headings, nome, note=""):
        lines: list[str] = []
        prev_p = None
        for c in a:
            name = L(c)
            if name == "table":
                caption = ""
                if prev_p is not None and is_caption(prev_p) and lines and lines[-1] == norm(xstring(prev_p)):
                    caption = lines.pop()
                self.add_table(c, caption, headings)
                prev_p = None
            elif name in ("p", "ul", "ol"):
                lines += lines_of(c)
                prev_p = c if name == "p" else None
            elif name is not None and name not in SKIP:
                self.stats["unknown"].append(f"Agrupamento/{name}")
                lines += lines_of(c)
        # the TXT unit precedes its tables in reading order only by position in the Agrupamento;
        # tables were appended as they appeared, so insert the TXT unit before them
        if lines:
            ids, labels = [h[0] for h in headings], [h[1] for h in headings]
            unit = Unit("TXT", a.get("id", ""), ", ".join(labels) or nome, " > ".join(labels),
                        ids, labels, lines=lines, note=note)
            k = len(self.units)
            while k > 0 and self.units[k - 1].kind == "TAB" and self.units[k - 1].table.getparent() is a:
                k -= 1
            self.units.insert(k, unit)

    def collect_document(self):
        root = self.tree.getroot()
        for pp in root.iter(f"{{{NSMAP['l']}}}PartePrincipal", f"{{{NSMAP['l']}}}Preambulo"):
            self.walk(pp, [])
        if self.meta.truncated and not self.meta.ementa_id and self.meta.ementa and not self.stats["ementa_chunk"]:
            # ementa taken from a campo (no Agrupamento): keep its full text as a chunk
            self.stats["ementa_chunk"] = True
            self.units.insert(0, Unit("TXT", "metadado_ementa", "ementa", "", [], [],
                                      lines=[self.meta.ementa], synthetic=True))

    def collect_loose(self, include_preambulo: bool):
        root = self.tree.getroot()
        for e in root.iter():
            name = L(e)
            if name in ("Articulacao", "PartePrincipal") or (include_preambulo and name == "Preambulo"):
                if any(L(a) == "Alteracao" for a in e.iterancestors()):
                    continue
                self.walk(e, [], loose=True)

    # ---------------- rows ----------------
    def build(self, offset: int = 1) -> Result:
        c = offset - 1
        rows, prov = [], []
        for u in self.units:
            head = self.prefix + (u.heading + " " if u.heading else "")
            if u.kind == "TXT":
                full = join_text(self.prefix + u.heading, u.lines) if u.heading else norm(self.prefix + " ".join(u.lines))
                parts = [u.lines] if self.tok.count(full) <= self.cap else split_lines(u.lines, head.strip(), self.cap, self.tok)
                texts = [join_text(head.strip(), p) for p in parts]
            else:
                rws = tabela_rows(u.table)
                cap_head = norm(head + " " + u.caption)
                full = join_text(cap_head, ["Tabela: " + " ; ".join(rws)])
                if self.tok.count(full) <= self.cap:
                    groups = [(rws, False)]
                else:
                    groups = split_table_rows(rws, table_header_count(u.table), cap_head, self.cap, self.tok)
                texts = [join_text(cap_head, ["Tabela: " + " ; ".join(g)]) for g, _ in groups]
            n = len(texts)
            if n > 1:
                self.stats["split_units"] += 1
            c += 1
            start = c
            for k, t in enumerate(texts, 1):
                if n > 1:
                    c += 1
                    s, e = c, c + 1
                    c += 1
                else:
                    s, e = start, start + 1
                    c += 1
                ntok = self.tok.count(t)
                over = ntok > self.cap
                if over:
                    self.stats["oversize"].append({"urn": f"{self.urn}!{u.uid}", "parte": k, "tokens": ntok})
                suffix = f"_p{k}" if n > 1 else ""
                label = ", ".join(x for x in (self.sigla, u.label) if x) + (f", parte {k}/{n}" if n > 1 else "")
                urn = f"{self.urn}!{u.uid}{suffix}"
                rows.append({"Tipo": u.kind, "Rotulo": label, "Num_Inicio": s, "Num_Final": e,
                             "Texto": t, "urn": urn})
                prov.append({"urn": urn, "parte": k, "n_partes": n, "unidade_id": u.uid,
                             "nivel": u.kind, "sintetico": u.synthetic,
                             "cobre_ids": [u.uid] if n == 1 else [],
                             "parcial_ids": [] if n == 1 else [u.uid],
                             "agrupadores_ids": u.agr_ids, "agrupadores_rotulos": u.agr_labels,
                             "citacao": u.label, "oversize": over, "nota": u.note})
            if n > 1:
                c += 1  # close the unit interval around its parts
        return Result(rows, prov, self.stats)


def segment_document(xml_path: Path, out_csv: Path, tok: Tokenizer, cap: int = DEFAULT_MAX_TOKENS,
                     ementa_max_tokens: int = DEFAULT_EMENTA_MAX_TOKENS,
                     keep_dropped_min_chars: int = DEFAULT_KEEP_DROPPED_MIN_CHARS,
                     meta: Meta | None = None) -> Result:
    seg = Segmenter(xml_path, tok, cap, ementa_max_tokens, keep_dropped_min_chars, meta)
    seg.collect_document()
    res = seg.build(1)
    write_rows(out_csv, res.rows)
    write_prov(out_csv, res.prov)
    return res


def segment_loose(xml_path: Path, csv_path: Path, offset: int, tok: Tokenizer,
                  cap: int = DEFAULT_MAX_TOKENS, include_preambulo: bool = True,
                  meta: Meta | None = None, tree=None) -> Result:
    """Append loose-content rows to an existing statutory CSV (numbering from offset)."""
    seg = Segmenter(xml_path, tok, cap, DEFAULT_EMENTA_MAX_TOKENS, 0, meta, tree)
    seg.collect_loose(include_preambulo)
    res = seg.build(offset)
    if res.rows:
        existing = read_rows(csv_path)
        write_rows(csv_path, existing + res.rows)
        write_prov(csv_path, res.prov, append=True)
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("xml", type=Path)
    p.add_argument("--mode", choices=("document", "loose"), default="document")
    p.add_argument("--out", type=Path, help="output CSV (document mode)")
    p.add_argument("--append", type=Path, help="statutory CSV to append to (loose mode)")
    p.add_argument("--offset", type=int, default=1)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    p.add_argument("--ementa-max-tokens", type=int, default=DEFAULT_EMENTA_MAX_TOKENS)
    p.add_argument("--keep-dropped-min-chars", type=int, default=DEFAULT_KEEP_DROPPED_MIN_CHARS,
                   help="keep dropped Agrupamentos (assinatura/localDataFecho/preliminar) at least "
                        "this long as TXT; 0 = drop all (plan Q4 default)")
    args = p.parse_args(argv)
    tok = get_tokenizer(args.tokenizer)
    if args.mode == "document":
        res = segment_document(args.xml, args.out, tok, args.max_tokens, args.ementa_max_tokens,
                               args.keep_dropped_min_chars)
    else:
        res = segment_loose(args.xml, args.append, args.offset, tok, args.max_tokens)
    print(json.dumps({"rows": len(res.rows), **{k: v if not isinstance(v, list) else len(v)
                                                for k, v in res.stats.items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
