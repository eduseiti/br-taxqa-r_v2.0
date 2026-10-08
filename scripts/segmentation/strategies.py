"""Strategy filters over the chunk table (plan §2.2; caput plan §4.1–4.2, C6).

    NS = {TXT, TAB}                     identical in every strategy
    S1 = {ART, DSP} ∪ NS                article (or article part / top-level orphan dispositivo)
    S2 = S1 ∪ {CPT, PAR, INC, ALI, ITE} + sub-article units with their ancestor path
    S3 = S2 ∪ {PRT, LIV, TIT, SBT, CAP, SEC, SSC} + grouping chunks

A strategy is a set of ``Tipo``s **and** a list of text variants (column ``variante``). Since the
caput plan (D-A, 2026-10-05) paragraph-family rows exist twice: ``base`` (article label +
paragraph subtree, used by S1–S3) and ``caput`` (with the caput's opening sentence after the label,
used by S4 and S2c). Per unit, a strategy keeps the row of the first listed variant that exists;
a ``caput`` row's ``chunk_id`` is ``<stem>#c<seq>`` and its base twin's is ``<stem>#<seq>``.

    S2c = S2 Tipos, variants [caput, base]   (S2 vs S2c: does a paragraph chunk need the caput?)
    S4  = S3 Tipos, variants [caput, base]   (S3 vs S4: the same question with groupings)

    import pandas as pd, strategies
    df = pd.read_csv("segmented/chunks_all.csv.gz")
    s4 = strategies.filter(df, "S4")
"""

from __future__ import annotations

NS = frozenset({"TXT", "TAB"})
S1 = frozenset({"ART", "DSP"}) | NS
S2 = S1 | {"CPT", "PAR", "INC", "ALI", "ITE"}
S3 = S2 | {"PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC"}
BASE = ("base",)
CAPUT = ("caput", "base")
STRATEGIES = {"S1": (S1, BASE), "S2": (S2, BASE), "S3": (S3, BASE),
              "S2C": (S2, CAPUT), "S4": (S3, CAPUT)}


def tipos(strategy: str) -> frozenset:
    return STRATEGIES[strategy.upper()][0]


def variantes(strategy: str) -> tuple[str, ...]:
    return STRATEGIES[strategy.upper()][1]


def base_chunk_id(chunk_ids):
    """Base twin id of each row (``<stem>#c12`` -> ``<stem>#12``; base ids are unchanged)."""
    return chunk_ids.str.replace(r"#c(\d+)$", r"#\1", regex=True)


def strategy_mask(df, strategy: str):
    """Boolean mask of the rows of a chunk DataFrame that ``strategy`` indexes.

    A Series of ``Tipo`` is accepted too, for tables without variants (Tipo membership only)."""
    if not hasattr(df, "columns"):
        return df.isin(tipos(strategy))
    m = df["Tipo"].isin(tipos(strategy))
    if "variante" not in df.columns:
        return m
    base_ids = base_chunk_id(df["chunk_id"])
    out = m & False
    taken: set = set()
    for v in variantes(strategy):
        mv = m & (df["variante"] == v) & ~base_ids.isin(taken)
        out |= mv
        taken |= set(base_ids[mv])
    return out


def filter(df, strategy: str):  # noqa: A001 - mirrors pandas vocabulary
    """Rows of a chunk DataFrame that ``strategy`` indexes (one row per unit)."""
    return df[strategy_mask(df, strategy)]
