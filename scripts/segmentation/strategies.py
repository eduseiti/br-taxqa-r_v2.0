"""Strategy filters over the chunk table (plan §2.2).

    NS = {TXT, TAB}                     identical in every strategy
    S1 = {ART, DSP} ∪ NS                article (or article part / top-level orphan dispositivo)
    S2 = S1 ∪ {CPT, PAR, INC, ALI, ITE} + sub-article units with their ancestor path
    S3 = S2 ∪ {PRT, LIV, TIT, SBT, CAP, SEC, SSC} + grouping chunks

Every chunk has one text regardless of strategy, so S1 and S2 are filters over the S3 embeddings.

    import pandas as pd, strategies
    df = pd.read_csv("segmented/chunks_all.csv")
    s1 = strategies.filter(df, "S1")
"""

from __future__ import annotations

NS = frozenset({"TXT", "TAB"})
S1 = frozenset({"ART", "DSP"}) | NS
S2 = S1 | {"CPT", "PAR", "INC", "ALI", "ITE"}
S3 = S2 | {"PRT", "LIV", "TIT", "SBT", "CAP", "SEC", "SSC"}
STRATEGIES = {"S1": S1, "S2": S2, "S3": S3}


def tipos(strategy: str) -> frozenset:
    return STRATEGIES[strategy.upper()]


def filter(df, strategy: str):  # noqa: A001 - mirrors pandas vocabulary
    """Rows of a chunk DataFrame (column 'Tipo') that strategy indexes."""
    return df[df["Tipo"].isin(tipos(strategy))]


def strategy_mask(tipo_series, strategy: str):
    return tipo_series.isin(tipos(strategy))
