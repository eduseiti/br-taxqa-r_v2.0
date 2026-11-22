# A2: in-text legal citations of the generated answers — implementation and first results

Date: 2026-11-22. Results note for item A2 of
`docs/20261122_164407_methodology_additions_plan_token_weighted_citations_sol_and_fix_b.md`, following the design in
`docs/20261122_134404_in_text_legal_citation_scoring_plan.md`. No API calls; $0.

## Summary

- **Implemented** `scripts/nuggets/nuggetizer/intext_citations.py` and the command `nuggets.py intext`, which takes
  ≈ 40 s for all 108 answer runs. Tests are in `scripts/nuggets/tests/test_intext_citations.py` (19 tests, all
  passing).
- **Outputs:** `nuggets/scoring/analysis/gold-v0-auto/gemini-3.8-flash/all/intext/`.
- **Validation:**
  - **Manual check:** 2 × 120 citations, stratified by generator × (closed book, RAG 4k). The first round found
    5 errors (95.8%). After the fixes, a new sample had 2 errors (98.3%), and one of them is now fixed too.
    Stage 3's gate (≥ 95% correct attribution) is met.
  - **`lexml-linker` cross-check:** the act detector finds 3,184 of the linker's 3,184 federal acts in the
    closed-book claims. It also finds 268 more through aliases (RIR, CTN, Código Civil…) that the linker does not
    know.
  - **Oracle sanity check:** with the oracle 4k context, the article-level precision of the in-text citations is
    0.81–0.91, at or above the 0.77–0.81 of the linked sources. As expected.
- **Closed book: GPT-5.6 Terra cites best from memory, but cites the P&R's own article in only 32% of the questions.**
  (Article level, the 596 questions with gold references.)
  - **Terra** cites an article in 80% of its answers. Its cited articles are right in 30%.
  - **Luna** cites less often (39%) but is the most precise (38%).
  - **The Maritaca models** cite often (Sabiá-4 77%, Sabiazinho-4 58%) but rarely the right article (precision 15%
    and 9%).
- **Hallucination signals are 3–7× higher for the Maritaca models in closed book:**
  - articles that do not exist in the cited act: 5–7%, against 0.7–1.0% for GPT;
  - units (paragraph, inciso…) that do not exist in an existing article: 17–22%, against 7–8%;
  - acts outside the corpus: 13–15%, against 2–3%. Sabiá-4 alone cites "IN RFB nº 2.179, de 2024" 54 times for
    the 2024 return rules; the P&R cites IN RFB nº 2.178, de 2024.
  - Citations of the revoked RIR/1999: Sabiazinho-4 16, Sabiá-4 6, Luna 1, Terra 0.
- **No act from 2025 or later is cited** in any run, so the year-level check for later-year knowledge is negative.
  Acts from 2024 that are outside the corpus and written without a day can't be dated offline (§4.3).
- **RAG:**
  - **In-text citation rates drop a lot for the Maritaca models.** In closed book they cite in 58–77% of their
    answers, with RAG at 4k in 16–38%; they lean on the linked sources instead. The GPT models keep citing in
    82–90% of their RAG answers.
  - **S2 lowers the share of in-text article citations outside the context** for every generator (§3.6 of the
    citation plan). Terra goes from 19.0% to 12.4%, Luna from 14.2% to 10.2%, Sabiá-4 from 24.2% to 14.1% and
    Sabiazinho-4 from 42.8% to 40.4%.
  - **Hardly any citation is in the context but not in the claim's sources** (1–4%). A citation that is in the
    context is almost always the claim's own source.
- **Link with quality** (descriptive): answers that cite a gold article score higher on V_strict than answers
  that cite only wrong articles. Terra closed book: 0.426 vs 0.324; Terra S2 4k: 0.421 vs 0.226.

## 1. What was built

### 1.1 Pipeline (`nuggetizer/intext_citations.py`)

1. **Act detection** (`find_acts`), claim by claim. Three kinds of mention:
   - **Numbered acts, by regex.** Type and issuer, then "nº", the number, and a date or year. All the written
     forms seen in the survey are covered:
     - `Lei nº 9.250, de 1995`, `Lei 7.713/88`, `Lei nº 7.713` (no year);
     - `Instrução Normativa RFB nº 2.178, de 5 de março de 2024`, `IN nº 84/2001`, `IN SRF nº 15, de 2001`;
     - `Solução de Consulta (Interna) Cosit nº …`, `Solução de Divergência`;
     - `Parecer Normativo CST/Cosit`;
     - `Ato Declaratório (Interpretativo|Normativo|Executivo) …`;
     - `Medida Provisória nº 2.158-35`, `Decreto-Lei`, `Lei Complementar`, `Portaria`, `Resolução`, `Nota`,
       `Súmula`, `Emenda Constitucional`.
   - **Named acts, by an alias table:**
     - RIR/2018 (also "Regulamento do Imposto sobre a Renda … 2018"), RIR/1999 and RIR/99, RIR/94, /80 and /75;
     - CTN, Código Civil, Constituição Federal, ECA, Estatuto do Idoso / da Pessoa Idosa, CLT, CPC.

     "Regulamento do Imposto de Renda" without a year is read as RIR/2018 (resolver `alias_default`, 15 closed-book
     citations). When the name is followed by "(Decreto nº …)" or "aprovado pelo Decreto nº …", the numbered decree
     decides, and the two count as one act.
   - **Anaphors:**
     - "da mesma Lei", "do referido Decreto", "desta Instrução Normativa", "do citado diploma";
     - a bare type word without a number ("do art. 10 da Lei").

     They point back to the previous act of the same type, in the claim or in earlier claims of the same answer.
2. **Resolution** to `dataset/documents.jsonl`: type family (from the `document_id` prefix) + number (dots removed;
   "MP nº 2.158" also matches 2.158-35) + year when given; the issuer (IN SRF vs RFB, PN CST vs Cosit, ADI/ADN/ADE)
   only breaks ties. Outcomes: `corpus`, `ambiguous` (3 cases in all runs), `not_in_corpus` (kept as
   `family:number:year`), `unresolved` (anaphor with nothing to point to).
3. **Provision chains:** `scripts/dataset/citations.py` (`find_chains`, `chain_units`), unchanged. A chain is
   attributed to an act by these rules, in order:
   - **genitive:** "art. 8º, § 2º, da Lei …" (also "art. 725 e seguintes do Decreto …") binds to the act right after;
   - **before:** otherwise, the closest act before the chain in the claim (the P&R style "Lei nº …, art. 8º");
   - **after:** otherwise, the closest act after it;
   - **carried:** otherwise, the last act of the previous claims of the same answer;
   - **none:** otherwise, the chain stays unattributed.

   Chains with no article (or numbered annex) count only when they bind directly to an act ("item 2 do Parecer
   Normativo CST nº 60"). This drops "outros anexos", "item 5 da ficha" and the like. An act mentioned with no
   chain is a **document-level citation** (`act_only`).
4. **Fixes found by the survey and the manual check:**
   - acts after "com a redação dada pela", "alterado pelo", "incluído pela" are amending acts, not citations, and are
     skipped;
   - "constituição" as a common noun ("constituição de servidão") is not the Constitution; a qualifier is required;
   - "§ 1º" of an article that has only a parágrafo único is rewritten to `par1u`, and the reverse (53 closed-book
     citations). This applies to existence and to the gold match.

### 1.2 Scoring

- **Gold:** the gold items of `ragpipe.relevance.gold_items` (596 questions). Recall uses the same denominators as
  the retrieval evaluation: all gold items of the level, including unreachable provisions.
- **Match rules** (`unit_matches`, defaults of citation plan §7, D6):
  - **document:** same `document_id`;
  - **article:** same article, with annex rule `either`. A citation that names an annex ("Anexo I, art. 10")
    matches only that file when the gold item names files;
  - **provision:** full when the cited unit equals the gold unit or is its ancestor (the coarse citation "art. 8º"
    for a gold "art. 8º, II, b"); partial when the cited unit is a descendant of the gold unit. The two are
    reported apart (`recall_any`, `precision_any`).
- **Per answer and level:**
  - recall over all answers with gold (an answer with no citation has zero recall), and over citing answers;
  - precision over citing answers. The cited units are distinct `(act, article)` / `(act, fragment)` pairs, and
    acts outside the corpus count as wrong;
  - `precision_in_corpus` leaves out the acts outside the corpus;
  - `cited_any`: the answer cites at least one gold item.
- **Validity, all 715 questions:**
  - `article_missing` / `unit_missing`: against the LexML units of the document (`segmented/unit_tokens.csv.gz`, any
    file of the document). Only for resolved documents that have articles;
  - `not_in_corpus`;
  - `later`: dated after 2024-05-03, the P&R date. The full date is used when written or known from the corpus,
    otherwise the year; a 2024 act without a day stays undetermined;
  - `revoked`: RIR/1999, /94, /80, /75.
- **Context class (§3.6), RAG runs:** each citation is turned into an article- or provision-level item and matched
  with the retrieval `Matcher` (G2–G5). The class is then:
  - `in_sources`: it hits one of the claim's `fundamentos` texts;
  - `in_context_not_sources`: it hits another text of the context;
  - `outside_context`: no context text holds it.

  The same is done at the document level.

### 1.3 Deviation from the plan: `lexml-linker` is a cross-check, not the resolver

The linker's XML output (`linkertool -x`) gives one span that merges the chain with the act ("art. 39 da Lei nº
11.196, de 2005"). It also returns nothing for Receita Federal acts or aliases, so a regex detector is needed anyway.
One detector for all acts keeps the act positions the attribution needs in one place. The linker is run on every
closed-book claim as a check (`linker_crosscheck.json`):

| | count |
|---|---:|
| Federal act found by both | 3,184 |
| Linker only | 0 |
| Regex only, numbered act | 1 |
| Regex only, alias (RIR, CTN, Código Civil, ECA…) | 268 |

## 2. Validation

### 2.1 Manual check

| Round | Sample | Errors | Correct | Errors found |
|---|---|---:|---:|---|
| 1 (before fixes) | 120 (8 strata × 15, seed 7) | 5 | 95.8% | (a) "art. 75 do Regulamento …, aprovado pelo Decreto nº 9.580" bound to the previous law; (b), (c) "constituição de servidão" taken as the Constitution (×2); (d) an amending act ("redação dada pela Lei nº 12.844") counted as cited; (e) a `carried` chain ("O art. 49 referido no parecer") bound to the parecer |
| 2 (after fixes) | 120 (seed 2026) | 2 | 98.3% | (f) "art. 725 e seguintes do Decreto nº 9.580" bound to the previous law (fixed afterwards); (g) "doações … ao Estatuto do Idoso" (the fund) counted as a document-level citation of the Estatuto |

- (a)–(d) and (f) are fixed and covered by tests.
- (e) and (g) remain:
  - `carried` is 10 of 4,264 closed-book citations;
  - a named statute mentioned without a citation is rare.
- Model errors are not counted as extraction errors, since the extraction reads them correctly. Examples: "Lei nº
  123, de 2006" for LC 123; "art. 190 da Lei nº 8.069/1970"; claims cut after "alínea".

### 2.2 Coverage of the resolver (closed book, 4 generators, 4,264 citation rows)

| Outcome | Rows |
|---|---:|
| Resolved to a corpus document | 3,884 (91.1%) |
| Act outside the corpus | 364 (8.5%) |
| Chain with no act | 16 (0.4%) |

- Resolvers: regex 3,885, alias 339, `alias_default` 15, anaphor 9.
- Bindings: genitive 3,795, act only 359, before 66, after 18, none 16, carried 10.
- In RAG runs, chains with no act are more frequent: 0.2–0.6% for GPT, 6–7% for Sabiá-4 and 23–24% for Sabiazinho-4.
  They are mostly "conforme o art. 63" or "arts. 26 a 45", where the act is the claim's source document. They are
  left unattributed (see §5).

## 3. Closed book: citations from memory

Questions with gold references, article level (document and provision in `intext_citations_runs.csv`):

| Generator | Answers citing an article | Recall (all answers) | cited@any | Recall (citing) | Precision (citing) |
|---|---:|---:|---:|---:|---:|
| GPT-5.6 Terra | 79.6% | 0.138 | 0.320 | 0.170 | 0.295 |
| GPT-5.6 Luna | 39.3% | 0.082 | 0.203 | 0.194 | 0.384 |
| Sabiá-4 | 76.5% | 0.060 | 0.165 | 0.077 | 0.146 |
| Sabiazinho-4 | 57.6% | 0.027 | 0.078 | 0.045 | 0.092 |

- **Document level** (cited@any): Terra 0.458, Sabiá-4 0.328, Luna 0.261, Sabiazinho-4 0.260.
- **Provision level:** full recall over all answers is 0.093 (Terra), 0.063, 0.041 and 0.018. Precision counting
  partial matches is 0.26, 0.35, 0.12 and 0.08.
- Coarse citations ("art. 8º" for a gold inciso) are full matches; finer-than-gold citations are rare (recall_any −
  recall ≤ 0.02).

### 3.1 Validity (all questions)

| Generator | Citations | Act outside corpus | Article missing | Unit missing | Revoked (RIR/1999) | Act ≥ 2025 |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Terra | 1,344 | 3.0% | 0.7% | 7.8% | 0 | 0 |
| GPT-5.6 Luna | 633 | 1.9% | 1.0% | 6.5% | 1 | 0 |
| Sabiá-4 | 1,370 | 14.5% | 5.2% | 21.6% | 6 | 0 |
| Sabiazinho-4 | 917 | 12.5% | 6.5% | 16.5% | 16 | 0 |

- **"Unit missing":** the article exists but the cited paragraph, inciso or alínea does not. Examples: Lei 9.250
  art. 8º inciso VII (art. 8º has two incisos); RIR art. 153 parágrafo único (it has §§ 1º–3º).
- **Acts outside the corpus, most cited:**
  - Sabiá-4: IN RFB 2.179/2024 (54), 2.172/2023, 2.171/2023, 2.110/2022 (10 each), ECA, IN 2.168/2023;
  - Sabiazinho-4: IN RFB 2.177/2024 (6), 2.179/2024 (5), 2.010/2021, Lei 8.012/1990, IN RFB 213/2022, Lei
    10.637/2002;
  - GPT: IN SRF 15/2001, Lei 8.218/1991, Súmula 215 STJ, Lei 14.663/2023, Estatuto do Idoso, CPC (≤ 2 each).

  These may be real acts the P&R doesn't cite, or invented ones. Only a lookup can tell (citation plan §7.3; not
  done).

## 4. RAG answers

### 4.1 In-text citations, article level (4k, primary embedding)

| Generator | Context | Citing | Recall (all) | cited@any | Precision (citing) |
|---|---|---:|---:|---:|---:|
| Terra | S1 | 82.3% | 0.332 | 0.594 | 0.525 |
| Terra | S2 | 90.4% | 0.375 | 0.672 | 0.536 |
| Terra | oracle | 88.9% | 0.574 | 0.894 | 0.907 |
| Luna | S1 | 85.6% | 0.359 | 0.645 | 0.538 |
| Luna | S2 | 89.8% | 0.393 | 0.685 | 0.501 |
| Luna | oracle | 89.8% | 0.593 | 0.899 | 0.910 |
| Sabiá-4 | S1 | 34.3% | 0.135 | 0.249 | 0.488 |
| Sabiá-4 | S2 | 34.6% | 0.151 | 0.268 | 0.465 |
| Sabiá-4 | oracle | 47.5% | 0.328 | 0.464 | 0.874 |
| Sabiazinho-4 | S1 | 21.2% | 0.065 | 0.136 | 0.434 |
| Sabiazinho-4 | S2 | 16.1% | 0.053 | 0.098 | 0.432 |
| Sabiazinho-4 | oracle | 15.5% | 0.077 | 0.140 | 0.806 |

- **In-text recall rises from S1 to S2** for Terra, Luna and Sabiá-4 (+0.02 to +0.04), and falls for Sabiazinho-4,
  which cites less in the text under S2.
- **The Maritaca models cite in the text far less with RAG than in closed book** (Sabiá-4 77% → 35%; Sabiazinho-4
  58% → 16–21%). They seem to leave the legal basis to the linked sources. For them, the linked-source scores of
  phase 5 are the better measure of legal grounding.
- In-text precision with retrieval (0.43–0.54) is at the level of the linked sources. With the oracle (0.81–0.91),
  it is above them: the sanity check of citation plan §4.

### 4.2 In-text citations vs the claim's sources vs the context (citation plan §3.6), article level, 4k

| Generator | Context | In the claim's sources | In context, not in sources | Outside the context |
|---|---|---:|---:|---:|
| Terra | S1 | 79.4% | 1.7% | 19.0% |
| Terra | S2 | 86.0% | 1.6% | 12.4% |
| Terra | oracle | 86.4% | 2.2% | 11.4% |
| Luna | S1 | 84.6% | 1.2% | 14.2% |
| Luna | S2 | 88.3% | 1.6% | 10.2% |
| Luna | oracle | 87.6% | 1.6% | 10.8% |
| Sabiá-4 | S1 | 74.1% | 1.7% | 24.2% |
| Sabiá-4 | S2 | 84.4% | 1.5% | 14.1% |
| Sabiá-4 | oracle | 85.9% | 1.9% | 12.2% |
| Sabiazinho-4 | S1 | 53.6% | 3.6% | 42.8% |
| Sabiazinho-4 | S2 | 56.3% | 3.3% | 40.4% |
| Sabiazinho-4 | oracle | 58.0% | 3.4% | 38.6% |

- **S2 cuts the in-text citations from outside the context** by about a third for the GPT models and by 42% for
  Sabiá-4. A likely reason is that the cited paragraph or inciso is now in the context as its own text. This is the
  in-text analogue of the phase 5 result that S2 helps on sub-article questions (granularity note §3).
- **10–14% of the GPT models' article citations stay outside the context, even with the oracle.** This is a floor of
  parametric knowledge used in RAG answers, at the citation level: "per-citation leakage", beside the nugget-level
  leakage of `utilisation_runs.csv`. It is also the baseline for A3's H3 (Sol).
- **Sabiazinho-4's ≈ 40% outside the context** mixes real leakage with unattributed chains read as the wrong act,
  which are not in this table, and with its weaker matching of claims to sources. Read it with care.
- Revoked acts in RAG answers: 3–24 citations per run. They can only come from memory, since the RIR/1999 is
  excluded from the main corpus.

### 4.3 Later-year acts

- No citation of an act dated 2025 or later, in any run.
- Acts from 2024 outside the corpus, written with the year only, can't be dated offline:
  - Lei 14.937/2024 (Luna, with Decreto Legislativo 36/2024 on the Rio Grande do Sul calamity);
  - Lei 14.848/2024 (Terra);
  - Lei 14.871/2024 and Lei 14.973/2024 (Sabiá-4);
  - INs RFB 2.168, 2.173, 2.177, 2.179, 2.210 and 2.219 of 2024 (Sabiazinho-4, Sabiá-4).

  Any of them dated after 2024-05-03 would be knowledge from after the reference date. A dated list from LexML or
  the Receita Federal would settle this. For A3 (Sol), this check matters most.

## 5. Link with answer quality (citation plan §3.7; descriptive)

V_strict by what the answer cites at the article level (questions with gold, answered):

| Generator | Context | No citation | Only wrong articles | A gold article | Spearman (recall, V_strict), citing answers |
|---|---|---:|---:|---:|---:|
| Terra | closed book | 0.279 (111) | 0.324 (270) | 0.426 (177) | 0.17 |
| Terra | S2 4k | 0.376 (49) | 0.226 (137) | 0.421 (361) | 0.32 |
| Luna | closed book | 0.240 (342) | 0.286 (120) | 0.256 (112) | 0.04 |
| Luna | S2 4k | 0.364 (48) | 0.228 (112) | 0.410 (324) | 0.28 |
| Sabiá-4 | closed book | 0.218 (127) | 0.214 (336) | 0.253 (90) | 0.10 |
| Sabiá-4 | S2 4k | 0.351 (373) | 0.228 (53) | 0.364 (144) | 0.30 |
| Sabiazinho-4 | closed book | 0.161 (233) | 0.182 (296) | 0.152 (43) | 0.02 |
| Sabiazinho-4 | S2 4k | 0.310 (493) | 0.133 (31) | 0.235 (53) | 0.28 |

- With RAG, answers that cite only wrong articles are the worst group for every generator, about 0.10–0.20 below
  the answers that cite a gold article.
- In closed book, Terra's correct citations go with clearly better answers (+0.10). For the other models, citation
  correctness says little about the answer.
- These are associations: both depend on how hard the question is.

## 6. Files

| File | Content |
|---|---|
| `scripts/nuggets/nuggetizer/intext_citations.py` | detector, resolver, attribution, scoring, context classes, run driver |
| `scripts/nuggets/nuggets.py intext` | command: `--sample all`, `--runs <glob>`, `--no-linker` |
| `scripts/nuggets/tests/test_intext_citations.py` | 19 tests (forms from the survey, the fixed errors, match rules) |
| `…/all/intext/intext_citations.csv.gz` | one row per cited unit: run, question, claim, chain, act text/kind/resolver/status, `act_key`, `document_id`, unit ids, match per level, validity flags, `ctx_document/article/provision` |
| `…/all/intext/intext_answers.csv.gz` | one row per answer × level: `n_gold`, `n_cited`, recall, recall_any, cited_any, precision (3 variants) |
| `…/all/intext/intext_citations_runs.csv` | per run × level; the document-level rows also carry the validity and context-class shares |
| `…/all/intext/intext_vs_quality.csv` | §5 |
| `…/all/intext/linker_crosscheck.json` | §1.3 counts and examples |

The tables also cover the other runs: budgets 2k and 8k, S2c/S3/S4, the `stratified_30` runs, wrong-context and
`context_v1`, and the gemini-emb-2 runs (`context_id` `…@gemini-emb-2`).

## 7. Open points

1. **Unattributed chains in RAG answers.** These are 23% of Sabiazinho-4's in-text chains: "conforme o art. 63",
   with no act. They could be bound to the document of the claim's own source (`fundamentos`). That would raise its
   in-text recall and change its §4.2 classes. It is not done yet, because it mixes the two citation channels.
   Decide before the paper tables.
2. **Acts outside the corpus and 2024 acts:** these need a manual or LexML lookup, to tell invented acts from real
   but uncited ones and to date the 2024 acts (§3.1, §4.3). This is citation plan §7.3; the default was a manual
   sample only.
3. **A3 (Sol)** gets these tables at no extra work once its runs exist: rerun `nuggets.py intext` (H3: per-citation
   leakage; H4: closed-book precision and later-year acts).
4. Not done: an in-text citation panel in the explorer's question trace (optional in the citation plan).
