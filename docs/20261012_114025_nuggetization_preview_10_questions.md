# Nuggetization preview — 10 questions, three creators, four judges

**Generated:** 2026-10-12 11:40:25 (local time, from `date +%Y%m%d_%H%M%S`)
**Plan:** `docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (plan v2). This is a smoke test
before phase 1, run to check the process end to end and to replace the assumptions of plan v2 §6.4
with measured token counts. It is **not** the phase 1 pilot: no prompt iteration, no 2-call mode, no
same-model noise runs, no auditors and no known-answer tests.
**Full results:** `nuggets/preview/report.md` (generated). It shows all nuggets side by side per
question, with validator issues and judge labels.
**Total spent:** **$1.01** in 90 API calls (ledger `nuggets/preview/costs.csv`), plus a few
probe calls of a fraction of a cent.

---

## 1. Is 10 questions enough?

**For this purpose, yes. For the phase 1 decisions, no.**

- **Process check:** 10 is enough. All three providers, structured output, validation, caching, the
  ledger and the report ran end to end. All 90 calls were accepted on the first attempt.
- **Cost estimate:** 10 is enough *if the questions are stratified by length*, because length
  drives cost. `preview_10` takes one question per answer-length decile, so the sample mean is close
  to the population mean. Tokens are fitted against length and summed over the 715 real lengths. The
  bootstrap 90 % intervals on the full-run costs are about ±10–25 % (report §5). Two things matter
  more than sample size:
  - the roles not run here (auditors, aligner, round trip) are priced from the judge-call shape;
  - the tail of long answers lies outside the sample. The longest preview answer has 1,372 tokens;
    14 answers are longer (up to 6,306) and hold 18 % of all question + answer tokens. The linear
    fit extrapolates into them.
- **Quality decisions** (prompt, 1 vs 2 calls, judge choice): 10 is too few. That is the job of the
  30-question pilot.

**Reuse:** `preview_10` is the first pick per decile of `stratified_30` (3 per decile, seed 13,
prompt-example questions 001 and 003 excluded). The pilot will therefore reuse these 10 questions,
and their cached responses.

Sample: Q503, 023, 039, 710, 259, 498, 564, 244, 703, 624. It has two Sim/Não verdicts, four
enumerations and two answers with percentages, but **no R$ amount**. The R$ cases of R8/R9 are
untested until the pilot.

## 2. What was built (phase 0, minimal)

| Path | Content |
|---|---|
| `scripts/llm_client/` | `LLM.complete_json()` for `openai` (Responses API, strict JSON schema), `gemini` (REST `generateContent`, `responseJsonSchema`) and `openai_compat` (Qwen on Model Studio). Raw-response cache keyed by the request hash, retry on invalid or truncated replies, cost ledger |
| `scripts/nuggets/models.yaml` | Registry with the medium-effort settings (D12) and the plan v2 prices |
| `scripts/nuggets/prompts/create_v1.pt.md` | Creation prompt: rules R1–R10, recurring cases, fields, two worked examples (Q003, abridged Q001); ≈ 3.1k tokens |
| `scripts/nuggets/prompts/assign_v1.pt.md` | Assignment prompt with the four labels (§5.2) |
| `scripts/nuggets/nuggetizer/` | `schema` (pydantic → strict schema), `data` (sampling), `values` (pt-BR values), `validate` (§3.3, §3.5.1), `report` |
| `scripts/nuggets/nuggets.py` | `sample`, `create`, `validate`, `selfscore`, `report` |
| `nuggets/preview/` | Inputs, sample, cache, nuggets, validation, assignments, ledger, report |

`openai` (3.29.0) and `pydantic` (2.14.1) were installed in `.venv`.

**Not built:** Batch submit/collect, `--dry-run`, the `fake` provider and tests, `review`/`assign`
on system answers, alignment, auditors, round trip, known-answer builders.

## 3. API findings (phase 0 checks of plan v2 §9 item 4)

| Provider | Finding |
|---|---|
| OpenAI `gpt-6.1-sol` | `reasoning.effort: medium` + strict JSON schema work. Medium effort used **little reasoning**: 147 tokens per creation call on average (plan assumed 1.5k), 21 per judge call |
| Gemini | `thinkingConfig.thinkingLevel: "medium"` is accepted by `gemini-3.1-pro-preview` and `gemini-3.8-flash`, so D12 maps directly. Thinking: 1,151 tokens per Pro creation call, 469 per Flash judge call. **No implicit caching** was reported for the 3.1k-token prefix (cached = 0), so Gemini estimates assume none |
| Alibaba `qwen3.8-max` | The API lists the snapshot `qwen3.8-max-0902`, which is pinned in `models.yaml`. `enable_thinking` + `thinking_budget: 2048` work. **`response_format: json_schema` returned malformed JSON** in the probe; `json_object` + pydantic validation works (0 retries in 20 calls). Context cache hit automatically (2.8k of 3.7k input tokens) |
| `.env` | `GEMINI_API_KEY` is **read differently by `python-dotenv` and by the shell**. The dotenv value is rejected ("API key not valid"); the shell-sourced value works. The commands therefore run after `set -a; . ./.env; set +a`. The line probably has quoting or a trailing character that the two parsers treat differently. Worth fixing in `.env` before anything relies on `load_dotenv` alone |

## 4. Nugget results

| Creator | Nuggets | Per question (min–max) | Vital | Validator errors | Warnings | Char coverage |
|---|---:|---|---:|---:|---:|---:|
| `gpt-6.1-sol` | 72 | 7.2 (2–29) | 58 % | 0 | 3 | 90 % |
| `gemini-3.1-pro` | 50 | 5.0 (2–21) | 64 % | 0 | 8 | 89 % |
| `qwen3.8-max` | 52 | 5.2 (2–21) | 63 % | 0 | 4 | 93 % |

- **Granularity differs by family.** GPT splits more (Q703: 13 vs 6 and 6; Q244: 9 vs 5 and 5;
  Q624: 29 vs 21 and 21). Each GPT nugget is one tax treatment per instrument, which follows R2.
  Gemini and Qwen group instruments that share a rate. The two are about equally good for scoring,
  but the difference will lower the cross-family alignment rates (§3.5.2). The alignment must be
  many-to-one, not one-to-one.
- **Gemini omissions.** Gemini left one statement uncovered in Q498 (the reasoning about the
  estate) and one in Q624 (missing CPF/CNPJ fields create pending items but do not block filing).
  Both are `okay`-level facts, and GPT and Qwen covered them.
- **R8 warnings.** Gemini (3) and Qwen (2) wrote percentage nuggets in Q703/Q624 without a period.
  GPT anchored every value.
- The validator's first version over-reported uncovered enumeration items: lead-in lines such as
  "…às seguintes alíquotas:" and roman-numeral sub-items. This is fixed, and no hard errors remain.

## 5. Main finding: R8 makes the judges penalize the gold answer itself

In the gold self-score (§3.5.5), every judge should label every nugget `support`. On the GPT set:

| Judge | support | partial_support |
|---|---:|---:|
| `gemini-3.8-flash` | 94.4 % | 4 |
| `gemini-3.1-pro` | 94.4 % | 4 |
| `qwen3.8-max` | 90.3 % | 7 |
| `gpt-6.1-sol` | 86.1 % | 10 |

**All but one** of the non-`support` labels have the same cause. GPT followed R8's fallback and
wrote "no ano-calendário de 2023" / "exercício de 2024" into deadline and rate nuggets (Q023,
Q039, Q564, Q703) whose question and answer state no year. The judges then mark `partial_support`
with "não menciona o ano-calendário de 2023". The Gemini and Qwen sets added fewer years and scored
98–100 % with Flash.

This would lower V_strict for **every** system answer that does not state the year, and the
§3.5.6 gate (≥ 98 % self-support) would fail on it. It is a prompt/judge interaction, not a nugget
error. Options for the pilot, to be chosen by the user:

1. **Judge side (recommended):** state in `assign_v1` that the P&R period (exercício 2024,
   ano-calendário 2023) is implicit context. A missing year is then not a defect, while a
   *different* year or value stays `contradicts`. The temporal-substitution test (§5.4) is kept,
   and the nuggets need no change.
2. **Creation side:** limit R8's document-period fallback to `valor_prazo` nuggets with amounts
   or rates, and mark the added period as `[período do documento]` so the judge can ignore it.
3. Both.

Other judge observations:
- Flash was the most lenient judge, GPT the strictest; Qwen3.8-Max was in between and also flagged
  Q703.
- The only non-R8 label was Flash on Qwen's Q710 nugget, which only says "the treatment of pergunta
  674 applies". That is a pointer the prompt says should give no nugget, so Flash was right to flag it.
- These differences are the reason the known-answer tests (§5.7) choose the judge.

## 6. Updated cost estimate

Measured tokens per call, extrapolated to 715 questions (method in report §5), with the plan v2
call counts:

| | Preview-based | Plan v2 §6.4 |
|---|---:|---:|
| Creation, `gpt-6.1-sol`, Batch | $4.6 (90 % CI $4.2–5.6) | ≈ $9 |
| Creation, `gemini-3.1-pro`, Batch | $10.6 ($9.9–11.0) | ≈ $12 |
| Creation, `qwen3.8-max` | $8.9 ($7.9–10.1) | ≈ $11–14 |
| OpenAI subtotal, phases 1–4 | $10.7 | ≈ $17–20 |
| Gemini subtotal, phases 1–4 | $35.7 | ≈ $50–55 |
| Alibaba subtotal, phases 1–4 | $27.4 | ≈ $35–40 |
| HF endpoint (not measured) | $10–25 | ≈ $10–25 |
| **Total, phases 1–4** | **≈ $85–100** | **≈ $115–140** |
| Scoring per run and nugget set: Flash, Batch | $1.3 | ≈ $3.5 |
| Scoring per run and nugget set: 3.1 Pro, Batch | $5.7 | ≈ $10 |
| Scoring per run and nugget set: Qwen3.8-Max | $6.4 | ≈ $11 |
| Scoring per run and nugget set: `gpt-6.1-sol`, Batch | $2.0 | ≈ $9 |
| Grid of 40 runs × 3 sets, Flash / 3.1 Pro | ≈ $160 / ≈ $690 | ≈ $420 / ≈ $1,200 |

Reasons and caveats:
- **OpenAI is about half the plan** because medium effort reasons very little on this task (147
  tokens, not 1.5k). Its prefix was cached at $0.10/M even in synchronous calls. If the pilot raises
  effort for quality reasons (plan v2 §9 item 5), the OpenAI lines move back toward the plan.
- **Judge calls are smaller than assumed:** ≈ 1.1–1.2k input, not 3.5k, because the assignment
  prompt is short. Output is 0.3–1.2k, not 2.1k. Real scoring judges **system** answers, not gold
  ones. If the generators write longer answers than the P&R (median 84 words), input grows; output
  grows mostly with the number of nuggets. A safety factor of 1.5× on the scoring rows is
  reasonable until the RAG Phase 3 pilot gives real answer lengths.
- Auditor, aligner and round-trip roles are **priced from the judge-call shape** (×1.3 for the
  auditors' longer instructions). They are the least certain lines, about 40 % of the total.
- The phase 5 scoring budget is now dominated by the choice between Flash and 3.1 Pro as primary
  judge, by a factor of ≈ 4.

## 7. How to rerun or extend

```bash
set -a; . ./.env; set +a
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
$P $N sample                       # writes nuggets/preview/sample.json (preview_10, stratified_30)
$P $N create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
$P $N validate
$P $N selfscore --judge gemini-3.8-flash --sets gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
$P $N report                       # nuggets/preview/report.md
```

Reruns read the cache and cost nothing. `--sample stratified_30 --out nuggets/pilot` runs the same
steps on the pilot sample, reusing nothing from the preview cache unless `--out` points to the same
folder. Copy `nuggets/preview/cache/` to keep the 10 calls.

## 8. Decisions for the user before phase 1

1. R8 vs the judge (§5): option 1, 2 or both.
2. Whether GPT's finer granularity is wanted (R2 as written), or R2 should allow grouping
   instruments that share a rule and value.
3. Whether to commit `nuggets/preview/` (3.2 MB, raw responses included) or keep only the report
   and manifests, as for `runs/`.
4. Fixing the `GEMINI_API_KEY` line in `.env` so that `python-dotenv` reads it (§3).
