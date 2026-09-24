"""Router, non-statutory segmenter (document + loose modes), strategies, tokenizer."""

from __future__ import annotations

import re

import pytest

import strategies
from classify_annexes import classify, loose_elements
from common import (Tokenizer, body_of, get_tokenizer, metadata_for, parse, read_prov, read_rows,
                    split_lines)
from conftest import fixture_path
from segment_non_statutory import segment_document, segment_loose


@pytest.mark.parametrize("name,cat,loose", [
    ("decreto_52288_19630724.anexo1.xml", "A", False),
    ("decreto_9358_20180430.anexo1.xml", "A", True),         # preamble text
    ("in_rfb_1548_20150213.anexo11.xml", "B", True),       # loose content in the annex Preambulo
    ("decreto_8289_20140725.anexo1.xml", "B", True),        # preamble text
    ("ade_rfb_3_20240402.anexo1.xml", "C", False),
    ("in_srf_256_20021211.anexo2.xml", "B", True),         # 148 loose p/table next to 138 dispositivos
    ("decreto_9580_20181122.anexo1.xml", "A", True),       # tax table before LIVRO I
])
def test_router(tok, name, cat, loose):
    d = classify(fixture_path(name), tok)
    assert d.categoria == cat
    assert (d.n_soltos > 0) == loose
    assert d.pai and d.pai_resolucao == "stem"
    assert "segmentadores" and d.segmentadores.startswith("xsl" if cat in "AB" else "python")
    if name.startswith("in_srf_256"):
        tree = parse(fixture_path(name))
        assert len(loose_elements(tree, include_preambulo=False)) == 148


def test_annex_metadata(tok):
    m = metadata_for(fixture_path("in_rfb_1548_20150213.anexo11.xml"), tok)
    assert m.text() == ("INSTRUÇÃO NORMATIVA Nº 1.548, DE 13 DE FEVEREIRO DE 2015 | "
                        "Dispõe sobre o Cadastro de Pessoas Físicas (CPF). | Anexo 11 – ANEXO VII")


def test_non_statutory_document(tmp_path, tok):
    xml = fixture_path("urn_lex_br_federal_parecer_2010_1503.xml")
    m = metadata_for(xml, tok)
    assert m.epigrafe == "PARECER PGFN/CAT/Nº 1503//2010"
    assert m.ementa == "Requerimento administrativo de servidora federal"
    cap = 300
    out = tmp_path / "p.csv"
    res = segment_document(xml, out, tok, cap)
    rows = read_rows(out)
    assert {r["Tipo"] for r in rows} == {"TXT"}
    assert all(tok.count(r["Texto"]) <= cap for r in rows)
    assert all(r["Texto"].startswith("[ PARECER PGFN/CAT/Nº 1503//2010 | Requerimento") for r in rows)
    assert {d["nome"] for d in res.stats["dropped"]} <= {"assinatura", "localDataFecho", "preliminar"}
    assert res.stats["dropped"]
    joined = " ".join(body_of(r["Texto"]) for r in rows)
    assert "PARECER PGFN/CAT/Nº 1503//2010 Requerimento" not in joined   # epígrafe/ementa: prefix only
    parts = [r for r in rows if ", parte " in r["Rotulo"]]
    assert parts and parts[0]["urn"].endswith("_p1")
    # section heading line at the start of each unit of section II
    sec2 = [r for r in rows if re.match(r"urn_lex_br_federal_parecer_2010_1503, II(,|$)", r["Rotulo"])]
    assert sec2 and all(body_of(r["Texto"]).startswith("II ") for r in sec2)
    # intervals: parts are sibling intervals, all disjoint
    ivs = sorted((int(r["Num_Inicio"]), int(r["Num_Final"])) for r in rows)
    assert all(a[1] < b[0] for a, b in zip(ivs, ivs[1:]))
    prov = read_prov(out)
    assert len(prov) == len(rows)
    assert all(p["parcial_ids"] == [p["unidade_id"]] for p in prov if p["n_partes"] > 1)


def test_table_header_repeated(tmp_path, tok):
    xml = fixture_path("ade_rfb_3_20240402.anexo1.xml")
    out = tmp_path / "a.csv"
    segment_document(xml, out, tok, 400)
    tabs = [r for r in read_rows(out) if r["Tipo"] == "TAB"]
    assert len(tabs) > 1
    header = "Tabela: código TIPI (original) | Código TIPI (desdobramentos) | DESCRIÇÃO | ALÍQUOTA IPI (%) ;"
    for r in tabs:
        assert tok.count(r["Texto"]) <= 400
        assert "(CÓDIGOS DESDOBRADOS) " + header in r["Texto"]    # caption + header in every part
    # the annex title line is in the prefix only
    assert all("Anexo 1 – ANEXO I ]" in r["Texto"] for r in read_rows(out))
    assert not any(body_of(r["Texto"]) == "ANEXO I" for r in read_rows(out))


def test_loose_offset_keeps_intervals_disjoint(tmp_path, xsl_out, tok):
    """decreto_9580.anexo1 (RIR/2018): the tax table before LIVRO I is appended after the XSL rows."""
    csv_path, rows, meta = xsl_out("decreto_9580_20181122.anexo1.xml")
    local = tmp_path / csv_path.name
    local.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    max_final = max(int(r["Num_Final"]) for r in rows)
    res = segment_loose(fixture_path("decreto_9580_20181122.anexo1.xml"), local, max_final + 1, tok)
    new = read_rows(local)[len(rows):]
    assert len(new) == len(res.rows) > 0
    assert min(int(r["Num_Inicio"]) for r in new) == max_final + 1
    tab = next(r for r in new if r["Tipo"] == "TAB")
    assert "TABELA PROGRESSIVA MENSAL" in tab["Texto"]
    assert "V I - para os meses de abril a dezembro" in tab["Texto"]          # caption
    assert not any(body_of(r["Texto"]) == "ANEXO" for r in new)               # title: prefix only
    prov = read_prov(local)
    txt = [p for p in prov if p["nivel"] == "TXT"]
    assert all(p["sintetico"] and p["unidade_id"].startswith("anexo1_pp_p") for p in txt)


def test_synthetic_loose_ids(tmp_path, xsl_out, tok):
    csv_path, rows, _ = xsl_out("in_srf_256_20021211.anexo2.xml")
    local = tmp_path / csv_path.name
    local.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    segment_loose(fixture_path("in_srf_256_20021211.anexo2.xml"), local,
                  max(int(r["Num_Final"]) for r in rows) + 1, tok)
    prov = read_prov(local)
    ids = [p["unidade_id"] for p in prov if p["sintetico"]]
    assert ids and all("_p" in i and "-p" in i for i in ids)


def test_split_lines_prefers_paragraph_numbers(tok):
    lines = ["Primeira frase do texto.", "2.", "Segunda parte que continua", "na linha seguinte.",
             "3.", "Terceira parte que também é longa o suficiente para passar do limite."]
    parts = split_lines(lines, "[ m ]", 22, tok)
    assert parts[1][0] == "2." or parts[1][0] == "3."
    assert all(p[0] != "na linha seguinte." for p in parts)


def test_strategies():
    assert strategies.S1 == {"ART", "DSP", "TXT", "TAB"}
    assert strategies.S2 - strategies.S1 == {"CPT", "PAR", "INC", "ALI", "ITE"}
    assert strategies.S3 - strategies.S2 == {"PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC"}


def test_reference_tokenizer_is_max():
    t = get_tokenizer("max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B")
    text = "A base de cálculo do imposto devido no ano-calendário será a diferença entre as somas"
    per = [lf.count(text) for lf in t.leaves()]
    assert t.count(text) == max(per) and len(per) == 2
    assert Tokenizer("chars:4").count("abcdefgh") == 2
