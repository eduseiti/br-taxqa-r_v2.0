"""Loading of the inputs (chunks, the v2.0 dataset configs, embedding outputs) and all input checks
(plan §8.3).

The embedding outputs are read through their documented release format only (embedding plan §4.2):

    embeddings/<slug>/corpus/{manifest.json, texts.csv, chunk_map.csv.gz, vectors.npy}
    embeddings/<slug>/queries/<instruction>/{manifest.json, queries.csv, vectors.npy}

so the vectors released on the Hub are enough; the embedding code is not imported.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .runs import REPO, read_json, rel, sha256_file

log = logging.getLogger("ragpipe")

#: Chunk columns used by the pipeline (``Texto`` is loaded only on request).
CHUNK_COLS = ["chunk_id", "Tipo", "arquivo", "categoria", "doc_urn", "unidade_id", "artigo_id", "citacao",
              "parte", "n_partes", "cobre_ids", "parcial_ids", "id_ambiguo", "n_tokens_qwen3",
              "Num_Inicio", "Num_Final", "variante"]
INT_COLS = ["parte", "n_partes", "id_ambiguo", "n_tokens_qwen3", "Num_Inicio", "Num_Final"]


class InputError(RuntimeError):
    """An input is missing or inconsistent. The message says what to do."""


@dataclass(frozen=True)
class Paths:
    """Default input/output locations, all relative to the repository root."""

    repo: Path = REPO
    chunks: Path = REPO / "segmented" / "chunks_all.csv.gz"
    dataset: Path = REPO / "dataset"
    embeddings: Path = REPO / "embeddings"
    runs: Path = REPO / "runs"
    strategies: Path = Path(__file__).resolve().parents[1] / "strategies.yaml"
    chapters: Path = Path(__file__).resolve().parents[1] / "data" / "pr_irpf_2024_chapters.csv"

    def retrieval_dir(self, embedding: str, instruction: str) -> Path:
        return self.runs / "retrieval" / embedding / instruction


# ------------------------------------------------------------------------------------------------
# Chunks
# ------------------------------------------------------------------------------------------------

def load_chunks(path: Path, with_text: bool = False) -> pd.DataFrame:
    """The chunk table, one row per chunk, in file order. Integer columns are converted."""
    if not Path(path).exists():
        raise InputError(f"chunk file {rel(path)} not found; run scripts/segmentation/segment_all.py "
                         "or download segmented/chunks_all.csv.gz from the Hub")
    cols = CHUNK_COLS + (["Texto", "Rotulo"] if with_text else [])
    header = pd.read_csv(path, dtype=str, nrows=0).columns
    df = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=[c for c in cols if c in header])
    if "variante" not in df.columns:  # chunk files from before the caput plan: one text per unit
        df["variante"] = "base"
    df = df[cols]
    for c in INT_COLS:
        df[c] = pd.to_numeric(df[c], errors="raise").astype(np.int64)
    if df["chunk_id"].duplicated().any():
        raise InputError(f"{rel(path)}: duplicated chunk_id values")
    return df.reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# Dataset (HF JSON Lines configs)
# ------------------------------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise InputError(f"{rel(path)} not found; build it with scripts/dataset/build_v2_dataset.py "
                         "or download the v2.0 dataset from the Hub")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@dataclass
class Dataset:
    """The three v2.0 configs, plus their hashes."""

    questions: pd.DataFrame
    references: list[dict]
    documents: pd.DataFrame
    sha256: dict[str, str] = field(default_factory=dict)

    @property
    def question_ids(self) -> list[str]:
        return self.questions["question_number"].tolist()

    def file_to_document(self) -> dict[str, str]:
        """LexML file basename (the chunks' ``arquivo``) → ``document_id``, main and annex files."""
        out: dict[str, str] = {}
        for doc in self.documents.itertuples():
            for f in [doc.lexml_file, *doc.lexml_annex_files]:
                if f:
                    out[Path(f).name] = doc.document_id
        return out


def load_dataset(dataset_dir: Path) -> Dataset:
    names = ("questions", "references", "documents")
    files = {n: Path(dataset_dir) / f"{n}.jsonl" for n in names}
    rows = {n: _read_jsonl(p) for n, p in files.items()}
    return Dataset(questions=pd.DataFrame(rows["questions"]), references=rows["references"],
                   documents=pd.DataFrame(rows["documents"]),
                   sha256={f"dataset/{n}.jsonl": sha256_file(p) for n, p in files.items()})


def load_chapters(path: Path, question_ids: list[str]) -> dict[str, str]:
    """``question_number`` → chapter of the P&R document (question ranges in a CSV)."""
    df = pd.read_csv(path, dtype=str)
    out = {}
    for r in df.itertuples():
        for n in range(int(r.first_question), int(r.last_question) + 1):
            out[f"{n:03d}"] = r.chapter
    missing = [q for q in question_ids if q not in out]
    if missing:
        raise InputError(f"{rel(path)} gives no chapter for questions {missing[:5]}…")
    return out


# ------------------------------------------------------------------------------------------------
# Embedding outputs
# ------------------------------------------------------------------------------------------------

@dataclass
class Embedding:
    """Stored corpus and query vectors of one model and one query instruction."""

    slug: str
    instruction: str
    corpus_dir: Path
    query_dir: Path
    corpus_manifest: dict
    query_manifest: dict
    text_ids: np.ndarray            # [n_texts] str, row order of the corpus vectors
    text_tokens: np.ndarray         # [n_texts] tokens of the embedding tokenizer
    chunk_map: pd.DataFrame         # chunk_id, text_id
    queries: pd.DataFrame           # row, query_id, n_tokens, text_sent

    @property
    def corpus_vectors_path(self) -> Path:
        return self.corpus_dir / "vectors.npy"

    @property
    def query_vectors_path(self) -> Path:
        return self.query_dir / "vectors.npy"

    def corpus_vectors(self) -> np.ndarray:
        return np.load(self.corpus_vectors_path, mmap_mode="r")

    def query_vectors(self) -> np.ndarray:
        return np.load(self.query_vectors_path, mmap_mode="r")

    def input_files(self) -> dict[str, Path]:
        return {"corpus_vectors": self.corpus_vectors_path, "corpus_texts": self.corpus_dir / "texts.csv",
                "chunk_map": self.corpus_dir / "chunk_map.csv.gz",
                "query_vectors": self.query_vectors_path, "queries": self.query_dir / "queries.csv"}

    def info(self) -> dict:
        m = self.query_manifest["model"]
        return {"slug": self.slug, "model_id": m.get("model_id"), "revision": m.get("revision"),
                "dim": m.get("dim"), "instruction_name": self.instruction,
                "instruction": m.get("instruction"), "query_template": m.get("template"),
                "document_template": self.corpus_manifest["model"].get("template")}


def list_instructions(embeddings_dir: Path, slug: str) -> list[str]:
    qdir = Path(embeddings_dir) / slug / "queries"
    return sorted(p.name for p in qdir.iterdir() if (p / "manifest.json").exists()) if qdir.exists() else []


def default_instruction(embeddings_dir: Path, slug: str) -> str:
    """The instruction to use when none is given: ``irpf`` if present, else the only one."""
    found = list_instructions(embeddings_dir, slug)
    if "irpf" in found:
        return "irpf"
    if len(found) == 1:
        return found[0]
    if not found:
        raise InputError(f"no query vectors for embedding '{slug}' under {rel(Path(embeddings_dir) / slug)}; "
                         f"run `embed.py queries --model {slug}`")
    raise InputError(f"embedding '{slug}' has several instructions ({', '.join(found)}); pass --instruction")


def load_embedding(embeddings_dir: Path, slug: str, instruction: str) -> Embedding:
    corpus_dir = Path(embeddings_dir) / slug / "corpus"
    query_dir = Path(embeddings_dir) / slug / "queries" / instruction
    if not (corpus_dir / "manifest.json").exists():
        raise InputError(f"no corpus embeddings for '{slug}' ({rel(corpus_dir)}/manifest.json missing); run "
                         f"`embed.py corpus --model {slug}` or download the vectors from the Hub")
    if not (query_dir / "manifest.json").exists():
        found = ", ".join(list_instructions(embeddings_dir, slug)) or "none"
        raise InputError(f"no query vectors for instruction '{instruction}' (available: {found}); run "
                         f"`embed.py queries --model {slug} --instruction-name {instruction}`")
    for p in [corpus_dir / "texts.csv", corpus_dir / "chunk_map.csv.gz", corpus_dir / "vectors.npy",
              query_dir / "queries.csv", query_dir / "vectors.npy"]:
        if not p.exists():
            raise InputError(f"{rel(p)} missing; the embedding run is incomplete "
                             f"(`embed.py finalize --model {slug}`)")
    texts = pd.read_csv(corpus_dir / "texts.csv", dtype={"text_id": str})
    queries = pd.read_csv(query_dir / "queries.csv", dtype={"query_id": str}, keep_default_na=False)
    return Embedding(slug=slug, instruction=instruction, corpus_dir=corpus_dir, query_dir=query_dir,
                     corpus_manifest=read_json(corpus_dir / "manifest.json"),
                     query_manifest=read_json(query_dir / "manifest.json"),
                     text_ids=texts["text_id"].to_numpy(dtype=object),
                     text_tokens=texts["n_tokens"].to_numpy(dtype=np.int64),
                     chunk_map=pd.read_csv(corpus_dir / "chunk_map.csv.gz", dtype=str),
                     queries=queries)


# ------------------------------------------------------------------------------------------------
# Checks
# ------------------------------------------------------------------------------------------------

@dataclass
class CheckReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_failed(self) -> None:
        if self.errors:
            raise InputError("input checks failed:\n  - " + "\n  - ".join(self.errors))

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "info": self.info}


def check_inputs(chunks: pd.DataFrame, chunks_sha256: str, emb: Embedding, ds: Dataset,
                 hash_vectors: bool = True) -> CheckReport:
    """All consistency checks between chunks, vectors, queries and the dataset (plan §8.3).

    Errors make the vectors unusable for these chunks/questions; warnings are known corpus gaps
    (plan §2.1) that the evaluation measures instead of hiding.
    """
    rep = CheckReport()
    cm = emb.corpus_manifest

    # Chunks ↔ corpus vectors
    expected = cm.get("input", {}).get("sha256")
    if expected != chunks_sha256:
        rep.errors.append(f"chunk file SHA-256 {chunks_sha256[:12]}… differs from the one embedded by "
                          f"'{emb.slug}' ({str(expected)[:12]}…): the vectors belong to other chunks; "
                          "re-embed or use the matching chunk file")
    n_rows = len(emb.text_ids)
    shape = cm.get("output", {}).get("shape")
    vec = emb.corpus_vectors()
    if vec.shape[0] != n_rows or (shape and list(vec.shape) != list(shape)):
        rep.errors.append(f"corpus vectors {tuple(vec.shape)} do not match texts.csv ({n_rows} rows) "
                          f"or the manifest shape {shape}")
    if pd.Series(emb.text_ids).duplicated().any():
        rep.errors.append("texts.csv has duplicated text_id values")
    cmap = emb.chunk_map
    chunk_ids = set(chunks["chunk_id"])
    mapped = set(cmap["chunk_id"])
    if chunk_ids - mapped:
        rep.errors.append(f"chunk_map.csv.gz does not cover {len(chunk_ids - mapped)} chunk_id(s), "
                          f"e.g. {sorted(chunk_ids - mapped)[:3]}")
    if mapped - chunk_ids:
        rep.warnings.append(f"chunk_map.csv.gz has {len(mapped - chunk_ids)} chunk_id(s) not in the chunk file")
    unknown_texts = set(cmap["text_id"]) - set(emb.text_ids)
    if unknown_texts:
        rep.errors.append(f"chunk_map.csv.gz points at {len(unknown_texts)} text_id(s) without a vector")

    # Queries ↔ dataset questions
    qvec = emb.query_vectors()
    if qvec.shape[0] != len(emb.queries) or qvec.shape[1] != vec.shape[1]:
        rep.errors.append(f"query vectors {tuple(qvec.shape)} do not match queries.csv ({len(emb.queries)} rows) "
                          f"or the corpus dimension {vec.shape[1]}")
    qids = emb.queries["query_id"].tolist()
    if sorted(qids) != sorted(ds.question_ids):
        rep.errors.append(f"query ids differ from dataset/questions.jsonl ({len(set(qids) ^ set(ds.question_ids))} "
                          f"differ); re-embed the queries: `embed.py queries --model {emb.slug} "
                          f"--instruction-name {emb.instruction}`")
    else:
        template = emb.query_manifest["model"].get("template") or "{text}"
        instruction = emb.query_manifest["model"].get("instruction") or ""
        qtext = dict(zip(ds.questions["question_number"], ds.questions["question_text"]))
        bad = [q for q, sent in zip(qids, emb.queries["text_sent"])
               if sent != template.replace("{instruction}", instruction).replace("{text}", qtext[q])]
        if bad:
            rep.errors.append(f"{len(bad)} query text(s) differ from question_text (e.g. {bad[:5]}); the "
                              f"questions changed after embedding: re-run `embed.py queries --model {emb.slug} "
                              f"--instruction-name {emb.instruction}`")

    # Vector hashes against the embedding manifests (optional: ~1 s per GB)
    if hash_vectors:
        for kind, man, files in (("corpus", cm, ["vectors.npy", "texts.csv", "chunk_map.csv.gz"]),
                                 ("queries", emb.query_manifest, ["vectors.npy", "queries.csv"])):
            base = emb.corpus_dir if kind == "corpus" else emb.query_dir
            for f in files:
                want = man.get("output", {}).get("sha256", {}).get(f)
                if want and sha256_file(base / f) != want:
                    rep.errors.append(f"{rel(base / f)} SHA-256 differs from its manifest (file changed after "
                                      "the embedding run)")

    # Dataset ↔ corpus
    file_doc = ds.file_to_document()
    doc_ids = set(ds.documents["document_id"])
    gold_docs = {r["document_id"] for r in ds.references if r["document_id"]}
    if gold_docs - doc_ids:
        rep.errors.append(f"{len(gold_docs - doc_ids)} gold document_id(s) not in documents.jsonl: "
                          f"{sorted(gold_docs - doc_ids)[:5]}")
    arquivos = set(chunks["arquivo"])
    unknown_files = sorted(arquivos - set(file_doc))
    if unknown_files:
        rep.warnings.append(f"{len(unknown_files)} chunk file(s) belong to no documents.jsonl row "
                            f"(e.g. {unknown_files[:3]}); their chunks count as non-gold")
    docs_with_chunks = {file_doc[a] for a in arquivos if a in file_doc}
    no_chunks = sorted(doc_ids - docs_with_chunks)
    cited_no_chunks = sorted(set(no_chunks) & gold_docs)
    if cited_no_chunks:
        rep.warnings.append(f"{len(cited_no_chunks)} cited document(s) without chunks (unreachable gold): "
                            f"{', '.join(cited_no_chunks)}")
    rep.info.update({
        "chunks": len(chunks), "unique_texts": int(cmap.loc[cmap["chunk_id"].isin(chunk_ids), "text_id"].nunique()),
        "corpus_vectors": list(vec.shape), "query_vectors": list(qvec.shape), "questions": len(ds.questions),
        "references": len(ds.references),
        "references_not_in_corpus": sum(1 for r in ds.references if not r["document_id"]),
        "documents": len(doc_ids), "documents_without_chunks": len(no_chunks),
        "cited_documents_without_chunks": cited_no_chunks,
    })
    return rep
