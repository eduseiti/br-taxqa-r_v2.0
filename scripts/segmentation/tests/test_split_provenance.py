"""Oversize splitting (§5b) and provenance columns (§2.7)."""

from __future__ import annotations

import re
from collections import Counter

import pytest

import segment_all
from common import (DISPOSITIVOS, L, NSMAP, Positions, body_of, doc_urn, in_alteracao, parse,
                    read_prov, read_rows, texto)
from conftest import fixture_path
from split_oversize import split_csv


def largest_articles(tree, n=3):
    arts = [a for a in tree.getroot().iter(f"{{{NSMAP['l']}}}Artigo") if not in_alteracao(a)]
    return sorted(arts, key=lambda a: -len(texto(a)))[:n]


def run_split(tmp_path, xsl_out, tok, name, cap):
    csv_path, rows, meta = xsl_out(name)
    local = tmp_path / csv_path.name
    local.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    res = split_csv(local, fixture_path(name), meta, tok, cap)
    return rows, read_rows(local), read_prov(local), res


@pytest.mark.parametrize("name", ["decreto_9580_20181122.anexo1.xml", "decreto_3000_19990326.xml"])
def test_article_split(tmp_path, xsl_out, tok, name):
    cap = 400  # small cap (chars/4 tokenizer) to force descent and within-leaf splits
    before, after, prov, res = run_split(tmp_path, xsl_out, tok, name, cap)
    tree = parse(fixture_path(name))
    urn = doc_urn(tree)
    pos = Positions(tree)
    assert res["split"]
    by_urn = {p["urn"]: p for p in prov}
    for art in largest_articles(tree):
        base = f"{urn}!{art.get('id')}"
        parts = [r for r in after if r["urn"].startswith(base + "_p") and r["Tipo"] == "ART"]
        assert len(parts) > 1
        n = len(parts)
        assert [r["Rotulo"].rsplit(", parte ", 1)[1] for r in parts] == [f"{k}/{n}" for k in range(1, n + 1)]
        # parts <= cap unless flagged uncuttable
        for r in parts:
            assert tok.count(r["Texto"]) <= cap or by_urn[r["urn"]]["oversize"]
        # every part starts with the article label; caput sentence repeated in HEAD when needed
        label = " ".join(art.xpath("string(l:Rotulo)", namespaces=NSMAP).split())
        caput = " ".join(" ".join(art.xpath("l:Caput/l:p", namespaces=NSMAP)[0].xpath("string()").split()).split()) \
            if art.xpath("l:Caput/l:p", namespaces=NSMAP) else ""
        for r in parts:
            assert label in body_of(r["Texto"])[:400]
        if caput:
            assert all(caput[:60] in r["Texto"] for r in parts)
        # part intervals ordered and inside the article interval
        s0, e0 = pos[art]
        ivs = [(int(r["Num_Inicio"]), int(r["Num_Final"])) for r in parts]
        assert all(s0 <= s and e <= e0 for s, e in ivs)
        assert all(a[0] <= b[0] for a, b in zip(ivs, ivs[1:]))
        # dispositivo coverage: every dispositivo covered exactly once or partial (descended/leaf)
        cobre = Counter(i for r in parts for i in by_urn[r["urn"]]["cobre_ids"])
        parcial = {i for r in parts for i in by_urn[r["urn"]]["parcial_ids"]}
        assert max(cobre.values()) == 1
        for d in art.iter():
            if d is art or L(d) not in DISPOSITIVOS or in_alteracao(d):
                continue
            chain = [d, *d.iterancestors()]
            chain = chain[:chain.index(art)]
            k = sum(cobre.get(a.get("id"), 0) for a in chain)
            assert k == 1 or (k == 0 and d.get("id") in parcial), d.get("id")
        assert art.get("id") in parcial


def test_within_leaf_table_split_repeats_header(tmp_path, xsl_out, tok):
    cap = 150
    _, after, prov, res = run_split(tmp_path, xsl_out, tok, "decreto_3000_19990326.xml", cap)
    tables = [p for p in prov if any(i for i in p["parcial_ids"] if "_tab" in i)]
    assert tables
    rows = {r["urn"]: r for r in after}
    heads = Counter(rows[p["urn"]]["Texto"].split("Tabela: ", 1)[1].split(" ; ")[0] for p in tables
                    if "Tabela: " in rows[p["urn"]]["Texto"])
    assert heads.most_common(1)[0][1] > 1       # same header row repeated in several pieces


def test_caput_in_head_of_paragraph_parts(tmp_path, xsl_out, tok):
    """lei_9250 art. 8 at a 1,024 chars/4 cap: parts made of paragraphs repeat the caput sentence."""
    _, after, prov, _ = run_split(tmp_path, xsl_out, tok, "lei_9250_19951226.xml", 1024)
    parts = {p["urn"]: p for p in prov}
    p8 = [r for r in after if re.search(r"!art8_p\d+$", r["urn"])]
    assert len(p8) > 1
    par_parts = [r for r in p8 if parts[r["urn"]]["cobre_ids"] and parts[r["urn"]]["cobre_ids"][0].startswith("art8_par")]
    assert par_parts
    for r in par_parts:
        assert body_of(r["Texto"]).startswith("Art. 8º A base de cálculo do imposto devido no ano-calendário será a diferença entre as somas: §")
        assert "art8_cpt" in parts[r["urn"]]["parcial_ids"]


@pytest.fixture(scope="module")
def prov_worker():
    segment_all._init({"tokenizer": "chars:4", "max_tokens": 1024, "ementa_max_tokens": 128,
                       "keep_dropped_min_chars": 300})
    return segment_all.w_provenance


def test_provenance_split_and_ambiguous(tmp_path, xsl_out, tok, prov_worker):
    name = "circ_bc_3432_20090203.xml"
    csv_path, rows, _ = xsl_out(name)
    out = prov_worker((str(csv_path), str(fixture_path(name)), "main", "xsl"))
    assert [r["chunk_id"] for r in out] == [f"circ_bc_3432_20090203#{i}" for i in range(1, len(out) + 1)]
    art16 = [r for r in out if r["unidade_id"] == "art16" and r["Tipo"] == "ART"]
    assert len(art16) == 2 and all(r["id_ambiguo"] == 1 for r in art16)
    assert all(r["id_ambiguo"] == 0 for r in out if r["unidade_id"] == "art1")
    par = next(r for r in out if r["unidade_id"] == "art1_par1" or r["Tipo"] == "PAR")
    assert par["artigo_id"] and par["citacao"].startswith("Art.")
    dsp = [r for r in out if r["Tipo"] == "DSP"]
    assert any(r["unidade_id"] == "par1u" for r in dsp)          # orphan paragraph in a main doc
    for r in dsp:
        assert r["artigo_id"] == r["unidade_id"] and r["cobre_ids"] == r["unidade_id"]


def test_provenance_orphans_main_document(xsl_out, prov_worker):
    name = "decreto_67542_19701112.xml"
    csv_path, rows, _ = xsl_out(name)
    out = prov_worker((str(csv_path), str(fixture_path(name)), "main", "xsl"))
    dsp = [r for r in out if r["Tipo"] == "DSP"]
    assert len(dsp) >= 100
    subs = [r for r in out if r["Tipo"] in ("INC", "ALI", "ITE") and r["artigo_id"] in {d["unidade_id"] for d in dsp}]
    assert all(r["doc_urn"] == "urn:lex:br:federal:decreto:1970-11-12;67542" and r["anexo_urn"] == "" for r in out)
    for r in subs:
        assert r["citacao"] and not r["citacao"].startswith("Art.")


def test_provenance_parts_and_annex(tmp_path, xsl_out, tok, prov_worker):
    name = "lei_9250_19951226.xml"
    csv_path, rows, meta = xsl_out(name)
    local = tmp_path / csv_path.name
    local.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    split_csv(local, fixture_path(name), meta, tok, 1024)
    out = prov_worker((str(local), str(fixture_path(name)), "main", "xsl"))
    p = next(r for r in out if r["urn"].endswith("!art8_p2"))
    assert p["parte"] == 2 and p["n_partes"] > 2 and p["unidade_id"] == "art8" and p["artigo_id"] == "art8"
    assert p["segmentador"] == "python" and "art8" in p["parcial_ids"].split(";")
    ite = next(r for r in out if r["unidade_id"] == "art8_cpt_inc2_ali2_ite10")
    assert ite["citacao"] == "Art. 8º, caput, II, b, 10"
    assert ite["agrupadores_ids"] == "cap3"
    assert ite["agrupadores_rotulos"].startswith("CAPÍTULO III – ")
    # annex: doc_urn = parent, anexo_urn = annex
    name = "in_rfb_1548_20150213.anexo11.xml"
    csv_path, rows, _ = xsl_out(name)
    out = prov_worker((str(csv_path), str(fixture_path(name)), "B", "xsl"))
    assert all(r["anexo_urn"].endswith("!anexo11") and not r["doc_urn"].endswith("!anexo11") for r in out)
