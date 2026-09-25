# Embedding Implementation Plan

**Generated:** 2026-09-25 12:20:58 (local time, from `date +%Y%m%d_%H%M%S`)
**Input:** `segmented/chunks_all.csv.gz`, produced by the segmentation pipeline
(`docs/20260924_123747_segmentation_implementation_plan.md`, results in
`docs/20260924_184339_segmentation_results.md`).
**Strategy background:** `docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` (referred
to below as **the strategy doc**). It requires **one embedding run per model over the S3 chunk set**;
S1 and S2 are filters on `Tipo`, so they need no extra embedding.
**Deliverables:** code in `scripts/embedding/`, outputs in `embeddings/`. The script is meant to be
**released with the research data**, so clarity, reproducibility and ease of use are requirements,
not extras (§6).

Status: **plan only; no code written yet.**

---

## 1. Decisions from the 2026-09-25 discussion

### 1.1 Models to compare

| Slug | Model | Provider / how it runs | Dim | Max input | License |
|---|---|---|---|---|---|
| `jua-4b-mixed` | `ufca-llms/jua-4B-mixed` @ `57f491c1718171c0ad71d723c4f6b2030684c4eb` | HF Inference Endpoint (TEI) | 2560 | 8192 (card) | MIT |
| `qwen3-emb-4b` | `Qwen/Qwen3-Embedding-4B` @ `5cf2132abc99cad020ac570b19d031efec650f2b` | HF Inference Endpoint (TEI) | 2560 | 32k (we cap at 8192) | Apache-2.0 |
| `inf-retriever-v1` | `infly/inf-retriever-v1` @ `6c5b3f3156c0a705e30608f8ef6375d965b0f18f` | HF Inference Endpoint (TEI) | 3584 | 32k (we cap at 8192) | Apache-2.0 |
| `openai-te3-large` | `text-embedding-3-large` | OpenAI API | 3072 | 8192 | paid API |
| `openai-te3-small` | `text-embedding-3-small` | OpenAI API | 1536 | 8192 | paid API |
| `gemini-emb-2` | `gemini-embedding-2` | Gemini API | 3072 | 8192 | paid API |

The commit SHAs are the Hub `main` revisions on 2026-09-25. **Pin them** on the endpoints and in the
config (§3.3, §5.2) so a later model update can't silently change the embeddings.

Model facts checked in the repos' own files on 2026-09-25:

- **jua-4B-mixed:** fine-tune of `Qwen/Qwen3-Embedding-4B`. The architecture is `Qwen3ForCausalLM`
  with 36 layers, hidden size 2560 and `dtype: bfloat16`. Weights are about 8 GB in two safetensors
  shards. The sentence-transformers modules are Transformer → last-token Pooling → Normalize, and
  `config_sentence_transformers.json` has the prompts `query` = the Qwen web-search instruction and
  `document` = `""`. The Hub repo has **no `text-embeddings-inference` tag**, unlike the other two.
  TEI should still load it because the architecture is identical to Qwen3-Embedding-4B, but this is
  checked at setup (§3.8).
  - Its card reports results on **BR-TaxQA-R (v1)** (NDCG@10 0.777) in the JUÁ evaluation
    environment. The listed training data (JUÁ-Juris, Ulysses legislative supervision, a synthetic
    legislative extension, SQuAD-pt) does not include BR-TaxQA-R. Cite this in the paper and state
    that no BR-TaxQA-R data was used for training (paper: arXiv:2605.04005).
- **Qwen3-Embedding-4B:** same architecture and modules as jua. TEI lists it as supported.
- **inf-retriever-v1:** built on `gte-Qwen2-7B-instruct`. The architecture is `Qwen2Model` with
  28 layers, hidden size 3584 and bf16 weights of about 15 GB. It uses last-token pooling +
  Normalize. The only prompt is `query` = the web-search instruction with a **trailing space**
  after `Query:`. Its transformers usage needs `trust_remote_code` (`modeling_qwen.py`) because
  **gte-Qwen2 models use bidirectional attention**. TEI lists gte-Qwen2 as supported. Its training
  data is mainly Chinese and English, so note it in the paper as a non-Portuguese baseline.
- **text-embedding-3-large / -small** (both are run; D2 decided 2026-09-25): 8192-token input limit using the `cl100k_base` tokenizer. The output
  is L2-normalized. Price is about **$0.13 per 1M tokens** (derived from OpenAI's "9,615 pages per
  dollar" at 800 tokens/page), so ≈ $3.5 for the corpus. `-small` costs about $0.02 per 1M tokens
  (≈ $0.5 for the corpus).
- **gemini-embedding-2:** 8192-token input limit and 3072 dimensions by default. Embeddings are
  normalized automatically, including at reduced dimensions. Task selection uses **text prefixes**:
  queries are `task: search result | query: {content}` and documents are
  `title: {title} | text: {content}` (§4.3). The Batch API costs 50 % of the normal price.

### 1.2 Why the local GPU is not used

- **Hardware:** the local GPU is an RTX 4050 Laptop with 6 GB of memory, in WSL2 with 15 GB of RAM.
  The 4B models need about 8 GB for their BF16 weights alone.
- **Quantization would fit, but it changes the embeddings.** Options include 8-bit bitsandbytes,
  4-bit NF4, or GGUF Q8_0 with `llama-server --embedding`. The embeddings would then no longer come
  from the published checkpoint, which is a confound in a model comparison. It would also be slow
  on 8k-token chunks.
- **Decision:** run every open model **unquantized** on HF Inference Endpoints. The local machine
  is used only as a client, and for the CPU parity reference of the 4B models (§5.4).

### 1.3 Why HF Inference Endpoints + TEI

- **Managed service:** HF runs the GPU. The endpoint is an HTTPS URL protected by the HF token, so
  it works just like a paid embedding API.
- **Supported models:** TEI (Text Embeddings Inference) supports Qwen3 and gte-Qwen2 natively. It
  batches requests by token count on the server side.
- **OpenAI compatibility:** it exposes `/v1/embeddings` as well as its own `/embed`.
- **Billing:** per minute, with **scale-to-zero** and pause. At current prices (§3.2), each open
  model costs a few dollars to embed the corpus.
- **Fallback:** if TEI fails the parity check for a model (§5.4), use the **vLLM** engine on the
  same endpoint service. vLLM supports bf16 and pooling models. For gte-Qwen2 it needs
  `--hf-overrides '{"is_causal": false}'`; without it the embeddings come out silently wrong.

### 1.4 Rules shared by every model (so the comparison is fair)

1. **Same inputs.** Embed the `Texto` column of `chunks_all.csv.gz` exactly as it is: no cleaning,
   no truncation, and the same text for every model.
2. **No silent truncation.** Every chunk is at or below 8192 tokens for every model. Tokens counted
   by the segmentation pipeline: max Qwen3 **8119** and max cl100k **7895**; the Gemini
   `countTokens` sample max was 7253. Each model's own tokenizer checks this before sending (§5.5),
   and the server is set to **reject** oversize inputs instead of truncating (TEI
   `AUTO_TRUNCATE=false` or per-request `truncate: false`).
3. **Documents without an instruction, queries with one.** This is how all three open models are
   meant to be used (the `document` prompt is `""`). A useful consequence is that **the query
   instruction can be changed later without re-embedding the corpus**, since 715 queries cost
   almost nothing.
4. **L2-normalized vectors at native dimension.** There is no MRL reduction in the main runs.
   Normalize on the client side too, since it is idempotent and protects against provider
   differences.
5. **Embed each unique text once.** The corpus has 87,704 rows but **84,569 distinct
   `texto_sha256`**. Store vectors per unique text and map them back to `chunk_id` (§4.1). Check
   that the full text matches for equal hashes (the hash is truncated to 16 hex characters).
6. **Record provenance.** For each run, record the model and revision, provider, engine version,
   dtype, prompts, input file SHA-256, the parity-check result, timings and the approximate cost
   (§4.4).

### 1.5 Corpus and query facts (measured 2026-09-25)

| Item | Value |
|---|---|
| Chunk rows / unique texts | 87,704 / 84,569 |
| Rows by `Tipo` | PAR 21,511 · INC 20,617 · ART 20,479 · CPT 8,084 · ALI 4,878 · TXT 3,545 · SEC 2,106 · CAP 1,843 · DSP 1,522 · ITE 1,302 · SSC 714 · TAB 706 · TIT 326 · LIV 45 · SBT 21 · PRT 5 |
| Qwen3 tokens: total / p50 / p90 / p99 / max | 27.0 M / 210 / 540 / 2,009 / 8,119 |
| cl100k tokens: total / max | 25.8 M / 7,895 |
| Rows > 2,048 Qwen3 tokens | 847 |
| Queries | 715 questions in `../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json` (`question_number`, `question_text`, …) |

Expected output sizes as float32 over 84,569 texts: 2560 dimensions ≈ 0.87 GB, 3584 ≈ 1.21 GB,
3072 ≈ 1.04 GB. All are above GitHub's 100 MB file limit (§4.2).

---

## 2. Work breakdown (order of execution)

0. **Fix the Constitution metadata** (§8.2). In
   `lexml/articulados/constituição_1988_19881005.xml`, set the epígrafe to
   `Constituição da República Federativa do Brasil` and the URN to
   `urn:lex:br:federal:constituicao:1988-10-05;1988`. Then re-run segmentation and re-freeze
   `segmented/chunks_all.csv.gz`. Every embedding run depends on the final chunk text.
1. **Scaffold `scripts/embedding/`** (§6.1): config file, CLI skeleton, README, pinned requirements,
   `.env.example`, and a `.gitignore` entry for `embeddings/**/*.npy` and `.env`.
2. **Providers** (§5.3): `tei`, `openai`, `gemini`, all behind one interface.
3. **Corpus and query loaders** (§4.1, §4.3), with de-duplication and token-length guards (§5.5).
4. **Resumable runner with a shard store** (§5.6) and a `finalize` step that writes the release
   format (§4.2).
5. **Parity check** (§5.4) and **smoke test** (`check` subcommand).
6. **Tests** (§6.4) that use a fake provider, so no network or GPU is needed.
7. **HF setup** (§3), done by the user following this document. Then run the models in cost order:
   `qwen3-emb-4b` first (TEI officially supports it, so it's the best test of the pipeline), then
   `jua-4b-mixed`, `inf-retriever-v1`, `openai-te3-small`, `openai-te3-large` and `gemini-emb-2`.
8. **Record costs** in the ledger as each step runs (§9), and reconcile them with the providers'
   billing once it is available.
9. **Record results** in a dated `docs/…_embedding_execution_log.md`: timings, cost, parity numbers
   and deviations. Update `CLAUDE.md` (`embeddings/` folder) and the release README.

---

## 3. Hugging Face Inference Endpoints setup (user reference)

This section is a self-contained guide. Prices and UI labels were checked on 2026-09-25; check them
again when creating the endpoints.

### 3.1 Account prerequisites

1. **HF account with billing.** Go to <https://huggingface.co/settings/billing> and add a payment
   method. HF recommends prepaid credits with automatic recharge so an endpoint doesn't stop
   mid-run. If the endpoints should be billed to an organization (e.g. `unicamp-dl`), the org
   needs its own billing, and you create the endpoints under the org namespace.
2. **Access token.** At <https://huggingface.co/settings/tokens>, create a **fine-grained** token
   named e.g. `br-taxqa-embeddings` with these permissions:
   - *Inference → Make calls to Inference Endpoints* (needed to embed);
   - *Inference → Manage Inference Endpoints* (needed only if the script or you pause, resume or
     delete endpoints programmatically, §3.6);
   - if you use an org, grant these for the org namespace.
3. **Store the token locally** without committing it: either run `hf auth login`, which writes it
   to `~/.cache/huggingface/token`, or put `HF_TOKEN=hf_…` in the repo's `.env` (gitignored, §6.3).
4. **GPU quota.** New accounts may have a small GPU quota. If an instance type is greyed out or
   creation fails with a quota error, request more through the Endpoints UI or HF support. Paused
   endpoints don't count against the quota; **scaled-to-zero endpoints do**.

### 3.2 Hardware choice and expected cost

Prices are per hour and billed per minute (HF pricing page, 2026-09-25):

| Instance | GPU memory | AWS | GCP |
|---|---|---|---|
| nvidia-t4 | 14–16 GB | $0.50 | $0.50 |
| **nvidia-l4** | 24 GB | $0.80 | $0.70 |
| nvidia-a10g | 24 GB | $1.00 | — |
| **nvidia-l40s** | 48 GB | $1.80 | — |
| nvidia-a100 | 80 GB | $2.50 | $3.60 |

| Model | Recommended | Why | Rough time / cost for the corpus |
|---|---|---|---|
| `qwen3-emb-4b`, `jua-4b-mixed` | **L4** (A10G as alternative) | 8 GB of weights plus room for 8k-token batches | ~1–3 h / ~$1–3 each |
| `inf-retriever-v1` | **L40S** | 15 GB of weights. 24 GB fits but leaves little room for activations at 8k tokens, and 48 GB allows a larger `MAX_BATCH_TOKENS` | ~1–2 h / ~$2–4 |

Avoid **T4**. It has no native bf16, TEI runs in fp16 anyway (§3.4), and it is slow. The time
estimates assume 30–40 % of peak throughput on about 2·params·27 M FLOPs. Treat them as order of
magnitude, and replace them with the rate measured in the first 5 minutes of the real run (§3.7).

### 3.3 Creating an endpoint in the UI (once per open model)

1. Open <https://endpoints.huggingface.co> and click **New** (or **Catalog**, then search).
   Alternatively, on the model's Hub page use **Deploy → Inference Endpoints**.
2. **Model repository:** enter the repo id, e.g. `Qwen/Qwen3-Embedding-4B`.
   - Set the **revision** to the commit SHA from §1.1 instead of `main`, under the
     advanced/model settings.
3. **Endpoint name:** use something short, since it becomes part of the URL, e.g.
   `qwen3-emb-4b-brtaxqa`, `jua-4b-mixed-brtaxqa`, `inf-retriever-v1-brtaxqa`.
4. **Cloud / region:** AWS `us-east-1` has the widest GPU choice. The provider must offer the
   chosen instance (L40S is AWS only).
5. **Hardware:** as in §3.2, with instance size `x1` (one GPU).
6. **Security level: Protected.** Requests need a valid HF token. Don't use *Public*, which has no
   auth. *Private* requires AWS PrivateLink and isn't needed.
7. **Autoscaling:**
   - **min replicas 0**, **max replicas 1**;
   - **scale-to-zero after 15 min** of inactivity. The UI default is 1 h; lower it so an
     unfinished session doesn't keep billing.
   - One replica is enough. Throughput comes from TEI's internal batching, and more replicas
     would only multiply the cost.
8. **Container / engine: Text Embeddings Inference.** It is usually pre-selected for models
   tagged `text-embeddings-inference`. **For `jua-4B-mixed` it may not be**, since the repo lacks
   the tag. Select TEI by hand; if the UI refuses, see §3.8.
9. **Engine settings.** Set these in the TEI configuration panel; the environment-variable name is
   given in brackets:
   - **Max Tokens per batch** [`MAX_BATCH_TOKENS`]:
     - `32768` on L4 / A10G;
     - `65536` on L40S;
     - it must be at least the model's max input length when `AUTO_TRUNCATE=false`, otherwise
       TEI refuses to start. For the Qwen3 models the config max is 40,960 positions, but TEI
       uses the tokenizer's `model_max_length`. If TEI fails at startup with a max-length
       message, raise `MAX_BATCH_TOKENS` above the value it prints.
   - **Max Concurrent Requests** [`MAX_CONCURRENT_REQUESTS`]: leave the default (512).
   - **Pooling** [`POOLING`]: **leave empty**, so it's read from `1_Pooling/config.json`, which is
     last-token for all three models. Set `last-token` only if TEI logs a different choice.
   - **Environment variables** (advanced section):
     - `AUTO_TRUNCATE=false`: oversize inputs are rejected with an error instead of being cut.
       The client also sends `truncate: false`.
     - `MAX_CLIENT_BATCH_SIZE=64`: inputs per request. The default is 32. The 2 MB payload limit
       is safe because 64 × 8k tokens is about 2 MB at worst, and the client caps each request by
       tokens anyway (§5.3).
     - `DTYPE` (only `float16` / `float32` are accepted): **leave it unset** at first, and TEI
       runs in fp16 on GPU. The models were trained and published in **bf16**, which TEI's
       `--dtype` does not offer. This is exactly what the parity check (§5.4) measures. If fp16
       fails the parity check, try `DTYPE=float32`, which needs 16 GB of weights for 4B and 30 GB
       for 7B, so an L40S or A100. If that also fails or is too slow, use the vLLM fallback
       (§3.8).
10. Click **Create Endpoint**. Initialization takes about 3–10 minutes, including the weight
    download. Wait until the status is **Running**.
11. Copy the **Endpoint URL**, e.g. `https://xxxxxxxx.us-east-1.aws.endpoints.huggingface.cloud`,
    into `.env` under the variable named in the model config, e.g. `ENDPOINT_URL_QWEN3_EMB_4B=…`
    (§6.3).

### 3.4 Smoke test (before any real run)

```bash
source .env   # HF_TOKEN, ENDPOINT_URL_…
URL=$ENDPOINT_URL_QWEN3_EMB_4B

# engine, model, revision, dtype, pooling, max_input_length, max_batch_tokens, version
curl -s "$URL/info" -H "Authorization: Bearer $HF_TOKEN" | python -m json.tool

# one embedding, no truncation allowed
curl -s "$URL/embed" -X POST -H "Authorization: Bearer $HF_TOKEN" -H 'Content-Type: application/json' \
  -d '{"inputs": ["Art. 1º Teste."], "normalize": true, "truncate": false}' | head -c 200

# token count as the server sees it
curl -s "$URL/tokenize" -X POST -H "Authorization: Bearer $HF_TOKEN" -H 'Content-Type: application/json' \
  -d '{"inputs": "Art. 1º Teste."}' | head -c 400
```

The script's `check` subcommand (§6.2) runs the same test, saves `/info` into the run manifest,
and fails if the `model_id`, `model_sha` or `max_input_length` doesn't match the config.

### 3.5 Running, then pausing

1. Run `embed corpus` (§6.2). The client keeps several requests in flight so TEI can fill its
   batches.
2. **Watch the first ~5 minutes** in the endpoint's **Analytics / Logs** tabs: GPU use, request
   latency, and any 4xx/5xx errors. Tune the concurrency flag or `MAX_BATCH_TOKENS` if the GPU is
   idle or out of memory.
3. **Right after the run, pause the endpoint.** Use **Settings → Pause** in the UI, or §3.6.
   Paused endpoints cost nothing and keep their configuration, so `resume` brings back the same
   URL. Delete the endpoint once all runs, including query re-runs, are final.
4. After scale-to-zero, the first request gets a **503** while the replica starts (minutes). The
   client retries with backoff for up to ~15 minutes, so a cold start doesn't fail the run.

### 3.6 Optional: managing endpoints from Python (`huggingface_hub`)

This is useful to pause and resume from the script's `endpoint` subcommand (§6.2) and to keep a
record of the configuration used. Create the endpoints **in the UI** (§3.3). Programmatic creation
needs the correct TEI image tag per GPU architecture (e.g. `89-<ver>` for Ada L4/L40S, `86-<ver>`
for A10G, `<ver>` for A100), and the UI picks that for you.

```python
from huggingface_hub import get_inference_endpoint

ep = get_inference_endpoint("qwen3-emb-4b-brtaxqa")   # namespace=… for an org
ep.resume().wait()          # blocks until Running
print(ep.url, ep.status, ep.raw["compute"], ep.raw["model"])   # save ep.raw in the run manifest
# … run the embedding …
ep.pause()                  # stop billing; ep.delete() when all runs are final
```

If you do want creation in code, use `huggingface_hub.create_inference_endpoint(name, repository=…,
revision=<sha>, framework="pytorch", task="sentence-embeddings", accelerator="gpu", vendor="aws",
region="us-east-1", instance_type="nvidia-l4", instance_size="x1", min_replica=0, max_replica=1,
scale_to_zero_timeout=15, type="protected", custom_image={…TEI image, health_route "/health", env…})`.
Check the argument names against the installed `huggingface_hub` version first.

### 3.7 Measuring throughput and cost

- The runner logs tokens/s and texts/s every N batches, and at the end writes the wall time into
  the manifest.
- **Cost is recorded automatically** in the cost ledger (§9). For endpoints the script measures
  the **replica-minutes** the endpoint was up, including cold start and idle time, not only the
  time spent embedding (§9.3).
- **Reproducibility note:** TEI batches dynamically, so batch composition and padding change
  between runs. In fp16 this can change the last digits of a vector. That's expected; the parity
  check thresholds (§5.4) allow for it, and the stored vectors are the reference.

### 3.8 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 / 403 | Token lacks *Make calls to Inference Endpoints*, or is for the wrong namespace | Fix the token's permissions (§3.1) |
| 503 on the first request | Scaled to zero, replica starting | Wait; the client retries automatically |
| 413 Payload too large | Too many long inputs in one request | Lower the client's `max_request_tokens` (§5.3) |
| 422 / "input validation error … must have less than N tokens" | A chunk longer than the server's max input length | Should not happen (§1.4 rule 2). Check the chunk; **never** turn truncation on to get around it |
| Endpoint fails at startup: `max_batch_tokens` < max input length | `AUTO_TRUNCATE=false` needs `MAX_BATCH_TOKENS` ≥ `max_input_length` | Raise `MAX_BATCH_TOKENS` to the value in the log |
| CUDA OOM at startup or under load | `MAX_BATCH_TOKENS` too high for the GPU | Halve it, or move to a larger GPU |
| TEI won't load `jua-4B-mixed` ("model not supported"), or the UI doesn't offer TEI | Missing Hub tag, or an architecture-detection problem | Pick **Custom container** with the TEI image, or duplicate the repo into your namespace with the `text-embeddings-inference` tag added in its README metadata (same weights; record both SHAs). Otherwise use the vLLM fallback below |
| Parity check fails in fp16 | fp16 overflow or precision loss vs bf16, or (inf-retriever) a causal-attention mismatch | Try `DTYPE=float32`. Otherwise **vLLM engine**: `--runner pooling` (older versions `--task embed`), `--dtype bfloat16`, `--max-model-len 8192`, and for inf-retriever `--hf-overrides '{"is_causal": false}'`. vLLM exposes the OpenAI `/v1/embeddings` route; the `tei` provider has an `openai_compat` mode for it (§5.3) |

---

## 4. Data formats

### 4.1 Corpus input

- **Default input:** `segmented/chunks_all.csv.gz`. Read it with pandas, `dtype=str` for ids, and
  `keep_default_na=False` so a text like "NA" isn't turned into NaN.
- **Columns used:** `chunk_id`, `texto_sha256` and `Texto`, plus the token-count columns for
  planning. The script **recomputes** `texto_sha256` over `Texto` and fails if it differs from the
  column, which catches an edited or re-encoded file.
- **Unique texts:** group by the full `Texto`, not only by the 16-hex hash, and embed each text
  once. The `text_id` is the hash; if two different texts ever share a hash prefix, it fails
  loudly.
- **Order:** sort unique texts by `text_id` so shards and outputs don't depend on the CSV row order.
- **Generic by design:** `--input` accepts any CSV/CSV.GZ/Parquet/JSONL with configurable `--id-col`
  and `--text-col`. Other people can reuse the script on their own chunks.

### 4.2 Output layout (release format)

```
embeddings/
  <model_slug>/
    corpus/
      vectors.npy          float32 [n_texts, dim], L2-normalized, rows in text_id order
      texts.csv            row, text_id (texto_sha256), n_tokens (model tokenizer)
      chunk_map.csv.gz     chunk_id, text_id   (87,704 rows → 84,569 texts)
      manifest.json        provenance (§4.4)
    queries/
      vectors.npy          float32 [n_queries, dim]
      queries.csv          row, query_id (question_number), text_sent (exact string embedded, prompt included)
      manifest.json
    parity.json            parity-check result (§5.4)
    _shards/               in-progress shard store (§5.6); removed by `finalize`
```

- Use **`.npy`** so it loads with `np.load(..., mmap_mode="r")`, needs no extra dependencies, and
  is language-neutral. A CSV sidecar maps rows to ids.
- **Size and release:** 0.9–1.2 GB per model doesn't fit in git. `embeddings/` stays gitignored
  except for manifests, `parity.json`, `endpoint_meter.jsonl` and the cost ledger `costs.csv` (§9), which are small and versioned so the provenance is in
  git. Release the vectors as a **Hugging Face dataset**, e.g. `unicamp-dl/BR-TaxQA-R` v2.0 files
  or a companion repo, with a README that states the `.npy` layout. Optionally also provide a
  float16 copy (half the size, negligible retrieval change). The float32 files are canonical.

### 4.3 Queries input and prompt templates

- **Queries** are the `question_text` of the 715 entries in
  `../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json`, with `question_number` as the id.
  Using `question_summary` too is left to §8. `--input` accepts any JSON/JSONL/CSV with
  configurable id and text fields, so the released script doesn't depend on the sibling repo path.
  Its README points to the HF dataset instead.
- **Templates live in the config, per model and per side.** `{text}` is the chunk or question and
  `{instruction}` is the shared task description:

  | Model | Query template | Document template |
  |---|---|---|
  | `jua-4b-mixed` | `Instruct: {instruction}\nQuery: {text}` (as on its card; note the space) | `{text}` |
  | `qwen3-emb-4b` | `Instruct: {instruction}\nQuery:{text}` (as in its ST config and the official usage) | `{text}` |
  | `inf-retriever-v1` | `Instruct: {instruction}\nQuery: {text}` (as in its ST config) | `{text}` |
  | `openai-te3-large`, `openai-te3-small` | `{text}` | `{text}` |
  | `gemini-emb-2` | `task: search result \| query: {text}` | `title: none \| text: {text}` (§8) |

  The exact string sent for every query is saved in `queries.csv` (`text_sent`), so there's no
  doubt about spaces or newlines.
- **Instruction (default, §8):** use **one shared, task-specific instruction** for the three
  instruct models, in English, since Qwen3's docs recommend English instructions even for
  non-English data:
  `Given a question about Brazilian personal income tax (IRPF), retrieve the legal provisions that answer it`.
  Qwen's default web-search instruction and jua's legal instruction are kept as named alternatives
  in the config. Changing the instruction only re-embeds the queries (§1.4 rule 3), so an
  instruction ablation is cheap.

### 4.4 Manifest (`manifest.json`)

The manifest records:

- `schema_version`, `created_at`, script version (git commit + dirty flag, as in the segmentation
  `run_info.json`), and the full command line;
- `model`: slug, provider, model id, revision SHA, dimension, and the templates and instruction
  used;
- `server`: the TEI `/info` output (model id and SHA, dtype, pooling, max input length, version),
  or the OpenAI/Gemini model name and API version;
- `input`: path, SHA-256 of the file, id/text columns, row count, unique-text count, and token
  stats from the model's own tokenizer;
- `output`: SHA-256 of `vectors.npy` and of the sidecar CSVs, shape, dtype, and a check that the
  vector norms are 1 ± 1e-3;
- `run`: start/end time, wall time, tokens/s, number of requests, retries and error counts;
  cost: a pointer to the ledger rows of this run (§9) and their estimated USD;
- `parity`: a pointer to `parity.json` and a pass/fail summary.

---

## 5. Script design

### 5.1 Location and dependencies

- **Folder:** `scripts/embedding/`, parallel to `scripts/segmentation/`. It is self-contained so it
  can be released on its own.
- **Dependencies:**
  - core: `numpy`, `pandas`, `pyyaml`, `huggingface_hub` (TEI client + endpoint management),
    `tokenizers` (length checks with the models' `tokenizer.json`), `tiktoken` (OpenAI length
    checks), `python-dotenv`, `tqdm`;
  - providers: `openai` and `google-genai`. Import them lazily so a user who only runs the open
    models doesn't need them.
  - **Parity reference only**, as an optional extra (`requirements-parity.txt`):
    `sentence-transformers`, `torch`, `transformers`.
- **Python 3.12**, with versions pinned in `requirements.txt` like the segmentation step.

### 5.2 Configuration (`scripts/embedding/models.yaml`)

One entry per model slug. The code contains **no model-specific settings**, so adding a model means
adding a YAML entry.

```yaml
defaults:
  instruction_name: irpf                     # D1, §8.1
  instructions:
    irpf: "Given a question about Brazilian personal income tax (IRPF), retrieve the legal provisions that answer it"
    web_search: "Given a web search query, retrieve relevant passages that answer the query"
    jua_legal: "Given a Brazilian legal search query, retrieve relevant legal passages or documents."
  max_input_tokens: 8192
  normalize: true

models:
  qwen3-emb-4b:
    provider: tei
    model_id: Qwen/Qwen3-Embedding-4B
    revision: 5cf2132abc99cad020ac570b19d031efec650f2b
    endpoint_url_env: ENDPOINT_URL_QWEN3_EMB_4B
    endpoint_name: qwen3-emb-4b-brtaxqa          # for pause/resume and the cost meter (§9.3)
    dim: 2560
    tokenizer: hf:Qwen/Qwen3-Embedding-4B@5cf2132…
    query_template: "Instruct: {instruction}\nQuery:{text}"
    document_template: "{text}"
    request: {max_inputs: 64, max_request_tokens: 32768, concurrency: 8}
    price: {usd_per_hour: 0.80, instance: nvidia-l4, checked: 2026-09-25}
  # jua-4b-mixed, inf-retriever-v1: same shape (see §1.1, §4.3)
  openai-te3-large:
    provider: openai
    model_id: text-embedding-3-large
    api_key_env: OPENAI_API_KEY
    dim: 3072
    tokenizer: tiktoken:cl100k_base
    query_template: "{text}"
    document_template: "{text}"
    request: {max_inputs: 256, max_request_tokens: 250000, concurrency: 4}
    price: {usd_per_million_tokens: 0.13, checked: 2026-09-25}
  openai-te3-small:            # same as openai-te3-large except:
    provider: openai
    model_id: text-embedding-3-small
    dim: 1536
    price: {usd_per_million_tokens: 0.02, checked: 2026-09-25}
  gemini-emb-2:
    provider: gemini
    model_id: gemini-embedding-2
    api_key_env: GEMINI_API_KEY
    dim: 3072
    tokenizer: gemini:countTokens      # the API's own count; used only for the pre-check sample
    query_template: "task: search result | query: {text}"
    document_template: "title: none | text: {text}"   # D3, §8.2
    request: {max_inputs: 100, concurrency: 4}
    price: {usd_per_million_tokens: null, checked: null}   # fill from the Gemini pricing page before the run (§9.2)
```

Check the OpenAI per-request limits (inputs per request and total tokens per request) and the
Gemini batch limits against the current API reference when implementing, and put them in the
config, not the code.

### 5.3 Provider interface

```python
class Provider(Protocol):
    name: str
    def info(self) -> dict: ...                                   # goes into the manifest
    def embed(self, texts: list[str]) -> np.ndarray: ...          # float32 [len(texts), dim]
    def count_tokens(self, texts: list[str]) -> list[int]: ...    # model's own tokenizer
```

- **`tei`:**
  - Uses `huggingface_hub.InferenceClient(model=<endpoint url>, token=HF_TOKEN)` and
    `feature_extraction(texts, normalize=True, truncate=False)`, or a plain `POST /embed` with the
    same body.
  - `info()` = `GET /info`.
  - Retries on 429/5xx and cold-start 503 with exponential backoff and jitter, up to a total wait
    limit.
  - `openai_compat: true` mode sends the request to `/v1/embeddings` instead. This is needed for
    the vLLM fallback, and in that case length checks rely only on the client-side guard.
- **`openai`:**
  - Uses the `openai` SDK `embeddings.create(model=…, input=[…], encoding_format="float")`, with
    no `dimensions` argument (native size).
  - Batches are packed under both the input-count and token-count limits.
- **`gemini`:**
  - Uses `google-genai` `client.models.embed_content(model=…, contents=[…])`, with no
    `output_dimensionality` (native 3072).
  - Turns off auto-truncation if the API offers the option; otherwise it relies on the pre-check.
  - The **Batch API** (50 % cheaper, asynchronous) is an optional mode, `--gemini-batch`. It is
    not the default, because the synchronous path is simpler to resume and the corpus costs
    little either way.
- **`fake`:** deterministic vectors from a hash of the text, used in tests and for dry runs
  (`--dry-run` estimates tokens and cost without sending anything).

### 5.4 Parity check (`embed.py parity`)

**Purpose:** show that the served embeddings equal those of the model's reference implementation.
This matters most for TEI, which runs in fp16 rather than bf16, and for inf-retriever's
bidirectional attention.

- **Sample:** a fixed and versioned set of **64 corpus texts** (stratified by `Tipo` and by length,
  including the 5 longest chunks) and **16 queries**. The ids are listed in
  `scripts/embedding/parity_sample.json`.
- **Reference:** sentence-transformers using **exactly the model card's usage**:
  - `SentenceTransformer(model_id, revision=sha, model_kwargs={"torch_dtype": torch.bfloat16})`,
    plus `trust_remote_code=True` for inf-retriever;
  - `prompt` = the same query string the endpoint gets (the templates are applied before both
    paths, so the prompt handling is the same);
  - `normalize_embeddings=True`.
- **Where the reference runs:**
  - 4B models: **on the local CPU in bf16**, about 8 GB of RAM (fits in the 15 GB), slow but fine
    for 80 texts.
  - `inf-retriever-v1` (15 GB in bf16, which doesn't fit): run on a **cloud GPU notebook**. Options
    are a Hugging Face Space with the JupyterLab template on an L4/L40S (pause it afterwards) or
    a Colab L4/A100 session. `embed.py parity --reference-only --out parity_ref_<slug>.npz` writes
    the reference vectors so they can be computed elsewhere and compared locally.
- **Metrics** saved in `parity.json`: per-text cosine similarity between served and reference
  vectors (min, p1, median), plus the **ranking agreement** of the 16 queries over the 64 texts
  (top-1 equal, Kendall τ of the full ranking).
- **Pass thresholds (provisional; adjust after the first run):** median cos ≥ 0.999, min cos
  ≥ 0.995, top-1 identical for all 16 queries.
- **Gate:** `embed corpus` refuses to start for a `tei` model without a passing `parity.json`
  for the same endpoint `/info` (model SHA + dtype). Override with `--skip-parity`, which is
  recorded in the manifest.
- **API models:** a lighter check, since there's no reference to compare against. It embeds the
  sample twice to confirm the results are deterministic up to ~1e-6 and that the norms are 1.

### 5.5 Length guard

- Before any request, the script counts tokens for every unique text with the **model's own
  tokenizer**, as set by `tokenizer` in the config:
  - `tokenizers` + the pinned `tokenizer.json` for the open models;
  - `tiktoken` for OpenAI;
  - Gemini `countTokens`: a full count is slow and costs API calls, so it covers only texts whose
    Qwen3 count is > 6,000, plus a random sample.
- It stops with a list of offending `chunk_id`s if any text is over `max_input_tokens`. It **never**
  truncates.
- The instruction prefix is added before counting for queries. Questions are short, so this only
  matters for correctness.
- For TEI the server double-checks (`truncate: false` → 422).

### 5.6 Resumable runner

- **Work unit:** a batch of unique texts, packed greedily in `text_id` order under
  `max_inputs` and `max_request_tokens`.
- **Shard store:**
  - each completed batch is written atomically (temp file + rename) as
    `_shards/<first_text_id>_<n>.npz` with `text_ids` and `vectors`;
  - on restart, the text ids already in shards are skipped. An interrupted run, cold start, or
    network failure loses at most the batches in flight.
- **Concurrency:** a thread pool of `concurrency` in-flight requests. TEI does the actual batching
  on the GPU, so the client only has to keep it fed.
- **Validation per batch:** shape = (n, dim), all values finite, norm 1 ± 1e-3 (it renormalizes
  and warns if not), and no all-zero vectors.
- **`finalize`:**
  - assembles the shards into `vectors.npy` in `text_id` order and checks for complete coverage
    (every unique text exactly once);
  - writes `texts.csv`, `chunk_map.csv.gz`, and the manifest with checksums;
  - deletes `_shards/` only after the checksums are written.
- **Idempotent:** re-running `corpus` on a finalized model does nothing unless `--overwrite` is
  given.

---

## 6. Release quality requirements

### 6.1 Files in `scripts/embedding/`

```
scripts/embedding/
  README.md                 usage for outside users (see 6.3); points to this plan
  embed.py                  CLI entry point (subcommands below)
  embedding/                small package: config.py, providers/{tei,openai,gemini,fake}.py,
                            corpus.py, runner.py, store.py, parity.py, manifest.py, tokens.py,
                            costs.py (ledger, endpoint meter, reconciliation; §9)
  models.yaml               model registry (§5.2)
  parity_sample.json        fixed parity sample ids (§5.4)
  requirements.txt          pinned runtime
  requirements-parity.txt   optional: sentence-transformers + torch for the reference
  .env.example              HF_TOKEN=, OPENAI_API_KEY=, OPENAI_ADMIN_KEY= (optional, §9.4),
                            GEMINI_API_KEY=, ENDPOINT_URL_…=
  tests/                    pytest, fake provider only (no network, no GPU)
```

### 6.2 CLI (single entry point with subcommands)

```bash
python scripts/embedding/embed.py models                          # list configured models and whether their env vars are set
python scripts/embedding/embed.py check    --model qwen3-emb-4b   # connectivity + /info + 1-text embed + config match
python scripts/embedding/embed.py parity   --model qwen3-emb-4b   # §5.4 → embeddings/qwen3-emb-4b/parity.json
python scripts/embedding/embed.py corpus   --model qwen3-emb-4b [--input segmented/chunks_all.csv.gz] [--dry-run]
python scripts/embedding/embed.py queries  --model qwen3-emb-4b [--input …questions.json] [--instruction-name default]
python scripts/embedding/embed.py finalize --model qwen3-emb-4b   # (corpus runs finalize automatically at the end)
python scripts/embedding/embed.py endpoint --model qwen3-emb-4b {status|resume|pause}   # optional, §3.6; metered, §9.3
python scripts/embedding/embed.py costs    [summary|add|reconcile --provider openai|import --provider {hf|gemini} FILE]   # §9
```

- **Defaults:** every subcommand works with no options other than `--model`, using the repo's
  default paths.
- **Help text:** `--help` shows an example for each subcommand.
- **Errors say what to do**, e.g. "ENDPOINT_URL_QWEN3_EMB_4B is not set; see README §HF setup" or
  "endpoint is paused; run `embed.py endpoint --model … resume`".
- **Progress and logs:** a `tqdm` bar with tokens/s and ETA; logs go to
  `embeddings/<slug>/run.log` as well as stderr.

### 6.3 README contents (for release)

1. **What it does**, in one paragraph, and the output format (§4.2) with a 5-line loading example:

   ```python
   import numpy as np, pandas as pd
   V = np.load("embeddings/jua-4b-mixed/corpus/vectors.npy", mmap_mode="r")
   texts = pd.read_csv("embeddings/jua-4b-mixed/corpus/texts.csv")
   cmap  = pd.read_csv("embeddings/jua-4b-mixed/corpus/chunk_map.csv.gz")
   Q = np.load("embeddings/jua-4b-mixed/queries/vectors.npy"); scores = Q @ V.T
   ```

2. **Install:** a venv plus `pip install -r requirements.txt`, and the optional parity extra.
3. **Credentials:** copy `.env.example` to `.env`; which variable each provider needs.
4. **Quick start per provider:** OpenAI, Gemini, and open models through an HF endpoint (a short
   version of §3 with a link to the full guide).
5. **Reproducing the paper's runs:** the exact commands, the model revisions, and where the
   released vectors are on the Hub, so people can use the vectors without re-embedding.
6. **Adding a model:** a YAML entry and nothing else.
7. **Cost and time table** from the actual runs, generated by `embed.py costs summary --markdown` (§9.5).
8. **License** (same as the dataset release) and a citation block.

### 6.4 Code quality

- Type hints; each module has a docstring stating its responsibility. Keep functions small and use
  no global state except the loaded config.
- **Tests** with pytest and the `fake` provider:
  - dedup and chunk map (including an equal-hash/different-text failure);
  - shard resume after a simulated crash;
  - `finalize` coverage and checksums;
  - template rendering (spaces and newlines are exact);
  - length guard rejection;
  - manifest completeness;
  - cost ledger: token and replica-minute pricing, and the endpoint meter with a fake status
    sequence;
  - CLI `--dry-run`.
- **No secrets in logs or manifests.** Tokens are read from the environment, and URLs are logged
  without query strings.
- **Deterministic output:** the same input + the same served vectors give byte-identical
  `texts.csv`, `chunk_map.csv.gz` (gzip with `mtime=0`, as in the segmentation step) and
  manifests, apart from the timestamps and timings in the `run` section.

---

## 7. Validation after each model run

The following checks go into the model's manifest and the execution log:

1. Coverage: every one of the 84,569 unique texts has exactly one vector, and all 87,704 chunk ids
   map to a text.
2. Norms are 1 ± 1e-3, values are finite, and there are no duplicate vectors for different texts
   (except the exact near-duplicates found by a `cos > 0.9999` scan, which should be reported).
3. **Sanity retrieval:** for 20 questions whose gold references are known
   (`formatted_references` in the questions file), check whether the referenced article appears
   in the top-100. This is a quick smoke signal, not the evaluation; it catches swapped
   query/document templates or a broken pooling.
4. Cross-model agreement: Spearman correlation of the query-chunk scores between models on the
   parity sample. It is only reported, not used as a gate.

---

## 8. Open decisions (defaults chosen; confirm before running)

| # | Question | Default in this plan | Cost of changing later |
|---|---|---|---|
| D1 | Query instruction (explained in §8.1) | One shared IRPF-specific English instruction (§4.3); model defaults kept as alternatives | Low: only 715 queries |
| D2 | OpenAI model | **Decided 2026-09-25:** both `text-embedding-3-large` (~$3.5) and `-small` (~$0.5) | — |
| D3 | Gemini document `title` (explained in §8.2) | `title: none`, since the chunk text already starts with Epígrafe + Ementa. The alternative, the chunk's `Rotulo` or document epígrafe, would add information to Gemini that other models don't get | **High**: re-embedding the corpus |
| D4 | Query text | `question_text` only (not `question_summary`) | Low |
| D5 | Full native dimensions vs reduced (MRL) | Native for all models | Low: truncation + renormalization can be done later from stored vectors, for the MRL-trained models |
| D6 | Where to release the vectors | HF dataset repo (float32, optional float16 copy) | Low |
| D7 | Parity thresholds | median ≥ 0.999, min ≥ 0.995, top-1 identical | Low |
| D8 | Query-side prompt also for OpenAI | none (the model has no instruction format) | Low |

### 8.1 D1 explained: what the query instruction is

The three open models (jua-4B-mixed, Qwen3-Embedding-4B, inf-retriever-v1) are **instruction-tuned
embedders**. A query is encoded together with a short *task description* that tells the model what
kind of match to look for. Documents are encoded **without** one; their configured document prompt
is `""`. For question 001, the string actually sent to the model is:

```
Instruct: Given a question about Brazilian personal income tax (IRPF), retrieve the legal provisions that answer it
Query: Quem está obrigado a apresentar a Declaração de Ajuste Anual relativa ao exercício de 2024, ano-calendário de 2023?
```

The same question can be embedded differently depending on the task: finding passages that
**answer** it, finding **similar questions**, or classifying it. These models were trained on many
such instructions, and Qwen reports about a 1–5 % gain from a task-specific instruction over a
generic one. Candidates:

| Name in `models.yaml` | Task description | Source |
|---|---|---|
| `web_search` | `Given a web search query, retrieve relevant passages that answer the query` | Default prompt of Qwen3-Embedding-4B, jua-4B-mixed and inf-retriever-v1 (`config_sentence_transformers.json`) |
| `jua_legal` | `Given a Brazilian legal search query, retrieve relevant legal passages or documents.` | Usage example on the jua-4B-mixed model card |
| **`irpf` (default)** | `Given a question about Brazilian personal income tax (IRPF), retrieve the legal provisions that answer it` | Written for this task. It is in English because Qwen recommends English instructions even for non-English data |

**Why one shared instruction:** the three open models get the same task description, so
differences between them come from the models and not from the prompts.

**The paid models have nothing equivalent:**
- OpenAI has no instruction mechanism, so the question is sent as it is.
- Gemini selects the task with a **fixed task name** (`task: search result | query: …`) rather
  than free text.

**Cost of changing:** it is cheap, because documents never carry the instruction. Changing it
re-embeds only the 715 questions, so an ablation over `web_search` / `jua_legal` / `irpf` costs
almost nothing (`embed.py queries --model … --instruction-name …`). The name used goes in the
query manifest.

### 8.2 D3 explained: why the document title only concerns Gemini

Each model expects documents in a particular input format:

| Model | Document input format |
|---|---|
| jua-4B-mixed, Qwen3-Embedding-4B, inf-retriever-v1 | Raw text (document prompt `""` in their configs) |
| text-embedding-3-small / -large | Raw text (OpenAI has no prompt format) |
| **gemini-embedding-2** | **`title: {title} \| text: {content}`**, the format Google trained it with |

Only Gemini's format has a **title slot**, so the question of what to put there exists only for
Gemini. The options:

- **`title: none`** (Google's convention when there is no title). Gemini then sees the same chunk
  text as every other model.
- **A real title**, such as the document's epígrafe or the chunk's `Rotulo`. Gemini would then get
  information the other four models don't, which biases the comparison. Evening it out would mean
  adding the title to every model's text, which changes the chunk text itself and breaks rule 1
  of §1.4.

A title would also be **redundant**, because every chunk already starts with its document's
metadata (strategy doc §6, item 1), e.g.:

```
[ DECRETO Nº 56.435, DE 8 DE JUNHO DE 1965 | Promulga a Convenção de Viena sôbre Relações Diplomáticas. … ] …
[ CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988 ] Art. 5º Todos são iguais perante a lei, …
```

**Default: `title: none`.** This decision changes the **document** vectors, so changing it later
means paying to embed the whole corpus again. Confirm it before the Gemini run.

**Data-quality item found while checking this (2026-09-25):** the Constitution chunks' metadata
reads `CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988`, with no accent and a "Nº 1" the Constitution
doesn't have. It is in the text of **3,018 chunks**, so **fix it (and re-freeze
`chunks_all.csv.gz`) before any embedding run** (§2 step 0). Details:

- **Origin:** the statutory parser, not segmentation. `lexml/articulados/constituição_1988_19881005.err.log`
  shows it was called with `-t constituicao --data 1988-10-05` and no number. The parser then
  **synthesized** both
  - the URN `urn:lex:br:federal:constituicao:1988-10-05;1` (`Metadado/Identificacao/@URN`), and
  - the epígrafe `<Epigrafe id="epigrafe">CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988 </Epigrafe>`
    from its type, number and date.

  The segmentation step (`scripts/segmentation/common.py`, `statutory_main_meta`) copies the
  `Epigrafe` into every chunk as-is.
- **Fix 1, the epígrafe (decided 2026-09-25):** replace it with the Constitution's actual title,
  **`Constituição da República Federativa do Brasil`**. The chunk prefix becomes
  `[ Constituição da República Federativa do Brasil ] Art. 5º …`. The Constitution has no
  `Ementa` in the XML, so the prefix is only the title, as today.
- **Fix 2, the URN (found while checking fix 1):** `lexml-linker` writes the Constitution as
  `urn:lex:br:federal:constituicao:1988-10-05;1988`, which is the standard LexML URN. It appears
  **1,303 times** in `lexml/` against a single `;1`, which is the document's own `Identificacao`.
  Because of this, the `urn` / `doc_urn` of the Constitution chunks don't match the references
  to it, so gold references can't be matched to Constitution chunks. Change it to `;1988`.
- **Where to fix:** in `lexml/articulados/constituição_1988_19881005.xml`, not in the segmentation
  code, so the XML stays the single source of truth. Change the `Epigrafe` text and the
  `Identificacao/@URN`. Record the manual edit in a comment at the top of the matching
  `.err.log`, and in the segmentation execution log. Also check whether the parser can take the
  number (`1988`) and the title as options, so a re-parse doesn't bring the problem back.
- **Then:** re-run `segment_all.py --overwrite` and check that the only changes in `chunks_all.csv`
  are the 3,018 Constitution rows (`Texto`, `texto_sha256`, token counts, `urn`/`doc_urn`). Update
  `run_info.json` and the segmentation report, and commit the re-frozen `chunks_all.csv.gz` **before**
  any embedding run. The corpus counts in §1.5 change slightly and need to be measured again.

---

## 9. Recording embedding costs

**Goal:** a versioned record of what each model cost, split by activity (smoke test, parity,
corpus, queries, re-runs). It is filled **automatically** by the script, then **reconciled** with
each provider's own billing, so the paper can report both the estimate and the amount actually
charged.

### 9.1 The ledger: `embeddings/costs.csv` (versioned in git)

One row per billable activity, appended by the script and never rewritten. Reconciliation adds
new rows that refer to the originals.

| Column | Meaning |
|---|---|
| `row_id` | UUID |
| `timestamp_start`, `timestamp_end` | UTC, ISO 8601 |
| `model_slug` | e.g. `jua-4b-mixed` |
| `activity` | `smoke` / `parity` / `parity_reference` / `corpus` / `queries` / `idle` / `other` |
| `run_id` | links to the manifest of the run (§4.4) |
| `provider` | `hf_endpoint` / `openai` / `gemini` / `hf_space` / `colab` / `other` |
| `billing_unit` | `tokens` or `replica_minutes` |
| `quantity` | number of tokens or replica-minutes |
| `unit_price_usd` | price per 1M tokens or per hour, copied from `models.yaml` |
| `price_checked` | the date the price in the config was checked |
| `usd` | `quantity × price` |
| `source` | `auto_estimate` (script), `provider_reported` (usage returned by the API or read from the provider's usage/cost API), `invoice` (entered by hand from the billing page) |
| `reconciles` | for reconciliation rows: the `row_id`s they cover |
| `notes` | free text, e.g. "first attempt, OOM, restarted" |

Failed or repeated runs are recorded too. The paper should report the actual cost of the
experiment, not only the successful run.

### 9.2 API models (OpenAI, Gemini): tokens × price, automatic

- **OpenAI:**
  - every `embeddings.create` response has `usage.prompt_tokens` / `usage.total_tokens`. The
    provider **adds them up exactly**, and the ledger row's quantity is that sum
    (`source=provider_reported`);
  - the `tiktoken` pre-count (§5.5) is kept in the manifest as a cross-check. The two should
    match.
- **Gemini:**
  - the REST `embedContent` / `batchEmbedContents` response may include
    `usageMetadata.promptTokenCount`, but the `google-genai` SDK currently hides it
    (`EmbedContentResponse` exposes only `embeddings` and `metadata`). The provider reads it from
    the raw HTTP response if it's there;
  - otherwise it calls **`countTokens`** (no charge, but rate-limited) on every text actually sent,
    concurrently, and records `source=auto_estimate`;
  - the Batch API mode (§5.3) uses the 50 % price.
- **Prices** come from `models.yaml` (`price.usd_per_million_tokens` + `checked`). The script
  **refuses to run a paid model whose price is missing** unless given `--price-unknown`, which
  writes `usd` as empty. The Gemini price must be filled in from
  <https://ai.google.dev/gemini-api/docs/pricing> before its run; this plan doesn't record it.
- `--dry-run` prints the expected cost from the pre-counts before anything is sent.

### 9.3 HF Inference Endpoints: replica-minutes × hourly price, automatic

HF bills the **time a replica is up** (per minute), not tokens. That includes initialization,
cold starts and the idle time before scale-to-zero. HF had no documented billing API on
2026-09-25, so the script **meters the endpoint itself**:

1. **Endpoint meter.** Whenever the script touches an endpoint (`check`, `parity`, `corpus`,
   `queries`, `endpoint resume`), a background thread polls
   `huggingface_hub.get_inference_endpoint(name).fetch()` every 60 s. It records the status and
   the number of running replicas (`ep.raw["status"]`, which includes the ready/target replica
   counts) into `embeddings/<slug>/endpoint_meter.jsonl`. The endpoint therefore needs
   `endpoint_name` in `models.yaml` and a token with *Manage Inference Endpoints* permission
   (§3.1), which is needed only for reading the status here.
2. **When the script's work ends**, the meter:
   - if the script **paused** the endpoint (`--pause-after`, **the default for `corpus`**): stops
     when the status reaches `paused`, so the interval is exact;
   - if the endpoint is left running: adds the **scale-to-zero timeout** from the endpoint's
     config (15 min in §3.3) as the expected idle tail, and marks that part as
     `activity=idle, source=auto_estimate`.
3. **Ledger rows:**
   - `quantity` = Σ(running replicas × minutes), rounded up to whole minutes;
   - `unit_price_usd` = the instance's hourly price from `models.yaml`;
   - the instance type is read from the endpoint (`ep.raw["compute"]`) and checked against the
     config, and a mismatch is a warning.
4. **Manual use of the endpoint** outside the script (UI playground, curl, leaving it running) is
   not metered. Use `embed.py costs add --model … --activity other --replica-minutes N --notes …`,
   or rely on reconciliation (§9.4) to catch it.
5. **Cross-check:** the endpoint's **Analytics → Running Replicas / Timeline** view (§3.5) shows
   the same intervals.

### 9.4 Reconciliation with actual billing

Estimates are good to a few percent. The amounts actually charged come from the providers. For
this to work, **each provider's charges must be attributable to this experiment only**:

| Provider | Isolation (set up before the first run) | Where the actual cost is | Automation |
|---|---|---|---|
| OpenAI | A dedicated **project** (e.g. `br-taxqa-r-embeddings`) with its own API key, used for nothing else | Costs API `GET /v1/organization/costs?start_time=…&group_by=project_id,line_item` (daily buckets); needs an **Admin key** (`OPENAI_ADMIN_KEY`, created by an org owner) | **Automatic:** `embed.py costs reconcile --provider openai --since 2026-09-25` fetches the daily costs of the project and appends `source=provider_reported` rows per day and line item, with `reconciles` set to the matching estimate rows |
| Gemini | A dedicated **Google Cloud project** for the Gemini API key (AI Studio → API keys → create key in a new project) | Google Cloud Console → Billing → Reports, filtered by that project, service "Gemini API", with SKUs per model | **Manual:** export the report as CSV, then run `embed.py costs import --provider gemini report.csv`. It is also possible with BigQuery billing export, but that's not worth setting up for a one-off experiment |
| HF Inference Endpoints | Only this experiment's endpoints in the account or org during the runs; if not possible, filter by endpoint name | <https://huggingface.co/settings/billing> (or the org's billing page): usage per endpoint | **Manual:** copy per-endpoint amounts, or download the usage CSV if the page offers it, then run `embed.py costs import --provider hf FILE` (or `costs add --source invoice`) |
| Parity reference (HF Space / Colab, §5.4) | — | The Space's billing line, or the Colab compute units used | **Manual:** `embed.py costs add --activity parity_reference …` |

- **Timing:** reconcile **a day or two after** the runs, since billing data lags; OpenAI's daily
  buckets fill in within about a day.
- `costs summary` then shows estimate vs actual per model, and flags differences above 10 % for a
  note in the execution log.

### 9.5 Reporting

`embed.py costs summary [--markdown] [--by model|activity|provider]` produces:

| Model | Corpus tokens | Corpus cost (est.) | Queries | Parity + smoke | Idle / failed | **Total est.** | **Total actual** | Wall time |
|---|---|---|---|---|---|---|---|---|

- The Markdown table goes into the execution log and the release README (§6.3 item 7).
- The per-model total also goes into each corpus manifest (§4.4), so the released vectors carry
  their cost.
- **Also report tokens per model.** A model with a different tokenizer (e.g. `cl100k_base` vs
  Qwen) processes a different number of tokens for the same corpus, which explains part of any
  cost difference.

### 9.6 Checklist per model run

1. Before: price in `models.yaml` checked (date), dedicated project/key (OpenAI, Gemini), and
   `endpoint_name` set (HF).
2. `embed.py corpus --model … --dry-run` gives the expected cost. Continue only if it's acceptable.
3. Run. The ledger rows are appended automatically, and HF endpoints are paused at the end by
   default.
4. `embed.py costs summary --model …`, then note anything unusual (retries, restarts) with
   `costs add --notes` or in the execution log.
5. After 1–2 days, reconcile (§9.4) and update the execution log with the actual amounts.
