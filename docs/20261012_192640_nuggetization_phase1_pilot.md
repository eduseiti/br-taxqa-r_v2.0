# Nuggetization phase 1 pilot — `stratified_30`

**Generated:** 2026-10-12 19:26:40 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** plan v2 §4 phase 1 (`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`), after the
preview (`docs/20261012_160349_nuggetization_preview_v2_execution.md`, which fixed `create_v4` and `assign_v2`).
**Outputs:** `nuggets/pilot/`: `report_pilot.md` (all pilot measurements), `report.md` (nuggets side by side
and per-question detail), `costs.csv` (ledger), one folder per stage (§1).
**Status:** **done.** Every phase 1 item of plan v2 §4 was run. Two items were added: the planted-error
auditor test (§6.3) and a dataset check of `answer_cleaned` (§8). The last two 3.1 Pro items, blocked by a
daily quota (§9.1), were completed on 2026-10-13 through the Batch API (§11).
**Cost: $8.62** at standard prices, **$8.29 billed** (35 calls via Batch at half price), 949 ledgered calls,
1 retry (§10). Expected before the run: ≈ $11; cap $15. No cap was hit.

**Updated 2026-10-12 20:03:05:** §13 records the follow-up work the user approved: the `answer_cleaned` fix
(§8 → done) and Batch API support (§9.1 → done).

**Updated 2026-10-13 03:30:59:** the pending 3.1 Pro items ran through Batch (§11); §6.3, §7, §9.1 and §10 now
include them.

**Gate of phase 1 (plan v2 §4):** "the user picks prompt and call mode from the report". Recommendation:
**`create_v4`, one call** (§4, §5). Both choices and the other decisions for phase 2 are in §12.

---

## 1. What was run

All commands from the repository root (`P=.venv/bin/python; N=scripts/nuggets/nuggets.py;
O="--out nuggets/pilot --sample stratified_30 --budget <cap>"`). The cap is cumulative per ledger; each step
raised it by its expected cost plus a margin (README "Costs and the budget cap").

| # | Step (plan v2 reference) | Command | Output | Calls | Cost |
|---|---|---|---|---:|---:|
| 1 | Sample (same `dataset_sha256` as the preview) | `$N --out nuggets/pilot sample` | `sample.json` | 0 | $0 |
| 2 | Creation, 3 families, `create_v4` (§3.5.2, D8) | `create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max` | `create/<model>/` | 90 | $1.61 |
| 3 | Same-model noise: two more GPT runs (§3.5.2) | `create --models gpt-6.1-sol --replicate 2` (and `3`) | `create/gpt-6.1-sol.r2`, `.r3` | 60 | $0.49 |
| 4 | 2-call mode: importance in a second call (§3.2) | `importance --source gpt-6.1-sol` | `create/gpt-6.1-sol.2call` | 30 | $0.13 |
| 5 | Validation (§3.3, §3.5.1) | `validate` | `create/*/validation.json` | 0 | $0 |
| 6 | Gold self-score, `assign_v2` (§3.5.5) | `selfscore` (Flash on 3 sets; 3.1 Pro, Qwen, GPT on the GPT set) | `selfscore/` | 180 | $1.43 |
| 7 | Cross-set alignment, `gemini-3.8-flash` (§3.5.2) | `align --pairs` P:G, P:Q, G:Q, P:r2, P:r3 | `align/<A>__<B>/` | 150 | $0.48 |
| 8 | Round trip (§3.5.4) | `roundtrip --set gpt-6.1-sol` (check v1; then v2, §6.2) | `roundtrip/` | 90 | $0.47 |
| 9 | Two-auditor review (§3.5.3) | `audit --set gpt-6.1-sol --auditor {gemini-3.1-pro,qwen3.8-max} --others …` | `audit/gpt-6.1-sol/` | 60 | $0.84 |
| 10 | Repair round 1 + re-audit + self-score of the repaired set | `repair --new gpt-6.1-sol.rep1`; `audit`/`selfscore` on `.rep1` | `create/gpt-6.1-sol.rep1`, … | 5 | $0.08 |
| 11 | Known-answer tests, Flash and 3.1 Pro (§5.7) | `known build/judge --set gpt-6.1-sol.rep1` | `known/gpt-6.1-sol.rep1/` | 218 | $2.12 |
| 12 | **Added:** planted errors, auditor sensitivity | `plant --set gpt-6.1-sol.rep1`; `audit` on `.planted` | `create/…planted`, `audit/…planted/` | 30 | $0.32 |
| 13 | Reports | `report`, `pilotreport` | `report.md`, `report_pilot.md` | 0 | $0 |

`stratified_30` = 3 questions per answer-length decile (seed 13), a superset of `preview_10`, the same
sample as the RAG pilot. Two questions point to other questions (`has_pointer`: Q710, Q028).

### 1.1 Code added for the pilot (no API cost unless run)

| File | What |
|---|---|
| `scripts/llm_client/client.py` | `complete_json(..., replicate=N)`: N > 0 enters only the cache key, so an identical request is sampled again (same-model noise). `QuotaExhausted`: a per-day quota (HTTP 429 `…PerDay…`) fails at once instead of backing off |
| `scripts/nuggets/nuggets.py` | `create --replicate`; new commands `importance`, `align`, `roundtrip`, `audit`, `repair`, `plant`, `known build/judge`, `pilotreport`. One user-prompt builder (`assign_user`) for self-score and known-answer tests, so gold tests reuse the self-score cache |
| `scripts/nuggets/nuggetizer/schema.py` | Strict schemas for importance labels, alignments, reconstruction, missing facts and audits |
| `scripts/nuggets/nuggetizer/known_answer.py` | Deterministic builders of the test types G, V, Y, N, D, C, W, E (plan v2 §5.7) and their metrics. Not built in the pilot: V from another period's value in the corpus, and the Flash rewrite for undelimited conditions (phase 4) |
| `scripts/nuggets/nuggetizer/planted.py` | One planted error per question (value, polarity, condition, quantifier, addition, merge, importance), each with the check it should fail |
| `scripts/nuggets/nuggetizer/pilot_report.py` | `report_pilot.md` |
| `scripts/nuggets/nuggetizer/validate.py` | Two false positives fixed (§3.1); the `temporal`, `short_answer` and `procedimento_pgd` flags (answer-based; over all 715: 303, 20 and 101 questions) |
| `scripts/nuggets/nuggetizer/report.py` | Generic title; derived sets (`.rN`, `.2call`, `.repN`, `.planted`) map to their registry model |
| `scripts/nuggets/prompts/` | `importance_v1`, `align_v1`, `roundtrip_write_v1`, `roundtrip_check_v1` → `v2` (§6.2), `audit_v1` (C1–C6 of plan v1 §3.4.1), `repair_v1` (appended to `create_v4`). None quotes a `stratified_30` question (README rule) |

---

## 2. Creation (`create_v4`, one call)

| Set | Nuggets | Per question (min–max) | Vital | Errors | Warnings | Char coverage | $ (30 q) |
|---|---:|---|---:|---:|---:|---:|---:|
| `gpt-6.1-sol` (primary) | 135 | 4.5 (1–23) | 64 % | 0 | 28 | 92 % | $0.27 |
| `gpt-6.1-sol.r2` | 137 | 4.6 (1–23) | 66 % | 0 | 25 | 93 % | $0.25 |
| `gpt-6.1-sol.r3` | 134 | 4.5 (1–23) | 63 % | 0 | 30 | 92 % | $0.24 |
| `gemini-3.1-pro` | 122 | 4.1 (1–23) | 67 % | 0 | 38 | 89 % | $0.95 |
| `qwen3.8-max` | 123 | 4.1 (1–21) | 64 % | 0 | 45 | 90 % | $0.39 |

- **No retries, no schema failures.** GPT/Qwen nugget ratio 1.10, the same as `create_v3` on the preview.
- **Pointer rule (`create_v4`) works as expected** (preview note §13.5): Q710's delegation sentence gives no
  nugget in any family (one `pointer_uncovered` warning per set), no nugget contains "pergunta NNN"
  (`pointer_in_text`: 0), and Q710 is 100 % `support` in every self-score.
- **Remaining warnings** (GPT set): 20 `unit_uncovered`, **all of them worked-example lines of Q330**
  (R10: no nugget for numbers that appear only in an example), 1 `pointer_uncovered` (Q710), 7
  `backreference` (resolved inside the nugget). Gemini and Qwen add `value_without_period` (8 and 15) and
  `span_fuzzy` (6 and 3), as in the preview.

### 2.1 Validator false positives fixed

The first validation gave 9 `enum_item_uncovered` errors (1 GPT, 4 Gemini, 4 Qwen). None was an omission:

1. **Q706** lists "a) 22,5%, em aplicações com prazo de até seis meses;" twice, word for word (long-term and
   short-term tables). `locate()` marked only the first occurrence as covered. It now marks every exact
   occurrence.
2. **Q330**: Qwen's spans for the PGD items leave out a long parenthetical ("(para os servidores que contribuem
   … Linha 03 do Quadro 3 …)"), so they cover 42–46 % of the item, under the 50 % sentence threshold. Plan v2
   §3.5.1 asks whether an item is "covered by some span"; an **enumerated item** now counts as covered from
   30 %. Sentences keep 50 %.

After the fix: 0 errors in every set. The committed preview outputs were not revalidated.

## 3. Same-model noise vs cross-family agreement (§3.5.2)

Alignment by `gemini-3.8-flash` (`align_v1`): for each nugget of A, the B nuggets with the same fact and the
relation (`same`, `a_broader`, `b_broader`, `overlap`, `conflict`, `none`). "Matched" = any relation but
`conflict`/`none`.

| A | B | Matched in B | `same` | `conflict` | Importance agreement (`same`, one-to-one) |
|---|---|---:|---:|---:|---:|
| GPT | GPT r2 | 100 % | 99 % | 0 | 95 % (133) |
| GPT | GPT r3 | 100 % | 94 % | 0 | 94 % (126) |
| GPT | Gemini | 99 % | 81 % | 0 | 84 % (108) |
| GPT | Qwen | 98 % | 75 % | 0 | 96 % (99) |
| Gemini | Qwen | 99 % | 80 % | 0 | 83 % (92) |

**Stability of the primary nuggets** (families with a matching nugget, the primary included):

| | 3/3 | 2/3 | 1/3 |
|---|---:|---:|---:|
| Cross-family, any match | **97 %** | 2 % | 1 % |
| Cross-family, `same` only (strict) | 70 % | 17 % | 13 % |
| Same model (primary + r2 + r3), any match | 100 % | 0 % | 0 % |
| Same model, `same` only | 93 % | | |

By category (any match): `resposta_direta`, `condicao` and `valor_prazo` are 100 % 3/3; every vital nugget is
3/3; `regra` 94 %, `procedimento_pgd` 96 %, `definicao` 3 of 4. Importance is identical in all three families
for **80 %** of the 3/3 nuggets matched one-to-one.

**Reading.** On these 30 questions the three families extract **the same facts**: no `conflict` relation in
any pair, and no fact made by both other families is missing from the GPT set (0 omission candidates from
the alignment, §6). They differ in **how they split** facts (strict 3/3 is 70 %; the rest are `a_broader`,
`b_broader` or `overlap`) and in **importance** (80 % three-way agreement). GPT's own runs differ much less
(93 % strict, 94–95 % importance), so most cross-family disagreement is style and family, not sampling noise.
This supports the plan's choice of three families over repeated GPT runs (D8): replicates would have shown
almost perfect stability and hidden the granularity and importance differences.

**Span overlap as a cheap aligner** (plan v2 §3.5.2: "first by `source_span` overlap, then by an LLM
aligner"). Taking the LLM alignment as reference, a span overlap ≥ 50 % of the shorter span finds 98 % of
the matches (recall) with 90 % precision, over the GPT–Gemini and GPT–Qwen pairs. For phase 3, span overlap
can settle most pairs, and the LLM is needed only for the rest and for the relation type. The aligner is
cheap anyway: $0.0032 per call, ≈ $1.1 per pair of full sets with Batch.

## 4. One call vs two calls (importance in a second call)

The 2-call set keeps the primary set's texts and asks `gpt-6.1-sol` only for vital/okay (`importance_v1`).

- The second call changed **19 of 135** labels (14 %): 12 vital → okay, 7 okay → vital.
- Against the label the **other two families agree on** (75 nuggets matched `same` one-to-one in both): 1-call
  **99 %**, 2-call **88 %**.
- Same-model noise floor of the 1-call label (primary vs replicates): 94 % agreement.

The second call moves labels by more than the same-model noise and **away** from the cross-family
consensus. Caveat: the consensus comes from creation calls with the `create_v4` definition of importance, and
`importance_v1` adds guidance of its own ("Atenção notes are normally okay"), so part of the gap is the
prompt, not the call mode. Either way there is no sign that a dedicated call labels importance better, and
plan v1 §3.2 sets two calls only "if importance labels in the single call are clearly worse".
**Recommendation: one call.** Cost of the second call would have been ≈ $1.5 per full set (Batch).

## 5. Prompt iterations

**None needed.** `create_v4` passed every automatic check on the 30 questions (§2, §6, §7). Plan v2 allowed
iterations on the pilot; the only prompt changed during the pilot is the **round-trip checker** (§6.2), which
is a robustness tool, not the creation prompt.

## 6. Robustness checks (§3.5)

### 6.1 Two-auditor review (`audit_v1`, C1–C6)

Auditors `gemini-3.1-pro` and `qwen3.8-max` on the primary set, with the omission candidates of §3.5.2 and
§3.5.4 (15 candidates in 7 questions, all from the round trip; none from the alignment).

| Check | 3.1 Pro | Qwen3.8-Max | Both (same check) |
|---|---:|---:|---:|
| C1 faithful | 0.0 % | 3.0 % | 0 |
| C2 self-contained | 0.0 % | 1.5 % | 0 |
| C3 one unit | 0.7 % | 0.0 % | 0 |
| C4 importance | 2.2 % | 1.5 % | 0 |
| Any check | 3.0 % | 5.9 % | **2 nuggets (1.5 %), on different checks** |
| C5 omissions / C6 redundant pairs | 0 / 0 | 1 / 0 | 0 / 0 |

The two nuggets flagged by both were Q679_N03 and N04 (3.1 Pro: "Atenção note, should be okay"; Qwen: "adds
'Para fins de apuração do imposto sobre a renda', not the answer's term 'imposto mensal sobre os ganhos
líquidos'"). Plan v2 §3.5.3 sends "items flagged by both auditors" to repair, so **any** check counts, not
only the same one.

**Repair round 1** (`repair_v1` appended to `create_v4`, `gpt-6.1-sol`): 1 question, 2 issues, $0.016.
GPT replaced the terms with the answer's own ("imposto mensal sobre os ganhos líquidos", "realizadas em bolsa")
and **kept `vital`**, which the rules allow (the Atenção note here is part of the answer to the question).
Re-audit: both auditors pass all four Q679 nuggets; self-score 4/4. **After repair, 0 nuggets are flagged by
both auditors** (gate ≤ 2 %). One round was enough; the second round was not needed.

Single-auditor flags kept with their flag (plan v2 §3.5.3), e.g. Q624_N04/N07 "abrangidas pela previsão legal
citada" (Qwen, C2): a real self-containment slip caused by R6 (citations go to `legal_basis`, so the text says
"the cited provision"). Worth a sentence in `create_v5` if it recurs in phase 2.

### 6.2 Round trip (§3.5.4)

`gemini-3.8-flash` rewrote each answer from the nugget texts alone; `qwen3.8-max` listed missing or altered
gold statements.

| Checker prompt | Findings | Real omissions |
|---|---:|---|
| `roundtrip_check_v1` | 15 in 7 questions | 0: 12 are **legal citations** the rewrite lacks (R6 keeps them out of the nugget text, and the writer sees only texts), 1 is the Q710 pointer, 2 are wording |
| `roundtrip_check_v2` (= v1 + "do not list legal references") | **1** | 0: the Q710 pointer sentence, excluded by `create_v4` |

`roundtrip_check_v2` is now the default. The auditors of §6.1 saw the v1 candidates, and they confirmed none
of them, which is the right outcome; their cache keys keep the v1 candidates.

### 6.3 Added: planted errors (auditor sensitivity)

The ≤ 2 % gate means little if the auditors flag little because they are lenient. So, as the known-answer tests
do for the judge, one nugget per question of the repaired set was damaged by rule, each with the check it
should fail (`planted.py`): scope clause added 11, verdict polarity 5, vital → okay 4, two nuggets merged 3,
quantifier 3, condition removed 3, value 1. The type rotation falls back to "addition" when a type does not
apply, so additions are over-represented and value changes rare.

| Auditor | Planted errors flagged | On the expected check | Other nuggets flagged |
|---|---:|---:|---:|
| `qwen3.8-max` | **29/30** | 29/30 | 4/102 (3.9 %) |
| `gemini-3.1-pro` | **29/30** | 29/30 | 0/102 (0.0 %) |
| **both** | 28/30 | | |

3.1 Pro missed only Q703_N03 ("addition"), and that one is a **flaw of the planted test**: the nugget is
already about a non-resident investor, so the appended "inclusive quando o contribuinte for não residente no
Brasil" changes nothing. Not flagging it is correct, so Pro caught 29 of the 29 real errors. A phase 4
version of `planted.py` should skip an addition clause that the nugget already implies.

Qwen missed only one merge (Q705). Its false-flag rate on undamaged nuggets matches its rate on the clean set
(3.7 % after repair), so **its low flag rate on the real nuggets means few errors, not leniency**.

### 6.4 Gold self-score (`assign_v2`)

| Judge | Set | Support rate | Non-`support` |
|---|---|---:|---|
| `gemini-3.8-flash` | GPT / GPT `rep1` | 98.5 % / 98.5 % | Q054_N01, Q622_N02 |
| `gemini-3.8-flash` | Gemini | 98.4 % | the same two facts |
| `gemini-3.8-flash` | Qwen | 100.0 % | — |
| `gemini-3.1-pro` | GPT / GPT `rep1` | 98.5 % / 98.5 % | Q054_N01, Q622_N02 |
| `qwen3.8-max` | GPT | 99.3 % | Q054_N01 |
| `gpt-6.1-sol` | GPT | 99.3 % | Q622_N02 |

Gate ≥ 98 % passed by every judge, by a narrow margin. Both causes are known:
- **Q622_N02**: the gold answer itself is **truncated** in `answer_cleaned` ("… deve ser informada na
  Declaração de"). A dataset problem, §8.
- **Q054_N01**: GPT carried the question's premise into the nugget ("mesmo que não influenciem no saldo de
  imposto…"); the answer does not repeat it. A mild R5 slip ("nothing that is only in the question"). Both
  Gemini and Qwen avoided it.

## 7. Known-answer tests (§5.7, judges `gemini-3.8-flash` and `gemini-3.1-pro`)

141 tests built from the repaired GPT set: G 30, V 6, Y 6, N 5, D 25, C 9, W 30, E 30. Detection = target not
`support`; specificity = non-targets still `support`.

| Type | Flash detection (as `contradicts`) | Flash specificity | Pro detection (as `contradicts`) | Pro specificity |
|---|---:|---:|---:|---:|
| G gold | — | 99 % | — | 99 % |
| V value changed | **100 % (100 %)** [15] | 100 % | 100 % (100 %) [15] | 100 % |
| Y year changed | **100 % (100 %)** [6] | 100 % | 100 % (100 %) [6] | 100 % |
| N verdict flipped | **100 % (100 %)** [5] | 100 % | **60 % (40 %)** [5] | 100 % |
| D span deleted | 88 % [26] | 96 % | 92 % [26] | 91 % |
| C condition removed | 78 % [9] | 100 % | 89 % [9] | 100 % |
| W wrong question | 97 % [135] | — | 96 % [135] | — |
| E empty | 100 % [135] | — | 100 % [135] | — |
| **Pooled** | sens. 97.3 %, spec. 98.5 %, **BA 97.9 %**; `contradicts` precision 90 % | | sens. 97.0 %, spec. 97.2 %, **BA 97.1 %** (all 141 tests); precision 96 % of 24 | |

- **Gate "sensitivity ≥ 0.90 on value, year and verdict corruptions" (§3.5.6): Flash passes (100 % on all
  three). 3.1 Pro fails on verdicts** (3 of 5): it reconciles a leading "Não" with an affirmative body
  ("a resposta afirma explicitamente que é atividade rural, apesar de iniciar com 'Não'").
- **D2 (Pro replaces Flash only if clearly better, > 0.05 BA): not the case.** Flash stays the Gemini judge
  candidate. The year-corruption test also confirms that `assign_v2`'s implicit-period rule did not make the
  judges lenient on a *different* year (6/6 `contradicts`, both judges).
- **Most misses are test-construction artifacts**, checked one by one: a deleted verdict that the rest of the
  answer still implies (503_D, 679_D); a removed condition restated in other words in the same answer
  (259_C: "se configurar prática comercial esporádica"); a removed exception repeated in another item (330_C);
  a "wrong question" that is a near-duplicate of the right one (336_W ← Q335, 507_W ← Q506); content of the
  deleted span repeated in other items (330_D). Non-target "errors" in D are mostly nuggets that relied on
  the deleted context (073_D, 028_D, 624_D). **One real judge error**, made by both judges: 622_W, a rule
  about traveler's cheques credited from an answer about foreign cash (Q621).
- **Fixes for phase 4:** W must not take a near-duplicate neighbour (another chapter, or a lexical-overlap
  cap); D and C must check that the removed fact is not restated elsewhere (e.g. self-score the target
  nugget against the corrupted answer with a cheap judge and drop tests it still supports, or report them
  apart); V should add the corpus "other period" variant.
- **3.1 Pro output glitch:** two Pro justifications came back with garbled characters in place of accented
  letters ("porxytytm nxytyto menciona…"). The labels were valid. Recorded because 3.1 Pro is a preview
  model (plan v2 §9 item 3).

## 8. Dataset finding: `answer_cleaned` loses content in ≈ 14 answers

Found through Q622's self-score. `answer_cleaned` (inherited from v1.0/v1.1; plan v2 W2 "gold answers checked
unchanged") is the nugget source. Comparing it with the raw `answer` over all 715 questions:

- 613 differ, almost always because the citation block and the "Consulte a pergunta NNN" pointers are
  removed, as intended.
- **≈ 14 lose real content**, because the cleaning removes the **whole line or parenthetical** around a
  pointer or citation:

| Q | Lost from `answer_cleaned` |
|---|---|
| 622 | the end of the last sentence: "… na Declaração de **Bens e Direitos da mesma forma prevista para a moeda estrangeira mantida em espécie.**" |
| 625 | "… poderão ter seus valores **atualizados para o valor de mercado em 31 de dezembro de 2023.**" |
| 129 | items **IV** and **VI** ("as despesas escrituradas em livro-caixa, quando permitidas"), leaving ");" |
| 186 | "sujeitando-se à incidência **do Imposto sobre a Renda na Fonte e na DAA.**" |
| 326 | "… base de cálculo do imposto **devido na declaração**", and two bullets cut to ");" |
| 122 | "(ou, alternativamente, informar a chave PIX do titular da declaração)" |
| 578 | "(falta de pagamento do preço ajustado, no caso)" |
| 035, 037, 040, 066 | "… ou do “Meu Imposto de Renda”" (an access channel) |
| 653 | "… líquidos em renda variável" |
| 442 | "(especificado no final da pergunta)", 8 times |
| 666 | a "No aspecto fiscal, …" parenthetical |

Only Q622 is in `stratified_30`. The list comes from a diff script; it may miss a few cases or include a
borderline one. **Decision for the user before phase 2** (§12): fix `answer_cleaned` for these answers in
the v2.0 build (an override file, like `reference_overrides.json`), or keep v1's text and flag them. The
gold answers are also what the RAG answers are compared with, so the fix affects more than the nuggets.

## 9. Operational findings

### 9.1 Gemini 3.1 Pro: 250 requests per model per day

The known-answer run with 3.1 Pro stopped on HTTP 429 `generate_requests_per_model_per_day, limit: 250,
model: gemini-3.1-pro` (200 Pro calls in this pilot plus ≈ 50 in the preview runs earlier the same day). The
client used to back off 2.5 min per call on any 429. It now raises `QuotaExhausted` at once on a per-day
quota. `known judge` writes partial results; rerunning the same command completes them from the cache.

**Consequence for phase 2:** at 250 requests per day, 3.1 Pro cannot run synchronously over 715 questions
(second set: 715; auditor 1: ≈ 750; known-answer subset: ≈ 300). Phase 2 needs the **Batch API** (plan v2
§6.3; implemented since, §13.2; batch quotas are separate) or a higher quota tier. Flash, GPT and Qwen
raised no quota errors.

**The reset is at 00:00 UTC, not midnight Pacific.** The 429 at 03:25 UTC on 2026-10-13 said "retry in
20h34m", i.e. at 00:00 UTC. The probe (one request every 15 min since 19:24 UTC) was refused until 03:25,
when a single request went through and the next ones were refused again. We made no other Pro calls in
between, so the quota did not visibly reset at 00:00 UTC on 2026-10-13. The window is unclear; do not
plan synchronous Pro runs around it, use Batch.

### 9.2 Other

- No schema failures and 1 retry in 914 calls. Mean latency per call over all roles: GPT 12 s, Flash 6 s,
  3.1 Pro 14 s, Qwen 24 s.
- Cache: 20 MB for the pilot (`nuggets/pilot/cache/`, gitignored). Plan: push it to the private HF dataset repo
  at the end of the phase (resolution note §3.2). **Not done**: it needs your go-ahead (outward-facing).

## 10. Costs

All at standard prices, from `nuggets/pilot/costs.csv` (`report_pilot.md` §1 has every role and model).

| Provider | Roles | Calls | Cost |
|---|---|---:|---:|
| OpenAI `gpt-6.1-sol` | creation ×3, importance, repair, self-score | 151 | $1.04 |
| Gemini `gemini-3.1-pro` | creation, auditor (+ planted), self-score, known-answer | 235 | $4.62 standard, $4.29 billed |
| Gemini `gemini-3.8-flash` | alignment, round-trip writer, self-score, known-answer | 382 | $1.31 |
| Alibaba `qwen3.8-max` | creation, auditor (+ planted), round-trip checker, self-score | 181 | $1.65 |
| **Total** | | **949** | **$8.62 standard, $8.29 billed** |

The plan's pilot items (§6.4: OpenAI ≈ $5–7, Gemini ≈ $2, Alibaba < $1) cost less on OpenAI (one call per
question at ≈ $0.009, one replicate pair instead of prompt iterations) and more on Gemini, because the pilot
also ran the 3.1 Pro auditor and the full known-answer set with 3.1 Pro.

The 35 Pro calls that finished the pilot went through Batch: $0.65 at standard prices, **$0.32 billed**
(estimated at submission: $0.30). The ≈ $1.2 expected for them had overestimated the output length.

**Running total of the nuggetization work (billed):** preview $2.63 + pilot $8.29 = **$10.92**, plus the batch
live test of §13.3 ($0.035).

### 10.1 Updated estimate, phases 1–4 (from the pilot's per-call costs, `report_pilot.md` §9)

Extrapolated to 715 questions on question + answer length; Batch prices where the provider has them.

| Item | Pilot-based | Preview-based (v3) | Plan v2 §6.4 |
|---|---:|---:|---:|
| Creation `gpt-6.1-sol`, Batch | $2.8 | $3.75 | ≈ $9 |
| Creation `gemini-3.1-pro`, Batch | $10.9 | $11.23 | ≈ $12 |
| Creation `qwen3.8-max` | $8.9 | $10.03 | ≈ $11–14 |
| Auditor 1, 3.1 Pro, Batch (+10 % re-audit) | $6.5 | — | ≈ $16 |
| Auditor 2, Qwen3.8-Max (+10 %) | $8.3 | — | ≈ $15 |
| Alignment, 3 cross-family pairs, Flash Batch | $3.3 (less with spans first) | — | ⎫ |
| Round trip: Flash writer (Batch) + Qwen checker | $1.1 + $4.3 | — | ⎬ ≈ $5 + $8–11 |
| Repair calls, GPT (≈ 3 % of questions) | < $0.5 | — | ≈ $3 |
| Gold self-score: Flash on 3 sets + 3.1 Pro on the primary, Batch | $3.5 + $4.3 | — | (in §5.7) |
| Known-answer: ≈ 3,000 Flash + 300 Pro calls, Batch | $5.2 + $1.7 | — | ≈ $18 |
| HF endpoint (open Qwen judge, not measured) | $10–25 | $10–25 | ≈ $10–25 |
| **Total, phases 1–4** | **≈ $71–86** | ≈ $77–92 | ≈ $115–140 |

With the ±25 % margin of the preview note §11 on the measured part (≈ $61): **≈ $56–102**. Scoring
(phase 5), per answer run and nugget set: Flash Batch ≈ $1.2–1.3 at gold-answer length, unchanged from
the preview estimate (× 1.5 until real answer lengths are known).

## 11. Pending items of this pilot (done 2026-10-13 via Batch)

`after_reset.sh` (scratchpad) waited for the Pro quota. Its probe got through at 03:25 UTC, but the real
calls were refused again at once (§9.1). The two items were then sent as two Batch jobs (30 + 5 requests: 30
planted audits and 5 known-answer tests); both succeeded within 5 minutes, 35/35 results, 0 failed:

```bash
O="--out nuggets/pilot --sample stratified_30 --budget 13.00"
$P $N $O --batch known judge --set gpt-6.1-sol.rep1 --judge gemini-3.1-pro      # 5 missing tests
$P $N $O --batch audit --set gpt-6.1-sol.rep1.planted --auditor gemini-3.1-pro  # Pro half of §6.3
$P $N --out nuggets/pilot batch wait --every 60
# the same two commands without --batch (outputs from the cache), then:
$P $N $O pilotreport
```

Results are in §6.3 (Pro 29/30 planted errors) and §7 (Pro BA 97.1 % on all 141 tests). None of the §7
conclusions changes: Pro still flips only 60 % of verdicts, and Flash stays the judge candidate.

## 12. Decisions for the user (phase 1 gate and before phase 2)

**Status 2026-10-13:** items 1–3 closed as recommended (with (a) and (b) of item 3); 4–5 done; the open
items are tracked in `docs/20261013_103834_nuggetization_open_decisions.md`.

1. **Prompt: `create_v4`** (recommended; §2, §5–§7). No iteration was needed.
2. **Call mode: one call** (recommended; §4).
3. **Gate thresholds (plan v2 §3.5.6, open question 6):** all four passed on the pilot (0 hard errors; self-score
   ≥ 98 % with Flash and 3.1 Pro; 0 % flagged by both auditors after repair; Flash sensitivity 100 % on V/Y/N).
   Suggested change: count a nugget as "flagged by both" when both auditors flag it **on any check** (as done
   here), and add the planted-error test as a condition on the auditors (e.g. each catches ≥ 80 %), so the
   ≤ 2 % gate is meaningful.
4. **`answer_cleaned` content loss (§8):** fix the ≈ 14 answers in the v2.0 build before phase 2
   (recommended; it changes gold answers that are also the RAG reference), or keep them and flag them.
   **Done (§13.1).**
5. **Gemini 3.1 Pro quota (§9.1):** implement Batch submit/collect before phase 2 (README "still missing"
   item 5; recommended), or raise the quota tier. **Done (§13.2, §13.3); used for §11.**
6. **Phase 4 builder fixes (§7):** W without near-duplicate neighbours; D/C dropping tests whose fact is
   restated; the corpus "other period" V.
7. **Cache backup** to the private HF dataset repo (§9.2): say when, and I will push it.

Not decided here, still open from the plan: the optional "expanded" score on `has_pointer` questions (preview
note §13.5 item 4), effort escalation for long answers (no sign of need: the longest answers, Q624 and Q330,
had no omissions), and the open-weight Qwen judge (D4).

---

## 13. Follow-up (2026-10-12 20:03): gold-answer fix and Batch API

The user asked for both items of §12 (4 and 5) and for explanations of items 1–3. The gate decisions 1–3 and
6–7 are still open.

### 13.1 `answer_cleaned` fix (§8)

**Cause** (found by an inventory of every deletion the v1 cleaning made, all 715 answers): the cleaning is
line-based. It drops a line from a leading "(" up to the next "." (so "(Lei nº 10.522, …" leaves a lone
"."), and on a line with "consulte … pergunta N" it drops everything from the line start to the pointer.
A diff heuristic sorted its 879 deletions into citation blocks (596), deletions containing a pointer
(253, mostly a citation block followed by "Consulte …", or a pointer-only sentence), acronyms in
parentheses (11) and others (19). Each non-citation deletion was then read by hand. Intended removals stay
removed, including pointer-only sentences, consistent with `create_v4`. The rest lost text or left
stray punctuation.

**Fix** (`scripts/dataset/answer_overrides.json`, applied by `build_v2_dataset.py`):
- 25 answers restored by **37 hand-verified find/replace edits**. Each edit is pinned to the SHA-256 of
  the v1.1 text and to an exact occurrence count, so a changed input makes the build fail.
  - Lost text: 035, 037, 040, 066 (the "Meu Imposto de Renda" channel / item c / item 3.2); 122 (PIX);
    129 (items IV and VI, and an empty "Atenção:"); 168; 186; 326; 442 (8 × "(especificado no final da
    pergunta)"); 578; 622 (truncation); 625 (date); 653.
  - A half-removed pointer parenthetical, now removed whole: 171.
  - Acronyms and parentheticals at a line start: 135 "(Holanda)", 150 "(UPU)" ×2, 177 "(Fapi)", 201,
    319, 327, 402, 483 "(DAA)", 419 "(RFB)", 460 "(e-CAC)".
  - Two items found while writing the edits, in addition to §8's list: 168 ("reciprocidade de
    tratamento") and 171.
- A general rule: a line made only of punctuation (".", ");", ":") is appended to the previous line when
  that line has no final punctuation (079, 335: "… se da união resultou filho" + "."), and dropped
  otherwise. It touched 22 more answers.
- **Result:** 47 answers differ from v1.1, and only in `answer_cleaned`. `references.jsonl` and
  `documents.jsonl` are byte-identical after the rebuild, and so is the rest of `build_report.json`,
  which now lists the edited questions (`answer_overrides`). `scripts/dataset/tests`: 36 passed.
  `dataset/README.md` ("Changes from v1.1") and `scripts/dataset/README.md` describe the fix.
- **Effect on the pilot:** 2 of the 30 pilot questions changed. Q622 is now complete; Q676 lost a
  stray "." line. The pilot outputs were made from the old text and are not regenerated. Q622_N02's two
  `partial_support` labels (§6.4) came from the truncation. Phase 2 starts from the new text (`sample`
  copies `dataset/questions.jsonl` and records its SHA-256).

### 13.2 Batch API (§9.1)

`scripts/llm_client/batch.py` and a global `--batch` flag on `nuggets.py`: any command can queue its
uncached OpenAI/Gemini requests as Batch jobs, then `batch wait` caches the results, and the same command
rerun without `--batch` writes its outputs from the cache. Usage and rules: `scripts/nuggets/README.md`
"Batch mode".

- **Same requests, same cache:** request bodies and response parsing are now shared functions used by
  both paths. Checked: the new parsers reproduce the cached text of all 715 OpenAI/Gemini responses in
  `nuggets/pilot/cache/`, and a synchronous rerun of a pilot command is served entirely from the cache.
- **Budget:** checked at submission (ledger + estimated job cost ≤ `--budget`), because a submitted job is
  billed whole. Ledger rows of batch results are tagged `batch:`; `usd_standard` keeps the synchronous
  price, and the cap and `report_pilot.md` (new "Billed" column) count them at half.
- **Daily quota:** a command that hits one now finishes the other items and stops with a clear message.
  Completed calls are cached, so a rerun after the reset resumes. This is why no "partial outputs"
  mode was added for `create`/`audit`: the cache already makes them resumable, and partial nugget sets
  would break the later steps.
- **Live test:** §13.3 (passed).

### 13.3 Batch live test (2026-10-12 21:55)

Scratch output folder, sample `tiny_2` (Q023, Q503), `create` with GPT-6.1 Sol and Gemini 3.8 Flash, `--budget 0.50`.

| Step | Result |
|---|---|
| Synchronous `create` (replicate 0) | 4 calls OK, outputs written |
| `--batch create --replicate 1` | 2 jobs submitted at 20:02 (1 OpenAI, 1 Gemini, 2 requests each); no outputs written; resume message printed |
| `batch wait --every 60` | Gemini collected after **≈3 min**; OpenAI `completed` in **≈1 h 53 min**; 2/2 cached each, 0 failed, 0 without a result |
| Rerun without `--batch` | all 4 items `[cache]`; `create/<model>.r1/` written; token counts equal the batch rows |
| Ledger | 4 `batch:create:…:r1` rows, `latency_s` 0.0; cost counted at half |

- Both result paths work: the OpenAI output file and the Gemini `responsesFile`.
- Test cost: **$0.035** ($0.023 sync + $0.023 standard / 2 for batch).
- OpenAI's turnaround is far slower than Gemini's on this tiny job (both within the 24 h window). Phase 2
  should plan for hours, not minutes, and keep using `batch wait`.
- Batch quotas are separate from the synchronous daily cap (§9.1), so the 3.1 Pro runs of phase 2 can go through
  `--batch` without waiting for the per-day reset.
