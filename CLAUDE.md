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
baseline, S2 article + ancestor-path sub-units (paragraphs without the caput), optional S3 +
groupings, optional S4 = S3 + caput sentence in paragraph chunks (S2c: the same for S2; S5: full
caput, later)), the annex rules and the implementation split are recorded in
`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md`; the caput variants in
`docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md`. Read them before
working on segmentation, embedding or retrieval code. The corpus was last rebuilt end to end on
2026-10-08 (`docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md` and its results note).

**Nuggetization** (gold answers → nuggets, and later scoring of system answers) is designed in
`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`. The preview (10 questions) and the
**phase 1 pilot** (`stratified_30`, `docs/20261012_192640_nuggetization_phase1_pilot.md`) are done;
the phase 1 gate is closed (`create_v4`, one call, thresholds in
`docs/20261013_103834_nuggetization_open_decisions.md`, which also tracks the open decisions). **Phases 2–4 are
done** (`docs/20261021_155704_nuggetization_phases_2_to_4_execution.md`; frozen set `nuggets/gold/v0-auto/`);
phase 5 (scoring) is done (`docs/20261023_210727_rag_phase5_scoring_and_analysis.md`). Start from `scripts/nuggets/README.md`
(status, commands, current prompts `create_v4` / `assign_v2`, budget cap, what is still missing); the
decisions and costs are in the `docs/20261012_*nuggetization*` notes. All LLM calls go through **OpenRouter** by default
(`--route openrouter`, one key `OPENROUTER_API_KEY`, flex endpoints for GPT/Gemini;
`docs/20261020_130829_openrouter_support_plan.md`); the preview and pilot runs used `--route direct`.
**Costs are tracked for the paper:** pass
`--budget` on every LLM run, and stop and report to the user before continuing if anything costs more
than expected.

## Folders

- **`docs/`** — the Q&A source PDF and dated notes (audits, design decisions). Check here first
  when the user refers to a previous analysis or decision.
- **`original/`** — the fetched source documents as `.docx`:
  - `articulados/` — statutory documents (laws, decrees, INs, ADEs…), named
    `<type>_<number>_<YYYYMMDD>.docx` (e.g. `lei_9250_19951226.docx`);
  - `nao_articulados/` — non-statutory documents (pareceres, soluções de consulta, court decisions…),
    as `.docx` or, for 12 soluções de consulta, born-digital `.pdf`.
- **`lexml/`** — the LexML XML produced from `original/`:
  - `articulados/` — one `<stem>.xml` per main document (root `ProjetoNorma`) plus one
    `<stem>.anexoN.xml` per annex. Annexes are separate files whose root is `Anexo` →
    `DocumentoArticulado` or `DocumentoGenerico`; segment them **by content** (has `Artigo` /
    orphan dispositivos only / plain text and tables), not by root element. `<stem>.err.log` holds the
    parser command line and output; `skipped_report.txt` lists parse failures.
  - `nao_articulados/` — non-statutory documents, named from their URN
    (`urn_lex_br_<authority>_<type>_<date>_<number>.xml`), root `DocumentoGenerico` with
    `Agrupamento` / `Bloco` / `p` / `table`. Every URN is **declared** in
    `scripts/lexml/nonstat_metadata.tsv` (stem → URN) and passed to the parser with `--metadata`;
    `scripts/dataset/nonstat_lexml_map.tsv` (stem → XML file) is generated from this folder.
    `_text/` holds the cleaned text of the PDF sources (the parser input). Each folder has a
    `PARSER_VERSION` file with the parser commit and command line.
- **`scripts/`** — code for the experiment pipeline: `lexml/` (corpus preparation: PDF → text,
  `.docx` repairs, declared URNs, article-coverage audit), segmentation (the amended copy of the XSL
  for statutory documents, Python code for non-statutory ones), embedding, RAG (`rag/`), nugget
  creation and evaluation (`nuggets/`), and the LLM client shared by them (`llm_client/`).
- **`dataset/`** — the v2.0 dataset as HF JSON Lines configs (`questions`, `references`,
  `documents`), built by `scripts/dataset/build_v2_dataset.py`. References point at `original/`
  stems and LexML URNs. Hand-verified corrections to the v1.1 references are in
  `scripts/dataset/reference_overrides.json`; the rationale is in
  `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md`.
- **`runs/`** — RAG pipeline outputs (`scripts/rag/rag.py`): `retrieval/<embedding>/<instruction>/`
  holds the rankings per strategy and `eval/<eval_id>/` the legal-provision retrieval test
  (`report.md`, `metrics.csv`). Only manifests and small result files are in git. Rankings and
  per-question tables are regenerated in about 30 s (`retrieve` + `evaluate`). `contexts/<embedding>/<instruction>/`
  holds the generator contexts (RAG Phase 2, `rag.py context`, ≈ 70 s; `summary.csv` and manifests in git):
  `docs/20261021_210251_rag_phase2_contexts_execution.md`. The main run `irpf` excludes the revoked documents listed
  in `scripts/rag/corpus_exclusions.yaml` (now the RIR/1999); `irpf_with_rir1999` is the run without exclusions
  (`docs/20261022_203625_corpus_exclusion_revoked_rir1999.md`). `answers/<embedding>/<instruction>/<prompt>/<llm>/<context_id>/`
  holds the generated answers (RAG Phase 3, `rag.py run --experiment scripts/rag/experiments/pilot.yaml`; generators in
  `scripts/rag/llms.yaml`: Sabiá-4 / Sabiazinho-4 on Maritaca, GPT-5.6 Terra / Luna on OpenRouter; `answers.jsonl`,
  `run.json`, `summary.csv` in git, raw responses in `answers/cache/` not); `runs/costs.csv` is the RAG cost ledger.
  Pilot (`stratified_30`, 14 sets × 4 generators, $5.59) and full-run costs: `docs/20261023_110952_rag_phase3_generation_pilot.md`;
  the budget ($150 OpenRouter for the whole experiment), the **trimmed grid** of the first full evaluation and its
  stages: `docs/20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md`. Generation of the
  trimmed grid on all 715 questions is done (`experiments/full_stage1.yaml`, `full_stage2.yaml`, 25 runs, $41.95):
  `docs/20261023_151928_rag_phase3_trimmed_full_generation.md`. Scoring (nugget phase 5: `nuggets.py score`,
  `ctxsupport`, `scoretable`, `analyze`; outputs in `nuggets/scoring/`, $55.96) and the first full analysis are done:
  `docs/20261023_210727_rag_phase5_scoring_and_analysis.md` (S2 > S1 by +0.02–0.03 V_strict, robust; S3/S2c/S4 ≈ S2;
  next: stages 3–4, §9 there). How the retrieval test scores chunks of a granularity other than the gold's
  (S1 vs sub-article units, S2 at the article vs the provision level) and the S1/S2 answer gap by citation
  granularity (S2 helps on sub-article questions, ≈ 0 on whole-article ones), and S3's grouping chunks (no
  document-level gain; whole-article gain grows with the budget):
  `docs/20261122_130934_retrieval_scoring_granularity_and_answer_quality.md`. Plan (not implemented) for scoring the
  legal citations generators write in their answers (closed book and RAG) against the gold references, and how
  closed-book runs were kept free of web search: `docs/20261122_134404_in_text_legal_citation_scoring_plan.md`.
  **Next additions (plan, 2026-11-22):** fix B first, then a token-weighted provision metric, in-text citations
  and GPT-6.2 Sol (Terra's 4 conditions), with costs and budget check:
  `docs/20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md`. **A1 (token-weighted
  metric) is done:** `rag.py evaluate --token-metrics` → eval id `v3_either_containment_merge_skip` (now the dashboard's),
  unit tokens `segmented/unit_tokens.csv.gz` (`scripts/segmentation/unit_tokens.py`), analyses
  `scripts/report/a1_token_metrics.py`; results `docs/20261122_192653_a1_token_weighted_provision_metric_results.md`.
  **A2 (in-text legal citations) is done:** `nuggets.py intext` (`nuggetizer/intext_citations.py`, no API calls, ≈ 40 s)
  → `nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/intext/`; results
  `docs/20261122_194659_a2_in_text_legal_citations_results.md`. **A3 (GPT-6.2 Sol, Terra's 4 conditions) is done:** OpenRouter Batch API
  (`rag.py run --experiment scripts/rag/experiments/sol.yaml --batch [--batch-max N]`, `rag.py batch wait`, rerun
  without `--batch`; `llm_client/batch.py`), analyses `scripts/report/a3_sol_analysis.py`; results and costs ($18.41)
  `docs/20261122_205115_a3_gpt_6_2_sol_results.md`; dashboards and HF repo B (`74fc95f`) include Sol. Report with Sol
  on granularity + token metric, closed-book citations vs retrieval, and answer quality at 4k (closed book vs RAG):
  `docs/20261122_231441_results_with_sol_granularity_citations_and_answer_quality.md` (`scripts/report/make_sol_report.py`,
  `python3`, no API calls).
  **Hugging Face release:** plan and status in
  `docs/20261024_180016_hugging_face_release_plan.md` (§9: both repos staged private under `eduseiti` on 2026-10-24),
  tooling in `scripts/release/` (`build_release.py`, `push_release.py`, token `HF_RELEASE_TOKEN`), record in
  `release/hf_release.json`; the Gemini outputs were added to repo B on 2026-11-08
(`docs/20261108_231904_hugging_face_update_gemini_embedding_2.md`). **Second embedding (gemini-embedding-2 via OpenRouter, `embed.py` provider `openrouter`):**
  plan `docs/20261108_153258_gemini_embedding_2_comparison_plan.md`, results
  `docs/20261108_175117_gemini_embedding_2_setup_embedding_and_retrieval_gate.md`. Outputs sit under
  `<…>/gemini-emb-2/`; in the nugget tables its runs are `<context_id>@gemini-emb-2` (`scoring.context_key`). `rag.py` does not
  read `.env`: run `set -a; . ./.env; set +a` first.
  **Results dashboard:** `docs/dashboard/index.html` (static, opens from file://), data rebuilt by
  `scripts/report/build_dashboard_data.py` (no API calls); see `docs/20261109_123355_results_dashboard.md`. Its
  **question trace** tab (8; one question through nuggets → documents → ranking → context/prompt → answer) has its
  own data, `scripts/report/build_trace_data.py` (≈ 7 min, gitignored `docs/dashboard/data/trace/`):
  `docs/20261110_194056_question_trace_dashboard_implementation.md`. On other computers, restore it from the HF eval repo
  (`raw/dashboard_trace.tar.gz`, `docs/20261115_141728_hugging_face_update_dashboard_trace.md`).
  **Corpus & question explorer** (the newer dashboard; the results dashboard is kept as a reference):
  `docs/explorer/index.html`, built on the trace data plus `scripts/report/build_explorer_data.py` (≈ 20 s, gitignored
  `docs/explorer/data/`): `docs/20261115_145149_corpus_and_question_explorer.md`.
- **`nuggets/`** — nugget pipeline outputs (`scripts/nuggets/nuggets.py`), one folder per run
  (`preview/`, `preview_v2/`, `preview_v3/`; `pilot/` next): nuggets, validation, self-score
  labels, the cost ledger `costs.csv` and `report.md`. Raw API responses (`cache/`) and the input
  copy (`input/`) are gitignored; the caches are backed up outside git (see `scripts/nuggets/README.md`).
- **`segmented/`** — segmentation outputs (chunk CSVs with the
  `Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn` schema) that feed the embedding step.

## Corpus revision (fix B): done 2026-11-22

The parser had turned some citation lines and headings into fake `Art. N` chunks (found on 2026-11-15; fix A worked
around them in the matcher). **Fix B repaired the corpus and released it on 2026-11-22**:
- the parser fix (`d6e2549`) and `.docx` repairs (`scripts/lexml/repair_docx.py`);
- the audit's new checks;
- re-segmentation, re-embedding, reruns and rescoring;
- HF repos A `5886f9a` and B `4ea3a09`.

The chunk exclusions are empty, and the chunk ids of the 15 changed files were renumbered. Results:
`docs/20261122_181611_fix_b_corpus_revision_results.md`.

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
