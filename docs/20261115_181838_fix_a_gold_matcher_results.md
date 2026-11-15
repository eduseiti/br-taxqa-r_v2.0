# Fix A (gold matcher, misparsed chunks): execution and results

**Generated:** 2026-11-15 18:18:38 (local time, from `date +%Y%m%d_%H%M%S`).
**Plan:** `20261115_172140_gold_matcher_annex_rule_and_misparsed_articles.md` §4 (approved by the user on
2026-11-15). Fix B (corpus revision, §5 there) is still pending.

**Cost:** $0.168 list, **$0.076 billed**:
- generation: 16 calls, $0.063 list, $0.023 billed;
- judge: 15 calls, $0.105 list, $0.052 billed.

The ledgers are `runs/costs.csv` and `nuggets/scoring/costs.csv` (rows of 2026-11-15).

**Backup** of every output before the fix: `../br-taxqa-r_fixA_backup_20261115/` (outside the repo, 306 MB):
- retrieval, evaluations, contexts;
- oracle answers;
- scoring `score/`, `ctxsupport/`, `tables/`, `analysis/`.

## 1. Code changes

| File | Change |
|---|---|
| `scripts/rag/ragpipe/relevance.py` | **G3 only for citations that name no file.** A provision whose `lexml_file` holds the article matches that file only. An article item carries `GoldItem.files`, the files named by its references' provisions, and matches only those when they hold the article. **G4.** `Matcher(ignore_rows=…)` drops the misparsed chunks from article and unit matching. The separate instances of an article id are computed (`article_instances`), the groupings that contain each instance count, and `Match.instances` reports items that match more than one instance. Match cache key includes the named files: the same `(doc, article)` cited by two questions can name different files. |
| `scripts/rag/ragpipe/exclusions.py`, `retrieval.py` | `corpus_exclusions.yaml` gets a `chunks:` section. `Exclusions.chunk_row_mask()`; `row_mask()` also drops these chunks from retrieval; the manifest records them, and the retrieval params record `excluded_chunks`. That entry is added only when the list is non-empty, so runs without chunk exclusions keep their hash. |
| `scripts/rag/corpus_exclusions.yaml` | `chunks:` the **4 pure-junk chunks**: RIR/2018 annex `#2754`, Lei 12.350 `#179`, Portaria Conj. 74 `#23`, Circular BC 3.432 `#30`. Each is the only chunk of its misparsed instance. Not listed, because they hold real legal text: IN RFB 1.131 art. 31 (2nd instance), DL 5.844 "art. 93" (2nd), MP 497 art. 31 (two wordings). Fix B repairs them. |
| `ragpipe/evaluation.py` | per-item column `multi_instance`, reachability column `multi_instance_matches`; matcher built with the chunk exclusions |
| `ragpipe/contexts.py`, `nuggetizer/analysis.py`, `nuggetizer/ctx_audit.py`, `scripts/report/build_trace_data.py`, `build_explorer_data.py` | every matcher is built with the chunk exclusions of the retrieval manifest |
| `scripts/nuggets/nuggetizer/analysis.py` | **Separate bug found while rerunning `analyze` (§4).** `citation_scores` read every run against the primary embedding's contexts and keyed it by the bare set name. Now it reads the run's own context (`run.json` `context.path`) and keys it with `scoring.context_key`. |
| `scripts/rag/tests/` | 2 fixture tests updated: Q003 of the fixture names the main file for art. 1, so the annex art. 1 no longer counts. 2 new tests: the G3 rule for named files, and ignored rows / instances. **46 passed.** |
| `scripts/rag/experiments/fixA_oracle.yaml` | the regeneration of `oracle_budget4000` only (§3) |

**Effect of the new matcher on the gold items**, old vs new matcher over all gold items:
- **7 items changed**, exactly the planned ones: the article and provision items of Q006 art. 1º, Q220 art. 5º and
  Q264 art. 4º.
- Removed: the decree's art. 1º, 4º and 5º, and the misparsed `#2754`.
- Q006 also **gains** two grouping chunks of the annex, TÍTULO I `#3660` and CAPÍTULO I `#3699`. Before, the junk
  instance stretched art. 1º's interval across the whole annex, so no grouping "contained" it.
- No gold item matches more than one article instance.

## 2. Retrieval, evaluation, contexts (no API calls)

```bash
set -a; . ./.env; set +a          # needed: the Qwen3 tokenizer for rendered-context counts
P=.venv/bin/python; R=scripts/rag/rag.py
$P $R retrieve --embedding jua-4b-mixed --force ; $P $R retrieve --embedding gemini-emb-2 --force
$P $R evaluate --retrieval <run> --force        # main eval, both embeddings; + v2d for both; + Gemini's
                                                # either_containment_skip and v2c (same commands as 2026-11-08)
$P $R context --retrieval runs/retrieval/jua-4b-mixed/irpf --sets "<the 13 sets>" --force   # + S2 4k context_v1
$P $R context --retrieval runs/retrieval/gemini-emb-2/irpf --sets S1@budget=4000,S2@budget=4000 --force
```

jua's two older evaluations (`either_containment_skip`, `v2c_…`) belong to an earlier chunk file and were left as
they were.

**Retrieval metrics:**
- **No budget-view metric changes**, for any strategy, level, budget or embedding.
- 107 rows (jua) and 30 rows (Gemini) of `metrics.csv` change, all in the raw and unit views of S3/S4, by at most
  +0.0038. The causes:
  - Q006's S3/S4 article and provision become reachable (rank 671 / 716) through the groupings above;
  - ranks shift by one where a removed junk chunk used to rank above (Q248, 261, 264, 265, 289, 295);
  - unit positions shift by one in S3/S4, because the groupings that contain RIR art. 1º now also project that
    article as a unit.
- `multi_instance_matches` = 0.
- Q006's remaining art. 1º chunks carry the corpus flag `id_ambiguo = 1`, so its item is now `only_ambiguous`. The
  flag will clear when fix B repairs the corpus.

**Contexts:**
- The **text** of every retrieved context (S1/S2 2k–8k, S2c/S3/S4 4k, context_v1, wrong-context, both embeddings)
  is byte-identical. Only the `rank` of a few items moves by one, where a junk chunk ranked above.
- Only the oracle contexts changed, for:
  - **Q006, Q220, Q264, Q438 at 4k**;
  - Q006, Q220, Q438 at 16k. Q264 16k keeps its texts, and only its gold record changes.
- Contexts ↔ evaluation consistency: 0 mismatches.

## 3. Oracle answers and judge

- **Regeneration:** `rag.py run --experiment scripts/rag/experiments/fixA_oracle.yaml --budget 73.33 --force`.
  - 16 new calls: 4 generators × Q006/220/264/438; everything else came from the cache.
  - The other experiments were not rerun: their dry runs showed 6 old `max_tokens` errors that a rerun would retry,
    which is out of the scope of this fix.
  - The answer text changed for Q006, Q220 and Q264 (all generators except Sabiá-4 on Q006) and for Q438
    (Sabiazinho-4 only). The other answers to the new contexts came back with the same text.
- **Judge:**
  1. The old labels of the 4 questions were removed from the 4 `score/…/oracle_budget4000` folders and from
     `ctxsupport/…/oracle_budget4000`, since `score` keeps existing labels.
  2. `nuggets.py --out nuggets/scoring --sample all --budget 143.60 score --runs ".../oracle_budget4000"`: 11 new
     calls. The 5 answers with unchanged text produced the same request and were cached.
  3. `ctxsupport --contexts …/oracle_budget4000`: 4 calls.

  No other judge, nugget set or oracle 16k label covers these questions.
- Then `scoretable` and `analyze`.

**`runs.csv` (gold, Gemini 3.8 Flash, all), the only rows that changed:**

| Run | V_strict | V | W | A_strict |
|---|---|---|---|---|
| Luna oracle 4k | 0.3384 → 0.3393 | 0.4750 → 0.4754 | 0.4352 → 0.4354 | 0.2993 → 0.2997 |
| Terra oracle 4k | 0.3682 → 0.3679 | 0.5144 → 0.5143 | 0.4711 → 0.4710 | 0.3248 → 0.3246 |
| Sabiá-4 oracle 4k | 0.3187 → 0.3185 | 0.4623 → 0.4621 | 0.4219 → 0.4218 | 0.2784 → 0.2783 |
| Sabiazinho-4 oracle 4k | 0.2935 → 0.2915 | 0.4614 → 0.4596 | 0.4247 → 0.4229 | 0.2630 → 0.2609 |

For Sabiazinho-4, the abstention rate is 0.057 → 0.059: one of the new answers abstains.

**`comparisons.csv`:**
- Only the 44 comparisons against oracle 4k changed, with |Δ diff| ≤ 0.002.
- **No significance flip:** p_perm at 0.05 and CIs excluding 0 are unchanged.
- S1 vs S2 and every other comparison are unchanged.

## 4. Analysis tables: first regeneration since 2026-10-24, and the citation bug

The `analysis/` outputs in git dated from 2026-10-24: before the Gemini runs, and before the context-support labels
of the wrong-context set. Regenerating them for this fix brings in those additions too:
- 4 Gemini runs in the run-level tables;
- the wrong-context linkage, `n_ctx0` 0 → 30.

Regenerating them also **exposed a bug** introduced with the Gemini runs (commit 83b3f55). `citation_scores` read
every answer run against the jua contexts and keyed it by the bare set name. So:
- the Gemini answers' `[Documento n]` citations were resolved against the jua contexts;
- the run-level citation tables pooled jua and Gemini (jua Luna S1 article `n_cited` 2.14 became 1.80).

Fixed (§1). With the fix:
- every jua run-level citation row equals the old one, except the oracle 4k rows (|Δ| ≤ 0.007);
- per answer, the citation table differs from the old one only for Q006/220/264/438 in the oracle 4k runs. So **no
  answer of a retrieved-context run cited the decree article in place of the annex**: the citation score of those
  runs does not change.

**What fix A changes in the analysis:**
- utilisation, values and PGD tables: only the oracle 4k rows (|Δ| ≤ 0.007);
- `slices_comparisons`: only comparisons against oracle 4k (|Δ diff| ≤ 0.003).

`perturbation_s1_s2`'s inputs are unchanged. Its rows moved by Monte Carlo noise: mean diff ≤ 0.0004, and the
share of significant draws by up to 0.05. The label table now also holds the Gemini rows, which reorders the seeded
draws.

## 5. Dashboards and release

- `build_dashboard_data.py`, `build_trace_data.py` and `build_explorer_data.py` were rerun; their results are in the
  update of the HF eval repo, §6.
- Repo A is unchanged: no corpus file changed.

## 6. Hugging Face

Repo B updated: `ccba6d5` → **`ea67478`** (`ea67478af8296b61ffe9725ffb0d681f2c5e4b18`), recorded in
`release/hf_release.json`. 2 new files (the two notes) and 129 changed.

| What changed | Files |
|---|---|
| Retrieval runs and evaluations, both embeddings | rankings, manifests, `metrics.csv`, `per_item`, `per_question`, `reachability`, `report.md` |
| Generator contexts | text unchanged except the oracle contexts; ranks and manifests change |
| The 4 oracle 4k answer runs, their scores and context support | answers, labels, calls |
| Scoring tables and the 9 analysis tables | `nuggets/scoring/tables/`, `nuggets/scoring/analysis/` |
| The 6 Parquet viewer tables | `tables/` |
| Cost ledgers | `runs/costs.csv`, `nuggets/scoring/costs.csv` |
| Archives repacked | answer cache 18,600 → 18,616 requests; scoring cache 26,420 → 26,435; trace and explorer data |
| Release files | card, `SHA256SUMS`, `release_manifest.json` |

Before pushing, the two cache archives were checked against the local caches: the local caches are the published
archives plus the new calls only. Repo A is unchanged.
