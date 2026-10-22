"""Corpus exclusions: an excluded document leaves the rankings, the oracle and the reachable gold, and its
gold items are reported as "excluded_from_corpus"; a run without exclusions is kept under another name."""

from __future__ import annotations

import pandas as pd
import pytest

from ragpipe.contexts import ContextConfig, load_contexts, run_contexts
from ragpipe.data import InputError
from ragpipe.evaluation import EvalConfig, run_evaluation
from ragpipe.retrieval import RetrievalConfig, load_rankings, run_retrieval
from ragpipe.runs import read_json

EVAL = EvalConfig(budgets=(16000,), unit_ks=(1,), raw_ks=(1,), n_resamples=50)


def test_excluded_document(repo, tmp_path):
    lst = tmp_path / "excl.yaml"
    lst.write_text("documents:\n  urn_x:\n    rule: revoked\n")
    rdir = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", exclusions=lst), repo)
    base = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", exclusions=None, run_name="irpf_all"),
                         repo)
    assert rdir.name == "irpf" and base.name == "irpf_all"
    man = read_json(rdir / "manifest.json")
    assert man["corpus_exclusions"]["documents"] == ["urn_x"] and man["corpus_exclusions"]["chunk_rows_excluded"] == 2
    for s in ("S1", "S2"):
        assert not load_rankings(rdir, s)["chunk_id"].str.startswith("urn_x").any()
        assert load_rankings(base, s)["chunk_id"].str.startswith("urn_x").any()
    edir = run_evaluation(rdir, EVAL, repo)
    it = pd.read_csv(edir / "per_item.csv.gz", dtype={"question_number": str}, keep_default_na=False)
    x = it[(it.level == "document") & (it.item == "urn_x")]
    assert len(x) and (x["reachable"].astype(str) == "False").all()
    assert set(x["unreachable_reason"]) == {"excluded_from_corpus"}
    assert read_json(edir / "manifest.json")["retrieval"]["excluded_documents"] == ["urn_x"]
    root = run_contexts(rdir, ContextConfig(sets=("oracle@budget=16000",), count_tokens=False), repo)
    assert root.name == "irpf"
    o = {ln["question_number"]: ln for ln in load_contexts(root / "oracle_budget16000")}
    assert not any(i["document_id"] == "urn_x" for i in o["003"]["items"]) and o["003"]["n_texts"] > 0
    allroot = run_contexts(base, ContextConfig(sets=("oracle@budget=16000",), count_tokens=False), repo)
    assert allroot.name == "irpf_all"


def test_unknown_excluded_document(repo, tmp_path):
    lst = tmp_path / "excl.yaml"
    lst.write_text("documents:\n  nope:\n    rule: revoked\n")
    with pytest.raises(InputError, match="not in dataset"):
        run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf", exclusions=lst), repo)
