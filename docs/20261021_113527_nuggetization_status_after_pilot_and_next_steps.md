# Nuggetization — status after the phase 1 pilot and next steps

**Generated:** 2026-10-21 11:35:27 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** a record of where the nuggetization stands before phase 2, and what is left to finish it.
**Sources:** plan v2 (`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`), the pilot note
(`docs/20261012_192640_nuggetization_phase1_pilot.md`), the open-decisions note
(`docs/20261013_103834_nuggetization_open_decisions.md`), the OpenRouter plan
(`docs/20261020_130829_openrouter_support_plan.md`) and `scripts/nuggets/README.md`.

## 1. Done

**Preview (10 questions, $2.63 billed).**
- Creation prompt settled: `create_v2` rejected (GPT over-split illustrative lists), `create_v3` → `create_v4`
  (pointer rule: a sentence that only says "see question N" gives no nugget).
- Scoring prompt settled: `assign_v2` (a missing exercício 2024 / ano-calendário 2023 is not a defect).

**Phase 1 pilot (`stratified_30`, $8.29 billed, `nuggets/pilot/`).** Every phase 1 item of plan v2 §4 was run:
- creation by three families (`gpt-6.1-sol`, `gemini-3.1-pro`, `qwen3.8-max`), two GPT replicates
  (same-model noise), and the 2-call mode (importance in a second call);
- cross-family alignment, round trip, two auditors (3.1 Pro, Qwen) with repair, a planted-error test of the
  auditors, gold self-score;
- known-answer tests of the judge (Flash and 3.1 Pro).

**Decisions closed** (open-decisions note §1):
- `create_v4`, **one call** (nuggets and `vital`/`okay` labels in the same response);
- gate thresholds: 0 hard errors; gold self-score ≥ 98 %; ≤ 2 % of nuggets flagged by both auditors (on
  any check) after repair; judge sensitivity ≥ 0.90 on value/year/verdict corruptions; each auditor catches
  ≥ 80 % of planted errors. The pilot passed all of them;
- `answer_cleaned` content loss fixed in the v2.0 build (47 answers);
- judge: Gemini Flash, not 3.1 Pro;
- all LLM calls through **OpenRouter** (flex endpoints for GPT/Gemini, no 250/day quota on 3.1 Pro).
  Implemented and probed on 2026-10-21 ($0.125); default route.

## 2. Next steps

1. **Phase 2 — full creation:** the three families on the 715 questions, `--route openrouter`, then
   `validate`. Gate: 0 hard validation errors. The 30 pilot questions inside the full run give the
   pilot-vs-OpenRouter comparison for free. Gaps:
   - `sample` only builds `preview_10` and `stratified_30`; a full-set sample is needed;
   - questions 001 and 003 are the prompt's worked examples: nuggetize them and flag them, or exclude them.
2. **Phase 3 — automatic robustness:** alignment, two auditors + repair, round trip, gold self-score (Flash on
   the three sets, 3.1 Pro on the primary). The freeze gate gives `v0-auto`.
3. **Phase 4 — judge selection:** known-answer tests on the full set, after the builder fixes (W without
   near-duplicate sources; D/C dropping tests whose fact is restated; V with a real other-period value).
   Optional: the open-weight Qwen judge on an HF endpoint (≈ $10–25).
4. **Phase 5 — scoring** of the RAG answer grid with both nugget sets, and robustness of the conclusions
   (needs RAG generation runs; Flash ≈ $1.2–1.3 per answer run and nugget set). Open: the "expanded" score
   on `has_pointer` questions.
5. **Phase 6 — release:** HF `nuggets` config, reports, raw responses. The cache push to the private HF repo
   needs the user's go-ahead.

## 3. Budget

Pilot-based estimate for phases 1–4: ≈ $71–86 (≈ $56–102 with margin), of which $10–25 is the optional HF
endpoint. The OpenRouter part is close to the key's **$80 limit**; the key **expires 2026-11-20**. Pass
`--budget` on every step and check the key's usage between steps.
