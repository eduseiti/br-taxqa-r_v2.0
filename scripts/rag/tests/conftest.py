"""Shared fixtures: a tiny repository layout under tmp_path (chunks, dataset, embeddings with random
normalized vectors). No network, no GPU.

Corpus (``Num_Inicio``/``Num_Final`` in brackets):

    lei_1_20000101.xml            CAP cap1 [1,20] ⊃ art1, art2
      art1  ART [1,10]  CPT art1_cpt [2,5]  INC art1_cpt_inc1 [3,4]  PAR art1_par1 [6,9]
      art2  ART parte 1/2 [11,15] (cobre art2_cpt_inc1;art2_cpt_inc2), parte 2/2 [16,19] (art2_par1)
            INC art2_cpt_inc1 [12,13]
      art3  ART [21,22] and INC art3_cpt_inc1 [21,22] with the same text (an alias)
    decreto_9_20000101.xml        art1 ART [1,2]
    decreto_9_20000101.anexo1.xml (categoria A) art1 ART [1,4], art5 ART [5,6]
    urn_x.xml                     non-statutory: TXT pp1 [1,2], TXT pp2 [3,4]
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ragpipe.data import Paths  # noqa: E402

DIM = 8
TEMPLATE = "Instruct: {instruction}\nQuery: {text}"
INSTRUCTION = "Find IRPF provisions"

L, D, A, X = "lei_1_20000101.xml", "decreto_9_20000101.xml", "decreto_9_20000101.anexo1.xml", "urn_x.xml"

# Tipo, arquivo, categoria, unidade_id, artigo_id, start, end, parte, n_partes, cobre, parcial, tokens, text
CHUNKS = [
    ("ART", L, "main", "art1", "art1", 1, 10, 1, 1, "art1", "", 400, "Art. 1 inteiro"),
    ("CPT", L, "main", "art1_cpt", "art1", 2, 5, 1, 1, "art1_cpt", "", 150, "Art. 1 caput"),
    ("INC", L, "main", "art1_cpt_inc1", "art1", 3, 4, 1, 1, "art1_cpt_inc1", "", 60, "Art. 1 inciso I"),
    ("PAR", L, "main", "art1_par1", "art1", 6, 9, 1, 1, "art1_par1", "", 120, "Art. 1 § 1"),
    ("ART", L, "main", "art2", "art2", 11, 15, 1, 2, "art2_cpt_inc1;art2_cpt_inc2", "art2;art2_cpt", 300,
     "Art. 2 parte 1"),
    ("ART", L, "main", "art2", "art2", 16, 19, 2, 2, "art2_par1", "art2;art2_cpt", 200, "Art. 2 parte 2"),
    ("INC", L, "main", "art2_cpt_inc1", "art2", 12, 13, 1, 1, "art2_cpt_inc1", "", 50, "Art. 2 inciso I"),
    ("ART", L, "main", "art3", "art3", 21, 22, 1, 1, "art3", "", 80, "Art. 3 único inciso"),
    ("INC", L, "main", "art3_cpt_inc1", "art3", 21, 22, 1, 1, "art3_cpt_inc1", "", 80, "Art. 3 único inciso"),
    ("CAP", L, "main", "cap1", "", 1, 20, 1, 1, "cap1", "", 1200, "Capítulo I inteiro"),
    ("ART", D, "main", "art1", "art1", 1, 2, 1, 1, "art1", "", 90, "Decreto art. 1 aprova o regulamento"),
    ("ART", A, "A", "art1", "art1", 1, 4, 1, 1, "art1", "", 110, "Regulamento art. 1"),
    ("ART", A, "A", "art5", "art5", 5, 6, 1, 1, "art5", "", 70, "Regulamento art. 5"),
    ("TXT", X, "nao_articulado", "pp1", "", 1, 2, 1, 1, "pp1", "", 100, "Parecer parte 1"),
    ("TXT", X, "nao_articulado", "pp2", "", 3, 4, 1, 1, "pp2", "", 100, "Parecer parte 2"),
]

QUESTIONS = [("001", "Qual a regra do inciso I do art. 1?"), ("002", "O que diz o art. 2?"),
             ("003", "E o regulamento?"), ("004", "Pergunta sem referência")]

REFERENCES = [
    # question, origin, document_id, article_ids, provisions [(fragment, article, file)]
    ("001", "explicit", "lei_1_20000101", ["art1"], [("art1_cpt_inc1", "art1", L)]),
    ("002", "explicit", "lei_1_20000101", ["art2"], [("art2", "art2", L)]),
    ("003", "explicit", "decreto_9_20000101", ["art1", "art5"], [("art1", "art1", D), ("art5", "art5", A)]),
    ("003", "embedded", "urn_x", [], []),
    ("003", "explicit", None, [], []),
]


def text_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_frame() -> pd.DataFrame:
    rows = []
    counters: dict[str, int] = {}
    for tipo, arq, cat, uid, art, s, e, parte, n, cobre, parcial, tok, text in CHUNKS:
        stem = arq[:-4]
        counters[stem] = counters.get(stem, 0) + 1
        rows.append({"Tipo": tipo, "Rotulo": f"{stem}, {uid}", "Num_Inicio": s, "Num_Final": e, "Texto": text,
                     "urn": f"urn:{stem}!{uid}", "arquivo": arq, "segmentador": "xsl", "categoria": cat,
                     "chunk_id": f"{stem}#{counters[stem]}", "doc_urn": f"urn:{stem}", "anexo_urn": "",
                     "nivel": tipo, "unidade_id": uid, "artigo_id": art, "agrupadores_ids": "",
                     "agrupadores_rotulos": "", "citacao": uid, "parte": parte, "n_partes": n, "cobre_ids": cobre,
                     "parcial_ids": parcial, "id_ambiguo": 0, "n_tokens": tok, "n_tokens_cl100k": tok,
                     "n_tokens_qwen3": tok, "texto_sha256": text_id(text)})
    return pd.DataFrame(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def normalized(rng: np.random.Generator, n: int) -> np.ndarray:
    v = rng.normal(size=(n, DIM)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


@pytest.fixture
def repo(tmp_path: Path) -> Paths:
    """A complete fixture repository; returns its :class:`Paths`."""
    rng = np.random.default_rng(0)
    (tmp_path / "segmented").mkdir()
    chunks = chunk_frame()
    chunks_path = tmp_path / "segmented" / "chunks_all.csv.gz"
    with gzip.open(chunks_path, "wt", encoding="utf-8") as fh:
        chunks.to_csv(fh, index=False)

    ds = tmp_path / "dataset"
    ds.mkdir()
    write_jsonl(ds / "questions.jsonl", [{"question_number": q, "question_summary": "", "question_text": t,
                                          "answer": "", "answer_cleaned": ""} for q, t in QUESTIONS])
    refs = []
    for i, (q, origin, doc, arts, provs) in enumerate(REFERENCES):
        refs.append({"reference_id": f"{q}-{i:02d}", "question_number": q, "origin": origin, "cited_title": doc,
                     "document_id": doc, "article_ids": arts,
                     "provisions": [{"label": f, "article_id": a, "fragment_id": f, "annex": None,
                                     "lexml_file": f"lexml/articulados/{fl}"} for f, a, fl in provs]})
    write_jsonl(ds / "references.jsonl", refs)
    write_jsonl(ds / "documents.jsonl", [
        {"document_id": "lei_1_20000101", "statutory": True, "lexml_file": f"lexml/articulados/{L}",
         "lexml_annex_files": []},
        {"document_id": "decreto_9_20000101", "statutory": True, "lexml_file": f"lexml/articulados/{D}",
         "lexml_annex_files": [f"lexml/articulados/{A}"]},
        {"document_id": "urn_x", "statutory": False, "lexml_file": f"lexml/nao_articulados/{X}",
         "lexml_annex_files": []},
        {"document_id": "lei_empty", "statutory": True, "lexml_file": "lexml/articulados/lei_empty.xml",
         "lexml_annex_files": []},
    ])

    # Embeddings: one vector per unique text; each question's vector equals the vector of one text
    corpus = tmp_path / "embeddings" / "fake" / "corpus"
    queries = tmp_path / "embeddings" / "fake" / "queries" / "irpf"
    corpus.mkdir(parents=True)
    queries.mkdir(parents=True)
    tids = sorted({text_id(t) for t in chunks["Texto"]})
    pd.DataFrame({"row": range(len(tids)), "text_id": tids, "n_tokens": 10}).to_csv(corpus / "texts.csv", index=False)
    with gzip.open(corpus / "chunk_map.csv.gz", "wt") as fh:
        pd.DataFrame({"chunk_id": chunks["chunk_id"], "text_id": chunks["texto_sha256"]}).to_csv(fh, index=False)
    V = normalized(rng, len(tids))
    np.save(corpus / "vectors.npy", V)
    target = {"001": "Art. 1 inciso I", "002": "Art. 2 parte 1", "003": "Regulamento art. 5", "004": "Parecer parte 1"}
    Q = np.stack([V[tids.index(text_id(target[q]))] for q, _ in QUESTIONS])
    np.save(queries / "vectors.npy", Q)
    sent = [TEMPLATE.replace("{instruction}", INSTRUCTION).replace("{text}", t) for _, t in QUESTIONS]
    pd.DataFrame({"row": range(len(QUESTIONS)), "query_id": [q for q, _ in QUESTIONS], "n_tokens": 10,
                  "text_sent": sent}).to_csv(queries / "queries.csv", index=False)
    model = {"slug": "fake", "model_id": "fake/model", "dim": DIM}
    (corpus / "manifest.json").write_text(json.dumps({
        "model": {**model, "template": "{text}"},
        "input": {"sha256": sha256(chunks_path)},
        "output": {"shape": [len(tids), DIM], "sha256": {f: sha256(corpus / f) for f in
                                                         ("vectors.npy", "texts.csv", "chunk_map.csv.gz")}}}))
    (queries / "manifest.json").write_text(json.dumps({
        "model": {**model, "template": TEMPLATE, "instruction_name": "irpf", "instruction": INSTRUCTION},
        "output": {"sha256": {f: sha256(queries / f) for f in ("vectors.npy", "queries.csv")}}}))

    rag = HERE.parent
    shutil.copy(rag / "strategies.yaml", tmp_path / "strategies.yaml")
    (tmp_path / "chapters.csv").write_text("first_question,last_question,chapter\n001,002,A\n003,004,B\n")
    return Paths(repo=tmp_path, chunks=chunks_path, dataset=ds, embeddings=tmp_path / "embeddings",
                 runs=tmp_path / "runs", strategies=tmp_path / "strategies.yaml", chapters=tmp_path / "chapters.csv",
                 exclusions=None)
