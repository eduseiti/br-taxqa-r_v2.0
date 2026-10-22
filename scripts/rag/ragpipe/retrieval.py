"""Stage R: rank the candidate texts of each strategy for every question and store the rankings
(plan §3, §5).

Output, under ``runs/retrieval/<embedding>/<instruction>/``::

    manifest.json
    <strategy>/rankings.csv.gz   question_number, rank, text_id, chunk_id, alias_chunk_ids, score
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .data import Paths, check_inputs, load_chunks, load_dataset, load_embedding
from .exclusions import Exclusions
from .retrievers import DenseRetriever
from .runs import base_manifest, prepare_run_dir, rel, sha256_file, sha256_json, write_csv, write_json
from .strategies import StrategyIndex, attach_text_rows, build_index, load_strategies

log = logging.getLogger("ragpipe")

RANKING_COLUMNS = ["question_number", "rank", "text_id", "chunk_id", "alias_chunk_ids", "score"]


@dataclass
class RetrievalConfig:
    embedding: str
    instruction: str
    strategies: list[str] | None = None
    top_n: int = 1000
    retriever: str = "dense"
    block_size: int = 128
    hash_vectors: bool = True
    force: bool = False
    run_name: str | None = None          # output directory name (default: the instruction)
    exclusions: Path | None | str = "default"   # "default": Paths.exclusions; None: no exclusion


def rankings_frame(index: StrategyIndex, chunks: pd.DataFrame, text_ids: np.ndarray,
                   query_ids: list[str], rankings: list[list[tuple[int, float]]]) -> pd.DataFrame:
    """Rankings of one strategy as the documented table (one row per question × rank)."""
    pos = index.position(len(text_ids))
    chunk_id = chunks["chunk_id"].to_numpy()
    rep = chunk_id[index.representative()]
    aliases = np.array([";".join(chunk_id[index.members(i)[1:]]) for i in range(len(index))], dtype=object)
    lens = [len(r) for r in rankings]
    rows = np.fromiter((r for rk in rankings for r, _ in rk), dtype=np.int64, count=sum(lens))
    scores = np.fromiter((s for rk in rankings for _, s in rk), dtype=np.float64, count=sum(lens))
    p = pos[rows]
    return pd.DataFrame({
        "question_number": np.repeat(np.asarray(query_ids, dtype=object), lens),
        "rank": np.concatenate([np.arange(1, n + 1) for n in lens]) if lens else np.array([], dtype=int),
        "text_id": text_ids[rows], "chunk_id": rep[p], "alias_chunk_ids": aliases[p],
        "score": np.round(scores, 6),
    })[RANKING_COLUMNS]


def run_retrieval(cfg: RetrievalConfig, paths: Paths = Paths()) -> Path:
    """Run stage R and return the run directory."""
    t0 = time.time()
    strat_cfg = load_strategies(paths.strategies)
    strategies = strat_cfg.select(cfg.strategies)
    chunks = load_chunks(paths.chunks)
    chunks_sha = sha256_file(paths.chunks)
    ds = load_dataset(paths.dataset)
    emb = load_embedding(paths.embeddings, cfg.embedding, cfg.instruction)
    report = check_inputs(chunks, chunks_sha, emb, ds, hash_vectors=cfg.hash_vectors)
    for w in report.warnings:
        log.warning("%s", w)
    report.raise_if_failed()
    t_load = time.time()

    excl = Exclusions.load(paths.exclusions if cfg.exclusions == "default" else cfg.exclusions)
    excluded = excl.row_mask(chunks, ds.file_to_document())
    run_name = cfg.run_name or cfg.instruction
    params = {"embedding": cfg.embedding, "instruction": cfg.instruction, "retriever": cfg.retriever,
              "top_n": cfg.top_n, "strategies": [s.name for s in strategies], "run_name": run_name,
              "excluded_documents": sorted(excl.documents)}
    inputs = {"chunks": {"path": rel(paths.chunks), "sha256": chunks_sha},
              **{Path(p).stem: {"path": p, "sha256": h} for p, h in ds.sha256.items()},
              "strategies_yaml": {"path": rel(paths.strategies), "sha256": strat_cfg.sha256},
              **{k: {"path": rel(p), "sha256": sha256_file(p) if cfg.hash_vectors else None}
                 for k, p in emb.input_files().items()},
              **({"corpus_exclusions": {"path": excl.path, "sha256": excl.sha256}} if excl.path else {})}
    config_hash = sha256_json({"params": params, "inputs": {k: v["sha256"] for k, v in inputs.items()},
                               "strategies": strat_cfg.to_dict()["strategies"]})
    out_dir = paths.retrieval_dir(cfg.embedding, run_name)
    prepare_run_dir(out_dir, config_hash, cfg.force)

    chunks = attach_text_rows(chunks, emb)
    indexes = {s.name: build_index(chunks, s, strat_cfg.unit_precedence, excluded) for s in strategies}
    if excl.documents:
        log.info("excluded from the corpus: %s (%d chunk rows)", ", ".join(sorted(excl.documents)), int(excluded.sum()))
    if cfg.retriever != "dense":
        raise ValueError(f"unknown retriever {cfg.retriever!r} (available: dense)")
    query_ids = ds.question_ids
    retriever = DenseRetriever(emb.corpus_vectors(), emb.text_ids, emb.query_vectors(),
                               emb.queries["query_id"].tolist(), block_size=cfg.block_size)
    t_index = time.time()
    log.info("searching %d questions × %d strategies (top-%d)", len(query_ids), len(indexes), cfg.top_n)
    results = retriever.search_many(query_ids, {n: ix.text_rows for n, ix in indexes.items()}, cfg.top_n)
    t_search = time.time()

    counts = {}
    for name, ix in indexes.items():
        df = rankings_frame(ix, chunks, emb.text_ids, query_ids, results[name])
        write_csv(df, out_dir / name / "rankings.csv.gz")
        counts[name] = {"chunk_rows": ix.n_chunk_rows, "candidate_texts": len(ix), "ranking_rows": len(df),
                        "texts_with_aliases": int((np.diff(ix.member_ptr) > 1).sum())}
        log.info("%s: %d chunks → %d texts; wrote %s", name, ix.n_chunk_rows, len(ix),
                 rel(out_dir / name / "rankings.csv.gz"))
    t_end = time.time()

    manifest = base_manifest("retrieval")
    manifest.update({
        "config_hash": config_hash, "params": params, "embedding": emb.info(), "retriever": retriever.info(),
        "strategies": strat_cfg.to_dict(), "inputs": inputs, "checks": report.to_dict(), "counts": counts,
        "corpus_exclusions": excl.to_manifest(int(excluded.sum())),
        "outputs": {n: {"path": f"{n}/rankings.csv.gz",
                        "sha256": sha256_file(out_dir / n / "rankings.csv.gz")} for n in indexes},
        "timings_s": {"load_and_check": round(t_load - t0, 2), "index": round(t_index - t_load, 2),
                      "search": round(t_search - t_index, 2), "write": round(t_end - t_search, 2),
                      "total": round(t_end - t0, 2)},
    })
    write_json(out_dir / "manifest.json", manifest)
    return out_dir


def load_rankings(run_dir: Path, strategy: str) -> pd.DataFrame:
    path = Path(run_dir) / strategy / "rankings.csv.gz"
    if not path.exists():
        raise FileNotFoundError(f"{rel(path)} not found; run `rag.py retrieve` first")
    return pd.read_csv(path, dtype={"question_number": str, "text_id": str, "chunk_id": str,
                                    "alias_chunk_ids": str}, keep_default_na=False)
