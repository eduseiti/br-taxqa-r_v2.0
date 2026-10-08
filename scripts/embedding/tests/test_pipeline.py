"""End-to-end tests with the fake provider: runs, resume after a crash, finalize, manifests, CLI."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from embedding.config import load_config
from embedding.corpus import load_corpus
from embedding.providers.fake import FakeProvider
from embedding.runner import run
from embedding.store import ShardStore, StoreError

MANIFEST_KEYS = {"schema_version", "created_at", "kind", "script", "model", "server", "input", "output",
                 "run", "parity", "cost_ledger"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_resume_after_crash(tmp_path, corpus_path):
    c = load_corpus(corpus_path)
    ids, texts = c.texts["text_id"].tolist(), c.texts["text"].tolist()
    n_tok = [1] * len(ids)
    store = ShardStore(tmp_path / "out")
    store.open({"k": 1})
    with pytest.raises(RuntimeError, match="simulated"):
        run(FakeProvider(8, fail_after=1), store, ids, texts, n_tok, 8, max_inputs=2, max_tokens=100,
            concurrency=1, progress=False)
    done = store.done_ids()
    assert 0 < len(done) < len(ids)
    s2 = run(FakeProvider(8), store, ids, texts, n_tok, 8, 2, 100, 1, progress=False)
    assert s2["n_skipped"] == len(done) and s2["n_texts"] == len(ids) - len(done)
    store.assemble(ids, 8, tmp_path / "v.npy")
    assert np.allclose(np.load(tmp_path / "v.npy"), FakeProvider(8).embed(texts))
    assert [s["status"] for s in store.state()["sessions"]][-1] == "complete"
    assert store.state()["sessions"][0]["status"].startswith("failed")


def test_fingerprint_mismatch_refused(tmp_path):
    store = ShardStore(tmp_path / "out")
    store.open({"template": "a"})
    with pytest.raises(StoreError, match="template"):
        store.open({"template": "b"})
    store.open({"template": "b"}, overwrite=True)
    assert store.state()["fingerprint"] == {"template": "b"}


def test_assemble_detects_missing(tmp_path):
    store = ShardStore(tmp_path / "out")
    store.open({})
    store.write(["a"], np.ones((1, 2), np.float32))
    with pytest.raises(StoreError, match="no vector"):
        store.assemble(["a", "b"], 2, tmp_path / "v.npy")
    assert not (tmp_path / "v.npy").exists()


def test_corpus_dry_run(cli, corpus_path, tmp_path, capsys):
    assert cli("corpus", "--model", "fake-8", "--input", str(corpus_path), "--dry-run") == 0
    assert "5 texts" in capsys.readouterr().out
    assert not (tmp_path / "embeddings" / "fake-8" / "corpus").exists()


def test_corpus_run_finalize_and_determinism(cli, corpus_path, tmp_path, capsys):
    out = tmp_path / "embeddings" / "fake-8" / "corpus"
    assert cli("corpus", "--model", "fake-8", "--input", str(corpus_path), "--no-progress") == 0
    m = _load(out / "manifest.json")
    assert MANIFEST_KEYS <= set(m)
    assert m["output"]["shape"] == [5, 8] and m["output"]["norms_ok"]
    assert m["input"]["rows"] == 6 and m["input"]["unique_texts"] == 5
    assert m["run"]["n_texts"] == 5 and m["parity"]["status"].startswith("not applicable")
    assert not (out / "_shards").exists()
    v = np.load(out / "vectors.npy")
    texts = pd.read_csv(out / "texts.csv", dtype=str)
    cmap = pd.read_csv(out / "chunk_map.csv.gz", dtype=str)
    assert len(texts) == 5 and len(cmap) == 6 and set(cmap.text_id) == set(texts.text_id)
    c = load_corpus(corpus_path)
    assert np.allclose(v, FakeProvider(8).embed(c.texts["text"].tolist()))

    # idempotent without --overwrite; byte-identical sidecars with it
    before = {p: (out / p).read_bytes() for p in ("texts.csv", "chunk_map.csv.gz", "vectors.npy")}
    assert cli("corpus", "--model", "fake-8", "--input", str(corpus_path)) == 0
    assert "already finalized" in capsys.readouterr().out
    assert cli("corpus", "--model", "fake-8", "--input", str(corpus_path), "--overwrite", "--no-progress") == 0
    assert {p: (out / p).read_bytes() for p in before} == before
    assert _load(out / "manifest.json")["output"]["sha256"] == m["output"]["sha256"]


def test_queries_per_instruction(cli, queries_path, tmp_path):
    root = tmp_path / "embeddings" / "fake-8" / "queries"
    assert cli("queries", "--model", "fake-8", "--input", str(queries_path), "--no-progress") == 0
    assert cli("queries", "--model", "fake-8", "--input", str(queries_path), "--instruction-name", "other",
               "--no-progress") == 0
    q = pd.read_csv(root / "irpf" / "queries.csv", dtype=str, keep_default_na=False)
    assert q["text_sent"][0] == "Instruct: Find IRPF provisions\nQuery: Pergunta 1 sobre {IRPF}?"
    assert q["query_id"].tolist() == ["001", "002", "003", "004"]
    m = _load(root / "other" / "manifest.json")
    assert m["model"]["instruction_name"] == "other" and m["model"]["instruction"] == "Other task"
    assert np.load(root / "irpf" / "vectors.npy").shape == (4, 8)


def test_length_guard_stops_run(cli, tmp_path):
    from embedding.corpus import text_hash
    df = pd.DataFrame({"chunk_id": ["a", "b"], "Texto": ["curto", "y" * 1000]})
    df["texto_sha256"] = df["Texto"].map(text_hash)
    p = tmp_path / "long.csv"
    df.to_csv(p, index=False)
    assert cli("corpus", "--model", "fake-8", "--input", str(p)) == 2
    assert not (tmp_path / "embeddings" / "fake-8" / "corpus" / "_shards").exists()


def test_costs_cli(cli, tmp_path, capsys):
    assert cli("costs", "add", "--model", "fake-8", "--activity", "other", "--replica-minutes", "30",
               "--notes", "UI playground") == 0
    assert cli("costs", "summary") == 0
    out = capsys.readouterr().out
    assert "fake-8" in out and "0.4" in out
    assert (tmp_path / "embeddings" / "costs.csv").exists()


def test_models_listing(cli, capsys):
    assert cli("models") == 0
    assert "fake-8" in capsys.readouterr().out


def test_repo_registry_loads():
    models = load_config()
    assert "jua-4b-mixed" in models
    jua = models["jua-4b-mixed"]
    assert jua.dim == 2560 and jua.revision.startswith("57f491c")
    assert jua.render_query("q").endswith("\nQuery: q")


def test_corpus_extend_embeds_only_new_texts(cli, corpus_path, tmp_path):
    """--extend (embed by text hash): texts already in the finalized store are reused, only new
    ones are sent, removed ones are dropped, and the result equals a full run."""
    from embedding.corpus import text_hash
    out = tmp_path / "embeddings" / "fake-8" / "corpus"
    assert cli("corpus", "--model", "fake-8", "--input", str(corpus_path), "--no-progress") == 0
    first = _load(out / "manifest.json")
    df = pd.read_csv(corpus_path, dtype=str)
    df = df[df["chunk_id"] != "doc#5"]                                   # one text removed
    new = pd.DataFrame({"chunk_id": ["doc#9", "doc#c3"], "Texto": ["Art. 9º Nono.", "Art. 1º Caput § 1º Parágrafo."],
                        "Tipo": ["ART", "PAR"]})
    new["texto_sha256"] = new["Texto"].map(text_hash)
    df = pd.concat([df, new.assign(n_tokens=new["Texto"].str.len().astype(str))], ignore_index=True)
    p2 = tmp_path / "chunks2.csv.gz"
    df.to_csv(p2, index=False)
    assert cli("corpus", "--model", "fake-8", "--input", str(p2), "--no-progress") == 0   # refuses silently
    assert _load(out / "manifest.json") == first
    assert cli("corpus", "--model", "fake-8", "--input", str(p2), "--extend", "--no-progress") == 0
    m = _load(out / "manifest.json")
    assert m["extend"]["reused_texts"] == 4 and m["extend"]["embedded_texts"] == 2
    assert m["extend"]["dropped_texts"] == 1
    assert m["run"]["n_texts"] == 2 and m["output"]["shape"] == [6, 8]
    v = np.load(out / "vectors.npy")
    texts = pd.read_csv(out / "texts.csv", dtype=str)
    c = load_corpus(p2)
    assert list(texts["text_id"]) == list(c.texts["text_id"])
    assert np.allclose(v, FakeProvider(8).embed(c.texts["text"].tolist()))
