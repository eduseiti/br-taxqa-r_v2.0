# Segmentation report

- Generated: 2026-09-24T20:10:35
- Overall: **OK**
- Command: `python scripts/segmentation/segment_all.py --jobs 16 --overwrite`
- Flags: `{"only": null, "overwrite": true, "jobs": 16, "max_tokens": 1024, "tokenizer": "max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B", "ementa_max_tokens": 128, "keep_dropped_min_chars": 300, "allow_count_change": false, "out_dir": "/work/unicamp/articles/RAG_evaluation/br-taxqa-r_v2.0/segmented", "grouping_max_tokens": 8192, "skip_validation": false}`
- Saxon: SaxonC-HE 13.0 from Saxonica; annex categories: {'A': 12, 'B': 50, 'C': 181}
- Timings (s): {'1_router_s': 9.7, '2_metadata_s': 4.7, '3_xsl_s': 30.5, '3b_4_split_loose_s': 15.5, '5_non_statutory_s': 9.3, '6_merge_s': 19.8, 'total_s': 90.3}

## Checks

| Check | Result | Detail |
|---|---|---|
| csv_schema | ok | {"detail": "chunks_all columns = 26 (6 + 3 + 14 provenance + 3 token counts)"} |
| non_empty | ok | {"count": 0} |
| chunk_id_unique | ok | {"dup_chunk_id": 0, "dup_urn_not_ambiguous": 0} |
| provenance | ok | {"count": 0, "by_kind": {"provenance_missing_id": 0, "provenance_ancestors": 0}} |
| intervals | ok | {"count": 0, "by_kind": {"interval_inverted": 0, "intervals_crossing": 0, "sub_outside_article": 0, "part_outside_unit": 0}} |
| coverage | ok | {"count": 0, "by_kind": {"coverage_art": 0, "coverage_dsp": 0, "coverage_parts": 0, "coverage_agrupamento": 0, "coverage_table": 0}} |
| cap | ok | {"count": 0, "by_kind": {"cap_unflagged": 0, "cap_hard_limit": 0}} |
| split_complete | ok | {"count": 0, "by_kind": {"split_incomplete": 0}} |
| text_coverage | ok | {"count": 0, "by_kind": {"text_coverage": 0}, "min": 0.9983} |
| grouping_limit | ok | {"limit": 8192, "listed": 243, "over_limit_in_chunks_all": 0, "listed_and_in_chunks_all": 0} |

## Rows

- Total rows: 87704 in 664 files
- Per strategy: {'S1': 26252, 'S2': 82644, 'S3': 87704}

| Tipo | Rows | ref p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| PAR | 21511 | 233 | 381 | 642 | 5936 |
| INC | 20617 | 193 | 352 | 569 | 4116 |
| ART | 20479 | 193 | 680 | 1007 | 1024 |
| CPT | 8084 | 162 | 356 | 1013 | 8103 |
| ALI | 4878 | 200 | 349 | 573 | 1420 |
| TXT | 3545 | 309 | 984 | 1021 | 1024 |
| SEC | 2106 | 582 | 2088 | 5493 | 7839 |
| CAP | 1843 | 819 | 3540 | 7256 | 7941 |
| DSP | 1522 | 150 | 592 | 911 | 1009 |
| ITE | 1302 | 165 | 295 | 436 | 1358 |
| SSC | 714 | 498 | 1885 | 4230 | 7771 |
| TAB | 706 | 354 | 981 | 1022 | 1163 |
| TIT | 326 | 1532 | 6030 | 7925 | 8102 |
| LIV | 45 | 1613 | 5869 | 8096 | 8119 |
| SBT | 21 | 3753 | 6829 | 7839 | 8061 |
| PRT | 5 | 2320 | 6129 | 7303 | 7433 |

Tokens per tokenizer (p50 / p99 / max):

| Tipo | cl100k_base | Qwen3 |
|---|---|---|
| ALI | 191 / 541 / 1257 | 200 / 573 / 1420 |
| ART | 185 / 965 / 1024 | 193 / 1007 / 1024 |
| CAP | 783 / 7035 / 7709 | 818 / 7256 / 7941 |
| CPT | 155 / 942 / 7613 | 162 / 1013 / 8103 |
| DSP | 143 / 856 / 995 | 150 / 911 / 1009 |
| INC | 182 / 528 / 2891 | 193 / 569 / 4116 |
| ITE | 158 / 428 / 1358 | 165 / 436 / 1358 |
| LIV | 1579 / 7791 / 7833 | 1613 / 8096 / 8119 |
| PAR | 222 / 599 / 4349 | 233 / 642 / 5936 |
| PRT | 2293 / 7102 / 7225 | 2320 / 7303 / 7433 |
| SBT | 3565 / 7460 / 7668 | 3753 / 7839 / 8061 |
| SEC | 560 / 5244 / 7839 | 578 / 5493 / 7831 |
| SSC | 470 / 4004 / 7436 | 498 / 4230 / 7771 |
| TAB | 324 / 965 / 1142 | 354 / 1022 / 1163 |
| TIT | 1440 / 7765 / 7895 | 1532 / 7925 / 8102 |
| TXT | 294 / 997 / 1024 | 309 / 1021 / 1024 |

- Per category: {'main': 71904, 'A': 11213, 'nao_articulado': 3051, 'B': 1041, 'C': 495}

## Split units (cap 1024)

- ART/DSP units split: 656 into 1752 parts ({'ART': 647, 'DSP': 9}); within-leaf splits: 72; truncated HEAD (D3): 8
- Non-statutory TXT/TAB units split: 342
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
| lei_11941_20090527, Art. 47. | 4912 | 7 | yes |
| in_rfb_1911_20191011, Art. 258. | 4747 | 7 | yes |
| lei_comp_123_20061214, Art. 18-A. | 4665 | 7 |  |
| decreto_9580_20181122.anexo1, Art. 881. | 4654 | 7 |  |
| in_rfb_1911_20191011, Art. 25. | 4376 | 6 |  |
| lei_10865_20040430, Art. 28. | 4307 | 6 |  |
| constituição_1988_19881005, Art. 100. | 4302 | 6 |  |
| lei_11941_20090527, Art. 26. | 4101 | 5 | yes |
| decreto_lei_1535_19770413, Art. 1º | 4050 | 5 | yes |
| lei_12249_20100611, Art. 65. | 4022 | 7 |  |
| lei_9250_19951226, Art. 8º | 3822 | 5 |  |
| constituição_1988_19881005, Art. 5º | 3777 | 5 |  |
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
| … 616 more (see segmentation_report.json) | | | |

## Over-cap rows that are not split (Q7)

Grouping chunks above 8192 tokens are not in chunks_all.csv (S3 option 2): 243 listed in `groupings_over_limit.csv` {'TIT': 84, 'CAP': 76, 'LIV': 43, 'SEC': 19, 'PRT': 13, 'SBT': 5, 'SSC': 3}. The table counts the rows kept.

| Tipo | Rows | > cap | ≥ 8,192 |
|---|---:|---:|---:|
| ALI | 4878 | 4 | 0 |
| CAP | 1843 | 780 | 0 |
| CPT | 8084 | 78 | 0 |
| INC | 20617 | 23 | 0 |
| ITE | 1302 | 1 | 0 |
| LIV | 45 | 30 | 0 |
| PAR | 21511 | 43 | 0 |
| PRT | 5 | 5 | 0 |
| SBT | 21 | 16 | 0 |
| SEC | 2106 | 600 | 0 |
| SSC | 714 | 152 | 0 |
| TIT | 326 | 204 | 0 |

## Other

- Rows with `id_ambiguo = 1`: 1803 (basic units: 1195)
- Dropped Agrupamentos (Q4): {'preliminar': 44, 'assinatura': 392, 'localDataFecho': 13}
- Long 'dropped' Agrupamentos kept as TXT (D2): 11
- Non-statutory metadata sources: {'epi=agrupamento,ementa=agrupamento': 119, 'epi=ementa-agrupamento-title,ementa=campo-assunto': 1, 'parent=urn,epi=agrupamento,ementa=agrupamento': 1, 'epi=agrupamento,ementa=none': 3, 'epi=first-section-heading,ementa=none': 1, 'epi=preliminar-first-line,ementa=none': 5, 'epi=agrupamento,ementa=campo-assunto': 104, 'epi=preliminar-first-line,ementa=agrupamento': 1, 'parent=stem,statutory': 181}
- Text coverage (‰) distribution: {'n': 664, 'p50': 1000, 'p90': 1000, 'p99': 1000, 'max': 1000}; files below 98%: []
- Gemini countTokens sample: {'status': 'not run', 'reason': 'no GEMINI_API_KEY / GOOGLE_API_KEY in the environment'}
