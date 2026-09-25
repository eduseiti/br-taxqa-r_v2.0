"""Shared fixtures: a tiny corpus, queries and a models.yaml with the ``fake`` provider, all under
tmp_path. No network, no GPU."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from embedding.corpus import text_hash  # noqa: E402

TEXTS = ["Art. 1º Primeiro.", "Art. 2º Segundo, com acentuação.", "Art. 1º Primeiro.",   # duplicate
         "§ 1º Parágrafo {com chaves}.", "Inciso I - texto longo " + "x" * 200, "Art. 3º Terceiro."]

MODELS_YAML = """
defaults:
  instruction_name: irpf
  instructions:
    irpf: "Find IRPF provisions"
    other: "Other task"
  max_input_tokens: 100
  parity: {median_cos: 0.999, min_cos: 0.995, top1_all: true}
models:
  fake-8:
    provider: fake
    model_id: fake/model
    dim: 8
    tokenizer: chars:4
    query_template: "Instruct: {instruction}\\nQuery: {text}"
    document_template: "{text}"
    request: {max_inputs: 2, max_request_tokens: 1000, concurrency: 2}
    price: {usd_per_hour: 0.80, checked: "2026-09-25"}
"""


@pytest.fixture
def corpus_path(tmp_path) -> Path:
    df = pd.DataFrame({"chunk_id": [f"doc#{i}" for i in range(len(TEXTS))], "Texto": TEXTS,
                       "Tipo": ["ART", "ART", "ART", "PAR", "INC", "ART"]})
    df["texto_sha256"] = df["Texto"].map(text_hash)
    df["n_tokens"] = df["Texto"].str.len()
    p = tmp_path / "chunks.csv.gz"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def queries_path(tmp_path) -> Path:
    q = [{"question_number": f"{i:03d}", "question_text": f"Pergunta {i} sobre {{IRPF}}?"} for i in range(1, 5)]
    p = tmp_path / "questions.json"
    p.write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def config_path(tmp_path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(MODELS_YAML, encoding="utf-8")
    return p


@pytest.fixture
def cli(tmp_path, config_path):
    """Runs embed.main with the test registry and outputs under tmp_path/embeddings."""
    import embed

    def run(*argv: str) -> int:
        return embed.main(["--config", str(config_path), "--out-root", str(tmp_path / "embeddings"), *argv])
    return run
