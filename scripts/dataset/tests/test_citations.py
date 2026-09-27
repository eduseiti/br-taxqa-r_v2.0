"""Tests of the citation parser (scripts/dataset/citations.py) on citation shapes of the Q&A document."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from citations import attribute, chain_units, parse  # noqa: E402


def ids(text):
    return [u.fragment_id for u in parse(text)]


@pytest.mark.parametrize("text, expected", [
    # siblings vs path: the case the v1.1 flat lists could not tell apart
    ("art. 1º, inciso X e parágrafo único", ["art1_cpt_inc10", "art1_par1u"]),
    ("art. 12, § 1º, inciso II", ["art12_par1_inc2"]),
    ("art. 1º, inciso IX, e parágrafo único", ["art1_cpt_inc9", "art1_par1u"]),
    ("art. 3º, inciso III, § 2º", ["art3_cpt_inc3", "art3_par2"]),
    # deeper paths
    ("art. 8º, inciso II, alínea “c”, item 9", ["art8_cpt_inc2_ali3_ite9"]),
    ("art. 35, inciso VII, “c”", ["art35_cpt_inc7_ali3"]),
    ("art. 167, inciso I, itens 24 e 25", ["art167_cpt_inc1_ite24", "art167_cpt_inc1_ite25"]),
    ("arts. 2º, parágrafo único, inciso II, 19, inciso XVI, e 21, parágrafo único",
     ["art2_par1u_inc2", "art19_cpt_inc16", "art21_par1u"]),
    # explicit caput
    ("art. 14, caput e §§ 1º e 2º", ["art14_cpt", "art14_par1", "art14_par2"]),
    ("arts. 29 e 62, caput, incisos V, VII e § 1º", ["art29", "art62_cpt_inc5", "art62_cpt_inc7", "art62_par1"]),
    # reverse order ("X do Y do Z")
    ("inciso II do § 1º do art. 162", ["art162_par1_inc2"]),
    ("art. 17 e § 4º do art. 19", ["art17", "art19_par4"]),
    ("§ 2º do art. 14, inciso III", ["art14_par2_inc3"]),
    ("alíneas a e b do inciso II do art. 8º", ["art8_cpt_inc2_ali1", "art8_cpt_inc2_ali2"]),
    ("arts. 732, incisos I e II, e 736, incisos I e II de seu § único",
     ["art732_cpt_inc1", "art732_cpt_inc2", "art736_par1u_inc1", "art736_par1u_inc2"]),
    # ranges
    ("arts. 10 a 13", ["art10", "art11", "art12", "art13"]),
    ("art. 3º, §§ 2º ao 5º, e art. 23", ["art3_par2", "art3_par3", "art3_par4", "art3_par5", "art23"]),
    ("art. 12, § 4º, inciso I, e art. 13 a 15, 18 e 21",
     ["art12_par4_inc1", "art13", "art14", "art15", "art18", "art21"]),
    # bare numbers go back to an open list; a list closed by "e" takes no more values
    ("art. 1º, 2º, 3º, §§ 1º e 4º, e 7º, inciso II e §1º",
     ["art1", "art2", "art3_par1", "art3_par4", "art7_cpt_inc2", "art7_par1"]),
    ("arts. 23, caput e §§ 1º e 7º, e 26", ["art23_cpt", "art23_par1", "art23_par7", "art26"]),
    ("arts. 1º, 2º, 3º, caput e §§ 2º a 4º, 16, caput e § 4º",
     ["art1", "art2", "art3_cpt", "art3_par2", "art3_par3", "art3_par4", "art16_cpt", "art16_par4"]),
    # the article itself is cited when a child follows it with "e"
    ("art. 26 e parágrafo único", ["art26", "art26_par1u"]),
    # article ids: suffix letters, thousands, "único", roman (treaties)
    ("art. 9º e 11-A, inciso I", ["art9", "art11-1_cpt_inc1"]),
    ("art. 1.042", ["art1042"]),
    ("Artigo único", ["art1u"]),
    ("art. IX, item 2", ["art9_cpt_ite2"]),
    # sloppy typography
    ("art.10, inciso IX", ["art10_cpt_inc9"]),
    ("art. 17 § 3º", ["art17_par3"]),
    ("arts. 4º, inciso VI, alínea ‘i’e 8º, § 1º", ["art4_cpt_inc6_ali9", "art8_par1"]),
    ("arts. 3º, caput e § 1º; e 4º", ["art3_cpt", "art3_par1", "art4"]),
])
def test_fragment_ids(text, expected):
    assert ids(text) == expected


def test_units_without_lexml_id_keep_their_label():
    units = parse("Anexo VII, inciso VII; itens 19.1 a 19.3; Capítulo III")
    assert [u.label for u in units] == ["Anexo VII, inciso VII", "item 19.1", "item 19.3", "Capítulo III"]
    assert all(u.fragment_id is None for u in units)
    assert units[0].annex == "Anexo VII"


def test_article_inside_annex_keeps_its_id():
    units = parse("arts. 4º e 46 do Anexo")
    assert [(u.fragment_id, u.annex) for u in units] == [("art4", "Anexo"), ("art46", "Anexo")]


def test_attribute_explicit_block():
    block = ["Lei nº 9.250, de 26 de dezembro de 1995, art. 25; Lei nº 11.482, de 31 de maio de 2007, "
             "art. 1º, inciso X e parágrafo único; e Regulamento do Imposto sobre a Renda - RIR/2018, "
             "arts. 36, inciso XIV, e 690 a 692, aprovado pelo Decreto nº 9.580, de 22 de novembro de 2018; "
             "Instrução Normativa SRF nº 81, de 11 de outubro de 2001, art. 3º, §§ 1º e 2º; e art. 6º"]
    titles = ["Lei nº 9.250, de 26 de dezembro de 1995", "Lei nº 11.482, de 31 de maio de 2007",
              "Regulamento do Imposto sobre a Renda - RIR/2018, aprovado pelo Decreto nº 9.580, de 22 de novembro de 2018",
              "Decreto nº 9.580, de 22 de novembro de 2018",
              "Instrução Normativa SRF nº 81, de 11 de outubro de 2001"]
    atts, orphans = attribute(titles, block, continuation=True)
    got = [[u.fragment_id for c in a.chains for u in chain_units(c)] for a in atts]
    assert got == [["art25"], ["art1_cpt_inc10", "art1_par1u"],
                   ["art36_cpt_inc14", "art690", "art691", "art692"],
                   [],                                      # only named as the RIR's approving decree
                   ["art3_par1", "art3_par2", "art6"]]      # "; e art. 6º" continues the IN
    assert not orphans
    assert atts[3].pieces and "aprovado pelo Decreto" in atts[3].pieces[0]


def test_attribute_reverse_citation_goes_to_the_following_act():
    atts, orphans = attribute(["Lei nº 7.713, de 22 de dezembro de 1988"],
                              ["inciso XIV do art. 6º da Lei nº 7.713, de 22 de dezembro de 1988"], continuation=False)
    assert [u.fragment_id for c in atts[0].chains for u in chain_units(c)] == ["art6_cpt_inc14"]
    assert not orphans


def test_attribute_amending_law_does_not_take_the_chain():
    atts, orphans = attribute(["Lei nº 11.482, de 31 de maio de 2007"],
                              ["Lei nº 11.482, de 31 de maio de 2007, alterada pela Lei nº 12.469, de 26 de agosto "
                               "de 2011, art. 2º e 3º"], continuation=True)
    assert [u.fragment_id for c in atts[0].chains for u in chain_units(c)] == ["art2", "art3"]
    assert not orphans


def test_number_broken_by_line_end():
    atts, _ = attribute(["Medida Provisória nº 2.158-35, de 24 de agosto de 2001"],
                        ["Medida Provisória nº 2.158-\n35, de 24 de agosto de 2001, art. 61"], continuation=True)
    assert [u.fragment_id for c in atts[0].chains for u in chain_units(c)] == ["art61"]
