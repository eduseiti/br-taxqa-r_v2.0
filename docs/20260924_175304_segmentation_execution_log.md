# Segmentation Implementation — Execution Log

**Started:** 2026-09-24 17:53:04 (local time, from `date +%Y%m%d_%H%M%S`)
**Executes:** `docs/20260924_123747_segmentation_implementation_plan.md` (referred to as **the plan**;
§ numbers point into it).
**Code:** `scripts/segmentation/` · **Outputs:** `segmented/`

---

## 0. Environment setup

- `python3` 3.12.3; `saxonche` 13.0.0, `lxml` 6.1.1, `pandas` 3.0.3 and `pytest` 9.1.1 were already
  installed in the system `dist-packages`.
- `pip install tiktoken transformers` failed first with PEP 668 (externally managed environment).
  `--break-system-packages` then failed as well: pip needed to upgrade the Debian-owned `rich`
  13.7.1 (`uninstall-no-record-file`). I did not overwrite the system package.
- `python3 -m venv` failed because `ensurepip` is missing (`python3.12-venv` is not installed).
- **Solution:** a venv **without pip** that also sees the system site-packages, filled by the system
  pip through `--python`:

  ```bash
  python3 -m venv --system-site-packages --without-pip .venv
  pip --python .venv/bin/python install tiktoken transformers
  ```

  This installed `tiktoken` 0.14.0, `transformers` 5.17.0, `tokenizers` 0.23.2 and `huggingface_hub`
  1.33.0. The `Qwen/Qwen3-Embedding-4B` tokenizer files download from the HF Hub without a token (no
  weights). `.venv/` is in `.gitignore`; the pins are in `scripts/segmentation/requirements.txt`.
  **Every command below uses `.venv/bin/python`.**

## Step 1 — Verbatim copies and regression baseline

- Copied `GeraCSVporArtigoPorAgrupador.xsl` and `run_segmentation_csv.py` unchanged from
  `../lexml-parser-projeto-lei/scripts/` (source commit `322b437`) into `scripts/segmentation/`.
  `diff -q` confirms they are identical. Work goes on branch `segmentation-implementation`, and the
  copies are committed alone ("Verbatim copy …", `5255a80`), so later diffs show only amendments.
- **Finding:** the verbatim driver does not run on `saxonche` 13.0
  (`AttributeError: 'PyXslt30Processor' object has no attribute 'exception_occurred'`; since
  saxonche 12, errors are raised as `PySaxonApiError`). The copy stays untouched as a reference. The
  adapted driver `run_xsl_segmentation.py` (plan §3.3) was written right away (job list, per-file
  parameters, process pool with `spawn`, saxonche-13 API, `max_num_final` per file), and it also runs
  the baseline.
- **Finding:** the first baseline run failed on 9 files with `field larger than field limit (131072)`
  when counting rows. Grouping rows (whole títulos) are longer than Python's default CSV field limit,
  so the driver now calls `csv.field_size_limit(sys.maxsize)`.
- **Baseline** (original XSL, no parameters, `--jobs 16`): 468/468 files, **93,801 rows**, 31.1 s
  wall-clock, in the scratchpad (`baseline_orig/`). Slowest files: `decreto_9580_20181122.anexo1`
  30.4 s, `lei_10406_20020110` 23.5 s, `decreto_3000_19990326` 23.4 s; everything is under the
  60 s threshold of X10.

## Step 2 — `common.py` and the annex router

- `common.py`: LexML helpers (XPath `string()`/`normalize-space()` equivalents, so only XML
  whitespace is collapsed, as in the XSL); the Python mirror of the XSL text rules (`texto`,
  `caminho`, `tabela`, `rotulo`, and `xsl_row_elements`, which reproduces the XSL's row selection and
  order); `Positions` (calculaPos in one DFS: `start = 2·before − anc + 1`,
  `end = start + 2·desc + 1`); `metadata_for`; the pluggable `Tokenizer` (`chars:N`,
  `tiktoken:…`, `hf:…`, `max:…`, cached, batched); CSV/sidecar I/O.
- **Metadata cleaning had to go beyond plan §2.3.** A survey of the 224 main-document ementas found
  Planalto/Câmara page furniture before the real ementa, besides the `CÂMARA DOS DEPUTADOS …` header
  already known: `Vide Recurso extraordinário nº 522897`, `Texto compilado`, `Texto original`,
  `Texto para impressão`, `Vigência`, `Exposição de Motivos`, `Convertida na Lei nº …`,
  `Produção de efeito`, `Sem eficácia`, `all_inclusiveRegulamentação`,
  `Revogado pelo Decreto nº 9.580, de 2018` (RIR/1999), `Publicado(a) no DOU de …`,
  `(Republicada no DOU …)`, and a page number `1 ` before a repeated epígrafe (5 laws).
  `clean_ementa` strips these with anchored patterns, repeatedly, together with the repeated
  epígrafe. After cleaning, every one of the 224 ementas starts with its real text (checked by
  listing those that do not start with a usual verb: only genuine ones such as "Código de Processo
  Civil." remain). `constituição_1988` has no ementa, so its prefix is the epígrafe only.
- **Non-statutory metadata** (235 files): epígrafe from `Agrupamento[@nome=epigrafe]` in 229 files.
  Fallbacks added for the 6 others, since no `campo` holds a title:
  - `solucao.consulta_2019-03-25_6007`: its only `ementa` group is really its title ("Solução de
    Consulta Disit/SRRF06 nº 6007…"), so it becomes the epígrafe and the ementa falls back to
    `campo Assunto`;
  - 5 `servico_2026_*` pages and `solucao.consulta_2009-03-09_15`: first line of `preliminar` (the
    page or document title);
  - `servico_2026_carne.leao`: first section heading. The URN fallback is no longer needed.

  Ementa: `Agrupamento[@nome=ementa]` in 121 files, `campo EMENTA`, else `campo ASSUNTO` (104
  soluções de consulta; repeated case-variant values are deduplicated). 5 files have no ementa at all
  (court decisions, `servico` pages).
- **Router** (`classify_annexes.py`): **A = 12, B = 50, C = 181**, as expected (self-check passes).
  Roots: A = 8 `DocumentoArticulado` + 4 `DocumentoGenerico`, B = 18 + 32, C = 181
  `DocumentoGenerico`, matching the strategy doc §4. All 243 parents resolve through the family stem.
  Loose content: 4 A and 32 B annexes counting `Articulacao`/`PartePrincipal` only, which reproduces
  plan §0 exactly; **10 A and 46 B** once the annex `Preambulo` is counted (plan §5.1/Q6: annex
  preambles are segmented, e.g. the convênio clauses in `in_rfb_1548_20150213.anexo11`).
  Output: `segmented/annex_manifest.csv`.
- **Deviation D1 — loose content in main documents.** Plan §4 routes loose `p`/`table` only for A/B
  annexes, but **27 main documents** also have them directly under `Articulacao`: 685 elements,
  ≈ 116 k chars. Examples: treaty texts in `decreto_67542_19701112` (184 elements, 42.6 k chars) and
  `decreto_50656_19610524`, the "Tabela Progressiva Anual" in `lei_10451_20020510`, and
  `circ_bc_3432_20090203`. The XSL would drop them, so loose mode runs on every statutory file that
  has them (main-document `Preambulo` still excluded, as in Q6).
- Not segmented, as the plan says: an `Alteracao` directly under `Articulacao` in `lei_13043_20141113`
  (8.2 k chars of quoted amending text outside any article; "Alteracao content gets no rows of its
  own").

## Steps 3–5 — Amended XSL (`segmenta_estatutario.xsl`, X1–X9)

Written as one pass over the verbatim copy, since X2–X7 all replace the same per-type blocks: one
`linha` template, with `lx:csv` (X9), `lx:tabela` (X8), `lx:texto` (X4), `lx:caminho` (X3/X3b),
`lx:rotulo`/`lx:curto` (X7), the `metadados` parameter with Epígrafe|Ementa fallback (X1/X2), CPT only
when the article has a `Paragrafo` and PAR iterated independently (X5), and `DSP` for top-level
orphan dispositivos in every document (X6). `calculaPos` is verbatim. Notes:

- Row order in the CSV: CPT, PAR, ART, DSP, PRT…SSC, INC, ALI, ITE.
- All string fields are quoted. `Num_Inicio`/`Num_Final` stay unquoted because `calculaPos` is kept
  verbatim; CSV readers treat both the same way.
- A top-level orphan dispositivo gets only its `DSP` row, not an `INC`/`PAR`/… row too, so S2 does
  not hold two copies of the same text (the same holds for articles: ART, never an "article-level" CPT
  duplicate).
- `TituloDispositivo` always comes **before** `Rotulo` in the XML (1,324/1,324), so document order
  gives "<title> Art. 8º …".
- **X10 not needed:** with the amended XSL, the slowest files take 22 s (`decreto_9580…anexo1`) and
  15 s (`decreto_3000`) under the process pool.
- **Early parity check** (Python `xsl_row_elements` + `rotulo` + `Positions` + `row_text` against the
  XSL output, every column of every row) on `lei_9250`, `in_rfb_1548.anexo11`, `decreto_8289.anexo1`,
  `circ_bc_3432`, `decreto_3000`, `decreto_9580.anexo1`: **11,680 rows, 0 mismatches**.
- §3.2 worked target reproduced: `ITE art8_cpt_inc2_ali2_ite10` = `[ LEI Nº 9.250, DE 26 DE DEZEMBRO
  DE 1995 | Altera a Legislação do Imposto de Renda das Pessoas Físicas e dá outras providências. ]
  Art. 8º A base de cálculo … somas: II – das deduções relativas: b) a pagamentos de despesas com
  instrução … 10. R$ 3.561,50 …`; `PAR art8_par2` = `… ] Art. 8º A base de cálculo … somas: § 2º O
  disposto na alínea a do inciso II: I – …`. Remission text is kept (`Art. 3º … de que tratam os
  arts. 7°, 8° e 12, da Lei n° 7.713 …`) and tables are serialized (`Tabela: BASE DE CÁLCULO EM R$ |
  ALÍQUOTA% | … ; até 900,00 | - | - ; …`).

## Step 6 — Non-statutory segmenter (`segment_non_statutory.py`)

- Document mode (235 `nao_articulados` + 181 category-C annexes) and loose mode (appended to the
  statutory CSV, numbering from `max Num_Final + 1`). Units, captions, splitting, `Rotulo` and ids
  follow plan §5. Every Python row gets a record in `<csv>.prov.jsonl`, not only split parts and
  synthetic ids (a superset of §5b), so the provenance step never has to re-derive Python rows.
- **Split boundaries:** paragraph numbers ("2.", "11.") sit on lines of their own in the PDF-derived
  `p`s, so a preferred cut is *before* a bare paragraph-number line, or after a line ending in
  `.`/`;`/`:` that is not itself a bare number. Lines over the cap by themselves are cut at sentences,
  then at words. Example: parecer 1503, section II, parts start at "5.", "6.", …
- `ul`/`li` lists (195 `ul` in `nao_articulados`) become one line per `li`, nested lists included.
- **Annex title line is prefix-only.** Without this, the first `p` "ANEXO I" of a `DocumentoGenerico`
  annex (or its `tituloAnexo` group), which is already in the prefix as `Anexo 1 – ANEXO I`, became a
  useless chunk "[ … Anexo 1 – ANEXO I ] ANEXO I" (e.g. `ade_rfb_3_20240402.anexo1`, the RIR/2018
  "ANEXO" line). Small departure from §5.2, which lists `tituloAnexo` under `TXT`.
- **Deviation D2 — long "dropped" Agrupamentos are kept.** Q4 drops `assinatura`, `localDataFecho`
  and `preliminar`. A survey found substantive text in some of them: `preliminar` holding a
  solução-de-consulta ementa ("ASSUNTO: IRPF Aplicação em moeda estrangeira…", 1,551 chars), court
  case headers (1.9 k chars), and `localDataFecho` holding case facts ("O interessado protocolou…").
  Flag `--keep-dropped-min-chars` (default 300) keeps those at least that long as TXT; **11** were
  kept, and 449 short ones were dropped (392 assinatura, 44 preliminar, 13 localDataFecho).
  `--keep-dropped-min-chars 0` restores the plain Q4 default.
- **Heading-only groupings become a TXT unit.** Found by the text-coverage check:
  `decreto_lei_58_19371210.anexo1` ends with an empty `Livro` "LIVRO AUXILIAR – N. 8", whose text was
  lost. A grouping/`AgrupamentoHierarquico` with a heading but no contained unit now yields a TXT
  unit of its heading (24 corpus-wide).

## Step 6b — Structural split of oversize ART/DSP (`split_oversize.py`)

- Implemented as in §5b. The items of a unit are its direct children that carry text: dispositivos,
  and also `table`, `Alteracao`, `Pena`, `DispositivoGenerico`, whose text would otherwise be lost
  when an item is descended into. HEAD = `caminho` of the part's first item, which is exactly "article
  label [+ caput sentence for paragraphs, X3b] + the opening of every descended unit". Parts thus
  concatenate back to the article text without their heads.
- Part interval = span of the whole counted items; pieces use their nearest counted ancestor. The
  sidecar also stores the unit's original interval (`intervalo_unidade`) for validation.
- **Finding / deviation D3 — huge repeated HEAD.** The first full run left 133 over-cap parts, all
  in **CLT art. 670** (`decreto_lei_5452_19430501.anexo1`). Its caput sentence (the composition of
  the 24 Tribunais Regionais plus a list of amending laws) is ≈ 1.9 k tokens, and X3b repeats it before
  every paragraph, so the article shattered into 136 parts that were all over the cap. Rule added:
  a HEAD that alone takes more than half of the cap goes into part(s) of its own, cut at sentence
  boundaries, the first time it appears; in later parts it is truncated to a quarter of the cap
  (256 tokens + "…"). A first version truncated it everywhere, which lost text, e.g. a DSP's opening
  sentence appears only as HEAD (text coverage of `in_rfb_2060_20211213.anexo1` fell to 97.7 %);
  hence the "first appearance in full" rule. Art. 670 now has **7 parts, all ≤ 1,024**. 8 units use
  the truncated HEAD.

## Step 7 — Orchestrator, validation, full run

- `segment_all.py` runs steps 1–7 with process pools (`spawn`); `validate_segments.py` writes
  `segmented/segmentation_report.{md,json}`. `chunks_all.csv` = 6 + 3 + 14 provenance columns +
  3 token columns (`n_tokens` = reference, `n_tokens_cl100k`, `n_tokens_qwen3`). The token columns
  are an addition, for the token-budget sweeps of strategy doc §7.
- **Problem: workers stalled on the HF Hub.** In the first full run only 10 of 16 workers finished
  loading the Qwen tokenizer: each worker called `AutoTokenizer.from_pretrained`, which contacts the
  Hub unauthenticated and gets rate-limited. Moreover, `import transformers` alone takes ≈ 12 s wall
  (2.7 s CPU) on this WSL 9p filesystem. **Fix:** the `hf:` tokenizer now loads the cached
  `tokenizer.json` with the `tokenizers` library (`local_files_only` first, network only when not
  cached, transformers as a last fallback). Counts are **identical** to the transformers fast
  tokenizer on 3,000 RIR chunks (970 k tokens), and the load takes 2.3 s instead of ≈ 21 s.
- **Problem: `--only` overwrote `run_info.json`** with the regenerated files only, so the validator
  lost the per-file "dropped"/"annex title" information and reported 450 false coverage failures.
  `--only` now merges its per-file results into the existing `run_info.json`.
- **Validator fixes** (the data was right): split units sharing a duplicate id (two orphan `ali2`,
  two `art33`) are now grouped by occurrence (a unit starts at `parte = 1`). The dispositivo
  completeness check accepts an id covered m times when m elements of the unit carry it (duplicate
  ids *inside* an article: `art100_par1` ×2 in the Constitution, `art106_cpt_ite8` ×6 in
  `decreto_9358.anexo1`), and it picks the candidate root that the parts fit (the split `ali9` of
  `decreto_8289.anexo1` is the 2nd `ali9` of the file).
- **Interval rule refined:** a sub-unit that was descended into (e.g. inciso II of art. 8, split
  across parts 1–4) necessarily *crosses* the part intervals. The nested-or-disjoint check therefore
  represents each split unit by its original interval and checks separately that every part lies
  inside it (plan §2.4 already says that parts of one unit never cover each other).
- **Final full run** (`segment_all.py --jobs 16 --overwrite`, 87.5 s): router 9.1 s, metadata 4.6 s,
  XSL 31.5 s, split + loose 14.5 s, non-statutory 9.1 s, merge + provenance 17.8 s; validation
  ≈ 20 s. **All checks pass:** csv_schema, non_empty, chunk_id_unique, provenance, intervals,
  coverage, cap (1 flagged uncuttable TAB row, 1,163 tokens, in `portaria_2012_1114`), split_complete,
  text_coverage (min 99.8 %).
- **Gemini `countTokens` sample: not run.** There is no `GEMINI_API_KEY`/`GOOGLE_API_KEY` and no
  Google SDK in this environment. `validate_segments.py` runs it (500 random chunks, stdlib REST,
  `--gemini-model gemini-embedding-2`) when a key is set; the report says "not run".

### Extra corpus-wide checks (beyond the pytest fixtures)

- **Python/XSL parity on every unsplit row** of all 287 statutory CSVs: 81,944 rows, **0 mismatches**
  (selection, label, interval, text, urn). It found one bug: the XSL's default `sigla` comes from
  `document-uri()`, which URL-encodes non-ASCII names (`constitui%C3%A7%C3%A3o_1988_19881005`).
  The orchestrator now passes `sigla` explicitly.
- **XSL regression over the whole corpus** (original vs amended, no parameters, 468 files):
  `(Num_Inicio, Num_Final, urn)` sets are identical for ART and all groupings. CPT loses 11,309
  caput-only rows (X5). 1,403 orphan INC/ALI/ITE rows became DSP (X6); DSP adds another 109 orphan
  `Paragrafo`/`Caput` that the original never emitted. The only other difference is
  `port_conj_tse_srf_74_20060110`, whose URN **contains a comma**
  (`…receita.federal,tribunal.superior.eleitoral:…`): the original XSL wrote `urn` unquoted, which
  broke its CSV for that file. X9 fixes it.

## Tests (`scripts/segmentation/tests`, pytest)

**35 passed** (68 s): regression vs the original XSL (`lei_9250`, RIR annex), §3.2 worked target,
remission text in the ancestor path, tables (lei 9.250 art. 3, decreto 3.000), orphan dispositivos
(`in_rfb_1548.anexo11`, `decreto_8289.anexo1`), labels without separator, Python/XSL parity (4
files), router (7 annexes, all categories), annex metadata, non-statutory document mode (parecer
1503: epígrafe/ementa, dropped groups, cap, headings, disjoint intervals), table header + caption
repetition (`ade_rfb_3.anexo1`), loose-mode offset (RIR tax table), synthetic loose ids, preferred
split boundaries, strategies, reference tokenizer, article split (largest articles of RIR/2018 and
RIR/1999: parts ≤ cap, label/caput in HEAD, ordered intervals inside the article, dispositivo
coverage), within-leaf table split with repeated header, caput in HEAD of paragraph parts, and
provenance (chunk ids, `id_ambiguo` on duplicate `art16`, DSP in a main document, split parts,
citation path, groupings, annex `doc_urn`/`anexo_urn`). Fixture notes: parent documents are copied
too, because annex metadata comes from the parent. The two large files (`decreto_9580…anexo1`,
`decreto_3000`, 4.6 MB) are read from `lexml/articulados` instead of being duplicated. The structural
split tests use the fast `chars:4` tokenizer with a small cap to force descent and leaf splits.

## Step 8 — Results

Final counts and length distributions: `docs/20260924_184339_segmentation_results.md`.
Headline: **S1 = 26,252, S2 = 82,644, S3 = 87,947 chunks**; ART units = 19,393 = the `Artigo` count;
647 articles + 9 DSP split into 1,752 parts. A pointer was added to strategy doc §5 (the estimates
there were ≈ 88 k / ≈ 94 k before the X5 CPT rule).

## Summary of deviations and decisions to review

| # | What | Why | How to revert |
|---|---|---|---|
| D1 | Loose `p`/`table` of **main** documents also segmented (27 docs, 685 elements, ≈ 116 k chars) | the XSL would drop treaty texts and tables | — |
| D2 | `preliminar`/`localDataFecho`/`assinatura` ≥ 300 chars kept as TXT (11 kept) | mis-tagged ementas and facts | `--keep-dropped-min-chars 0` |
| D3 | HEAD over half the cap: full once, then truncated to cap/4 | CLT art. 670 made 133 over-cap parts | — |
| — | Ementa noise stripping beyond §2.3; epígrafe fallbacks for 7 non-statutory files | page furniture in ≈ 20 ementas (plus the 15 known CÂMARA headers) | — |
| — | Annex title line/`tituloAnexo` is prefix-only | avoided "ANEXO I"-only chunks | — |
| — | Heading-only groupings → TXT | lost text in `decreto_lei_58.anexo1` | — |
| — | `hf:` tokenizer via `tokenizers` + `tokenizer.json` | HF Hub rate limit and slow imports; same counts | — |
| — | 3 token-count columns in `chunks_all.csv`; provenance records for every Python row | token-budget sweeps; simpler provenance | — |
| — | Large test fixtures read from `lexml/` | avoid 4.6 MB of duplicates | — |

Open points: the Gemini sample check (needs a key); 243 grouping rows are ≥ 8,192 tokens and
cannot be embedded as they are if S3 is run (Q7); `segmented/` is 256 MB
(`chunks_all.csv` 148 MB, above GitHub's 100 MB file limit), so it was **not committed**.

**Finished:** 2026-09-24 ≈ 18:50.

## Addendum — S3 grouping limit (decided 2026-09-24, after review)

- Reviewed with the user: S3 keeps its original meaning (a grouping chunk = its own label + the
  whole content below it, as in the original XSL, [L]/[F] and plan X4). The **Q7 condition is met**
  for groupings (2,030 of 5,303 above 1,024 tokens, 243 ≥ 8,192), and the user chose **option 2:
  keep only the grouping chunks that fit the models' 8,192-token input**. Applying §5b to groupings
  (option 1) would mostly duplicate the S1 article chunks.
- Implemented in `segment_all.py` step 6 (`--grouping-max-tokens`, default 8192; 0 keeps all).
  PRT…SSC rows with more than 8,192 reference tokens are left out of `chunks_all.csv` and listed in
  **`segmented/groupings_over_limit.csv`**: the same columns minus `Texto`, plus `n_chars`, sorted by
  tokens. Their rows stay in the per-file CSVs, so they can be handled later. New validation check
  `grouping_limit` (none left above the limit, list and `chunks_all` disjoint): ok.
- Result: **243 groupings listed** (TIT 84, CAP 76, LIV 43, SEC 19, PRT 13, SBT 5, SSC 3; top files
  RIR/2018 annex 33, IN RFB 1.911 29, RIR/1999 25, Código Civil 18, CPC 18). The largest is the
  Código Civil PARTE ESPECIAL (179 k tokens). **S3 = 87,704 chunks** (5,060 groupings kept); S1 and S2
  unchanged (26,252 / 82,644). `chunks_all.csv` shrinks from 148 MB to 130 MB.
- The user accepted the other defaults and deviations (D1–D3 and the smaller ones in the table above).

## Addendum — freeze for embedding and manual sample review (2026-09-24)

- **Freeze.** `run_info.json` records the git commit of the run (`git.commit`, and `git.dirty`,
  true when `scripts/segmentation` or `lexml/` had uncommitted changes) and the SHA-256 of
  `chunks_all.csv`, `groupings_over_limit.csv` and `annex_manifest.csv`. `chunks_all.csv` has a new
  column **`texto_sha256`** (first 16 hex digits of the SHA-256 of `Texto`); embeddings should be
  keyed by `chunk_id` + `texto_sha256`. New validation check `texto_sha256`: ok. The reference run was
  made at commit `aadd584` (clean): 87,704 rows, `chunks_all.csv` sha256 `d24a4af1…a1a9a5`. Only
  the merged files changed relative to the previous run; the 1,300 per-file CSV/sidecar files came
  out byte-identical, so the pipeline is deterministic.
- **Manual sample review** (seeded random sample: 5 unsplit ART, 5 ART parts, 5 DSP, 8 TXT, 5 TAB,
  plus the earlier spot checks). Metadata prefixes are clean; article parts read coherently, with the
  article label and caput sentence in HEAD; DSP, TXT and statutory TAB chunks are as intended.
  Findings, all from the source/parse rather than the segmentation, none blocking:
  - **Prose parsed as tables:** 52 of 623 loose tables (45 in `nao_articulados`, 7 in statutory
    files) hold running text, ≈ 47 k chars ≈ 0.2 % of the corpus. Examples: the one-column STJ case
    list of `portaria_2012_1114` (which also holds the one uncuttable 1,163-token row) and paragraphs
    of some soluções de consulta. They come out as `Tabela: 13. Primeiramente, … | ; faz-se …`: the
    text is complete, but with table separators. Possible later fix: serialize one-column or
    prose-like tables as plain text.
  - Boilerplate `nota` groups (e.g. the AGU electronic-signature notice) are kept as TXT, as §5.2
    specifies for `nota`.
  - Parse artifacts in the source labels/text: e.g. `decreto_9358.anexo1` items whose `Rotulo` "6."
    precedes the real number ("6. 29 examinar…"), and old tables flattened into text
    (`lei_4504` art. 50, "ALÍQUOTAAté 2 ...").
- **Gemini `countTokens` check (plan §2.6) — done.** The key is read from `~/keys/gemini_api_key` (outside
  the repository) only for the command that runs the check:
  `GEMINI_API_KEY="$(cat ~/keys/gemini_api_key)" .venv/bin/python scripts/segmentation/validate_segments.py`.
  The user's first attempt looked hung: 500 sequential requests plus the validation took ≈ 3 min with no
  output. The check now uses 8 threads with retries, prints progress, sends the key in the
  `x-goog-api-key` header instead of the URL, and adds the **100 largest chunks** to the 500 random
  ones. Model `gemini-embedding-2` (it lists `countTokens`). Result over the S3 chunk set (0 errors):
  - random sample (500): Gemini/reference ratio p50 **0.883**, p99 0.964, max 1.099; only 2 chunks
    count more in Gemini than in the reference (by at most 60 tokens); max 4,847 Gemini tokens;
  - 100 largest chunks (reference counts up to 8,192): ratio p50 0.878, max 0.929; **max 7,253 Gemini
    tokens; none above 8,192**.

  So Gemini tokenizes this corpus ≈ 12 % more compactly than the max(cl100k, Qwen3) reference, and
  **no chunk in `chunks_all.csv` would be truncated by `gemini-embedding-2`**. At most, a basic
  unit at the 1,024 cap could count ≈ 1,125 Gemini tokens (ratio 1.099), which affects granularity
  only.
