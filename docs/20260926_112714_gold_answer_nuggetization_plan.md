# Gold-Answer Nuggetization and Nugget-Based Answer Evaluation — Plan

**Generated:** 2026-09-26 11:27:14 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** plan only. Nothing has been implemented or run.
**Goal:** turn the 715 gold answers of BR-TaxQA-R into **legal nuggets** (short, self-contained,
atomic statements), and define how the answers of the RAG aggregator LLM are scored against them.
The segmentation experiment (`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md`)
needs this to compare S1 / S2 / S3.
**Deliverables:** code in `scripts/nuggets/`, outputs in `nuggets/`. The code will be **released with
the research**, so clear design, reproducibility and short usage instructions are requirements (§7).

---

## 0. Decisions (these override the sections below where they differ)

Decisions from 2026-09-26, revised on 2026-09-27:

| # | Topic | Decision |
|---|---|---|
| D1 | Aggregator (generator) LLMs | **OpenAI**, **Maritaca Sabiá and Sabiazinho**, and **DeepSeek** (revised 2026-09-27: Qwen is no longer a generator) |
| D2 | Judge | Families excluded as judge: OpenAI, Maritaca, DeepSeek. **Candidates: Gemini** (key now in `.env` as `GEMINI_API_KEY`) **and an open-weight Qwen model**. Both are calibrated against the human labels (§4.4). If Qwen's agreement is within about 0.05 κ of Gemini's, **Qwen is the primary judge**: pinned weights make the scoring exactly reproducible by anyone. Otherwise Gemini is primary and Qwen is reported as the second judge. An **OpenAI judge on a subset** measures self-preference directly (does it rate the OpenAI generator higher than the neutral judges do?) |
| D3 | Nugget creator | Computed from scratch with a **strong model**. The [LN] nuggets file is **not** requested. The pilot compares the strongest available OpenAI model and Gemini, and the audit picks one. The [LN] prompt + `gpt-5.4-nano` stays only as a cheap optional pilot baseline |
| D4 | GPU endpoints | **Needed only if Qwen is served ourselves** (revised 2026-09-27). The HF Inference Endpoint set up for the embeddings can run the Qwen judge with vLLM at a pinned revision. A hosted Qwen API with a pinned model version is an alternative for calibration. The model size is chosen at implementation, balancing judge quality against the endpoint's GPU cost |
| D5 | Human audit | Kept. **Annotators: the user and another research team member.** The full protocol is in §3.4 |
| D6 | Legal-provision score | **Wanted**, as a **secondary** metric. The main metric stays nugget recall (§4.3). The design is in §4.5 |
| D7 | `contradicts` label | **Kept** (2026-09-27), §4.2. Calibration only reports its κ; it no longer decides whether the label is kept |
| D8 | Nugget-set robustness | **New (2026-09-27):** a second full nugget set is made with the other creator model, and all runs are scored with both sets (§3.4, last part) |

---

## 1. Sources and what each one contributes

| Ref | Work | What we take from it |
|---|---|---|
| **[LN]** | Pereira, Brito, Lotufo, Pereira — *Legal Nugget Extraction for Granular Retrieval over Long Jurisprudential Texts*, arXiv:2607.22479 (2026). Code: `github.com/ufca-llms/nuggets-search` | The **legal-nugget definition** ("short, self-contained statement that captures an atomic legal argument or thesis"; no party names, procedural history or generic text), an extraction prompt **already adapted to BR-TaxQA** (§1.1), and the generator it used (**GPT-5.4-nano**) |
| **[AN]** | Pradeep et al. — *Initial Nugget Evaluation Results for the TREC 2024 RAG Track with the AutoNuggetizer Framework*, arXiv:2411.09607. Code: `github.com/castorini/nuggetizer` (Apache-2.0) | The **evaluation protocol**: importance labels (`vital` / `okay`), assignment labels (`support` / `partial_support` / `not_support`) and the scores (§4.3) |
| **[GR]** | Pradeep et al. — *The Great Nugget Recall*, arXiv:2504.15068 | Evidence that fully automatic nuggets give run rankings that agree well with manual ones. This supports automatic creation followed by a **sampled** human audit instead of full manual annotation |
| **[CA]** | Sharifymoghaddam et al. — *Chatbot Arena Meets Nuggets*, arXiv:2504.20006 (suggested in the 2026-06 meeting) | Nugget scores correlate with human preferences. It also notes that nugget generation is hard, especially in pt-BR and in the legal domain |

### 1.1 What [LN] does and does not give us

[LN] uses nuggets for **retrieval**: it indexes nuggets instead of documents. It does **not** score
generated answers. Two facts matter here:

- Its BR-TaxQA run (`runs/brtaxqa_openai_nuggets.json`) already nuggetized **the Q&A answers
  themselves**. That means the same gold text we have. It used `gpt-5.4-nano`,
  `response_format=json_object`, no explicit temperature, and this prompt:
  > *"Voce e um contador especialista. Sua tarefa e extrair fatos atomicos (nuggets) de um conjunto
  > de perguntas e respostas juridicas. O texto analisado e a resposta de uma duvida frequente.
  > Transforme-a em fatos independentes que poderiam ser uteis para responder perguntas futuras. O
  > nugget deve ser direto em se tratando de prazos e obrigacoes. Nao invente fatos. Retorne
  > estritamente JSON no formato {"nuggets": ["Fato 1", "Fato 2"]}."*
- The paper reports that on BR-TaxQA the nuggets **underperformed** full answers for retrieval
  (*"tax questions and answers often depend on complete explanatory context"*). For **evaluation**
  this is a warning: a nugget that drops its condition ("desde que…", "exceto…") or its subject
  cannot be judged on its own. That is why the prompt in §3.2 is **question-conditioned** and keeps
  each condition attached to the rule it limits.

**Decision:** take the nugget **definition and domain framing** from [LN]; take the **scoring
protocol** from [AN]. The [LN] prompt + `gpt-5.4-nano` is kept as a **baseline configuration**, so the
paper can report how its nuggets compare with the adapted ones (§5, pilot).

The generated nuggets file from [LN] (`data/brtaxqa/nuggets_report.json`) is not in the public repo.
**It will not be requested (D3):** we recompute the nuggets with a stronger model.

---

## 2. Input: the gold answers

- **Source of truth:** HF `unicamp-dl/BR-TaxQA-R`, file `questions_QA_2024_v1.0.json` (715
  questions), downloaded at a **pinned revision** with its SHA-256 recorded. On 2026-09-26 I checked
  the local copies: `question_text` and `answer_cleaned` are identical in v1.0, v1.1 (used for the
  query embeddings) and v1.1_manual_fix. So nuggets and queries share the same text.
- **Field used:** `answer_cleaned` (the list of PDF lines with the external-reference block and
  "Consulte a pergunta N" lines removed), always **together with `question_text`**. Lines are joined
  with `\n` so list items ("1 -", "a)") stay visible. Nothing else is rewritten. The prepared text and
  its hash are stored.
- **Profile** (measured 2026-09-26): 698,724 characters in total; median 84 words; p90 316 words;
  max 3,316 words.
- **Cases the prompt and validation must handle:**
  - **20 answers are shorter than 80 characters** ("Não há limitação quanto à idade.", "Não, por falta
    de previsão legal."). They only make sense with the question, so conditioning on the question is
    required.
  - **Long enumerations** (e.g. Q001, 11 obligation criteria plus exemptions) should give one nugget
    per item, with the item's own values.
  - **50 answers still mention another question** in the cleaned text. **66 answers** refer to the
    declaration program, e.g. "ficha", "PGD". These are procedural instructions, not law, and the
    legal corpus cannot support them. They get a category tag (§3.1) so results can be reported with
    and without them.
  - **Embedded legal citations** ("nos termos do art. 39 da Lei nº 11.196…") stay in the text. They
    go into a separate `legal_basis` field, not into nugget text (§3.1).
  - We do **not** expand `linked_questions`. The gold answer is only what the answer itself says.
- **Scope:** all 715 questions are prose (open-ended) questions. We nuggetize all of them, and the
  flags let each experiment choose a subset.

---

## 3. Nugget creation

### 3.1 Nugget schema (one JSON object per nugget)

```json
{
  "nugget_id": "Q001_N03",
  "question_number": "001",
  "text": "Está obrigada a apresentar a DAA de 2024 a pessoa física residente que, em 2023, recebeu rendimentos tributáveis sujeitos ao ajuste cuja soma foi superior a R$ 30.639,90.",
  "importance": "vital",
  "category": "condicao",
  "legal_basis": [],
  "source_span": "1 - recebeu rendimentos tributáveis, sujeitos ao ajuste na declaração, cuja soma foi superior a R$ 30.639,90",
  "ordinal": 3
}
```

- `category` ∈ `resposta_direta` (the Sim/Não or one-line verdict) · `regra` · `condicao` (condition,
  exception or requirement) · `valor_prazo` (amounts, limits, rates, deadlines) · `procedimento_pgd`
  (program/filling instructions) · `definicao`.
- `importance` ∈ `vital` / `okay`, as in [AN]. A nugget is `vital` if a correct answer to **this
  question** must contain it.
- `legal_basis`: citations taken from the nugget's own span, verbatim. They are kept for an optional
  "cites the right legal basis" score. They do not count in the main score, because the aggregator
  is not required to cite.
- `source_span`: the verbatim sentence or line the nugget comes from. It makes the grounding check
  and the human audit fast.

### 3.2 Prompt design (pt-BR, versioned files in `scripts/nuggets/prompts/`)

The prompt starts from [LN]'s BR-TaxQA prompt, adds [AN]'s importance step, and adds these rules for
evaluation use:

1. The input is the question **and** the answer. Each nugget must be understandable **without either
   of them**: name the subject, the tax year and the declaration. Resolve pronouns and "esse/tal".
2. **Atomic, but not cut apart:** one fact per nugget. A condition or exception stays in the same
   nugget as the rule it limits.
3. **Keep exact values** (R$, %, dates, deadlines, counts) **and technical terms** ("rendimentos
   tributáveis sujeitos ao ajuste", "ganho de capital"…) as written. Do not round or paraphrase them
   (§3.4.2).
4. **Always emit the verdict nugget** (`resposta_direta`) when the answer starts with Sim/Não or
   gives a one-line conclusion.
5. **Nothing outside the answer:** no facts from the model's own knowledge, and no nuggets made from
   the question alone.
6. Citations go in `legal_basis`, not in `text`.
7. Output must follow the JSON schema. Where the provider supports it, use structured output / JSON
   schema mode, and validate the result with pydantic in any case.

**Importance in the same call or a second call?** [AN] creates nuggets and then scores importance in
a separate call. With a single short gold answer as the source, one call is enough and cheaper. The
pilot (§5) compares one call with two calls on 30 questions. We use two calls only if importance
labels in the single call are clearly worse.

**Long answers:** no chunking is needed. The longest answer is about 5k tokens. We do not copy
[AN]'s cap of 30 nuggets (that cap exists to limit pooled web documents). We **flag** answers with
more than 40 nuggets for human review.

### 3.3 Automatic validation (`validate` step, no LLM)

- The JSON is valid against the schema, and ids are unique and contiguous.
- **Grounding of numbers:** every number, amount, percentage and date in `text` must also appear in
  the answer (normalized: `R$ 30.639,90` ≡ `30.639,90`). A mismatch is a hard error, because it is
  the most harmful hallucination in tax answers.
- `source_span` is found in the answer, allowing whitespace and hyphenation differences.
- Duplicates are removed after normalization (casefold, whitespace), as `dedupe_texts` does in [LN].
- Coverage check: each answer sentence or list item should map to at least one `source_span`.
  Uncovered lines go to review.
- Every question has at least one `vital` nugget. Answers under 80 characters have at least one.
- Output: `validation.json`, with per-question issues and totals.

### 3.4 Human audit

**Why an audit is needed.** Every system is measured against the gold nuggets, so an error in them
is a **systematic** error for all runs. Typical LLM errors are:
- a changed value or deadline;
- a condition dropped from its rule, which makes the nugget false in general;
- a list item that disappeared;
- a nugget that only makes sense next to the answer;
- a wrong vital/okay label, which changes V_strict directly.

The validator (§3.3) catches only mechanical errors. [GR] validates automatic nuggets on English
web QA, not on pt-BR tax law.

#### 3.4.1 What the audit checks, and what it does not

The **gold answer is the ground truth by definition**: the Receita Federal wrote it. Annotators check
the nuggets **against the answer text, never against the law**.
- They do **not** judge whether the P&R is legally right.
- "Missing information" means missing **from the answer**, not missing from the legislation.

So the task is careful reading plus a textual-entailment judgment. It is not legal analysis.

Checks per nugget. Each is yes/no, with a decision rule:

| Check | The annotator asks | It fails when |
|---|---|---|
| **C1 Faithful** | Does the answer (read with the question) say this, with nothing added, removed or changed? | A value, date or rate differs; Sim↔Não is flipped; a quantifier or scope changes ("somente", "até", "qualquer", "todos"); a technical term is swapped for a near-synonym ("rendimentos tributáveis" for "rendimentos tributáveis sujeitos ao ajuste"); a condition or exception from the same sentence is dropped; it states something the answer does not say |
| **C2 Self-contained** | Could someone who never saw the question or the answer understand it and check it? | It has an unresolved "esse", "tal" or "o contribuinte" where the question limits who is meant; the tax year or declaration is missing when the rule depends on it |
| **C3 One unit** | Can a system answer get it **entirely right or entirely wrong**? | It joins two independent facts (split it), or it is a fragment with no meaning alone (merge it). A rule together with its own condition is **one** unit |
| **C4 Importance** | Would an answer to *this question* without this fact be wrong or misleading? Yes = `vital`, no = `okay` | The label is the other one |

Checks per answer:

| Check | How |
|---|---|
| **C5 Complete** | Every factual statement in the answer is covered by at least one nugget. The review sheet **highlights answer lines that no `source_span` covers**, so only those lines need a close reading. Each missing fact is written as a new nugget |
| **C6 Not redundant** | No two nuggets carry the same fact |

**Guideline rules for recurring cases:**
- Worked numerical examples: no nugget, unless the example states a rule.
- "Atenção" notes: they get nuggets, usually `okay`.
- Program or screen instructions: `procedimento_pgd` nuggets, with importance set by C4.
- Pointers to other questions: no nugget.

Each item gets one outcome: **pass**, **fix** (the annotator writes the corrected text or label), or
**escalate** (unsure about the legal meaning).

#### 3.4.2 Is legal expertise required?

**Mostly not.** C1–C3, C5 and C6 are reading tasks, as long as the nuggets keep technical terms
**verbatim** (rule 3 in §3.2 is extended to terms, not only values). The annotator then never has to
decide whether a paraphrase of a legal term keeps its meaning.

Expertise matters in two places:
1. **A remaining paraphrase that might change legal scope.** Such items are escalated.
2. **C4 on long, multi-part answers** (e.g. Q001). Here "vital" is partly a judgment call even for
   experts, and it is expected to be the least reliable label. The robustness check in §3.4.4 covers
   it.

Escalated items (a few % expected) go to a tax or legal specialist in **one short session**. A
specialist does not have to review everything.

Annotators are **the user and another research team member** (D5). A team member without
specialist training works well with the guideline and the calibration round below. Record both
annotators' backgrounds for the paper.

#### 3.4.3 Process

1. **Guideline v1** (pt-BR, one worked example per check), written from the pilot outputs.
2. **Calibration round:** both annotators label the same **10 answers**, discuss every
   disagreement, and refine the guideline to **v2**. This round is not counted.
3. **Main audit:** a **stratified sample of 60 questions**:
   - stratified by answer length (tertiles), P&R chapter and flags (short answer, long
     enumeration, `procedimento_pgd`);
   - plus every question the validator flagged.

   Annotator A labels all 60 answers. Annotator B labels 12 of them independently (20 %). An
   **adjudication** step resolves their disagreements.
4. **Specialist session** for the escalated items.
5. **Report:**
   - pass rate per check with a 95 % CI (this gives the estimated error rate of the full set);
   - Cohen's κ per check between A and B;
   - a table of error types.
6. **Freeze gate:** C1 ≥ 95 %, and ≥ 90 % of answers with no missing vital fact (C5). If the gate
   fails, change the prompt or model and repeat the pilot. The fixed set is frozen as
   `nuggets/gold/v1/` (SHA-256). The corrections are released as a patch.

Tools: `review export` writes one XLSX per annotator. It has one row per nugget, with the answer
shown and uncovered lines highlighted. `review import` validates the labels and builds the patch.

Effort: about 500 nugget judgments for A (3–5 h) and about 100 for B (1 h), plus the calibration
round. Judge-calibration labels (§4.4) are the bigger task, about 1,200 labels and 8–12 h. They can
drop to 100 pairs (about 800 labels) if needed.

#### 3.4.4 Is there a creation method good enough to skip the audit?

**No published nugget-creation method has been validated for pt-BR tax Q&A:**
- [LN] reports no human check of its nuggets.
- TREC uses human assessors as the reference, and [GR] is itself a measurement of automatic nuggets
  **against** that reference.

What the literature offers is **design guidance**, which the prompt in §3.2 already follows:
- **atomic-fact decomposition**: FActScore, Min et al., EMNLP 2023;
- **decontextualization / "molecular facts"**: a fact should be as small as possible but still carry
  enough context to be checked alone. See Gunjal & Durrett, *Molecular Facts*, Findings of EMNLP
  2024, arXiv:2406.20079. This is the rule behind C2 and C3;
- **scores depend on the decomposition method**: Wanner et al., *A Closer Look at Claim
  Decomposition*, *SEM 2024, arXiv:2403.11903. This is the reason to measure the audit rather than
  assume quality.

So the method **reduces** errors, and the audit **measures** what is left. Two cheap additions make
the result stronger without more human work:

- **LLM cross-check over all 715 answers:** the model *not* chosen as creator runs C1–C3 and C5. Its
  flags are added to the human queue. The flags are **not** labels: the error estimate comes only
  from the random sample, so it stays unbiased.
- **Nugget-set robustness (D8):** make a second full nugget set with the other creator model (about
  715 calls), and score every RAG run with **both** sets. The paper's claim is a **comparison**
  (S1 vs S2 vs S3), not an absolute score. If the ranking of strategies agrees under both sets
  (Kendall τ, and the same sign in the paired tests), the conclusion does not depend on the choice of
  nuggets. This is the most direct answer to "are the nuggets good enough?". The extra cost is one
  more assignment pass per run, so it can be limited to the main comparisons.

---

## 4. Scoring system answers against the nuggets (assignment)

### 4.1 Input contract

Any RAG run is one JSONL file with one line per question:
`{"run_id": "...", "question_number": "001", "answer": "..."}`. The run metadata (strategy S1/S2/S3,
embedding model, top-k/context size, aggregator LLM) goes in a sidecar `run.json`. This keeps the
evaluator independent of the RAG code.

### 4.2 Assignment call

For each (question, system answer), the judge LLM gets the question, the system answer and **all
nuggets of that question in one call** (they are few; [AN] batches 10), and labels each nugget
`support` / `partial_support` / `not_support`, with a short justification.

**4th label, `contradicts`.** Take the gold nugget *"As despesas com instrução estão sujeitas ao
limite individual anual de R$ 3.561,50"* (Q400).
- Answer A does not mention the limit. [AN] labels this `not_support`.
- Answer B says the limit is R$ 5.000,00, or that there is no limit. [AN] also labels this
  `not_support`.

Both score 0, yet A is incomplete and B is wrong in a way that would mislead a taxpayer. A verdict
reversal ("Sim" instead of "Não") is the same kind of case. With `contradicts`, the judge labels B
separately:
- It scores 0 like `not_support`, so V_strict / A stay comparable with TREC. Mapping
  `contradicts` → `not_support` gives [AN]'s 3 labels back exactly.
- A **contradiction rate** per run is reported. This matters for the segmentation question: a
  retriever that brings in the wrong or outdated provision should show more contradictions, not
  just fewer supported nuggets.

It adds no extra call, only one more option in the same assignment prompt. The risk is that the
judge confuses "not mentioned" with "contradicted". The label is **kept** (D7). Calibration (§4.4)
reports its κ, so readers know how far to trust the contradiction rate.

### 4.3 Scores (from [AN], computed without an LLM)

Per question, with s(support)=1, s(partial)=0.5, s(not/contradicts)=0:

- **V_strict** = support-only credit over `vital` nuggets (main metric, as in TREC RAG 2024);
- **V** = vital nuggets, partial credit 0.5; **A_strict**, **A** = the same over all nuggets;
- **W** (weighted) = (Σ vital s + 0.5·Σ okay s) / (#vital + 0.5·#okay);
- optional: contradiction rate; legal-basis recall (§3.1).

Run score = mean over questions. Slices: with and without `procedimento_pgd`, and by chapter and by
answer length. Paired comparisons between strategies (S1 vs S2, same generator and k) use a paired
bootstrap or a permutation test over questions.

**Known limit:** nugget recall does not penalize extra wrong content. Nugget **precision** would
cover that: nuggetize the system answer too and check each of its nuggets against the gold answer.
It is left as an optional extension. It doubles the judge cost, and hallucinations are partly
covered by `contradicts`.

### 4.4 Judge calibration

- **Human labels** on 150 (question, answer) pairs: 50 questions × 3 systems of different quality,
  drawn from the first real RAG runs.
- Report nugget-level agreement (Cohen's κ, 3 or 4 labels) and **run-level ranking agreement**
  (Kendall τ) for each candidate judge. The judge used for the paper is the candidate with the best
  agreement within budget.
- **The judge must not be from the same model family as the aggregator LLM**, to avoid
  self-preference bias. If several aggregators from different families are tested, the judge is
  fixed and from a family not among them, or a second judge is reported as a robustness check.

### 4.5 Legal-provision score (secondary, D6)

> **Update 2026-09-27:** the gold citations now come from `dataset/references.jsonl` (v2.0).
> It has one row per (question, cited act), resolved to a corpus `document_id` / `document_urn`
> with LexML `article_ids`, and the v1.1 reference errors are corrected. 42 references whose act is
> not in the corpus are marked `not_in_corpus`. See
> `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md`. The v1.1 fields named below
> are superseded.

- **Gold citations** per question come from the dataset itself. `references` and
  `formatted_references` hold the reference block that `answer_cleaned` removed, and
  `formatted_embedded_references` holds the citations inside the answer text (569 questions have
  explicit references).
- **System citations** are extracted from the generated answer.
- Both sides are normalized to **LexML URNs with `../lexml-linker/`** (the same tool that produced
  the `Remissao` elements). Matching is then deterministic, with no LLM, at two levels: **document**
  (right law or IN) and **dispositivo** (right article, or §/inciso when both sides give one).
- Report citation precision / recall / F1 per level. This fits the segmentation question well: S2
  chunks carry the exact inciso path, so they should raise dispositivo-level precision.
- Per-nugget `legal_basis` (§3.1) stays as a finer, optional view: does the answer cite the right
  provision *for this fact*?

---

## 5. Which LLMs: options and recommendation

**Is an LLM needed?** For **creation**, the only alternatives are rule-based splitting (sentences or
list items) or full manual annotation. Rule-based pieces are not self-contained ("Não há limitação
quanto à idade"), and manual annotation of about 700k characters is too expensive. So an LLM with
human audit is the practical choice. For **assignment**, cheap non-LLM baselines exist: NLI
cross-encoders for pt-BR, and embedding similarity. They handle negation and numeric mismatch badly,
and those are exactly what tax answers depend on. They are worth running **once as a sanity
baseline** only.

The two roles have very different cost profiles:

| Role | Calls | Tokens (estimate) | What matters |
|---|---|---|---|
| Creation | 715, **once** | ≈ 1.3 M in / 0.3 M out | Quality. Cost is negligible, so use the strongest model |
| Assignment | 715 **per RAG run** | ≈ 1.8 M in / 0.15 M out per run | Cost × number of runs, determinism, agreement with humans. The grid of 3 strategies × embedding models × k × generators can reach 50–100 runs, about 100–180 M input tokens |

Candidates (versions and prices must be checked and pinned when implementing, as in the embedding
plan):

| Option | Examples | For | Against |
|---|---|---|---|
| A. [LN] setup | `gpt-5.4-nano` + [LN] prompt | Same setup as the reference paper; very cheap | Smallest model; [LN] itself reports context loss on BR-TaxQA |
| B. Frontier API | Claude Opus 5.5 / Sonnet 5, a larger GPT-5.x, Gemini (Pro/Flash) | Best pt-BR reasoning; structured outputs; batch APIs (≈50 % cheaper) and prompt caching for assignment | Closed; the model can change or be retired, so reruns are not guaranteed; cost grows with the number of runs |
| C. Open weights (vLLM) | A recent large Qwen3-family instruct model, gpt-oss, Llama | **Pinned weights = exactly reproducible** by anyone using the released code; no per-token cost | Needs GPU endpoints (the HF Endpoint setup from the embedding work can be reused); may lag B on legal nuance and needs calibration |
| D. Brazilian model | Sabiá (Maritaca AI) | Trained for pt-BR, including legal text | API only; smaller ecosystem; check structured-output support |

**Recommendation**

- **Creation:** a strong **option B** model as the main nuggetizer. A **second family** (another B,
  or C) runs on the pilot only, to measure nugget-set agreement. Option A runs as the paper baseline.
  The nuggets are then **frozen and released**, so later readers do not need that model at all: the
  gold nuggets become part of the dataset.
- **Assignment (D2, revised 2026-09-27):** calibrate **Gemini** (B) and an open-weight **Qwen** (C)
  against the human labels (§4.4). If Qwen's agreement is within about 0.05 κ of Gemini's, Qwen is
  primary (reproducible, and no per-token cost over many runs) and Gemini is the second judge.
  Otherwise the roles swap. An OpenAI judge on a subset measures self-preference.
- In all cases, set temperature 0 where the API allows it (otherwise record the reasoning-effort
  setting and seed), and **cache every raw response** keyed by hash(model, prompt version, input),
  so reruns are free and the raw outputs can be released.

**Using `castorini/nuggetizer` directly or reimplementing?** nuggetizer is Apache-2.0 and supports
OpenAI, OpenRouter and vLLM. But its prompts are in English, its creation step iterates over a pool
of retrieved documents, and it uses TREC input formats. We **reimplement the protocol** with pt-BR
legal prompts and a gold-answer source. We also write an **exporter to nuggetizer's JSONL format**
and run the original tool on a sample as a cross-check. The exporter also lets others use our
nuggets with their existing tooling.

---

## 6. Phases and gates

| # | Phase | Output | Gate |
|---|---|---|---|
| 0 | Scaffold: package, providers (`openai`, `anthropic`, `gemini`, `openai_compat` for vLLM/Maritaca, `fake`), `prepare` | `nuggets/gold/input/questions.jsonl` + manifest | Tests pass with the `fake` provider |
| 1 | **Pilot creation:** 30 stratified questions × {OpenAI, Gemini, optional [LN] baseline} × {1 call, 2 calls}; guideline v1 + calibration round (§3.4.3) | `nuggets/pilot/…` + comparison report | A human reviews the pilot and picks model + prompt |
| 2 | **Full creation** + `validate` + LLM cross-check; second nugget set with the other model (D8) | `nuggets/gold/v0/`, `nuggets/alt/v0/` | 0 hard validation errors |
| 3 | **Human audit** (§3.4) + corrections | `nuggets/gold/v1/` (frozen) | Audit gate met |
| 4 | **Judge calibration** (§4.4) on the first RAG runs: Gemini vs Qwen (+ OpenAI subset) | `nuggets/calibration/` + report | Primary judge chosen; κ reported, including for `contradicts` |
| 5 | **Scoring** of all RAG runs | `nuggets/assignments/<run_id>/<judge>/`, `nuggets/scores.csv` | — |
| 6 | **Release:** code + gold nuggets + human labels + raw responses | HF dataset v2.0 (nuggets config) + repo | README quick start works in a clean venv |

A dated `docs/` note records the decisions and results at the end of each phase.

---

## 7. Code design (`scripts/nuggets/`)

This mirrors `scripts/embedding/`: one CLI, one YAML registry, provenance manifests and a `fake`
provider for tests.

```
scripts/nuggets/
  README.md               quick start, formats, costs, reproducing the paper
  nuggets.py              CLI entry point (argparse subcommands)
  models.yaml             LLM registry: provider, model id/snapshot, params, price, api_key_env
  prompts/                create_v1.pt.md, importance_v1.pt.md, assign_v1.pt.md, ln_baseline.pt.md
  nuggetizer/
    data.py               load/prepare questions (HF pinned revision or local JSON)
    schema.py             pydantic models + exported JSON Schemas (nugget, assignment, run)
    providers/            base.py (one `complete_json(messages, schema)` interface), openai.py,
                          anthropic.py, gemini.py, openai_compat.py, fake.py
    cache.py              content-addressed raw-response cache (JSONL)
    create.py, validate.py, review.py, assign.py, metrics.py, export.py (nuggetizer format)
  tests/                  pytest: schema, validation rules, metrics math, fake-provider end-to-end
```

**CLI (target usage for the README):**

```bash
N=scripts/nuggets/nuggets.py
.venv/bin/python $N prepare                                   # fetch + clean the 715 gold answers
.venv/bin/python $N create   --model <slug> [--questions 001,002] [--limit 30]
.venv/bin/python $N validate --nuggets nuggets/gold/v0
.venv/bin/python $N review export|import ...
.venv/bin/python $N assign   --nuggets nuggets/gold/v1 --answers runs/<run>.jsonl --judge <slug>
.venv/bin/python $N metrics  --assignments nuggets/assignments/<run>/<judge>
```

**Output layout:**

```
nuggets/
  gold/input/questions.jsonl, manifest.json
  gold/v1/nuggets.jsonl, manifest.json, validation.json, audit/ (sample, labels, patch)
  raw/<step>/<model>/responses.jsonl      every raw LLM response (released)
  assignments/<run_id>/<judge>/assignments.jsonl, manifest.json
  scores.csv                              one row per run × judge × metric × slice
```

**Manifests** record the git commit and dirty flag, the input SHA-256, the prompt file SHA-256,
model id/snapshot and parameters, token usage and cost, timings and error counts. Cost goes into a
ledger like `embeddings/costs.csv`. **Resumable:** questions already in the cache or output are
skipped. **Concurrency** is bounded, with retry and backoff. **Batch API** mode is optional for
`assign`.

**Documentation for release:** the README gives a 3-command quick start (prepare → assign → metrics
with the released gold nuggets, so users need no creation step), every file format with an example,
how to add a provider, and cost tables. Docstrings go on the public functions.

---

## 8. Open questions

Answered on 2026-09-26 and 2026-09-27: see §0 (D1–D8). Still open:

1. **How Qwen is run for the judge:** our own HF endpoint (vLLM, pinned revision) or a hosted API
   with a pinned version, and which model size (D4).
2. **Name and background of the second annotator** (for the guideline round and the paper, §3.4.2).
3. **Tax/legal specialist** for the escalation session (§3.4.2): who is available?
