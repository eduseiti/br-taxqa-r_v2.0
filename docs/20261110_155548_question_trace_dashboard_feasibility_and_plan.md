# Question trace view for the results dashboard: feasibility analysis and implementation plan

**Generated:** 2026-11-10 15:55:48 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** checks whether the data needed to follow one question through every stage of the pipeline
(gold answer → nuggets → gold documents → segmentation → retrieval → context → answer → nugget labels) is
available, records the gaps, and plans how to add this view to the results dashboard
(`20261109_123355_results_dashboard.md`). It changes no experiment and plans no LLM calls ($0).
**Request (user, 2026-11-10):** extend the dashboard so that each data instance can be inspected across the
processing stages:
- from a question, see its gold-answer nuggets and, from each nugget, reach the gold document that contains it;
- from a question, see its referred documents and, from each document, its segmentation under every strategy;
- at retrieval, see the order of the returned segments, linked to their documents, with a mark when a segment
  belongs to the question's gold set;
- at answer time, see the final list of texts that fit in the token budget, and the nuggets of the generated
  answer compared with the gold set.

The user expected all of this to be in the Hugging Face repo `eduseiti/BR-TaxQA-R-RAG-eval`.
**Decisions (user, 2026-11-10, §7):** D1 top 100 + every gold hit, and show the prompt with its parts marked;
D2 no pilot runs; D3 and D4 not done (no extra cost); D5 build from the local files. Sections 3–6 below already
apply these decisions. §8 adds how the trace view shows the vital/okay importance of the nuggets.

## 1. Summary

**Feasible, with three corrections to the request:**

1. **Repo B alone is not enough; repos A + B together are.** `BR-TaxQA-R-RAG-eval` (repo B) has the rankings,
   contexts, answers and judge labels. The questions, gold answers, references, gold nuggets, chunk texts, LexML
   and original files are in `eduseiti/BR-TaxQA-R` (repo A). Both repos mirror this git repo's paths, so the
   builder can read either the local working copy or a download of the two repos (§2).
2. **No data links a nugget to a gold document.** Nuggets are extracted from the gold answer text. The citations
   (`references.jsonl`) belong to the question, not to the nugget. Three partial signals exist and can be shown
   together, each labelled for what it is (§3.1). A precise per-nugget link would need a new LLM step, which is
   not planned here (§7, D3).
3. **No nuggets are extracted from the generated answers.** Phase 5 scores in the opposite direction
   (`assign_v2`). The judge reads the answer and labels **each gold nugget** as `support`, `partial_support`,
   `not_support` or `contradicts`, and justifies each label. So the comparison with the gold set exists nugget by
   nugget. The generators did, however, write their answers as a list of **claims** (`afirmacoes`), each with
   the documents it cites and a quoted excerpt, checked at generation time (`answers.jsonl`: `claims`, `checks`,
   `cited_chunk_ids`). These claims can be shown and linked to the context ($0), but no data matches them to the
   gold nuggets (§3.5).

Everything else is in the data: segmentation by strategy, the full rankings (1,000 per question), the gold
match per ranked chunk, the in-budget text list with its rendered prompt, the answers, and the labels.

## 2. Where each piece lives

Checked on 2026-11-10 with a listing of both repos (`HfApi.list_repo_tree`) and the local files.

| Data | Repo | Path (same in git and on the Hub) | Notes |
|---|---|---|---|
| Questions, gold answers | A | `dataset/questions.jsonl` | 715 |
| References (gold documents, articles, provisions) | A | `dataset/references.jsonl` | 1,916 rows; 596 questions have at least one |
| Documents (title, URN, files) | A | `dataset/documents.jsonl` | 453 |
| Gold nuggets | A | `nuggets/v0-auto/nuggets.jsonl` (git: `nuggets/gold/v0-auto/`) | 3,175; `source_span`, `legal_basis`, `importance`, `values` |
| Chunks of every strategy, with text | A | `segmented/chunks_all.csv.gz` | 104,574 rows, 85 M characters; `artigo_id`, `cobre_ids`, `parcial_ids`, `agrupadores_ids`, `variante`, `n_tokens_qwen3` |
| LexML / original files | A | `lexml/…`, `original/…` | for links, not needed to render chunks |
| Rankings | B | `runs/retrieval/<emb>/irpf/<S>/rankings.csv.gz` | top 1,000 per question; 5 strategies × 2 embeddings (Gemini: S1, S2) |
| Gold match per item | B | `runs/retrieval/<emb>/irpf/eval/either_containment_merge_skip/per_item.csv.gz` | `rank_full`, `rank_any`, `unit_pos`, `budget_{full,any}_<k>` per gold item |
| Generator contexts | B | `runs/contexts/<emb>/irpf/<context_id>/contexts.jsonl.gz` | in-budget `items` (rank, chunk, aliases, tokens, source), `gold` hits, rendered `context` text |
| Answers | B | `runs/answers/<emb>/irpf/<prompt>/<llm>/<context_id>/answers.jsonl` | 60 runs locally (full, oracle, closed-book, pilot) |
| Answer labels per gold nugget | B | `nuggets/scoring/score/gold-v0-auto/gemini-3.8-flash/…/labels.jsonl` | label + justification per nugget; also the second judges `gemini-3.1-pro.rep0`, `qwen3.8-max.rep0` on subsets |
| Context labels per gold nugget | B | `nuggets/scoring/ctxsupport/gold-v0-auto/gemini-3.8-flash/…/labels.jsonl` | 12 jua contexts + 2 Gemini contexts (list in §3.1) |
| Value hits, citations per answer | B | `nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/{values_per_nugget,citations_per_answer}.csv.gz` | per run × question (× nugget) |

**Reading from the Hub in the browser is not an option.** Both repos are private (staging), the dashboard opens
from `file://`, and a browser would need the token and CORS access. The builder therefore downloads or reads the
files and writes static data files, as the current dashboard does.

**Machine state.** The gitignored per-question files of the current dashboard (`questions.js`, `contexts.js`,
`answers/`) are not on this computer; `runs/` and `nuggets/scoring/` are. On a computer without them, the builder
can fetch the needed paths from both repos with `snapshot_download(allow_patterns=…)` (≈ 300 MB without the
embeddings and the `raw/` caches).

## 3. Feasibility per interaction

### 3.1 Question → nuggets → gold document

- **Question → nuggets:** direct (`question_number`). `source_span` locates each nugget in the gold answer
  (`span_match`: exact or fuzzy), so the nuggets can be highlighted in the answer text.
- **Nugget → gold document:** not recorded. Three signals, shown in this order:
  1. **Explicit legal basis.** 478 of 3,175 nuggets (15 %, in 183 questions) carry `legal_basis` strings copied
     from the answer, e.g. `art. 39 da Lei nº 11.196, de 21 de novembro de 2005`. They can be resolved to the
     question's references by matching them with `citation_text` and the article numbers. Resolution rate to be
     measured in step 2 (§5); unresolved strings are shown as text.
  2. **Support by the gold articles.** The judge labelled every nugget against the oracle context
     (`ctxsupport`, `oracle_budget4000`, 596 questions; `oracle_budget16000` for 57). This says whether the gold
     articles, as packed in 4k tokens, support the nugget. The justification sometimes names the article. It is
     a label on the whole oracle context, not on one document.
  3. **Lexical candidate (computed, $0).** Rank the question's gold-article texts by word overlap (BM25) with the
     nugget text and show the best match and its score, marked "heuristic". It is a pointer to where to look,
     not a gold link.
- **Limits.** The 119 questions without references have no gold documents; for them the view stops at the
  nuggets. Nuggets that restate PGD procedure or the Q&A's own wording may have no legal source at all.

### 3.2 Question → referred documents → segmentation under every strategy

- **Feasible from repo A alone.** `references.jsonl` gives the documents and articles; `chunks_all.csv.gz` gives
  every chunk with its document, article, ancestors, groupings and variant.
- **Strategy membership** is computed with `ragpipe.strategies.member_mask`, as the dashboard already does for
  the chunk counts (S1 / S2 / S3 / S2c / S4 = 20,461 / 68,656 / 72,061 / 68,656 / 72,061 after the RIR/1999
  exclusion). A chunk can belong to several strategies.
- **View:** the document's articles in order; for each article, the chunks each strategy makes of it (S1: the
  article, in parts if split; S2: + caput-less paragraphs and sub-units with the ancestor path; S3: + groupings;
  S2c/S4: the caput variants). Gold articles of the current question are marked. Annexes and non-statutory
  documents are shown with their own chunk types (`TXT`, `TAB`, orphan dispositivos).
- **Excluded document.** The RIR/1999 is referenced by questions but excluded from the `irpf` indexes. It is
  shown with a note "not indexed in the main run".
- **Links** to the LexML and original files on the Hub (repo A paths) for the full source.

### 3.3 Retrieval: ranked segments with gold marks

- **Rankings** are complete (1,000 per question) for 10 strategy × embedding runs. Each row has `chunk_id`, which
  joins to `chunks_all` for the document, article and label.
- **Gold mark per chunk.** Not stored per chunk, but computable with the evaluation's own matcher
  (`ragpipe.relevance`, rule G2: any chunk of a gold article hits it; a grouping chunk hits every article it
  contains). It will be computed at the document, article and provision levels, with full and partial hits, and
  shown as such.
- **Check:** the first gold hit per item must equal `rank_any` / `rank_full` in `per_item.csv.gz`, and the
  unit-projection position `unit_pos`.
- **Size.** All 1,000 rows × 10 runs × 715 questions is 7.15 M rows: too much for static files. Keep the top
  *K* (proposed *K* = 100, decision D1) plus every gold-hit row below *K*, so every gold item's rank is visible.
- **Cross-stage marks:** each ranked chunk also shows whether it entered the context of that strategy at 2k / 4k
  / 8k, and in what form (kept, merged into a parent, skipped for budget).

### 3.4 Answer stage: the texts that fit in the budget

- **Feasible directly.** `contexts.jsonl.gz` holds, per question and context, the ordered `items` (`n`, rank,
  `chunk_id`, `alias_chunk_ids` for merged children, `tokens_qwen3`, `fonte`), the `gold` hits at each level, and
  the exact rendered `context` text the generator saw.
- **View:** a token bar of the budget filled item by item; each item linked back to its ranking row and to the
  document view; gold items marked; a toggle to show the full prompt (below).
- **Contexts available:** 13 jua contexts (S1 / S2 at 2k–8k, S2c, S3, S4 at 4k, oracle 4k / 16k, the
  `wrong-S2` control, `S2_budget4000_context_v1`) and 2 Gemini contexts. The `irpf_with_rir1999` side run is a
  pilot-scale run and is left out (D2). Closed-book has no context.

**The prompt, with its parts marked (D1).** The prompt is not stored as one text per answer, but it can be
rebuilt exactly from three stored parts:

| Part | Source | Shown as |
|---|---|---|
| Instructions (system message) | the prompt template, `scripts/rag/prompts/<prompt>.pt.md` before `<<<USER>>>` (`answer_v1`, `answer_closed_v1`; the run's `run.json` names it) | grey block, labelled "instructions — template `answer_v1`" |
| User frame | the template after `<<<USER>>>` (`Disposições:` … `Pergunta:`) | plain text |
| Inserted context | the `context` field of `contexts.jsonl.gz` (the `{context}` slot) | each `[Documento n]` block coloured as a context item, gold items marked, linked to panel D |
| Inserted question | `question_text` (the `{question}` slot) | highlighted |

- **Verified at build time.** The LLM cache keeps the request that was sent (`runs/answers/cache/<cache_key>.json`,
  fields `request.system` and `request.user`). The builder rebuilds each prompt and compares it with the cache,
  byte for byte. Tried on Q001, Luna, S2 4k: both messages are identical.
- **Only the parts are stored.** The template is stored once per prompt version, and the context once per
  question and context, so the page assembles the prompt in the browser and adds nothing to the file size. Each
  answer carries a flag: *verified against the request sent*, *not verifiable (no local cache)* or *differs*
  (the build fails if any answer differs).
- **Local cache coverage** (2026-11-10): 17,393 of the 20,735 answers of the 29 full runs. Missing: the four
  Gemini runs (2,860; generated on the other computer, see `two_machine_state`), the 4 × 119 oracle rows of
  questions without references (no call was made, so nothing to verify) and 6 single answers. The Gemini requests
  are in repo B's `raw/runs_answers_cache.tar.gz` (59 MB) if that archive was packed after the Gemini runs.
  Downloading it for this check only costs nothing, and the build stays local (D5). Otherwise, those answers
  show "not verifiable".

### 3.5 Answer stage: answer nuggets vs. gold set

- **What exists:** per run and question, the label of each gold nugget in the answer with the judge's
  justification (`score`), and the same label against the context (`ctxsupport`) for the 14 scored contexts.
- **The view this enables, per nugget:** *in the gold articles?* (oracle ctxsupport) → *in the retrieved context?*
  (ctxsupport of the run's context) → *in the answer?* (score label) → *contradicted?* This separates
  retrieval failures from generation failures, which a per-answer score cannot do.
- **Extra signals:** numeric value hits per nugget (`values_per_nugget`: `value_hit`, `conflict`,
  `temporal_substitution`), the documents the answer cites vs. the gold and the context (`citations_per_answer`),
  and the second judges' labels where they ran.
- **The answer's own claims ($0).** Each answer is stored as claims (`claims[].texto`), each with its grounds
  (`fundamentos`: document number in the context + quoted excerpt + a `status` from the generation-time quote
  check), plus `checks` (`quotes_ok`, `quotes_bad_document`, `claims_without_quote`, `values_not_in_context`)
  and `cited_chunk_ids`. The view lists the claims, links each ground to its context item (and so to its rank and
  its document), and marks quotes that failed the check.
- **Not available (D3: not done):** a match between the claims and the gold nuggets. The view shows the two lists
  side by side: the gold nuggets with the judge's labels, and the claims with their grounds. It does not claim
  which claim covers which nugget.

## 4. Design

### 4.1 Where it goes in the page

A new tab **"9 · Question trace"** (implemented as tab 8, before the notes, which became tab 9: `20261110_194056_question_trace_dashboard_implementation.md`), reachable from tab 7 (question explorer: a "trace" button per question) and
by URL hash (`#trace/<question>/<emb>/<strategy>/<budget>/<llm>`), so a case can be linked from notes. Tab 7
stays as the overview across runs; the trace tab follows one question through one run at a time, with a run
picker.

Layout: five stage panels in pipeline order, each collapsible, with a shared selection:

| Panel | Content | Links out |
|---|---|---|
| A · Question | text, chapter, gold answer with nugget spans highlighted, references | nugget → B, D, E; reference → B |
| B · Gold documents | per referred document, the article tree with the strategy toggle (S1 … S4) and chunk texts; gold articles marked; for a selected nugget, the three signals of §3.1 | chunk → C (its rank in each run) |
| C · Retrieval | run picker (embedding × strategy); ranked list (rank, score, document, label, gold mark, in-context mark); a "first gold hit" summary per gold item, compared across the 10 runs | row → B (chunk in its document), → D |
| D · Context | budget picker; token bar; items with merge / alias info and gold marks; rendered prompt toggle | item → C, B |
| E · Answer and nuggets | generator picker; answer claims with their grounds; nugget table (with the vital/okay badge, §8): oracle support → context support → answer label → values / contradiction, with justifications on hover; cited vs. gold documents | nugget → A, B; ground → D |

### 4.2 Data files

The static page loads data through `<script>` tags (no `fetch()` under `file://`). New files are loaded on
demand by injecting a script tag. All are gitignored (per-question data, `runs/**` rule).

| File | Content | Estimated size |
|---|---|---|
| `data/trace/index.js` | per question: chapter, number of nuggets / references, available runs | < 0.5 MB |
| `data/trace/q/<qid>.js` | question, gold answer, nugget spans, references, the three nugget→document signals; rankings top-*K* + gold rows for 10 runs with gold and in-context marks; contexts (items, gold, rendered text) for all contexts; answers and labels (score, ctxsupport, values, citations) for all scored runs | ≈ 150–250 kB each, ≈ 150 MB total (rendered contexts and answers dominate) |
| `data/trace/doc/<document_id>.js` | per document: articles in order; per chunk: id, type, label, article, ancestors, variant, tokens, strategy bitmask, text | 85 M characters over ≈ 625 files (main + annexes); median 16 kB, RIR/1999 8.5 MB |

Shared chunk lookups (chunk → document / article / label) go in the question file for the chunks it uses, so the
ranking view does not need the document files. Document files load only when a document is opened.

The prompt adds only the templates (a few kB in `index.js`); the context text is already in the question
files (§3.4).

### 4.3 Builder

New script `scripts/report/build_trace_data.py`, separate from `build_dashboard_data.py` so the main build stays
at ≈ 70 s.

- Reads the local files (D5): everything the view needs is on this computer. A `--source hf` option is left for
  later; it is not built now. The only Hub download is the optional answer-cache archive for the prompt check
  (§3.4).
- Runs: the 29 full runs (25 jua, 4 Gemini), the oracle and closed-book runs; pilot-only runs are skipped (D2).
- Reuses `ragpipe.strategies.member_mask`, `ragpipe.relevance` (gold matching) and the context-reading code, so
  nothing is reimplemented in a way that could drift from the evaluation.
- Nugget → document resolution (§3.1 signals 1 and 3) in a small module, with a report of how many `legal_basis`
  strings resolve.
- `--questions 001,028,…` for quick partial builds while developing the page.

## 5. Steps

| # | Step | Output | Check |
|---|---|---|---|
| 1 | Builder skeleton: local readers, question index, prompt templates | `index.js` | 715 questions; counts of references, nuggets as in the dataset card |
| 2 | Nugget → document signals | in `q/*.js` | share of `legal_basis` resolved, reported; oracle ctxsupport present for the 596 questions with references |
| 3 | Document files with strategy membership | `doc/*.js` | per-strategy chunk totals equal the counts in §3.2 |
| 4 | Rankings with gold and in-context marks | in `q/*.js` | first gold hit per item = `rank_any` / `rank_full` / `unit_pos` of `per_item.csv.gz`, for all items; in-context marks = `budget_any_4000` |
| 5 | Contexts, answers with claims, labels, values, citations; prompt check | in `q/*.js` | label counts per run equal `tables/nugget_labels.parquet`; context gold hits equal the context `gold` field; every rebuilt prompt equal to the cached request (count of verified / not verifiable reported) |
| 6 | Page: tab 9, panels A–E, hash links, button in tab 7 | `index.html` | rendered with headless Chrome at 1,300 px and phone width; light and dark |
| 7 | Walk-through of chosen cases (e.g. a question where S2 finds the gold article and S1 does not; a nugget supported by the context but missed by the answer; a contradiction) | screenshots in the results note | the trace agrees with tab 7 and the tables |
| 8 | Results note in `docs/`, `CLAUDE.md` pointer, update of `20261109_123355_…` §6 | | |

Steps 1–5 are data work (≈ 1 day); step 6 is the bulk of the work (≈ 1–2 days); 7–8 are short. No API calls.

## 6. Risks

- **Size and load time.** One question file of ≈ 200 kB and one document file load fast. The RIR/1999 file
  (8.5 MB) is slow; it can be split by book/title, or shown with only the articles the question cites.
- **Gold mark semantics.** The view must show the same rule as the metrics (any part of a gold article counts at
  the article level; partial vs. full at the provision level). Otherwise a reader will see "gold" chunks that the
  provision metric does not count. The panel names the level in use.
- **Heuristic link mistaken for gold.** Signal 3 of §3.1 is labelled as a heuristic everywhere it appears.
- **Data drift.** If the corpus or the runs are rebuilt, the trace must be rebuilt too. The builder writes the git
  commit and the input file hashes into `index.js`, and the page shows them.

## 7. Decisions

Asked in the first version of this note; answered by the user on 2026-11-10.

| | Question | Decision |
|---|---|---|
| D1 | Ranking depth; rendered context in the files | Top 100 + every gold hit. Keep the prompt, with its parts marked (§3.4) |
| D2 | Pilot-only runs and `irpf_with_rir1999` | Not now |
| D3 | Extract nuggets from the generated answers (LLM) | Not done: no extra cost. The generators' own claims are shown instead (§3.5) |
| D4 | LLM link from each nugget to a gold article | Not done: no extra cost. The three $0 signals of §3.1 only |
| D5 | Local files or Hub download | Local files. The local data are complete for the view; only the prompt check of the Gemini answers may need the Hub cache archive (§3.4) |

## 8. Nugget importance (vital / okay) in the view

Asked by the user on 2026-11-10: what the vital / okay distinction is, where it comes from, and whether the
dashboard shows it.

- **What it is.** "Gold nuggets" are all the nuggets of the official (gold) answers: 3,175 in
  `nuggets/gold/v0-auto/`. Each one has an importance: **vital** (2,262) or **okay** (913). The test, check C4 of
  plan v1 §3.1 (`20260926_112714_gold_answer_nuggetization_plan.md`): *would an answer to this question without
  this fact be wrong or misleading?* Yes = vital, no = okay. The `create_v4` prompt says: `vital` if a correct
  answer to this question must contain the fact; `okay` if it is useful but not essential. Project rules on top:
  every question has at least one vital nugget, except pointer answers such as Q316; "Atenção" notes are
  usually okay.
- **Where it comes from.** The vital / okay split is from the literature; the C4 test, the categories and the
  rules above are this project's own. References (links and contents checked 2026-11-10):
  - **[AN]** R. Pradeep, N. Thakur, S. Upadhyay, D. Campos, N. Craswell, J. Lin. *Initial Nugget Evaluation
    Results for the TREC 2024 RAG Track with the AutoNuggetizer Framework*. arXiv:2411.09607, 2024.
    <https://arxiv.org/abs/2411.09607>. Labels nuggets `vital` / `okay` and defines the scores used here: A,
    A_strict, V, V_strict (the primary metric), and W, with vital weighted 1 and okay 0.5. Its definition of
    vital is a quotation of Voorhees (2003).
  - **[V03a]** E. M. Voorhees. *Evaluating Answers to Definition Questions*. HLT-NAACL 2003, short papers.
    <https://aclanthology.org/N03-2037/> (PDF: <https://aclanthology.org/N03-2037.pdf>). The origin: the assessor
    marks the nuggets that must appear in a good answer as vital; the others are a "don't care" condition, and
    recall counts vital nuggets only.
  - **[V03b]** E. M. Voorhees. *Overview of the TREC 2003 Question Answering Track*. TREC 2003 (NIST SP 500-255).
    <https://trec.nist.gov/pubs/trec12/papers/QA.OVERVIEW.pdf>. The same method as used in the track.
  - **[LD06]** J. Lin, D. Demner-Fushman. *Will Pyramids Built of Nuggets Topple Over?* HLT-NAACL 2006.
    <https://aclanthology.org/N06-1049/> (PDF: <https://aclanthology.org/N06-1049.pdf>). The critique: the binary
    vital / okay split is a source of evaluation instability, since systems get credit only for vital nuggets.
    It proposes nugget pyramids, which weight nuggets by how many assessors marked them vital. This is relevant
    to our single-model labels and the flip test below.
- **How the labels were made.** The creator model (GPT-6.1 Sol, `create_v4`, one call per question; frozen from
  `gpt-6.1-sol.rep2`) labelled them. No person labelled them. Checks
  (`20261021_155704_nuggetization_phases_2_to_4_execution.md` §2.4 and later):
  - Gemini 3.1 Pro and Qwen 3.8 Max created nuggets independently. Where all three families produced the same
    nugget, they gave it the same importance 81 % of the time.
  - The audit found most planted importance errors but missed three vital → okay relabels.
  - In the phase 5 robustness test (`20261023_210727_…`), S2 − S1 stayed significant in 95 / 79 / 65 % of
    replicates (Luna) with 10 / 20 / 30 % of the labels flipped at random.
- **What the current dashboard shows.** Tab 5 says that nuggets are vital or okay, has a calculator for the
  metrics, and has a robustness chart with random vital ↔ okay flips (tab 6). Tab 7 shows each nugget's
  importance only as small grey text (`id · vital · category`). The dashboard does not show the C4 test, who
  assigned the labels, or the agreement across model families.
- **Added in the trace view:**
  - a vital / okay badge on every nugget, with the C4 test and the label's source (creator model, prompt) on
    hover;
  - the per-nugget `stability` (how many of the three families produced the nugget);
  - where the cross-family alignment links the frozen nugget to a nugget of another family, the importance that
    family gave it. The frozen set comes from `rep2` and the alignment from `rep0`, so this link is checked in
    step 2 before it is shown.
  - The same short explanation, with the references, is added to tab 5's text.
