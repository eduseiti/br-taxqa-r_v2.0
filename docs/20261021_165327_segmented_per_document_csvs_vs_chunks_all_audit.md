# Segmented folder: per-document CSVs vs `chunks_all.csv` — audit

**Generated:** 2026-10-21 16:53:27 (local time, from `date +%Y%m%d_%H%M%S`).
**Question:** shouldn't every `.csv` under `segmented/statutory/` and `segmented/non_statutory/` be in
`segmented/chunks_all.csv(.gz)`? Some seemed to be missing.
**Answer:** all the content that should be in `chunks_all` is there. 75 of the 700 per-document CSVs are not in
it: 69 are leftovers of documents removed from the corpus on purpose, and 6 are annexes with no text.
**Status:** investigation only; **no files changed**. The cleanup (§4) is left for later.

## 1. Method

`segmented/chunks_all.csv` (last built 2026-10-09 12:57, `run_info.json`; 104,574 rows) was matched to the
per-document CSVs by its `arquivo` column (the LexML file of each chunk, e.g. `lei_9250_19951226.xml` →
`statutory/lei_9250_19951226.csv`).

| | Count |
|---|---:|
| Per-document CSVs (`statutory/` 276 + `non_statutory/` 424) | 700 |
| Distinct `arquivo` values in `chunks_all` | 625 |
| `arquivo` values without a per-document CSV | 0 |
| **Per-document CSVs with no row in `chunks_all`** | **75** (statutory 20, non-statutory 55) |

## 2. The 69 leftovers: documents removed from the corpus

| Document | CSVs | Rows | File date | Why it was removed |
|---|---:|---:|---|---|
| `in_rfb_1911_20191011` (IN RFB 1.911/2019, PIS/Cofins; main + 60 annexes) | 61 | 4,351 in the main file | main 2026-10-08, annexes 2026-09-25 | Never cited; v1's wrong match for IN RFB 1.997/2019 (the Q025 reference was dropped). The largest distractor in the corpus (≈ 5 % of the S3 rows) |
| `in_rfb_1505_20141031` (main + 4 annexes) | 5 | 7 in the main file | 2026-09-25 | Cited only by Q081's dropped hallucinated reference |
| `decreto_7030_20091214` (Vienna Convention on the Law of Treaties) | 1 | 3 | 2026-09-25 | Cited only by the wrong reference 144-05 (Q144 means the diplomatic-relations convention, Decreto 56.435); its "Artigo N" numbering was also not parsed (3 of 85 articles) |
| `lei_3071_19160101` (Código Civil de 1916) | 1 | 3,095 | 2026-10-08 | Cited nowhere; came from the fetcher's `fetched_documents`; 25 duplicate article ids |
| `lei_5869_19730111` (CPC de 1973) | 1 | 3,748 | 2026-10-08 | Cited nowhere (the answers cite the CPC of 2015, Lei 13.105) |

- Decision: `docs/20261008_190226_reference_fixes_and_label_only_articles_investigation.md` (§2, items O2/O3, and the
  recommendation "remove `in_rfb_1911_20191011`, `in_rfb_1505_20141031`, `decreto_7030_20091214` and … `lei_3071_19160101`
  and `lei_5869_19730111`"). Applied in the 2026-10-09 rebuild (`docs/20261009_121822_nonstat_reparse_decision_and_pipeline_rerun_log.md`).
- These documents are no longer in `original/` or `lexml/`, and no question in `dataset/questions.jsonl` references them.
- **Why their CSVs are still there:** `scripts/segmentation/segment_all.py` (run with `--overwrite`) writes the
  outputs of the documents present in `lexml/` and builds `chunks_all` from them. It never deletes the per-document
  outputs of documents that are gone. 46 matching `.prov.jsonl` provenance files are leftovers too.
- The pipeline reads only `chunks_all.csv(.gz)` (`segmented/README.md`: "Use this one"), so the leftovers do not reach
  embedding or retrieval.

## 3. The 6 empty annexes: documents still in the corpus

All six CSVs were written by the last run (2026-10-09) with 0 rows; `annex_manifest.csv` records them as
`DocumentoGenerico`, category C, 0 chunks.

| Annex | XML content | Source `.docx` | Content lost? |
|---|---|---|---|
| `in_rfb_1585_20150831.anexo1`, `anexo2`, `anexo3` | the title only ("ANEXO I"…) | the headings only; the annexes are 3 embedded images | **No** (no text to extract) |
| `in_rfb_1500_20141029.anexo19` | "ANEXO XI" | "[Incluído(a) pelo(a) Instrução Normativa RFB nº 2299, de 17 de dezembro de 2025]" and nothing else | **No** (an empty 2025 insertion, after the P&R date anyway) |
| `in_srf_208_20020927.anexo1` | "ANEXO I" | **repeated heading**: "ANEXO I", then "Anexo I" + the "Tabela de Atualização do Custo de Bens e Direitos" | **No**: the table is in `anexo2.xml` (7,648 chars), which is in `chunks_all` (TAB chunk) |
| `in_srf_81_20011011.anexo1` | "ANEXO I" | same repeated heading and table | **No**: the table is in `anexo2.xml` (7,691 chars), in `chunks_all` |

**Side effect in IN SRF 208/2002 and IN SRF 81/2001.** The parser opens a new annex at each heading, so the repeated
heading creates an empty `anexo1`. Every later annex file is then shifted by one: legal Anexo I is `anexo2`, and
legal Anexo II is split into `anexo3` (title + header) and `anexo4` (the form). The URNs of those chunks carry the
shifted number. **No gold reference points to an annex of these two INs** (`dataset/references.jsonl`), so the
legal-provision retrieval evaluation is not affected today.

The segmentation report's `non_empty` check (`segmentation_report.md`: count 0) validates `chunks_all`, not the
per-document files. That is why it does not list these six.

## 4. Possible cleanup (not done; for later)

1. **Delete the 69 leftover CSVs and their 46 `.prov.jsonl` files** (§2). No effect on the pipeline; the folder
   then matches `chunks_all`. Look at the list again before deleting.
2. **Make `segment_all.py` delete per-document outputs whose document is no longer in `lexml/`**, or warn about
   them, so later rebuilds do not leave stale files.
3. **Optional:** make the parser ignore a repeated annex heading (IN SRF 208, IN SRF 81), so the cost-update tables get
   the `anexo1` URN. Needed only if a reference to these annexes is ever added. This is a re-parse plus
   re-segmentation of two documents, and their embeddings would change.
4. Optionally, add a check to `validate_segments.py`: every per-document CSV is either in `chunks_all` or listed as
   empty (0 chunks) in `annex_manifest.csv`.
