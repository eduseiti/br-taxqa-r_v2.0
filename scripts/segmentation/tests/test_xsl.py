"""Amended XSL: regression against the original, worked target, X3/X3b/X4/X6/X7/X8, parity."""

from __future__ import annotations

import re

import pytest

from common import (NSMAP, Positions, ORPHAN_TYPES, doc_urn, has_disp_ancestor, in_alteracao,
                    in_article_paragraph, L, parse, rotulo, row_text, xsl_row_elements)
from conftest import fixture_path

GROUPS = ("PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC")


def key_set(rows, tipo):
    return {(r["Num_Inicio"], r["Num_Final"], r["urn"]) for r in rows if r["Tipo"] == tipo}


@pytest.mark.parametrize("name", ["lei_9250_19951226.xml", "decreto_9580_20181122.anexo1.xml"])
def test_regression_against_original(xsl_out, name):
    """(Tipo, Num_Inicio, Num_Final, urn) identical for unchanged Tipos; CPT only loses caput-only
    articles (X5); top-level orphans move to DSP (X6)."""
    _, orig, _ = xsl_out(name, original=True)
    _, new, _ = xsl_out(name)
    tree = parse(fixture_path(name))
    for t in ("ART",) + GROUPS:
        assert key_set(orig, t) == key_set(new, t), t
    urn = doc_urn(tree)
    caput_only = {f"{urn}!{c.get('id')}" for c in tree.getroot().iter(f"{{{NSMAP['l']}}}Caput")
                  if L(c.getparent()) == "Artigo" and not any(L(x) == "Paragrafo" for x in c.getparent())
                  and not in_alteracao(c)}
    removed_cpt = key_set(orig, "CPT") - key_set(new, "CPT")
    assert key_set(new, "CPT") <= key_set(orig, "CPT")
    assert {u for _, _, u in removed_cpt} == caput_only
    dsp = key_set(new, "DSP")
    for t in ("PAR", "INC", "ALI", "ITE"):
        o, n = key_set(orig, t), key_set(new, t)
        assert n - o == set() or t == "PAR", t
        assert (o - n) <= dsp, t   # rows that disappeared became DSP rows


def body(t):
    return t.split(" ] ", 1)[1]


def test_worked_target(xsl_out):
    _, rows, meta = xsl_out("lei_9250_19951226.xml")
    by = {r["urn"].rsplit("!", 1)[1]: r for r in rows}
    ite = by["art8_cpt_inc2_ali2_ite10"]
    assert ite["Tipo"] == "ITE"
    assert ite["Texto"].startswith("[ LEI Nº 9.250, DE 26 DE DEZEMBRO DE 1995 | Altera a Legislação do Imposto")
    assert re.match(r"Art\. 8º A base de cálculo do imposto devido no ano-calendário será a diferença entre "
                    r"as somas: II – das deduções relativas: b\) a pagamentos de despesas com instrução .* "
                    r"até o limite anual individual de: .*10\. R\$ 3\.561,50", body(ite["Texto"]))
    assert "1. R$ 2.198,00" not in ite["Texto"]           # no sibling items
    assert ite["Rotulo"] == "lei_9250_19951226, Art. 8º, caput, Inciso II, Alínea b, Item 10"
    # caput plan D-A: the base PAR row has the article label and the paragraph, no caput sentence
    par = by["art8_par2"]
    assert body(par["Texto"]).startswith("Art. 8º § 2º O disposto na alínea a do inciso II:")
    assert "A base de cálculo" not in par["Texto"]
    assert by["art8_par2_inc1"]["Texto"].split(" ] ", 1)[1].startswith("Art. 8º § 2º O disposto na alínea a")
    assert "CÂMARA DOS DEPUTADOS" not in meta


def test_worked_target_caput_sentence(xsl_out):
    """caput_em_paragrafo='frase' gives the old X3b texts (the S4/S2c caput variant); caput-side
    and non-paragraph rows are the same with both settings."""
    _, base_rows, _ = xsl_out("lei_9250_19951226.xml")
    _, rows, _ = xsl_out("lei_9250_19951226.xml", caput="frase")
    by = {r["urn"].rsplit("!", 1)[1]: r for r in rows}
    assert re.match(r"Art\. 8º A base de cálculo .* somas: § 2º O disposto na alínea a do inciso II:",
                    body(by["art8_par2"]["Texto"]))
    tree = parse(fixture_path("lei_9250_19951226.xml"))
    els = xsl_row_elements(tree)
    assert len(rows) == len(base_rows) == len(els)
    for b, r, (_, e) in zip(base_rows, rows, els):
        if in_article_paragraph(e):
            continue
        assert b["Texto"] == r["Texto"], b["urn"]
    assert by["art8_cpt_inc2_ali2_ite10"]["Texto"] == \
        next(b for b in base_rows if b["urn"].endswith("!art8_cpt_inc2_ali2_ite10"))["Texto"]


def test_remission_text_kept(xsl_out):
    _, rows, _ = xsl_out("lei_9250_19951226.xml")
    by = {r["urn"].rsplit("!", 1)[1]: r for r in rows}
    # the span-linked "arts. 7°, 8° e 12, da Lei n° 7.713" is in the caput of art. 3 and in the
    # ancestor path of the paragraph
    assert "de que tratam os arts. 7°, 8° e 12, da Lei n° 7.713" in by["art3"]["Texto"]
    # inciso whose parent caput sentence has a Remissao: the path keeps it (bug at orig. 182-183)
    tree = parse(fixture_path("lei_9250_19951226.xml"))
    n = 0
    for inc in tree.getroot().iter(f"{{{NSMAP['l']}}}Inciso"):
        cpt = inc.getparent()
        if L(cpt) == "Caput" and cpt.xpath("l:p/l:span", namespaces=NSMAP) and not in_alteracao(inc):
            span_text = " ".join(cpt.xpath("l:p/l:span", namespaces=NSMAP)[0].xpath("string()").split())
            assert span_text in by[inc.get("id")]["Texto"]
            n += 1
    assert n > 0


def test_table_serialized(xsl_out):
    _, rows, _ = xsl_out("lei_9250_19951226.xml")
    art3 = next(r for r in rows if r["urn"].endswith("!art3"))
    assert "Tabela: BASE DE CÁLCULO EM R$ | ALÍQUOTA% | PARCELA A DEDUZIR DO IMPOSTO EM R$ ; até 900,00 | - | -" in art3["Texto"]


def test_table_inside_article_decreto_3000(xsl_out):
    name = "decreto_3000_19990326.xml"
    _, rows, _ = xsl_out(name)
    tree = parse(fixture_path(name))
    arts = [a for a in tree.getroot().iter(f"{{{NSMAP['l']}}}Artigo")
            if a.xpath(".//l:table", namespaces=NSMAP) and not in_alteracao(a)]
    assert arts
    by = {r["urn"]: r for r in rows if r["Tipo"] == "ART"}
    urn = doc_urn(tree)
    for a in arts[:20]:
        t = a.xpath(".//l:table", namespaces=NSMAP)[0]
        first_cell = " ".join(t.xpath("string(.//l:td[1])", namespaces=NSMAP).split())
        assert "Tabela: " in by[f"{urn}!{a.get('id')}"]["Texto"]
        assert first_cell in by[f"{urn}!{a.get('id')}"]["Texto"]


@pytest.mark.parametrize("name", ["in_rfb_1548_20150213.anexo11.xml", "decreto_8289_20140725.anexo1.xml"])
def test_orphan_dispositivos(xsl_out, name):
    _, rows, _ = xsl_out(name)
    tree = parse(fixture_path(name))
    orphans = [e for e in tree.getroot().iter() if L(e) in ORPHAN_TYPES and not in_alteracao(e)
               and not has_disp_ancestor(e)]
    dsp = [r for r in rows if r["Tipo"] == "DSP"]
    assert len(dsp) == len(orphans) > 0
    assert {r["urn"].rsplit("!", 1)[1] for r in dsp} == {e.get("id") for e in orphans}
    if name.startswith("in_rfb_1548"):
        assert any(L(e) == "Paragrafo" for e in orphans)        # orphan Paragrafo gets a row
    for r in rows:
        assert ", ," not in r["Rotulo"] and "Art. ," not in r["Rotulo"]
        assert not r["Rotulo"].endswith(", ")
        if r["Tipo"] in ("INC", "ALI", "ITE", "PAR"):
            assert "Art." not in r["Rotulo"]                     # no empty article label


def test_labels_without_separator(xsl_out):
    """X7: short labels also for '-', '—' or no separator (substring-before returned '')."""
    _, rows, _ = xsl_out("decreto_9580_20181122.anexo1.xml")
    for r in rows:
        if r["Tipo"] in ("INC", "ALI", "ITE"):
            assert not re.search(r"(Inciso|Alínea|Item)(,|$)", r["Rotulo"]), r["Rotulo"]


@pytest.mark.parametrize("caput", [("nao", "nenhum"), ("frase", "frase")], ids=["nao", "frase"])
@pytest.mark.parametrize("name", ["lei_9250_19951226.xml", "decreto_3000_19990326.xml",
                                  "circ_bc_3432_20090203.xml", "in_srf_256_20021211.anexo2.xml"])
def test_python_xsl_parity(xsl_out, name, caput):
    """Every row: Python selection, label, interval and text == XSL (Python mirror, plan §5b), with
    both caput_em_paragrafo settings."""
    xsl_caput, py_caput = caput
    _, rows, meta = xsl_out(name, caput=xsl_caput)
    tree = parse(fixture_path(name))
    els = xsl_row_elements(tree)
    pos = Positions(tree)
    urn = doc_urn(tree)
    assert len(els) == len(rows)
    sig = name[:-4]
    for r, (tipo, e) in zip(rows, els):
        assert r["Tipo"] == tipo
        assert r["urn"] == f"{urn}!{e.get('id')}"
        assert r["Rotulo"] == rotulo(e, sig)
        assert (int(r["Num_Inicio"]), int(r["Num_Final"])) == pos[e]
        assert r["Texto"] == row_text(e, meta, py_caput)
