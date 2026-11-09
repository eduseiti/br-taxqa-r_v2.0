# Hugging Face update: the gemini-embedding-2 comparison added to the evaluation repo

**Generated:** 2026-11-08 23:19:04 (local time, from `date +%Y%m%d_%H%M%S`).
**Follows:**
- `20261024_180016_hugging_face_release_plan.md`: its rule for later updates (§5.4) and the first staging (§9);
- `20261108_175117_gemini_embedding_2_setup_embedding_and_retrieval_gate.md`: the outputs released here.

**Result:**
- Repo B (`eduseiti/BR-TaxQA-R-RAG-eval`, still private) has a new commit with every Gemini output, built and
  checked by the release tooling.
- Repo A (`eduseiti/BR-TaxQA-R`) needed no change.

**Cost:** $0. No LLM or embedding calls were made.

## 1. What changed where, and why

The plan's update rule (§5.4):
- new evaluation outputs go to **B** as new commits, under new paths;
- **A** changes only if the benchmark changes;
- no history is rewritten.

| Repo | Before | After | Change |
|---|---|---|---|
| A `eduseiti/BR-TaxQA-R` | `2b10e0f` | `2b10e0f` (unchanged) | None needed. A rebuild from this checkout matches the Hub file for file (`push_release.py --dry-run`: 0 new, 0 changed, 0 only on the remote). The Gemini work used the same questions, chunks and nuggets. |
| B `eduseiti/BR-TaxQA-R-RAG-eval` | `af37fda` | **`0a69ef9`** (`0a69ef96537c06149a2e8ccb76d7588d1ce90ca7`), recorded in `release/hf_release.json` | 81 new files, 19 changed, 0 deleted. 973 files, 3.0 GB, of which the Gemini corpus vectors are 1.25 GB. |

**New in B, all under the `gemini-emb-2` paths that mirror the git repo:**

| Path | Content |
|---|---|
| `embeddings/gemini-emb-2/` | `corpus/` (`vectors.npy` 101,943 × 3,072, `texts.csv`, `chunk_map.csv.gz`, `manifest.json`), `queries/irpf/`, `check.json`, `parity.json` (the determinism check) |
| `runs/retrieval/gemini-emb-2/irpf/` | rankings of the five strategies; the four evaluations, with the same parameters as jua's |
| `runs/contexts/gemini-emb-2/irpf/` | `S1_budget4000`, `S2_budget4000`, `summary.csv` |
| `runs/answers/gemini-emb-2/irpf/answer_v1/{sabia-4,gpt-5.6-luna}/{S1,S2}_budget4000/` | the 4 core-grid runs × 715 answers |
| `nuggets/scoring/score/…/gemini-emb-2/…`, `nuggets/scoring/ctxsupport/…/gemini-emb-2/…` | the judge's labels on the 4 runs and on the 2 context sets |
| `docs/` | the Gemini plan and results notes |

**Changed in B. Every change only adds rows; nothing published was altered (checks in §3):**
- ledgers: `embeddings/costs.csv`, `runs/costs.csv`, `nuggets/scoring/costs.csv`;
- the scoring tables in `nuggets/scoring/tables/gold-v0-auto/gemini-3.8-flash/all/`, where Gemini runs are named
  `<context_id>@gemini-emb-2`;
- the six Parquet viewer tables;
- the two cache archives that grew:
  - `raw/runs_answers_cache.tar.gz`: 15,874 → 18,600 requests;
  - `raw/nuggets_scoring_cache.tar.gz`: 22,688 → 26,420 requests;
- the card `README.md`, and `SHA256SUMS` / `release_manifest.json`.

## 2. Viewer configs (row counts after the update)

| Config | Before | After | Note |
|---|---:|---:|---|
| `run_metrics` | 56 | 60 | + 4 Gemini runs |
| `answers` | 18,805 | 21,665 | + 4 × 715. It already had an `embedding` column. |
| `nugget_labels` | 82,186 | 94,886 | |
| `per_question_scores` | 18,309 | 21,169 | |
| `comparisons` | 336 | 378 | + the jua ↔ Gemini and Gemini S1 → S2 pairs |
| `retrieval_metrics` | 11,255 | 22,510 | **New `embedding` column (first)**: the two embeddings' main evaluations are stacked, 11,255 rows each. |

`retrieval_metrics` is the only schema change. Adding a column keeps one config per kind of table, the same
choice as `answers` and `nugget_labels`. A split per embedding was the alternative, but split names cannot hold `-`.

## 3. How it was built and checked

```bash
uv pip install -r scripts/release/requirements.txt     # pyarrow was missing on this computer (pip into .venv)
# the six unchanged cache archives are not on this computer (nuggets/full/cache is empty): downloaded from af37fda,
# SHA-256 checked against the Hub's LFS hashes, into ../br-taxqa-r_hf_release/BR-TaxQA-R-RAG-eval/raw/
.venv/bin/python scripts/release/build_release.py --repos b --keep-raw      # repacks only the two grown caches
.venv/bin/python scripts/release/build_release.py --repos a                 # then push_release --dry-run: in sync
.venv/bin/python scripts/release/push_release.py --tree ../br-taxqa-r_hf_release/BR-TaxQA-R-RAG-eval \
    --repo-id eduseiti/BR-TaxQA-R-RAG-eval --message "Add the gemini-embedding-2 comparison: …"
```

**Checks against the published revision `af37fda` (done before the upload):**
- **Ledgers:** each old ledger is a byte prefix of the new one (embedding 10 → 14 lines, generation
  15,877 → 18,603, scoring 22,714 → 26,446).
- **Scoring tables:** every old row is still present. The one exception is described under "Known differences"
  below.
- **Parquet tables:**
  - `answers` starts with the old rows, equal in Arrow;
  - `nugget_labels` and `comparisons` start with the old rows, equal value for value;
  - `run_metrics` and `per_question_scores` contain every old row;
  - the jua part of `retrieval_metrics` equals the old table;
  - all Arrow schemas are unchanged, except the new `embedding` column.
- **Cache archives:** all 15,874 and 22,688 old members are present with the same SHA-256.
- **Build checks** (secrets, local paths, row counts) pass.

**Known differences from the published state:**
- **`ctxsupport_runs.csv`, row `oracle_budget16000`:** n 25 → 57 (V_strict 0.576 → 0.460).
  - The published table was built before the §10 audit of the phase 5 note was tabulated. That audit scored
    `oracle_budget16000` on the 57 questions of `stratified_70`, and the table now uses all of them.
  - The row `wrong-S2_budget4000` (70 questions) is new for the same reason.
  - The labels behind both rows were already published.
- **Gemini contexts and answers have `rendered_tokens_qwen3` = null.**
  - This is the optional Qwen3 count of the rendered context. `rag.py context` skips it, with only a warning,
    when the tokenizer is not in the local HF cache, which was the case on this computer.
  - `context_tokens_qwen3`, the count the budget uses, is filled, and the answers are not affected.
  - The card says so. In the Parquet table the column stays `int64`, with nulls for Gemini.
  - Rebuilding the contexts with the tokenizer and replaying the generation from the cache would fill it at no
    cost. It was not done, because it would rewrite run outputs after scoring.

**After the upload:**
- `push_release.py` compared the Hub with the tree again: "in sync" at `0a69ef9`. Every file is present, and LFS
  files match by SHA-256.
- The repo is still private.
- **Wrong label in the commit message:** the Hub commit message says "git 83b3f55". The tree was built from
  `4f85083` plus the uncommitted release-tooling changes of §4, as `release_manifest.json` and
  `release/hf_release.json` record. Hub history was not rewritten for this (§5.4).

## 4. Changes to the release tooling (uncommitted)

**`scripts/release/build_release.py`:**
- The answers and labels tables read every embedding folder, jua first, so the old rows keep their order.
- A `flat` entry can stack several CSVs with a key column (`csvs:` + `key:`).
- `rendered_tokens_qwen3` is kept as a nullable integer.
- `pack` keeps an existing archive *before* checking that its cache folder exists. So a computer without a cache
  can reuse the published archive.
- **`OTHER_REPO_ROOTS`:** the tracked jua embedding manifests hold the other computer's checkout path
  (`/work/unicamp/articles/…`). The build there rewrote it automatically, as its own repo path. It is now
  rewritten on any computer, so the copies are identical to the published ones.

**`scripts/release/repo_b.yaml`:**
- adds the Gemini embedding, answer and doc paths;
- the stacked `retrieval_metrics`;
- the new counts;
- excludes the per-question tables of two old jua evaluations (`either_containment_skip` of 2026-09-27 and
  `v2c_…` of 2026-10-08). They are gitignored leftovers on this computer, made from older chunk files, and were
  not in the release. Their `metrics.csv` and `report.md` are released, as before.

**`scripts/release/cards/repo_b.md`:**
- the second embedding in "The experiment";
- a Gemini results table;
- the `@gemini-emb-2` naming;
- the new row counts and archive sizes;
- the Gemini cost ($26.91);
- the limitations line.

## 5. Not done

- **No tag.** The plan tags a paper version (§5.4), and none is fixed yet.
- **Viewer check:** the viewer still cannot run on the private repo (non-PRO account).
- **`datasets.load_dataset` check:** not repeated in a clean venv. The Parquet files were read back with pyarrow
  and compared with the published ones instead.
- **Not uploaded:** the overview report `20261108_224913_results_overview_segmentation_and_embedding.md` and its
  figures. The user has not reviewed them yet.
- **Unchanged next steps** of the plan (publication under `unicamp-dl`, checks C5–C7): they still wait for the
  user.
