"""Tests of the in-text citation extractor and act resolver (nuggetizer/intext_citations.py, plan A2).

The forms come from the generated answers (survey of 2026-11-22). They read ``dataset/documents.jsonl``.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nuggetizer import intext_citations as I  # noqa: E402


@pytest.fixture(scope="module")
def ix():
    return I.DocIndex.load([json.loads(x) for x in open(I.REPO / "dataset" / "documents.jsonl")])


def cites(text, ix, claims=None):
    c, _ = I.extract_claims(claims or [text], ix)
    return [(x.act.act_key if x.act and x.act.status != "unresolved" else None, x.fragment_id, x.binding) for x in c]


@pytest.mark.parametrize("text, expected", [
    # genitive, federal act with year only and with "/yy"
    ("conforme o art. 39 da Lei nº 11.196, de 2005, e o art. 6º, inciso XIV, da Lei 7.713/88.",
     [("lei_11196_20051121", "art39", "genitive"), ("lei_7713_19881222", "art6_cpt_inc14", "genitive")]),
    # P&R style: act first, then the chain
    ("Lei nº 9.250, de 26 de dezembro de 1995, art. 8º, inciso II, alínea “b”.",
     [("lei_9250_19951226", "art8_cpt_inc2_ali2", "before")]),
    # Receita Federal acts, with and without issuer, "nº x/yyyy"
    ("art. 2º da Instrução Normativa RFB nº 2.178, de 5 de março de 2024", [("in_rfb_2178_20240305", "art2", "genitive")]),
    ("art. 17 da IN nº 84/2001", [("in_srf_84_20011011", "art17", "genitive")]),
    ("conforme a Solução de Divergência Cosit nº 19/2013.", [("sd_cosit_19_20130916", None, "act_only")]),
    # aliases
    ("art. 43 do CTN e art. 1.723 do Código Civil", [("lei_5172_19661025", "art43", "genitive"),
                                                    ("lei_10406_20020110", "art1723", "genitive")]),
    ("art. 132, inciso II, e § 2º, do RIR/2018.", [("decreto_9580_20181122", "art132_cpt_inc2", "genitive"),
                                                   ("decreto_9580_20181122", "art132_par2", "genitive")]),
    ("art. 49, inciso I, do RIR/1999", [("decreto_3000_19990326", "art49_cpt_inc1", "genitive")]),
    # the regulation's name followed by the decree: one act, the chain binds to it
    ("o art. 6º da Lei nº 8.134, de 1990, e o art. 75 do Regulamento do Imposto sobre a Renda, aprovado pelo "
     "Decreto nº 9.580, de 2018.", [("lei_8134_19901227", "art6", "genitive"), ("decreto_9580_20181122", "art75", "genitive")]),
    # MP with the reissue number
    ("A Medida Provisória nº 2.158-35, de 2001, art. 7º.", [("mp_2158-35_20010824", "art7", "before")]),
    # acts outside the corpus keep family:number:year
    ("art. 5º da IN RFB nº 2.179, de 2024", [("in:2179:2024", "art5", "genitive")]),
    # amending act is not a citation
    ("art. 12-A da Lei nº 7.713, de 1988, com redação dada pela Lei nº 12.844, de 2013.",
     [("lei_7713_19881222", "art12-1", "genitive")]),
    # "constituição" as a common noun is not the Constitution
    ("indenização decorrente de constituição de servidão de passagem", []),
    ("art. 153, inciso III, da Constituição Federal", [("constituição_1988_19881005", "art153_cpt_inc3", "genitive")]),
    # "e seguintes" between the chain and the act
    ("art. 7º da Lei nº 7.713, de 1988, e art. 725 e seguintes do Decreto nº 9.580, de 2018.",
     [("lei_7713_19881222", "art7", "genitive"), ("decreto_9580_20181122", "art725", "genitive")]),
    # no act at all: unattributed
    ("conforme os arts. 26 a 27.", [(None, "art26", "none"), (None, "art27", "none")]),
])
def test_extract(text, expected, ix):
    assert cites(text, ix) == expected


def test_anaphor_and_carried(ix):
    claims = ["O art. 8º da Lei nº 9.250, de 1995, trata das deduções.",
              "O § 2º do art. 8º da mesma Lei limita a dedução.",
              "O art. 10 também se aplica."]
    got = cites(None, ix, claims)
    assert got[1] == ("lei_9250_19951226", "art8_par2", "genitive")
    assert got[2] == ("lei_9250_19951226", "art10", "carried")


def test_unit_matches():
    from ragpipe.relevance import GoldItem
    act = I.Act(0, 0, "", "numbered", doc_id="lei_9250_19951226", status="corpus")
    cit = I.Citation(0, act, I.C.parse("art. 8º, inciso II")[0])
    gold_ali = GoldItem("001", "provision", ("lei_9250_19951226", "art8_cpt_inc2_ali2", "lei_9250_19951226.xml"),
                        "lei_9250_19951226", "", article_id="art8", fragment_id="art8_cpt_inc2_ali2",
                        lexml_file="lei_9250_19951226.xml")
    gold_art = GoldItem("001", "article", ("lei_9250_19951226", "art8"), "lei_9250_19951226", "", article_id="art8")
    gold_doc = GoldItem("001", "document", ("lei_9250_19951226",), "lei_9250_19951226", "")
    assert I.unit_matches(cit, gold_ali, "provision", None) == "full"      # coarser citation contains the gold unit
    assert I.unit_matches(cit, gold_art, "article", None) == "full"
    assert I.unit_matches(cit, gold_doc, "document", None) == "full"
    fine = I.Citation(0, act, I.C.parse("art. 8º, inciso II, alínea b, item 1")[0])
    assert I.unit_matches(fine, gold_ali, "provision", None) == "partial"  # finer than the gold unit
    other = I.Citation(0, act, I.C.parse("art. 8º, inciso I")[0])
    assert I.unit_matches(other, gold_ali, "provision", None) is None


def test_norm():
    assert I.norm_number("9.250") == "9250"
    assert I.norm_number("2.158-35") == "2158-35"
    assert I.norm_year("88") == 1988 and I.norm_year("01") == 2001 and I.norm_year("2024") == 2024
