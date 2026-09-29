# FiscalQA Pro (arXiv:2608.09393) vs. our research: temporal grounding and deterministic nuggets

**Generated:** 2026-09-29 11:13:56 (local time, from `date +%Y%m%d_%H%M%S`)
**Paper:** Cymbler, Guez, Fabre — *Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark
for French Tax Law*, arXiv:2608.09393v1 (10 Aug 2026), ICML 2026 Workshop AI4Law. Code and data:
`github.com/rosecymbler/fiscal-fr-bench`. Referred to below as **[FQ]**.
**Goal:** (1) explain the temporal problem [FQ] studies, (2) explain how its deterministic nuggets
score answers, (3) compare both with our goals (hierarchical segmentation for RAG over the P&R IRPF
2024, scored with nuggets), and (4) list what we should adopt. Section 4 includes measurements on
our own data taken for this note.

---

## 0. Summary

- [FQ] asks a **different question** from ours. It studies **which version** of a legal article
  must be retrieved (time). We study **which unit** of a legal document should be retrieved
  (structure). The two axes are orthogonal, but they meet in our corpus (§4).
- **Temporal misgrounding** = retrieving and citing the version of an article that is in force
  **now**, when the question needs the version that applied at an earlier (or later) date. [FQ]
  shows that with a current-only corpus it is almost total (2.7 % strict), and that indexing all
  versions and selecting one by the question's date almost removes it (98.3 %).
- **Deterministic nuggets:** each question has **two** hand-written nuggets: a **regex** on the
  article number and a **numeric match with tolerance** on the value at the question's date. No
  LLM judge is used. Their reason: an LLM judge shares the same recency bias it is supposed to
  measure.
- **For us:** our corpus is the **current consolidated text** (*vigente* view, fetched in 2026),
  while the gold answers are anchored in **exercício 2024 / ano-calendário 2023** (P&R published
  2024-05-03). In [FQ]'s terms, every run we make is their **Condition B** (static current
  corpus), and our "oracle" context is B with the gold article, not their version oracle.
  Brazilian consolidated texts soften the problem: annual values are often **added as new items**
  inside the same article, so older values stay in the text. But wording that was **rewritten in
  place** is lost.
- **Exposure (measured, §4.3):** 33 of the 218 referenced statutory documents carry amendment notes
  dated after May 2024. 116 of the 596 questions with resolved references cite at least one of
  them. Only 77 answers contain R$ amounts and 86 contain percentages, so a numbers-only scheme
  like [FQ]'s could cover only a small part of our 715 prose answers.
- **Recommendation (§5):** keep the LLM-judge nugget protocol for rules and conditions. Add
  [FQ]-style **deterministic value checks** for `valor_prazo` nuggets, a **temporal slice** in the
  reports, a **reference date in the generation prompt**, and a year-aware reading of the
  `contradicts` label.

---

## 1. The paper in brief

| Item | [FQ] |
|---|---|
| Domain | French tax law: CGI (+ 4 annexes) and LPF |
| Corpus | **32,436 article-versions** over 8,076 articles (4.02 versions per article; CGI art. 81 has 94). Span 1938–2031, including **future-effective** versions. Built from Légifrance `getArticleByCid`, which returns the full version history with `date_debut` / `date_fin` / `etat` per version |
| Auxiliary resource | 69,208 version-aware links from court decisions to the article version in force at the decision date (regex extractor, 98–99 % precision). Not used in the main experiment |
| Benchmark | Four regimes: R1 citation extraction, R2 computation, **R3 temporal reasoning** (the main track), R4 multi-document synthesis. R3 has 221 questions (209 scored) over 33 CGI articles |
| Question creation | A script finds value changes between consecutive versions ("drift points"). The authors write each question, its date anchor, the answer and the nuggets. A French tax professional reviews them |
| Filters | (a) **Parametric filter:** a question is dropped if any of the 11 models gives the gold value closed-book in any of 4 draws ("all-model-hard"). (b) **Divergence filter:** a question is dropped if the gold value still appears in the current version of the article |
| Conditions | **A** LLM only · **B** RAG over the current corpus, **given the gold article** · **C_or** gold article, version chosen by date (oracle) · **C_prod** end-to-end: dense (domain-adapted encoder) + BM25 with RRF over a multi-version index (3 versions per article), top-5 articles, then a version layer picks each article's version by date |
| Models | 11: Opus 4.7/4.8, Sonnet 4.6, GPT-5.4/5.5, Gemini 2.5 Pro, Mistral Large, Llama 4 Maverick, Qwen 3 235B, Gemma 3 27B, GLM 5.2 |
| Main results (mean strict) | A 3.0 %, B 2.7 %, C_or 99.1 %, C_prod 98.3 %. Provenance (gold version retrieved): B 0 %, C_or 100 %, C_prod 99 % |
| Statistics | Cluster bootstrap over articles (33 clusters, 10k iterations), McNemar per model, Wilcoxon on coverage, leave-one-article-out |

---

## 2. The temporal discussion, clarified

### 2.1 What "temporal misgrounding" is

Tax statutes are **amended in place**: the article keeps its number, but its text (a rate, a
threshold) changes every year or so through finance laws. A question such as "what was the
corporate tax rate for fiscal years opening on or after 1 Jan 2018?" has one correct answer
(33⅓ %, the 2018 version of CGI art. 219), which is not the current value (25 %). **Temporal
misgrounding** is the failure in which the system retrieves, uses and cites the **currently in
force** version instead. The answer is then wrong **and** looks well grounded: the article exists,
and the citation is real.

[FQ] names three causes that act together:

1. **Parametric recency bias.** Training data over-represents current law, so the LLM's prior is
   the current value.
2. **No temporal conditioning in retrieval.** Dense retrievers rank by meaning and ignore the date
   in the query.
3. **Article-number aliasing.** "Art. 219" names every version, so the identifier does not say
   which one is meant.

And three properties of legal corpora explain why static retrieval cannot fix it:

- **(P1) Same identifier, different content.** The (article, version) pair, not the article,
  carries the content. A single-snapshot index keeps one point per article.
- **(P2) Date-dependent correctness.** Each version has an explicit validity interval. For a given
  date exactly one version is right. A "nearly right" version is simply wrong.
- **(P3) Cross-version similarity.** Consecutive versions often differ by one number, so their
  embeddings are nearest neighbours. Similarity alone cannot tell them apart.

### 2.2 Failure modes (taxonomy)

| Mode | What happens | Evaluated in [FQ]? |
|---|---|---|
| **Current-law substitution** | The in-force version is returned whatever the query date | **Yes** (the only one; all B errors are of this type) |
| Future-law leakage | A version that is enacted but not yet in force is returned for a present-tense question | No (future work; the corpus has such versions up to 2031) |
| Wrong-amendment resolution | "Art. X in the wording before Law Y" returns the current or an arbitrary version | No |
| Multi-version confusion | A before/after comparison collapses to one version | No |

### 2.3 How they condition on time

- **Index:** all versions are kept, each with its validity interval. For first-stage retrieval,
  the dense/BM25 index holds 3 versions per article (first, median and last by `date_debut`), so
  the article can be found whichever wording the query resembles.
- **Version layer:** after the top-5 **articles** are found, a deterministic step picks, for each
  article, the version whose `[date_debut, date_fin)` contains the question's date. **Time is a
  metadata filter applied after retrieval, not a feature learned by the retriever.**
- **Where the date comes from:** every R3 question carries an explicit date anchor ("for fiscal
  years opening on or after 1 January 2018"). The paper does not describe how the date is
  extracted from the query in C_prod. The retriever code and encoder weights are proprietary and
  not released, so C_prod cannot be reproduced; only its per-question responses are published.
- **Context:** every condition gets the same prompt with at most 8,000 characters per article,
  windowed around the query. They checked that the gold value is inside the window for all 209
  questions. Full-article prompting made long articles worse (long-context distraction).

### 2.4 How to read the results (caveats)

- **B fails partly by construction.** The divergence filter keeps only questions whose gold value
  is absent from the current text. B's 2.7 % therefore shows that the filter works more than it
  measures anything. The informative parts are B's **0 % provenance** (a single-version index
  cannot hold the right version) and the gap between B and C_or, where only the version served
  changes.
- **C is near the ceiling because the task is well specified.** The date is explicit, and the
  article number appears in the question text in **83.7 %** of the questions. Once the right
  version is in the context, reading the value is easy (99 % for every model). The remaining
  0.8-point gap between C_or and C_prod is article recall (one article, art. 1417), not version
  selection.
- **Scope is narrow on purpose:** single-date questions, one article, one value. It does not show
  how temporal errors behave in open prose questions with several conditions, which is our
  setting.

---

## 3. How their deterministic nuggets work

### 3.1 Definition and scoring

- A **nugget** is an atomic claim that a program can check. It has one of three types:
  - **article identifier** → **regex**, e.g. `\b219\b`;
  - **numeric value** → **numeric match with tolerance**, after normalizing French number formats
    (thousands separators, decimal comma) and simple arithmetic forms (33⅓ % ≡ 33.333 %);
  - **exact string** match.
- Each R3 question has **two required nuggets**: the article and the value at the question's date.
  (The appendix example lists 4 nuggets for the art. 219 case study, including the version and the
  regime. The scored R3 protocol states two.)
- Scores per question:
  - **coverage** = fraction of nuggets matched (Σ 1[nᵢ ∈ r] / |N|);
  - **strict** = all required nuggets matched (right article **and** right value): the headline
    metric;
  - **value-only coverage**, because the article nugget is mostly given away by the question
    (83.7 %). Value-only tracks strict within 1 point;
  - **provenance** (retrieval side, not answer side): the gold version is among the retrieved
    versions (the single article for B/C_or, the top 5 for C_prod).
- Aggregation: mean over the 209 questions per model, with cluster bootstrap over articles.

### 3.2 Why no LLM judge

Their argument is specific to time. An LLM judge has the same recency prior as the systems under
test, so it may accept a fluent answer that states the **current** value, because that value
agrees with what the judge "knows". A regex or a numeric comparison has no prior. All the
judgement (which article, which value, what tolerance) is made **once, at annotation time**, and
checked against the primary source. Disagreements are settled by reading the versioned text again,
not by prompting a model again. They take the nugget idea from KARL (Databricks) and note that
KARL's nugget scoring is still an LLM-as-judge variant. They also criticize Prior et al. (2026),
concurrent German work on the same problem, for using an LLM judge.

### 3.3 Limits of the scheme (our reading; not all are discussed in [FQ])

1. **Expressivity.** Only identifiers and numbers can be checked. Conditions, exceptions, verdicts
   (Sim/Não) and procedures cannot. This works for R3 because the questions were **written** so
   that a single number answers them.
2. **Recall only; no penalty for extra claims.** An answer that lists the values of several years
   ("33⅓ % in 2018, 31 % in 2019, 25 % since 2022") matches the value nugget and gets strict = 1
   while still hedging. The paper does not mention this.
3. **Short regexes over-match.** `\b219\b` also fires on "R$ 219" or "item 219". This is harmless
   when the question already names the article, but not in general.
4. **Tolerance is a judgement call** made per question. A tolerance too wide would accept a
   neighbouring year's value when two versions differ slightly.
5. **Leakage.** The question text gives the article in 83.7 % of the questions (they report
   value-only coverage for this reason).

### 3.4 Why their scheme works for them and cannot be our main metric

Deterministic scoring works in [FQ] because of how the **questions were written**, not because
of a general property of legal QA. Each R3 question is built from one value change in one article.
It asks for one number on one date, and its complete correct answer is "article X, value V". So
the whole meaning of the answer fits into two checkable tokens. Because the article is usually
named in the question, the score depends almost entirely on the **value**.

Our situation is the reverse. The questions and gold answers are Receita Federal's own prose
(median 84 words, up to 3,316), and most of what a correct answer must contain is rules,
conditions, exceptions, verdicts (Sim/Não) and procedures. None of these can be checked with a
regex or a number. Only a minority of answers contain values at all (77 with R$ amounts, 86 with
percentages; §4.3), and even there the value is usually one part of a longer answer. So [FQ]'s
approach cannot be our main metric. It can still serve as an extra check on the value-bearing
nuggets (§5, item 1).

---

## 4. Comparison with our research

### 4.1 Goals and setup side by side

| Aspect | [FQ] | Ours (BR-TaxQA-R v2.0) |
|---|---|---|
| Research question | Is **version selection by date** the bottleneck of legal RAG? | Does **hierarchical segmentation** (S1 article vs. S2 article + sub-article units with ancestor path, optional S3 groupings) give better chunks for answering prose tax questions? |
| Axis | Time (which version) | Structure (which unit) |
| Questions | 209 author-written, single-date, single-value, filtered to be hard for all models | 715 existing questions from Receita Federal's P&R IRPF 2024. Open prose, many conditions, no filtering |
| Gold answers | One value + one article per question | Official prose answers (median 84 words, up to 3,316) |
| Corpus | 32k versions of 2 codes, with validity intervals | 459 documents of many kinds (laws, decrees, INs, ADEs, pareceres, soluções de consulta, court decisions) as LexML, **one version each**: the current consolidated text |
| Retrieval unit | Article (chunked), then version | S1 article / S2 caput-§-inciso-alínea-item with ancestor path / S3 groupings |
| Retriever | Proprietary dense + BM25 + RRF | Dense embedding models (Juá and others) under token-budget control and containment de-duplication |
| Conditions | A closed-book, B current corpus + gold article, C_or version oracle, C_prod end-to-end | closed-book (`k=0`), **oracle** = gold articles of the current text, retrieval by strategy × budget (`docs/20260927_204356_rag_pipeline_implementation_plan.md` §5) |
| Answer scoring | Deterministic nuggets (regex / numeric), 2 per question | LLM-created legal nuggets from the gold answers, human audit, LLM judge (Gemini / Qwen) with `support` / `partial` / `not_support` / `contradicts`, metrics V_strict etc. from AutoNuggetizer (`docs/20260926_112714_gold_answer_nuggetization_plan.md`) |
| Citation scoring | Article regex nugget + retrieval provenance | Secondary legal-provision score, deterministic after URN normalization with `lexml-linker` (D6) |
| Statistics | Cluster bootstrap by article, McNemar | Paired bootstrap / permutation over questions |

Conditions A and C_or map onto our plan, but **our oracle is their B, not their C_or**: it serves
the gold article in its **current** wording. A gap between our oracle and 100 % can therefore
come partly from time drift, not only from the reader LLM. It is worth reporting it that way.

### 4.2 Time in our corpus: how the Brazilian case differs

**Our time situation.** The gold answers describe the law for **ano-calendário 2023 / exercício
2024**, as of 2024-05-03. The corpus holds the **current consolidated text**: the document fetcher
renders the *vigente* view (`../br-taxqa-document-fetcher/20260729_171931_receita_federal_rendering_fidelity_plan.md`,
issue 3: "keep `omitir === false` segments, emit `ancorasDestino[].texto` as annotations, no
strikethrough"). The texts cite amending acts up to Lei nº 15.371, de 31.3.2026 (82 chunks). The
snapshot dates also **differ between documents**: e.g. the `.docx` files of Lei 9.250 and Lei
11.482 are dated 2026-03-15 (file mtime), while other documents already include later changes. The
corpus is therefore about two years **after** the question date and is not one single point in
time.

Brazilian consolidated texts store history differently from Légifrance, in three ways:

1. **Values added as new items (history kept inside one article).** Laws that update annual
   values often **add a new item** rather than rewrite the old one, so the older values stay in the
   current text:
   - Lei 9.250, art. 8º, II, b: items 1–10 give the education-deduction limit per year, ending
     with "10. R$ 3.561,50 …, a partir do ano-calendário de 2015";
   - Lei 11.482, art. 1º: one inciso per period of the monthly progressive table, up to
     "XII – a partir do mês de maio do ano-calendário de 2025 (Inciso acrescido pela Lei nº
     15.191, de 11.8.2025)" (exemption band up to R$ 2.428,80). The 2023 table (up to R$
     2.112,00) is still there.

   Here [FQ]'s (P1)/(P3) happen **inside one chunk** instead of across versions. The right value is
   retrieved, but next to near-identical values for other years, and **the reader LLM must choose
   by year**. This ties time to **our** research question: an S2 inciso chunk isolates one
   period's table together with its year label. S1 gives the whole article with every year. S2
   should therefore produce fewer wrong-year values, if the retriever ranks the right inciso first.

2. **Wording rewritten in place (history lost).** When the wording itself is replaced, the
   *vigente* view keeps only the new text plus a note "(Redação dada pela Lei X, de …)". The
   wording that applied in 2023 is gone. This is [FQ]'s **current-law substitution** in its pure
   form. Example: the inciso of Lei 11.482, art. 1º for the May-2023 table carries "(Inciso
   acrescido pela Lei nº 14.663, de 28.8.2023, e com nova redação dada pela Lei nº 14.848, de
   1º/5/2024)". Revoked provisions keep only the note "(Revogado pela …)".

3. **Acts tied to one year.** Many answers rely on acts that are themselves bound to one year,
   such as **IN RFB nº 2.178/2024**, the DAA 2024 instruction, which contains the R$ 30.639,90
   filing threshold of Q001. These act as correctly dated documents even in a current-only
   corpus. The risk comes back when a newer act on the same subject is also in the corpus. We have
   not measured this.

There is also a **future-law** risk relative to the question date: the corpus contains rules made
after 2024 (e.g. the 2025 table of Lei 11.482, and Lei 15.270/2025 inside Lei 9.249). An LLM given
these may answer an AC-2023 question with the 2025 value, which is [FQ]'s current-law substitution.

### 4.3 Measurements on our data (2026-09-29, rough, for sizing only)

Computed over `dataset/questions.jsonl`, `dataset/references.jsonl`, `lexml/articulados/` and
`segmented/chunks_all.csv.gz`. The patterns are rough; treat the numbers as orders of magnitude.

| Measure | Value |
|---|---|
| Answers with at least one R$ amount | **77** of 715 |
| Answers with at least one percentage | **86** of 715 |
| Questions or answers naming "ano-calendário de YYYY" / "exercício de YYYY" | 66 |
| (question, distinct R$ amount) pairs | 279. Of these, **184** appear verbatim somewhere in the corpus. Most of the others are computed figures in worked examples (e.g. Q620, Q617), not values stated in the law |
| Questions that cite an article in the question text | **3** (vs. 83.7 % in [FQ]), so our provision score is not given away by the question |
| Referenced statutory documents with amendment notes dated after 2024-05 | **33** of 218 (most notes: LC 123/2006 198, Lei 11.196 67, Lei 9.394 46, Lei 10.833 37, Lei 10.865 37) |
| Questions citing at least one of those documents | **116** of 596 questions with resolved references |
| Examples of AC-2023 values in the corpus | 30.639,90 (4 chunks), 2.112,00 (5), 16.754,34 (18). Checked but not found: 564,80, 528,00, 2.824,00 |

The last two exposure rows are an **upper bound**: an amendment note on the document does not
mean that the cited provision, or the answer, changed. Measuring the true set needs
provision-level matching (the `provisions` / `fragment_id` of `references.jsonl` against the notes
of that fragment).

---

## 5. What to adopt, adapt or skip

**Adopt**

1. **Deterministic value checks alongside the LLM judge.** For every nugget in the `valor_prazo`
   category, pull its amounts, rates and dates out with pt-BR normalization (`30.639,90` ≡
   `30639.90`, `7,5 %`, dates). Then check the system answer with a regex / numeric match with
   tolerance, as [FQ] does. Report it as a separate **value-hit** score and use it to **audit the
   judge**: agreement between the judge's `support` and the value hit on these nuggets gives a
   free, bias-free check of the judge. This extends the grounding check already in the nugget
   validator (§3.3 of the nuggetization plan) from creation time to scoring time.
2. **Year-aware `contradicts`.** When the answer states a **different** value of the same kind
   (another R$ amount in the same slot), mark it as a deterministic *contradiction candidate*. When
   that value appears in the corpus as a value of **another period** of the same provision (e.g.
   the 2025 table of Lei 11.482), mark it as **temporal substitution**. This gives our
   `contradicts` rate a temporal part and directly tests the S1 vs. S2 hypothesis in §4.2.1.
3. **Temporal slice in every report.** Tag the questions that (a) have `valor_prazo` nuggets, or
   (b) cite a provision amended after 2024-05-03 (at provision level, §4.3). Report all metrics on
   this slice and on the rest.
4. **Reference date in the generation prompt.** Add a fixed line to `prompts/answer_v1.pt.md`
   (exercício 2024, ano-calendário 2023). This is [FQ]'s date conditioning applied to the reader,
   at no cost. It helps with case 1 of §4.2 and does nothing for case 2. It must be the same for
   every strategy, so it does not bias the S1/S2/S3 comparison.
5. **Cluster-aware statistics.** Questions that share cited documents or P&R chapters are not
   independent. Add a cluster bootstrap (by chapter or by main cited document) next to the paired
   bootstrap over questions.

**Adapt**

6. **Describe our oracle correctly** in the paper, as "gold provisions, current wording", and
   discuss the time gap between the question date and the corpus as a threat to validity. It is the
   same for every strategy, so it does not bias the **comparison**, but it lowers absolute scores.
7. **Optional, later:** fetch the wording as of 2024-05-03 for the documents actually hit by
   in-place rewrites, if the source portals offer a multi-version or point-in-time view (to be
   checked in `../br-taxqa-document-fetcher`). This would allow a small version-oracle ablation
   like their C_or. It is out of scope for the segmentation paper unless the temporal slice turns
   out to be large.

**Skip**

8. **Numbers-only scoring as the main metric.** Most of our answers are rules, conditions and
   verdicts, so an LLM judge with human calibration remains the right main tool. [FQ]'s
   "judge shares the recency bias" argument is weaker for us, because our judge is **shown** the
   gold nugget, which states the dated value. The risk is still there when a nugget states a rule
   without its year, which is why item 1 is worth its low cost.
9. **An all-model-hard parametric filter.** Our goal is to compare strategies on the official
   question set, not to build a benchmark that no model can answer closed-book. Our `k=0`
   condition already measures parametric knowledge.

---

## 6. References

- [FQ] Cymbler, R., Guez, D., Fabre, L. *Temporal Misgrounding in Legal RAG: A Versioned-Corpus
  Benchmark for French Tax Law.* arXiv:2608.09393, 2026.
- Opsahl-Ong, K. et al. *OfficeQA Pro.* arXiv:2603.08655, 2026. The deterministic grounded-scoring
  and parametric-filter methodology that [FQ] extends.
- Databricks AI Research. *KARL: Knowledge Agents via Reinforcement Learning.* arXiv:2603.05218,
  2026. The nugget decomposition that [FQ] uses, there with an LLM judge.
- Prior, M., Schultz, A., Grabmair, M. *Asking for an Old Friend: Diagnosing and Mitigating Temporal
  Failure Modes in LLM-based Statutory QA.* arXiv:2605.23497, 2026. German statutes, LLM judge.
- de Martim, H. *An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and
  Deterministic Approach.* JURIX 2025. Point-in-time queries on the Brazilian Constitution; a
  co-author of our segmentation reference [F].
- Our docs: `20260923_193852_segmentation_strategies_for_rag_experiments.md`,
  `20260926_112714_gold_answer_nuggetization_plan.md`,
  `20260927_204356_rag_pipeline_implementation_plan.md`.
