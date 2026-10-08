# Embedding pipeline

Embeds the BR-TaxQA-R v2.0 chunks (`segmented/chunks_all.csv.gz`) and questions with one configured
model at a time, and writes vectors plus full provenance. Design and decisions:
`docs/20260925_122058_embedding_implementation_plan.md` (referred to as "the plan").

**Status (2026-09-25):** implemented for the `tei` provider (HF Inference Endpoints running Text
Embeddings Inference) and a `fake` provider for tests. Configured and set up: `jua-4b-mixed`.
The `qwen3-emb-4b` and `inf-retriever-v1` entries are in `models.yaml` but have no endpoint yet;
the OpenAI and Gemini providers are not implemented yet.

## Output format

```
embeddings/<model>/
  corpus/vectors.npy        float32 [n_texts, dim], L2-normalized, rows in text_id order
  corpus/texts.csv          row, text_id (= texto_sha256), n_tokens (model tokenizer)
  corpus/chunk_map.csv.gz   chunk_id, text_id   (118,766 chunks -> 115,582 unique texts since 2026-10-08)
  corpus/manifest.json      provenance: model + revision, server /info, endpoint config, input and
                            output SHA-256, token stats, sessions, timings, parity result
  queries/<instruction>/vectors.npy, queries.csv (row, query_id, n_tokens, text_sent), manifest.json
  check.json, parity.json   smoke test and parity check results
  endpoint_meter.jsonl      endpoint status samples (cost metering)
embeddings/costs.csv        cost ledger (all models)
```

```python
import numpy as np, pandas as pd
V = np.load("embeddings/jua-4b-mixed/corpus/vectors.npy", mmap_mode="r")
texts = pd.read_csv("embeddings/jua-4b-mixed/corpus/texts.csv", dtype=str)
cmap  = pd.read_csv("embeddings/jua-4b-mixed/corpus/chunk_map.csv.gz", dtype=str)
Q = np.load("embeddings/jua-4b-mixed/queries/irpf/vectors.npy"); scores = Q @ V.T
```

Only the manifests, `check.json`, `parity.json`, `endpoint_meter.jsonl` and `costs.csv` are
versioned in git; vectors and sidecar CSVs are released on the HF Hub (plan §4.2).

## Install

Python 3.12, from the repository root (the venv is shared with `scripts/segmentation`):

```bash
pip --python .venv/bin/python install -r scripts/embedding/requirements.txt
pip --python .venv/bin/python install -r scripts/embedding/requirements-parity.txt   # parity reference only
```

## Credentials

Copy `scripts/embedding/.env.example` to `.env` at the repository root (gitignored) and fill in
`HF_TOKEN`. The token needs *Make calls to Inference Endpoints* and, for resume/pause and the cost
meter, *Manage Inference Endpoints*. When `endpoint_name` is set in `models.yaml`, the endpoint URL
is read from the endpoint API, so `ENDPOINT_URL_…` is optional.

## Running a model (jua-4b-mixed)

```bash
E="scripts/embedding/embed.py"
.venv/bin/python $E models                                   # registry + credentials
.venv/bin/python $E check  --model jua-4b-mixed --resume     # resumes the paused endpoint, smoke test
.venv/bin/python $E parity --model jua-4b-mixed --reference-only   # bf16 CPU reference, ~8 GB RAM, slow
.venv/bin/python $E parity --model jua-4b-mixed --resume     # served vs reference -> parity.json
.venv/bin/python $E corpus --model jua-4b-mixed --dry-run    # tokens and requests, sends nothing
.venv/bin/python $E corpus --model jua-4b-mixed --resume     # full run; pauses the endpoint at the end
.venv/bin/python $E queries --model jua-4b-mixed --resume --pause-after
.venv/bin/python $E costs summary --markdown
```

- **Parity gate:** `corpus` and `queries` refuse to run without a passing `parity.json` made
  against the same server (repo, revision, TEI image and version, dtype, pooling). `--skip-parity`
  overrides it and is recorded in the manifest.
- **Resumable:** every completed request is written to `<output>/_shards/`. After an interruption,
  run the same command again; only the missing texts are sent. A resume with a different
  configuration (template, instruction, input file, server) is refused unless `--overwrite`.
- **Embed by text hash (`corpus --extend`):** after a new segmentation run, reuse the finalized
  vectors of every text that is still in the input (texts are keyed by `texto_sha256`) and send only
  the new texts. Refused unless the store was made with the same model, revision, template,
  dimension and server configuration. Texts no longer in the input are dropped from the new store.
  The manifest's `extend` block records the previous manifest and input, and the reused, embedded
  and dropped counts. The 2026-10-08 rebuild sent 32,194 of 115,582 texts this way
  (`--extend --dry-run` shows the count first).
- **No truncation:** every text is counted with the model's own tokenizer and the run stops if one
  is over `max_input_tokens` (8,192); the server also has truncation off.
- **Endpoint:** a paused endpoint is resumed only with `--resume`. `corpus` pauses it when done
  (`--no-pause-after` to keep it); other commands leave it running, and it scales to zero after
  15 idle minutes. `embed.py endpoint --model … {status|resume|pause}` manages it directly.
- **Costs:** while a command runs, the endpoint status is polled every 60 s and the billed
  replica-minutes × the hourly price in `models.yaml` are appended to `embeddings/costs.csv`
  (plan §9.3). Use outside the script is not metered: add it with `embed.py costs add`.
- **Instruction ablation:** `queries --instruction-name web_search` writes to
  `queries/web_search/` without touching the corpus vectors.

## Adding a model

Add an entry to `models.yaml` (provider, model id and pinned revision, dimension, tokenizer spec,
templates, request limits, price). For a TEI endpoint, create it as in plan §3.3 and set
`endpoint_name`. No code changes.

## Tests

```bash
.venv/bin/python -m pytest -q scripts/embedding/tests      # fake provider: no network, no GPU
```

## Files

| File | Role |
|---|---|
| `embed.py` | CLI: `models`, `check`, `parity`, `corpus`, `queries`, `finalize`, `endpoint`, `costs` |
| `models.yaml` | model registry (templates, instructions, limits, prices, parity thresholds) |
| `parity_sample.json` | fixed parity sample: 64 text ids (5 longest + spread over `Tipo` × length) and 16 questions |
| `embedding/config.py` | registry loading, paths, template rendering |
| `embedding/corpus.py` | corpus de-duplication and chunk map, query loading |
| `embedding/tokens.py` | client-side tokenizers and the length guard |
| `embedding/providers/` | `tei` (with retries and the `openai_compat` mode) and `fake` |
| `embedding/runner.py` | request packing, concurrent requests, per-batch validation |
| `embedding/store.py` | shard store, `vectors.npy` assembly, deterministic CSV/gzip writers |
| `embedding/parity.py` | sample building, sentence-transformers reference, metrics |
| `embedding/endpoint.py` | endpoint access, resume/pause, replica meter |
| `embedding/costs.py` | cost ledger and summary |
| `embedding/manifest.py` | git state, checksums, JSON helpers |
