# A1: token-weighted provision metric — implementation and results

Date: 2026-11-22. Stage 2 of `docs/20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md`
(§3), run on the corpus revised by fix B (`docs/20261122_181611_fix_b_corpus_revision_results.md`). No API calls.

## Summary

- **What was added.**
  - A table of Qwen3 tokens per LexML unit: `segmented/unit_tokens.csv.gz`, 81,179 units in 258 files.
  - A token accounting of every budget-view context against the gold units (`scripts/rag/ragpipe/tokens.py`).
  - Five new metrics at the article and provision levels: `token_recall`, `item_coverage`, `token_precision`,
    `noise_share` and `scaffold_share`. They are written under the new evaluation id
    **`v3_either_containment_merge_skip`** (decision D5), for both embeddings.
  - The old metrics in v3 are identical to `either_containment_merge_skip` (11,255 rows, max |Δ| = 0).
- **Gate passed.** The unit tokens add up to the article chunks. Over 16,054 unsplit articles, prefix + the
  sum of own tokens deviates from `n_tokens_qwen3` by a median of +0.5% and at most 4.8%. None is above 5%.
- **The contexts are mostly not the cited text.** At 4k (jua, provision level):
  - only 7–9% of the tokens are gold text;
  - 62–68% are off-gold content;
  - 25–30% are scaffold (title/ementa prefix, ancestor paths, grouping names).

  The article level is a little cleaner: 11–13% gold. All shares get worse as the budget grows.
- **S2 beats S1 on every token measure, but its article-level gain is mostly fragments.**
  - Provision level, 4k: the token-weighted gain is as large as the binary one. Token recall +0.060 vs full-hit
    recall +0.052 (jua), both p < .001.
  - Article level, 4k: binary recall +0.106, but token recall only **+0.008 (p .15)** with jua and +0.017 with
    Gemini. S2 touches many more cited articles than S1, but with a paragraph or an inciso, not the whole text.
  - S2's noise share is 5–6 points lower than S1's. Its scaffold share is 4–5 points higher: more, smaller
    chunks each repeat the prefix.
- **S3's context-precision advantage was mostly an artefact, as suspected** (granularity note §5, caveat 2).
  - Provision level, S3 − S2: context precision +0.026 at 4k and +0.057 at 16k, but token precision only
    +0.004 and +0.003.
  - S3 has the highest noise share of the S2 family. Its token recall gain is real but small: +0.006 at 4k
    (n.s.), +0.030 at 16k.
- **The caput variants (S2c/S4) have the cleanest contexts**: token precision +0.005 over S2 and +0.006 over S3
  at 4k (p < .001). The caput sentence they carry is often itself the cited text. They do not add scaffold
  against S2 with jua; with Gemini they add about 2 points.
- **Token metrics do not track answer quality better than the binary hit.**
  - Per-question Spearman with V_strict, provision level, mean over runs: full-hit recall 0.169,
    `item_coverage` 0.158, `token_recall` 0.149, `token_precision` 0.034. The binary hit stays the best.
  - In the paired S2 − S1 design (granularity note §4) as well: provision full hit 0.122, `item_coverage`
    0.110, `token_recall` 0.095.
  - Noise does not predict utilisation (ρ ≈ 0.01). Neither does token precision once recall is controlled
    for (partial ρ −0.01).
- **Whole-article questions** (granularity note §3): with graded coverage, S1's lead over S2 shrinks.
  - jua: from 3.3 points (full hit) to 1.5 points (coverage).
  - Gemini: from 1.7 points to 0.3.

  S2 gets partial credit for the paragraphs it delivers. This supports reading 1 of that note: on these
  questions, part of the article is nearly as good as all of it.

## 1. What was built

### 1.1 Unit tokens (`scripts/segmentation/unit_tokens.py`, ≈ 8 s)

A **unit** is an element numbered by `calculaPos`: the 6 dispositivo and 7 grouping types, outside
`Alteracao` (`common.Positions`). The table has one row per unit of every statutory file that has dispositivo,
grouping or DSP chunks. Columns:
- the nested-set interval (`Num_Inicio`, `Num_Final`), the same numbering as the chunk table;
- `own_tokens`: Qwen3 tokens of the unit's own text. This is its `Rotulo`, `TituloDispositivo`, `NomeAgrupador`,
  `p` and `table` elements whose nearest numbered ancestor is the unit, so the text of a quoted `Alteracao`
  belongs to the dispositivo that quotes it. The pieces are joined as the segmentation's `texto` joins them;
- `subtree_tokens`: the unit with all its children, tokenised as one text;
- `subtree_own_sum`: the sum of `own_tokens` over the subtree.

A unit lies inside a chunk iff its `Num_Inicio` is inside the chunk's interval. So the units of a chunk, or of
a gold unit, form one contiguous block of the file's units sorted by start, and every overlap is a slice
of a prefix sum.

Two side outputs:
- `segmented/prefix_tokens.csv`: the tokens of each file's `[ epígrafe | ementa ]` prefix. There is one
  prefix per file (checked).
- `segmented/unit_tokens_report.json`: the checks.

| Check | Result |
|---|---|
| Unit chunks (dispositivo, grouping, DSP) whose interval does not start at a unit | 0 of all |
| Unsplit ART/DSP base chunks: prefix + `subtree_own_sum` vs `n_tokens_qwen3` | 16,054 chunks; relative deviation median +0.5%, p99 +2.0%, min −4.8%, max +4.4%; none above 5%; total +0.38% |
| Same with `subtree_tokens` (one tokenisation) | median +0.5%, max 3.2%; total +0.37% |

The small positive bias comes from token boundaries at the joins. The accounting uses the additive
`own_tokens` and rescales gold + off-gold to the context size when they exceed it (§1.2).

A first run skipped the 28 annexes that hold only loose dispositivos (DSP chunks), because `DSP` was missing
from the chunk-type list. 387 chunks had no unit. This was fixed before any evaluation.

### 1.2 Accounting of a context (`ragpipe/tokens.py`)

What a chunk shows:
- **content**: the units inside its interval;
- **path**: the dispositivo units around it (article label, caput sentence before an inciso, paragraph head),
  plus two more cases:
  - for the S2c/S4 `caput` variant, the caput (`contexto_ids`);
  - for a split-article part, the units its repeated head shows (`parcial_ids`; e.g. the caput sentence
    before paragraphs). These are restricted to the chunk's own article.
- the file prefix;
- TXT/TAB chunks (non-statutory text, loose annex content) have no units: they hold a prefix and off-gold
  content.

The tokens `T` of a context (the `n_tokens_qwen3` of the selected texts, as in `context_precision`) are
split into three parts:

| Part | Definition |
|---|---|
| gold | own tokens of the distinct gold units visible as content **or on a path**, each counted once |
| off-gold | own tokens of the distinct non-gold dispositivo units in the content, plus the text of unit-less chunks |
| scaffold | `T − gold − off-gold`: prefixes, grouping names, path text outside the gold, repeated text |

Gold + off-gold are rescaled to `T` when the sum of own tokens exceeds it (the +0.4% bias), so the three
shares always add up to 1.

Per gold item:
- `coverage` = visible own tokens of the item's subtree ÷ its own tokens;
- when the item has several candidate units, the best one is used. This happens with the annex rule `either`
  (main file and annex) and with repeated article ids, the same "any" logic as the hit;
- `gold_tokens` (the size used to weight items) = the largest candidate.

Per question:
- `token_recall` = Σ coverage·size ÷ Σ size;
- `item_coverage` = the mean coverage over items;
- the context shares are `gold / T`, `off-gold / T` and `scaffold / T`.

Items with no LexML unit have no size and are left out of the token metrics. Per strategy, that is 46 of
2,230 provision items (no LexML id) and 11 of 1,958 article items (article not in the LexML).

**Deviations from the plan's definitions (§3.3), all deliberate:**
1. **Path text is credited to the gold.** The plan counted all ancestor-path text as scaffold. But when the
   gold is a caput and the context holds its inciso I, the caput sentence printed before the inciso *is*
   the cited text, and the generator sees it. Counting it once as gold makes "S2 rebuilt the caput from its
   incisos" a full coverage, the same as the CPT chunk itself. Path text outside the gold, and every
   repetition, stays scaffold.
2. **Grouping names are scaffold** (as in the plan), but the article label is part of the article's own text,
   so it is gold when the article is.
3. **Split leaves.** When one leaf is cut into pieces (72 split articles have parts that share a unit), each
   piece gets an equal share of the leaf's tokens. Two pieces in one context cover it fully.

### 1.3 Pipeline changes

- `rag.py evaluate --token-metrics` (`EvalConfig.token_metrics`): default id
  `v3_<annex_rule>_<dedup>_<overflow>`. Without the flag, nothing changes: same columns, same config hash.
- `per_item.csv.gz` gets `gold_tokens` and `budget_cov_<B>`. `per_question.csv.gz`, `metrics.csv` and
  `comparisons.csv` get the five metrics (budget view, article and provision levels; the three context
  shares for gold = all and slice = all only). `report.md` gets a §8 with them.
- `Paths.unit_tokens` and `Paths.prefix_tokens` are read next to `--chunks`. The chunk loader reads
  `contexto_ids`.
- Runtime: ≈ 100 s per embedding, against ≈ 30 s before (the accounting is per question × strategy × level ×
  budget).
- Tests: `scripts/rag/tests/test_tokens.py` (7 tests).
  - Hand-computed accounting on a small nested corpus: inciso with its path, caput variant, repeated head of a
    split part, leaf pieces, grouping and non-statutory chunks, rescaling.
  - A smoke test checks that v3 leaves the old metrics unchanged and that the shares sum to 1.
  - All 53 rag tests pass.

### 1.4 Consistency with the binary hits (jua, all budgets, both levels)

- No coverage above 1.
- No item with coverage 0 that is hit, at any budget.
- Coverage > 0 without a hit: 0–3 items per budget, all S2c/S4 caput items. The caput sentence reaches the
  context only inside a paragraph chunk (the variant's purpose), which the binary matcher does not count.
- Provision items fully hit with coverage < 0.99: none, except 1 at 16k.
- Items with full coverage but no full hit: 3–6 per budget. For example, S2 retrieves every caput and
  paragraph chunk of art. 10 of Lei 9.250 but not the ART chunk. The text is all there, but the binary rule
  wants the article chunk.

## 2. Results: what the contexts hold

jua-4b-mixed, provision level, all gold (`noise_signal.csv`; Gemini is in the same file and shows the same
pattern):

| Metric | Strategy | 1k | 2k | 4k | 8k | 16k |
|---|---|---:|---:|---:|---:|---:|
| full-hit recall | S1 | 0.178 | 0.265 | 0.369 | 0.468 | 0.541 |
| | S2 | 0.219 | 0.311 | 0.420 | 0.524 | 0.598 |
| | S3 | 0.224 | 0.321 | 0.429 | 0.536 | 0.632 |
| token recall | S1 | 0.179 | 0.271 | 0.376 | 0.481 | 0.558 |
| | S2 | 0.233 | 0.333 | 0.436 | 0.542 | 0.621 |
| | S2c | 0.233 | 0.330 | 0.440 | 0.541 | 0.618 |
| | S3 | 0.237 | 0.343 | 0.442 | 0.551 | 0.651 |
| | S4 | 0.236 | 0.339 | 0.450 | 0.554 | 0.642 |
| context precision (binary) | S1 | 0.158 | 0.153 | 0.122 | 0.084 | 0.053 |
| | S2 | 0.198 | 0.174 | 0.136 | 0.097 | 0.063 |
| | S3 | 0.204 | 0.200 | 0.162 | 0.144 | 0.119 |
| token precision | S1 | 0.098 | 0.092 | 0.069 | 0.047 | 0.030 |
| | S2 | 0.113 | 0.101 | 0.076 | 0.052 | 0.033 |
| | S2c | 0.125 | 0.108 | 0.081 | 0.055 | 0.034 |
| | S3 | 0.115 | 0.105 | 0.079 | 0.056 | 0.036 |
| | S4 | 0.126 | 0.111 | 0.085 | 0.058 | 0.036 |
| noise share | S1 | 0.593 | 0.641 | 0.680 | 0.708 | 0.730 |
| | S2 | 0.507 | 0.572 | 0.623 | 0.659 | 0.684 |
| | S2c | 0.487 | 0.563 | 0.621 | 0.661 | 0.687 |
| | S3 | 0.512 | 0.582 | 0.640 | 0.693 | 0.726 |
| | S4 | 0.494 | 0.576 | 0.638 | 0.693 | 0.729 |
| scaffold share | S1 | 0.310 | 0.267 | 0.251 | 0.245 | 0.240 |
| | S2 | 0.380 | 0.327 | 0.301 | 0.288 | 0.283 |
| | S2c | 0.388 | 0.329 | 0.299 | 0.284 | 0.279 |
| | S3 | 0.374 | 0.312 | 0.280 | 0.251 | 0.238 |
| | S4 | 0.380 | 0.314 | 0.276 | 0.249 | 0.234 |

Article level, 4k (jua / Gemini):

| | S1 | S2 | S2c | S3 | S4 |
|---|---:|---:|---:|---:|---:|
| article recall (binary) | 0.398 / 0.413 | 0.503 / 0.515 | 0.480 / 0.511 | 0.507 / 0.517 | 0.487 / 0.517 |
| token recall | 0.344 / 0.371 | 0.352 / 0.388 | 0.366 / 0.398 | 0.361 / 0.405 | 0.378 / 0.409 |
| token precision | 0.108 / 0.118 | 0.115 / 0.129 | 0.122 / 0.134 | 0.119 / 0.134 | 0.127 / 0.138 |
| noise share | 0.642 / 0.671 | 0.586 / 0.625 | 0.583 / 0.602 | 0.602 / 0.636 | 0.599 / 0.617 |

Paired comparisons (`comparisons.csv`, 10,000 resamples; jua unless stated):

| Comparison | Level, budget | Binary | Token-weighted |
|---|---|---|---|
| S1 → S2 | article, 4k | recall **+0.106** [0.083, 0.130] | token recall +0.008 [−0.003, 0.019], p .15; item coverage +0.003, p .58 |
| S1 → S2 | article, 4k, Gemini | recall +0.103 | token recall +0.017 [0.006, 0.028] |
| S1 → S2 | article, 16k | recall +0.100 | token recall +0.033 [0.022, 0.044] |
| S1 → S2 | provision, 4k | recall +0.052 [0.032, 0.073] | token recall **+0.060** [0.040, 0.080]; noise −0.057; scaffold +0.051 |
| S2 → S3 | provision, 4k | context precision +0.026 | token precision +0.004 [0.000, 0.007]; noise +0.017 |
| S2 → S3 | provision, 16k | context precision +0.057 | token precision +0.003; token recall +0.030 [0.017, 0.044] |
| S2 → S2c | provision, 4k | context precision +0.009 | token precision +0.005 [0.002, 0.008]; token recall +0.004, n.s. |
| S3 → S4 | provision, 4k | context precision +0.008 | token precision +0.006 [0.003, 0.010] |

**Reading.**
1. **Noise.** Two-thirds of a 4k context is text about something else, and a quarter is scaffold. As
   expected, S1 has the most noise: a whole article for one inciso. The plan expected S3 to be about as
   noisy as S1. It is not: S3 sits between S2 and S1, because only 58% of its contexts hold a grouping chunk
   (granularity note §5).
2. **The highest signal ratio is in S2c/S4, not S2.** The plan expected S2c/S4 to "show the cost of their
   scaffold". With jua that cost is cancelled: the caput sentence is gold whenever the caput is cited, and
   the variants' contexts hold fewer texts (11.5 vs 12.4 at 4k), hence fewer prefixes.
3. **Scaffold is the price of self-contained chunks**, and it falls with the budget. At 1k a third of an S2
   context is prefix and path. The ementa prefix (up to 128 tokens per chunk) is most of it.
4. **The article-level S1 → S2 gain is about breadth, not depth.** The binary article recall counts a
   paragraph of the article as a hit. S2 reaches more cited articles, but delivers about as much of their text
   as S1 at 4k. The provision level, where the gold is the cited unit itself, is the fair level for S2.
5. **S3's high context precision is an artefact of the binary rule**: a 3,000-token chapter that holds a
   40-token gold inciso counts as relevant in full. Token-weighted, S3 ≈ S2 at 4k. At 16k S3's real advantage
   is recall (+0.03), not precision.

## 3. Do token metrics track answer quality? (§3.5 analysis 2)

`scripts/report/a1_token_metrics.py` (4 s), outputs in
`nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/token_metrics/`. The runs are every answer run with
a retrieval context (jua S1/S2 at 2k/4k/8k; S2c/S3/S4 at 4k; Gemini S1/S2 at 4k; 4 generators where they
exist): 40 runs per level (the 2k/8k grid covers fewer generators). Judge Gemini 3.8 Flash, primary set.

**(a) Levels: Spearman over questions within a run, mean over runs** (`spearman_levels.csv`):

| Metric (provision level) | ~ answer V_strict | ~ context's own nugget support | ~ answer utilisation |
|---|---:|---:|---:|
| full-hit recall | **0.169** | 0.115 | 0.090 |
| partial (any) recall | 0.149 | 0.113 | **0.123** |
| token recall | 0.149 | 0.102 | 0.074 |
| item coverage | 0.158 | **0.122** | 0.114 |
| context precision (binary) | 0.125 | **0.189** | 0.029 |
| token precision | 0.034 | 0.110 | 0.009 |
| noise share | 0.072 | 0.021 | 0.011 |
| token precision, partial on token recall | −0.073 | — | −0.011 |

- Utilisation is the share of the context-supported nuggets that the answer supports, per question.
- Per generator, V_strict ~ full-hit recall / item coverage: Luna 0.184 / 0.172, Terra 0.170 / 0.186,
  Sabiá-4 0.149 / 0.132, Sabiazinho-4 0.174 / 0.145.
- At the article level the ordering is the same (full hit 0.160, coverage 0.147, token recall 0.098).

The precision rows are **confounded by gold size**. Token precision rises with the gold's size (ρ = 0.45 with
the question's gold tokens, S2 4k): a question citing three long articles fills more of any context with
gold. Questions with large gold have more nuggets and are not easier. This is why the cross-question
correlation of precision is near zero, or negative once recall is held fixed. The paired design below
removes that confound.

**(b) Gains: the granularity note §4 design** (`spearman_gains.csv`). Per question, the S2 − S1 retrieval gain
at 4k against the S2 − S1 V_strict gain. Spearman, mean over the 4 generators (jua; `none` excluded):

| Group (n) | article recall | prov. full hit | prov. any hit | token recall | item coverage | token precision | context precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| all (551) | 0.074 | **0.122** | 0.112 | 0.095 | 0.110 | 0.090 | 0.077 |
| whole_only (186) | 0.090 | 0.026 | **0.091** | 0.046 | 0.071 | 0.045 | 0.043 |
| sub_only (130) | 0.038 | **0.126** | 0.124 | 0.094 | 0.122 | 0.110 | 0.087 |
| mixed (235) | 0.100 | **0.157** | 0.123 | 0.124 | 0.129 | 0.104 | 0.086 |

Gemini (2 generators): all 0.085 (full hit) vs 0.083 (item coverage) vs 0.067 (token recall).

**Reading.**
- **No token metric beats the binary full hit as a predictor of answer quality**, in levels or in gains. All
  the correlations are weak (≤ 0.19), as in the granularity note.
- Item coverage is the best of the token metrics, close to the full hit. Token recall (size-weighted) is
  worse: large gold items dominate it, and their partial delivery matters little to the answer.
- **Noise does not measurably hurt the generators.** Neither noise share nor token precision predicts
  utilisation, before or after controlling for recall. The generators use what is in the context about as
  well whether it is 5% or 15% of the tokens. Utilisation does differ between strategies (phase 5, e.g.
  Terra 0.65 with S2 against 0.51–0.55 with S3/S4 at 4k), but per question that difference does not follow the
  noise share.
- Binary context precision correlates best with the **context's** own nugget support (0.19). The
  context-support judge labels nuggets as supported by passages; a context with more passages near the
  gold supports more nuggets. Token precision, which counts only the cited unit itself, does so less (0.11).
- On whole-article questions, coverage (0.071) sits between the full hit (0.026) and the any hit (0.091).
  This confirms the granularity note's corrected statement: for these questions partial retrieval counts.

## 4. Whole vs sub-article questions with graded coverage (§3.5 analysis 3)

Provision items, statutory, per-question mean, 4k (`coverage_by_group.csv`; question groups as in the
granularity note §3):

| Embedding | Group | S1 full / coverage | S2 full / coverage | S3 full / coverage | S2 − S1, full → coverage |
|---|---|---|---|---|---|
| jua | whole_only (187) | 0.444 / 0.459 | 0.411 / 0.444 | 0.427 / 0.455 | −0.033 → **−0.015** |
| jua | sub_only (130) | 0.410 / 0.416 | 0.580 / 0.587 | 0.590 / 0.597 | +0.170 → +0.171 |
| jua | mixed (235) | 0.299 / 0.306 | 0.353 / 0.372 | 0.355 / 0.373 | +0.054 → +0.066 |
| Gemini | whole_only | 0.437 / 0.465 | 0.420 / 0.462 | 0.461 / 0.489 | −0.017 → **−0.003** |
| Gemini | sub_only | 0.450 / 0.455 | 0.597 / 0.603 | 0.605 / 0.611 | +0.147 → +0.148 |
| Gemini | mixed | 0.307 / 0.320 | 0.371 / 0.394 | 0.379 / 0.396 | +0.064 → +0.073 |

- On whole-article questions, S1's retrieval advantage under the strict rule shrinks to 1.5 points (jua) or
  vanishes (Gemini) once S2's partial delivery of those articles gets graded credit. That is about S2's
  coverage of whole articles. Measured by coverage, S2 delivers 97–99% of what S1 delivers on these
  questions; under the strict full hit it gets 93–96% of S1's value.
- On sub-article questions nothing changes: the units are small, so coverage ≈ full hit.
- The asymmetry of the granularity note becomes sharper. S2 is far ahead where citations are fine-grained
  (+15–17 points) and level with S1 where they are coarse. On whole-article questions the answers were already
  tied (granularity note §3), and graded coverage now agrees with that.

## 5. Implications for the paper

1. **Report the provision level as the primary retrieval level, with token recall next to it.** The binary
   article recall overstates S2's advantage (+0.106 at 4k, against +0.008 token-weighted). The binary context
   precision overstates S3's (+0.026, against +0.004). Both are artefacts of counting a chunk as wholly
   relevant or wholly irrelevant.
2. **The cleanest description of the strategies' trade-off is the three-way token split.**
   - S1: high noise, low scaffold.
   - S2: −5 points of noise, +5 points of scaffold, +6 points of gold coverage at the provision level.
   - S3: S2 plus grouping chunks that raise recall at large budgets and raise noise.
   - S2c/S4: the best signal ratio.
3. **Do not claim that "less noise → better answers".** The data do not support it: noise does not predict
   answer quality or utilisation once recall is fixed. The S2 > S1 answer gain is explained by delivering the
   cited unit (provision coverage), not by cleaner contexts.
4. **For the remaining plan.**
   - A2 can reuse `unit_tokens` to weight a cited provision against the gold.
   - The A3 (Sol) contexts are the same as Terra's, so the token tables need no rerun for it.

## 6. Files and reproduction

| Path | Status |
|---|---|
| `scripts/segmentation/unit_tokens.py` | new: unit-token builder and its check |
| `segmented/unit_tokens.csv.gz` (0.9 MB, byte-deterministic), `prefix_tokens.csv`, `unit_tokens_report.json` | new |
| `scripts/rag/ragpipe/tokens.py`, `tests/test_tokens.py` | new |
| `scripts/rag/ragpipe/evaluation.py`, `report.py`, `data.py`, `rag.py` | `--token-metrics`, report §8, `Paths.unit_tokens`, `contexto_ids` |
| `runs/retrieval/{jua-4b-mixed,gemini-emb-2}/irpf/eval/v3_either_containment_merge_skip/` | new evaluation (manifests, metrics, comparisons, reachability, report in git; per-question and per-item tables gitignored) |
| `scripts/report/a1_token_metrics.py` → `nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/token_metrics/` | analyses §2–4 |
| `scripts/report/build_dashboard_data.py`, `docs/dashboard/index.html` | the dashboard reads v3. The retrieval tab offers the five metrics (budget chart and comparisons) with their definitions. Trace and explorer data rebuilt on v3 (same values) |

```bash
.venv/bin/python scripts/segmentation/unit_tokens.py                      # ≈ 8 s, after segment_all.py
for e in jua-4b-mixed gemini-emb-2; do
  .venv/bin/python scripts/rag/rag.py evaluate --retrieval runs/retrieval/$e/irpf --token-metrics   # ≈ 100 s each
done
.venv/bin/python scripts/report/a1_token_metrics.py                       # ≈ 4 s
```

**Not done:**
- The HF release of these outputs. Repo A gets `segmented/unit_tokens.csv.gz` and `prefix_tokens.csv`; repo B
  gets the v3 evaluations and the analysis tables. Planned for stage 6 together with A2/A3 (plan §6), unless
  wanted earlier.
- The `irpf_with_rir1999` ablation was not re-evaluated with token metrics.

## 7. Next

Stage 3 of the plan: **A2, in-text legal citations**, closed book of the 4 current generators first
(`docs/20261122_134404_in_text_legal_citation_scoring_plan.md`). Its gate is a manual check of 100–150
citations with ≥ 95% correct attribution. Stage 0 (new OpenRouter key, credit check, decisions D2–D3) is still
needed before A3.
