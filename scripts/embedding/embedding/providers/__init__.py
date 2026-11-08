"""Embedding back-ends behind one interface (plan §5.3).

Implemented: ``tei`` (HF Inference Endpoint running Text Embeddings Inference, or any server with
the OpenAI ``/v1/embeddings`` route via ``openai_compat``), ``openrouter`` (API models such as
gemini-embedding-2, token-priced) and ``fake`` (tests, dry runs). Direct ``openai`` and ``gemini``
clients are not implemented: their models are reached through ``openrouter``.
"""

from __future__ import annotations

import os

from ..config import ConfigError, ModelConfig
from .base import Provider, ProviderError

TOKEN_PRICED = {"openrouter"}          # billed per token: cost ledger from the replies, --budget required


def get_provider(cfg: ModelConfig, url: str | None = None, budget_usd: float | None = None) -> Provider:
    if cfg.provider == "openrouter":
        from .openrouter import OpenRouterProvider
        env = cfg.api_key_env or "OPENROUTER_API_KEY"
        token = os.environ.get(env)
        if not token:
            raise ConfigError(f"{env} is not set (.env)")
        return OpenRouterProvider(token, cfg.model_id, routing=cfg.routing, served_provider=cfg.served_provider,
                                  max_input_tokens=cfg.max_input_tokens, budget_usd=budget_usd,
                                  timeout=cfg.request_opt("timeout_s", 300),
                                  max_wait=cfg.request_opt("max_retry_wait_s", 900))
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
    raise ConfigError(f"provider {cfg.provider!r} is not implemented (available: tei, openrouter, fake)")


__all__ = ["Provider", "ProviderError", "TOKEN_PRICED", "get_provider"]
