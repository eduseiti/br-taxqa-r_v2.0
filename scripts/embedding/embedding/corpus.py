"""Corpus and query loaders (plan §4.1, §4.3).

The corpus is de-duplicated by the **full text**: each unique text is embedded once, keyed by
``text_id`` (the 16-hex ``texto_sha256``), and ``chunk_map`` maps every chunk back to it.
Unique texts are sorted by ``text_id`` so outputs do not depend on the input row order.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .manifest import sha256_file

HASH_LEN = 16


class CorpusError(Exception):
    pass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LEN]


def read_table(path: Path) -> pd.DataFrame:
    name = path.name.lower()
    if name.endswith((".csv", ".csv.gz")):
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if name.endswith(".parquet"):
        return pd.read_parquet(path).astype(str)
    if name.endswith((".jsonl", ".jsonl.gz")):
        return pd.read_json(path, lines=True, dtype=False).astype(str)
    if name.endswith(".json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        return pd.DataFrame(data).astype(str)
    raise CorpusError(f"unsupported input format: {path.name} (csv, csv.gz, parquet, json, jsonl)")


@dataclass
class Corpus:
    texts: pd.DataFrame        # text_id, text   (unique, sorted by text_id)
    chunk_map: pd.DataFrame    # chunk_id, text_id   (input row order)
    rows: pd.DataFrame         # the input table (for sample building)
    info: dict                 # goes into the manifest


def load_corpus(path: Path, id_col: str = "chunk_id", text_col: str = "Texto",
                hash_col: str | None = "texto_sha256") -> Corpus:
    df = read_table(path)
    for c in (id_col, text_col):
        if c not in df.columns:
            raise CorpusError(f"{path.name}: column {c!r} not found; use --id-col / --text-col")
    if df[id_col].duplicated().any():
        raise CorpusError(f"{path.name}: {id_col!r} is not unique")
    computed = df[text_col].map(text_hash)
    if hash_col and hash_col in df.columns:
        bad = df.index[df[hash_col] != computed]
        if len(bad):
            raise CorpusError(f"{path.name}: {len(bad)} rows where {hash_col} != sha256(Texto)[:16], "
                              f"e.g. {df.at[bad[0], id_col]} (edited or re-encoded file?)")
    df = df.assign(_text_id=computed)
    uniq = df.drop_duplicates(text_col)[["_text_id", text_col]]
    clash = uniq["_text_id"].duplicated(keep=False)
    if clash.any():
        raise CorpusError(f"different texts share a {HASH_LEN}-hex hash: "
                          f"{sorted(set(uniq.loc[clash, '_text_id']))[:5]}")
    texts = (uniq.rename(columns={"_text_id": "text_id", text_col: "text"})
             .sort_values("text_id").reset_index(drop=True))
    chunk_map = df[[id_col, "_text_id"]].rename(columns={id_col: "chunk_id", "_text_id": "text_id"})
    info = {"path": str(path), "sha256": sha256_file(path), "id_col": id_col, "text_col": text_col,
            "rows": len(df), "unique_texts": len(texts)}
    return Corpus(texts=texts, chunk_map=chunk_map.reset_index(drop=True), rows=df, info=info)


def load_queries(path: Path, id_field: str = "question_number",
                 text_field: str = "question_text") -> tuple[pd.DataFrame, dict]:
    """Returns (query_id, text) in input order, plus manifest info."""
    df = read_table(path)
    for c in (id_field, text_field):
        if c not in df.columns:
            raise CorpusError(f"{path.name}: field {c!r} not found; use --id-field / --text-field")
    q = df[[id_field, text_field]].rename(columns={id_field: "query_id", text_field: "text"})
    if q["query_id"].duplicated().any():
        raise CorpusError(f"{path.name}: {id_field!r} is not unique")
    if (q["text"].str.strip() == "").any():
        raise CorpusError(f"{path.name}: empty {text_field!r} for "
                          f"{q.loc[q['text'].str.strip() == '', 'query_id'].tolist()[:5]}")
    info = {"path": str(path), "sha256": sha256_file(path), "id_field": id_field,
            "text_field": text_field, "rows": len(q)}
    return q.reset_index(drop=True), info
