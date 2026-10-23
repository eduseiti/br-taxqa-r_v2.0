# RAG pipeline — BR-TaxQA-R v2.0 segmentation experiment

Tests whether **hierarchical segmentation** of the legal documents cited by the *Perguntas e
Respostas IRPF 2024* gives better chunks for answering its questions. This directory holds the
pipeline code. Design: `docs/20260927_204356_rag_pipeline_implementation_plan.md`.

**Status: Phase 1 (retrieval and its evaluation, "the legal-provision test"), Phase 2 (generator
contexts, `context`) and Phase 3 (answer generation, `generate` / `run`; pilot on `stratified_30`).**
Phase 3 run and decisions: `docs/20261023_110952_rag_phase3_generation_pilot.md`. Phase 2 run and decisions:
`docs/20261021_210251_rag_phase2_contexts_execution.md`; the first evaluation's plan, costs and grounding
safeguards: `docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md`.

## Stages

```
chunks + vectors ──► R  retrieve  ──► rankings ──► RE evaluate ──► metrics, report      (Phase 1)
                                         │
                                         └──► C  context ──► G  generate ──► answers ──► nugget scoring
                                              (Phase 2)      (Phase 3)                   (scripts/nuggets/)
```

Stages talk only through files, so each one can be rerun, replaced or released on its own.

| Stage | Input | Output |
|---|---|---|
| R — retrieve | `segmented/chunks_all.csv.gz`, `embeddings/<model>/…`, `dataset/questions.jsonl` | `runs/retrieval/<model>/<instruction>/<strategy>/rankings.csv.gz` |
| RE — evaluate | rankings, chunks, `dataset/references.jsonl` + `documents.jsonl` | `runs/retrieval/<model>/<instruction>/eval/<eval_id>/…` |
| C — context | rankings, chunks (with text), dataset, `prompts/context_v2.pt.md` | `runs/contexts/<model>/<instruction>/<context_id>/contexts.jsonl.gz` |
| G — generate | contexts, `dataset/questions.jsonl`, `llms.yaml`, `prompts/answer_v1.pt.md` | `runs/answers/<model>/<instruction>/<prompt>/<llm>/<context_id>/answers.jsonl` |

## Install

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r scripts/rag/requirements.txt
```

## Quick start

From the repository root, with the dataset, the chunks and the vectors in place (built by the
repository scripts or downloaded from the Hub):

```bash
R=scripts/rag/rag.py
.venv/bin/python $R check    --embedding jua-4b-mixed                          # input checks only
.venv/bin/python $R retrieve --embedding jua-4b-mixed                          # S1, S2, S3, S2c, S4; top-1000 (≈20 s)
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf      # ≈15 s
.venv/bin/python $R compare  --retrieval runs/retrieval/jua-4b-mixed/irpf --a S1 --b S2
```

Then read `runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_merge_skip/report.md`.

Phase 2, the generator contexts (≈ 70 s for the 12 pilot sets × 715 questions, half of it loading):

```bash
.venv/bin/python $R context --retrieval runs/retrieval/jua-4b-mixed/irpf        # the pilot sets (below)
.venv/bin/python $R context --retrieval runs/retrieval/jua-4b-mixed/irpf --sets S2@budget=16000,oracle@budget=8000
.venv/bin/python $R show-context --context runs/contexts/jua-4b-mixed/irpf/S2_budget4000 --questions 012,345
```

Phase 3, the answers (keys in the repository-root `.env`: `MARITACA_API_KEY`, `OPENROUTER_API_KEY`). Size
every grid with `--dry-run` first; `--budget` (USD) caps the total of the ledger `runs/costs.csv`:

```bash
.venv/bin/python $R run --experiment scripts/rag/experiments/pilot.yaml --dry-run      # calls, cached, est. cost
.venv/bin/python $R run --experiment scripts/rag/experiments/pilot.yaml --budget 18
.venv/bin/python $R generate --contexts runs/contexts/jua-4b-mixed/irpf --sets S2_budget4000 --llms sabia-4 \
    --sample all --budget 30                                                           # one run, all questions
.venv/bin/python $R show-answers --run runs/answers/jua-4b-mixed/irpf/answer_v1/sabia-4/S2_budget4000 --questions 350
```

Options (every subcommand has `--help` with an example):

| Subcommand | Main options |
|---|---|
| `check` | `--embedding` (required), `--instruction` (default `irpf`, or the only one), `--no-hash` |
| `retrieve` | `--strategies S1,S2,S3,S2c,S4`, `--top-n 1000`, `--exclusions <yaml> \| none` (default `corpus_exclusions.yaml`), `--run-name` (default: the instruction), `--force` (replace a run made with other settings) |
| `evaluate` | `--annex-rule {either,main_first}`, `--budgets 1000,…,16000`, `--unit-ks`, `--raw-ks`, `--dedup {containment,containment_merge,none}`, `--overflow {skip,stop}`, `--comparisons S1:S2,S2:S3`, `--eval-id` |
| `compare` | `--a`, `--b`, `--views budget,unit,raw`, `--eval-id` |
| `report` | `--eval <eval dir>` (regenerate `report.md`) |
| `context` | `--sets` (specs below), `--dedup`, `--overflow`, `--order {score,document}`, `--template context_v2`, `--annex-rule`, `--oracle-strategy S1`, `--seed`, `--eval-id`, `--no-token-count`, `--force` |
| `show-context` | `--context <set dir>`, `--questions`, `--no-text`, `--max-chars` |
| `generate` | `--contexts <folder>`, `--sets <context ids>`, `--llms <llms.yaml names>`, `--sample stratified_30 \| all \| 001,002`, `--prompt answer_v1`, `--closed-prompt answer_closed_v1`, `--budget`, `--dry-run`, `--workers 8`, `--registry`, `--force` |
| `run` | `--experiment <yaml>` (the same settings as a versioned file), `--sample`, `--budget`, `--dry-run` |
| `show-answers` | `--run <answer run dir>`, `--questions` |

Input locations default to the repository layout and can be changed with `--chunks`, `--dataset`,
`--embeddings-dir`, `--runs-dir` and `--strategies-file`.

## Corpus exclusions

`corpus_exclusions.yaml` lists documents of the dataset that are **not retrieval candidates** (rule: documents
revoked as a whole before the P&R date, 2024-05-03). They stay in `dataset/`, `segmented/` and `embeddings/`;
`retrieve` drops their chunks from every strategy and records the list in its manifest, from which `evaluate`
(their gold items: `unreachable_reason = excluded_from_corpus`) and `context` (oracle) take it. Now excluded:
`decreto_3000_19990326` (RIR/1999). The run without exclusions is kept as an ablation:
`retrieve --exclusions none --run-name irpf_with_rir1999`. Analysis and audit:
`docs/20261022_203625_corpus_exclusion_revoked_rir1999.md`.

## What is measured

**Strategies** (`strategies.yaml`): the chunk types each one indexes and the text variant it
prefers per unit (`variantes`; caput plan `docs/20261005_184116_*`). Paragraph-family chunks have a
`base` text (article label + paragraph) and a `caput` text (with the caput's opening sentence).
Counts of the 2026-10-08 chunk set (`d1b9cf7e…`):

| | Tipos | Variants | Chunks | Texts |
|---|---|---|---:|---:|
| S1 | ART, DSP, TXT, TAB | base | 26,364 | 26,323 |
| S2 | S1 + CPT, PAR, INC, ALI, ITE | base | 83,496 | 83,330 |
| S3 | S2 + PRT, LIV, TIT, SBT, CAP, SEC, SSC | base | 88,600 | 88,434 |
| S2c | as S2 | caput, base | 83,496 | 80,325 |
| S4 | as S3 | caput, base | 88,600 | 85,429 |

A `caput` row is indexed instead of its base twin, never next to it; the evaluation treats only the
indexed rows as members of a strategy (`strategies.member_mask`).

Vectors are stored per unique text, so a ranked item is **one text**. It is represented by its
coarsest chunk (`unit_precedence`), and the other chunks with that text are its aliases.

**Retrieval** (`dense`): exact cosine over the stored L2-normalized vectors (brute force, no ANN
index). Ties are broken by `text_id`. One scoring pass serves all strategies.

**Gold** (`references.jsonl`, resolved references only), at three levels:

| Level | Gold item | A chunk hits it when… |
|---|---|---|
| document | `document_id` | it belongs to the document's main or annex LexML file |
| article | `(document_id, article_id)` | it is (part of) the article, or a grouping chunk that contains it. Annex rule `either`: article N of the main file or of an annex; `main_first`: the annex only when the main file lacks it |
| provision | `(document_id, fragment_id)`, e.g. `art1_cpt_inc10` | **full**: a `cobre_ids` id equals the fragment or is its ancestor, or a grouping chunk contains it, or all parts of a split article that hold it are retrieved; **partial**: the chunk holds only part of it |

**Views** (the headline is the token budget, because raw k is not comparable across strategies):

| View | Ranked list | Cutoffs |
|---|---|---|
| `budget` | Texts selected by `ragpipe.context.select`, in rank order: containment de-duplication, then filled up to B Qwen3 tokens (`n_tokens_qwen3`), skipping texts that do not fit | 1k, 2k, 4k, 8k, 16k |
| `unit` | Ranking projected to distinct documents / articles (a grouping chunk stands for the articles it contains) | 1, 3, 5, 10, 20, 50, 100; MRR and nDCG@10 at cutoff `-` |
| `raw` | Texts as retrieved (diagnostic) | 1, 5, 10, 20, 50, 100, 1000 |
| `oracle` | Can any chunk of the strategy hit the item at all (the ceiling)? | `-` |

**Metrics** per question, averaged over questions with gold at the level: `recall`, `hit`,
`full_recall`, `partial_recall` (provision), `mrr`, `ndcg@10`, `context_precision` (share of context
tokens from texts that hit gold), `context_tokens`, `context_texts`. Every metric is reported over
all resolved gold (`gold=all`) and over the gold the strategy can reach (`gold=reachable`), and per
slice: `all`, `explicit`/`embedded` (origin of the reference), `statutory`/`non_statutory`,
`annex_A` (gold in a category-A annex, e.g. the RIR/2018), `whole_article`/`sub_article`
(provision level) and the P&R chapter (`data/pr_irpf_2024_chapters.csv`).

**Paired comparisons** (S1 vs S2, S2 vs S3): mean per-question difference, with a 95 % paired
bootstrap CI (10,000 resamples, seed 13) and a two-sided sign-flip permutation p-value.

## Contexts (Phase 2)

A **context set** is one way of building the context of every question (`--sets`, comma list):

| Spec | Context id | Context |
|---|---|---|
| `S2@budget=4000` | `S2_budget4000` | the strategy's ranking cut by the budget selection (containment de-duplication, `skip` overflow): **the same texts as the evaluation's budget view** |
| `S3@k=10` | `S3_k10` | the first k texts after de-duplication |
| `closed_book` | `closed_book` | empty: what the generator knows without retrieval |
| `oracle@budget=4000` | `oracle_budget4000` | the question's gold articles (rules G1–G3, annex rule) as S1 article units, plus the chunks of gold documents with no gold article; ordered by S1 rank (unranked after, in file order), cut by the budget. A gold document none of whose gold articles is matchable (e.g. a treaty's "art. IX") adds its chunks. Empty for the 119 questions without resolved gold |
| `wrong:S2@budget=4000` | `wrong-S2_budget4000` | the S2 context of a **donor** question: another P&R chapter, no shared gold document, no chunk of the question's gold documents in the donor context (seeded permutation). Control for answers from the model's own knowledge |

The default `--sets` is the pilot grid: S1, S2, S3, S2c, S4 at 4k; S1, S2 at 2k and 8k; closed-book;
oracle at 4k; wrong S2 at 4k. Non-default options add a suffix to the id (`S2_budget4000_order-document`).

**Rendering** (`--template`, default **`context_v2`**, `prompts/context_v2.pt.md`): one block per text,
joined by a blank line:

```
[Documento 1] INSTRUÇÃO NORMATIVA Nº 1.500, DE 29 DE OUTUBRO DE 2014 — Receita Federal do Brasil — Art. 90 (parte 1 de 2)
Ementa: Dispõe sobre normas gerais de tributação relativas ao Imposto sobre a Renda das Pessoas Físicas.
Art. 90. Podem ser considerados dependentes: I – o cônjuge; …

[Documento 5] INSTRUÇÃO NORMATIVA Nº 1.500, DE 29 DE OUTUBRO DE 2014 — Receita Federal do Brasil — Art. 90 (parte 2 de 2)
Art. 90. Podem ser considerados dependentes: § 7º …
```

The header is the document title, the issuing body when the title lacks it (RFB/SRF acts), the annex
label for annex chunks (e.g. `Anexo 17 – ANEXO IX LIMITES ANUAIS …`), the chunk's citation path
(`citacao`) and `(parte p de n)` for a split article. The chunk's `[ Epígrafe | Ementa | Anexo ]` prefix
is removed from the text; the ementa is shown once per document, on its first block. `context_v1` keeps
the full chunk text (prefix included) under the header, with `Anexo` alone for annexes.
The budget counts the full chunk texts (`n_tokens_qwen3`), so the selection does not depend on the
template; the rendered Qwen3 count is in each line (`rendered_tokens_qwen3`). At 4k a context renders to
≈ 3.8k tokens with `context_v2` and ≈ 4.45–4.6k with `context_v1`.

**De-duplication** (`--dedup`, also an `evaluate` option): **`containment_merge` (default since 2026-10-21)**
drops a text inside an already selected chunk, and lets a parent ranked *after* its selected children
replace them (in the first child's place; it needs only its extra tokens), so no text repeats.
`containment` (the Phase 1 rule, eval `v2d_either_containment_skip`) keeps such a parent next to its
child, whose text is then sent twice (9–15 % of the 4k context in S2–S4). `none` keeps everything.
Effect on the legal-provision test: Phase 2 note §4.

**Budget fill** (`--overflow`): texts are taken in rank order and never truncated. With `skip` (default)
a text that does not fit the remaining budget is passed over and filling goes on with lower-ranked texts
that fit, until no remaining candidate fits; with `stop` filling ends at the first text that does not fit.
So a context is at most the budget: at 4k, 16 tokens short on average (max ≈ 70). The late, small texts
that fill the gap can come from deep ranks (S2 4k: median deepest rank 36, p90 333), but they carry only
1–6 % of the context tokens.

**Gold coverage per context** (`gold` field): for each level, the gold items fully (`full`) or partly
(`any`) held by the context, by the evaluation's rules. For retrieval sets it is checked against the
evaluation's `budget_full_<B>` (`consistency_with_evaluation` in the manifest: 0 mismatches expected).
It is the per-question link between retrieval and answer scores (phase 5).

## Answers (Phase 3)

One **answer run** = one context set × one generator (`llms.yaml`) × one prompt. Every question of the sample
gets one call; questions whose context is empty (the oracle of a question without resolved gold) are
`skipped`. The closed-book set uses `answer_closed_v1`, every other set `answer_v1`.

- **Reply format** (strict JSON schema): `afirmacoes` — claims, each with `fundamentos`
  `[{documento, trecho}]` (context document number and a verbatim quote) — then `abstencao`. The scored
  answer is the claim texts joined in order; no claim means abstention, written as a fixed sentence.
- **Grounding checks (no LLM):** each quote is looked up in the cited `[Documento n]` block (words in
  order, punctuation and case ignored, an ellipsis may skip text): `ok`, `not_found`, `too_short`
  (< 3 words) or `bad_document`; a claim is *grounded* when one of its quotes is `ok`. Values (R$, %, dates)
  of the answer that are in neither the context nor the question are listed (`values_not_in_context`).
- **No tools, no web search:** `llm_client` refuses a registry entry with tools / plugins / `:online`, and
  rejects (without retry, logged in the ledger as `rejected:<reason>`) a reply with tool calls, URL
  citations, web search sources, built-in tool executions (Maritaca) or a billed cost above its token cost.
- **Generators** (`llms.yaml`): Sabiá-4 and Sabiazinho-4 (Maritaca, direct route, temperature 0, BRL prices
  converted with the recorded `fx_brl_per_usd`), GPT-5.6 Terra and Luna (OpenRouter, `openai/flex`,
  reasoning effort `none`; no temperature parameter). DeepSeek entries are disabled here.
- **Cache:** raw responses in `runs/answers/cache/` (keyed by the request): a rerun is free and gives the
  same file; a run folder refuses another configuration (prompt, generator settings, context set) unless
  `--force`. Lines of other questions already in a run's `answers.jsonl` are kept, so a run can grow from the
  pilot sample to all questions.

## Output formats

`runs/retrieval/<embedding>/<instruction>/`:

| File | Content | In git |
|---|---|---|
| `manifest.json` | git commit + dirty flag, command line, SHA-256 of every input, parameters, counts, timings, `config_hash`, input checks | yes |
| `<strategy>/rankings.csv.gz` | `question_number, rank, text_id, chunk_id, alias_chunk_ids, score` (top-N per question; aliases `;`-separated) | no (Hub) |
| `eval/<eval_id>/manifest.json` | matcher rules, cutoffs, gold counts, pointer to the retrieval manifest | yes |
| `eval/<eval_id>/metrics.csv` | `strategy, level, view, cutoff, gold, slice, metric, value, n_questions` | yes |
| `eval/<eval_id>/comparisons.csv` | `a, b, level, view, cutoff, metric, mean_a, mean_b, diff, ci_low, ci_high, p_permutation, n_questions` | yes |
| `eval/<eval_id>/reachability.csv` | gold items per strategy × level: reachable, unreachable by reason, G3/G4 counts | yes |
| `eval/<eval_id>/report.md` | generated tables | yes |
| `eval/<eval_id>/metrics_by_chapter.csv.gz` | as `metrics.csv`, with `slice = chapter:<name>` | no |
| `eval/<eval_id>/per_question.csv.gz` | one row per question × strategy × level × view × cutoff × gold set (for other tests) | no |
| `eval/<eval_id>/per_item.csv.gz` | one row per gold item × strategy: `rank_full`, `rank_any`, `unit_pos`, `budget_full_<B>`, `budget_any_<B>`, reachability flags | no |

`runs/contexts/<embedding>/<instruction>/`:

| File | Content | In git |
|---|---|---|
| `summary.csv` | one row per context set: options, counts, mean texts / tokens, gold recall and hit per level, consistency mismatches | yes |
| `<context_id>/manifest.json` | parameters, input hashes (retrieval manifest, chunks, dataset, template), counts, donor rule, consistency check | yes |
| `<context_id>/contexts.jsonl.gz` | one line per question: `context_id, question_number, kind, [donor_question], n_texts, context_tokens_qwen3, rendered_tokens_qwen3, rendered_chars, items[{n, text_id, chunk_id, alias_chunk_ids, rank, score, document_id, arquivo, tipo, citacao, tokens_qwen3, fonte}], gold{level: {n, full, any}}, context` | no (Hub) |

`runs/answers/<embedding>/<instruction>/`:

| File | Content | In git |
|---|---|---|
| `summary.csv` | one row per answer run: counts, abstention rate, claims, answer length, tokens, quote and claim grounding rates, values not in context, cost | yes |
| `<prompt>/<llm>/<context_id>/run.json` | generator config (no key), prompt and schema SHA-256, context manifest pointer and SHA-256, counts, `config_hash` | yes |
| `<prompt>/<llm>/<context_id>/answers.jsonl` | one line per question: `run_id, question_number, answer` (the nugget-scoring contract) + `status, abstained, claims[{texto, fundamentos[{documento, trecho, status}]}], checks, cited_chunk_ids, usage, usd_list, usd_billed, from_cache, model_served, provider_served, cache_key` | yes |
| `cache/<key>.json` | raw request and response | no (backup / Hub) |

`runs/costs.csv`: one row per API call (all stages), the `llm_client` ledger with `fx_brl_per_usd` for BRL-priced
models.

Example lines:

```
# rankings.csv.gz
001,1,3343d23be0d7f974,in_rfb_2178_20240305#167,,0.803779
# metrics.csv
S2,provision,budget,4000,all,sub_article,recall,0.376…,…
```

The same inputs give byte-identical rankings and metrics (gzip with mtime 0, stable sorting, fixed
seeds). A run directory refuses to be overwritten by a run with another configuration unless
`--force` is given.

## Extending

- **A strategy:** add an entry to `strategies.yaml` (the Tipos it indexes, optionally `variantes`
  and the expected chunk count). No code change.
- **A retriever:** a class with `name`, `info()` and `search(query_ids, candidate_rows, top_n)`
  (`ragpipe/retrievers/base.py`). Override `search_many` to share work across strategies.
- **An embedding model or instruction:** embed with `scripts/embedding/embed.py`, then
  `retrieve --embedding <slug> --instruction <name>`. Only the documented embedding release files
  are read; the embedding code is not imported.

## Code

```
rag.py                 CLI
strategies.yaml        strategy → Tipo sets, grouping Tipos, unit precedence, expected counts
data/                  P&R chapter ranges (from the PDF table of contents)
ragpipe/data.py        loading of chunks, dataset and embedding outputs; input checks
ragpipe/strategies.py  strategy filters, text ↔ chunk aliasing
ragpipe/retrievers/    Retriever protocol, dense retriever
ragpipe/retrieval.py   stage R driver
ragpipe/relevance.py   gold items and the gold ↔ chunk matcher (shared with answer evaluation)
ragpipe/context.py     containment de-duplication, k / budget selection, header and template rendering
ragpipe/exclusions.py  corpus exclusion list (corpus_exclusions.yaml) → excluded chunk rows
ragpipe/contexts.py    stage C driver: context sets, oracle, wrong-context donors, gold coverage
ragpipe/generation.py  stage G driver: registry, prompts, run loop on llm_client, grounding checks, outputs
llms.yaml              generator registry (providers, pinned models, parameters, prices, FX rate)
experiments/           versioned experiment files (pilot.yaml)
prompts/               context_v1/v2.pt.md (context templates; v2 the default); answer_v1.pt.md,
                       answer_closed_v1.pt.md (system part, a '<<<USER>>>' line, user part)
ragpipe/metrics.py     IR metrics, paired bootstrap / permutation
ragpipe/evaluation.py  stage RE driver and aggregation
ragpipe/report.py      metrics → markdown
ragpipe/runs.py        manifests, hashing, deterministic writing
tests/                 pytest on a fixture corpus with random vectors (no network, no GPU)
```

Run the tests with `.venv/bin/python -m pytest scripts/rag/tests`.

## License and citation

Code under the repository license; dataset BR-TaxQA-R v2.0 under CC BY 4.0. Citation: to be added
with the paper.
