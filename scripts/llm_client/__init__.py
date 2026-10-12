"""Minimal LLM client shared by the nugget pipeline and (later) RAG Phase 3.

``complete_json`` sends one system + user prompt to one of three providers and returns parsed
JSON, normalized token usage and the cost. Every raw response is cached on disk, keyed by the
request, so a rerun reads the cache instead of calling the API (reasoning models are not
deterministic; the cache is what makes reruns exact).
"""
from .client import LLM, BudgetExceeded, LLMError, Result, Usage, load_registry  # noqa: F401
