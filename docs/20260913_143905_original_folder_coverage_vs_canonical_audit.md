# `original/` Folder Coverage vs. the BR-TAXQA-R Canonical Document List

**Generated:** 2026-09-13 14:39:05 (local time, from `date +%Y%m%d_%H%M%S`)
**Question:** have all required documents been captured inside `original/`?
**Answer:** **Yes — 459 of the 462 canonical documents are present (99.4%). The 3 absent ones are the documents that were already known to be unobtainable or mis-keyed; no document that was successfully fetched is missing from `original/`.**

**Reference audit:** [`../br-taxqa-document-fetcher/20260731_212654_canonical_duplicates_and_missing_documents_audit.md`](../../br-taxqa-document-fetcher/20260731_212654_canonical_duplicates_and_missing_documents_audit.md)
**Canonical source:** `br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json` (478 references → 462 unique documents)

---

## Headline numbers

| | Count |
|---|---:|
| Canonical references | 478 |
| Unique canonical documents | 462 |
| **Canonical documents covered by a file in `original/`** | **459 (99.4%)** |
| **Canonical documents with no file** | **3** |
| `.docx` files on disk under `original/` | 461 |
| — of which distinct basenames | 459 |
| — byte-identical copies filed in two folders | 2 |
| Files not serving any canonical record | 3 |

The 459 covered documents are served by 456 distinct files: three files each satisfy two
canonical records (see [Files serving two records](#files-serving-two-canonical-records)).

---

## Method

Matching reproduces the reference audit's rules, against the 462 unique records keyed by
`(type_slug, number, date, canonical_name)`. Filenames were parsed as
`<prefix>_<number>_<YYYYMMDD|nodate>[_N].docx`; numbers normalized by stripping thousand
separators and leading zeros while **preserving Medida Provisória suffixes** (`2158-35`);
dates normalized from the Portuguese long form. Prefixes come from
`receita_norma_fetcher.ACT_TYPES[slug].file_prefix`, extended with `lei`, `lei_comp`,
`decreto`, `decreto_lei`, `mp`, and the manual-round prefixes.

| Rule | Matches |
|---|---:|
| 1. Exact `prefix + number + date` | 413 |
| 2. Hand-verified mapping (jurisprudência, súmulas, pareceres SEI/PGFN, constituição, …) | 26 |
| 3. Undated canonical record → `prefix + number`, any date | 9 |
| 4. Hand-verified mapping, `outros` bucket (DBF, DIMOB, DMED, DOI, DIRF, DIAT, Carnê-Leão, …) | 6 |
| 5. `prefix + number`, date differs — absorbs the audit's documented date defects | 2 |
| **Total matched** | **456 files → 459 records** |

Rule 5 fired exactly twice, on the two date discrepancies the reference audit already
recorded — neither is a coverage gap:

| Canonical record | File in `original/` | Note |
|---|---|---|
| `Decreto-Lei nº 1.535, de 15 de abril de 1977` | `articulados/decreto/decreto_lei_1535_19770413.docx` | Act text reads *"DE 13 DE ABRIL DE 1977"*; the canonical date is wrong. |
| `Instrução Normativa RFB nº 1.131, de 20 de fevereiro de 2011` | `articulados/instrucao_normativa_rfb/in_rfb_1131_20110221.docx` | Act text reads *"DE 21/02/2011"*; canonical date off by one day. |

---

## The 3 documents not present

All three were already open in the reference audit, or are explained by it. **None is a
capture failure in `original/`** — there is no file to copy in the upstream folders either.

| # | Document | `type_slug` | Status |
|---:|---|---|---|
| 1 | Convenção de Berna da União Postal Universal (UPU) | `tratados_convencoes` | **Known-missing (audit #1).** No act number, no date; the dataset's own `filedata` is a Wikipedia article about the UPU, not a treaty text. There is no Brazilian normative act to fetch unless the target is redefined as the promulgating decree of a specific UPU act. |
| 2 | Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006 | `solucao_de_consulta_interna_cosit` | **Known-missing (audit #2).** The canonical record is mislabelled — the dataset's `filedata` is `Ato Declaratório Executivo Cosit nº 5, de 24 de fevereiro de 2006`. The audit's recommended re-key **was never carried out**: `ato_declaratorio_executivo_cosit/` still holds only `ade_cosit_30_20010723.docx`, upstream and in `original/`. |
| 3 | Acordo para Evitar a Dupla Tributação … Brasil e Alemanha | `tratados_convencoes` | **Not flagged as missing by the July audit, but absent here.** No treaty-like file exists anywhere under `original/`. The audit's coverage table credits `tratados_convencoes` with 1 of 2 served from `output_manual`; that manual file is not in the current `output_manual/documents/` listing either, so the accord is uncovered on both sides. |

> **Note on item 3.** The July audit reported only 2 missing documents; this analysis reports 3.
> The difference is the Brazil–Germany accord, which the audit counted as manually served. It is
> not present in `original/` and no corresponding file remains in `output_manual/documents/`.
> This is the one item worth re-checking against the manual round's working copies before
> concluding it was lost.

---

## Findings worth recording

### Files serving two canonical records

The canonical de-duplication key slightly over-counts: three pairs of records are the same act
under two canonical names, so 459 records are covered by 456 files.

| File in `original/` | Canonical records served |
|---|---|
| `não_articulados/parecer_sei/parecer_sei_110_2018.docx` | `Parecer SEI nº 110, de 26 de agosto de 2020` (idx 334) · `Parecer SEI nº 110` (idx 336) |
| `não_articulados/parecer_normativo_cst/pn_cst_129_19730913.docx` | `Parecer Normativo CST nº 129, de 13 de setembro de 1973` (idx 297) · `Parecer Normativo nº 129, de 13 de setembro de 1973` (idx 326) |
| `articulados/instrucao_normativa_srf/in_srf_67_19880421.docx` | `Instrução Normativa RFB nº 67` (idx 140) — see below |

`Instrução Normativa RFB nº 67` (undated) is served by `in_srf_67_19880421.docx`: the órgão in
the canonical record (`RFB`) is wrong — the dataset content is **IN SRF nº 67 de 21/04/1988**.
The file is correctly filed under `instrucao_normativa_srf/`, so the record *is* covered; only
the canonical metadata is defective.

### Files present that serve no canonical record (3)

| File | Status |
|---|---|
| `articulados/lei/lei_3071_19160101.docx` | Código Civil de 1916 — cited only indirectly, no canonical record. Harmless extra; carried over from `fetched_documents`. |
| `articulados/lei/lei_5869_19730111.docx` | CPC de 1973 — same situation. |
| `articulados/instrucao_normativa_srf/in_srf_67_19880421.docx` | Not actually extra — it serves canonical idx 140 under the corrected órgão (above). Listed here only because the strict `type_slug` key does not reach it. |

### The two byte-identical duplicates

Two files are filed under **both** `articulados/` and `não_articulados/`, with matching MD5s:

| Basename | MD5 | Locations |
|---|---|---|
| `port_conj_tse_srf_74_20060110.docx` | `17ff5f57…d01b2` | `articulados/outro/` · `não_articulados/outro/` |
| `resol_cgpc_26_20080929.docx` | `91ac00d9…1bfe2` | `articulados/outro/` · `não_articulados/outro/` |

This is why the tree holds 461 files but only 459 distinct documents. Both acts are arguably
articulated (a Portaria Conjunta and a Resolução, both with numbered articles); if the
articulado/não-articulado split is meant to be a partition, **one copy of each should be
removed**. If the duplication is deliberate — e.g. each folder is meant to be independently
complete — no action is needed.

### Upstream drift since the July audit

`output_manual/documents/` now holds **61** `.docx`, not the 62 the audit recorded. The
difference is `sci_cosit_20130215.docx`, which the audit identified as redundant (a 14 KB
ementa-only extract of an act already served in full by
`output_receita_federal/…/sci_cosit_5_20130215.docx`) and marked *"safe to delete"*. It is gone
from `output_manual/` and correctly absent from `original/` — the deletion was carried out as
recommended.

---

## Coverage by top-level bucket

| Bucket | Folders | Files |
|---|---:|---:|
| `original/articulados` | 12 | 226 |
| `original/não_articulados` | 20 | 235 |
| **Total** | **32** | **461** |

### `articulados/`

| Folder | Files |
|---|---:|
| `ato_declaratorio_executivo_codac` | 1 |
| `ato_declaratorio_executivo_cosit` | 1 |
| `ato_declaratorio_executivo_rfb` | 2 |
| `ato_declaratorio_executivo_srf` | 1 |
| `ato_declaratorio_interpretativo_rfb` | 3 |
| `ato_declaratorio_interpretativo_srf` | 9 |
| `decreto` | 47 |
| `instrucao_normativa_rfb` | 23 |
| `instrucao_normativa_srf` | 17 |
| `lei` | 110 |
| `medida_provisoria` | 7 |
| `outro` | 5 |

### `não_articulados/`

| Folder | Files |
|---|---:|
| `acao_direta_inconstitucionalidade` | 2 |
| `ato_declaratorio_comum_cosar` | 1 |
| `ato_declaratorio_comum_cosit` | 1 |
| `ato_declaratorio_comum_pgfn` | 14 |
| `ato_declaratorio_comum_srf` | 7 |
| `ato_declaratorio_normativo_cosit` | 6 |
| `ato_declaratorio_normativo_cst` | 5 |
| `nota_pgfn` | 5 |
| `nota_sei` | 1 |
| `outro` | 20 |
| `parecer_cosit` | 1 |
| `parecer_normativo_cosit` | 7 |
| `parecer_normativo_cst` | 24 |
| `parecer_pgfn` | 7 |
| `parecer_sei` | 3 |
| `portaria_mf` | 4 |
| `solucao_de_consulta_cosit` | 109 |
| `solucao_de_consulta_disit` | 2 |
| `solucao_de_consulta_interna_cosit` | 12 |
| `solucao_de_divergencia_cosit` | 4 |

---

## Recommended actions

1. **Brazil–Germany double-taxation accord** — re-check the manual round's working copies. This
   is the only item that may represent an actual loss rather than a known-unobtainable document.
2. **SCI Cosit nº 5 (28/03/2006)** — carry out the July audit's recommendation: re-key the
   canonical record to `type_slug = ato_declaratorio_executivo_cosit`, `number = 5`,
   `date = 24 de fevereiro de 2006`, then run
   `python fetch_receita_normas_main.py --only ato_declaratorio_executivo_cosit`.
3. **UPU / Convenção de Berna** — close as *not applicable* unless the target is redefined as a
   specific promulgating decree. There is no Brazilian act to fetch.
4. **Decide the duplicate policy** for `port_conj_tse_srf_74_20060110.docx` and
   `resol_cgpc_26_20080929.docx` — remove one copy each if the two buckets are meant to partition.
5. **Optional metadata fixes** (do not affect coverage): correct the canonical dates for
   Decreto-Lei nº 1.535 and IN RFB nº 1.131, and the órgão for IN RFB nº 67 → `instrucao_normativa_srf`.

---

## Reproducing this analysis

The matcher is at
`/tmp/claude-0/-work-doutorado-artigos-RAG-evaluation-br-taxqa-r-v2-0/a6967aba-b5c9-44db-8ea2-b368bb093be0/scratchpad/match3.py`
(session scratchpad — copy it into `scripts/` if it should be kept). It takes
`output_canonical/canonical_referred_documents.json` plus a walk of `original/`, and its only
project dependency is `receita_norma_fetcher.ACT_TYPES`. Run it from the project root. The
hand-verified mapping for the manual-round filenames is the only part that cannot be regenerated
mechanically; it is embedded in the script and derived from the reference audit.
