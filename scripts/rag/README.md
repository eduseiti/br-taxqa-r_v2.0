# RAG pipeline — BR-TaxQA-R v2.0 segmentation experiment

Tests whether **hierarchical segmentation** of the legal documents cited by the *Perguntas e
Respostas IRPF 2024* gives better chunks for answering its questions. This directory holds the
pipeline code. Design: `docs/20260927_204356_rag_pipeline_implementation_plan.md`.

**Status: Phase 1 (retrieval and its evaluation, "the legal-provision test").** Context formatting
(Phase 2) and answer generation (Phase 3) are not implemented yet.

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
.venv/bin/python $R retrieve --embedding jua-4b-mixed                          # S1, S2, S3; top-1000 (≈10 s)
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf      # ≈15 s
.venv/bin/python $R compare  --retrieval runs/retrieval/jua-4b-mixed/irpf --a S1 --b S2
```

Then read `runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_skip/report.md`.

Options (every subcommand has `--help` with an example):

| Subcommand | Main options |
|---|---|
| `check` | `--embedding` (required), `--instruction` (default `irpf`, or the only one), `--no-hash` |
| `retrieve` | `--strategies S1,S2,S3`, `--top-n 1000`, `--force` (replace a run made with other settings) |
| `evaluate` | `--annex-rule {either,main_first}`, `--budgets 1000,…,16000`, `--unit-ks`, `--raw-ks`, `--dedup {containment,none}`, `--overflow {skip,stop}`, `--comparisons S1:S2,S2:S3`, `--eval-id` |
| `compare` | `--a`, `--b`, `--views budget,unit,raw`, `--eval-id` |
| `report` | `--eval <eval dir>` (regenerate `report.md`) |

Input locations default to the repository layout and can be changed with `--chunks`, `--dataset`,
`--embeddings-dir`, `--runs-dir` and `--strategies-file`.

## What is measured

**Strategies** (`strategies.yaml`): the chunk types each one indexes.

| | Tipos | Chunks | Texts |
|---|---|---:|---:|
| S1 | ART, DSP, TXT, TAB | 26,250 | 26,208 |
| S2 | S1 + CPT, PAR, INC, ALI, ITE | 82,642 | 79,508 |
| S3 | S2 + PRT, LIV, TIT, SBT, CAP, SEC, SSC | 87,702 | 84,568 |

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

- **A strategy:** add an entry to `strategies.yaml` (the Tipos it indexes and, optionally, the
  expected chunk count). No code change.
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
ragpipe/context.py     containment de-duplication, k / budget selection
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
