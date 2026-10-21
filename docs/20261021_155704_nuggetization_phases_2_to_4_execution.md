# Nuggetization phases 2–4 — execution on the 715 questions

**Generated:** 2026-10-21 15:57:04 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** plan v2 §4 phases 2, 3 and 4 (`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`),
with the decisions of `docs/20261013_103834_nuggetization_open_decisions.md` (`create_v4`, one call, gate
thresholds, OpenRouter). Starting point: `docs/20261021_113527_nuggetization_status_after_pilot_and_next_steps.md`.
**Left out, as asked:** the open-weight Qwen judge (plan v2 D4).
**Outputs:** `nuggets/full/` (all sets, audits, alignments, round trip, self-scores, known-answer tests;
`report_full.md` has every table; `costs.csv` is the ledger; `logs/` holds the command logs and scripts),
`nuggets/gold/v0-auto/` (**the frozen nugget set**), `nuggets/parity_openrouter/` (pilot vs OpenRouter, §3).
**Route:** OpenRouter for every call (flex endpoints for GPT and Gemini, Alibaba for Qwen); every reply came
from the pinned provider (`provider_served`: OpenAI, Google AI Studio, Alibaba). No 429 and no quota error.

## 1. Cost and time

### 1.1 Totals

| | Calls | Billed | List price (direct API, synchronous) | Wall-clock |
|---|---:|---:|---:|---|
| **Nugget generation (phase 2 creation, 3 families × 715)** | 2,148 | **$23.06** | $36.70 | **58 min** (11:38–12:36 UTC) |
| **Phases 2–4, everything** (`nuggets/full/costs.csv`) | 12,564 | **$65.34** | $103.67 | **4 h 15 min** (11:38–15:53 UTC) |
| Pilot vs OpenRouter comparison (`nuggets/parity_openrouter/`) | 90 | $0.15 | | 3 min |

- Creation per family, 8 concurrent calls per model: `gpt-6.1-sol` 23 min ($3.20), `gemini-3.1-pro` 23 min
  ($10.54), `qwen3.8-max` 58 min ($9.32). Qwen set the wall-clock time; it is also the slowest per call (≈ 20–45 s).
- During the 4 h 15 min of phases 2–4, some API call was in flight for 4 h 10 min: the checks between steps
  overlapped with steps already running (e.g. the round trip started while Qwen was still creating). The summed
  latency of all calls is 49.5 h (12.9 h for creation), the time a single sequential worker would have needed.
- OpenRouter key: usage $65.61 = this run + the comparison + the 2026-10-21 probe ($0.125); **$14.39 left** of
  the $80 limit (expires 2026-11-20).
- **Running total of the nuggetization (billed):** preview $2.63 + pilot $8.29 + batch test $0.035 + OpenRouter
  probe $0.125 + phases 2–4 $65.34 + comparison $0.15 = **$76.57**.
- Estimate before the run (status note §3; pilot per-call costs × 715 at flex prices): ≈ $61 for the same steps
  (≈ $70 with the full 3.1 Pro self-score, not run, §6). Actual $65.34 (+7 %). The overshoot: the Qwen audit
  (+$1.2), the two re-audit rounds ($2.6, not in the estimate) and the planted test (+$0.4).

### 1.2 Per step (ledger)

| Phase | Step | Calls | Retries | Billed | Wall-clock |
|---|---|---:|---:|---:|---:|
| 2 | Creation, 3 families (`create_v4`) | 2,148 | 3 | $23.06 | 58 min |
| 2 | Repair of hard validator errors, each family by itself (§2.2) | 21 | 0 | $0.80 | 7 min |
| 3 | Round trip (Flash writer, Qwen checker), raw and `rep0` primary | 1,432 | 0 | $5.74 | 40 min |
| 3 | Cross-family alignment, 3 pairs (Flash) | 2,118 | 0 | $3.66 | 14 min |
| 3 | Gold self-score, Flash (4 sets) | 2,138 | 0 | $3.82 | 120 min (in parallel with others) |
| 3 | Two auditors on the primary set (3.1 Pro, Qwen) | 1,446 | 14 | $15.45 | 75 min |
| 3 | Repair round 1 + re-audit | 42 + 85 | 2 | $2.42 | 24 min |
| 3 | Repair round 2 + re-audit | 10 + 17 | 2 | $0.73 | 19 min |
| 3 | Planted-error auditor test (`stratified_70`) | 141 | 1 | $1.76 | 9 min |
| 4 | Known-answer tests: Flash on all, 3.1 Pro on `stratified_70` | 2,966 | 3 | $7.89 | 50 min |

Retries are reply rejections (truncated or invalid JSON) retried by the client; the 14 audit retries include
three truncated Qwen replies on Q442 (§2.4).

## 2. What was run

All commands are in `nuggets/full/logs/*.sh` and in §2.6; global options `--out nuggets/full --sample all
--budget <cap> --workers 8`. The cap is cumulative per ledger; it was raised step by step (32 → 75), never hit.

### 2.1 Samples (`sample --keep-from nuggets/pilot/sample.json`)

The 47 answer fixes of the v2.0 build (pilot note §13.1) changed some answer lengths, so recomputing the deciles
today gives other `preview_10` / `stratified_30` lists. Both are kept **verbatim from the pilot**
(`stratified_30` is also the RAG pilot sample). New lists: `all` (715) and `stratified_70` = `stratified_30` + 4
more per current decile (the 10 % subset of plan v2 §5.7). Questions 001 and 003, the prompt's worked
examples, are in `all`: they need nuggets for scoring, and the validator flags them (`prompt_example`).

### 2.2 Phase 2: creation and validation

| Set | Nuggets | Per question | Vital | Hard errors: raw → after validator repair (`rep0`) |
|---|---:|---|---:|---|
| `gpt-6.1-sol` (primary) | 3,185 | 4.5 (1–115) | 72 % | 5 → 3 |
| `gemini-3.1-pro` | 2,888 | 4.0 (1–33) | 77 % | 60 → 3 |
| `qwen3.8-max` | 3,001 | 4.2 (1–80) | 72 % | 42 → 21 (18 in Q442) |

**Validator fixes** (false positives found in the first full validation; with them, the raw sets' hard errors
went from 18 / 76 / 57 to the 5 / 60 / 42 of the table):
- **verdict check:** a verdict is "Sim"/"Não" followed by punctuation (174 answers). "Não havendo acordo…" (Q131) and
  "Não se caracterizam…" (Q255) open a sentence and are not verdicts; all three families were flagged on them;
- **R10:** the lettered items of the worked numerical examples Q617 and Q620 give no nugget (plan v2 R10):
  `enum_item_worked_example`, a warning;
- **pointer answers:** Q316 only delegates to Q249 plus an Atenção note, so no vital nugget is expected:
  `no_vital_pointer`, a warning.

The remaining hard errors (omitted enumerated items, one duplicate, two unmatched spans) went back to **each
set's own creator** in one repair call per question (`repair` without auditors, `repair_v1`): the plan's rule
that hard validator errors go to repair, applied before the auditors so the three sets enter phase 3 clean.
The `.rep0` sets are the phase 2 output.

**Phase 2 gate (0 hard errors): not fully met.** Left in the primary set: three enumerated items in Q149, Q326
and Q442 that GPT kept uncovered through all three repair calls. Two are headings ("II – Fundos Controlados
pelos Conselhos … da Pessoa Idosa;", whose content the next nuggets carry) or sub-items restated by another
nugget, so they are validator false positives or borderline. Q149 item 2 ("Funcionário residente …") is
partly covered by N04. They are listed here and in `create/gpt-6.1-sol.rep2/validation.json`. The alternative
sets keep 3 (Gemini) and 21 (Qwen) errors; they are used only for agreement.

### 2.3 Pilot vs OpenRouter (open-decisions note decision 6, OpenRouter plan §7 decision 3)

The 30 `stratified_30` questions of the phase 2 sets against the pilot's direct-route sets, aligned by Flash
(`nuggets/parity_openrouter/`):

| Family | Matched | `same` | Importance agreement | Conflicts | Reasoning tokens per call (direct → OpenRouter) |
|---|---:|---:|---:|---:|---|
| `gpt-6.1-sol` | 100 % | 94 % | 97 % | 0 | 98 → 93 |
| `gemini-3.1-pro` | 99 % | 82 % | 90 % | 0 | 1,316 → 1,244 |
| `qwen3.8-max` | 100 % | 86 % | 90 % | 0 | 1,052 → 1,197 |

GPT is within the pilot's same-model noise (replicates: 94–99 % `same`, 94–95 % importance). Gemini and Qwen
have no same-model reference, but they are above the cross-family level of the pilot (75–81 % `same`). Nugget
counts per set: 135/133, 122/118, 123/123. **The route does not change the nuggets beyond sampling noise.**

### 2.4 Phase 3: automatic robustness

**Cross-family agreement** (`rep0` sets; report §3): 95 % of the primary nuggets are matched by both other
families (3/3), 4 % by one; strict (`same` only) 68 %. Vital nuggets 97 % 3/3, okay 90 %; `resposta_direta` 100 %.
Importance identical in all three families for 81 % of the 3/3 nuggets matched one to one. One `conflict`
relation in each of two pairs.

**Round trip** (Flash rewrites from the nugget texts, Qwen checks with `roundtrip_check_v2`): 69 findings in 49
questions (23 missing, 46 altered), passed to the auditors as omission candidates (71 candidates in total with
the alignment's).

**Two auditors** (`audit_v1`, C1–C6) and **two repair rounds** (the plan's maximum):

| Set | 3.1 Pro flags | Qwen flags | Flagged by both (any check) | Questions repaired next |
|---|---:|---:|---:|---|
| `gpt-6.1-sol.rep0` | 2.8 % | 4.1 % | **41 (1.3 %, CI 0.7–2.1 %)** | 44 (65 agreed issues) |
| `gpt-6.1-sol.rep1` | 1.9 % | 3.0 % | 8 (0.3 %) | 13 (16 issues) |
| `gpt-6.1-sol.rep2` | 1.7 % | 2.6 % | **1 (0.03 %)** | — |

The 1.3 % before repair is the model-based error estimate of plan v2 §3.5.3 ("flagged by two independent LLM
auditors"). Round 1 also created four new uncovered items (merging redundant nuggets removed spans); round 2
fixed them. The one nugget still flagged by both, Q356_N02, is the R6 citation slip seen in the pilot ("a
solução de consulta indicada na fundamentação legal" instead of the Solução de Consulta Cosit nº 354): 3.1 Pro
flags C1, Qwen C2.

Qwen's audit of Q442 (115 nuggets) was truncated at 16k output tokens three times; `audit` now retries a
truncated reply once with twice the output limit (`longer()`), which enters only that call's cache key.

**Planted errors** (`plant` on `stratified_70`, one damaged nugget per question; addition 20, importance 13,
polarity 10, condition 10, merge 7, quantifier 7, value 3; the addition is no longer planted on a nugget that
already implies it):

| Auditor | Planted errors flagged | Other nuggets flagged |
|---|---:|---:|
| `gemini-3.1-pro` | **67/70 (96 %)** | 3.0 % |
| `qwen3.8-max` | **65/70 (93 %)** | 1.8 % |

Missed: two removed quantifiers ("apenas", "somente") by both, three vital → okay relabels, one removed condition.

**Gold self-score** (`assign_v2`): Flash 99.9 % `support` on the final primary set (4 `partial_support` of
3,175), 99.8 % / 99.6 % on the Gemini / Qwen sets. 3.1 Pro: 100 % on the 348 nuggets of `stratified_70` (the
G tests of §2.5 use the self-score prompt, so they are its self-score on that subset).

**Freeze** (`freeze`, plan v2 §3.5.3 and D10) → `nuggets/gold/v0-auto/`: 3,175 nuggets, 2,262 vital, **0
dropped** (none flagged on C1 by both auditors). 134 nuggets carry one auditor's flag and 1 carries both, in the
new `audit` field; `stability` (3/3: 2,925, 2/3: 112, 1/3: 25) is filled where the nugget is unchanged since the
aligned `rep0` set (null for 113 nuggets of repaired questions).

### 2.5 Phase 4: known-answer tests (judge selection)

3,354 tests built from the frozen set (G 715, V 191, VP 27, Y 142, N 189, D 458, C 202, W 715, E 715). Flash judged
all of them; 3.1 Pro the 348 tests of `stratified_70`.

**Builder fixes of the pilot's test artifacts** (pilot note §7, open-decisions note §2.1), all by content-word
bigram containment (`restated`):
- **W:** the nearest question whose answer restates none of the nuggets (the pilot's near-duplicates are now
  skipped: Q335 for Q336, Q506 for Q507, Q621 for Q622);
- **D / C:** the first deletion (or condition) whose content is not restated in the rest of the answer; D no
  longer deletes the verdict nugget (N tests it);
- **VP (new):** an R$ amount replaced by a real amount from the corpus (S1 article chunks), 0.75–1.34× of it,
  at least 2 % away, written within 300 characters of it: often the same item's value in another year's table
  (2.275,08 → 2.156,52, 3.561,50 → 3.375,83). Found for 25 of the 182 distinct amounts of the answers;
- **N:** a verdict nugget that restates the body ("Sim. O contribuinte deve apresentar somente uma DAA…") is
  ambiguous, since the unchanged body still supports it (§2.5.1).

| Type | Flash detection (as `contradicts`) | Flash specificity | 3.1 Pro (`stratified_70`) detection | Pro specificity |
|---|---:|---:|---:|---:|
| G gold | — | 100 % | — | 100 % |
| V value ± step | **97 % (96 %)** [261] | 100 % | 100 % [27] | 99 % |
| VP corpus value | **100 % (100 %)** [34] | 100 % | 100 % [4] | 100 % |
| Y year | **99 % (98 %)** [145] | 98 % | 100 % [15] | 100 % |
| N verdict flip | **96 % (94 %)** [113] | 95 % | **67 %** [9] | 100 % |
| D span deleted | 97 % [528] | 99 % | 94 % [50] | 98 % |
| C condition removed | 89 % [202] | 99 % | 88 % [25] | 99 % |
| W wrong question | 99 % [3,175] | — | 99 % [348] | — |
| E empty | 100 % [3,175] | — | 100 % [348] | — |
| **Pooled** | sens. 98.9 %, spec. 99.1 %, **BA 99.0 %** | | sens. 98.5 %, spec. 99.4 %, **BA 99.0 %** | |

`contradicts` precision: Flash 75 % of 714 labels, Pro 84 % of 62 (the metric counts `contradicts` on ambiguous
nuggets as false; most are the N tests' restated verdicts).

**Judge (D2): Gemini 3.8 Flash stays the primary judge.** Same balanced accuracy as 3.1 Pro (Pro would need
> 0.05 more), and 3.1 Pro again fails on verdict flips (6 of 9; the pilot: 3 of 5), reconciling a flipped
"Não" with an affirmative body.

#### 2.5.1 The N test before the ambiguity rule

With every verdict nugget as a target, Flash detected **88.9 %** of 189 flips, below the 0.90 gate. All 21
misses were read: each verdict nugget restates the answer's body (e.g. 009 "O contribuinte deve apresentar
somente uma Declaração…", 044 "O direito de retificar… extingue-se em cinco anos"), which the flip leaves
intact, so `support` is defensible. This is the artifact the pilot found for D (a deleted verdict implied by the
rest of the answer). With the rule, 76 nuggets become ambiguous and 113 stay targets; no API call changed
(the labels are the same, from the cache). Both figures belong in the paper.

### 2.6 Commands

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py; O="--out nuggets/full --sample all --workers 8 --budget <cap>"
$P $N --out nuggets/full sample --keep-from nuggets/pilot/sample.json
$P $N $O create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max && $P $N $O validate
for m in gpt-6.1-sol gemini-3.1-pro qwen3.8-max; do $P $N $O repair --set $m --model $m --new $m.rep0; done
$P $N $O validate
nuggets/full/logs/phase3a.sh      # align (3 pairs of .rep0), roundtrip on gpt-6.1-sol.rep0, Flash selfscore
nuggets/full/logs/phase3b.sh      # audit by gemini-3.1-pro and qwen3.8-max, --candidates-from gpt-6.1-sol.rep0
$P $N $O repair --set gpt-6.1-sol.rep0 --auditors gemini-3.1-pro,qwen3.8-max --new gpt-6.1-sol.rep1
#   validate; audit .rep1 (both auditors, same --others/--candidates-from); then the same for .rep2
$P $N $O freeze --set gpt-6.1-sol.rep2 --aligned gpt-6.1-sol.rep0 --others gemini-3.1-pro.rep0,qwen3.8-max.rep0
nuggets/full/logs/phase34.sh      # plant + audit on stratified_70; known build; known judge Flash / 3.1 Pro
$P $N --out nuggets/full --sample all pilotreport --primary gpt-6.1-sol.rep0 \
     --others gemini-3.1-pro.rep0,qwen3.8-max.rep0                     # → report_full.md
```

## 3. Gate summary (open-decisions note §1.1)

| Gate | Threshold | Result | |
|---|---|---|---|
| Hard validation errors | 0 | primary: 3 enumerated items in 3 questions after 2 repair rounds (§2.2) | **not met; listed** |
| Gold self-score | ≥ 98 % | Flash 99.9 % (all); 3.1 Pro 100 % (`stratified_70` only) | met (Pro on the subset) |
| Flagged by both auditors after repair (any check) | ≤ 2 % | 0.03 % (1 nugget); 1.3 % before repair | met |
| Judge sensitivity, value / year / verdict | ≥ 0.90 | Flash V 97 %, VP 100 %, Y 99 %, N 96 % (89 % without the N rule) | met |
| Each auditor catches planted errors | ≥ 80 % | 3.1 Pro 96 %, Qwen 93 % | met |

## 4. Code changes (no API cost by themselves)

| File | Change |
|---|---|
| `scripts/nuggets/nuggets.py` | `sample --keep-from`, `all` and `stratified_70` lists; `repair` without `--auditors` (validator errors only); `freeze`; `audit` retries a truncated reply with `longer()`; `known build --corpus` (VP), `known judge --name` and only the `--sample` questions' tests; `pilotreport --primary/--others` → `report_full.md`; `jl_read` splits on `\n` only (a 3.1 Pro justification held U+2028, which `splitlines()` splits on) |
| `nuggetizer/validate.py` | verdict = Sim/Não + punctuation; `enum_item_worked_example` (R10: Q617, Q620); `no_vital_pointer`; `prompt_example` flag |
| `nuggetizer/known_answer.py` | `restated()`; W near-duplicate skip; D/C restatement skip, D not on the verdict; N ambiguity rule; `CorpusValues` and the VP type |
| `nuggetizer/planted.py` | no "addition" on a nugget that already implies it |
| `nuggetizer/pilot_report.py`, `report.py` | full-run variant of the report (title, no 715-row table); VP row; reader fix |

## 5. Points for the paper

- Methods: route (OpenRouter, pinned providers, flex), the parity result (§2.3), validator-only repair before
  the audit (§2.2), two repair rounds, the freeze rules, and the builder fixes (§2.5) with both N figures.
- The model-based error estimate: 1.3 % of nuggets flagged by two independent LLM auditors before repair
  (CI 0.7–2.1 %), 0.03 % after.
- Synthetic corruptions remain cleaner than real generator errors (plan v2 §5.7); the real-run part of phase 4
  (judge agreement on RAG answers) waits for the RAG Phase 3 pilot.

## 6. Open items (for the user)

1. **3.1 Pro self-score on all 715 questions** (≈ $8.8 at flex prices, not run): the gate asks for "both judges";
   it is met on `stratified_70` only. Left out to keep a margin under the key's limit ($14.39 left) and because
   it exceeded the run's estimate. Run it with
   `selfscore --judge gemini-3.1-pro --sets gpt-6.1-sol.rep2` if wanted.
2. **The 3 residual validator errors** (Q149, Q326, Q442): accept as listed (recommended; two are heading /
   restated items), or fix by hand.
3. **Cache backup** of `nuggets/full/cache/` (gitignored; 246 MB) to the private HF dataset repo: needs your
   go-ahead (outward-facing).
4. Still open from before: the "expanded" score on `has_pointer` questions (phase 5), and the open-weight Qwen
   judge (left out here).
5. **Key:** renew or raise the limit before phase 5 (scoring ≈ $1.2–1.3 per answer run and nugget set with Flash).
