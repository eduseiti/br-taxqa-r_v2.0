# Plan: reproduce the best jua-4b-mixed results with gemini-embedding-2

**Generated:** 2026-11-08 15:32:58 (local time, from `date +%Y%m%d_%H%M%S`).
**Status:** **executed on 2026-11-08: steps 1–8, B then A.** Results, costs and what is not done are in
`20261108_175117_gemini_embedding_2_setup_embedding_and_retrieval_gate.md`. The rest of this note is the plan as written. **The open points were decided by the
user on 2026-11-08 (§6):**
- the embedding goes through OpenRouter;
- the document template is `title: none`;
- Terra is not added;
- **all texts are embedded.**

The OpenRouter key limit was raised to $200: $55.22 left at 17:15.
**Builds on:**
- the scoring and analysis note `20261023_210727_rag_phase5_scoring_and_analysis.md` (the jua results);
- the trimmed-grid plan `20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md`
  and the generation note `20261023_151928_rag_phase3_trimmed_full_generation.md` (measured costs);
- the embedding plan `20260925_122058_embedding_implementation_plan.md` (§1.1, §5.2, §8.2, §9.2: the Gemini
  design that was deferred);
- the HF release plan `20261024_180016_hugging_face_release_plan.md` (§3.1, §9: what is on the Hub).

**Goal:** test whether a stronger embedding changes the main result, using as few new runs as possible. The
main result is that S2 beats S1 by a small but robust margin, and S3, S2c and S4 add nothing. Every number
here comes from the jua-4b-mixed runs. Only the retrieval stage changes: segmentation, generators, prompts,
nugget set, judge and the 4k budget stay the same.

---

## 1. Which results to compare against

### 1.1 The best results with jua-4b-mixed (V_strict, 715 questions, phase 5 note §2–§3)

| Generator | closed book | S1 4k | S2 4k | best other 4k set | oracle 4k | S1 → S2 |
|---|---:|---:|---:|---|---:|---|
| GPT-5.6 Terra | **0.351** | 0.325 | **0.341** | — | 0.368 | +0.016, p .11 (significant under both other nugget sets) |
| Sabiá-4 | 0.239 | 0.290 | **0.317** | S3 0.315 | 0.319 | **+0.027, p .009** |
| GPT-5.6 Luna | 0.259 | 0.271 | 0.299 | **S2c 0.314** | 0.338 | **+0.028, p .007** |
| Sabiazinho-4 | 0.177 | 0.267 | 0.272 | **S4 0.287** | 0.293 | +0.005, p .63 |

Retrieval-side numbers that a new embedding can move:
- context support (vital nuggets the context fully states): S1 4k 0.397, S2 4k 0.411, oracle 4k 0.483 (§4);
- context article recall on the 596 questions with gold: S1 0.398, S2 0.503, oracle 0.803 (§6.2);
- the legal-provision retrieval test (`runs/retrieval/jua-4b-mixed/irpf/eval/`): free to recompute.

### 1.2 What the comparison should contain

**Keep:** S1 4k and S2 4k. S2 4k is the best RAG strategy for Sabiá-4 and Terra, and S1 → S2 is the paper's
main hypothesis. Rerunning both shows two things:
- whether the better embedding raises the scores;
- whether the S2 gain survives it, grows, or disappears. A stronger embedding may find the right article
  in S1 anyway.

**Do not rerun:**
- **closed book and the oracle contexts.** They do not use retrieval, so the jua answers and scores are the
  reference for both embeddings.
- **S3, S2c and S4.** They add nothing measurable over S2 (all |diff| ≤ 0.014, none significant).
  Luna's S2c 0.314 is the best Luna score, but its gain over S2 (+0.014, p .15) is not significant. It is an
  optional extension (§4.3).
- **the 2k / 8k budgets and `wrong-S2`**: they are controls and sweeps, not best results.

**Generators**, ranked by how informative they are for the cost:

| Generator | Why | Cost of one 715-question run (generation + scoring) |
|---|---|---:|
| **GPT-5.6 Luna** | S1 → S2 significant. It gains most from better contexts (S1 → oracle +0.044, p .002), so it is the most sensitive to retrieval quality. Cheapest generator | ≈ $0.48 + $1.65 = **$2.1** |
| **Sabiá-4** | S1 → S2 significant. It is the Portuguese model, and one of the two generators in the cross-set and second-judge checks | ≈ $4.6 (Maritaca, direct) + $1.65 = **$6.3** |
| GPT-5.6 Terra | Highest RAG score, but retrieval does not help it (closed book 0.351 ≥ S2 0.341). A better embedding mainly shows up as fewer contradictions, not higher recall | ≈ $5.0 + $1.65 = $6.7 |
| Sabiazinho-4 | No S1 → S2 gain; utilisation of the context is lowest (0.48–0.49) | ≈ $0.93 + $1.65 = $2.6 |

**Recommendation: Luna and Sabiá-4 on S1 4k and S2 4k (4 runs).** These are the two generators where both
retrieval and segmentation matter significantly. Add context support on the two new context sets: it is the
direct measure of what the better embedding puts in the context, and it lets the linkage decomposition of
§5 of the phase 5 note be repeated. Terra and Sabiazinho-4 are optional (§4.3).

### 1.3 A free gate before any LLM call

Run the legal-provision retrieval test on the Gemini rankings first (`rag.py evaluate`, no LLM, ≈ 30 s) and
compare it with jua (`rag.py compare`, or the metrics side by side):
- article recall at the 4k budget, S1 and S2;
- recall@k of the unit and raw-rank views.

If Gemini is clearly better, go on to generation. If it is no better or worse, stop and report: generation
and scoring would then measure noise. That would still be a result: "the stronger embedding does not
retrieve the cited provisions better".

---

## 2. Downloading what is on Hugging Face

### 2.1 What this machine (`f3593e5b57d4`) has now (checked 2026-11-08)

- The git checkout is clean and up to date (HEAD `1783692`), so everything tracked in git is here:
  - `dataset/`, `nuggets/gold/v0-auto/`;
  - the answer files (`answers.jsonl`, `run.json`);
  - the scoring labels and tables (`nuggets/scoring/`, 299 files);
  - the manifests.
- `segmented/chunks_all.csv.gz` is the released one (SHA-256 `a6087b7f…326a`, 104,574 rows, 101,943 unique
  texts).
- **The local jua embeddings and rankings are stale. Do not use them.**
  - `embeddings/jua-4b-mixed/corpus/vectors.npy` has 115,582 rows: it is the 2026-10-08 store.
  - The release, and every RAG run, uses the 2026-10-09 store with 101,943 rows (its `manifest.json` is
    here, its vectors are not).
  - `runs/retrieval/jua-4b-mixed/irpf/*/rankings.csv.gz` are also from 2026-10-08.
- **Missing:**
  - the generator contexts (`runs/contexts/…/contexts.jsonl.gz`; only the manifests are here);
  - all raw LLM caches (`runs/answers/cache/`, `nuggets/scoring/cache/`, `nuggets/full/cache/`).
- **`.env`** has `HF_TOKEN`, `GEMINI_API_KEY`, `OPENAI_API_KEY` and `DASHSCOPE_API_KEY`. It does **not**
  have:
  - `OPENROUTER_API_KEY` (needed for Luna, the judge, and the OpenRouter embedding route);
  - `MARITACA_API_KEY` (Sabiá-4);
  - `HF_RELEASE_TOKEN` (needed to read the private repos).

### 2.2 Operations (repo B, private `eduseiti/BR-TaxQA-R-RAG-eval`, HF commit `af37fda`)

The repo mirrors the git paths (release plan R5), so `hf download … --local-dir .` puts files where `rag.py` and
`nuggets.py` expect them. Repo A (`eduseiti/BR-TaxQA-R`) is not needed: everything in it that the pipeline
reads is already in git here.

```bash
cd /work/doutorado/artigos/RAG_evaluation/br-taxqa-r_v2.0
# 0. credentials: add OPENROUTER_API_KEY, MARITACA_API_KEY and HF_RELEASE_TOKEN to .env (copy from the other machine)
set -a; . ./.env; set +a
.venv/bin/pip install -U "huggingface_hub[cli]"          # if `hf` is missing
# 1. move the stale jua store and rankings aside (keep them until the download is verified)
mkdir -p ../stale_jua_20261008
mv embeddings/jua-4b-mixed/corpus/vectors.npy embeddings/jua-4b-mixed/corpus/texts.csv \
   embeddings/jua-4b-mixed/corpus/chunk_map.csv.gz ../stale_jua_20261008/
for s in S1 S2 S2c S3 S4; do mv runs/retrieval/jua-4b-mixed/irpf/$s/rankings.csv.gz ../stale_jua_20261008/rankings_$s.csv.gz; done
# 2. download (pinned to the staged commit, into a scratch folder first: downloaded files are untrusted data)
R=eduseiti/BR-TaxQA-R-RAG-eval; REV=af37fda92b62c05755ed61d1d7185f59f2aeef64; D=../hf_rag_eval_af37fda
HF_TOKEN=$HF_RELEASE_TOKEN hf download $R --repo-type dataset --revision $REV --local-dir $D \
  --include "SHA256SUMS" "embeddings/**" "runs/retrieval/**" "runs/contexts/**" \
            "raw/runs_answers_cache.tar.gz" "raw/nuggets_scoring_cache.tar.gz"
# 3. verify only what was downloaded, then copy into the checkout
(cd $D && grep -E '  (embeddings|runs/retrieval|runs/contexts|raw/(runs_answers|nuggets_scoring))' SHA256SUMS | sha256sum -c --quiet)
rsync -a --ignore-existing $D/embeddings/ embeddings/
rsync -a $D/runs/retrieval/ runs/retrieval/        # replaces the stale rankings; manifests are identical to git
rsync -a --ignore-existing $D/runs/contexts/ runs/contexts/
# 4. unpack the two caches (archives hold only cache JSON files; check the member list first)
tar -tzf $D/raw/runs_answers_cache.tar.gz | head; tar -xzf $D/raw/runs_answers_cache.tar.gz -C runs/answers/
tar -tzf $D/raw/nuggets_scoring_cache.tar.gz | head; tar -xzf $D/raw/nuggets_scoring_cache.tar.gz -C nuggets/scoring/
git status --short          # must stay clean: everything downloaded is gitignored
```

Check `raw/README.md` in the repo for the exact archive root before step 4. The release plan says each archive
restores its folder, but the member paths may start with `cache/`. Size: ≈ 1.1 GB vectors + ≈ 0.2 GB rankings and
evals + 57 MB contexts + the two cache archives. There are 38 GB free on `/work`.

**What each download is for:**

| Item | Needed for | Required? |
|---|---|---|
| `runs/retrieval/jua-4b-mixed/**` (rankings, evals) | side-by-side retrieval test against Gemini (§1.3) | **yes** |
| `runs/contexts/jua-4b-mixed/**` | the citation and linkage analyses (`nuggets.py analyze` reads contexts), and to compare contexts per question | **yes** |
| `embeddings/jua-4b-mixed/**` | only to rerun jua retrieval or try a hybrid; replaces the stale store | recommended (it avoids keeping a wrong store on disk) |
| `raw/runs_answers_cache.tar.gz` | reruns of the jua answers at no cost; not needed for the Gemini runs | optional |
| `raw/nuggets_scoring_cache.tar.gz` | free cache hits when an answer is identical to one already scored (likely for some Gemini answers on questions whose retrieved context did not change) | recommended (it saves a few dollars) |

**Check after the download:** rerun `rag.py retrieve --embedding jua-4b-mixed` and `rag.py evaluate` (≈ 30 s,
no cost). The rankings and `metrics.csv` must be byte-identical to the downloaded ones. This proves the local
pipeline reproduces the released jua run before Gemini is compared with it.

---

## 3. What has to be implemented first

1. **An embedding provider for gemini-embedding-2 in `scripts/embedding/`.** The `openai` and `gemini`
   providers of the embedding plan §5.3 were never implemented.
   - **Route A: OpenRouter, recommended.** OpenRouter's `/api/v1/embeddings` is OpenAI-compatible, so it can
     be either a small `openrouter` provider or the `tei` provider in `openai_compat` mode with a base URL and
     headers. It needs:
     - provider pinning in the request: `provider: {only: [google-ai-studio], allow_fallbacks: false,
       data_collection: deny}`;
     - the reported `usage` added up into the ledger.
   - **Route B: direct Google (`google-genai`, `GEMINI_API_KEY`)**, as designed in §5.3 of the embedding
     plan, optionally with the Batch API (`--gemini-batch`).
2. **The registry entry** (`models.yaml`, from embedding plan §5.2), with:
   - `dim: 3072` (native; no `output_dimensionality`);
   - `query_template: "task: search result | query: {text}"`;
   - `document_template: "title: none | text: {text}"` (decision D3, §8.2: **confirm `title: none` before
     the run**, since changing it later means re-embedding);
   - `price: {usd_per_million_tokens: 0.20, checked: 2026-11-08}`.

   **Check the prefixes against the current gemini-embedding-2 docs while implementing.** OpenRouter lists no
   `supported_parameters` for this model, so the task must go in the text and not in a `task_type` field.
3. **Cost ledger for API models** (embedding plan §9.2): tokens × price, with `source=provider_reported` when
   the response has `usage`.
4. **Length guard:**
   - The longest S2 text is 8,103 Qwen3 tokens. Gemini counts fewer tokens than Qwen3 on this corpus (sample
     of 2026-09-25: Gemini max 7,253 against Qwen3 8,119). With the ≈ 7-token prefix, every text fits in
     8,192.
   - The guard stays on the Qwen3 count plus a margin. Gemini `countTokens` is used only for texts above
     7,000 Qwen3 tokens.
   - Also confirm that the API does not truncate silently: send one over-long synthetic text and expect an
     error.
5. **API-model check** (plan §5.4): embed the parity sample twice. The norms must be 1 and the results
   deterministic to about 1e-6. Also check that the reported dimension is 3072.
6. **Full store (decided 2026-11-08).** Embed all 101,943 unique texts, the same store jua has.
   - `rag.py retrieve` and `evaluate` then run on all five strategies (S1, S2, S2c, S3, S4) without changes.
   - Only S1 and S2 4k go on to generation.
7. **Experiment file** `scripts/rag/experiments/gemini_core.yaml`:
   - `contexts: runs/contexts/gemini-emb-2/irpf`;
   - sets `[S1_budget4000, S2_budget4000]`;
   - llms `[gpt-5.6-luna, sabia-4]`;
   - prompt `answer_v1`.

   Answers go to `runs/answers/gemini-emb-2/irpf/answer_v1/<llm>/<set>/`. The embedding slug is in the path,
   so nothing of the jua runs is touched.
8. **Analysis.** `nuggets.py scoretable` / `analyze` must pair a Gemini run with the jua run of the same
   generator and set (paired bootstrap and permutation, as in phase 5 §3). Check whether `--runs` globs
   across embeddings already work; otherwise add the jua ↔ Gemini pairs to the comparison list.

Tests: extend `scripts/embedding/tests` with a mocked OpenRouter/Gemini response (usage, dimension, error on
an over-long input). No network.

---

## 4. Cost estimate

### 4.1 Embedding

| Text set | Unique texts | Tokens (Qwen3 count) | OpenRouter / Google standard ($0.20 / M) | Google Batch API ($0.10 / M) |
|---|---:|---:|---:|---:|
| **S1 ∪ S2** (= S2; S1 is a subset) | 72,960 | 16.46 M (+0.5 M prefix) | **≈ $3.4** | ≈ $1.7 |
| all strategies (S3 groupings, caput variants) | 101,943 | 27.88 M (+0.7 M) | ≈ $5.7 | ≈ $2.9 |
| 715 queries | 715 | < 0.1 M | < $0.02 | — |
| determinism check, smoke tests | — | — | < $0.10 | — |

- The Qwen3 counts are an upper bound: Gemini's tokenizer gave ≈ 10 % fewer tokens on the sample.
- The revoked RIR/1999 is embedded too, as with jua. Retrieval excludes it (`corpus_exclusions.yaml`), and
  the store stays comparable with jua's.
- **Prices checked on 2026-11-08:**
  - OpenRouter catalogue: `google/gemini-embedding-2`, $0.20 / M prompt tokens on `google-ai-studio`,
    `google-vertex/us` and `google-vertex/global` ($0.22 on `google-vertex/eu`), context 8,192.
  - Google's pricing page: text $0.20 standard, $0.10 Batch. The free tier is free of charge but
    rate-limited, and free-tier data may be used by Google.

**Route choice:**
- **OpenRouter (recommended):** one key and one ledger with the rest of the experiment. The cost difference
  from the Batch API is ≈ $1.7.
- **Google Batch API:** the cheapest, but asynchronous. It needs the direct provider and the billing-report
  import for the ledger (plan §9.2, §10).
- **Google free tier:** possible for $0, but the rate limits make 73k long texts slow. The cost would also no
  longer be reportable as a market price.

**Decided (2026-11-08):** OpenRouter, all texts: **≈ $5.7**.

### 4.2 Core grid (recommended): Luna + Sabiá-4 × S1 4k + S2 4k, 715 questions

> **Update 2026-11-08, after the user's decisions (§6).** All texts are embedded, so the embedding line is
> ≈ $5.7 instead of $3.4, and E3 is part of the core.
>
> | | Estimate | With 20 % contingency |
> |---|---:|---:|
> | **Core total** | ≈ $28.8 | ≈ $35 |
> | OpenRouter | ≈ $19.6 | ≈ $23.5 |
> | Maritaca | ≈ $9.2 | ≈ $11 |
>
> The table below keeps the original S2-only estimate.

The per-call costs are measured on the jua runs: `runs/costs.csv` and `nuggets/scoring/costs.csv`. Generation
per run is scaled from the 685 / 650 non-pilot calls of the full runs to 715. Context lengths are the same,
because the 4k budget is fixed.

| Step | Calls | Route | Estimate |
|---|---:|---|---:|
| Embedding S2 texts + queries (§4.1) | ≈ 1,000 requests | OpenRouter | $3.4 |
| Retrieval, retrieval test, contexts (`retrieve`, `evaluate`, `context`) | 0 | local | $0 |
| Generation Luna S1, S2 | 1,430 | OpenRouter (OpenAI flex) | ≈ $1.0 |
| Generation Sabiá-4 S1, S2 | 1,430 | Maritaca, direct | ≈ $9.2 (≈ R$ 47) |
| Scoring, 4 runs × 715 ($0.0023 / answer) | 2,860 | OpenRouter (Gemini 3.8 Flash flex) | ≈ $6.6 |
| Context support, Gemini S1 + S2 4k ($0.0044 / question) | 1,430 | OpenRouter | ≈ $6.3 |
| **Total** | | | **≈ $26.5** |
| of which OpenRouter | | | ≈ $17.3 |
| of which Maritaca | | | ≈ $9.2 |

With a 20 % contingency: **≈ $32 ($21 OpenRouter + $11 Maritaca)**. A `stratified_30` pilot first costs about
4 % of this (≈ $1.2) and can be skipped: the generation and scoring pipeline is unchanged and was validated
in the jua pilot.

### 4.3 Optional extensions (each independent)

| Extension | Adds | Estimate |
|---|---|---:|
| E1: Terra S1 + S2 4k | the strongest generator; tests whether a better context finally beats closed book | ≈ $13.3 OR (gen $10.0 + scoring $3.3) |
| E2: Sabiazinho-4 S1 + S2 4k | completes the four generators of the jua grid | ≈ $5.2 (Maritaca $1.9 + OR $3.3) |
| E3: embed the remaining texts (S3, S2c, S4) | the free retrieval test for all five strategies | ≈ $2.3 OR |
| E4: Luna S2c 4k (needs E3) | the best jua Luna score (0.314) | ≈ $2.1 OR |
| E5: cross-set scoring (Gemini 3.1 Pro and Qwen3.8-Max nugget sets), Sabiá-4 S1/S2 | nugget-creator robustness, as in phase 5 §7.3 | ≈ $6.3 OR |

Core + all extensions: ≈ $62 (≈ $45 OpenRouter, ≈ $17 Maritaca), before contingency.

### 4.4 Budget status and caps

- **OpenRouter key:**
  - On 2026-10-24 it had $5.22 left of its $150 spending limit. This is a limit on the key, not the
    account's prepaid credit. Reading the account credit needs a management key.
  - **The user raised the limit to $200 on 2026-11-08.** `GET /api/v1/key` at 17:15 gave usage $144.78
    and **$55.22 left**.
  - That covers the core grid (≈ $23.5 OpenRouter with contingency) and leaves ≈ $32 for extensions. E2 and
    E4 fit in it; E5 too, but not all three together with the contingency.
  - Check `GET /api/v1/key` before each paid step.
- Pass `--budget` on every run, as usual. The ledgers are cumulative (`runs/costs.csv`,
  `nuggets/scoring/costs.csv`, `embeddings/costs.csv`), so the caps are the current total plus the step's
  estimate × 1.2.
- Stop and report if any step goes above its estimate.

---

## 5. Order of execution (each step waits for the user's go-ahead)

1. **Set up** (no cost):
   - add the missing keys to `.env`;
   - download and verify the HF files (§2.2);
   - reproduce the jua retrieval and evaluation byte for byte.
2. **Implement** the provider, the registry entry, the ledger and the tests (§3). Confirm `title: none`
   (D3).
3. **Embed** all texts and the queries with gemini-embedding-2 (≈ $5.7).
   - `embed.py corpus --model gemini-emb-2 --dry-run` first: it gives the token count and the expected
     cost.
   - Then the determinism check, then the full run.
4. **Retrieve and evaluate** all five strategies ($0). Compare with jua (§1.3). **This is the gate: report
   and decide here.**
5. **Contexts** S1 / S2 4k (`rag.py context`, $0). Compare gold coverage per question with jua
   (`summary.csv`).
6. **Generate** the core grid (≈ $10.2).
7. **Score and run context support** (≈ $12.9). Then run `scoretable` and `analyze`, and pair each run with
   jua.
8. **Write the results note:**
   - Gemini vs jua per generator and set;
   - S1 → S2 under each embedding;
   - context support and linkage;
   - the decision on the extensions of §4.3.

## 6. Decisions (user, 2026-11-08)

1. **Route: OpenRouter.** Pin the provider to `google-ai-studio`, with no fallbacks and `data_collection:
   deny`.
2. **D3: `title: none`.** Every embedding model then gets exactly the same chunk string. Gemini's template
   adds only its fixed task prefix.
3. **Terra (E1) is not added for now.** The core grid stays Luna + Sabiá-4 × S1 / S2 4k.
4. **All texts are embedded (E3 is in the core),** so the retrieval stage can be checked fully on all five
   strategies.
5. **OpenRouter key limit: $200.** It has $55.22 left (§4.4).
