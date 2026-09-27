"""The retriever interface (plan §3.2).

A retriever ranks corpus **texts** (rows of the stored vectors) for questions. Strategies differ only
in their candidate set, so :meth:`BaseRetriever.search_many` lets a retriever score once and filter
per strategy; the default just calls :meth:`search` for each candidate set.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

#: One ranked list: (corpus row, score), best first.
Ranking = list[tuple[int, float]]


@runtime_checkable
class Retriever(Protocol):
    name: str

    def info(self) -> dict:
        """Settings and identity of the retriever, recorded in the run manifest."""
        ...

    def search(self, query_ids: list[str], candidate_rows: np.ndarray, top_n: int) -> list[Ranking]:
        """Rank ``candidate_rows`` for each query; ties broken by ``text_id`` (deterministic)."""
        ...


class BaseRetriever:
    name = "base"

    def info(self) -> dict:
        return {"name": self.name}

    def search(self, query_ids: list[str], candidate_rows: np.ndarray, top_n: int) -> list[Ranking]:
        raise NotImplementedError

    def search_many(self, query_ids: list[str], candidates: dict[str, np.ndarray],
                    top_n: int) -> dict[str, list[Ranking]]:
        return {name: self.search(query_ids, rows, top_n) for name, rows in candidates.items()}


def top_n_sorted(scores: np.ndarray, rows: np.ndarray, tie_key: np.ndarray, top_n: int) -> Ranking:
    """Best ``top_n`` of ``scores`` (aligned with ``rows``), sorted by score desc then ``tie_key``.

    Exact: every candidate tied with the n-th score is considered before cutting, so the result does
    not depend on the partition order.
    """
    n = len(scores)
    if n == 0:
        return []
    k = min(top_n, n)
    if k < n:
        kth = np.partition(scores, n - k)[n - k]
        keep = np.flatnonzero(scores >= kth)
    else:
        keep = np.arange(n)
    order = np.lexsort((tie_key[keep], -scores[keep]))[:k]
    sel = keep[order]
    return [(int(r), float(s)) for r, s in zip(rows[sel], scores[sel])]
