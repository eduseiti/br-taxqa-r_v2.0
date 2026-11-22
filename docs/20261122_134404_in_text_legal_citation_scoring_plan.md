# Plan: scoring the legal provisions that generators cite in their answer text

Date: 2026-11-22. Plan note (nothing implemented yet). It extends the phase 5 citation analysis
(`docs/20261023_210727_rag_phase5_scoring_and_analysis.md` §6.2, open item 3 of §9) to the citations
the generators **write in their answers** ("conforme o art. 8º, inciso II, da Lei nº 9.250, de 1995").
It also records how the closed-book runs were kept free of web search (§1), which is what makes the
closed-book answers a test of the models' own (parametric) knowledge.

## Summary

- **Closed book measures parametric knowledge only; web search was blocked at the API level.**
  - No request can carry tools, plugins, web-search options or an `:online` model.
  - Every reply is checked for tool use, URL citations, search sources and extra billing.
  - All 18,618 generation calls ended `stop`, none rejected.

  The prompt has no explicit "do not search" instruction. None is needed, since the model has no tool to
  call, and adding one would mean regenerating all closed-book answers. Residual limits: provider
  self-reporting (Maritaca), and the P&R 2024 being in the training data.
- **What is scored today:** for RAG answers, only the context texts each claim links to as its sources
  (`cited_chunk_ids`), with the retrieval matcher. **Not scored:**
  - the in-text citations of the closed-book answers. 39–79% of these answers cite an article, by
    generator (Terra 79%, Sabiá-4 76%, Sabiazinho-4 61%, Luna 39%);
  - the in-text citations of the RAG answers.
- **Proposed:**
  1. extract the in-text citations of every answer (`scripts/dataset/citations.py` for the provision
     chains);
  2. resolve each act to a corpus document (`lexml-linker` for federal acts, plus a regex resolver for Receita
     Federal acts, plus an alias table for names like RIR/2018);
  3. score against the gold references at the document, article and provision levels;
  4. flag citations of non-existent articles, acts outside the corpus and acts from after the reference
     date.

  For RAG answers, also compare each claim's in-text citations with the sources it links to and with its
  context.
- **Cost:** no API calls. Effort: roughly 2–3 days of implementation and validation, most of it the act
  resolver and a manual check of 100–150 citations.

## 1. Closed book as a test of parametric knowledge

### 1.1 Web search and tools are blocked at the API level

Design: `docs/20261021_194457_first_rag_evaluation_readiness_costs_and_grounding.md` §4.1.
Implementation: `scripts/llm_client/client.py` (`FORBIDDEN_PARAMS`, `tool_use()`, `ToolUseDetected`,
`BILLED_TOLERANCE_USD`). The same client serves the RAG and closed-book runs.

**Requests.**
- The client refuses any registry entry (`scripts/rag/llms.yaml`) with `tools`, `tool_choice`,
  `plugins`, `web_search_options`, `web_search` or `functions`, and any OpenRouter model id ending in
  `:online`.
- On OpenRouter, web search runs only through the `web` plugin or the `:online` suffix. OpenAI and
  Gemini search grounding run only as tools.
- The OpenRouter calls (GPT-5.6 Terra and Luna) are pinned to one upstream (`only: [openai/flex]`,
  `allow_fallbacks: false`, `require_parameters: true`), and the serving provider is checked on every
  reply.

**Maritaca.** Its built-in tools (web search, page reading, code execution, Data Ocean) run only when
the request lists them. Ours never do.

**Replies.** A reply is rejected (not retried; ledger `finish = rejected:<reason>`) when it shows any
of:
- `tool_calls`;
- `url_citation` annotations;
- `web_search_sources`;
- `usage.tool_execution_details` (Maritaca's report of a search or page read);
- `usage.server_tool_use`;
- a billed cost (OpenRouter `usage.cost`) above the token cost. The web plugin adds $0.01 per request.

**Record.** `runs/costs.csv` has 18,618 generation calls (Luna 5,675; Sabiá-4 5,674; Sabiazinho-4
4,308; Terra 2,961). All ended `stop`; none was rejected for tool use or billing.

### 1.2 No explicit "do not search" instruction in the prompt

`scripts/rag/prompts/answer_closed_v1.pt.md` says to answer "com base no seu conhecimento da
legislação tributária" ("based on your knowledge of the tax legislation") and that no documents are
given. It does not say "do not search the internet". Decision: **leave the prompt as it is.**

- The instruction would have no effect: the model has no tool to call.
- Changing the prompt would mean a new version (`answer_closed_v2`) and regenerating and rescoring
  4 × 715 closed-book answers, or else the new answers would not be comparable with the existing ones.
  The cost would be small, but the change would buy nothing.
- If a future prompt revision happens for other reasons, add the sentence then. It documents the
  intent for readers of the prompt.

### 1.3 What "parametric knowledge" includes, and the limits to state in the paper

- **Provider self-reporting.** The request guard and the billing check are under our control. The
  reply checks rely on each provider reporting its tool use. For Maritaca, the guarantee is that the
  requests never list tools, plus its own usage report. That is strong, but not independent proof.
- **The P&R itself is probably in the training data.** The P&R 2024 is public (May 2024). The GPT-5.6
  cutoff is 2026-02-16; Maritaca publishes none. Closed-book scores therefore mix legal knowledge with
  possible memorisation of the gold answers (grounding note §4.2, item 6).
- **Later years leak in.** Models know rules and acts from after the reference date (exercise 2024,
  calendar year 2023). The value checks of phase 5 catch values from later years. This plan adds the
  same check for cited acts (§3.5).

Suggested wording for the paper: *"In the closed-book condition no documents were provided; tools and
web search were disabled at the API level and every response was verified to contain no tool use, so
the answers reflect the models' parametric knowledge (which may include the public Q&A document
itself)."*

## 2. Questions this plan answers

1. **Closed book:** when a model cites a provision from memory, is it the provision the P&R cites?
   This is the per-generator recall and precision at the document, article and provision levels.
2. **Validity:** how often does a model cite an act or article that does not exist (in the corpus),
   or one from after the reference date, or a revoked act (RIR/1999)?
3. **RAG answers:** do the in-text citations agree with the sources each claim links to? How often do
   they name a provision that is not in the context at all, so it comes from the model's own
   knowledge?
4. **Link with answer quality:** do answers that cite the right provision score higher (V_strict)?

## 3. Method

### 3.1 Input

- Closed book: `runs/answers/jua-4b-mixed/irpf/answer_closed_v1/<llm>/closed_book/answers.jsonl`,
  4 generators × 715 questions. These don't depend on the embedding: no retrieval.
- RAG: the 25 trimmed-grid runs and the gemini-emb-2 runs. The headline runs are `S1_budget4000`,
  `S2_budget4000` and `oracle_budget4000`.
- Each answer line has `claims` (list of `{texto, fundamentos}`). The claim text is the unit of
  extraction, so each citation is tied to a claim and to that claim's sources.
- Gold: `dataset/references.jsonl` through `ragpipe.relevance.gold_items` (596 questions with legal
  references). The other 119 questions get only the validity checks (§3.5).

### 3.2 Extraction of provision chains

`scripts/dataset/citations.py` already handles the P&R citation style:
- `find_chains()` finds the chains of provision tokens;
- `chain_units()` turns them into nested LexML ids (`art12_par1_inc2`), handling the reverse form
  ("inciso II do § 1º do art. 162") and sibling lists ("art. 26 e parágrafo único").

Generator text is close to the P&R's: the prompt asks for "conforme o art. 8º, inciso II, alínea "b",
da Lei nº 9.250, de 1995".

Expected gaps, to be checked on a sample before scoring:
- "caput" and "parágrafo único" written out;
- "art. 8º, II, b" (bare numerals);
- "arts. 1º a 3º" ranges;
- citations without an article ("conforme a Lei nº 9.250, de 1995"), which are document-level only.

### 3.3 Act resolution (the main work)

Each chain must be attributed to an act, and the act resolved to a `document_id` of
`dataset/documents.jsonl` (453 documents, 209 statutory). Three resolvers, tried in order:

1. **`lexml-linker`** (`linkertool`, installed locally; run with `LANG=C.UTF-8` and the text on stdin).
   It resolves federal acts with the provision path, including year-only dates and the "9.250/1995"
   form:
   - "art. 39 da Lei nº 11.196, de 2005" → `urn:lex:br:federal:lei:2005;11196!art39`;
   - "art. 6º, inciso XIV, da Lei nº 7.713, de 22 de dezembro de 1988" →
     `…lei:1988-12-22;7713!art6_cpt_inc14`.

   It returns **nothing** for Receita Federal acts ("Instrução Normativa RFB nº 2.179, de 2024") or for
   "Regulamento do Imposto sobre a Renda – RIR/2018". Map the URN to a `document_id` by authority, type,
   number and year (the URNs in `documents.jsonl` have full dates; generators often give only the
   year). The fragment after `!` is a LexML id usable directly.
2. **Regex resolver for Receita Federal and other acts.** Type + issuing body + number + year, for
   Instrução Normativa (RFB/SRF), Ato Declaratório (Executivo/Interpretativo/Normativo), Solução de
   Consulta (COSIT), Parecer Normativo, Portaria, Nota… These are the `in_`, `ade_`, `adi_`, `sc_`, `pn_`…
   stems of the corpus. Match against the document list by (type, number, year). Then reuse the
   attribution logic of `citations.attribute()` ("do/da <act>" binds a chain to the next act mention,
   otherwise to the closest previous one), with the detected acts as `titles`.
3. **Alias table** for names without a number: RIR/2018 → `decreto_9580_20181122`, RIR/1999 →
   `decreto_3000_19990326`, CTN, Constituição Federal, Lei do IRPF… The table is small, written by hand
   and kept in `scripts/nuggets/` next to the scorer.

**Unresolved acts** are kept with their text, in two categories:
- `act_not_in_corpus`: well-formed, with a type, number and year, but absent from the corpus. It may
  be real (the P&R never cites it) or invented; this can't be told offline. Sample them by hand, e.g.
  check whether the "IN RFB nº 2.179, de 2024" that Sabiá-4 cites exists. The P&R cites IN RFB
  nº 2.178 for that question;
- `unparsed`: an act mention or chain with no act.

The resolver's coverage (share of chains attributed to a corpus document) is a reported figure, per
generator.

### 3.4 Scoring against the gold references

For each answer: the set of cited units at three levels (document; `(document, article)`;
`(document, LexML id)`). Compare with the question's gold items using the rules of
`ragpipe/relevance.py`:
- **document level:** same `document_id`;
- **article level:** same article in the same file, with the annex rule G3 (`either`), as in the
  retrieval evaluation;
- **provision level:**
  - full match when the cited unit equals the gold unit or is its ancestor. The answer cites a larger
    unit that contains the gold one, the analogue of G5;
  - partial match when the cited unit is a descendant of the gold unit.

Report the full and partial matches separately, since "art. 8º" for a gold "art. 8º, II, b" is
right but coarse.

Metrics per run and level:
- **cited recall:** the share of gold items the answer cites;
- **cited precision:** the share of the answer's cited units that match a gold item;
- **cited@any:** whether the answer cites at least one gold item.

Use the same definitions as `citations_runs.csv`, so closed book, the in-text RAG citations and the
linked sources sit in one table. Compute them over answers that cite something, and also over all
answers (no citation = zero recall), with the citation rate reported beside them.

Caveat: the gold set is what the P&R cites. A correct provision that the P&R does not cite counts as
wrong. Precision is a lower bound, as for the linked-source scores.

### 3.5 Validity checks (all 715 questions)

- **Non-existent article.** The act resolves to a corpus document but the article (or unit) id is not
  in its LexML (`lexml/`; the chunk table's `artigo_id` / `unidade_id`). This is a strong hallucination
  signal.
- **Act outside the corpus** (`act_not_in_corpus`, §3.3), with a manual sample.
- **After the reference date.** The act is dated after 2024-05 (e.g. the INs that govern the 2025
  return): parametric knowledge from later years, the citation analogue of the phase 5 value checks.
- **Revoked act.** RIR/1999 (excluded from the main corpus, `scripts/rag/corpus_exclusions.yaml`) or
  other acts revoked before 2024.

### 3.6 RAG answers: in-text citations vs linked sources vs context

For each claim of a RAG answer, map the resolved in-text citations to chunks of that question's
context: the same document and an article or unit the chunk covers (`cobre_ids` / `artigo_id`).
Then classify each in-text citation:
- `in_sources`: it matches one of the claim's own linked sources (`fundamentos` → `cited_chunk_ids`);
- `in_context_not_sources`: it matches another chunk of the context;
- `outside_context`: no context chunk holds it. This is parametric knowledge used in a RAG answer, a
  per-citation leakage figure to set beside the nugget-level leakage (phase 5 `utilisation_runs.csv`).

By strategy: does S2 lower `outside_context` compared with S1, because the cited paragraph is now in
the context?

### 3.7 Link with answer quality

Per question, for closed book and for S1/S2 at 4000:
- V_strict of answers with a correct citation at the article level vs answers with none or only wrong
  ones (paired across generators where possible);
- a Spearman correlation between cited recall and V_strict.

This is descriptive: both depend on the question's difficulty.

## 4. Validation

- **Unit tests** for the new pieces: generator-style citation forms, the act regexes, the alias table,
  and the linker-URN → `document_id` mapping. Add them to the existing tests of `citations.py`
  (`scripts/dataset/tests/` if present, otherwise `scripts/nuggets/tests/`).
- **Manual check** of 100–150 citations, stratified by generator and by closed book vs RAG. For each,
  check the extraction (chain → units), the act attribution and the resolution. Target: ≥ 95%
  correct attribution among resolved citations. Report the error rate in the note.
- **Sanity check on the oracle runs.** In-text citations of `oracle_budget4000` answers should mostly
  be `in_sources` or `in_context_not_sources`, and their cited precision should come close to the
  linked-source precision (0.77–0.81 at the article level).

## 5. Implementation

- New module `scripts/nuggets/nuggetizer/intext_citations.py`:
  - extraction (`citations.find_chains` / `chain_units`);
  - act detection and resolution (linker via subprocess, batched; regex; alias table);
  - scoring with `ragpipe.relevance.Matcher` / `ProvisionScorer`;
  - context mapping (§3.6).
- Wired into `nuggets.py analyze` as one more step (no LLM calls), writing to
  `nuggets/scoring/analysis/<gold>/<judge>/<set>/`:
  - `intext_citations.csv.gz` — one row per extracted citation: run, question, claim, raw text,
    act, document_id, unit, resolver, validity flags, match level, §3.6 class;
  - `intext_citations_runs.csv` — per run × level: citation rate, recall, precision, cited@any,
    resolver coverage, invalid / outside-corpus / later-year / revoked shares, §3.6 class shares;
  - `intext_vs_quality.csv` — §3.7.
- The linker runs once per distinct claim text, with results cached in a gitignored folder. Expect
  tens of thousands of claims; at the linker's speed this should take minutes. Measure it on one run
  first.
- Results note in `docs/`, then a pointer in `CLAUDE.md` and in `scripts/nuggets/README.md`.
- Optionally later: an in-text citation panel in the explorer's question trace.

## 6. Steps

1. **Survey** (½ day): extract the claims of the 4 closed-book runs and 2 RAG runs. Run `find_chains`
   and the linker. Count the citation forms that fail, and draft the act regexes and the alias table
   from what generators actually write.
2. **Resolver + tests** (1 day).
3. **Scoring + validity + §3.6** (½–1 day). First on closed book and `S1/S2/oracle_budget4000`, then all
   runs.
4. **Manual check** (§4) and fixes (½ day).
5. **Results note**, tables, pointer in `CLAUDE.md`.

## 7. Open decisions

1. Whether citations of acts outside the corpus count as wrong in precision (default: yes, reported
   separately so they can be excluded).
2. Whether a coarse citation (the article, for a gold inciso) counts as correct at the provision level
   (default: full match by the G5 analogy, with the partial/descendant case reported apart).
3. How far to verify acts outside the corpus: a manual sample only (default), or a lookup in the
   sibling `br-taxqa-document-fetcher` / LexML.
4. Whether to add the "do not search" sentence at the next closed-book prompt revision (§1.2; default:
   only if the prompt changes for another reason).
