# Gold-Answer Nuggetization and Nugget-Based Answer Evaluation — Plan v2

**Generated:** 2026-10-11 22:40:49 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** plan only. Nothing in `scripts/nuggets/` has been implemented or run.
**Revised 2026-10-11 (later):** the human audit cannot be run in the near term. It is **postponed**,
not dropped. §3.5 (nugget robustness without people), §5.6 (robustness of the conclusions) and §5.7
(known-answer tests, which also replace the human judge calibration) take its place, and the release
is labelled as automatic (D5, D10, W10).
**Revised 2026-10-11 (latest):** a third nugget set by **Qwen3.8-Max** replaces the repeated GPT
creation runs; stability is measured as **agreement across model families**. The cost estimate now
covers **every provider**, not only OpenAI, and the OpenAI part uses the lean option (D8, D11, W11,
§3.5.2, §6.4). **Medium reasoning effort** is fixed for every LLM call (D12), and the Gemini judge
candidate is **Gemini 3.8 Flash**, with 3.1 Pro only on a check subset (D2, §5.7). Qwen3.8-Max does
not replace Gemini: without a batch discount in the Singapore region it is not cheaper (§6.4).
**Supersedes:** `docs/20260926_112714_gold_answer_nuggetization_plan.md` (**v1**). v1 is still the
reference for the literature review (v1 §1), the audit check tables (v1 §3.4.1) and the rationale
for the audit (v1 §3.4.4). Where this note and v1 differ, this note wins.
**Goal (unchanged):** turn the 715 gold answers of BR-TaxQA-R into **legal nuggets** (short,
self-contained, atomic statements) and score the answers of the RAG generator LLMs against them, so
the segmentation strategies can be compared on answer quality, not only on retrieval.

---

## 0. What changed since v1 (2026-09-26 → 2026-10-11)

| # | Work done after v1 | Effect on this plan |
|---|---|---|
| W1 | **Dataset v2.0 built** (`dataset/`, `scripts/dataset/build_v2_dataset.py`; `docs/20260927_180401_*`). `questions.jsonl` already has `answer_cleaned` as one string (lines joined with `\n`) | `prepare` reads `dataset/questions.jsonl` instead of downloading v1.0 from the HF Hub (§2). Nuggets become a 4th HF config, `nuggets`, as already foreseen in the dataset note |
| W2 | **Gold answers checked unchanged** after every rebuild: 715 questions, 698,724 characters of `answer_cleaned`, median 84 words, p90 316, max 3,316, 20 answers under 80 characters (re-measured 2026-10-11) | Nuggets do **not** depend on the corpus. The corpus rebuilds of 2026-10-08/09 do not invalidate them, and future corpus fixes will not either. Only the legal-provision score (§5.5) depends on the corpus and on `references.jsonl` |
| W3 | **References resolved at provision level** (`docs/20260927_213420_*`, rebuild of 2026-10-09): 1,916 references, 0 `not_in_corpus` (v1 counted 42), nested `fragment_id`s (`art12_par1_inc2`), `matchable` flags, 13 unmatchable fragments (treaty articles) | §5.5 matches system citations against `fragment_id`s directly. `scripts/dataset/citations.py` parses both citation orders; `lexml-linker` does not parse the act-first order ("Lei nº 11.482, de 2007, art. 1º"), so `citations.py` is the extractor of system citations, with the linker only as a cross-check |
| W4 | **Retrieval (RAG Phase 1) done** (`scripts/rag/`, `docs/20260927_222210_*`, `docs/20261009_121822_*` §9). Strategies are now **S1, S2, S3, S2c, S4** (caput variants, `docs/20261005_184116_*`). Result `v2d`: S2 best at 4k; the caput sentence hurts at every level (p ≤ 0.002); groupings neutral for recall | The answer grid has five strategies, not three. The paired comparisons of interest are S2 − S1 (main hypothesis), S3 − S2, S2c − S2 and S4 − S3 (§5.3). Retrieval recall is only a proxy; whether a partial hit is enough to answer is exactly what nugget scoring decides |
| W5 | **Generation (RAG Phase 3) not implemented.** No system answers exist yet (`runs/` holds only `retrieval/`) | Nugget creation, validation and the automatic robustness checks (phases 1–3) can run **now**. Judge selection (phase 4) needs only the gold answers and their corruptions (§5.7), so most of it can run before the first answer runs too |
| W6 | **FiscalQA Pro comparison** (`docs/20260929_111356_*` §5): adopt deterministic value checks, year-aware `contradicts`, a temporal slice, a reference date in the generation prompt and cluster-aware statistics | Folded into creation (rule R8, the year stays attached to every value, §3.2), validation (§3.3) and scoring (§5.3, §5.4). The reference date belongs to the RAG generation prompt |
| W7 | **OpenAI reasoning models reject `temperature`.** Measured in the sibling parser: `gpt-5.6-luna` returns `400 unsupported_value` for `temperature=0`; only the default is accepted (`../lexml_parser_non_statutory/docs/20260916_173138_openai_referee_temperature_400.md`). The Sol models are reasoning models too | v1's "temperature 0 where the API allows it" becomes: **no `temperature` for OpenAI reasoning models**; pin model id + `reasoning.effort` + prompt hash, and make reruns exact through the **raw-response cache**, not through decoding settings (§6.3) |
| W8 | **Newer OpenAI models released.** `gpt-6.1-sol` came out on 2026-09-29 (DevDay), three days after v1 | Creator choice settled on **`gpt-6.1-sol`** (§6.1). The user asked for an OpenAI frontier model as creator |
| W9 | **The shared LLM client** (RAG plan §7.5, recommended) does not exist yet | Whichever of nuggets / RAG Phase 3 is built first creates `scripts/llm_client/`. With W5, that is likely the nugget code (§7) |
| W11 | **Cost review** (2026-10-11): the earlier ≈ $95–135 covered OpenAI only, and half of it was repeated GPT runs and a prompt-iteration buffer at high effort. The Gemini roles had not been costed | Repeated GPT runs replaced by a Qwen3.8-Max set (§3.5.2); prompt iteration on the 30 pilot questions only; all providers in one cost table (§6.4); multi-set **scoring** flagged as the real cost driver |
| W10 | **No human audit in the near term** (user, 2026-10-11) | Without people, nugget **accuracy** cannot be measured, only reduced and estimated by models. The plan therefore (1) strengthens automatic error reduction (§3.5), (2) shows that the paper's **comparisons** do not depend on nugget errors (§5.6), and (3) tests nuggets + judge on answers whose correct score is known by construction (§5.7). The judge calibration of v1 §4.4 also relied on human labels; §5.7 replaces it |

---

## 1. Decisions (revised)

| # | Topic | Decision |
|---|---|---|
| D1 | Generator LLMs | Unchanged: **OpenAI**, **Maritaca Sabiá and Sabiazinho**, **DeepSeek** |
| D2 | Judge | **Revised (2026-10-11):** candidates **Gemini** and an open-weight **Qwen**, **selected with the known-answer tests (§5.7)** while human labels are not available. The Gemini candidate is **`gemini-3.8-flash`**; `gemini-3.1-pro-preview` runs on a 10 % subset of the tests and replaces Flash only if it is clearly better there (balanced accuracy > 0.05 higher). Qwen is primary if its balanced accuracy there is within ≈ 0.05 of Gemini's. An **OpenAI judge on a subset** measures self-preference. Human calibration (v1 §4.4) is added when the audit happens |
| D3 | Nugget creator | **Revised (2026-10-11): `gpt-6.1-sol`**, OpenAI Responses API, `reasoning.effort = medium` (D12), Structured Outputs (strict JSON schema), Batch API for the full run. `gpt-5.6-sol` is not used (§6.1). The [LN] baseline (prompt of v1 §1.1 + a small model) is optional; if run, use `gpt-5.6-luna`, since `gpt-5.4-nano` is two generations old |
| D4 | GPU endpoints | Unchanged: only if Qwen is served ourselves |
| D5 | Human audit | **Revised (2026-10-11): postponed.** Replaced for now by the automatic robustness program (§3.5, §5.6, §5.7). When it happens, it follows v1 §3.4 (annotators: the user and another team member), or a minimal version (§3.4) |
| D6 | Legal-provision score | Unchanged (secondary metric), now on `fragment_id`s and `citations.py` (W3, §5.5) |
| D7 | `contradicts` label | Kept, plus a deterministic **value-conflict** and **temporal-substitution** check (W6, §5.4) |
| D8 | Nugget-set robustness | **Revised (2026-10-11): three full nugget sets from three families**: `gpt-6.1-sol` (primary), **Gemini** (`gemini-3.1-pro-preview`) and **Qwen3.8-Max** (Alibaba Model Studio API). Neither Gemini nor Qwen is a generator family (D1). With no human audit, agreement across the sets is the **main** robustness argument (§3.5.2, §5.6). The main comparisons are scored with all three sets; the rest of the grid with the primary set only (§6.4) |
| D9 | **New:** question scope | All 715 questions are nuggetized. Slices (procedure-only, temporal, short answers) are flags, not exclusions |
| D11 | **New:** model per role | Creation: `gpt-6.1-sol`, Batch, medium effort (D12). Second and third sets: `gemini-3.1-pro-preview` (Batch) and `qwen3.8-max`. Auditors: Gemini 3.1 Pro and Qwen3.8-Max. Mechanical roles (alignment, round-trip reconstruction, corruption rewrites): `gemini-3.8-flash` (Batch). Judge candidates: `gemini-3.8-flash` (3.1 Pro on a check subset) and an open-weight Qwen on our endpoint (D2). Qwen3.8-Max is **not** a judge candidate: it is not cheaper than Gemini (§6.4), it would make both candidates Qwen-family, and it created the third nugget set. Run the Gemini Flash roles **before 2027-01-01**, when its prices double |
| D12 | **New:** reasoning effort | **Medium for every LLM call** (user, 2026-10-11, to limit cost): `reasoning.effort: medium` for `gpt-6.1-sol`; the equivalent setting for Gemini (a medium thinking level where the model offers one, otherwise a thinking budget of ≈ 2k tokens) and for Qwen3.8-Max (thinking on, thinking budget ≈ 2k tokens). The exact Gemini and Qwen parameters are checked in phase 0 and recorded in `models.yaml`. The pilot no longer compares effort levels; it reports quality at medium, and any change of effort is a new decision by the user |
| D10 | **New:** release label | The nuggets are frozen and released as **`nuggets/gold/v0-auto/`** ("automatic, not human-audited"), with every raw response, flag and robustness report. A later audit produces `v1` as a patch on it. The paper describes the error estimates as **model-based**, never as measured accuracy |

---

## 2. Input

- **Source:** `dataset/questions.jsonl` (v2.0, built by `scripts/dataset/build_v2_dataset.py`), fields
  `question_number`, `question_summary`, `question_text`, `answer_cleaned`. `prepare` records the
  SHA-256 of the file and of each prepared text, and the dataset build commit
  (`dataset/build_report.json`). When v2.0 is on the HF Hub, the manifest also records the Hub
  revision. The text is identical to v1.0/v1.1 (checked in v1 §2 and again on 2026-10-11, W2).
- **Prompt input:** `question_summary` + `question_text` + `answer_cleaned`. The summary ("OBRIGATORIEDADE")
  is new relative to v1. It costs a few tokens and helps the model name the subject in each nugget.
- **Size** (o200k tokenizer, question + answer): **195k tokens in total**, median 156, p90 523,
  max 6,306 (the 3,316-word answer). One call per question is enough; no chunking.
- **Cases the prompt and validator must handle** (unchanged from v1 §2): 20 answers under 80
  characters; long enumerations (one nugget per item); 50 answers still pointing to other questions;
  program/PGD instructions; embedded citations (to `legal_basis`, not to the text); `linked_questions`
  are not expanded.
- **New: temporal values.** 77 answers contain R$ amounts and 86 contain percentages
  (`docs/20260929_111356_*` §4.3). The corpus holds **other years' values of the same provisions**
  (Lei 9.250 art. 8º II b items 1–10; Lei 11.482 art. 1º tables up to May 2025). A nugget that states
  "o limite é R$ 3.561,50" without its year cannot tell a correct AC-2023 answer from a wrong-year
  one, so the year must be part of the nugget (rule R8).

---

## 3. Nugget creation

### 3.1 Schema

As in v1 §3.1 (`nugget_id`, `question_number`, `text`, `importance` vital/okay, `category`,
`legal_basis`, `source_span`, `ordinal`), plus:

- `values`: list of `{raw, kind (brl|pct|date|count|deadline), normalized, reference_period}`, filled
  by the **validator** from `text`, not by the LLM. It drives the value checks of §3.3 and §5.4.
- `flags`: `procedimento_pgd`, `temporal` (has a value, or cites a provision amended after
  2024-05-03), `short_answer`. Question-level flags are copied to every nugget so slices are one
  filter.

The pydantic model is the single source: the JSON schema sent to the API (Structured Outputs,
`strict: true`) is exported from it, without the validator-filled fields.

### 3.2 Prompt rules (pt-BR, `scripts/nuggets/prompts/create_v1.pt.md`)

Rules R1–R7 are v1 §3.2 rules 1–7: self-contained nuggets; atomic, but a condition stays with its
rule; exact values and technical terms verbatim; always a verdict nugget; nothing outside the answer;
citations in `legal_basis`; schema output. Added:

- **R8 (temporal anchor).** Every nugget that states an amount, rate, limit or deadline names the
  period it applies to (exercício 2024 / ano-calendário 2023, or the period the answer gives). If the
  answer gives no period, the nugget uses the question's period, never a year the model knows from
  elsewhere.
- **R9 (no updating).** The model must not "correct" a value to the law it knows. `gpt-6.1-sol` has a
  knowledge cutoff of 2026-04-30, so it knows the 2025 tables (e.g. Lei 15.191/2025, Lei 15.270/2025).
  The gold answer is the truth even when the law changed later. The numeric grounding check (§3.3)
  enforces this mechanically.
- **R10 (worked examples).** Numbers that appear only in a worked example (e.g. Q617, Q620) give no
  nugget unless the example states a rule. This also keeps computed figures out of the value checks.

The prompt has a fixed prefix (instructions, schema, two worked examples: one short Sim/Não answer
and one enumeration like Q001) and a variable suffix (the question). The fixed prefix is
≈ 3k tokens and identical across calls, so OpenAI prompt caching bills it at the cached rate.

**One call or two (importance separately)?** Unchanged: the pilot decides (§4, phase 1).

### 3.3 Automatic validation (`validate`, no LLM)

v1 §3.3 (schema, unique ids, numeric grounding as a hard error, `source_span` found in the answer,
dedupe, coverage of answer lines, ≥ 1 vital per question, `validation.json`), plus:

- **Value extraction** with pt-BR normalization (`R$ 30.639,90` ≡ `30639.90`; `7,5%` ≡ `0.075`;
  `30 de abril de 2024` ≡ `2024-04-30`; amounts written in words in parentheses are ignored). The
  same module is reused at scoring time (§5.4), so creation and scoring normalize values the same
  way.
- **Period check (R8):** a `valor_prazo` nugget without a year or period expression is a warning, sent
  to the review queue.
- **Out-of-answer year:** a year in the nugget that is not in the question or answer is a hard error
  (catches R9 violations that change only the year).

### 3.4 Human audit (postponed, D5)

When it happens, it follows v1 §3.4: checks C1–C6, guideline v1 → calibration on 10 answers → guideline v2,
stratified sample of 60 questions + every validator flag, annotator A on all 60, B on 12, adjudication,
specialist session for escalations, report with 95 % CIs and κ, **freeze gate** (C1 ≥ 95 %, ≥ 90 % of
answers with no missing vital fact). Two changes:

- The stratification adds the **temporal** flag, so value-bearing answers are in the sample in
  proportion (≥ 10 of the 60).
- The LLM cross-check over all 715 answers (v1 §3.4.4) is run by **Gemini**, the family not chosen as
  creator. Its flags go to the review queue; they are not labels.

The audited set is `nuggets/gold/v1/` (SHA-256), released as a patch on `v0-auto` (D10).

**Minimal version**, if only a little time becomes available: one annotator, 20 answers drawn at
random from the same strata (with ≥ 4 temporal answers), checks C1, C4 and C5 only, about 1–2 h. It
turns the model-based error estimates of §3.5 into a measured (if wide) interval, and checks whether
the LLM auditors' flags agree with a person.

### 3.5 Nugget robustness without the human audit (W10)

Five layers, from cheapest to most expensive. None of them measures accuracy the way the audit
would: models share blind spots with the creator. Together they remove most mechanical and
single-model errors, and they produce **model-based** error estimates for the paper.

#### 3.5.1 Mechanical checks (no LLM)

§3.3 becomes the main safety net. Added for the no-audit setting:

- **Enumeration count:** for answers with numbered or lettered items ("1 -", "a)"), the number of
  items whose line is covered by some `source_span` must equal the number of items, unless R10 or a
  guideline rule (pointers to other questions) excludes the item. A missing item is a hard error.
- **Self-containment regex (C2 proxy):** nuggets that start with or contain unresolved back-references
  ("esse", "essa", "tal", "o referido", "o mesmo", "a mesma", "neste caso", "nessa hipótese") or that
  mention "o contribuinte" when the question limits who is meant are warnings, sent to the repair
  queue (§3.5.3).
- **Verdict check:** if the answer starts with "Sim" or "Não", exactly one `resposta_direta` nugget
  must exist and carry the same polarity.
- All warnings that survive repair are listed per nugget in the release (`flags`).

#### 3.5.2 Cross-family agreement (replaces repeated GPT runs)

Repeated runs of the same model measure only its sampling noise: a mistake GPT makes every time
(e.g. always dropping a given condition) is "stable" across three GPT runs. Three model families have
different blind spots, so their agreement is the stronger signal, and it costs less (W11).

- The three sets of D8 (GPT, Gemini, Qwen3.8-Max) are made with the **same prompt** (R1–R10, the same
  schema) and validated with §3.3.
- Align them per question: first by `source_span` overlap, then by an LLM aligner
  (`gemini-3.8-flash`) for the rest.
- Each primary nugget gets `stability` ∈ {3/3, 2/3, 1/3} (how many families produced a matching
  nugget) and `importance_agreement` (how many gave the same vital/okay label).
- A fact present in **both** other sets but missing from the primary set, with a `source_span` in the
  gold answer, is an **omission candidate** for the repair step (§3.5.3).
- Reported: share of 3/3 nuggets, share of vital labels with 3/3 agreement, per category. Unstable
  vital labels are the expected weak point (v1 §3.4.2); §5.6 tests whether they matter.
- **Same-model noise** is still measured, on the 30 pilot questions only: two more `gpt-6.1-sol`
  runs, reported as a side number (how much of the cross-family disagreement is just sampling).

#### 3.5.3 Two-auditor LLM review with a repair loop

- Two auditors from families other than the creator apply checks **C1–C6** (v1 §3.4.1) to every
  question, comparing the nuggets with the **gold answer** (never with the law). Auditor 1 is
  **Gemini 3.1 Pro**; auditor 2 is **Qwen3.8-Max** (D11). Each audits the primary set, not its own
  family's set.
- Inputs to the auditors: the question, the gold answer, the nuggets, and the omission candidates of
  §3.5.2 and §3.5.4.
- **Repair:** items flagged by **both** auditors, plus hard validator warnings, go back to the creator
  with the auditors' reasons, in one repair call per question. The repaired nuggets go through §3.3
  and the auditors again. At most two repair rounds; what is still flagged by both auditors is
  dropped (C1 failures) or kept with a flag (other checks), and listed.
- Items flagged by **one** auditor are kept and listed with the flag.
- **Model-based error estimate:** before repair, the share of nuggets flagged by both auditors per
  check, with a 95 % CI over questions. Reported as "flagged by two independent LLM auditors", not as
  an error rate.

#### 3.5.4 Round trip and cross-set alignment (omissions)

- **Round trip:** `gemini-3.8-flash` writes an answer from the nuggets alone (no access to the gold
  answer). Qwen3.8-Max lists gold-answer statements missing from that reconstruction. These are omission
  candidates (C5 proxy), sent to §3.5.3.
- **Cross-set alignment:** the alignment of §3.5.2 also gives the nugget-level agreement for each
  pair of sets (share of one set's nuggets matched in the other, both directions), which is reported.

#### 3.5.5 Gold self-score (faithfulness through the judge)

Every candidate judge (§5.7) scores the **gold answer itself** against its own nuggets. A nugget that
both judges label `not_support` or `contradicts` against the text it was extracted from is either
unfaithful or not self-contained, and goes to the repair queue. This is part of §5.7, run early.

#### 3.5.6 Automatic freeze gate (replaces the human gate of v1 §3.4.3)

Proposed thresholds, to be confirmed after the pilot:

| Gate | Threshold |
|---|---|
| Validation | 0 hard errors (numbers, years, spans, enumeration count, verdict polarity) |
| Gold self-score | ≥ 98 % of nuggets `support` by both judges against the gold answer, after repair |
| Two-auditor review | ≤ 2 % of nuggets still flagged by both auditors after repair |
| Known-answer tests (§5.7) | sensitivity ≥ 0.90 on value, year and verdict corruptions for the selected judge |

Cross-family stability (§3.5.2) and set agreement (§3.5.4) are **reported, not gated**: there is no reference
value for them. The set that passes is frozen as `nuggets/gold/v0-auto/` (D10).

---

## 4. Phases and gates

| # | Phase | Output | Gate | Can start |
|---|---|---|---|---|
| 0 | Scaffold: `scripts/llm_client/` (providers `openai`, `gemini`, `openai_compat`, `fake`; cache; cost ledger), `scripts/nuggets/` package, `prepare` | `nuggets/gold/input/questions.jsonl` + manifest | Tests pass with `fake` | now |
| 1 | **Pilot creation:** 30 stratified questions (the RAG plan's `stratified_30`, seed 13, so pilot answers can be scored later) × `gpt-6.1-sol` {1 call, 2 calls} at medium effort (D12); prompt iterations on these 30 only; two more GPT runs for same-model noise (§3.5.2); Gemini 3.1 Pro and Qwen3.8-Max on the same 30 with the winning prompt; the known-answer tests (§5.7) on the 30, with Flash and Pro, as a first look at the judge; optional [LN] baseline. The robustness checks of §3.5 run on the pilot too | `nuggets/pilot/…`, comparison report (nugget counts, reasoning tokens and cost per call **per provider**, validator errors, auditor flags, cross-family stability, gold self-score); a revised cost estimate | The user picks prompt and call mode from the report, with an informal read of a few questions (minutes, not an audit) | after 0 |
| 2 | **Full creation** with `gpt-6.1-sol` (Batch API) + `validate`; **second and third sets** with Gemini 3.1 Pro (Batch) and Qwen3.8-Max (D8) | `nuggets/gold/v0/`, `nuggets/alt_gemini/v0/`, `nuggets/alt_qwen/v0/` | 0 hard validation errors | after 1 |
| 3 | **Automatic robustness** (§3.5): alignment, two-auditor review, round trip, repair loop; gold self-score with both candidate judges (§3.5.5) | `nuggets/gold/v0-auto/` (frozen), `nuggets/robustness/` reports | Automatic freeze gate (§3.5.6) | after 2 |
| 4 | **Judge selection** with the known-answer tests (§5.7) on gold, corrupted and wrong answers; value-hit and inter-judge agreement added once real runs exist | `nuggets/known_answer/` + report | Primary judge chosen; sensitivity / specificity per corruption type reported, incl. `contradicts` | after 3 (real-run part after the RAG Phase 3 pilot) |
| 5 | **Scoring** of the answer grid with both nugget sets; robustness of conclusions (§5.6) | `nuggets/assignments/<run_id>/<judge>/`, `nuggets/scores.csv`, `nuggets/robustness/conclusions.md` | — | after 4 |
| 6 | **Release:** code, `v0-auto` nuggets (HF config `nuggets`), robustness and known-answer reports, raw responses | HF dataset v2.0 + repo | README quick start works in a clean venv | after 5 |
| 7 | *Later, optional:* human audit (§3.4, full or minimal) and human judge calibration (v1 §4.4) | `nuggets/gold/v1/` patch, `nuggets/calibration/` | Audit gate of v1 | when people are available |

A dated `docs/` note records the decisions and results at the end of each phase.

---

## 5. Scoring system answers

### 5.1 Input contract

Unchanged: one JSONL per run, `{"run_id", "question_number", "answer"}`, plus a sidecar `run.json`.
The RAG plan (§7.4) already writes `runs/answers/<run_id>/answers.jsonl` in this form, with
`context_id` and token usage per line. `run.json` carries the strategy (S1/S2/S3/S2c/S4), embedding,
budget or `k=0` / oracle, generator and prompt hash.

### 5.2 Assignment call

Unchanged (v1 §4.2): one judge call per (question, answer) with all nuggets of the question, labels
`support` / `partial_support` / `not_support` / `contradicts`, short justification, Structured Outputs.

### 5.3 Scores and statistics

- V_strict (main), V, A_strict, A, W, contradiction rate (v1 §4.3).
- **Slices:** with/without `procedimento_pgd`; **temporal** vs rest (W6); chapter; answer length.
- **Paired comparisons** for the same generator, embedding and budget: **S2 − S1** (main), S3 − S2,
  S2c − S2, S4 − S3, and each strategy vs the oracle and `k=0`. Paired bootstrap or permutation over
  questions, **plus a cluster bootstrap** by P&R chapter (W6 item 5).
- Answer **length** is reported per run, since recall rewards long answers.

### 5.4 Deterministic checks next to the judge (new, from W6)

For every nugget with `values`:

- **Value hit:** the normalized value appears in the system answer (with a per-kind tolerance;
  exact for R$ and dates). Reported as a separate score.
- **Judge audit for free:** agreement between the judge's `support` and the value hit on these
  nuggets, per judge (§5.7). Disagreements are kept for the later human calibration.
- **Value conflict:** the answer states a different value of the same kind in the same slot →
  deterministic `contradicts` candidate.
- **Temporal substitution:** the conflicting value appears in the corpus as another period's value of
  the same provision (e.g. the 2025 band of Lei 11.482) → tagged `temporal_substitution`. This tests
  the hypothesis that S2 inciso chunks, which isolate one period with its year label, give fewer
  wrong-year answers than S1 article chunks.

### 5.5 Legal-provision score (secondary, D6)

As v1 §4.5, updated by W3: gold = `references.jsonl` (`document_id`, `article_ids`,
`provisions[].fragment_id`, `matchable`); system citations extracted with `scripts/dataset/citations.py`
(both citation orders), resolved to `document_id` + `fragment_id`; `lexml-linker` as a cross-check.
Precision / recall / F1 at document, article and provision level, with the same "unmatchable" rules
as the retrieval evaluation (`docs/20261008_133726_*` §3.1), so retrieval and answer citation scores
are comparable.

### 5.6 Robustness of the conclusions (W10)

The paper's claims are **comparisons** (S2 − S1, etc.), so the question to answer is not "how good
are the nuggets?" but "could nugget errors change the comparison?".

- **Three nugget sets (D8):** score every main comparison with the primary, Gemini and Qwen sets. Report Kendall τ between the strategy rankings and whether every
  paired difference keeps its sign and significance under each set. Agreement means the conclusion
  does not depend on the choice of creator.
- **Perturbation test (no LLM, free):** re-score existing assignments after damaging the nugget set
  with a simulated error model, 1,000 replicates per setting:
  - random nugget **deletion** at 5, 10, 15, 20 % (omissions);
  - **vital ↔ okay flips** at 10, 20, 30 % (the least reliable label), and flips restricted to
    unstable labels (§3.5.2);
  - **targeted deletion** of `condicao` nuggets: conditions and exceptions are where sub-article
    chunks (S2) are expected to help, so losing them is the error most likely to *bias* S2 − S1, not
    just add noise;
  - deletion of nuggets flagged by one auditor (§3.5.3), as a "pessimistic" set.

  Report, per comparison, the share of replicates in which the difference keeps its sign and stays
  significant, and the **break-even error rate** at which it would flip. If S2 − S1 survives 15–20 %
  damage, the missing audit cannot plausibly overturn it.
- **Score variants:** report V_strict, V, A_strict, A and W side by side. A conclusion that holds under
  A (which ignores importance) does not depend on the vital/okay labels.
- **Stable-only scores:** recompute the main comparison on nuggets that all three families produced
  (stability 3/3, §3.5.2).

### 5.7 Known-answer tests (nuggets + judge; replaces human judge calibration for now)

Answers whose correct labels are known **by construction**, built by script from the gold answers and
nuggets. They test the nuggets and the judge together, and they are the basis for choosing the judge
(D2) while human labels are missing.

| Test answer | How it is built | Expected labels |
|---|---|---|
| **Gold** | the gold answer itself | every nugget `support` (also §3.5.5) |
| **Value corruption** (V) | one value of a nugget with `values` changed in the gold text: ± a plausible step, or **another period's value of the same provision found in the corpus** (doubles as a temporal-substitution test) | target nugget `contradicts` (`not_support` counted as a partial detection); others `support` |
| **Year corruption** (Y) | the year of a `valor_prazo` statement changed | target `contradicts` / `not_support`; others `support` |
| **Verdict flip** (N) | leading "Sim" ↔ "Não" (and the verb negated where needed) | `resposta_direta` nugget `contradicts` |
| **Omission** (D) | the `source_span` of one nugget deleted | target `not_support`; others `support` |
| **Dropped condition** (C) | a condition clause ("desde que", "exceto", "salvo", "caso", "se") removed from the target span, rule-based where the clause is delimited, otherwise rewritten by `gemini-3.8-flash` and checked by diff that only the target span changed | target `partial_support` or `not_support`; others `support` |
| **Wrong question** (W) | the gold answer of another question of the same chapter | almost all nuggets `not_support` |
| **Empty** (E) | "Não há informação suficiente nos dispositivos fornecidos." | all `not_support` |

- **Size:** 715 gold + ≈ 1,500 corruptions (V and Y only where values exist; one D and one C per
  question where possible; N for the Sim/Não answers) + 715 wrong-question answers ≈ 3,000 judge calls
  per candidate judge. Gemini 3.1 Pro runs on a 10 % stratified subset (≈ 300 calls) only, to check
  that Flash is not clearly worse (D2).
- **Metrics per judge and corruption type:** sensitivity (target nugget detected), specificity
  (non-target nuggets still `support`), `contradicts` precision, and the score drop of V_strict
  against the gold answer. Balanced accuracy over all types selects the primary judge (D2).
- **On real runs** (after the RAG Phase 3 pilot): agreement between the two candidate judges (κ per
  label, Kendall τ of run rankings) and the judge–value-hit agreement of §5.4.
- **Limit, stated in the paper:** synthetic corruptions are cleaner than real generator errors
  (paraphrase, partial coverage, hedging). The tests bound the judge's behaviour on clear cases; the
  human calibration of v1 §4.4 remains the reference for the subtle ones and is added when possible.

---

## 6. LLM choice, settings and cost

### 6.1 Creator: `gpt-6.1-sol` rather than `gpt-5.6-sol`

Checked on 2026-10-11 on the OpenAI model pages and pricing page (prices per 1M tokens):

| | `gpt-6.1-sol` | `gpt-5.6-sol` |
|---|---|---|
| Released | 2026-09-29 | earlier (2026) |
| Input / cached input / output (standard) | **$2.00 / $0.10 / $10.00** | $4.00 / $0.40 / $20.00 (promotional, "at least through 2026-11-21") |
| Batch (−50 %) | $1.00 / $0.05 / $5.00 | $2.00 / $0.20 / $10.00 |
| Context / max output | 1.05M / 128k | 1.05M / 128k |
| Reasoning effort | low, medium (default), high, xhigh, max | none, low, medium (default), high, xhigh, max |
| Structured Outputs, Batch API | yes | yes |
| Knowledge cutoff | 2026-04-30 | 2026-02-16 |

**Recommendation: `gpt-6.1-sol`.**
1. **Half the price** at every tier, and the 5.6 price is promotional with no stated end rate, so a
   rerun after November could cost more.
2. **Newer generation.** OpenAI reports fewer factual errors than GPT-6 Sol at low effort, and
   better adherence to reasoning instructions than both GPT-6 Sol and GPT-5.6 Sol (a weak proxy). Nuggetization is
   mostly careful instruction following (R1–R10), so this is the property that matters. There is no
   pt-BR or legal benchmark that separates the two; the pilot measures it on our data.
3. Same context, output limit, Structured Outputs and Batch support, so nothing is lost. The missing
   `none` effort level does not matter here.
4. Its later knowledge cutoff is a mild **risk**, not a benefit: it knows more post-2024 law (R9). The
   numeric and year checks of §3.3 catch this mechanically, and the audit measures what is left.

If the pilot shows a clear quality problem with `gpt-6.1-sol`, running `gpt-5.6-sol` on the same 30
questions costs about $5 and settles it.

### 6.2 Creator–generator family overlap

OpenAI is both the nugget creator and a generator (D1). Nuggets phrased by an OpenAI model might match
the phrasing of the OpenAI generator a little better. The paper's comparisons are **between
strategies with the same generator**, so this cancels in the paired tests. It could still favour the
OpenAI generator in a cross-generator table. Controls: R3 (technical terms and values verbatim from the
gold answer), the judge from another family (D2), and the Gemini and Qwen nugget sets (D8): report the
generator ranking under all three sets.

The same reasoning applies to the **judge**: if an open-weight Qwen is the primary judge, it scores
one of the three nugget sets made by its own family (Qwen3.8-Max). This is a creator–judge overlap,
not a creator–generator one, and it is the same for every strategy, so it cancels in the paired
comparisons. The GPT and Gemini sets act as controls, and the paper states it in one sentence.

### 6.3 Settings and reproducibility

- Responses API, `model: gpt-6.1-sol` (the only snapshot listed; record the `model` field returned
  in each response), `reasoning: {effort: "medium"}` (D12), Structured Outputs
  with `strict: true`, **no `temperature`/`top_p`** (W7), `max_output_tokens` ≈ 32k (reasoning +
  nuggets; a truncated response is an error, never parsed).
- **Cache** every raw response keyed by hash(provider, model, params, rendered messages) and release
  it. Reasoning models are not deterministic, so the cache, not the API, is what makes a rerun exact.
- Batch API for phase 2 (≤ 24 h turnaround, 50 % off); synchronous calls with bounded concurrency
  for the pilot and the review loop.
- Cost and token usage (input, cached, output, **reasoning**) per call go to the manifest and to a
  ledger `nuggets/costs.csv`, like `embeddings/costs.csv`.

### 6.4 Cost estimate (all providers, medium effort)

Prices checked on 2026-10-11 on the providers' official pages (per 1M tokens):

| Model | Input | Cached input | Output (incl. reasoning) | Batch |
|---|---|---|---|---|
| `gpt-6.1-sol` | $2.00 | $0.10 | $10.00 | −50 % |
| `gemini-3.1-pro-preview` (≤ 200k prompt) | $2.00 | $0.20 | $12.00 | −50 % |
| `gemini-3.8-flash` (until 2026-12-31; doubles on 2027-01-01) | $0.75 | $0.075 | $3.75 | −50 % |
| `qwen3.8-max` (Model Studio, Singapore) | $2.00 | ≈ 10 % of input (context cache; exact rate on the cache page) | $6.00, thinking and non-thinking alike | none in Singapore |

**Why Qwen3.8-Max does not replace Gemini.** With Batch, Gemini 3.1 Pro costs $1.00 input /
$6.00 output, the same output price as Qwen3.8-Max, which has no batch discount in Singapore, and
half its input price. Moving a Gemini Pro role to Qwen3.8-Max saves nothing; for the known-answer
tests it costs slightly more (table below). It would also leave the robustness checks with two
families instead of three. The saving comes from **Gemini 3.8 Flash** for the judge role and from
**medium effort** (D12).

**Assumptions** (to be replaced by the pilot's measurements; medium effort everywhere):
- **Creation call:** ≈ 3k-token fixed prompt prefix (cached) + 273 tokens of question and answer on
  average → 2.34M input per full set (≈ 2.14M cacheable). Output ≈ 0.8k visible + ≈ 1.5k reasoning
  per question → ≈ 1.6M per set.
- **Audit call:** ≈ 3.5k input (instructions, gold answer, nuggets, omission candidates), ≈ 2k
  output with reasoning; +40 % calls for the repair rounds.
- **Judge call** (known-answer tests and scoring): ≈ 3.5k input (2k cached), ≈ 2.1k output with
  reasoning.

**Creation of one full set (715 questions):** `gpt-6.1-sol` Batch ≈ $9; `gemini-3.1-pro-preview`
Batch ≈ $12; `qwen3.8-max` ≈ $11–14. For reference, high effort (≈ 4k reasoning tokens) would roughly
double each of these.

**Known-answer tests, ≈ 3,000 judge calls per candidate (§5.7):**

| Judge | Estimate |
|---|---|
| `gemini-3.8-flash`, Batch | **≈ $14** |
| `gemini-3.1-pro-preview`, Batch, full | ≈ $43 (only ≈ $4 on the 10 % check subset) |
| `qwen3.8-max` (no batch) | ≈ $48 |
| open-weight Qwen on the HF endpoint | ≈ $10–25 of GPU time |

**Nugget side: creation, robustness and judge selection (phases 1–4):**

| Provider | Item | Estimate |
|---|---|---|
| OpenAI | Pilot: 30 q × {1, 2 calls}, prompt iterations on the same 30, two runs for same-model noise | ≈ $5–7 |
| OpenAI | Full creation, Batch | ≈ $9 |
| OpenAI | Repair calls (≈ 20 % of questions, up to two rounds) | ≈ $3 |
| | **OpenAI subtotal** | **≈ $17–20** |
| Gemini | Pilot set and pilot known-answer tests on 30 q | ≈ $2 |
| Gemini | Second set, 3.1 Pro, Batch | ≈ $12 |
| Gemini | Auditor 1, 3.1 Pro, Batch | ≈ $16 |
| Gemini | Alignment of three sets, round-trip reconstruction, corruption rewrites (3.8 Flash, Batch) | ≈ $5 |
| Gemini | Known-answer tests: 3.8 Flash in full + 3.1 Pro on the 10 % subset, Batch | ≈ $18 |
| | **Gemini subtotal** | **≈ $50–55** |
| Alibaba | Pilot set on 30 q | < $1 |
| Alibaba | Third set, Qwen3.8-Max | ≈ $11–14 |
| Alibaba | Auditor 2 | ≈ $15 |
| Alibaba | Round-trip comparison | ≈ $8–11 |
| | **Alibaba subtotal** | **≈ $35–40** |
| HF endpoint | Known-answer tests with the open-weight Qwen judge (model size still open, §9) | ≈ $10–25 |
| | **Total, phases 1–4** | **≈ $115–140** |

If the 10 % subset shows that 3.1 Pro is clearly the better Gemini judge (D2), running it in full adds
≈ $39.

**Scoring the answer grid (phase 5) is the real cost driver** and is not in the total. One answer run
(715 questions) costs, per judge and per nugget set, at medium effort:

| Judge | Per run and set |
|---|---|
| `gemini-3.8-flash`, Batch | ≈ $3.5 |
| `gemini-3.1-pro-preview`, Batch | ≈ $10 |
| `qwen3.8-max` (no batch) | ≈ $11 |
| `gpt-6.1-sol`, Batch (self-preference subset only) | ≈ $9 |
| open-weight Qwen on the HF endpoint | ≈ $3–8 of GPU time |

A grid of 40 runs scored with three sets is ≈ $420 with Gemini 3.8 Flash and ≈ $1,200 with 3.1 Pro.
The plan therefore scores **every run with the primary set and the primary judge**, and uses the two
other sets and the second judge only for the **main comparisons** (S2 − S1 and the caput variants at
the headline budget, per generator). The phase 5 budget is estimated with `--dry-run` once the grid
is fixed. The OpenAI self-preference subset (e.g. 8 runs × 200 questions, ≈ $18) belongs to this
phase too.

---

## 7. Code design

As v1 §7, with these changes:

```
scripts/llm_client/            shared with scripts/rag/ Phase 3 (RAG plan §7.5)
  providers/ base.py (complete_json(messages, schema) -> result + usage), openai.py (Responses API,
             Structured Outputs, Batch submit/poll), gemini.py, openai_compat.py, fake.py
  cache.py, cost.py (prices from the registry, ledger rows), retry.py
scripts/nuggets/
  nuggets.py, models.yaml, prompts/, nuggetizer/{data,schema,create,validate,values,review,assign,
  metrics,export}.py, tests/
  nuggetizer/robustness/  align.py (cross-run and cross-set alignment), audit.py (two-auditor review
                          + repair loop), roundtrip.py, perturb.py (§5.6 error models),
                          known_answer.py (§5.7 corruption builders and metrics)
```

- `models.yaml` entry for the creator:

  ```yaml
  gpt-6.1-sol:
    provider: openai
    model_id: gpt-6.1-sol
    api_key_env: OPENAI_API_KEY
    params: {reasoning_effort: medium, max_output_tokens: 32000}   # D12; no temperature (W7)
    price: {usd_per_million_input: 2.00, usd_per_million_cached_input: 0.10,
            usd_per_million_output: 10.00, batch_discount: 0.5, checked: 2026-10-11}
  ```
- Registry entries for the other families (the Qwen one goes through `openai_compat`):

  ```yaml
  gemini-3.1-pro:
    provider: gemini
    model_id: gemini-3.1-pro-preview        # preview: record the served version; outputs are cached
    api_key_env: GEMINI_API_KEY
    price: {usd_per_million_input: 2.00, usd_per_million_cached_input: 0.20,
            usd_per_million_output: 12.00, batch_discount: 0.5, checked: 2026-10-11}
  gemini-3.8-flash:
    provider: gemini
    model_id: gemini-3.8-flash
    api_key_env: GEMINI_API_KEY
    price: {usd_per_million_input: 0.75, usd_per_million_cached_input: 0.075,
            usd_per_million_output: 3.75, batch_discount: 0.5, checked: 2026-10-11,
            note: "doubles on 2027-01-01"}
  qwen3.8-max:
    provider: openai_compat
    base_url: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    model_id: qwen3.8-max                   # pin a dated snapshot (e.g. qwen3.8-max-0902) if listed
    api_key_env: DASHSCOPE_API_KEY
    params: {response_format: json_object}  # schema enforced by pydantic validation + retry
    price: {usd_per_million_input: 2.00, usd_per_million_output: 6.00, checked: 2026-10-11}
  ```
- `create --batch` writes the Batch input file, submits it, and `create --collect` fetches the
  results into the cache; the rest of the pipeline reads only the cache.
- `create --dry-run` prints calls, tokens and the estimated cost from `models.yaml`, and sends
  nothing (same idea as `rag.py run --dry-run`).
- `values.py` holds the pt-BR value normalizer used by `validate` (§3.3), by `metrics` (§5.4) and by
  the value and year corruptions (§5.7).
- The corruption builders are deterministic (seeded), and every test answer records which nugget it
  targets and the expected label, so the known-answer set is itself releasable as a test suite for
  other judges.
- `.env` is loaded with `python-dotenv` from the repo root, as in `scripts/embedding/embed.py`.

---

## 8. Setting up the API keys

`.env` (repo root) is gitignored (`.gitignore` line 8). It holds `HF_TOKEN`, `GEMINI_API_KEY`,
`ENDPOINT_URL_JUA_4B_MIXED` and, since 2026-10-11, `OPENAI_API_KEY`. This plan needs one more key,
`DASHSCOPE_API_KEY` (§8.2).

### 8.1 OpenAI (done)

The line added was:

```
OPENAI_API_KEY=sk-proj-…
```

1. On platform.openai.com, create (or pick) a **project** for this research, set a monthly budget
   limit on it (e.g. $75, comfortably above the OpenAI part of §6.4 plus the self-preference
   subset), and create a **project API key** under
   *API keys*. Keys created this way start with `sk-proj-`.
2. Append it without echoing it to the terminal or the shell history:

   ```bash
   read -rs -p "OpenAI API key: " K && printf 'OPENAI_API_KEY=%s\n' "$K" >> .env && unset K; echo
   ```

   (`.env` ends with a newline, so the line is appended cleanly. Editing `.env` with a text editor
   works too.)
3. Check that the key works and the model is visible to the project, without printing the key:

   ```bash
   set -a; . ./.env; set +a
   curl -s https://api.openai.com/v1/models/gpt-6.1-sol \
        -H "Authorization: Bearer $OPENAI_API_KEY" | python3 -m json.tool
   ```

   A JSON object with `"id": "gpt-6.1-sol"` means it works; an `error` object names the problem
   (invalid key, or the model not enabled for the project / usage tier).
4. Batch API queue limits depend on the account's usage tier. 715 requests of ≈ 3k input tokens
   (≈ 2.3M enqueued tokens) fit the lower tiers, but check *Limits* in the project settings before
   phase 2.

Optional, only if the account has several organizations: `OPENAI_ORG_ID=org-…` and
`OPENAI_PROJECT_ID=proj_…` on further lines; the `openai` SDK reads both from the environment.

### 8.2 Alibaba Model Studio (Qwen3.8-Max)

1. In the Alibaba Cloud console, open **Model Studio** in the **Singapore (international)** region and
   create an API key. Keys are tied to a region: a Singapore key works only with the international
   endpoint below, not with the China (Beijing) one. Set a spending alert of about $75 in Billing.
2. Append it the same way:

   ```bash
   read -rs -p "DashScope API key: " K && printf 'DASHSCOPE_API_KEY=%s\n' "$K" >> .env && unset K; echo
   ```
3. Check it with a tiny request (a fraction of a cent):

   ```bash
   set -a; . ./.env; set +a
   curl -s https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions \
        -H "Authorization: Bearer $DASHSCOPE_API_KEY" -H "Content-Type: application/json" \
        -d '{"model": "qwen3.8-max", "messages": [{"role": "user", "content": "Responda apenas: ok"}],
             "max_tokens": 5}' | python3 -m json.tool
   ```

   A `choices` array means it works. An `error` with `InvalidApiKey` usually means the key belongs
   to another region.

### 8.3 Gemini

`GEMINI_API_KEY` is already in `.env`. Before phase 2, check that the project has Batch API access
and that `gemini-3.1-pro-preview` and `gemini-3.8-flash` are listed for the key.

---

## 9. Open questions

1. **How Qwen is run for the judge** (D4): own HF endpoint (vLLM, pinned revision) or a hosted API,
   and which size. Still open from v1.
2. **Second annotator** (name, background) and the **tax/legal specialist** for escalations. Still
   open from v1.
3. **Gemini models** (D11): `gemini-3.1-pro-preview` is a preview and may be replaced. Confirm it at
   phase 1 and record the served version.
4. **Medium-effort equivalents** (D12): the exact Gemini thinking setting and the Qwen3.8-Max thinking
   budget that correspond to OpenAI's medium, checked in phase 0 against the reasoning tokens
   each provider reports.
5. **Effort escalation:** if the pilot shows a clear quality problem at medium (e.g. dropped
   conditions in long enumerations), whether to allow high effort for the long answers only.
6. **Automatic gate thresholds** (§3.5.6): confirm or adjust after the pilot.
7. **Scoring budget** (phase 5): which runs count as "main comparisons" scored with all three sets
   and both judges (§6.4).
8. **Order with RAG Phase 3:** nuggets phases 0–3 do not need answers and can start now. Building
   `scripts/llm_client/` here first means RAG Phase 3 reuses it. Confirm this order.
