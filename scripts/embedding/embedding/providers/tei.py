"""Text Embeddings Inference client (HF Inference Endpoint, protected by the HF token).

- ``POST /embed`` with ``normalize: true, truncate: false``: the server rejects oversize inputs
  instead of cutting them (plan §1.4 rule 2);
- ``openai_compat`` sends to ``/v1/embeddings`` instead (vLLM fallback, plan §3.8);
- retries 429 / 5xx / connection errors (including the 503 of a scaled-to-zero endpoint waking
  up) with exponential backoff and jitter, up to ``max_wait`` seconds per request; any other
  4xx is fatal (``ProviderError``).
"""

from __future__ import annotations

import logging
import random
import threading
import time

import numpy as np
import requests

from .base import ProviderError

log = logging.getLogger("embedding")

RETRY_STATUS = {429, 500, 502, 503, 504}
HINTS = {
    401: "check HF_TOKEN and its 'Make calls to Inference Endpoints' permission",
    403: "check HF_TOKEN and its 'Make calls to Inference Endpoints' permission",
    413: "request too large: lower request.max_request_tokens / max_inputs in models.yaml",
    422: "input rejected (too long?): the length guard should have caught it; check the chunk",
    424: "model error on the server (often CUDA OOM): lower MAX_BATCH_TOKENS or the request size",
}


class TEIProvider:
    name = "tei"

    def __init__(self, url: str, token: str, openai_compat: bool = False, model_id: str = "",
                 timeout: float = 300, max_wait: float = 900):
        self.url = url.rstrip("/")
        self.openai_compat = openai_compat
        self.model_id = model_id
        self.timeout = timeout
        self.max_wait = max_wait
        self.stats = {"requests": 0, "retries": 0, "errors": 0}
        self._lock = threading.Lock()
        self._local = threading.local()
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ----------------------------------------------------------------------------------------
    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = self._local.session = requests.Session()
            s.headers.update(self._headers)
        return s

    def _count(self, key: str) -> None:
        with self._lock:
            self.stats[key] += 1

    def _request(self, method: str, route: str, payload=None):
        start, attempt = time.monotonic(), 0
        while True:
            self._count("requests")
            try:
                r = self._session().request(method, self.url + route, json=payload, timeout=self.timeout)
                status, body = r.status_code, r.text
            except requests.RequestException as e:
                status, body = None, f"{type(e).__name__}: {e}"
            if status is not None and status < 400:
                return r.json()
            waited = time.monotonic() - start
            if status is not None and status not in RETRY_STATUS:
                self._count("errors")
                hint = HINTS.get(status, "")
                raise ProviderError(f"{method} {route} -> {status}: {body[:500]}" + (f" [{hint}]" if hint else ""))
            if waited >= self.max_wait:
                self._count("errors")
                raise ProviderError(f"{method} {route}: gave up after {waited:.0f}s; last: {status} {body[:300]}"
                                    " (endpoint paused or failing? `embed.py endpoint --model … status`)")
            attempt += 1
            self._count("retries")
            delay = min(60.0, 2.0 * 2 ** min(attempt, 6)) * random.uniform(0.5, 1.0)
            delay = min(delay, max(1.0, self.max_wait - waited))
            if status == 503 and attempt == 1:
                log.info("endpoint answered 503 (starting from zero?); retrying for up to %.0f min",
                         self.max_wait / 60)
            else:
                log.debug("retry %d after %s in %.1fs", attempt, status or body, delay)
            time.sleep(delay)

    # ----------------------------------------------------------------------------------------
    def info(self) -> dict:
        if self.openai_compat:
            return {"engine": "openai_compat", "url": self.url}
        return self._request("GET", "/info")

    def tokenize(self, texts: list[str]) -> list[int]:
        """Token counts as the server sees them (TEI ``/tokenize``, special tokens added)."""
        out = self._request("POST", "/tokenize", {"inputs": texts, "add_special_tokens": True})
        return [len(x) for x in out]

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.openai_compat:
            out = self._request("POST", "/v1/embeddings", {"input": texts, "model": self.model_id,
                                                           "encoding_format": "float"})
            vecs = [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]
        else:
            vecs = self._request("POST", "/embed", {"inputs": texts, "normalize": True, "truncate": False})
        arr = np.asarray(vecs, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts):
            raise ProviderError(f"unexpected response shape {arr.shape} for {len(texts)} inputs")
        return arr
