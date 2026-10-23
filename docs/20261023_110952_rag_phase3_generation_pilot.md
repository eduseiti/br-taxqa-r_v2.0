# RAG Phase 3 — answer generation: implementation and pilot (`stratified_30`)

**Generated:** 2026-10-23 11:09:52 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** RAG plan §7 (`docs/20260927_204356_rag_pipeline_implementation_plan.md`, stage G) and the grounding
safeguards of `docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md` §4.1–§4.2, on the contexts
of Phase 2 (`docs/20261021_210251_rag_phase2_contexts_execution.md`, main corpus without the RIR/1999,
`docs/20261022_203625_corpus_exclusion_revoked_rir1999.md`).
**User decisions (2026-10-23):** no further corpus exclusion (the revoked INs the P&R cites stay; §4.5 of the
exclusion note closed as "keep everything else"); generators **Sabiá-4, Sabiazinho-4, GPT-5.6 Terra, GPT-5.6 Luna**;
**oracle 4k and 16k** both run; reasoning effort **none** (the lowest level offered); answer format **option A**
(claims with verbatim quotes); no output cap tighter than the default.
**Cost:** **$5.59** in total (ledger `runs/costs.csv`, 1,489 calls): OpenRouter **$2.90** billed (Terra $2.65, Luna
$0.25; the key's usage counter moved by $1.88 only, probably lagging; $32.51 left of the $100 limit), Maritaca
**R$ 13.68** at list price (≈ $2.69 at R$ 5.08/US$; Sabiá-4 R$ 11.37, Sabiazinho-4 R$ 2.31). Estimate before the run:
$13.53 at list price.
**Status:** pilot done; **gate** (RAG plan §9: "pilot answers read by hand; cost per full run estimated") needs the
user's reading (§6); cost per full run in §5.

## 1. What was built

| File | Change |
|---|---|
| `scripts/llm_client/client.py` | `ToolUseDetected`: refuses a registry entry with `tools` / `plugins` / `web_search_options` / … or a `:online` model; rejects (no retry, ledger `finish = rejected:<reason>`) a reply with tool calls, `url_citation` annotations, `web_search_sources` or `usage.tool_execution_details` (Maritaca), `server_tool_use`, or — opt-in `check_billed`, used by generation — a billed cost above the token cost. `temperature` passed on the OpenRouter and `openai_compat` routes; strict `json_schema` on `openai_compat`; ledger column `fx_brl_per_usd`; `request_key` / `is_cached`; `offline` mode (dry runs); `fake` provider (tests) |
| `scripts/rag/llms.yaml` (new) | Generator registry (§2); DeepSeek V4 Pro / Flash present but `enabled: false` (other machine) |
| `scripts/rag/prompts/answer_v1.pt.md`, `answer_closed_v1.pt.md` (new) | System part, a `<<<USER>>>` line, user part (§3) |
| `scripts/rag/ragpipe/generation.py` (new) | Stage G: registry (BRL → USD), prompts, samples, run planning, `--dry-run` estimate, concurrent run loop on `llm_client`, grounding checks, `answers.jsonl` / `run.json` / `summary.csv` |
| `scripts/rag/rag.py` | `generate`, `run --experiment`, `show-answers` |
| `scripts/rag/experiments/pilot.yaml` (new) | The pilot grid (§4) |
| `scripts/rag/tests/test_generation.py` (new) | 7 tests (outputs and checks, closed book, empty oracle skipped, cache rerun byte-identical with no new ledger row, dry run, budget stop and resume, configuration guard, disabled model, tool-use refusal, registry, CLI). **44 + 13 passed** (`scripts/rag/tests`, `scripts/llm_client/tests`) |
| `scripts/rag/README.md`, `requirements.txt`, `.gitignore`, `CLAUDE.md` | Phase 3 documented; `runs/answers/**/{answers.jsonl,run.json,summary.csv}` versioned, `runs/answers/cache/` not |

```bash
P=.venv/bin/python; R=scripts/rag/rag.py
$P $R run --experiment scripts/rag/experiments/pilot.yaml --dry-run      # 56 runs, 1,640 calls, est. $13.53 list
$P $R run --experiment scripts/rag/experiments/pilot.yaml --budget 18    # 5 min 53 s
$P $R show-answers --run runs/answers/jua-4b-mixed/irpf/answer_v1/sabia-4/S2_budget4000 --questions 350
```

Layout: `runs/answers/jua-4b-mixed/irpf/<prompt>/<llm>/<context_id>/{answers.jsonl,run.json}`, run id
`jua-4b-mixed/irpf/answer_v1/sabia-4/S2_budget4000`; `summary.csv` one row per run. A run folder refuses another
configuration (prompt hash, generator settings, context set, checks version) unless `--force`; questions of other
samples already in `answers.jsonl` are kept, so the same runs grow from the pilot to all 715 questions.

## 2. Generators (probed 2026-10-23)

| Name | Route | Model | Settings | Price per 1M (list) |
|---|---|---|---|---|
| `sabia-4` | Maritaca direct (`chat.maritaca.ai/api`) | `sabia-4-2026-01-06` (accepted; `/models` lists only `sabia-4`; replies name `sabia-4`) | temperature 0, `max_tokens` 4000, strict `json_schema` | R$ 5 / R$ 20 (cached R$ 1,25) |
| `sabiazinho-4` | Maritaca direct | `sabiazinho-4-2026-01-06` | same | R$ 1 / R$ 4 |
| `gpt-5.6-terra` | OpenRouter, `only: openai/flex`, no fallbacks | `openai/gpt-5.6-terra` (snapshot `-20260709`) | reasoning effort `none` (offered: none, low, medium = default, high, xhigh, max; no `minimal`); **no temperature parameter** on any endpoint; `max_tokens` 4000 | $2 / $12; flex bills ≈ 57 % of list in the pilot |
| `gpt-5.6-luna` | same | `openai/gpt-5.6-luna` (`-20260709`) | same | $0.20 / $1.20 |

- Knowledge cutoff (OpenRouter catalog): GPT-5.6 **2026-02-16** — after the P&R date, so 2025–2026 law is in its
  training data; Maritaca publishes none.
- **FX:** `fx_brl_per_usd: 5.08` (PTAX of 2026-10-16, found by web search on 2026-10-23), recorded in `llms.yaml`,
  each `run.json` and each ledger row; to be replaced by the rate of the billing date. The BRL prices stay in
  `run.json`. Maritaca night (22–06 BRT) and flex discounts are not modelled: the ledger is at list price.
- No reply in the pilot showed tool use or a billed cost above its token cost (all 1,489 ledger rows `stop`);
  no reasoning tokens; no retries; served provider OpenAI on every GPT call.

## 3. Prompt and reply format

`answer_v1` (pt-BR): answer only from the numbered provisions; **reference date** exercício 2024 / ano-calendário
2023 (the recommendation of `docs/20260929_111356_fiscalqa_pro_temporal_misgrounding_comparison.md` §5 item 4);
claims that, read in order, form the answer; each claim with one or more `{documento, trecho}` — a short (≈ 30
words) verbatim excerpt; legal provisions cited in the usual form in the claim text; no value, date, rate, law or
year absent from the provisions; a negative answer may rest on an exhaustive list or an unmet condition; answer
the supported part only; abstain (empty claims, `abstencao: true`) when nothing is supported. `answer_closed_v1`:
the same without documents, from the model's own knowledge (closed-book control).

Strict schema `{afirmacoes: [{texto, fundamentos: [{documento, trecho}]}], abstencao}`. **The scored answer is the
claim texts joined by newlines**; no claim → the fixed sentence "As disposições fornecidas não são suficientes para
responder à pergunta." (closed book: "Não sei responder a esta pergunta."), `abstained: true`.

**Changes made during the probes (Q350, Q012, Q676 on S2 4k, 18 calls, $0.09), before the pilot:**

1. Quotes of whole articles (≈ 600 output tokens for Terra on Q350) → "trecho curto (até cerca de 30 palavras) … Não
   copie artigos inteiros": Terra's output fell to ≈ 220 tokens on the same questions.
2. `abstencao` moved after `afirmacoes` in the schema (the model writes what the context supports before deciding).
3. Rule 6 added (negative answers): both Sabiá models abstained on Q350 ("sogro/sogra as dependents?") with Lei 9.250
   art. 35 in the context — the answer is that the exhaustive list of dependents does not include them. With the
   rule both answer correctly. Many P&R questions are of this "is X allowed? — no" form.
4. Quote check on words (punctuation ignored): Luna's quote of art. 35 failed on one missing comma.

### 3.1 Grounding checks (no LLM, per answer)

- **Quote status** per fundamento: `ok` (the quote's words appear contiguously and in order in the cited
  `[Documento n]` block; case, punctuation and spacing ignored; an ellipsis may skip text, the pieces then in
  order), `not_found`, `too_short` (< 3 words), `bad_document` (no such block). A claim is **grounded** when one of
  its quotes is `ok`.
- **Values not in context:** R$, % and dates of the answer (`nuggetizer/values.py`) found in neither the context nor
  the question (a date without a year matches day and month).
- `cited_chunk_ids` (document numbers → chunk ids) for the legal-provision score of phase 5.

## 4. Pilot grid

14 context sets × 4 generators × 30 questions (`stratified_30`): S1, S2, S3, S2c, S4 at 4k; S1, S2 at 2k and 8k;
closed book; oracle 4k and 16k; wrong context (S2 4k); `S2_budget4000_context_v1` (template ablation). 1,680 answer
lines: **1,639 ok, 40 skipped** (the oracle of the 5 sample questions without resolved gold, × 2 oracle sets × 4
generators), **1 error** (§6.6). ≈ 150 calls were cache hits (most oracle 4k and 16k prompts are identical: the
oracle of these questions fits in 4k).

### 4.1 Per generator (all sets)

| Generator | Abstention | Mean output tokens (max) | Quote `ok` | Claims grounded* | List USD | Billed |
|---|---:|---:|---:|---:|---:|---:|
| Sabiá-4 | 11.7 % | 622 (2,334) | 90.5 % | 85.0 % | 2.42 | R$ 11.37 |
| Sabiazinho-4 | 7.3 % | 620 (1,997) | 87.3 % | 85.4 % | 0.49 | R$ 2.31 |
| GPT-5.6 Terra | 9.3 % | 395 (1,389) | 99.4 % | 89.2 % | 4.95 | $2.65 |
| GPT-5.6 Luna | 21.0 % | 338 (1,167) | 98.8 % | 91.7 % | 0.47 | $0.25 |

\* Over all claims, closed book (no quotes) included; on the retrieval sets the grounded share is 0.90–0.98
(Maritaca) and 0.97–1.00 (GPT).

### 4.2 Abstention rate by set

| Set | Sabiá-4 | Sabiazinho-4 | Terra | Luna |
|---|---:|---:|---:|---:|
| S1 / S2 / S3 / S2c / S4 4k | 0.03 each | 0 | 0–0.03 | 0.10–0.17 |
| S1 2k / S2 2k | 0.03 / 0.10 | 0 | 0 / 0.07 | 0.23 / 0.17 |
| S1 8k / S2 8k | 0 / 0 | 0 | 0.03 / 0.03 | 0.20 / 0.13 |
| closed book | 0.03 | 0 | 0 | 0 |
| oracle 4k / 16k (25 questions) | 0.12 | 0.08 | 0.04 | 0.16 |
| **wrong context** | **1.00** | **0.87** | **0.97** | **1.00** |
| S2 4k with `context_v1` | 0.07 | 0 | 0.03 | 0.23 |

Most retrieval-set abstentions are on questions whose gold articles are not in the context (e.g. Luna S2 4k: 3 of
5); the oracle abstentions all have the gold in the context (Luna: Q023, Q039, Q350, Q705).

### 4.3 Other measures

- **Answer length** (non-abstained): ≈ 650–900 characters on the retrieval sets, growing with the budget for every
  generator (S1 2k → 8k: Terra 667 → 1,008; Sabiá-4 677 → 817). Length must be reported next to nugget recall.
- **Values not in context** (retrieval and oracle sets): 7 answers in 1,350, **all false positives** (checked one by
  one): 6 values the context writes in words ("quinze por cento" for "15%", Q113 ×4; "vinte por cento", Q703 ×2) and
  one date written "1° de janeiro de 1992" with a degree sign (Q710): limits of the check (§6.3). Closed book: 20–47 % of
  the answers carry a value the question does not contain (expected: they come from the model's knowledge; the
  closed-book answers are the leakage reference).
- **Bad document numbers:** 55 quotes in 1,639 answers, almost all Maritaca (a quote attributed to the wrong block,
  e.g. Sabiazinho Q012: the excerpt is in Documento 1, cited as Documento 4).
- **`abstencao` true with claims:** 27 answers, all Sabiazinho-4 (partial answers flagged as abstentions). The flag
  is not used: an answer with claims counts as answered.

## 5. Cost per full run (715 questions), from the pilot's billed cost per call

| Grid | Sabiá-4 | Sabiazinho-4 | Terra (flex) | Luna (flex) | OpenRouter total |
|---|---:|---:|---:|---:|---:|
| one 4k retrieval run | $4.4–4.9 (R$ 22–25) | $0.9–1.0 (R$ 5) | $5.1–5.4 | $0.5 | $5.6–5.9 |
| headline grid (5 strategies at 4k + closed book + oracle 4k) | $27.4 (R$ 139) | $5.5 (R$ 28) | $31.6 | $3.0 | **$34.6** |
| the pilot's 11-run grid (§2.3 of the first-evaluation note) | $46.4 (R$ 236) | $9.4 (R$ 48) | $54.9 | $5.2 | $60.1 |
| all 14 pilot sets | $58.8 (R$ 299) | $12.0 (R$ 61) | $69.4 | $6.6 | $76.0 |

Maritaca at list price; its flex tier (−50 %) or the night discount (−30 %) would halve or cut these. Oracle and
closed-book runs over all 715 questions are slightly overestimated (119 questions have an empty oracle, and the
per-call mean is used).

**Against the budget:** the OpenRouter key has **$32.51 left** (limit $100, expires 2026-11-20). The headline grid's
generation alone (**≈ $35**) does not fit, and phase 5 scoring adds ≈ $28–42 (primary nugget set, 28 runs) + ≈ $12
(context support) + the cross-set scoring of S1 vs S2 (≈ $16–24). **The first full evaluation needs ≈ $90–115 on
OpenRouter**, so the key limit must be raised (≈ $84 of prepaid credit was left behind it on 2026-10-21) before it
starts. The pilot measured GPT costs ≈ 30 % above the first-evaluation note's flex estimate (Terra $31.6 vs
$22 for 7 runs), mostly from the longer output (quotes) and the flex discount being ≈ 43 % rather than 50 %.

## 6. Observations and open items

1. **Hand reading (gate):** I read Q350, Q012, Q676 (probes), Q503 and Q440 across generators and S1/S2 at 4k. The
   answers are on topic, follow the provisions, cite them in the usual form and quote correctly; Terra gave the
   gold provision for Q503 (IN SRF 83, art. 2º, VI, "e"), Sabiá-4 the same article with a wrong inciso ("V"), a
   citation error the legal-provision score will see. **To be read by the user:**
   `rag.py show-answers --run runs/answers/jua-4b-mixed/irpf/answer_v1/<llm>/<set> --questions <n>` on 3–5 pilot
   questions; suggested Q350, Q440, Q503, Q676, Q705.
2. **"Insufficiency" claims.** Answers to partly supported questions often end with a claim such as "As disposições
   fornecidas não estabelecem em qual ano-calendário…" (Q440, Terra and Sabiá-4). It is honest and matches rule 7,
   but it is not content: the judge will mark it `not_support` for every nugget, so it does not inflate recall; it
   lowers precision-like measures, if any are reported.
3. **Value check: spelled-out numbers and "1°".** The provisions write many values in words ("quinze por cento",
   "vinte por cento"), and some ordinals with a degree sign; the check compares digits and `º` only, so every flag
   of the pilot outside closed book is a false positive. Fix for phase 5 (pt-BR number words → digits, `°` as `º`,
   in the presence test). The closed-book rate is unaffected (no context).
4. **The wrong-context control works, and its failures are off-topic answers, not leaks.** The 5 non-abstentions
   (Sabiazinho Q039, Q259, Q291, Q564; Terra Q039) answer the **donor question's** topic from the donor context
   (Q039 "local de apresentação" answered with book-expense deductions; Q291 "indenização do locador" with prizes in
   goods): the context is followed, the question is not. Nugget scoring will give them ≈ 0; report them as
   "off-topic" next to the abstention rate.
5. **Luna abstains most** (10–23 % on retrieval sets, 4 of 25 oracle contexts with the gold in them): a generator
   trait that lowers its recall on every strategy alike; it does not bias the paired strategy comparisons, but the
   abstention rate must be reported per generator and set.
6. **One error:** Sabiazinho-4, `S2_budget4000_context_v1`, Q291: the output reached `max_tokens` (4,000) and Maritaca
   rejected the truncated strict-schema reply with HTTP 400 (not retried; at temperature 0 a retry would loop again).
   Recorded in the answer line (`status: error`); scoring should count it as an empty answer. If it recurs in the
   full runs (it is 1 of 1,640 here), raise `max_tokens` for Maritaca to 8,000 in a new registry version.
7. **`context_v1` vs `context_v2`** (S2 4k, same texts): abstention and grounding are similar (Luna abstains more
   with v1: 0.23 vs 0.17); the input is 14 % shorter with v2. The answer-score comparison needs phase 5.
8. **Answer length grows with the budget** (§4.3); report it with every score.
9. **Negative-inference questions in the oracle (user review, 2026-10-23).** Q350 (sogro/sogra as dependents; oracle
   = Lei 9.250 art. 35 only) and Q705 (compensation of tax withheld on financial investments; oracle = IN RFB 1.585
   art. 70, whose inciso II makes it "definitivo, no caso de pessoa física") have their gold fully in the oracle 4k
   context (1 and 2 texts, 736 and 1,342 tokens). The answers that read as "no context" were **abstentions**, not a
   pipeline error (`show-answers` did not print the context; it now does, with `--context` for the full text).
   Terra and Sabiazinho-4 answer both correctly ("Não"); Luna abstains on both; Sabiá-4 abstains on Q350 (it answered
   on S2 4k, whose context also holds the IN 1.500 and RIR/2018 lists) and answers Q705 with a **self-contradicting
   verdict** ("Sim, … é definitivo … não havendo previsão de compensação") — the verdict-flip case the Flash judge
   detects (96 % in the known-answer tests). Rule 6 of `answer_v1` reduced but did not remove abstention on answers
   that must be inferred from an exhaustive list or a definitive regime. Q440's oracle is empty because the question
   has no reference at all (its answer points to questions 229 and 439): correctly skipped.

## 7. Next

**Update (2026-10-23):** the budget, the trimmed grid adopted by the user, the staging and the S2 / S3 hypotheses are
in `docs/20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md`; it supersedes item 3.

1. **User:** read the pilot answers (§6.1) — the Phase 3 gate.
2. Nugget phase 5 `score` on the pilot answers (`assign_v2`, Flash), with the retrieval ↔ answer linkage (first-
   evaluation note §3.1, the `gold` coverage of each context line joins by `context_id` + `question_number`), the
   context-support call (§4.3 there), the value checks (with the fix of §6.3) and the legal-provision score from
   `cited_chunk_ids` and the claim texts; judge agreement on real answers.
3. **Raise the OpenRouter key limit** (§5) before the first full evaluation; decide its grid (headline 7 runs per
   generator recommended; the wrong-context and `context_v1` controls on a subset).
4. DeepSeek V4 from the other machine (`llms.yaml` entries to enable after a probe there).
