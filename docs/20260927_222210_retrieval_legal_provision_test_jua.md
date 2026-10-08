# Retrieval Legal-Provision Test with `jua-4b-mixed` (RAG pipeline Phase 1)

**Generated:** 2026-09-27 22:22:10 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** implemented and run. Provisional result (one embedding model, corpus with known gaps).
**Plan:** `docs/20260927_204356_rag_pipeline_implementation_plan.md` (Phase 1: stages R and RE).
**Code:** `scripts/rag/` (usage and formats in `scripts/rag/README.md`).
**Outputs:** `runs/retrieval/jua-4b-mixed/irpf/` (rankings) and
`runs/retrieval/jua-4b-mixed/irpf/eval/either_containment_skip/` (`report.md` has every table).

> **Note (2026-10-08):** this test ran on the **old corpus** (chunk file `f3db0904…`). By the
> definitions of `docs/20261005_184116_*`, its S2/S3 are **S2c/S4**: the paragraph chunks carried the
> caput sentence. The corpus was rebuilt on 2026-10-08 and the retrieval re-run with S1/S2/S3/S2c/S4;
> see `docs/20261008_010441_corpus_rebuild_results.md`. The rankings under `runs/retrieval/jua-4b-mixed/irpf/S*/` now belong to the new run.
> This evaluation's `report.md`/`metrics.csv` are kept as they were.

---

## 1. What was run

```bash
R=scripts/rag/rag.py
.venv/bin/python $R check    --embedding jua-4b-mixed
.venv/bin/python $R retrieve --embedding jua-4b-mixed                        # 11 s
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf    # 15 s
```

- **Inputs:** chunks `segmented/chunks_all.csv.gz` (SHA-256 `f3db0904…`, the file the
  `jua-4b-mixed` corpus manifest records), corpus vectors [84,568 × 2,560], query vectors of
  instruction `irpf` [715 × 2,560], dataset v2.0 after the provision fix
  (`docs/20260927_213420_reference_provisions_from_citation_text.md`). `check` passes. Its only
  warning is the 11 cited documents without chunks (§4).
- **Retrieval:** exact cosine, top-1,000 texts per question and strategy, S1 / S2 / S3 as in
  `scripts/rag/strategies.yaml`.

  | | Chunks | Texts |
  |---|---:|---:|
  | S1 | 26,250 | 26,208 |
  | S2 | 82,642 | 79,508 |
  | S3 | 87,702 | 84,568 |

- **Evaluation:** annex rule `either`, containment de-duplication, overflow `skip`, budgets
  1k–16k Qwen3 tokens, paired bootstrap (10,000 resamples, seed 13) and sign-flip permutation
  tests.
- **Determinism:** a second run of both stages gave byte-identical rankings, `metrics.csv`,
  `per_question.csv.gz` and `comparisons.csv`.
- **Tests:** 23 pytest tests on a fixture corpus pass (`scripts/rag/tests`).

## 2. Headline: token-budget view, all resolved gold

Recall of the gold items of each question, averaged over questions. "Oracle" is the ceiling given
the corpus gaps (§4).

| Level (questions) | Strategy | 1k | 2k | 4k | 8k | 16k | Oracle |
|---|---|---:|---:|---:|---:|---:|---:|
| Document (594) | S1 | 0.378 | 0.495 | 0.613 | 0.718 | 0.796 | 0.993 |
| | S2 | **0.453** | **0.548** | **0.635** | **0.727** | **0.804** | 0.993 |
| | S3 | 0.450 | 0.543 | 0.630 | 0.716 | 0.794 | 0.993 |
| Article (553) | S1 | 0.170 | 0.270 | 0.388 | 0.491 | 0.576 | 0.985 |
| | S2 | **0.278** | **0.354** | **0.435** | 0.530 | 0.617 | 0.985 |
| | S3 | 0.273 | **0.354** | 0.430 | **0.532** | **0.631** | 0.985 |
| Provision, full (558) | S1 | 0.157 | **0.243** | **0.358** | **0.462** | 0.540 | 0.961 |
| | S2 | 0.165 | 0.228 | 0.327 | 0.439 | 0.541 | 0.961 |
| | S3 | **0.170** | 0.232 | 0.337 | 0.447 | **0.559** | 0.961 |
| Provision, full or partial | S1 | 0.166 | 0.261 | 0.370 | 0.474 | 0.558 | 0.961 |
| | S2 | **0.249** | 0.315 | 0.398 | 0.501 | 0.589 | 0.961 |
| | S3 | 0.245 | **0.317** | **0.399** | **0.502** | **0.601** | 0.961 |

Context precision is the share of context tokens that come from texts hitting a gold article:

| | 1k | 2k | 4k | 8k | 16k |
|---|---:|---:|---:|---:|---:|
| S1 | 0.145 | 0.141 | 0.126 | 0.089 | 0.057 |
| S2 | 0.223 | 0.204 | 0.184 | 0.148 | 0.106 |
| S3 | 0.221 | 0.211 | 0.194 | 0.170 | 0.142 |

The budgets are filled: the mean selected context is 983–985 tokens at 1k and 15,982–15,985 at 16k,
with 4–49 texts.

## 3. Findings

1. **S2 beats S1 at document and article level at every budget.** Article recall S2 − S1:
   **+10.8 pts at 1k** [+8.3, +13.4], +8.4 at 2k, +4.7 at 4k, +3.9 at 8k, +4.1 at 16k (all p ≤ 0.0002).
   Context precision is higher at every budget (+4.9 to +7.8 pts, p = 0.0001). The same holds in
   the unit projection, which compares with other retrieval papers: article R@10 is 0.505 → 0.543,
   nDCG@10 0.397 → 0.427. **S2 finds the cited articles with less noise.**
2. **At provision level the effect depends on what the gold cites.**

   | 4k budget, provision recall | S1 | S2 | S3 |
   |---|---:|---:|---:|
   | Sub-article gold (caput / § / inciso / alínea / item; 366 questions) | 0.328 | **0.376** | 0.369 |
   | Whole-article gold ("art. 2º"; 429 questions) | **0.345** | 0.243 | 0.260 |
   | Whole-article gold, full or partial | 0.359 | 0.358 | 0.358 |

   On **sub-article** gold, S2 gains +4.8 to +8.4 pts at every budget, which is the S2 hypothesis
   of the strategy doc (§5.1). On **whole-article** gold, S2 retrieves *a part* of the cited
   article as often as S1 retrieves the whole (partial recall is equal), but it puts the whole
   `ART` chunk in the context less often, so full recall drops by 6–10 pts. Overall provision
   recall is therefore not significantly different at 1k, 2k and 16k, and S1 is ahead at 4k
   (−3.1 pts [−5.6, −0.7], p = 0.010) and 8k (−2.4 pts, p = 0.028). Whether a part of an article
   is enough to answer is exactly what the nugget evaluation will decide. The retrieval test
   cannot.
3. **S3 (groupings) adds little.** S3 − S2 is within ±1 pt at document level and on article
   recall up to 8k. S3 is slightly better on provision full recall at 4k and 16k (+1.8 / +2.5 pts,
   p ≈ 0.01–0.02), because chapter chunks hold whole articles. It is worse on the article unit
   projection (R@10 −2.8 pts, p = 0.001), because a grouping chunk takes many unit positions.
   This matches the strategy doc's expectation: keep **S1 vs S2** as the main comparison.
4. **Embedded references are hard:** at 4k, article recall is 0.13 for embedded gold vs 0.42–0.48
   for explicit gold. Embedded references are the acts cited *inside* the answer text, often
   side remarks.
5. **Budgets for the generation grid:** the S1–S2 gap is largest at 1k–2k and the recall curves
   are still rising at 16k (article recall 0.62 for S2). The 4k default of plan §6.1 is a
   reasonable middle point. 2k and 8k bracket it.

## 4. Reachability and known issues in force

From `reachability.csv` (gold items, identical across strategies after the split-article rule, §5):

| Level | Gold items | Reachable | Unreachable | Reason |
|---|---:|---:|---:|---|
| Document | 1,687 | 1,673 | 14 | 11 cited documents without chunks (empty `<Articulacao>`) |
| Article | 1,957 | 1,933 | 24 | 8 in documents without chunks, 16 article ids missing from the LexML |
| Provision | 2,229 | 2,160 | 69 | gold units without a LexML id (annex-only citations, "item 9" of pareceres, ids not in the XML) |

- 42 references are `not_in_corpus` and are not counted as gold.
- **G3 (main/annex):** the main file and an annex both have the cited article in only 3 article
  items (4 provision items), so `either` vs `main_first` hardly matters for this run.
- **G4:** no gold item is reachable only through `id_ambiguo = 1` chunks.
- **Non-statutory provisions** (10 questions, "item 18" of a Parecer Normativo, etc.) have no
  LexML id and are all unreachable. Non-statutory gold counts only at document level.
- `strategies.yaml` records the chunk counts of the current chunk file. The plan quotes 26,252 /
  82,644 / 87,947 from the 2026-09-24 run, before the over-limit grouping chunks
  (`segmented/groupings_over_limit.csv`) were dropped.

## 5. Deviations from the plan

1. **Split articles in G5 (provision matching).** The plan's rule is per chunk: a unit is fully hit
   when one chunk holds it. An article long enough to be split into `parte 1..n` ART chunks is then
   never fully hit in S1/S2 when it is cited as a whole. That made 108 (S1) and 98 (S2) provision
   items unreachable while S3 reached them through grouping chunks, and 65 more were unreachable in
   every strategy. The matcher now also counts a unit as fully hit once **all the parts of the
   split article that hold it** are retrieved (rank = the rank of the last part). The budget view
   checks that all those parts are in the context. After the change the provision oracle is 0.961
   for all three strategies. `reachability.csv` counts the items that only this rule makes
   reachable (`reachable_by_split_parts_only`: 173 / 163 / 65).
2. **Extra columns** `gold` (`all` / `reachable`) and `slice` in `metrics.csv` and
   `per_question.csv.gz`. Plan §5 lists only `strategy, level, view, cutoff, metric, value,
   n_questions`.
3. **Extra outputs:** `per_item.csv.gz` (per gold item, used for the examples below),
   `reachability.csv`, `comparisons.csv`, `metrics_by_chapter.csv.gz`. `per_item`,
   `per_question` and the per-chapter file are not versioned (size).
4. **Module layout:** the stage drivers are in `ragpipe/retrieval.py` and `ragpipe/evaluation.py`,
   so `rag.py` only parses arguments. There is also a `report` subcommand that regenerates
   `report.md`.
5. **Chapter slice:** the dataset has no chapter field. The ranges were taken from the table of
   contents of the P&R PDF (48 chapters) and stored in `scripts/rag/data/pr_irpf_2024_chapters.csv`.
   They could become a `chapter` field of the `questions` config in a later dataset build.
6. **Unit projection:** a grouping chunk (S3) stands for every article it contains, in document
   order. Positions beyond 1,000 distinct units count as not retrieved (this bounds the work for
   `PARTE`/`LIVRO` chunks). MRR and nDCG@10 are reported at cutoff `-` of the `unit` view.
   Provision level has no unit projection.
7. **Evaluation needs no vectors:** `evaluate` reads the rankings (representative chunk + aliases),
   the chunks and the dataset. It checks that the chunk file and the ranking files match the
   retrieval manifest.

## 6. Worked examples (4k budget, provision level)

**S2 finds the cited unit, S1 misses it** (83 sub-article gold items; the reverse happens for 59):

| Q | Gold | S1 full rank | S2 full rank |
|---|---|---:|---:|
| 128 "Como são tributados os rendimentos recebidos no Brasil por não residente?" | IN RFB 1.500/2014, art. 19, inciso XVI | 590 | **1** |
| 124 "…deduções de pagamentos efetuados em moeda estrangeira na Declaração de Saída Definitiva…" | IN SRF 208/2002, art. 9º, § 7º | 15 | **1** |
| 120 | IN SRF 208/2002, art. 2º, inciso IV | 15 | **3** |
| 179 | IN RFB 1.500/2014, art. 62, caput, inciso XIII | 620 | **7** |

In Q128 the whole IN 1.500 art. 19 is a long list of incisos. Its S1 vector is diluted and ranks
590th, while S2 matches the one inciso at rank 1. This is the S2 case of the strategy doc (§5.1).

**S1 has the whole cited article, S2 only a part** (107 whole-article gold items; the reverse
happens for 2):

| Q | Gold | S1 full rank | S2 first part | S2 whole article |
|---|---|---:|---:|---:|
| 001 "Quem está obrigado a apresentar a Declaração de Ajuste Anual…?" | IN RFB 2.178/2024, art. 2º | 4 | 2 | 37 |
| 005 (CNPJ of associations) | IN RFB 2.178/2024, art. 2º | 4 | 1 | 41 |
| 031 ("Meu Imposto de Renda") | IN RFB 2.178/2024, art. 5º | 2 | 1 | 26 |

Here S2 shows its failure mode. In Q005 its top text is art. 2º, § 3º (a taxpayer may not appear
in more than one return). That is a sibling unit of the cited article, but not the provision that
answers the CNPJ question, and the whole article that holds the answer only comes at rank 41. S1
ranks the whole article 4th. A matching fragment can crowd out the article that holds the answer.
The nugget evaluation will show how often a partial hit is still enough.

## 7. Next steps

- Phase 1b (optional): BM25 baseline and the instruction ablation, to check that the S1/S2
  pattern is not specific to this embedding model.
- Phase 2: context formatting (`prompts/context_v1.pt.md`), closed-book and oracle contexts.
  Selection is already implemented and tested (`ragpipe/context.py`).
- Rerun `retrieve` + `evaluate` whenever the corpus gaps of §4 are fixed. The manifests record
  the chunk and dataset hashes, so results of different fix levels cannot be mixed up.
