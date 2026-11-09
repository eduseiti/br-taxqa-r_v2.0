---
license: cc-by-4.0
language:
- pt
pretty_name: BR-TaxQA-R v2.0 — RAG evaluation data
task_categories:
- question-answering
- text-retrieval
size_categories:
- 100K<n<1M
source_datasets:
- unicamp-dl/BR-TaxQA-R
tags:
- rag
- evaluation
- nuggets
- llm-as-judge
- embeddings
- legal
- tax
- brazil
configs:
- config_name: run_metrics
  default: true
  data_files:
  - split: results
    path: tables/run_metrics.parquet
- config_name: answers
  data_files:
  - split: results
    path: tables/answers.parquet
- config_name: nugget_labels
  data_files:
  - split: results
    path: tables/nugget_labels.parquet
- config_name: per_question_scores
  data_files:
  - split: results
    path: tables/per_question_scores.parquet
- config_name: comparisons
  data_files:
  - split: results
    path: tables/comparisons.parquet
- config_name: retrieval_metrics
  data_files:
  - split: irpf
    path: tables/retrieval_metrics.parquet
---

# BR-TaxQA-R v2.0 — RAG evaluation data

Every output of the first RAG evaluation on [BR-TaxQA-R v2.0](https://huggingface.co/datasets/unicamp-dl/BR-TaxQA-R),
and of a second-embedding comparison (`gemini-embedding-2`, added on 2026-11-08):
corpus and query embeddings, retrieval rankings, generator contexts, generated answers, nugget-based scores and
analyses, the nugget-creation runs behind the gold nuggets, and **every raw LLM response**. The question is
whether **hierarchical segmentation** of Brazilian legal documents (sub-article chunks) gives better RAG answers
than article chunks.

The code is at <https://github.com/eduseiti/br-taxqa-r_v2.0>. The paths here mirror that repository, so
downloading this dataset into a checkout gives the scripts the state they expect. The design and result notes
cited below are copied under `docs/`.

## The experiment

1. **Corpus and chunks.** The legal corpus of BR-TaxQA-R v2.0 is cut by five strategies: **S1** article chunks;
   **S2** S1 + sub-article chunks (paragraph, inciso, alínea, item, each with its ancestors' text); **S3** S2 +
   grouping chunks; **S2c** / **S4** S2 / S3 with the caput added to paragraph chunks.
2. **Embeddings.**
   - **`jua-4b-mixed`** (primary): model `ufca-llms/jua-4B-mixed` (revision `57f491c`), served by TEI in float16.
     There is one vector per distinct chunk text (101,943 × 2,560, float32) and one per question (715), with the
     query instruction `irpf`.
   - **`gemini-emb-2`** (second embedding): Google `gemini-embedding-2` through OpenRouter (provider pinned to
     Google AI Studio), the same 101,943 texts and 715 questions (× 3,072, float32, unit norm). Templates
     `task: search result | query: {text}` and `title: none | text: {text}`. The query folder is also called
     `irpf` so the paths match.
3. **Retrieval.** Exact cosine search per strategy. `irpf` is the main run, without the revoked RIR/1999.
   `irpf_with_rir1999` is the run without exclusions. A legal-provision retrieval test scores the rankings
   against the gold citations.
4. **Contexts.** Top chunks packed into a token budget (2k / 4k / 8k Qwen3 tokens), plus three controls:
   **oracle** (the cited provisions), **closed book** (no context) and **wrong context** (the S2 context of a question from
   another chapter with no shared gold document).
5. **Generation.** Four generators answer in Portuguese with claims and quotes: Sabiá-4 and Sabiazinho-4
   (Maritaca), and GPT-5.6 Terra and GPT-5.6 Luna (OpenAI via OpenRouter). All run at temperature 0 or with
   reasoning off. The pilot ran 14 context sets × 4 generators on 30 questions (`stratified_30`). The
   **trimmed grid** then ran 25 runs on all 715 questions. With `gemini-emb-2`: all five strategies are retrieved
   and tested, and the core grid (S1 and S2 at 4k × Sabiá-4 and GPT-5.6 Luna, 4 runs × 715) is generated and
   scored; closed book and oracle do not depend on the embedding.
6. **Scoring.** Gemini 3.8 Flash judges each answer against the gold nuggets (`gold-v0-auto`) as `support`,
   `partial_support`, `not_support` or `contradicts`. It also judges whether each context supports each nugget.
   Robustness checks: two alternative nugget sets (Gemini 3.1 Pro, Qwen3.8-Max), a second judge (Gemini 3.1 Pro),
   perturbed nugget sets, chapter-cluster bootstrap.

## Headline results (V_strict: strict recall of vital nuggets, 715 questions, 4k-token contexts)

| Generator | closed book | S1 | S2 | oracle |
|---|---:|---:|---:|---:|
| GPT-5.6 Terra | 0.351 | 0.325 | 0.341 | 0.368 |
| Sabiá-4 | 0.239 | 0.290 | 0.317 | 0.319 |
| Sabiazinho-4 | 0.177 | 0.267 | 0.272 | 0.293 |
| GPT-5.6 Luna | 0.259 | 0.271 | 0.299 | 0.338 |

- **S2 beats S1 for all four generators by +0.005 to +0.028**, significant for Luna and Sabiá-4 (paired
  bootstrap and permutation tests).
- **S3, S2c and S4 add nothing measurable over S2.**
- **Retrieval mostly cuts contradictions**: 27–38 % of closed-book answers contradict a nugget, against
  8–14 % with retrieval.

**Second embedding** (`gemini-emb-2`, same 4k budget, prompt and judge; paired differences with 95 % bootstrap CI and
permutation p):

| Generator | S1 jua → Gemini | S2 jua → Gemini | S1 → S2 with Gemini |
|---|---|---|---|
| Sabiá-4 | 0.290 → **0.320** (+0.029, p .011) | 0.317 → 0.328 (+0.011, n.s.) | +0.009 (n.s.) |
| GPT-5.6 Luna | 0.271 → **0.296** (+0.025, p .030) | 0.299 → **0.327** (+0.027, p .018) | **+0.030** (p .007) |

- Gemini ranks the cited articles much better (MRR 0.52 → 0.61 for S1, 0.55 → 0.64 for S2), but the share of cited
  articles inside the 4k context barely changes (+0.01, n.s.).
- Its contexts state more of the gold answers' vital nuggets (+0.042 / +0.047, p < .001), and the answers improve
  in 3 of 4 comparisons.
- S2 > S1 holds for Luna under Gemini, not for Sabiá-4.

Every metric for every run: config `run_metrics`; tests: config `comparisons`. Details:
`docs/20261023_210727_rag_phase5_scoring_and_analysis.md` and
`docs/20261108_175117_gemini_embedding_2_setup_embedding_and_retrieval_gate.md`.

## Configurations (dataset viewer)

The configs read Parquet copies in `tables/`: the answers and labels flattened from the per-run files, and the
primary-set tables of `nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/` (`runs.csv`, `per_question.csv.gz`,
`comparisons.csv`) and `runs/retrieval/<embedding>/irpf/eval/either_containment_merge_skip/metrics.csv`. In the
scoring tables, a context or run of the second embedding is named `<context_id>@gemini-emb-2` (e.g.
`S2_budget4000@gemini-emb-2`); a bare `context_id` is `jua-4b-mixed`. `answers` and `nugget_labels` have an
`embedding` column.

| Config | Rows | Content |
|---|---:|---|
| `run_metrics` | 60 | V_strict, V, A_strict, A, W, contradicts, any_contradicts, abstained, errors, answer_chars, over the 715 questions (`n`); the pilot-only sets have `n` = 30 |
| `answers` | 21,665 | every generated answer: `run_id`, `embedding`, `prompt`, `llm`, `context_id`, `sample` (`all` or `stratified_30`), `question_number`, `answer`, `abstained`, `claims_json` (claims with quotes), `cited_chunk_ids`, tokens, cost, `model_served`, `cache_key` |
| `nugget_labels` | 94,886 | the judge's label and justification for each nugget of each answer (primary nugget set and judge) |
| `per_question_scores` | 21,169 | the per-question metrics behind `run_metrics` |
| `comparisons` | 378 | paired differences, bootstrap CIs, permutation p-values, chapter-cluster CIs |
| `retrieval_metrics` | 22,510 | the legal-provision retrieval test of the `irpf` rankings (context precision, recall… at document and provision level), 11,255 rows per `embedding` |

## Files

**Embeddings** — `embeddings/<embedding>/` (`jua-4b-mixed`, `gemini-emb-2`)

| Path | Content |
|---|---|
| `corpus/vectors.npy` | float32 (101,943 × 2,560 for jua, × 3,072 for Gemini), one row per distinct chunk text; `np.load(p, mmap_mode="r")` |
| `corpus/texts.csv` | row → `text_id` and text hash |
| `corpus/chunk_map.csv.gz` | `chunk_id` (all strategies) → `text_id` |
| `queries/irpf/vectors.npy`, `queries.csv` | the 715 query vectors and their ids |
| `*/manifest.json`, `parity.json`, `check.json`, `endpoint_meter.jsonl`, `../costs.csv` | model revision, templates, endpoint, cost. jua: `parity.json` is the check against local inference. Gemini (an API model): `parity.json` is a determinism check (the sample embedded twice, bit-identical) with the server fingerprint, and `costs.csv` holds the provider-billed tokens and USD |

**Retrieval** — `runs/retrieval/jua-4b-mixed/{irpf,irpf_with_rir1999}/` and `runs/retrieval/gemini-emb-2/irpf/` (same
four evaluations with the same parameters)

| Path | Content |
|---|---|
| `<S>/rankings.csv.gz` | ranked chunks per question: `question_number, rank, text_id, chunk_id, alias_chunk_ids, score` |
| `eval/<eval_id>/` | retrieval test: `report.md`, `metrics.csv`, `comparisons.csv`, `reachability.csv`, `per_question.csv.gz`, `per_item.csv.gz`, `metrics_by_chapter.csv.gz` |

**Contexts** — `runs/contexts/<embedding>/<run>/<context_id>/contexts.jsonl.gz`: one row per question with the
rendered `context`, its `items` (chunk ids, ranks, tokens) and the `gold` coverage; `summary.csv` per run. Gemini has
`S1_budget4000` and `S2_budget4000`. Their `rendered_tokens_qwen3` is empty: the optional Qwen3 count of the
rendered context was skipped when they were built (the tokenizer was not in the local cache); `context_tokens_qwen3`,
the budget count, is filled. The same field is empty in the Gemini answers.

**Answers** — `runs/answers/<embedding>/irpf/<prompt>/<llm>/<context_id>/answers.jsonl` and `run.json` (config,
prompt hash, model, sample, cost); `runs/costs.csv` is the generation cost ledger.

**Nuggets and scoring** — `nuggets/`

| Path | Content |
|---|---|
| `full/` | creation of the gold nuggets on 715 questions: three creators and replicas (`create/`), self-scores, alignments, audits, planted-error tests, known-answer tests (judge selection), report |
| `pilot/`, `preview*/`, `parity_openrouter/` | the 30-question pilot, the 10-question previews (prompt development) and the direct-vs-OpenRouter parity check |
| `scoring/score/<nugget set>/<judge>/<run>/labels.jsonl` | per-answer nugget labels (also `calls.jsonl`, `manifest.json`) |
| `scoring/ctxsupport/…` | per-context nugget support |
| `scoring/ctxaudit/…` | audit of the vital nuggets that the cited provisions do not support |
| `scoring/tables/<set>/<judge>/<sample>/` | `runs.csv`, `comparisons.csv`, per-question and context-support tables |
| `scoring/analysis/…` | value checks, citation scores, linkage, utilisation, slices, perturbation, cross-sets, judge agreement |
| `*/costs.csv` | cost ledgers |

**Raw LLM responses** — `raw/*.tar.gz`. Each archive holds one cache folder of the pipeline: one JSON file per
API request, named by the SHA-256 of the canonical request. Each file has `request` (provider, model,
parameters, system and user prompts), `response`, `text`, `usage`, `model_served`, `latency_s`, `ts`.

| Archive | Restores | Requests |
|---|---|---:|
| `runs_answers_cache.tar.gz` | `runs/answers/cache/` | 18,600 |
| `nuggets_full_cache.tar.gz` | `nuggets/full/cache/` | 12,519 |
| `nuggets_scoring_cache.tar.gz` | `nuggets/scoring/cache/` | 26,420 |
| `nuggets_pilot_cache.tar.gz`, `nuggets_preview*_cache.tar.gz`, `nuggets_parity_openrouter_cache.tar.gz` | the pilot, preview and parity caches | 1,230 |

## Reproducing

```bash
git clone https://github.com/eduseiti/br-taxqa-r_v2.0 && cd br-taxqa-r_v2.0
hf download unicamp-dl/BR-TaxQA-R --repo-type dataset --local-dir .
hf download unicamp-dl/BR-TaxQA-R-RAG-eval --repo-type dataset --local-dir .
for f in raw/*.tar.gz; do tar -xzf "$f"; done        # restores the caches under their repo paths
```

With the caches in place, `scripts/rag/rag.py` and `scripts/nuggets/nuggets.py` replay every LLM call from the
cache at no cost. See the READMEs of `scripts/rag/` and `scripts/nuggets/`. `SHA256SUMS` lists every file.

## Costs

Generation of the trimmed grid cost $41.95, scoring $55.96, and nugget creation (phases 2–4) $65.34. The
`gemini-embedding-2` comparison cost $26.91: embedding $5.08, context support $6.42, generation $9.98, scoring
$5.43. Per-call costs are in the `costs.csv` ledgers.

## Limitations

- The judge and the nuggets are LLMs (selected and checked with known-answer and planted-error tests). The
  nuggets were not verified by people.
- Two embedding models, one query instruction (or template) each. The second embedding covers S1 and S2 at 4k
  with two of the four generators; it has not been re-scored with the alternative nugget sets.
- Served models can change behind a model id. `model_served` and the raw responses record what answered.
- The P&R answers do not always follow from the provisions they cite: only ≈ 47 % of vital nuggets are fully
  supported by the cited provisions within 4k tokens (`docs/20261023_210727_*` §4, §10).

## License

CC BY 4.0. The legal texts quoted in contexts and answers are official acts, which are not protected by
copyright in Brazil (Lei nº 9.610/1998, art. 8º, IV).
