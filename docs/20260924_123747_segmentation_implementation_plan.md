# Segmentation Implementation Plan

**Generated:** 2026-09-24 12:37:47 (local time, from `date +%Y%m%d_%H%M%S`)
**Implements:** `docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` (referred to below
as **the strategy doc**; section numbers like §6 point into it).
**Deliverables:** everything goes into `scripts/segmentation/`; outputs go into `segmented/`.

The plan has five parts:

1. an **amended copy of the XSL** for statutory documents and annex categories A/B (§3 below);
2. a **Python segmenter for non-statutory content** (`nao_articulados`, annex category C, and loose
   text/tables in A/B annexes) (§5);
3. an **annex router** that picks the segmenter from each annex's content (§4);
4. an **oversize-article splitter** that enforces the 1,024-token cap on articles (§2.6, §5b);
5. an orchestrator and a validator that tie them together (§6–§7).

---

## 0. Corpus facts checked for this plan (2026-09-24)

These were measured on `lexml/` while writing this plan. They add to the strategy doc §4 and affect
the design:

| Finding | Where | Consequence |
|---|---|---|
| Annex categories by content: **A = 12, B = 50, C = 181** | `lexml/articulados/*.anexoN.xml` | Matches the strategy doc; the router rule in §4 reproduces it |
| **32 of 50 category-B annexes and 4 of 12 category-A annexes also have loose `p`/`table`** next to the dispositivos (e.g. `in_srf_256_20021211.anexo2`: 138 dispositivos + 148 loose `p`/`table`; RIR `decreto_9580_20181122.anexo1`: a tax table before `LIVRO I`) | `PartePrincipal`/`Articulacao` children | The XSL alone would drop them. They get the non-statutory treatment (§5), in the same CSV as the XSL rows |
| **≈ 420 tables inside dispositivos**: 137 inside `Artigo` (58 in main documents, 79 in annexes), the rest under orphan dispositivos of category-B annexes (direct parents: `Item` 308, `Inciso` 81, `Caput` 22, `Alinea` 9, …); `td` never holds `p` | e.g. `decreto_3000_19990326.xml` | The XSL reads only `p` text, so **table content (tax tables) is lost**. Fix X8 |
| `TituloDispositivo` in 1,324 dispositivos (1,038 under `Artigo`) | statutory | Ignored by the XSL. Fix X4 |
| Remissions and links are `span`/`Remissao` children of `p` | all | The XSL's `p/text()` (enumeration context, lines 182–183, 196) **drops the cited text** ("arts. 7°", "Lei nº …"). Fix X3 |
| 15 of 224 main-document `Ementa`s start with `CÂMARA DOS DEPUTADOS Centro de Documentação e Informação <epígrafe>`; `constituição_1988_19881005.xml` has no `Ementa`; longest ementa is 2,951 chars | main docs | Clean ementas in one place (Python, §2.3) and pass the metadata to the XSL as a parameter |
| Non-statutory structure: `PartePrincipal` → `Agrupamento[@nome]` (`texto` 1,438, `assinatura` 392, `nota` 366, `epigrafe` 226, `ementa` 121, `preliminar` 53, …) and `AgrupamentoHierarquico` (section with `Rotulo`/`NomeAgrupador`, nesting depth ≤ 4); `Bloco` is an empty ordering marker; `p` elements are **PDF lines**, not paragraphs | `lexml/nao_articulados` | Units are `Agrupamento`s; split on line boundaries that end a sentence (§5.3) |
| `Agrupamento` text length: median 290 chars, p90 3.8 k, p99 20.8 k, max 83 k | `nao_articulados` | A token cap with splitting is required |
| `decreto_lei_58_19371210.anexo1` has a `Livro` but no `Artigo` or dispositivo | category C | Python treats groupings as section headings (§5.2) |
| Environment: `saxonche` and `lxml` are installed; `tiktoken` and `transformers` are not | — | Install both for the reference tokenizer (§2.6); keep the tokenizer pluggable (§5.4) |
| Element `id`s are **hierarchical**: every dispositivo's `id` is its parent dispositivo's `id` + `_…` (0 exceptions), e.g. `art8_cpt_inc2_ali2_ite10`; grouping ids likewise (`liv2_tit4_stt1_cap2_sec7`). This is the same fragment scheme the linker uses in `Remissao`/`span` hrefs (`…;7713!art7`, `…;12618!art3_par1`) | statutory | An id alone gives the article and the full dispositivo path; gold citations passed through `lexml-linker` can be matched to chunks by id prefix (§2.7) |
| **Duplicate ids in 61 files** (≈ 1.4 k repeats: orphan `Item` 532 / `Alinea` 305 such as `ali1`, and 65 `Artigo`s, e.g. two `Art. 16.` = `art16` in `circ_bc_3432_20090203`) | statutory | `urn` is **not** unique; add a unique `chunk_id` and flag ambiguous ids (§2.7) |
| **Orphan dispositivos also in 21 main documents** (e.g. `decreto_67542_19701112` 104, `decreto_50656_19610524` 57) | statutory main docs | `DSP` rows must be emitted in every document, not only in category-B annexes (X6 amended) |
| Loose `p` under `PartePrincipal`/`Articulacao` have **no `id`** (0 of 1,809); every `table` has one | annexes | Python builds synthetic ids for loose-text units (§2.7) |
| `Artigo` text length: p50 372, p90 1,605, p99 4,841, max 32,740 chars; 409 articles > 3,500 chars (≈ 1,024 tokens), 51 of them with a single leaf dispositivo > 3,500 chars | statutory | Split oversize articles (§2.6, §5b) |

---

## 1. Layout in `scripts/` and `segmented/`

```
scripts/segmentation/
  README.md                          how to run; pointer to this plan
  GeraCSVporArtigoPorAgrupador.xsl   verbatim copy of the original (reference, never edited)
  segmenta_estatutario.xsl           amended XSL (§3)
  common.py                          metadata extraction, CSV writer, numbering, tokenizer (§2)
  classify_annexes.py                annex router (§4) → segmented/annex_manifest.csv
  run_xsl_segmentation.py            Saxon driver, adapted from run_segmentation_csv.py (§3.3)
  segment_non_statutory.py           lxml segmenter (§5)
  split_oversize.py                  splits ART/DSP rows above the token cap (§5b)
  segment_all.py                     orchestrator (§6)
  validate_segments.py               checks + statistics report (§7)
  strategies.py                      S1/S2/S3 filters over the chunk table (§2.2)
  tests/                             pytest + small XML fixtures copied from lexml/

segmented/
  annex_manifest.csv                 router decisions, one row per annex
  statutory/<file>.csv               XSL output (+ loose-content rows for A/B annexes)
  non_statutory/<file>.csv           Python output (nao_articulados + category C)
  */<file>.prov.jsonl                provenance sidecars for split / synthetic-id rows (§5b, §2.7)
  chunks_all.csv                     merged table fed to the embedding step, with provenance (§2.7)
  segmentation_report.{md,json}      counts, lengths, oversize list, validation results
```

One CSV per source XML, named after that XML file, keeps provenance simple and lets a single
document be regenerated.

---

## 2. Shared conventions (both segmenters)

### 2.1 CSV schema and `Tipo` vocabulary

Per-file CSVs keep the XSL schema exactly: `Tipo, Rotulo, Num_Inicio, Num_Final, Texto, urn`. All
fields are quoted, and inner quotes are doubled. `chunks_all.csv` adds trailing columns:
`arquivo` (source XML), `segmentador` (`xsl` | `python`), `categoria` (`main` | `A` | `B` | `C` |
`nao_articulado`), and the provenance columns of §2.7.

| `Tipo` | Produced by | Meaning | New? |
|---|---|---|---|
| `ART` | XSL (+ `split_oversize.py`) | Article (whole subtree), or one part of an article above the token cap (§5b) | — |
| `DSP` | XSL (+ `split_oversize.py`) | **Top-level orphan dispositivo**: a `Caput`/`Paragrafo`/`Inciso`/`Alinea`/`Item` with no dispositivo ancestor. Mostly in category-B annexes, but also in 21 main documents (§0). It is the article-equivalent unit of rule 3.2 | **new** |
| `CPT`, `PAR`, `INC`, `ALI`, `ITE` | XSL | Sub-article units with ancestor path | — |
| `PRT`, `LIV`, `TIT`, `SBT`, `CAP`, `SEC`, `SSC` | XSL | Groupings | — |
| `TXT` | Python | Non-statutory text unit (an `Agrupamento`, or one split part of it) | **new** |
| `TAB` | Python | A table, or a row-group part of one | **new** |

### 2.2 Strategy filters (`strategies.py`)

```
NS = {TXT, TAB}                     # identical in every strategy (§6 item 4)
S1 = {ART, DSP} ∪ NS
S2 = S1 ∪ {CPT, PAR, INC, ALI, ITE}
S3 = S2 ∪ {PRT, LIV, TIT, SBT, CAP, SEC, SSC}
```

Every chunk has one text regardless of strategy, so S1 and S2 are filters over the S3 embeddings.

### 2.3 Chunk text template and metadata

```
Texto = "[ " + METADADOS + " ] " + CAMINHO + CONTEUDO
```

- **`METADADOS`** is computed **once, in Python** (`common.metadata_for(xml_path)`), and passed to the
  XSL as a parameter, so both segmenters use the same rules:
  - main statutory document: `Epígrafe | Ementa`;
  - annex (any category): `<parent Epígrafe> | <parent Ementa> | <annex label>`. The annex label is
    `Anexo N` (from the `!anexoN` URN suffix) plus the annex's own title when there is one (the annex
    `Epigrafe` for `DocumentoArticulado`, or the first `PartePrincipal/p` if it starts with
    `ANEXO`);
  - non-statutory document: `<Agrupamento nome="epigrafe">` text (fallback: `campo` fields, then the
    URN), then ` | ` and `<Agrupamento nome="ementa">` (fallback: `campo[@nome=EMENTA|Ementa|ASSUNTO|Assunto]`).
  - Cleaning: normalize whitespace; strip a leading `CÂMARA DOS DEPUTADOS Centro de Documentação e
    Informação` and a repeated epígrafe at the start of the ementa; replace `[`/`]` inside metadata
    with `(`/`)` so the prefix stays parseable. Truncate the ementa in the prefix to
    `--ementa-max-tokens` (default 128; see open question Q2). A non-statutory ementa that is
    truncated also gets its own `TXT` chunk, so no text is lost.
- **`CAMINHO`** (ancestor path, §5.2 of the strategy doc) applies to sub-article units only: for
  each ancestor dispositivo, its `Rotulo` + `TituloDispositivo` + its **own** `p` (not its other
  children). For units inside a `Paragrafo`, the caput's own `p` is inserted after the article label
  (strategy doc §6 item 2). No `NomeAgrupador` is included.
- **`CONTEUDO`**: the unit's own `Rotulo`, `TituloDispositivo`, `p` and table text, then the same for
  all its descendants, in document order.
- Table serialization (both segmenters): cells joined with ` | `, rows joined with ` ; `, prefixed by
  `Tabela:`; the header row(s) come first.

### 2.4 Interval numbering

Both segmenters produce nested intervals that follow the XSL's `calculaPos` contract: a parent's
`[Num_Inicio, Num_Final]` encloses its descendants' intervals, and siblings are disjoint.

- The XSL keeps `calculaPos` unchanged (a regression test guards it, §7).
- Python numbers by a DFS counter (`start = ++c` on entry, `end = ++c` on exit). Split parts are
  sibling intervals inside the unit's range.
- When Python adds **loose-content rows to an A/B annex CSV**, its counter starts at
  `max(Num_Final of the XSL rows) + 1`, so the intervals never overlap within a file.
- Split article parts (§5b) take the interval `[min Num_Inicio, max Num_Final]` of the dispositivos
  they contain, so parts are disjoint and still enclose their sub-unit rows. Pieces of a single leaf
  split inside itself share the leaf's interval.
- Containment de-duplication at retrieval time compares intervals **only within the same `arquivo`**,
  and never treats two parts of the same split unit (same base `urn` before `_p<k>`) as covering
  each other.

### 2.5 `urn` column

It holds `<Identificacao/@URN>!<element id>`, as the XSL already does. Annex URNs already contain
`!anexoN`, which gives e.g. `urn:…;9580!anexo1!art1`, so consumers split on the **last** `!`. Python
rows use the `id` of the `Agrupamento`/`table`; split parts get the suffix `_p<k>` (e.g.
`…!pp1_agr5_p2`). Split article parts (§5b) follow the same pattern (`…!art8_p2`).
Because the source has duplicate ids (§0), `urn` is **not** guaranteed to be unique. The unique key is
`chunk_id` (§2.7). For retrieval evaluation, use the provenance columns of §2.7 rather than parsing
`urn`.

### 2.7 Provenance columns (for retrieval evaluation)

Each chunk must be traceable back to its document, annex, groupings, article and dispositivo, and a
split part must say exactly which dispositivos it holds. The 6-column per-file CSVs cannot carry all
of that, so a Python **provenance step** (orchestrator step 6, §6) adds these columns to
`chunks_all.csv`. It looks up each row's element in the XML through the `id` in `urn`, or through the
part and piece bookkeeping of §5 and §5b.

| Column | Content | Example |
|---|---|---|
| `chunk_id` | Unique key: `<arquivo stem>#<row seq>` | `lei_9250_19951226#412` |
| `doc_urn` | URN of the **main** document (for an annex, the parent's URN) | `urn:lex:br:federal:lei:1995-12-26;9250` |
| `anexo_urn` | Annex URN, empty for main documents | `urn:lex:br:federal:decreto:2018-11-22;9580!anexo1` |
| `nivel` | Hierarchy level of the unit: `ART`, `DSP`, `CPT`, `PAR`, `INC`, `ALI`, `ITE`, `PRT`…`SSC`, `TXT`, `TAB` | `ITE` |
| `unidade_id` | LexML `id` of the unit, with **no** part suffix (for a part, the article's id) | `art8_cpt_inc2_ali2_ite10` |
| `artigo_id` | `id` of the enclosing article or `DSP` (empty for groupings and non-statutory rows) | `art8` |
| `agrupadores_ids` | Ids of the enclosing groupings, outermost first, `;`-separated | `cap3` |
| `agrupadores_rotulos` | Their labels + names | `CAPÍTULO III – DA DECLARAÇÃO DE RENDIMENTOS` |
| `citacao` | Citation-style path | `Art. 8º, caput, II, b, 10` |
| `parte`, `n_partes` | `k`, `n` for split units; `1`, `1` otherwise | `2`, `4` |
| `cobre_ids` | Ids of the **maximal dispositivos wholly contained** in the chunk, `;`-separated. For an unsplit unit this is `unidade_id`; for an article part, the packed units (e.g. `art6_par3;art6_par4;art6_par5`, or `art6_cpt_inc20;…;art6_cpt_inc35` after descending). Descendants are implied by id prefix | `art6_par3;art6_par4` |
| `parcial_ids` | Ids of dispositivos that are only **partly** in the chunk: a leaf split within itself (§5b step 4), plus the article and caput whose labels and sentence are repeated in `HEAD` but whose other children are in other parts | `art6;art6_cpt` |
| `id_ambiguo` | `1` if `unidade_id` (or any id in `cobre_ids`) occurs more than once in the file | `0` |

Non-statutory rows:
- `unidade_id` = the `Agrupamento` or `table` id;
- loose text runs, which have no id in the XML, get a synthetic id `<parent id>_p<first>-<last>`,
  built from the 1-based positions of their `p` children (e.g. `anexo8_pp_p3-p7`);
- `cobre_ids` = `unidade_id`; the `agrupadores_*` columns come from the `AgrupamentoHierarquico`
  path.

**How the evaluation uses it** (the matching itself belongs to the evaluation code, not to this
plan). A gold citation resolved to `doc_urn!fragment` (e.g. with `lexml-linker`, which uses the same
id scheme) is **fully hit** by a chunk when some id in `cobre_ids` equals the fragment or is its
ancestor (id prefix up to a `_` boundary), and **partly hit** through `parcial_ids`. Coarser levels
come from the same columns: document (`doc_urn`), annex (`anexo_urn`), grouping
(`agrupadores_ids`), and article (`artigo_id`).
Rows with `id_ambiguo = 1` are reported separately, since a match on them is not unique.

**Known caveat for evaluation:** a gold citation such as "art. 35 do RIR/2018" may resolve to
`…;9580!art35`, but the article lives in `…;9580!anexo1`. The decree's own articles and the annex's
articles share `doc_urn`, and only `anexo_urn` tells them apart. The evaluation code must map these
citations to the annex (keep a small table of "regulamento aprovado pelo decreto" cases).

### 2.6 Token cap: **1,024 tokens** (decided 2026-09-24)

Embedding models to be swept, with their input limits (checked 2026-09-24 on the model cards / API
docs):

| Model | Max input (tokens) | Tokenizer | Notes |
|---|---:|---|---|
| `text-embedding-3-small` (OpenAI) | 8,192 | `cl100k_base` | API; over-limit input is rejected |
| `gemini-embedding-2` (Google) | 8,192 | Gemini (count via API `countTokens`) | API; over-limit input is silently truncated |
| `Qwen/Qwen3-Embedding-4B` | 32 k | Qwen | 2,560 dims (32–2,560 selectable) |
| `ufca-llms/jua-4B-mixed` | 32 k inherited; model card example uses `max_length=8192` | Qwen (fine-tuned from Qwen3-Embedding-4B) | Training length not stated in the paper (arXiv 2605.04005) |
| `infly/inf-retriever-v1` | 32,768 | Qwen2 (base: gte-Qwen2-7B-instruct) | 7B, 3,584 dims |

The binding model limit is therefore 8,192 tokens, but the cap is set well below it, as a
**granularity** choice: non-statutory and oversize chunks compete with statutory chunks in the same
index and the same RAG context budget, so they should have the size of a typical article, not of a
whole opinion. Reference points (text chars, ≈ 3.5–4 chars/token for Portuguese): `Artigo` p50 372,
p90 1,605, p99 4,841, max 32,740 chars; 1,024 tokens ≈ article p97.

Rules:

1. **Every chunk that a strategy indexes as its basic unit must be ≤ 1,024 tokens**, counted on the
   **full** `Texto` (metadata prefix and path included): `TXT`, `TAB` (§5.3) **and `ART`/`DSP`**,
   which are split into parts when above the cap (§5b). Expected: ≈ 400–600 of the 19.4 k articles
   (2–3 %) are split; ≈ 50 of them have a single dispositivo (usually a table) that is over the cap
   by itself and needs a within-leaf split.
2. **Reference tokenizer = the per-text maximum over `tiktoken:cl100k_base` and
   `hf:Qwen/Qwen3-Embedding-4B`** (`--tokenizer max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`).
   The Qwen tokenizer covers the three Qwen-based models. Gemini cannot be counted locally at corpus
   scale: during step 7 (§8) count a random sample of ≈ 500 chunks with `countTokens` and confirm
   Gemini ≤ the reference count (with 8,192 as the real limit, a small excess would not truncate
   anything, but it is reported).
3. One segmentation run, with this cap and tokenizer, serves **all** embedding models, so every model
   embeds exactly the same chunk set.

Dependencies to add: `tiktoken`, `transformers` (tokenizer only, no model weights).

---

## 3. XSL changes (`scripts/segmentation/segmenta_estatutario.xsl`)

Step 1 is a **verbatim copy** of `../lexml-parser-projeto-lei/scripts/GeraCSVporArtigoPorAgrupador.xsl`,
committed on its own so that later diffs show only the amendments. Line numbers below refer to the
original.

### 3.1 Amendments

| # | Change | Original lines | Strategy doc |
|---|---|---|---|
| **X1** | New param `metadados` (full prefix, from Python). When `metadados` is empty, fall back to `normalize-space(//Epigrafe) \|\| ' \| ' \|\| normalize-space(//Ementa)`, for standalone use. `sigla` stays. | 14–15 | §6.1 |
| **X2** | Remove every `ancestor::*/NomeAgrupador` / `ancestor-or-self::*/NomeAgrupador` loop from the context of `CPT`, `PAR`, `ART` and the groupings. The prefix becomes `[ $metadados ]` for every `Tipo`. | 67, 78, 89, 99…159 | §6.1 |
| **X3** | Replace the six hand-written enumeration-context expressions with **one function** `lx:caminho($n)`. It walks `$n/ancestor::*[self::Artigo or self::Caput or self::Paragrafo or self::Inciso or self::Alinea or self::Item]` in document order and emits each ancestor's `Rotulo`, `TituloDispositivo` and `string()` of its **direct** `p` children. Use `string(p)`, never `p/text()`, so `span`/`Remissao` text is kept (bug at 182–183, 196). | 168–171, 181–184, 194–197 | §5.2 |
| **X3b** | In `lx:caminho`, when `$n` has a `Paragrafo` ancestor, insert `../Caput/p` (own `p` only) right after the article `Rotulo`. This applies to `PAR` rows too, whose context today is only the ementa. | 73–82 + X3 | §6.2 |
| **X4** | Replace the per-type content expressions (`descendant::p`, `descendant::p//text()\|descendant::Rotulo`, …) with **one function** `lx:texto($n)`: `$n`'s own `Rotulo`, `TituloDispositivo`, `p`, table text, then the same for every descendant, in document order. Groupings include their **own** `Rotulo` + `NomeAgrupador` (today `descendant::` skips the grouping's own label, which only reaches the text through the context loop removed by X2). `CPT`/`PAR` content gains the inciso/alínea labels that `descendant::p` drops today. | 65, 76, 87, 97…157, 167, 180, 193 | §6.1 |
| **X5** | Iterate `//Caput[parent::Artigo]` and `//Paragrafo[not(ancestor::Alteracao)]` independently, so a `Paragrafo` outside an `Artigo` (category B) gets a row and the nested loop no longer decides coverage. **Skip the `CPT` row when the article has no `Paragrafo`**, because its text would duplicate the `ART` row (see Q5). | 62–83 | §6.2, §6.3.2 |
| **X6** | In **every** document (category-B annexes, but also the 21 main documents and any A annex that have orphan dispositivos, §0): emit a **`DSP`** row for each `Caput`/`Paragrafo`/`Inciso`/`Alinea`/`Item` that has no dispositivo ancestor (not in `Alteracao`), with content `lx:texto(.)`, and treat it as the root of `lx:caminho` for its descendants. `Rotulo` column: `sigla, <Rotulo>` (e.g. `in_rfb_1717_20170717.anexo1, Item 3`). Descendant `INC`/`ALI`/`ITE`/`PAR` labels drop the empty `Art.` part. | new | §6.3.2 |
| **X7** | Build the `Rotulo` column in one `lx:rotulo($n)` function, which also fixes: the `ancestor::Subitulo` typo (135, 145, 155); the `caput, , Inciso` double comma in `ITE` (191); and `substring-before(Rotulo, ' –')` / `(Rotulo, ')')` / `(Rotulo, '.')`, which return `''` when the label uses `-`, `—` or no separator (replace with `replace(Rotulo, '^\s*([^\s–—\-).]+).*$', '$1')`). | 105–202 | — |
| **X8** | Serialize `table` descendants of a dispositivo into the text (format in §2.3), both as own content and as descendant content. Tables inside `Alteracao` follow the text: they are included in the text but get no rows. | new | — |
| **X9** | Pass all `Rotulo` column values through the `escape` template (today the label is written between raw quotes). | 63, 74, 85, … | — |
| **X10** | Performance: `calculaPos` counts `preceding::` nodes for every row (O(n²)). Time it on the largest files (`decreto_lei_5452_19430501.anexo1`, `decreto_9580_20181122.anexo1`, `decreto_3000_19990326`). Only if a file takes more than about 60 s, precompute positions with an `xsl:key`/accumulator that yields **identical** numbers (the regression test must still pass). | 53–58 | — |

Out of scope for the XSL (kept as is): `Alteracao` content gets no rows of its own; the main-document
`Preambulo`/`ParteFinal` are not segmented. The XSL always emits whole `ART`/`DSP` rows (it cannot
count tokens); rows above the 1,024-token cap are replaced by parts in a Python post-processing step
(§5b).

### 3.2 Worked target (acceptance fixture)

In `lei_9250_19951226.xml`, the `ITE` row for `art8_cpt_inc2_ali2_ite10` must equal the strategy
doc §5.2 example: `[ LEI Nº 9.250, … | Altera a Legislação … ] Art. 8º A base de cálculo … somas: II
– das deduções relativas: b) a pagamentos de despesas com instrução … até o limite anual individual
de: 10. R$ 3.561,50 …`. In the same file, `art8_par2` (`PAR`) must contain `Art. 8º`, the caput
sentence, and then `§ 2º O disposto na alínea a do inciso II: …`.

### 3.3 Driver (`run_xsl_segmentation.py`)

Adapted from `../lexml-parser-projeto-lei/scripts/run_segmentation_csv.py`, keeping its Saxon
setup, `is_lexml`, and report writing. Changes:

- It takes the **job list** from the orchestrator (`xml_path`, `out_csv`, `metadados`)
  instead of globbing a folder. It passes the parameters with
  `executable.set_parameter(name, proc.make_string_value(v))` and resets them per file.
- It writes one CSV per XML into `segmented/statutory/` and returns per-file `rows`,
  `max_num_final` (used for the loose-content offset, §2.4), duration and errors.
- The stylesheet is compiled once, and `--jobs N` can use a process pool (one Saxon processor per
  worker).

---

## 4. Annex router (`classify_annexes.py`)

It is the only place that decides which segmenter handles an annex.

**Input:** `lexml/articulados/*.anexo*.xml`. **Output:** `segmented/annex_manifest.csv` with
`arquivo, familia, pai, raiz, categoria, n_artigos, n_dispositivos_topo, n_soltos (p/table), segmentadores, metadados`.

**Classification rule** (elements inside `Alteracao` are ignored):

```
if  any Artigo                                     → A   (XSL)
elif any Item|Alinea|Inciso|Paragrafo|Caput        → B   (XSL; top-level dispositivos → DSP)
else                                               → C   (Python, full document)
and for A and B: if Articulacao/PartePrincipal/ParteInicial-Preambulo holds
    direct p or table children                     → also Python, loose-content mode
```

- The root element (`DocumentoArticulado` vs `DocumentoGenerico`) is recorded but **not used** to
  decide (strategy doc §4).
- **Parent resolution:** the family stem (`ANEXO_RE` from the original driver) gives `<stem>.xml` in
  `lexml/articulados/`. If that file is missing, the router strips `!anexoN` from the annex URN and
  looks for a main document with that `Identificacao/@URN`, first in `articulados/` and then in
  `nao_articulados/`. Unresolved parents are listed in the report, and the annex keeps only its own
  label as metadata.
- **Self-check:** the run fails loudly if the category counts differ from **A = 12 / B = 50 /
  C = 181** without the `--allow-count-change` flag. This catches silent changes after a re-parse.
- It also exposes `classify(path) -> AnnexDecision` for the orchestrator and the tests.

---

## 5. Non-statutory segmenter (`segment_non_statutory.py`, lxml)

### 5.1 Modes

- `--mode document`: a whole `nao_articulados` file or a category-C annex.
- `--mode loose --offset K --append <csv>`: only the direct `p`/`table` children of
  `Articulacao`/`PartePrincipal` (and an annex `Preambulo`) of an A/B annex, appended to the XSL CSV
  with numbering starting at `K`.

### 5.2 Units

| Source | Unit → `Tipo` |
|---|---|
| `Agrupamento[@nome in (texto, nota, preambulo, formulaPromulgacao, tituloAnexo)]` | `TXT` (split if needed) |
| `Agrupamento[@nome = ementa]` | in the prefix; also its own `TXT` if truncated there (§2.3) |
| `Agrupamento[@nome in (epigrafe)]` | prefix only |
| `Agrupamento[@nome in (assinatura, localDataFecho, preliminar)]` | dropped (signatures, dates, NUP/INTERESSADOS header lines); listed in the report (see Q4) |
| `table` (anywhere) | `TAB`, taken out of the surrounding text; the `p` right before it becomes its caption when it is shorter than 200 chars and does not end with `.` |
| `AgrupamentoHierarquico`, and `Livro`/`Capitulo`/… with no articles | no row of its own; its `Rotulo` + `NomeAgrupador` go into a heading line that starts each contained unit's `CONTEUDO` (non-statutory treatment is fixed across S1–S3, so this does not bias the comparison) |
| Runs of loose `p` in category C / loose mode | consecutive `p`s between tables or dispositivos form one `TXT` unit |
| `Bloco` | ignored (empty ordering marker) |

### 5.3 Splitting to the token cap

- Cap = `--max-tokens` (**1,024**, §2.6), counted on the **full** `Texto`, prefix included, with the
  reference tokenizer.
- **Text:** join `p` lines with spaces. If the unit is over the cap, cut it greedily at the last line
  boundary that ends with `.`, `;`, `:` or a paragraph number such as `12.`, keeping each part under
  the cap. If no such boundary exists, cut at a line boundary, then at a word boundary. No overlap
  (see Q3). Each part is a `TXT` row (`Rotulo` gets `, parte k/n`).
- **Tables:** header = the first row, plus the second when the first is a single spanning title
  (`colspan` = column count). If the table is over the cap, pack consecutive rows into parts and
  repeat caption + header in every part.
- **Oversize after splitting** (a single line or row above the cap) is kept, flagged, and counted in
  the report.

### 5.4 Tokenizer

`common.Tokenizer` accepts `chars:4` (≈ chars / 4, no dependency; for quick tests only),
`hf:<model>` (lazy `transformers` import, tokenizer files only), `tiktoken:<encoding>`, and
`max:<spec>,<spec>,…` (per-text maximum). The production default is the reference tokenizer of §2.6,
`max:tiktoken:cl100k_base,hf:Qwen/Qwen3-Embedding-4B`. Token counts are cached per text, because the
same texts are measured again when packing parts.

### 5.5 `Rotulo` column

`<sigla>, <nome do agrupamento or heading path>[, Tabela k][, parte i/n]`, where `sigla` is the file
stem. Example: `urn_lex_br_federal_parecer_2010_1503, I, parte 2/3`.

---

## 5b. Oversize article splitting (`split_oversize.py`)

The XSL cannot count tokens, so it always writes whole `ART`/`DSP` rows. A Python post-processing
step replaces each such row whose `Texto` is above the cap (§2.6) with parts built **along the
structure**, so every part is a self-contained piece of the article.

**Input:** a statutory CSV + its XML (the element is found through the `id` after the last `!` in
`urn`). **Output:** the same CSV, where each oversize `ART`/`DSP` row is replaced in place by its parts.
All other rows are unchanged.

**Algorithm** (greedy, in document order):

1. The article's split units are its direct dispositivo children, in order: `Caput` (own `p` +
   descendants) and each `Paragrafo`. For a `DSP`, they are its direct child dispositivos.
2. Pack consecutive units into a part while `Texto(part) ≤ cap`, where
   `Texto(part) = "[ " + METADADOS + " ] " + HEAD + units`, and `HEAD` is:
   - the article's `Rotulo` + `TituloDispositivo`;
   - plus the caput's own `p` when the part does not start with the caput. This is the same rule as
     X3b, so a part made of §§ 3–5 still reads "Art. 8º <caput sentence> § 3º …".
3. **A unit that is over the cap by itself** is replaced by its own children (incisos → alíneas →
   itens). These are packed the same way, with that unit's `CAMINHO` (ancestor path, §2.3) added to
   `HEAD`. For example, a part made of incisos XX–XXXV of the caput starts with
   "Art. 6º <caput sentence>".
4. **A leaf that is over the cap by itself** (no child dispositivos, ≈ 50 cases, mostly tables) is
   split within the leaf:
   - tables: by row groups with the caption and header repeated (as in §5.3);
   - text: at sentence boundaries, then at word boundaries;
   - every piece keeps `HEAD` + the leaf's path.
5. Parts keep the `Tipo` (`ART`/`DSP`), so the strategy filters (§2.2) are unchanged: S1 indexes the
   parts instead of the whole article.

**Columns of a part:**
- `Rotulo` = the original label + `, parte k/n` (e.g. `decreto_9580_20181122.anexo1, Art. 6º, parte 2/4`);
- `urn` = the original `urn` + `_p<k>`;
- `Num_Inicio`/`Num_Final` as in §2.4.

**Provenance sidecar.** The 6-column CSV cannot hold the part contents, so `split_oversize.py` writes
`<file>.prov.jsonl` next to the CSV, with one record per part:
`{urn, parte, n_partes, cobre_ids, parcial_ids}` (§2.7). `segment_non_statutory.py` writes the same
kind of sidecar for split `TXT`/`TAB` units and for synthetic loose-text ids. The provenance step
(§6 step 6) reads these files; a row without a sidecar record is an unsplit unit whose `cobre_ids`
is its own id.

The report lists each split article with its original token count, number of parts, and whether a
within-leaf split was needed.

**Consistency with the XSL text rules.** `split_oversize.py` rebuilds text from the XML, so
`common.py` carries Python versions of `lx:texto`, `lx:caminho` and table serialization (§2.3). A
**parity test** runs both implementations on every article that is *not* split and requires the
Python text to equal the XSL `ART` text. This keeps the two implementations from drifting apart.

**Scope.** Only the basic units (`ART`, `DSP`, `TXT`, `TAB`) are bounded by the cap. Sub-article rows
(`CPT`, `PAR`, `INC`, `ALI`, `ITE`) and groupings (`PRT`…`SSC`, S3 only) are not split. Their
over-cap counts are reported (see Q7).

---

## 6. Orchestrator (`segment_all.py`)

```
1. manifest = classify_annexes(lexml/articulados)                      # §4
2. jobs_xsl = main docs + A + B, each with metadados = common.metadata_for(file)
3. run_xsl_segmentation(jobs_xsl)             → segmented/statutory/*.csv
3b. split_oversize on every statutory CSV     (ART/DSP > 1,024 tokens → parts, §5b)
4. for A/B annexes with loose content:
       segment_non_statutory --mode loose --offset max_num_final+1 --append …
5. segment_non_statutory --mode document on lexml/nao_articulados/* and category C
                                              → segmented/non_statutory/*.csv
6. merge all CSVs into segmented/chunks_all.csv (+ arquivo, segmentador, categoria)
   and add the provenance columns (§2.7) from the XML + the .prov.jsonl sidecars
7. validate_segments → segmented/segmentation_report.{md,json}; non-zero exit on failure
```

Flags: `--only <glob>` to regenerate selected files, `--overwrite`, `--jobs`, `--max-tokens`
(default 1,024), `--tokenizer` (default: the reference tokenizer of §2.6), `--ementa-max-tokens`. The command line and the flag values are written into the
report, so every chunk set can be traced back to its parameters.

---

## 7. Validation (`validate_segments.py` + `tests/`)

**Structural checks (every run):**

- every CSV parses with 6 columns (`chunks_all.csv`: 6 + 3 + the §2.7 columns); no empty `Texto`;
  `chunk_id` is unique; `urn` is unique except where `id_ambiguo = 1`;
- **provenance:** every `unidade_id` and every id in `cobre_ids`/`parcial_ids` exists in the source
  XML (synthetic loose-text ids resolve to their `p` run); `artigo_id` and `agrupadores_ids` agree
  with the XML ancestors; the `cobre_ids` of an article's parts add up to all its dispositivos
  exactly once, and no part's `cobre_ids` overlap another's;
- within each `arquivo`, all intervals are nested or disjoint, and each `INC`/`ALI`/`ITE`/`PAR`
  interval lies inside its `ART`/`DSP` interval;
- **coverage:** one `ART` (or one complete set of parts `parte 1..n`) per `Artigo` outside
  `Alteracao`; the same for `DSP` per top-level dispositivo in B annexes; every non-dropped
  `Agrupamento` and `table` appears in at least one row;
- **cap:** every `ART`, `DSP`, `TXT` and `TAB` row is ≤ 1,024 reference tokens. The only exception is a
  single sentence, table row or word that cannot be cut further; these are listed and must be under
  8,192;
- **split completeness:** the parts of a split article together contain every dispositivo of that
  article exactly once (leaf pieces count as one);
- **text coverage:** for each file, the characters of the S1 chunk bodies (prefix removed) are at
  least 98 % of the document's text characters outside `Alteracao`, the preamble and the dropped
  `Agrupamento`s. This catches dropped tables or labels.

**Statistics in the report:** rows per `Tipo`, per strategy (expected S1 ≈ 19.4 k + DSP + NS,
S2 ≈ 88 k, S3 ≈ 94 k; strategy doc §5; S1 grows by the extra parts of split articles), per
category; token-length percentiles per `Tipo` and per tokenizer; the split articles (§5b); the
over-cap counts of the sub-article and grouping rows (Q7); the Gemini `countTokens` sample check
(§2.6).

**Tests (pytest, fixtures copied from `lexml/`):**

| Test | Fixture |
|---|---|
| XSL regression: for the unchanged `Tipo`s, the `(Tipo, Num_Inicio, Num_Final, urn)` sets of the original and the amended XSL are identical, except for the `CPT` rows removed by X5 | `lei_9250_19951226.xml`, `decreto_9580_20181122.anexo1.xml` |
| §3.2 worked target (`ITE` art8…ite10, `PAR` art8_par2) | `lei_9250_19951226.xml` |
| Remission text kept in the enumeration context (X3) | a `p` with `span` inside an inciso of `lei_9250` |
| Table inside a dispositivo is serialized (X8) | `decreto_3000_19990326.xml` (one article with a table) |
| Orphan dispositivos: `DSP` rows, orphan `Paragrafo` gets a row, no empty `Art.` label | `in_rfb_1548_20150213.anexo11.xml`, `decreto_8289_20140725.anexo1.xml` |
| Router categories + loose-content flag | one file per category, plus `in_srf_256_20021211.anexo2.xml` |
| Non-statutory: epígrafe/ementa extraction, dropped agrupamentos, split respects the cap, table header repetition | `urn_lex_br_federal_parecer_2010_1503.xml`, `ade_rfb_3_20240402.anexo1.xml` |
| Loose-mode offset keeps the intervals disjoint | `decreto_9580_20181122.anexo1.xml` |
| Provenance: `cobre_ids`/`parcial_ids` of split parts; `id_ambiguo` on duplicated ids; `DSP` + provenance for orphan dispositivos in a main document; synthetic loose-text ids | a split article (as below), `circ_bc_3432_20090203.xml` (duplicate `art16`, orphan `par1u`), `decreto_67542_19701112.xml`, `in_rfb_1500_20141029.anexo8.xml` |
| Python/XSL text parity on non-split articles (§5b) | `lei_9250_19951226.xml`, `decreto_3000_19990326.xml` (tables) |
| Article split: parts ≤ cap, caput sentence repeated in `HEAD`, descent into incisos, within-leaf table split with header repeated, disjoint part intervals, dispositivo coverage | the largest articles of `decreto_9580_20181122.anexo1.xml` and `decreto_3000_19990326.xml` (pick by length when building fixtures) |

---

## 8. Work order

| Step | Content | Done when |
|---|---|---|
| 1 | Copy the XSL and the driver verbatim into `scripts/segmentation/`; run the original on the corpus into a scratch folder as the regression baseline | Commit "verbatim copy" |
| 2 | Install `tiktoken` + `transformers`; `common.py` (metadata, CSV writer, reference tokenizer) + `classify_annexes.py` | Manifest reproduces A/B/C = 12/50/181; parents resolved |
| 3 | XSL X1–X2, X4, X7, X9 (template, content and labels) | Regression + label tests pass |
| 4 | XSL X3/X3b (ancestor path + caput for paragraphs) | §3.2 target test passes |
| 5 | XSL X5, X6, X8 (orphan dispositivos → `DSP`, CPT rule, tables); X10 only if needed | Orphan-dispositivo and table tests pass |
| 6 | `segment_non_statutory.py`, document mode, then loose mode | Non-statutory tests pass |
| 6b | Python `texto`/`caminho` in `common.py` + `split_oversize.py` | Parity and split tests pass |
| 7 | `segment_all.py` + `validate_segments.py`, full run; Gemini `countTokens` sample check | Report clean; counts near the strategy doc §5 estimates; no chunk over the cap except the listed uncuttable ones |
| 8 | Dated note in `docs/` with the final counts and length distributions; update the strategy doc §4/§5 numbers if they differ | — |

---

## 9. Open questions (defaults used until decided)

- **Q1 – Reference tokenizer and cap.** **Decided (2026-09-24):** 1,024 tokens, applied to
  `TXT`/`TAB` and to `ART`/`DSP` (articles above it are split, §5b); tokenizer = per-text maximum of
  `cl100k_base` and the Qwen3 tokenizer, checked against Gemini on a sample (§2.6).
- **Q2 – Ementa length in the prefix.** Solução-de-consulta ementas can be long; a full ementa on
  every chunk would dominate short chunks. Default: truncate to 128 tokens in the prefix, and keep
  the full ementa as its own chunk.
- **Q3 – Overlap between split parts.** Default: none (parts carry the same prefix and heading line).
- **Q4 – Dropped `Agrupamento`s** (`assinatura`, `localDataFecho`, `preliminar`). `preliminar` holds
  the NUP/INTERESSADOS/ASSUNTO header lines; `ASSUNTO` is already reachable through the metadata
  fallback. Default: drop all three.
- **Q5 – `CPT` for caput-only articles.** Default: not emitted, since it would duplicate `ART` in
  S2/S3. The regression test accounts for it.
- **Q6 – Main-document `Preambulo`.** Default: not segmented (enacting formula, as in the original
  XSL). Annex preambles are segmented, because in category B they can hold substantive text (e.g.
  `decreto_9358_20180430.anexo2`).
- **Q7 – Over-cap sub-article and grouping rows.** A `CPT`/`PAR` with many incisos, or a grouping in
  S3, can exceed 1,024 tokens. Only the largest ones can approach 8,192 (the longest article has
  ≈ 32.7 k chars), and the report flags any that do. Default: not split, because in S2
  their children are indexed as well, and the groupings belong only to the optional S3. The report
  counts them. If many exceed the cap, apply the §5b algorithm to them too (the parts would keep
  their own `Tipo`).
