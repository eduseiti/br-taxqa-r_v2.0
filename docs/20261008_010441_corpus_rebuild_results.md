# Corpus Rebuild Results (R1–R10): LexML → segmentation with caput variants → dataset → embeddings → retrieval

**Generated:** 2026-10-08 01:04:41 (local time, from `date +%Y%m%d_%H%M%S`)
**Executes:** `docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md` (**the rebuild plan**; steps
R1–R10) and the segmentation part of
`docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md` (**the caput plan**;
D-A, D-B, C1–C10). Decisions taken: the plan's recommendations D4 (re-point 249-03), D7 (treaty
articles at document level), D8 (declared URNs upstream) and the caput plan's defaults Q1–Q3
(128-token ementa, caput sentence kept in split-part HEADs, S5 later).
**Embedding:** only `jua-4b-mixed` (the only model embedded so far), instruction `irpf`.
**Status:** done. Every step ends with its check passing. Open points are in §6.

---

## 1. Summary

| | Before (2026-09-27) | After (2026-10-08) |
|---|---:|---:|
| `original/` files (articulados + nao_articulados) | 225 + 234 = 459 | 214 + 244 = 458 (12 of them PDFs) |
| `lexml/articulados` XML (main + annexes) | 467 | 455 |
| `lexml/nao_articulados` XML | 235 | 245 (244 documents + 1 annex) |
| Chunk rows (`chunks_all.csv.gz`) | 87,702 | 118,766 = 88,600 `base` + 30,166 `caput` |
| S1 / S2 / S3 rows | 26,250 / 82,642 / 87,702 | 26,364 / 83,496 / 88,600 |
| S2c / S4 rows | — | 83,496 / 88,600 |
| References / `not_in_corpus` / dropped | 1,919 / 42 / 7 | 1,917 / **0** / 9 |
| Questions with an unresolved reference | 37 | **0** |
| Documents / cited / cited without chunks | 459 / 424 / **11** | 458 / 447 / **0** |
| Cited article ids missing from the LexML | 28 | 13, all treaty articles, listed as unmatchable |
| Cited provision fragments missing | 41 | 25 |
| Unique texts embedded (`jua-4b-mixed`) | 84,568 | 115,582 (83,388 reused, 32,194 new, $0.27) |

**Headline retrieval result** (recall at a 4k-token context, all gold; §4):

| Level | S1 | S2 | S3 | S2c | S4 |
|---|---:|---:|---:|---:|---:|
| document | 0.604 | **0.665** | 0.652 | 0.631 | 0.627 |
| article | 0.379 | **0.473** | 0.464 | 0.428 | 0.426 |
| provision | 0.347 | **0.361** | **0.361** | 0.321 | 0.334 |
| provision, sub-article gold | 0.313 | **0.424** | 0.409 | 0.370 | 0.367 |

**Adding the caput sentence to paragraph chunks hurts retrieval** (S2c < S2 and S4 < S3, significant
at every budget and level, §4.2). Decision D-A, caput-free paragraph chunks, is the better S2.

---

## 2. Commits

| Repository | Commit | Step |
|---|---|---|
| br-taxqa-r_v2.0 | `408cf46` | R1: PDF → cleaned text |
| | `5d97665` | R2/R3a/R3b: statutory re-parse, MP 2.189-49 un-struck, audit |
| | `bf94141`, `bf79a58` | R3c: non-statutory re-parse with declared URNs; front-matter fix re-parse |
| | `496acbb` | R5 code: dataset build |
| | `51536b9` | R6: segmentation code (caput plan C1–C5, C10) |
| | `f2e49d7` | R8 code: `embed.py corpus --extend` |
| | `9513dbb` | R9 code: strategy variants in the RAG pipeline |
| | `280121b` | R7: segmentation run (new frozen chunk set) |
| | `7d88bd6` | R5: dataset rebuilt (clean tree, after R7) |
| | (next commit) | R8/R9 outputs, R10 docs (this note) |
| ../lexml-parser-projeto-lei | `6142756` | `batch_parse.py`: `--no-justificativa`, `--only`, TSE resolutions (`work_history/20261008_001450_*`) |
| ../lexml_parser_non_statutory | `d9624a7` | `parse --urn / --metadata` (`docs/20261008_003108_declared_urn_option.md`) |
| | `e8c3d1e` | front matter: layout tables, presidential preamble, portal lines (`docs/20261008_003915_*`) |
| ../br-taxqa-document-fetcher | `c7f4b8f` | 27 canonical records corrected (`20261008_002333_canonical_list_corrections.md`) |

None of these commits is pushed.

---

## 3. Steps as run

### R0 — decisions and blockers

B1–B3 were done before this run (rebuild plan §8). B4 (stale LexML) is handled by regenerating both
`lexml/` folders completely (R2). The Word lock-file pattern `.~lock.*` was added to `.gitignore`.

### R1 — PDF → text (`scripts/lexml/pdf_to_text.py`)

The rebuild plan's prototype was lost with an earlier session's scratchpad, so the converter was
rewritten. It reads `pdftotext -bbox-layout` (line positions) rather than `-raw`:

- **Furniture by position.** Lines above y = 72 pt are dropped, and so are lines between 72 and
  90 pt that look like furniture ("Cosit", "Fls. N", the faux-bold running header "S o l u ç ã o…",
  "Erro: Origem da referência não encontrada"). Lines below 785 pt (page number, "Cópia autenticada
  administrativamente") are dropped too. A fixed 85 pt cut would have lost the first line of some
  pages (body text starts at y ≈ 81 in SC 211/2019 and 214/2021).
- **Header box → title.** Everything before `Assunto:` on page 1 (Processo, Interessado, Data…)
  becomes `Solução de Consulta Cosit nº N, de <data>`, the first line of the existing SC `.docx`.
- **Paragraphs from geometry.** Words on one baseline are merged, so "2." joins its text. A gap
  above 1.3 × the line spacing starts a paragraph. A paragraph cut by a page break is rejoined when
  its last line has no closing punctuation or the next page starts in lower case. Words closer than
  0.5 pt are joined: small caps came out as "A SSUNTO : I MPOSTO…".
- **Ementa zone:** the `Assunto:` line, upper-case heading runs and ementa texts become separate
  paragraphs, as in the `.docx`.
- **Quotation indent:** paragraphs whose lines all start right of the body margin (taken from the
  numbered paragraphs) get leading spaces (180 twips per space in `txt_reader`).

Checks (plan §1.3): all 12 files route to the `solucao_consulta` profile with the right URN, and
**100 %** of the `pdftotext -raw` word tokens (furniture excluded) are in the text. Output:
`lexml/nao_articulados/_text/<stem>.txt` (committed).

### R2/R3a/R3b — statutory LexML

- **Jar.** The jar in `../lexml-parser-projeto-lei/target/` was from 2026-05-25, older than HEAD
  `ebf6567`. It was rebuilt with `mvn -Ponejar package -DskipTests` (SHA-256 `51963519…a766`).
  Provenance is in `lexml/articulados/PARSER_VERSION`.
- **Driver.** `batch_parse.py --no-justificativa --linker /usr/local/bin/linkertool original/articulados …`.
  The new flag passes `--prof-regex-justificativa '(?!)'` (cause 2b guard). The `resolucao` overrides
  gained `%^relator` (post-epígrafe) and `%^o tribunal superior eleitoral` (preamble), so
  `resol_tse_22250_20060629` parses with the batch (rebuild plan §1.2): 50 articles, `art14` present.
- **Result:** 214 converted, 0 skipped, 0 failed. 440 of the 451 files shared with the previous
  parse are **byte-identical**, so the jar reproduces the committed corpus. Of the other 11, 7 come
  from the `.docx` repairs (Decreto 59.566, Lei 11.941, Lei 13.043, Lei 6.404, MP 2.158-35 main +
  annex, MP 2.189-49). The other 4 differ only in `Remissao` links (§5.3).
- **Corpus-wide audit** (new `scripts/lexml/audit_article_coverage.py`). It compares each `.docx`'s
  article labels outside quotes with the top-level `Artigo` ids of the main and annex XMLs. Before:
  36 documents differed, with 10 cited ids missing. After the repairs: 21 documents differ, and no
  cited id is missing apart from the treaty articles in `scripts/lexml/unmatchable_articles.tsv`
  (the gate). One new case was found and fixed:
  - **MP 2.189-49, arts. 1–6 (cause 2a).** Planalto strikes them through with "(Revogado pela Lei
    nº 14.754, de 2023)". The parser drops struck runs, so the XML started at art. 7. Lei 14.754 took
    effect in 2024, so these articles were in force in 2023 (D5). New
    `scripts/lexml/unstrike_revoked.py --revoked-by 'Lei nº 14\.754, de 2023'` removed the strike from
    the 28 paragraphs of those articles and of the art. 10 amendment item they belong to; the note
    stays in the text. Re-parse: `art1…art20` top-level. Only one other statutory document has
    struck articles: `mp_2228-1_20010906` (uncited), whose struck text is superseded wordings, so it
    was left alone. A corpus scan found no other "Revogado pela Lei nº 14.754" strike.
  - The remaining audit differences are in uncited documents (§6).

### R3c — non-statutory LexML

- **Declared URNs** (rebuild plan §3.2, D8). `scripts/lexml/nonstat_metadata.tsv` gives
  stem → authority, type, date, number, URN, with a `note` per row:

  | Source of the URN | Stems |
  |---|---:|
  | committed parse (2026-09-16), unchanged | 197 |
  | committed statutory parse (the 11 decrees/INs moved in `ce032e6`) | 11 |
  | corrected (§3.2 table: PGFN notes and pareceres → `procuradoria.geral.fazenda.nacional`; IN SRF 84 → `instrucao.normativa`; `sc_6007` and 3 new SCs `federal` → `…receita.federal`; AD Mesa CN 38 full date) | 20 |
  | inferred by the parser (new documents) | 15 |
  | declared like the other service pages (Diat → `…servico:2026;diat`) | 1 |

  All 244 URNs are distinct, no date is `0000`, and every `_<number>_<YYYYMMDD>` stem agrees with its
  URN.
- **Upstream option.** `lexml_nonstat parse --urn` / `--metadata` (`d9624a7`) puts the declared
  identity into `Identificacao`, the annex URNs and the `-o` file names; the `*_source` fields say
  `declared`. Five tests were added.
- **Linker round trip (§3.2 step 3) is not possible.** `linkertool` returns nothing for Notas,
  Pareceres, SCs, ADs, Súmulas or IN SRF titles; it only resolves federal laws and decrees (for
  "Decreto nº 27.784, de 16 de fevereiro de 1950" it gives the declared URN). So the vocabulary
  follows the conventions this corpus already uses.
- **Parse** (`lexml/nao_articulados/PARSER_VERSION`): the same options as the committed parse
  (`--emitter=generico-aninhado --generation=proposed --referee=api --linker=…`) plus `--metadata`.
  Result: 244 documents + 1 annex, schema-valid (rigid and flexible), exit 0, 94 rendered flat.
  `/tmp/lexml_referee_cache` held only 41 of the earlier answers, so 513 referee calls were made
  (deepseek). 180 of the 213 documents also in the old parse are identical apart from the URN. The
  other 33 differ by one borderline section heading or a few `Remissao` links, with the text equal
  to within one word.
- **Front-matter fix (found in R7, `e8c3d1e`).** The segmentation's coverage check failed on a
  dropped table in five treaty decrees, and the metadata prefix of 27 documents carried a wrong
  ementa:
  - the 9 treaty decrees: the ementa sits in a one-row layout table (empty first cell), and the
    preamble "O PRESIDENTE DA REPÚBLICA…" was taken as the ementa;
  - 18 Receita portal pages (IN SRF 23/67/84, 10 PN CST, ADs, Portaria MF 80/1979, SD 16/2012,
    AD PGFN 1/2014): "Norma Federal - Publicado no DO em …" was taken as the ementa.

  The parser now unwraps one-row tables among the first 12 blocks (the rule fires in exactly these 5
  documents), reads "O PRESIDENTE DA REPÚBLICA" as a preamble opener, and skips portal lines
  ("Vide…", "Texto compilado", "Download…", "(Norma Federal -) Publicado no DO…") before an
  unlabelled ementa. The re-parse with cached referee answers changed exactly those 27 files; the
  other 218 are byte-identical. The parser's suite fails the same 11 corpus-dependent tests as
  before the change (§6).
- `scripts/dataset/nonstat_lexml_map.tsv` is now generated from the output
  (`scripts/lexml/nonstat_lexml_map.py`, match `declared-urn`).

### R4 — fetcher canonical list

`../br-taxqa-document-fetcher/scripts/fix_canonical_records.py` applies the reviewed
`output_canonical/canonical_corrections_20261008.json`. 27 records changed: 25 now name the cited
act, Parecer Cosit 30/2001 is `nonexistent_act`, and SCI Cosit 27/2008 is `not_found`. Each record
gets `source: manual` and `correction: {date, was, reason}`, and `by_type/*.md` and `index.md` are
regenerated. A second run is a no-op. Re-running `extract_canonical_names.py` would undo the
corrections; the note there says so.

### R5 — dataset

- `reference_overrides.json`: the 25 `not_in_corpus` entries are gone, because the acts now resolve
  `auto_exact` from the corrected list. Also removed: the now-redundant "Convenção … Nações Unidas"
  entry. Diat now maps to its document. Q313's Parecer Cosit 30 is dropped (fix 1). 37 `files` and
  9 `drop` entries remain.
- `build_v2_dataset.py`:
  - a canonical `correction.reason` becomes the `resolution_note`, and a `status` record resolves to
    no document. With this, fix 2 (Q249 → Nota 981/2015) comes from the canonical list, not from an
    override;
  - `*.pdf` sources are read;
  - guards: dead override (error), contradiction (error), redundant override and uncited file name
    (warnings), uncited documents (warning). The uncited-file-name rule differs from the plan: the 5
    service-page overrides are used by no question but are still needed, because every canonical
    file name must resolve;
  - new fields: `provisions[].matchable`, `article_ids_unmatchable` and `unmatchable_reasons`;
  - the fetcher's git commit is recorded in `build_report.json`.
- **Expected deltas (plan §5): all met.** `not_in_corpus` 42 → 0; questions with an unresolved
  reference 37 → 0; dropped 7 → 9; Q179 unchanged; Q249/Q313/Q187 resolved or dropped; 458
  documents; `article_ids_missing` 28 → 13, all explained (`article_ids_missing_unexplained = []`).
  The 36 dataset tests pass. The final build ran on a clean tree (`7d88bd6`), against the R7 chunks:
  `cited_documents_without_chunks = []`.

### R6 — segmentation code (caput plan C1–C5, C10, adapted as in the rebuild plan §4)

| Item | Implementation |
|---|---|
| C1 | XSL param `caput_em_paragrafo` (`nao` default, `frase` = old X3b) |
| C2 | `common.caminho_parts(n, caput="nenhum"\|"frase"\|"completo")`; `split_oversize.py` uses `frase` explicitly (Q2: ART-part HEADs unchanged) |
| C3 | `add_caput_variants.caput_variant(e, tipo, base_text)`. Called from step 6 (merge) rather than writing separate `<file>.caput.csv` files: it uses the element lookup step 6 already does, and **asserts that the base text equals prefix + caput-free Python text**. That is an XSL/Python parity check over every paragraph-family row of the corpus |
| C4 | `segment_all.py --variants caput` (default), `--frozen`, `--frozen-lexml-rev`; new columns `variante`, `contexto_ids`; chunk ids `<stem>#<seq>` (base) and `<stem>#c<seq>` (caput, the same seq as its twin). `--chunk-id-source` was dropped, as the rebuild plan says |
| C5 | `validate_segments.py`: structural checks on base rows; `variant_twins`, `base_no_caput` (the variant is the base plus one inserted segment), `diff_vs_frozen` (report only, rebuild plan §4) |
| C6 | `strategies.py`: `(tipos, variantes)`; S2C, S4 |
| C10 | worked target (base `art8_par2` = `Art. 8º § 2º O disposto…`), caput target with `frase`, parity with both settings on 4 fixtures, variant and filter tests: **45 pass** |

**Environment:** the segmentation runs in `.venv` (Python 3.12). It lacked `lxml`/`saxonche`, so
`scripts/segmentation/requirements.txt` was installed into it. The conda Python's `tokenizers`
0.19 cannot read the Qwen3 `tokenizer.json`.

### R7 — segmentation run

```bash
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --allow-count-change \
    --variants caput --frozen <old chunks_all.csv.gz> --frozen-lexml-rev 0ce50c5     # 62 s
```

- Router A/B/C = 12 / 50 / 179 (was 12 / 50 / 181: two annexes of removed documents are gone).
  XSL: 276 files, 83,569 rows. 655 ART/DSP rows split into 1,746 parts. Loose: 697 rows. Non-statutory:
  424 files, 3,486 rows.
- `chunks_all.csv`: **118,766 rows** = 88,600 base + 30,166 caput. 243 grouping rows over 8,192
  tokens are listed in `groupings_over_limit.csv`.
- **Validation OK** on all 14 checks.
- **`diff_vs_frozen`:** for the 569 files whose LexML did not change since `0ce50c5`, **75,979 rows
  compared, 0 differ, 0 missing, 0 extra**. Base rows equal the frozen rows, and the caput rows equal
  the frozen paragraph-family texts. The caput plan's invariants (i) and (ii) therefore hold
  wherever the corpus did not change. 147 files changed, were added or were removed.
- Per Tipo (base): PAR 21,813, INC 20,867, ART 20,662, CPT 8,209, ALI 4,938, TXT 3,497, SEC 2,128,
  CAP 1,863, DSP 1,519, ITE 1,305, SSC 714, TAB 686, TIT 328, LIV 45, SBT 21, PRT 5. The caput
  plan's 29,876 paragraph-family rows are now 30,166 (more documents and articles).

### R8 — embeddings (`jua-4b-mixed`)

`embed.py corpus` gained **`--extend`** (embed by text hash; rebuild plan §4, generalizing C9). The
vectors of texts still in the input are copied from the finalized store into the shard store, so
resume and assembly are unchanged. The store must match in model, revision, template, dimension and
server fingerprint. A fake-provider test covers it, and the 27 embedding tests pass.

```bash
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --extend --dry-run
.venv/bin/python scripts/embedding/embed.py corpus --model jua-4b-mixed --extend --resume
```

- 115,582 unique texts: **83,388 reused, 32,194 embedded** (5.95 M tokens, 504 requests, 0 retries,
  5,182 tok/s, 19.9 replica-minutes, **≈ $0.27**), 1,180 old texts dropped. Vectors are
  [115,582 × 2,560] with norms OK. The endpoint was paused afterwards.
- The old store is kept in `embeddings/jua-4b-mixed/corpus_prev_20260926/` (vectors gitignored,
  manifest versioned), so the old rankings can be regenerated.
- **Queries were not re-embedded:** the question texts did not change, and `rag.py check` verifies
  them against `questions.jsonl`.

### R9 — retrieval and evaluation

- C7: `strategies.yaml` has `variantes` (default `[base]`), S2c and S4, and the new expected rows.
  `ragpipe.strategies.member_mask` (first listed variant per unit) is used both by the index and by
  the evaluation. The evaluation previously filtered by `Tipo` only, which would have counted caput
  rows as members of S2/S3. Chunk files without `variante` load as `base`. 24 RAG tests pass.

```bash
R=scripts/rag/rag.py
.venv/bin/python $R check    --embedding jua-4b-mixed                                  # OK
.venv/bin/python $R retrieve --embedding jua-4b-mixed --force                          # 20 s
.venv/bin/python $R evaluate --retrieval runs/retrieval/jua-4b-mixed/irpf \
    --eval-id v2c_either_containment_skip --comparisons S1:S2,S2:S3,S2:S2c,S3:S4,S1:S2c  # 32 s
```

- `check`: 0 references not in the corpus, 0 documents without chunks.
- Texts per strategy: S1 26,323; S2 83,330; S3 88,434; S2c 80,325; S4 85,429. Without the caput
  sentence fewer paragraph chunks share a text, so S2 has 3,000 more distinct texts than S2c.
- The old evaluation `eval/either_containment_skip/` (report, metrics) is untouched. The rankings in
  `S1/S2/S3/` are now the new ones (`--force` replaces only the files it writes).

---

## 4. Retrieval results (`runs/retrieval/jua-4b-mixed/irpf/eval/v2c_either_containment_skip/report.md`)

Settings as in the first IR test: annex rule `either`, containment de-duplication, overflow `skip`,
Qwen3-token budgets, paired bootstrap (10,000 resamples, seed 13) and permutation tests. Gold: 1,725
document, 1,958 article and 2,230 provision items. Unreachable: 13 articles (the treaty articles)
and 57 provisions, the same for every strategy.

### 4.1 Recall by budget (all resolved gold)

| Level | Strategy | 1k | 2k | 4k | 8k | 16k |
|---|---|---:|---:|---:|---:|---:|
| document | S1 | 0.376 | 0.482 | 0.604 | 0.717 | 0.803 |
| | S2 | **0.488** | **0.575** | **0.665** | **0.763** | **0.833** |
| | S3 | 0.479 | 0.565 | 0.652 | 0.745 | 0.815 |
| | S2c | 0.444 | 0.537 | 0.631 | 0.727 | 0.805 |
| | S4 | 0.440 | 0.534 | 0.627 | 0.715 | 0.791 |
| article | S1 | 0.169 | 0.265 | 0.379 | 0.479 | 0.566 |
| | S2 | **0.307** | **0.387** | **0.473** | **0.567** | 0.650 |
| | S3 | 0.302 | 0.379 | 0.464 | 0.566 | **0.659** |
| | S2c | 0.273 | 0.346 | 0.428 | 0.523 | 0.616 |
| | S4 | 0.269 | 0.348 | 0.426 | 0.525 | 0.624 |
| provision | S1 | 0.157 | 0.240 | 0.347 | 0.454 | 0.532 |
| | S2 | 0.187 | **0.261** | **0.361** | 0.467 | 0.565 |
| | S3 | **0.192** | 0.260 | **0.361** | **0.482** | **0.581** |
| | S2c | 0.164 | 0.226 | 0.321 | 0.433 | 0.538 |
| | S4 | 0.169 | 0.231 | 0.334 | 0.443 | 0.555 |

Slices at 4k (provision level): sub-article gold (366 questions) S1 0.313 / S2 **0.424** / S3 0.409 /
S2c 0.370 / S4 0.367; whole-article gold (429) S1 **0.337** / S2 0.266 / S3 0.270 / S2c 0.237 /
S4 0.259. Non-statutory provisions (15 questions) cannot be hit by any strategy: their oracle is 0,
because those documents have no article ids.

### 4.2 Paired comparisons (recall, budget view; difference [95 % CI], permutation p)

| Pair | Level | 1k | 4k | 16k |
|---|---|---|---|---|
| S2 − S1 | article | +0.138 [+0.112, +0.165] p<0.001 | +0.094 [+0.072, +0.117] p<0.001 | +0.084 [+0.064, +0.105] p<0.001 |
| S2 − S1 | provision | +0.031 [+0.008, +0.053] p=0.007 | +0.014 [−0.012, +0.039] p=0.29 | +0.033 [+0.015, +0.051] p<0.001 |
| S3 − S2 | provision | +0.004 p=0.25 | −0.000 p=0.95 | +0.016 [+0.002, +0.030] p=0.02 |
| **S2c − S2** | article | −0.034 [−0.054, −0.015] p<0.001 | −0.045 [−0.062, −0.028] p<0.001 | −0.034 [−0.047, −0.022] p<0.001 |
| **S2c − S2** | provision | −0.023 [−0.038, −0.009] p<0.001 | −0.040 [−0.056, −0.024] p<0.001 | −0.026 [−0.039, −0.015] p<0.001 |
| **S4 − S3** | article | −0.033 [−0.053, −0.014] p=0.001 | −0.038 [−0.055, −0.022] p<0.001 | −0.035 [−0.049, −0.022] p<0.001 |
| **S4 − S3** | provision | −0.023 [−0.037, −0.008] p=0.002 | −0.027 [−0.040, −0.012] p<0.001 | −0.026 [−0.038, −0.015] p<0.001 |
| S2c − S1 | provision | +0.007 p=0.52 | −0.026 [−0.050, −0.003] p=0.03 | +0.007 p=0.47 |

S2c is also worse than S2 at the document level (−0.044 at 1k, p<0.001). S3 − S2 trades a little
document recall (−0.013 at 4k) for higher context precision at 8k/16k. All rows are in
`comparisons.csv`.

### 4.3 Reading

- **Sub-article units help** (S2 vs S1): +9–14 points of article recall, and +11 points of
  provision recall on sub-article gold at 4k. On the old corpus the S2 tested was really S2c: its
  provision recall at 4k was *below* S1 (0.327 vs 0.358). The caput-free S2 is the first variant
  above S1 at the provision level.
- **The caput sentence hurts** (S2c vs S2, S4 vs S3): every level and budget, about 2–5 points,
  all significant. One likely cause: paragraph chunks of one article all start with the same caput
  sentence, so their vectors resemble each other and the article's caput chunk. That crowds the
  token budget with near-duplicates of one article (S2c has 3,005 fewer distinct texts than S2, and
  its contexts hold fewer texts per budget). It also dilutes what is specific to each paragraph. The
  full-caput S5 (caput plan Q3) is therefore **not worth building** unless a generation-level test
  shows the opposite.
- **Groupings** (S3 vs S2) remain about neutral for recall. They are better for context precision
  at large budgets.
- These are retrieval scores on one embedding model. The answer-level (nugget) evaluation is still
  to come.
- **Old vs new runs are not directly comparable:** the corpus changed (22 documents replaced,
  11 re-routed, missing articles restored, URNs and ementas fixed) and the gold changed (42
  references resolved, 2 dropped).

---

## 5. Findings and deviations from the plans

1. **PDF prototype missing** (R1): rewritten as above; the plan's checks pass.
2. **New cause-2a case: MP 2.189-49** (R3a), fixed with a reusable tool. D5's rule ("each article
   once, in its 2023 wording") applied.
3. **Linker defect, unchanged:** for "art. 19, caput, da Lei nº 9.096…" `linkertool` returns
   `…;9096!cpt` and loses the article. The committed corpus already had 227 such links; the new one
   has 234. Four unchanged `.docx` (Decreto 9.580 annex 1, Lei 10.833, Lei 8.242 annex 1, Lei 9.504)
   now get these weaker links where the committed XML had better ones, probably from a linker built
   elsewhere (old logs point at `/work/unicamp/…`). The current binary dates from 2025-10-31. Chunk
   text is unaffected. Details in the statutory parser's `work_history` note.
4. **Non-statutory front matter** (R3c fix): 27 wrong ementas corrected upstream. Without this fix
   the coverage check failed, and every chunk of those documents carried the preamble or a DOU
   publication line as its "ementa".
5. **Referee cache was volatile:** `/tmp/lexml_referee_cache` had lost most of the 2026-09-16 run's
   answers, so 513 new API answers were bought and section headings differ slightly in 33
   documents. The cache now holds 554 answers; it is still under `/tmp`.
6. **Dead-override rule relaxed** (R5, see above).
7. **C3 lives inside step 6** rather than writing per-file `.caput.csv` (R6); same output, with a
   built-in parity assertion.
8. **`diff_vs_frozen` passes with zero differences** (R7), so the new code changes nothing that the
   caput plan did not intend.
9. **Retrieval directory reused** with `--force` (R9). The old evaluation stays readable, but its
   rankings were replaced; they can be regenerated from `corpus_prev_20260926`.
10. **Authority vocabulary SRF vs RFB:** the statutory side writes
    `…secretaria.receita.federal.brasil` for acts after 2007-05-02, while the non-statutory side
    writes `…secretaria.receita.federal` for every Receita act (SCs of 2014–2023 included). This was
    kept as is (the plan only fixed inconsistent groups), but two documents of one authority can
    carry different spellings.

---

## 6. Open points (for the user)

| # | Point | Suggestion |
|---|---|---|
| O1 | **Treaty articles (2f, D7):** 11 cited articles (13 gold article items) of 9 treaty decrees are unmatchable; the treaty texts are missing or numbered `ARTIGO I…`. Listed in `scripts/lexml/unmatchable_articles.tsv` | Fetch the treaty texts (DOU/Senado), then map `ARTIGO N` blocks by label |
| O2 | **Uncited documents:** `in_rfb_1911_20191011` (the old wrong match for IN RFB 1.997) and `in_rfb_1505_20141031` (cited only by Q081's dropped hallucinated reference). Also uncited, as before: the 5 service pages, `lei_3071_19160101`, `lei_5869_19730111`, `par_cosit_26_20000629`, `sc_cosit_153_20140611` | Remove the first two, like the D3 removals? |
| O3 | **Uncited documents with parse gaps** (audit): `decreto_7030_20091214` (85 articles in the `.docx`, 3 in the XML; the Vienna Convention, numbered "Artigo N"), `mp_2228-1_20010906` (arts. 13, 31, 51, 73 missing; all wordings struck), duplicate ids in `decreto_70951`, `decreto_71733`, `lei_12715`, `decreto_lei_58`, `lei_3071` | They affect only distractor chunks; fix if they are kept in the corpus |
| O4 | **25 cited provision fragments not in the XML** (e.g. `lei_9250` art. 10 inc. X, `lei_6015` art. 167 I items 7/24/25, `lei_12350` art. 45 § 3º, `lei_11033` art. 3º p.u.); marked `matchable: false` | Check each against the source (revoked text? citation error?) |
| O5 | **11 tests of `lexml_parser_non_statutory` fail** (with and without these changes): they pin the 2026-09 corpus (233 documents, flatness counts, referee fixtures) | Update their expected values or freeze a corpus copy for them |
| O6 | **Linker defect** (§5.3) | Fix in `../lexml-linker`, then re-parse |
| O7 | **Referee cache** in `/tmp` | Copy `/tmp/lexml_referee_cache` into the parser repo's fixtures so the parse can be reproduced without the API |
| O8 | **Other embedding models** (`qwen3-emb-4b`, `inf-retriever-v1`): no vectors yet | Embed the new chunk set directly (no `--extend` needed) |
| O9 | **S5** (full caput) | Not recommended after §4.3 |
| O10 | Lei 13.043 heading typos ("D a …", "REPÚBLIC A") and the art. 22 § 1º wording (rebuild plan §3.1.1) | Still to confirm or fix |

---

## 7. Reproduction (from `original/`)

```bash
# R1
python3 scripts/lexml/pdf_to_text.py original/nao_articulados/*.pdf -o lexml/nao_articulados/_text/
# R3b (jar: ../lexml-parser-projeto-lei, mvn -Ponejar package -DskipTests at ebf6567)
python3 ../lexml-parser-projeto-lei/scripts/batch_parse.py --no-justificativa \
    --linker /usr/local/bin/linkertool original/articulados lexml/articulados
python3 scripts/lexml/audit_article_coverage.py                       # gate
# R3c (from ../lexml_parser_non_statutory, e8c3d1e; see lexml/nao_articulados/PARSER_VERSION)
PYTHONPATH=src LC_ALL=C.UTF-8 python3 -m lexml_nonstat parse --emitter=generico-aninhado \
    --generation=proposed --referee=api --referee-cache=/tmp/lexml_referee_cache \
    --linker=/usr/local/bin/linkertool --linker-cache=.cache/linker \
    --metadata ../br-taxqa-r_v2.0/scripts/lexml/nonstat_metadata.tsv \
    -o ../br-taxqa-r_v2.0/lexml/nao_articulados \
    ../br-taxqa-r_v2.0/original/nao_articulados/*.docx ../br-taxqa-r_v2.0/lexml/nao_articulados/_text/*.txt
python3 scripts/lexml/nonstat_lexml_map.py
# R4 (from ../br-taxqa-document-fetcher)
python3 scripts/fix_canonical_records.py output_canonical/canonical_corrections_20261008.json
# R7, R5
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite --variants caput
python3 scripts/dataset/build_v2_dataset.py
# R8, R9: §3 above
```
