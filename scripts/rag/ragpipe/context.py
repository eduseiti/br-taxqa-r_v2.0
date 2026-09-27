"""Context selection: containment de-duplication and k / token-budget cutoffs (plan §6.1).

Used by the retrieval evaluation for the token-budget view (plan §4.3) and, in Phase 2, by stage C,
so the retrieval numbers describe exactly the contexts the generator will see. Formatting of the
selected chunks (plan §6.2) comes in Phase 2.

A ranked item is a text; ``intervals[i]`` lists the ``(file, Num_Inicio, Num_Final)`` of every chunk
of the strategy that has text ``i`` (representative and aliases).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

import numpy as np

Interval = tuple[int, int, int]      # (file index, Num_Inicio, Num_Final)

DEDUP_MODES = ("none", "containment")
OVERFLOW_MODES = ("skip", "stop")


@dataclass(frozen=True)
class Cutoff:
    """``k=<n>`` (number of texts) or ``budget=<tokens>`` (Qwen3 tokens)."""

    kind: str
    value: int

    @classmethod
    def parse(cls, spec: str) -> "Cutoff":
        m = re.fullmatch(r"\s*(k|budget)\s*=\s*(\d+)\s*", spec)
        if not m:
            raise ValueError(f"bad cutoff {spec!r}: use k=<n> or budget=<tokens>")
        return cls(m.group(1), int(m.group(2)))

    def __str__(self) -> str:
        return f"{self.kind}={self.value}"


def is_contained(item_intervals: Sequence[Interval], selected: dict[int, list[tuple[int, int]]]) -> bool:
    """True when some chunk of the item lies inside a selected chunk of the same file."""
    for f, s, e in item_intervals:
        for s2, e2 in selected.get(f, ()):
            if s2 <= s and e <= e2:
                return True
    return False


def select(ranked: Sequence[int], tokens: np.ndarray, intervals: Sequence[Sequence[Interval]], cutoff: Cutoff,
           dedup: str = "containment", overflow: str = "skip") -> list[int]:
    """Indices (into ``ranked``) of the texts that make up the context, in rank order.

    - ``ranked``: candidate positions, best first; ``tokens`` and ``intervals`` are indexed by them.
    - ``dedup="containment"``: drop a text whose chunk interval is inside the interval of an already
      selected chunk of the same file (a lower-ranked child of a selected parent). The reverse case
      (a parent after its child) is kept, since the parent adds text.
    - ``overflow``: for budgets, ``skip`` a text that does not fit and keep filling, or ``stop``.
    """
    if dedup not in DEDUP_MODES:
        raise ValueError(f"dedup must be one of {DEDUP_MODES}")
    if overflow not in OVERFLOW_MODES:
        raise ValueError(f"overflow must be one of {OVERFLOW_MODES}")
    ranked = np.asarray(ranked, dtype=np.int64)
    toks = tokens[ranked]
    budget = cutoff.value if cutoff.kind == "budget" else None
    k = cutoff.value if cutoff.kind == "k" else None
    # suffix minimum of the token counts: once nothing further can fit, stop scanning
    suffix_min = np.minimum.accumulate(toks[::-1])[::-1] if budget is not None and len(toks) else toks
    use_dedup = dedup == "containment"
    selected: dict[int, list[tuple[int, int]]] = {}
    out: list[int] = []
    used = 0
    for i in range(len(ranked)):
        if k is not None and len(out) >= k:
            break
        if budget is not None:
            remaining = budget - used
            if suffix_min[i] > remaining:
                break
            if toks[i] > remaining:
                if overflow == "stop":
                    break
                continue
        ivs = intervals[ranked[i]]
        if use_dedup and is_contained(ivs, selected):
            continue
        out.append(i)
        used += int(toks[i])
        if use_dedup:
            for f, s, e in ivs:
                selected.setdefault(f, []).append((s, e))
    return out
