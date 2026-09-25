"""Model registry (``models.yaml``), repository paths and prompt templates.

The code holds no model-specific settings: adding a model means adding a YAML entry (plan §5.2).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parents[1]          # scripts/embedding
REPO = HERE.parents[1]
EMB_DIR = REPO / "embeddings"
DEFAULT_CONFIG = HERE / "models.yaml"
DEFAULT_CORPUS = REPO / "segmented" / "chunks_all.csv.gz"
DEFAULT_QUERIES = REPO.parent / "br-taxqa-document-fetcher" / "questions_QA_2024_v1.1.json"
PARITY_SAMPLE = HERE / "parity_sample.json"


class ConfigError(Exception):
    """A configuration problem the user has to fix (message says how)."""


@dataclass
class ModelConfig:
    slug: str
    provider: str
    model_id: str
    dim: int
    tokenizer: str
    query_template: str
    document_template: str
    instructions: dict[str, str]
    instruction_name: str
    max_input_tokens: int
    normalize: bool = True
    revision: str | None = None
    endpoint_url_env: str | None = None
    endpoint_name: str | None = None
    endpoint_namespace: str | None = None
    expected_pooling: str | None = None
    request: dict[str, Any] = field(default_factory=dict)
    price: dict[str, Any] = field(default_factory=dict)
    parity: dict[str, Any] = field(default_factory=dict)
    reference: dict[str, Any] = field(default_factory=dict)
    out_root: Path = EMB_DIR

    # ----------------------------------------------------------------------------------------
    @property
    def out_dir(self) -> Path:
        return self.out_root / self.slug

    def instruction(self, name: str | None = None) -> str:
        name = name or self.instruction_name
        if name not in self.instructions:
            raise ConfigError(f"unknown instruction {name!r}; available: {sorted(self.instructions)}")
        return self.instructions[name]

    def render_query(self, text: str, instruction_name: str | None = None) -> str:
        """Exact string sent for a query. ``{instruction}`` is filled first, so a ``{text}`` inside
        the instruction is not expanded, and braces inside the question are left alone."""
        tpl = self.query_template
        if "{instruction}" in tpl:
            tpl = tpl.replace("{instruction}", self.instruction(instruction_name))
        return tpl.replace("{text}", text)

    def render_document(self, text: str) -> str:
        return self.document_template.replace("{text}", text)

    def request_opt(self, key: str, default: Any) -> Any:
        return self.request.get(key, default)

    def endpoint_url(self) -> str | None:
        """Endpoint URL from the environment variable named in the config (None if unset)."""
        return os.environ.get(self.endpoint_url_env) if self.endpoint_url_env else None


def load_config(path: Path | str | None = None, out_root: Path | None = None) -> dict[str, ModelConfig]:
    path = Path(path or DEFAULT_CONFIG)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    models: dict[str, ModelConfig] = {}
    for slug, entry in (data.get("models") or {}).items():
        merged = {k: v for k, v in defaults.items() if k in ModelConfig.__dataclass_fields__}
        merged.update(entry)
        # nested dicts are merged one level deep (e.g. parity thresholds)
        for key in ("request", "parity", "reference"):
            if isinstance(defaults.get(key), dict) or isinstance(entry.get(key), dict):
                merged[key] = {**defaults.get(key, {}), **entry.get(key, {})}
        missing = [k for k in ("provider", "model_id", "dim", "tokenizer", "query_template",
                               "document_template") if k not in merged]
        if missing:
            raise ConfigError(f"{path.name}: model {slug!r} lacks {missing}")
        unknown = set(merged) - set(ModelConfig.__dataclass_fields__)
        if unknown:
            raise ConfigError(f"{path.name}: model {slug!r} has unknown keys {sorted(unknown)}")
        models[slug] = ModelConfig(slug=slug, out_root=out_root or EMB_DIR, **merged)
    return models


def get_model(slug: str, path: Path | str | None = None, out_root: Path | None = None) -> ModelConfig:
    models = load_config(path, out_root)
    if slug not in models:
        raise ConfigError(f"model {slug!r} is not in {Path(path or DEFAULT_CONFIG).name}; "
                          f"configured: {', '.join(sorted(models))}")
    return models[slug]
