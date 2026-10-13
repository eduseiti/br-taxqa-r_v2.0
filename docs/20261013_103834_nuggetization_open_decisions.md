# Nuggetization — decisions after the phase 1 pilot

**Generated:** 2026-10-13 10:38:34 (local time, from `date +%Y%m%d_%H%M%S`).
**Source:** §12 of `docs/20261012_192640_nuggetization_phase1_pilot.md` (the pilot note), plus the items still
open in plan v2 (`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`).
**Purpose:** one place for what is decided and what is still open. Update the status of an item here when it
is decided.

## 1. Closed

| # | Decision | Outcome | Date | Evidence |
|---|---|---|---|---|
| 1 | Creation prompt | **`create_v4`**, unchanged | 2026-10-13 | Pilot note §2, §5–§7: 0 rejected sets after the validator fixes; self-score 98.5–100 % |
| 2 | Call mode | **One call** (nuggets and `vital`/`okay` labels in the same response) | 2026-10-13 | Pilot note §4: the 2-call mode changed 14 % of labels and agreed less with the other families' consensus (88 % vs 99 %), at a higher cost |
| 3 | Acceptance thresholds | **Plan v2 §3.5.6 thresholds, plus (a) and (b) below** | 2026-10-13 | Pilot note §6, §7, §12 |
| 4 | `answer_cleaned` content loss | Fixed in the v2.0 build (`scripts/dataset/answer_overrides.json`; 47 answers changed) | 2026-10-12 | Pilot note §8, §13.1 |
| 5 | Gemini 3.1 Pro daily quota | Batch API mode (`--batch`, `batch wait`) | 2026-10-12 | Pilot note §9.1, §13.2–§13.3; used to finish the pilot (§11) |

### 1.1 Thresholds adopted (decision 3)

A nugget set passes when all of these hold:
- **0 hard errors** (schema, span, validator).
- **Gold self-score ≥ 98 %** of nuggets labelled `support` against their own gold answer.
- **≤ 2 % of nuggets flagged by both auditors**, after repair.
  - **(a)** A nugget counts as "flagged by both" when each auditor flags it **on any check**, not necessarily the
    same one. Q679 in the pilot was flagged by both auditors, for different reasons.
- **Judge sensitivity ≥ 0.90** on the value, year and verdict corruptions of the known-answer tests.
- **(b)** **Each auditor catches ≥ 80 % of the planted errors** (one damaged nugget per question; pilot note
  §6.3). This makes the ≤ 2 % gate meaningful: a lenient auditor would flag little and still pass it.

Pilot values: 0 hard errors; self-score 98.5 % or more with every judge; 0 % flagged by both after repair;
Flash 100 % on V/Y/N; planted errors Qwen 29/30, 3.1 Pro 29/30 (its miss is a test flaw, item 6).

## 2. Open

### 2.1 Before phase 4: fixes to the known-answer test builder (pilot note §12 item 6)

The known-answer tests corrupt a gold answer and check that the judge notices. Most judge "misses" in the
pilot (pilot note §7) were flaws in the generated tests, not judge errors:

- **W (answer to the wrong question):** the substitute answer sometimes comes from a near-duplicate question,
  so the nugget really is supported. Fix: exclude near-duplicate questions as the source.
- **D / C (a sentence or condition deleted):** the deleted fact is sometimes restated elsewhere in the
  answer, so `support` is correct. Fix: drop tests whose fact survives in the remaining text.
- **V (value changed):** replace the synthetic bump with a real value of the same item for another period,
  taken from the corpus. This is a harder, more realistic test.
- **Planted errors (`planted.py`, added 2026-10-13):** skip an "addition" clause that the nugget already implies
  (Q703_N03: the clause "inclusive quando o contribuinte for não residente no Brasil" was appended to a
  nugget already about non-resident investors).

**To decide:** whether to do these, and when (suggested: before phase 4).

### 2.2 Cache backup to the private HF dataset repo (pilot note §12 item 7)

The cache (`nuggets/<run>/cache/`, gitignored; ≈ 20 MB for the pilot) holds every raw API response. Reruns
are free and reproducible because of it. The plan backs it up to the private HF dataset repo at the end of
each phase.

**To decide:** when to push. This is outward-facing, so it is not done without the user's go-ahead.

### 2.3 "Expanded" score on `has_pointer` questions (plan v2; preview note §13.5 item 4)

Some gold answers only point to another question ("consulte a pergunta N"); `create_v4` makes no nugget for
the pointer itself. Optionally, score such answers a second time with the target question's nuggets added.

**To decide:** whether to report this score. It matters only at scoring time (phase 5).

### 2.4 Open-weight Qwen judge (plan v2 D4)

An open-weight Qwen model as a judge next to Gemini Flash, for reproducibility with an open model. It would be
served from an HF endpoint; estimated $10–25, not measured.

**To decide:** whether to include it, and when to test it (it needs its own known-answer run).

## 3. Not open (for the record)

- **Effort escalation for long answers** (plan v2): no sign of need in the pilot; the longest answers
  (Q624, Q330) had no omissions. Revisit only if phase 2 shows omissions on long answers.
- **Gemini judge: Flash, not 3.1 Pro** (plan v2 D2: Pro replaces Flash only if its balanced accuracy is
  > 0.05 higher). On all 141 tests, Flash had BA 97.9 % and Pro 97.1 %. Pro also caught only 3 of 5 flipped
  verdicts (pilot note §7).

## 4. Next step

With decisions 1–3 closed, **phase 2** can start on the 715 questions: creation by the three families,
the two auditors with repair, and Gemini 3.1 Pro and GPT through Batch, with `--budget` on every run (pilot
note §10.1 has the estimate).
