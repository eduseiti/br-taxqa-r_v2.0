# Retrieval scoring across granularities, and its link to answer quality

Date: 2026-11-22. Discussion note (no code changes, no API calls). Covers:

- how the legal-provision retrieval test (`scripts/rag/ragpipe/relevance.py`, `evaluation.py`) scores
  chunks whose granularity differs from the gold reference's;
- an ad hoc check of whether citation granularity explains the S1 vs S2 difference in answer quality
  (nugget phase 5 scores);
- how S3's grouping chunks fare under the same rules.

All retrieval numbers come from the **main evaluation `either_containment_merge_skip`**, with
parent/child merging, the setting the generator contexts use. A first version of this note used
`v2d_either_containment_skip` (containment only, no merge). That overstated S1's lead on whole-article
citations. The conclusions do not change. The answer results never depended on the evaluation, since
they come from the merged contexts.

## Summary

1. **S1 chunks against sub-article references.** A whole-article S1 chunk is a **full hit** for any
   unit inside the article (G5: its `cobre_ids = [artN]`, an ancestor of every unit in it). The
   exception is an oversize article split into parts: each part fully hits only the units it holds.
   The article itself is then fully hit only when all parts are in the context (`Match.parts`). So S1 is
   not penalised by the hit definition. Its cost shows up through the token budget (fewer distinct
   articles fit) and in context precision.
2. **S2 at the article level vs the provision level.** The two levels are scored differently.
   - **Article level (G2):** any chunk of the article (ART, caput, paragraph, inciso…) is a full hit.
   - **Provision level (G5):** a full hit needs a chunk that contains the cited unit (the unit, an
     ancestor, a grouping chunk, or all parts of a split article). Descendant chunks are only
     **partial** hits (`budget_any_*`).

   So for a **whole-article** citation at the provision level, only the S2 ART chunk (or all its parts)
   counts as full. S2's sub-unit chunks count only as "any" hits.
3. **Retrieval numbers** (jua-4b-mixed, `irpf`, budget 4000):

   | Gold items | S1 | S2 |
   |---|---|---|
   | Provision, sub-article (820), full | 0.287 | **0.406** |
   | Provision, whole-article (1377), full | **0.257** | 0.234 |
   | Provision, whole-article, any | 0.266 | **0.295** |
   | Article level (1958) | 0.279 | **0.357** |

   The S1/S2 ordering flips between the article level and the strict provision level for
   whole-article citations.
4. **Effect on answer quality (questions grouped by citation granularity).** Of the 596 questions
   with legal references: 187 cite only whole articles, 130 only sub-article units, 235 a mix, 44
   no statutory provision. The retrieval premise holds in both pure groups. **Only half of the hypothesis holds for answers:**
   - *Sub-article questions:* S2 > S1 for 5 of the 6 generator/embedding pairs. Significant only for
     gpt-5.6-luna with jua (+0.077 V_strict, CI [0.02, 0.14]).
   - *Whole-article questions:* S1 never wins. The answer difference is ≈ 0, although S1 gets the
     whole cited article into the context somewhat more often (+3.3 points per question with jua).

   The result is **asymmetric, not a crossover**: finer chunks help when the citation is fine-grained
   and cost nothing when it is coarse. The grouping ignores document-level references. Dropping the
   questions that cite a document without any article (§3 robustness check) gives the same picture,
   with wider CIs.
5. **Most likely explanation (reason 1, untested):** the gold answer rarely needs the whole article.
   One or two paragraphs suffice, and S2 retrieves them. Supporting this weakly: per question, the strict provision full hit has
   almost no relation to answer gains on whole-article questions (Spearman 0.02). Metrics that also count
   partial retrieval (article level, provision "any") give the same weak signal (≈ 0.09). An earlier
   broader claim, that the article level generally predicts answer quality better than the provision
   level, was **checked and is wrong**: across all questions the provision metrics are slightly
   better. All per-question correlations are weak (≤ 0.25).
6. **S3 (S2 + grouping chunks).** S3 does **not** retrieve better at the document level: ≈ S2 or
   slightly worse at every budget. It gains where a grouping chunk fully contains what was cited:
   - whole-article provision: +0.02 over S2 at 4000, +0.06 at 16000;
   - article level: +0.01 at 4000, +0.03 at 16000.

   Grouping chunks seldom fail to fit (9% of those in the top 10 exceed 4000 tokens). The real cost is
   crowding out: when one is in the context (58% of the questions at 4000), it takes 32% of the tokens.
   The hit rule and context precision are both generous to S3. Answers were generated only at 4000,
   where S3 ≈ S2.
7. **Open next steps:** (a) add the granularity grouping as a slice in `nuggets.py analyze`
   (`slices_comparisons.csv`, with permutation p and cluster CIs); (b) test reason 1 directly. For
   whole-article questions, check whether S2's partial chunks contain the paragraphs that support the
   gold nuggets (`ctxsupport` tables); (c) a token-weighted hit, which would remove the generosity
   towards S1 (§1) and S3 (§5).

## 1. How S1 chunks are scored against sub-article references

Matching rule G5 (`relevance.py`, module docstring and `_match_provision`). A provision-level gold
item is a LexML id (`art5`, `art5_par2`, `art5_par2_inc3`…). Every chunk carries `cobre_ids` (units it
holds whole) and `parcial_ids` (units it holds in part). A chunk is:

- a **full hit** if some `cobre_ids` id equals the gold id or is its ancestor (`_is_prefix(c, frag)`),
  or if it is a grouping chunk whose interval contains the unit;
- a **partial hit** if the gold id is an ancestor of something in `cobre_ids` (the chunk holds only a
  piece of the unit), or appears in `parcial_ids`.

An unsplit S1 article chunk has `cobre_ids = [artN]` and so fully hits every unit of the article.

**Split articles** (`scripts/segmentation/split_oversize.py`, `part_provenance`). Each part lists in
`cobre_ids` only the whole items it holds (e.g. `art1_par2`). The article id and the ancestors of
items cut inside the part go to `parcial_ids`. Hence:

- a sub-article unit is fully hit only by the part that contains it;
- a whole-article citation is only partially hit by each part. It becomes a full hit when **all**
  parts of one file are retrieved (the G5 refinement, `Match.parts`, `rank_cover` in
  `evaluation.evaluate_strategy`). This is the `reachable_by_parts_only` column: 1.2% of S1
  sub-article items, 11.9% of whole-article items in S1/S2, 4.6% in S3/S4 (where grouping chunks can
  also contain the article).

This is the mirror of S2 against article-level references (G2): neither strategy is penalised for
its granularity in the hit definition. The differences come from the budget: an S1 article spends
many more tokens to deliver the same inciso, so fewer distinct articles fit, and context precision
drops.

Sub-article slice, provision level (820 items), budget 4000:

| Strategy | reachable | full hit | any hit |
|---|---|---|---|
| S1 | 0.994 | 0.287 | 0.293 |
| S2 | 0.994 | **0.406** | 0.412 |
| S3 | 0.994 | 0.407 | 0.413 |
| S2c | 0.994 | 0.380 | 0.387 |
| S4 | 0.994 | 0.373 | 0.380 |

S1's reachability equals S2's. It loses about 12 points in the budget view because whole articles
crowd each other out, and possibly because a long article's embedding is diluted relative to a
focused paragraph.

Caveat: "hit" means "the right text is somewhere in the context", not "it is easy to find there".
`context_precision` (gold tokens / context tokens) captures part of this. A token-weighted
provision hit (unit tokens / chunk tokens) would make it explicit but is not implemented.

## 2. How S2 is scored at the article level vs the provision level

**Article level** (G2, `_match_article`). The gold item is `(document_id, article_id)`. Every chunk
whose `(arquivo, artigo_id)` matches is a full hit: ART, caput, any paragraph, inciso or alínea. In
S3/S4, a grouping chunk containing the article also counts. There is no partial hit at this level.
The rank is that of the first chunk of the article. This is the only level (with the document level)
that has the `unit` view, where the ranking is collapsed to distinct articles.

**Provision level** (G5). For a whole-article citation (`art5`):

- the ART chunk is a full hit;
- if the article was split, it is a full hit only once **all** parts are in the context;
- in S3/S4 a grouping chunk containing the article is a full hit;
- `art5_par2`, `art5_cpt_inc1`… chunks are partial hits only. They count in `hit_any`
  (`budget_any_*`), not in `hit_full`.

So yes: for the headline (full) metric, only the position of the whole-article chunk (or its full set
of parts, or a grouping chunk) is scored.

Budget 4000. The whole-article rows use a rough filter (provision items with `sub_article = False`
whose key contains "art"):

| Strategy | Provision, whole-article: full | Provision, whole-article: any | Article level |
|---|---|---|---|
| S1 | **0.257** | 0.266 | 0.279 |
| S2 | 0.234 | 0.295 | 0.357 |
| S2c | 0.245 | 0.300 | 0.347 |
| S3 | 0.253 | 0.307 | **0.365** |
| S4 | **0.271** | **0.318** | 0.356 |

At the article level S2 beats S1 by ~8 points. At the provision level, whole-article citations, S2 is
below S1 on full hits (by 2.3 points): its sub-unit chunks often outrank the ART chunk and use up budget
without fully covering the cited unit. On "any" hits S2 is ahead again, by 3 points. S3/S4 recover the
full-hit gap through grouping chunks that contain the whole article (§5).

The two levels ask different questions. The article level asks whether the system found the right
article. The provision level asks whether it delivered the whole cited unit. For whole-article
citations the latter is strict by design and favours S1. Suggested reporting: article level for
article-level citations, provision level for sub-article citations, and whole-article
provision results with both full and any. A further source of uncertainty: some "art. 5º"
references may really point at one paragraph but were annotated at article level.

## 3. Does citation granularity explain the S1 vs S2 answer difference?

**Hypothesis.** Retrieval favours S1 for whole-article citations and S2 for sub-article ones, so
answers should follow: S1 better on questions citing only whole articles, S2 on questions citing
only sub-article units.

**Method.**

- Questions are grouped by their statutory provision-level gold items (S1 rows of `per_item.csv.gz`;
  the grouping is the same in every evaluation):
  - `whole_only`: all such items have `sub_article = False`;
  - `sub_only`: all have `sub_article = True`;
  - `mixed`: both kinds;
  - `none`: no statutory provision item.

  Counts (all / without documents cited with no article): whole_only 187 / 121, sub_only 130 / 98,
  mixed 235 / 130, none 44 / 3. The remaining 119 of the 715 questions have no gold legal reference
  in the eval. The numbers below use the "all" grouping.
- Answer quality: per-question V_strict from
  `nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/per_question.csv.gz`, contexts
  `S1_budget4000` vs `S2_budget4000` (and `…@gemini-emb-2`). Paired difference per question, mean,
  percentile bootstrap CI (5000 resamples, seed 0; not cluster-aware).

**Retrieval premise** (provision full-hit recall at 4000, per-question mean):

| Group | jua S1 | jua S2 | gemini S1 | gemini S2 |
|---|---|---|---|---|
| whole_only | **0.444** | 0.411 | **0.437** | 0.420 |
| sub_only | 0.410 | **0.580** | 0.450 | **0.597** |
| mixed | 0.299 | **0.353** | 0.307 | **0.371** |

The premise holds in both directions, but asymmetrically. S2's lead on sub-article questions
(+15–17 points) is much larger than S1's on whole-article ones (+2–3 points).

**Answer quality: V_strict difference, S2 − S1, with 95% bootstrap CI.** gemini-emb-2 answers exist only for
gpt-5.6-luna and sabia-4:

| Generator | whole_only (n=186) | sub_only (n=130) | mixed (n=235) |
|---|---|---|---|
| gpt-5.6-luna, jua | −0.009 [−0.05, 0.03] | **+0.077 [0.02, 0.14]** | +0.024 [−0.01, 0.06] |
| gpt-5.6-terra, jua | −0.003 [−0.04, 0.03] | +0.017 [−0.05, 0.08] | +0.018 [−0.01, 0.05] |
| sabia-4, jua | −0.004 [−0.05, 0.04] | +0.035 [−0.01, 0.08] | +0.022 [−0.01, 0.05] |
| sabiazinho-4, jua | −0.004 [−0.04, 0.03] | −0.015 [−0.07, 0.04] | −0.003 [−0.03, 0.03] |
| gpt-5.6-luna, gemini | +0.031 [−0.02, 0.08] | +0.042 [−0.01, 0.09] | +0.024 [−0.01, 0.06] |
| sabia-4, gemini | +0.011 [−0.02, 0.05] | +0.015 [−0.04, 0.07] | −0.020 [−0.06, 0.02] |

(`none`, n=44: noisy; sabia-4/jua +0.095 [0.02, 0.18].)

**Reading.**

- Sub-article questions: S2 ahead for 5 of the 6 generator/embedding pairs, significant for one.
  These questions carry a good share of the overall S2 > S1 gain.
- Whole-article questions: S1 never wins. Its retrieval advantage on full hits there is small
  (+3.3 points with jua), and S2 leads on "any" hits.
- Mixed: in between, near the overall average (+0.02).

Possible reasons for the whole-article result:

1. the gold answer rarely needs the whole article: one or two paragraphs suffice, and S2 retrieves
   them (its "any" hit rate there is higher than S1's);
2. some whole-article annotations really point at a specific paragraph;
3. a full S1 article uses budget that S2 spends on other relevant material;
4. S1's full-hit advantage is small to begin with.

**Document-level references.** The grouping uses only statutory provision-level items. Document-level
references are ignored, and so are the 25 non-statutory provision items. Every article citation also
yields a document item for its document, so the only signal the grouping misses is a document cited
**without** any article (e.g. a whole IN). A question with such a document plus whole-article
citations is still `whole_only`. `none` holds the questions with only whole documents and/or
non-statutory references. Such documents occur in 66 whole_only, 32 sub_only and 105 mixed questions.

**Robustness check: without those questions** (the "pure" grouping: whole_only 121, sub_only 98,
mixed 130). Retrieval gaps widen. Provision full hit at 4000, S1 / S2:

| Group | jua S1 | jua S2 | gemini S1 | gemini S2 |
|---|---|---|---|---|
| whole_only | **0.534** | 0.490 | **0.538** | 0.510 |
| sub_only | 0.464 | **0.635** | 0.537 | **0.665** |
| mixed | 0.382 | **0.433** | 0.383 | **0.438** |

V_strict difference, S2 − S1 [95% CI]:

| Generator | whole_only (n=121) | sub_only (n=98) | mixed (n=130) |
|---|---|---|---|
| gpt-5.6-luna, jua | −0.022 [−0.07, 0.02] | +0.058 [−0.00, 0.12] | +0.033 [−0.01, 0.08] |
| gpt-5.6-terra, jua | +0.002 [−0.04, 0.04] | +0.003 [−0.07, 0.08] | +0.030 [−0.02, 0.08] |
| sabia-4, jua | −0.011 [−0.06, 0.04] | +0.047 [−0.01, 0.11] | +0.022 [−0.02, 0.06] |
| sabiazinho-4, jua | −0.021 [−0.07, 0.03] | +0.006 [−0.06, 0.07] | −0.005 [−0.05, 0.04] |
| gpt-5.6-luna, gemini | +0.044 [−0.02, 0.11] | +0.050 [−0.01, 0.12] | +0.040 [−0.01, 0.09] |
| sabia-4, gemini | +0.011 [−0.04, 0.06] | +0.028 [−0.04, 0.09] | −0.029 [−0.08, 0.02] |

Same conclusion, with wider CIs:
- Sub_only: S2 is ahead for all 6 pairs, none clearly above zero (luna/jua is borderline).
- Whole_only, jua: 3 of the 4 generators lean slightly towards S1 (−0.01 to −0.02), all CIs including
  zero. With gemini-emb-2 the difference is positive again.

Reproduce with the appendix script and `--pure`.

**Implication for the paper.** The effect is asymmetric, not a crossover: fine-grained chunks help on
fine-grained citations and cost nothing on coarse ones. That is a stronger argument for S2 than the
overall average alone. The subgroups (130–186 questions) are small, so only one cell clears zero.

## 4. Which retrieval metric tracks answer gains? (checking a claim)

In the discussion, reason 1 led to the claim that "the article level predicts answer quality better
than the strict provision level". That claim was based only on the aggregate orderings (article level: S2 > S1
and answers S2 ≥ S1; strict provision, whole-article: S1 > S2 but answers tied). It was then
checked per question. For each question: the retrieval gain S2 − S1 under three metrics, against the
answer gain S2 − S1 in V_strict. Spearman correlation, jua, budget 4000, mean over the 4 generators:

| Questions | Article | Provision full | Provision any |
|---|---|---|---|
| all (551) | 0.077 | 0.124 | 0.114 |
| whole_only (186) | 0.091 | **0.024** | 0.092 |
| sub_only (130) | 0.038 | 0.126 | 0.124 |
| mixed (235) | 0.100 | 0.158 | 0.125 |

Per generator, all (article / prov. full / prov. any): luna 0.076 / 0.150 / 0.108; terra 0.063 /
0.095 / 0.108; sabia-4 0.073 / 0.144 / 0.110; sabiazinho-4 0.095 / 0.106 / 0.129. Whole_only, provision
full: luna 0.235, terra −0.127, sabia-4 −0.022, sabiazinho-4 0.011.

- **The general claim is wrong:** over all questions the article level tracks answer gains worse
  than the provision metrics.
- **A narrow version holds:** on whole-article questions the strict full hit has almost no relation to
  answer gains, while counting partial retrieval restores the weak signal. This fits reason 1:
  for these questions, part of the article is about as useful as all of it. It is not consistent across
  generators, though: gpt-5.6-luna shows the opposite (0.235).
- All correlations are weak (≤ 0.25) and vary by generator. Per-question answer differences are noisy:
  many questions have identical retrieval under both strategies but different answers (generator
  variance, judge noise). So this is a hint, not evidence.

Corrected statement: *for whole-article citations, the strict provision hit does not track answer
quality on average, while metrics that also count partial retrieval do, weakly.*

## 5. S3: grouping chunks under the same rules

S3 = S2 + chunks for each grouping (parte, livro, título, subtítulo, capítulo, seção, subseção),
holding the whole grouping's text. Groupings above 8,192 tokens were not emitted
(`groupings_over_limit.csv`). Grouping chunks are never split into parts.

**How they are scored.** A grouping chunk is a hit at every level for everything inside it:

- document level: its document;
- article level: every article whose interval it contains (G2);
- provision level: every unit it contains, as a **full** hit (G5).

**Retrieval by level** (jua, budget view, full hit; whole-article = all provision items with
`sub_article = False`, so these numbers differ slightly from §2's filtered ones):

| Gold items | Budget | S1 | S2 | S3 | S3 − S2 |
|---|---|---|---|---|---|
| Document | 1000 / 4000 / 16000 | 0.298 / 0.503 / 0.708 | 0.395 / 0.575 / 0.752 | 0.392 / 0.568 / 0.744 | −0.003 / −0.007 / −0.008 |
| Article | 1000 / 4000 / 16000 | 0.126 / 0.279 / 0.450 | 0.211 / 0.357 / 0.528 | 0.213 / 0.365 / 0.560 | +0.002 / +0.008 / +0.032 |
| Provision, whole article | 1000 / 4000 / 16000 | 0.119 / 0.251 / 0.395 | 0.091 / 0.228 / 0.377 | 0.095 / 0.248 / 0.438 | +0.004 / +0.020 / +0.061 |
| Provision, sub-article | 1000 / 4000 / 16000 | 0.110 / 0.287 / 0.506 | 0.222 / 0.406 / 0.640 | 0.222 / 0.407 / 0.645 | 0 / +0.001 / +0.005 |

At 2000 and 8000 the pattern is the same (whole-article S3 − S2: +0.010, +0.045; article: +0.002,
+0.021; document: −0.002, −0.006).

- **Document level:** no gain. Documents are already easy for S2: one of the top 10 distinct
  documents is right for 96% of questions (unit view, hit@10 0.958 for S2 and S3). A grouping chunk
  brings no new document and takes budget from chunks that might. An S3 context at 4000 has 11.6
  texts from 6.1 documents, against S2's 12.6 from 6.3.
- **Whole-article citations:** this is where the grouping chunks pay off. A chapter or section chunk
  fully contains its articles, so it is a full hit without needing the ART chunk or all the parts of a
  split article (`reachable_by_parts_only` drops from 11.9% to 4.6%). At 4000 S3 ≈ S1. At 16000 it is
  clearly ahead of both S1 and S2.
- **Article level:** same pattern, small at 4000 and +3 points at 16000. A bigger budget lets more
  chapter-size chunks in, each counting for every article inside it.
- **Sub-article citations:** no change. S2's paragraph and inciso chunks already deliver them.

**Do grouping chunks fit in the budget?**

- Size: median 692 tokens, 90th percentile 3030, 99th 7194 (other chunks: median 189). By type,
  median CAP 910, SEC 604, SSC 521, TIT 1886.
- Ranking (S3 rankings, jua): groupings are 6.8% of the top-10 texts. 46% of questions have one in
  the top 10, 20% in the top 3, 7% in first place.
- Not fitting is a minor issue: 9% of the top-10 groupings are above 4000 tokens (skipped at that
  budget, `overflow = skip`), 16% above 2000.
- Crowding out is the real cost. 58% of the S3 contexts at 4000 contain at least one grouping chunk
  (S4: 60%), and when they do it takes **32% of the tokens** on average (19% over all questions). The
  parent/child merge softens this: a grouping that ranks below some of its own articles replaces
  them and costs only the extra tokens.

**Caveats.**

1. *The hit rule is generous to S3.* A chapter with 20 articles is a full hit for all of them, even
   when the relevant paragraph is a small part of 3000 tokens: the S1-vs-sub-article issue of §1 one
   level up.
2. *S3's context precision is inflated.* It looks clearly better than S2's (article level: 0.169 vs
   0.145 at 4000, 0.124 vs 0.069 at 16000; provision: 0.162 vs 0.136 at 4000). But all the tokens of a
   grouping chunk that holds a gold article count as relevant. This measures the metric's design, not
   cleaner contexts. A token-weighted hit would fix both caveats.

**Answers.** S3 ≈ S2 overall at 4000 (phase 5 note). Generation ran only at 4000, where S3's
retrieval gain is still small. The +4 to +6 points on whole articles at 8000–16000 are untested on
answers.

## 6. Next steps

1. Add the granularity grouping (`whole_only` / `sub_only` / `mixed` / `none`) as a slice in
   `nuggets.py analyze`, so it lands in `slices_comparisons.csv` with permutation p and cluster CIs.
2. Test reason 1 directly. For whole_only questions, check whether S2's partial chunks contain the
   paragraphs that support the gold nuggets (`ctxsupport` tables).
3. A token-weighted hit (unit tokens / chunk tokens), which removes the generosity towards S1 (§1) and
   S3 (§5) and the inflation of S3's context precision.
4. If S3 is to be tested on answers, use a larger budget (8000–16000), where its retrieval gain on
   whole-article citations appears.

## Appendix: reproduction

Run from the repo root, with no API calls (≈ seconds). The grouping and paired-difference script used:

```python
import sys, numpy as np, pandas as pd
args = [x for x in sys.argv[1:] if not x.startswith("--")]
emb = args[0] if args else "jua-4b-mixed"        # or gemini-emb-2; add --pure for the §3 robustness check
suffix = "" if emb == "jua-4b-mixed" else "@" + emb
d = pd.read_csv(f"runs/retrieval/{emb}/irpf/eval/either_containment_merge_skip/per_item.csv.gz")
d["question_number"] = d.question_number.astype(str)
s1 = d[d.strategy == "S1"]
prov = s1[(s1.level == "provision") & s1.statutory]
g = prov.groupby("question_number").sub_article.agg(["size", "sum"])
cls = pd.Series("none", index=sorted(set(s1.question_number)))
cls[g.index] = np.where(g["sum"] == 0, "whole_only", np.where(g["sum"] == g["size"], "sub_only", "mixed"))
# "pure" grouping (§3 robustness check): drop questions citing a document without any article of it
art = s1[s1.level == "article"]
docs_with_art = set(zip(art.question_number, art.item.str.split("|").str[0]))
docq = s1[s1.level == "document"]
doc_only = set(docq.question_number[[(q, i) not in docs_with_art for q, i in zip(docq.question_number, docq.item)]])
if "--pure" in sys.argv:
    cls = cls[~cls.index.isin(doc_only)]

# retrieval premise: provision full-hit recall at 4000 per class
p = d[(d.level == "provision") & d.statutory & d.strategy.isin(["S1", "S2"])]
r = p.groupby(["question_number", "strategy"]).budget_full_4000.mean().unstack().join(cls.rename("cls"), how="inner")
print(r.groupby("cls")[["S1", "S2"]].mean().round(3))

pq = pd.read_csv("nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/per_question.csv.gz")
pq["question_number"] = pq.question_number.astype(str)
a, b = "S1_budget4000" + suffix, "S2_budget4000" + suffix
rng = np.random.default_rng(0)
for llm, x in pq[pq.context_id.isin([a, b])].groupby("llm"):
    w = x.pivot_table(index="question_number", columns="context_id", values="V_strict").dropna()
    if a not in w or b not in w:
        continue
    w["diff"] = w[b] - w[a]; w["cls"] = cls.reindex(w.index)
    for c, y in w.groupby("cls"):
        bs = rng.choice(y["diff"].to_numpy(), (5000, len(y))).mean(1)
        print(llm, c, len(y), round(y["diff"].mean(), 3), np.percentile(bs, [2.5, 97.5]).round(3))
```

For §4: per question, the retrieval gain is the mean over gold items of `budget_full_4000`
(article level; provision level, statutory) or `budget_any_4000` (provision), S2 minus S1. It is
correlated (Spearman) with the V_strict gain, per generator and per group (`none` excluded).

For §5: the level × budget table is `per_item.csv.gz` averaged by strategy. The unit view and context
precision come from `metrics.csv` (`gold = all`, `slice = all`). The grouping-chunk statistics come from
`segmented/chunks_all.csv.gz` (`Tipo` in PRT…SSC), `runs/retrieval/jua-4b-mixed/irpf/S3/rankings.csv.gz`
and `runs/contexts/jua-4b-mixed/irpf/S3_budget4000/contexts.jsonl.gz` (`items[].tipo`, `tokens_qwen3`).
