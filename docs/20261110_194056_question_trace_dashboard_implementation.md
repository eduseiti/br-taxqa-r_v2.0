# Question trace tab: implementation and checks

**Generated:** 2026-11-10 19:40:56 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** records how the question-trace tab of the results dashboard was built, what it shows, where each
piece comes from, the files fetched from the Hub to complete this computer's data, and the checks run.
It decides nothing about the experiments, and it made no LLM calls ($0).
**Plan:** `20261110_155548_question_trace_dashboard_feasibility_and_plan.md` (decisions D1–D5 there, §7).
**Request (user, 2026-11-10):** implement that plan.

## 1. How to open and rebuild it

```bash
.venv/bin/python scripts/report/build_trace_data.py      # ≈ 7 min, reads local files only, no API calls
xdg-open "docs/dashboard/index.html#trace/350/jua-4b-mixed/S2/4000/gpt-5.6-luna"
```

- **Tab "8 · Question trace"**, between the question explorer (7) and the notes, which became tab 9. Tab 7 has a
  "Trace this question" button.
- **Link to a case:** the URL hash `#trace/<question>/<embedding>/<strategy>/<budget>/<generator>` opens it, so a
  case can be cited in a note.
- **`--questions 001,350`** builds only those question files, for quick work on the page; `--no-docs` skips the
  document files.

| Folder (`docs/dashboard/data/trace/`, gitignored) | Content | Size |
|---|---|---:|
| `index.js` | question list, runs, contexts, prompt templates, document list, build checks | 0.2 MB |
| `q/<question>.js` (715) | one question through every stage (§2) | 325 MB (median ≈ 450 kB; largest 1.1 MB) |
| `doc/dNNN.js` (453) | one document: every chunk of every strategy, with text and a strategy bitmask | 112 MB (largest 12.5 MB) |

Most of a question file is the rendered context text of its 16 generator contexts (≈ 180 kB), kept so the prompt
can be shown (D1).

## 2. What the tab shows

| Panel | Content | Source |
|---|---|---|
| Bar | question (number, ◀ ▶), embedding, strategy, budget, context (follows the strategy and budget by default, or any context incl. oracle, wrong-context control, closed book), generator | — |
| A · Question | text, official answer with each nugget's `source_span` highlighted (click selects the nugget), references with links to B, nugget table: vital/okay badge (hover: the C4 test, who labelled it, the references), the three nugget → document signals of plan §3.1, stability and the other families' importance | `dataset/`, `nuggets/gold/v0-auto/`, ctxsupport labels of `oracle_budget4000` / `16000`, alignment `nuggets/full/align/gpt-6.1-sol.rep0__*` |
| B · Gold documents | per referred document (or any document opened from C/D/A), the chunks of the selected strategy in file order, the gold article(s) and the groupings that contain them (or the whole document), with type, label, tokens, caput variant, split part, the strategies that index the chunk, its rank in the current run, and the text | `segmented/chunks_all.csv.gz`, `ragpipe.strategies.member_mask` |
| C · Retrieval | first rank at which each gold item is hit in all 10 strategy × embedding runs; the ranking of the selected run (top 30 / 100, plus every lower row that hits a gold article or provision), with gold marks at the chosen level and the in-context mark for the chosen budget | `runs/retrieval/<emb>/irpf/<S>/rankings.csv.gz`, matched with `ragpipe.relevance.Matcher` |
| D · Context | the texts of the generator context in context order, token bar (gold in green), rank links to C; the prompt sent, with its parts marked (system instructions, user frame, each inserted context text, the inserted question) and the result of the prompt check | `runs/contexts/<emb>/irpf/<context>/contexts.jsonl.gz`, `scripts/rag/prompts/*.pt.md`, `runs/answers/cache/` |
| E · Answer | the generator's claims with their grounds (context text number, quote, quote check), the generation-time checks, citations vs. gold; per gold nugget: oracle support → context support → answer label, value check, with the judge's justifications | `runs/answers/.../answers.jsonl`, `nuggets/scoring/{score,ctxsupport}/gold-v0-auto/gemini-3.8-flash/`, `nuggets/scoring/analysis/.../{values_per_nugget,citations_per_answer}.csv.gz` |

**Runs included:** the 29 full runs (25 jua, 4 Gemini), with the oracle and closed-book runs among them. The
pilot-only runs are left out (D2). 16 contexts: 14 jua (incl. `wrong-S2_budget4000` and
`S2_budget4000_context_v1`) and 2 Gemini.

**In-context marks (C).** For each ranked text and each budget (1k–16k), the builder runs the evaluation's own
`ragpipe.context.select` (`containment_merge`, overflow `skip`): `#n` = text n of the context; `in #n` = inside
text n (a parent that contains it was selected); no mark = not in the context.

**Tab 5** now has a "Vital or okay" box: the C4 test, who assigned the labels, the agreement and robustness
numbers, and the references with links (plan §8).

## 3. Data fetched from the Hub (this computer)

The plan's D5 assumed the local files were complete. They were not: the Gemini runs were made on the other
computer (memory `two_machine_state`). Missing here, and fetched from repo B (`eduseiti/BR-TaxQA-R-RAG-eval`,
staging commit `0a69ef9`, free):

| Files | Check | Placed in |
|---|---|---|
| `runs/retrieval/gemini-emb-2/irpf/{S1,S2,S3,S2c,S4}/rankings.csv.gz` | sha256 = the retrieval run's `manifest.json` outputs (5/5) | `runs/` |
| `…/eval/either_containment_merge_skip/{per_item,per_question,metrics_by_chapter}.csv.gz` | sha256 = the eval `manifest.json` (3/3) | `runs/` |
| `runs/contexts/gemini-emb-2/irpf/{S1,S2}_budget4000/contexts.jsonl.gz` | sha256 = the context `manifest.json` (2/2) | `runs/` |
| `raw/runs_answers_cache.tar.gz` | holds the cache files of all 2,860 Gemini answers | 2,726 missing files added to `runs/answers/cache/` (the others were already here, same request) |

The downloaded copy stays in `../br-taxqa-r_hf_cache/` (outside the repo).

## 4. Checks

Run by the builder on every build and shown at the bottom of the tab:

| Check | Result |
|---|---|
| Strategy chunk counts (S1/S2/S3/S2c/S4, RIR/1999 excluded) | 20,461 / 68,656 / 72,061 / 68,656 / 72,061, as in the results overview |
| First full and first any hit of every gold item, recomputed with the evaluation's matcher, vs. `per_item.csv.gz` (both embeddings, all strategies, all levels) | 59,120 / 59,120 equal |
| Budget hits (1k–16k) of every gold item vs. `per_item.csv.gz` | 295,600 / 295,600 equal |
| Recomputed context selections vs. the stored generator contexts (same strategy and budget) | 7,865 / 7,865 equal |
| Rebuilt prompt (template + context + question) vs. the request in the LLM cache, byte for byte | 20,253 verified, 0 differ; not verifiable: 476 `skipped` rows (no context, no call) and 6 `error` rows |
| Judge label count per run vs. `runs.csv` `n` | 29 / 29 equal |
| Prompt templates unchanged since the runs (sha256 vs. `run.json`) | `answer_v1`, `answer_closed_v1`: unchanged |
| Nugget `legal_basis` strings resolved to a document | 625 of 677 (92 %), all to a document the question cites; 29 name a document not in the corpus; 23 have no document number |

**Rendering:** headless Chromium (Playwright, from the scratchpad, not a repo dependency) at 1,300 px light and
390 px dark, on Q350 (jua S2 4k Luna), Q001 (Gemini S1 4k Sabiá-4), Q316 (jua S1 2k, no Sabiazinho-4 run) and
Q005 (jua S3 4k Terra), clicking a nugget, the prompt button, a ranked row and a justification; phone width also
on Q442 and Q120. Final run: no JavaScript errors, no horizontal page scroll (1,300 and 390 px). Screenshots
looked at. Fixed after that review:
- the "inside a selected parent" mark used the colour of a partial provision hit;
- B called a non-gold focused article "gold";
- B opened in S2 when the link asked for S1;
- a pasted trace link did not reload the case (no `hashchange` handler);
- legal-basis citations with the article after the document ("Lei nº 9.250, …, art. 35") lost the article, and
  "Ato Declaratório PGFN nº 2, de 2016" resolved to the RFB ADE nº 2 of 2024. The resolver now also checks the
  year and the document type prefix (`ad_`, `adi_`, `lei_comp_`, `mp_`…). Resolved strings went from 496 to 625
  of 677;
- a long URN in B's document header widened the page at phone width (390 px → 564 px).

## 5. Limits

- **The nugget → document link is a set of signals, not a gold link** (plan §3.1; D4: no LLM attribution). The
  BM25 candidate is labelled as a heuristic. Legal-basis strings with no document number (e.g. "art. 8º" alone,
  which refers to the document the answer cites elsewhere) stay unresolved.
- **No nuggets are extracted from the answers** (D3). E shows the generator's claims next to the judged gold
  nuggets; it does not say which claim covers which nugget.
- **Gold marks for oracle and other non-strategy contexts in D** come from the chunk's own article, not from the
  matcher (a grouping chunk there is marked only at the document level).
- **Size:** ≈ 440 MB of gitignored files. A question file loads in well under a second from disk; the largest
  document file (12.5 MB) takes a moment.
- **Tab 7's per-question files** were also missing on this computer; `build_dashboard_data.py` was rerun
  (`core.js` changed only in its build time; `docs.js` now holds this note and the plan).
- **No automated test suite for the page**; the checks above cover the data, the screenshots the rendering.
