# Corpus exclusion of the revoked RIR/1999 and audit of other revoked documents

**Generated:** 2026-10-22 20:36:25 (local time, from `date +%Y%m%d_%H%M%S`).
**Origin:** the user's hand review of the pilot contexts (Q350, Q503, Q676; RAG Phase 2 gate,
`docs/20261021_210251_rag_phase2_contexts_execution.md` §5) found the RIR/1999 (Decreto nº 3.000, de 1999) next
to the RIR/2018 in the contexts, often ranked above it, although the P&R cites the RIR/1999 only once,
historically.
**Decision (user, 2026-10-22):** exclude it from the retrieval corpus. **Rule:** revoked documents are not part of
this experiment (it is about segmentation, not about telling revoked from current law).
**Done:** the exclusion mechanism, the exclusion of `decreto_3000_19990326`, and the reruns of retrieval,
evaluation and contexts (§2–§3), with the previous corpus kept as an ablation run. **Open:** the other revoked
documents found by the audit (§4) — **decisions for the user**.
**Cost:** $0 (no API call, no re-embedding).

## 1. Analysis

### 1.1 How the RIR/1999 entered the dataset

- One reference: `282-12`, **embedded**, `Decreto nº 3.000, de 1999, art. 39, § 6º`. In the answer of Q282 it appears only
  inside a quoted thesis of a PGFN dispensation (Parecer SEI nº 110/2018/CRJ/PGACET/PGFN-MF, Despacho nº
  348/2020): "por força do art. 6º, XIV, da Lei nº 7.713, de 1988, do art. 39, § 6º, do Decreto nº 3.000, de 1999,
  e do art. 6º, § 4º, III, da IN RFB nº 1.500, de 2014, a isenção … estende-se ao resgate …". The rules in force are in
  Lei 7.713 and IN RFB 1.500, both in the corpus.
- The gold nuggets do not depend on its text: it appears only in the `legal_basis` of `Q282_N03`, next to five other
  sources; the nugget's content is the PGFN dispensation.
- It was revoked as a whole by the Decreto nº 9.580, de 2018 (the RIR/2018, in the corpus). The source `.docx` says
  so in its header ("Revogado pelo Decreto nº 9.580, de 2018").

### 1.2 Its weight in the corpus and in the contexts

It brought 6,960 chunk rows (1,036 S1 units, 6,403 S2 units) — 5 % of the S1 index, about the size of the RIR/2018
itself (1,141 S1 units) — for a single embedded citation. Contexts of the run before the exclusion (merge selection,
`context_v2`):

| Set | Contexts with RIR/1999 | With RIR/2018 | RIR/1999 above RIR/2018, or alone | RIR/1999 share of context tokens |
|---|---:|---:|---:|---:|
| S1 4k | 379 | 342 | 286 | 9.3 % |
| S2 4k | 463 | 469 | 306 | 10.3 % |
| S4 4k | 451 | 459 | 292 | 12.0 % |
| S2 8k | 571 | 574 | 357 | 9.6 % |

A revoked near-duplicate of the current regulation (same rules, other article numbers, sometimes outdated
values) took ≈ 10 % of every context budget and outranked the current text in ≈ 300 of 715 contexts: noise for
the segmentation comparison, and a source of the temporal misgrounding studied in
`docs/20260929_111356_fiscalqa_pro_temporal_misgrounding_comparison.md`.

### 1.3 Why exclude rather than delete

- The reference is real: the dataset (`references.jsonl`, `documents.jsonl`) keeps it.
- Deleting its chunks would change the chunk file's SHA-256, which the embedding manifests pin, so the vectors
  would have to be re-finalized or recomputed. An exclusion only removes its texts from the candidates.
- It is reversible and gives a free ablation (§3).

## 2. Implementation

| File | Change |
|---|---|
| `scripts/rag/corpus_exclusions.yaml` (new) | The list: `decreto_3000_19990326` (rule `revoked`, revoked by Decreto 9.580/2018 art. 4º, superseded by `decreto_9580_20181122`, cited by 282-12), the rule, the decision date |
| `scripts/rag/ragpipe/exclusions.py` (new) | `Exclusions`: load from the YAML or from a retrieval manifest; chunk-row mask of the excluded documents (main and annex files); unknown document ids are an error |
| `ragpipe/retrieval.py` | Reads the list (default file; `--exclusions none` or another path), drops the excluded rows from every strategy index, records `corpus_exclusions` (path, SHA-256, documents, rows) in the manifest and the parameters (config hash); new `--run-name` (output `runs/retrieval/<embedding>/<run name>`, default the instruction) |
| `ragpipe/strategies.py` | `build_index(…, exclude=)`, applied after the expected-rows check (which describes the chunk file) |
| `ragpipe/evaluation.py` | Takes the exclusions from the retrieval manifest; excluded rows are not in any strategy; gold items of an excluded document get `unreachable_reason = excluded_from_corpus` (column `unreachable:excluded_from_corpus` in `reachability.csv`); the manifest lists the excluded documents |
| `ragpipe/contexts.py` | Oracle candidates without excluded rows; output root `runs/contexts/<embedding>/<retrieval run name>` |
| `rag.py`, `ragpipe/data.py` | `retrieve --run-name --exclusions`; `Paths.exclusions` |
| `tests/test_exclusions.py` (new), `conftest.py`, CLI tests | Excluded document absent from rankings and oracle, gold reported as excluded, run-name directories, unknown id error; fixture paths use no exclusion list. **37 passed** |

Commands (`/tmp/…/scratchpad/rerun_exclusion.sh`, 10 min 20 s in total):

```bash
P=.venv/bin/python; R=scripts/rag/rag.py; SETS=<the 13 pilot sets of the Phase 2 note §10>
# ablation: the corpus before the exclusion
$P $R retrieve --embedding jua-4b-mixed --exclusions none --run-name irpf_with_rir1999
$P $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf_with_rir1999
$P $R context  --retrieval runs/retrieval/jua-4b-mixed/irpf_with_rir1999 --sets "$SETS"
# main run, with scripts/rag/corpus_exclusions.yaml
$P $R retrieve --embedding jua-4b-mixed --force
$P $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf --force
$P $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf --dedup containment --eval-id v2d_either_containment_skip --force
$P $R context  --retrieval runs/retrieval/jua-4b-mixed/irpf --sets "$SETS" --force
$P $R context  --retrieval runs/retrieval/jua-4b-mixed/irpf --sets S2@budget=4000 --template context_v1 --force
```

Checks: the ablation run reproduces the previous headline exactly (S1 → S2 article recall +0.1113, the value of the
Phase 2 note §9), so the code change does not alter a run without exclusions. Main run: 6,960 chunk rows excluded
(S1 20,461 rows, S2 68,656, S3 72,061; candidate texts 20,422 / 68,501 / 71,906); contexts ↔ evaluation 0
mismatches in both runs; no RIR/1999 chunk in any context; Q282's RIR/1999 gold item is `excluded_from_corpus` at
the three levels (1 item each).

**Run layout now:**

| Run | Corpus | Headline evaluation | Contexts |
|---|---|---|---|
| `runs/retrieval/jua-4b-mixed/irpf` | **without the RIR/1999 (main)** | `eval/either_containment_merge_skip`; Phase 1 rule `eval/v2d_either_containment_skip` | `runs/contexts/jua-4b-mixed/irpf/` (13 sets + `S2_budget4000_context_v1`) |
| `runs/retrieval/jua-4b-mixed/irpf_with_rir1999` | as before (ablation) | `eval/either_containment_merge_skip` | `runs/contexts/jua-4b-mixed/irpf_with_rir1999/` (13 sets) |

The older evaluations in `irpf/eval/` (`either_containment_skip` of 2026-09-28, `v2c_…` of 2026-10-08) belong to
earlier chunk files and are stale.

## 3. Effect on the legal-provision test (budget view, all gold, merge selection)

| Article recall | 2k: with → without RIR/1999 | 4k | 8k |
|---|---|---|---|
| S1 | 0.266 → 0.296 (+0.030) | 0.383 → **0.398** (+0.015) | 0.480 → 0.492 |
| S2 | 0.402 → 0.425 (+0.023) | 0.495 → **0.503** (+0.009) | 0.587 → 0.600 |
| S3 | 0.400 → 0.424 | 0.494 → **0.507** (+0.013) | 0.584 → 0.606 |
| S2c | 0.372 → 0.391 | 0.468 → 0.480 (+0.012) | 0.567 → 0.579 |
| S4 | 0.364 → 0.397 | 0.468 → 0.487 (+0.020) | 0.564 → 0.593 |

Provision recall gains +0.011 to +0.034, document recall +0.008 to +0.033, article context precision +0.004 to
+0.029; every strategy and budget improves. Paired comparisons, article recall at 4k:

| Pair | With RIR/1999 | Without (main) |
|---|---|---|
| S1 → S2 | +0.111 (0.090–0.135) | **+0.105** (0.083–0.129), p < 0.001 |
| S2 → S3 | −0.001 (n.s.) | +0.004 (−0.004–0.012, p = 0.34) |
| S2 → S2c | −0.027 (−0.043 to −0.011) | −0.023 (−0.039 to −0.007), p = 0.006 |
| S3 → S4 | −0.026 (−0.042 to −0.011) | −0.020 (−0.036 to −0.004), p = 0.014 |
| S1 → S2c | +0.085 | +0.082 |

The conclusions do not change; S1 gains slightly more than S2 at small budgets (whole-article RIR/1999 units took
proportionally more of an S1 context), so the S1 → S2 gap narrows by 0.006. The contexts now contain the RIR/2018
in 474 of the S2 4k contexts (469 before).

## 4. Audit: other revoked documents (rule of the user: revoked documents only)

**Method** (`/tmp/…/scratchpad/revoked_audit.py`): the header of every source document (`original/`, text before
the first article or the first 1,500 characters) scanned for whole-document status notes — "Revogado(a) pelo(a)",
"Sem eficácia", "Perdeu a eficácia", "Vigência encerrada", "Convertida na Lei", "Rejeitada"; the 12 PDF-sourced
soluções de consulta checked in `lexml/nao_articulados/_text/`. Planalto and the RFB normas site put these notes
right under the epígrafe (e.g. "[Revogado(a) pelo(a) Instrução Normativa RFB nº 2172, de 9 de janeiro de 2024]").
Partial revocations (single articles) are out of scope. 14 documents carry a note; 3 are false positives.

### 4.1 Revoked as a whole before the P&R date (2024-05-03) — the rule applies

| Document | Revoked by (date; in the corpus?) | References | Corpus size (S1 / S2 units) |
|---|---|---|---|
| `decreto_3000_19990326` (RIR/1999) | Decreto 9.580, 2018 (yes) | 1 embedded (Q282) | 1,036 / 6,403 — **excluded** |
| `in_rfb_1548_20150213` (CPF) | IN RFB 2.172, 2024-01-09 (yes, `in_rfb_2172_20240109`) | **2 explicit** (Q058, Q059) | 99 / 422 |
| `in_rfb_1717_20170717` (restituição, compensação) | IN RFB 2.055, 2021-12-06 (yes, `in_rfb_2055_20211206`) | **2 explicit** (Q053, Q074) | 242 / 1,046 |
| `in_srf_118_20001228` (ganho de capital em moeda estrangeira) | IN RFB 2.180, 2024-03-11 (yes, `in_rfb_2180_20240311`) | 13: **11 explicit** (Q264, Q456, Q459, Q461, Q558, Q560, Q617–Q621, Q623) | 21 / 90 |
| `in_srf_76_20010918` (restituição pela rede arrecadadora) | IN RFB 2.155, 2023-08-04 (**no**) | **1 explicit** (Q070) | 15 / 53 |
| `ad_pgfn_1_20090327` | AD PGFN 2, 2016-03-10 (yes, `ad_pgfn_2_20160310`) | 2 embedded (Q230, Q316) | 2 / 2 |
| `pn_cst_36_19770530` (despesas médicas) | ADE RFB 4, 2014-08-05 (no) | 1 embedded (Q364) | 9 / 9 |

### 4.2 Not in force on 2024-05-03 for another reason (not "revoked")

| Document | Status | References | Size |
|---|---|---|---|
| `mp_252_20050615` | "Sem eficácia": lapsed in 2005, not converted | 1 embedded (Q630) | 75 / 369 |
| `mp_497_20100727` | converted into Lei 12.350, 2010 (in the corpus) | 1 embedded (Q248) | 36 / 169 |
| `mp_670_20150310` | converted into Lei 13.149, 2015 (in the corpus) | 1 embedded (Q248) | 5 / 5 |

### 4.3 Revoked after the P&R date — in force for the P&R, kept

`in_rfb_1888_20190503` (criptoativos; revoked by IN RFB 2.291 of 2025-11-14; 4 references) and
`in_rfb_2066_20220224` (Centro Virtual de Atendimento; revoked by IN RFB 2.320 of 2026-04-06; 3 references). The
documents were fetched in 2026, so their headers show later revocations; they were in force on 2024-05-03.

### 4.4 False positives

`lei_13043_20141113` ("Vigência encerrada" refers to MP 1.303/2025, which amended it), `pn_cst_179_19700727` (its
text says another decree was revoked), `sc_cosit_75_20200625` (a body sentence: "esse dispositivo não foi
revogado").

### 4.5 The difference with the RIR/1999, and the decisions for the user

The RIR/1999 case was clear-cut: a historical, embedded mention, a 5 % share of the corpus, and the current version
in the corpus. **Four of the revoked documents are different: the P&R 2024 cites them as the explicit legal basis of
its answers** (17 questions: IN RFB 1.548, IN RFB 1.717, IN SRF 118, IN SRF 76). The P&R was not updated after their
revocation (IN SRF 118 was revoked two months before the P&R date; Q617–Q623 cite it next to its replacement IN RFB
2.180). Excluding them:

- makes their gold items unreachable (`excluded_from_corpus`) in 17 questions, for the retrieval test and the
  legal-provision score of the answers;
- leaves the generator only the replacement act for 16 of them (IN 2.172, 2.055, 2.180 are in the corpus; IN 2.155,
  the replacement of IN SRF 76, is not, so Q070 would lose its basis);
- does not change the nuggets (they come from the answer text).

Their corpus weight is small (≈ 380 S1 units together, 1.8 % of the index), so keeping them biases the segmentation
comparison far less than the RIR/1999 did.

Decisions:

1. **Embedded / historical revoked documents** (`ad_pgfn_1_20090327`, `pn_cst_36_19770530`): exclude, like the
   RIR/1999 (same rule, 11 S1 units, 3 embedded references). **Recommended.**
2. **Revoked documents the P&R cites as explicit legal basis** (`in_rfb_1548_20150213`, `in_rfb_1717_20170717`,
   `in_srf_118_20001228`, `in_srf_76_20010918`): **keep (recommended)** — they are the basis of the gold answers,
   and excluding them would remove the gold of 17 questions — and report them as a dataset property (the P&R cites
   revoked norms), with a slice in the results. The strict reading of the rule (exclude every revoked document)
   is the alternative; it is one line each in `corpus_exclusions.yaml` and a 10-minute rerun.
3. **MPs no longer in force** (`mp_252_20050615` lapsed; `mp_497_20100727`, `mp_670_20150310` converted): not
   revoked, so outside the rule as stated; all three are embedded, single-question references. Recommendation:
   treat the lapsed MP 252 like a revoked document (exclude) and keep the converted MPs out of the rule (their text
   lives on in the conversion laws, both in the corpus, and they are tiny: 41 S1 units). Your call.

Whatever is decided, the exclusion rule and the list go into the paper's corpus description, and the ablation run
(`irpf_with_rir1999`) gives the with/without numbers.
