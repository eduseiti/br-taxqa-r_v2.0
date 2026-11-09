# Results dashboard: an interactive explorer of the retrieval and answer results

**Generated:** 2026-11-09 12:33:55 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** records why and how the results dashboard (`docs/dashboard/index.html`) was built, what each tab
shows, where its numbers come from, and how it was checked. It decides nothing about the experiments, and
it made no LLM or API calls ($0).
**Request (user, 2026-11-09):** an interactive visualizer of all executed experiments, built from
`20261108_224913_results_overview_segmentation_and_embedding.md`. It should say exactly what each result shows and
compares, so the execution can be validated. It should explain how strategies that cut the text differently
(S1 vs S2) are compared, which the report's §2.2 does not say, and link to the notes in `docs/` where each choice
was made.

## 1. How to open and rebuild it

```bash
.venv/bin/python scripts/report/build_dashboard_data.py     # ≈ 70 s, reads result tables only
xdg-open docs/dashboard/index.html                          # or open it in any browser; works from file://
```

- **Static page, no server.** The data are JavaScript files loaded with `<script>` tags. `fetch()` would be
  blocked under `file://`; script tags are not.
- **External dependency:** `marked` 12.0.2 from cdnjs renders the notes in the side reader. Offline, the notes
  are shown as plain text. Everything else is inline: the charts are hand-written SVG, with no chart library.
- **Theme:** light/dark, from the OS or the toggle button.

| File (`docs/dashboard/data/`) | Content | Size | In git |
|---|---|---:|---|
| `core.js` | retrieval metrics, comparisons and reachability for both embeddings; nugget runs, comparisons and robustness tables; strategy chunk counts; run index | 2.5 MB | yes |
| `docs.js` | every `docs/*.md` plus `scripts/{rag,nuggets}/README.md`, for the in-page reader | 1.2 MB | yes |
| `questions.js` | per question: text, official answer, references, nuggets, the judge's labels in every run and context, and the ranks of every gold item for every strategy × embedding | 6.2 MB | no (gitignored) |
| `contexts.js` | per question, the chunks of 13 generator contexts (rank, type, source, tokens, gold-hit mark) | 6.5 MB | no |
| `answers/*.js` | one file per scored run with its answers, loaded when a cell is clicked | 17 MB | no |

The per-question files follow the repo rule that per-question tables stay out of git (`runs/**` in `.gitignore`).
The page says so and names the build command when they are missing.

## 2. Inputs

All read by `scripts/report/build_dashboard_data.py`:

- **Retrieval evaluation:** `runs/retrieval/{jua-4b-mixed,gemini-emb-2}/irpf/eval/either_containment_merge_skip/`
  (`metrics.csv`, `comparisons.csv`, `reachability.csv`, `per_question.csv.gz`, `per_item.csv.gz`, `manifest.json`).
  This is the main evaluation, the one the results-overview figures use. The older `v2c_`/`v2d_` and `containment`
  evaluations are not shown.
- **Contexts:** `runs/contexts/<emb>/irpf/<context_id>/contexts.jsonl.gz`. Each chunk is linked to its article
  through `segmented/chunks_all.csv.gz`.
- **Answers:** `runs/answers/<emb>/irpf/<prompt>/<llm>/<context_id>/answers.jsonl`.
- **Nugget scoring:** `nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/` (`runs.csv`, `comparisons.csv`,
  `ctxsupport_runs.csv`), `nuggets/scoring/analysis/…/all/*.csv` (cross-set, perturbation, slices, chapters,
  judge agreement, utilisation, linkage) and the labels in `nuggets/scoring/{score,ctxsupport}/gold-v0-auto/gemini-3.8-flash/…/labels.jsonl`.
- **Gold nuggets:** `nuggets/gold/v0-auto/nuggets.jsonl`.
- **Dataset:** `dataset/{questions,references}.jsonl` and `scripts/rag/data/pr_irpf_2024_chapters.csv`.

**Computed by the script.** Everything else is copied as stored.
- **Strategy chunk counts.** Computed with `ragpipe.strategies.member_mask` minus the excluded RIR/1999 files.
  Result: 20,461 / 68,656 / 72,061 / 68,656 / 72,061 for S1 / S2 / S3 / S2c / S4, the same as the results overview.
- **Gemini − jua retrieval comparisons.** `rag.py compare` works within one retrieval run only, so these are
  computed from the two `per_question.csv.gz`, paired over the same questions. They use the same
  `ragpipe.metrics` functions (bootstrap 10,000, seed 13; sign-flip permutation) and count the questions that are
  better and worse.
  - They reproduce the ad hoc table of `20261108_175117_…` §4.3. Article recall at 4k: S1 +0.015, p .27, 101/86
    questions better/worse; S2 +0.012, p .37. Unit recall@10: +0.081 (S1) and +0.049 (S2).
  - The CIs differ in the third decimal, because the note used 5,000 resamples.
  - The script resamples once per group of metrics that share the same questions. A first per-metric version gave
    identical numbers (max |Δ| = 0) and took 3.7 min; the build now takes 1.1 min.

## 3. What each tab shows

| Tab | What it answers | Main elements |
|---|---|---|
| 1 · Map | What was run, and on which questions? | Clickable pipeline. Each stage shows what was varied, what was held fixed, and the notes where it was decided. Experiment grid: context set × generator, V_strict and n. Full (715), oracle (596) and pilot (30) runs are badged, so pilot runs are not compared with full runs by mistake. Headline KPIs. |
| 2 · Segmentation | What does each index contain? | Toggle S1…S4 on one article (Lei 9.250 art. 35) to see the chunks it produces: ancestor path, caput variant, grouping chunk. Chunk counts by type, and the strategy table. |
| 3 · Retrieval: how scored | How are S1 and S2 compared when they cut the text differently? | The answer to the user's question (§4 below). An interactive worked example that re-implements the matcher, the context selection (`containment_merge`, overflow skip) and RR/nDCG/recall in the browser, with the level, budget and dedup mode adjustable. A table of all rules with their code locations. |
| 4 · Retrieval: results | Retrieval metrics, filtered by embedding, strategy, level, gold set and item slice | Budget-view curves (1k–16k), unit-view recall@k, MRR/nDCG@10, raw view (labelled diagnostic), and a "What is shown" box rewritten for each selection. Paired-comparison forest plots per view and cutoff, including Gemini − jua. Reachability table. |
| 5 · Nuggets: how scored | What do V_strict, V, A_strict, A, W and contradictions mean? | A calculator: toggle the labels and the vital/okay importance of toy nuggets, or simulate an abstention, and see every metric with its formula. Notes on macro averaging, n = 714 vs 715, abstentions, oracle n, and context support vs answer scores. |
| 6 · Answers: results | Answer and context scores | Heatmap of runs × generators for any metric. Forest plots grouped by comparison family (S1 → S2, jua → Gemini, variants, controls, pilot budgets), with bootstrap and chapter-cluster CIs. Context V_strict vs answer V_strict. Utilisation. Robustness: three nugget sets, random and targeted nugget damage, nugget subsets, per-chapter differences, second judge. |
| 7 · Question explorer | Validate single cases end to end | Search or filter questions (e.g. "S1 4k recall > S2"). For each question: the gold items with their 4k membership, unit position and raw rank for all 10 strategy × embedding runs; two contexts side by side with gold-article chunks marked; a nuggets × runs label grid (plus "ctx:" columns for the judge on the context). Clicking a cell loads the answer. |
| 8 · Notes | All design and execution notes | A list of `docs/*.md`; the ¶ links across the page open the reader at the relevant section. |

## 4. The S1 vs S2 comparison, as the dashboard explains it

This is the point the user found unclear in the results overview §2.2. Read from `scripts/rag/ragpipe/relevance.py`
and `evaluation.py`, and already written down in `20261013_111626_retrieval_metrics_views_and_position_metrics.md`:

- **Matching happens at the level of the gold, not of the chunk** (rule G2). An article-level gold item
  `(document, art N)` is hit by **any** chunk of article N: the whole article, a split part, the caput, any §,
  inciso, alínea or item. In S3/S4 a grouping chunk also hits every article it contains.
- **MRR and nDCG@10 use the unit projection.** The chunk ranking is turned into a ranking of distinct articles, in
  the order in which *any* of their chunks first appears.
  - The MRR is 1 / (that position of the first gold article). It is the position of **any part** of the article,
    not of the whole-article chunk.
  - nDCG@10 uses binary gain over the first 10 distinct articles.
  - Positions beyond 1,000 count as not retrieved.
  - Both exist only at the document and article levels.
- **Recall within the 4k budget** (the headline) is a yes/no test per gold item: is any of its chunks in the context
  the generator saw? Position in the context does not count. It is the only view that charges each strategy for
  the length of its chunks.
- **Consequences shown on the page:**
  - S2 gets article credit when only one inciso of the article is in the context. The provision level, with
    full/partial hits, is the stricter test.
  - There is no provision-level MRR.
  - The means are over 553 (article), 596 (document) and 558 (provision) questions. The 119 questions without
    citations are in the answer scores only.

## 5. Checks done

- **The rendered numbers match the stored tables and the results overview.**
  - Article recall at 4k: 0.398 / 0.503 (jua S1/S2) and 0.413 / 0.515 (Gemini).
  - MRR: 0.524 / 0.555 / 0.614 / 0.638.
  - Answer V_strict: Luna S1 → S2 +0.028, p .007; Gemini vs jua as in the report.
  - Strategy chunk counts as in §2.
- **Gemini − jua comparisons:** reproduce the Gemini note's §4.3 (§2 above).
- **Every tab was rendered** with headless Chrome (1,300 px wide), and the screenshots were looked at. Fixed after
  that review:
  - the perturbation chart mixed random and targeted settings on one rate axis; the targeted settings are now a
    table;
  - the chapter labels were clipped;
  - the doc-link glyph did not render;
  - a sentence of the worked example did not follow the budget slider.
- **The worked example's selection logic** follows `ragpipe/context.py select`:
  - a text inside a selected one is dropped;
  - a parent replaces its already-selected children at the first child's place and costs its tokens minus theirs;
  - a text that does not fit is skipped.

  It is a re-implementation for teaching, on made-up rankings. The real per-question behaviour is in tab 7.

## 6. Limits and possible next steps

- **No test suite for the page.** It was checked visually and against the tables, not by automated tests.
- **Answer text is not compared with the context text.** The question explorer shows chunk labels, not chunk
  text, to keep the files small. The full context text is in `runs/contexts/…/contexts.jsonl.gz`.
- **Missing runs are shown as empty cells.** The 30-question pilot runs, the Terra/Sabiazinho-4 Gemini runs (not
  run) and the `irpf_with_rir1999` side run are visible only through these gaps or the run badges.
- **Rebuild after new runs.** New runs (e.g. Gemini with the other two nugget sets) appear after
  `build_dashboard_data.py` is rerun, as long as they write to the same table layouts.
