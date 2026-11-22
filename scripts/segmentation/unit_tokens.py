#!/usr/bin/env python3
"""Qwen3 token counts per LexML unit, for the token-weighted retrieval metric (A1).

Plan: ``docs/20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md`` §3.2.

For every statutory file that has dispositivo or grouping chunks in ``segmented/chunks_all.csv.gz``,
one row per **unit**, i.e. per element numbered by ``calculaPos`` (the 13 dispositivo and grouping
types outside ``Alteracao``; :class:`common.Positions`):

- ``Num_Inicio`` / ``Num_Final``: the unit's nested-set interval, the same numbering as the chunk table.
  A unit lies inside a chunk iff its ``Num_Inicio`` is within the chunk's interval;
- ``own_tokens``: Qwen3 tokens of the unit's own text (``Rotulo``, ``TituloDispositivo``,
  ``NomeAgrupador``, ``p``, ``table`` whose nearest numbered ancestor is the unit, which includes the
  text of an ``Alteracao`` it quotes), joined as the segmentation's ``texto`` joins them;
- ``subtree_tokens``: Qwen3 tokens of ``texto(unit)``, the unit with all its children, tokenised as one text;
- ``subtree_own_sum``: the sum of ``own_tokens`` over the subtree. Overlaps are computed with the
  additive ``own_tokens``; the difference to ``subtree_tokens`` (tokens that straddle a join) is reported.

A second table, ``prefix_tokens``, gives per file the tokens of the ``[ epígrafe | ementa ]`` prefix that
starts every chunk text (one prefix per file, checked).

Check (``--check``, also written to the run report): for every unsplit ART / DSP chunk,
``prefix_tokens + subtree_own_sum`` against the chunk's ``n_tokens_qwen3``.

Usage::

    .venv/bin/python scripts/segmentation/unit_tokens.py            # → segmented/unit_tokens.csv.gz, …
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (ART_DIR, POS_TYPES, SEG_DIR, TEXT_TAGS, TIPO_OF, L, Positions, in_alteracao,  # noqa: E402
                    norm, parse, tabela, xstring, get_tokenizer)

QWEN3 = "hf:Qwen/Qwen3-Embedding-4B"
UNIT_TIPOS = frozenset(TIPO_OF.values()) | {"DSP"}   # chunk types whose interval is a unit (DSP: loose dispositivos)
OUT_UNITS = SEG_DIR / "unit_tokens.csv.gz"
OUT_PREFIX = SEG_DIR / "prefix_tokens.csv"
OUT_REPORT = SEG_DIR / "unit_tokens_report.json"
COLS = ["arquivo", "unidade_id", "tipo", "Num_Inicio", "Num_Final", "own_tokens", "subtree_tokens", "subtree_own_sum"]


def _counted(e) -> bool:
    return L(e) in POS_TYPES and not in_alteracao(e)


def units_of_file(path: Path) -> list[dict]:
    """Rows (without token counts) of one LexML file: own text and subtree text per numbered unit."""
    tree = parse(path)
    pos = Positions(tree)
    root = tree.getroot()
    units = [e for e in root.iter() if _counted(e)]
    own: dict = defaultdict(list)
    for x in root.iter():
        if L(x) not in TEXT_TAGS or any(L(a) == "table" for a in x.iterancestors()):
            continue
        owner = next((a for a in x.iterancestors() if _counted(a)), None)
        if owner is not None:
            own[owner].append(tabela(x) if L(x) == "table" else norm(xstring(x)))
    rows = []
    for e in units:
        s, f = pos[e]
        sub = [p for d in e.iter() if _counted(d) for p in own.get(d, [])]   # document order = texto order
        rows.append({"arquivo": path.name, "unidade_id": e.get("id") or "", "tipo": TIPO_OF[L(e)],
                     "Num_Inicio": s, "Num_Final": f, "own_text": norm(" ".join(own.get(e, []))),
                     "subtree_text": norm(" ".join(sub))})
    return rows


def _work(path: str) -> pd.DataFrame:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    tok = get_tokenizer(QWEN3)
    df = pd.DataFrame(units_of_file(Path(path)))
    if not len(df):
        return pd.DataFrame(columns=COLS)
    df["own_tokens"] = [n if t else 0 for t, n in zip(df["own_text"], tok.count_many(df["own_text"].tolist()))]
    df["subtree_tokens"] = [n if t else 0 for t, n in zip(df["subtree_text"], tok.count_many(df["subtree_text"].tolist()))]
    df = df.sort_values("Num_Inicio", kind="stable").reset_index(drop=True)
    # sum of own tokens over the subtree: units inside [s, f] are a contiguous block in Num_Inicio order
    cs = df["own_tokens"].cumsum().to_numpy()
    starts = df["Num_Inicio"].to_numpy()
    import numpy as np
    lo = np.searchsorted(starts, df["Num_Inicio"].to_numpy(), side="left")
    hi = np.searchsorted(starts, df["Num_Final"].to_numpy(), side="right")
    df["subtree_own_sum"] = cs[hi - 1] - np.where(lo > 0, cs[lo - 1], 0)
    tok.clear_cache()
    return df[COLS]


PREFIX_RE = __import__("re").compile(r"^\[\s*([^\]]*?)\s*\]\s*")


def prefix_table(chunks: pd.DataFrame) -> pd.DataFrame:
    """Per file: the chunk-text prefix and its Qwen3 tokens (``[ … ] `` as written by ``common.prefixo``)."""
    pre = chunks["Texto"].str.extract(r"^(\[[^\]]*\] )", expand=False).fillna("")
    per = pd.DataFrame({"arquivo": chunks["arquivo"], "prefix": pre}).drop_duplicates()
    n = per.groupby("arquivo")["prefix"].nunique()
    multi = n[n > 1]
    per = per.drop_duplicates("arquivo")
    tok = get_tokenizer(QWEN3)
    per["prefix_tokens"] = [tok.count(p) if p else 0 for p in per["prefix"]]
    per["n_prefixes"] = per["arquivo"].map(n)
    return per.sort_values("arquivo").reset_index(drop=True), sorted(multi.index)


def check(units: pd.DataFrame, prefix: pd.DataFrame, chunks: pd.DataFrame) -> dict:
    """Unsplit ART / DSP base chunks: prefix + subtree_own_sum vs n_tokens_qwen3 (and subtree_tokens)."""
    c = chunks[chunks["Tipo"].isin(["ART", "DSP"]) & (chunks["n_partes"].astype(int) == 1)
               & (chunks["variante"] == "base")]
    m = c.merge(units, on=["arquivo", "Num_Inicio", "Num_Final"], how="left", suffixes=("", "_u"))
    m = m.merge(prefix[["arquivo", "prefix_tokens"]], on="arquivo", how="left")
    found = m["own_tokens"].notna()
    m = m[found]
    est_sum = m["prefix_tokens"] + m["subtree_own_sum"]
    est_one = m["prefix_tokens"] + m["subtree_tokens"]
    dev_sum = (est_sum - m["n_tokens_qwen3"]) / m["n_tokens_qwen3"]
    dev_one = (est_one - m["n_tokens_qwen3"]) / m["n_tokens_qwen3"]
    q = lambda s: {k: round(float(v), 4) for k, v in s.describe(percentiles=[.5, .9, .99]).items()}  # noqa: E731
    return {"chunks_checked": int(len(m)), "chunks_without_unit": int((~found).sum()),
            "rel_dev_subtree_own_sum": q(dev_sum), "rel_dev_subtree_tokens": q(dev_one),
            "share_abs_dev_over_5pct_own_sum": round(float((dev_sum.abs() > 0.05).mean()), 4),
            "share_abs_dev_over_5pct_subtree": round(float((dev_one.abs() > 0.05).mean()), 4),
            "total_rel_dev_own_sum": round(float(est_sum.sum() / m["n_tokens_qwen3"].sum() - 1), 5),
            "total_rel_dev_subtree": round(float(est_one.sum() / m["n_tokens_qwen3"].sum() - 1), 5),
            "worst": m.assign(dev=dev_sum).reindex(dev_sum.abs().sort_values(ascending=False).index)
            .head(10)[["chunk_id", "n_tokens_qwen3", "prefix_tokens", "subtree_own_sum", "subtree_tokens", "dev"]]
            .to_dict("records")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", type=Path, default=SEG_DIR / "chunks_all.csv.gz")
    ap.add_argument("--jobs", type=int, default=min(16, os.cpu_count() or 1))
    args = ap.parse_args()
    t0 = time.time()
    chunks = pd.read_csv(args.chunks, low_memory=False, keep_default_na=False)
    files = sorted(set(chunks.loc[chunks["Tipo"].isin(UNIT_TIPOS), "arquivo"]))
    missing = [f for f in files if not (ART_DIR / f).exists()]
    if missing:
        raise SystemExit(f"LexML files not found under {ART_DIR}: {missing[:5]}")
    with ProcessPoolExecutor(args.jobs) as ex:
        parts = list(ex.map(_work, [str(ART_DIR / f) for f in files], chunksize=4))
    units = pd.concat(parts, ignore_index=True)
    prefix, multi = prefix_table(chunks)

    # every dispositivo / grouping chunk interval must start at a unit (split parts: their first unit)
    c = chunks[chunks["Tipo"].isin(UNIT_TIPOS)]
    have = set(zip(units["arquivo"], units["Num_Inicio"]))
    no_unit = [cid for cid, f, s in zip(c["chunk_id"], c["arquivo"], c["Num_Inicio"]) if (f, int(s)) not in have]

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(units.to_csv(index=False).encode("utf-8"))
    OUT_UNITS.write_bytes(buf.getvalue())
    prefix[["arquivo", "prefix_tokens", "n_prefixes"]].to_csv(OUT_PREFIX, index=False)
    report = {"files": len(files), "units": int(len(units)), "units_by_tipo": units["tipo"].value_counts().to_dict(),
              "units_without_id": int((units["unidade_id"] == "").sum()),
              "files_with_more_than_one_prefix": multi,
              "unit_chunks_not_starting_at_a_unit": no_unit[:50], "n_unit_chunks_not_starting_at_a_unit": len(no_unit),
              "check_unsplit_articles": check(units, prefix, chunks),
              "chunks_sha256_input": __import__("hashlib").sha256(args.chunks.read_bytes()).hexdigest(),
              "seconds": round(time.time() - t0, 1)}
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "check_unsplit_articles"}, ensure_ascii=False, default=str)[:2000])
    print(json.dumps(report["check_unsplit_articles"], ensure_ascii=False, indent=1, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
