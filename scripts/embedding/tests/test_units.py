"""Unit tests: config/templates, loaders, packing, length guard, validation, parity metrics, costs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from embedding import costs, endpoint, parity
from embedding.config import ConfigError, load_config
from embedding.corpus import CorpusError, load_corpus, load_queries, text_hash
from embedding.providers.base import ProviderError
from embedding.runner import pack, validate
from embedding.tokens import LengthError, guard, load_counter


# ------------------------------------------------------------------------------------------------
# config / templates
# ------------------------------------------------------------------------------------------------

def test_templates_exact(config_path):
    cfg = load_config(config_path)["fake-8"]
    assert cfg.render_query("Q {text} ?") == "Instruct: Find IRPF provisions\nQuery: Q {text} ?"
    assert cfg.render_query("x", "other") == "Instruct: Other task\nQuery: x"
    assert cfg.render_document("  doc {instruction}\n") == "  doc {instruction}\n"
    with pytest.raises(ConfigError):
        cfg.render_query("x", "missing")


def test_unknown_key_rejected(tmp_path, config_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(config_path.read_text().replace("dim: 8", "dim: 8\n    dimm: 3"))
    with pytest.raises(ConfigError, match="dimm"):
        load_config(bad)


def test_nested_defaults_merged(config_path):
    cfg = load_config(config_path)["fake-8"]
    assert cfg.parity == {"median_cos": 0.999, "min_cos": 0.995, "top1_all": True}
    assert cfg.max_input_tokens == 100


# ------------------------------------------------------------------------------------------------
# loaders
# ------------------------------------------------------------------------------------------------

def test_dedup_and_chunk_map(corpus_path):
    c = load_corpus(corpus_path)
    assert c.info["rows"] == 6 and c.info["unique_texts"] == 5
    assert c.texts["text_id"].is_monotonic_increasing
    m = dict(zip(c.chunk_map["chunk_id"], c.chunk_map["text_id"]))
    assert m["doc#0"] == m["doc#2"] == text_hash("Art. 1º Primeiro.")
    assert set(m.values()) == set(c.texts["text_id"])


def test_edited_text_detected(tmp_path, corpus_path):
    df = pd.read_csv(corpus_path, dtype=str, keep_default_na=False)
    df.loc[1, "Texto"] += " "
    p = tmp_path / "edited.csv"
    df.to_csv(p, index=False)
    with pytest.raises(CorpusError, match="sha256"):
        load_corpus(p)


def test_hash_prefix_collision_fails(corpus_path, monkeypatch):
    import embedding.corpus as corpus
    monkeypatch.setattr(corpus, "text_hash", lambda t: "0" * 16)
    with pytest.raises(CorpusError, match="share"):
        load_corpus(corpus_path, hash_col=None)


def test_queries_loader(queries_path):
    q, info = load_queries(queries_path)
    assert q["query_id"].tolist() == ["001", "002", "003", "004"] and info["rows"] == 4


# ------------------------------------------------------------------------------------------------
# packing, guard, validation
# ------------------------------------------------------------------------------------------------

def test_pack_limits():
    b = pack([10, 10, 10, 50, 5, 100, 1], max_inputs=3, max_tokens=60)
    assert b == [[0, 1, 2], [3, 4], [5], [6]]
    assert sorted(i for x in b for i in x) == list(range(7))


def test_length_guard():
    guard(["a", "b"], [5, 10], 10)
    with pytest.raises(LengthError) as e:
        guard(["a", "b", "c"], [11, 5, 30], 10)
    assert [i for i, _ in e.value.offenders] == ["c", "a"]


def test_chars_counter():
    assert load_counter("chars:4")(["abcd", "abcde", ""]) == [1, 2, 1]


def test_validate():
    counters = {"renormalized": 0}
    v = np.array([[3.0, 4.0], [0.6, 0.8]], dtype=np.float32)
    out = validate(v, 2, 2, counters)
    assert counters["renormalized"] == 1 and np.allclose(np.linalg.norm(out, axis=1), 1)
    with pytest.raises(ProviderError, match="shape"):
        validate(v, 2, 3, counters)
    with pytest.raises(ProviderError, match="non-finite"):
        validate(np.array([[np.nan, 1.0]]), 1, 2, counters)
    with pytest.raises(ProviderError, match="zero"):
        validate(np.zeros((1, 2)), 1, 2, counters)


# ------------------------------------------------------------------------------------------------
# parity
# ------------------------------------------------------------------------------------------------

def _unit(a):
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def test_kendall_tau():
    a = np.arange(10.0)
    assert parity.kendall_tau(a, a) == 1.0 and parity.kendall_tau(a, -a) == -1.0


def test_compare_pass_and_fail():
    rng = np.random.default_rng(0)
    ref = _unit(rng.standard_normal((20, 16)))
    th = {"median_cos": 0.999, "min_cos": 0.995, "top1_all": True}
    ok = parity.compare(_unit(ref + 1e-5 * rng.standard_normal(ref.shape)), ref, 16, th)
    assert ok["passed"] and ok["metrics"]["top1_agree"] == 4
    bad = parity.compare(_unit(ref + 0.3 * rng.standard_normal(ref.shape)), ref, 16, th)
    assert not bad["passed"] and not bad["checks"]["cos_min"]


def test_make_sample_deterministic():
    tipos = [f"T{i:02d}" for i in range(16)]
    rows = pd.DataFrame({"texto_sha256": [f"{i:016x}" for i in range(400)],
                         "Tipo": [tipos[i % 16] for i in range(400)], "n_tokens": [str(i * 7 % 997) for i in range(400)]})
    q = pd.DataFrame({"query_id": [f"{i:03d}" for i in range(1, 716)]})
    s1, s2 = parity.make_sample(rows, q), parity.make_sample(rows, q)
    assert s1 == s2
    assert len(s1["text_ids"]) == 64 == len(set(s1["text_ids"])) and len(s1["query_ids"]) == 16
    longest = rows.assign(n=rows.n_tokens.astype(int)).nlargest(5, "n")["texto_sha256"]
    assert set(longest) <= set(s1["text_ids"])
    assert set(rows.set_index("texto_sha256").loc[s1["text_ids"], "Tipo"]) == set(tipos)


# ------------------------------------------------------------------------------------------------
# endpoint meter and costs
# ------------------------------------------------------------------------------------------------

def test_replica_minutes():
    s = [{"ts": 0, "state": "paused", "ready": 0, "target": 1},
         {"ts": 60, "state": "initializing", "ready": 0, "target": 1},
         {"ts": 360, "state": "running", "ready": 1, "target": 1},
         {"ts": 960, "state": "paused", "ready": 0, "target": 1}]
    assert endpoint.replica_minutes(s) == pytest.approx(15.0)       # 5 initializing + 10 running
    assert endpoint.replica_minutes(s[:3], end_ts=420) == pytest.approx(6.0)
    assert endpoint.round_minutes(14.01) == 15 and endpoint.round_minutes(0) == 0


def test_ledger_rows_and_summary(tmp_path, config_path):
    cfg = load_config(config_path)["fake-8"]
    ledger = tmp_path / "costs.csv"
    rows = costs.endpoint_rows(ledger, cfg, "corpus", "run1", {"replica_minutes": 90.2, "start": 0, "end": 5400},
                               idle_minutes=15)
    assert [r["activity"] for r in rows] == ["corpus", "idle"]
    assert rows[0]["quantity"] == 91 and rows[0]["usd"] == pytest.approx(91 * 0.8 / 60, abs=1e-4)
    assert rows[1]["usd"] == pytest.approx(0.2)
    df = pd.read_csv(ledger)
    assert list(df.columns) == costs.COLUMNS and len(df) == 2
    md = costs.summary(ledger, "model", markdown=True)
    assert md.startswith("| model_slug |") and "fake-8" in md and "TOTAL" in md
