"""Provider interface."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class ProviderError(Exception):
    """A request failed in a way retrying will not fix (bad input, auth, server bug)."""


class Provider(Protocol):
    name: str
    stats: dict            # requests, retries, errors: goes into the run record

    def info(self) -> dict: ...                          # server/model description for the manifest

    def embed(self, texts: list[str]) -> np.ndarray: ...  # float32 [len(texts), dim]
