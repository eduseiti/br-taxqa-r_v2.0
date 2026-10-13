# Segmentation maximum length: strategy and its effect on the corpus

**Generated:** 2026-10-13 10:58:50 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** a quick reference that gathers what the earlier notes decided about chunk length, with the
figures of the current corpus. It decides nothing new.
**Sources:**
- `docs/20260924_123747_segmentation_implementation_plan.md` §2.6 (cap and tokenizer), §5.3 (non-statutory
  splitting), §5b (oversize article splitting);
- `docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` §6 item 5;
- `docs/20260924_184339_segmentation_results.md` (first run) and the Gemini `countTokens` check;
- `docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md` E1 (128-token ementa);
- `docs/20261009_121822_nonstat_reparse_decision_and_pipeline_rerun_log.md` (current corpus);
- `segmented/segmentation_report.md` (rerun of 2026-10-09 12:57, the current chunk set).

## 1. Strategy

### 1.1 The cap: 1,024 tokens per basic unit (decided 2026-09-24)

Every chunk that a strategy indexes as its basic unit (`ART`, `DSP`, `TXT`, `TAB`) must be ≤ 1,024 tokens.

**The cap is about chunk size, not a model limit.** The embedding models accept 8,192 tokens
(`text-embedding-3-small`, `gemini-embedding-2`) or 32 k (Qwen3-Embedding-4B, jua-4B-mixed,
inf-retriever-v1). Non-statutory chunks and parts of long articles compete with articles in the same index
and the same context budget, so they should be about the size of a typical article, not of a whole opinion.
1,024 tokens ≈ the 97th percentile of article length (article p50 372, p90 1,605, p99 4,841 characters).

### 1.2 How tokens are counted

- **Reference tokenizer:** the per-text maximum of `tiktoken:cl100k_base` and `hf:Qwen/Qwen3-Embedding-4B`
  (`--tokenizer max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`). Qwen counts ≈ 4–6 % more on this
  corpus, so it sets the count almost everywhere.
- **Gemini** cannot be counted locally at corpus scale. A sample of 600 chunks (500 random + the 100
  largest) was checked with `countTokens`: Gemini counts ≈ 12 % fewer tokens (ratio p50 0.88, max 1.10); its
  largest chunk was 7,253 tokens, so nothing is truncated.
- One segmentation run serves **all** embedding models, so every model embeds the same chunk set.

### 1.3 The cap includes the metadata prefix and the ementa

The cap applies to the **full `Texto`**:

```
[ epígrafe | ementa (≤ 128 tokens) | annex label ]  <article label / ancestor path>  <body>
```

The 128-token limit (`--ementa-max-tokens 128`, caput plan E1) is applied **first**, to the ementa alone.
The 1,024-token cap then applies to prefix + label/path + body. The ementa is **not** added on top of the
1,024.

Where it is enforced:
- `scripts/segmentation/split_oversize.py:86`: a part is accepted only if
  `count(prefix + HEAD + bodies) ≤ cap`;
- `scripts/segmentation/segment_non_statutory.py:268–270`: TXT/TAB pieces are built from
  `prefix + heading + lines`;
- `validate_segments.py`, check `cap`: uses the stored token count of the full chunk text.

The prefix is `[ epígrafe | ementa | annex label ]`, and only the ementa is limited to 128 tokens. So the
prefix as a whole can go slightly above 128.

**Prefix size**, measured on 2026-10-13 on a sample of 4,000 base ART/DSP/TXT/TAB chunks, in `cl100k_base`
tokens (the reference count is ≈ 5 % higher):

| Tipo | Sampled | Prefix median | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| ART | 3,107 | 53 | 139 | 153 | 156 |
| DSP | 153 | 85 | 102 | 145 | 153 |
| TXT | 645 | 64 | 153 | 157 | 161 |
| TAB | 95 | 85 | 153 | 181 | 181 |

- The room left for content is ≈ 860–970 tokens per chunk.
- In chunks near the cap (over 900 tokens, 245 in the sample), the prefix is a median **7 %** of the text.
- **Side effect:** a document with a long ementa has less room per chunk, so its long articles split into
  slightly more parts. The caput plan (E1) recorded this when the 128 limit was chosen: "a longer prefix can
  create a few more article parts".

### 1.4 What happens above the cap

| Unit | Rule |
|---|---|
| **Articles (`ART`) and orphan dispositivos (`DSP`)** | Split along the structure by `split_oversize.py` (plan §5b), details below |
| **Non-statutory text (`TXT`)** | Cut greedily at the last line ending in `.`, `;`, `:` or a paragraph number (`12.`); then at a line, then at a word boundary. No overlap. `Rotulo` gets `, parte k/n` |
| **Tables (`TAB`)** | Packed by groups of rows, with the caption and header repeated in every part |
| **A single line or table row above the cap** | Kept, flagged, and reported |
| **Sub-article units (`CPT`, `PAR`, `INC`, `ALI`, `ITE`; S2)** | Not capped: the few above 1,024 tokens are kept as they are (all below 8,192) |
| **Groupings (`CAP`, `SEC`, `TIT`…; S3)** | A separate limit of **8,192** tokens (`--grouping-max-tokens`), the real model limit. Groupings above it are left out of `chunks_all.csv` and listed in `segmented/groupings_over_limit.csv` (decision "option 2", 2026-09-24) |

**How an article is split** (plan §5b):
- Caput and paragraphs are packed greedily into parts.
- A unit that is too big by itself is replaced by its children: incisos → alíneas → itens.
- A single leaf that is still too big (usually a table) is split inside the leaf.
- Every part repeats a HEAD: the article label + the caput sentence, plus the ancestor path when needed. So a
  part made of §§ 3–5 still reads "Art. 8º <caput sentence> § 3º …" (caput plan Q2).
- Parts keep the `Tipo`, so S1 indexes "article or article part".
- `urn` gets `_p<k>`, and `<csv>.prov.jsonl` records what each part covers.

## 2. Effect on the current corpus (rerun of 2026-10-09: 77,080 base rows, 625 files)

### 2.1 Splitting

- **597 of ≈ 15.8 k articles (≈ 3.8 %) and 9 DSP were split**, into 1,626 parts.
  - 69 needed a split inside a single leaf.
  - In 8, the repeated HEAD was itself shortened to 256 tokens + "…" after its first full appearance
    (deviation D3).
- **316 non-statutory TXT/TAB units (≈ 11 %) were split.** Opinions and soluções de consulta are much longer
  than articles.
- **1 row is above the cap and cannot be cut:** a single 1,163-token table row of `portaria_2012_1114`. It is
  flagged.
- **193 groupings above 8,192 tokens are left out** (243 before the 2026-10-09 rerun).
- Validation: `cap` 0 violations; text coverage after splitting ≥ 99.8 % per file.

Largest split articles:

| Article | Tokens | Parts | Leaf split |
|---|---:|---:|---|
| Lei 10.865/2004, art. 8º | 16,239 | 26 | yes |
| IN RFB 1.343/2013, art. 9º | 14,415 | 21 | yes |
| RIR/2018 (`decreto_9580_20181122.anexo1`), art. 35 | 10,238 | 12 | |
| LC 123/2006, art. 18 | 9,947 | 15 | |
| Lei 9.718/1998, art. 5º | 6,997 | 11 | |
| Lei 9.250/1995, art. 8º | 3,822 | 5 | |

Full list: `segmented/segmentation_report.json`.

### 2.2 Resulting lengths (reference tokens, base rows)

| Tipo | Rows | p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| ART | 16,784 | 217 | 727 | 1,010 | 1,024 |
| DSP | 875 | 166 | 742 | 926 | 1,009 |
| TXT | 3,306 | 330 | 983 | 1,020 | 1,024 |
| TAB | 532 | 310 | 977 | 1,023 | 1,163 |
| CPT | 7,091 | 166 | 356 | 1,027 | 8,103 |
| PAR | 19,675 | 150 | 253 | 489 | 5,776 |
| INC | 18,235 | 168 | 280 | 473 | 3,956 |
| ALI | 5,045 | 170 | 291 | 431 | 1,420 |
| ITE | 1,575 | 164 | 277 | 416 | 1,358 |
| SEC | 1,745 | 606 | 2,267 | 5,739 | 7,827 |
| SSC | 567 | 521 | 2,037 | 4,192 | 7,771 |
| CAP | 1,431 | 910 | 3,870 | 7,378 | 7,941 |
| TIT | 187 | 1,886 | 6,218 | 7,953 | 8,102 |
| SBT / LIV / PRT | 20 / 9 / 3 | 3,290 / 1,599 / 4,172 | — | — | 8,061 / 6,055 / 7,433 |

The capped types (ART, TXT, TAB) bunch up just below 1,024 (p99 ≈ 1,010–1,023). That is the greedy packing
filling parts up to the cap.

### 2.3 Earlier runs (for the paper)

| Run | ART/DSP split → parts | Groupings left out (> 8,192) |
|---|---:|---:|
| First run, 2026-09-24 | 656 (647 ART + 9 DSP) → 1,752 | 243 |
| Rebuild R7, 2026-10-08 | 655 → 1,746 | 243 |
| Rerun, 2026-10-09 (current) | 606 (597 ART + 9 DSP) → 1,626 | 193 |

The drop on 2026-10-09 comes mostly from five removed documents: Lei 3.071/1916, Lei 5.869/1973, IN RFB
1.911/2019 with its 60 annexes, Decreto 7.030/2009 and IN RFB 1.505/2014.
