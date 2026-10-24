# Slide deck: first full evaluation (rationale, method, results, robustness)

Date: 2026-10-24. A 29-slide deck that presents the hierarchical-segmentation RAG experiment to
peers and reviewers who know RAG, retrieval evaluation and LLM judges, but not this dataset or
experiment. It covers the state after the phase 5 scoring and analysis
(`20261023_210727_rag_phase5_scoring_and_analysis.md`, including its §10 ceiling audit).

- **Live deck (private until shared from the page's Share menu):**
  https://claude.ai/artifact/M7A2qaMUx4AHye6F6sNtTq (claude.ai Slides artifact; PDF / PPTX export
  from the page).
- **Copy in the repo:** `docs/slides/20261024_145130_first_full_evaluation_deck/`
  - `project/deck.json` — slide order, sections, fonts (the artifact type's index format, v4);
  - `project/slides/<id>.html` — one 1920×1080 `<section>` per slide, inline styles, speaker notes
    in `<aside>`;
  - `deck.html` — offline view of all slides, scaled to the window, each with its notes below it
    (print to PDF for a handout). Regenerate with `python3 build_standalone.py` after editing a
    slide. Fonts come from Google Fonts, so it needs internet access for the intended typefaces.

The copy was downloaded from the published version (1792808737-9c99) and matches the source files
byte for byte. `deck.html` has not been checked in a browser here (no headless browser in this
environment), and neither has the live deck: page through both once for overflowing text or
overlapping chart labels.

## How it was made

1. **Sources.** Every number comes from the notes in `docs/`, mainly:
   `20261023_210727_rag_phase5_scoring_and_analysis.md` (results, robustness, ceiling audit),
   `20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md` (H1–H6, the
   trimmed grid, the perturbation threshold), `20261023_151928_rag_phase3_trimmed_full_generation.md`,
   `20261021_155704_nuggetization_phases_2_to_4_execution.md` (nugget QA, judge selection),
   `20260923_193852_segmentation_strategies_for_rag_experiments.md`,
   `20261022_203625_corpus_exclusion_revoked_rir1999.md`, the retrieval report
   `runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_merge_skip/report.md`,
   `segmented/segmentation_report.md`, `scripts/rag/llms.yaml` and the prompt
   `scripts/rag/prompts/answer_v1.pt.md`.
2. **Checked against the data, not only the notes:**
   - the Q350 nuggets on the nuggets slide come from `nuggets/gold/v0-auto/nuggets.jsonl` (N02
     vital: parent-in-law only in a joint return, with the R$ 24.511,92 limit; N01, N03 okay). A first
     draft paraphrased them from memory; it was replaced with the real ones;
   - the article-chunk example (Lei 9.250/1995, art. 35: ≈ 720 tokens as an S1 article chunk, ≈ 140
     tokens as the S2 inciso VI chunk) comes from `segmented/chunks_all.csv.gz`.
3. **Structure.** It is laid out like a paper: motivation → hypotheses → data → method → evaluation
   design → results → robustness → synthesis, with a section marker in each footer and speaker
   notes on every slide aimed at the questions a reviewer would ask.
4. **Look.** Light paper background with dark cover/closing slides; Source Serif 4 for headings,
   IBM Plex Sans for text. One colour per strategy throughout (S2 blue `#2E62A8`, S1 orange
   `#B85F22`). Charts are inline SVG (retrieval recall vs budget, S1→S2 forest plot, perturbation
   curve) or plain bar layouts (contradictions, decomposition, ceiling causes).
5. **Fixes during review of the slide sources:** forest-plot p-value labels repositioned; retrieval
   slide shortened to fit; contradiction bars rescaled to their percentages; an unsupported table
   `colspan` replaced by separate boxes; label collisions on the perturbation chart moved; the
   ceiling-causes chart narrowed to fit the slide.
6. **Wording kept honest:**
   - the second-judge slide says both judges give the *same* S1→S2 Δ. On its 70-question sample
     that Δ is slightly negative and not significant for both judges, so the check shows the judges
     agree with each other; it does not reproduce the main effect;
   - the phase 5 note says the 60 cause classifications were all read and 17 changed. That review
     was done by the assistant, not by a person, so the slides say "re-checked against the evidence",
     and the limitations slide says a tax-law expert still needs to confirm them;
   - the ceiling audit (slides 24–25) is marked as exploratory: it was run after the main analysis,
     on 57 questions.

## Outline and description

| # | Slide | Content |
|---|---|---|
| 1–4 | Motivation | Earlier work on structural segmentation of Brazilian law only measured retrieval, not answers. H1–H6 from the plan note. The slides point out that H3–H6 were written down before any answer was scored, so their null results aren't post hoc. |
| 5–9 | Data and pipeline | Dataset and LexML corpus (715 Q&A, 1,916 references, 453 documents, RIR/1999 excluded). Lei 9.250 art. 35 as one ~720-token S1 article chunk vs a ~140-token S2 inciso chunk, tied to Q350. The five strategies, all filtered from one chunk table and one embedding run. The comparison is at equal token budget (4k), not equal number of chunks. Four generators in two same-vendor size pairs, with closed-book, oracle and wrong-context controls. |
| 10–12 | Evaluation design | Nugget creation (primary GPT-6.1 Sol set, 3,175 nuggets) shown on Q350's real nuggets. Quality checks against fixed thresholds, including the one that wasn't met (3 leftover validator errors). Why Gemini 3.8 Flash was chosen as judge (BA 99.0 % on 3,354 known-answer tests). V_strict as the headline metric. Paired bootstrap, permutation test, chapter-cluster bootstrap. |
| 13–19 | Results | S2 retrieves about 0.10 more of the cited articles at every budget (chart). V_strict table. Forest plot of S1→S2: Luna +0.028 (p .007), Sabiá-4 +0.027 (p .009), Terra +0.016 (n.s.), Sabiazinho-4 +0.005 (n.s.). S3, S2c and S4 add nothing over S2. Retrieval mainly cuts contradictions (27–38 % of answers → 8–14 %). Two limits on answer quality: what the context holds (oracle 0.48) and how much the generator uses (48–65 %). Most of S2's gain comes from the 479 questions where the context holds the same facts under both strategies. |
| 20–25 | Robustness | Opens with a map pairing each threat with the check that addresses it, then: nugget subsets and chapter clustering; deliberately damaged nugget sets (the effect survives 15–20 % damage, against the threshold set in the plan); rescoring with the Gemini and Qwen nugget sets (Terra also significant there); a second judge (κ 0.90, same Δ); the exploratory ceiling audit (context judge BA 98.5 %, a 16k oracle raises support to 50.5 %; about one vital fact in six isn't stated in any legal text of the corpus). |
| 26–29 | Synthesis | Scorecard of the six hypotheses (H1, H2 supported; H3–H6 not). Limitations grouped by type of validity. Cost (≈ $184 in LLM calls, all in the ledgers) and reproducibility. Next steps. |

## Before presenting

- Fill in the placeholders `[co-authors]` (cover) and `[contact]` (last slide). The author line
  uses the git user name.
- Chunk counts on the strategies slide (S1 21.5k, S2 73.1k, S3 77.1k) are from the segmentation
  report, i.e. before the RIR/1999 exclusion.
- To change a slide, edit the live artifact (or ask Claude to), then download it again into this
  folder and rerun `build_standalone.py`. The copy here is a snapshot of the published version
  above, not the source the artifact is published from.
