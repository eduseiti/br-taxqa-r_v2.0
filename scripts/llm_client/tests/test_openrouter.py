"""OpenRouter provider, route config and ledger, against mocked HTTP replies. No network, no key needed.

    .venv/bin/python -m pytest scripts/llm_client/tests
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

from llm_client import client  # noqa: E402
from llm_client.client import (LLM, CreditsExhausted, LLMError, RouteMismatch, ledger_total,  # noqa: E402
                               load_registry, openrouter_body, route_config)

REGISTRY = load_registry(SCRIPTS / "nuggets" / "models.yaml")
SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}


class Reply:
    def __init__(self, status=200, body=None, ctype="application/json"):
        self.status_code, self._body = status, body or {}
        self.headers = {"content-type": ctype}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


def ok(text='{"x": 1}', provider="OpenAI", finish="stop", cost=0.0021):
    return Reply(body={"id": "gen-1", "model": "openai/gpt-6.1-sol", "provider": provider,
                       "choices": [{"finish_reason": finish, "native_finish_reason": "completed",
                                    "message": {"role": "assistant", "content": text}}],
                       "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": cost,
                                 "prompt_tokens_details": {"cached_tokens": 400},
                                 "completion_tokens_details": {"reasoning_tokens": 120}}})


@pytest.fixture
def replies(monkeypatch):
    """Queue of replies served to ``httpx.post``; the requests sent are recorded."""
    q, sent = [], []

    def post(url, json=None, headers=None, timeout=None):  # noqa: A002
        sent.append({"url": url, "json": json, "headers": headers})
        return q.pop(0)

    monkeypatch.setattr(client.httpx, "post", post)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    return q, sent


def make(tmp_path, name="gpt-6.1-sol", budget=None):
    return LLM(name, route_config(REGISTRY[name], "openrouter"), tmp_path / "cache", tmp_path / "costs.csv",
               budget_usd=budget)


def ledger(tmp_path):
    return list(csv.DictReader((tmp_path / "costs.csv").open()))


# ------------------------------------------------------------------ registry and route config
def test_every_model_has_an_openrouter_route():
    for name, cfg in REGISTRY.items():
        r = route_config(cfg, "openrouter")
        assert r["provider"] == "openrouter" and r["api_key_env"] == "OPENROUTER_API_KEY"
        assert r["routing"]["allow_fallbacks"] is False and r["routing"]["require_parameters"] is True
        assert len(r["routing"]["only"]) == 1 and r["served_provider"]
        assert "reasoning" in r["params"], f"{name}: reasoning must be explicit (D12)"
        assert "openrouter" not in r and "base_url" not in r


def test_direct_route_is_the_registry_entry():
    cfg = REGISTRY["qwen3.8-max"]
    r = route_config(cfg, "direct")
    assert {k: v for k, v in r.items() if k != "route"} == cfg and r["route"] == "direct"


def test_qwen_route_keeps_the_pilot_thinking_budget_and_price_override():
    r = route_config(REGISTRY["qwen3.8-max"], "openrouter")
    assert r["params"]["reasoning"] == {"max_tokens": 2048}       # OpenRouter's default effort is xhigh
    assert r["params"]["response_format"] == "json_object"
    assert r["price"]["usd_per_million_cached_input"] == 0.25
    assert r["price"]["usd_per_million_input"] == REGISTRY["qwen3.8-max"]["price"]["usd_per_million_input"]


def test_unknown_route():
    with pytest.raises(LLMError):
        route_config(REGISTRY["gpt-6.1-sol"], "nowhere")


def test_body_shapes():
    gpt = route_config(REGISTRY["gpt-6.1-sol"], "openrouter")
    b = openrouter_body(gpt["model_id"], gpt["params"], gpt["routing"], "S", "U", SCHEMA, "nuggets")
    assert b["response_format"] == {"type": "json_schema",
                                    "json_schema": {"name": "nuggets", "schema": SCHEMA, "strict": True}}
    assert b["reasoning"] == {"effort": "medium"} and b["provider"]["only"] == ["openai/flex"]
    assert [m["role"] for m in b["messages"]] == ["system", "user"]
    q = route_config(REGISTRY["qwen3.8-max"], "openrouter")
    assert openrouter_body(q["model_id"], q["params"], q["routing"], "S", "U", SCHEMA, "n")["response_format"] == \
        {"type": "json_object"}


# ------------------------------------------------------------------ calls
def test_call_cache_and_ledger(tmp_path, replies):
    q, sent = replies
    q.append(ok())
    m = make(tmp_path)
    r = m.complete_json("S", "U", SCHEMA, "n", tag="create:001")
    assert r.data == {"x": 1} and not r.from_cache
    assert (r.usage.input, r.usage.cached_input, r.usage.output, r.usage.reasoning) == (1000, 400, 200, 120)
    assert r.meta["provider"] == "OpenAI" and r.meta["usd_billed"] == 0.0021
    assert sent[0]["url"].endswith("/chat/completions") and sent[0]["headers"]["Authorization"] == "Bearer sk-or-test"
    row = ledger(tmp_path)[0]
    assert row["route"] == "openrouter" and row["provider_served"] == "OpenAI" and float(row["usd_billed"]) == 0.0021
    # list price: 600 × 2.00 + 400 × 0.10 + 200 × 10.00 per 1M
    assert float(row["usd_standard"]) == pytest.approx((600 * 2 + 400 * 0.1 + 200 * 10) / 1e6)
    assert ledger_total(tmp_path / "costs.csv") == pytest.approx(0.0021)
    r2 = m.complete_json("S", "U", SCHEMA, "n", tag="create:001")      # cache hit: no HTTP call queued
    assert r2.from_cache and r2.data == {"x": 1} and len(sent) == 1


def test_routing_enters_the_cache_key_only_on_openrouter(tmp_path, replies, monkeypatch):
    q, _ = replies
    q.append(ok())
    m = make(tmp_path)
    k_or = m.complete_json("S", "U", SCHEMA, "n").cache_key
    rec = json.loads((tmp_path / "cache" / f"{k_or}.json").read_text())
    assert rec["request"]["routing"]["only"] == ["openai/flex"] and rec["request"]["provider"] == "openrouter"
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    d = LLM("gemini-3.8-flash", route_config(REGISTRY["gemini-3.8-flash"], "direct"), tmp_path / "c2")
    assert d.routing is None       # direct requests (and their cache keys) are as before


def test_error_in_a_200_reply_is_retried(tmp_path, replies):
    q, sent = replies
    q += [Reply(body={"error": {"code": 502, "message": "upstream"}}), ok()]
    assert make(tmp_path).complete_json("S", "U", SCHEMA, "n").data == {"x": 1}
    assert len(sent) == 2 and len(ledger(tmp_path)) == 1     # the failed reply was not billed or logged


def test_402_is_fatal_and_not_retried(tmp_path, replies):
    q, sent = replies
    q += [Reply(402, {"error": {"code": 402, "message": "Insufficient credits"}}), ok()]
    with pytest.raises(CreditsExhausted):
        make(tmp_path).complete_json("S", "U", SCHEMA, "n")
    assert len(sent) == 1


def test_truncated_reply_is_logged_and_retried(tmp_path, replies):
    q, sent = replies
    q += [ok(text="", finish="length"), ok()]
    r = make(tmp_path).complete_json("S", "U", SCHEMA, "n")
    assert r.attempts == 2 and [x["finish"] for x in ledger(tmp_path)] == ["length", "stop"]


def test_other_upstream_provider_is_refused(tmp_path, replies):
    q, _ = replies
    q.append(ok(provider="Azure"))
    with pytest.raises(RouteMismatch):
        make(tmp_path).complete_json("S", "U", SCHEMA, "n")
    assert ledger(tmp_path)[0]["provider_served"] == "Azure"     # billed, so it is in the ledger
    assert not list((tmp_path / "cache").glob("*.json"))


def test_budget_counts_the_billed_cost(tmp_path, replies):
    q, _ = replies
    q += [ok(cost=0.6), ok(text='{"x": 2}', cost=0.6)]
    m = make(tmp_path, budget=1.0)
    m.complete_json("S", "U1", SCHEMA, "n")
    m.complete_json("S", "U2", SCHEMA, "n")
    with pytest.raises(client.BudgetExceeded):
        m.complete_json("S", "U3", SCHEMA, "n")


# ------------------------------------------------------------------ ledger compatibility
def test_old_ledger_gets_the_new_columns(tmp_path, replies):
    old = ["ts", "model", "served", "tag", "attempt", "finish", "input", "cached_input", "output", "reasoning",
           "usd_standard", "latency_s"]
    with open(tmp_path / "costs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=old)
        w.writeheader()
        w.writerow({k: "" for k in old} | {"model": "gpt-6.1-sol", "tag": "create:001", "attempt": 1,
                                           "usd_standard": "0.5"})
        w.writerow({k: "" for k in old} | {"model": "gemini-3.1-pro", "tag": "batch:create:001", "attempt": 1,
                                           "usd_standard": "0.5"})
    q, _ = replies
    q.append(ok(cost=0.01))
    make(tmp_path).complete_json("S", "U", SCHEMA, "n")
    rows = ledger(tmp_path)
    assert list(rows[0]) == client.LEDGER_FIELDS and len(rows) == 3
    assert rows[0]["usd_billed"] == "" and rows[2]["route"] == "openrouter"
    assert ledger_total(tmp_path / "costs.csv") == pytest.approx(0.5 + 0.25 + 0.01)
