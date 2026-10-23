# First full RAG evaluation — budget, trimmed plan, staging, and the S2 / S3 hypotheses

**Generated:** 2026-10-23 12:07:34 (local time, from `date +%Y%m%d_%H%M%S`).
**Context:** discussion of 2026-10-23 after the RAG Phase 3 pilot (`docs/20261023_110952_rag_phase3_generation_pilot.md`).
It sizes the first full evaluation against the OpenRouter budget, records the **trimmed plan the user chose**, the
staging, what the scoring (nugget phase 5) covers, and the analysis of the S2 / S3 hypotheses with the ideas kept
for later. Builds on `docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md` (**first-evaluation
note**) and `docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (**plan v2**).
**Status:** decisions and analysis only; no API call (three S1/S2/S3 16k context sets were built locally in the
session scratchpad, outside `runs/`, for §4.1).

## 0. Decisions and open questions (2026-10-23)

| # | Item | Status |
|---|---|---|
| D1 | **Trimmed grid** (§2) for the first full evaluation | **adopted by the user** |
| D2 | Staged execution (§3), each stage sized with `--dry-run`, capped with `--budget`, ledger reviewed; stop and report on any overrun | adopted |
| D3 | The 16k point and the extra Terra run of §4.4 | **not adopted now; kept in mind** (user) |
| Q1 | Do the OpenAI, Gemini and Qwen (DashScope) accounts have their own budget, and how much? Decides whether to move GPT generation and/or the judge off OpenRouter (§1.2) | open (user) |
| Q2 | Raise the OpenRouter key limit (now $100) to use the prepaid credit left | open (user) |
| Q3 | Stage 0 (scoring of the pilot answers, ≈ $4–5) after the user's reading of the pilot answers | next |

## 1. Budget

### 1.1 Where the money stands

The whole experiment has **$150 prepaid on OpenRouter** (user). Used so far: **$67.49** (nuggetization and the RAG
pilot; key status 2026-10-23), so **≈ $82.5 of prepaid credit is left**; the key's $100 limit leaves $32.51 of it
usable until the limit is raised (Q2). Maritaca is billed separately in BRL and is not part of the $150.

The first-evaluation note's full first evaluation (4 generators × 7 headline runs, scoring with all extras) needs
**≈ $90–115** at OpenRouter flex prices (pilot measurements, Phase 3 note §5): it does not fit.

### 1.2 Splitting across keys moves the cost, it does not reduce it

OpenRouter already uses the half-price flex endpoints for GPT and Gemini; OpenAI's own flex tier / Batch API and
Gemini's Batch API are also ≈ half of the list price. So the total is about the same whichever account pays; a split
helps only if the other accounts have their own money (Q1). If they do:

- **GPT generation (≈ $35 of the full plan) → `OPENAI_API_KEY`.** The client already has the `openai` provider
  (Responses API, `reasoning_effort`, strict schema) and batch support (`llm_client/batch.py`); `rag.py generate` needs
  the flex `service_tier` or batch mode wired in. `OPENAI_API_KEY` is not in this machine's `.env`. The route enters
  the cache key and the run configuration, so **each generator keeps one route for the whole paper**: switching
  regenerates the 30 pilot questions of Terra and Luna (< $1).
- **The Flash judge (the largest item, §3.1) → `GEMINI_API_KEY`** (in `.env`; used by the nugget preview and pilot,
  `--route direct`), synchronous or Batch API: OpenRouter would then be almost untouched.
- **Qwen (DashScope)** is not needed for generation or scoring (the Qwen nugget set already exists); its best use is
  the second judge of the judge-agreement check on real answers (§3.1 item 4).

## 2. The trimmed grid (D1)

| Cut | Saves |
|---|---:|
| Terra only on S1 4k, S2 4k, closed book, oracle 4k; Luna, Sabiá-4, Sabiazinho-4 on all 7 headline runs (S1, S2, S3, S2c, S4 at 4k, closed book, oracle 4k) | ≈ $16 |
| Cross-set scoring (Gemini and Qwen nugget sets) only for S1 vs S2 at 4k, on 2 generators | ≈ $8–12 |
| Context-support calls on S1 4k, S2 4k, oracle 4k only | ≈ $6 |
| Wrong-context and `context_v1` controls kept at pilot size (`stratified_30`) | — |

**Total ≈ $58–75** (OpenRouter prices), within the ≈ $82.5 left even if everything stays on OpenRouter; with GPT on
OpenAI and the judge on Gemini (Q1), OpenRouter keeps a reserve. S3, S2c and S4 are **not** dropped: only Terra, the
expensive generator (≈ $5.2 per 4k run + scoring), is limited to S1 / S2, the main hypothesis, as the strong-model
check. Maritaca across all stages: ≈ R$ 170 at list price (its flex −50 % and night 22–06 BRT −30 % discounts: to be
confirmed with one call whether flex can be requested through the API).

## 3. Staging (D2)

| Stage | Content | Estimate |
|---|---|---:|
| 0 | Nugget phase 5 `score` on the pilot answers: measures the real cost per scored answer (scoring is the largest and least certain item) | ≈ $4–5 |
| 1 | Core result: S1 vs S2 at 4k + closed book + oracle 4k, all 715 questions, 4 generators, generated and scored | ≈ $30–35 |
| 2 | S3, S2c, S4 at 4k (Luna, Sabiá-4, Sabiazinho-4) | ≈ $15–20 |
| 3 | Budget sweep: S1 / S2 at 2k and 8k, Luna and Sabiazinho-4 only, or on `stratified_70` (see §4.4 for the alternative 16k point) | ≈ $5–8 |
| 4 | Cross-set scoring, robustness; DeepSeek V4 later from the other machine (cheap) | ≈ $10–15 |

Before each stage: `--dry-run`, then `--budget` set to the stage's estimate, then the ledger (`runs/costs.csv`, and
the nugget ledgers) reviewed; any overrun stops the work and is reported (CLAUDE.md rule).

### 3.1 What the scoring covers (nugget phase 5)

**Paid (LLM calls):**

1. **Answer assignment — the main cost.** Gemini 3.8 Flash (`assign_v2`, medium reasoning) reads the question, all
   gold nuggets of the question and one system answer, and labels each nugget `support` / `partial_support` /
   `not_support` / `contradicts` with a short justification (plan v2 §5.2). One call per answer and nugget set, i.e.
   715 per run → V_strict (headline), V, A_strict, A, W, contradiction rate (§5.3). ≈ **$1.0–1.5 per run and nugget
   set**, dominated by the judge's reasoning tokens; the judge does not read the context, so the cost does not grow
   with the context budget.
2. **Cross-set scoring (robustness):** the same assignment against the second (Gemini 3.1 Pro) and third (Qwen3.8-Max)
   nugget sets, so no conclusion depends on the nugget creator. Each extra set costs as much as item 1.
3. **Context support** (first-evaluation note §4.3; new prompt `assign_ctx_v1`): the judge assigns the gold nuggets
   against the **context** instead of an answer. Gives which nuggets each context holds → answer recall relative to
   what the context allowed (utilisation), a per-nugget leakage measure (nuggets supported by the answer but not by
   its context), and the size × strategy test of §4.3. One call per question and context set, shared by all
   generators: ≈ **$2 per context set** (it reads the 4k context).
4. **Judge agreement on real answers** (the deferred part of nugget phase 4): a second judge on a sample of answers;
   small; candidate for the Qwen key.

**Free (scripts):** value checks (plan v2 §5.4: value hit, value conflict, temporal substitution; with the fix for
spelled-out numbers and "1°" of the Phase 3 note §6.3), the legal-provision score of the answers' citations (§5.5;
`cited_chunk_ids` + `scripts/dataset/citations.py` on the claim texts), the retrieval ↔ answer linkage
(first-evaluation note §3.1), paired and chapter-cluster bootstraps, the robustness analyses (§5.6), the known-answer
tests (§5.7).

**In the trimmed plan:** primary set on 25 runs ≈ $25–38; cross-sets on 8 runs ≈ $8–12; context support on 3 sets
≈ $6; stage 0 ≈ $4–5 — **≈ $43–61 of the ≈ $58–75 total**: scoring, not generation, is the largest part.

### 3.2 Why Gemini 3.8 Flash is the judge (reminder)

Plan v2 D2 (2026-10-11), confirmed in nugget phase 4 (`docs/20261021_155704_nuggetization_phases_2_to_4_execution.md`
§2.5; `docs/20261013_103834_nuggetization_open_decisions.md` §3):

1. **Another family than the nugget creator.** The primary nugget set is GPT (`gpt-6.1-sol`); a GPT judge could
   favour answers phrased like its own nuggets (plan v2 §6.2). Candidates were therefore Gemini and an open-weight
   Qwen; Qwen3.8-Max was excluded (it created the third nugget set and is not cheaper than Gemini, plan v2 D11, §6.4).
2. **Cost.** Flash was the Gemini candidate; Gemini 3.1 Pro would replace it only with a balanced accuracy > 0.05
   higher on the known-answer tests.
3. **Selected by the known-answer tests** (3,354 tests: corrupted gold answers, wrong-question and empty answers):
   Flash and 3.1 Pro both reached **99.0 % balanced accuracy**, and Flash caught **96 % of flipped verdicts**
   ("Sim" ↔ "Não") against **67 %** for Pro (6 of 9 missed: Pro reconciled a flipped "Não" with the affirmative
   body); Flash detection: value ± step 97 %, corpus value of another year 100 %, year 99 %.

The open-weight Qwen judge (plan v2 D4) was left out at the user's request.

### 3.3 What the scoring contributes to the segmentation analysis

The scoring is **not mainly a robustness measure of the nuggetization**: it is **how answer quality is measured**,
the dependent variable of the answer-level experiment. Without it the paper has only the retrieval test, which shows
that S2 *retrieves* the gold provisions better than S1, not that it *answers* better.

| Part | Contribution to the segmentation analysis | Role | Trimmed-plan cost |
|---|---|---|---:|
| Answer assignment, primary nugget set | The headline outcome: V_strict per strategy × generator → the paired S2 − S1 (and S3 − S2, S2c − S2, S4 − S3) answer-quality differences, each strategy against the closed-book and oracle bounds, and the contradiction rate, which tests the hypothesis that S2 inciso chunks, isolating one period's value, give fewer wrong-year answers than S1 article chunks mixing several years' tables (plan v2 §5.4, temporal substitution) | **core**: the dependent variable | ≈ $25–38 |
| Context support (`assign_ctx_v1`) | Which nuggets each context holds → splits an answer difference into "the context held more" (retrieval) and "the generator used what it had better" (chunk form); tests the S3 "explains better" hypothesis and the size × strategy hypothesis (§4.2–§4.3); a per-nugget leakage measure | **core**, segmentation-specific | ≈ $6 |
| Cross-set scoring (Gemini, Qwen nugget sets) | S2 > S1 does not depend on which model wrote the nuggets | robustness of the segmentation conclusion against nugget-creator bias | ≈ $8–12 |
| Judge agreement on real answers | The conclusion does not depend on the judge | robustness | small |
| Free: value checks, legal-provision score of the answers' citations, retrieval ↔ answer linkage | Segmentation-specific detail (citation accuracy comparable to the retrieval metrics; answer score by context state) | core | $0 |

So ≈ $31–44 of the scoring budget is the core measurement and only ≈ $8–12 is robustness, already trimmed to the one
comparison that matters most (S1 vs S2 at 4k, 2 generators).

**No free substitute for the main assignment:** the value checks cover only nuggets carrying a value (R$, %,
dates); rules, conditions and verdicts — most of the P&R — need a judge. **If the budget gets tight, cut in this
order:** cross-set scoring (fewer runs, or `stratified_70` instead of all questions), then Terra's runs; the primary
assignment and the context-support calls last.

## 4. Why S1 / S2 at 4k, and the S2 / S3 hypotheses

### 4.1 What the retrieval test says (main corpus, budget view, all gold, `either_containment_merge_skip`)

Article recall:

| Budget | S1 | S2 | S3 | S2c | S4 |
|---|---:|---:|---:|---:|---:|
| 2k | 0.296 | 0.425 | 0.424 | 0.391 | 0.397 |
| 4k | 0.398 | 0.503 | 0.507 | 0.480 | 0.487 |
| 8k | 0.492 | 0.600 | 0.606 | 0.579 | 0.593 |
| 16k | 0.574 | 0.674 | **0.693** | 0.652 | 0.669 |

Paired differences (`comparisons.csv`):

| Pair | Article recall | Provision recall |
|---|---|---|
| S1 → S2 | +0.10 to +0.14 at every budget (16k +0.099), p < 0.001 | +0.04 to +0.06, p < 0.001 |
| S2 → S3 | ≈ 0, n.s., up to 8k; **+0.020 at 16k** (CI 0.010–0.030, p < 0.001) | +0.005 to +0.012 up to 8k (p 0.02–0.09); **+0.034 at 16k**, p < 0.001 |
| S2 → S2c, S3 → S4 | −0.013 to −0.034, mostly significant | ≈ 0, n.s. |

- **S1 vs S2 does not depend on the budget** (the earlier assumption that strategies converge at large budgets is
  wrong for retrieval): 4k is not special, but the middle of the range, cheap, and matched by the oracle 4k bound.
- **S3 differs from S2 only at 16k**, as expected from how it works: it adds grouping chunks (whole sections,
  chapters; Tipos CAP, LIV, PRT, SBT, SEC, SSC, TIT), which are large and fit mostly in large budgets.
- **S2c / S4 retrieve slightly worse at article level**, but the caput sentence is meant for the generator (readable
  paragraph chunks), so only answer scores can judge them; they stay in the grid.

What S3's contexts hold (computed in the session; S2 / S3 16k sets built in the scratchpad):

| | S3 4k | S3 16k |
|---|---:|---:|
| Share of context tokens from grouping chunks | 18.7 % | 26.1 % |
| Questions with ≥ 1 grouping chunk | 415 / 715 (pilot 21 / 30) | 642 / 715 (pilot 28 / 30) |
| Contexts identical to S2's | 299 / 715 (pilot 9 / 30) | 73 / 715 (pilot 2 / 30) |

### 4.2 The hypotheses (user)

- **S2 better than S1 through accuracy:** smaller units rank the specific provision better and more distinct
  provisions fit in the budget. Retrieval already supports it (+0.10 article recall); whether it becomes better
  answers is the main phase 5 result.
- **S3 better than S1 (or S2) through context that explains the subject:** a grouping chunk brings neighbouring
  articles (definitions, conditions, exceptions). **The 4k comparison is the cleanest test of this mechanism:** S2 and
  S3 hold the gold equally often at 4k, but S3 spends ≈ 19 % of the budget on whole sections instead of isolated
  provisions, so an S3 − S2 answer difference at 4k comes from the **form** of the context, not from retrieval. The
  phase 5 decomposition (answer difference on questions with the same vs a different retrieval outcome, first-
  evaluation note §3.1) separates the two; at 16k both effects mix (S3 also retrieves more).
- **Smaller generators may handle S3 worse** (more irrelevant text next to the relevant one): plausible
  (long-context distraction; `docs/20260929_111356_fiscalqa_pro_temporal_misgrounding_comparison.md` reports that
  whole-article prompting made long articles worse). Two caveats: S1 is noisy too (a whole article where one inciso
  matters); the cleanest context is S2's. And **the retrieval test cannot measure this noise:** its context precision
  counts every token of a chunk that contains any gold (`evaluation.py`, `gold_toks / total`), so a chapter holding one
  gold article counts as fully relevant — which is why it rates S3 the "most precise" (article level, 4k: S1 0.129, S2
  0.145, S3 0.169; 16k: 0.058, 0.069, 0.124).

### 4.3 How phase 5 tests the size hypothesis

With the context-support call (§3.1 item 3): for each generator, the share of the **context-supported** nuggets
that the answer recovers (utilisation). The hypothesis predicts that utilisation drops from S2 to S3 more for the
small model of each pair than for the large one: the **interaction** (S3 − S2)_small − (S3 − S2)_large, within
vendor (Sabiá-4 / Sabiazinho-4, Terra / Luna) — the reason the generators come in same-release size pairs. An
interaction needs far more data than a main effect; with 715 paired questions it may stay inconclusive, and should
then be reported with its confidence interval, not as "no effect".

### 4.4 Ideas kept for later (D3)

- **A 16k point instead of the 2k / 8k sweep in stage 3:** S2 and S3 at 16k for Sabiá-4 and Sabiazinho-4 (the
  within-family size contrast, off OpenRouter: ≈ R$ 125 for 2 runs each) and Luna (≈ $2.6); S1 16k optional (≈ $1.3
  Luna, ≈ R$ 12 Sabiazinho, ≈ R$ 50 Sabiá-4) for S1 → S2 at 16k; scoring ≈ $1–1.5 per run. The 16k S1 / S2 / S3
  contexts are built locally in about a minute (`rag.py context --sets S1@budget=16000,…`). The 2k / 8k sweep adds
  little now that S1 vs S2 is flat across 2k–8k.
- **Terra on S3 4k** (≈ $5.4 + scoring), so the OpenAI pair also has an S2 vs S3 contrast.
- **Terra at 16k** (≈ $14.5 per run), only if the cheaper generators show an S3 effect there.

## 5. What the pilot says about these hypotheses (very little)

Not scored yet; only the proxies, at 4k:

| | Sabiá-4 | Sabiazinho-4 | Terra | Luna |
|---|---|---|---|---|
| Claims grounded (S1 / S2 / S3) | 0.92 / 0.95 / 0.98 | 0.90 / 0.93 / 0.97 | 0.99 / 0.99 / 1.00 | 1.00 / 0.98 / 0.99 |
| Abstention (S1 / S2 / S3) | 0.03 / 0.03 / 0.03 | 0 / 0 / 0 | 0 / 0 / 0 | 0.10 / 0.17 / 0.17 |

No sign that the small models struggle with S3 at 4k: Sabiazinho-4's grounded share is in fact highest on S3. But a
valid quote shows that the model read the context, not that the answer is right or complete; 30 questions, 9 of them
with identical S2 / S3 contexts, cannot show a small difference; and stage 0 will give the first answer-level numbers,
not an answer to the size question, which needs the 715 questions.

## 6. Next

1. **User:** read the pilot answers (Phase 3 gate; suggested Q350, Q440, Q503, Q676, Q705); answer Q1, Q2.
2. Stage 0: implement nugget phase 5 `score` (with the context-support call, the value-check fix and the linkage) and
   run it on the pilot answers; replace the scoring estimates of §3.1 with the measured cost.
3. Stages 1–4 of §3, each sized and capped; revisit D3 after stage 2.
