"""diff_vs_frozen: like-with-like comparison of base and caput rows (X7, docs/20261009_121822_*)."""

from __future__ import annotations

import pandas as pd

from validate_segments import diff_vs_frozen

COLS = ["arquivo", "Tipo", "urn", "Num_Inicio", "Num_Final", "parte", "chunk_id", "variante", "Texto"]
ROWS = [
    ("lei_x.xml", "ART", "urn:a!art1", "1", "3", "1", "lei_x#1", "base", "Art. 1º Caput. § 1º P."),
    ("lei_x.xml", "PAR", "urn:a!art1_par1", "2", "3", "1", "lei_x#2", "base", "Art. 1º § 1º P."),
    ("lei_x.xml", "PAR", "urn:a!art1_par1", "2", "3", "1", "lei_x#c2", "caput", "Art. 1º Caput. § 1º P."),
]


def _frames(rows):
    df = pd.DataFrame(rows, columns=COLS)
    return df[df["variante"] == "base"], df[df["variante"] != "base"]


def _write(tmp_path, rows, with_variante=True):
    df = pd.DataFrame(rows, columns=COLS)
    if not with_variante:
        df = df.drop(columns="variante")
    path = tmp_path / "frozen.csv"
    df.to_csv(path, index=False)
    return path


def test_frozen_with_variants_compares_variant_by_variant(tmp_path):
    base, variants = _frames(ROWS)
    r = diff_vs_frozen(base, variants, _write(tmp_path, ROWS), None)
    assert r["by_variant"] and r["rows_compared"] == 3 and r["rows_text_differs"] == 0
    assert r["rows_only_new"] == 0 and r["rows_only_frozen"] == 0


def test_frozen_with_variants_reports_a_changed_base_text(tmp_path):
    frozen = [ROWS[0], ROWS[1][:-1] + ("Art. 1º § 1º Old.",), ROWS[2]]
    base, variants = _frames(ROWS)
    r = diff_vs_frozen(base, variants, _write(tmp_path, frozen), None)
    assert r["rows_text_differs"] == 1 and r["examples"] == ["urn:a!art1_par1"]


def test_frozen_before_the_caput_plan_compares_against_the_caput_text(tmp_path):
    """An old frozen set has one row per unit, holding the caput sentence in paragraph rows."""
    frozen = [ROWS[0], ROWS[2][:6] + ("lei_x#2", "base", ROWS[2][-1])]
    base, variants = _frames(ROWS)
    r = diff_vs_frozen(base, variants, _write(tmp_path, frozen, with_variante=False), None)
    assert not r["by_variant"] and r["rows_compared"] == 2 and r["rows_text_differs"] == 0
