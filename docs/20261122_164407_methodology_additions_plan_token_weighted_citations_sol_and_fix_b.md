# Plan: methodology additions (token-weighted metric, in-text citations, GPT-6.2 Sol) and the corpus revision

Date: 2026-11-22. Plan note. **Status (2026-11-22):** B done (`docs/20261122_181611_*`); A1 done
(`docs/20261122_192653_a1_token_weighted_provision_metric_results.md`); A2 and A3 not started. It covers four
pieces of work:

- **A1:** a token-weighted provision metric, to measure how much of each strategy's context is noise;
- **A2:** scoring the legal provisions cited in the answer text (closed book first);
- **A3:** answer quality and cited provisions of `gpt-6.2-sol`, to test whether it strengthens the trend
  seen with GPT-5.6 Terra;
- **B:** whether to do the pending corpus revision (fix B) now.

## Summary

**Recommendation: do fix B first, then A1, A2 and A3 on the revised corpus.**
- Fix B is cheap at this point. Only 0–2 of the 715 contexts per 4k run hold a misparsed chunk or its
  neighbour, plus 1–11 that hold an article to be reviewed for duplication. So at most ≈ 1.5% of the
  answers need regenerating.
- A1 needs a rerun of the evaluation and a new unit-token table anyway. Building both once, on the
  final corpus, avoids redoing them.
- Running Sol on the final contexts means its answers never need regenerating.
- The public release needs fix B regardless.
- The cost of fix B is time (parser repair, renumbered chunk ids, rebuilding the dashboards), not
  money.

**Costs** (§7). A1 and A2 make no API calls. Fix B ≈ $3–6 across accounts. A3 (Sol: closed book, S1,
S2 and oracle at 4k, plus scoring) costs ≈ $19–25 at the half-price batch rate, or ≈ $31–42 at list
price. **Total ≈ $22–31 with batch, ≈ $35–50 at list price** (all accounts), before a 20% contingency.

**Budget: two blockers before any paid step.**
1. **The OpenRouter key has expired.** `GET /api/v1/key` on 2026-11-22 returned HTTP 401 "API key
   expired". A new key, with a budget cap, is needed.
2. **Credit left: ≈ $37.3 on the old key's $200 limit.** That is $37.34 after the Gemini comparison on
   2026-11-08, minus $0.08 of ledger spending since. Whether the account's prepaid credit still covers
   it must be checked with a management key or on the dashboard. At batch prices everything fits in
   ≈ $37 with a small margin. At list price A3 alone nearly uses it up.

**Decisions needed** (§8):
- D1: the timing of fix B;
- D2: the Sol endpoint (batch, list price or a direct OpenAI key) and its reasoning setting;
- D3: Sol's scope (4 conditions, or more);
- D4: a new OpenRouter key and confirmation of the remaining credit.

## 1. Where things stand

- **Results to extend:** phase 5 (`docs/20261023_210727_rag_phase5_scoring_and_analysis.md`), Gemini
  comparison (`docs/20261108_175117_*`), fix A (`docs/20261115_181838_*`), granularity analysis
  (`docs/20261122_130934_*`), in-text citation plan (`docs/20261122_134404_*`).
- **The Terra trend** (phase 5 §2–3):
  - Terra answers the P&R questions about as well without retrieval as with it: closed book 0.351
    V_strict, against S1 0.325, S2 0.341 and oracle 0.368. Closed book → S2 is −0.010, p .56.
  - For the smaller or weaker generators, retrieval helps clearly. Closed book → S2: Luna +0.041,
    Sabiá-4 +0.078, Sabiazinho-4 +0.095.
  - What retrieval buys Terra is correctness. Closed-book answers contradict at least one nugget in
    29.5% of the questions, against 8.0% with S2.
  - Its S1 → S2 gain is the smallest of the GPT models (+0.016, not significant on the primary set).

  The hypothesis for A3: a stronger, newer model knows the P&R content better. Retrieval would then
  add even less to recall, or take away from it, while still cutting contradictions.

## 2. Fix B: the corpus revision, now

### 2.1 Scope

The scope is unchanged from `docs/20261115_172140_gold_matcher_annex_rule_and_misparsed_articles.md`
§5:
1. repair the parse of the 6 misparsed documents and confirm the 2 "to check" ones;
2. review the 21 article-level duplicate ids;
3. add both checks to the article-coverage audit;
4. re-segment;
5. re-embed the changed chunks (both embeddings);
6. rerun retrieval, evaluation and contexts, then regenerate and rescore only the answers whose prompt
   changed;
7. drop the chunk exclusions that are no longer needed;
8. release new versions of repos A and B.

### 2.2 Measured impact on the existing runs (2026-11-22)

Contexts holding a flagged chunk (§2 of the fix A note) or the chunk next to it, where the moved
heading or citation text would land; and, separately, contexts holding a chunk of the documents whose
duplicates must be reviewed (Lei 12.715, Decreto-Lei 58/1937, MP 2.228-1 annex):

| Context set | Flagged ±1 | Duplicate-review documents |
|---|---:|---:|
| jua S1 / S2 4k | 2 / 1 | 6 / 11 |
| jua S2c / S3 / S4 4k | 2 / 0 / 1 | 8 / 11 / 8 |
| jua S1 / S2 2k | 1 / 1 | 3 / 7 |
| jua S1 / S2 8k | 10 / 7 | 14 / 19 |
| gemini S1 / S2 4k | 2 / 1 | 1 / 2 |

- **Upper bound:** ≈ 15 contexts per 4k set and ≈ 30 per 8k set change, out of 715. Only the contexts
  whose rendered text changes produce new requests. All others come from the LLM cache at no cost:
  chunk ids are renumbered, but ids are not in the prompt.
- **Oracle contexts** change only where a gold article is repaired (Q006 and a few others).
- **Rankings** of other questions could shift slightly, because changed chunks get new vectors. This
  matters only where a changed chunk crosses a context boundary, and those cases are already in the
  counts above.

### 2.3 Why now

- **It costs about the same now or later**, since later it would also cover Sol's answers in the same
  ≈ 1.5% of contexts. But doing it **after** A1–A3 would change every reported number once more:
  retrieval, nuggets, citations and the token-weighted metric, plus the dashboards and the HF release.
- **A1 is built on the chunk table and the LexML** (unit token counts, §3.2). Building it on the
  repaired corpus avoids building it twice.
- **The public release** (moving the HF repos to `unicamp-dl`) is the other trigger for fix B, and the
  additions will have to be released anyway.
- **Risk:** the parser repair is manual work in a sibling repo, of uncertain size. If it takes longer
  than ≈ 2 days, A1 and A2 (both free) can run on the current corpus, while Sol waits for the repaired
  contexts. Sol is the only paid step that fix B affects.

### 2.4 Fix B steps and costs

| Step | Work | Cost |
|---|---|---:|
| B1 | Repair the 6 documents (parser fix or `.docx` repair under `scripts/lexml/`); check the 2 "to check" ones and the 21 duplicates against the sources; extend the coverage audit | time (1–2 days) |
| B2 | Re-parse the affected documents, re-segment all (`segment_all.py`), validate (`validate_segments.py`) | free |
| B3 | Re-embed changed texts: **gemini-emb-2** (OpenRouter, cents); **jua** (HF Inference Endpoint, TEI, same instance type as the original; ≈ 1 h) | < $0.05 OR; ≈ $1–3 HF |
| B4 | Parity check: unchanged texts keep their vectors (copied, not re-embedded); re-embed a sample of 20 unchanged texts to confirm the endpoint reproduces them | included |
| B5 | `rag.py retrieve` + `evaluate` (both embeddings) + `context` | free (minutes) |
| B6 | Regenerate the answers whose prompt changed: ≤ ≈ 15 per 4k run, ≤ ≈ 30 per 8k run, over the 25 jua runs + 4 Gemini runs + the oracle; dry run first to count them | ≈ $0.5–1.5 (OR + Maritaca) |
| B7 | Rescore those answers (`nuggets.py score`), context support of the changed contexts (`ctxsupport`), `scoretable`, `analyze` | ≈ $1–2 OR |
| B8 | Rebuild the dashboard, trace and explorer data; new results note; HF repos A and B (`build_release.py`, `push_release.py`) | free |

**Fix B total ≈ $3–6** (OpenRouter ≈ $2–3.5; Maritaca ≈ $0.5; HF ≈ $1–3).

## 3. A1: token-weighted provision metric (retrieval noise)

### 3.1 What it measures

Today, a chunk that touches a gold unit counts whole:
- `hit_full` / `hit_any` per gold item;
- `context_precision` = tokens of the texts that touch any gold unit ÷ context tokens.

So a 3000-token chapter (S3) or a whole article (S1) that holds a 40-token inciso counts as fully
relevant (granularity note §1 and §5). A1 counts only the **gold tokens**.

### 3.2 Building block: token counts per LexML unit

New table `segmented/unit_tokens.csv.gz`: one row per `(arquivo, unidade_id)` with:
- `own_tokens`: Qwen3 tokens of the unit's own text, without its children;
- `subtree_tokens`: the unit with all its children.

The tokenizer is the same as for `n_tokens_qwen3`, and the text is taken from the LexML with the
segmentation's normalisation (`scripts/segmentation/common.py`).

Check: for each unsplit article, `subtree_tokens(art)` + its prefix (ementa, label) ≈ `n_tokens_qwen3`
of its ART chunk. Report the deviation.

### 3.3 Overlap of a chunk with a gold unit

For a chunk `c` and a gold unit `u` (provision level; the article level uses `u = art`):
- `c` contains `u` (ancestor in `cobre_ids`, or a grouping chunk around it): overlap =
  `subtree_tokens(u)`;
- `c` holds part of `u` (descendant, or a split-article part): overlap = the sum of `subtree_tokens`
  of the units of `c` that lie inside `u`;
- otherwise 0.

Within a context, each gold unit's tokens count once: with merge de-duplication, a unit is never in
two texts. All other tokens are split into two kinds:
- **scaffold**: ementa, grouping names, article label, ancestor path, and the caput sentence of
  S2c/S4. Computed as the chunk's tokens minus the `own_tokens` of the units it holds;
- **off-gold content**: everything else.

### 3.4 Metrics

At the article and provision levels, budget view:

| Metric | Definition | Reads as |
|---|---|---|
| `token_recall` | gold tokens in the context ÷ gold tokens of all gold units (per question) | how much of the cited text was delivered; partial credit for S2 fragments and split-article parts |
| `token_precision` (signal ratio) | gold tokens ÷ context tokens | how much of the context is the cited text |
| `noise_share` | off-gold content ÷ context tokens | retrieval noise |
| `scaffold_share` | scaffold ÷ context tokens | the price of self-contained chunks (S2c/S4 caput, S3 headings) |
| `item_coverage` | per gold item: share of its tokens in the context | a graded `hit_full`; the mean over items is `token_recall` macro-averaged |

These are added to `metrics.csv` and `per_item.csv.gz` under a **new evaluation id**, e.g.
`v3_either_containment_merge_skip`. The other metrics are unchanged.

### 3.5 Analyses

1. Noise and signal by strategy × budget × level. Expected: S1 and S3 have high noise; S2 the
   highest signal ratio. S2c/S4 show the cost of their scaffold.
2. Does token precision explain answer quality or utilisation better than the binary hit?
   Per-question Spearman with V_strict and with utilisation (phase 5 `utilisation_runs.csv`), the same
   design as granularity note §4.
3. Rerun the whole-article vs sub-article split (granularity note §3) with `item_coverage` in place of
   `hit_full`.

### 3.6 Implementation and cost

- `scripts/segmentation/`: the unit-token builder, run after segmentation.
- `ragpipe/relevance.py`: per-match token overlaps.
- `ragpipe/evaluation.py`: the new columns.
- `ragpipe/metrics.py`: the aggregates.
- Tests on the conftest corpus.
- Results note and the dashboard's retrieval tab.

**No API calls.** About 1.5–2 days.

## 4. A2: in-text legal citations (closed book first)

Follow `docs/20261122_134404_in_text_legal_citation_scoring_plan.md`:
- extraction with `citations.py`;
- act resolution with `lexml-linker` + a regex resolver for Receita Federal acts + an alias table;
- scoring at the three levels;
- validity checks (non-existent article, act outside the corpus, after 2024-05, revoked);
- for RAG answers, in-text citations vs linked sources vs context.

Two changes for this plan:
- **Order:** closed book of the 4 current generators first; then S1/S2/oracle 4k; then Sol (A3), which
  gets the same tables at no extra work.
- **Sol is the most interesting case:** a later knowledge cutoff makes citations of acts from after
  the reference date more likely (e.g. the INs of the 2025 or 2026 returns). The validity check of
  plan §3.5 is the direct test.

**No API calls.** About 2–3 days.

## 5. A3: GPT-6.2 Sol

### 5.1 The model and its endpoints (OpenRouter catalogue, 2026-11-22)

- `openai/gpt-6.2-sol`: created 2026-11-17; context 1.05 M tokens. Knowledge cutoff not in the
  catalogue (probe it, record it in `llms.yaml`).
- Endpoints:
  - `openai`, `azure` and `amazon-bedrock` at **$2 / $10 per M tokens** (input / output; cached input
    $0.10);
  - `openai/fast` and `openai/ultrafast` at 2× and 3× that.
- **No `openai/flex` endpoint**, unlike Terra and Luna (flex is half price).
- The half-price option is the **`openai/gpt-6.2-sol:batch`** model id: **$1 / $5**, served by
  `openai`. How OpenRouter runs `:batch` (synchronous with a delay, or an asynchronous job) has to be
  probed. Our client's batch support (`llm_client/batch.py`) covers the OpenAI and Gemini batch APIs
  directly, not OpenRouter's.
- For comparison, Terra is $2 / $12 list, $1 / $6 flex. Per token, Sol costs about the same as Terra.

### 5.2 Design: comparable with Terra

- **Same conditions as Terra:**
  - closed book (`answer_closed_v1`);
  - S1 4k and S2 4k (`answer_v1`, jua contexts);
  - oracle 4k (596 questions with gold).

  715 questions each. These are exactly Terra's four full runs.
- **Same request shape:**
  - `json_schema` output, `max_tokens 4000`;
  - one pinned upstream (`only: [openai]` or the `:batch` route), `allow_fallbacks: false`,
    `require_parameters: true`, `data_collection: deny`;
  - the same tool and web-search guard (citation plan §1.1).
- **Reasoning:** Terra ran with effort `none`. Sol lists `reasoning_effort`. Probe whether `none` is
  accepted:
  - if it is, use it (comparable);
  - if the minimum is `minimal` or `low`, record it and report the reasoning tokens. That is a
    confound to state, since the trend could come partly from reasoning.
- **Optional, cheap controls:**
  - `wrong-S2_budget4000` on `stratified_30` (≈ $0.2): checks that Sol reads the context;
  - Sol S2 with gemini-emb-2 contexts (≈ $5): only if D3 asks for it.
- **Confound to state:** Sol differs from Terra in both generation (6.2 vs 5.6) and tier (Sol vs
  Terra). The catalogue has `gpt-6.1-terra` but no `gpt-6.2-terra`, so the two cannot be fully
  separated. An optional `gpt-6.1-terra` closed book + S2 run (≈ $4–6 at $1 / $5 list) would separate
  most of it.

### 5.3 Hypotheses and analyses

Run on the primary nugget set, judge Gemini 3.8 Flash, as in phase 5.

- **H1, retrieval adds less recall:** closed book → S2 for Sol ≤ Terra's −0.010. Test the
  difference-in-differences (Sol − Terra) × (S2 − closed book), paired by question, with bootstrap CI
  and permutation p.
- **H2, retrieval still buys correctness:** the contradiction rate drops from closed book to S2 for
  Sol, as for Terra (29.5% → 8.0%).
- **H3, more own knowledge used inside RAG answers:**
  - higher leakage, P(answer support | context not support);
  - more "answer support not in context" (phase 5 §5, `utilisation_runs.csv`);
  - more in-text citations outside the context (A2 §3.6).
- **H4, closed-book citations are more accurate, and more often from later years:** A2 cited
  recall/precision against the gold references, and the after-reference-date share. Sol vs Terra vs
  the others.
- **H5, S1 → S2 gain smaller than Terra's** (+0.016).

Also report: Sol vs Terra per condition (paired), the values checks, abstention and answer length.
`analyze` runs as is once the runs are registered.

### 5.4 Steps

1. **Probe (≈ $0.05):**
   - check that `reasoning: none`, `response_format: json_schema` and `require_parameters` are accepted
     on the chosen endpoint;
   - see how `:batch` behaves;
   - check `served_provider` and the billed cost per call;
   - record the knowledge cutoff the model states (as information only).
2. **Registry entry** `gpt-6.2-sol` in `scripts/rag/llms.yaml` (price, routing, cutoff), plus an
   experiment file `scripts/rag/experiments/sol.yaml` (4 conditions; prompts as in `full_stage1.yaml`).
3. **Pilot on `stratified_30`** (≈ $0.7): measure input and output tokens per answer to replace the
   assumptions in §7, read some answers, stop if the cost is off by more than 30%.
4. **Full generation** (`rag.py run --budget`), with the ledger reviewed after each condition.
5. **Scoring:** `nuggets.py score` (4 runs), `scoretable`, `analyze`; with the pilot, `stratified_30`
   tables too. No `ctxsupport` is needed: the contexts are shared with the other generators.
6. **Results note,** HF repo B update, dashboard and explorer rebuild.

## 6. Order and gates

| Stage | Content | Paid | Gate before the next stage |
|---|---|---|---|
| 0 | New OpenRouter key with a cap; confirm the account credit; D1–D3 answered | — | user |
| 1 | Fix B (B1–B8) | ≈ $3–6 | results note; numbers that moved are listed; the user reviews |
| 2 | A1 on the revised corpus | free | noise tables look sane (unit-token check < 5% deviation) |
| 3 | A2 on closed book of the 4 generators, then their RAG runs | free | manual check of 100–150 citations ≥ 95% correct attribution |
| 4 | A3 probe + pilot | ≈ $0.8 | per-answer cost within 30% of §7 |
| 5 | A3 full generation + scoring + A2 for Sol | ≈ $19–41 | ledger within the cap; stop and report on an overrun (CLAUDE.md) |
| 6 | Analyses (H1–H5, A1 × quality), note, HF release, dashboards | free | — |

Stages 2–3 can start before stage 1 ends if the parser repair drags (§2.3). Then only their final
numbers are recomputed after fix B, at no cost.

## 7. Cost estimate

### 7.1 A3 (Sol), from Terra's measured tokens

Terra's ledger: mean input / output tokens per answer were closed book 421 / 296, S1 4k 3,715 / 404,
S2 4k 3,768 / 403, oracle 4k 2,526 / 402.

- **Input:** 7.15 M tokens over the 4 conditions (715 + 715 + 715 + 592 answers).
- **Output:** 1.03 M tokens at Terra's length. Sol is assumed to write 1× to 2× as much:
  1.03–2.06 M tokens.

| Item | Batch ($1 / $5) | List ($2 / $10) |
|---|---:|---:|
| Input 7.15 M | $7.2 | $14.3 |
| Output 1.03–2.06 M | $5.2–10.3 | $10.3–20.6 |
| Generation | **$12.4–17.5** | **$24.6–34.9** |
| + if the minimum reasoning effort is not `none` (≈ 500 reasoning tokens/answer, 1.37 M) | +$6.8 | +$13.7 |
| Scoring, 2,737 answers × $0.0023 (phase 5 rate, Flash flex) | $6.3 | $6.3 |
| Probe + pilot | $0.4 | $0.8 |
| **A3 total (without reasoning)** | **≈ $19–24** | **≈ $32–42** |

Optional: wrong context $0.2; Sol S2 with gemini contexts ≈ $5–7; `gpt-6.1-terra` closed book + S2
≈ $4–6 plus scoring $3.3.

### 7.2 Everything

| Work | OpenRouter | Maritaca (BRL billing) | HF endpoint |
|---|---:|---:|---:|
| Fix B | $2–3.5 | ≈ $0.5 | $1–3 |
| A1 token-weighted metric | $0 | — | — |
| A2 in-text citations | $0 | — | — |
| A3 Sol (batch / list) | $19–24 / $32–42 | — | — |
| **Total** | **$21–28 / $34–46** | **≈ $0.5** | **$1–3** |
| + 20% contingency | $25–33 / $41–55 | | |

### 7.3 Does it fit?

- **OpenRouter:** ≈ $37.3 left on the old key's limit (estimate; the key has expired).
  - **Batch route:** everything fits, contingency included ($25–33).
  - **List route:** fits only without contingency and without reasoning tokens, and not with the
    optional runs.

  If batch is not usable, the options are: raise the limit (if the account has the credit), use a
  direct OpenAI key with the Batch API (`llm_client/batch.py` supports it; `OPENAI_API_KEY` is not in
  this machine's `.env`), or drop the oracle condition (≈ −$5–8 at list price, scoring included) and keep closed book,
  S1 and S2.
- **Maritaca and HF** are billed separately; their amounts are small.

## 8. Open decisions

| # | Decision | Proposal |
|---|---|---|
| D1 | Timing of fix B | **Now, before A3** (§2.3); A1/A2 may start in parallel |
| D2 | Sol route and reasoning | `:batch` if the probe shows it works with our client and honours the parameters; else list price on `openai` with a cap. Effort `none` if accepted, else the lowest, reported as a confound |
| D3 | Sol scope | The 4 Terra conditions (closed book, S1, S2, oracle 4k); optional wrong-context control ($0.2); no Gemini-context or `gpt-6.1-terra` runs unless asked |
| D4 | Key and credit | User: create a new OpenRouter key (cap ≈ $40), confirm the account credit, add the key to `.env` |
| D5 | A1 evaluation id | New id `v3_either_containment_merge_skip`; keep the old ones for provenance |
| D6 | A2 defaults | As in the citation plan §7 (acts outside the corpus count as wrong but are reported apart; coarse citations are full matches at the provision level) |
