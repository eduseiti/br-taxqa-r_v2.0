# BR-TaxQA-R v2.0 — New Dataset Format and Reference Fixes

**Generated:** 2026-09-27 18:04:01 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** implemented and run. Outputs are in `dataset/`, code and hand-verified data in `scripts/dataset/`.
**Context:** the legal-provision score (`docs/20260926_112714_gold_answer_nuggetization_plan.md`, §4.5)
takes its gold citations from the dataset. v1.1 references point at `.txt` file names of the v1
corpus, some of which are duplicated or wrong. The v2.0 corpus (`original/` → `lexml/` → `segmented/`)
uses different names. So the references had to be re-keyed to v2.0 documents and corrected.

---

## 1. Request

The user asked for:

1. Three specific fixes:
   - **Q277:** remove the "Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006" reference.
     The act does not exist; v1 downloaded the unrelated *Ato Declaratório Executivo Cosit nº 5, de
     24/02/2006*.
   - **Q150:** "Convenção Postal Universal.txt" is the *Decreto nº 9.358, de 30 de abril de 2018*.
   - **Q141:** the Brazil–Germany double-taxation accord is the *Decreto Legislativo nº 92, de 1975*.
2. All referred-document file names updated to the v2.0 corpus, for every question.
3. A new JSON file for the updated references, in a format that is easy to store and load on the
   HF Hub. The v1 format does not have to be kept.
4. A proposal for a whole new dataset format holding the questions, references and ground truth.
5. This note, recording the discussion and the execution.

## 2. Sources used

| Input | Path | Notes |
|---|---|---|
| v1.1 questions | `../questions_QA_2024_v1.1_manual_fix.json` | same MD5 (`339dc9ca…`) as HF `questions_QA_2024_v1.1.json` in the local HF clone `/work/doutorado/datasets_creation/legal/BR-TaxQA-R/`. SHA-256 `097abfc4…` in `build_report.json` |
| v1.1 corpus | `…/BR-TaxQA-R/referred_legal_documents_QA_2024_v1.1.json` | used only to see what v1 actually held for a file name |
| canonical list | `../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json` | 478 records, one per v1.1 file name: act type, number, date |
| v2.0 corpus | `original/{articulados,nao_articulados}/*.docx` (225 + 234 = 459) and `lexml/` | the corpus is now flat, not split into per-type sub-folders as in the 2026-09-13 audit |
| chunks | `segmented/chunks_all.csv.gz` | used to check that every cited document can be retrieved |

## 3. Format decision

### 3.1 Problems with v1.1

- A single questions file holds nested reference lists with **irregular schemas**: 5 key sets for
  reference entries and 5 for article entries (`alíneas`, `itens`, `detalhes` appear only
  sometimes), two empty `{"anexos": []}` entries, and `null` instead of `[]`.
- The custom loader script (`BR-TaxQA-R.py`) declares `Sequence(dict)`. HF turns that into a
  **dict of lists** and stringifies the article dicts. The v1 README admits this.
- `all_formatted_references` is a dict keyed by title that just concatenates the two lists.
- References point at `.txt` file names. Several file names are the same act, and some point at the
  wrong act (§5).
- Loader scripts are deprecated on the Hub (`datasets` ≥ 4 no longer runs them).

### 3.2 Chosen format: three JSON Lines configs, no loader script

Three flat tables joined by keys, declared in the dataset card's YAML `configs:` block
(`dataset/README.md`). The Hub and `load_dataset(path, config)` read them directly. Every row has
every key (`[]`/`null` when empty), so Arrow infers one schema. `provisions` loads as a **list of
structs**, not as the v1 dict-of-lists (verified with `datasets` 2.19.2).

| Config | Rows | Key | Role |
|---|---:|---|---|
| `questions` | 715 | `question_number` | question, full answer, **gold answer** (`answer_cleaned`), raw reference text, cited `document_ids` |
| `references` | 1,919 | `reference_id` = `<question_number>-<nn>` | one row per cited act per question: origin (`explicit`/`embedded`), cited title, `document_id` + `document_urn`, how it was resolved, structured provisions with LexML article ids, the v1.1 file name |
| `documents` | 459 | `document_id` = `original/` stem | URN, title, statutory flag, number, date, `original/` and `lexml/` paths (including annex files), v1.1 file names that resolve to it, number of citing questions |

The field-by-field schema is in `dataset/README.md`. Design choices:

- **JSON Lines, not one JSON array.** It is the Hub's standard for the `json` builder: it streams,
  diffs line by line and needs no custom code. Parquet can be produced from it on upload if needed.
- **References in their own table.** The legal-provision score (§4.5 of the nuggetization plan)
  works on (question, document, provision) rows. A flat table filters and joins directly, with no
  nested parsing. `questions.document_ids` is a convenience for document-level scoring.
- **`document_urn`** equals `doc_urn` in `segmented/chunks_all.csv.gz`. Gold citations therefore
  match retrieved chunks with no extra mapping, and match `lexml-linker` URNs on the system side.
- **`article_ids`** follow the LexML `id` convention of the XMLs (`art25`, `art12-1` for art. 12-A).
  Ranges (`"10 a 13"`) are expanded up to 300 articles. Unparseable strings (roman numerals of
  treaties, `"Capítulo III"`, `"item 4"`) give `[]`, and the raw string stays in `article`.
  Paragraph/inciso/alínea lists are kept as v1.1 had them, only trimmed of `§`. v1.1 lost which
  inciso belongs to which paragraph, and that cannot be recovered reliably. Provision-level URNs
  are left to the §4.5 implementation (`lexml-linker` on `references_text`).
- **Answers as strings** (lines joined with `\n`), as the nuggetization plan §2 prepares them.
- **Traceability:** each reference keeps `v1_file`, `resolution` and `resolution_note`. Every
  hand decision is in `scripts/dataset/reference_overrides.json`, with a reason.
- **Room for ground truth:** the gold nuggets planned in `scripts/nuggets/` can be added as a fourth
  config, `nuggets` (one row per nugget, keyed by `question_number`), with no change to the others.

Dropped from v1.1: `all_formatted_references` (redundant) and the `.txt` file names as keys
(they survive only as `v1_file`/`v1_files`).

## 4. Execution

### 4.1 Mapping non-statutory `.docx` to their XML

`lexml/nao_articulados/*.xml` are named after their URN, so the `.docx` stem does not appear in the
name, and no stored map existed. I re-parsed each of the 234 `.docx` with
`../lexml_parser_non_statutory` (`python -m lexml_nonstat parse`) and matched the URN it printed.
214 matched directly. For the other 20, the current parser leaves the date as `0000`, while the
committed XMLs carry it. Those 20 paired one-to-one by authority, type and number. The result is
committed as `scripts/dataset/nonstat_lexml_map.tsv` (234 stems → 234 distinct XMLs), so the build
does not re-run the parser.

### 4.2 Resolving v1.1 file names to v2.0 documents

`scripts/dataset/build_v2_dataset.py` resolves each v1.1 `file` value through its canonical
record, in this order:

1. **Hand-verified override** (`reference_overrides.json`): `files` (per file name), `drop` (one
   question's reference) or `reassign` (one question's reference moved to another document).
2. **`auto_exact`**: stem prefix + number + date of the canonical record.
3. **`auto_undated`**: prefix + number, when the canonical record has no date.

Any v1.1 file name left unresolved makes the build **fail**. Date-tolerant matching is not
automatic. The 2026-09-13 audit's rule 5 and its per-type "hand map" hid real errors (§5.2).

### 4.3 Checks, and how they surfaced the errors

- **Coverage:** all 478 canonical file names resolve or are explicitly marked.
- **Article existence:** every `article_id` is looked up in the document's LexML ids (main XML, then
  annex XMLs). This found the RIR/2018 articles in `decreto_9580…anexo1.xml`.
- **Cited number vs document number**, and **cited date vs document date**: these found the
  wrong-act matches in §5.2. For every cross-year mismatch I compared the question's subject with
  the corpus document's *assunto*/ementa.
- **Titles without an act number** (RIR, CF, treaties): listed title → document pairs by hand. This
  found `160-02` and `362-07`.
- **Citation present in the source text**: each reference's act number or keywords must appear in
  `references_text` (explicit) or in `answer` (embedded). This found Q025 and Q081.

## 5. Corrections applied

### 5.1 The three requested fixes

| Question | v1.1 reference (file) | v2.0 |
|---|---|---|
| 277 | Solução de Consulta Interna Cosit nº 5, de 28/03/2006 | **removed** (listed in `build_report.json → dropped_references`) |
| 150 | Convenção Postal Universal | `decreto_9358_20180430` (`urn:lex:br:federal:decreto:2018-04-30;9358`) |
| 141 | Acordo … Brasil e a Alemanha | `decreto_legislativo_92_19751105` (`urn:lex:br:congresso.nacional:decreto.legislativo:1975-11-05;92`) |

**Q150 also has a second UPU entry**, "Convenção de Berna da União Postal Universal (UPU).txt". Its
raw reference text is just "UPU", and v1 held a Wikipedia article for it. It is the same convention,
so it is also mapped to `decreto_9358_20180430`. This is **my inference** from the user's fix, and it
is easy to revert in `reference_overrides.json`.

### 5.2 Additional errors found and fixed

These fall under the user's note that the first version had inconsistencies. **Please review them.**

**a) The canonical list, and v1, matched the wrong act.** Cosit numbers its Soluções de Consulta per
year. The fetcher therefore matched a same-numbered SC from another year (v1's `.txt` names had no
date). A few other acts had the same problem. In every case below, the corpus document is on an
unrelated subject. The reference is kept, with `document_id = null` and `resolution =
not_in_corpus`, so no wrong document is used as gold:

| Cited act | Questions | Corpus holds instead |
|---|---|---|
| SC Cosit nº 50, de 22/06/2020 | 097, 645 | SC 50/2024 (IRPJ, Sociedades de Crédito Direto) |
| SC Cosit nº 69, de 30/12/2013 | 129 | SC 69/2020 (IRPJ, prizes) |
| SC Cosit nº 64, de 07/03/2014 | 148, 149 | SC 64/2024 (interval between shifts) |
| SC Cosit nº 194, de 05/08/2015 | 148, 149, 150 | SC 194/2023 (PIS, cerealistas) |
| SC Cosit nº 140, de 21/09/2021 | 180 | SC 140/2023 (IRPJ, ICMS-DIFAL) |
| SCI Cosit nº 27, de 07/07/2008 | 187 | Solução de Divergência 27/2008 (IRRF/Cide) |
| Decreto-Lei nº 8.794, de 23/01/1946 | 188 | Lei 8.794/1993 (budget credit) |
| AD PGFN nº 2, de 10/03/2016 | 230, 316 | AD PGFN 2/2018 |
| SC Cosit nº 179, de 16/08/2023 | 234, 282 | SC 179/2024 (compensatory alimony) |
| AD PGFN nº 3, de 30/03/2016 | 280 | AD PGFN 3/2008 |
| SC Cosit nº 75, de 25/06/2020 | 280, 281 | SC 75/2023 (software royalties) |
| SC Cosit nº 123, de 13/09/2021 | 305, 306 | SC 123/2023 (Cofins) |
| SC Cosit nº 7, de 13/01/2017 | 307 | SC 7/2021 (IRPJ, real estate) |
| Parecer Cosit nº 30, de 28/09/2001 | 313 | ADE Cosit 30/2001 (dollar rate) |
| SC Cosit nº 354, de 17/12/2014 | 356 | SC 354/2017 (pension-plan contributions) |
| SC Cosit nº 173, de 03/07/2015 | 361, 375 | SC 173/2023 (PIS credits) |
| SC Cosit nº 214, de 20/12/2021 | 460, 627 | SC 214/2024 (real-estate rights) |
| ADI RFB nº 3, de 27/04/2016 | 559, 627 | ADE RFB 3/2024 (TIPI) |
| SC Cosit nº 211, de 24/06/2019 | 560, 562 | SC 211/2024 (Simples Nacional) |
| SC Cosit nº 183, de 25/06/2014 | 580 | SC 134/2014 (CIDE); v1 already held this text |
| SC Cosit nº 166, de 28/05/2019 | 610, 611, 614 | SC 166/2023 (residential-property exemption) |
| PN CST nº 38, de 1975 | 253, 255 | PN CST 38/1980 (cooperatives) |
| PN CST nº 72, de 1979 | 607 | PN CST 72/1975 (pre-operating expenses) |
| Resolução TSE nº 22.250, de 2006 (art. 14) | 438 | Res. TSE 22.205/2006 (no art. 14) |
| Parecer PGFN/CAT nº 815/2010 | 249 | `parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015.docx` holds **Nota PGFN/CRJ 981/2015**, a duplicate of `nota_pgfn_981_20151104` |
| Documento de Informação e Apuração do ITR (Diat) | 634 | not in `original/`. It was fetched (`../br-taxqa-document-fetcher/output_manual/documents/documento_de_informacao_e_apuracao_do_ITR_DIAT.docx`) but never copied |

That is 26 acts and 42 references. 37 questions have at least one unresolved reference; for 2 of
them, none of their references resolves.

**Which of these were already in v1.0** (checked on 2026-09-27). I traced each act through the
released v1.0 files (`../questions_QA_2024_v1.0.json` and `../referred_legal_documents_QA_2024_v1.0.json`,
byte-identical to HF commits `52ec296` / LFS oid `4c5ed205…`). For every act, v1.0 used the same
file name as v1.1, and the text of that file is the same in v1.0 and v1.1.

- **Already wrong in v1.0 (23 acts):** the 21 same-number acts from another year or of another
  type, the "Parecer PGFN/CAT 815/2010" file (already holds Nota PGFN/CRJ 981/2015) and SC Cosit
  183/2014 (already holds SC 134/2014). Resolução TSE 22.250 was also wrong in v1.0, in a different
  way. v1.0 held a TSE *index page* that lists resolutions 22.205, 22.249, 22.250… with one-line
  summaries, not the text of 22.250 (no art. 14). v2.0 fetched 22.205, the first entry of that list.
- **Correct in v1.0, broken in v2.0 (3 acts):**
  - **PN CST nº 38, de 24/03/1975** (Q253, Q255): the v1.0 text is the right opinion, on
    professional services by individuals. The v2.0 fetch got PN CST 38/1980.
  - **PN CST nº 72, de 18/12/1979** (Q607): the v1.0 text is the right opinion, on inherited
    property cost. The v2.0 fetch got PN CST 72/1975.
  - **Diat** (Q634): v1.0 held Receita Federal's Diat service page. It is the same kind of source as
    the DBF/Dmed/DOI pages that v2.0 kept, and it was lost only because the fetched `.docx` was never
    copied to `original/`.

The v1.0 texts of PN CST 38/1975 and 72/1979 can be used to recover these two acts in v2.0.

Same-year date differences were checked and kept, because the act is the right one: IN RFB 1.131
(20 vs 21/02/2011), IN RFB 1.585 (cited "31/12/2015", act of 31/08/2015), SC Cosit 125/2014,
SC Cosit 264/2019, IN SRF 83 and 118, PN CST 6 and 66, Lei 9.718, and the typo'd years of Lei
9.250 / Lei 7.713 / Decreto 9.580. PDF typos resolved correctly: "Lei nº 8.891" → Lei 8.981/1995
(Q176); "Lei nº 1.535" → Decreto-Lei 1.535/1977.

**b) The canonical list mapped to the wrong document of the corpus:**

| File (v1.1) | Canonical said | v2.0 |
|---|---|---|
| Convenção sobre Privilégios e Imunidades das Nações Unidas (Q150) | Decreto 52.288/1963 (the *Agências Especializadas* convention) | `decreto_27784_19500216`, which promulgates the UN convention and which Q150's own answer cites next to it |
| IN RFB nº 1.997/2019 (Q025) | IN RFB 1.911/2019 | not in corpus (and the reference is dropped, see d) |

**c) v1.1 attached the wrong file to one citation** (`reassign`, per question):

| Reference | Cited | v1.1 file | v2.0 |
|---|---|---|---|
| 160-02 | Acordo sobre o Novo Banco de Desenvolvimento, art. 34 | Convenção de Viena sobre o Direito dos Tratados | `decreto_8624_20151229` (annex 1 is the NDB agreement) |
| 362-07 | art. 66 do RIR/2018 | Circular BCB 3.432/2009 | `decreto_9580_20181122` |

**d) Hallucinated embedded references (dropped).** Q025 ("Não é devida a multa…") and Q081
("Apresenta declaração de acordo com as instruções para contribuinte casado.") cite nothing. Yet
v1.0 and v1.1 list three "embedded" references for each: Lei 9.532, IN RFB 1.997, CTN, Decreto
3.000 and IN RFB 1.505 "de 05/08/2014". This is an artefact of the LLM extraction. These 6 references
are removed. Together with Q277 that makes 7 dropped references. No other reference failed the
source-text check.

## 6. Results

`python3 scripts/dataset/build_v2_dataset.py` (about 2 s):

| | Count |
|---|---:|
| Questions | 715 |
| Questions with ≥ 1 reference | 596 |
| References | 1,919 (1,475 explicit, 444 embedded) |
| — `auto_exact` / `auto_undated` | 1,776 / 30 |
| — `override` (hand-verified) | 71 |
| — `not_in_corpus` | 42 |
| Dropped references | 7 (Q277 ×1, Q025 ×3, Q081 ×3) |
| Corpus documents | 459; 424 cited by some question |
| Cited article ids found in the LexML | 1,792 / 1,811 (1,385 main XML, 407 only in an annex XML) |

The 35 uncited documents (listed in `build_report.json`) are the wrong-year acts above, the
Nota-981 duplicate, Lei 3.071 and Lei 5.869 (known extras), and a few acts v1.1 never cited:
the DBF/Dimob/Dmed/DOI/Carnê-Leão pages, Parecer Cosit 26/2000 and SC Cosit 153/2014.

## 7. Open issues found along the way (not fixed here)

1. **11 cited documents have no chunks.** Their statutory LexML has an empty `<Articulacao>`, so
   the XSL produced 0 rows. They cannot be retrieved, although 16 references in 6 questions (Q149,
   Q150, Q154, Q158, Q159, Q666; mostly treaty decrees) cite them: `decreto_27784`, `decreto_59308`, `decreto_59309`,
   `decreto_62125`, `decreto_63151`, `decreto_85801`, `decreto_86006`, `decreto_86084`,
   `decreto_93153`, `in_srf_23_19830325` and `in_srf_67_19880421`. The earlier segmentation notes
   do not mention this. Fix it in parsing (for example, re-route them to the non-statutory parser,
   as was done for `in_srf_84_19791220`).
2. **Articles present in the `.docx` but missing from the XML:** MP 2.158-35 art. 24 (8
   references), Lei 6.404 art. 252, Lei 11.941 art. 56, Decreto 59.566 art. 3 ("Art 3º" without a
   period). Lei 13.043 art. 16 appears in the `.docx` only as a dotted placeholder. Decreto 361 art.
   13 and IN SRF 107 art. 1 are not in the `.docx` at all. `build_report.json →
   validation.article_ids_missing` lists all 19.
3. **Fetch the missing acts** in §5.2a (21 SC/AD/Parecer/DL acts, PN CST 38/1975, PN CST 72/1979, Res.
   TSE 22.250/2006, Parecer PGFN/CAT 815/2010) and copy the Diat `.docx` into `original/`. Then
   replace their overrides with the new stems and rebuild. Until then, report the legal-provision
   score over resolved references, or count unresolved ones as unmatchable gold.
4. **Duplicate in the corpus:** `parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015` repeats Nota 981/2015.
   It is harmless for scoring (nothing cites it now), but it adds a duplicate to retrieval.
5. **Non-statutory URN quality:** some committed URNs have the wrong authority or type, for example
   `nota_sei_48_2018` → `…procuradoria.geral.fazenda.nacional:nota.pgfn:2018;48`,
   `nota_pgfn_crj_1104_2017` → `…superior.tribunal.justica:solucao.consulta…`, and
   `parecer_pgfncat_815…` → `…:sumula:2015;981`. `document_urn` copies what the corpus has, so gold
   and chunks agree. Matching them against `lexml-linker` URNs of generated answers, however, will
   miss these. The §4.5 implementation should match at `document_id` level, or normalize both sides.
6. The fetcher's `canonical_referred_documents.json` still carries the errors in §5.2a–b. The
   corrections live only in `reference_overrides.json`.
7. Not verified: any remaining v1.1 extraction errors in provision details (paragraph/inciso lists),
   beyond the article-existence check.

## 8. Files

| Path | Content |
|---|---|
| `dataset/questions.jsonl`, `references.jsonl`, `documents.jsonl` | the v2.0 dataset |
| `dataset/README.md` | HF dataset card with the `configs:` block and the schema |
| `dataset/build_report.json` | counts, dropped/unresolved references, validation, input hashes, git commit |
| `scripts/dataset/build_v2_dataset.py` | the builder |
| `scripts/dataset/reference_overrides.json` | every hand decision, with its reason |
| `scripts/dataset/nonstat_lexml_map.tsv` | non-statutory `.docx` stem → LexML file |
| `scripts/dataset/README.md` | how to run it |
