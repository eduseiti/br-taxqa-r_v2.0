# First RAG evaluation — what is missing, costs, scope and grounding safeguards

**Generated:** 2026-10-21 19:44:57 (local time, from `date +%Y%m%d_%H%M%S`).
**Context:** nuggetization phases 2–4 are done (`docs/20261021_155704_nuggetization_phases_2_to_4_execution.md`,
frozen set `nuggets/gold/v0-auto/`). This note records the discussion of 2026-10-21 on what the first RAG answer
evaluation still needs, with the user's answers and new information (§0). Plans it builds on:
`docs/20260927_204356_rag_pipeline_implementation_plan.md` (**RAG plan**) and
`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (**plan v2**).
**Status:** discussion and decisions only; no code changed, no API call made (only free model listings and the
OpenRouter key status).

## 0. New information and decisions from the user (2026-10-21)

| # | Item |
|---|---|
| U1 | **OpenRouter cap raised to $100.** `nuggets.py openrouter-key` (19:44): usage $65.61, **$34.39 left**, expires 2026-11-20. The account had $150 prepaid (2026-10-20), so ≈ $84 of prepaid credit is left behind the cap |
| U2 | **Maritaca AI key** created: `MARITACA_API_KEY` in the repo-root `.env`. Checked: `GET https://chat.maritaca.ai/api/models` lists `sabia-4`, `sabiazinho-4`, `sabia-4-thinking` and their `-br-sp` variants |
| U3 | **Generators:** Sabiá-4 and Sabiazinho-4, plus at least one pair of strong frontier models, preferably OpenAI but **not GPT "sol"** (the `gpt-6.1-sol` family created the primary nugget set). Suggestions in §5 |
| U4 | **DeepSeek** models are wanted too, but they cannot be reached from this environment; they run later, from another machine (see the two-machine note in memory). Keep them in `llms.yaml` and in the experiment files so that run is only a config switch |
| U5 | **Agreed:** add the per-question retrieval ↔ answer linkage to phase 5 (§3.1) |

## 1. What is missing before the first RAG evaluation

The retrieval stage (RAG Phase 1) is done: `rag.py check --embedding jua-4b-mixed` passes (2026-10-21), the
rankings of S1/S2/S3/S2c/S4 are in `runs/retrieval/jua-4b-mixed/irpf/`, and the legal-provision test is in
`eval/v2d_either_containment_skip/`. The nuggets are frozen. Missing:

| # | Missing | Where | Notes |
|---|---|---|---|
| 1 | **RAG Phase 2 — context:** `context` subcommand, provenance header per chunk (`[Documento n] Lei nº … — Art. 8º, II, b`), versioned template `context_v1.pt.md`, the **closed-book** (`k=0`) and **oracle** contexts, `runs/contexts/…` | `scripts/rag/ragpipe/context.py` (selection exists) | Gate: pilot contexts read by hand (RAG plan §9) |
| 2 | **RAG Phase 3 — generation:** `llms.yaml` registry, `answer_v1.pt.md`, `generate` / `run --experiment`, `--dry-run` cost estimate, `answers.jsonl` + `run.json`, ledger `runs/costs.csv`, `fake` provider and tests | `scripts/rag/` on the shared `scripts/llm_client/` | Gate: 30-question pilot (`stratified_30`), answers read by hand, cost per full run estimated |
| 3 | **Maritaca provider:** not on OpenRouter, so a direct `openai_compat` route (`https://chat.maritaca.ai/api`, `MARITACA_API_KEY`) with cache, ledger and the grounding checks of §4 | `scripts/llm_client/client.py` | Prices in BRL (§2.1); the ledger needs a BRL→USD rate column or a fixed rate recorded per run |
| 4 | **Nugget phase 5 — scoring:** `nuggets.py` has no `score` command | `scripts/nuggets/` | Judge assignment of system answers (`assign_v2`, Flash), V_strict/V/A_strict/A/W, contradiction rate, value checks (plan v2 §5.4), legal-provision score (§5.5), paired bootstrap + chapter-cluster bootstrap, perturbation robustness (§5.6), judge agreement on real answers (the deferred real-run part of phase 4), and the linkage of §3.1 |
| 5 | **Open decisions:** headline budget (4k was a placeholder; S2 vs S1 article recall 0.47 vs 0.38 at 4k, 0.57 vs 0.48 at 8k), the "expanded" score on `has_pointer` questions, reasoning effort of the generators (§5) | user | |
| 6 | **Budget:** $34.39 on the OpenRouter key covers the pilot, not the full first evaluation (§2.3) | user | |

## 2. Cost estimates (only `jua-4b-mixed`)

**Retrieval costs nothing more:** query and corpus vectors are stored, rankings regenerate locally in ≈ 30 s.
Having one embedding model only removes a grid dimension. A BM25 baseline (RAG plan Phase 1b) would be a free
second retriever.

### 2.1 Prices (checked 2026-10-21)

OpenRouter public model list (`/api/v1/models`, per 1M tokens, list price; OpenAI and Gemini have half-price flex
endpoints on OpenRouter, to be confirmed per model with a probe as in `probe_openrouter.py`). Maritaca official
pricing page (`docs.maritaca.ai/pt/precos`, BRL); USD figures below assume **R$ 5.5 / US$** (to be replaced by
the rate on the billing date).

| Model | Released | Input | Output | Notes |
|---|---|---:|---:|---|
| `sabia-4` (pin `sabia-4-2026-01-06`) | 2026-01-06 | R$ 5,00 (≈ $0.91) | R$ 20,00 (≈ $3.64) | cache R$ 1,25; **flex / batch / night (22–06 BRT) −50 % / −30 %**; 128k context |
| `sabiazinho-4` (pin `sabiazinho-4-2026-01-06`) | 2026-01-06 | R$ 1,00 (≈ $0.18) | R$ 4,00 (≈ $0.73) | same discounts; 128k context |
| `sabia-4-thinking` | 2026 | R$ 5,00 | R$ 40,00 | 1M context; not proposed (reasoning cost, no non-thinking twin of Sabiazinho) |
| `openai/gpt-6-astra` | 2026-09-04 | $10.00 | $50.00 | OpenAI's top tier |
| `openai/gpt-5.6-terra` | 2026-07-09 | $2.00 | $12.00 | |
| `openai/gpt-5.6-luna` | 2026-07-09 | $0.20 | $1.20 | |
| `openai/gpt-6-luna` | 2026-09-22 | $0.10 | $0.50 | |
| `anthropic/claude-sonnet-5.5` | 2026-09-28 | $2.00 | $10.00 | |
| `anthropic/claude-haiku-5.5` | 2026-10-07 | $0.10 | $0.50 | |
| `deepseek/deepseek-v4-pro` | 2026 | $0.41 | $0.83 | later, from the other machine (U4) |
| `deepseek/deepseek-v4-flash` | 2026 | $0.09 | $0.18 | later (U4) |

Maritaca also sells **built-in tools** (web search R$ 0,0165 per search, page reads R$ 0,066 per page), reported in
`usage.tool_execution_details`: see §4.1.

### 2.2 Per-call and per-run assumptions

Input ≈ context budget + ≈ 0.9k tokens (instructions, question, chunk headers); output ≈ 0.7k visible tokens, plus
≈ 0.3k reasoning at low effort where a model reasons. Budgets are counted in Qwen3 tokens, so each generator's own
count differs by ≈ ±20 %. One full run = 715 questions; at 4k ≈ 3.5M input and 0.5M output.

| Generator, one full run | closed-book | 4k | 8k | 16k |
|---|---:|---:|---:|---:|
| Sabiá-4 (list / flex) | R$ 13 / 6 | **R$ 28 / 14** (≈ $5 / 2.5) | R$ 44 / 22 | R$ 76 / 38 |
| Sabiazinho-4 (list / flex) | R$ 3 / 1.3 | **R$ 5.5 / 2.8** (≈ $1 / 0.5) | R$ 9 / 4.5 | R$ 15 / 7.5 |
| `gpt-6-astra`, low effort (list / flex) | $41 / 20 | **$70 / 35** | $100 / 50 | $165 / 82 |
| `gpt-5.6-terra`, minimal effort (list / flex) | $7 / 3.5 | **$13 / 6.5** | $19 / 10 | $33 / 17 |
| `gpt-5.6-luna` / `gpt-6-luna` | $0.7 / 0.4 | $1.3 / 0.7 | $2 / 1 | $3.5 / 1.8 |
| `claude-sonnet-5.5` / `claude-haiku-5.5` | $6 / 0.3 | $12 / 0.6 | $18 / 0.9 | $31 / 1.5 |

**Scoring** (Flash flex, primary nugget set): the Flash self-score of a 715-question set cost $0.95 on the gold
answers (phases 2–4 ledger); system answers are longer, so **≈ $1.0–1.5 per answer run and nugget set**. The
judge reads nuggets + answer, not the context, so this does not grow with the budget. The context-support check
of §4.3 costs ≈ $2 per context set (it reads the context), and is shared by all generators.

### 2.3 Sizing

**Pilot** (`stratified_30`, the RAG Phase 3 gate): 11 contexts per generator (S1, S2, S3, S2c, S4 at 4k; S1, S2 at
2k and 8k; closed-book; oracle at 4k) = 330 calls per generator.

| Item | Cost |
|---|---:|
| Sabiá-4 + Sabiazinho-4 (Maritaca account, list) | ≈ R$ 15 |
| `gpt-5.6-terra` + `gpt-5.6-luna` (OpenRouter, list / flex) | ≈ $6.5 / 3.5 |
| `gpt-6-astra` on 4 contexts only (S1, S2 at 4k, closed-book, oracle), list / flex | ≈ $11 / 5.5 |
| Scoring ≈ 1,450 judge calls + context support (10 contexts × 30) | ≈ $4.5 |
| **OpenRouter total** | **≈ $10–22** (fits the $34.39 left) |

**First full evaluation** (715 questions), the reduced "headline" grid: 5 strategies at 4k + closed-book + oracle
= 7 runs per generator, 4 generators (Sabiá-4, Sabiazinho-4, an OpenAI pair, §5):

| Item | Cost |
|---|---:|
| Maritaca generation (Sabiá-4 7 runs + Sabiazinho-4 7 runs), list / flex | ≈ R$ 230 / 115 |
| `gpt-5.6-terra` + `gpt-5.6-luna`, 7 runs each, flex | ≈ $45 |
| Scoring: 28 runs × primary set | ≈ $28–42 |
| Scoring: Gemini and Qwen sets on S1 vs S2 at 4k, 4 generators (16 runs) | ≈ $16–24 |
| Context support (6 context sets) | ≈ $12 |
| **OpenRouter total** | **≈ $100–125** |

The full 11-run grid adds ≈ 60 % to this. `gpt-6-astra` on the headline grid alone would add ≈ $125 at flex
($250 at list), so it is a candidate for the headline comparison on a subset only (§5). **The key and the
prepaid credit need a top-up before the full first evaluation**; the pilot's ledger replaces these estimates.

## 3. Scope of the next phases: retrieval and answers

- **Retrieval (the legal-provision test):** done in RAG Phase 1 (document / article / provision recall, MRR,
  nDCG@10, context precision, paired S1/S2/S3 comparisons). Not rerun; reported next to the answer scores.
- **Answers vs gold nuggets:** nugget phase 5, the main metric, with the value checks (plan v2 §5.4), the
  legal-provision score of the citations in the answers (§5.5, comparable to the retrieval metrics), and the
  closed-book and oracle runs as bounds.

### 3.1 Retrieval ↔ answer linkage (agreed, U5; added to phase 5)

Join the per-question answer scores with the retrieval outcome of the same context
(`eval/<eval_id>/per_item.csv.gz`: `budget_full_<B>`, `budget_any_<B>`, `rank_full`; `per_question.csv.gz`):

- answer score by **context state**: gold provision fully in context / partly / absent;
- per strategy pair (S2 − S1), split the answer-score difference into the questions where the retrieval outcome
  differs and those where it is the same: "S2 answers better **because** it retrieves better" vs "S2 answers
  better from the same evidence (better chunk form)";
- nugget support in the context (§4.3) as the mediator: answer recall is bounded by the share of nuggets the
  context supports;
- report the correlation of context recall / context precision with V_strict per strategy and budget.

No extra API cost beyond §4.3.

## 4. Keeping the generators on the retrieved segments

### 4.1 Web search: blocked at the API level

- **No tools in generation requests.** `scripts/llm_client/` sends no `tools` or `plugins` today. Add a hard check
  that refuses a generation request with `tools`, `plugins`, `web_search_options` or a model id ending in
  `:online` (OpenRouter web search runs only through the `web` plugin or the `:online` suffix, $0.01 per request on
  these models; OpenAI and Gemini search grounding run only as tools).
- **Maritaca has built-in tools** (web search, page reading, code execution, Data Ocean). Send no `tools`, and
  reject a reply whose `usage.tool_execution_details` shows any web search or page read.
- **Check every reply:** reject tool calls, `url_citation` annotations, or a billed cost above the token cost
  (`usd_billed` vs tokens × price); log the reason in the ledger.
- Keep the pinned providers with `allow_fallbacks: false` on OpenRouter, as for the nuggets. No search-native
  models in `llms.yaml`.

### 4.2 Own (parametric) knowledge: discouraged and measured

It cannot be switched off. The P&R 2024 is public and probably in the training data of every candidate.

1. **Prompt (`answer_v1`):** answer only from the numbered provisions; cite `[Documento n]` for every statement;
   write no value, date or rate absent from the provisions; if they are not enough, reply with a fixed abstention
   sentence (gives an abstention rate); do not name a "current" law or year beyond the context.
2. **Structured output with quotes:** each claim with `{document ids, verbatim quote}`; a script checks that the
   quote is a substring of the cited chunk. Claims without a valid quote count as ungrounded (no LLM).
3. **Values not in the context:** extract R$, %, dates from the answer (`nuggetizer/values.py`); flag any value
   absent from both the context and the question. Catches the worst leak: 2025 tables or limits from training.
4. **Controls:**
   - closed-book (`k=0`): what the model knows without retrieval;
   - **wrong context:** another question's context; a good score there means the model is not reading it;
   - the "gold missing from context" slice (§3.1): support there points to own knowledge (or redundant provisions).
5. **Nugget support in the context (§4.3):** the judge assigns the gold nuggets against the context itself, once
   per strategy × budget, shared by all generators. A nugget supported by the answer but not by its context is a
   direct, per-nugget leakage measure.
6. **Memorization:** n-gram overlap of the answer with gold-answer text that is not in the context (the model
   recites the P&R).
7. **Settings:** low or minimal reasoning, temperature 0 where allowed, knowledge cutoff recorded per generator in
   `llms.yaml`.

Items 1–3 cost nothing extra; 4–5 add ≈ 10–20 % to the scoring budget and give the paper a measured leakage
figure.

### 4.3 Context-support call

`assign_v2` with the context in place of the answer (a new prompt version, e.g. `assign_ctx_v1`, since the
context is legal text, not an answer). Output per nugget: supported by the context or not. Cost ≈ $2 per context
set (715 questions at 4k, Flash flex).

## 5. Generator suggestions (U3)

Constraints: the primary nugget set is GPT (`gpt-6.1-sol`), the second set and auditor 1 are Gemini 3.1 Pro, the
judge is Gemini 3.8 Flash, the third set and auditor 2 are Qwen3.8-Max. A generator from none of these families
avoids every overlap; an OpenAI generator overlaps with the creator **vendor** even when it is not "sol" (plan v2
§6.2: it cancels in the paired strategy comparisons, and the three nugget sets control the cross-generator table).

| Pair | Large | Small | Pros | Cons |
|---|---|---|---|---|
| **A (recommended for the grid): OpenAI 5.6** | `gpt-5.6-terra` ($2 / $12) | `gpt-5.6-luna` ($0.20 / $1.20) | A clean large/small pair of one release, like Sabiá-4 / Sabiazinho-4; an older generation than the creator `gpt-6.1-sol` (less stylistic overlap, earlier knowledge cutoff → less post-2024 law); affordable on the full grid | Not OpenAI's top tier |
| **B: OpenAI 6** | `gpt-6-astra` ($10 / $50) | `gpt-6-luna` ($0.10 / $0.50) | The strongest OpenAI model | Astra ≈ $35–70 per run: only on the headline comparison (S1 vs S2 at 4k + closed-book + oracle), ideally on `stratified_70`; same generation as the creator |
| **C (optional, no family overlap): Anthropic** | `claude-sonnet-5.5` ($2 / $10) | `claude-haiku-5.5` ($0.10 / $0.50) | No overlap with creator, auditors or judge; costs like pair A | A third vendor to pin and probe |

**Recommendation:** Sabiá-4 + Sabiazinho-4 (pinned `-2026-01-06`, non-thinking, flex tier for the full runs) and
**pair A** for the grid; `gpt-6-astra` as a "ceiling" generator on the headline comparison of a subset if the
budget allows; pair C if a vendor without overlap is wanted. DeepSeek V4 Pro / Flash later (U4), as a fourth
pair. The `-br-sp` Maritaca variants cost 30 % more for in-country processing and are not needed here.

To confirm in the pilot: which reasoning-effort levels each OpenAI model accepts (minimal / none / low), flex
availability on OpenRouter for terra, luna and astra, and the provider pin for each.

## 6. Next steps

1. RAG Phase 2 (`context`, closed-book, oracle, wrong-context control) → contexts of the pilot read by hand.
2. RAG Phase 3 (`llms.yaml` with Maritaca + pair A [+ astra, pair C, DeepSeek disabled here], `answer_v1`,
   grounding checks of §4.1, `--dry-run`) → pilot on `stratified_30`, answers read by hand, cost ledger.
3. Nugget phase 5 `score` (with §3.1 and §4.3) on the pilot answers; judge agreement on real answers.
4. Top up the OpenRouter key / credit with the pilot's measured costs, then the first full evaluation (§2.3).
