# Segmentation report

- Generated: 2026-11-22T17:31:58
- Overall: **OK**
- Command: `python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change --variants caput --frozen ../br-taxqa-r_fixB_backup_20261122/chunks_all_20261008.csv.gz --frozen-lexml-rev HEAD`
- Flags: `{"only": null, "overwrite": true, "jobs": 16, "max_tokens": 1024, "tokenizer": "max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B", "ementa_max_tokens": 128, "keep_dropped_min_chars": 300, "allow_count_change": true, "out_dir": "/work/doutorado/artigos/RAG_evaluation/br-taxqa-r_v2.0/segmented", "grouping_max_tokens": 8192, "skip_validation": false, "variants": "caput", "frozen": "../br-taxqa-r_fixB_backup_20261122/chunks_all_20261008.csv.gz", "frozen_lexml_rev": "HEAD"}`
- Saxon: SaxonC-HE 13.0 from Saxonica; annex categories: {'A': 12, 'B': 37, 'C': 130}
- Code: {"commit": "38b37f0ea48617466609aec051b8f6ad1d7fd824", "branch": "main", "dirty": true, "dirty_files": ["M lexml/articulados/PARSER_VERSION", " M lexml/articulados/circ_bc_3432_20090203.err.log", " M lexml/articulados/circ_bc_3432_20090203.xml", " M lexml/articulados/decreto_57942_19660310.err.log", " M lexml/articulados/decreto_57942_19660310.xml", " M lexml/articulados/decreto_71733_19730118.err.log", " M lexml/articulados/decreto_71733_19730118.xml", " M lexml/articulados/decreto_85306_19801030.err.log", " M lexml/articulados/decreto_85306_19801030.xml", " M lexml/articulados/decreto_87563_19820913.err.log", " M lexml/articulados/decreto_87563_19820913.xml", " M lexml/articulados/decreto_9580_20181122.anexo1.xml", " M lexml/articulados/decreto_9580_20181122.err.log", " M lexml/articulados/decreto_lei_5844_19430923.err.log", " M lexml/articulados/decreto_lei_5844_19430923.xml", " M lexml/articulados/in_rfb_1131_20110221.err.log", " M lexml/articulados/in_rfb_1131_20110221.xml", " M lexml/articulados/lei_12350_20101220.err.log", " M lexml/articulados/lei_12350_20101220.xml", " M lexml/articulados/lei_12715_20120917.err.log"]}
- Output checksums (sha256): {"chunks_all.csv": "6e02039936b255cbfbbf070533e3e79ae2990dd3157e86f524696a0f6742f07d", "chunks_all.csv.gz": "21bf98e5a1aa52b209ee009b107194d2416e036fa5076ad4d5a8a112119d910a", "groupings_over_limit.csv": "4b2a925235d6d3f490465daa07964b192ba7e8292ac2ba80980d745d57ec4fba", "annex_manifest.csv": "b672a43c50a000588db0f542d6a8896bacc6c5176534604d1c733cb6ff948da5"}
- Timings (s): {'1_router_s': 4.7, '2_metadata_s': 1.2, '3_xsl_s': 22.8, '3b_4_split_loose_s': 22.6, '5_non_statutory_s': 12.1, '6_merge_s': 14.4, 'total_s': 78.7}

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
| grouping_limit | ok | {"limit": 8192, "listed": 193, "over_limit_in_chunks_all": 0, "listed_and_in_chunks_all": 0} |
| variant_twins | ok | {"count": 0, "variants": 27490} |
| base_no_caput | ok | {"count": 0} |
| diff_vs_frozen | ok | {"report_only": true, "lexml_rev": "HEAD", "files_unchanged_lexml": 612, "files_changed_or_new_or_removed": 15, "by_variant": true, "rows_compared": 92112, "rows_text_differs": 0, "rows_only_new": 0, "rows_only_frozen": 0} |

## Rows

- Total base rows: 77135 in 627 files; rows per variant: {'base': 77135, 'caput': 27490}
- Per strategy: {'S1': 21514, 'S2': 73173, 'S3': 77135, 'S2C': 73173, 'S4': 77135}

| Tipo | Rows | ref p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| PAR | 19688 | 150 | 252 | 488 | 5776 |
| INC | 18231 | 168 | 280 | 473 | 3956 |
| ART | 16817 | 217 | 724 | 1010 | 1024 |
| CPT | 7103 | 166 | 356 | 1026 | 8103 |
| ALI | 5062 | 170 | 290 | 429 | 1420 |
| TXT | 3312 | 330 | 984 | 1020 | 1024 |
| SEC | 1745 | 606 | 2267 | 5739 | 7827 |
| ITE | 1575 | 164 | 277 | 418 | 1358 |
| CAP | 1431 | 910 | 3870 | 7378 | 7941 |
| DSP | 852 | 166 | 744 | 928 | 1009 |
| SSC | 567 | 521 | 2037 | 4192 | 7771 |
| TAB | 533 | 307 | 976 | 1023 | 1163 |
| TIT | 187 | 1886 | 6218 | 7953 | 8102 |
| SBT | 20 | 3290 | 6841 | 7850 | 8061 |
| LIV | 9 | 1599 | 5067 | 5956 | 6055 |
| PRT | 3 | 4172 | 6781 | 7368 | 7433 |

Tokens per tokenizer (p50 / p99 / max):

| Tipo | cl100k_base | Qwen3 |
|---|---|---|
| ALI | 162 / 409 / 1257 | 170 / 429 / 1420 |
| ART | 207 / 971 / 1023 | 217 / 1009 / 1024 |
| CAP | 887 / 7229 / 7697 | 910 / 7364 / 7941 |
| CPT | 158 / 981 / 7613 | 166 / 1026 / 8103 |
| DSP | 158 / 872 / 995 | 166 / 928 / 1009 |
| INC | 159 / 440 / 2759 | 168 / 473 / 3956 |
| ITE | 157 / 397 / 1358 | 164 / 418 / 1358 |
| LIV | 1579 / 5928 / 6044 | 1591 / 5956 / 6055 |
| PAR | 142 / 460 / 4205 | 150 / 488 / 5776 |
| PRT | 4161 / 7164 / 7225 | 4172 / 7368 / 7433 |
| SBT | 3124 / 7471 / 7668 | 3290 / 7850 / 8061 |
| SEC | 584 / 5527 / 7827 | 604 / 5739 / 7817 |
| SSC | 498 / 4025 / 7436 | 521 / 4192 / 7771 |
| TAB | 289 / 945 / 1142 | 307 / 1023 / 1163 |
| TIT | 1832 / 7830 / 7895 | 1886 / 7953 / 8102 |
| TXT | 316 / 997 / 1024 | 330 / 1020 / 1024 |

- Per category: {'main': 61307, 'A': 11298, 'nao_articulado': 3016, 'B': 1080, 'C': 434}

## Split units (cap 1024)

- ART/DSP units split: 601 into 1615 parts ({'ART': 592, 'DSP': 9}); within-leaf splits: 67; truncated HEAD (D3): 8
- Non-statutory TXT/TAB units split: 316
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
| lei_comp_123_20061214, Art. 18-A. | 4665 | 7 |  |
| decreto_9580_20181122.anexo1, Art. 881. | 4654 | 7 |  |
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
| lei_8069_19900713, Art. 52. | 3275 | 4 |  |
| lei_7713_19881222, Art. 6º | 3267 | 4 |  |
| … 561 more (see segmentation_report.json) | | | |

## Over-cap rows that are not split (Q7)

Grouping chunks above 8192 tokens are not in chunks_all.csv (S3 option 2): 193 listed in `groupings_over_limit.csv` {'CAP': 73, 'TIT': 66, 'LIV': 22, 'SEC': 16, 'PRT': 7, 'SBT': 6, 'SSC': 3}. The table counts the rows kept.

| Tipo | Rows | > cap | ≥ 8,192 |
|---|---:|---:|---:|
| ALI | 5062 | 4 | 0 |
| CAP | 1431 | 660 | 0 |
| CPT | 7103 | 72 | 0 |
| INC | 18231 | 22 | 0 |
| ITE | 1575 | 2 | 0 |
| LIV | 9 | 7 | 0 |
| PAR | 19688 | 24 | 0 |
| PRT | 3 | 3 | 0 |
| SBT | 20 | 15 | 0 |
| SEC | 1745 | 539 | 0 |
| SSC | 567 | 121 | 0 |
| TIT | 187 | 127 | 0 |

## Other

- Rows with `id_ambiguo = 1`: 1262 (basic units: 567)
- Dropped Agrupamentos (Q4): {'preliminar': 65, 'assinatura': 388, 'localDataFecho': 18}
- Long 'dropped' Agrupamentos kept as TXT (D2): 11
- Non-statutory metadata sources: {'epi=agrupamento,ementa=agrupamento': 126, 'parent=urn,epi=agrupamento,ementa=agrupamento': 1, 'epi=agrupamento,ementa=none': 6, 'epi=first-section-heading,ementa=none': 1, 'epi=preliminar-first-line,ementa=none': 5, 'epi=urn,ementa=agrupamento': 1, 'epi=agrupamento,ementa=campo-assunto': 103, 'epi=preliminar-first-line,ementa=agrupamento': 1, 'epi=ementa-agrupamento-title,ementa=campo-assunto': 1, 'parent=stem,statutory': 130}
- Text coverage (‰) distribution: {'n': 627, 'p50': 1000, 'p90': 1000, 'p99': 1000, 'max': 1000}; files below 98%: []
- Gemini countTokens sample: {'status': 'run', 'model': 'gemini-embedding-2', 'random_sample': {'n': 500, 'gemini_gt_reference': 0, 'max_excess': 0, 'ratio_gemini_over_reference': {'p50': np.float64(0.881), 'p99': np.float64(0.954), 'max': np.float64(0.961)}, 'max_gemini': 5869, 'gemini_over_8192': []}, 'largest_chunks': {'n': 100, 'gemini_gt_reference': 0, 'max_excess': 0, 'ratio_gemini_over_reference': {'p50': np.float64(0.875), 'p99': np.float64(0.926), 'max': np.float64(0.929)}, 'max_gemini': 7253, 'gemini_over_8192': []}, 'errors': 0, 'error_examples': []}
