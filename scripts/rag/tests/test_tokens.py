"""Token accounting of contexts against gold units (A1, ``ragpipe.tokens``), hand-computed."""

from __future__ import annotations

import dataclasses
import gzip
import math

import numpy as np
import pandas as pd
import pytest

from ragpipe.evaluation import EvalConfig, run_evaluation
from ragpipe.relevance import GoldItem, Match
from ragpipe.retrieval import RetrievalConfig, run_retrieval
from ragpipe.tokens import UnitTokens

F, T = "lei_7_20000101.xml", "urn_y.xml"

# unidade_id, tipo, start, end, own tokens (a proper nested-set numbering)
UNITS = [
    ("cap1", "CAP", 1, 22, 5),
    ("art1", "ART", 2, 11, 4),
    ("art1_cpt", "CPT", 3, 6, 20),
    ("art1_cpt_inc1", "INC", 4, 5, 30),
    ("art1_par1", "PAR", 7, 10, 40),
    ("art1_par1_inc1", "INC", 8, 9, 10),
    ("art2", "ART", 12, 21, 3),
    ("art2_cpt", "CPT", 13, 14, 50),
    ("art2_par1", "PAR", 15, 16, 60),
    ("art2_par2", "PAR", 17, 18, 70),
    ("art2_par3", "PAR", 19, 20, 80),
    ("art3", "ART", 23, 26, 2),
    ("art3_cpt", "CPT", 24, 25, 200),
]
PREFIX = {F: 10, T: 8}

# Tipo, unidade_id, start, end, n_partes, parcial_ids, variante, contexto_ids, tokens
CHUNKS = [
    ("ART", "art1", 2, 11, 1, "", "base", "", 114),                      # 0
    ("INC", "art1_cpt_inc1", 4, 5, 1, "", "base", "", 64),               # 1: path art1, art1_cpt
    ("INC", "art1_par1_inc1", 8, 9, 1, "", "base", "", 64),              # 2: path art1, art1_par1
    ("INC", "art1_par1_inc1", 8, 9, 1, "", "caput", "art1_cpt", 84),     # 3: + caput sentence
    ("ART", "art2", 13, 16, 2, "art2", "base", "", 123),                 # 4: part 1 (caput, § 1)
    ("ART", "art2", 17, 20, 2, "art2;art2_cpt", "base", "", 213),        # 5: part 2, head repeats the caput
    ("CAP", "cap1", 1, 22, 1, "", "base", "", 600),                      # 6
    ("ART", "art3", 24, 25, 2, "art3;art3_cpt", "base", "", 112),        # 7: a leaf cut in two pieces
    ("ART", "art3", 24, 25, 2, "art3;art3_cpt", "base", "", 112),        # 8
    ("TXT", "pp1", 1, 2, 1, "", "base", "", 100),                        # 9: non-statutory
]


@pytest.fixture(scope="module")
def ut() -> UnitTokens:
    units = pd.DataFrame([{"arquivo": F, "unidade_id": u, "tipo": t, "Num_Inicio": s, "Num_Final": e, "own_tokens": o,
                           "subtree_tokens": 0, "subtree_own_sum": 0} for u, t, s, e, o in UNITS])
    prefix = pd.DataFrame({"arquivo": list(PREFIX), "prefix_tokens": list(PREFIX.values())})
    chunks = pd.DataFrame([{"Tipo": tp, "arquivo": T if tp == "TXT" else F, "unidade_id": u, "Num_Inicio": s,
                            "Num_Final": e, "n_partes": n, "parcial_ids": p, "variante": v, "contexto_ids": c,
                            "n_tokens_qwen3": k} for tp, u, s, e, n, p, v, c, k in CHUNKS])
    return UnitTokens(units, prefix, chunks)


def blocks(ut: UnitTokens, level: str, uid: str) -> list[tuple[int, int]]:
    art = uid.split("_")[0]
    it = GoldItem("001", level, (), "lei_7", uid, article_id=art, fragment_id=None if level == "article" else uid,
                  lexml_file=F)
    m = Match(full=np.empty(0, np.int64), partial=np.empty(0, np.int64), units=[(F, art)])
    return ut.item_blocks(it, m)


def test_sizes(ut):
    assert ut.size(blocks(ut, "article", "art1")[0]) == 104          # 4 + 20 + 30 + 40 + 10
    assert ut.size(blocks(ut, "provision", "art1_cpt")[0]) == 50
    assert blocks(ut, "provision", "art9") == []


def test_inciso_with_its_path(ut):
    acc = ut.account([1], 64, [blocks(ut, "provision", "art1_cpt")])
    assert acc.coverage == [1.0]                   # the caput sentence is on the path, the inciso is content
    assert (acc.gold, acc.offgold, acc.scaffold) == (50, 0, 14)          # prefix 10 + article label 4
    acc = ut.account([1], 64, [blocks(ut, "article", "art1")])
    assert acc.coverage == [pytest.approx(54 / 104)]


def test_caput_variant(ut):
    g = [blocks(ut, "provision", "art1_cpt")]
    base = ut.account([2], 64, g)
    assert base.coverage == [0.0] and (base.gold, base.offgold, base.scaffold) == (0, 10, 54)
    cap = ut.account([3], 84, g)
    assert cap.coverage == [pytest.approx(0.4)] and (cap.gold, cap.offgold, cap.scaffold) == (20, 10, 54)
    both = ut.account([1, 3], 148, g)              # gold text seen twice is counted once
    assert both.coverage == [1.0] and (both.gold, both.offgold, both.scaffold) == (50, 10, 88)


def test_split_parts_and_pieces(ut):
    assert ut.account([5], 213, [blocks(ut, "provision", "art2_cpt")]).coverage == [1.0]   # repeated head
    assert ut.account([5], 213, [blocks(ut, "provision", "art2_par1")]).coverage == [0.0]
    a = ut.account([4, 5], 336, [blocks(ut, "article", "art2")])
    assert a.coverage == [1.0] and a.gold == 263
    g = [blocks(ut, "provision", "art3_cpt")]
    one = ut.account([7], 112, g)
    assert one.coverage == [0.5] and one.gold == 100
    assert ut.account([7, 8], 224, g).coverage == [1.0]


def test_grouping_and_text_chunks(ut):
    acc = ut.account([6, 9], 700, [blocks(ut, "provision", "art2_par2")])
    assert acc.coverage == [1.0] and acc.gold == 70
    assert acc.offgold == (104 + 3 + 50 + 60 + 80) + (100 - 8)          # other articles + the parecer text
    assert acc.scaffold == 700 - acc.gold - acc.offgold                  # prefixes and the chapter name


def test_shares_never_exceed_the_context(ut):
    acc = ut.account([0], 50, [blocks(ut, "article", "art1")])           # own sums above the text's tokens
    assert acc.gold + acc.offgold == pytest.approx(50) and acc.scaffold == 0
    empty = ut.account([], 0, [blocks(ut, "article", "art1")])
    assert empty.coverage == [0.0] and empty.gold == 0


def test_evaluation_with_token_metrics(repo):
    """Smoke test on the fixture repository: columns present, values in [0, 1], old metrics unchanged."""
    chunks = pd.read_csv(repo.chunks, keep_default_na=False)
    # one unit per chunk interval (the fixture numbering is not nested-set exact; enough for a smoke test)
    units = (chunks[chunks["Tipo"] != "TXT"].drop_duplicates(["arquivo", "Num_Inicio", "Num_Final"])
             .assign(tipo=lambda d: d["Tipo"], own_tokens=lambda d: d["n_tokens_qwen3"] // 4, subtree_tokens=0,
                     subtree_own_sum=0)
             [["arquivo", "unidade_id", "tipo", "Num_Inicio", "Num_Final", "own_tokens", "subtree_tokens",
               "subtree_own_sum"]])
    seg = repo.chunks.parent
    with gzip.open(seg / "unit_tokens.csv.gz", "wt") as fh:
        units.to_csv(fh, index=False)
    pd.DataFrame({"arquivo": sorted(set(chunks["arquivo"])), "prefix_tokens": 2}).to_csv(seg / "prefix_tokens.csv",
                                                                                        index=False)
    paths = dataclasses.replace(repo, unit_tokens=seg / "unit_tokens.csv.gz", prefix_tokens=seg / "prefix_tokens.csv")
    rdir = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", top_n=50), paths)
    small = dict(budgets=(500, 16000), unit_ks=(1,), raw_ks=(1,), n_resamples=200)
    old = run_evaluation(rdir, EvalConfig(**small), paths)
    new = run_evaluation(rdir, EvalConfig(**small, token_metrics=True), paths)
    assert new.name == "v3_either_containment_merge_skip"
    mo, mn = pd.read_csv(old / "metrics.csv"), pd.read_csv(new / "metrics.csv")
    k = ["strategy", "level", "view", "cutoff", "gold", "slice", "metric"]
    j = mo.merge(mn, on=k, suffixes=("_o", "_n"))
    assert len(j) == len(mo) and np.allclose(j["value_o"], j["value_n"], equal_nan=True)
    tok = mn[mn["metric"].isin(["token_recall", "item_coverage", "token_precision", "noise_share", "scaffold_share"])]
    assert set(tok["level"]) == {"article", "provision"} and set(tok["view"]) == {"budget"}
    assert tok["value"].between(0, 1).all()
    pq = pd.read_csv(new / "per_question.csv.gz", dtype={"question_number": str, "cutoff": str})
    s = pq[(pq["gold"] == "all") & (pq["slice"] == "all") & (pq["view"] == "budget") & pq["token_precision"].notna()]
    assert np.allclose(s["token_precision"] + s["noise_share"] + s["scaffold_share"], 1)
    items = pd.read_csv(new / "per_item.csv.gz", dtype={"question_number": str})
    assert {"gold_tokens", "budget_cov_500", "budget_cov_16000"} <= set(items.columns)
    assert not math.isnan(items.loc[items["level"] == "article", "gold_tokens"].iloc[0])
