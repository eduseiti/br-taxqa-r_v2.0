# RAG Pipeline Implementation Plan (retrieval first)

**Generated:** 2026-09-27 20:43:56 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** plan only. Nothing has been implemented or run.
**Goal:** build the full RAG pipeline for the segmentation experiment (retrieval → context
selection → answer generation → hand-off to nugget evaluation), but implement and run **only the
retrieval stage first**. The first run is a **legal-provision retrieval test** with the existing
`jua-4b-mixed` embeddings. It gives an early view of how the segmentation strategies (S1 / S2 / S3)
affect retrieval, before any LLM money is spent.
**Deliverables:** code in `scripts/rag/`, outputs in `runs/`. The code will be **released with the
research**, so clean design, documentation and ease of use are requirements, not extras (§8).

**Background (read first):**

- `docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` — the strategies, and §7
  (token budget instead of raw k, containment de-duplication). Referred to below as **the strategy
  doc**.
- `docs/20260925_122058_embedding_implementation_plan.md` — the embedding release format (§4.2) this
  pipeline reads. Referred to below as **the embedding plan**.
- `docs/20260926_112714_gold_answer_nuggetization_plan.md` — the answer-evaluation side: the input
  contract for system answers (§4.1), the generator LLMs (D1) and the legal-provision score (§4.5).
  Referred to below as **the nugget plan**.
- `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md` — the v2.0 `references` config,
  which is the gold standard for retrieval, and its open issues (§7).

---

## 1. Scope and staging

| Stage | What it does | LLM? | Implemented in |
|---|---|---|---|
| **R — Retrieve** | Rank the chunks of each strategy for each question, using stored query and corpus vectors | no | **Phase 1 (now)** |
| **RE — Retrieval evaluation** | Score the rankings against the gold references at document, article and provision level (the "legal-provision test") | no | **Phase 1 (now)** |
| C — Context selection | De-duplicate and cut a ranking to k chunks or a token budget, then format the context | no | Phase 2 |
| G — Generate (aggregation) | Answer each question from its context with an LLM | yes | Phase 3 |
| E — Answer evaluation | Nugget scoring and the legal-provision score of the answers | yes | nugget plan (`scripts/nuggets/`) |

The stages talk to each other **only through files** with documented formats (§5). Each stage can
be rerun, replaced or released on its own. For example, a reranker could later be added between R and
C without touching the other stages. Stage E stays in `scripts/nuggets/`, as the nugget plan
decided: it reads the answer files that stage G writes and knows nothing about retrieval.

Phase 1 must still be **designed for the whole pipeline**. The run layout, the manifests, the
strategy definitions and the relevance matcher are used by all later stages, so they are built
properly now, not as throw-away scripts.

---

## 2. Facts this plan relies on (checked 2026-09-27)

| Item | Value |
|---|---|
| Chunks | `segmented/chunks_all.csv.gz`, 87,702 rows / 84,568 unique texts, SHA-256 `f3db0904…55f9b`. This is the same file the `jua-4b-mixed` corpus manifest records |
| Corpus vectors | `embeddings/jua-4b-mixed/corpus/vectors.npy`, float32 [84,568 × 2,560], rows in `text_id` order; `chunk_map.csv.gz` maps `chunk_id → text_id` |
| Query vectors | `embeddings/jua-4b-mixed/queries/irpf/vectors.npy`, 715 rows. The query text inside `text_sent` equals `dataset/questions.jsonl` `question_text` for **all 715** questions |
| Chunk rows by `Tipo` | PAR 21,511 · INC 20,617 · ART 20,477 · CPT 8,084 · ALI 4,878 · TXT 3,545 · SEC 2,106 · CAP 1,843 · DSP 1,522 · ITE 1,302 · SSC 714 · TAB 706 · TIT 326 · LIV 45 · SBT 21 · PRT 5 |
| Provenance columns | `arquivo`, `categoria` (`main`/`A`/`B`/`C`/`nao_articulado`), `doc_urn`, `anexo_urn`, `unidade_id`, `artigo_id`, `agrupadores_ids`, `citacao`, `parte`/`n_partes`, `cobre_ids`, `parcial_ids`, `id_ambiguo`, `n_tokens_qwen3`, `Num_Inicio`/`Num_Final` |
| Gold | `dataset/references.jsonl`: 1,919 references; **594 questions** have at least one reference resolved to a corpus document, **550** have at least one cited article id |
| Hardware | 20 cores, 62 GB RAM. Exact brute-force search is enough: Q·Vᵀ for 715 × 84,568 × 2,560 takes seconds in numpy. No ANN index (FAISS etc.) is needed, so there is no approximation error to report |

### 2.1 Known issues that affect the first run ("despite the remaining issues")

The first run uses the corpus and gold as they are now. These issues put an upper limit on the
scores. The evaluator **measures the limit** instead of hiding it:

1. **11 cited documents have no chunks** (empty `<Articulacao>`; 16 references in 6 questions).
2. **19 cited article ids are missing from the LexML** (`build_report.json →
   validation.article_ids_missing`).
3. **42 references are `not_in_corpus`** (acts never fetched).
4. **RIR/2018-style ambiguity:** a citation of Decreto 9.580/2018 art. N may mean the decree's own
   article or the article of its annex (the RIR). The same holds for any document whose annex has
   articles (categoria `A`). See rule G3 in §4.2.
5. `id_ambiguo = 1` on 1,802 rows (the same id occurs more than once in one file).

Each gold item is tagged as **reachable** (at least one chunk in the strategy can match it) or
**unreachable**. Metrics are reported (a) over all resolved gold, with the **oracle ceiling**
(the best possible value) shown next to them, and (b) over reachable gold only. Retrieval is cheap,
so the whole test is simply rerun once these issues are fixed. The report records the chunk and
dataset hashes, so results from different fix levels are never mixed up.

---

## 3. Stage R — retrieval

### 3.1 Strategies as configuration

`scripts/rag/strategies.yaml` defines each strategy as the set of `Tipo`s it indexes. It follows the
strategy doc (§5) and the segmentation results:

```yaml
strategies:
  S1: {tipos: [ART, DSP, TXT, TAB],                                  description: "Article (or top-level dispositivo) + non-statutory units"}
  S2: {tipos: [ART, DSP, TXT, TAB, CPT, PAR, INC, ALI, ITE],         description: "S1 + sub-article units with ancestor path"}
  S3: {tipos: [ART, DSP, TXT, TAB, CPT, PAR, INC, ALI, ITE, PRT, LIV, TIT, SBT, CAP, SEC, SSC], description: "S2 + grouping chunks"}
# Coarse-to-fine order, used when one text belongs to several chunks (§3.3)
unit_precedence: [PRT, LIV, TIT, SBT, CAP, SEC, SSC, ART, DSP, TXT, TAB, CPT, PAR, INC, ALI, ITE]
```

New strategies (for example "leaves only", which the strategy doc mentions as an extra) are added
with a YAML entry and no code change. At load time the code checks that the S1/S2/S3 row counts
match the segmentation results (S1 = 26,252, S2 = 82,644, S3 = 87,947 after the 2026-09-25
re-run; the expected counts are stored in the YAML and checked with a warning, not an error).

### 3.2 Retriever interface

```python
class Retriever(Protocol):
    name: str
    def info(self) -> dict: ...                     # goes into the manifest
    def search(self, query_ids: list[str], candidate_text_ids: np.ndarray,
               top_n: int) -> list[list[tuple[str, float]]]: ...   # (text_id, score), best first
```

- **`dense`** (Phase 1): loads `vectors.npy` with `mmap_mode="r"`, restricts it to the
  strategy's candidate rows, and computes exact cosine scores (the vectors are L2-normalized, so
  this is a dot product). It works in query blocks to keep memory bounded. Ties are broken by
  `text_id`, so the output is deterministic.
- **`bm25`** (optional, cheap): a lexical baseline over the same `Texto`, useful to check that
  strategy effects are not an artifact of one embedding model. It is listed here so the interface
  is not built around dense retrieval only. It is not needed for the first run.
- Retrieval works on **texts**, not chunks, because vectors are stored per unique text. Each strategy
  is searched separately (S1, S2 and S3 have different candidate sets), but **all strategies share
  one scoring pass**: scores are computed once over all 84,568 texts and then filtered per strategy.
  The result is the same, and it costs less.

### 3.3 From texts back to chunks

Several chunks can share one text (for example an `ART` whose only content is one inciso has the
same text as that `INC` chunk). Inside one strategy they would get the same score and fill several
ranks with the same content. So each ranked item is **one text**, represented by its coarsest chunk
(by `unit_precedence`). The other chunks with that text are kept as `alias_chunk_ids`. The relevance
matcher uses the union of the provenance of the chunk and its aliases.

### 3.4 Output

Retrieval keeps the **top-N = 1,000** texts per question and strategy (configurable). That is deep
enough for Recall@1000 and for any token budget up to 16k tokens, even after de-duplication.
Context selection and generation then read the stored ranking and never search again. §5 gives the
file layout.

---

## 4. Stage RE — retrieval evaluation (the legal-provision test)

### 4.1 Gold items

From `dataset/references.jsonl`, rows with `document_id` not null, per question:

- **Document level:** the set of cited `document_id`s.
- **Article level:** the set of `(document_id, article_id)` from the row-level `article_ids`.
  References without article ids (for example non-statutory acts cited as a whole) take part only
  at document level.
- **Provision level:** `(lexml_file, fragment_id)` from `provisions[]`, the nested LexML ids parsed
  from the citation text (`art1_cpt_inc10`, `art12_par1_inc2`;
  `docs/20260927_213420_reference_provisions_from_citation_text.md`). Units with `fragment_id` or
  `lexml_file` `null` (41 not in the XML, 36 without an id form) are unreachable gold at this
  level.

`origin` (`explicit` / `embedded`) is kept on each gold item so results can be sliced by it.

### 4.2 Matching gold to chunks (`relevance.py`)

The matcher is **shared** with the later legal-provision score of the answers (nugget plan §4.5),
so both use one definition of "the right provision".

- **G1. Chunk → document.** `arquivo` → `document_id` through `documents.jsonl` (`lexml_file` and
  `lexml_annex_files`). This uses the file, not the URN, so the URN-quality issues of the
  non-statutory documents (dataset doc §7.5) do not affect it.
- **G2. Chunk → article.** `(document_id, artigo_id)`. Any chunk of an article counts as an article
  hit, including a single inciso, a paragraph or an article part (`parte`/`n_partes`). For the
  **grouping** chunks of S3, an article is hit when the grouping contains it (interval containment
  through `Num_Inicio`/`Num_Final` within the same `arquivo`).
- **G3. Main or annex (RIR/2018 case).** The gold says "document D, article N". Default rule: it
  matches article N in **the main file or in any annex file of D**. The number of gold items where
  both exist is reported, and the stricter "main first, annex only if the main file lacks it" rule
  (the one the dataset builder uses to validate article ids) is a switch
  (`--annex-rule {either,main_first}`), so its effect can be shown.
- **G4.** A match that goes only through an `id_ambiguo = 1` chunk is counted, but also reported
  separately.
- **G5. Chunk → provision.** A gold unit is **fully hit** by a chunk of the same `lexml_file` when
  an id in the chunk's `cobre_ids` equals the `fragment_id` or is its ancestor (prefix up to a
  `_`): the chunk holds the whole unit. It is **partly hit** when the `fragment_id` is an ancestor
  of a `cobre_ids` id, or appears in `parcial_ids`: the chunk holds only part of it (e.g. one inciso
  of a cited paragraph). Recall counts full hits; partial hits are reported next to them.
- **Relevance is binary** (gain 1 for nDCG) at document and article level: a hit on the right
  inciso counts as much as a hit on the whole article. At provision level the full/partial split
  above is what measures "which part".

### 4.3 Making strategies comparable

The strategy doc (§7) warns that raw k is not comparable: an S1 chunk is a whole article, an S2
chunk may be one inciso. Three views are therefore reported, and **the token-budget view is the
headline**, because it matches what the LLM will get:

| View | Ranked list | Cutoffs | Question it answers |
|---|---|---|---|
| **Token budget** (headline) | Texts in rank order after containment de-duplication (§6.1), taken while they fit in the budget, counted in `n_tokens_qwen3` | B ∈ {1k, 2k, 4k, 8k, 16k} | "With the same amount of context, which strategy brings more of the cited provisions?" |
| **Unit projection** | Chunk ranking projected to distinct gold units (first rank at which each document / article appears) | k ∈ {1, 3, 5, 10, 20, 50, 100} | "How high does the right article or document rank?" This is the one that can be compared with other retrieval papers |
| Raw chunk rank | Texts as retrieved | k ∈ {1, 5, 10, 20, 50, 100, 1000} | Diagnostic only |

The token-budget view uses **the same selection code as stage C** (§6.1), so the retrieval numbers
describe exactly the contexts the generator will see.

### 4.4 Metrics

Per question, then averaged over questions that have at least one gold item at that level
(document, article, provision):

- **Recall** (fraction of gold items hit), **Hit** (at least one gold item hit), **Full recall** (all
  gold items hit);
- **MRR** and **nDCG@10** on the unit-projection view;
- **Context precision** on the token-budget view: the fraction of context tokens that come from
  gold documents / gold articles. This shows the "less noise" part of the S2 hypothesis (strategy doc
  §5.1);
- the **oracle ceiling** per level and the counts of reachable and unreachable gold (§2.1).

**Slices:** `origin` (explicit / embedded), statutory vs non-statutory gold, category-A annex gold,
and the chapter of the Q&A document.

**Paired comparison** S1 vs S2 and S2 vs S3: per-question differences with a **paired bootstrap**
(10,000 resamples, fixed seed) 95 % CI and a **permutation test** p-value. The per-question table
is saved, so other tests can be run later.

### 4.5 Output of the first run

A dated `docs/…_retrieval_legal_provision_test_jua.md` note with:

1. the headline table: S1 / S2 / S3 × {document, article, provision} × token budget (recall, hit,
   context precision), with the oracle ceiling;
2. the unit-projection table (Recall@k, MRR, nDCG@10);
3. the paired-difference CIs;
4. the reachability counts and the list of the known issues (§2.1) in force at run time;
5. a few worked examples (questions where S2 finds the cited inciso and S1 misses it, and the
   reverse).

This test is **provisional**. It uses one embedding model and a corpus with known gaps. It is meant
to see whether segmentation moves retrieval at all and in which direction, and to size the budgets
for the generation grid. It is not a paper result.

---

## 5. Run layout and formats

```
runs/
  retrieval/<embedding>/<instruction>/                       e.g. jua-4b-mixed/irpf/
    manifest.json                                            provenance (§8.3)
    <strategy>/rankings.csv.gz                               question_number, rank, text_id, chunk_id, alias_chunk_ids, score
    eval/<eval_id>/metrics.csv                               long format: strategy, level, view, cutoff, metric, value, n_questions
    eval/<eval_id>/per_question.csv.gz                       one row per question × strategy × level × view × cutoff (for paired tests)
    eval/<eval_id>/report.md                                 generated tables
    eval/<eval_id>/manifest.json                             gold file hash, matcher rules (annex rule, gains), cutoffs
  contexts/<context_id>/contexts.jsonl + manifest.json      Phase 2 (§6)
  answers/<run_id>/answers.jsonl + run.json + raw/          Phase 3 (§7); answers.jsonl follows nugget plan §4.1
```

- **Ids are readable and deterministic.** `context_id` = `<embedding>__<instruction>__<strategy>__<budget or k>__<dedup>`
  and `run_id` = `<context_id>__<llm>__<prompt version>`. The full config of each run is also hashed
  into the manifest, so two runs with the same id and different settings are detected.
- **Versioned in git:** manifests, `metrics.csv`, `report.md`, the experiment YAML files, and
  `answers.jsonl` + `run.json` (small text). **Not versioned** (released on the HF Hub with the
  vectors): `rankings.csv.gz`, `per_question.csv.gz`, `contexts.jsonl` and the raw LLM responses.
  `.gitignore` gets rules like the ones for `embeddings/`.

---

## 6. Stage C — context selection (Phase 2)

### 6.1 Selection

Input: a stored ranking. Parameters (all recorded in the manifest):

| Parameter | Values | Default |
|---|---|---|
| `cutoff` | `k=<n>` or `budget=<tokens>` | `budget=4000` (to be revisited after §4.5) |
| `dedup` | `none`, `containment` | `containment` |
| `overflow` | `skip` (skip a text that does not fit and keep filling), `stop` | `skip` |
| `order` | `score`, `document` (group by document and sort by position in the document, a common option for legal text) | `score` |
| `token_counter` | `qwen3` (the `n_tokens_qwen3` column) | `qwen3` |

- **Containment de-duplication** (strategy doc §7, [L] §4.2): drop a text whose chunk interval
  `[Num_Inicio, Num_Final]` is inside the interval of a higher-ranked chunk **of the same
  `arquivo`**. The reverse case (a lower-ranked parent after a child) is kept by default, since the
  parent adds text. A `containment_merge` option that replaces the child with the parent is left for
  later.
- **The budget is counted in one fixed tokenizer** (Qwen3, already in the chunk CSV) for every
  generator, so "4k context" means the same text for all LLMs. The generator's own count is checked
  in stage G against its context window.

### 6.2 Formatting

Each selected chunk is rendered with a short header built from provenance, then its `Texto`
(which already starts with the `[ Epígrafe | Ementa ]` prefix):

```
[Documento 3] Lei nº 9.250, de 26 de dezembro de 1995 — Art. 8º, caput, II, b, 10
<Texto>
```

The template is a versioned file (`prompts/context_v1.pt.md`), so the header can change without
code changes. The citation-style path (`citacao`) is in the header so the generator can cite
provisions in a form the legal-provision score can parse later (nugget plan §4.5).

### 6.3 Reference contexts

Two special context sets bound the results and use the same format:

- **closed-book** (`k=0`): no context. It measures what the LLM knows without retrieval.
- **oracle**: the gold articles of each question (by the §4.2 rules), in the same format and budget.
  It measures the best a retriever can do for this generator.

---

## 7. Stage G — generation / aggregation (Phase 3)

### 7.1 Design goal: cheap experiments over LLMs and context size

The parameters most likely to change (LLM, number or budget of retrieved chunks, prompt version,
decoding settings) are **configuration, not code**. There are three ways to set them, from quick to
reproducible:

```bash
R=scripts/rag/rag.py
# 1. One run from the command line
.venv/bin/python $R generate --retrieval runs/retrieval/jua-4b-mixed/irpf --strategy S2 \
    --budget 4000 --llm sabia-3.1
# 2. A small sweep from the command line (comma lists expand to the product)
.venv/bin/python $R generate --retrieval runs/retrieval/jua-4b-mixed/irpf --strategy S1,S2 \
    --budget 2000,4000,8000 --llm sabiazinho-3,deepseek-chat --limit 30
# 3. A versioned experiment file (the form used for the paper runs)
.venv/bin/python $R run --experiment scripts/rag/experiments/pilot.yaml [--dry-run]
```

```yaml
# scripts/rag/experiments/pilot.yaml
name: pilot
questions: {sample: stratified_30, seed: 13}        # or "all", or a list
retrieval: [runs/retrieval/jua-4b-mixed/irpf]
grid:
  strategy: [S1, S2]
  context: [{budget: 2000}, {budget: 4000}, {budget: 8000}, {k: 0}, {oracle: true}]
  llm: [gpt-5.x-mini, sabiazinho-3, deepseek-chat]
  prompt: [answer_v1]
fixed: {dedup: containment, order: score, temperature: 0}
```

- `--dry-run` prints the expanded grid, the number of calls and an **estimated cost** (input tokens
  from the contexts × the prices in `llms.yaml`), and sends nothing. The grid grows fast (strategy ×
  embedding × budget × LLM), so every sweep should be sized before it runs.
- `--limit` / `questions.sample` run a subset (pilot runs), using the same stratified sample as the
  nugget plan so pilot answers can be scored.

### 7.2 LLM registry (`scripts/rag/llms.yaml`)

The code has no model-specific settings; adding a model means adding a YAML entry:

```yaml
llms:
  sabia-3.1:
    provider: openai_compat
    base_url: https://chat.maritaca.ai/api
    model_id: sabia-3.1                     # pin the dated snapshot where the API offers one
    api_key_env: MARITACA_API_KEY
    context_window: 128000
    params: {temperature: 0, max_tokens: 1500}
    price: {usd_per_million_input: null, usd_per_million_output: null, checked: null}
  deepseek-chat:
    provider: openai_compat
    base_url: https://api.deepseek.com
    model_id: deepseek-chat
    api_key_env: DEEPSEEK_API_KEY
    # …
  gpt-5.x-mini:
    provider: openai
    model_id: <pinned snapshot>
    api_key_env: OPENAI_API_KEY
    # …
```

Generators follow nugget plan D1: **OpenAI, Maritaca Sabiá and Sabiazinho, DeepSeek**. Maritaca and
DeepSeek both offer OpenAI-compatible APIs, so **two providers (`openai`, `openai_compat`) cover all
four**, plus `fake` for tests. Model ids, snapshots, limits and prices are checked against the
providers' current documentation at implementation time and pinned in the YAML, as in the embedding
plan.

### 7.3 Prompt

- A versioned pt-BR prompt file (`prompts/answer_v1.pt.md`) with a system part and a user part
  (`{question}`, `{context}`). It asks the model to answer from the given provisions, to say so
  when they are not enough, and to **cite the provisions it used** in standard Brazilian form
  ("art. 8º, II, b, da Lei nº 9.250, de 1995"), so the legal-provision score (nugget plan §4.5) can
  extract them. Note for that score: `lexml-linker` recognises this "provision da Lei" order, but
  not the act-first order of the Q&A document ("Lei nº 11.482, de 2007, art. 1º, inciso X" gives no
  URN; checked 2026-09-27). `scripts/dataset/citations.py`, which parses the gold, handles both
  orders and can be used on the answers too.
- The prompt file's SHA-256 goes into `run.json`. Changing the prompt means a new version file, never
  an edit of a released one.
- Answer length is not capped in the prompt beyond `max_tokens`. Length is reported per run, since
  nugget recall rewards longer answers (nugget plan §4.3, "known limit").

### 7.4 Execution

- **Cache** every raw response, keyed by hash(provider, model id, params, rendered messages). Reruns
  are free and the raw outputs can be released. This is the same scheme as the nugget plan (§5).
- **Resumable:** questions already answered in a run are skipped.
- **Bounded concurrency**, with retry and exponential backoff on 429/5xx; errors are recorded per
  question and never silently dropped (a failed question is marked in `answers.jsonl` with
  `"error"`, and `run.json` counts them).
- **Outputs:** `answers.jsonl` in the nugget plan's input contract
  (`{"run_id", "question_number", "answer"}`) plus `context_id` and token usage per line, and
  `run.json` with the full config, the context manifest pointer, token totals and cost. Cost rows
  also go into a ledger `runs/costs.csv`, like `embeddings/costs.csv`.

### 7.5 Shared LLM client (decision to confirm)

Stage G and the nugget scripts both need the same providers, cache, retry and cost accounting.
Recommendation: **one small shared package** (for example `scripts/llm_client/`) used by both
`scripts/rag/` and `scripts/nuggets/`, instead of two copies. Whichever of the two is implemented
first creates it. The alternative (a copy in each, as self-contained as `scripts/embedding/`) is
simpler to release one piece at a time, but the two copies would drift.

---

## 8. Code design and release quality

### 8.1 Files

```
scripts/rag/
  README.md                 quick start, formats, reproducing the paper runs (§8.4)
  rag.py                    CLI entry point (argparse subcommands)
  strategies.yaml           strategy → Tipo sets, unit precedence, expected counts (§3.1)
  llms.yaml                 generator registry (§7.2)                          [Phase 3]
  prompts/                  context_v1.pt.md, answer_v1.pt.md                   [Phase 2–3]
  experiments/              versioned experiment grids (§7.1)                   [Phase 3]
  requirements.txt          pinned: numpy, pandas, pyyaml, tqdm (+ openai, python-dotenv in Phase 3)
  .env.example              OPENAI_API_KEY=, MARITACA_API_KEY=, DEEPSEEK_API_KEY=  [Phase 3]
  ragpipe/
    data.py                 load chunks, the v2.0 dataset configs and embedding outputs; all input checks (§8.3)
    strategies.py           strategy filters, text ↔ chunk aliasing (§3.3)
    retrievers/             base.py (Retriever protocol), dense.py, [bm25.py]
    relevance.py            gold items and the gold ↔ chunk matcher (§4.2); shared with answer evaluation
    context.py              de-duplication, k / budget selection, formatting (§6)   [selection used in Phase 1]
    metrics.py              IR metrics, paired bootstrap / permutation (§4.4)
    generation.py           prompt rendering, run loop                             [Phase 3]
    runs.py                 run ids, layout, manifests, config hashing (§5)
    report.py               metrics.csv → markdown tables
  tests/                    pytest; tiny fixture corpus, random vectors, fake LLM; no network, no GPU
```

The embedding code is **not imported**. `ragpipe` reads only the documented embedding output format
(embedding plan §4.2), so the vectors released on the Hub are enough to run retrieval without the
embedding scripts.

### 8.2 CLI

```bash
R=scripts/rag/rag.py
.venv/bin/python $R check    --embedding jua-4b-mixed                    # input checks only (§8.3)
.venv/bin/python $R retrieve --embedding jua-4b-mixed [--instruction irpf] [--strategies S1,S2,S3] [--top-n 1000]
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf [--annex-rule either] [--budgets 1000,2000,4000,8000,16000]
.venv/bin/python $R compare  --retrieval runs/retrieval/jua-4b-mixed/irpf --a S1 --b S2   # paired CIs
.venv/bin/python $R context  --retrieval … --strategy S2 --budget 4000                   # Phase 2
.venv/bin/python $R llms                                                                  # Phase 3: registry + env check
.venv/bin/python $R generate …  |  run --experiment …                                     # Phase 3 (§7.1)
```

- Every subcommand works with only its required option, using the repo's default paths.
- `--help` shows an example for each subcommand. Errors say what to do (for example "no query
  vectors for instruction 'jua_legal'; run `embed.py queries --model jua-4b-mixed
  --instruction-name jua_legal`").
- Phase 1 is just `retrieve` then `evaluate`, and together they should take well under a minute.

### 8.3 Input checks and provenance

`check` (and the start of every stage) fails loudly when:

- the chunk file's SHA-256 differs from `input.sha256` of the embedding corpus manifest (the vectors
  would belong to other chunks);
- `chunk_map.csv.gz` does not cover every `chunk_id`, or `texts.csv` does not match the vector rows;
- query ids or texts differ from `dataset/questions.jsonl` (the text after the instruction prefix
  in `queries.csv → text_sent` must equal `question_text`);
- a gold `document_id` is not in `documents.jsonl`, or a `documents.jsonl` file path does not
  appear in the chunks (reported as "document without chunks", not an error; §2.1).

Every manifest records: git commit + dirty flag, the command line, SHA-256 of every input (chunks,
vectors, query vectors, `references.jsonl`, `strategies.yaml`, prompts), the resolved parameters, the
counts, and timings. This is the same scheme as the segmentation and embedding steps.

### 8.4 README (for release)

1. What the pipeline does, the stage diagram (§1) and the run layout (§5).
2. Install (venv + `pip install -r requirements.txt`).
3. **Quick start with released data:** download the dataset, chunks and vectors from the Hub, then
   `retrieve` → `evaluate` in two commands.
4. Every file format with an example line.
5. How to add a strategy (YAML), a retriever (one class), a generator LLM (YAML) and a prompt
   version (a file).
6. Reproducing the paper runs: the exact experiment files and commands.
7. License and citation.

### 8.5 Code quality

- Type hints; one docstring per module stating its responsibility; docstrings on public functions;
  small functions; no global state apart from the loaded configs.
- **Deterministic:** stable tie-breaking, fixed seeds, sorted outputs, gzip with `mtime=0`; the same
  inputs give byte-identical rankings and metrics.
- **Tests** (pytest, fixture corpus of a few documents with nested articles, an annex and a
  non-statutory file, with random normalized vectors):
  - strategy filtering and text aliasing;
  - the gold matcher: document, article, annex rule, grouping containment, split article parts;
  - containment de-duplication and budget selection (`skip` / `stop`);
  - metrics against hand-computed values (recall, MRR, nDCG, context precision);
  - input checks (hash mismatch, query text mismatch);
  - Phase 3: generation with the `fake` provider, cache hits, resume after a simulated crash, grid
    expansion and `--dry-run` cost estimate.
- **No secrets** in logs, manifests or cached responses.

---

## 9. Phases and gates

| # | Phase | Output | Gate |
|---|---|---|---|
| 1 | **Retrieval + legal-provision test** with `jua-4b-mixed`: scaffold, `data`, `strategies`, `dense` retriever, `relevance`, `context` selection (needed for the budget view), `metrics`, `report`, tests | `runs/retrieval/jua-4b-mixed/irpf/…` + dated `docs/` note (§4.5) | Tests pass; `check` passes; the report shows reachability and ceilings |
| 1b | Optional: `bm25` baseline, instruction ablation (needs `embed.py queries` only) | extra eval ids | — |
| 2 | Context formatting, closed-book and oracle contexts | `runs/contexts/…` | Contexts of a pilot sample reviewed by hand |
| 3 | Generation: LLM registry, prompt v1, cache, run loop; pilot on 30 questions | `runs/answers/<run_id>/…` | Pilot answers read by hand; cost per full run estimated |
| 4 | Full grid (sized with the Phase 1 results and the Phase 3 cost estimate), scoring in `scripts/nuggets/` | answer runs + nugget scores | Nugget plan phases 4–5 |
| 5 | Release: code, rankings, contexts, answers, raw responses | HF dataset files + repo | README quick start works in a clean venv |

Each phase ends with a dated `docs/` note (decisions, results, deviations), and `CLAUDE.md` gets the
`runs/` folder once Phase 1 creates it.

---

## 10. Decisions to confirm (defaults chosen)

1. **Annex rule** (§4.2 G3): `either` by default, `main_first` reported as a variant.
2. **Headline budgets:** 1k / 2k / 4k / 8k / 16k Qwen3 tokens; the generation default (4k) is
   revisited after the Phase 1 results.
3. **Top-N stored:** 1,000 per question and strategy.
4. **Shared LLM client** for `scripts/rag/` and `scripts/nuggets/` (§7.5): recommended.
5. **Package name** `ragpipe` and outputs under `runs/`.
6. **Provision-level retrieval gold** (§4.1): part of Phase 1, now that `references.jsonl` carries
   nested `fragment_id`s (fixed 2026-09-27).
