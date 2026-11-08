"""OpenRouter embeddings client (``POST /api/v1/embeddings``, OpenAI-compatible).

Used for API embedding models such as ``google/gemini-embedding-2`` (plan
docs/20261108_153258_gemini_embedding_2_comparison_plan.md §3):

- the upstream provider is pinned through the request's ``provider`` block (``routing`` in models.yaml:
  ``only``, ``allow_fallbacks: false``, ``data_collection: deny``), and every reply's ``provider`` is
  checked against ``served_provider``;
- ``usage.prompt_tokens`` and ``usage.cost`` (USD billed) are added up in ``stats`` for the cost ledger;
- Gemini **truncates over-long inputs silently** (probe of 2026-11-08: a 17,386-token input was accepted
  and billed). The client-side length guard is therefore the only protection; on top of it, a request
  holding a single text is checked against ``max_input_tokens`` with the reported token count;
- an optional ``budget_usd`` stops the run (``BudgetExceeded``) once the billed cost of this process
  reaches it;
- retries 408 / 429 / 5xx / connection errors with exponential backoff and jitter, up to ``max_wait``
  seconds per request; any other 4xx is fatal (``ProviderError``).
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import Counter

import numpy as np
import requests

from .base import ProviderError

log = logging.getLogger("embedding")

API_URL = "https://openrouter.ai/api/v1"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
HINTS = {
    401: "check OPENROUTER_API_KEY",
    402: "OpenRouter credit or key limit exhausted: check GET /api/v1/key",
    403: "key limit reached or provider blocked: check the key's limit and the routing block",
    404: "no endpoint matches the model and the routing constraints (provider.only?)",
}


class BudgetExceeded(ProviderError):
    """The billed cost of this process reached ``budget_usd``."""


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, token: str, model_id: str, routing: dict | None = None, served_provider: str | None = None,
                 max_input_tokens: int | None = None, budget_usd: float | None = None, base_url: str = API_URL,
                 timeout: float = 300, max_wait: float = 900, session_factory=None):
        self.url = base_url.rstrip("/") + "/embeddings"
        self.model_id = model_id
        self.routing = dict(routing or {})
        self.served_provider = served_provider
        self.max_input_tokens = max_input_tokens
        self.budget_usd = budget_usd
        self.timeout = timeout
        self.max_wait = max_wait
        self.stats = {"requests": 0, "retries": 0, "errors": 0, "prompt_tokens": 0, "cost_usd": 0.0}
        self.served: Counter = Counter()          # upstream provider name -> replies
        self._lock = threading.Lock()
        self._local = threading.local()
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._session_factory = session_factory

    # ----------------------------------------------------------------------------------------
    def _session(self):
        s = getattr(self._local, "session", None)
        if s is None:
            s = self._local.session = (self._session_factory or requests.Session)()
            s.headers.update(self._headers)
        return s

    def _count(self, key: str, n=1) -> None:
        with self._lock:
            self.stats[key] += n

    def info(self) -> dict:
        """Stable description (no timestamps): it is part of the server fingerprint of the stores."""
        return {"model_id": self.model_id, "model_sha": None, "model_dtype": None, "version": None,
                "engine": "openrouter", "url": self.url, "routing": self.routing,
                "served_provider": self.served_provider, "max_input_length": self.max_input_tokens,
                "auto_truncate": None}

    def _post(self, payload: dict) -> dict:
        start, attempt = time.monotonic(), 0
        while True:
            self._count("requests")
            try:
                r = self._session().post(self.url, json=payload, timeout=self.timeout)
                status, body = r.status_code, r.text
                data = r.json() if status < 400 else None
            except requests.RequestException as e:
                status, body, data = None, f"{type(e).__name__}: {e}", None
            except ValueError:                       # 2xx with a body that is not JSON
                status, body, data = 502, r.text, None
            if data is not None and "error" in data and "data" not in data:
                # OpenRouter can answer 200 with an error object (upstream failure)
                code = str(data["error"].get("code", ""))
                status = int(code) if code.isdigit() else 502
                body, data = str(data["error"])[:500], None
            if data is not None:
                return data
            waited = time.monotonic() - start
            if status is not None and status not in RETRY_STATUS:
                self._count("errors")
                hint = HINTS.get(status, "")
                raise ProviderError(f"POST {self.url} -> {status}: {body[:500]}" + (f" [{hint}]" if hint else ""))
            if waited >= self.max_wait:
                self._count("errors")
                raise ProviderError(f"POST {self.url}: gave up after {waited:.0f}s; last: {status} {body[:300]}")
            attempt += 1
            self._count("retries")
            delay = min(60.0, 2.0 * 2 ** min(attempt, 6)) * random.uniform(0.5, 1.0)
            delay = min(delay, max(1.0, self.max_wait - waited))
            log.debug("retry %d after %s in %.1fs", attempt, status or body, delay)
            time.sleep(delay)

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.budget_usd is not None and self.stats["cost_usd"] >= self.budget_usd:
            raise BudgetExceeded(f"budget of ${self.budget_usd:.4f} for this run reached "
                                 f"(billed ${self.stats['cost_usd']:.4f})")
        payload = {"model": self.model_id, "input": texts, "encoding_format": "float"}
        if self.routing:
            payload["provider"] = self.routing
        out = self._post(payload)
        usage = out.get("usage") or {}
        ptok = int(usage.get("prompt_tokens") or 0)
        cost = float(usage.get("cost") or 0.0)
        with self._lock:
            self.stats["prompt_tokens"] += ptok
            self.stats["cost_usd"] += cost
            self.served[out.get("provider") or "?"] += 1
        served = out.get("provider")
        if self.served_provider and served != self.served_provider:
            self._count("errors")
            raise ProviderError(f"reply served by {served!r}, expected {self.served_provider!r} (routing broken?)")
        if not usage:
            log.warning("reply without usage: cost not reported for %d inputs", len(texts))
        if len(texts) == 1 and self.max_input_tokens and ptok > self.max_input_tokens:
            self._count("errors")
            raise ProviderError(f"input of {ptok} tokens (provider count) is over {self.max_input_tokens}: it was "
                                "truncated silently; the length guard missed it")
        items = sorted(out.get("data") or [], key=lambda d: d["index"])
        arr = np.asarray([d["embedding"] for d in items], dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts):
            raise ProviderError(f"unexpected response shape {arr.shape} for {len(texts)} inputs")
        return arr
