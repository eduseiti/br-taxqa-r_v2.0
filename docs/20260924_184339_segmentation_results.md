# Segmentation Results (first full run)

**Generated:** 2026-09-24 18:43:39 (local time, from `date +%Y%m%d_%H%M%S`)
**Implements:** step 8 of `docs/20260924_123747_segmentation_implementation_plan.md`. How the numbers
were produced, with problems found and deviations, is in
`docs/20260924_175304_segmentation_execution_log.md`.
**Run:** `.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite`. Cap
1,024 tokens, reference tokenizer `max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`, ementa in
the prefix ≤ 128 tokens. 87.5 s wall-clock on 16 workers. Validation: **all checks pass**
(`segmented/segmentation_report.md`).

## 1. Chunk counts

| Strategy | Tipos | Chunks | Σ reference tokens | Strategy doc §5 estimate |
|---|---|---:|---:|---:|
| **S1** | ART, DSP, TXT, TAB | **26,252** | 8.20 M | ≈ 19.4 k statutory + DSP + NS |
| **S2** | S1 + CPT, PAR, INC, ALI, ITE | **82,644** | 20.94 M | ≈ 88 k |
| S3 | S2 + PRT…SSC ≤ 8,192 tokens | **87,704** ² | — | ≈ 94 k |

- **ART units = 19,393**, exactly the number of `Artigo` outside `Alteracao` (strategy doc §4). 647
  of them (3.3 %) are above the cap and were split into parts, so S1 holds 20,479 ART rows.
- S2/S3 are ≈ 5.5 k below the estimates because **CPT is emitted only for articles that have a
  paragraph** (plan X5/Q5): 8,084 CPT rows instead of 19,393. The other difference is the 1,403
  orphan INC/ALI/ITE rows of the original XSL, which are now `DSP` rows.
- S3 holds 32.5 M tokens against 8.2 M for S1. Groupings are the bulk: one PRT reaches 179 k tokens.

| Tipo | Rows | p50 | p90 | p99 | max (reference tokens) |
|---|---:|---:|---:|---:|---:|
| ART | 20,479 | 193 | 680 | 1,007 | 1,024 |
| DSP | 1,522 | 150 | 592 | 911 | 1,009 |
| TXT | 3,545 | 309 | 984 | 1,021 | 1,024 |
| TAB | 706 | 354 | 981 | 1,022 | 1,163 ¹ |
| CPT | 8,084 | 162 | 356 | 1,013 | 8,103 |
| PAR | 21,511 | 233 | 381 | 642 | 5,936 |
| INC | 20,617 | 193 | 352 | 569 | 4,116 |
| ALI | 4,878 | 200 | 349 | 573 | 1,420 |
| ITE | 1,302 | 165 | 295 | 436 | 1,358 |
| SEC / SSC | 2,125 / 717 | 588 / 500 | 2,227 / 1,965 | 7,383 / 4,990 | 33,325 / 10,328 |
| CAP / TIT | 1,919 / 410 | 871 / 2,476 | 4,516 / 14,610 | 15,847 / 34,857 | 72,385 / 76,134 |
| LIV / SBT / PRT | 88 / 26 / 18 | 8,092 / 4,200 / 21,256 | — | — | 147,686 / 18,756 / 179,420 |

² Updated 2026-09-24 after review (option 2): the 243 grouping chunks above 8,192 tokens are left
out of `chunks_all.csv` and listed in `segmented/groupings_over_limit.csv`. The first run had 87,947.

¹ The only chunk above the cap: one table row of `portaria_2012_1114`, which cannot be cut (plan
§5.3); it is flagged.

The Qwen3 tokenizer counts ≈ 4–6 % more tokens than `cl100k_base` on this corpus (e.g. ART p50 194 vs
187; INC 193 vs 182). It sets the reference count almost everywhere.

Per category (rows, all Tipos): main documents 72,103 · A annexes 11,257 · B annexes 1,041 ·
C annexes 495 · `nao_articulados` 3,051.

## 2. Splitting

- **ART/DSP split** (§5b): 656 units (647 ART, 9 DSP) → 1,752 parts. 72 needed a within-leaf split
  (text or table). In 8 of them the repeated HEAD was truncated after its first full appearance
  (deviation D3). Largest: `lei_10865_20040430` art. 8 (16.2 k tokens → 25 parts),
  `in_rfb_1343_20130405` art. 9 (14.4 k → 21), RIR/2018 art. 35 (10.2 k → 12).
- **Non-statutory TXT/TAB** units split: 342.

## 3. Over-cap rows left unsplit (Q7)

| Tipo | Rows | > 1,024 | ≥ 8,192 |
|---|---:|---:|---:|
| CPT | 8,084 | 78 | 0 |
| PAR | 21,511 | 43 | 0 |
| INC | 20,617 | 23 | 0 |
| ALI / ITE | 4,878 / 1,302 | 4 / 1 | 0 |
| SEC / SSC | 2,125 / 717 | 619 / 155 | 19 / 3 |
| CAP | 1,919 | 856 | 76 |
| TIT / SBT | 410 / 26 | 288 / 21 | 84 / 5 |
| LIV / PRT | 88 / 18 | 73 / 18 | 43 / 13 |

Sub-article rows: 149 of 56.4 k are above the cap, all below 8,192. They can go into S2 as they are
(the Q7 default holds). Groupings: 243 rows are **≥ 8,192 tokens**, so they would be rejected by
`text-embedding-3-small` and truncated by Gemini. **Decision (option 2):** only the embeddable groupings
are kept; the 243 others are listed in `segmented/groupings_over_limit.csv` (see the execution log
addendum).

## 4. Other figures

- Rows with `id_ambiguo = 1`: 1,810, of which 1,195 are basic units (ART/DSP/TXT/TAB). These are
  duplicate ids in the source, e.g. orphan `ali1`/`ite2` repeated in the annexes of
  `decreto_8289_20140725` and two `art16` in `circ_bc_3432_20090203`.
- Dropped `Agrupamento`s (Q4): 392 `assinatura`, 44 `preliminar`, 13 `localDataFecho`. **11 long
  ones were kept as TXT** (deviation D2, ≥ 300 chars): mis-tagged soluções-de-consulta ementas (up to
  1.5 k chars), case facts, and court-case headers.
- Text coverage (word multiset of the S1 bodies vs. document text): minimum 99.8 %, every file
  ≥ 98 %.
- Gemini `countTokens` check (`gemini-embedding-2`, run later on 2026-09-24): 500 random + the 100
  largest chunks. Gemini counts ≈ 12 % fewer tokens than the reference (ratio p50 0.88, max 1.10);
  the largest chunk counts 7,253 Gemini tokens, so **none is above 8,192** and nothing would be
  truncated.
- Outputs: `segmented/chunks_all.csv` is 148 MB (groupings account for most of it), and
  `segmented/` is 256 MB in total.
