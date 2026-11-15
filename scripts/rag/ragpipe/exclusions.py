"""Documents and chunks excluded from the retrieval corpus (``scripts/rag/corpus_exclusions.yaml``).

An excluded document stays in the dataset, the chunk file and the embeddings; only its chunks stop
being retrieval candidates. Excluded **chunks** (section ``chunks:``) are parser misparses with no legal
text of their own (a citation line or a heading parsed as an ``Art. N``): they stop being retrieval
candidates and the gold matcher ignores them (``Matcher(ignore_rows=...)``), since they are not the
article whose id they carry (docs/20261115_172140_gold_matcher_annex_rule_and_misparsed_articles.md). The list is read by stage R and recorded in its manifest; stages RE and C
take it from that manifest, so they always agree with the rankings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .data import InputError
from .runs import rel, sha256_file


@dataclass(frozen=True)
class Exclusions:
    documents: dict[str, dict] = field(default_factory=dict)
    chunks: dict[str, dict] = field(default_factory=dict)
    path: str | None = None
    sha256: str | None = None

    @classmethod
    def load(cls, path: Path | None) -> "Exclusions":
        """The list at ``path``; ``None`` (``--exclusions none``) means no exclusion."""
        if path is None:
            return cls()
        path = Path(path)
        if not path.exists():
            raise InputError(f"exclusion list {rel(path)} not found (use --exclusions none for a run without one)")
        y = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(dict(y.get("documents") or {}), dict(y.get("chunks") or {}), rel(path), sha256_file(path))

    @classmethod
    def from_manifest(cls, manifest: dict) -> "Exclusions":
        """The exclusions a retrieval run was made with (none for runs before the list existed)."""
        e = manifest.get("corpus_exclusions") or {}
        return cls({d: {} for d in e.get("documents", [])}, {c: {} for c in e.get("chunks", [])}, e.get("path"),
                   e.get("sha256"))

    def __contains__(self, document_id: object) -> bool:
        return document_id in self.documents

    def chunk_row_mask(self, chunks: pd.DataFrame) -> np.ndarray:
        """Chunk-table rows of the excluded chunks (misparses)."""
        if not self.chunks:
            return np.zeros(len(chunks), dtype=bool)
        mask = chunks["chunk_id"].isin(list(self.chunks)).to_numpy()
        unknown = sorted(set(self.chunks) - set(chunks["chunk_id"][mask]))
        if unknown:
            raise InputError(f"excluded chunk(s) {unknown} not in the chunk file")
        return mask

    def row_mask(self, chunks: pd.DataFrame, file_to_doc: dict[str, str]) -> np.ndarray:
        """Chunk-table rows that stop being retrieval candidates: the rows of an excluded document (main or
        annex file) and the excluded chunks."""
        mask = self.chunk_row_mask(chunks)
        if not self.documents:
            return mask
        files = [f for f, d in file_to_doc.items() if d in self.documents]
        unknown = sorted(set(self.documents) - set(file_to_doc.values()))
        if unknown:
            raise InputError(f"excluded document(s) {unknown} not in dataset/documents.jsonl")
        return chunks["arquivo"].isin(files).to_numpy() | mask

    def to_manifest(self, n_rows: int) -> dict:
        return {"path": self.path, "sha256": self.sha256, "documents": sorted(self.documents),
                "chunks": sorted(self.chunks), "chunk_rows_excluded": int(n_rows)}
