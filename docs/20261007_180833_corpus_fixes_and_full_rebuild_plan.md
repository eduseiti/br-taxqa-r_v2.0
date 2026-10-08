# Corpus Fixes and Full Rebuild Plan (LexML → segmentation → dataset → embeddings → RAG)

**Generated:** 2026-10-07 18:08:33 (local time, from `date +%Y%m%d_%H%M%S`)
**Status:** plan. **Updated 2026-10-07** after five rounds of user review (§8): B1, B2 and B3 done;
fix 3 (Q187) added; PDF route tested; the user's `.docx` repairs for item 2 checked by re-parsing
(§3.1.1); the §1.2 removals (D3) done and Resolução TSE nº 22.250/2006 fetched (commit `7c44d73`).
Everything else is still to do.
**Executed 2026-10-08 (R1–R10):** results, deviations and open points in
`docs/20261008_010441_corpus_rebuild_results.md`.
**Builds on:** `docs/20260927_180401_dataset_v2_format_and_reference_fixes.md` (**the dataset note**;
§5.2, §7) and `docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md`
(**the caput plan**; D-A, D-B, C1–C10).
**Trigger:** the user's corrections to `original/` in commits `1db1c58` (Resolução TSE 22.205
renamed) and `ce032e6` (22 wrong documents replaced, Diat added, 11 documents moved to
`original/nao_articulados`), then `a575acc` and `7c44d73` (the follow-ups listed in §8).

---

## 0. Summary

The plan rebuilds every derived layer from `original/`:

```
original/ ──(parse)──► lexml/ ──(segment, with D-A/D-B variants)──► segmented/
     │                    │                                            │
     └──────(build_v2_dataset)──► dataset/ ◄───────────────────────────┘
                                     │
                     embeddings/ ──► runs/retrieval + runs/eval (new eval_id)
```

It also covers:

- the two requested reference fixes, Q313 and Q249 (§2);
- explanations and fixes for items 2, 5 and 6 of the dataset note's §7 (§3);
- **problems found while checking the new `original/`**, some of which block the rebuild (§1.2).

**Blockers to settle before step R1 (§5):**

| # | Problem | Proposed action |
|---|---|---|
| B1 | `ad_pgfn_3_20080918.docx` was deleted, but **Q179 cites it** (179-03, 179-06: "AD PGFN nº 3 de 18 de setembro de 2008"). Only Q280 cited AD PGFN 3/**2016** | **Done (2026-10-07):** restored with `git checkout 1db1c58 -- original/nao_articulados/ad_pgfn_3_20080918.docx`. The new `ad_pgfn_3_20160330` stays too |
| B2 | `SCI Cosit nº 24-2008.pdf` is **SCI Cosit nº 24, de 27/06/2008** (social-security exemption, CNAS). Q187 cites **SCI Cosit nº 27, de 07/07/2008** (private pension plans) | **Done (2026-10-07):** the PDF is removed (nothing cites SCI 24/2008). SCI 27/2008 cannot be found, so reference 187-02 is **dropped** (fix 3, §2.3) |
| B3 | 12 `.pdf` (13 before B2) and 3 `.odt` files. The non-statutory parser reads only `.docx/.html/.htm/.txt`, and `build_v2_dataset.py` globs only `*.docx`. The PDF names didn't follow `<type>_<number>_<YYYYMMDD>` | **Done (user, 2026-10-07):** PDFs renamed to the §1.3 stems; ODTs converted to `.docx`. Still to do: PDF → cleaned text (R1) and the `*.pdf` glob in the build |
| B4 | Stale LexML: `lexml/` still holds the XMLs of the removed documents and of the 11 moved ones. `segment_all.py` globs `lexml/articulados/*.xml` and `lexml/nao_articulados/*.xml`, so these would be **segmented and indexed** | Delete them in step R2 (§5) |

---

## 1. State of `original/` after the user's changes (checked 2026-10-07)

### 1.1 What changed

| Change | Files |
|---|---|
| Replaced in `articulados/` | `ade_rfb_3_20240402` → `adi_rfb_3_20160427`; `lei_8794_19931221` → `decreto_lei_8794_19460123` (added as `decreto-lei_…`, renamed to the `decreto_lei` prefix the build expects, and the old file removed in `7c44d73`; see 1.2) |
| Replaced in `nao_articulados/` (`.docx`) | `ad_pgfn_2_20180403` → `ad_pgfn_2_20160310`; `ad_pgfn_3_20080918` → `ad_pgfn_3_20160330` (**B1**); `pn_cst_38_19801031` → `pn_cst_38_19750324`; `pn_cst_72_nodate` → `pn_cst_72_19791218`; `resol_tse_22_20060523` → `resol_tse_22205_20060523` (rename only), then → `resol_tse_22250_20060629` (the cited act, fetched by the user; `7c44d73`) |
| Replaced in `nao_articulados/` (`.odt`, now `.docx`) | `sc_cosit_69_20200624` → `sc_cosit_69_20131230`; `sc_cosit_140_20230714` → `sc_cosit_140_20210921`; `sc_cosit_194_20230829` → `sc_cosit_194_20150805`. Converted by the user; the word counts equal the ODTs' (142/163/179). **Note:** these three hold only the published ementa (DOU), not the full SC text |
| Replaced in `nao_articulados/` (`.pdf`, renamed to the §1.3 stems) | SC Cosit 7/2017, 50/2020, 64/2014, 75/2020, 123/2021, 166/2019, 173/2015, 179/2023, 183/2014 (replaces `sc_cosit_134_20140602`), 211/2019, 214/2021, 354/2014; SCI Cosit 24/2008 (replaces `sd_cosit_27_20080530`; **B2**) |
| Added | `documento_de_informacao_e_apuracao_do_ITR_DIAT.docx` |
| Moved `articulados/` → `nao_articulados/` | `decreto_27784`, `_59308`, `_59309`, `_62125`, `_63151`, `_85801`, `_86006`, `_86084`, `_93153`, `in_srf_23_19830325`, `in_srf_67_19880421` |

I checked the first page of every new PDF/ODT and the opening of every new `.docx`: number and date
match the cited act in all cases except B2.

Of the removed documents, only `ad_pgfn_3_20080918` is cited by a question (B1). The others were
cited only through the wrong matches that the new files replace.

### 1.2 Remaining corpus issues

All four were settled by the user in commit `7c44d73` (2026-10-07):

| Item | State | Action |
|---|---|---|
| Resolução TSE nº 22.250/2006 (Q438, art. 14) | `resol_tse_22205_20060523` was a different act | **Done:** `resol_tse_22250_20060629.docx` fetched into `nao_articulados/`; `resol_tse_22205_20060523.docx` removed. **Q438 resolution fixed:** `"resolucao_tse": "resol_tse"` added to `PREFIX` (`build_v2_dataset.py`) and the `not_in_corpus` override deleted (62 `files` entries left). 438-03 now resolves `auto_undated` to `resol_tse_22250_20060629`, and `auto_exact` once R4 sets the canonical record's date (index 344) to 2006-06-29. The file has art. 14. **Moved to `articulados/`** (2026-10-07) after rejoining its hard-wrapped lines, so the statutory parse gives `art1…art50` and `art14` gets its own `Artigo` id (below the table) |
| `lei_8794_19931221` | cited by no question (the wrong match for DL 8.794/1946) | **Done:** removed. `decreto-lei_8794_19460123.docx` renamed to `decreto_lei_8794_19460123.docx` |
| `ade_cosit_30_20010723` | cited by no question (the wrong match for "Parecer Cosit nº 30") | **Done:** removed (fix 1, §2.1) |
| `parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015.docx` | a duplicate of `nota_pgfn_981_20151104` (dataset note §7.4) | **Done:** removed (fix 2, §2.2) |

**Statutory parse of Res. TSE 22.250 (tested 2026-10-07, scratchpad only).** Jar rebuilt from the
parser's HEAD (`ebf6567`, `mvn -Ponejar package`; the old `phase2.jar` path no longer exists). It
reproduces `lexml/articulados/lei_9250_19951226.xml` byte for byte.

- **As fetched, it fails.** The `.docx` has a hard break after every printed line (610 paragraphs for
  50 articles). Wrapped citations that start a line ("9.504/97, art. 24…", "22.") are read as
  dispositivos, and only 12 articles are top-level; the rest fall into a bogus `anexo1`.
- **With the lines rejoined, it is clean.** One paragraph per dispositivo (281 paragraphs): a line
  starts a paragraph only if it begins with a marker (`Art.`, `§`, `Parágrafo único`, `I –`, `a)`,
  TÍTULO/CAPÍTULO/Seção + title) **and** the previous line ends with `.`, `:` or `;`. Otherwise it is
  a wrapped citation such as "(Lei nº 9.504/97, art. 28," / "§ 2º).". Result: 0 parser warnings;
  `art1…art50` in order; 80 parágrafos, 95 incisos, 5 alíneas; 2 títulos, 11 capítulos, 10 seções;
  `art14` complete; URN `urn:lex:br:tribunal.superior.eleitoral:resolucao:2006-06-29;22250`. All but
  8 of the 5,938 source words are in the XML (the "Relator …" line is skipped as post-epigraph).
- **Profile:** `-a tribunal.superior.eleitoral -t resolucao -n 22250 --data 2006-06-29
  --prof-regex-epigrafe '^resolucao' --prof-regex-pos-epigrafe '^relator' --prof-regex-preambulo
  '^o tribunal superior eleitoral' --prof-epigrafe-head 'RESOLUÇÃO'`. Without the epigraph regex the
  parse stops at "Epígrafe ausente"; with `^ementa` in the post-epigraph regex it stops at "Ementa
  ausente". `batch_parse.py` needs these for the `resol_tse` stem in R3b.
- **R3b caveat:** in this shell `LANG=en_US.UTF-8` is set but that locale is not installed, so the
  JVM decodes non-ASCII arguments wrongly (`--prof-epigrafe-head 'RESOLUÇÃO'` → `RESOLU����O`). Run
  the parser with `LC_ALL=C.UTF-8`. The committed `lexml/` has no replacement characters.
- **Adopted (2026-10-07):** `original/articulados/resol_tse_22250_20060629.docx` is the rejoined file
  (moved from `nao_articulados/` with `git mv`; the as-fetched file is in `git` history). It was made
  with the new `scripts/lexml/rejoin_docx_lines.py`, which moves the runs of each wrapped line into
  the previous paragraph, so formatting is kept:
  `python3 scripts/lexml/rejoin_docx_lines.py <fetched>.docx original/articulados/resol_tse_22250_20060629.docx
  --start '^RESOLUÇÃO' --start '^Relator' --start '^Ementa' --start '^O Tribunal Superior Eleitoral'
  --start '^Sala de Sessões' --start '^Brasília,'`. Its output has the same paragraph text as the
  tested version, and the parse is byte-identical (0 warnings).

Removing uncited wrong matches keeps the corpus defined as "documents referred to by the Q&A".
Leaving them in only adds distractors that no question needs.

### 1.3 Converting the PDF and ODT files (B3)

**2026-10-07:** the user renamed every PDF to the target stem below and converted the ODTs. The
SC 354/2014 date was confirmed on the PDF ("17 de dezembro de 2014").

Target names follow `original/` conventions, so `build_v2_dataset.py` resolves them automatically
once the canonical list is fixed (§3.3):

| Source | Target stem | Date (from the document) |
|---|---|---|
| `SC_Cosit_n_50-2020.pdf` | `sc_cosit_50_20200622` | 22/06/2020 |
| `SC_Cosit_n_64-2014.pdf` | `sc_cosit_64_20140307` | 07/03/2014 |
| `SC Cosit nº 7-2017 .pdf` | `sc_cosit_7_20170113` | 13/01/2017 |
| `SC Cosit nº 75-2020.pdf` | `sc_cosit_75_20200625` | 25/06/2020 |
| `SC Cosit nº 123-2021.pdf` | `sc_cosit_123_20210913` | 13/09/2021 |
| `SC Cosit nº 166-2019.pdf` | `sc_cosit_166_20190528` | 28/05/2019 |
| `SC Cosit nº 173-2015.pdf` | `sc_cosit_173_20150703` | 03/07/2015 |
| `SC Cosit nº 179-2023.pdf` | `sc_cosit_179_20230816` | 16/08/2023 |
| `SC Cosit nº 183-2014.pdf` | `sc_cosit_183_20140625` | 25/06/2014 |
| `SC Cosit nº 211-2019.pdf` | `sc_cosit_211_20190624` | 24/06/2019 |
| `SC Cosit nº 214-2021.pdf` | `sc_cosit_214_20211220` | 20/12/2021 |
| `SC Cosit nº 354-2014.pdf` | `sc_cosit_354_20141217` | 17/12/2014 (cited date; confirm on the PDF, whose first page starts with a broken field "Erro: Origem da referência não encontrada") |
| `sc_cosit_69_20131230.odt`, `_140_20210921.odt`, `_194_20150805.odt` | same stems, `.docx` | already in the name |

Conversion:

- **ODT → DOCX (done by the user):** `soffice --headless --convert-to docx` (LibreOffice is not installed in this WSL
  image, so either install it or convert on the Windows side). The result is lossless for these
  plain-text documents.
- **PDF → text, no OCR (tested 2026-10-07 on SC Cosit 166/2019).** The PDFs are born-digital
  (embedded fonts), and `pdftotext -raw` extracts the full text. Extraction is easy; the problem is
  **layout**. The raw output has:
  1. page furniture on every page: `Cosit`, `Fls. N`, the page number, the header-box labels
     (`Processo`, `Interessado`, `CNPJ/CPF`), and in SC 354/2014 a broken field "Erro: Origem da
     referência não encontrada";
  2. a running header drawn in faux bold (each glyph printed twice, slightly shifted). It comes out as
     `S / So / ol / lu / uç …`;
  3. a hard line break at the end of every PDF line, so paragraphs are split into lines.

  Fed to `lexml_nonstat parse` as is, the whole document becomes **one `<p>`**, with the generic
  profile and a wrong URN (`urn:lex:br:federal:documento:2019-05-28;166`). After a small cleanup
  (drop items 1–2, rejoin lines into paragraphs at sentence ends, numbered paragraphs "2.", "3." and
  section headings, and de-hyphenate), the same file is parsed with the **`solucao_consulta`
  profile** and the right URN
  (`urn:lex:br:ministerio.fazenda;secretaria.receita.federal:solucao.consulta:2019-05-28;166`), as
  the existing SC `.docx` files are. The prototype is in this session's scratchpad. It becomes
  `scripts/lexml/pdf_to_text.py`, plus a rule list per page layout: there are two, the 2014–2021
  "Fls." layout and the 2023 "PROCESSO / SOLUÇÃO DE CONSULTA" layout of SC 179/2023.
  Known limits of the text route: quoted legal passages lose their indentation, which the parser
  uses as a "quoted" cue (the docx sources have the same warnings, so this is minor); a few
  headings ("Relatório", "Fundamentos") get joined to the next paragraph unless they are listed as
  breaks; and tables, if any, become lines. `pdf2docx` is the alternative if a PDF has tables.
- **Where things go:** the renamed `.pdf` stays in `original/nao_articulados/` as the source
  document. The cleaned text is a derived file, `lexml/nao_articulados/_text/<stem>.txt` (committed,
  so the parse is reproducible), and it is the parser input. `build_v2_dataset.load_documents` must
  glob `*.docx` **and** `*.pdf` (and `*.odt`, unless they are converted). ODTs are better converted
  to `.docx` in place, keeping the `.odt` in `original/nao_articulados/_sources/`.
- **Checks:** (i) parse each `.docx`/`.txt` with `lexml_nonstat parse --summary` and confirm a
  `DocumentoGenerico` with an ementa and the expected URN; (ii) text coverage: ≥ 98 % of the
  `pdftotext` word tokens (page furniture excluded) appear in the XML text.

---

## 2. The two requested reference fixes

Common facts:

- Neither citation appears in `answer_cleaned` (the gold answer), so **nuggets are not affected**.
- `answer` and `references_text` are verbatim copies of the Receita Federal PDF. **They are not
  edited:** they record what the source says. The correction lives in the `references` row, with
  a `resolution_note` that explains it. The fixes are applied everywhere else (tables below).
- The legal-provision score de-duplicates gold items per `(question, document)` key
  (`ragpipe/relevance.py: gold_items`), so a second reference to the same document does not count
  twice.

### 2.1 Fix 1 — Q313: remove "Parecer Cosit nº 30, de 28/09/2001"

The act does not exist. Only Q313 uses this v1.1 file name, and it is the last reference of Q313
(313-06), so no other `reference_id` changes.

| Place | Change |
|---|---|
| `scripts/dataset/reference_overrides.json → drop` | add `{"question_number": "313", "file": "Parecer Cosit nº 30, de 28 de setembro de 2001.txt", "reason": "user fix (2026-10-07): no such act exists; v1/v2 matched the unrelated ADE Cosit nº 30, de 23/07/2001 (US dollar rate)"}` |
| `reference_overrides.json → files` | delete the `"Parecer Cosit nº 30, de 28 de setembro de 2001.txt"` `not_in_corpus` entry (the drop makes it dead; the build should refuse dead overrides, §3.3) |
| `original/articulados/ade_cosit_30_20010723.docx` + `lexml/articulados/ade_cosit_30_20010723.{xml,err.log}` | `.docx` **done** (removed in `7c44d73`); the LexML files go in R2 |
| `../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json` (index 293) | mark the record `"status": "nonexistent_act"`, with `canonical_name: null` and a `correction` field (§3.3) |
| `dataset/references.jsonl`, `questions.jsonl` (`document_ids`, `n_unresolved_references`: 1 → 0), `build_report.json` (`dropped_references` gains it), `dataset/README.md` counts | regenerated by the build |
| `docs/20260927_180401_…md` §5.2a table row and §6 counts | append a dated correction note; don't rewrite the row |

### 2.2 Fix 2 — Q249: "Parecer PGFN/CAT nº 815/2010" → Nota PGFN/CRJ nº 981/2015

Only Q249 uses the v1.1 file `Parecer PGFNCAT nº 815 2010.txt`. Q249 **already cites** Nota 981/2015
as `249-04` (→ `nota_pgfn_981_20151104`). There are two ways to apply the fix:

- **(a) Recommended: re-point 249-03** to `nota_pgfn_981_20151104` through the `files` override.
  `reference_id`s stay stable, `cited_title` keeps the PDF's wording, and the `resolution_note`
  states the correction. Scoring is unchanged by the duplicate (de-duplicated gold items).
- (b) Drop 249-03. This gives the same scoring result, but it shifts `249-04…249-16` to `249-03…249-15`.

| Place | Change |
|---|---|
| `reference_overrides.json → files["Parecer PGFNCAT nº 815 2010.txt"]` | `{"document_id": "nota_pgfn_981_20151104", "reason": "user fix (2026-10-07): the citation is replaced by Nota PGFN/CRJ nº 981/2015 (the document v1 held under this name; also cited as 249-04)"}` |
| `original/nao_articulados/parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015.docx` | **done** (removed in `7c44d73`; duplicate, dataset note §7.4) |
| `lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_sumula_2015_981.xml` and its row in `scripts/dataset/nonstat_lexml_map.tsv` | remove (this is also the wrong URN of item 5) |
| fetcher canonical record (index 332) | `canonical_name: "Nota PGFN/CRJ nº 981/2015"`, `type_slug: nota_pgfn`, `number: 981`, `correction` field (§3.3) |
| `dataset/*`, `build_report.json` (`unresolved_references` loses 249-03; Q249 `n_unresolved_references` 1 → 0) | regenerated |
| dataset note §5.2a row | dated correction note |

### 2.3 Fix 3 — Q187: remove "Solução de Consulta Interna Cosit nº 27, de 7 de julho de 2008"

The act cannot be found (user, 2026-10-07). The PDF fetched for it, `SCI Cosit nº 24-2008.pdf`, is
SCI 24 of 27/06/2008, a different act that no question cites, so it was removed (B2). Only Q187 uses
this v1.1 file name, and 187-02 is the last reference of Q187, so no other `reference_id` changes.
Q187 keeps 187-01 (Lei 7.713, art. 6).

| Place | Change |
|---|---|
| `scripts/dataset/reference_overrides.json → drop` | **done:** `{"question_number": "187", "file": "Solução de Consulta Interna Cosit nº 27, de 7 de julho de 2008.txt", "reason": "user fix (2026-10-07): … cannot be found …"}` |
| `reference_overrides.json → files` | **done:** its `not_in_corpus` entry deleted |
| `original/nao_articulados/SCI Cosit nº 24-2008.pdf` | **done:** removed |
| fetcher canonical record | `status: "not_found"` (§3.3) |
| `dataset/*`, `build_report.json` | regenerated in R5 (Q187 `n_unresolved_references` 1 → 0) |
| dataset note §5.2a row | dated correction note |

---

## 3. Items 2, 5 and 6 of the dataset note's §7

### 3.1 Item 2 — articles that are in the `.docx` but not in the XML

**What it means.** The dataset checks each cited article (e.g. `art24`) against the `id`s in the
document's LexML. For 28 cited article ids (`build_report.json → validation.article_ids_missing`),
no `<Artigo id="artN">` exists. A gold provision that the XML lacks has **no chunk**. So no retriever
can find it, and the legal-provision score counts it as a miss for every system. That depresses all
strategies equally and adds noise to S1-vs-S2 comparisons.

I traced every case to its cause. There are six:

| # | Cause | Cases (references) | Evidence | Fix |
|---|---|---|---|---|
| 2a | **Revoked text is dropped.** Planalto marks revoked text with strike-through, and the parser drops struck runs, which takes the whole article with them | MP 2.158-35 **art. 24** (560-15, 617-01, 618-02, 618-09, 620-01, 620-08, 621-02, 624-04) | Art. 24 is struck, "(Revogado pela Lei nº 14.754, de 2023)". XML has `art23`, `art25` and no `art24` | **Important:** the P&R IRPF 2024 covers calendar year 2023, before the revocation took effect. The article is still the right legal basis, so it must be in the corpus. Keep struck articles as text and mark them revoked, rather than dropping them (preprocessing: remove `<w:strike/>` from runs of an article whose last run says "(Revogado …)", and keep the note in the text). Apply corpus-wide (audit, below) |
| 2b | **A heading read as the start of a bill's "Justificação".** The parser is the *projeto de lei* parser, and its `regexJustificativa` marker ends the articulação | Lei 6.404 **art. 252** (584-01); in fact **arts. 225–300 are all missing** | The paragraph "Justificação" is the section heading of art. 225. XML stops at `art224`; `ProjetoLei.scala:172,187` | Re-parse statutory documents with `--prof-regex-justificativa` set to a never-matching pattern: enacted acts have no justification section |
| 2c | **Unclosed amendment quote.** The text after an `Alteracao` is taken as more quoted text, so the act's own articles become `Artigo` elements *inside* the amendment and get no rows of their own (caput plan §3) | Lei 11.941 **art. 56** (312-02); in fact arts. **15–24 and 48–72** are nested (`art47_cpt_alt1_art56` …) | Top-level ids jump `art14 → art25` and `art47 → art73` | Fix the quotes in the `.docx` (add the missing closing `”`/`(NR)`, or split the block) and re-parse. The audit below finds the other cases. **Correction (2026-10-07):** arts. 15–24 are *not* a parser fault: the `.docx` has one line, "Arts. 15 a 24. (Revogados pela MP nº 627/2013, convertida na Lei nº 12.973/2014)" |
| 2d | **Label split across two paragraphs** ("Art" / "3º Arrendamento rural …") | Decreto 59.566 **art. 3** (480-02) | Its §§ 1–3 were attached to art. 2 (`art2_par1..3`): the gold is missing *and* art. 2 holds wrong text | Merge the two paragraphs in the `.docx` and re-parse |
| 2e | **Text not in the source.** Planalto prints the article as a dotted placeholder | Lei 13.043 **art. 16** (677-02, 677-04, 699-02, 699-04) | No paragraph starts with "Art. 16" | Take the text from the DOU (original publication) and add it to the `.docx`, citing the source in `original/…/README` or in a dated note. Otherwise mark these provisions `unmatchable` (below) |
| 2f | **Treaty articles.** The question cites an article of a *promulgated treaty*, not of the decree. The treaty text is either missing from the `.docx` (only the 2-article promulgating decree was fetched) or present but numbered `ARTIGO I…`, which the statutory parser does not read as articles | 149-01, 149-03, 150-05, 150-12 (decretos 27.784, 59.308); 152-01, 153-01 (57.942: no article markers at all); 153-04 (361: treaty text absent); 154-01 (86.084); 155-01 (87.563: `ARTIGO I…XXV`); 157-02 (8.289: `Artigo I…XIV` in annex 1); 158-02 (85.801: treaty absent); 159-01 (93.153: treaty absent) | `.docx` paragraph counts of 10–13 for 27.784, 85.801, 93.153 and 361 | (i) Fetch the treaty texts where they are missing (the DOU/Senado publication). (ii) After the move to `nao_articulados`, these documents have no `Artigo` ids at all. So map treaty articles to the non-statutory blocks: the non-statutory segmenter emits each `ARTIGO N` heading as a block boundary, and the build records `fragment_id = null`, `block_label = "ARTIGO V"`, matched by label. (iii) Until then, score them at **document level only** |

#### 3.1.1 Status after the user's `.docx` repairs (checked 2026-10-07)

The user repaired MP 2.158-35, Lei 11.941, Decreto 59.566 and Lei 13.043 (the working tree is not
committed). Lei 6.404 was not changed. I re-parsed all five with the **same jar** that produced
today's `lexml/` (`phase2.jar`, the command line in each `.err.log`) into the session scratchpad,
and compared the top-level `Artigo` ids with the committed XML and with the `.docx` article labels.

| Document | What the user changed | Top-level articles (old → new) | Cited article | Result |
|---|---|---|---|---|
| MP 2.158-35 (2a) | New source text: no strike-through runs (76 struck paragraphs → 0); art. 24 is plain text, without the "(Revogado …)" note | 89 → **93**, equal to the 93 `Art.` paragraphs of the `.docx`, no gaps | `art24` ✔ (full text, §§ 1–7) | **Fixed.** No duplicate-label warnings, so no superseded wordings were left in. The text is the version in force in 2023, which suits the P&R 2024 |
| Lei 11.941 (2c) | Added the closing `…” (NR)` after art. 47's amendment block | 45 → **70**, equal to the `.docx` | `art56` ✔ | **Fixed.** The only gap, arts. 15–24, is the collective revocation (see 2c). Arts. 48–72 are now top-level |
| Decreto 59.566 (2d) | Merged "Art" + "3º …"; also joined four broken quoted fragments (`" b` / `"`) and fixed `Art 41.O` | 88 → **89**, equal to the `.docx` | `art3` ✔ (and §§ 1–3 are back under art. 3) | **Fixed** |
| Lei 13.043 (2e) | **Round 1:** new source, the Planalto compilation instead of the Câmara text (art. 16 present; arts. 2 etc. in the wording before MP 1.303/2025). **Round 2:** fixed the two amendment closings (end of art. 50 and art. 84). **Round 3:** removed the superseded wordings of arts. 19, 42 and art. 22 § 1º | 103 → **115**, equal to the 115 `.docx` labels; no gaps, no duplicate ids, arts. 51–53 and 85 top-level, `art28-1` present | `art16` ✔ | **Fixed.** 0 duplicate-label warnings (29 before). Kept: art. 19 = original wording (caput + §§ 1–3); art. 42 = the Lei 13.097/2015 wording; art. 22 § 1º = "O percentual referido no caput poderá variar…" (the first of the two wordings; confirm on Planalto that it is the one in force in 2023). Heading typos remain (minor, below) |
| Lei 6.404 (2b) | **Round 2:** deleted the "Justificação" heading paragraph before art. 225 (the only change in the `.docx`) | 232 → **314**, up to `art300`, equal to the `.docx` (A-articles included, e.g. `art4-1`, `art299-2`) | `art225`, `art252` ✔ | **Fixed**, with or without `--prof-regex-justificativa`. Its 6 duplicate-label warnings (arts. 59, 140, 183) were already in the committed parse. R3b still passes the flag for all statutory documents, as a guard |

**Lei 13.043: what is left (after round 3).** Only cosmetic: split words in headings, "Do s Fundos…",
"D a Isenção…", "D a Contribuição…", "D a Legislação Aduaneira", "D a Legislação Tributária…",
"D a Alienação Fiduciária", and "PRESIDENTE DA REPÚBLIC A Faço saber" in the preamble. They reach
only the grouping chunks (S3) and the preamble, not article chunks. Fixing them is optional and does
not change any article id.

**All five item-2 `.docx` repairs are done** (MP 2.158-35, Lei 11.941, Decreto 59.566, Lei 6.404, Lei 13.043). The remaining item-2 cases are the treaty articles (2f) and whatever the corpus-wide audit finds.

**Corpus-wide audit (new, `scripts/lexml/audit_article_coverage.py`).** Every case above was found
only because a question cites the article. Others surely exist. For each statutory `.docx`, list the
paragraphs that start an article (`^Art\.?\s*\d+`, outside quotes) and compare them with the
top-level `Artigo` ids of the XML (main plus annexes). Report missing, nested-in-`Alteracao` and
out-of-order ids per document, flagging cited documents first. Run it after R3, and fix by cause
(2a–2e). Gate: no cited article missing, unless it is listed in an `unmatchable` table with a
reason.

**Scoring rule for what remains:** the build marks each remaining provision `"matchable": false`.
`ragpipe/relevance.py` then reports metrics over matchable gold, with the unmatchable count shown
next to them. That is better than silently counting them as misses.

### 3.2 Item 5 — wrong authority or type in non-statutory URNs

**What it means.** Each document's URN (`urn:lex:br:<authority>:<type>:<date>;<number>`) is its
identity across the pipeline: `document_urn` in the dataset, `doc_urn` in the chunks, and the
`Remissao` links that `lexml-linker` writes when it finds "Nota PGFN/CRJ nº 1.104/2017" in a text.
The non-statutory parser **infers** authority and type from the document's text and profile, and
for some documents it guessed wrong. Today gold and chunks agree, because both copy the same wrong
URN. But the planned legal-provision check on *generated answers* would extract the citation with
`lexml-linker`, get the *correct* URN, and fail to match.

Audit of the 234 current non-statutory URNs, grouped by stem prefix (consistent groups omitted):

| Stem prefix | URN authority : type | Should be |
|---|---|---|
| `nota_pgfn_981…` | `…receita.federal : sumula` | `procuradoria.geral.fazenda.nacional : nota` |
| `nota_pgfn_crj_*` (3) | `pgfn : nota.pgfn`, `superior.tribunal.justica : solucao.consulta`, `…receita.federal : portaria` | `procuradoria.geral.fazenda.nacional : nota` |
| `nota_sei_48_2018` | `pgfn : nota.pgfn` | the issuing body of the SEI note (to check) |
| `par_pgfn`, `parecer_pgfn_crj` (2), `parecer_pgfn_pga` (2), `parecer_sei` (3), `parecer_pgfncat_1503` | `superior.tribunal.justica`, `…receita.federal`, `ministerio.fazenda`, `federal` | `procuradoria.geral.fazenda.nacional : parecer` (SEI pareceres: issuing body as printed) |
| `sc_*` (1 of 2) | `federal : solucao.consulta` | `…receita.federal : solucao.consulta` |
| `in_srf_84_19791220` | `…receita.federal : ato.declaratorio` | check: the stem says IN SRF, the URN says AD |
| the 11 moved documents | not parsed yet | the **statutory** URNs they had (`urn:lex:br:federal:decreto:1950-02-16;27784`, …), which `lexml-linker` produces for "Decreto nº 27.784" |

**Fix.** Make URNs **declared, not inferred**, for this corpus:

1. Add `scripts/lexml/nonstat_metadata.tsv` (stem → authority, type, date, number), generated from
   the stems and the (fixed) canonical records, then reviewed by hand. The 20 documents whose parser
   date was `0000` (dataset note §4.1) also go here.
2. Upstream, in `../lexml_parser_non_statutory`, add `parse --urn <urn>` (or `--metadata <tsv>`).
   This overrides the inferred URN in `Identificacao`, in the output file name and in `@xlink:href`
   bases. Until it lands, a post-parse rewrite step in this repo does the same
   (`scripts/lexml/fix_nonstat_urns.py`).
3. **Normalize URN vocabulary with `lexml-linker`.** For each corrected type, run the linker on the
   document's own title ("Nota PGFN/CRJ nº 981/2015") and require that it yields the same URN. That
   check is the actual goal, and it also catches type spellings (`nota` vs `nota.pgfn`).
4. Since all non-statutory XMLs are re-parsed anyway (R3), regenerate `nonstat_lexml_map.tsv`
   **from the parse output** instead of by matching. The re-parse + manual pairing of dataset note
   §4.1 is no longer needed.
5. Build check (new): `document_urn` equals the linker URN of `cited_title` for every resolved
   reference whose title has a number. List the exceptions (colloquial titles, treaties).

### 3.3 Item 6 — the fetcher's canonical list still carries the errors

**What it means.** `canonical_referred_documents.json` (in `../br-taxqa-document-fetcher`) maps each
v1.1 file name to the act it *should* be (type, number, date). `build_v2_dataset.py` uses it to find
the `original/` stem automatically (`prefix + number + date`). For the 26 acts of dataset note §5.2a
and the 2 of §5.2b, the record names the **wrong** act, because the fetcher picked a
same-numbered act from another year. For example, `Solução de Consulta Cosit nº 50.txt` → "SC
Cosit nº 50, de 22 de março de **2024**", and `Parecer Cosit nº 30…txt` → "ADE Cosit nº 30". The
corrections were put only in this repo's `reference_overrides.json`, as `not_in_corpus` entries.
Consequences:

- the canonical list, which is the fetcher's source of truth and the input of any re-fetch, still
  says to fetch the wrong acts;
- now that the right documents are in `original/` with proper stems, the build **still** resolves
  them through the overrides, which say `not_in_corpus`. Without a fix, the 22 new documents would
  remain uncited and the 42 references unresolved;
- two sources of truth disagree, and nothing checks them against each other.

**Fix.**

1. **Correct the records in the fetcher** (`scripts/fix_canonical_records.py` there, driven by a
   reviewed JSON of corrections). For each §5.2a/b record, set `canonical_name`, `type_slug`,
   `number`, `date` to the cited act, `source: "manual"`, and add
   `"correction": {"date": "2026-10-07", "was": "<old canonical_name>", "reason": "…"}`. Special
   cases:
   - `Parecer Cosit nº 30…` → `status: "nonexistent_act"` (fix 1);
   - `Parecer PGFNCAT nº 815 2010.txt` → Nota PGFN/CRJ 981/2015 (fix 2);
   - `Solução de Consulta Interna Cosit nº 27…` → `status: "not_found"` (fix 3: the act cannot be
     found; the record's current target, SD Cosit 27/2008, is a different act);
   - `Solução de Consulta Cosit nº 183.txt` → nº **183**, 25/06/2014 (the record had 134);
   - IN RFB 1.997/2019 (§5.2b) and the Convenção … Nações Unidas (→ `decreto_27784`);
   - `Resolução TSE nº 22.250, de 2006.txt` (index 344) → `date: 2006-06-29` (now in `original/`).
     The build's `PREFIX` already has `resolucao_tse → resol_tse` (§1.2).
   Also regenerate `output_canonical/by_type/*.md`, and record the change in a dated note in the
   fetcher repo.
2. **Make this repo trust the corrected list.** Delete from `reference_overrides.json → files` every
   `not_in_corpus` entry whose act is now in `original/`; they then resolve as `auto_exact`. What
   remains in `files` are true hand mappings (stems with no date, treaties). `drop`, `reassign`
   and `citations` stay, since they are per-question decisions that do not belong in the fetcher.
3. **New build guards in `build_v2_dataset.py`:**
   - *dead override*: fail if a `files` override is never used, or if its file name is fully covered
     by `drop`;
   - *redundant override*: warn when the automatic resolution gives the same answer as the override;
   - *contradiction*: fail if an override says `not_in_corpus` but the canonical record resolves
     `auto_exact`;
   - *uncited document*: list stems in `original/` that no question cites (the corpus should be
     exactly the cited set, plus a whitelist).
4. Pin the canonical file's SHA-256 in `build_report.json` (already done) **and** print the fetcher's
   git commit next to it.

---

## 4. Segmentation: the caput plan, adapted to a changed corpus

The caput plan assumed an **unchanged corpus**: invariant (i) "every non-paragraph-family `base` row
is byte-identical to the frozen set", reuse of frozen `chunk_id`s for `caput` rows, and embedding
with `--extend` for only the 29,876 new texts. After this rebuild many documents change (new,
removed, re-routed, re-parsed with fixes 2a–2d, new URNs), so these assumptions are relaxed:

| Caput plan item | Change in this plan |
|---|---|
| D-A, D-B, S1–S5 definitions, `variante` column, `contexto_ids` (§4.1–4.2) | **unchanged** |
| C1–C3, C6–C8, C10 | **unchanged** (implement as written) |
| C4 `--chunk-id-source` (reuse frozen ids) | **Dropped.** Old and new results are not comparable anyway, because the corpus differs. Chunk ids are assigned fresh: `<stem>#<seq>` for `base`, `<stem>#c<seq>` for `caput` |
| C5 `base_unchanged`, `caput_variant_frozen` | Replace with **`diff_vs_frozen`**: restricted to documents whose LexML SHA-256 did not change, base rows must equal the frozen ones and `caput` rows the frozen paragraph-family rows. The check reports, not gates, the documents that changed. The other C5 checks stay |
| C9 `--extend` | Generalize to **embed by text hash**: reuse any vector whose `texto_sha256` is in the existing store, and embed only new texts. This covers both the caput-free texts and the changed documents, and it is still much cheaper than a full re-embed |
| §4.6 renaming of old results | Still true (old S2/S3 = S2c/S4 on the **old corpus**). New runs use a new `eval_id` and new manifests |

Open questions Q1–Q3 of the caput plan, defaults taken unless the user says otherwise: **Q1** keep
the 128-token ementa; **Q2** keep the caput sentence in the HEAD of split ART parts; **Q3** S5 later.

Also in segmentation:

- `classify_annexes.check_counts` will fail, because category counts change (new annexes, the
  re-parse of Lei 6.404, treaty annexes). Run with `--allow-count-change` once and record the new
  counts.
- The 11 moved documents become TXT/TAB chunks (non-statutory path), with the statutory URNs of
  §3.2.

---

## 5. Rebuild order

Each step ends with its check. Commit after each **R**-step, so that a failure can be bisected.

| Step | What | Commands / files | Check |
|---|---|---|---|
| **R0** | Decisions (§7) + blocker B4 (B1–B3 done) | §1.2 removals **done** (`7c44d73`) | `git status` shows exactly the intended `original/` changes |
| **R1** | PDF → cleaned text (§1.3; ODTs already converted) | `scripts/lexml/pdf_to_text.py` → `lexml/nao_articulados/_text/`; `build_v2_dataset.load_documents` globs `*.pdf` too | §1.3 checks (i), (ii) |
| **R2** | Clean stale LexML | delete `lexml/articulados/{11 moved stems, ade_rfb_3_20240402, ade_cosit_30_20010723, lei_8794_19931221}.*` (`decreto_lei_8794_19460123` and `resol_tse_22250_20060629` are new and parsed in R3b; the latter with the TSE profile of §1.2 and `LC_ALL=C.UTF-8`), and every `lexml/nao_articulados/*.xml` (fully regenerated in R3) | for each folder, the set of `lexml` stems equals the set of `original` stems |
| **R3a** | `.docx` repairs for item 2: MP 2.158-35, Lei 11.941 and Decreto 59.566 **done**; Lei 6.404 and Lei 13.043 **done** (Lei 13.043 heading typos optional); then the repairs that the audit finds | edit the `.docx` (pre-edit copies stay in `git` history; list the edits in the results note) | §3.1.1 re-parse check per document: top-level ids = `.docx` article labels, no duplicate-label warnings |
| **R3b** | Re-parse **statutory**: all of `original/articulados` (≈ 205 stems), with a pinned, reproducible jar | `../lexml-parser-projeto-lei/scripts/batch_parse.py` with a pinned jar: the old logs point at `phase2.jar` in another session's scratchpad (`/tmp/claude-0/-work-unicamp-articles-RAG-evaluation-lexml-parser-projeto-lei/…/phase2.jar`, still present and used for the §3.1.1 check). Copy it to a stable path, or rebuild it from the parser repo's commit and check that both produce identical XML, and record its SHA-256 in `lexml/articulados/PARSER_VERSION`, `--prof-regex-justificativa` never-match (2b), `--linker /usr/local/bin/linkertool` | `skipped_report.txt` reviewed; `audit_article_coverage.py` (§3.1) passes or lists `unmatchable` |
| **R3c** | Re-parse **non-statutory**: all of `original/nao_articulados` (≈ 247 stems), declared URNs (§3.2) | `python -m lexml_nonstat parse -o lexml/nao_articulados/ …` + `fix_nonstat_urns.py` until `--urn` exists upstream; regenerate `scripts/dataset/nonstat_lexml_map.tsv` from the output | XSD-valid; URN = `nonstat_metadata.tsv`; linker round trip (§3.2 step 3) |
| **R4** | Fix the canonical list in the fetcher (§3.3 step 1) | `../br-taxqa-document-fetcher` commit | 28 corrected records + 1 `nonexistent_act` |
| **R5** | Dataset | `reference_overrides.json` (§2, §3.3 step 2) + build guards (§3.3 step 3), the `matchable` flag (§3.1) → `python3 scripts/dataset/build_v2_dataset.py` | see the expected deltas below; tests in `scripts/dataset/tests` updated |
| **R6** | Segmentation code: caput plan C1–C5, C10, adapted as in §4 | `scripts/segmentation/*` | unit tests + XSL/Python parity with both `caput_em_paragrafo` values |
| **R7** | Full segmentation run → new frozen set | `python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change --variants caput` | `validate_segments.py` passes; `diff_vs_frozen` report; **no cited document without chunks** (`build_report → cited_documents_without_chunks` empty after re-running R5 against the new chunks) |
| **R8** | Embeddings | C9 generalized (embed by text hash) → `embed.py corpus --model jua-4b-mixed --extend`; parity gate; queries unchanged | store covers every `texto_sha256` of the new `chunks_all` |
| **R9** | RAG: C6, C7 (`variantes`, S2c/S4, new `expected_rows` and chunk-file SHA-256) | `rag.py retrieve` + `evaluate` for S1, S2, S3, S2c, S4 with a **new `eval_id`** (e.g. `v2c_either_containment_skip`) | report and metrics written; old `runs/…/either_containment_skip` untouched |
| **R10** | Notes and docs (§6) | — | — |

**Expected dataset deltas after R5** (to check, not to force):

- `not_in_corpus`: 42 → **0**. 249-03 is re-pointed (fix 2), 313-06 and 187-02 are dropped
  (fixes 1 and 3), 438-03 resolves to `resol_tse_22250_20060629` (§1.2), and the other 38 resolve
  `auto_exact` to the new documents (SCs, ADs, ADI 3/2016, DL 8.794/1946, PN CST 38/1975 and
  72/1979, Diat).
- Questions with ≥ 1 unresolved reference: 37 → **0** (Q438 included).
- Dropped references: 7 → **9** (+ 313-06, 187-02).
- Q179 unchanged (B1 restored); Q249 and Q313 `n_unresolved_references` → 0.
- Corpus documents: 459 → **458**. After B1 and B2, `original/` held 461 files (`.docx` + `.pdf`);
  `7c44d73` removed 4 (D3) and added Res. TSE 22.250, so it now holds **458**.
- `article_ids_missing`: 28 → only the `unmatchable` list.

---

## 6. Notes and documentation to update (R10)

| File | Update |
|---|---|
| new `docs/<ts>_corpus_rebuild_results.md` | what was run, counts before/after, `diff_vs_frozen` summary, new IR results (S1/S2/S3/S2c/S4) |
| `docs/20260927_180401_…dataset_v2…md` | dated header note: §5.2a rows resolved by the 2026-10-07 corpus fix; fixes 1–2; §7 items 1–6 status with a pointer here |
| `docs/20261005_184116_…caput…md` | header note: C4/C5/C9 adapted (§4 here) |
| `docs/20260927_222210_retrieval_legal_provision_test_jua.md` | header note: old corpus; S2/S3 = S2c/S4 |
| `docs/20260923_193852_…strategies…md`, `docs/20260924_123747_…plan.md` | the caput plan's §6 updates |
| `CLAUDE.md` | strategy list (S4/S5), `_sources/` folder, `scripts/lexml/` |
| `dataset/README.md`, `scripts/dataset/README.md` | counts, the `matchable` field, the guards, the canonical-list dependency |
| `scripts/segmentation/README.md`, `scripts/rag/README.md`, `scripts/embedding/README.md` | as in the caput plan §6, plus "embed by text hash" |

---

## 7. Decisions needed from the user

| # | Question | Recommendation |
|---|---|---|
| D1 | B1: restore `ad_pgfn_3_20080918` (Q179)? | **Decided: yes, done** |
| D2 | B2: SCI 24/2008 PDF and Q187 | **Decided:** PDF removed; 187-02 dropped (fix 3) |
| D3 | Remove the uncited wrong matches (`lei_8794_19931221`, `ade_cosit_30_20010723`, `resol_tse_22205_20060523`) and the Nota-981 duplicate? | **Decided: yes, done** (`7c44d73`); Res. TSE 22.250 fetched as well |
| D4 | Q249: re-point 249-03 (a) or drop it (b)? | **(a)**, stable ids |
| D5 | MP 2.158-35 art. 24 and other revoked articles: keep them as text marked "revogado" (2a)? | **Done for MP 2.158-35** (the user used a source without strike runs). For other documents, the audit decides; whatever the source, each article must appear once, in its 2023 wording |
| D6 | Lei 13.043 art. 16 (2e): add the DOU text, or mark it unmatchable? | **Done** (Planalto source). The remaining Lei 13.043 items are in §3.1.1 |
| D7 | Treaty articles (2f): fetch the missing treaty texts and match by block label, or score at document level only? | Fetch them; document level only until done |
| D8 | URN fix (item 5): upstream `--urn` option in `lexml_parser_non_statutory`, or post-parse rewrite here? | Upstream, with the rewrite as a stop-gap |
| D9 | Caput plan Q1–Q3 | the defaults in §4 |

---

## 8. Review log

**2026-10-07, after the user's review:**

- D1: `ad_pgfn_3_20080918.docx` restored from `1db1c58`.
- D2: SCI 24/2008 PDF removed (no question, reference or canonical record mentions it). Q187's
  SCI 27/2008 reference dropped (fix 3, §2.3); `reference_overrides.json` validated as JSON (63
  `files`, 8 `drop` entries).
- The user will rename the PDFs to the target stems of §1.3.
- PDF text extraction without OCR: confirmed and tested (§1.3).
- **Found while checking:** `build_v2_dataset.py` reads `--questions` by default from
  `../questions_QA_2024_v1.1_manual_fix.json`, which no longer exists. The copy
  `../br-taxqa-document-fetcher/questions_QA_2024_v1.1.json` has the same SHA-256 as the one recorded
  in `build_report.json` (`097abfc4…1585`). R5 passes it with `--questions`, or the default is
  changed to that path.
- The dataset has **not** been rebuilt yet: as it stands, the build would fail on the new stems
  missing from `nonstat_lexml_map.tsv` (R3c).

**2026-10-07, second review (`.docx` repairs and PDF renames):**

- PDFs renamed to the §1.3 stems; ODTs converted to `.docx` (text identical to the ODTs). B3 done
  except the text extraction (R1).
- Item 2 repairs re-parsed and checked (§3.1.1): MP 2.158-35, Lei 11.941 and Decreto 59.566 are
  fixed. Lei 13.043 has art. 16 now, but two amendment closings are malformed (arts. 51–53 and 85
  nested) and superseded wordings of arts. 19, 22 and 42 are merged. Lei 6.404 needs only the
  parser flag, tested.
- Correction to 2c: Lei 11.941 arts. 15–24 are revoked collectively; there is no parser defect.
- The re-parsed XMLs are only in the session scratchpad; `lexml/` is unchanged until R3b.

**2026-10-07, third review (Lei 6.404 and Lei 13.043, round 2):**

- Lei 6.404: the "Justificação" heading was removed; the re-parse gives all 314 articles (225 and 252
  included), with or without the parser flag. Done.
- Lei 13.043: both amendment closings fixed (arts. 51–53 and 85 are top-level), and the Word lock
  file is gone. Still open: the duplicate versions of arts. 19 and 42 (now duplicate XML ids) and
  of art. 22 § 1º, plus the heading typos (§3.1.1 items 2–3).

**2026-10-07, fourth review (Lei 13.043, round 3):**

- Superseded wordings removed. Re-parse: 115 top-level articles = 115 `.docx` labels, no gaps, no
  duplicate ids, 0 duplicate-label warnings. All five item-2 `.docx` repairs are done.
- To confirm: the art. 22 § 1º wording kept is the first one ("…referido no caput poderá variar…").
- Optional: heading typos in Lei 13.043 ("D a …", "Do s …", "REPÚBLIC A").

**2026-10-07, fifth review (§1.2 removals, commit `7c44d73`):**

- `decreto-lei_8794_19460123.docx` renamed to `decreto_lei_8794_19460123.docx` (the build's
  `decreto_lei` prefix; the hyphenated name would not have resolved).
- Removed: `lei_8794_19931221.docx`, `ade_cosit_30_20010723.docx`,
  `parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015.docx`, `resol_tse_22205_20060523.docx`.
- Added: `resol_tse_22250_20060629.docx` (`nao_articulados/`), the act Q438 cites. `original/` now
  holds 458 files.
- Q438: `resolucao_tse → resol_tse` added to the build's `PREFIX`, and the `not_in_corpus` override
  deleted. `resolve()` returns `resol_tse_22250_20060629` (`auto_undated`); the
  `port_conj_tse_srf_74` record is unaffected; `scripts/dataset/tests` pass (36). Open: the act sits
  in `nao_articulados/`, so `art14` will lack an `Artigo` id (§1.2).
- D3 done. The stale LexML of the removed documents (including
  `…resolucao.tse_2006-05-23_22205.xml` and `…sumula_2015_981.xml`) is deleted in R2 (B4).
- The commit also added the Word lock file `original/articulados/.~lock.lei_13043_20141113_fix.docx#`,
  which is already deleted in the working tree; commit that deletion (and consider a `.~lock.*`
  entry in `.gitignore`).

**2026-10-07, sixth review (Res. TSE 22.250 to the statutory path):**

- The as-fetched `.docx` breaks the statutory parse (hard line breaks; 12 of 50 articles top-level).
  Rejoined with the new `scripts/lexml/rejoin_docx_lines.py` and moved to
  `original/articulados/resol_tse_22250_20060629.docx`. Parse check: 0 warnings, `art1…art50`, `art14`
  complete (§1.2). `resolve()` still returns it for 438-03.
- The parser jar for R3b can be rebuilt from `../lexml-parser-projeto-lei` HEAD (`ebf6567`) with
  `mvn -Ponejar package`; it reproduces `lei_9250_19951226.xml` byte for byte. The `phase2.jar` path
  in the `.err.log` files no longer exists.
