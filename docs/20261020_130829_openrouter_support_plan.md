# OpenRouter as the single access point for the nuggetization LLMs — plan

**Generated:** 2026-10-20 13:08:29 (local time, from `date +%Y%m%d_%H%M%S`).
**Status:** **implemented and probed on 2026-10-21 (§8)**; `--route openrouter` is the default.
Decisions registered on 2026-10-20: §7 (all models, flex, no parity check now, $150 prepaid).
**Context:** phase 2 of the nuggetization is next (`docs/20261013_103834_nuggetization_open_decisions.md` §4).
The user now has an OpenRouter account and can create an API key. This note looks at the current client and
plans how to send all LLM calls through OpenRouter.

## 1. Current implementation (what must keep working)

| Piece | Where | What it does today |
|---|---|---|
| Provider-neutral client | `scripts/llm_client/client.py` | `LLM.complete_json()` with three providers: `openai` (Responses API, strict JSON schema, `reasoning.effort`), `gemini` (REST `generateContent`, `responseJsonSchema`, `thinkingLevel`), `openai_compat` (Chat Completions on DashScope Singapore for Qwen, `json_object` + pydantic + retry, `enable_thinking` + `thinking_budget: 2048`) |
| Disk cache | same | key = sha256 of (provider, model id, params, system, user, schema[, replicate]); one cache per `--out` |
| Cost ledger + cap | same | `costs.csv`: one row per call, `usd_standard` computed from the `models.yaml` prices; `--budget` checked before each call against `ledger_total()` (batch rows at `BATCH_DISCOUNT` = 0.5) |
| Errors | same | retries on 408/429/5xx; `QuotaExhausted` on a per-day 429 (Gemini 3.1 Pro: 250 requests/day) |
| Batch | `scripts/llm_client/batch.py` | OpenAI Batch (`/v1/responses`) and Gemini `batchGenerateContent`; jobs fill the same cache; Qwen stays synchronous |
| Registry | `scripts/nuggets/models.yaml` | 4 models: `gpt-6.1-sol`, `gemini-3.1-pro`, `gemini-3.8-flash`, `qwen3.8-max` (snapshot `qwen3.8-max-0902`); one `api_key_env` each |
| Caller | `scripts/nuggets/nuggets.py` | `llm(name, out, budget)` builds an `LLM` from the registry; the logical model **name** goes into folder names (`create/<model>/`), set names, the ledger and the manifests |

Three keys are needed today (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`). The `.env` on this
machine only has `GEMINI_API_KEY` (and `HF_TOKEN`), so this machine cannot run the OpenAI or Qwen roles.
With one OpenRouter key, both machines can run every role.

## 2. What OpenRouter offers (checked 2026-10-20)

Sources: the public catalog `GET https://openrouter.ai/api/v1/models` and `/models/<id>/endpoints` (no key
needed), and the docs pages API overview, reasoning tokens, provider routing, FAQ and Batch quickstart.

**All four models are listed, with the same upstream providers and list prices as in `models.yaml`:**

| Our name | OpenRouter id | Upstream endpoints (USD per 1M in / out / cached in) | `:batch` variant |
|---|---|---|---|
| `gpt-6.1-sol` | `openai/gpt-6.1-sol` | `openai` 2.00 / 10.00 / 0.10; **`openai/flex` 1.00 / 5.00 / 0.05**; Azure, Bedrock (+10 %); `fast`/`ultrafast` (×2, ×6) | yes, 1.00 / 5.00 |
| `gemini-3.1-pro` | `google/gemini-3.1-pro-preview` | `google-ai-studio` and `google-vertex/global` 2.00 / 12.00 / 0.20; **`google-ai-studio/flex` 1.00 / 6.00 / 0.10**; `priority` (×1.8) | yes, 1.00 / 6.00 |
| `gemini-3.8-flash` | `google/gemini-3.8-flash` | `google-ai-studio`, `google-vertex/global` 0.75 / 3.75 / 0.075; **`google-ai-studio/flex` 0.375 / 1.875**; `vertex/us` +10 %; `priority` ×1.8 | yes, 0.375 / 1.875 |
| `qwen3.8-max` | `qwen/qwen3.8-max-0902` (the pinned snapshot) | `alibaba`, `alibaba/us-east-1` 2.00 / 6.00 / **0.25** (we assumed 0.20) | **no** |

- **API:** OpenAI-compatible Chat Completions at `https://openrouter.ai/api/v1` (the `openai` SDK we already
  use works with `base_url`). A Responses endpoint exists too (`/v1/responses`, listed by the Batch API).
- **Structured outputs:** `response_format: {type: json_schema, json_schema: {..., strict: true}}`. All four
  models list `structured_outputs`.
- **Reasoning:** one `reasoning` object: `effort` (`minimal`…`xhigh`) **or** `max_tokens`. Gemini 3:
  `effort` maps directly to `thinkingLevel`. Qwen: "some Qwen thinking models" map `max_tokens` to
  `thinking_budget`. **The default effort of `qwen3.8-max-0902` is `xhigh`.** If it is not set explicitly,
  Qwen would reason far longer than in the pilot (D12 says medium).
- **Usage:** every response has `usage` with `cost` (the billed credits), `cost_details`,
  `prompt_tokens_details.cached_tokens`, `completion_tokens_details.reasoning_tokens`. Token counts use the
  model's native tokenizer. `GET /api/v1/generation?id=` returns the stats of a past call.
- **Provider routing:** `provider: {only, order, allow_fallbacks, require_parameters, data_collection, zdr,
  ...}`. By default OpenRouter picks the cheapest provider and **falls back** to another one on errors. For
  reproducibility we must pin it.
- **Fees:** no markup on inference prices. Buying credits costs **5.5 %** (min $0.80) by card, or 5 % in crypto.
- **Rate limits:** calls use OpenRouter's upstream accounts, so **our Gemini 3.1 Pro quota of 250
  requests/day does not apply**. This holds unless we attach our own Gemini key (BYOK), which we should not do.
- **Batch API (beta, launched 2026-09):** `POST /api/v1/batches` with an inline `requests` array (no file
  upload), **one model and one endpoint per batch**, results returned inline in `GET /batches/:id`, about
  50 % off, 24 h window (Vertex up to 96 h, AI Studio expires at 48 h). On Google models every request in a
  batch must use the same `response_format`. Usage is documented at batch level only (per-result usage is not
  documented). Inputs and results are deleted after 30 days.
- **Flex endpoints** (`openai/flex`, `google-ai-studio/flex`): **synchronous calls at half price**, probably
  slower and with more "capacity" errors. They give the batch discount without job handling.
- Also in the catalog: DeepSeek (RAG generator, D1) and several open-weight Qwen models (D2/D4 judge
  candidate). Maritaca Sabiá is **not** listed.

## 3. Cost for phase 1–4 (measured part, pilot note §10.1)

The measured part of the estimate is ≈ $61. That is ≈ $39 for the roles priced with Batch (GPT and Gemini)
plus ≈ $22 for Qwen (synchronous).

| Route | Estimate | Note |
|---|---:|---|
| Direct APIs (current: Batch for GPT/Gemini, Qwen sync) | ≈ $61 | three keys; Gemini Pro needs Batch because of the daily quota |
| OpenRouter, standard synchronous endpoints | ≈ $100 + 5.5 % ≈ **$106** | loses the 50 % discount on ≈ $39 of calls |
| OpenRouter, `flex` or `:batch` for GPT and Gemini | ≈ $61 + 5.5 % ≈ **$65** | +$3–4 credit fee; same prices otherwise |

The open-weight Qwen judge ($10–25, not measured) is outside these numbers. **OpenRouter only pays off if the
GPT and Gemini roles use `flex` or `:batch`.**

## 4. Design

### 4.1 Registry: one logical model, two routes

Keep the logical names (`gpt-6.1-sol`, …). Folder names, set names, manifests and the analysis code use them,
and phase 2 outputs must stay comparable with the pilot. Add an `openrouter` block per model:

```yaml
  gpt-6.1-sol:
    provider: openai                     # direct route, unchanged
    ...
    openrouter:
      model_id: openai/gpt-6.1-sol
      params: {reasoning: {effort: medium}, max_tokens: 32000, response_format: json_schema}
      routing: {only: [openai], allow_fallbacks: false, require_parameters: true, data_collection: deny}
      tier: flex                         # standard | flex | batch (see §4.4)
  qwen3.8-max:
    ...
    openrouter:
      model_id: qwen/qwen3.8-max-0902
      params: {reasoning: {max_tokens: 2048}, max_tokens: 16000, response_format: json_object}  # §5 probe
      routing: {only: [alibaba], allow_fallbacks: false, require_parameters: true}
```

- A global `--route direct|openrouter` in `nuggets.py`, default `direct` until the parity check (§5 step 3)
  passes. The default then moves to `openrouter`. `llm()` merges the route block over the model entry.
- `api_key_env: OPENROUTER_API_KEY` for the whole route (one key in `.env`).
- `require_parameters: true` + `allow_fallbacks: false`: a request is never served by a provider that would
  ignore `reasoning` or the schema, or by another vendor (Azure/Bedrock). That is what makes "same model,
  same settings" true for the paper.
- Prices stay in the registry (for `usd_standard` and the batch estimate); add the OpenRouter-specific
  values (Qwen cached input 0.25) to the route block.

### 4.2 Client: provider `openrouter` in `client.py`

- `openrouter_body()` / `parse_openrouter()` next to the existing builders, so a future batch backend can
  share them (the same pattern as `openai_body` / `parse_openai`).
- Call through the existing `openai` SDK: `OpenAI(base_url="https://openrouter.ai/api/v1")`,
  `chat.completions.create(..., extra_body={"reasoning": ..., "provider": ...})`. Optional attribution
  headers `X-Title` / `HTTP-Referer`. No new dependency.
- **Chat Completions for all four models.** The pilot sent GPT through the Responses API. Through
  OpenRouter, the request shape is different, but the model, effort and schema are the same; the parity check
  (§5) verifies this. Use `/v1/responses` for GPT only if parity fails.
- **Cache key:** `provider` becomes `openrouter`, and the routed `model_id` and params are new. So OpenRouter
  calls never mix with the direct-API cache entries. This is intended, but it means **pilot caches cannot
  serve OpenRouter calls**. Record the route in the key itself, not only in the manifest.
- **Usage → `Usage`:** `prompt_tokens`, `cached_tokens`, `completion_tokens` (reasoning included),
  `reasoning_tokens`. Also keep `usage.cost` (billed) and the served `provider` and `model` from the response.
- **Errors:** 402 (out of credits) → a new fatal `CreditsExhausted`, never retried. 429 → backoff as today. An
  upstream error can arrive as HTTP 200 with an `error` object or `finish_reason: "error"` → treat it as a
  retryable failure, not as a reply. `finish_reason: "length"` (reasoning ate the budget) → truncated, as today.
  `QuotaExhausted` stays for the direct Gemini route.

### 4.3 Ledger and budget

- New columns in `costs.csv`: `route`, `provider_served`, `usd_billed`. `usd_billed` is OpenRouter's
  `usage.cost` (actual charge, flex/batch discounts included). `usd_standard` stays the registry list price,
  so reports can still compare.
- `ledger_total()`: use `usd_billed` when the row has it, else the current rule (`usd_standard`, batch rows
  at half). The 5.5 % credit fee is not per call. Report it once in the cost notes for the paper.
- **Header compatibility:** `_log` appends with `DictWriter` without checking the header. Adding columns to an
  existing `costs.csv` would misalign rows. Phase 2 uses a new `--out`, but the code must still compare the
  header and refuse (or rewrite the file with the new columns) instead of appending blindly.
- `report.py` and `pilot_report.py` sum `usd_standard`; switch them to the billed value, with the same rule.
- **Second safety net:** create the OpenRouter key with a **spending limit** (set in the OpenRouter
  dashboard), slightly above the phase budget. `--budget` stays the primary cap, and the key limit catches a
  runaway loop or a leaked key. Optionally, `GET /api/v1/key` before a run prints the remaining limit.

### 4.4 Discounted tier: `flex` first, OpenRouter Batch second

1. **`flex` (recommended if the probe passes):** synchronous calls with `provider.only:
   ["openai/flex"]` / `["google-ai-studio/flex"]` (to be confirmed: whether `only` accepts the tagged slug).
   No job submission, no `batch wait`, no rerun. The existing threaded runner, retries, cache and budget
   checks work as they are. Concurrency and latency must be measured (§5 step 2). Lower `--workers` if flex
   throws capacity errors.
2. **OpenRouter Batch (fallback):** a third backend in `batch.py`. One job per model **and per schema** (Google
   requires one `response_format` per batch). Requests inline (body size limits to check for ≈ 715 × 6k
   tokens). Results are read from `GET /batches/:id`. Because per-result usage is not documented, cost per row
   may need `/generation?id=` lookups or a split of the batch-level `usage.cost`. More code, and still beta.
3. Qwen has no `:batch` and no `flex` variant: it stays synchronous at list price, as today.

The direct route and its `batch.py` backends stay in the code. They are the fallback if OpenRouter is down or
changes a model, and the pilot was produced with them.

## 5. Steps

| # | Step | Cost | Output |
|---|---|---:|---|
| 0 | User creates the key (spending limit ≈ phase budget + margin), adds `OPENROUTER_API_KEY` to `.env` on both machines, buys credits | fee 5.5 % | — |
| 1 | **Probes** (a throwaway script, not the pipeline): one `create_v4` call per model on a `preview_10` question, standard and flex. Check: strict schema accepted (and Qwen `json_schema` vs `json_object` again); `reasoning` honoured (reasoning tokens close to the pilot's: GPT ≈ 140 per creation call, Gemini/Qwen from `costs.csv`); **Qwen `reasoning.max_tokens: 2048` maps to `thinking_budget`**, else pick the `effort` with the closest token count; served provider and model in the response; `usage.cost` = registry price × tokens; `only` with `/flex` tags | < $0.50 | probe note |
| 2 | Implement §4.1–§4.3 (+ flex). Add the **`fake` provider and unit tests** still missing from the phase 0 gate (README "what is still missing" item 3): mocked OpenRouter replies, including the 200-with-error, 402 and `length` cases | 0 | code, tests |
| 3 | **Deferred (§7, decision 3).** *Parity check:* `create` + `validate` + `selfscore` (Flash) on `preview_10` in a new `--out nuggets/parity_openrouter`, all three families via OpenRouter, `--budget 2`. Compare with `nuggets/pilot/` on the same 10 questions: hard errors, nugget counts, reasoning tokens, self-score, and Flash alignment against the pilot sets (the same-model noise of pilot note §3 is the reference) | ≈ $1–1.5 (flex) | parity note; route default switched if it passes |
| 4 | Gemini 3.1 Pro over a full day of calls is no longer blocked by the 250/day quota: confirm on step 3's calls that no quota error comes back | 0 | — |
| 5 | Phase 2 through OpenRouter, `--budget` on every run, as planned in the open-decisions note §4 | ≈ $65 (§3) | phase 2 |
| 6 | Docs: `scripts/nuggets/README.md` (keys, `--route`, flex), `CLAUDE.md` pointer, open-decisions note, paper methods (route, served providers, fee) | 0 | — |

Stop and report to the user if step 1 shows a mismatch in prices or reasoning tokens, or if flex is not usable.

## 6. Risks and how the plan handles them

| Risk | Handling |
|---|---|
| Silent fallback to another provider (Azure, Bedrock, Vertex vs AI Studio) | `only` + `allow_fallbacks: false`; log `provider_served` per call; a mismatch is an error |
| Parameters silently dropped | `require_parameters: true`; check reasoning tokens in the probe and in the reports |
| Qwen default effort `xhigh` | explicit `reasoning` in the registry; probe step 1 |
| Upstream errors returned as 200 | parsed as failures (§4.2), tested with the fake provider |
| Pilot vs phase 2 run on different routes (paper) | parity check (step 3); every manifest records the route; both stated in the methods |
| Flex: slow or "no capacity" | lower `--workers`; fall back to OpenRouter Batch or to the direct Batch API for that model |
| OpenRouter Batch is beta, docs incomplete (per-result usage) | used only if flex fails |
| Data handling: one more party sees the prompts | the gold answers are public (BR-TaxQA-R); `data_collection: deny` costs nothing, so set it |
| Credit fee 5.5 % | ≈ $3–4 for phases 1–4; reported once |
| Cache backup to HF (open decision §2.2) | unchanged: caches are local per `--out`, whatever the route |

## 7. Decisions (user, 2026-10-20)

| # | Question | Decision |
|---|---|---|
| 1 | Scope | **All four models through OpenRouter.** The direct route stays in the code as a fallback |
| 2 | Discounted tier for GPT and Gemini | **`flex`** (§4.4 option 1), after the step 1 probe. OpenRouter Batch only if flex is not usable |
| 3 | Parity check on `preview_10` before phase 2 | **Not now.** Step 3 is deferred (see below) |
| 4 | Credits and key | **USD 150 already prepaid**, so no new credit purchase or fee for phases 1–4 (§3). The key is still to be created (step 0 below) |
| 5 | Open-weight Qwen judge, RAG generators | **To discuss later.** The user will probably prefer an **HF endpoint**, as for the embeddings, over OpenRouter for the open Qwen judge |

**Consequences for §5:**
- **Step 0:** create the key in the OpenRouter dashboard (Settings → API Keys,
  `https://openrouter.ai/settings/keys`), with a credit limit. Suggested limit: ≈ **$80** (phase 1–4
  estimate ≈ $61 at flex prices, plus probes and margin), below the $150 balance, so a runaway run cannot spend
  all of it. Add it to the **`.env` at the repository root** (gitignored, read by `python-dotenv` in
  `nuggets.py`) on **both machines**, as one line: `OPENROUTER_API_KEY=sk-or-v1-...`. No shell export is needed.
  The other keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`) can stay for the direct route.
- **Step 3 (parity check) deferred.** The step 1 probes still check the settings (schema, reasoning tokens,
  served provider, prices) before phase 2. The pilot-vs-OpenRouter comparison then comes **at no extra cost
  from phase 2 itself**: phase 2 creates nugget sets for all 715 questions, `stratified_30` included, so the
  30 pilot questions can be compared afterwards (nugget counts, reasoning tokens, self-score, Flash alignment
  against the pilot sets). This comparison goes in the phase 2 note.
- **Route default:** without the parity step, `--route openrouter` becomes the default once step 1 (probes)
  and step 2 (code and tests) are done.
- §3's 5.5 % fee row: already paid on the prepaid credits; it is a cost of the work, but not an extra charge
  in phase 2.

## 8. Implementation and probe results (2026-10-21)

### 8.1 What was implemented

| Plan item | Where | Note |
|---|---|---|
| §4.1 registry routes | `scripts/nuggets/models.yaml` (`openrouter:` per model), `client.route_config()` | as planned; `served_provider` added (display name checked on every reply) |
| `--route` | `nuggets.py` (global option, default **`openrouter`**) | manifests record the route and the resolved registry entry; `batch status/collect/wait` always use the direct route; `--batch` with `--route openrouter` is refused |
| §4.2 provider | `client.py`: `openrouter_body()`, `parse_openrouter()`, `_call_openrouter()` | `httpx`, not the `openai` SDK (the raw reply keeps `provider` and `usage.cost`); `routing` enters the cache key **only** on this route, so direct-route keys are unchanged |
| §4.2 errors | `CreditsExhausted` (402, never retried), error in a 200 reply → retried as 502, `RouteMismatch` (logged, not cached, fatal) | |
| §4.3 ledger | `LEDGER_FIELDS` + `route`, `provider_served`, `usd_billed`; `row_billed()` used by `ledger_total()`, `report.py`, `pilot_report.py` | an older `costs.csv` is rewritten with the new (empty) columns on its first new row |
| key check | `nuggets.py openrouter-key` | limit, usage, expiry |
| tests | `scripts/llm_client/tests/test_openrouter.py` (13 tests, mocked HTTP) | the fake provider of the phase 0 gate is still not done |
| §5 step 1 probe | `scripts/nuggets/probe_openrouter.py`, output `nuggets/probe_openrouter/` | |
| docs | `scripts/nuggets/README.md` ("OpenRouter route"), `CLAUDE.md` | |

This machine's `.venv` had no nugget requirements; they were installed with `uv pip install --python
.venv/bin/python -r scripts/nuggets/requirements.txt` (pinned versions).

**Key:** limit $80, **expires 2026-11-20** (renew before phase 2 ends).

### 8.2 Probe: `create_v4`, first 3 questions of `preview_10` (503, 023, 039), 18 calls, **$0.125 billed**

The key's usage on OpenRouter ($0.12503) matched the ledger, after a short lag.

| Variant | Valid replies | Served by | Reasoning tokens (pilot, same questions) | Billed / list |
|---|---|---|---|---|
| `gpt-6.1-sol` (flex) | 3/3, 2 nuggets each (pilot 2) | OpenAI | 91, 0, 0 (0, 0, 0) | 0.50 on calls 2–3; 0.60 on the first, see below |
| `gemini-3.1-pro` (flex) | 3/3, 2 each (pilot 2) | Google AI Studio | 933, 1067, 582 (872, 664, 527) | 0.50 |
| `gemini-3.8-flash` (flex) | 3/3, 2 each | Google AI Studio | 798, 581, 535 (no pilot creation) | 0.50 |
| `qwen3.8-max` (`reasoning.max_tokens: 2048`) | 3/3, 2 each (pilot 2) | Alibaba | 751, 461, 454 (791, 940, 541) | 1.00 (list, cached at $0.25 ✓) |
| `qwen3.8-max`, `effort: medium` | 3/3 | Alibaba | 930, 877, 505 | 1.00 |
| `qwen3.8-max`, strict `json_schema` | 3/3 (one with 3 nuggets) | Alibaba | 489, 889, 608 | 1.00 |

Findings:
- **Pinning works:** `only` with the tagged slugs `openai/flex` and `google-ai-studio/flex` is accepted, with
  `data_collection: deny` and `require_parameters: true`; every reply came from the pinned provider.
- **Flex is half price**, as listed. Latency: GPT ≈ 10 s, Gemini 7–10 s, Qwen 15–30 s, about the pilot's.
  No capacity errors at this size; watch for them at phase 2 concurrency.
- **The first GPT call costs 1.25× input on the cached prefix**: OpenRouter reports `cache_write_tokens: 3525`,
  billed at 1.25 × the flex input price. The next calls read the cached prefix at $0.05/M. It is
  a one-time cost per prefix (≈ $0.001), and it is included in `usd_billed`. `usd_standard` (list price)
  does not model cache writes.
- **Gemini 3.1 Pro had no cached input** (as on the direct route).
- **Reasoning effort matches the pilot's (D12):** the Gemini and GPT tokens are within the pilot's per-call
  spread. Qwen with `reasoning.max_tokens: 2048` stays below 2,048 and in the pilot's range, so the pilot setting
  (`thinking_budget: 2048`) is kept. `effort: medium` gives similar counts. Whether OpenRouter passes
  `max_tokens` as `thinking_budget` cannot be seen in the reply; both settings stay well under the budget.
- **Qwen strict `json_schema` worked 3/3** here (it returned malformed JSON on the direct API in the preview).
  `json_object` + pydantic + retry is kept, so phase 2 runs Qwen as the pilot did.
- No 429 and no quota error on Gemini 3.1 Pro.

**Next:** phase 2 with `--route openrouter` (the default), `--budget` on every run. The pilot comparison on the
30 `stratified_30` questions goes in the phase 2 note (§7, decision 3).
