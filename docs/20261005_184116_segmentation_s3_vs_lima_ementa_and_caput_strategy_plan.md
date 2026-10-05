# S3 vs. [L], Ementa Enrichment of S1/S2, and a Caput Strategy (S4) — Review and Plan

**Generated:** 2026-10-05 18:41:16 (local time, from `date +%Y%m%d_%H%M%S`)
**Revised:** 2026-10-05, after review with the user (§4 decisions D-A, D-B).
**Builds on:** `docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` (**the strategy
doc**), `docs/20260924_123747_segmentation_implementation_plan.md` (**the plan**; X1–X10, §2.3, §5b),
`docs/20260924_175304_segmentation_execution_log.md` (**the log**; D1–D3, addenda),
`docs/20260927_204356_rag_pipeline_implementation_plan.md` (**the RAG plan**) and
`docs/20260927_222210_retrieval_legal_provision_test_jua.md` (**the first IR test**).
**Sources:** [L] = Oliveira Lima, *Unlocking Legal Knowledge with Multi-Layered Embedding-Based
Retrieval*, arXiv:2411.07739v1 (re-read from arXiv for this note); [F] = Fernandes, Lima, de Martim,
Oliveira, Lotufo, Pereira, *Structural Segmentation for Brazilian Legal Document Retrieval*
(`../Artigo chunks legislação.pdf`).
**Data checked:** `segmented/chunks_all.csv.gz` (87,702 rows, the frozen set used by the RAG runs).

---

## 0. Short answers and decisions

1. **Does S3 match [L]?** It has the same four layers that [L] actually embeds (grouping, article,
   caput/§, enumeration) and uses [L]'s enumeration-context rule. It is **not identical**: it leaves
   out [L]'s document and document-component layers, adds [F]'s metadata prefix to every chunk,
   has no CPT chunk for caput-only articles, splits articles above 1,024 tokens, and drops groupings
   above 8,192 tokens. Today it also adds the caput sentence to paragraph chunks; decision D-A below
   removes that. The full list is in §1.
2. **Ementa enrichment of S1 and S2 — already implemented.** Every chunk of every strategy already
   starts with `[ Epígrafe | Ementa ]`, which is exactly [F]'s "document metadata"
   (`[Bill No. x/xxxx | Summary of the bill.]`), in 100 % of the rows of every `Tipo` (checked). So
   **S1 already is [F]'s "Core Chunks + Metadata"**. The one remaining gap from [F] is that the ementa
   is **truncated to 128 tokens** in the prefix (9,318 rows). See §2.
3. **Caput and paragraphs are siblings — correct** (§3). In the frozen chunk set, however, paragraph
   chunks (PAR, and the INC/ALI/ITE under a §) also carry the **article label and the caput's opening
   sentence** (plan X3b / strategy doc §6 item 2), in S2 and S3 alike, because S2 and S3 are filters
   over one chunk set.
4. **Decisions (user, 2026-10-05):**
   - **D-A — S2 and S3 lose the caput sentence in paragraph chunks.** Paragraph-family chunks keep
     the article label + the paragraph subtree, and enumerations keep their ancestor path up to the
     §. This is [L]'s and [F]'s treatment (§1). S3 is still "S2 + groupings", so S2 vs S3 still tests
     one factor.
   - **D-B — S4 = S3 + the caput opening sentence in paragraph-family chunks**, i.e. exactly the
     texts the current chunk set holds. **S2c** (S2 + caput sentence) is the matching free filter.
     Adding the **full** caput (sentence + incisos/alíneas/itens) becomes the optional **S5**.
5. **Consequence:** the current S2/S3 retrievals and the first IR test were run on texts that are,
   by these definitions, **S2c and S4**. Those results stay valid under the new names. S2 and S3 must
   be re-embedded (only the 29,876 changed paragraph-family texts) and re-run (§4.6).
6. **Non-statutory documents:** no change (§5).

---

## 1. S3 compared with [L]

[L] §4.1 defines six layers. Its worked example (Title I of the Constitution) yields 32 chunks: 1
document + 1 document component + 4 articles + 25 article components (4 capita, 2 sole paragraphs,
19 incisos) + 1 title. The only context [L] adds is the ancestor text of enumerations, up to the
caput or paragraph (footnote 7: "[A República Federativa … tem como fundamentos:] dignidade da pessoa
humana").

| Aspect | [L] | S3 (after D-A) | Match? |
|---|---|---|---|
| Document layer | 1 chunk per document | not produced (strategy doc §5, "Not included") | **No.** Deliberate: whole documents exceed the embedding limits. [L]'s retrieved chunks never include one either |
| Document-component layer (main text, justification, annexes, tables) | 1 chunk per component | not produced as one chunk. Annex content is segmented into ART/DSP/TXT/TAB units | **No.** Deliberate. Annex text is reachable, but not as one whole-component vector |
| Basic unit hierarchy (parte … subseção) | 1 chunk per grouping | PRT…SSC = own label + name + all content below, **only if ≤ 8,192 tokens**. 243 groupings are left out (`segmented/groupings_over_limit.csv`), e.g. 5 of the Constitution's 9 títulos | **Partial.** Same unit; the largest groupings are missing |
| Basic unit (article) | whole article | whole article; **articles above 1,024 tokens are split** into structural parts (647 articles → 1,752 parts) | **Partial** |
| Basic unit component (caput, §) | caput **and** every paragraph, for every article (4 capita for 4 articles in the example) | CPT only when the article has ≥ 1 paragraph (plan X5/Q5; for caput-only articles the CPT text would equal the ART text); PAR for every paragraph | **Equivalent in content.** Only a duplicate vector is missing |
| Enumeration (inciso, alínea, item) | own text + ancestor text up to the caput/§ | same rule (strategy doc §5.2), and it also includes the **article label** and any `TituloDispositivo` | **Yes** (plus the label) |
| Paragraph context | paragraph text only (also [F] Fig. 3, chunk 6) | article label + paragraph subtree (**caput sentence removed by D-A**; it moves to S4) | **Yes** (plus the label) |
| Document metadata | none | `[ Epígrafe \| Ementa ]` on every chunk (ementa ≤ 128 tokens) | **No.** Taken from [F] |
| Grouping titles (`NomeAgrupador`) in the context | none (in [L]) | dropped (X2), following [F]'s finding that they bring no clear gain | Yes, for [L] |
| Remission text, tables, `TituloDispositivo`, orphan dispositivos (DSP), annexes, non-statutory TXT/TAB | not addressed | handled (X3, X4, X6, X8; plan §4–§5) | Extension |
| Retrieval filter (§4.2): 2,500-token budget, drop hits more than 25 % below the top score, containment de-duplication, at least 7 chunks | — | not segmentation. The RAG pipeline uses a **token budget** and **containment de-duplication**, but not the 25 % cut or the minimum of 7 | Partial (retrieval side) |

Constitution, for scale: [L] reports 2,954 chunks. S3 has **3,017** (ART 318 incl. split parts, CPT 195,
PAR 803, INC 1,295, ALI 318, TIT 4, CAP 29, SEC 50, SSC 5). The two counts are not directly
comparable, because of the CPT rule, article splitting, the grouping limit and possibly a different
ADCT coverage.

**Verdict:** after D-A, S3 is [L]'s multi-layer scheme restricted to its four embedded layers, with
[F]'s metadata and structural splitting of oversize articles. In the paper, describe it as "[L]'s
article-level-and-below layers plus groupings, with [F]'s metadata". The remaining differences from a
strictly [L]-faithful scheme are the metadata prefix, the missing CPT for caput-only articles, and
article splitting. I do not recommend removing them: [F] shows that metadata helps dense retrieval,
the missing CPT chunks only duplicate article vectors, and splitting is needed for the 1,024 cap.

**Not changed by D-A:** the HEAD of **split article parts** (plan §5b). A part that starts with a
paragraph still repeats the article label + caput sentence, because it is a piece of the article
(an ART unit in S1), not a paragraph chunk. S1 is therefore unchanged. If the user wants D-A applied
there too, it would change the 769 ART/DSP parts (of 1,749) whose first unit is a paragraph, and so the S1 baseline. I do not recommend it: without
the caput sentence, a part would not say what the article is about.

---

## 2. Ementa enrichment of S1 and S2 ([F] "metadata")

### 2.1 Current state (verified 2026-10-05)

```
Texto = "[ " + Epígrafe + " | " + Ementa(≤128 tokens) [+ " | " + annex label] + " ] " + CAMINHO + CONTEUDO
```

Example: the S1 ART chunk and the S2 INC chunk of Lei 9.250, art. 8 both start with
`[ LEI Nº 9.250, DE 26 DE DEZEMBRO DE 1995 | Altera a Legislação do Imposto de Renda das Pessoas
Físicas e dá outras providências. ] Art. 8º …`.

| Item | [F] | Ours |
|---|---|---|
| Fields | title + summary | Epígrafe + Ementa (cleaned of Planalto/Câmara page furniture, log step 2) |
| Separator / brackets | `[Bill No. x/xxxx \| Summary of the bill.]` | `[ <epígrafe> \| <ementa> ]` |
| Length | full summary (no limit stated) | ementa **truncated to 128 tokens** + ` …` |
| Annexes | — | parent epígrafe + parent ementa + `Anexo N – <title>` |
| Documents without an ementa | — | epígrafe only (e.g. `constituição_1988`) |
| Levels enriched | all chunks in Hierarchical; core chunks in the Core strategies | **all chunks of all strategies**, S1–S5 and TXT/TAB |

The requested change is in place for S1 (ART/DSP) and S2 (CPT/PAR/INC/ALI/ITE), and D-A does not
touch the prefix.

### 2.2 What is left (decisions and documentation only)

| # | Item | Recommendation |
|---|---|---|
| E1 | **Ementa truncation.** 9,318 of 87,702 rows (S1: 3,219 of 26,250; S2: 8,923 of 82,642) carry a truncated ementa, from 33 main documents, 26 category-C annexes and 72 non-statutory documents. [F] uses the full summary. Removing the limit makes long ementas (up to 2,951 chars in main documents; soluções de consulta are longer) dominate short chunks (INC p50 = 193 tokens), and the rows would have to be re-embedded | **Keep 128** and state it in the paper as a deviation from [F]. If the user prefers [F]-exact, set `--ementa-max-tokens 0` (meaning: no limit; this needs a one-line change in `common.truncate_tokens`), and do it **in the same re-run as D-A** (§4.5), so that only one new chunk set is frozen and embedded. The ART/DSP cap of 1,024 still applies, so a longer prefix can create a few more article parts |
| E2 | "Core Chunks + No Context" ablation ([F] Table 1) | **Do not run.** [F] already shows that it is worse. If a reviewer asks for it, strip the prefix with `^\[ .*? \] ` (no `]` can occur inside the prefix, because `metadata_for` replaces `[`/`]` with `(`/`)`) and embed the S1 texts once (≈ 26 k texts) |
| E3 | Documentation | Record in the strategy doc that S1 = [F] Core + Metadata and S2 = [F] Hierarchical without hierarchy titles and groupings (§6) |

---

## 3. Caput and paragraphs: is the premise right?

In LexML, and in LC 95/1998, an article is `Artigo → Caput, Paragrafo*`. **The caput and its
paragraphs are siblings**, and incisos/alíneas/itens hang under either of them. Checked: the corpus
`id`s are hierarchical (`art8_cpt_inc2…`, `art8_par2_inc1`). Outside `Alteracao`, **no**
`Paragrafo` lies under a `Caput` in `lexml/articulados`. The 1,596 that do are quoted amending text
("Art. X passa a vigorar com …"), which gets no rows of its own.

Paragraph-family texts per strategy, for Lei 9.250, art. 8 (text after the prefix):

| Chunk | Frozen set today (= S2c/S4 after D-B) | S2/S3 after D-A | S5 (optional) |
|---|---|---|---|
| CPT `art8_cpt` | `Art. 8º A base de cálculo … somas: I – … II – das deduções relativas: a) … b) …` | unchanged | unchanged |
| PAR `art8_par2` | `Art. 8º A base de cálculo … somas: § 2º O disposto na alínea a do inciso II: I – … II – …` | `Art. 8º § 2º O disposto na alínea a do inciso II: I – … II – …` | `Art. 8º A base de cálculo … somas: I – … II – das deduções relativas: a) … § 2º O disposto …` |
| INC `art8_par2_inc1` | `Art. 8º A base de cálculo … somas: § 2º O disposto na alínea a do inciso II: I – aplica-se, também, …` | `Art. 8º § 2º O disposto na alínea a do inciso II: I – aplica-se, também, …` | full caput before `§ 2º` |
| INC `art8_cpt_inc2` (caput side) | `Art. 8º A base de cálculo … somas: II – das deduções relativas: a) …` | unchanged (the caput is its ancestor, not a sibling) | unchanged |

So, after D-A:

- "caput and its components" = CPT, **only for the 8,084 articles that have a paragraph** (for
  caput-only articles the ART chunk is the same text);
- "paragraph and its components" = PAR, with only the article label as context;
- the caput sentence in paragraph chunks belongs to S4, and the full caput to S5.

---

## 4. Plan: caput-free paragraphs in S2/S3, caput sentence in S4 (full caput in S5)

### 4.1 Strategy definitions

| ID | Indexed `Tipo`s | Paragraph-family text | Status |
|---|---|---|---|
| **S1** | ART, DSP, TXT, TAB | — (no paragraph chunks; ART parts keep their HEAD, §1) | Baseline, **unchanged** |
| **S2** | S1 + CPT, PAR, INC, ALI, ITE | **article label + paragraph subtree** (D-A) | Main hypothesis, **re-built** |
| S3 | S2 + PRT…SSC (≤ 8,192 tokens) | same as S2 | Optional, **re-built** |
| **S4** | same `Tipo`s as S3 | article label + **caput sentence** + paragraph subtree (= the frozen texts) | Optional (D-B) |
| S2c | same `Tipo`s as S2 | same as S4 | Free filter: S2 vs S2c is the cheaper caput comparison |
| S5 | same `Tipo`s as S3 | article label + **full caput** + paragraph subtree | Optional, later |

"Paragraph family" = every PAR row plus every INC/ALI/ITE row with a `Paragrafo` ancestor: **29,876
rows** (PAR 21,511, INC 6,645, ALI 1,644, ITE 76). All other rows (ART/DSP and their parts, CPT,
caput-side INC/ALI/ITE, groupings, TXT, TAB) are identical in every strategy.

Comparisons:
- S1 vs S2: sub-article units (main question, now without the caput confound);
- S2 vs S3: groupings;
- **S3 vs S4** (or S2 vs S2c): does a paragraph chunk need the caput sentence? (the question you
  asked for);
- S4 vs S5: does it need the caput's components as well? (optional).

### 4.2 Data model: text variants, not new `Tipo`s

Today a strategy is a set of `Tipo`s over one chunk table, and each chunk has one text (`strategies.py`,
`scripts/rag/strategies.yaml`). S4/S2c/S5 change the **text** of existing units, so they cannot be
`Tipo` filters.

- `chunks_all.csv` gets a column **`variante`**:
  - `base` — every row of S1–S3; paragraph-family rows **without** the caput sentence (D-A);
  - `caput` — 29,876 paragraph-family rows **with** the caput sentence (S4/S2c);
  - `caput_completo` — S5 rows (only if S5 is built).

  A variant row copies every column of its `base` twin (Tipo, Rotulo, urn, intervals, provenance)
  except `Texto`, `texto_sha256`, the token columns and `chunk_id`.
- **Chunk ids (recommended):** the `caput` rows **keep the `chunk_id`s of the frozen set**, since
  their texts are the frozen texts, and the new caput-free `base` rows get new ids
  (`<stem>#b<seq>`). The existing `chunk_map.csv.gz`, rankings and per-item tables then stay
  consistent as the S2c/S4 results without any remapping (§4.6).
- New columns: `contexto_ids` (id of the caput whose text was added; empty for `base`) and
  `caput_completo` (S5 only: 1, or 0 when the cap rule fell back to the sentence, §4.4).
- Strategy config:

  ```yaml
  S2:  {tipos: [<S2 tipos>], variantes: [base]}
  S3:  {tipos: [<S3 tipos>], variantes: [base]}
  S2c: {tipos: [<S2 tipos>], variantes: [caput, base]}           # per unit, first variant that exists
  S4:  {tipos: [<S3 tipos>], variantes: [caput, base]}
  S5:  {tipos: [<S3 tipos>], variantes: [caput_completo, base]}  # optional
  ```

  `variantes` defaults to `[base]`. Row counts: S2/S2c = 82,642; S3/S4/S5 = 87,702 (variants replace
  rows rather than adding them).
- **Invariants (validated):** (i) every non-paragraph-family `base` row is byte-identical to the
  frozen set (same `chunk_id`, `texto_sha256`), so S1 and its embeddings, rankings and evaluations
  are untouched; (ii) the `caput` rows are byte-identical to the frozen paragraph-family rows.

Rejected: new `Tipo` codes (`PRC`, `INCC`, …). They would leak into `nivel`, `unit_precedence`, the
relevance levels and every report, all of which are about structure, not text.

### 4.3 Implementation steps

| # | Where | Change |
|---|---|---|
| C1 | `scripts/segmentation/segmenta_estatutario.xsl` | Make **X3b switchable**: new param `caput_em_paragrafo` (`nao` \| `frase`, default **`nao`**). With `nao`, `lx:caminho` no longer inserts `../Caput/p` after the article label for nodes with a `Paragrafo` ancestor. The XSL's default output becomes the D-A `base` texts |
| C2 | `scripts/segmentation/common.py` | Python mirror: `caminho(n, caput="nenhum"\|"frase"\|"completo")`, where `completo` inserts `texto(Caput)`. **`split_oversize.py` must call it with `caput="frase"` explicitly**, so the ART-part HEAD is unchanged (§1). The XSL/Python parity test runs with both XSL settings |
| C3 | new `scripts/segmentation/add_caput_variants.py` | For each statutory CSV + XML: select the paragraph-family rows (through the XML: element with a `Paragrafo` ancestor inside an `Artigo`, or a PAR); write `<file>.caput.csv` (`frase` texts) and, with `--completo`, `<file>.caput_completo.csv` with the cap rule of §4.4; write provenance records (`variante`, `contexto_ids`, `caput_completo`). Covers main documents and category-A annexes. Paragraphs with no `Caput` sibling (orphan structures, e.g. under DSP; 98 rows) get no variant, so S4 falls back to their `base` row. Python is used rather than a second XSL pass because S5 needs token counts, which XSLT cannot do (plan §5b) |
| C4 | `scripts/segmentation/segment_all.py` | XSL with `caput_em_paragrafo=nao`; new step 3c `add_caput_variants` (`--variants caput[,caput_completo]`, default `caput`). The merge (step 6) appends the variant rows and assigns `chunk_id`s as in §4.2 (it reads the frozen `chunks_all` to reuse the ids; `--chunk-id-source <csv.gz>`). `run_info.json` records the flags |
| C5 | `scripts/segmentation/validate_segments.py` | New checks: `base_unchanged` (invariant i); `caput_variant_frozen` (invariant ii: `caput` texts and ids equal the frozen paragraph-family rows); `variant_twins` (one `base` twin per variant row, with the same `urn`, `Tipo` and intervals); `base_no_caput` (a `base` paragraph-family text does not contain the caput sentence right after the article label); S5 only: `variant_cap`. The text-coverage check is unaffected (it uses S1) |
| C6 | `scripts/segmentation/strategies.py` | `STRATEGIES` holds `(tipos, variantes)`; `filter(df, "S4")` keeps, per `(arquivo, urn, Tipo)`, the row of the first listed variant. Callers that only pass a `Tipo` set keep working (they get `base`) |
| C7 | `scripts/rag/strategies.yaml`, `ragpipe/strategies.py`, `ragpipe/data.py` | Parse `variantes`, apply the same per-unit selection, add S2c/S4 (S5 later), and update `expected_rows` and the chunk-file SHA-256. Text ↔ chunk aliasing is unchanged |
| C8 | `ragpipe/relevance.py`, `context.py` | **Nothing for S4/S2c**: the caput sentence is partial caput text, and the frozen texts were already scored without caput credit. S5 only: report gold hits with and without `contexto_ids` as covered (`gold_cover` modes), and let a `caput_completo` row cover its own interval **and** the caput's interval in containment de-duplication |
| C9 | `scripts/embedding` | `corpus` refuses a different input file unless `--overwrite`. Add **`--extend`**: load the existing store, embed only the `text_id`s that are missing (the 29,876 caput-free texts, ≲ 7.7 M reference tokens, minus the removed sentences), and write a merged store (`vectors.npy` + `texts.csv` + `chunk_map.csv.gz`) whose manifest lists both input SHA-256s. The parity gate and the template/instruction checks still apply. Run it for `jua-4b-mixed` first, then for every other model |
| C10 | tests (`scripts/segmentation/tests`, `scripts/rag/tests`) | Update the §3.2 worked target of the plan: `PAR art8_par2` (`base`) = `Art. 8º § 2º O disposto …`, with no caput sentence; its `caput` variant equals today's text. The `ITE art8_cpt_inc2_ali2_ite10` target is unchanged (caput side). XSL regression with both param values. Split-part HEAD unchanged (largest RIR/2018 article). Filters: S4 = S3 with substitutions; S2c = S2 with substitutions; S1 unchanged |

### 4.4 S5 (optional): full caput

Same machinery, variant `caput_completo`. Estimates from `chunks_all`: PAR + full caput ≈ p50 354,
p90 711, p99 1,672, max ≈ 8,383 tokens; 824 PAR rows (3.8 %) over 1,024 and 14 over 8,192. Proposed
rule: full caput when the chunk is ≤ 1,024 tokens, otherwise fall back to the caput sentence
(`caput_completo = 0`). Texts whose caput has no components are identical to the S4 text and share
its `text_id`. A third variant, "only the caput components the paragraph cites" (e.g. "alínea a do
inciso II"), needs intra-article reference resolution and is future work. `lexml-linker` targets
references to legislation; whether it resolves bare "inciso II" mentions has not been checked.

### 4.5 Work order

1. Decide Q1–Q3 (§7). If E1 changes, implement it now so that only one new chunk set is frozen.
2. C1 + C2 + C10 (segmentation tests) → check on `lei_9250`, `decreto_9580…anexo1`, `decreto_3000`.
3. C3 + C4 + C5 → full run; `base_unchanged` and `caput_variant_frozen` must pass; freeze
   (`run_info.json`, `chunks_all.csv.gz`, which now has ≈ 117.6 k rows).
4. C9 → embed the caput-free texts with `jua-4b-mixed` (`--extend`).
5. C6 + C7 (+ rag tests) → `rag.py retrieve` + `evaluate` for S1, S2, S3, S2c, S4.
6. Dated results note in `docs/`, and the doc updates of §6.
7. S5 (C3 `--completo`, C8, embedding) only if S3 vs S4 shows an effect worth refining.

### 4.6 Existing results

- `runs/retrieval/jua-4b-mixed/irpf/` (S1/S2/S3) and `runs/…/eval/either_containment_skip/` were
  produced from the frozen set. Under the new definitions: **S1 stays S1, S2 → S2c, S3 → S4.**
- After step 5 the S2/S3 names refer to the caput-free texts. To avoid silently mixing the two
  meanings, the re-run should use a new `eval_id`. The old manifests keep the old chunk-file
  SHA-256, which tells them apart, and the first IR test should get a header note: "S2/S3 in this
  note = S2c/S4 in the 2026-10-05 definitions".
- The headline numbers of the first IR test (e.g. sub-article gold Recall 0.328 / 0.376 / 0.369 for
  S1 / S2 / S3) therefore already answer part of the S1-vs-S2c question. S1 vs the new S2 must be
  measured again.

---

## 5. Non-statutory documents

| Change | Apply to `nao_articulados` / category C / loose content? | Why |
|---|---|---|
| Ementa metadata (§2) | **Already applied**: `[ Epígrafe \| Ementa ]` with fallbacks (`campo EMENTA`/`ASSUNTO`, `preliminar` first line). 5 files have no ementa | Same rule as statutory, so the prefix is not a confounder |
| Ementa truncation (E1) | If E1 changes, change it **for all documents at once** (72 non-statutory files and 26 category-C annexes are affected) | A strategy-independent setting must stay identical across all strategies |
| D-A / S4 / S5 (caput in paragraphs) | **No** | There is no caput/paragraph structure: `Agrupamento`/`p` are PDF lines, and headings are already repeated at the start of each unit. The nearest analogue, a soluções-de-consulta ementa acting as the "head" of every part, is already in the prefix. Changing NS rows would mix a second factor into S3 vs S4 (strategy doc §6 item 4). They stay `base` only and are identical in every strategy |
| Annexes with articles (category A) | **Yes, automatically**: C1/C3 handle them like main documents | They are statutory |
| Orphan dispositivos (category B, DSP) | No variant | A top-level orphan `Paragrafo` has no caput sibling |

---

## 6. Documentation updates to bring the strategy record up to date

| File | Update |
|---|---|
| `docs/20260923_193852_…strategies…md` | Decision table: S1 / S2 / S3 now with **caput-free paragraph chunks**; add **S4 (optional) = S3 + caput sentence in paragraph-family chunks**, S2c, and S5 (optional, full caput), with a pointer to this note. §5: S1 = [F] "Core Chunks + Metadata", S2 = [F] "Hierarchical" without hierarchy titles. **§6 item 2: reversed on 2026-10-05**: the caput sentence moves out of the base chunks into the S4 variant (D-A/D-B); the Art. 8 § 2 example moves to the S4 rationale. §5.2: unchanged (it is a caput-side example). §5 counts: refer to the grouping-limit addendum (S3 = 87,702) |
| `docs/20260924_123747_…implementation_plan.md` | Short note at X3b and §3.2: "superseded by the 2026-10-05 note; X3b is now the `caput_em_paragrafo=frase` option" |
| `docs/20260927_222210_retrieval_legal_provision_test_jua.md` | Header note: its S2/S3 are S2c/S4 in the new definitions (§4.6) |
| `CLAUDE.md` | Strategy list: "S1 article baseline, S2 article + ancestor-path sub-units (paragraphs without the caput), optional S3 + groupings, optional S4 = S3 + caput sentence in paragraph chunks (S5: full caput)", plus a pointer to this note |
| `scripts/segmentation/README.md`, `strategies.py` docstring | `caput_em_paragrafo`, `add_caput_variants.py`, `variante`/`contexto_ids` columns |
| `scripts/rag/README.md`, `strategies.yaml` header | `variantes`, new strategies, expected counts and SHA-256 |
| `scripts/embedding/README.md` | `--extend` |
| Paper text | §1 verdict on S3 vs [L]; E1 (ementa truncated to 128 tokens) as a deviation from [F] |

---

## 7. Open questions

- **Q1 — Ementa truncation (E1).** Keep 128 tokens (recommended), or use the full ementa as in [F]?
  If it changes, do it in the same re-run as D-A.
- **Q2 — Split article parts.** Keep the caput sentence in the HEAD of ART parts that start with a
  paragraph (recommended; S1 unchanged), or apply D-A there too?
- **Q3 — S5.** Build it now, or only after S3 vs S4 (recommended)?
