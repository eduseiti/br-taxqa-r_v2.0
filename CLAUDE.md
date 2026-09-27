# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Version 2.0 of the [BR-TaxQA-R](https://huggingface.co/datasets/unicamp-dl/BR-TaxQA-R) dataset. The
legal documents referred to by the Q&A source document (`docs/P&R IRPF 2024 - v1.0 - 2024.05.03.pdf`,
Receita Federal's IRPF 2024 "Perguntas e Respostas") have been fetched and parsed to LexML XML,
whether statutory or non-statutory.

It is used for RAG experiments that test whether **hierarchical segmentation** of these documents
gives better chunks for answering the **prose** questions of the Q&A document. System answers are
compared with the gold answers using nuggets. The chosen segmentation strategies (S1 article
baseline, S2 article + ancestor-path sub-units, optional S3 + groupings), the annex rules and the
implementation split are recorded in
`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md`. Read it before working on
segmentation, embedding or retrieval code.

## Folders

- **`docs/`** — the Q&A source PDF and dated notes (audits, design decisions). Check here first
  when the user refers to a previous analysis or decision.
- **`original/`** — the fetched source documents as `.docx`:
  - `articulados/` — statutory documents (laws, decrees, INs, ADEs…), named
    `<type>_<number>_<YYYYMMDD>.docx` (e.g. `lei_9250_19951226.docx`);
  - `nao_articulados/` — non-statutory documents (pareceres, soluções de consulta, court decisions…).
- **`lexml/`** — the LexML XML produced from `original/`:
  - `articulados/` — one `<stem>.xml` per main document (root `ProjetoNorma`) plus one
    `<stem>.anexoN.xml` per annex. Annexes are separate files whose root is `Anexo` →
    `DocumentoArticulado` or `DocumentoGenerico`; segment them **by content** (has `Artigo` /
    orphan dispositivos only / plain text and tables), not by root element. `<stem>.err.log` holds the
    parser command line and output; `skipped_report.txt` lists parse failures.
  - `nao_articulados/` — non-statutory documents, named from their URN
    (`urn_lex_br_<authority>_<type>_<date>_<number>.xml`), root `DocumentoGenerico` with
    `Agrupamento` / `Bloco` / `p` / `table`. Documents that failed statutory parsing may appear here
    under their URN name (e.g. `in_srf_84_19791220` →
    `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1979-12-20_84.xml`).
- **`scripts/`** — code for the experiment pipeline: segmentation (the amended copy of the XSL for
  statutory documents, Python code for non-statutory ones), embedding, RAG and nugget evaluation.
- **`dataset/`** — the v2.0 dataset as HF JSON Lines configs (`questions`, `references`,
  `documents`), built by `scripts/dataset/build_v2_dataset.py`. References point at `original/`
  stems and LexML URNs. Hand-verified corrections to the v1.1 references are in
  `scripts/dataset/reference_overrides.json`; the rationale is in
  `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md`.
- **`segmented/`** — segmentation outputs (chunk CSVs with the
  `Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn` schema) that feed the embedding step.

## Related repositories (siblings under `../`)

- `br-taxqa-document-fetcher/` — builds LexML URNs for the documents referred to in the dataset and
  fetches them as `.docx`; holds the canonical document list
  (`output_canonical/canonical_referred_documents.json`).
- `lexml-parser-projeto-lei/` — statutory `.docx` → LexML parser, plus
  `scripts/GeraCSVporArtigoPorAgrupador.xsl` and `scripts/run_segmentation_csv.py` (the original
  segmentation XSL and its Saxon batch driver). Do not modify the XSL there; amend a copy in `scripts/`.
- `lexml_parser_non_statutory/` — non-statutory `.docx` → LexML parser.
- `lexml-linker/` — Haskell tool that finds references to legislation in text ("art. 8º da Lei nº …")
  and turns them into LexML URNs (the `Remissao` elements in the XML).

## Conventions

**IMPORTANT:** every `.md` file created in `docs/` must be prefixed with a `YYYYMMDD_HHMMSS_`
timestamp taken from the output of `date +%Y%m%d_%H%M%S` at creation time (e.g.
`20260923_193852_segmentation_strategies_for_rag_experiments.md`). `CLAUDE.md` and any `README.md`
are the exceptions.
