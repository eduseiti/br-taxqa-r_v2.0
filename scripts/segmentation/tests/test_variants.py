"""Caput text variants (caput plan C3, C6, C10) and variant-aware strategy filters."""

from __future__ import annotations

import pandas as pd
import pytest

import strategies
from add_caput_variants import caput_variant
from common import in_article_paragraph, parse, xsl_row_elements
from conftest import fixture_path


@pytest.mark.parametrize("name", ["lei_9250_19951226.xml", "decreto_3000_19990326.xml"])
def test_caput_variant_equals_the_frase_xsl_text(xsl_out, name):
    """The variant built from a base row is the XSL text with caput_em_paragrafo='frase'."""
    _, base_rows, _ = xsl_out(name)
    _, frase_rows, _ = xsl_out(name, caput="frase")
    els = xsl_row_elements(parse(fixture_path(name)))
    n = 0
    for b, f, (tipo, e) in zip(base_rows, frase_rows, els):
        cv = caput_variant(e, tipo, b["Texto"])
        if cv is None:
            assert b["Texto"] == f["Texto"] or tipo == "DSP", b["urn"]
            continue
        n += 1
        assert in_article_paragraph(e) and tipo in ("PAR", "INC", "ALI", "ITE")
        assert cv[0] == f["Texto"]
        assert cv[1].endswith("_cpt")
    assert n > 0


def test_caput_variant_rejects_a_text_that_is_not_the_base(xsl_out):
    _, rows, _ = xsl_out("lei_9250_19951226.xml", caput="frase")
    els = xsl_row_elements(parse(fixture_path("lei_9250_19951226.xml")))
    r, (tipo, e) = next((r, te) for r, te in zip(rows, els) if r["urn"].endswith("!art8_par2"))
    with pytest.raises(ValueError):
        caput_variant(e, tipo, r["Texto"])


def _table():
    rows = [
        ("d#1", "ART", "base"), ("d#2", "CPT", "base"), ("d#3", "PAR", "base"), ("d#c3", "PAR", "caput"),
        ("d#4", "INC", "base"), ("d#c4", "INC", "caput"), ("d#5", "INC", "base"), ("d#6", "CAP", "base"),
        ("d#7", "TXT", "base"),
    ]
    return pd.DataFrame(rows, columns=["chunk_id", "Tipo", "variante"])


def test_strategy_filters_with_variants():
    df = _table()
    ids = {s: list(strategies.filter(df, s)["chunk_id"]) for s in strategies.STRATEGIES}
    assert ids["S1"] == ["d#1", "d#7"]
    assert ids["S2"] == ["d#1", "d#2", "d#3", "d#4", "d#5", "d#7"]
    assert ids["S3"] == ["d#1", "d#2", "d#3", "d#4", "d#5", "d#6", "d#7"]
    # S2c / S4: caput rows replace their base twins; units without a variant keep the base row
    assert ids["S2C"] == ["d#1", "d#2", "d#c3", "d#c4", "d#5", "d#7"]
    assert ids["S4"] == ["d#1", "d#2", "d#c3", "d#c4", "d#5", "d#6", "d#7"]
    assert len(ids["S4"]) == len(ids["S3"]) and len(ids["S2C"]) == len(ids["S2"])


def test_strategy_mask_on_a_tipo_series_and_on_a_table_without_variants():
    df = _table()
    assert strategies.strategy_mask(df["Tipo"], "S1").sum() == 2
    old = df[df["variante"] == "base"].drop(columns="variante")
    assert list(strategies.filter(old, "S4")["chunk_id"]) == list(strategies.filter(old, "S3")["chunk_id"])
