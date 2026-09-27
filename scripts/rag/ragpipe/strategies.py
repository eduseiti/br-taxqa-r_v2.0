"""Strategy definitions (``strategies.yaml``) and the text ↔ chunk aliasing of a strategy (plan §3.1, §3.3).

Vectors are stored per unique text, and several chunks can share one text (an ``ART`` whose only
content is one inciso has the text of that ``INC``). Inside a strategy each ranked item is therefore
**one text**, represented by its coarsest chunk (``unit_precedence``); the other chunks of the
strategy with that text are its aliases. The relevance matcher uses the union of their provenance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .data import Embedding, InputError
from .runs import rel, sha256_file

log = logging.getLogger("ragpipe")


@dataclass(frozen=True)
class Strategy:
    name: str
    tipos: frozenset[str]
    description: str
    expected_rows: int | None


@dataclass(frozen=True)
class StrategyConfig:
    strategies: dict[str, Strategy]
    grouping_tipos: frozenset[str]
    unit_precedence: tuple[str, ...]
    path: Path
    sha256: str

    def select(self, names: list[str] | None) -> list[Strategy]:
        """Strategies by name (all, in file order, when ``names`` is empty)."""
        if not names:
            return list(self.strategies.values())
        unknown = [n for n in names if n not in self.strategies]
        if unknown:
            raise InputError(f"unknown strategy {unknown}; defined in {rel(self.path)}: "
                             f"{', '.join(self.strategies)}")
        return [self.strategies[n] for n in names]

    def to_dict(self) -> dict:
        return {"path": rel(self.path), "sha256": self.sha256,
                "strategies": {s.name: {"tipos": sorted(s.tipos), "description": s.description}
                               for s in self.strategies.values()},
                "grouping_tipos": sorted(self.grouping_tipos), "unit_precedence": list(self.unit_precedence)}


def load_strategies(path: Path) -> StrategyConfig:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    prec = tuple(cfg["unit_precedence"])
    strategies = {}
    for name, s in cfg["strategies"].items():
        tipos = frozenset(s["tipos"])
        missing = tipos - set(prec)
        if missing:
            raise InputError(f"{rel(path)}: strategy {name} uses Tipo(s) {sorted(missing)} absent from "
                             "unit_precedence")
        strategies[name] = Strategy(name, tipos, s.get("description", ""), s.get("expected_rows"))
    return StrategyConfig(strategies, frozenset(cfg.get("grouping_tipos", [])), prec, Path(path),
                          sha256_file(path))


def attach_text_rows(chunks: pd.DataFrame, emb: Embedding) -> pd.DataFrame:
    """Add ``text_id`` and ``text_row`` (row of the corpus vectors) to the chunk table."""
    tmap = dict(zip(emb.chunk_map["chunk_id"], emb.chunk_map["text_id"]))
    row_of = {t: i for i, t in enumerate(emb.text_ids)}
    out = chunks.copy()
    out["text_id"] = out["chunk_id"].map(tmap)
    if out["text_id"].isna().any():
        raise InputError("chunks without a text_id in chunk_map.csv.gz; run `rag.py check`")
    out["text_row"] = out["text_id"].map(row_of).astype(np.int64)
    return out


@dataclass
class StrategyIndex:
    """The candidate texts of one strategy and the chunks behind each of them.

    ``text_rows[i]`` is a row of the corpus vectors; its chunks are
    ``member_rows[member_ptr[i]:member_ptr[i+1]]`` (chunk-table rows), the first one being the
    representative chunk.
    """

    strategy: Strategy
    text_rows: np.ndarray       # [n] sorted
    member_ptr: np.ndarray      # [n+1]
    member_rows: np.ndarray     # [n_chunks_in_strategy]
    n_chunk_rows: int

    def __len__(self) -> int:
        return len(self.text_rows)

    def position(self, n_texts: int) -> np.ndarray:
        """Array over all corpus rows: position in this index, or -1 when not a candidate."""
        pos = np.full(n_texts, -1, dtype=np.int64)
        pos[self.text_rows] = np.arange(len(self.text_rows))
        return pos

    def members(self, i: int) -> np.ndarray:
        return self.member_rows[self.member_ptr[i]:self.member_ptr[i + 1]]

    def representative(self) -> np.ndarray:
        return self.member_rows[self.member_ptr[:-1]]


def build_index(chunks: pd.DataFrame, strategy: Strategy, precedence: tuple[str, ...]) -> StrategyIndex:
    """Group the strategy's chunks by text; order members coarse-to-fine, then by file order.

    ``chunks`` must carry ``text_row`` (see :func:`attach_text_rows`).
    """
    rank = {t: i for i, t in enumerate(precedence)}
    sub = chunks.loc[chunks["Tipo"].isin(strategy.tipos), ["text_row", "Tipo"]]
    if strategy.expected_rows is not None and len(sub) != strategy.expected_rows:
        log.warning("strategy %s: %d chunk rows, strategies.yaml expects %d (other chunk file?)",
                    strategy.name, len(sub), strategy.expected_rows)
    order = np.lexsort((sub.index.to_numpy(), sub["Tipo"].map(rank).to_numpy(), sub["text_row"].to_numpy()))
    rows = sub.index.to_numpy()[order]
    trows = sub["text_row"].to_numpy()[order]
    starts = np.flatnonzero(np.r_[True, trows[1:] != trows[:-1]])
    return StrategyIndex(strategy, text_rows=trows[starts], member_ptr=np.r_[starts, len(rows)].astype(np.int64),
                         member_rows=rows.astype(np.int64), n_chunk_rows=len(rows))
