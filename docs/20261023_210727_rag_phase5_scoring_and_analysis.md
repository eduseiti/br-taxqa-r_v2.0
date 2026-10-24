# Nugget phase 5 — scoring of the trimmed grid and the first full RAG analysis

**Generated:** 2026-10-23 21:07:27 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** nugget phase 5 (plan v2 §5,
`docs/20261011_224049_gold_answer_nuggetization_plan_v2.md`) on the 25 runs of the trimmed grid
(`docs/20261023_151928_rag_phase3_trimmed_full_generation.md`): stage 0 and the scoring parts of stages 1, 2 and 4
of `docs/20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md` §3.
**Cost:** **$55.96** billed (ledger `nuggets/scoring/costs.csv`, 22,096 ledger rows, 0 failed answers): stage 0 $4.28, primary
scoring $29.94, context support $8.30, cross-set scoring $11.09, second judge $2.35. The plan note estimated
$43–61. OpenRouter key: **$9.08 left** of the $150 limit (2026-10-23 21:07).
**Update 2026-10-24:** §10 audits the context-support result of §4 (steps a–e, $3.86; key: $5.22 left).
**Status:** scoring and the free analyses are done. Not done: stages 3 and 4 (budget sweep or 16k point;
DeepSeek V4), plus the open items of §9.

## 1. What was run

All judge calls use Gemini 3.8 Flash (`google-ai-studio/flex` on OpenRouter); the only exception is the second
judge in §7.4. Commands (global options before the subcommand):

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py; A=runs/answers/jua-4b-mixed/irpf; C=runs/contexts/jua-4b-mixed/irpf
O="--out nuggets/scoring --workers 24"
# stage 0: the 56 pilot runs (stratified_30) and context support on the 11 pilot context sets
$P $N $O --sample stratified_30 --budget 6 score --runs "$A/*/*/*"
$P $N $O --sample stratified_30 --budget 6 ctxsupport --contexts "$C/*"
# primary scoring, 715 questions (28 outputs: the 25 runs + Terra's pilot-size S3/S2c/S4)
$P $N $O --sample all --budget 45 score --runs "$A/*/*/*"
# context support (S1, S2, oracle 4k) and the cross-sets (S1/S2 4k, Terra and Sabiá-4)
$P $N $O --sample all --budget 58 ctxsupport --contexts $C/S1_budget4000 $C/S2_budget4000 $C/oracle_budget4000
for s in gemini-3.1-pro.rep0 qwen3.8-max.rep0; do
  $P $N $O --sample all --budget 58 score --set $s --runs "$A/answer_v1/gpt-5.6-terra/S[12]_budget4000" "$A/answer_v1/sabia-4/S[12]_budget4000"
done
# second judge on stratified_70
$P $N --out nuggets/scoring --sample stratified_70 --workers 12 --budget 57.5 score --judge gemini-3.1-pro \
  --runs "$A/answer_v1/gpt-5.6-terra/S[12]_budget4000" "$A/answer_v1/sabia-4/S[12]_budget4000"
# tables and analyses (no LLM)
for s in gold gemini-3.1-pro.rep0 qwen3.8-max.rep0; do $P $N --out nuggets/scoring --sample all scoretable --set $s; done
$P $N --out nuggets/scoring --sample all analyze        # ≈ 8 min
```

| Item | Calls | Billed | Estimate | Per call |
|---|---:|---:|---:|---:|
| Stage 0 (56 pilot runs + 11 pilot context sets) | 1,567 | $4.28 | $4–5 | $0.0023 / $0.0047 |
| Primary scoring, 28 outputs × 715 | 13,238 | $29.94 | $25–38 | $0.0023 |
| Context support, S1 / S2 / oracle 4k | 1,898 | $8.30 | $9.09 (plan: $6) | $0.0044 |
| Cross-sets (Gemini 3.1 Pro, Qwen3.8-Max sets), 4 runs each | 5,133 | $11.09 | $12.1 (plan: $8–12) | $0.0022 |
| Second judge (Gemini 3.1 Pro), `stratified_70` × 4 runs | 257 | $2.35 | ≈ $2.7 | $0.0091 |

Answers that are abstentions or errors are not sent to the judge: every nugget gets `not_support`. Identical
answers (S3 / S4 prompts that repeat S2 / S2c ones) are cache hits.

**Code:**
- `nuggets.py score | ctxsupport | scoretable | analyze`.
- `nuggetizer/scoring.py`: per-question scores and the paired, permutation and chapter-cluster statistics.
- `nuggetizer/analysis.py`: the analyses that need no LLM.
- `nuggetizer/values.py`: `digits_for_words`, the fix for spelled-out numbers.
- `prompts/assign_ctx_v1.pt.md`: the judge applied to the context instead of the answer.

**Outputs:**
- `nuggets/scoring/score/<set>/<judge>/<run_id>/` and `ctxsupport/<set>/<judge>/<context path>/`: `labels.jsonl`,
  `calls.jsonl`, `manifest.json`.
- `tables/<set>/<judge>/<sample>/`: `runs.csv`, `comparisons.csv`, per-question tables, context-support tables.
- `analysis/gold-v0-auto/gemini-3.8-flash/all/`: one CSV per analysis below.

## 2. Answer scores (primary set, 715 questions)

Vital-nugget recall with strict credit (V_strict, the headline), plus V, A_strict, W, the share of answers that
contradict at least one nugget ("contra."), abstention and answer length. Oracle 4k: the 596 questions with a
gold provision in the corpus.

| Generator | Set | V_strict | V | A_strict | W | contra. | abstained | chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Terra | closed book | **0.351** | 0.490 | 0.308 | 0.448 | 0.295 | 0.000 | 1,049 |
| Terra | S1 4k | 0.325 | 0.456 | 0.284 | 0.419 | 0.092 | 0.036 | 740 |
| Terra | S2 4k | 0.341 | 0.479 | 0.303 | 0.441 | 0.080 | 0.035 | 764 |
| Terra | oracle 4k | 0.368 | 0.514 | 0.325 | 0.471 | 0.065 | 0.047 | 735 |
| Sabiá-4 | closed book | 0.239 | 0.379 | 0.213 | 0.350 | 0.382 | 0.013 | 1,016 |
| Sabiá-4 | S1 4k | 0.290 | 0.446 | 0.257 | 0.409 | 0.115 | 0.054 | 787 |
| Sabiá-4 | S2 4k | **0.317** | 0.470 | 0.285 | 0.433 | 0.112 | 0.034 | 822 |
| Sabiá-4 | S3 / S2c / S4 4k | 0.315 / 0.305 / 0.307 | | | | | | |
| Sabiá-4 | oracle 4k | 0.319 | 0.462 | 0.278 | 0.422 | 0.091 | 0.121 | 706 |
| Sabiazinho-4 | closed book | 0.177 | 0.327 | 0.159 | 0.300 | 0.380 | 0.000 | 1,030 |
| Sabiazinho-4 | S1 4k | 0.267 | 0.427 | 0.241 | 0.395 | 0.139 | 0.032 | 722 |
| Sabiazinho-4 | S2 4k | 0.272 | 0.439 | 0.242 | 0.403 | 0.119 | 0.027 | 683 |
| Sabiazinho-4 | S3 / S2c / S4 4k | 0.277 / 0.286 / 0.287 | | | | | | |
| Sabiazinho-4 | oracle 4k | 0.293 | 0.461 | 0.263 | 0.425 | 0.117 | 0.057 | 601 |
| Luna | closed book | 0.259 | 0.420 | 0.220 | 0.378 | 0.266 | 0.003 | 672 |
| Luna | S1 4k | 0.271 | 0.387 | 0.235 | 0.351 | 0.080 | 0.241 | 624 |
| Luna | S2 4k | 0.299 | 0.424 | 0.261 | 0.388 | 0.085 | 0.168 | 692 |
| Luna | S3 / S2c / S4 4k | 0.300 / 0.314 / 0.304 | | | | | | |
| Luna | oracle 4k | 0.338 | 0.475 | 0.299 | 0.435 | 0.065 | 0.128 | 673 |

Wrong-context control: V_strict 0 for every generator, which is the expected result.

## 3. Paired comparisons (V_strict, b − a, 714 questions)

| Comparison | Luna | Terra | Sabiá-4 | Sabiazinho-4 |
|---|---|---|---|---|
| **S1 → S2 4k** | **+0.028** (0.008, 0.049) p .007 | +0.016 (−0.004, 0.037) p .11 | **+0.027** (0.007, 0.047) p .009 | +0.005 (−0.015, 0.025) p .63 |
| S2 → S3 4k | +0.000 p .98 | — | −0.002 p .74 | +0.005 p .56 |
| S2 → S2c 4k | +0.014 p .15 | — | −0.012 p .22 | +0.013 p .16 |
| S3 → S4 4k | +0.005 p .66 | — | −0.007 p .44 | +0.010 p .30 |
| closed book → S1 | +0.013 p .43 | −0.027 p .12 | **+0.051** p .003 | **+0.090** p < .001 |
| closed book → S2 | **+0.041** p .011 | −0.010 p .56 | **+0.078** p < .001 | **+0.095** p < .001 |
| S1 → oracle 4k (595) | **+0.044** p .002 | +0.014 p .33 | +0.005 p .69 | +0.009 p .52 |
| S2 → oracle 4k (595) | +0.021 p .14 | +0.004 p .78 | −0.016 p .21 | +0.009 p .54 |

The intervals are 95 % paired-bootstrap CIs, and p is a paired permutation test. The chapter-cluster bootstrap
agrees on S1 → S2: Luna (0.006, 0.052), Sabiá-4 (0.004, 0.047), Terra (−0.002, 0.037), Sabiazinho-4 (−0.010, 0.023).
All tables are in `tables/gold-v0-auto/gemini-3.8-flash/all/comparisons.csv`, for every metric.

**Reading:**
- **S2 answers better than S1 for all four generators, but the gain is small.** It is significant for Luna and
  Sabiá-4. With the other nugget sets it is significant for Terra as well (§7.3).
- **S3, S2c and S4 add nothing measurable over S2** (all |diff| ≤ 0.014, none significant). The pilot hints of
  S3 / S2c gains were noise.
- **Retrieval helps the Maritaca models and Luna, but not Terra.** Terra's closed-book score is as high as its
  RAG scores (0.351 against 0.341). At the same time, closed-book answers contradict at least one nugget in
  27–38 % of the questions, against 8–14 % with retrieval. So retrieval mainly buys correctness rather than
  recall: Terra's closed-book recall partly comes from what it already knows about the P&R content.
- **The oracle gives little.** With the cited provisions as context (within 4k tokens), V_strict reaches only
  0.29–0.37. §4 and §5 give two reasons; §10 tests the first one.

## 4. Context support (what the context holds)

The judge applies the same nuggets to the context instead of an answer (`assign_ctx_v1`). PGD/program
instructions missing from the texts count as `not_support`, and so does another period's value.

| Context | Questions | V_strict | V | A_strict | contra. |
|---|---:|---:|---:|---:|---:|
| S1 4k | 715 | 0.397 | 0.509 | 0.372 | 0.025 |
| S2 4k | 715 | 0.411 | 0.524 | 0.385 | 0.027 |
| oracle 4k | 596 | 0.483 | 0.598 | 0.463 | 0.029 |

- **The oracle context fully supports fewer than half of the vital nuggets, as judged.**
  - Measured: the article chunks of the cited provisions, cut to 4,000 tokens (80 % of the gold articles fit),
    judged by Flash with `assign_ctx_v1`.
  - Per nugget (595 questions): support 46.7 %, partial_support 20.1 %, not_support 32.7 %, contradicts 0.5 %.
  - Without PGD nuggets, and only on questions whose context holds every gold article and provision (804
    nuggets, 317 questions): 47.4 % / 22.0 % / 29.7 %.
  - This bounds the RAG answers of §2. Whether it reflects the P&R document (answers that go beyond, or cite
    other provisions than, the legal texts), the corpus, the 4k cut or the context judge was not tested when
    this section was written: §10 tests it.
- **S2's contexts hold barely more than S1's** (+0.014 V_strict). The retrieval test's +0.10 article recall
  turns into little extra nugget content.

## 5. Linkage and utilisation (`linkage_*.csv`, `utilisation_runs.csv`)

**What the answer uses from the context** (vital nuggets, nugget level, S1 / S2 / oracle 4k):

| Generator | Context supports | Utilisation P(ans support \| ctx support) | Leakage P(ans support \| ctx not_support) | Answer support not in context |
|---|---|---|---|---|
| Terra | 0.380 / 0.386 / 0.467 | 0.625 / 0.649 / 0.591 | 0.024 / 0.025 / 0.028 | 3.8 / 3.5 / 2.9 % |
| Sabiá-4 | same contexts | 0.566 / 0.610 / 0.520 | 0.018 / 0.030 / 0.012 | 3.1 / 4.7 / 1.5 % |
| Sabiazinho-4 | same contexts | 0.494 / 0.479 / 0.471 | 0.027 / 0.030 / 0.020 | 5.3 / 5.7 / 2.6 % |
| Luna | same contexts | 0.546 / 0.557 / 0.541 | 0.018 / 0.016 / 0.017 | 3.3 / 2.8 / 1.9 % |

- **Generators state only 48–65 % of the vital nuggets their context fully supports.** This is the second limit,
  after the ceiling of §4. Utilisation is higher on S2 than on S1 for three generators. It is *lower* on the
  oracle for all four: Luna abstains on more oracle questions, and so do the Maritaca models (pilot note §6.9:
  negative-inference questions).
- **Leakage with retrieval is small.** 2–6 % of the answers' `support` labels are for nuggets the context does
  not support. RAG answers come from the context; recall from the model's own knowledge shows up only in closed
  book.
- **Answer score follows the context.** Answer V_strict is 0.07–0.13 when the context supports no vital nugget,
  0.26–0.34 when it supports some, and 0.54–0.72 when it supports all of them. The Spearman correlation between
  answer and context V_strict per question is 0.53–0.67.
- **S1 → S2 decomposition** (552 questions with both scores): the context support changes in only 73 questions.
  - Where it improves (47), the answer gains +0.04 to +0.13.
  - Where it worsens (26), the answer loses −0.05 to −0.11.
  - **Most of the S2 gain comes from the 479 questions whose context support is unchanged**: Luna +0.024 of its
    +0.025, Sabiá-4 +0.009 of +0.016.

  So S2 helps the generator use what it gets (smaller, focused sub-unit chunks, more of the gold provisions:
  article recall +0.094 in those questions). It does not mainly help by bringing new facts into the context.

## 6. Value checks and citations (no LLM)

### 6.1 Value checks (plan v2 §5.4; `values_*.csv`)

There are 539 nuggets with values per run (R$, %, dates).

- **The value-hit rate (0.19–0.44) is above the judge's `support` (0.06–0.21).** The value is often there while a
  condition of the nugget is missing.
- **When the judge says `support`, the value is in the answer in 79–95 % of the cases.** The rest are
  paraphrases: "fora do prazo" for "after 31/05/2024", "último dia útil de maio".
- **Overall judge–value agreement is 0.72–0.85.** This doubles as a free check of the judge.
- **Value conflicts are rare: at most 1.1 % of the value nuggets, 1–6 per run.** A conflict is another value of
  the same kind in the answer sentence that restates the nugget, or the answer's only value of that kind.
  - The first, looser rule ("any other value of the same kind") flagged whole tables: a single 30 % in an answer
    flagged 11 rate nuggets of Q706.
  - Most of the judge's `contradicts` labels on value nuggets are therefore not value swaps (≤ 17 % are). They
    are verdicts, conditions and rules.
  - **The temporal-substitution hypothesis (S2 inciso chunks cause fewer wrong-year values than S1) cannot be
    tested.** There are only 0–4 temporal substitutions per RAG run (1–6 in closed book).
- **The "values not in context" proxy of Phase 3, with spelled-out numbers and "1°" fixed, drops to 0–0.5 % of the
  answers** (it was up to 1.3 %). The remaining flags are real; closed book is excluded because it has no context.

### 6.2 Legal-provision score of the citations (plan v2 §5.5; `citations_*.csv`)

The texts each answer cites (`cited_chunk_ids`) are scored against the gold provisions with the matcher of the
retrieval evaluation. Precision is the share of cited (or retrieved) texts that touch a gold unit; it is a count
share, not the evaluation's token-weighted precision. 596 questions with gold, article level:

| Generator | Texts cited (S1 / S2) | Cited recall S1 / S2 / oracle | Context recall S1 / S2 / oracle | Cited precision S1 / S2 | Context precision S1 / S2 |
|---|---|---|---|---|---|
| Terra | 2.2 / 2.5 | 0.296 / 0.351 / 0.559 | 0.398 / 0.503 / 0.803 | 0.362 / 0.400 | 0.103 / 0.122 |
| Sabiá-4 | 3.1 / 3.7 | 0.330 / 0.417 / 0.568 | same | 0.320 / 0.331 | same |
| Sabiazinho-4 | 3.6 / 4.1 | 0.346 / 0.415 / 0.627 | same | 0.284 / 0.299 | same |
| Luna | 2.1 / 2.5 | 0.273 / 0.336 / 0.538 | same | 0.366 / 0.369 | same |

- **Generators cite 66–86 % of the gold articles the context holds.**
- **Their citations are about 3× as precise as the context.**
- **S2 raises cited recall by 0.05–0.09 for every generator.** That is the retrieval gain carried into the answer.
- Closed-book answers have no cited texts; scoring their in-text legal citations (`citations.py` + act
  attribution) was not done.

## 7. Robustness

### 7.1 Nugget subsets (`slices_comparisons.csv`, S1 → S2 V_strict)

- **Without PGD nuggets** (613 questions), S1 → S2 is Luna +0.035 (p .003), Sabiá-4 +0.026 (p .022), Terra +0.019,
  Sabiazinho-4 +0.004. That is slightly larger than with them.
- **PGD nuggets score low everywhere** (V_strict 0.11–0.30). The exception is Terra closed book, at 0.297.
- **On temporal nuggets** (302 questions) the difference is −0.01 to +0.02 and not significant. Sub-article chunks do not
  help period-specific facts more than others (no support for the S2 temporal hypothesis).
- **On `condicao` nuggets** (235) it is +0.004 to +0.015, not significant. The expected S2 advantage on conditions
  and exceptions does not show.
- **Stable-only** (nuggets that all three families produced) and **not-audit-flagged** nuggets give the same
  results as the full set: Luna +0.028 / +0.033, Sabiá-4 +0.028 / +0.025, both significant.
- **By chapter** (`chapters_s1_s2.csv`), S2 > S1 in 19–24 of 48 chapters per generator. No single chapter carries
  the gain. "Aplicações financeiras" is positive for all four (+0.02 to +0.13).

### 7.2 Perturbed nugget sets (`perturbation_s1_s2.csv`, 1,000 replicates)

Share of replicates in which S2 − S1 keeps its sign and stays significant (paired t, p < .05), V_strict:

| Damage | Luna | Sabiá-4 |
|---|---:|---:|
| none | 1.00 | 1.00 |
| random deletion 10 % / 15 % / 20 % | 0.95 / 0.89 / 0.78 | 0.97 / 0.93 / 0.86 |
| random deletion 30 % / 40 % / 50 % | 0.60 / 0.48 / 0.32 | 0.79 / 0.68 / 0.60 |
| vital ↔ okay flips 10 % / 20 % / 30 % | 0.95 / 0.79 / 0.65 | 0.97 / 0.90 / 0.81 |
| all `condicao` nuggets deleted | 1.00 | 1.00 |
| audit-flagged deleted; stable-only | 1.00; 1.00 | 1.00; 1.00 |

- **The S2 − S1 result survives 15–20 % nugget damage**, the bar set by plan v2 §5.6. The break-even (< 50 % of
  replicates significant) is around 40 % random deletion for Luna and above 50 % for Sabiá-4.
- **The sign is kept in every replicate.**
- Terra: the difference is significant under A_strict (+0.019, p .036) but not under V_strict. It is fragile to
  deletion (0.34–0.64).

### 7.3 Cross-sets (`crossset_*.csv`; Terra and Sabiá-4, S1 / S2 4k)

| Nugget set | Terra S1 → S2 | Sabiá-4 S1 → S2 |
|---|---|---|
| primary (GPT-6.1 Sol) | +0.016 (−0.004, 0.037) p .11 | +0.027 (0.007, 0.047) p .009 |
| Gemini 3.1 Pro set | **+0.024** (0.004, 0.045) p .020 | **+0.023** (0.003, 0.043) p .022 |
| Qwen3.8-Max set | **+0.026** (0.006, 0.047) p .010 | **+0.028** (0.008, 0.048) p .007 |

- **Every difference keeps its sign and is significant under both other sets**, with the chapter-cluster CI above
  zero. Terra becomes significant.
- **The ranking of the 4 runs is identical under the three sets** (Kendall τ = 1).
- **The conclusion does not depend on the nugget creator.** The primary set is the most conservative of the three.

### 7.4 A second judge on real answers (`judge_*_gemini-3.1-pro.csv`)

Gemini 3.1 Pro judged `stratified_70` × {Terra, Sabiá-4} × {S1, S2 4k}: 280 answers, 1,364 nugget labels.

- **Agreement with Flash is 94.7 % on the four labels** (Cohen's κ 0.90), and κ = 0.93 for `support` against the
  rest.
- **Disagreements sit on the boundaries.** 34 Flash `partial_support` labels are Pro `not_support`, 12 Flash
  `support` are Pro `partial_support`, and 10 Flash `contradicts` are Pro `not_support`. Flash is a little harsher
  on `contradicts` (2.4 % of labels against 1.6 %).
- **Both judges give the same S1 → S2 direction and size on this sample**: Terra −0.020 (Flash) / −0.013 (Pro),
  Sabiá-4 −0.032 / −0.025, none significant at n = 70.
- **The judge choice (D2) holds on real answers.**

## 8. Conclusions of the first full evaluation

1. **Hierarchical segmentation (S2) gives better answers than article chunks (S1), but by little:** +0.02 to
   +0.03 V_strict. The gain is significant for Luna and Sabiá-4 on the primary set, and for Terra and Sabiá-4 on
   both other nugget sets. It is robust to nugget damage, chapter clustering and nugget subsets. Sabiazinho-4
   shows no gain.
2. **The groupings and caput variants (S3, S2c, S4) add nothing over S2 at 4k.**
3. **The gain is small because the answers are limited by two things that segmentation does not change:**
   - what the context holds of the P&R answers: about 47 % of vital nuggets fully supported even by the cited
     provisions within 4k tokens (§4). This rests on one context judge; how much of it reflects the P&R document
     itself is the subject of §10;
   - how much of the supported content the generator states (48–65 %, §5).

   S2's advantage comes mostly from better use of the context. It brings little extra content.
4. **Retrieval mainly reduces contradictions** (27–38 % → 8–14 % of answers). It helps recall only for the weaker
   generators; Terra answers the P&R questions about as well from its own knowledge.
5. **The temporal and condition hypotheses for S2 are not supported**: no extra gain on temporal or `condicao`
   nuggets, and value conflicts are too rare to test.

## 9. Open items

1. Stages 3 and 4 of the plan note: the 16k point (S2 / S3 for Sabiá-4 and Sabiazinho-4, plan note §4.4) or the
   2k / 8k sweep, and DeepSeek V4 from the other machine. **$9.08 was left on the OpenRouter key ($5.22 after
   §10).** At the
   measured $0.0023 per scored answer, a 715-question run costs ≈ $1.6 to score, plus generation.
2. The 6 truncated Maritaca answers (generation note §3) still count as empty. They change no mean by more than
   0.003.
3. Citation scoring of closed-book answers (in-text citations, act attribution).
4. A human calibration sample (plan v1 §4.4): the 72 Flash–Pro disagreements of §7.4 are natural candidates.
5. Commit the scoring outputs. Only `labels.jsonl`, `calls.jsonl`, manifests and the tables are small enough for
   git; `nuggets/scoring/cache/` is gitignored.

## 10. Update (2026-10-24 01:58): do the cited provisions hold the P&R answers?

**Question (user, after §4):** §4 found that the oracle context fully supports only about 47 % of the vital
nuggets. Does that mean the legal texts the P&R cites do not hold much of what its answers state? If so, it is a
finding about the source document's consistency. It must then be shown that the result is not an artefact of the
oracle context, the corpus or the context judge.

**What §4 had not ruled out:**
- The 4k cut: only 80 % of the gold articles fit.
- A single, untested context judge (`assign_ctx_v1` had no known-answer tests; Flash only).
- Facts that sit in legislation the P&R does not cite.
- Content in the nuggets that is not normative (PGD instructions).

Steps a–e were run on `stratified_70`: the 57 questions with resolvable references, 212 vital nuggets.
**Cost: $3.86** billed (617 calls, ledger `nuggets/scoring/costs.csv`); the OpenRouter key has **$5.22 left**.

Commands:

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py; C=runs/contexts/jua-4b-mixed/irpf
O="--out nuggets/scoring --sample stratified_70"
$P $N $O --budget 57 ctxsupport --contexts $C/oracle_budget16000 $C/wrong-S2_budget4000          # c, a (negative)
$P $N $O --budget 58.5 ctxsupport --contexts $C/oracle_budget16000 --judge gemini-3.1-pro         # b
$P $N $O --budget 61 ctxaudit known      # a: phase 4 tests + needle tests, judged with assign_ctx_v1
$P $N $O --budget 61 ctxaudit corpus     # d: corpus search for the unsupported vital nuggets
$P $N $O --budget 61.5 ctxaudit classify # e: cause of each unsupported nugget (Gemini 3.1 Pro)
```

Outputs are in `nuggets/scoring/ctxaudit/gold-v0-auto/stratified_70/`: `known/`, `corpus/`, `classify/`, and
`classify/review.csv` (the 60 unsupported nuggets, all the evidence, the classifier's cause and the reviewed
cause). Code: `nuggetizer/ctx_audit.py`, `nuggets.py ctxaudit`, prompt `ctxaudit_classify_v1.pt.md`.

### 10.1 (a) The context judge is reliable

Known-answer tests judged with `assign_ctx_v1`. The test text plays the role of the context: it is the gold
answer, corrupted as in phase 4 (§2.5 of the phases 2–4 note).

| Test | Tests | Result |
|---|---:|---|
| G (gold answer as context) | 70 | 98.0 % of nuggets `support` |
| V / VP / Y (value or year changed) | 14 / 3 / 14 | detected 100 % (`contradicts` 100 % / 100 % / 53 %; the rest `not_support`, as the period rule asks) |
| N (verdict flipped) | 14 | 89 % |
| D (span deleted) / C (condition removed) | 44 / 25 | 94 % / 80 % |
| W (another question's answer) / E (empty) | 70 / 70 | 99.4 % / 100 % `not_support` |
| **Pooled** | 324 | sensitivity 98.7 %, specificity 98.4 %, **balanced accuracy 98.5 %** |
| Needle: the nugget's P&R source sentence appended to its 16k oracle context | 60 | `support` 65 %, `partial_support` 28 %, `not_support` 7 % |
| Wrong context (`wrong-S2_budget4000`), real legal texts of another question | 70 | 99.1 % `not_support` (0 `support`) |

- **The judge finds a fact that is in a long legal context.** The needle partials and misses are list fragments of
  the P&R answer that do not carry their own subject: "Ganho apurado na alienação de imóveis adquiridos até
  1969;" is not, by itself, a statement that the gain is exempt.
- **The judge does not invent support from unrelated legal text.**

### 10.2 (b, c) The oracle context without the 4k cut, and a second judge

`oracle_budget16000`: 94.5 % of gold articles fit (4k: 80 %). Vital nuggets of the 57 questions:

| Context, judge | support | partial | not_support | contradicts |
|---|---:|---:|---:|---:|
| oracle 4k, Flash | 38.2 % | 17.5 % | 44.3 % | 0 |
| **oracle 16k, Flash** | **50.5 %** | 20.8 % | 28.3 % | 0.5 % |
| oracle 16k, Gemini 3.1 Pro | 49.5 % | 19.8 % | 30.2 % | 0.5 % |

- **The 4k cut made the gap look bigger than it is.** On these questions the cut hid 12 points of support. Of the
  212 labels, 41 moved up from 4k to 16k and 1 moved down (`support` → `partial_support`).
- **Two judges give the same picture.** Flash and Pro agree on 86.6 % of the labels (κ 0.79; κ 0.79 on `support`
  against the rest), and the disagreements are between adjacent labels.
- **So about half the vital nuggets are fully stated by the cited provisions, one fifth in part, and 28–30 % not
  at all.**

### 10.3 (d, e) Why 60 vital nuggets are not supported

**d. Corpus search.** For each unsupported nugget, the context was made of other texts:
- the 4 texts a TF-IDF search on the nugget text ranks highest in the whole corpus, outside the cited articles;
- plus the question's dense S2 retrieval, outside the cited articles.

The revoked RIR/1999 is excluded, as in the RAG runs. Flash then judged the nugget against that context: 13 of
the 60 are fully supported there and 15 partly.

**e. Classification.** Gemini 3.1 Pro saw the question, the official answer, its references, the nugget, both
contexts and both judges' labels, and assigned one cause per nugget. I then read all 60 classifications against
the evidence, and changed 17 of them:
- **12 `corpus_gap` → `oracle_gap`.** All are on Q560, Q326 and Q592, and the cited provision is in the corpus
  but not in the oracle context:
  - Q560 and Q326 cite 17 articles each and overflow 16k tokens: 6 and 11 of 17 fit.
  - Q592 lost part 1 of a split article (Lei 8.981 art. 21).
  - The cause is in the oracle construction: a cited document without article ids (mostly Soluções de
    Consulta) enters the context whole and uses up the budget.
- **4 `interpretation` → `other_provision`** (Q271 ×3, Q165): the fact is stated in a Solução de Consulta of the
  corpus that the answer does not cite.
- **1 `other_provision` → `interpretation`** (Q555_N02): no text in either context states it.

The classifier found no `judge_error` and no `nugget_problem`.

Share of the 212 vital nuggets. The CI is a 95 % bootstrap over the 57 questions (clusters):

| Reviewed class | Nuggets | Share | 95 % CI | Questions |
|---|---:|---:|---|---:|
| supported by the cited provisions | 107 | 50.5 % | 39.3–62.4 | |
| partly supported | 44 | 20.8 % | 12.5–28.1 | |
| `oracle_gap`: cited, in the corpus, not in our oracle context | 12 | 5.7 % | 0.0–12.7 | 3 |
| `other_provision`: stated in another, uncited text of the corpus | 15 | 7.1 % | 3.0–12.4 | 10 |
| `interpretation`: the Receita's application, combination or *a contrario* reading of the provisions | 20 | 9.4 % | 4.5–17.1 | 14 |
| `pgd_practical`: program, form, field instructions | 8 | 3.8 % | 0.6–9.2 | 5 |
| `not_in_legislation`: no basis in any corpus text (administrative position) | 5 | 2.4 % | 0.0–7.4 | 2 |
| contradicts (not audited) | 1 | 0.5 % | | |

**Examples:**
- **interpretation:**
  - Q350: a parent-in-law is not a dependant unless the spouse files jointly. The law lists only "pais".
  - Q661: selling part of one's only property does not get the exemption for the "único imóvel".
  - Q604: a transfer of quotas between spouses under comunhão universal is not an alienação.
- **other_provision:**
  - Q023: someone travelling on the deadline still has to file. This is Decreto-Lei 5.844/1943 art. 194, not
    cited.
  - Q267: late carnê-leão payments bear charges. This is IN RFB 1.500/2014 art. 107, not cited.
  - Q515: three rules of IN SRF 84/2001 arts. 9 and 19; the answer cites only art. 3.
- **not_in_legislation:**
  - Q533: four rules on the treatment of rural-activity assets after the property is sold.
  - Q283: tax-exempt grants do not justify an increase in wealth.

### 10.4 What this supports, and what it does not

**Supported, on this sample:**
- **Most of the vital content of a P&R answer is stated by the provisions it cites:** 50.5 % fully, 20.8 % in part.
- **About one vital nugget in six (15.6 %, CI 8.2–25.7 %, in 20 of 57 questions) is not stated in any legal text
  of the corpus.** It is the Receita's own application of the provisions to the case (9.4 %), program
  instructions (3.8 %) or an administrative position (2.4 %).
- **About one in fourteen (7.1 %) is stated in legislation the answer does not cite.** The P&R's citations are
  then incomplete for that fact.
- **These conclusions do not depend on the context judge** (98.5 % balanced accuracy on known answers, needle and
  wrong-context controls passed, Flash and Pro agree), **nor on the 4k cut.**

For the RAG results this means the oracle ceiling is mainly the P&R document's own content beyond its citations,
plus our oracle construction. It is not the judge.

**Not yet supported:**
- **Sample size and concentration:** 57 questions. Q560 alone has 12 of the 60 unsupported nuggets, so the CIs are
  wide.
- **The 44 partly supported nuggets (20.8 %) were not audited.** They probably mix missing conditions,
  interpretation and the same `oracle_gap`.
- **The causes come from one classifier plus my reading.** The legal calls — mainly `interpretation` against
  `not_in_legislation` — need a tax-law reader. `review.csv` has a `reviewed_cause` column for that.
- **The corpus is the legislation the P&R cites anywhere, not all IRPF legislation.** `not_in_legislation` means
  "not in this corpus", and the corpus search is one lexical and one dense search, so a fact it missed could
  still exist.
- **The oracle construction understates the cited content for questions with many references.** The same
  `oracle_gap` affects the oracle answer runs of §2–§3.

**Next, to make it a paper claim:**
1. Context support with the 16k oracle on all 596 questions (≈ $3.3, nearly all of the $5.22 left on the key).
2. The same classification on the 44 partial nuggets (≈ $0.8).
3. Your review of `review.csv` (60 rows; then the partials).
4. An oracle that keeps all cited articles before whole uncited-article documents, or a larger budget, so that
   `oracle_gap` disappears. It is free to build; scoring it costs the same as item 1.
