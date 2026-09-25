"""Deterministic fake provider: unit vectors seeded by the text hash (tests and dry runs)."""

from __future__ import annotations

import hashlib
import threading

import numpy as np


class FakeProvider:
    name = "fake"

    def __init__(self, dim: int, fail_after: int | None = None):
        self.dim = dim
        self.fail_after = fail_after          # raise on the N-th call (crash simulation in tests)
        self.stats = {"requests": 0, "retries": 0, "errors": 0}
        self._lock = threading.Lock()

    def info(self) -> dict:
        return {"model_id": "fake", "model_sha": None, "model_dtype": "float32", "version": "0",
                "max_input_length": 10**9, "auto_truncate": False,
                "model_type": {"embedding": {"pooling": "fake"}}}

    def embed(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            self.stats["requests"] += 1
            if self.fail_after is not None and self.stats["requests"] > self.fail_after:
                raise RuntimeError("simulated crash")
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = int.from_bytes(hashlib.sha256(t.encode()).digest()[:8], "little")
            v = np.random.default_rng(seed).standard_normal(self.dim)
            out[i] = v / np.linalg.norm(v)
        return out
