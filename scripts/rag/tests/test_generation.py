"""Stage G on the fixture repository with the ``fake`` provider: prompts, grounding checks, outputs,
cache reruns, dry run, budget and configuration guards, tool-use refusal. No network."""

from __future__ import annotations

import csv
import json
import re

import pytest
import yaml

import rag
from llm_client import LLM, ToolUseDetected, client
from ragpipe import generation as G
from ragpipe.contexts import ContextConfig, run_contexts
from ragpipe.data import InputError
from ragpipe.evaluation import EvalConfig, run_evaluation
from ragpipe.retrieval import RetrievalConfig, run_retrieval
from ragpipe.runs import RunError, read_json

SETS = ("S1@budget=500", "closed_book", "oracle@budget=16000")
IDS = ("S1_budget500", "closed_book", "oracle_budget16000")


def fake_reply(self, system, user, schema, schema_name):
    """Quote the first four words of the first block (or nothing in closed book); one value not in the context."""
    m = re.search(r"\[Documento 1\][^\n]*\n(.+)", user)
    funds = [{"documento": 1, "trecho": " ".join(m.group(1).split()[:4])}] if m else []
    data = {"abstencao": False, "afirmacoes": [
        {"texto": "Primeira afirmação, conforme o art. 1º da Lei nº 1, de 2000.", "fundamentos": funds},
        {"texto": "O limite é de R$ 999,99.", "fundamentos": [{"documento": 7, "trecho": "nada disso"}]}]}
    text = json.dumps(data, ensure_ascii=False)
    return {"fake": True}, text, client.Usage(len(user) // 4, 0, len(text) // 4, 0), "fake-1", \
        {"finish": "stop", "truncated": False}


@pytest.fixture
def gen(repo, tmp_path, monkeypatch):
    rdir = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf"), repo)
    run_evaluation(rdir, EvalConfig(budgets=(500, 16000), unit_ks=(1,), raw_ks=(1,), n_resamples=50), repo)
    root = run_contexts(rdir, ContextConfig(sets=SETS, count_tokens=False), repo)
    reg = tmp_path / "llms.yaml"
    reg.write_text(yaml.safe_dump({"fx_brl_per_usd": 5.0, "models": {
        "fake-brl": {"provider": "fake", "model_id": "fake-1", "api_key_env": "NONE", "params": {},
                     "price": {"currency": "BRL", "per_million_input": 5.0, "per_million_output": 20.0}},
        "off": {"provider": "fake", "model_id": "x", "api_key_env": "NONE", "params": {}, "enabled": False,
                "price": {"usd_per_million_input": 1, "usd_per_million_output": 1}}}}))
    monkeypatch.setattr(LLM, "_call_fake", fake_reply)

    def config(**kw):
        base = dict(contexts=root, sets=IDS, llms=("fake-brl",), sample="001,002,003,004", registry=reg,
                    budget_usd=1.0, workers=2)
        return G.GenConfig(**{**base, **kw})
    return repo, root, config


def ledger_rows(paths):
    with open(paths.runs / "costs.csv", newline="") as f:
        return list(csv.DictReader(f))


def test_run_outputs_checks_and_rerun(gen):
    paths, root, config = gen
    out, df = G.run_generation(config(), paths)
    assert len(df) == 3 and set(df["context_id"]) == set(IDS)
    run = out / "answer_v1" / "fake-brl" / "S1_budget500"
    lines = {ln["question_number"]: ln for ln in G.load_answers(run)}
    assert set(lines) == {"001", "002", "003", "004"}
    ln = lines["001"]
    assert ln["run_id"] == "fake/irpf/answer_v1/fake-brl/S1_budget500" and ln["status"] == "ok"
    assert ln["answer"].startswith("Primeira afirmação") and not ln["abstained"]
    assert [f["status"] for c in ln["claims"] for f in c["fundamentos"]] == ["ok", "bad_document"]
    assert ln["checks"]["claims_grounded"] == 1 and ln["checks"]["values_not_in_context"] == ["R$ 999,99"]
    assert ln["cited_chunk_ids"] and ln["usd_list"] > 0
    man = read_json(run / "run.json")
    assert man["llm"]["price"]["fx_brl_per_usd"] == 5.0 and man["llm"]["price"]["usd_per_million_input"] == 1.0
    assert man["prompt"]["name"] == "answer_v1" and man["counts"]["ok"] == 4 and man["complete"]
    # closed book uses its own prompt; the oracle skips questions without gold (empty context)
    closed = G.load_answers(out / "answer_closed_v1" / "fake-brl" / "closed_book")
    assert all(c["fundamentos"] == [] for ln in closed for c in ln["claims"][:1])
    oracle = {ln["question_number"]: ln for ln in G.load_answers(out / "answer_v1" / "fake-brl" / "oracle_budget16000")}
    assert oracle["004"]["status"] == "skipped" and oracle["001"]["status"] == "ok"
    n_calls = len(ledger_rows(paths))
    assert n_calls == 4 + 4 + 3 and ledger_rows(paths)[0]["fx_brl_per_usd"] == "5.0"
    # a rerun reads the cache: same answers, no new ledger row
    before = (run / "answers.jsonl").read_text().replace('"from_cache": false', '"from_cache": true')
    G.run_generation(config(), paths)
    assert len(ledger_rows(paths)) == n_calls
    assert (run / "answers.jsonl").read_text() == before
    assert (out / "summary.csv").exists()


def test_dry_run_budget_and_guards(gen):
    paths, root, config = gen
    _, est = G.run_generation(config(dry_run=True, budget_usd=None), paths)
    assert est["calls"].tolist() == [4, 4, 3] and est["cached"].sum() == 0 and est["est_usd_list"].sum() > 0
    assert not (paths.runs / "costs.csv").exists()
    with pytest.raises(InputError, match="--budget"):
        G.run_generation(config(budget_usd=None), paths)
    with pytest.raises(InputError, match="disabled"):
        G.run_generation(config(llms=("off",), dry_run=True), paths)
    G.run_generation(config(sets=("S1_budget500",)), paths)
    _, est = G.run_generation(config(sets=("S1_budget500",), dry_run=True), paths)
    assert est["cached"].tolist() == [4]
    # the run folder holds another configuration (e.g. an edited prompt file): refused before any call
    run = paths.runs / "answers" / "fake" / "irpf" / "answer_v1" / "fake-brl" / "S1_budget500" / "run.json"
    man = read_json(run)
    man["config_hash"] = "0" * 64
    run.write_text(json.dumps(man))
    n = len(ledger_rows(paths))
    with pytest.raises(RunError, match="another configuration"):
        G.run_generation(config(sets=("S1_budget500",)), paths)
    assert len(ledger_rows(paths)) == n


def test_budget_stops_and_resumes(gen):
    paths, root, config = gen
    (paths.runs).mkdir(exist_ok=True)
    with open(paths.runs / "costs.csv", "w", newline="") as f:     # an earlier spend at the cap
        w = csv.DictWriter(f, fieldnames=client.LEDGER_FIELDS)
        w.writeheader()
        w.writerow({k: "" for k in client.LEDGER_FIELDS} | {"tag": "x", "usd_standard": "1.0"})
    with pytest.raises(RunError, match="BudgetExceeded"):
        G.run_generation(config(sets=("S1_budget500",)), paths)
    _, df = G.run_generation(config(sets=("S1_budget500",), budget_usd=2.0), paths)
    assert df["ok"].tolist() == [4]


def test_tool_use_is_refused(gen, monkeypatch):
    paths, root, config = gen

    def with_search(self, system, user, schema, schema_name):
        raw, text, u, served, meta = fake_reply(self, system, user, schema, schema_name)
        return {"choices": [{"message": {"content": text}}], "web_search_sources": [{"url": "https://x"}]}, \
            text, u, served, meta
    m = LLM("t", {"provider": "fake", "model_id": "m", "api_key_env": "N", "params": {},
                  "price": {"usd_per_million_input": 1, "usd_per_million_output": 1}}, paths.runs / "c")
    m.provider = "openai_compat"
    m._call_openai_compat = lambda *a: with_search(m, *a)
    with pytest.raises(ToolUseDetected, match="web_search_sources"):
        m.complete_json("s", "u", G.SCHEMA, "r")
    with pytest.raises(ToolUseDetected):
        LLM("t", {"provider": "fake", "model_id": "m", "api_key_env": "N", "params": {"tools": []},
                  "price": {}}, paths.runs / "c")
    with pytest.raises(ToolUseDetected):
        LLM("t", {"provider": "fake", "model_id": "m:online", "api_key_env": "N", "params": {}, "price": {}},
            paths.runs / "c")


def test_quote_status_and_values():
    ctx = ("[Documento 1] LEI Nº 1 — Art. 1º\nArt. 1º São dedutíveis as despesas “médicas” pagas no ano, "
           "até o limite de R$ 3.561,50 por dependente.\n\n[Documento 2] LEI Nº 2 — Art. 5º\nArt. 5º Outro texto.")
    b = G.split_blocks(ctx)
    assert set(b) == {1, 2} and b[2].startswith("[Documento 2]")
    assert G.quote_status('São dedutíveis as despesas "médicas"', b[1]) == "ok"
    assert G.quote_status("são  DEDUTÍVEIS as despesas ... por dependente.", b[1]) == "ok"
    assert G.quote_status("por dependente ... São dedutíveis", b[1]) == "not_found"
    assert G.quote_status("despesas", b[1]) == "too_short"
    assert G.quote_status("São dedutíveis as despesas", None) == "bad_document"
    line = {"context": ctx, "items": [{"n": 1, "chunk_id": "l1#1"}, {"n": 2, "chunk_id": "l2#5"}]}
    claims, checks, cited = G.check_answer({"abstencao": True, "afirmacoes": [
        {"texto": "Limite de R$ 3.561,50 e de 20%, até 30 de abril.", "fundamentos": [
            {"documento": 1, "trecho": "até o limite de R$ 3.561,50"}]}]}, line, "Qual o prazo de 30/04/2024?")
    assert cited == ["l1#1"] and checks["claims_grounded"] == 1
    assert checks["values_not_in_context"] == ["20%"]          # the date is in the question (day and month)
    assert checks["abstention_inconsistent"]
    with pytest.raises(ValueError):
        G.validate_shape({"abstencao": "não", "afirmacoes": []})


def test_prompts_and_registry():
    p = G.Prompt.load("answer_v1")
    assert "{context}" in p.user and "{question}" in p.user and "2024" in p.system
    assert p.render("Q {x}?", "C") .endswith("Pergunta: Q {x}?")
    c = G.Prompt.load("answer_closed_v1")
    assert "{context}" not in c.user
    models, fx = G.load_registry()
    for name in ("sabia-4", "sabiazinho-4", "gpt-5.6-terra", "gpt-5.6-luna"):
        cfg = G.resolve_llm(name, models, fx)
        assert cfg["price"]["usd_per_million_input"] > 0
        assert not any(k in cfg["params"] for k in client.FORBIDDEN_PARAMS)
    assert G.resolve_llm("gpt-5.6-terra", models, fx)["params"]["reasoning"] == {"effort": "none"}
    assert G.resolve_llm("sabia-4", models, fx)["route"] == "direct"
    with pytest.raises(InputError):
        G.resolve_llm("deepseek-v4-pro", models, fx)


def test_cli(gen, capsys, monkeypatch):
    paths, root, config = gen
    args = ["generate", "--contexts", str(root), "--sets", "S1_budget500", "--llms", "fake-brl", "--sample",
            "001,002", "--registry", str(config().registry), "--runs-dir", str(paths.runs),
            "--dataset", str(paths.dataset)]
    assert rag.main(args + ["--dry-run"]) == 0
    assert "Nothing was sent" in capsys.readouterr().out
    assert rag.main(args + ["--budget", "1"]) == 0
    run = paths.runs / "answers" / "fake" / "irpf" / "answer_v1" / "fake-brl" / "S1_budget500"
    assert rag.main(["show-answers", "--run", str(run), "--questions", "002"]) == 0
    assert "[Documento 1] ok" in capsys.readouterr().out
