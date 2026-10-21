# Gold-answer nuggetization — BR-TaxQA-R v2.0

Turns the 715 gold answers into **legal nuggets** (short, self-contained, atomic statements), so the
answers of the RAG generators can be scored against them. Design:
`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (**plan v2**).

**Status (2026-10-13): phase 1 pilot done** on `stratified_30` (`nuggets/pilot/`, $8.29 billed; the last
two 3.1 Pro items ran through Batch, pilot note §11). Every phase 1 item of plan v2 §4 is implemented: three
families, replicates, the 2-call mode, alignment, round trip, two auditors with repair, planted-error
auditor test, known-answer tests and the pilot report. **Phase 2 waits for the user's gate decisions**
(pilot note §12). Read, in this order:

1. `docs/20261012_114025_nuggetization_preview_10_questions.md` — preview v1: API findings, first
   cost estimate, open items;
2. `docs/20261012_154616_nuggetization_preview_open_items_resolution.md` — decisions on R8/judge,
   granularity and git;
3. `docs/20261012_160349_nuggetization_preview_v2_execution.md` — v2/v3 runs, pointer rule (§13);
4. `docs/20261012_192640_nuggetization_phase1_pilot.md` — **the pilot**: results, `answer_cleaned`
   content loss (§8), Gemini 3.1 Pro daily quota (§9), **cost estimate (§10)**, decisions (§12);
5. `docs/20261020_130829_openrouter_support_plan.md` — **OpenRouter route** (default from 2026-10-21):
   design, decisions (§7), implementation and probe results (§8).

## Layout

```
scripts/llm_client/           provider-neutral client (shared with RAG Phase 3 later)
  client.py                   LLM.complete_json(): openai (Responses API), gemini (REST), openai_compat (Qwen),
                              openrouter (Chat Completions, pinned upstream); route_config(); disk cache keyed
                              by the request; ledger rows; --budget cap (BudgetExceeded)
  batch.py                    Batch API jobs (direct route only)
  tests/                      pytest, OpenRouter provider against mocked replies (no network)
scripts/nuggets/
  nuggets.py                  CLI: sample, create [--replicate], importance, validate, selfscore, align,
                              roundtrip, audit, repair, plant, known build|judge, report, pilotreport,
                              batch, openrouter-key
  probe_openrouter.py         one create_v4 call per model through OpenRouter (route checks, plan §5 step 1)
  models.yaml                 registry: model ids, medium-effort params (D12), prices (checked 2026-10-11);
                              `openrouter:` block per model (id, params, pinned provider, served_provider)
  prompts/                    create_v1..v4.pt.md, assign_v1..v2.pt.md (pt-BR; see "Prompts" below)
  nuggetizer/
    data.py                   questions, o200k lengths, stratified samples, user prompt
    schema.py                 pydantic models → strict JSON schemas sent to the APIs
    values.py                 pt-BR value extraction (R$, %, dates, years)
    validate.py               mechanical checks (plan v2 §3.3, §3.5.1), flags
    known_answer.py           known-answer test builders G V Y N D C W E and metrics (plan v2 §5.7)
    planted.py                one planted error per question, to measure auditor sensitivity
    report.py                 report.md: nuggets side by side, validation, self-score, tokens, cost extrapolation
    pilot_report.py           report_pilot.md: agreement, 1 vs 2 calls, round trip, audit, known-answer, costs
nuggets/<run>/                outputs (see "Outputs")
```

## Install and keys

```bash
python3.12 -m venv .venv                       # already exists in the repo checkout
.venv/bin/pip install -r scripts/nuggets/requirements.txt
```

If `.venv/bin/pip` is missing (the venv of the other machine's layout), use
`uv pip install --python .venv/bin/python -r scripts/nuggets/requirements.txt`.

`nuggets.py` loads `.env` (repo root, gitignored) with `python-dotenv`; no shell sourcing is needed.

- **Default route, `--route openrouter`:** only `OPENROUTER_API_KEY=sk-or-v1-...` is needed. The key has a
  credit limit of **$80** (a second cap behind `--budget`) and **expires on 2026-11-20**: renew it before
  then, on both machines. `nuggets.py openrouter-key` prints its limit, usage and expiry (free).
- **`--route direct`** (the preview and pilot runs, and their caches): `OPENAI_API_KEY`, `GEMINI_API_KEY`
  and `DASHSCOPE_API_KEY` (Alibaba Model Studio, **Singapore** region). Setup: plan v2 §8.

## Commands

All from the repository root. Global options go **before** the subcommand.

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
O="--out nuggets/pilot --sample stratified_30 --budget 5.00"   # example; see "Costs and the budget cap"

$P $N --out nuggets/pilot sample            # input/questions.jsonl + sample.json (preview_10, stratified_30)
$P $N $O create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max          # --prompt defaults to create_v4
$P $N $O validate                           # free; rewrites nuggets.jsonl with values/flags/issues
$P $N $O selfscore --judge gemini-3.8-flash --sets gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max  # --prompt assign_v2
for j in gemini-3.1-pro qwen3.8-max gpt-6.1-sol; do
  $P $N $O selfscore --judge $j --sets gpt-6.1-sol                       # the other judges, primary set only
done
$P $N $O report                             # nuggets/pilot/report.md
```

The rest of the phase 1 pilot, as run (pilot note §1; set names: `<model>.rN` replicate, `.2call`,
`.repN` repaired, `.planted`):

```bash
$P $N $O create --models gpt-6.1-sol --replicate 2                      # and 3: same-model noise
$P $N $O importance --source gpt-6.1-sol                                # 2-call mode → create/gpt-6.1-sol.2call
$P $N $O align --pairs gpt-6.1-sol:gemini-3.1-pro,gpt-6.1-sol:qwen3.8-max,gemini-3.1-pro:qwen3.8-max
$P $N $O roundtrip --set gpt-6.1-sol                                    # Flash writes, Qwen checks (check_v2)
for a in gemini-3.1-pro qwen3.8-max; do
  $P $N $O audit --set gpt-6.1-sol --auditor $a --others gemini-3.1-pro,qwen3.8-max
done
$P $N $O repair --set gpt-6.1-sol --auditors gemini-3.1-pro,qwen3.8-max --new gpt-6.1-sol.rep1
$P $N $O validate                                                       # then audit/selfscore on .rep1
$P $N $O known build --set gpt-6.1-sol.rep1
$P $N $O known judge --set gpt-6.1-sol.rep1 --judge gemini-3.8-flash     # and gemini-3.1-pro
$P $N $O plant --set gpt-6.1-sol.rep1                                   # then audit the .planted set
$P $N $O pilotreport                                                    # nuggets/pilot/report_pilot.md
```

- `--sample` names a list in `<out>/sample.json`. `preview_10` = one question per answer-length
  decile (o200k tokens of question + answer, seed 13); `stratified_30` = three per decile, and its
  first pick per decile is `preview_10`. Questions 001 and 003 are the prompt's worked examples and
  are never sampled.
- `--workers` (default 5) is the concurrency **per model**. `create` runs the models in parallel.
- `--route` (global, default `openrouter`) picks the route. **Rerunning a command on `nuggets/pilot/` or a
  preview folder needs `--route direct`**: the route enters the cache key, so the OpenRouter route would call
  the API again instead of reading those caches.
- Several `selfscore` processes may run in parallel on the same `--out`. The ledger is shared, and
  the budget cap reads it before every call.

## OpenRouter route (default)

Every model has an `openrouter:` block in `models.yaml` (plan `docs/20261020_130829_openrouter_support_plan.md`):

| Model | OpenRouter id | Pinned endpoint | Params |
|---|---|---|---|
| `gpt-6.1-sol` | `openai/gpt-6.1-sol` | `openai/flex` (half price) | `reasoning.effort: medium`, strict `json_schema` |
| `gemini-3.1-pro` | `google/gemini-3.1-pro-preview` | `google-ai-studio/flex` (half price) | same |
| `gemini-3.8-flash` | `google/gemini-3.8-flash` | `google-ai-studio/flex` (half price) | same |
| `qwen3.8-max` | `qwen/qwen3.8-max-0902` | `alibaba` (list price; no flex or batch) | `reasoning.max_tokens: 2048`, `json_object` |

- **Pinned:** `only` one endpoint, `allow_fallbacks: false`, `require_parameters: true`,
  `data_collection: deny`. Every reply's upstream provider is checked against `served_provider`; another one
  raises `RouteMismatch` (the call is in the ledger, not in the cache).
- **Ledger:** columns `route`, `provider_served`, `usd_billed` (OpenRouter's `usage.cost`). The budget cap and the
  reports use `usd_billed` when present, else `usd_standard` (batch rows at half). `usd_standard` stays the
  list price of the direct API, for comparison. An older `costs.csv` gets the new columns (empty) on its first
  new row.
- **Errors:** HTTP 402 (key limit or balance used up) raises `CreditsExhausted`, not retried. An upstream error
  in an HTTP 200 reply is retried like a 502. `finish_reason: length` is a truncated reply, retried.
- **No 250/day quota** on Gemini 3.1 Pro: OpenRouter calls Google on its own accounts (do not add our Gemini key
  to OpenRouter as BYOK). **`--batch` is refused on this route**: flex already gives the 50 % discount on
  synchronous calls.
- Probe (2026-10-21, `nuggets/probe_openrouter/`, $0.125): plan §8.

## Batch mode (direct route only; OpenAI and Gemini Batch APIs, 50 % off)

Any command can run in batch mode with `--route direct`. With the global `--batch`, cache hits are served as usual, and every
uncached OpenAI or Gemini request is **queued** instead of called. At the end, one job per model is
submitted (`<out>/batches/`), and the command stops **without writing its outputs**. Qwen
(`openai_compat`, no batch in Singapore) is still called synchronously.

```bash
$P $N $O --batch create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max   # submits the GPT and Gemini jobs
$P $N --out nuggets/<run> batch wait                 # polls every 2 min; caches results as they finish
$P $N $O create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max           # same command, no --batch: all cached
```

- `batch status` lists the jobs; `batch collect` polls once; `batch wait` polls until no job is open
  (jobs finish within 24 h; Gemini expires them after 48 h).
- **Budget:** a job is billed whole, so the cap is checked **at submission**: ledger + estimated job
  cost (the mean cost of the same role and model in the ledger, else a rough token estimate) must stay
  under `--budget`, or nothing is submitted.
- **Ledger:** each result is a row tagged `batch:<tag>`. `usd_standard` stays the synchronous price;
  the budget cap and `report_pilot.md` count batch rows at half (`BATCH_DISCOUNT`).
- A batch result the command's validation rejects (e.g. it misses a nugget number) is called again
  synchronously when the command is rerun.
- `batches/*.json` (job records) are versioned; `batches/*.jsonl` (inputs, full requests) are gitignored.
- Gemini 3.1 Pro's **250 requests/day** quota does not apply to batch jobs (their limit is queued tokens:
  5M for 3.1 Pro at Tier 1, so a full set goes in one or two jobs).

A command that hits a daily quota stops after the other items finish, with `QuotaBlocked`. Completed
calls are cached, so rerunning the same command after the reset resumes where it stopped.

## Prompts

| Prompt | Status | Note |
|---|---|---|
| `create_v1` | superseded | preview v1 |
| `create_v2` | **rejected** | R2 "one nugget per listed object": GPT over-split illustrative lists (execution note §3) |
| `create_v3` | superseded | R2 "follow the answer's structure"; passed both acceptance checks (execution note §8–§9) |
| **`create_v4`** | **current; pilot passed** | `create_v3` + pointer rule: a sentence that only delegates to another question gives no nugget (execution note §13; pilot note §2) |
| `assign_v1` | superseded | penalized the implicit P&R period (R8) |
| **`assign_v2`** | **current** | implicit period: a missing exercício 2024 / ano-calendário 2023 is not a defect; another year is `contradicts` |
| `importance_v1` | tested, not adopted | 2-call mode: importance in a second call (pilot note §4) |
| `align_v1` | current | cross-set alignment, relation per nugget (`gemini-3.8-flash`) |
| `roundtrip_write_v1`, `roundtrip_check_v2` | current | round trip; `check_v1` listed missing legal citations as omissions (pilot note §6.2) |
| `audit_v1` | current | checks C1–C6 of plan v1 §3.4.1, omissions, redundant pairs |
| `repair_v1` | current | appended to the creation prompt; current nuggets + issues both auditors agree on |

**Rule for prompt examples:** never quote or paraphrase a question of `stratified_30` in a prompt;
the sample would then measure leakage. Invent examples (as in `create_v3`/`v4`). Make a new
version (`create_vN`) for any change, and keep the old file: manifests and cache keys refer to the
prompt text.

## Outputs

```
nuggets/<run>/
  sample.json                     samples + dataset SHA-256
  input/questions.jsonl           prepared questions            (gitignored; regenerated by `sample`)
  cache/<sha256>.json             raw API response per request  (gitignored; back it up, see below)
  costs.csv                       ledger: one row per API call, retries included
  create/<model>/                 nuggets.jsonl, validation.json, calls.jsonl, manifest.json
  selfscore/<judge>/<set>/        assignments.jsonl, calls.jsonl, manifest.json
  report.md
```

Existing runs: `nuggets/preview/` (v1 prompts), `nuggets/preview_v2/` (rejected `create_v2`,
creation only), `nuggets/preview_v3/` (`create_v3` + `assign_v2`), `nuggets/pilot/` (phase 1; extra folders
`align/`, `roundtrip/`, `audit/`, `known/`, and `report_pilot.md`), `nuggets/probe_openrouter/` (OpenRouter
route probe, `probe.jsonl`). A full copy, caches included,
is in `../nuggets_backup_20261012_132700/` (outside the repo). From the pilot on, the caches go to
a private HF dataset repo at the end of each phase (resolution note §3.2).

**Cache semantics.** The cache key is the hash of (provider, model id, params, system prompt, user
prompt, schema). Rerunning a command is free and returns the same responses. A **new run with the
same prompt in a new `--out`** calls the API again, because each `--out` has its own cache. The
v3 cache cannot serve `create_v4` (different prompt text).

## Costs and the budget cap

- Every call is logged to `<out>/costs.csv` at the **standard** (synchronous list) price, and, on the
  OpenRouter route, with the **billed** cost (`usd_billed`, flex discount and OpenAI cache writes included).
- `--budget USD` makes the client refuse any call once the ledger of that `--out` reaches the cap.
  It is checked before every call; concurrent workers can overshoot by at most one call each. The
  cap is **cumulative per `--out`**: for a second step in the same folder, set it to the amount
  already spent plus the new allowance.
- **Always pass `--budget`**, and stop and report if a run hits it or costs more than expected.
- **Gemini 3.1 Pro has a daily quota of 250 requests per model** on our tier. The client raises
  `QuotaExhausted` at once (no backoff); `known judge` writes partial results and a rerun completes them
  from the cache. Full runs with 3.1 Pro need the Batch API (pilot note §9.1). The reset time is unclear
(the 429 points to 00:00 UTC, but the quota stayed blocked until about 03:25 UTC), so do not plan around it.
- Measured on the pilot (`stratified_30`, standard prices): pilot note §10 and `report_pilot.md` §1, §9.
- Measured on `preview_10` with `create_v3`/`assign_v2` (standard prices, per 10 questions):
  creation GPT $0.111, Gemini 3.1 Pro $0.327, Qwen3.8-Max $0.146; self-score layout above $0.369.
  So **one full creation + self-score loop on `stratified_30` is ≈ $2.9**. Reasoning length varies
  between runs by up to ≈ 20 % (Gemini Pro). Phase 1–4 estimate: execution note §11.

## Validator codes

| Code | Severity | Meaning |
|---|---|---|
| `number_not_in_source`, `year_not_in_source` | error | a number or year in the nugget is not in the question or answer (R9; 2023/2024 are allowed as the P&R period) |
| `span_not_found` | error | `source_span` not found in the answer |
| `duplicate_of` | error | same normalized text as another nugget |
| `no_vital`, `verdict_count` | error | no vital nugget; a Sim/Não answer without exactly one `resposta_direta` |
| `enum_item_uncovered` | error | an enumerated item of the answer is not covered by any span |
| `span_fuzzy` | warning | span matched only approximately (≥ 85 %) |
| `backreference` | warning | "esse", "tal", "o referido"… (self-containment proxy; often resolved inside the nugget) |
| `value_without_period` | warning | a value without a year or period expression (R8) |
| `pointer_in_text` | warning | "pergunta NNN" in a nugget's text (`create_v4` forbids it) |
| `pointer_uncovered` | warning | an uncovered sentence with a pointer: **expected** under `create_v4`; check it only for a missed content part of a mixed sentence |
| `unit_uncovered` | warning | another uncovered sentence (possible omission) |
| `verdict_polarity`, `many_nuggets` | warning | a "Não" verdict nugget without a negation; more than 40 nuggets |

Flags (filled by the validator from the answer, copied to every nugget): `has_pointer`, `temporal` (the
answer states an R$, % or date value; the "provision amended after 2024-05-03" half of plan v2 §3.1 is not
implemented), `short_answer` (< 80 characters), `procedimento_pgd` (ficha / PGD / campo / código NN).

Coverage rule: a sentence counts as covered when spans cover ≥ 50 % of it; an enumerated item from 30 %
(spans may leave out a long parenthetical); every exact occurrence of a span counts (answers repeat items
verbatim). Pilot note §2.1.

## Provider notes (direct route, checked 2026-10-12; OpenRouter: plan §8)

- `gpt-6.1-sol`: `reasoning.effort: medium`, strict JSON schema, no `temperature`. It reasons very
  little on this task (≈ 140 tokens per creation call). The 3.1k-token prompt prefix is cached
  automatically, at $0.10/M.
- Gemini (`gemini-3.1-pro-preview`, `gemini-3.8-flash`): `thinkingConfig.thinkingLevel: "medium"`,
  `responseJsonSchema`. No implicit caching was reported for the prefix. Flash prices double on
  2027-01-01.
- `qwen3.8-max-0902` (pinned snapshot): `enable_thinking` with `thinking_budget: 2048`.
  **`response_format: json_schema` returned malformed JSON**, so `json_object` + pydantic + retry is
  used. The context cache hits automatically.

## Before phase 2: what is still missing

1. ~~Batch API submit/collect~~ **done** (see "Batch mode").
2. Known-answer builders (phase 4, pilot note §7): W without near-duplicate neighbours; D/C tests whose fact
   is restated elsewhere; V with another period's value from the corpus; the Flash rewrite for conditions
   that are not delimited by punctuation.
3. `--dry-run`, a `fake` provider and tests (plan v2 phase 0 gate). Done in part: the OpenRouter provider has
   tests against mocked replies (`.venv/bin/python -m pytest scripts/llm_client/tests`).
4. The corpus half of the `temporal` flag.

Decisions: `docs/20261013_103834_nuggetization_open_decisions.md`. Closed: `create_v4`, one call, gate
thresholds (+ "flagged by both" on any check, each auditor ≥ 80 % of planted errors). Open: phase 4 builder fixes, cache backup to
the private HF repo, and, still from the plan, the optional "expanded" score on `has_pointer` questions and
the open-weight Qwen judge.
