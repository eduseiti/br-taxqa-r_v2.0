"""IR metrics over gold-item positions, and paired statistics (plan §4.4).

Every per-question metric takes the positions (1-based) at which the question's gold items are
first hit, with ``inf`` for items never hit, and the number of gold items ``n_gold``. Relevance is
binary.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

INF = math.inf


def recall_at(positions: Sequence[float], k: float, n_gold: int) -> float:
    """Fraction of the gold items hit within the first ``k`` positions."""
    return sum(p <= k for p in positions) / n_gold if n_gold else math.nan


def hit_at(positions: Sequence[float], k: float) -> float:
    """1 when at least one gold item is hit within ``k``."""
    return float(any(p <= k for p in positions))


def full_recall_at(positions: Sequence[float], k: float, n_gold: int) -> float:
    """1 when every gold item is hit within ``k``."""
    return float(n_gold > 0 and sum(p <= k for p in positions) == n_gold)


def reciprocal_rank(positions: Sequence[float]) -> float:
    best = min(positions, default=INF)
    return 0.0 if best == INF else 1.0 / best


def ndcg_at(positions: Sequence[float], k: int, n_gold: int) -> float:
    """Binary-gain nDCG@k; the ideal ranking puts all ``n_gold`` items first."""
    if not n_gold:
        return math.nan
    dcg = sum(1.0 / math.log2(p + 1) for p in positions if p <= k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(n_gold, k) + 1))
    return dcg / idcg


# ------------------------------------------------------------------------------------------------
# Paired comparison
# ------------------------------------------------------------------------------------------------

#
# Both functions take per-question differences ``diff`` of shape [n] or [n × m] (m metrics over the
# same questions) and resample questions once for all columns: one matrix product per test.

def paired_bootstrap_ci(diff: np.ndarray, n_resamples: int = 10_000, seed: int = 13,
                        alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Percentile CI of the mean per-question difference (questions resampled with replacement)."""
    d = np.asarray(diff, dtype=np.float64)
    d2 = d.reshape(len(d), -1)
    n = len(d2)
    if n == 0:
        nan = np.full(d2.shape[1], np.nan)
        return (nan, nan) if d.ndim == 2 else (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, np.full(n, 1.0 / n), size=n_resamples).astype(np.float64)
    means = counts @ d2 / n
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2], axis=0)
    return (lo, hi) if d.ndim == 2 else (float(lo[0]), float(hi[0]))


def paired_permutation_p(diff: np.ndarray, n_resamples: int = 10_000, seed: int = 13) -> np.ndarray | float:
    """Two-sided sign-flip permutation test of mean difference = 0 (add-one smoothed p-value)."""
    d = np.asarray(diff, dtype=np.float64)
    d2 = d.reshape(len(d), -1)
    n = len(d2)
    if n == 0:
        return np.full(d2.shape[1], np.nan) if d.ndim == 2 else math.nan
    rng = np.random.default_rng(seed)
    signs = rng.integers(0, 2, size=(n_resamples, n)).astype(np.float64) * 2 - 1
    observed = np.abs(d2.mean(axis=0))
    null = np.abs(signs @ d2 / n)
    p = (1 + (null >= observed - 1e-12).sum(axis=0)) / (n_resamples + 1)
    return p if d.ndim == 2 else float(p[0])
