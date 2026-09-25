# Document Metadata Fix (Constitution + 4 MPs: epígrafe + URN) and Segmentation Re-runs

**Generated:** 2026-09-25 12:55:14 (local time, from `date +%Y%m%d_%H%M%S`)
**Found while writing:** `docs/20260925_122058_embedding_implementation_plan.md` §8.2 (the Gemini
document-title decision). The plan's step 0 requires this fix before any embedding run.
**Affects:** `lexml/articulados/constituição_1988_19881005.xml` and every segmentation output
derived from it. Segmentation design: `docs/20260924_123747_segmentation_implementation_plan.md`;
previous results: `docs/20260924_184339_segmentation_results.md`.

**Update, 2026-09-25 afternoon:** the manual edit of §2 was replaced by a **parser fix**, which
also fixed four MPs with the same bug. The parser change is documented in
`../lexml-parser-projeto-lei/work_history/20260925_130918_numero_complemento_and_constituicao_epigrafe_fix.md`,
and the resulting re-parse and second segmentation run are in §5 below. §1–§4 describe the first,
manual step and remain as a record.

---

## 1. Problem

The Constitution's LexML file had two **synthesized** metadata values:

| Element | Before | Problem |
|---|---|---|
| `ParteInicial/Epigrafe` | `CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988 ` | Not the document's title: no accent, and a "Nº 1" the Constitution doesn't have |
| `Metadado/Identificacao/@URN` | `urn:lex:br:federal:constituicao:1988-10-05;1` | `lexml-linker` writes the Constitution as `…:1988-10-05;1988` (the standard LexML URN). It appears **1,303 times** in `lexml/`, and `;1` appeared only here |

**Origin:** the statutory parser. `constituição_1988_19881005.err.log` shows it was run with
`-t constituicao --data 1988-10-05` and **no number**. It then built the URN and the epígrafe
from type, number (default 1) and date. The source `.docx` has no such epígrafe.

**Why it matters:**

- **Epígrafe:** segmentation copies it into the metadata prefix of every chunk (strategy doc §6,
  item 1). All **3,018** Constitution chunks started with `[ CONSTITUICAO Nº 1, DE 5 DE OUTUBRO
  DE 1988 ]`, which is wrong text in what gets embedded.
- **URN:** the chunks' `urn` / `doc_urn` (`<doc URN>!<element id>`) are built from
  `Identificacao/@URN`. They could not match the linker's references to the Constitution
  (`…;1988!art5_…`), so gold references to the Constitution could not be matched to its chunks.

## 2. Fix (applied 2026-09-25)

Two lines were changed by hand in `lexml/articulados/constituição_1988_19881005.xml`. There is no
code change; the XML stays the single source of truth for segmentation.

```diff
-      <Identificacao URN="urn:lex:br:federal:constituicao:1988-10-05;1"/>
+      <Identificacao URN="urn:lex:br:federal:constituicao:1988-10-05;1988"/>
-      <Epigrafe id="epigrafe">CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988 </Epigrafe>
+      <Epigrafe id="epigrafe">Constituição da República Federativa do Brasil</Epigrafe>
```

- The title is the one decided on 2026-09-25: **"Constituição da República Federativa do Brasil"**.
  The canonical list in `../br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json`
  (index 59) uses "Constituição da República Federativa do Brasil de 1988".
- The XML has no `Ementa` for the Constitution, so the chunk prefix is only the title:
  `[ Constituição da República Federativa do Brasil ] Art. 5º …`.
- **Re-parse warning (resolved):** re-running the old parser command would undo this edit.
  **Resolved by §5**: the fixed parser now produces exactly this XML, byte for byte.

## 3. Segmentation re-run

```bash
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite
```

The run took 92 s and **all validation checks passed** (`csv_schema, non_empty, texto_sha256,
chunk_id_unique, provenance, intervals, coverage, cap, split_complete, text_coverage,
grouping_limit`). The run was made on commit `24f450e` with the XML edit uncommitted, so
`run_info.json` records `dirty: true` with the XML as the only dirty file.

### 3.1 What changed (compared with the frozen output of commit `24f450e`)

| Item | Before | After |
|---|---|---|
| `chunks_all.csv` rows | 87,704 | **87,703** |
| Constitution rows | 3,018 | 3,017 |
| Unique texts (`texto_sha256` / full `Texto`) | 84,569 | 84,569 |
| Rows per strategy S1 / S2 / S3 | 26,252 / 82,644 / 87,704 | 26,251 / 82,643 / 87,703 |
| ART/DSP units split | 656 → 1,752 parts | 655 → 1,750 parts |
| Qwen3 tokens total / p90 / max | 27,018,900 / 540 / 8,119 | 26,976,581 / 539 / 8,119 |
| cl100k tokens total / max | 25,761,563 / 7,895 | 25,725,279 / 7,895 |
| Rows outside the Constitution | — | **identical** (every column, same order) |
| `groupings_over_limit.csv` | — | same rows; only the Constitution URNs changed |

- **Every Constitution row changed** in `Texto`, `texto_sha256`, the token counts, `urn` and
  `doc_urn`. The new prefix is about 14 Qwen3 tokens shorter.
- **The one row fewer is Art. 144.** Before, at 876 + 230 tokens, it was split into `parte 1/2`
  and `parte 2/2`. With the shorter prefix the whole article is **1,014 tokens**, below the
  1,024 cap, so it is now a single `ART` row. This is the cap rule working as designed, not a
  regression.
- `chunk_id`s of Constitution rows after Art. 144 shift by one sequence number
  (e.g. `constituição_1988_19881005#1318` no longer exists). Nothing has been built on the old
  ids yet (no embeddings), so no mapping is needed.

### 3.2 Output files changed

`segmented/chunks_all.csv(.gz)`, `segmented/statutory/constituição_1988_19881005.{csv,prov.jsonl}`,
`segmented/groupings_over_limit.csv`, `segmented/run_info.json`,
`segmented/segmentation_report.{md,json}`. New `chunks_all.csv.gz` SHA-256:
`c296dc219bb396a8bf9509c3d60db07addf4720c44f5d53b81a33ce940e168d8`
(`chunks_all.csv`: `5add6d424fd2e6d224623d2b3038b55591102f2a301d367b6dfef116d47a1eba`).

### 3.3 Gemini `countTokens` check not re-run

The report's Gemini sample check ran in the previous frozen output. This time it shows
`status: not run` because no `GEMINI_API_KEY` / `GOOGLE_API_KEY` was set. Chunk text only got
**shorter**, so the earlier result (max 7,253 Gemini tokens in the largest-chunk sample, none over
8,192) still holds. To restore the check in the report, run the validator alone with the key set:

```bash
GEMINI_API_KEY=… .venv/bin/python scripts/segmentation/validate_segments.py
```

## 4. Follow-ups (from the manual step; see §5 for their outcome)

- **Commit** the XML fix together with the re-frozen outputs. For a clean `run_info.json`
  (`dirty: false`), commit the XML first, then re-run `segment_all.py` (outputs are
  deterministic) and commit the outputs.
- **Other documents with the same bug.** A first check for `;1` URNs found `mp_2228-1_20010906`.
  (`adi_rfb_1_20160118` is really nº 1, so it is correct.) Comparing every parse command's `-n`
  with the filename number then found **four MPs** in total. All were fixed in §5.

## 5. Parser fix, re-parse and second segmentation run (2026-09-25)

### 5.1 Root cause and fix (statutory parser, `../lexml-parser-projeto-lei`)

| Document | Parse command before | Metadata before | After |
|---|---|---|---|
| `constituição_1988_19881005` | no `-n` (parser default 1) | `;1` / `CONSTITUICAO Nº 1, DE 5 DE OUTUBRO DE 1988` | `;1988` / `Constituição da República Federativa do Brasil` |
| `mp_2158-35_20010824` | `-n 35` | `;35` / `Nº 35` | `;2158-35` / `MEDIDA PROVISÓRIA Nº 2.158-35, DE 24 DE AGOSTO DE 2001` |
| `mp_2159-70_20010824` | `-n 70` | `;70` / `Nº 70` | `;2159-70` / `Nº 2.159-70` |
| `mp_2189-49_20010823` | `-n 49` | `;49` / `Nº 49` | `;2189-49` / `Nº 2.189-49` |
| `mp_2228-1_20010906` | `-n 1` | `;1` / `Nº 1` | `;2228-1` / `Nº 2.228-1` |

- **Batch driver (`scripts/batch_parse.py`):**
  - it could not read a number with a complement (`2.228-1`), neither from the DOCX epígrafe nor
    from the filename, where `2228` was taken as a year. It now passes
    `-n 2228 --complemento 1`;
  - a constitution gets its year as its number (`-n 1988`).
- **Scala (`DocumentProfileOverride`):** it dropped the profiles' own epígrafe templates. The
  registered Constitution template (`Constituição da República Federativa do Brasil`, with its
  trailing period removed) is now used.

### 5.2 Re-parse

- The full `original/articulados` was re-parsed with the fixed parser: 225 converted, 0 failed.
- **42 of 468 XML files changed** and were promoted into `lexml/articulados`. The other 426 are
  byte-identical, so `lexml/articulados` now equals the fixed parser's output exactly. The
  changes:
  - **the 4 MPs** (7 files with their annexes): URN and epígrafe as in the table;
  - **the Constitution:** identical to the manual edit of §2; only its `.err.log` header is new;
  - **34 `decreto_*`:** the epígrafe lost a trailing space. The chunk text is unchanged because
    segmentation normalizes whitespace;
  - **`decreto_legislativo_92_19751105`:** the epígrafe is now `DECRETO LEGISLATIVO Nº 92, DE 1975`
    (was `…, DE 5 DE NOVEMBRO DE 1975`), which is **exactly the title in its DOCX**.

### 5.3 Segmentation re-run

```bash
.venv/bin/python scripts/segmentation/segment_all.py --jobs 16 --overwrite
```

The run took 89 s and all validation checks passed. The comparison is with the output of §3:

| Item | After §3 (Constitution only) | **After §5** |
|---|---|---|
| `chunks_all.csv` rows | 87,703 | **87,702** |
| Unique texts | 84,569 | **84,568** |
| Rows per strategy S1 / S2 / S3 | 26,251 / 82,643 / 87,703 | **26,250 / 82,642 / 87,702** |
| Qwen3 tokens total / max | 26,976,581 / 8,119 | **26,979,867 / 8,119** |
| cl100k tokens total / max | 25,725,279 / 7,895 | **25,726,989 / 7,895** |
| Files whose rows changed | — | 9 (listed below); all other files identical |

- **Changed files:**
  - `mp_2158-35` (+ `anexo1`), `mp_2159-70`, `mp_2189-49`, `mp_2228-1` (+ `anexo1`, `anexo2`): new
    `Texto` prefix, `texto_sha256`, token counts, `urn` / `doc_urn` / `anexo_urn`;
  - `decreto_legislativo_92` (+ `anexo1`): new `Texto` prefix (the shorter epígrafe).
- **The one row fewer:** in `mp_2228-1_20010906.anexo1`, the third `Art. 33.` got a slightly
  longer prefix, and the oversize-article splitter now packs it into **2 parts
  (1,021 + 1,019 tokens) instead of 3 (160 + 1,021 + 1,002)**. It is still under the cap.
- **References now match:**

  | `doc_urn` | Chunks | Linker references in `lexml/` |
  |---|---|---|
  | `…:2001-08-24;2158-35` | 295 | 148 |
  | `…:2001-08-24;2159-70` | 27 | 4 |
  | `…:2001-08-23;2189-49` | 54 | 25 |
  | `…:2001-09-06;2228-1` | 412 | 79 |
  | `…constituicao:1988-10-05;1988` | 3,017 | 1,303 |

- **Checksums:** `chunks_all.csv.gz`
  `f3db09046bb475bfcab1dfe84f4805a40a8fcd2629f252577c3aa492d1855f9b`, `chunks_all.csv`
  `fcacf9a46545f15a3e5cc682ae7d9b057f80c395944e523142d9dfb8055dde37`.
- `run_info.json` is again `dirty: true` (uncommitted `lexml/` changes), and the Gemini
  `countTokens` check was again not run (§3.3).

### 5.4 Remaining steps

1. **Commit**, in this order:
   - `../lexml-parser-projeto-lei`: the parser fix (code, tests, `CLAUDE.md`, work_history note);
   - here: `lexml/articulados` (42 XML + 40 `.err.log`) and the docs;
   - then re-run `segment_all.py` (deterministic) so `run_info.json` is clean, and commit
     `segmented/`.
2. Optionally re-run the Gemini check:
   `GEMINI_API_KEY="$(cat ~/keys/gemini_api_key)" .venv/bin/python scripts/segmentation/validate_segments.py`.

### 5.5 Outcome of §5.4 (2026-09-25)

- **Step 1 (commits).** The parser fix was committed in `../lexml-parser-projeto-lei`
  (`ebf6567`) and the re-parsed `lexml/articulados` here (`ecd68e5`). `segment_all.py` was then
  re-run on `ecd68e5` with clean inputs: 99 s, all validation checks passed, and
  `run_info.json` now records **`dirty: false`**. The output is **byte-identical** to §5.3
  (same `chunks_all.csv.gz` and `chunks_all.csv` SHA-256), confirming the run is deterministic.
  `segmented/` and these docs were committed together.
- **Step 2 (Gemini `countTokens`, `gemini-embedding-2`).** Re-run with the key; 0 errors, all
  checks still OK, and the result is now in `segmentation_report.{md,json}`:

  | Sample | n | Gemini > reference | Gemini/reference p50 / p99 / max | Max Gemini tokens | Over 8,192 |
  |---|---|---|---|---|---|
  | Random | 500 | 2 (max excess 61) | 0.886 / 0.960 / 1.101 | 6,220 | 0 |
  | 100 largest | 100 | 0 | 0.878 / 0.926 / 0.929 | 7,253 | 0 |

  The largest-chunk maximum (7,253) is the same as before the fix, as §3.3 expected.
