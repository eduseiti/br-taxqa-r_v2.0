"""OpenRouter provider (token-priced API models): mocked HTTP session, no network."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from embedding.corpus import text_hash
from embedding.providers import openrouter as orp
from embedding.providers.base import ProviderError
from embedding.runner import pack

from conftest import TEXTS

OR_MODEL = """
  or-8:
    provider: openrouter
    model_id: google/fake-embedding
    api_key_env: TEST_OR_KEY
    routing: {only: [google-ai-studio], allow_fallbacks: false, data_collection: deny}
    served_provider: Google AI Studio
    dim: 8
    tokenizer: chars:4
    query_template: "task: search result | query: {text}"
    document_template: "title: none | text: {text}"
    request: {max_inputs: 2, max_request_tokens: 1000, solo_above_tokens: 40, concurrency: 2}
    price: {usd_per_million_tokens: 0.20, checked: "2026-11-08"}
    parity: {determinism_min_cos: 0.9999}
"""


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    """Answers like OpenRouter's /embeddings. ``script`` holds forced replies (status, body) consumed first."""
    script: list = []
    calls: list = []
    served = "Google AI Studio"
    tokens_per_char = 0.25

    def __init__(self):
        self.headers = {}

    def post(self, url, json=None, timeout=None):
        FakeSession.calls.append(json)
        if FakeSession.script:
            return FakeResponse(*FakeSession.script.pop(0))
        data = []
        for i, t in enumerate(json["input"]):
            seed = int.from_bytes(hashlib.sha256(t.encode()).digest()[:8], "little")
            v = np.random.default_rng(seed).standard_normal(8)
            data.append({"object": "embedding", "index": i, "embedding": (v / np.linalg.norm(v)).tolist()})
        tok = sum(max(1, int(len(t) * self.tokens_per_char)) for t in json["input"])
        return FakeResponse(200, {"object": "list", "data": data[::-1], "model": json["model"],
                                  "provider": FakeSession.served,
                                  "usage": {"prompt_tokens": tok, "total_tokens": tok, "cost": tok * 0.2e-6}})


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    FakeSession.script, FakeSession.calls, FakeSession.served = [], [], "Google AI Studio"
    monkeypatch.setattr(orp.requests, "Session", FakeSession)
    monkeypatch.setattr(orp.time, "sleep", lambda s: None)
    monkeypatch.setenv("TEST_OR_KEY", "sk-test")


def provider(**kw):
    args = dict(token="sk", model_id="google/fake-embedding", routing={"only": ["google-ai-studio"]},
                served_provider="Google AI Studio", max_input_tokens=100)
    return orp.OpenRouterProvider(**(args | kw))


# ------------------------------------------------------------------------------------------------
# provider
# ------------------------------------------------------------------------------------------------

def test_embed_orders_by_index_and_counts_usage():
    p = provider()
    v = p.embed(["a" * 40, "b" * 80])
    assert v.shape == (2, 8) and v.dtype == np.float32
    again = p.embed(["a" * 40])
    assert np.allclose(v[0], again[0])                 # reply came reversed: sorted by index
    assert p.stats["prompt_tokens"] == 10 + 20 + 10
    assert p.stats["cost_usd"] == pytest.approx(40 * 0.2e-6)
    assert FakeSession.calls[0]["provider"] == {"only": ["google-ai-studio"]}
    assert FakeSession.calls[0]["encoding_format"] == "float"
    assert dict(p.served) == {"Google AI Studio": 2}


def test_wrong_served_provider_fails():
    FakeSession.served = "Google Vertex"
    with pytest.raises(ProviderError, match="served by"):
        provider().embed(["x"])


def test_single_overlong_input_detected():
    with pytest.raises(ProviderError, match="truncated silently"):
        provider(max_input_tokens=10).embed(["y" * 400])     # 100 tokens reported > 10


def test_retry_then_success_and_fatal_4xx():
    FakeSession.script = [(429, {"error": {"code": 429, "message": "rate"}}),
                          (200, {"error": {"code": 502, "message": "upstream"}})]
    p = provider()
    assert p.embed(["z"]).shape == (1, 8)
    assert p.stats["retries"] == 2
    FakeSession.script = [(402, {"error": {"code": 402, "message": "no credit"}})]
    with pytest.raises(ProviderError, match="402"):
        p.embed(["z"])


def test_budget_stops_run():
    p = provider(budget_usd=1e-6)
    p.embed(["w" * 40])                                  # 10 tokens = $2e-6: over the budget afterwards
    with pytest.raises(orp.BudgetExceeded):
        p.embed(["w"])


def test_pack_sends_long_texts_alone():
    assert pack([10, 50, 10, 10, 60, 10], max_inputs=3, max_tokens=1000, solo_above=40) == [[0], [1], [2, 3], [4], [5]]
    assert pack([10, 50, 10], max_inputs=3, max_tokens=1000) == [[0, 1, 2]]


# ------------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------------

@pytest.fixture
def or_cli(tmp_path, config_path, cli):
    config_path.write_text(config_path.read_text() + OR_MODEL, encoding="utf-8")
    return cli


def test_corpus_needs_budget_and_writes_ledger(or_cli, corpus_path, tmp_path):
    common = ["corpus", "--model", "or-8", "--input", str(corpus_path), "--no-progress", "--skip-parity"]
    assert or_cli(*common) == 2                                              # no --budget
    assert or_cli(*common, "--budget", "1e-9") == 2                          # estimate over the cap
    assert or_cli(*common, "--budget", "1") == 0
    out = tmp_path / "embeddings" / "or-8" / "corpus"
    assert np.load(out / "vectors.npy").shape == (5, 8)
    man = json.loads((out / "manifest.json").read_text())
    assert man["model"]["template"] == "title: none | text: {text}"
    assert man["run"]["prompt_tokens"] > 0 and man["run"]["cost_usd"] > 0
    led = pd.read_csv(tmp_path / "embeddings" / "costs.csv")
    row = led.iloc[-1]
    assert (row.provider, row.billing_unit, row.source, row.activity) == ("openrouter", "tokens", "provider_reported", "corpus")
    assert row.quantity == man["run"]["prompt_tokens"]
    assert row.usd == pytest.approx(man["run"]["cost_usd"], abs=1e-6)
    sent = [c["input"] for c in FakeSession.calls]
    assert all(t.startswith("title: none | text: ") for b in sent for t in b)
    assert any(len(b) == 1 and len(b[0]) > 160 for b in sent)                # the long text went alone


def test_determinism_parity_gates_the_run(or_cli, corpus_path, queries_path, tmp_path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"text_ids": [text_hash(t) for t in TEXTS[:2]], "query_ids": ["001", "002"]}))
    common = ["--model", "or-8", "--input", str(corpus_path)]
    assert or_cli("parity", *common, "--queries", str(queries_path), "--sample", str(sample)) == 0
    par = json.loads((tmp_path / "embeddings" / "or-8" / "parity.json").read_text())
    assert par["passed"] and par["checks"]["deterministic"] and par["metrics"]["dim"] == 8
    assert len(FakeSession.calls) == 2                                       # 4 strings, twice, in batches of 8
    assert or_cli("corpus", *common, "--no-progress", "--budget", "1") == 0     # gate passes without --skip-parity
    led = pd.read_csv(tmp_path / "embeddings" / "costs.csv")
    assert list(led.activity) == ["parity", "corpus"]
