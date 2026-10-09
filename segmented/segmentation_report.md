# Segmentation report

- Generated: 2026-10-09T12:59:14
- Overall: **OK**
- Command: `python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change --variants caput --frozen /tmp/claude-0/-work-unicamp-articles-RAG-evaluation-br-taxqa-r-v2-0/36df1725-581b-4996-9f90-469e4024fdaa/scratchpad/chunks_all_r7.csv.gz --frozen-lexml-rev 280121b`
- Flags: `{"only": null, "overwrite": true, "jobs": 16, "max_tokens": 1024, "tokenizer": "max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B", "ementa_max_tokens": 128, "keep_dropped_min_chars": 300, "allow_count_change": true, "out_dir": "/work/unicamp/articles/RAG_evaluation/br-taxqa-r_v2.0/segmented", "grouping_max_tokens": 8192, "skip_validation": false, "variants": "caput", "frozen": "/tmp/claude-0/-work-unicamp-articles-RAG-evaluation-br-taxqa-r-v2-0/36df1725-581b-4996-9f90-469e4024fdaa/scratchpad/chunks_all_r7.csv.gz", "frozen_lexml_rev": "280121b"}`
- Saxon: SaxonC-HE 13.0 from Saxonica; annex categories: {'A': 12, 'B': 35, 'C': 130}
- Code: {"commit": "a94c2bf6ef663439a98f91ca29068a8c4e976c4b", "branch": "main", "dirty": true, "dirty_files": ["M lexml/nao_articulados/PARSER_VERSION", " M lexml/nao_articulados/urn_lex_br_advocacia.geral.uniao_parecer_2018-12-28_93.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_portaria_1979-03-01_80.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_portaria_2018-06-07_277!anexo1.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1996-12-27_28.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1998-11-11_19.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-01-07_3.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-09-14_24.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_1999-11-26_96.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_ato.declaratorio_2000-10-25_19.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1983-12-29_28.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1986-02-18_6.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1986-08-25_66.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1992-09-30_11.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1994-03-17_1.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1995-08-08_1.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_1995-11-03_4.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_2000-06-29_26.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_2002-09-24_1.xml", " M lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_parecer_2014-08-04_6.xml"]}
- Output checksums (sha256): {"chunks_all.csv": "35f691772c60ac1be156064b0eff88089e82c7f0c6da0fcb0011ba7b75af32e5", "chunks_all.csv.gz": "a6087b7f19ff5b02cc0863523b6dd423f6feddf291fe9f11e7f08d45146c326a", "groupings_over_limit.csv": "34819c6fdb009a8400c66019789f654f2be39566bce9b4a46b56ec7de94f992a", "annex_manifest.csv": "c443ca771ba1f6e1582722643e9c7a4a6b9cb32db306fc251cde3db580f4b749"}
- Timings (s): {'1_router_s': 5.5, '2_metadata_s': 4.4, '3_xsl_s': 30.0, '3b_4_split_loose_s': 15.6, '5_non_statutory_s': 8.8, '6_merge_s': 26.1, 'total_s': 91.3}

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
| variant_twins | ok | {"count": 0, "variants": 27494} |
| base_no_caput | ok | {"count": 0} |
| diff_vs_frozen | ok | {"report_only": true, "lexml_rev": "280121b", "files_unchanged_lexml": 364, "files_changed_or_new_or_removed": 308, "rows_compared": 31605, "rows_text_differs": 8555, "rows_only_new": 0, "rows_only_frozen": 0} |

### Examples

- **diff_vs_frozen**: `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u_inc1`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u_inc2`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u_inc3`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u_inc4`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u_inc5`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.executivo:2024-03-06;2!art1_par1u`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.interpretativo:2007-12-06;18!art4_par1`; `urn:lex:br:ministerio.fazenda;secretaria.receita.federal.brasil:ato.declaratorio.interpretativo:2007-12-06;18!art4_par2`

## Rows

- Total base rows: 77080 in 625 files; rows per variant: {'base': 77080, 'caput': 27494}
- Per strategy: {'S1': 21497, 'S2': 73118, 'S3': 77080, 'S2C': 73118, 'S4': 77080}

| Tipo | Rows | ref p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| PAR | 19675 | 150 | 253 | 489 | 5776 |
| INC | 18235 | 168 | 280 | 473 | 3956 |
| ART | 16784 | 217 | 727 | 1010 | 1024 |
| CPT | 7091 | 166 | 356 | 1027 | 8103 |
| ALI | 5045 | 170 | 291 | 431 | 1420 |
| TXT | 3306 | 330 | 983 | 1020 | 1024 |
| SEC | 1745 | 606 | 2267 | 5739 | 7827 |
| ITE | 1575 | 164 | 277 | 416 | 1358 |
| CAP | 1431 | 910 | 3870 | 7378 | 7941 |
| DSP | 875 | 166 | 742 | 926 | 1009 |
| SSC | 567 | 521 | 2037 | 4192 | 7771 |
| TAB | 532 | 310 | 977 | 1023 | 1163 |
| TIT | 187 | 1886 | 6218 | 7953 | 8102 |
| SBT | 20 | 3290 | 6841 | 7850 | 8061 |
| LIV | 9 | 1599 | 5067 | 5956 | 6055 |
| PRT | 3 | 4172 | 6781 | 7368 | 7433 |

Tokens per tokenizer (p50 / p99 / max):

| Tipo | cl100k_base | Qwen3 |
|---|---|---|
| ALI | 163 / 410 / 1257 | 170 / 431 / 1420 |
| ART | 208 / 971 / 1023 | 217 / 1009 / 1024 |
| CAP | 887 / 7229 / 7697 | 910 / 7364 / 7941 |
| CPT | 158 / 981 / 7613 | 166 / 1027 / 8103 |
| DSP | 157 / 872 / 995 | 166 / 926 / 1009 |
| INC | 159 / 440 / 2759 | 168 / 473 / 3956 |
| ITE | 157 / 397 / 1358 | 164 / 416 / 1358 |
| LIV | 1579 / 5928 / 6044 | 1591 / 5956 / 6055 |
| PAR | 142 / 461 / 4205 | 150 / 489 / 5776 |
| PRT | 4161 / 7164 / 7225 | 4172 / 7368 / 7433 |
| SBT | 3124 / 7471 / 7668 | 3290 / 7850 / 8061 |
| SEC | 584 / 5527 / 7827 | 604 / 5739 / 7817 |
| SSC | 498 / 4025 / 7436 | 521 / 4192 / 7771 |
| TAB | 290 / 945 / 1142 | 310 / 1023 / 1163 |
| TIT | 1832 / 7830 / 7895 | 1886 / 7953 / 8102 |
| TXT | 316 / 997 / 1024 | 330 / 1020 / 1024 |

- Per category: {'main': 61366, 'A': 11225, 'nao_articulado': 3016, 'B': 1039, 'C': 434}

## Split units (cap 1024)

- ART/DSP units split: 606 into 1626 parts ({'ART': 597, 'DSP': 9}); within-leaf splits: 69; truncated HEAD (D3): 8
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
| … 566 more (see segmentation_report.json) | | | |

## Over-cap rows that are not split (Q7)

Grouping chunks above 8192 tokens are not in chunks_all.csv (S3 option 2): 193 listed in `groupings_over_limit.csv` {'CAP': 73, 'TIT': 66, 'LIV': 22, 'SEC': 16, 'PRT': 7, 'SBT': 6, 'SSC': 3}. The table counts the rows kept.

| Tipo | Rows | > cap | ≥ 8,192 |
|---|---:|---:|---:|
| ALI | 5045 | 4 | 0 |
| CAP | 1431 | 660 | 0 |
| CPT | 7091 | 72 | 0 |
| INC | 18235 | 22 | 0 |
| ITE | 1575 | 2 | 0 |
| LIV | 9 | 7 | 0 |
| PAR | 19675 | 24 | 0 |
| PRT | 3 | 3 | 0 |
| SBT | 20 | 15 | 0 |
| SEC | 1745 | 539 | 0 |
| SSC | 567 | 121 | 0 |
| TIT | 187 | 127 | 0 |

## Other

- Rows with `id_ambiguo = 1`: 1326 (basic units: 609)
- Dropped Agrupamentos (Q4): {'preliminar': 65, 'assinatura': 388, 'localDataFecho': 18}
- Long 'dropped' Agrupamentos kept as TXT (D2): 11
- Non-statutory metadata sources: {'epi=agrupamento,ementa=agrupamento': 126, 'parent=urn,epi=agrupamento,ementa=agrupamento': 1, 'epi=agrupamento,ementa=none': 6, 'epi=first-section-heading,ementa=none': 1, 'epi=preliminar-first-line,ementa=none': 5, 'epi=urn,ementa=agrupamento': 1, 'epi=agrupamento,ementa=campo-assunto': 103, 'epi=preliminar-first-line,ementa=agrupamento': 1, 'epi=ementa-agrupamento-title,ementa=campo-assunto': 1, 'parent=stem,statutory': 130}
- Text coverage (‰) distribution: {'n': 625, 'p50': 1000, 'p90': 1000, 'p99': 1000, 'max': 1000}; files below 98%: []
- Gemini countTokens sample: {'status': 'not run', 'reason': 'no GEMINI_API_KEY / GOOGLE_API_KEY in the environment'}
