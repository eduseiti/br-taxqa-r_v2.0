"""Stage C on the fixture repository: context sets, oracle, wrong-context donors, gold coverage and its
consistency with the evaluation, rendering, determinism."""

from __future__ import annotations

import pytest

import rag
from ragpipe.context import Template, source_label, split_prefix
from ragpipe.contexts import PROMPTS, ContextConfig, SetSpec, load_contexts, run_contexts
from ragpipe.evaluation import EvalConfig, run_evaluation
from ragpipe.retrieval import RetrievalConfig, load_rankings, run_retrieval
from ragpipe.runs import read_json

SETS = ("S1@budget=500", "S2@budget=16000", "S3@k=2", "closed_book", "oracle@budget=16000", "wrong:S2@k=1")


def build(paths, **kw):
    rdir = run_retrieval(RetrievalConfig(embedding="fake", instruction="irpf"), paths)
    run_evaluation(rdir, EvalConfig(budgets=(500, 16000), unit_ks=(1,), raw_ks=(1,), n_resamples=50), paths)
    root = run_contexts(rdir, ContextConfig(sets=SETS, count_tokens=False, **kw), paths)
    return root, {d.name: {ln["question_number"]: ln for ln in load_contexts(d)}
                  for d in root.iterdir() if d.is_dir()}


def test_sets_and_consistency(repo):
    root, ctx = build(repo)
    assert sorted(ctx) == ["S1_budget500", "S2_budget16000", "S3_k2", "closed_book", "oracle_budget16000",
                           "wrong-S2_k1"]
    for cid in ("S1_budget500", "S2_budget16000"):
        check = read_json(root / cid / "manifest.json")["consistency_with_evaluation"]
        assert check["mismatches"] == 0 and check["items"] > 0
    assert read_json(root / "S3_k2" / "manifest.json")["consistency_with_evaluation"] is None
    assert all(len(ln["items"]) == 2 for ln in ctx["S3_k2"].values())
    assert all(ln["n_texts"] == 0 and ln["context"] == "" for ln in ctx["closed_book"].values())
    # budget respected (merged parents may sit before higher-ranked texts, so ranks need not increase)
    for ln in ctx["S1_budget500"].values():
        assert ln["context_tokens_qwen3"] <= 500
    assert (root / "summary.csv").exists()


def test_oracle(repo):
    _, ctx = build(repo)
    o = ctx["oracle_budget16000"]
    ids = {q: {it["chunk_id"] for it in ln["items"]} for q, ln in o.items()}
    assert ids["001"] == {"lei_1_20000101#1"}                                 # art1, the whole article
    assert ids["002"] == {"lei_1_20000101#5", "lei_1_20000101#6"}             # both parts of split art2
    # Q003: decreto art1 (main and annex, annex rule "either"), annex art5, and urn_x (document-only gold)
    assert ids["003"] == {"decreto_9_20000101#1", "decreto_9_20000101.anexo1#1", "decreto_9_20000101.anexo1#2",
                          "urn_x#1", "urn_x#2"}
    assert o["004"]["n_texts"] == 0                                            # no gold
    for q in ("001", "002", "003"):
        g = o[q]["gold"]
        assert len(g["article"]["full"]) == g["article"]["n"] and len(g["provision"]["full"]) == g["provision"]["n"]


def test_wrong_context(repo):
    root, ctx = build(repo)
    w, base = ctx["wrong-S2_k1"], ctx["S2_budget16000"]
    s2 = load_rankings(repo.runs / "retrieval" / "fake" / "irpf", "S2")
    top1 = dict(zip(s2[s2["rank"] == 1]["question_number"], s2[s2["rank"] == 1]["chunk_id"]))
    assert read_json(root / "wrong-S2_k1" / "manifest.json")["donor_context_rule_relaxed"] == 0
    chapter = {"001": "A", "002": "A", "003": "B", "004": "B"}
    for q, ln in w.items():
        d = ln["donor_question"]
        assert d != q and chapter[d] != chapter[q]
        # the donor's own top-1 text, holding none of the question's gold
        assert [it["chunk_id"] for it in ln["items"]] == [top1[d]]
        assert all(not c["full"] and not c["any"] for c in ln["gold"].values())
    assert base["001"]["gold"]["document"]["full"]


def test_rendering(repo):
    _, ctx = build(repo)
    ln = ctx["S2_budget16000"]["001"]
    first = ln["items"][0]
    assert ln["context"].startswith(f"[Documento 1] {first['fonte']}\n")
    assert "<!--" not in ln["context"] and ln["context"].count("[Documento ") == ln["n_texts"]
    t = Template.load(PROMPTS, "context_v1")
    assert t.render([("A", "x {n}"), ("B", "y")]) == "[Documento 1] A\nx {n}\n\n[Documento 2] B\ny"


def test_source_label():
    rfb = "urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:instrucao.normativa:2014-10-29;1500"
    assert source_label("INSTRUÇÃO NORMATIVA Nº 1.500, DE 29 DE OUTUBRO DE 2014", rfb, False, "Art. 3º, § 1º", 1, 1) \
        == "INSTRUÇÃO NORMATIVA Nº 1.500, DE 29 DE OUTUBRO DE 2014 — Receita Federal do Brasil — Art. 3º, § 1º"
    assert source_label("Ato Declaratório PGFN nº 1", "urn:lex:br:procuradoria.geral.fazenda.nacional:x:y", False,
                        "texto", 1, 1) == "Ato Declaratório PGFN nº 1"
    assert source_label("LEI Nº 9.250", "urn:lex:br:federal:lei:1995-12-26;9250", True, "Art. 8º", 2, 3) \
        == "LEI Nº 9.250 — Anexo — Art. 8º (parte 2 de 3)"
    assert source_label("LEI", "", False, "Art. 71., § 1º", 1, 1) == "LEI — Art. 71, § 1º"
    assert source_label("LEI", "", False, "Art. 1º, Parágrafo único., II", 1, 1) == "LEI — Art. 1º, Parágrafo único, II"


def test_context_v2():
    assert split_prefix("[ LEI Nº 1 | Dispõe sobre X. | Anexo 2 – TABELA ] Texto do anexo") == \
        (["LEI Nº 1", "Dispõe sobre X.", "Anexo 2 – TABELA"], "Texto do anexo")
    assert split_prefix("[ ] Art. 1º x") == ([], "Art. 1º x")
    assert split_prefix("sem prefixo") == ([], "sem prefixo")
    t = Template.load(PROMPTS, "context_v2")
    assert t.per_document_ementa and not Template.load(PROMPTS, "context_v1").per_document_ementa
    assert t.render([("LEI Nº 1 — Art. 1º", "Ementa: Dispõe sobre X.\n", "Art. 1º a"), ("LEI Nº 1 — Art. 2º", "", "Art. 2º b")]) \
        == "[Documento 1] LEI Nº 1 — Art. 1º\nEmenta: Dispõe sobre X.\nArt. 1º a\n\n[Documento 2] LEI Nº 1 — Art. 2º\nArt. 2º b"
    assert source_label("LEI Nº 1", "", True, "Tabela 1", 1, 1, "Anexo 2 – TABELA") == "LEI Nº 1 — Anexo 2 – TABELA — Tabela 1"


def test_epigrafe():
    from ragpipe.contexts import epigrafe
    assert epigrafe("[ LEI Nº 9.250 | Dispõe sobre … ] Art. 1º") == "LEI Nº 9.250"
    assert epigrafe("[ Só o título ] texto") == "Só o título"
    assert epigrafe("[ urn:lex:br:x:servico:2026;diat | Documento de Informação (Diat) ] O Diat…") == \
        "Documento de Informação (Diat)"
    assert epigrafe("sem prefixo") is None


def test_spec_parse():
    assert SetSpec.parse("wrong:S2@budget=4000") == SetSpec("wrong", "S2", SetSpec.parse("S2@budget=4000").cutoff)
    assert SetSpec.parse("closed_book").base_id() == "closed_book"
    assert SetSpec.parse("oracle@budget=4000").base_id() == "oracle_budget4000"
    for bad in ("S2", "closed_book@k=1", "wrong:oracle@k=1", "S2@tokens=4"):
        with pytest.raises(ValueError):
            SetSpec.parse(bad)


def test_determinism_and_variants(repo):
    root, _ = build(repo)
    before = (root / "S2_budget16000" / "contexts.jsonl.gz").read_bytes()
    root2, ctx = build(repo, order="document")                                 # another option → another id
    assert (root2 / "S2_budget16000" / "contexts.jsonl.gz").read_bytes() == before
    assert "S2_budget16000_order-document" in ctx


def test_cli(repo, capsys):
    common = ["--chunks", str(repo.chunks), "--dataset", str(repo.dataset), "--embeddings-dir", str(repo.embeddings),
              "--runs-dir", str(repo.runs), "--strategies-file", str(repo.strategies)]
    assert rag.main(["retrieve", "--embedding", "fake", "--exclusions", "none", *common]) == 0
    rdir = repo.runs / "retrieval" / "fake" / "irpf"
    assert rag.main(["context", "--retrieval", str(rdir), "--sets", "S2@budget=500,closed_book", "--no-token-count",
                     *common]) == 0
    assert rag.main(["show-context", "--context", str(repo.runs / "contexts" / "fake" / "irpf" / "S2_budget500"),
                     "--questions", "001"]) == 0
    out = capsys.readouterr().out
    assert "S2_budget500 — question 001" in out and "[Documento 1]" in out
