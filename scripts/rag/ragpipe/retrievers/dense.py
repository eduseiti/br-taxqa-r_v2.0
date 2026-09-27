"""Exact dense retrieval over stored, L2-normalized vectors (plan §3.2).

Brute force: Q·Vᵀ over all corpus rows, in query blocks to bound memory. No ANN index, so there is
no approximation error. Scores are computed once per block and filtered per strategy.
"""

from __future__ import annotations

import numpy as np

from .base import BaseRetriever, Ranking, top_n_sorted


class DenseRetriever(BaseRetriever):
    name = "dense"

    def __init__(self, corpus_vectors: np.ndarray, text_ids: np.ndarray, query_vectors: np.ndarray,
                 query_ids: list[str], block_size: int = 128):
        # Materialize once: every block reads all rows anyway (≈0.9 GB for jua-4b-mixed).
        self.V = np.ascontiguousarray(corpus_vectors, dtype=np.float32)
        self.Q = np.asarray(query_vectors, dtype=np.float32)
        self.text_ids = np.asarray(text_ids)
        self.qrow = {q: i for i, q in enumerate(query_ids)}
        self.block_size = block_size
        # Rank of each text_id in sorted order: an integer tie-break key equal to sorting by text_id.
        self.tie_key = np.empty(len(self.text_ids), dtype=np.int64)
        self.tie_key[np.argsort(self.text_ids, kind="stable")] = np.arange(len(self.text_ids))

    def info(self) -> dict:
        return {"name": self.name, "similarity": "cosine (dot product of L2-normalized float32 vectors)",
                "search": "exact brute force", "tie_break": "text_id ascending", "block_size": self.block_size}

    def scores(self, query_ids: list[str]) -> np.ndarray:
        """[len(query_ids) × n_texts] similarity matrix."""
        idx = [self.qrow[q] for q in query_ids]
        return self.Q[idx] @ self.V.T

    def search(self, query_ids: list[str], candidate_rows: np.ndarray, top_n: int) -> list[Ranking]:
        return self.search_many(query_ids, {"_": candidate_rows}, top_n)["_"]

    def search_many(self, query_ids: list[str], candidates: dict[str, np.ndarray],
                    top_n: int) -> dict[str, list[Ranking]]:
        out: dict[str, list[Ranking]] = {name: [] for name in candidates}
        for b in range(0, len(query_ids), self.block_size):
            block = self.scores(query_ids[b:b + self.block_size])
            for name, rows in candidates.items():
                sub = block[:, rows]
                keys = self.tie_key[rows]
                out[name].extend(top_n_sorted(sub[i], rows, keys, top_n) for i in range(sub.shape[0]))
        return out
