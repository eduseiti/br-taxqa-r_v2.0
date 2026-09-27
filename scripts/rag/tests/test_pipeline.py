"""End-to-end: retrieve → evaluate on the fixture repository, determinism, run-directory guards, CLI."""

from __future__ import annotations

import json

import pandas as pd
import pytest

import rag
from ragpipe.evaluation import EvalConfig, run_evaluation
from ragpipe.retrieval import RetrievalConfig, load_rankings, run_retrieval
from ragpipe.runs import RunError, read_json

from conftest import text_id

EVAL = EvalConfig(budgets=(500, 16000), unit_ks=(1, 3), raw_ks=(1, 5), n_resamples=200)


def run_all(paths, cfg=EVAL):
    rdir = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf"), paths)
    return rdir, run_evaluation(rdir, cfg, paths)


def test_rankings(repo):
    rdir, _ = run_all(repo)
    s1, s2 = load_rankings(rdir, "S1"), load_rankings(rdir, "S2")
    assert list(s1.columns) == ["question_number", "rank", "text_id", "chunk_id", "alias_chunk_ids", "score"]
    assert s1.groupby("question_number").size().tolist() == [9, 9, 9, 9]    # all candidates (top-N > corpus)
    # question 001's vector is the text of INC art1_cpt_inc1: rank 1 in S2, absent from S1
    top2 = s2[s2["question_number"] == "001"].iloc[0]
    assert top2["text_id"] == text_id("Art. 1 inciso I") and top2["score"] == pytest.approx(1.0)
    assert text_id("Art. 1 inciso I") not in set(s1["text_id"])
    # the shared ART/INC text of art3 carries its alias in S2 only
    art3 = s2[(s2["question_number"] == "001") & (s2["text_id"] == text_id("Art. 3 único inciso"))].iloc[0]
    assert art3["alias_chunk_ids"] != "" and art3["chunk_id"] != art3["alias_chunk_ids"]
    man = read_json(rdir / "manifest.json")
    assert man["counts"]["S2"] == {"chunk_rows": 14, "candidate_texts": 13, "ranking_rows": 52,
                                   "texts_with_aliases": 1}


def test_evaluation_items(repo):
    rdir, edir = run_all(repo)
    it = pd.read_csv(edir / "per_item.csv.gz", dtype={"question_number": str, "cutoff": str})
    get = lambda s, lv, q: it[(it.strategy == s) & (it.level == lv) & (it.question_number == q)]  # noqa: E731
    # Q001 provision art1_cpt_inc1: the inciso is rank 1 in S2; in S1 the whole article covers it
    assert get("S2", "provision", "001")["rank_full"].iloc[0] == 1
    s1_rank = load_rankings(rdir, "S1")
    s1_q1 = s1_rank[s1_rank.question_number == "001"].reset_index(drop=True)
    art1_rank = s1_q1.index[s1_q1.text_id == text_id("Art. 1 inteiro")][0] + 1
    assert get("S1", "provision", "001")["rank_full"].iloc[0] == art1_rank
    # Q002 provision art2 (split article): part 1 is a partial hit at rank 1; full once part 2 is in
    q2 = get("S1", "provision", "002").iloc[0]
    s1_q2 = s1_rank[s1_rank.question_number == "002"].reset_index(drop=True)
    part2 = s1_q2.index[s1_q2.text_id == text_id("Art. 2 parte 2")][0] + 1
    assert q2["rank_any"] == 1 and q2["rank_full"] == max(1, part2)
    assert bool(q2["reachable"]) and bool(q2["reachable_by_parts_only"]) and bool(q2["budget_full_16000"])
    # in S3 the chapter chunk holds the whole article
    assert not bool(get("S3", "provision", "002")["reachable_by_parts_only"].iloc[0])
    # Q003: documents decreto_9 (explicit) + urn_x (embedded); no gold for Q004
    docs = get("S1", "document", "003")
    assert sorted(docs["origin"]) == ["embedded", "explicit"] and "004" not in set(it.question_number)
    # annex article art5 is rank 1 (the question vector is its text) and is category-A annex gold
    a5 = get("S1", "article", "003")
    assert a5["annex_A"].all() and a5["unit_pos"].min() == 1


def test_evaluation_metrics(repo):
    _, edir = run_all(repo)
    m = pd.read_csv(edir / "metrics.csv", dtype={"cutoff": str})
    get = lambda **kw: m.loc[(m[list(kw)] == pd.Series(kw)).all(axis=1), "value"]  # noqa: E731
    # everything fits in 16k: recall = oracle, context precision well defined
    for s in ("S1", "S2", "S3"):
        for lv in ("document", "article", "provision"):
            full = get(strategy=s, level=lv, view="budget", cutoff="16000", gold="all", slice="all", metric="recall")
            oracle = get(strategy=s, level=lv, view="oracle", cutoff="-", gold="all", slice="all", metric="recall")
            assert full.iloc[0] == pytest.approx(oracle.iloc[0])
    assert set(m["gold"]) == {"all", "reachable"}
    assert {"explicit", "embedded", "annex_A"} <= set(m["slice"])
    comp = pd.read_csv(edir / "comparisons.csv")
    assert set(zip(comp["a"], comp["b"])) == {("S1", "S2"), ("S2", "S3")}
    assert (edir / "report.md").read_text().startswith("# Retrieval evaluation — fake / irpf")
    chap = pd.read_csv(edir / "metrics_by_chapter.csv.gz")
    assert set(chap["slice"]) == {"chapter:A", "chapter:B"}


def test_deterministic_outputs(repo):
    rdir, edir = run_all(repo)
    first = {p: (rdir / p).read_bytes() for p in ("S1/rankings.csv.gz", "S3/rankings.csv.gz")}
    first |= {p: (edir / p).read_bytes() for p in ("metrics.csv", "per_question.csv.gz", "comparisons.csv")}
    run_all(repo)
    for p, data in first.items():
        base = rdir if p.endswith("rankings.csv.gz") else edir
        assert (base / p).read_bytes() == data, p


def test_run_dir_guard(repo):
    rdir, _ = run_all(repo)
    with pytest.raises(RunError, match="another configuration"):
        run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", top_n=3), repo)
    run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", top_n=3, force=True), repo)
    assert load_rankings(rdir, "S1").groupby("question_number").size().max() == 3


def test_evaluate_rejects_other_chunks(repo):
    rdir, _ = run_all(repo)
    man = read_json(rdir / "manifest.json")
    man["inputs"]["chunks"]["sha256"] = "f" * 64
    (rdir / "manifest.json").write_text(json.dumps(man))
    with pytest.raises(Exception, match="another chunk file"):
        run_evaluation(rdir, EVAL, repo)


def test_annex_rule_main_first(repo):
    rdir, _ = run_all(repo)
    edir = run_evaluation(rdir, EvalConfig(annex_rule="main_first", budgets=(16000,), unit_ks=(1,), raw_ks=(1,),
                                           n_resamples=100), repo)
    assert edir.name == "main_first_containment_skip"
    it = pd.read_csv(edir / "per_item.csv.gz", dtype={"question_number": str})
    a1 = it[(it.level == "article") & (it.item == "decreto_9_20000101|art1")]
    assert a1["main_and_annex"].all()


def test_cli(repo, capsys):
    common = ["--chunks", str(repo.chunks), "--dataset", str(repo.dataset), "--embeddings-dir", str(repo.embeddings),
              "--runs-dir", str(repo.runs), "--strategies-file", str(repo.strategies)]
    assert rag.main(["check", "--embedding", "fake", *common]) == 0
    assert rag.main(["retrieve", "--embedding", "fake", "--strategies", "S1,S2", *common]) == 0
    rdir = repo.runs / "retrieval" / "fake" / "irpf"
    assert rag.main(["evaluate", "--retrieval", str(rdir), "--budgets", "500,1000", "--resamples", "100",
                     *common]) == 0
    assert rag.main(["compare", "--retrieval", str(rdir), "--a", "S1", "--b", "S2", "--resamples", "100"]) == 0
    assert "S2 − S1" in capsys.readouterr().out
    assert rag.main(["retrieve", "--embedding", "nope", *common]) == 2       # helpful error, no traceback
    assert "embed.py queries --model nope" in capsys.readouterr().err
