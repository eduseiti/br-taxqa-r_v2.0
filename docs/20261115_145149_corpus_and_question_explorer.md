# Corpus & question explorer: a second dashboard, built on the question-trace data

**Generated:** 2026-11-15 14:51:49 (local time, from `date +%Y%m%d_%H%M%S`).
**Page:** `docs/explorer/index.html` (static, opens from `file://`).
**Data:** `scripts/report/build_explorer_data.py` (≈ 20 s, no API calls) → `docs/explorer/data/` (gitignored, ≈ 17 MB).
**Reuses:** the question-trace data `docs/dashboard/data/trace/` (`scripts/report/build_trace_data.py`;
`20261110_194056_question_trace_dashboard_implementation.md`) and the trace tab's rendering code, copied into the new
page. The results dashboard `docs/dashboard/index.html` is unchanged and kept as a reference, so its views can be
pulled into the explorer later. The explorer links to it from the header.

## 1. What it shows

Two entry points, each a searchable and sortable list:

**Questions** (`#/q`): all 715 questions, with chapter, explicit and embedded references, documents, nuggets, the
mean V_strict over the scored runs, and the article recall of jua S2 at 4k. One question (`#/q/<n>`) has six
collapsible sections:

| Section | Content |
|---|---|
| Official answer | with each nugget's source span highlighted; a click opens that nugget |
| Gold nuggets | one collapsible row per nugget, with a strip of its label in every scored answer. Open: id, category, values, oracle 4k/16k support with the judge's justification, the legal basis in the nugget (linked to the corpus), the closest gold text (BM25), other model families |
| Referred documents | the references grouped by document, each marked explicit or embedded. Open: citation, articles, provisions, and links to the document or article in the corpus |
| Gold segments by strategy | for each gold article or provision, the chunks of each strategy (S1, S2, S3, S2c, S4) that the evaluation's matcher counts as a hit, full or partial: an item × strategy matrix, then one collapsible item per strategy with the chunk texts |
| Retrieval | per-question metrics of the 10 runs (5 strategies × 2 embeddings) for the chosen gold level: recall at the 5 budgets, R@1/5/10/100, MRR, nDCG@10, context precision; the first rank of each gold item in each run; each run's ranking with gold and in-context marks |
| Answer generation | V_strict, V, W, A_strict and the label counts of every scored run (29); a nugget × run label grid; per run the context (token bar and items), the prompt as sent (with the LLM-cache check), the answer's claims and their quotes, and each nugget's label against the oracle context, the run's context and the answer |

**Corpus** (`#/d`): the 453 documents, with kind, date, files, articles, chunks per strategy, the questions that
cite each one, and its explicit and embedded references. One document (`#/d/<id>`) has four sections:

| Section | Content |
|---|---|
| Questions that cite this document | one row per reference, filterable by origin (explicit, embedded), with the articles and provisions cited; a row opens the question |
| Segmentation overview | per strategy: chunks, tokens (total, median, max), chunks per type |
| Structure: articles compared across strategies | one collapsible row per article (main text, then annexes), with the chunk count of each strategy and the number of questions that cite it. Open: the citing questions, then per strategy its chunks and, in S3/S4, the groupings that contain it. Filter by label, or show only the cited articles. Chunks outside articles and grouping chunks are listed apart. A document without articles gets one list per strategy. |
| Chunks of one strategy, in file order | the index as the retriever sees it, 300 at a time |

**Navigation:**
- Every page is a URL hash, so the browser's Back and Forward buttons work, and so does the "◀ Back" button.
- A trail of recent pages sits in the header. Returning to a page restores its scroll position.
- Links between the two explorers:
  - a document, article or nugget legal basis → the corpus page, opened at that article;
  - a ranked row, context item, cited `[Documento n]` or gold segment → the corpus page, opened at that chunk, with
    the chunk outlined;
  - a citing question → the question page.

**Collapsing:**
- Every block is a `<details>` section whose content is built only when it is first opened. This keeps the long
  documents fast; the RIR/1999 has more than 1,000 articles.
- Each section remembers whether it was open, in this browser (`localStorage`, optional). Open "Retrieval" on one
  question and it stays open on the next.
- "Expand all" and "Collapse all" act on the top-level sections.

## 2. Data added by `build_explorer_data.py`

The trace data had no per-document list of citing questions, no chunk ↔ gold mapping beyond the ranked rows, and
no per-question metric tables. The builder reads local files only:
- the dataset;
- `segmented/chunks_all.csv.gz`;
- the evaluation's `per_question.csv.gz` of both embeddings (`either_containment_merge_skip`);
- `nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/per_question.csv.gz`;
- the trace's `index.js`, for its run list and as a consistency check.

It writes:
- `index.js` (0.37 MB): the documents with their citing references `[question, reference, origin, articles,
  provisions]`, chunk and token counts per strategy, and a summary row per question;
- `q/<n>.js` (715, 16 MB): the gold segments of each gold item per strategy. These come from
  `ragpipe.relevance.Matcher`, the evaluation's own matcher: full and partial chunk ids, with the excluded documents
  removed as in the indexes. Also the per-question retrieval metrics (`gold = all`, `slice = all`) and the nugget
  scores of the 29 runs in the trace data.

**Check:** the builder stops if its strategy chunk counts differ from the trace data's (20,461 / 68,656 / 72,061 /
68,656 / 72,061). Gold segments over all questions:
- article × strategy: 9,720 with a hit, 70 without;
- provision × strategy: 10,905 with a hit, 245 without.

The cases without a hit are excluded documents, and provisions that no chunk of that strategy holds in full or in
part.

## 3. Use on another computer

Both data sets are on the HF eval repo since 2026-11-15 (commit `ccba6d5`, recorded in `release/hf_release.json`).
From the repo root:

```bash
hf auth login      # the repo is gated
hf download eduseiti/BR-TaxQA-R-RAG-eval raw/dashboard_trace.tar.gz raw/dashboard_explorer.tar.gz --repo-type dataset --local-dir .
tar -xzf raw/dashboard_trace.tar.gz && tar -xzf raw/dashboard_explorer.tar.gz
xdg-open docs/explorer/index.html
```

Or rebuild them: `scripts/report/build_trace_data.py`, then `scripts/report/build_explorer_data.py`. The explorer
builder needs the evaluation's `per_question.csv.gz`, which is under `runs/` in the HF eval repo.

**Upload (2026-11-15):** `build_release.py --repos b --keep-raw`, then `push_release.py` gave `4ddc246` →
`ccba6d5`. Changes:
- new: `raw/dashboard_explorer.tar.gz` (1.2 MB, 716 files) and this note;
- changed: the card, `SHA256SUMS`, `release_manifest.json`, and the trace implementation note (a pointer to the
  archive).

Nothing else changed. The archive was downloaded back from the Hub and is identical to `docs/explorer/data/`.

## 4. Checks

Headless Chrome (Playwright, from the scratchpad, not a repo dependency):
- **Pages:** at 1,300 px light and 390 px dark: the question list, Q350, Q001 (many embedded references), Q442 (the
  largest question file), the corpus list, `lei_9250_19951226`, and its art. 8 (cited by 21 questions). Every
  section was opened.
- **Navigation:** a ranked row → its chunk in the corpus (outlined) → Back returns to Q350; a citing-question row →
  the question.
- **Sweep:** 7 more questions with every section opened, and every 25th document plus the RIR/1999.

Results:
- no JavaScript errors;
- no horizontal page scroll at 390 px, after two fixes (the chapter select, the nugget detail table).

Screenshots looked at. Fixed after that review:
- the chevron of a long section title wrapped onto its own line;
- nugget texts were all bold;
- the split-article note was worded wrong.
