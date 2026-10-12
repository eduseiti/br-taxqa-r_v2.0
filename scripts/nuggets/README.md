# Gold-answer nuggetization — BR-TaxQA-R v2.0

Turns the 715 gold answers into **legal nuggets** (short, self-contained, atomic statements), so the
answers of the RAG generators can be scored against them. Design:
`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (**plan v2**).

**Status (2026-10-12): preview done, phase 1 pilot not started.** A minimal phase 0 (plan v2 §4) is
implemented: three providers, cache, cost ledger, budget cap, sampling, creation, validation, gold
self-score and a report. It was exercised on 10 questions in three runs (≈ $2.63 in total). Read, in
this order:

1. `docs/20261012_114025_nuggetization_preview_10_questions.md` — preview v1: API findings, first
   cost estimate, open items;
2. `docs/20261012_154616_nuggetization_preview_open_items_resolution.md` — decisions on R8/judge,
   granularity and git;
3. `docs/20261012_160349_nuggetization_preview_v2_execution.md` — v2/v3 runs, **final cost
   estimate (§10–§11)**, pointer rule (§13), next steps (§12).

## Layout

```
scripts/llm_client/           provider-neutral client (shared with RAG Phase 3 later)
  client.py                   LLM.complete_json(): openai (Responses API), gemini (REST), openai_compat (Qwen);
                              disk cache keyed by the request; ledger rows; --budget cap (BudgetExceeded)
scripts/nuggets/
  nuggets.py                  CLI: sample, create, validate, selfscore, report
  models.yaml                 registry: model ids, medium-effort params (D12), prices (checked 2026-10-11)
  prompts/                    create_v1..v4.pt.md, assign_v1..v2.pt.md (pt-BR; see "Prompts" below)
  nuggetizer/
    data.py                   questions, o200k lengths, stratified samples, user prompt
    schema.py                 pydantic models → strict JSON schemas sent to the APIs
    values.py                 pt-BR value extraction (R$, %, dates, years)
    validate.py               mechanical checks (plan v2 §3.3, §3.5.1), flags
    report.py                 report.md: nuggets side by side, validation, self-score, tokens, cost extrapolation
nuggets/<run>/                outputs (see "Outputs")
```

## Install and keys

```bash
python3.12 -m venv .venv                       # already exists in the repo checkout
.venv/bin/pip install -r scripts/nuggets/requirements.txt
```

`nuggets.py` loads `.env` (repo root, gitignored) with `python-dotenv`. It needs `OPENAI_API_KEY`,
`GEMINI_API_KEY` and `DASHSCOPE_API_KEY` (Alibaba Model Studio, **Singapore** region). Setup:
plan v2 §8. The `GEMINI_API_KEY` line was fixed on 2026-10-12 so that `python-dotenv` reads it; no
shell sourcing is needed.

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

- `--sample` names a list in `<out>/sample.json`. `preview_10` = one question per answer-length
  decile (o200k tokens of question + answer, seed 13); `stratified_30` = three per decile, and its
  first pick per decile is `preview_10`. Questions 001 and 003 are the prompt's worked examples and
  are never sampled.
- `--workers` (default 5) is the concurrency **per model**. `create` runs the models in parallel.
- Several `selfscore` processes may run in parallel on the same `--out`. The ledger is shared, and
  the budget cap reads it before every call.

## Prompts

| Prompt | Status | Note |
|---|---|---|
| `create_v1` | superseded | preview v1 |
| `create_v2` | **rejected** | R2 "one nugget per listed object": GPT over-split illustrative lists (execution note §3) |
| `create_v3` | superseded | R2 "follow the answer's structure"; passed both acceptance checks (execution note §8–§9) |
| **`create_v4`** | **current, not run yet** | `create_v3` + pointer rule: a sentence that only delegates to another question gives no nugget (execution note §13) |
| `assign_v1` | superseded | penalized the implicit P&R period (R8) |
| **`assign_v2`** | **current** | implicit period: a missing exercício 2024 / ano-calendário 2023 is not a defect; another year is `contradicts` |

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
creation only), `nuggets/preview_v3/` (`create_v3` + `assign_v2`). A full copy, caches included,
is in `../nuggets_backup_20261012_132700/` (outside the repo). From the pilot on, the caches go to
a private HF dataset repo at the end of each phase (resolution note §3.2).

**Cache semantics.** The cache key is the hash of (provider, model id, params, system prompt, user
prompt, schema). Rerunning a command is free and returns the same responses. A **new run with the
same prompt in a new `--out`** calls the API again, because each `--out` has its own cache. The
v3 cache cannot serve `create_v4` (different prompt text).

## Costs and the budget cap

- Every call is logged at **standard** (synchronous) prices to `<out>/costs.csv`. Batch discounts
  only appear in the report's extrapolation.
- `--budget USD` makes the client refuse any call once the ledger of that `--out` reaches the cap.
  It is checked before every call; concurrent workers can overshoot by at most one call each. The
  cap is **cumulative per `--out`**: for a second step in the same folder, set it to the amount
  already spent plus the new allowance.
- **Always pass `--budget`**, and stop and report if a run hits it or costs more than expected.
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

Flags (filled by the validator, copied to every nugget): `has_pointer`. Plan v2 §3.1 also foresees
`temporal`, `short_answer` and `procedimento_pgd`, which are **not implemented yet**.

## Provider notes (checked 2026-10-12)

- `gpt-6.1-sol`: `reasoning.effort: medium`, strict JSON schema, no `temperature`. It reasons very
  little on this task (≈ 140 tokens per creation call). The 3.1k-token prompt prefix is cached
  automatically, at $0.10/M.
- Gemini (`gemini-3.1-pro-preview`, `gemini-3.8-flash`): `thinkingConfig.thinkingLevel: "medium"`,
  `responseJsonSchema`. No implicit caching was reported for the prefix. Flash prices double on
  2027-01-01.
- `qwen3.8-max-0902` (pinned snapshot): `enable_thinking` with `thinking_budget: 2048`.
  **`response_format: json_schema` returned malformed JSON**, so `json_object` + pydantic + retry is
  used. The context cache hits automatically.

## Before / during the phase 1 pilot: what is still missing

Plan v2 §4 phase 1 needs items that are **not implemented**:

1. **Same-model noise runs** (two more `gpt-6.1-sol` runs on the same prompt). Because of the cache
   semantics above, identical requests in the same `--out` return the cached response. This needs a
   `--replicate N` (or run tag) that enters the cache key, or a separate `--out` per replicate.
2. **Two-call mode** (importance in a second call, plan v2 §3.2).
3. **Known-answer tests** (plan v2 §5.7: corruption builders, metrics), the **two auditors** with the
   repair loop (§3.5.3), **cross-set alignment** (many-to-one, §3.5.2) and the **round trip**
   (§3.5.4).
4. The `temporal`, `short_answer` and `procedimento_pgd` flags; `--dry-run`; a `fake` provider and
   tests (plan v2 phase 0 gate).
5. **Batch API** submit/collect (needed for phase 2, not for the pilot).

Open decisions carried into the pilot: the automatic gate thresholds (plan v2 §3.5.6); whether to
add the optional "expanded" secondary score on `has_pointer` questions (execution note §13.5 item 4);
effort escalation for long answers (plan v2 §9 item 5).
