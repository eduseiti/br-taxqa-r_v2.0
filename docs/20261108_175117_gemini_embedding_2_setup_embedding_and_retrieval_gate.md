# gemini-embedding-2: setup, corpus embedding and the retrieval gate

**Generated:** 2026-11-08 17:51:17 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** steps 1–5 of `20261108_153258_gemini_embedding_2_comparison_plan.md` §5. The user's decisions of
2026-11-08 (plan §6) were: OpenRouter route, `title: none`, no Terra, all texts embedded.
**Cost:** **$26.91** in total for steps 1–8 (§7.3). Embedding alone is **$5.08** billed (`embeddings/costs.csv`):

| Step | Cost |
|---|---:|
| smoke check | $0.00001 |
| determinism check | $0.035 |
| queries | $0.005 |
| corpus | $5.036 |

- Plan estimate: ≤ $5.72.
- OpenRouter key after this step: usage $149.86 of the $200 limit, **$50.14 left**.

**Status:**
- Stopped at the gate (plan §1.3, step 4).
- **User decision (2026-11-08): B, then A.**
- B (context support) is done: §6.
- A (generation and scoring of the core grid) is done: §7.

## 1. Step 1: Hugging Face download and the jua reproduction

- **Source:** private repo `eduseiti/BR-TaxQA-R-RAG-eval`, pinned to commit `af37fda`.
- **Downloaded:** `embeddings/**`, `runs/retrieval/**`, `runs/contexts/**`, and the caches
  `raw/runs_answers_cache.tar.gz` and `raw/nuggets_scoring_cache.tar.gz`.
- **Staging folder:** `../hf_rag_eval_af37fda/`.
- **Checksums:** all 115 files pass `sha256sum -c` against the repo's `SHA256SUMS`.
- **What was copied into the checkout:**
  - only the 51 files that git does not track;
  - the 60 tracked files are identical to the download;
  - the 2 embedding manifests that differ only by the release's path rewrites were left as they are in git.
- **Stale files moved aside to `../stale_jua_20261008/`:** the 2026-10-08 jua store (115,582 rows) and its
  rankings.
- **Vectors:** the restored `vectors.npy` / `texts.csv` / `chunk_map.csv.gz` match the SHA-256 in the git
  manifest.
- **Caches:**
  - both archives held only `<cache dir>/<sha256>.json` regular files;
  - unpacked: `runs/answers/cache/` 15,874 files, `nuggets/scoring/cache/` 22,688 files.
- **Reproduction:** `rag.py retrieve --embedding jua-4b-mixed --run-name irpf_repro` followed by `evaluate`
  gives:
  - rankings (5 strategies) byte-identical to the release;
  - `metrics.csv`, `comparisons.csv`, `reachability.csv` and the per-question / per-item / per-chapter tables
    byte-identical too.

  The scratch run was then deleted.
- **CLI quirk:** `hf download … --include a b c` treated part of the list as file names and skipped
  `SHA256SUMS`. Fetch it separately, as was done here.

## 2. Step 2: the OpenRouter embedding provider

**New files:**
- `scripts/embedding/embedding/providers/openrouter.py`: `POST /api/v1/embeddings`. It provides:
  - the `provider` routing block from `models.yaml`;
  - a check of the served provider on every reply;
  - `usage.prompt_tokens` and `usage.cost` added up for the ledger;
  - retries on 408/429/5xx and on 200-with-error replies;
  - an optional per-run budget (`BudgetExceeded`).
- `tests/test_openrouter.py`: 7 tests with a mocked HTTP session. All 35 embedding tests pass.

**Changes to existing files:**
- `config.py`: new fields `api_key_env`, `routing`, `served_provider`.
- `runner.pack`: `solo_above` sends texts above 6,000 guard tokens alone. The provider then checks each one's
  reported token count against 8,192.
- `costs.py`: `api_row` (`provider_reported` rows, `billing_unit=tokens`) and `ledger_total`.
- `embed.py`:
  - the API usage of `check`, `parity`, `corpus` and `queries` goes to the ledger;
  - `--budget` is **required** for token-priced models. It is a cap on the `embeddings/costs.csv` total; the
    run refuses to start if the ledger plus the estimate is over it;
  - token-priced dry runs;
  - `parity` for API models is a **determinism check**: the sample is embedded twice and compared, and
    `parity.json` is written with the server fingerprint, so the parity gate works unchanged.
- `models.yaml`: entry `gemini-emb-2`:
  - model `google/gemini-embedding-2`, pinned to `google-ai-studio`, no fallbacks, `data_collection: deny`;
  - 3,072 dimensions;
  - templates `task: search result | query: {text}` and `title: none | text: {text}`, as on Google's
    embeddings page, checked on 2026-11-08: gemini-embedding-2 takes no `task_type`;
  - price $0.20 / M tokens;
  - batches of ≤ 50 inputs / 20,000 tokens, 8 concurrent.

**Facts measured on 2026-11-08:**
- **The API truncates over-long inputs silently.** A 17,386-token input was accepted (200) and billed. Google's
  page says the same.
- **Gemini counts fewer tokens than Qwen3.** On the 40 longest texts (with the prefix), Gemini `countTokens`
  is 0.83–0.91 × the Qwen3 count, max 7,259. So the Qwen3 guard (max 8,110 with the prefix, limit 8,192) is a
  safe upper bound.
- Over the whole corpus the provider billed 25.18 M tokens, against 28.59 M by the Qwen3 count (0.88 ×).
- **The output is deterministic.** Two runs of the parity sample are bit-identical (max |diff| 0), unit-norm,
  3,072 dimensions, and give the same top-1 for 16/16 queries.

**New parity sample: `scripts/embedding/parity_sample_20261108.json`.**
- Reason: the 2026-09-25 sample (`parity_sample.json`) names texts that the 2026-10-09 re-segmentation
  changed.
- The new one was built with the same rule (`embed.py parity --make-sample --sample …`).
- The jua file was left untouched, since it is jua's provenance.

## 3. Step 3: embedding (`embeddings/gemini-emb-2/`)

```bash
E=scripts/embedding/embed.py; P=.venv/bin/python
$P $E check  --model gemini-emb-2
$P $E parity --model gemini-emb-2 --sample scripts/embedding/parity_sample_20261108.json --budget 0.2
$P $E corpus --model gemini-emb-2 --budget 9.77 --no-progress     # ledger $2.90 + 1.2 × $5.72
$P $E queries --model gemini-emb-2 --budget 9.9 --no-progress
```

| Store | Shape | Provider tokens | Billed | Requests | Retries / errors | Wall |
|---|---|---:|---:|---:|---|---:|
| corpus | 101,943 × 3,072 | 25,179,092 | $5.036 | 2,186 | 0 / 0 | 11.7 min |
| queries (`irpf`) | 715 × 3,072 | 25,318 | $0.005 | 15 | 0 / 0 | 5 s |

**Inputs:**
- Same corpus as jua: `chunks_all.csv.gz`, SHA `a6087b7f…`, all 101,943 unique texts.
- Same question file: SHA `097abfc4…`.
- The query folder is called `irpf` so that the paths match jua's. Gemini's template has no free instruction;
  the fixed task prefix replaces it.

## 4. Step 4: retrieval and the legal-provision test

```bash
R=scripts/rag/rag.py; G=runs/retrieval/gemini-emb-2/irpf
$P $R retrieve --embedding gemini-emb-2
$P $R evaluate --retrieval $G                                                  # either_containment_merge_skip (main)
$P $R evaluate --retrieval $G --dedup containment --strategies S1,S2,S3 --comparisons S1:S2,S2:S3 --eval-id either_containment_skip
$P $R evaluate --retrieval $G --dedup containment --comparisons S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c --eval-id v2c_either_containment_skip
$P $R evaluate --retrieval $G --dedup containment --eval-id v2d_either_containment_skip
```

- The parameters of all four evaluations are identical to jua's (checked in their manifests).
- Corpus exclusions: the same (RIR/1999).

### 4.1 Main evaluation, recall within the token budget (what the generator gets; gold = all)

| Strategy | Article 2k jua / gem | **Article 4k jua / gem** | Article 8k jua / gem | Provision 4k jua / gem | Document 4k jua / gem |
|---|---|---|---|---|---|
| S1 | 0.296 / 0.318 | **0.398 / 0.413** | 0.492 / 0.515 | 0.369 / 0.380 | 0.621 / 0.598 |
| S2 | 0.425 / 0.451 | **0.503 / 0.515** | 0.600 / 0.597 | 0.420 / 0.435 | 0.700 / 0.682 |
| S2c | 0.391 / 0.451 | 0.480 / 0.511 | 0.579 / 0.592 | 0.417 / 0.438 | 0.686 / 0.664 |
| S3 | 0.424 / 0.451 | 0.507 / 0.517 | 0.606 / 0.609 | 0.429 / 0.454 | 0.691 / 0.671 |
| S4 | 0.397 / 0.453 | 0.487 / 0.517 | 0.593 / 0.607 | 0.427 / 0.454 | 0.680 / 0.660 |

### 4.2 Ranking quality (unit view: the first k distinct articles, no token budget)

| Strategy | MRR jua / gem | nDCG@10 jua / gem | recall@1 jua / gem | recall@10 jua / gem | recall@20 jua / gem |
|---|---|---|---|---|---|
| S1 | 0.524 / **0.614** | 0.441 / **0.525** | 0.186 / 0.252 | 0.529 / **0.610** | 0.622 / 0.676 |
| S2 | 0.555 / **0.638** | 0.478 / **0.546** | 0.206 / 0.254 | 0.581 / **0.630** | 0.661 / 0.702 |
| S2c | 0.545 / 0.642 | 0.473 / 0.548 | 0.192 / 0.259 | 0.577 / 0.625 | 0.658 / 0.696 |
| S3 | 0.552 / 0.630 | 0.474 / 0.537 | 0.206 / 0.249 | 0.574 / 0.618 | 0.648 / 0.685 |
| S4 | 0.543 / 0.634 | 0.464 / 0.537 | 0.190 / 0.254 | 0.559 / 0.608 | 0.633 / 0.680 |

### 4.3 Paired tests, Gemini − jua

Per question, article level, gold = all. 5,000 bootstrap resamples (95 % CI) and a sign-flip permutation test.

| Metric | Strategy | Diff | 95 % CI | p | Questions better / worse |
|---|---|---:|---|---:|---|
| article recall, 4k budget | S1 | +0.015 | (−0.011, +0.041) | .27 | 101 / 86 |
| | S2 | +0.012 | (−0.014, +0.037) | .37 | 100 / 82 |
| | S2c | **+0.031** | (+0.006, +0.054) | .017 | 102 / 69 |
| | S3 | +0.009 | (−0.014, +0.034) | .45 | 97 / 82 |
| | S4 | **+0.030** | (+0.006, +0.054) | .014 | 109 / 75 |
| provision recall, 4k | S1 / S2 | +0.011 / +0.016 | n.s. | .42 / .22 | |
| document recall, 4k | S1 / S2 | −0.024 / −0.018 | (−0.050, +0.001) / (−0.040, +0.002) | .06 / .10 | |
| article recall@10, unit view | S1 | **+0.081** | (+0.059, +0.105) | < .001 | 132 / 41 |
| | S2 | **+0.049** | (+0.027, +0.070) | < .001 | 104 / 40 |

These tests are ad hoc, run for this note. `rag.py compare` works within one retrieval run, not across
embeddings.

### 4.4 Why the ranking gain mostly disappears within 4k tokens

*Corrected on 2026-11-08 after the user's question.* The first version blamed mainly the longer texts. A
per-article decomposition shows that is only part of the cause. Inputs: `per_item.csv.gz` of the main evaluation
and the 4k `contexts.jsonl.gz`, ad hoc script.

**1. Most of Gemini's rank gains do not cross the context boundary.**

A 4k context holds the first ≈ 10 texts of the ranking, plus a few short texts further down that fit in the
budget left (`overflow: skip`). Recall changes only when a gold article crosses that boundary.

| What Gemini does to the gold article (1,944 reachable gold articles, 553 questions) | S1 | S2 |
|---|---:|---:|
| ranks it higher, already in jua's 4k context (median text rank S1 5 → 2, S2 8 → 2) | 187 | 243 |
| ranks it higher, still outside Gemini's 4k context (median S1 206 → 66, S2 308 → 110) | 593 | 421 |
| ranks it higher and **brings it into** the 4k context | 140 | 155 |
| ranks it lower and **pushes it out** of the 4k context | 109 | 117 |
| in the 4k context: both / only Gemini / only jua / neither | 432 / 143 / 115 / 1,254 | 573 / 163 / 126 / 1,082 |

- Net: +28 (S1) and +37 (S2) gold articles, which is the +0.012–0.015 of §4.1.
- MRR and the unit-view recall@k reward the first two rows: moves inside the context and moves in the deep
  tail.
- The unit view counts *distinct articles*, so its top 10 reaches deeper than the ≈ 10 texts of a 4k context.
  At a fixed number of **texts** (raw view) the gain is smaller:

  | | raw@1 | raw@5 | raw@10 | raw@20 |
  |---|---:|---:|---:|---:|
  | S1 | +0.043 | +0.028 | +0.044 | +0.052 |
  | S2 | +0.034 | +0.046 | +0.038 | +0.031 |

  Unit@10 gives +0.081 / +0.049.

**2. Longer texts cost about half of what is left.**
- Gemini's top-ranked texts are longer: the mean length of the top 10 is 535 tokens against jua's 454 (S1),
  and 411 against 341 (S2). That is +18–21 %; the medians are 450 / 345 and 269 / 232.
- In S1, the unbroken block of top-ranked texts in the 4k context is 7.6 texts for Gemini and 9.4 for jua.
- Recall from that block alone:

  | | Recall |
  |---|---:|
  | jua | 0.389 |
  | Gemini | 0.400 |
  | Gemini with jua's block size | 0.423 |

- So the better ranking is worth ≈ +0.03 at an equal number of texts, and the shorter block costs ≈ −0.02.
- Of the 115 articles Gemini loses in S1, 18 fall between the two block sizes. The other 97 are ranked deeper
  than jua's whole block, so they are true ranking losses.
- **S2 cannot be split this way.** `containment_merge` drops or merges sub-units of articles already in the
  context, so the unbroken top block is only 2.5–3.2 texts there.

**3. Two things that 4k recall does not see, and that may still help the answers:**
- **Position:** where both contexts hold the gold article, Gemini puts it near the top (median text rank 2
  against 5–8). Recall ignores order.
- **Non-gold content:** the contexts share only 25–29 % of their texts (§4.5). Recall counts only the
  provisions the P&R cites. Context support (nuggets) measures the rest.

**Other results:**
- The caput variants S2c and S4 gain +0.03 at 4k (significant) and reach S2's level with Gemini.
- Document recall is slightly lower with Gemini (−0.02, p .06–.10).
- **S1 → S2 still holds with Gemini** at 4k: +0.10 article recall (jua +0.105).

### 4.5 Step 5: generator contexts (`runs/contexts/gemini-emb-2/irpf/`, $0)

`rag.py context --retrieval runs/retrieval/gemini-emb-2/irpf --sets S1@budget=4000,S2@budget=4000` builds the two
sets with the same parameters as jua's: `containment_merge`, `skip`, `score`, `context_v2`, annex rule
`either`.

| Set | Texts | Article recall | Document recall | Provision recall | Item Jaccard with jua's context (mean / median) | Contexts identical to jua's |
|---|---:|---:|---:|---:|---|---:|
| S1 4k | 9.4 (jua 11.2) | 0.413 (0.398) | 0.598 (0.621) | 0.380 (0.369) | 0.29 / 0.28 | 5 / 715 |
| S2 4k | 10.5 (jua 12.6) | 0.515 (0.503) | 0.682 (0.700) | 0.435 (0.420) | 0.25 / 0.23 | 2 / 715 |

**The contexts are mostly different texts, but the gold coverage is about the same.** Whether the new texts
hold more of the answers' content (nuggets) cannot be measured by gold-article recall. Context support
(plan §4.2, ≈ $6.3 for both sets) measures exactly that.

## 5. Gate: what was found and the options

**Result:**
- Gemini ranks the cited provisions clearly better than jua: MRR +0.08–0.10 and top-10 article recall +0.05 /
  +0.08, p < .001.
- Inside the 4k budget the advantage is small and not significant for S1 and S2 (+0.01–0.015).
- The S1 → S2 gain is the same under both embeddings.

**Options** (costs from plan §4.2; OpenRouter key: $50.14 left):

| Option | What it answers | Cost |
|---|---|---:|
| **A. Core grid as planned** (context support, then Luna + Sabiá-4 × S1 / S2 4k, scoring) | does S2 > S1 hold for the answers under a second embedding? Do Gemini's different contexts change answer quality? | ≈ $23 (≈ $13.6 OpenRouter + $9.2 Maritaca) |
| **B. Context support first** (S1 and S2 4k), then decide on generation | do Gemini's contexts hold more nugget content than jua's? | ≈ $6.3 OpenRouter, part of A |
| C. Stop here | the paper reports the retrieval comparison only | $0 |

**Recommendation: B, then A.**
- B is part of A anyway, so doing it first costs nothing extra.
- The contexts are mostly different texts, so their nugget support can differ even though gold-article recall
  does not.
- The S1 → S2 answer comparison under a second embedding is the robustness result the paper needs, whatever
  B shows.

## 6. B: context support of the Gemini contexts (2026-11-08)

```bash
C=runs/contexts/gemini-emb-2/irpf
$P scripts/nuggets/nuggets.py --out nuggets/scoring --sample all --workers 24 --budget 67.8 \
   ctxsupport --contexts $C/S1_budget4000 $C/S2_budget4000          # ledger $59.82 before
$P scripts/nuggets/nuggets.py --out nuggets/scoring --sample all scoretable
```

**Cost:**
- **$6.42** billed: 1,363 judge calls (Gemini 3.8 Flash, `google-ai-studio`), plus 67 cache hits, 0 failed.
- `nuggets/scoring/costs.csv` total: $66.24.

**Setup fixes:**
- **Missing input copy.** `nuggets/full/input/questions.jsonl` is gitignored and was not released. It was
  rewritten with the pipeline's own loader (`data.load_questions(dataset/questions.jsonl)`, the code of `sample`),
  without rerunning `sample`, which would rewrite the tracked `sample.json`.
- `dataset/questions.jsonl` matches the `dataset_sha256` in `sample.json`.

**Code change (no LLM): keys for the second embedding.**
- Before, `scoretable` and `analysis.nugget_labels` named a run or context set by the last path component, so
  `S2_budget4000` of both embeddings would collide.
- `scoring.context_key` keeps the bare id for `jua-4b-mixed` and gives other embeddings `S2_budget4000@gemini-emb-2`.
- `scoring.PAIRS` gains:
  - jua vs Gemini for S1 and for S2;
  - Gemini S1 → S2.
- **Check:** the regenerated `runs.csv`, `comparisons.csv` and `per_question.csv.gz` are identical to git. The
  jua rows of `ctxsupport_per_question.csv.gz` are identical too.
- The table also gains the jua `oracle_budget16000` (57 questions) and `wrong-S2` (70) context sets of the
  §10 audit of the phase 5 note. They had never been tabulated.

### 6.1 Result: Gemini's contexts hold more of the answers' content

Vital nuggets fully supported by the 4k context (Flash judge with `assign_ctx_v1`), 714 paired questions,
paired bootstrap / permutation / chapter-cluster CI:

| Context | jua | Gemini | Gemini − jua (95 % CI) | p | cluster CI |
|---|---:|---:|---|---:|---|
| S1 4k, V_strict | 0.397 | 0.439 | **+0.042** (0.024, 0.061) | < .001 | (0.026, 0.061) |
| S2 4k, V_strict | 0.411 | 0.458 | **+0.047** (0.029, 0.065) | < .001 | (0.028, 0.062) |
| S1 4k, V | 0.509 | 0.550 | +0.041 | < .001 | |
| S2 4k, V | 0.524 | 0.569 | +0.046 | < .001 | |
| contradicts at least one nugget, S1 / S2 | 0.025 / 0.027 | 0.025 / 0.022 | 0.000 / −0.004 | 1.0 / .65 | |

| S1 → S2 within an embedding (V_strict) | Diff | 95 % CI | p |
|---|---:|---|---:|
| jua | +0.014 | (0.002, 0.026) | .027 |
| Gemini | +0.018 | (0.006, 0.031) | .005 |

**Reading:**
- Measured against the gold nuggets, the Gemini contexts are clearly better: about +0.045 V_strict. That is
  three times the S1 → S2 effect.
- Their recall of the provisions the P&R cites is about the same as jua's (§4.1).
- So the extra support comes from what §4.4 point 3 could not see: texts other than the cited articles that
  state the answer's facts, and the longer texts Gemini prefers.
- For reference, the oracle 4k context (the cited articles only) reaches 0.483. Gemini S2 4k (0.458) closes
  about two thirds of jua S2's gap to it (0.411 → 0.483: 0.047 of 0.072). This compares 596 oracle questions
  with 715; the comparison is indicative only.
- S2 still beats S1 under Gemini, by a margin like jua's.

## 7. A: generation and scoring of the core grid (2026-11-08)

```bash
$P scripts/rag/rag.py run --experiment scripts/rag/experiments/gemini_core.yaml --budget 63      # runs/costs.csv $47.54 before
$P scripts/nuggets/nuggets.py --out nuggets/scoring --sample all --workers 24 --budget 73.2 \
   score --runs "runs/answers/gemini-emb-2/irpf/*/*/*"                                         # ledger $66.24 before
$P scripts/nuggets/nuggets.py --out nuggets/scoring --sample all scoretable
```

**Generation:**
- 4 runs × 715 answers, 0 errors, 26 min.
- 2,726 new calls; 67 per generator were cache hits. For 67 questions Gemini's S1 and S2 contexts are
  identical (jua: 36), so the S2 request reused the S1 response.
- Billed **$9.98**: Sabiá-4 $9.04 (Maritaca, list price at R$ 5.08/US$), Luna $0.95.

**Scoring:**
- 2,369 new judge calls (the rest were abstentions, which are not judged, or cache hits), 0 failed.
- Billed **$5.43**.

**Tables:**
- The regenerated `tables/gold-v0-auto/gemini-3.8-flash/all/` add 4 rows to `runs.csv` and 42 to
  `comparisons.csv`.
- No jua row changed.

### 7.1 Answer scores (715 questions; jua rows from the phase 5 note)

| Generator | Context | V_strict | V | A_strict | W | contra. | abstained | chars |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Luna | closed book | 0.259 | 0.420 | 0.220 | 0.378 | 0.266 | 0.003 | 672 |
| Luna | S1 4k jua | 0.271 | 0.387 | 0.235 | 0.351 | 0.080 | 0.241 | 624 |
| Luna | **S1 4k Gemini** | **0.296** | 0.418 | 0.259 | 0.382 | 0.066 | 0.197 | 672 |
| Luna | S2 4k jua | 0.299 | 0.424 | 0.261 | 0.388 | 0.085 | 0.168 | 692 |
| Luna | **S2 4k Gemini** | **0.327** | 0.466 | 0.286 | 0.427 | 0.091 | 0.133 | 743 |
| Luna | oracle 4k (596) | 0.338 | 0.475 | 0.299 | 0.435 | 0.065 | 0.128 | 673 |
| Sabiá-4 | closed book | 0.239 | 0.379 | 0.213 | 0.350 | 0.382 | 0.013 | 1,016 |
| Sabiá-4 | S1 4k jua | 0.290 | 0.446 | 0.257 | 0.409 | 0.115 | 0.054 | 787 |
| Sabiá-4 | **S1 4k Gemini** | **0.320** | 0.478 | 0.283 | 0.439 | 0.112 | 0.050 | 822 |
| Sabiá-4 | S2 4k jua | 0.317 | 0.470 | 0.285 | 0.433 | 0.112 | 0.034 | 822 |
| Sabiá-4 | **S2 4k Gemini** | **0.328** | 0.491 | 0.287 | 0.449 | 0.105 | 0.042 | 828 |
| Sabiá-4 | oracle 4k (596) | 0.319 | 0.462 | 0.278 | 0.422 | 0.091 | 0.121 | 706 |

### 7.2 Paired comparisons (V_strict, b − a, 714 questions)

95 % paired-bootstrap CI, paired permutation p, chapter-cluster CI.

| Comparison | Luna | Sabiá-4 |
|---|---|---|
| **S1 jua → S1 Gemini** | **+0.025** (0.002, 0.048) p .030; cluster (0.003, 0.047) | **+0.029** (0.007, 0.052) p .011; cluster (0.007, 0.050) |
| **S2 jua → S2 Gemini** | **+0.027** (0.005, 0.050) p .018; cluster (0.003, 0.048) | +0.011 (−0.010, 0.034) p .31 |
| **S1 → S2, Gemini** | **+0.030** (0.008, 0.053) p .007; cluster (0.005, 0.052) | +0.009 (−0.011, 0.029) p .39 |
| S1 → S2, jua (phase 5 note) | **+0.028** (0.008, 0.049) p .007 | **+0.027** (0.007, 0.047) p .009 |
| contradictions, S1 → S2 Gemini | +0.025 p .018 | −0.007 p .62 |
| contradictions, jua → Gemini (S1 / S2) | −0.014 / +0.006, n.s. | −0.003 / −0.007, n.s. |

**Reading:**
- **The stronger embedding gives better answers.**
  - Three of the four jua → Gemini comparisons are significant: +0.025 to +0.029 V_strict, robust to
    chapter clustering. That is about the size of the S1 → S2 effect with jua.
  - Sabiá-4 on S2 gains less (+0.011, n.s.).
  - It follows the context support of §6: +0.042 (S1), +0.047 (S2).
  - Retrieval does not raise contradictions.
  - Luna abstains less (S1 24 % → 20 %, S2 17 % → 13 %).
- **Best scores so far:**
  - Luna: S2 Gemini 0.327, close to its oracle 4k (0.338, on 596 questions).
  - Sabiá-4: S2 Gemini 0.328, above its oracle 4k (0.319) and its jua S2 (0.317).
  - Terra's jua S2 4k (0.341) is still higher. Terra was not rerun (user decision).
- **S1 → S2 under Gemini: holds for Luna, not for Sabiá-4.**
  - Luna: +0.030, p .007, the same as with jua (+0.028).
  - Sabiá-4: +0.009, p .39, against +0.027 with jua. Sabiá-4's S1 score rises more with Gemini (+0.029) than
    its S2 score (+0.011), so the gap closes.
  - So the segmentation effect is **not** embedding-independent for every generator. With the stronger
    retriever, S1 contexts already carry much of what S2 added for Sabiá-4.
  - The context-level S1 → S2 gain is similar under both embeddings (+0.014 jua, +0.018 Gemini, §6.1). So the
    difference is in how Sabiá-4 uses the two Gemini contexts.
- Luna's contradiction share rises from S1 to S2 under Gemini (+0.025, p .018). It did not with jua (+0.005).
  This is worth a look before it is reported.

### 7.3 Costs of the Gemini comparison (2026-11-08)

| Step | Ledger | Billed |
|---|---|---:|
| embedding: smoke, determinism, queries, corpus | `embeddings/costs.csv` | $5.08 |
| context support, S1 / S2 4k | `nuggets/scoring/costs.csv` | $6.42 |
| generation, 4 runs | `runs/costs.csv` | $9.98 (Maritaca $9.04, OpenRouter $0.95) |
| scoring, 4 runs | `nuggets/scoring/costs.csv` | $5.43 |
| **Total** | | **$26.91** (OpenRouter $17.87, Maritaca $9.04) |

- Plan estimate (§4.2 update): ≈ $28.8.
- OpenRouter key: usage $162.66 of $200, **$37.34 left**.

### 7.4 Not done

- **`nuggets.py analyze`** (linkage, utilisation, citations, slices, perturbation) for the Gemini runs:
  - `analysis.py` reads jua's contexts and retrieval through fixed paths (`RETRIEVAL`, `contexts_root /
    context_id`), so the citation and linkage analyses would skip or misread the `@gemini-emb-2` runs;
  - it needs a small change first. The tracked outputs in `analysis/` were not regenerated.
- **Robustness checks of phase 5 §7:** cross-sets (Gemini 3.1 Pro and Qwen3.8-Max nugget sets, ≈ $3 for the 4
  runs) and the perturbation of the Sabiá-4 S1 → S2 result.
- Extensions E1 (Terra), E2 (Sabiazinho-4) and E4 (Luna S2c) of the plan.
