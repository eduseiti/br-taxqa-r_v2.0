# Segmentation report

- Generated: 2026-10-08T00:41:16
- Overall: **OK**
- Command: `python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change --variants caput --frozen /tmp/claude-0/-work-doutorado-artigos-RAG-evaluation-br-taxqa-r-v2-0/24a96df7-849b-42d8-8bd9-be98b91c2eda/scratchpad/frozen/chunks_all.csv.gz --frozen-lexml-rev 0ce50c5`
- Flags: `{"only": null, "overwrite": true, "jobs": 16, "max_tokens": 1024, "tokenizer": "max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B", "ementa_max_tokens": 128, "keep_dropped_min_chars": 300, "allow_count_change": true, "out_dir": "/work/doutorado/artigos/RAG_evaluation/br-taxqa-r_v2.0/segmented", "grouping_max_tokens": 8192, "skip_validation": false, "variants": "caput", "frozen": "/tmp/claude-0/-work-doutorado-artigos-RAG-evaluation-br-taxqa-r-v2-0/24a96df7-849b-42d8-8bd9-be98b91c2eda/scratchpad/frozen/chunks_all.csv.gz", "frozen_lexml_rev": "0ce50c5"}`
- Saxon: SaxonC-HE 13.0 from Saxonica; annex categories: {'A': 12, 'B': 50, 'C': 179}
- Code: {"commit": "bf79a583e23bd114d93cba7dcc20b8d6789fddde", "branch": "main", "dirty": true, "dirty_files": ["M scripts/segmentation/README.md"]}
- Output checksums (sha256): {"chunks_all.csv": "9ddfa9abb25a18e8bd13aa5980745c306c9f91de4c0005ff98adf38fa6e2c876", "chunks_all.csv.gz": "d1b9cf7e2dbbdaa269c332bf7e5ac4b70f8d465a417a7e71c58d7ff1dcb525ff", "groupings_over_limit.csv": "7c754784db0c1bf164c05546856a4dc5a4ff27ab36cc369d17419dcfe14c3bea", "annex_manifest.csv": "2d87cb3a8e40d6c988113a4576ed010f7c11044553632ba384707e4c0395076d"}
- Timings (s): {'1_router_s': 1.8, '2_metadata_s': 1.5, '3_xsl_s': 25.4, '3b_4_split_loose_s': 9.1, '5_non_statutory_s': 4.5, '6_merge_s': 19.2, 'total_s': 62.2}

## Checks

| Check | Result | Detail |
|---|---|---|
| csv_schema | ok | {"detail": "chunks_all columns = 29 (6 + 3 + 16 provenance + 3 token counts + texto_sha256)"} |
| non_empty | ok | {"count": 0} |
| texto_sha256 | ok | {"count": 0} |
| chunk_id_unique | ok | {"dup_chunk_id": 0, "dup_urn_not_ambiguous": 0} |
| provenance | ok | {"count": 0, "by_kind": {"provenance_missing_id": 0, "provenance_ancestors": 0}} |
| intervals | ok | {"count": 0, "by_kind": {"interval_inverted": 0, "intervals_crossing": 0, "sub_outside_article": 0, "part_outside_unit": 0}} |
| coverage | ok | {"count": 0, "by_kind": {"coverage_art": 0, "coverage_dsp": 0, "coverage_parts": 0, "coverage_agrupamento": 0, "coverage_table": 0}} |
| cap | ok | {"count": 0, "by_kind": {"cap_unflagged": 0, "cap_hard_limit": 0}} |
| split_complete | ok | {"count": 0, "by_kind": {"split_incomplete": 0}} |
| text_coverage | ok | {"count": 0, "by_kind": {"text_coverage": 0}, "min": 0.9983} |
| grouping_limit | ok | {"limit": 8192, "listed": 243, "over_limit_in_chunks_all": 0, "listed_and_in_chunks_all": 0} |
| variant_twins | ok | {"count": 0, "variants": 30166} |
| base_no_caput | ok | {"count": 0} |
| diff_vs_frozen | ok | {"report_only": true, "lexml_rev": "0ce50c5", "files_unchanged_lexml": 569, "files_changed_or_new_or_removed": 147, "rows_compared": 75979, "rows_text_differs": 0, "rows_only_new": 0, "rows_only_frozen": 0} |

## Rows

- Total base rows: 88600 in 672 files; rows per variant: {'base': 88600, 'caput': 30166}
- Per strategy: {'S1': 26364, 'S2': 83496, 'S3': 88600, 'S2C': 83496, 'S4': 88600}

| Tipo | Rows | ref p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| PAR | 21813 | 150 | 253 | 482 | 5776 |
| INC | 20867 | 169 | 285 | 473 | 3967 |
| ART | 20662 | 194 | 678 | 1008 | 1024 |
| CPT | 8209 | 162 | 356 | 1009 | 8103 |
| ALI | 4938 | 174 | 299 | 461 | 1420 |
| TXT | 3497 | 305 | 981 | 1020 | 1024 |
| SEC | 2128 | 584 | 2098 | 5471 | 7827 |
| CAP | 1863 | 822 | 3583 | 7252 | 7941 |
| DSP | 1519 | 149 | 594 | 911 | 1009 |
| ITE | 1305 | 157 | 286 | 419 | 1358 |
| SSC | 714 | 498 | 1885 | 4230 | 7771 |
| TAB | 686 | 370 | 981 | 1022 | 1163 |
| TIT | 328 | 1556 | 6009 | 7923 | 8102 |
| LIV | 45 | 1613 | 5869 | 8096 | 8119 |
| SBT | 21 | 3753 | 6829 | 7839 | 8061 |
| PRT | 5 | 2320 | 6129 | 7303 | 7433 |

Tokens per tokenizer (p50 / p99 / max):

| Tipo | cl100k_base | Qwen3 |
|---|---|---|
| ALI | 166 / 425 / 1257 | 174 / 461 / 1420 |
| ART | 186 / 964 / 1023 | 194 / 1007 / 1024 |
| CAP | 788 / 7029 / 7697 | 822 / 7252 / 7941 |
| CPT | 155 / 934 / 7613 | 162 / 1009 / 8103 |
| DSP | 143 / 856 / 995 | 149 / 911 / 1009 |
| INC | 160 / 439 / 2759 | 169 / 473 / 3967 |
| ITE | 150 / 394 / 1358 | 157 / 418 / 1358 |
| LIV | 1579 / 7791 / 7833 | 1613 / 8096 / 8119 |
| PAR | 142 / 459 / 4205 | 150 / 482 / 5776 |
| PRT | 2293 / 7102 / 7225 | 2320 / 7303 / 7433 |
| SBT | 3565 / 7460 / 7668 | 3753 / 7839 / 8061 |
| SEC | 562 / 5231 / 7827 | 582 / 5471 / 7817 |
| SSC | 470 / 4004 / 7436 | 498 / 4230 / 7771 |
| TAB | 332 / 966 / 1142 | 370 / 1022 / 1163 |
| TIT | 1478 / 7760 / 7895 | 1556 / 7923 / 8102 |
| TXT | 293 / 998 / 1024 | 305 / 1020 / 1024 |

- Per category: {'main': 72861, 'A': 11212, 'nao_articulado': 2997, 'B': 1041, 'C': 489}

## Split units (cap 1024)

- ART/DSP units split: 655 into 1746 parts ({'ART': 646, 'DSP': 9}); within-leaf splits: 70; truncated HEAD (D3): 8
- Non-statutory TXT/TAB units split: 319
- Uncuttable over-cap rows: 1

| Unit | Tokens | Parts | Leaf split |
|---|---:|---:|---|
| lei_10865_20040430, Art. 8º | 16239 | 26 | yes |
| in_rfb_1343_20130405, Art. 9º | 14415 | 21 | yes |
| decreto_9580_20181122.anexo1, Art. 35. | 10238 | 12 |  |
| lei_comp_123_20061214, Art. 18. | 9947 | 15 |  |
| lei_9718_19981127, Art. 5º | 6997 | 11 |  |
| lei_12973_20140513, Art. 2º | 6846 | 9 | yes |
| resol_cgsn_140_20180522, Art. 25. | 6771 | 10 |  |
| lei_8036_19900511, Art. 20. | 5978 | 7 |  |
| decreto_3000_19990326, Art. 39. | 5919 | 7 |  |
| decreto_9358_20180430.anexo3, Art. 38. | 5839 | 7 |  |
| lei_10522_20020719, Art. 10-A. | 5530 | 10 |  |
| lei_10833_20031229, Art. 3º | 5481 | 7 |  |
| lei_12431_20110624, Art. 1º | 5475 | 12 |  |
| lei_10865_20040430, Art. 21. | 5422 | 7 | yes |
| lei_11727_20080623, Art. 32. | 5212 | 7 | yes |
| lei_9481_19970813, Art. 1º | 5135 | 7 |  |
| lei_6015_19731231, Art. 167. | 4987 | 6 |  |
| in_rfb_1911_20191011, Art. 258. | 4747 | 7 | yes |
| lei_comp_123_20061214, Art. 18-A. | 4665 | 7 |  |
| decreto_9580_20181122.anexo1, Art. 881. | 4654 | 7 |  |
| in_rfb_1911_20191011, Art. 25. | 4376 | 6 |  |
| lei_10865_20040430, Art. 28. | 4307 | 6 |  |
| constituição_1988_19881005, Art. 100. | 4288 | 6 |  |
| lei_11941_20090527, Art. 26. | 4101 | 5 | yes |
| decreto_lei_1535_19770413, Art. 1º | 4050 | 5 | yes |
| lei_12249_20100611, Art. 65. | 4022 | 7 |  |
| lei_9250_19951226, Art. 8º | 3822 | 5 |  |
| constituição_1988_19881005, Art. 5º | 3765 | 5 |  |
| lei_9430_19961227, Art. 74. | 3652 | 5 |  |
| resol_cgsn_140_20180522, Art. 15. | 3652 | 5 |  |
| lei_11941_20090527, Art. 35. | 3632 | 5 | yes |
| lei_8036_19900511, Art. 9º | 3534 | 5 |  |
| in_rfb_1500_20141029, Art. 62. | 3527 | 5 |  |
| lei_13254_20160113, Art. 4º | 3474 | 6 |  |
| lei_10833_20031229, Art. 76. | 3470 | 5 |  |
| lei_comp_123_20061214, Art. 13. | 3461 | 5 | yes |
| lei_9615_19980324, Art. 18-A. | 3409 | 5 |  |
| lei_11482_20070531, Art. 1º | 3344 | 5 |  |
| lei_12249_20100611, Art. 114. | 3303 | 4 | yes |
| lei_6015_19731231, Art. 213. | 3298 | 5 |  |
| … 615 more (see segmentation_report.json) | | | |

## Over-cap rows that are not split (Q7)

Grouping chunks above 8192 tokens are not in chunks_all.csv (S3 option 2): 243 listed in `groupings_over_limit.csv` {'TIT': 84, 'CAP': 76, 'LIV': 43, 'SEC': 19, 'PRT': 13, 'SBT': 5, 'SSC': 3}. The table counts the rows kept.

| Tipo | Rows | > cap | ≥ 8,192 |
|---|---:|---:|---:|
| ALI | 4938 | 4 | 0 |
| CAP | 1863 | 790 | 0 |
| CPT | 8209 | 78 | 0 |
| INC | 20867 | 23 | 0 |
| ITE | 1305 | 1 | 0 |
| LIV | 45 | 30 | 0 |
| PAR | 21813 | 24 | 0 |
| PRT | 5 | 5 | 0 |
| SBT | 21 | 16 | 0 |
| SEC | 2128 | 609 | 0 |
| SSC | 714 | 152 | 0 |
| TIT | 328 | 206 | 0 |

## Other

- Rows with `id_ambiguo = 1`: 1804 (basic units: 1194)
- Dropped Agrupamentos (Q4): {'preliminar': 64, 'assinatura': 388, 'localDataFecho': 18}
- Long 'dropped' Agrupamentos kept as TXT (D2): 11
- Non-statutory metadata sources: {'epi=agrupamento,ementa=agrupamento': 125, 'parent=urn,epi=agrupamento,ementa=agrupamento': 1, 'epi=agrupamento,ementa=none': 6, 'epi=first-section-heading,ementa=none': 1, 'epi=preliminar-first-line,ementa=none': 5, 'epi=urn,ementa=agrupamento': 1, 'epi=agrupamento,ementa=campo-assunto': 104, 'epi=preliminar-first-line,ementa=agrupamento': 1, 'epi=ementa-agrupamento-title,ementa=campo-assunto': 1, 'parent=stem,statutory': 179}
- Text coverage (‰) distribution: {'n': 672, 'p50': 1000, 'p90': 1000, 'p99': 1000, 'max': 1000}; files below 98%: []
- Gemini countTokens sample: {'status': 'not run', 'reason': 'no GEMINI_API_KEY / GOOGLE_API_KEY in the environment'}
