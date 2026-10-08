"""Unit tests: strategies and aliasing, the gold matcher, context selection, metrics, input checks."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from ragpipe import metrics as M
from ragpipe.context import Cutoff, select
from ragpipe.data import Paths, check_inputs, load_chunks, load_dataset, load_embedding
from ragpipe.relevance import GoldItem, Matcher, gold_items
from ragpipe.runs import sha256_file
from ragpipe.strategies import attach_text_rows, build_index, load_strategies, member_mask

from conftest import A, D, L


@pytest.fixture
def loaded(repo):
    chunks = load_chunks(repo.chunks)
    ds = load_dataset(repo.dataset)
    emb = load_embedding(repo.embeddings, "fake", "irpf")
    return repo, chunks, ds, emb


def make_matcher(chunks, ds, rule="either"):
    main = {d: f.split("/")[-1] for d, f in zip(ds.documents["document_id"], ds.documents["lexml_file"])}
    return Matcher(chunks, ds.file_to_document(), main, load_strategies(Paths().strategies).grouping_tipos, rule)


# ------------------------------------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------------------------------------

def test_strategy_filter_and_aliases(loaded):
    repo, chunks, _, emb = loaded
    cfg = load_strategies(repo.strategies)
    ch = attach_text_rows(chunks, emb)
    s1, s2, s3 = (build_index(ch, cfg.strategies[n], cfg.unit_precedence) for n in ("S1", "S2", "S3"))
    assert (s1.n_chunk_rows, len(s1)) == (9, 9)
    assert (s2.n_chunk_rows, len(s2)) == (14, 13)      # ART art3 and INC art3_cpt_inc1 share one text
    assert (s3.n_chunk_rows, len(s3)) == (15, 14)
    ids = chunks["chunk_id"].to_numpy()
    shared = [i for i in range(len(s2)) if len(s2.members(i)) == 2]
    assert len(shared) == 1
    rep, alias = ids[s2.members(shared[0])]
    assert chunks.set_index("chunk_id").loc[rep, "Tipo"] == "ART"          # coarsest chunk represents the text
    assert chunks.set_index("chunk_id").loc[alias, "Tipo"] == "INC"


def test_member_mask_with_caput_variants():
    """S2c/S4 (caput plan §4.2): a caput row replaces its base twin; other units keep the base row."""
    ch = pd.DataFrame({"chunk_id": ["d#1", "d#2", "d#c2", "d#3", "d#c3", "d#4"],
                       "Tipo": ["ART", "PAR", "PAR", "INC", "INC", "CAP"],
                       "variante": ["base", "base", "caput", "base", "caput", "base"]})
    s2 = ["ART", "PAR", "INC"]
    assert ch["chunk_id"][member_mask(ch, s2)].tolist() == ["d#1", "d#2", "d#3"]
    assert ch["chunk_id"][member_mask(ch, s2, ("caput", "base"))].tolist() == ["d#1", "d#c2", "d#c3"]
    assert ch["chunk_id"][member_mask(ch.drop(columns="variante"), s2)].tolist() == ["d#1", "d#2", "d#c2", "d#3", "d#c3"]


def test_unknown_strategy_is_reported(repo):
    cfg = load_strategies(repo.strategies)
    with pytest.raises(Exception, match="unknown strategy"):
        cfg.select(["S9"])


# ------------------------------------------------------------------------------------------------
# Gold items and matcher
# ------------------------------------------------------------------------------------------------

def test_gold_items(loaded):
    _, _, ds, _ = loaded
    g = gold_items(ds)
    assert set(g) == {"001", "002", "003"}                          # not_in_corpus references dropped
    docs = {it.document_id: it.origin for it in g["003"]["document"]}
    assert docs == {"decreto_9_20000101": "explicit", "urn_x": "embedded"}
    assert [it.key for it in g["003"]["article"]] == [("decreto_9_20000101", "art1"), ("decreto_9_20000101", "art5")]


def item(level, doc, art=None, frag=None, f=None):
    key = {"document": (doc,), "article": (doc, art), "provision": (doc, frag, f)}[level]
    return GoldItem("q", level, key, doc, "x", {"explicit"}, art, frag, f)


def test_document_and_article_matching(loaded):
    _, chunks, ds, _ = loaded
    m = make_matcher(chunks, ds)
    assert m.match(item("document", "lei_1_20000101")).full.tolist() == list(range(10))
    # any chunk of the article, and the grouping chunk that contains it
    assert m.match(item("article", "lei_1_20000101", "art1")).full.tolist() == [0, 1, 2, 3, 9]
    # split article: both parts count; CAP [1,20] contains art2 [11,19]
    assert m.match(item("article", "lei_1_20000101", "art2")).full.tolist() == [4, 5, 6, 9]
    # CAP [1,20] does not contain art3 [21,22]
    assert m.match(item("article", "lei_1_20000101", "art3")).full.tolist() == [7, 8]


def test_annex_rule(loaded):
    _, chunks, ds, _ = loaded
    either, main_first = make_matcher(chunks, ds, "either"), make_matcher(chunks, ds, "main_first")
    a1 = item("article", "decreto_9_20000101", "art1")
    assert either.match(a1).full.tolist() == [10, 11]
    assert either.match(a1).main_and_annex
    assert main_first.match(a1).full.tolist() == [10]
    a5 = item("article", "decreto_9_20000101", "art5")         # only in the annex: both rules find it
    assert either.match(a5).full.tolist() == main_first.match(a5).full.tolist() == [12]
    assert either.is_annex_a([u[0] for u in either.match(a5).units])


def test_provision_full_partial_and_split_parts(loaded):
    _, chunks, ds, _ = loaded
    m = make_matcher(chunks, ds)
    inc = m.match(item("provision", "lei_1_20000101", "art1", "art1_cpt_inc1", L))
    assert inc.full.tolist() == [0, 1, 2, 9]            # ART, CPT (ancestors), INC itself, CAP (contains)
    assert inc.partial.tolist() == []
    art2 = m.match(item("provision", "lei_1_20000101", "art2", "art2", L))
    assert art2.full.tolist() == [9]
    assert art2.partial.tolist() == [4, 5, 6]            # parts and an inciso hold only part of art. 2
    assert [p.tolist() for p in art2.parts] == [[4, 5]]
    cpt = m.match(item("provision", "lei_1_20000101", "art1", "art1", L))
    assert cpt.full.tolist() == [0, 9] and cpt.partial.tolist() == [1, 2, 3]


def test_unit_projection_of_grouping(loaded):
    _, chunks, ds, _ = loaded
    m = make_matcher(chunks, ds)
    assert m.units_of_rows(np.array([9]), "article") == [(L, "art1"), (L, "art2")]
    assert m.units_of_rows(np.array([11, 10]), "document") == [("decreto_9_20000101",)]


# ------------------------------------------------------------------------------------------------
# Context selection
# ------------------------------------------------------------------------------------------------

def test_containment_dedup_and_budget():
    # texts: 0 = article [1,10]; 1 = its inciso [3,4]; 2 = other file; 3 = parent of 4 but ranked after it
    tokens = np.array([500, 100, 300, 400, 50])
    iv = [[(0, 1, 10)], [(0, 3, 4)], [(1, 1, 2)], [(0, 20, 30)], [(0, 21, 22)]]
    ranked = [0, 1, 2, 4, 3]
    assert select(ranked, tokens, iv, Cutoff("k", 5)) == [0, 2, 3, 4]              # inciso 1 dropped
    assert select(ranked, tokens, iv, Cutoff("k", 5), dedup="none") == [0, 1, 2, 3, 4]
    # budget 900: 500 + (inciso dropped) + 300 = 800; 50 fits (850); 400 does not
    assert select(ranked, tokens, iv, Cutoff("budget", 900)) == [0, 2, 3]
    # overflow=stop halts at the first text that does not fit; skip keeps filling
    assert select([0, 3, 2, 4], tokens, iv, Cutoff("budget", 850), overflow="stop") == [0]
    assert select([0, 3, 2, 4], tokens, iv, Cutoff("budget", 850), overflow="skip") == [0, 2, 3]
    assert select([], tokens, iv, Cutoff("budget", 900)) == []


def test_cutoff_parse():
    assert Cutoff.parse("budget=4000") == Cutoff("budget", 4000)
    assert str(Cutoff.parse("k=5")) == "k=5"
    with pytest.raises(ValueError):
        Cutoff.parse("top5")


# ------------------------------------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------------------------------------

def test_metrics_hand_computed():
    pos = [2, 5, math.inf]
    assert M.recall_at(pos, 1, 3) == 0
    assert M.recall_at(pos, 5, 3) == pytest.approx(2 / 3)
    assert M.hit_at(pos, 2) == 1.0 and M.hit_at(pos, 1) == 0.0
    assert M.full_recall_at(pos, 1000, 3) == 0.0 and M.full_recall_at([1, 2], 2, 2) == 1.0
    assert M.reciprocal_rank(pos) == 0.5 and M.reciprocal_rank([math.inf]) == 0.0
    dcg = 1 / math.log2(3) + 1 / math.log2(6)
    idcg = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert M.ndcg_at(pos, 10, 3) == pytest.approx(dcg / idcg)
    assert M.ndcg_at([1, 2], 10, 2) == pytest.approx(1.0)


def test_paired_statistics():
    lo, hi = M.paired_bootstrap_ci(np.full(50, 0.1))
    assert lo == pytest.approx(0.1) and hi == pytest.approx(0.1)
    assert M.paired_permutation_p(np.zeros(30)) == 1.0
    p = M.paired_permutation_p(np.full(30, 1.0))
    assert p < 0.001
    D = np.column_stack([np.full(40, 0.2), np.r_[np.ones(20), -np.ones(20)]])
    lo, hi = M.paired_bootstrap_ci(D, n_resamples=2000)
    assert lo[0] == pytest.approx(0.2) and lo[1] < 0 < hi[1]


# ------------------------------------------------------------------------------------------------
# Input checks
# ------------------------------------------------------------------------------------------------

def test_checks_pass(loaded):
    repo, chunks, ds, emb = loaded
    rep = check_inputs(chunks, sha256_file(repo.chunks), emb, ds)
    assert rep.ok, rep.errors
    assert rep.info["cited_documents_without_chunks"] == []
    assert rep.info["documents_without_chunks"] == 1


def test_check_chunk_hash_mismatch(loaded):
    repo, chunks, ds, emb = loaded
    rep = check_inputs(chunks, "0" * 64, emb, ds)
    assert not rep.ok and "belong to other chunks" in rep.errors[0]


def test_check_query_text_mismatch(loaded):
    repo, chunks, ds, emb = loaded
    ds.questions.loc[0, "question_text"] = "Outra pergunta"
    rep = check_inputs(chunks, sha256_file(repo.chunks), emb, ds, hash_vectors=False)
    assert not rep.ok and any("differ from question_text" in e for e in rep.errors)


def test_check_missing_query_instruction(repo):
    with pytest.raises(Exception, match="instruction-name other"):
        load_embedding(repo.embeddings, "fake", "other")
