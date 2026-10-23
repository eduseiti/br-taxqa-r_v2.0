# RAG Phase 3 — generation of the trimmed grid on all 715 questions (stages 1 and 2)

**Generated:** 2026-10-23 15:19:28 (local time, from `date +%Y%m%d_%H%M%S`).
**Implements:** the generation part of stages 1 and 2 of the trimmed grid adopted by the user
(`docs/20261023_120734_first_full_evaluation_budget_trimmed_plan_and_s2_s3_hypotheses.md` §2–§3, D1/D2), after the
user's review of the pilot answers (`docs/20261023_110952_rag_phase3_generation_pilot.md`, Phase 3 gate).
**Cost:** **$41.95** billed (ledger `runs/costs.csv`, 14,387 new calls): OpenRouter **$16.38** (Terra $14.15, Luna
$2.23), Maritaca **$25.58 ≈ R$ 130** at list price (R$ 5.08/US$). Estimate from the pilot's cost per call: $47.9.
Ledger total since the start of RAG Phase 3: $47.54. OpenRouter key: **$65.18 left** of the $150 limit (2026-10-23
15:19).
**Status:** generation done; scoring (nugget phase 5) not started — stage 0 of the plan (scoring the pilot answers
to measure the real scoring cost) is next.

## 1. What was run

| Experiment file | Sets (all 715 questions) | Generators | Runs | New calls | Billed | Time |
|---|---|---|---:|---:|---:|---:|
| `scripts/rag/experiments/full_stage1.yaml` | S1 4k, S2 4k, closed book, oracle 4k | Sabiá-4, Sabiazinho-4, Terra, Luna | 16 | 10,329 | $30.39 | 86 min |
| `scripts/rag/experiments/full_stage2.yaml` | S3 4k, S2c 4k, S4 4k | Sabiá-4, Sabiazinho-4, Luna | 9 | 4,058 | $11.56 | 41 min |

```bash
set -a; . ./.env; set +a            # rag.py does not read .env itself
P=.venv/bin/python; R=scripts/rag/rag.py
$P $R run --experiment scripts/rag/experiments/full_stage1.yaml --dry-run
$P $R run --experiment scripts/rag/experiments/full_stage1.yaml --budget 43    # cap on the ledger total ($5.59 before)
$P $R run --experiment scripts/rag/experiments/full_stage2.yaml --budget 56    # ledger total $35.98 before
```

The runs grew the pilot folders (`runs/answers/jua-4b-mixed/irpf/<prompt>/<llm>/<set>/`): the 30 `stratified_30`
answers were reused from the cache. Stage 2 needed only 4,058 of 6,165 calls: S3 / S4 prompts identical to S2 /
S2c ones (e.g. 299 S3 contexts are identical to S2's, plan note §4.1) are cache hits, so their answers are the same
by construction. The controls (wrong context, `context_v1`) and the 2k / 8k / oracle 16k sets stay at pilot size.

Per run (billed USD):

| Set | Sabiá-4 | Sabiazinho-4 | Terra | Luna |
|---|---:|---:|---:|---:|
| S1 4k | 4.40 | 0.89 | 4.84 | 0.45 |
| S2 4k | 4.30 | 0.84 | 4.67 | 0.45 |
| S3 4k | 2.59 | 0.52 | — | 0.27 |
| S2c 4k | 3.83 | 0.76 | — | 0.40 |
| S4 4k | 2.46 | 0.49 | — | 0.26 |
| closed book | 1.15 | 0.24 | 1.51 | 0.11 |
| oracle 4k (596 questions) | 2.61 | 0.52 | 3.13 | 0.30 |

## 2. Proxies (from `summary.csv`; no answer scores yet)

| Set | Abstention: Sabiá-4 / Sabiazinho-4 / Terra / Luna | Claims grounded |
|---|---|---|
| S1 4k | 0.055 / 0.032 / 0.036 / 0.241 | 0.95 / 0.93 / 0.99 / 0.98 |
| S2 4k | 0.034 / 0.027 / 0.035 / 0.168 | 0.94 / 0.95 / 0.99 / 0.98 |
| S3 4k | 0.042 / 0.022 / — / 0.175 | 0.95 / 0.95 / — / 0.98 |
| S2c 4k | 0.038 / 0.022 / — / 0.182 | 0.95 / 0.94 / — / 0.98 |
| S4 4k | 0.053 / 0.024 / — / 0.190 | 0.95 / 0.94 / — / 0.98 |
| closed book | 0.013 / 0 / 0 / 0.003 | — |
| oracle 4k | 0.121 / 0.057 / 0.047 / 0.128 | 0.95 / 0.93 / 1.00 / 0.98 |

- Luna abstains most on every set (as in the pilot); S1 → S2 lowers abstention for Luna (0.24 → 0.17) and Sabiá-4.
- The oracle abstention is higher than the retrieval sets' for the Maritaca models and Luna: the negative-inference
  questions of the pilot note §6.9 (gold in the context, answer to be inferred) at full scale.
- All 14,387 ledger rows `stop`: no tool use, no billed cost above the token cost, served provider OpenAI on every
  GPT call.

## 3. Errors: 6 truncated replies (Maritaca)

6 of 16,669 answers are `status: error`, all `max_tokens_reached` (output reached 4,000 tokens; Maritaca rejects the
truncated strict-schema reply with HTTP 400 and returns no text, so the cause — a long answer or a repetition loop —
cannot be seen; two of them broke off before `afirmacoes` was closed):

| Generator | Set | Question |
|---|---|---|
| Sabiazinho-4 | S2 4k | Q659 |
| Sabiazinho-4 | closed book | Q468, Q672 |
| Sabiazinho-4 | S2c 4k | Q137 |
| Sabiá-4 | S2c 4k | Q346, Q659 |

Not billed (no ledger row). Scoring counts them as empty answers (pilot note §6.6). Q659 fails twice: worth a look.
Option, if the user wants them answered: a new registry version with `max_tokens` 8,000 for Maritaca and a rerun of
the failed questions only (the run folder's configuration guard requires `--force` or a new generator name).

## 4. Next

1. Stage 0: nugget phase 5 `score` on the pilot answers (implementation still to be done), then scoring of these
   25 runs (≈ $25–38 primary set, plan note §3.1), context support on S1 / S2 / oracle 4k, cross-set scoring of S1 vs
   S2 on 2 generators.
2. Stages 3–4 of the plan note (budget sweep or the 16k point of §4.4; DeepSeek V4 from the other machine).
