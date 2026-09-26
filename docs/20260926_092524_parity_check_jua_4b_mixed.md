# Parity check: `jua-4b-mixed` (TEI endpoint vs sentence-transformers reference)

**Date:** 2026-09-26 (run finished 03:14 UTC)
**Plan reference:** `docs/20260925_122058_embedding_implementation_plan.md` §5.4 (method), §3.8 (fallbacks)
**Result file:** `embeddings/jua-4b-mixed/parity.json` (versioned)
**Verdict:** **PASSED** on all three thresholds (D7). The endpoint can be used for the corpus run.

## 1. What was compared

| Side | Setup |
|---|---|
| **Served** | HF Inference Endpoint `jua-4b-mixed-bgc` (L4, custom container `ghcr.io/huggingface/text-embeddings-inference:89-1.9.4`), repository `ufca-llms/jua-4B-mixed` @ `57f491c1718171c0ad71d723c4f6b2030684c4eb`, TEI dtype **float16**, pooling `last_token`, `AUTO_TRUNCATE=false` |
| **Reference** | sentence-transformers 6.1.0, transformers 5.17.0, torch 2.11.0+cpu, same model and revision loaded in **bfloat16** on CPU (i7-12700F, no native bf16), pooled output cast to float32 and L2-normalized |

- **Sample:** `scripts/embedding/parity_sample.json`: 64 corpus texts (the 5 longest, 8,061–8,119
  Qwen3 tokens, and 59 spread over the 16 `Tipo`s by length) plus 16 queries (001, 045, …, 671).
- **Query prompt:** instruction `irpf` (the default, D1) with jua's template
  `Instruct: {instruction}\nQuery: {text}`. Documents are sent as they are.
- Both sides receive exactly the same strings, with the templates already applied.

## 2. Results

| Metric | Value | Threshold |
|---|---|---|
| Cosine served↔reference, median (80 items) | **0.99979** | ≥ 0.999 |
| Cosine, minimum | **0.99919** | ≥ 0.995 |
| Cosine, p1 | 0.99928 | — |
| Cosine, min over the 64 texts / 16 queries | 0.99919 / 0.99976 | — |
| Top-1 agreement (16 queries × 64 texts) | **16/16** | all |
| Kendall τ of the full ranking, min / median | 0.978 / 0.990 | reported only |

- **Where the gap is:** the lowest cosines are on the long chunks. Three of the five ~8k-token texts
  are among the four lowest (`ada0911a5dca724f` 0.99919, `4d415d8efbaac288` 0.99930,
  `be45a84194816150` 0.99948). This fits fp16 (server) vs bf16 (reference) rounding building up
  over long sequences. Queries, which are short, all score ≥ 0.99976.
- **Ranking changes:** Kendall τ < 1 comes from swaps between texts with nearly equal scores. The
  top-1 text is the same for every query.
- **Conclusion:** fp16 serving in TEI reproduces the published bf16 checkpoint closely, so neither
  `DTYPE=float32` nor the vLLM fallback (§3.8) is needed for this model.

## 3. Execution notes

- **Environment:** a fresh machine; a Python 3.12 `.venv` was created with conda and filled from
  `requirements-parity.txt`, with the CPU-only torch wheel. The 26 tests passed before the run.
- **Commands:**
  ```bash
  .venv/bin/python scripts/embedding/embed.py parity --model jua-4b-mixed --reference-only   # local CPU
  .venv/bin/python scripts/embedding/embed.py parity --model jua-4b-mixed --resume --pause-after
  ```
- **Reference time:** 2 h 11 min on CPU for 80 texts. Nearly all of it went to the 5 long texts,
  at about 12 min each; sentence-transformers encodes the longest first. The vectors are cached in
  `embeddings/jua-4b-mixed/parity_reference.npz` plus a `.json`. They are **not versioned**; keep
  them to avoid recomputing.
- **Served side:** the endpoint was resumed (running in 45 s), the 80 embeddings took about 25 s,
  and the endpoint was then paused. It was metered at **2 replica-minutes ≈ $0.03** in
  `embeddings/costs.csv` (run `20260926T031250-04e63b`). The CPU reference has no cost row.
- **Gate:** `parity.json` stores the server fingerprint (repository, revision, image, TEI version,
  dtype, pooling). `embed.py corpus` will accept this endpoint without `--skip-parity` as long as
  that fingerprint does not change.
- **Earlier query run:** the queries (`embeddings/jua-4b-mixed/queries/irpf/`, 2026-09-25) were
  embedded with `--skip-parity` before this check, and their manifest records the gate as skipped.
  They came from the same server configuration that now passes; re-run `queries` (≈ $0.05) if the
  manifest should show a pass.
