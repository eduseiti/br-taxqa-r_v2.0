"""Embedding back-ends behind one interface (plan §5.3).

Implemented: ``tei`` (HF Inference Endpoint running Text Embeddings Inference, or any server with
the OpenAI ``/v1/embeddings`` route via ``openai_compat``) and ``fake`` (tests, dry runs).
``openai`` and ``gemini`` are planned but not implemented yet.
"""

from __future__ import annotations

import os

from ..config import ConfigError, ModelConfig
from .base import Provider, ProviderError


def get_provider(cfg: ModelConfig, url: str | None = None) -> Provider:
    if cfg.provider == "fake":
        from .fake import FakeProvider
        return FakeProvider(cfg.dim)
    if cfg.provider == "tei":
        from .tei import TEIProvider
        url = url or cfg.endpoint_url()
        if not url:
            raise ConfigError(f"no endpoint URL for {cfg.slug}: set {cfg.endpoint_url_env} in .env "
                              f"(see README, 'HF endpoint setup')")
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ConfigError("HF_TOKEN is not set (.env or `hf auth login`)")
        return TEIProvider(url, token, openai_compat=cfg.request_opt("openai_compat", False),
                           model_id=cfg.model_id, timeout=cfg.request_opt("timeout_s", 300),
                           max_wait=cfg.request_opt("max_retry_wait_s", 900))
    raise ConfigError(f"provider {cfg.provider!r} is not implemented (available: tei, fake)")


__all__ = ["Provider", "ProviderError", "get_provider"]
