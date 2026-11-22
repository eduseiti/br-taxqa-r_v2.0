"""Token accounting of a context against the gold units: the token-weighted provision metric (A1).

Plan: ``docs/20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md`` §3.

The building block is ``segmented/unit_tokens.csv.gz`` (``scripts/segmentation/unit_tokens.py``): one row
per LexML unit (dispositivo or grouping) with its nested-set interval and the Qwen3 tokens of its **own**
text (label, heading, ``p``, tables; not its children). A unit lies inside a chunk iff its ``Num_Inicio``
is within the chunk's interval, so the units of a chunk, or of a gold unit, are one contiguous block of
the file's units sorted by ``Num_Inicio``.

What a chunk shows:

- **content**: the units inside its interval (an S1 article, an S2 inciso with its alíneas, an S3
  chapter with its articles). Split-article parts that share a unit (a leaf cut into pieces) get an
  equal share of its tokens;
- **path**: the opening text of the dispositivo units around it (article label, caput sentence, inciso
  head…), for the S2c/S4 ``caput`` variant the caput sentence (``contexto_ids``), and for split-article
  parts the units their head repeats (``parcial_ids``: the article, the caput sentence before paragraphs).
  Shown, so it is credited to a gold unit it belongs to, once per context;
- the ``[ epígrafe | ementa ]`` prefix (``segmented/prefix_tokens.csv``);
- chunks of other types (TXT / TAB: non-statutory text, loose annex content) have no units: prefix +
  off-gold content.

Per context, its tokens ``T`` (the ``n_tokens_qwen3`` of the selected texts) split into:

- ``gold``: own tokens of the distinct gold units visible (content or path), each counted once;
- ``offgold``: own tokens of the distinct non-gold dispositivo units in the content, plus the text of
  unit-less chunks;
- ``scaffold``: the rest: prefixes, grouping names (own text of grouping units), the path text outside
  the gold, repeated text. ``T − gold − offgold``, clipped at 0 (sums of own tokens are ≈ 0.4 % above the
  tokens of the joined text, ``unit_tokens_report.json``).

Per gold item, ``coverage`` = visible own tokens of the item's unit subtree ÷ its total; with several
candidate units (main file and annex under the ``either`` rule, repeated article ids) the best one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .data import InputError
from .relevance import GoldItem, Match
from .runs import rel

#: Chunk types whose interval is a LexML unit.
UNIT_TIPOS = frozenset({"ART", "CPT", "PAR", "INC", "ALI", "ITE", "DSP", "PRT", "LIV", "TIT", "SBT", "CAP", "SEC",
                        "SSC"})
GROUPING_TIPOS = frozenset({"PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC"})
#: Unit types that can be on an ancestor path (the segmentation's ``caminho``: dispositivo ancestors).
PATH_TIPOS = frozenset({"ART", "CPT", "PAR", "INC", "ALI", "ITE"})
TOKEN_LEVELS = ("article", "provision")
EMPTY_I = np.empty(0, dtype=np.int64)
EMPTY_F = np.empty(0, dtype=np.float64)


@dataclass
class ChunkShow:
    """What one chunk shows: content units (global indices, sorted) with their weights, and path units."""

    content: np.ndarray
    weight: np.ndarray
    path: np.ndarray
    text_tokens: int          # tokens of unit-less content (TXT / TAB chunks without the prefix)


@dataclass
class Accounting:
    """Token split of one context and the per-item coverage."""

    total: int
    gold: float
    offgold: float
    scaffold: float
    coverage: list[float]       # per gold item, NaN when the item has no unit


class UnitTokens:
    """The unit table, indexed for interval queries, and the chunk → units mapping."""

    def __init__(self, units: pd.DataFrame, prefix: pd.DataFrame, chunks: pd.DataFrame):
        units = units.sort_values(["arquivo", "Num_Inicio"], kind="stable").reset_index(drop=True)
        self.arquivo = units["arquivo"].to_numpy()
        self.start = units["Num_Inicio"].to_numpy(np.int64)
        self.end = units["Num_Final"].to_numpy(np.int64)
        self.own = units["own_tokens"].to_numpy(np.float64)
        self.tipo = units["tipo"].to_numpy()
        self.uid = units["unidade_id"].to_numpy()
        self.is_group = np.isin(self.tipo, list(GROUPING_TIPOS))
        self.can_path = np.isin(self.tipo, list(PATH_TIPOS))
        # content tokens: grouping names are scaffold, not content
        self.own_content = np.where(self.is_group, 0.0, self.own)
        self.span: dict[str, tuple[int, int]] = {}
        for f, idx in units.groupby("arquivo", sort=False).indices.items():
            self.span[f] = (int(idx.min()), int(idx.max()) + 1)
        self.by_id: dict[tuple[str, str], list[int]] = {}
        for i, (f, u) in enumerate(zip(self.arquivo, self.uid)):
            self.by_id.setdefault((f, u), []).append(i)
        self.prefix = dict(zip(prefix["arquivo"], prefix["prefix_tokens"].astype(int)))

        self.c_tipo = chunks["Tipo"].to_numpy()
        self.c_file = chunks["arquivo"].to_numpy()
        self.c_start = chunks["Num_Inicio"].to_numpy()
        self.c_end = chunks["Num_Final"].to_numpy()
        self.c_tokens = chunks["n_tokens_qwen3"].to_numpy()
        self.c_ctx = chunks["contexto_ids"].to_numpy() if "contexto_ids" in chunks else np.full(len(chunks), "")
        self.c_parcial = chunks["parcial_ids"].to_numpy()
        self._piece_weights = self._split_part_weights(chunks)
        self._cache: dict[int, ChunkShow] = {}

    @classmethod
    def load(cls, units_path: Path, prefix_path: Path, chunks: pd.DataFrame) -> "UnitTokens":
        for p in (units_path, prefix_path):
            if not Path(p).exists():
                raise InputError(f"{rel(p)} not found; run scripts/segmentation/unit_tokens.py")
        units = pd.read_csv(units_path, keep_default_na=False, dtype={"unidade_id": str})
        prefix = pd.read_csv(prefix_path, keep_default_na=False)
        return cls(units, prefix, chunks)

    # -- interval queries ------------------------------------------------------------------------

    def block(self, f: str, s: int, e: int) -> tuple[int, int]:
        """Global index range ``[lo, hi)`` of the units of file ``f`` inside ``[s, e]``."""
        sp = self.span.get(f)
        if sp is None:
            return 0, 0
        a, b = sp
        lo = a + int(np.searchsorted(self.start[a:b], s, side="left"))
        hi = a + int(np.searchsorted(self.start[a:b], e, side="right"))
        return lo, hi

    def ancestors(self, f: str, s: int, e: int) -> np.ndarray:
        """Path units around ``[s, e]``: dispositivo units of ``f`` that strictly contain it."""
        sp = self.span.get(f)
        if sp is None:
            return EMPTY_I
        a, _ = sp
        lo, _ = self.block(f, s, e)
        cand = np.arange(a, lo)
        cand = cand[(self.end[cand] >= e) & (self.start[cand] < s)]
        return cand[self.can_path[cand]]

    def _split_part_weights(self, chunks: pd.DataFrame) -> dict[int, dict[int, float]]:
        """Chunk row → {unit: weight < 1} for units shared by several parts of one split article."""
        out: dict[int, dict[int, float]] = {}
        parts = chunks[(chunks["n_partes"] > 1) & chunks["Tipo"].isin(["ART", "DSP"])]
        for _, g in parts.groupby(["arquivo", "unidade_id", "variante", "n_partes"], sort=False):
            rows = g.index.to_numpy()
            mult: dict[int, int] = {}
            blocks = {}
            for r in rows:
                lo, hi = self.block(self.c_file[r], int(self.c_start[r]), int(self.c_end[r]))
                blocks[r] = (lo, hi)
                for u in range(lo, hi):
                    mult[u] = mult.get(u, 0) + 1
            for r, (lo, hi) in blocks.items():
                w = {u: 1.0 / mult[u] for u in range(lo, hi) if mult[u] > 1}
                if w:
                    out[int(r)] = w
        return out

    def show(self, row: int) -> ChunkShow:
        """What chunk ``row`` shows (cached)."""
        c = self._cache.get(row)
        if c is not None:
            return c
        f = self.c_file[row]
        if self.c_tipo[row] not in UNIT_TIPOS or f not in self.span:
            c = ChunkShow(EMPTY_I, EMPTY_F, EMPTY_I, max(0, int(self.c_tokens[row]) - self.prefix.get(f, 0)))
        else:
            s, e = int(self.c_start[row]), int(self.c_end[row])
            lo, hi = self.block(f, s, e)
            content = np.arange(lo, hi, dtype=np.int64)
            weight = np.ones(hi - lo)
            pw = self._piece_weights.get(row)
            if pw:
                for u, w in pw.items():
                    weight[u - lo] = w
            path = self.ancestors(f, s, e)
            ids = [x for x in (self.c_ctx[row] + ";" + self.c_parcial[row]).split(";") if x]
            if ids:
                # within the chunk's own article only (a file can repeat an article id): the outermost
                # dispositivo around or at the chunk
                top = path[0] if len(path) else lo
                a_s, a_e = int(self.start[top]), int(self.end[top])
                extra = [i for cid in ids for i in self.by_id.get((f, cid), [])
                         if a_s <= self.start[i] and self.end[i] <= a_e]
                if extra:
                    path = np.union1d(path, np.array(extra, dtype=np.int64))
            c = ChunkShow(content, weight, path, 0)
        self._cache[row] = c
        return c

    # -- gold ------------------------------------------------------------------------------------

    def item_blocks(self, item: GoldItem, m: Match) -> list[tuple[int, int]]:
        """Candidate unit blocks of a gold item (article / provision level); empty when it has no unit."""
        uid = item.article_id if item.level == "article" else item.fragment_id
        if not uid:
            return []
        out = []
        for f, _ in m.units:
            for i in self.by_id.get((f, uid), []):
                if item.level == "article" and self.tipo[i] not in ("ART", "DSP"):
                    continue
                out.append(self.block(f, int(self.start[i]), int(self.end[i])))
        return out

    def size(self, blk: tuple[int, int]) -> float:
        lo, hi = blk
        return float(self.own_content[lo:hi].sum())

    # -- one context -----------------------------------------------------------------------------

    def account(self, rows: list[int], total: int, item_blocks: list[list[tuple[int, int]]]) -> Accounting:
        """Token split of a context made of chunk ``rows`` (``total`` tokens) and the coverage of each
        gold item (``item_blocks``: its candidate unit blocks)."""
        shows = [self.show(r) for r in rows]
        text_tokens = float(sum(s.text_tokens for s in shows))
        if shows:
            cidx = np.concatenate([s.content for s in shows])
            cw = np.concatenate([s.weight for s in shows])
            pidx = np.concatenate([s.path for s in shows])
        else:
            cidx, cw, pidx = EMPTY_I, EMPTY_F, EMPTY_I
        uc, inv = np.unique(cidx, return_inverse=True)
        wc = np.minimum(np.bincount(inv, weights=cw, minlength=len(uc)), 1.0) if len(uc) else EMPTY_F
        # visible units: content (weighted) ∪ path (whole own text, weight 1)
        up = np.setdiff1d(np.unique(pidx), uc)
        vis = np.concatenate([uc, up])
        vw = np.concatenate([wc, np.ones(len(up))])
        order = np.argsort(vis, kind="stable")
        vis, vw = vis[order], vw[order]
        vtok = self.own_content[vis] * vw if len(vis) else EMPTY_F
        csum = np.concatenate([[0.0], np.cumsum(vtok)])

        def visible_in(lo: int, hi: int) -> float:
            a, b = np.searchsorted(vis, lo, "left"), np.searchsorted(vis, hi, "left")
            return float(csum[b] - csum[a])

        cov, gold_mask = [], np.zeros(len(vis), dtype=bool)
        for blks in item_blocks:
            best = np.nan
            for lo, hi in blks:
                size = self.size((lo, hi))
                a, b = np.searchsorted(vis, lo, "left"), np.searchsorted(vis, hi, "left")
                gold_mask[a:b] = True
                if size > 0:
                    v = visible_in(lo, hi) / size
                    best = v if np.isnan(best) else max(best, v)
            cov.append(best)
        gold = float(vtok[gold_mask].sum())
        # off-gold: non-gold content units only (path text outside the gold is scaffold)
        in_content = np.isin(vis, uc)
        offgold = float(vtok[in_content & ~gold_mask].sum()) + text_tokens
        if gold + offgold > total > 0:          # sums of own tokens slightly above the joined text's tokens
            k = total / (gold + offgold)
            gold, offgold = gold * k, offgold * k
        scaffold = max(0.0, total - gold - offgold)
        return Accounting(total, gold, offgold, scaffold, cov)
