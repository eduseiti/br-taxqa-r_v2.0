# Hugging Face release plan: BR-TaxQA-R v2.0 dataset and the RAG evaluation data

Date: 2026-10-24. Status: **plan, nothing uploaded yet.** Every upload, visibility change, tag
or repo move below is an outward-facing step. Each one waits for the user's go-ahead.

This plan covers what goes to the Hugging Face Hub, how it is described (dataset cards, configs,
licenses), and how to deploy it: first under the personal account `eduseiti`, then under the
`unicamp-dl` organization. The user is a member of the organization (checked with `whoami` on
2026-10-24; the token in `.env` is fine-grained). Earlier notes already decided that bulk outputs
go to the Hub and only provenance stays in git: embedding plan §4.2
(`20260925_122058_*`), RAG plan §5 (`20260927_204356_*`), nugget plan v2 D10 (`20261011_224049_*`),
and the nugget cache resolution §3.2 (`20261012_154616_*`). This note puts those decisions into one
release.

---

## 1. Summary of decisions

| # | Decision | Proposal |
|---|---|---|
| R1 | Number of repos | **Two public dataset repos**: (A) the **benchmark** (questions, references, corpus, chunks, gold nuggets), (B) the **evaluation data** (embeddings, rankings, contexts, answers, scores, raw LLM responses). A is small (≈ 130 MB) and is what most users want. B is ≈ 1.3 GB and is for reproduction and further analysis. |
| R2 | Final names | A = **`unicamp-dl/BR-TaxQA-R`**, as revision v2.0 of the existing repo (v1.1 is kept under the tag `v1.1`). B = **`unicamp-dl/BR-TaxQA-R-RAG-eval`** (new). |
| R3 | Staging | Both are first built as **private** repos under `eduseiti`: `eduseiti/BR-TaxQA-R` and `eduseiti/BR-TaxQA-R-RAG-eval`. Validation (§6.3) runs there. |
| R4 | Moving to the org | B: **move** the repo (`HfApi.move_repo`). The history is kept and the old URL redirects. A: the target repo already exists, so a move cannot merge into it. **Re-upload** the validated tree to `unicamp-dl/BR-TaxQA-R` as one commit, then tag it `v2.0`. |
| R5 | File layout | **Mirror the GitHub repo paths** (`dataset/`, `original/`, `lexml/`, `segmented/`, `nuggets/`, `runs/`, `embeddings/`). Then `documents.jsonl`'s `original_file` / `lexml_file` paths resolve inside the HF repo too. `hf download … --local-dir .` in a checkout of the code gives back the state that `rag.py` and `nuggets.py` expect. The config `data_files` point into these paths. |
| R6 | File formats | Keep the native formats (JSONL, CSV(.gz), NPY, XML, DOCX/PDF). The Hub viewer converts JSONL/CSV configs to Parquet by itself (`refs/convert/parquet`). Raw LLM caches (≈ 51k small JSON files) are packed as `tar.gz` per cache, because the Hub handles many small files poorly. |
| R7 | License | **CC BY 4.0** for both, as in v1.1. The legal texts are not protected by copyright in Brazil (Lei 9.610/1998, art. 8º, IV). The embedding model `ufca-llms/jua-4B-mixed` is MIT. Provider terms for LLM outputs are to be checked (§7, C5). |
| R8 | Versioning | Git tag `v2.0` on GitHub and HF tags `v2.0` on both repos, pointing at the same content. `release/hf_release.json` in git records the HF commit SHAs (§6.4). The code stays on GitHub (`eduseiti/br-taxqa-r_v2.0`), and the cards link to it. |

---

## 2. Repo A: the benchmark, `BR-TaxQA-R` v2.0

### 2.1 Files

| Path in the HF repo | Source in git repo | Size | Content |
|---|---|---:|---|
| `README.md` | new; based on `dataset/README.md` | — | dataset card (§2.3) |
| `dataset/questions.jsonl` | `dataset/` | 2.1 MB | 715 questions, gold answers (`answer_cleaned`), linked questions, raw reference text, cited `document_ids` |
| `dataset/references.jsonl` | `dataset/` | 1.6 MB | 1,916 rows, one per cited act per question: resolution to a corpus document and URN, cited articles and `fragment_id`s (`provisions`) |
| `dataset/documents.jsonl` | `dataset/` | 0.24 MB | 453 corpus documents: URN, title, statutory flag, paths to `original/` and `lexml/` files, number of citing questions |
| `dataset/build_report.json` | `dataset/` | 14 KB | build counts, dropped and unresolved references, answer overrides, validation |
| `dataset/reference_overrides.json`, `dataset/answer_overrides.json` | `scripts/dataset/` | small | hand-verified corrections to v1.1 (references, gold answers) and why each was made |
| `nuggets/v0-auto/nuggets.jsonl` | `nuggets/gold/v0-auto/` | 3.0 MB | **gold nuggets**: 3,175 atomic facts of the gold answers (`importance` vital/okay, `category`, `values`, `source_span`, audit flags, `stability`) |
| `nuggets/v0-auto/manifest.json` | same | 331 B | how the set was frozen (source run, auditors, counts, route) |
| `original/articulados/*.docx` | `original/` | 14 MB | 209 statutory source documents as fetched |
| `original/nao_articulados/*.{docx,pdf}` | `original/` | 19 MB | 244 non-statutory source documents (12 born-digital PDFs) |
| `lexml/articulados/*.xml` (+ `PARSER_VERSION`, `skipped_report.txt`) | `lexml/` | 43 MB | LexML XML of the statutory documents: one main file plus one file per annex. `*.err.log` stays out (local paths, parser noise) |
| `lexml/nao_articulados/*.xml` (+ `PARSER_VERSION`) | `lexml/` | 6 MB | LexML XML of the non-statutory documents (`DocumentoGenerico`). `_text/` is included: it is the parser input for the PDF sources |
| `segmented/chunks_all.csv.gz` | `segmented/` | 19 MB | **all chunks of all strategies** (104,574 rows; S1 21,497, S2/S2c 73,118, S3/S4 77,080), with `chunk_id`, `urn`, `Rotulo`, `Texto`, `n_tokens`, `variante` … |
| `segmented/README.md`, `segmentation_report.{md,json}`, `annex_manifest.csv`, `groupings_over_limit.csv` | `segmented/` | 0.4 MB | strategy definitions with examples, validation, annex treatment, S3/S4 groupings left out |
| `docs/P&R IRPF 2024 - v1.0 - 2024.05.03.pdf` | `docs/` | — | the Receita Federal source of the questions |
| `LICENSE` | new | — | CC BY 4.0 text plus the note on the legal texts |
| `SHA256SUMS` | generated | — | checksum of every file (§6.1) |

Not included: `segmented/chunks_all.csv` (the uncompressed copy), and `segmented/statutory/`
and `non_statutory/` per-document CSVs (99 + 9 MB). They are the same rows as `chunks_all`
(audit `20261021_165327_*`). Leaving them out avoids ≈ 700 small files that only duplicate it.
The v1.1 files (`BR-TaxQA-R.py`, `questions_QA_2024_v1.1.json`,
`referred_legal_documents_QA_2024_v1.1.json`, `acordaos_CARF_2023.json`) are **removed from
`main`** and stay reachable under the tag `v1.1`. The card says how to load it
(`revision="v1.1"`).

Total ≈ 130 MB and ≈ 1,300 files (most of them the `original/` and `lexml/` corpus).

### 2.2 Configs (viewer and `load_dataset`)

```yaml
configs:
- config_name: questions          # default
  default: true
  data_files: [{split: test, path: dataset/questions.jsonl}]
- config_name: references
  data_files: [{split: test, path: dataset/references.jsonl}]
- config_name: documents
  data_files: [{split: test, path: dataset/documents.jsonl}]
- config_name: nuggets
  data_files: [{split: test, path: nuggets/v0-auto/nuggets.jsonl}]
- config_name: chunks
  data_files: [{split: corpus, path: segmented/chunks_all.csv.gz}]
```

`chunks` has mixed-type columns (`Num_Inicio`, ids that look like numbers). Before publishing,
check that the viewer and `load_dataset(..., "chunks")` read it. If they don't, add an explicit
`features:` block or publish a Parquet copy `segmented/chunks_all.parquet` with string dtypes for
the config. The CSV stays for the scripts.

### 2.3 Card (`README.md`)

YAML header: `license: cc-by-4.0`, `language: [pt]`, `pretty_name: BR-TaxQA-R v2.0`,
`task_categories: [question-answering, text-retrieval]`, `task_ids: [open-domain-qa,
document-retrieval]`, `size_categories: 1K<n<10K` (questions; the chunks are 100K<n<1M),
`tags: [legal, tax, brazil, portuguese, rag, lexml, nuggets]`, `annotations_creators:
[expert-generated, machine-generated]` (gold answers by Receita Federal, nuggets by LLM),
`source_datasets: [unicamp-dl/BR-TaxQA-R]`, and the `configs:` block of §2.2.

Sections:
1. **Summary.** 715 IRPF 2024 questions with gold answers and resolved legal references, a
   453-document legal corpus in LexML, five segmentation strategies, and gold nuggets for
   nugget-based evaluation of generated answers.
2. **What's new in v2.0.** The current "Changes from v1.1" section of `dataset/README.md`, plus
   the corpus, the chunks and the nuggets.
3. **Configs and schemas.** The field tables of `dataset/README.md`, plus `nuggets` (from
   `scripts/nuggets/README.md`) and `chunks` (from `segmented/README.md`).
4. **Corpus files.** The `original/` and `lexml/` layout, how annexes are stored, URNs, and
   `PARSER_VERSION`.
5. **Segmentation strategies.** The S1–S4 table and how to filter `chunks_all` per strategy
   (`scripts/segmentation/strategies.py` on GitHub).
6. **Gold nuggets.** How they were made (`create_v4`, GPT-5 family creator, two auditors,
   freeze), the counts, what `stability` and the flags mean, and known limits (machine-generated,
   not human-verified; `has_pointer` answers).
7. **Usage.** `load_dataset` per config, `hf_hub_download` for a LexML file, and `snapshot_download`
   into a code checkout.
8. **Companion repo.** Link to `BR-TaxQA-R-RAG-eval`.
9. **License and sources.** CC BY 4.0, the Receita Federal source, and the public-domain status of
   legal texts.
10. **Citation.** v1.1 paper BibTeX, plus the v2.0 paper when available.
11. **Versions.** `v1.1` (tag) and `v2.0`.

---

## 3. Repo B: the evaluation data, `BR-TaxQA-R-RAG-eval`

### 3.1 Files

**Embeddings** (`jua-4b-mixed` = `ufca-llms/jua-4B-mixed` @ `57f491c`, TEI float16 serving,
2,560 dims)

| Path | Size | Content |
|---|---:|---|
| `embeddings/jua-4b-mixed/corpus/vectors.npy` | 1.04 GB | float32 (101,943 × 2,560), one row per distinct chunk text (`text_id`); `np.load(..., mmap_mode="r")` |
| `embeddings/jua-4b-mixed/corpus/texts.csv` | 2.7 MB | row → `text_id`, text hash, tokens |
| `embeddings/jua-4b-mixed/corpus/chunk_map.csv.gz` | 1.4 MB | `chunk_id` (all strategies) → `text_id` |
| `embeddings/jua-4b-mixed/queries/irpf/{vectors.npy,queries.csv}` | 7.5 MB | 715 query vectors with the instruction `irpf` |
| `…/manifest.json` (corpus, queries), `parity.json`, `check.json`, `endpoint_meter.jsonl`, `embeddings/costs.csv` | small | provenance: model revision, templates, endpoint, parity check, cost |

Not included: `corpus_prev_20260926/` (superseded), `run.log`. A float16 copy (≈ 520 MB) is
optional (embedding plan D6). The proposal is not to publish it, because float32 is canonical
and the repo stays smaller.

**Retrieval** (`runs/retrieval/jua-4b-mixed/<run>/`; `<run>` = `irpf` main, without the revoked
RIR/1999, and `irpf_with_rir1999`)

| Path | Size | Content |
|---|---:|---|
| `<run>/<S>/rankings.csv.gz`, S ∈ {S1, S2, S2c, S3, S4} | ≈ 15 MB each | ranked chunks per question (`question_number, rank, text_id, chunk_id, alias_chunk_ids, score`) |
| `<run>/manifest.json` | small | embedding, exclusions, k |
| `<run>/eval/<eval_id>/` | ≈ 8 MB each | legal-provision retrieval test: `report.md`, `metrics.csv`, `comparisons.csv`, `reachability.csv`, `per_question.csv.gz`, `per_item.csv.gz`, `metrics_by_chapter.csv.gz`, `manifest.json` |

All four `eval_id`s of `irpf` are included. They are the metric variants described in
`20261013_111626_*`.

**Generator contexts** (`runs/contexts/jua-4b-mixed/<run>/<context_id>/contexts.jsonl.gz` +
`manifest.json`, plus `summary.csv` per run; 30 + 27 MB). There are 15 context sets in `irpf`:
`closed_book`, `oracle_budget{4000,16000}`, `S1_budget{2000,4000,8000}`,
`S2_budget{2000,4000,8000}`, `S2_budget4000_context_v1`, `S2c/S3/S4_budget4000`,
`wrong-S2_budget4000`. Each row is one question: the rendered `context`, the `items` (chunk ids,
ranks, tokens) and the `gold` coverage.

**Generated answers** (`runs/answers/jua-4b-mixed/irpf/<prompt>/<llm>/<context_id>/answers.jsonl`
+ `run.json`; 62 MB). LLMs: `sabia-4`, `sabiazinho-4`, `gpt-5.6-terra`, `gpt-5.6-luna`. Prompts:
`answer_v1` and `answer_closed_v1`. There are **25 full runs** (715 questions) of the trimmed grid,
and **31 pilot-only** sets (30 questions of `stratified_30`). Each row has the answer, claims,
cited chunk ids, the abstention flag, checks, usage and cost, and the `cache_key` of the raw
response. `runs/costs.csv` (2 MB) is the generation cost ledger.

**Nugget runs and scoring** (`nuggets/`, without `cache/` and `input/`)

| Path | Size | Content |
|---|---:|---|
| `nuggets/full/` (`create/`, `selfscore/`, `align/`, `audit/`, `known/`, `roundtrip/`, `report_full.md`, `costs.csv`, `sample.json`) | 48 MB | phases 2–4: the nugget sets of the three creators and their replicas, self-scores, alignments, audits, known-answer tests. This is where `v0-auto` comes from |
| `nuggets/pilot/`, `nuggets/preview*/`, `nuggets/parity_openrouter/` | 8 MB | phase 1 pilot, the three previews, and the direct-vs-OpenRouter parity check. Provenance for the prompt decisions |
| `nuggets/scoring/score/<nuggets>/<judge>/…/labels.jsonl` (+ `calls.jsonl`, `manifest.json`) | 30 MB | **per-answer nugget labels** (support / partial / contradicts / not_mentioned …) for every answer set, judge `gemini-3.8-flash`. Also the second judge `gemini-3.1-pro` and the alternative nugget sets `gemini-3.1-pro.rep0`, `qwen3.8-max.rep0` |
| `nuggets/scoring/ctxsupport/…` | 3.6 MB | whether each context supports each nugget |
| `nuggets/scoring/ctxaudit/gold-v0-auto/stratified_70/` | 2.8 MB | audit of nuggets not supported by the corpus (`20261024_*` investigation) |
| `nuggets/scoring/tables/…` | 0.4 MB | **result tables**: `runs.csv` (V_strict, V, A_strict, A, W, contradicts, abstained per run), `comparisons.csv`, `per_question.csv.gz`, `ctxsupport_*` |
| `nuggets/scoring/analysis/…` | 0.8 MB | the phase 5 analyses (chapters, citations, linkage, perturbation, judge agreement, values) |
| `nuggets/scoring/costs.csv` | 5.3 MB | scoring cost ledger |

`probe_openrouter/` (a connectivity probe) stays out.

**Raw LLM responses** (`raw/`; the only exact record of non-deterministic outputs, and what makes
reruns free and reproducible)

| Path | Files packed | Unpacked | Restores |
|---|---:|---:|---|
| `raw/runs_answers_cache.tar.gz` | 15,874 | 301 MB | `runs/answers/cache/` |
| `raw/nuggets_full_cache.tar.gz` | 12,519 | 246 MB | `nuggets/full/cache/` |
| `raw/nuggets_scoring_cache.tar.gz` | 22,688 | 444 MB | `nuggets/scoring/cache/` |
| `raw/nuggets_parity_openrouter_cache.tar.gz` | — | 1.4 MB | `nuggets/parity_openrouter/cache/` |
| `raw/nuggets_pilot_cache.tar.gz` | — | ≈ 20 MB | `nuggets/pilot/cache/`; **not on this machine** (see C1) |

Each cache file holds `request` (provider, model, params, system and user prompts), `response`,
`text`, `usage`, `model_served`, `latency_s`, `ts`. The packed size is still to be measured.
JSON compresses well, so expect ≈ 100–200 MB in total. `raw/README.md` gives the cache-key
scheme (SHA-256 of the canonical request, `scripts/llm_client/`) and the unpack command.

**Other:** `README.md` (card, §3.3), `LICENSE`, `SHA256SUMS`, and `docs/` with a copy of the
notes the card cites (the strategy, nugget, RAG phase 3 and phase 5 notes), so the repo makes sense
without GitHub.

Total ≈ 1.3–1.5 GB in ≈ 700 files.

### 3.2 Configs

Only the tables people browse get viewer configs. Rankings, vectors and raw responses do not:

```yaml
configs:
- config_name: run_metrics       # default; one row per (llm, context set), the main result table
  default: true
  data_files: [{split: all, path: nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/runs.csv}]
- config_name: answers
  data_files: [{split: full, path: "runs/answers/jua-4b-mixed/irpf/*/*/*/answers.jsonl"}]
- config_name: nugget_labels
  data_files: [{split: full, path: "nuggets/scoring/score/gold-v0-auto/gemini-3.8-flash/**/labels.jsonl"}]
- config_name: per_question_scores
  data_files: [{split: all, path: nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/per_question.csv.gz}]
- config_name: retrieval_metrics
  data_files: [{split: irpf, path: runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_merge_skip/metrics.csv}]
```

Two problems to solve in the build script (§6.1):

- The `answers` glob mixes full and pilot sets, and the rows of `answers.jsonl` carry `run_id`
  but not the LLM and context set as separate columns. Check that `run_id` is enough to tell them
  apart. If it isn't, generate a flat **`answers_full.jsonl`** with
  `llm, prompt, context_id, question_number, answer, abstained, cited_chunk_ids, …` from the 25
  full runs only, and point the config at it. The per-run files stay for the scripts.
- `labels.jsonl` rows have `source` and a nested `labels` list. The path holds the run identity.
  Use the same fix: a flat `nugget_labels_full.jsonl`, one row per (run, question, nugget).

### 3.3 Card (`README.md`)

YAML: `license: cc-by-4.0`, `language: [pt]`, `pretty_name: BR-TaxQA-R v2.0 — RAG evaluation
data`, `task_categories: [question-answering, text-retrieval]`, `tags: [rag, evaluation, nuggets,
llm-as-judge, embeddings, legal, tax, brazil]`, `size_categories: 10K<n<100K`,
`source_datasets: [unicamp-dl/BR-TaxQA-R]`, plus `configs:`.

Sections:
1. **What this is.** The full trail of the first RAG evaluation on BR-TaxQA-R v2.0: embeddings →
   rankings → contexts → answers → nugget scores → tables.
2. **Pipeline and the experiment grid.** Segmentation strategies × token budgets × 4 generators;
   oracle, closed-book and wrong-context controls; the trimmed grid; the `irpf` and
   `irpf_with_rir1999` runs. Include a figure from the slide deck.
3. **Headline results.** The `runs.csv` table (S2 > S1 by +0.02–0.03 V_strict; S3/S2c/S4 ≈ S2) with
   a pointer to the paper.
4. **File layout.** The tables of §3.1.
5. **Models and versions.** Embedding model and revision. Generators, judges and nugget creators
   with the model ids actually served (`model_served`), routes (OpenRouter / Maritaca), dates and
   temperatures.
6. **Reproducing.** `git clone` the code, `hf download unicamp-dl/BR-TaxQA-R-RAG-eval
   --repo-type dataset --local-dir .`, unpack `raw/*.tar.gz`, then rerun `rag.py` / `nuggets.py`.
   Cached calls cost nothing.
7. **Costs.** The ledgers, and the totals per phase (generation $41.95, scoring $55.96, …).
8. **Limitations.** LLM judge, machine-made nuggets, one embedding model, served-model drift.
9. **License, citation, links.**

---

## 4. Not uploaded anywhere

- `.env`, the `.venv`, `__pycache__`, `.~lock.*`.
- `*.err.log`, `run.log`, `nuggets/**/input/` (regenerated from `questions.jsonl`; its SHA-256 is
  in `sample.json`), and `nuggets/**/batches/*.jsonl`.
- `embeddings/jua-4b-mixed/corpus_prev_20260926/`, `nuggets/probe_openrouter/`.
- `docs/slides/` and the internal notes, except the copies listed in §3.1.

---

## 5. Staging and deployment strategy

### 5.1 Phase 1: private staging under `eduseiti`

1. Create `eduseiti/BR-TaxQA-R` and `eduseiti/BR-TaxQA-R-RAG-eval` as **private** dataset repos
   (`HfApi.create_repo(..., repo_type="dataset", private=True)`).
2. Build the two release trees in a scratch folder with `scripts/release/build_release.py` (§6.1).
3. Upload. Use `upload_folder` for A. Use `upload_large_folder` for B: it resumes and handles the
   1 GB `.npy`. New repos store files with Xet, so later re-uploads only send the changed chunks.
4. Validate (§6.3). Fix and re-upload until it passes.
5. **This private copy also serves as the cache backup** that the nugget notes have kept postponing
   (open decisions §2.2). It can happen before the paper is final.

Storage: ≈ 1.5 GB private, well inside the free private quota.

### 5.2 Phase 2: optional review access

If co-authors or reviewers need access before publication:
- Add them as collaborators, or make the repos public under `eduseiti` for a short time.
- **If the paper is under double-blind review**, `eduseiti` and `unicamp-dl` both reveal the
  authors. Use an anonymous link instead, for example a separate anonymous HF account or the
  venue's supplementary material (see C7).

### 5.3 Phase 3: publication under `unicamp-dl`

Prerequisites: a write role in `unicamp-dl` for `eduseiti`, and a token whose fine-grained
permissions include write on `unicamp-dl` repos and repo creation in the org. Check both with
`whoami` before starting.

**Repo A (the existing `unicamp-dl/BR-TaxQA-R`):**
1. `create_tag("unicamp-dl/BR-TaxQA-R", tag="v1.1", revision="9f0f4263928c6152a40f888da3e63375a24bb0f3")`.
   This is the current `main`, last modified 2025-11-22.
2. Upload the validated tree from `eduseiti/BR-TaxQA-R` (same local folder, same build) to
   `unicamp-dl/BR-TaxQA-R` with `upload_folder(..., delete_patterns=["*"])` and the commit
   message "BR-TaxQA-R v2.0". `delete_patterns` removes the v1.1 files from `main`. Alternative:
   open it as a PR (`create_pr=True`), review it on the Hub, and merge. **Recommended**, because
   the org repo is public and already used.
3. `create_tag(..., tag="v2.0")` on the merge commit.
4. Delete `eduseiti/BR-TaxQA-R` or keep it private. It cannot be moved, because the name in the org
   is taken.

**Repo B:**
1. `move_repo(from_id="eduseiti/BR-TaxQA-R-RAG-eval", to_id="unicamp-dl/BR-TaxQA-R-RAG-eval",
   repo_type="dataset")`. History and tags move with it, and the old URL redirects.
2. Make it public with `update_repo_settings(private=False)`, then `create_tag(tag="v2.0")`.

Then check again (§6.3, steps 2–4) against the org URLs. Update the cross-links between the two
cards and the GitHub README, and record the commit SHAs (§6.4).

### 5.4 Later updates

New experiments (stages 3–4 of the trimmed plan, more embedding models, human-verified nuggets):
- New evaluation outputs go to B as new commits under new paths (e.g. `embeddings/<model>/`),
  with a tag per paper version (`v2.1`, …).
- A changes only if the benchmark changes (e.g. `nuggets/v1-human/`), which is a dataset
  version bump.
- Do not rewrite history on a published repo.

---

## 6. Implementation

### 6.1 `scripts/release/build_release.py` (new)

- Input: a YAML file list per repo (`scripts/release/repo_a.yaml`, `repo_b.yaml`) that encodes
  §2.1 and §3.1 as include/exclude globs. Output: `<out>/repo_a/` and `<out>/repo_b/` with the
  HF paths. It hardlinks where possible, so the 1 GB `.npy` is not copied.
- Packs each cache into `raw/*.tar.gz` (deterministic: sorted names, fixed mtime) and writes
  `raw/README.md`.
- Generates the flat `answers_full.jsonl` / `nugget_labels_full.jsonl` if §3.2 needs them.
- **Checks** (it fails on any of these):
  - secret patterns in every file, caches included (`sk-…`, `sk-or-…`, `hf_…`, `AIza…`,
    `Bearer`). A sample of 9,000 cache files had 0 hits on 2026-10-24;
  - absolute local paths (`/work/`, `/home/`, `/root/`). Three embedding manifests have them
    today (corpus, `corpus_prev_20260926`, queries). Rewrite them to repo-relative paths in the
    release copy only;
  - every path in `documents.jsonl` (`original_file`, `lexml_file`, `lexml_annex_files`) exists in
    tree A;
  - the row counts in the card match the files.
- Writes `SHA256SUMS` and `release_manifest.json` (git commit, build time, file list with sizes
  and hashes) in each tree.

### 6.2 `scripts/release/push_release.py` (new)

`--repo-id`, `--tree`, `--private`, `--create-pr`, `--tag`, `--dry-run` (lists what would change
against the remote). It reads `HF_TOKEN` from `.env`. It never changes visibility or moves a repo
unless the matching flag is set. Moves and visibility changes stay manual one-liners in the
README.

### 6.3 Validation

1. In a clean venv (`datasets`, `huggingface_hub` only): `load_dataset(repo, config)` for every
   config of A and B, checking row counts (715 / 1,916 / 453 / 3,175 / 104,574; answers 25 × 715).
2. The Hub viewer shows every config without errors, including the Parquet conversion of `chunks`.
3. `snapshot_download` both repos into a fresh clone of the GitHub repo, then `sha256sum -c
   SHA256SUMS`.
4. Reproduction smoke test: unpack `raw/`, then rerun `rag.py run` for one full run and
   `nuggets.py score` / `scoretable` for one run with `--budget 0.01`. Every call must come from
   the cache ($0), and `runs.csv` must match byte for byte.
5. Read both cards on the Hub: links, tables, citation.

### 6.4 Changes in the git repo

- `release/hf_release.json`: the repo ids, the commit SHAs and tags of each publication.
- `dataset/README.md`: fix the stale counts. It says 1,917 references and 458 documents, but
  `build_report.json` and the files have **1,916** and **453**. Turn it into the source of the
  repo A card, or replace it with a pointer to the card.
- The repo has no top-level `README.md` yet. Add a short one that points to the two HF repos.
  `CLAUDE.md` and the `.gitignore` comments ("released on the HF Hub") get the final URLs. The nugget manifest records the Hub revision (plan v2, W1).
- A git tag `v2.0` on the release commit, pushed to GitHub, with the user's go-ahead.

---

## 7. Checks before going public

| # | Check | Status |
|---|---|---|
| C1 | **Pilot and preview nugget caches**: they are not on this machine (`nuggets/pilot/cache/` is missing; see the two-machine memory note). Copy them from the other computer before building B, or document them as not released. Missing: `nuggets/{pilot,preview,preview_v2,preview_v3}/cache/`. Copy them with `scripts/release/transfer_caches.py` (`pack` there, `unpack` here; see `scripts/release/README.md`) | open |
| C2 | Full secret scan of every released file (§6.1) | sample OK |
| C3 | Absolute paths in manifests (§6.1) | 3 files found |
| C4 | Stale counts in `dataset/README.md` (§6.4) | open |
| C5 | Provider terms for publishing model outputs: OpenAI (GPT-5.x via OpenRouter), Google (Gemini), Alibaba (Qwen), Maritaca (Sabiá-4). All four generally allow it, but check Maritaca's terms and OpenRouter's pass-through terms specifically | open |
| C6 | Source documents: Receita Federal Q&A PDF and the acts are public works. CARF decisions and soluções de consulta are official acts. Check that no non-statutory document contains personal data of taxpayers beyond what the authority already publishes | open |
| C7 | Double-blind review: is the paper submitted anonymously? This decides whether §5.2 needs an anonymous mirror | to decide |
| C8 | Whether to include the 31 pilot-only answer sets and the preview/pilot nugget runs (proposal: yes, under the same paths; they are small and cited by the notes) | to decide |
| C9 | Org repo name for B (`BR-TaxQA-R-RAG-eval`), and whether `unicamp-dl` wants a different naming | to decide |
| C10 | Whether to also publish a float16 copy of the vectors (proposal: no) | to decide |

---

## 8. Order of work

1. User decisions C7–C10, and C1 (copy the caches from the other machine).
2. Write `build_release.py`, `push_release.py` and the two YAML file lists. Build both trees
   locally and review the trees and the cards (no upload).
3. **Go-ahead 1:** create the private repos under `eduseiti` and upload. Validate (§6.3).
4. Resolve C4–C6. Final card text.
5. **Go-ahead 2:** tag `v1.1`, open the PR on `unicamp-dl/BR-TaxQA-R`, and move B to `unicamp-dl`.
6. **Go-ahead 3:** merge the PR, make B public, add the tags, and run the final validation. Commit
   `release/hf_release.json` and the README updates, and tag `v2.0` on GitHub.

HF storage and transfer cost nothing for public datasets of this size. No LLM calls are needed
(only the cached $0 smoke test in §6.3).
